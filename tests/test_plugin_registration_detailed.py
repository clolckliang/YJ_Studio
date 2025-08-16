#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细测试插件注册过程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.plugin_manager import PluginManager
from utils.logger import ErrorLogger

class MockMainWindow:
    def __init__(self):
        self.error_logger = ErrorLogger()

def test_plugin_registration_detailed():
    print("=== 详细测试插件注册过程 ===")
    
    # 创建模拟的主窗口和插件管理器
    mock_main_window = MockMainWindow()
    plugin_manager = PluginManager(mock_main_window)
    
    # 直接导入PID插件模块
    try:
        import panel_plugins.pid_code_generator as pid_plugin
        print("✅ 成功导入PID插件模块")
        
        # 检查模块是否有register_plugin_panels函数
        if hasattr(pid_plugin, 'register_plugin_panels'):
            print("✅ 找到register_plugin_panels函数")
            
            # 调用注册函数
            try:
                pid_plugin.register_plugin_panels(plugin_manager)
                print("✅ 成功调用register_plugin_panels")
                
                # 检查注册结果
                registered_types = plugin_manager.registered_panel_types
                print(f"\n注册的面板类型: {list(registered_types.keys())}")
                
                for type_name, (panel_class, display_name, module_name) in registered_types.items():
                    print(f"\n面板类型: {type_name}")
                    print(f"  - 面板类: {panel_class.__name__}")
                    print(f"  - 显示名称: {display_name}")
                    print(f"  - 模块名称: {module_name}")
                    print(f"  - PANEL_TYPE_NAME: {getattr(panel_class, 'PANEL_TYPE_NAME', 'N/A')}")
                    print(f"  - PANEL_DISPLAY_NAME: {getattr(panel_class, 'PANEL_DISPLAY_NAME', 'N/A')}")
                
                # 测试get_creatable_panel_types
                creatable_types = plugin_manager.get_creatable_panel_types()
                print(f"\n可创建的面板类型: {creatable_types}")
                
                if "advanced_pid_generator" in creatable_types:
                    print("\n✅ PID插件注册成功，可以在界面中使用！")
                else:
                    print("\n❌ PID插件未在可创建列表中")
                    
            except Exception as e:
                print(f"❌ 调用register_plugin_panels失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("❌ 未找到register_plugin_panels函数")
            print(f"模块属性: {dir(pid_plugin)}")
            
    except Exception as e:
        print(f"❌ 导入PID插件模块失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_plugin_registration_detailed()