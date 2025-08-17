"""配置访问器测试模块"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.config_accessor import ConfigAccessor, ConfigManager, PerformanceConfig, AckMechanismConfig, DebuggingConfig
from utils.protocol_config_manager import ProtocolConfigManager


class TestConfigAccessor:
    """ConfigAccessor类的测试"""
    
    def test_init_with_none_config_manager(self):
        """测试使用None配置管理器初始化"""
        accessor = ConfigAccessor(None)
        assert accessor._config_manager is None
        assert accessor._cache == {}
        assert accessor._cache_enabled is True
    
    def test_init_with_config_manager(self):
        """测试使用配置管理器初始化"""
        mock_config = MagicMock()
        accessor = ConfigAccessor(mock_config)
        assert accessor._config_manager is mock_config
    
    def test_get_with_none_config_manager(self):
        """测试在没有配置管理器时获取配置"""
        accessor = ConfigAccessor(None)
        result = accessor.get('test.path', 'default_value')
        assert result == 'default_value'
    
    def test_get_existing_nested_value(self):
        """测试获取存在的嵌套配置值"""
        mock_config = MagicMock()
        mock_config.performance.buffer_size = 1024
        
        accessor = ConfigAccessor(mock_config)
        result = accessor.get('performance.buffer_size', 512)
        assert result == 1024
    
    def test_get_non_existing_value(self):
        """测试获取不存在的配置值"""
        mock_config = MagicMock()
        del mock_config.non_existing  # 确保属性不存在
        
        accessor = ConfigAccessor(mock_config)
        result = accessor.get('non_existing.value', 'default')
        assert result == 'default'
    
    def test_get_with_cache(self):
        """测试缓存功能"""
        mock_config = MagicMock()
        mock_config.performance.buffer_size = 1024
        
        accessor = ConfigAccessor(mock_config)
        
        # 第一次调用
        result1 = accessor.get('performance.buffer_size', 512)
        assert result1 == 1024
        
        # 修改配置值
        mock_config.performance.buffer_size = 2048
        
        # 第二次调用应该返回缓存值
        result2 = accessor.get('performance.buffer_size', 512)
        assert result2 == 1024  # 应该是缓存的值
    
    def test_get_without_cache(self):
        """测试禁用缓存时的行为"""
        mock_config = MagicMock()
        mock_config.performance.buffer_size = 1024
        
        accessor = ConfigAccessor(mock_config)
        
        # 第一次调用
        result1 = accessor.get('performance.buffer_size', 512, use_cache=False)
        assert result1 == 1024
        
        # 修改配置值
        mock_config.performance.buffer_size = 2048
        
        # 第二次调用应该返回新值
        result2 = accessor.get('performance.buffer_size', 512, use_cache=False)
        assert result2 == 2048
    
    def test_has_existing_value(self):
        """测试检查存在的配置值"""
        mock_config = MagicMock()
        mock_config.performance.buffer_size = 1024
        
        accessor = ConfigAccessor(mock_config)
        assert accessor.has('performance.buffer_size') is True
    
    def test_has_non_existing_value(self):
        """测试检查不存在的配置值"""
        mock_config = MagicMock()
        del mock_config.non_existing  # 确保属性不存在
        
        accessor = ConfigAccessor(mock_config)
        assert accessor.has('non_existing.value') is False
    
    def test_clear_cache(self):
        """测试清空缓存"""
        mock_config = MagicMock()
        mock_config.performance.buffer_size = 1024
        
        accessor = ConfigAccessor(mock_config)
        
        # 添加缓存
        accessor.get('performance.buffer_size', 512)
        assert len(accessor._cache) > 0
        
        # 清空缓存
        accessor.clear_cache()
        assert len(accessor._cache) == 0
    
    def test_enable_disable_cache(self):
        """测试启用/禁用缓存"""
        accessor = ConfigAccessor(None)
        
        # 默认启用
        assert accessor._cache_enabled is True
        
        # 禁用缓存
        accessor.enable_cache(False)
        assert accessor._cache_enabled is False
        
        # 重新启用
        accessor.enable_cache(True)
        assert accessor._cache_enabled is True
    
    def test_update_config_manager(self):
        """测试更新配置管理器"""
        old_config = MagicMock()
        new_config = MagicMock()
        
        accessor = ConfigAccessor(old_config)
        accessor._cache['test'] = 'value'  # 添加缓存
        
        accessor.update_config_manager(new_config)
        
        assert accessor._config_manager is new_config
        assert len(accessor._cache) == 0  # 缓存应该被清空


class TestPerformanceConfig:
    """PerformanceConfig类的测试"""
    
    def test_buffer_size_default(self):
        """测试buffer_size默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = 1024 * 32
        
        config = PerformanceConfig(mock_accessor)
        result = config.buffer_size
        
        mock_accessor.get.assert_called_with('performance.buffer_size', 1024 * 32)
        assert result == 1024 * 32
    
    def test_buffer_usage_warning_percent_default(self):
        """测试buffer_usage_warning_percent默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = 90.0
        
        config = PerformanceConfig(mock_accessor)
        result = config.buffer_usage_warning_percent
        
        mock_accessor.get.assert_called_with('performance.buffer_usage_warning_percent', 90.0)
        assert result == 90.0
    
    def test_max_frames_per_parse_default(self):
        """测试max_frames_per_parse默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = 10
        
        config = PerformanceConfig(mock_accessor)
        result = config.max_frames_per_parse
        
        mock_accessor.get.assert_called_with('performance.max_frames_per_parse', 10)
        assert result == 10
    
    def test_parse_timeout_warning_ms_default(self):
        """测试parse_timeout_warning_ms默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = 5.0
        
        config = PerformanceConfig(mock_accessor)
        result = config.parse_timeout_warning_ms
        
        mock_accessor.get.assert_called_with('performance.parse_timeout_warning_ms', 5.0)
        assert result == 5.0


class TestAckMechanismConfig:
    """AckMechanismConfig类的测试"""
    
    def test_enabled_default(self):
        """测试enabled默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = True
        
        config = AckMechanismConfig(mock_accessor)
        result = config.enabled
        
        mock_accessor.get.assert_called_with('ack_mechanism.enabled', True)
        assert result is True
    
    def test_window_size_default(self):
        """测试window_size默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = 8
        
        config = AckMechanismConfig(mock_accessor)
        result = config.window_size
        
        mock_accessor.get.assert_called_with('ack_mechanism.window_size', 8)
        assert result == 8
    
    def test_default_timeout_ms_default(self):
        """测试default_timeout_ms默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = 1000
        
        config = AckMechanismConfig(mock_accessor)
        result = config.default_timeout_ms
        
        mock_accessor.get.assert_called_with('ack_mechanism.default_timeout_ms', 1000)
        assert result == 1000
    
    def test_max_retries_default(self):
        """测试max_retries默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = 3
        
        config = AckMechanismConfig(mock_accessor)
        result = config.max_retries
        
        mock_accessor.get.assert_called_with('ack_mechanism.max_retries', 3)
        assert result == 3


class TestDebuggingConfig:
    """DebuggingConfig类的测试"""
    
    def test_verbose_error_messages_default(self):
        """测试verbose_error_messages默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = False
        
        config = DebuggingConfig(mock_accessor)
        result = config.verbose_error_messages
        
        mock_accessor.get.assert_called_with('debugging.verbose_error_messages', False)
        assert result is False
    
    def test_log_frame_details_default(self):
        """测试log_frame_details默认值"""
        mock_accessor = MagicMock()
        mock_accessor.get.return_value = False
        
        config = DebuggingConfig(mock_accessor)
        result = config.log_frame_details
        
        mock_accessor.get.assert_called_with('debugging.log_frame_details', False)
        assert result is False


