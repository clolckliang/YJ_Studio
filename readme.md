# 嵌入式C串口通信协议重构文档



## 协议概述

这是一个支持两种校验模式的串口通信协议：
1. **原始求和/累加校验模式**(Original Sum/Add)
2. **CRC-16/CCITT-FALSE校验模式**

协议特点：
- 固定帧头(0xAB)
- 支持设备地址和目标地址
- 可变长度数据负载
- 两种可选的校验机制
- 环形缓冲区接收机制
- 小端字节序数据打包/解包

## 文件1: yj_protocol_config.h (配置头文件)

```c
#ifndef YJ_PROTOCOL_CONFIG_H
#define YJ_PROTOCOL_CONFIG_H

#include <stdint.h>

/* 校验模式配置 */
typedef enum {
    YJ_CHECKSUM_MODE_ORIGINAL = 0, // 原始求和/累加校验模式
    YJ_CHECKSUM_MODE_CRC16 = 1     // CRC-16/CCITT-FALSE校验模式
} yj_checksum_mode_t;

/* 选择当前设备使用的校验模式 */
// 可以在编译前修改，或者改为运行时变量(需要修改yj_protocol_handler_t和初始化函数)
#define YJ_ACTIVE_CHECKSUM_MODE  YJ_CHECKSUM_MODE_ORIGINAL // 或 YJ_CHECKSUM_MODE_CRC16

/* 基本配置 */
#define YJ_DEFAULT_DEVICE_ADDRESS    0x01   // 默认设备地址
#define YJ_DEFAULT_HOST_ADDRESS      0x02   // 默认主机地址
#define YJ_FRAME_HEAD_BYTE           0xAB   // 帧头字节

/* 缓冲区大小配置 */
#define YJ_MAX_DATA_PAYLOAD_SIZE     256    // 最大数据负载大小
#define YJ_RX_BUFFER_SIZE            ((6 + YJ_MAX_DATA_PAYLOAD_SIZE + 2) * 2) // 接收缓冲区大小

/* 物理层抽象(函数指针类型定义) */
typedef int32_t (*yj_send_byte_func_t)(uint8_t byte);  // 发送单字节函数类型
typedef int32_t (*yj_recv_byte_func_t)(uint8_t* byte, uint32_t timeout_ms); // 接收单字节函数类型

/* 调试输出配置 */
// #define YJ_ENABLE_DEBUG_PRINTF
#ifdef YJ_ENABLE_DEBUG_PRINTF
    #include <stdio.h> // 或自定义的printf头文件
    #define YJ_DEBUG_LOG(format, ...) printf(format, ##__VA_ARGS__)
#else
    #define YJ_DEBUG_LOG(format, ...) ((void)0)
#endif

#endif // YJ_PROTOCOL_CONFIG_H
```

## 文件2: yj_protocol.h (协议API和结构体定义)

