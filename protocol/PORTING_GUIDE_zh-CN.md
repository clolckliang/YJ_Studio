# YJ串口通信协议移植指南

## 1. 协议概述
YJ协议是一个轻量级的串口通信协议，支持两种校验模式：
- 原始模式：求和校验(SC) + 累加校验(AC)
- CRC模式：CRC-16/CCITT-FALSE

### 帧格式
```
+--------+--------+--------+---------+----------+-----------+------+----------+
| 帧头   | 源地址 | 目的地址| 功能码  | 长度低位 | 长度高位  | 数据 | 校验字段 |
| 1字节  | 1字节  | 1字节  | 1字节   | 1字节    | 1字节     | N字节| 2字节    |
+--------+--------+--------+---------+----------+-----------+------+----------+
```

## 2. 移植准备

### 硬件需求
- 支持串口通信的MCU
- 至少512字节RAM（用于接收缓冲区）

### 软件需求
- C编译器支持C99标准
- 标准库头文件：`stdint.h`, `stddef.h`, `string.h`

## 3. 配置选项

编辑`yj_protocol_config.h`进行配置：

```c
/* 校验模式选择 */
#define YJ_ACTIVE_CHECKSUM_MODE  YJ_CHECKSUM_MODE_ORIGINAL 
// 或 YJ_CHECKSUM_MODE_CRC16

/* 地址配置 */
#define YJ_DEFAULT_DEVICE_ADDRESS    0x01   // 本机地址
#define YJ_DEFAULT_HOST_ADDRESS      0x02   // 主机地址

/* 缓冲区大小 */
#define YJ_MAX_DATA_PAYLOAD_SIZE     256    // 最大数据长度
#define YJ_RX_BUFFER_SIZE            ((6 + YJ_MAX_DATA_PAYLOAD_SIZE + 2) * 2)
```

## 4. 移植步骤

1. 将以下文件添加到项目：
   - yj_protocol.h
   - yj_protocol.c 
   - yj_protocol_config.h

2. 实现字节发送函数：
```c
int32_t my_send_byte(uint8_t byte) {
    // 实现串口发送单字节
    return 0; // 成功返回0
}
```

3. 初始化协议处理器：
```c
yj_protocol_handler_t handler;
yj_protocol_init(&handler, 
                my_send_byte,
                my_frame_received_callback,
                YJ_CHECKSUM_MODE_CRC16);
```

4. 在串口接收中断中调用：
```c
void USART_IRQHandler(void) {
    uint8_t byte = USART_ReceiveData();
    yj_protocol_rx_buffer_add_byte(&handler, byte);
}
```

5. 在主循环中调用：
```c
while(1) {
    yj_protocol_tick(&handler);
    // 其他任务...
}
```

## 5. API使用说明

### 发送数据帧
```c
uint8_t data[] = {0x01, 0x02, 0x03};
yj_protocol_send_frame(&handler, 
                      0x02, // 目标地址
                      0x10, // 功能码
                      data, 
                      sizeof(data));
```

### 接收回调函数
```c
void my_frame_received_callback(yj_frame_t* frame) {
    // 处理接收到的帧
    printf("收到帧: 功能码=0x%02X, 长度=%u\n", 
           frame->func_id, frame->data_len);
}
```

## 6. 数据打包/解包

协议提供小端字节序的打包/解包函数：

```c
// 打包16位整数
uint8_t buf[2];
yj_pack_u16_le(buf, 0x1234); 

// 解包16位整数
uint16_t val = yj_unpack_u16_le(buf);
```

支持的数据类型：
- 16/32位有符号/无符号整数
- 浮点数

## 7. 调试技巧

1. 启用调试输出：
```c
#define YJ_ENABLE_DEBUG_PRINTF
```

2. 常见错误：
- 校验和错误：检查两端校验模式是否一致
- 缓冲区满：增大`YJ_RX_BUFFER_SIZE`
- 帧长度错误：检查`YJ_MAX_DATA_PAYLOAD_SIZE`

## 8. 注意事项

1. 多线程/中断环境下：
- 需要保护环形缓冲区的访问
- 建议禁用中断操作缓冲区指针

2. 性能考虑：
- CRC模式计算量较大，低端MCU慎用
- 大数据传输建议分帧发送

3. 扩展建议(应用层实现，不修改协议)：

### 超时重传机制(应用层实现)
```c
// 在应用层维护发送队列和超时检测
typedef struct {
    uint8_t data[YJ_MAX_DATA_PAYLOAD_SIZE];
    uint16_t len;
    uint32_t send_time;
    uint8_t retry_count;
} yj_pending_frame_t;

yj_pending_frame_t pending_frames[5]; // 发送队列
uint8_t current_seq = 0; // 应用层序号

// 发送函数封装
int32_t yj_send_with_retry(yj_protocol_handler_t* handler, 
                          uint8_t dest, uint8_t func, 
                          const uint8_t* data, uint16_t len) {
    // 添加到发送队列
    pending_frames[current_seq % 5].send_time = get_current_time();
    memcpy(pending_frames[current_seq % 5].data, data, len);
    pending_frames[current_seq % 5].len = len;
    
    // 使用协议原始发送函数
    return yj_protocol_send_frame(handler, dest, func, data, len);
}

// 超时检测(在主循环中调用)
void yj_check_timeouts(yj_protocol_handler_t* handler) {
    for (int i = 0; i < 5; i++) {
        if (pending_frames[i].len > 0 && 
            (get_current_time() - pending_frames[i].send_time) > 1000) {
            if (pending_frames[i].retry_count < 3) {
                // 重传
                yj_protocol_send_frame(handler, dest, func, 
                                     pending_frames[i].data, pending_frames[i].len);
                pending_frames[i].retry_count++;
                pending_frames[i].send_time = get_current_time();
            }
        }
    }
}
```

### 帧序号防丢包(应用层实现)
```c
// 在应用层数据中包含序号
typedef struct {
    uint8_t seq;        // 应用层序号
    uint8_t data[YJ_MAX_DATA_PAYLOAD_SIZE - 1]; // 实际数据
} yj_app_data_t;

// 发送时封装序号
void yj_send_with_seq(yj_protocol_handler_t* handler, 
                     uint8_t dest, uint8_t func,
                     const uint8_t* data, uint16_t len) {
    static uint8_t seq = 0;
    yj_app_data_t app_data;
    app_data.seq = seq++;
    memcpy(app_data.data, data, len);
    
    yj_protocol_send_frame(handler, dest, func, (uint8_t*)&app_data, len + 1);
}

// 接收时处理序号
void my_frame_received_callback(yj_frame_t* frame) {
    yj_app_data_t* app_data = (yj_app_data_t*)frame->data;
    static uint8_t expected_seq = 0;
    
    if (app_data->seq != expected_seq) {
        // 处理丢包情况
    }
    expected_seq = app_data->seq + 1;
    
    // 处理实际数据
    process_data(app_data->data, frame->data_len - 1);
}
```
