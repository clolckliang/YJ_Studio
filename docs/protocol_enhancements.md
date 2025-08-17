# YJ Studio 协议增强功能文档

## 概述

本文档描述了 YJ Studio 串口协议的增强功能，包括统一错误处理机制、重传和ACK机制、性能优化以及配置管理等功能。

## 主要功能

### 1. 统一错误处理机制

#### 错误类型枚举
```python
class ProtocolError(Enum):
    CHECKSUM_MISMATCH = "校验和不匹配"
    FRAME_TOO_LONG = "帧过长"
    INVALID_LENGTH = "长度无效"
    BUFFER_OVERFLOW = "缓冲区溢出"
    TIMEOUT = "超时"
    INVALID_SEQUENCE = "序列号无效"
```

#### 特性
- 统一的错误分类和处理
- 详细的错误日志记录
- 错误统计和分析
- 自动错误恢复机制

### 2. 重传和ACK机制

#### 核心特性
- **可靠传输**: 支持帧的确认和重传机制
- **滑动窗口**: 可配置的发送窗口大小
- **超时重传**: 可配置的超时时间和重试次数
- **序列号管理**: 自动管理帧序列号

#### 使用示例
```python
# 启用ACK机制
frame_parser.set_ack_enabled(True)
frame_parser.set_window_size(8)

# 发送需要ACK的帧
seq_num = frame_parser.send_frame_with_ack(
    dest_addr=0x02,
    func_id=0x01,
    data=b"test data",
    max_retries=3,
    timeout_ms=1000
)

# 处理ACK/NACK
frame_parser.handle_ack(seq_num)  # 确认
frame_parser.handle_nack(seq_num)  # 否定确认
```

### 3. 性能监控和优化

#### 监控指标
- 缓冲区使用率
- 帧解析耗时
- 重传次数
- 超时次数
- 错误统计

#### 性能优化
- 限制单次解析帧数，防止阻塞
- 缓冲区溢出保护
- 自适应性能警告
- 内存使用优化

#### 获取性能统计
```python
stats = frame_parser.get_performance_stats()
print(f"缓冲区使用率: {stats['buffer_usage_percent']:.1f}%")
print(f"待处理帧数: {stats['pending_frames_count']}")
print(f"解析帧总数: {stats['parsed_frame_count']}")
```

### 4. 配置管理系统

#### 配置文件结构
配置文件 `config/protocol_config.json` 包含以下部分：

- **protocol_settings**: 协议基本信息
- **frame_format**: 帧格式配置
- **ack_mechanism**: ACK机制配置
- **performance_settings**: 性能相关配置
- **error_handling**: 错误处理配置
- **optimization**: 优化选项
- **debugging**: 调试配置
- **network_simulation**: 网络模拟配置
- **advanced_features**: 高级功能配置

#### 配置管理器使用
```python
from utils.protocol_config_manager import ProtocolConfigManager

# 创建配置管理器
config_manager = ProtocolConfigManager()

# 动态修改配置
config_manager.update_ack_mechanism(default_timeout_ms=2000)
config_manager.update_performance(buffer_size=128*1024)

# 保存配置
config_manager.save_config()

# 获取配置摘要
summary = config_manager.get_config_summary()
```

## 配置参数说明

### 帧格式配置 (frame_format)
- `header_byte`: 帧头字节 (默认: "AB")
- `default_source_addr`: 默认源地址 (默认: "01")
- `default_dest_addr`: 默认目标地址 (默认: "02")
- `checksum_mode`: 校验模式 ("ORIGINAL_SUM_ADD" 或 "CRC16_CCITT_FALSE")
- `max_data_payload_size`: 最大数据负载大小 (默认: 1024)
- `min_frame_length`: 最小帧长度 (默认: 8)

### ACK机制配置 (ack_mechanism)
- `enabled`: 是否启用ACK机制 (默认: true)
- `default_timeout_ms`: 默认超时时间 (默认: 1000ms)
- `max_retries`: 最大重试次数 (默认: 3)
- `window_size`: 滑动窗口大小 (默认: 8)
- `ack_func_id`: ACK功能码 (默认: "F0")
- `nack_func_id`: NACK功能码 (默认: "F1")

### 性能配置 (performance_settings)
- `buffer_size`: 缓冲区大小 (默认: 65536)
- `max_frames_per_parse`: 单次解析最大帧数 (默认: 10)
- `parse_timeout_warning_ms`: 解析超时警告阈值 (默认: 5.0ms)
- `frame_timeout_warning_ms`: 单帧超时警告阈值 (默认: 10.0ms)
- `buffer_usage_warning_percent`: 缓冲区使用率警告阈值 (默认: 90.0%)
- `stats_update_interval_ms`: 统计更新间隔 (默认: 5000ms)

### 错误处理配置 (error_handling)
- `auto_recovery`: 自动错误恢复 (默认: true)
- `max_consecutive_errors`: 最大连续错误数 (默认: 10)
- `error_reset_timeout_ms`: 错误重置超时 (默认: 5000ms)
- `log_level`: 日志级别 (默认: "INFO")
- `detailed_error_logging`: 详细错误日志 (默认: true)