```c
#ifndef YJ_PROTOCOL_H
#define YJ_PROTOCOL_H

#include <stdint.h>
#include <stddef.h> // 用于size_t
#include "yj_protocol_config.h" // 用户配置和yj_checksum_mode_t
/**
 * @file yj_protocol.h
 * @brief YJ串口通信协议API接口
 * @version 2.0
 * @date 2025
 * 
 * 本文件定义了协议的数据结构、状态机和API接口
 * 
 * 协议帧格式:
 * +--------+--------+--------+---------+----------+-----------+------+----------+
 * | 帧头   | 源地址 | 目的地址| 功能码  | 长度低位 | 长度高位  | 数据 | 校验字段 |
 * | 1字节  | 1字节  | 1字节  | 1字节   | 1字节    | 1字节     | N字节| 2字节    |
 * +--------+--------+--------+---------+----------+-----------+------+----------+
 * 
 * 校验字段(2字节):
 * - 原始模式: [和校验][累加校验]
 * - CRC模式:  [CRC高位][CRC低位] (大端序)
 */
/* 帧结构常量定义 */
#define YJ_FRAME_OFFSET_HEAD         0    // 帧头偏移
#define YJ_FRAME_OFFSET_SADDR        1    // 源地址偏移
#define YJ_FRAME_OFFSET_DADDR        2    // 目标地址偏移
#define YJ_FRAME_OFFSET_FUNC_ID      3    // 功能ID偏移
#define YJ_FRAME_OFFSET_LEN_LOW      4    // 长度低字节偏移
#define YJ_FRAME_OFFSET_LEN_HIGH     5    // 长度高字节偏移
#define YJ_FRAME_OFFSET_DATA_START   6    // 数据起始偏移

#define YJ_FRAME_HEADER_SIZE         YJ_FRAME_OFFSET_DATA_START // 帧头大小
#define YJ_FRAME_CHECKSUM_FIELD_SIZE 2    // 校验和字段大小(固定2字节)
#define YJ_FRAME_MIN_OVERHEAD        (YJ_FRAME_HEADER_SIZE + YJ_FRAME_CHECKSUM_FIELD_SIZE) // 最小开销

#define YJ_MAX_FRAME_SIZE            (YJ_FRAME_MIN_OVERHEAD + YJ_MAX_DATA_PAYLOAD_SIZE) // 最大帧大小

/* 协议接收状态枚举 */
typedef enum {
    YJ_RX_STATE_WAIT_HEAD,            // 等待帧头
    YJ_RX_STATE_WAIT_SADDR,           // 等待源地址
    YJ_RX_STATE_WAIT_DADDR,           // 等待目标地址
    YJ_RX_STATE_WAIT_FUNC_ID,         // 等待功能ID
    YJ_RX_STATE_WAIT_LEN_LOW,         // 等待长度低字节
    YJ_RX_STATE_WAIT_LEN_HIGH,        // 等待长度高字节
    YJ_RX_STATE_WAIT_DATA,            // 等待数据
    YJ_RX_STATE_WAIT_CHECKSUM_BYTE1,  // 等待校验和字节1
    YJ_RX_STATE_WAIT_CHECKSUM_BYTE2   // 等待校验和字节2
} yj_rx_state_t;

/* 帧数据结构体 */
typedef struct {
    uint8_t head;       // 帧头(0xAB)
    uint8_t s_addr;     // 源地址
    uint8_t d_addr;     // 目标地址
    uint8_t func_id;    // 功能ID
    uint16_t data_len;  // 数据长度
    uint8_t data[YJ_MAX_DATA_PAYLOAD_SIZE]; // 数据负载
    uint8_t received_checksum_bytes[YJ_FRAME_CHECKSUM_FIELD_SIZE]; // 接收到的校验和字节
} yj_frame_t;

/* 协议处理实例结构体 */
typedef struct {
    /* 接收状态机 */
    yj_rx_state_t rx_state;             // 当前接收状态
    yj_frame_t    current_rx_frame;     // 当前接收帧
    uint16_t      rx_data_bytes_received; // 已接收数据字节数
  
    /* 校验模式相关 */
    yj_checksum_mode_t active_checksum_mode; // 当前校验模式
    uint8_t       rx_calc_original_sc;  // 原始求和校验计算值
    uint8_t       rx_calc_original_ac;  // 原始累加校验计算值
    uint16_t      rx_calc_crc16;        // CRC16计算值
  
    /* 接收环形缓冲区 */
    uint8_t       rx_circ_buffer[YJ_RX_BUFFER_SIZE]; // 环形缓冲区
    volatile uint16_t rx_circ_buffer_head;  // 缓冲区头指针
    volatile uint16_t rx_circ_buffer_tail;  // 缓冲区尾指针
    volatile uint16_t rx_circ_buffer_count; // 缓冲区数据计数
  
    /* 物理层和回调函数 */
    yj_send_byte_func_t send_byte_func; // 字节发送函数指针
    void (*frame_received_callback)(yj_frame_t* received_frame); // 帧接收回调函数
} yj_protocol_handler_t;

/* API函数声明 */

/**
 * @brief 初始化协议处理器
 * @param handler 协议处理器实例指针
 * @param send_byte_impl 字节发送函数指针
 * @param frame_received_cb 帧接收回调函数
 * @param mode 校验模式(YJ_CHECKSUM_MODE_ORIGINAL或YJ_CHECKSUM_MODE_CRC16)
 */
void yj_protocol_init(yj_protocol_handler_t* handler,
                      yj_send_byte_func_t send_byte_impl,
                      void (*frame_received_cb)(yj_frame_t* received_frame),
                      yj_checksum_mode_t mode);

/**
 * @brief 发送数据帧
 * @param handler 协议处理器实例指针
 * @param dest_addr 目标地址
 * @param func_id 功能ID
 * @param data 数据指针
 * @param data_len 数据长度
 * @return 0成功, 负数失败
 */
int32_t yj_protocol_send_frame(yj_protocol_handler_t* handler,
                               uint8_t dest_addr,
                               uint8_t func_id,
                               const uint8_t* data,
                               uint16_t data_len);

/**
 * @brief 处理接收到的字节
 * @param handler 协议处理器实例指针
 * @param byte_received 接收到的字节
 */
void yj_protocol_process_byte(yj_protocol_handler_t* handler, uint8_t byte_received);

/**
 * @brief 向接收环形缓冲区添加字节
 * @param handler 协议处理器实例指针
 * @param byte_to_add 要添加的字节
 * @return 0成功, -1缓冲区已满
 */
int32_t yj_protocol_rx_buffer_add_byte(yj_protocol_handler_t* handler, uint8_t byte_to_add);

/**
 * @brief 协议处理器主循环处理函数
 * @param handler 协议处理器实例指针
 */
void yj_protocol_tick(yj_protocol_handler_t* handler);

/* 数据打包/解包辅助函数(小端字节序) */
void yj_pack_u16_le(uint8_t* buffer, uint16_t value);
uint16_t yj_unpack_u16_le(const uint8_t* buffer);
void yj_pack_i16_le(uint8_t* buffer, int16_t value);
int16_t yj_unpack_i16_le(const uint8_t* buffer);
void yj_pack_u32_le(uint8_t* buffer, uint32_t value);
uint32_t yj_unpack_u32_le(const uint8_t* buffer);
void yj_pack_i32_le(uint8_t* buffer, int32_t value);
int32_t yj_unpack_i32_le(const uint8_t* buffer);
void yj_pack_float_le(uint8_t* buffer, float value);
float yj_unpack_float_le(const uint8_t* buffer);

#endif // YJ_PROTOCOL_H
```