class TestConfigManager:
    """ConfigManager类的测试"""
    
    def test_init(self):
        """测试初始化"""
        mock_config = MagicMock()
        manager = ConfigManager(mock_config)
        
        assert isinstance(manager.performance, PerformanceConfig)
        assert isinstance(manager.ack_mechanism, AckMechanismConfig)
        assert isinstance(manager.debugging, DebuggingConfig)
    
    def test_get_direct(self):
        """测试直接获取配置值"""
        mock_config = MagicMock()
        manager = ConfigManager(mock_config)
        
        with patch.object(manager._accessor, 'get', return_value='test_value') as mock_get:
            result = manager.get('test.path', 'default')
            
            mock_get.assert_called_with('test.path', 'default')
            assert result == 'test_value'
    
    def test_has_direct(self):
        """测试直接检查配置是否存在"""
        mock_config = MagicMock()
        manager = ConfigManager(mock_config)
        
        with patch.object(manager._accessor, 'has', return_value=True) as mock_has:
            result = manager.has('test.path')
            
            mock_has.assert_called_with('test.path')
            assert result is True
    
    def test_clear_cache_direct(self):
        """测试直接清空缓存"""
        mock_config = MagicMock()
        manager = ConfigManager(mock_config)
        
        with patch.object(manager._accessor, 'clear_cache') as mock_clear:
            manager.clear_cache()
            mock_clear.assert_called_once()
    
    def test_update_config_manager(self):
        """测试更新配置管理器"""
        old_config = MagicMock()
        new_config = MagicMock()
        
        manager = ConfigManager(old_config)
        
        with patch.object(manager._accessor, 'update_config_manager') as mock_update:
            manager.update_config_manager(new_config)
            mock_update.assert_called_with(new_config)
    
    def test_has_config_updated_signal(self):
        """测试检查配置更新信号"""
        mock_config = MagicMock()
        manager = ConfigManager(mock_config)
        
        with patch.object(manager._accessor, 'has', return_value=True) as mock_has:
            result = manager.has_config_updated_signal()
            
            mock_has.assert_called_with('config_updated')
            assert result is True
    
    def test_connect_config_updated_signal_exists(self):
        """测试连接配置更新信号（信号存在）"""
        mock_config = MagicMock()
        mock_callback = MagicMock()
        
        manager = ConfigManager(mock_config)
        
        with patch.object(manager, 'has_config_updated_signal', return_value=True):
            manager.connect_config_updated(mock_callback)
            mock_config.config_updated.connect.assert_called_with(mock_callback)
    
    def test_connect_config_updated_signal_not_exists(self):
        """测试连接配置更新信号（信号不存在）"""
        mock_config = MagicMock()
        mock_callback = MagicMock()
        
        manager = ConfigManager(mock_config)
        
        with patch.object(manager, 'has_config_updated_signal', return_value=False):
            manager.connect_config_updated(mock_callback)
            # 不应该调用connect
            mock_config.config_updated.connect.assert_not_called()
    
    def test_disconnect_config_updated_signal_exists(self):
        """测试断开配置更新信号（信号存在）"""
        mock_config = MagicMock()
        mock_callback = MagicMock()
        
        manager = ConfigManager(mock_config)
        
        with patch.object(manager, 'has_config_updated_signal', return_value=True):
            manager.disconnect_config_updated(mock_callback)
            mock_config.config_updated.disconnect.assert_called_with(mock_callback)
    
    def test_disconnect_config_updated_with_exception(self):
        """测试断开配置更新信号时发生异常"""
        mock_config = MagicMock()
        mock_config.config_updated.disconnect.side_effect = TypeError("Signal not connected")
        mock_callback = MagicMock()
        
        manager = ConfigManager(mock_config)
        
        with patch.object(manager, 'has_config_updated_signal', return_value=True):
            # 不应该抛出异常
            manager.disconnect_config_updated(mock_callback)
            mock_config.config_updated.disconnect.assert_called_with(mock_callback)


if __name__ == '__main__':
    pytest.main([__file__])