"""配置访问辅助模块

提供简化的配置访问接口，避免重复的hasattr检查
"""

from typing import Any, Optional, Union, Dict
from utils.protocol_config_manager import ProtocolConfigManager


class ConfigAccessor:
    """配置访问辅助类，提供简化的配置访问接口"""
    
    def __init__(self, config_manager: Optional[ProtocolConfigManager] = None):
        self._config_manager = config_manager
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = True
    
    def get(self, path: str, default: Any = None, use_cache: bool = True) -> Any:
        """获取配置值
        
        Args:
            path: 配置路径，使用点号分隔，如 'performance.buffer_size'
            default: 默认值
            use_cache: 是否使用缓存
            
        Returns:
            配置值或默认值
        """
        if not self._config_manager:
            return default
            
        # 检查缓存
        if use_cache and self._cache_enabled and path in self._cache:
            return self._cache[path]
            
        try:
            value = self._get_nested_value(self._config_manager, path)
            if value is not None:
                # 缓存结果
                if use_cache and self._cache_enabled:
                    self._cache[path] = value
                return value
        except (AttributeError, KeyError):
            pass
            
        return default
    
    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """获取嵌套属性值"""
        parts = path.split('.')
        current = obj
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                return None
                
        return current
    
    def has(self, path: str) -> bool:
        """检查配置是否存在"""
        if not self._config_manager:
            return False
            
        try:
            value = self._get_nested_value(self._config_manager, path)
            return value is not None
        except (AttributeError, KeyError):
            return False
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def enable_cache(self, enabled: bool = True):
        """启用或禁用缓存"""
        self._cache_enabled = enabled
        if not enabled:
            self.clear_cache()
    
    def update_config_manager(self, config_manager: Optional[ProtocolConfigManager]):
        """更新配置管理器"""
        self._config_manager = config_manager
        self.clear_cache()


class PerformanceConfig:
    """性能配置访问器"""
    
    def __init__(self, accessor: ConfigAccessor):
        self._accessor = accessor
    
    @property
    def buffer_size(self) -> int:
        return self._accessor.get('performance.buffer_size', 1024 * 32)
    
    @property
    def buffer_usage_warning_percent(self) -> float:
        return self._accessor.get('performance.buffer_usage_warning_percent', 90.0)
    
    @property
    def max_frames_per_parse(self) -> int:
        return self._accessor.get('performance.max_frames_per_parse', 10)
    
    @property
    def parse_timeout_warning_ms(self) -> float:
        return self._accessor.get('performance.parse_timeout_warning_ms', 5.0)


class AckMechanismConfig:
    """ACK机制配置访问器"""
    
    def __init__(self, accessor: ConfigAccessor):
        self._accessor = accessor
    
    @property
    def enabled(self) -> bool:
        return self._accessor.get('ack_mechanism.enabled', True)
    
    @property
    def window_size(self) -> int:
        return self._accessor.get('ack_mechanism.window_size', 8)
    
    @property
    def default_timeout_ms(self) -> int:
        return self._accessor.get('ack_mechanism.default_timeout_ms', 1000)
    
    @property
    def max_retries(self) -> int:
        return self._accessor.get('ack_mechanism.max_retries', 3)


class DebuggingConfig:
    """调试配置访问器"""
    
    def __init__(self, accessor: ConfigAccessor):
        self._accessor = accessor
    
    @property
    def verbose_error_messages(self) -> bool:
        return self._accessor.get('debugging.verbose_error_messages', False)
    
    @property
    def log_frame_details(self) -> bool:
        return self._accessor.get('debugging.log_frame_details', False)


class ConfigManager:
    """统一配置管理器，提供简化的配置访问接口"""
    
    def __init__(self, config_manager: Optional[ProtocolConfigManager] = None):
        self._accessor = ConfigAccessor(config_manager)
        self.performance = PerformanceConfig(self._accessor)
        self.ack_mechanism = AckMechanismConfig(self._accessor)
        self.debugging = DebuggingConfig(self._accessor)
    
    def update_config_manager(self, config_manager: Optional[ProtocolConfigManager]):
        """更新配置管理器"""
        self._accessor.update_config_manager(config_manager)
    
    def get(self, path: str, default: Any = None) -> Any:
        """直接获取配置值"""
        return self._accessor.get(path, default)
    
    def has(self, path: str) -> bool:
        """检查配置是否存在"""
        return self._accessor.has(path)
    
    def clear_cache(self):
        """清空缓存"""
        self._accessor.clear_cache()
    
    def has_config_updated_signal(self) -> bool:
        """检查是否有配置更新信号"""
        return self._accessor.has('config_updated')
    
    def connect_config_updated(self, callback):
        """连接配置更新信号"""
        if self.has_config_updated_signal():
            config_manager = self._accessor._config_manager
            if hasattr(config_manager, 'config_updated'):
                config_manager.config_updated.connect(callback)
    
    def disconnect_config_updated(self, callback):
        """断开配置更新信号"""
        if self.has_config_updated_signal():
            config_manager = self._accessor._config_manager
            if hasattr(config_manager, 'config_updated'):
                try:
                    config_manager.config_updated.disconnect(callback)
                except (TypeError, RuntimeError):
                    pass  # 信号可能已经断开