## 文件3: yj_protocol.c (协议实现)

```c
#include "yj_protocol.h"
#include <string.h> // 用于memcpy

/* 内部辅助函数: 原始求和/累加校验计算 */
static void calculate_original_checksums_internal(const uint8_t* frame_part_data, uint16_t length,
                                                  uint8_t* sum_check_out, uint8_t* add_check_out) {
    uint8_t sc = 0; // 求和校验
    uint8_t ac = 0; // 累加校验
    for (uint16_t i = 0; i < length; ++i) {
        sc = (sc + frame_part_data[i]) & 0xFF;
        ac = (ac + sc) & 0xFF;
    }
    *sum_check_out = sc;
    *add_check_out = ac;
}

/* 内部辅助函数: CRC-16/CCITT-FALSE计算 */
// 多项式: 0x1021 (x^16 + x^12 + x^5 + 1)
// 初始值: 0xFFFF
// 无输入反射, 无输出反射, 无最终XOR
static uint16_t crc16_ccitt_false_update(uint16_t crc, uint8_t data) {
    data ^= (uint8_t)(crc >> 8); // 使用CRC的高字节处理
    data ^= data >> 4;
    data ^= data >> 2;
    data ^= data >> 1;
    crc = (crc << 8) ^ ((uint16_t)data << 15) ^ ((uint16_t)data << 4) ^ ((uint16_t)data);
    return crc;
}

static uint16_t calculate_crc16_internal(const uint8_t* data_p, uint16_t length) {
    uint16_t crc = 0xFFFF; // 初始值
    while (length--) {
        crc = crc16_ccitt_false_update(crc, *data_p++);
    }
    return crc;
}

/* API函数实现 */

/**
 * @brief 初始化协议处理器
 */
void yj_protocol_init(yj_protocol_handler_t* handler,
                      yj_send_byte_func_t send_byte_impl,
                      void (*frame_received_cb)(yj_frame_t* received_frame),
                      yj_checksum_mode_t mode) {
    if (!handler || !send_byte_impl || !frame_received_cb) {
        YJ_DEBUG_LOG("错误: yj_protocol_init中的空指针\n");
        return;
    }
    memset(handler, 0, sizeof(yj_protocol_handler_t));

    handler->send_byte_func = send_byte_impl;
    handler->frame_received_callback = frame_received_cb;
    handler->rx_state = YJ_RX_STATE_WAIT_HEAD;
    handler->active_checksum_mode = mode; // 设置校验模式

    handler->rx_circ_buffer_head = 0;
    handler->rx_circ_buffer_tail = 0;
    handler->rx_circ_buffer_count = 0;

    YJ_DEBUG_LOG("YJ协议初始化完成. 模式: %s\n",
        (mode == YJ_CHECKSUM_MODE_CRC16) ? "CRC-16" : "原始求和/累加");
}

/**
 * @brief 发送数据帧
 */
int32_t yj_protocol_send_frame(yj_protocol_handler_t* handler,
                               uint8_t dest_addr,
                               uint8_t func_id,
                               const uint8_t* data,
                               uint16_t data_len) {
    if (!handler || !handler->send_byte_func) {
        YJ_DEBUG_LOG("错误: 处理器或send_byte_func未初始化\n");
        return -1;
    }
    if (data_len > YJ_MAX_DATA_PAYLOAD_SIZE) {
        YJ_DEBUG_LOG("错误: 数据长度 %u 超过最大值 %u\n", data_len, YJ_MAX_DATA_PAYLOAD_SIZE);
        return -2;
    }

    uint8_t frame_buffer[YJ_MAX_FRAME_SIZE];
    uint16_t current_idx = 0;

    // 1. 构建帧头
    frame_buffer[current_idx++] = YJ_FRAME_HEAD_BYTE;
    frame_buffer[current_idx++] = YJ_DEFAULT_DEVICE_ADDRESS;
    frame_buffer[current_idx++] = dest_addr;
    frame_buffer[current_idx++] = func_id;

    // 2. 数据长度(小端字节序)
    frame_buffer[current_idx++] = (uint8_t)(data_len & 0xFF);
    frame_buffer[current_idx++] = (uint8_t)((data_len >> 8) & 0xFF);

    // 3. 数据负载
    if (data && data_len > 0) {
        memcpy(&frame_buffer[current_idx], data, data_len);
        current_idx += data_len;
    }

    // 4. 根据当前校验模式计算并附加校验和
    if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
        uint16_t calculated_crc = calculate_crc16_internal(frame_buffer, current_idx);
        // 附加CRC(大端字节序: MSB在前)
        frame_buffer[current_idx++] = (uint8_t)((calculated_crc >> 8) & 0xFF); // MSB
        frame_buffer[current_idx++] = (uint8_t)(calculated_crc & 0xFF);        // LSB
        YJ_DEBUG_LOG("发送帧, CRC: 0x%04X ", calculated_crc);
    } else { // 原始求和/累加校验模式
        uint8_t sc, ac;
        calculate_original_checksums_internal(frame_buffer, current_idx, &sc, &ac);
        frame_buffer[current_idx++] = sc;
        frame_buffer[current_idx++] = ac;
        YJ_DEBUG_LOG("发送帧, SC:0x%02X AC:0x%02X ", sc, ac);
    }

    // 5. 发送帧
    YJ_DEBUG_LOG("(共 %u 字节)\n", current_idx);
    for (uint16_t i = 0; i < current_idx; ++i) {
        if (handler->send_byte_func(frame_buffer[i]) != 0) {
            YJ_DEBUG_LOG("错误: 发送字节 %u 失败\n", i);
            return -3;
        }
    }
    return 0; // 成功
}

/**
 * @brief 处理接收到的字节
 */
void yj_protocol_process_byte(yj_protocol_handler_t* handler, uint8_t byte_received) {
    if (!handler) return;

    switch (handler->rx_state) {
        case YJ_RX_STATE_WAIT_HEAD:
            if (byte_received == YJ_FRAME_HEAD_BYTE) {
                handler->current_rx_frame.head = byte_received;
                if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                    handler->rx_calc_crc16 = 0xFFFF; // 初始化CRC
                    handler->rx_calc_crc16 = crc16_ccitt_false_update(handler->rx_calc_crc16, byte_received);
                } else {
                    handler->rx_calc_original_sc = byte_received;
                    handler->rx_calc_original_ac = byte_received;
                }
                handler->rx_state = YJ_RX_STATE_WAIT_SADDR;
            }
            break;

        case YJ_RX_STATE_WAIT_SADDR:
            handler->current_rx_frame.s_addr = byte_received;
            if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                handler->rx_calc_crc16 = crc16_ccitt_false_update(handler->rx_calc_crc16, byte_received);
            } else {
                handler->rx_calc_original_sc = (handler->rx_calc_original_sc + byte_received) & 0xFF;
                handler->rx_calc_original_ac = (handler->rx_calc_original_ac + handler->rx_calc_original_sc) & 0xFF;
            }
            handler->rx_state = YJ_RX_STATE_WAIT_DADDR;
            break;

        case YJ_RX_STATE_WAIT_DADDR:
            handler->current_rx_frame.d_addr = byte_received;
            // 可选: 在此处添加地址过滤逻辑
            if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                handler->rx_calc_crc16 = crc16_ccitt_false_update(handler->rx_calc_crc16, byte_received);
            } else {
                handler->rx_calc_original_sc = (handler->rx_calc_original_sc + byte_received) & 0xFF;
                handler->rx_calc_original_ac = (handler->rx_calc_original_ac + handler->rx_calc_original_sc) & 0xFF;
            }
            handler->rx_state = YJ_RX_STATE_WAIT_FUNC_ID;
            break;

        case YJ_RX_STATE_WAIT_FUNC_ID:
            handler->current_rx_frame.func_id = byte_received;
            if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                handler->rx_calc_crc16 = crc16_ccitt_false_update(handler->rx_calc_crc16, byte_received);
            } else {
                handler->rx_calc_original_sc = (handler->rx_calc_original_sc + byte_received) & 0xFF;
                handler->rx_calc_original_ac = (handler->rx_calc_original_ac + handler->rx_calc_original_sc) & 0xFF;
            }
            handler->rx_state = YJ_RX_STATE_WAIT_LEN_LOW;
            break;

        case YJ_RX_STATE_WAIT_LEN_LOW:
            handler->current_rx_frame.data_len = byte_received; // LSB
            if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                handler->rx_calc_crc16 = crc16_ccitt_false_update(handler->rx_calc_crc16, byte_received);
            } else {
                handler->rx_calc_original_sc = (handler->rx_calc_original_sc + byte_received) & 0xFF;
                handler->rx_calc_original_ac = (handler->rx_calc_original_ac + handler->rx_calc_original_sc) & 0xFF;
            }
            handler->rx_state = YJ_RX_STATE_WAIT_LEN_HIGH;
            break;

        case YJ_RX_STATE_WAIT_LEN_HIGH:
            handler->current_rx_frame.data_len |= ((uint16_t)byte_received << 8); // MSB
            if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                handler->rx_calc_crc16 = crc16_ccitt_false_update(handler->rx_calc_crc16, byte_received);
            } else {
                handler->rx_calc_original_sc = (handler->rx_calc_original_sc + byte_received) & 0xFF;
                handler->rx_calc_original_ac = (handler->rx_calc_original_ac + handler->rx_calc_original_sc) & 0xFF;
            }

            if (handler->current_rx_frame.data_len > YJ_MAX_DATA_PAYLOAD_SIZE) {
                YJ_DEBUG_LOG("接收错误: 数据长度 %u 超过最大值 %u. 重置状态.\n",
                             handler->current_rx_frame.data_len, YJ_MAX_DATA_PAYLOAD_SIZE);
                handler->rx_state = YJ_RX_STATE_WAIT_HEAD;
            } else if (handler->current_rx_frame.data_len == 0) {
                handler->rx_state = YJ_RX_STATE_WAIT_CHECKSUM_BYTE1; // 无数据,直接跳转到校验和
            } else {
                handler->rx_data_bytes_received = 0;
                handler->rx_state = YJ_RX_STATE_WAIT_DATA;
            }
            break;

        case YJ_RX_STATE_WAIT_DATA:
            handler->current_rx_frame.data[handler->rx_data_bytes_received++] = byte_received;
            if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                handler->rx_calc_crc16 = crc16_ccitt_false_update(handler->rx_calc_crc16, byte_received);
            } else {
                handler->rx_calc_original_sc = (handler->rx_calc_original_sc + byte_received) & 0xFF;
                handler->rx_calc_original_ac = (handler->rx_calc_original_ac + handler->rx_calc_original_sc) & 0xFF;
            }

            if (handler->rx_data_bytes_received >= handler->current_rx_frame.data_len) {
                handler->rx_state = YJ_RX_STATE_WAIT_CHECKSUM_BYTE1;
            }
            break;

        case YJ_RX_STATE_WAIT_CHECKSUM_BYTE1:
            handler->current_rx_frame.received_checksum_bytes[0] = byte_received;
            handler->rx_state = YJ_RX_STATE_WAIT_CHECKSUM_BYTE2;
            break;

        case YJ_RX_STATE_WAIT_CHECKSUM_BYTE2:
            handler->current_rx_frame.received_checksum_bytes[1] = byte_received;
            uint8_t is_checksum_valid = 0;

            if (handler->active_checksum_mode == YJ_CHECKSUM_MODE_CRC16) {
                // 接收到的CRC是大端字节序: byte1是MSB, byte2是LSB
                uint16_t received_crc = ((uint16_t)handler->current_rx_frame.received_checksum_bytes[0] << 8) |
                                         handler->current_rx_frame.received_checksum_bytes[1];
                if (received_crc == handler->rx_calc_crc16) {
                    is_checksum_valid = 1;
                } else {
                    YJ_DEBUG_LOG("接收CRC错误! 接收CRC:0x%04X, 计算CRC:0x%04X\n",
                                 received_crc, handler->rx_calc_crc16);
                }
            } else { // 原始求和/累加校验模式
                uint8_t received_sc = handler->current_rx_frame.received_checksum_bytes[0];
                uint8_t received_ac = handler->current_rx_frame.received_checksum_bytes[1];
                if (received_sc == handler->rx_calc_original_sc &&
                    received_ac == handler->rx_calc_original_ac) {
                    is_checksum_valid = 1;
                } else {
                    YJ_DEBUG_LOG("接收原始校验错误! 接收SC:0x%02X 计算SC:0x%02X | 接收AC:0x%02X 计算AC:0x%02X\n",
                                 received_sc, handler->rx_calc_original_sc,
                                 received_ac, handler->rx_calc_original_ac);
                }
            }

            if (is_checksum_valid) {
                YJ_DEBUG_LOG("接收帧校验成功(模式:%d). 功能ID:0x%02X, 长度:%u\n",
                             handler->active_checksum_mode, handler->current_rx_frame.func_id, handler->current_rx_frame.data_len);
                if (handler->frame_received_callback) {
                    handler->frame_received_callback(&(handler->current_rx_frame));
                }
            }
            handler->rx_state = YJ_RX_STATE_WAIT_HEAD; // 重置状态等待下一帧
            break;

        default: // 不应该发生的情况
            handler->rx_state = YJ_RX_STATE_WAIT_HEAD;
            break;
    }
}

/**
 * @brief 向接收环形缓冲区添加字节
 */
int32_t yj_protocol_rx_buffer_add_byte(yj_protocol_handler_t* handler, uint8_t byte_to_add) {
    if (!handler) return -1;
    // 多线程/ISR访问时需要考虑临界区保护
    if (handler->rx_circ_buffer_count >= YJ_RX_BUFFER_SIZE) {
        YJ_DEBUG_LOG("错误: 接收环形缓冲区已满!\n");
        return -1;
    }
    handler->rx_circ_buffer[handler->rx_circ_buffer_head] = byte_to_add;
    handler->rx_circ_buffer_head = (handler->rx_circ_buffer_head + 1) % YJ_RX_BUFFER_SIZE;
    handler->rx_circ_buffer_count++;
    return 0;
}

/**
 * @brief 协议处理器主循环处理函数
 */
void yj_protocol_tick(yj_protocol_handler_t* handler) {
    if (!handler) return;
    uint8_t byte_from_buffer;
    // 多线程/ISR访问缓冲区计数/尾指针时需要考虑临界区保护
    while (handler->rx_circ_buffer_count > 0) {
        byte_from_buffer = handler->rx_circ_buffer[handler->rx_circ_buffer_tail];
        handler->rx_circ_buffer_tail = (handler->rx_circ_buffer_tail + 1) % YJ_RX_BUFFER_SIZE;
        handler->rx_circ_buffer_count--; // 成功获取字节后递减计数
        yj_protocol_process_byte(handler, byte_from_buffer);
    }
}

/* 数据打包/解包辅助函数(小端字节序) */

/**
 * @brief 打包16位无符号整数(小端字节序)
 */
void yj_pack_u16_le(uint8_t* buffer, uint16_t value) {
    buffer[0] = (uint8_t)(value & 0xFF);
    buffer[1] = (uint8_t)((value >> 8) & 0xFF);
}

/**
 * @brief 解包16位无符号整数(小端字节序)
 */
uint16_t yj_unpack_u16_le(const uint8_t* buffer) {
    return ((uint16_t)buffer[1] << 8) | buffer[0];
}

/**
 * @brief 打包16位有符号整数(小端字节序)
 */
void yj_pack_i16_le(uint8_t* buffer, int16_t value) {
    buffer[0] = (uint8_t)(value & 0xFF);
    buffer[1] = (uint8_t)((value >> 8) & 0xFF);
}

/**
 * @brief 解包16位有符号整数(小端字节序)
 */
int16_t yj_unpack_i16_le(const uint8_t* buffer) {
    return (int16_t)(((uint16_t)buffer[1] << 8) | buffer[0]);
}

/**
 * @brief 打包32位无符号整数(小端字节序)
 */
void yj_pack_u32_le(uint8_t* buffer, uint32_t value) {
    buffer[0] = (uint8_t)(value & 0xFF);
    buffer[1] = (uint8_t)((value >> 8) & 0xFF);
    buffer[2] = (uint8_t)((value >> 16) & 0xFF);
    buffer[3] = (uint8_t)((value >> 24) & 0xFF);
}

/**
 * @brief 解包32位无符号整数(小端字节序)
 */
uint32_t yj_unpack_u32_le(const uint8_t* buffer) {
    return ((uint32_t)buffer[3] << 24) | 
           ((uint32_t)buffer[2] << 16) | 
           ((uint32_t)buffer[1] << 8)  | 
           buffer[0];
}

/**
 * @brief 打包32位有符号整数(小端字节序)
 */
void yj_pack_i32_le(uint8_t* buffer, int32_t value) {
    buffer[0] = (uint8_t)(value & 0xFF);
    buffer[1] = (uint8_t)((value >> 8) & 0xFF);
    buffer[2] = (uint8_t)((value >> 16) & 0xFF);
    buffer[3] = (uint8_t)((value >> 24) & 0xFF);
}

/**
 * @brief 解包32位有符号整数(小端字节序)
 */
int32_t yj_unpack_i32_le(const uint8_t* buffer) {
    return (int32_t)(((uint32_t)buffer[3] << 24) | 
                     ((uint32_t)buffer[2] << 16) | 
                     ((uint32_t)buffer[1] << 8)  | 
                     buffer[0]);
}

/**
 * @brief 打包浮点数(小端字节序)
 */
void yj_pack_float_le(uint8_t* buffer, float value) {
    union {
        float f;
        uint32_t u;
    } converter;
    converter.f = value;
    yj_pack_u32_le(buffer, converter.u);
}

/**
 * @brief 解包浮点数(小端字节序)
 */
float yj_unpack_float_le(const uint8_t* buffer) {
    union {
        float f;
        uint32_t u;
    } converter;
    converter.u = yj_unpack_u32_le(buffer);
    return converter.f;
}
```

