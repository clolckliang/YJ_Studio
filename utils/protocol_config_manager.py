#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议配置管理器

负责加载、保存和管理协议相关的配置参数。
支持动态配置更新和配置验证。

作者: YJ Studio
日期: 2024
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from PySide6.QtCore import QObject, Signal

class ConfigError(Exception):
    """配置错误异常"""
    pass

class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ChecksumMode(Enum):
    """校验模式枚举"""
    ORIGINAL_SUM_ADD = "ORIGINAL_SUM_ADD"
    CRC16_CCITT_FALSE = "CRC16_CCITT_FALSE"

@dataclass
class FrameFormatConfig:
    """帧格式配置"""
    header_byte: str = "AB"
    default_source_addr: str = "01"
    default_dest_addr: str = "02"
    checksum_mode: str = "ORIGINAL_SUM_ADD"
    max_data_payload_size: int = 1024
    min_frame_length: int = 8

@dataclass
class AckMechanismConfig:
    """ACK机制配置"""
    enabled: bool = True
    default_timeout_ms: int = 1000
    max_retries: int = 3
    window_size: int = 8
    ack_func_id: str = "F0"
    nack_func_id: str = "F1"

@dataclass
class PerformanceConfig:
    """性能配置"""
    buffer_size: int = 65536
    max_frames_per_parse: int = 10
    parse_timeout_warning_ms: float = 5.0
    frame_timeout_warning_ms: float = 10.0
    buffer_usage_warning_percent: float = 90.0
    stats_update_interval_ms: int = 5000

@dataclass
class ErrorHandlingConfig:
    """错误处理配置"""
    auto_recovery: bool = True
    max_consecutive_errors: int = 10
    error_reset_timeout_ms: int = 5000
    log_level: str = "INFO"
    detailed_error_logging: bool = True

@dataclass
class OptimizationConfig:
    """优化配置"""
    enable_performance_monitoring: bool = True
    enable_buffer_optimization: bool = True
    enable_adaptive_timeout: bool = False
    memory_usage_limit_mb: int = 100
    cpu_usage_limit_percent: float = 80.0

@dataclass
class DebuggingConfig:
    """调试配置"""
    enable_frame_logging: bool = False
    enable_timing_analysis: bool = True
    enable_statistics_collection: bool = True
    log_raw_data: bool = False
    verbose_error_messages: bool = True

@dataclass
class NetworkSimulationConfig:
    """网络模拟配置"""
    packet_loss_rate: float = 0.1
    network_delay_ms: int = 10
    jitter_ms: int = 5
    enable_simulation: bool = False

@dataclass
class AdvancedFeaturesConfig:
    """高级功能配置"""
    enable_large_data_transfer: bool = True
    fragmentation_size: int = 512
    enable_compression: bool = False
    enable_encryption: bool = False
    flow_control: bool = True

@dataclass
class ProtocolSettings:
    """协议设置信息"""
    version: str = "1.0.0"
    description: str = "YJ Studio 增强协议配置"
    last_updated: str = "2024-01-01"

