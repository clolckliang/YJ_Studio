#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试PID插件注册功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.plugin_manager import PluginManager
from utils.logger import ErrorLogger

class MockMainWindow:
    def __init__(self):
        self.error_logger = ErrorLogger()

def test_pid_plugin_registration():
    print("=== 测试PID插件注册 ===")
    
    # 创建模拟的主窗口和插件管理器
    mock_main_window = MockMainWindow()
    plugin_manager = PluginManager(mock_main_window)
    
    # 设置启用的插件
    enabled_plugins = {"panel_plugins.pid_code_generator"}
    plugin_manager.update_enabled_plugins(enabled_plugins)
    
    print(f"启用的插件: {enabled_plugins}")
    
    # 发现和加载插件
    try:
        loaded_types = plugin_manager.discover_plugins(
            "panel_plugins", 
            load_only_enabled=True,
            reload_modules=True
        )
        print(f"加载的面板类型: {loaded_types}")
        
        # 获取可创建的面板类型
        creatable_types = plugin_manager.get_creatable_panel_types()
        print(f"可创建的面板类型: {list(creatable_types.keys())}")
        
        # 检查PID插件是否在其中
        if "advanced_pid_generator" in creatable_types:
            print("✅ PID插件注册成功！")
            panel_class = creatable_types["advanced_pid_generator"]
            print(f"面板类: {panel_class}")
            if hasattr(panel_class, 'PANEL_DISPLAY_NAME'):
                print(f"面板显示名称: {panel_class.PANEL_DISPLAY_NAME}")
            if hasattr(panel_class, 'PANEL_TYPE_NAME'):
                print(f"面板类型名称: {panel_class.PANEL_TYPE_NAME}")
        else:
            print("❌ PID插件未找到")
            print("可用的面板类型:")
            for type_name, info in creatable_types.items():
                print(f"  - {type_name}: {info.get('display_name', 'N/A')}")
                
    except Exception as e:
        print(f"❌ 插件加载失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pid_plugin_registration()