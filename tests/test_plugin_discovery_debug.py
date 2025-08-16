#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试插件发现过程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_manager import ConfigManager
from utils.logger import ErrorLogger
from core.plugin_manager import PluginManager

class MockMainWindow:
    def __init__(self):
        self.error_logger = ErrorLogger()
        self.config_manager = ConfigManager(error_logger=self.error_logger, filename="serial_debugger_config_v2.json")
        self.enabled_plugin_module_names = set()
        self.plugin_manager = PluginManager(self)

def test_plugin_discovery_with_debug():
    """测试插件发现过程（带调试信息）"""
    print("=== 调试插件发现过程 ===")
    
    # 创建模拟主窗口
    mock_window = MockMainWindow()
    
    # 加载配置
    config_data = mock_window.config_manager.load_config()
    enabled_plugin_module_names = set(config_data.get("enabled_plugins", []))
    print(f"从配置文件加载的启用插件: {enabled_plugin_module_names}")
    
    # 更新启用的插件
    mock_window.plugin_manager.update_enabled_plugins(enabled_plugin_module_names)
    print(f"插件管理器中启用的插件: {mock_window.plugin_manager.enabled_plugin_modules}")
    
    # 发现插件（带详细日志）
    print("\n=== 开始插件发现过程 ===")
    try:
        discovered_modules = mock_window.plugin_manager.discover_plugins("panel_plugins", load_only_enabled=True)
        print(f"发现的插件模块: {discovered_modules}")
    except Exception as e:
        print(f"插件发现过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 检查注册的面板类型
    print(f"\n=== 注册的面板类型 ===")
    registered_types = mock_window.plugin_manager.registered_panel_types
    for type_name, (panel_class, display_name, module_name) in registered_types.items():
        print(f"类型名: {type_name}")
        print(f"  显示名: {display_name}")
        print(f"  面板类: {panel_class}")
        print(f"  模块名: {module_name}")
        print()
    
    # 获取可创建的面板类型
    creatable_types = mock_window.plugin_manager.get_creatable_panel_types()
    print(f"\n=== 可创建的面板类型 ===")
    for type_name, display_name in creatable_types.items():
        print(f"{type_name}: {display_name}")
    
    # 检查PID插件是否存在
    if "advanced_pid_generator" in creatable_types:
        print(f"\n✅ PID插件已成功发现！显示名称: {creatable_types['advanced_pid_generator']}")
    else:
        print("\n❌ PID插件未被发现")
        print("已注册的类型:", list(registered_types.keys()))
    
    # 检查会话阻止列表
    print(f"\n=== 会话阻止的模块 ===")
    print(f"阻止列表: {mock_window.plugin_manager.session_blocklisted_modules}")

if __name__ == "__main__":
    test_plugin_discovery_with_debug()