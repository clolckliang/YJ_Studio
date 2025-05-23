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