## 使用说明

### 初始化协议处理器

```c
#include "yj_protocol.h"

yj_protocol_handler_t my_handler;

// 帧接收回调函数
void my_frame_handler(yj_frame_t* received_frame) {
    // 处理接收到的帧
}

// 字节发送函数
int32_t my_send_byte(uint8_t byte) {
    // 实现字节发送逻辑
    return 0; // 成功返回0
}

int main() {
    // 初始化协议处理器
    yj_protocol_init(&my_handler, 
                    my_send_byte, 
                    my_frame_handler,
                    YJ_ACTIVE_CHECKSUM_MODE);
  
    while(1) {
        yj_protocol_tick(&my_handler); // 主循环中调用tick函数
    }
    return 0;
}
```

### 发送数据帧

```c
uint8_t data[] = {0x01, 0x02, 0x03};
yj_protocol_send_frame(&my_handler, 
                      0x02, // 目标地址
                      0x10, // 功能ID
                      data, 
                      sizeof(data));
```

### 接收数据处理

在UART中断服务例程中调用:

```c
void USART1_IRQHandler(void) {
    if(USART_GetITStatus(USART1, USART_IT_RXNE) != RESET) {
        uint8_t byte = USART_ReceiveData(USART1);
        yj_protocol_rx_buffer_add_byte(&my_handler, byte);
    }
}
```

## 注意事项

1. 在多线程环境中使用环形缓冲区时，需要添加适当的临界区保护
2. 校验模式需要在通信双方保持一致
3. 帧接收回调函数中应避免耗时操作
4. 调试输出可以通过定义YJ_ENABLE_DEBUG_PRINTF启用

这个协议实现提供了灵活的校验模式选择，支持两种不同的校验机制，可以根据实际需求进行配置。