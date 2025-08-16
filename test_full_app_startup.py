#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整的应用程序启动过程
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
        self.enabled_plugin_module_names = set()
        self.plugin_manager = PluginManager(self)

def test_full_app_startup():
    print("=== 测试完整应用程序启动过程 ===")
    
    # 创建模拟的主窗口
    mock_main_window = MockMainWindow()
    
    # 1. 加载配置
    print("\n1. 加载配置文件...")
    config_data = mock_main_window.config_manager.load_config()
    if config_data:
        enabled_plugins = set(config_data.get("enabled_plugins", []))
        print(f"从配置文件加载的启用插件: {enabled_plugins}")
        mock_main_window.enabled_plugin_module_names = enabled_plugins
    else:
        enabled_plugins = set()
        print("未找到配置文件，使用空的启用插件列表")
    
    # 2. 更新插件管理器的启用插件列表
    print("\n2. 更新插件管理器...")
    mock_main_window.plugin_manager.update_enabled_plugins(enabled_plugins)
    
    # 3. 注册核心面板（模拟_register_core_panels）
    print("\n3. 注册核心面板...")
    # 这里我们跳过核心面板注册，因为我们只关心插件
    
    # 4. 发现插件
    print("\n4. 开始插件发现...")
    try:
        loaded_types = mock_main_window.plugin_manager.discover_plugins(
            "panel_plugins", 
            load_only_enabled=True
        )
        print(f"发现的面板类型: {loaded_types}")
        
        # 5. 模拟_update_add_panel_menu
        print("\n5. 模拟更新添加面板菜单...")
        available_panel_types = mock_main_window.plugin_manager.get_creatable_panel_types()
        print(f"可用动态面板插件: {available_panel_types}")
        
        if not available_panel_types:
            print("❌ 无可用动态面板插件")
        else:
            print("\n📋 添加面板菜单项:")
            for type_name, display_name in available_panel_types.items():
                print(f"  - 添加 {display_name}...")
        
        # 6. 检查PID插件
        if "advanced_pid_generator" in available_panel_types:
            print("\n✅ PID插件在添加面板菜单中！")
            print(f"菜单项: 添加 {available_panel_types['advanced_pid_generator']}...")
        else:
            print("\n❌ PID插件不在添加面板菜单中")
            
        # 7. 测试创建面板实例
        if "advanced_pid_generator" in available_panel_types:
            print("\n7. 测试创建PID面板实例...")
            try:
                panel_instance = mock_main_window.plugin_manager.create_panel_instance(
                    "advanced_pid_generator", 1, None
                )
                if panel_instance:
                    print("✅ 成功创建PID面板实例")
                    print(f"面板类型: {type(panel_instance).__name__}")
                    print(f"面板ID: {panel_instance.panel_id}")
                    print(f"初始标题: {panel_instance.get_initial_dock_title()}")
                else:
                    print("❌ 创建PID面板实例失败")
            except Exception as e:
                print(f"❌ 创建PID面板实例时出错: {e}")
                import traceback
                traceback.print_exc()
            
    except Exception as e:
        print(f"❌ 插件发现失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_app_startup()