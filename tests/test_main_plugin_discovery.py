#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试主应用程序的插件发现过程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.plugin_manager import PluginManager
from utils.logger import ErrorLogger
from utils.config_manager import ConfigManager

class MockMainWindow:
    def __init__(self):
        self.error_logger = ErrorLogger()
        self.config_manager = ConfigManager(error_logger=self.error_logger, filename="serial_debugger_config_v2.json")

def test_main_app_plugin_discovery():
    print("=== 模拟主应用程序插件发现过程 ===")
    
    # 创建模拟的主窗口
    mock_main_window = MockMainWindow()
    plugin_manager = PluginManager(mock_main_window)
    
    # 加载配置
    config_data = mock_main_window.config_manager.load_config()
    if config_data:
        enabled_plugins = set(config_data.get("enabled_plugins", []))
        print(f"从配置文件加载的启用插件: {enabled_plugins}")
    else:
        enabled_plugins = set()
        print("未找到配置文件，使用空的启用插件列表")
    
    # 更新启用的插件
    plugin_manager.update_enabled_plugins(enabled_plugins)
    
    # 注册核心面板（模拟_register_core_panels）
    print("注册核心面板...")
    # 这里我们跳过核心面板注册，因为我们只关心插件
    
    # 发现插件
    print("开始插件发现...")
    try:
        loaded_types = plugin_manager.discover_plugins(
            "panel_plugins", 
            load_only_enabled=True
        )
        print(f"发现的面板类型: {loaded_types}")
        
        # 获取可创建的面板类型
        creatable_types = plugin_manager.get_creatable_panel_types()
        print(f"\n可创建的面板类型数量: {len(creatable_types)}")
        
        for type_name, panel_info in creatable_types.items():
            if isinstance(panel_info, dict):
                display_name = panel_info.get('display_name', 'N/A')
                panel_class = panel_info.get('class')
            else:
                # panel_info is the class itself
                panel_class = panel_info
                display_name = getattr(panel_class, 'PANEL_DISPLAY_NAME', 'N/A')
            print(f"  - {type_name}: {display_name}")
        
        # 检查PID插件
        if "advanced_pid_generator" in creatable_types:
            print("\n✅ PID插件在可创建列表中！")
        else:
            print("\n❌ PID插件不在可创建列表中")
            
    except Exception as e:
        print(f"❌ 插件发现失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_main_app_plugin_discovery()