class ProtocolConfigManager(QObject):
    """协议配置管理器"""
    
    # 配置更新信号
    config_updated = Signal(str)  # config_section
    config_error = Signal(str)    # error_message
    
    def __init__(self, config_file_path: Optional[str] = None):
        super().__init__()
        
        # 默认配置文件路径
        if config_file_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            config_file_path = os.path.join(project_root, "config", "protocol_config.json")
        
        self.config_file_path = config_file_path
        
        # 初始化配置对象
        self.protocol_settings = ProtocolSettings()
        self.frame_format = FrameFormatConfig()
        self.ack_mechanism = AckMechanismConfig()
        self.performance = PerformanceConfig()
        self.error_handling = ErrorHandlingConfig()
        self.optimization = OptimizationConfig()
        self.debugging = DebuggingConfig()
        self.network_simulation = NetworkSimulationConfig()
        self.advanced_features = AdvancedFeaturesConfig()
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file_path):
                # 如果配置文件不存在，创建默认配置
                self.save_config()
                return True
            
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 更新配置对象
            self._update_config_from_dict(config_data)
            
            # 验证配置
            self._validate_config()
            
            return True
            
        except Exception as e:
            error_msg = f"加载配置文件失败: {str(e)}"
            self.config_error.emit(error_msg)
            return False
    
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            # 确保配置目录存在
            config_dir = os.path.dirname(self.config_file_path)
            os.makedirs(config_dir, exist_ok=True)
            
            # 构建配置字典
            config_data = {
                "protocol_settings": asdict(self.protocol_settings),
                "frame_format": asdict(self.frame_format),
                "ack_mechanism": asdict(self.ack_mechanism),
                "performance_settings": asdict(self.performance),
                "error_handling": asdict(self.error_handling),
                "optimization": asdict(self.optimization),
                "debugging": asdict(self.debugging),
                "network_simulation": asdict(self.network_simulation),
                "advanced_features": asdict(self.advanced_features)
            }
            
            # 保存到文件
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            error_msg = f"保存配置文件失败: {str(e)}"
            self.config_error.emit(error_msg)
            return False
    
    def _update_config_from_dict(self, config_data: Dict[str, Any]):
        """从字典更新配置对象"""
        # 更新协议设置
        if "protocol_settings" in config_data:
            settings_data = config_data["protocol_settings"]
            self.protocol_settings = ProtocolSettings(**settings_data)
        
        # 更新帧格式配置
        if "frame_format" in config_data:
            frame_data = config_data["frame_format"]
            self.frame_format = FrameFormatConfig(**frame_data)
        
        # 更新ACK机制配置
        if "ack_mechanism" in config_data:
            ack_data = config_data["ack_mechanism"]
            self.ack_mechanism = AckMechanismConfig(**ack_data)
        
        # 更新性能配置
        if "performance_settings" in config_data:
            perf_data = config_data["performance_settings"]
            self.performance = PerformanceConfig(**perf_data)
        
        # 更新错误处理配置
        if "error_handling" in config_data:
            error_data = config_data["error_handling"]
            self.error_handling = ErrorHandlingConfig(**error_data)
        
        # 更新优化配置
        if "optimization" in config_data:
            opt_data = config_data["optimization"]
            self.optimization = OptimizationConfig(**opt_data)
        
        # 更新调试配置
        if "debugging" in config_data:
            debug_data = config_data["debugging"]
            self.debugging = DebuggingConfig(**debug_data)
        
        # 更新网络模拟配置
        if "network_simulation" in config_data:
            net_data = config_data["network_simulation"]
            self.network_simulation = NetworkSimulationConfig(**net_data)
        
        # 更新高级功能配置
        if "advanced_features" in config_data:
            adv_data = config_data["advanced_features"]
            self.advanced_features = AdvancedFeaturesConfig(**adv_data)
    
    def _validate_config(self):
        """验证配置参数"""
        # 验证帧格式配置
        if len(self.frame_format.header_byte) != 2:
            raise ConfigError("帧头字节必须是2个十六进制字符")
        
        if self.frame_format.max_data_payload_size <= 0:
            raise ConfigError("最大数据负载大小必须大于0")
        
        # 验证ACK机制配置
        if self.ack_mechanism.default_timeout_ms <= 0:
            raise ConfigError("ACK超时时间必须大于0")
        
        if self.ack_mechanism.max_retries < 0:
            raise ConfigError("最大重试次数不能为负数")
        
        if self.ack_mechanism.window_size <= 0 or self.ack_mechanism.window_size > 32:
            raise ConfigError("窗口大小必须在1-32之间")
        
        # 验证性能配置
        if self.performance.buffer_size <= 0:
            raise ConfigError("缓冲区大小必须大于0")
        
        if self.performance.max_frames_per_parse <= 0:
            raise ConfigError("每次解析最大帧数必须大于0")
        
        # 验证优化配置
        if self.optimization.memory_usage_limit_mb <= 0:
            raise ConfigError("内存使用限制必须大于0")
        
        if not (0 <= self.optimization.cpu_usage_limit_percent <= 100):
            raise ConfigError("CPU使用限制必须在0-100之间")
    
    def update_frame_format(self, **kwargs):
        """更新帧格式配置"""
        for key, value in kwargs.items():
            if hasattr(self.frame_format, key):
                setattr(self.frame_format, key, value)
        
        self.config_updated.emit("frame_format")
    
    def update_ack_mechanism(self, **kwargs):
        """更新ACK机制配置"""
        for key, value in kwargs.items():
            if hasattr(self.ack_mechanism, key):
                setattr(self.ack_mechanism, key, value)
        
        self.config_updated.emit("ack_mechanism")
    
    def update_performance(self, **kwargs):
        """更新性能配置"""
        for key, value in kwargs.items():
            if hasattr(self.performance, key):
                setattr(self.performance, key, value)
        
        self.config_updated.emit("performance")
    
    def update_error_handling(self, **kwargs):
        """更新错误处理配置"""
        for key, value in kwargs.items():
            if hasattr(self.error_handling, key):
                setattr(self.error_handling, key, value)
        
        self.config_updated.emit("error_handling")
    
    def update_optimization(self, **kwargs):
        """更新优化配置"""
        for key, value in kwargs.items():
            if hasattr(self.optimization, key):
                setattr(self.optimization, key, value)
        
        self.config_updated.emit("optimization")
    
    def update_debugging(self, **kwargs):
        """更新调试配置"""
        for key, value in kwargs.items():
            if hasattr(self.debugging, key):
                setattr(self.debugging, key, value)
        
        self.config_updated.emit("debugging")
    
    def get_checksum_mode_enum(self):
        """获取校验模式枚举"""
        try:
            return ChecksumMode(self.frame_format.checksum_mode)
        except ValueError:
            return ChecksumMode.ORIGINAL_SUM_ADD
    
    def get_log_level_enum(self):
        """获取日志级别枚举"""
        try:
            return LogLevel(self.error_handling.log_level)
        except ValueError:
            return LogLevel.INFO
    
    def reset_to_defaults(self):
        """重置为默认配置"""
        self.protocol_settings = ProtocolSettings()
        self.frame_format = FrameFormatConfig()
        self.ack_mechanism = AckMechanismConfig()
        self.performance = PerformanceConfig()
        self.error_handling = ErrorHandlingConfig()
        self.optimization = OptimizationConfig()
        self.debugging = DebuggingConfig()
        self.network_simulation = NetworkSimulationConfig()
        self.advanced_features = AdvancedFeaturesConfig()
        
        self.config_updated.emit("all")
    
    def export_config(self, export_path: str) -> bool:
        """导出配置到指定路径"""
        try:
            original_path = self.config_file_path
            self.config_file_path = export_path
            result = self.save_config()
            self.config_file_path = original_path
            return result
        except Exception as e:
            self.config_error.emit(f"导出配置失败: {str(e)}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """从指定路径导入配置"""
        try:
            original_path = self.config_file_path
            self.config_file_path = import_path
            result = self.load_config()
            self.config_file_path = original_path
            
            if result:
                self.config_updated.emit("all")
            
            return result
        except Exception as e:
            self.config_error.emit(f"导入配置失败: {str(e)}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "protocol_version": self.protocol_settings.version,
            "checksum_mode": self.frame_format.checksum_mode,
            "ack_enabled": self.ack_mechanism.enabled,
            "buffer_size": self.performance.buffer_size,
            "performance_monitoring": self.optimization.enable_performance_monitoring,
            "debug_mode": self.debugging.enable_frame_logging,
            "config_file": self.config_file_path
        }

# 全局配置管理器实例
_global_config_manager = None

def get_global_config_manager() -> ProtocolConfigManager:
    """获取全局配置管理器实例"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ProtocolConfigManager()
    return _global_config_manager

def set_global_config_manager(config_manager: ProtocolConfigManager):
    """设置全局配置管理器实例"""
    global _global_config_manager
    _global_config_manager = config_manager