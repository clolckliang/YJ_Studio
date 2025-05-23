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