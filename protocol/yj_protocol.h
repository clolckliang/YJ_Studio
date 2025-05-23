#ifndef YJ_PROTOCOL_H
#define YJ_PROTOCOL_H

#include <stdint.h>
#include <stddef.h> // 用于size_t
#include "yj_protocol_config.h" // 用户配置和yj_checksum_mode_t
/**
 * @file yj_protocol.h
 * @brief YJ串口通信协议API接口
 * @version 2.0
 * @date 2024
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