### 优化配置 (optimization)
- `enable_performance_monitoring`: 启用性能监控 (默认: true)
- `enable_buffer_optimization`: 启用缓冲区优化 (默认: true)
- `enable_adaptive_timeout`: 启用自适应超时 (默认: false)
- `memory_usage_limit_mb`: 内存使用限制 (默认: 100MB)
- `cpu_usage_limit_percent`: CPU使用限制 (默认: 80.0%)

## 使用指南

### 1. 基本使用

```python
from core.protocol_handler import FrameParser, ProtocolSender
from utils.protocol_config_manager import ProtocolConfigManager

# 创建配置管理器
config_manager = ProtocolConfigManager()

# 创建协议处理器
frame_parser = FrameParser(config_manager=config_manager)
protocol_sender = ProtocolSender(
    send_byte_func=your_send_function,
    frame_parser=frame_parser,
    config_manager=config_manager
)

# 发送数据
protocol_sender.send_frame(
    dest_addr=0x02,
    func_id=0x01,
    data=b"Hello, World!",
    require_ack=True
)
```

### 2. 配置自定义

```python
# 修改ACK配置
config_manager.update_ack_mechanism(
    enabled=True,
    default_timeout_ms=2000,
    max_retries=5,
    window_size=16
)

# 修改性能配置
config_manager.update_performance(
    buffer_size=128*1024,
    max_frames_per_parse=20,
    parse_timeout_warning_ms=10.0
)

# 保存配置
config_manager.save_config()
```

### 3. 错误处理

```python
# 连接错误信号
frame_parser.error_occurred.connect(handle_error)
frame_parser.analyzer.performance_warning.connect(handle_warning)

def handle_error(error_type, error_message):
    print(f"协议错误: {error_type} - {error_message}")

def handle_warning(warning_message):
    print(f"性能警告: {warning_message}")
```

### 4. 性能监控

```python
# 定期获取性能统计
def print_stats():
    stats = frame_parser.get_performance_stats()
    print(f"性能统计: {stats}")

# 设置定时器
timer = QTimer()
timer.timeout.connect(print_stats)
timer.start(5000)  # 每5秒打印一次
```

## 信号和事件

### FrameParser 信号
- `frame_successfully_parsed`: 帧解析成功
- `checksum_error`: 校验和错误
- `error_occurred`: 发生错误
- `ack_received`: 收到ACK
- `nack_received`: 收到NACK
- `retransmission_needed`: 需要重传

### ProtocolAnalyzer 信号
- `performance_warning`: 性能警告

### ProtocolSender 信号
- `frame_sent`: 帧发送成功
- `send_failed`: 发送失败

### ProtocolConfigManager 信号
- `config_updated`: 配置更新
- `config_error`: 配置错误

## 最佳实践

### 1. 配置管理
- 在应用启动时加载配置
- 根据实际需求调整缓冲区大小
- 定期保存配置更改
- 使用配置验证确保参数有效

### 2. 性能优化
- 监控缓冲区使用率，避免溢出
- 根据网络条件调整ACK超时时间
- 限制单次解析的帧数，防止UI阻塞
- 定期清理性能统计数据

### 3. 错误处理
- 实现适当的错误恢复机制
- 记录详细的错误日志用于调试
- 设置合理的错误阈值
- 提供用户友好的错误提示

### 4. 可靠性
- 根据网络质量调整重传参数
- 使用适当的窗口大小平衡性能和可靠性
- 实现超时处理避免死锁
- 定期检查和清理超时帧

## 故障排除

### 常见问题

1. **配置文件加载失败**
   - 检查文件路径是否正确
   - 验证JSON格式是否有效
   - 确保有读取权限

2. **ACK机制不工作**
   - 确认ACK机制已启用
   - 检查功能码配置是否正确
   - 验证序列号管理

3. **性能问题**
   - 检查缓冲区大小设置
   - 调整单次解析帧数限制
   - 监控内存使用情况

4. **重传过多**
   - 增加超时时间
   - 检查网络连接质量
   - 调整重试次数

### 调试技巧

1. **启用详细日志**
   ```python
   config_manager.update_debugging(
       enable_frame_logging=True,
       verbose_error_messages=True,
       log_raw_data=True
   )
   ```

2. **性能分析**
   ```python
   config_manager.update_debugging(
       enable_timing_analysis=True,
       enable_statistics_collection=True
   )
   ```

3. **网络模拟**
   ```python
   config_manager.update_network_simulation(
       enable_simulation=True,
       packet_loss_rate=0.1,
       network_delay_ms=50
   )
   ```

## 版本历史

### v1.0.0 (2024-01-01)
- 初始版本
- 基本协议功能
- 简单错误处理

### v1.1.0 (2024-01-15)
- 添加ACK重传机制
- 性能监控功能
- 统一错误处理

### v1.2.0 (2024-01-30)
- 配置管理系统
- 高级性能优化
- 调试和诊断工具

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

## 联系方式

如有问题或建议，请联系 YJ Studio 开发团队。