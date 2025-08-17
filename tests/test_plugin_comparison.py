#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比较PID插件与其他插件的差异
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_manager import ConfigManager
from utils.logger import ErrorLogger
from core.plugin_manager import PluginManager
import importlib
import traceback

class MockMainWindow:
    def __init__(self):
        self.error_logger = ErrorLogger()
        self.config_manager = ConfigManager(error_logger=self.error_logger, filename="serial_debugger_config_v2.json")
        self.enabled_plugin_module_names = set()
        self.plugin_manager = PluginManager(self)

def test_individual_plugin(plugin_name):
    """测试单个插件"""
    print(f"\n=== 测试插件: {plugin_name} ===")
    
    try:
        # 尝试导入插件模块
        module_path = f"panel_plugins.{plugin_name}"
        print(f"尝试导入模块: {module_path}")
        module = importlib.import_module(module_path)
        print(f"✅ 模块导入成功: {module}")
        
        # 检查是否有register_plugin_panels函数
        if hasattr(module, 'register_plugin_panels'):
            print("✅ 找到register_plugin_panels函数")
            
            # 创建模拟插件管理器
            mock_window = MockMainWindow()
            
            # 尝试调用注册函数
            try:
                result = module.register_plugin_panels(mock_window.plugin_manager)
                print(f"✅ 注册函数调用成功，返回值: {result}")
                
                # 检查注册的面板类型
                registered_types = mock_window.plugin_manager.registered_panel_types
                print(f"注册的面板类型数量: {len(registered_types)}")
                for type_name, (panel_class, display_name, module_name) in registered_types.items():
                    print(f"  - {type_name}: {display_name} ({panel_class})")
                    
            except Exception as e:
                print(f"❌ 注册函数调用失败: {e}")
                traceback.print_exc()
        else:
            print("❌ 未找到register_plugin_panels函数")
            print(f"模块属性: {dir(module)}")
            
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        traceback.print_exc()

def test_plugin_files():
    """检查插件文件结构"""
    print("\n=== 检查插件文件结构 ===")
    
    plugins_dir = "panel_plugins"
    if os.path.exists(plugins_dir):
        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            if os.path.isdir(item_path) and not item.startswith('__'):
                print(f"\n插件目录: {item}")
                
                # 检查__init__.py文件
                init_file = os.path.join(item_path, '__init__.py')
                if os.path.exists(init_file):
                    print(f"  ✅ 存在__init__.py")
                    
                    # 读取文件内容检查关键函数
                    try:
                        with open(init_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if 'register_plugin_panels' in content:
                                print(f"  ✅ 包含register_plugin_panels函数")
                            else:
                                print(f"  ❌ 不包含register_plugin_panels函数")
                                
                            if 'PANEL_TYPE_NAME' in content:
                                print(f"  ✅ 包含PANEL_TYPE_NAME")
                            else:
                                print(f"  ❌ 不包含PANEL_TYPE_NAME")
                                
                    except Exception as e:
                        print(f"  ❌ 读取文件失败: {e}")
                else:
                    print(f"  ❌ 缺少__init__.py")
                    
                # 列出目录内容
                try:
                    files = os.listdir(item_path)
                    print(f"  文件列表: {files}")
                except Exception as e:
                    print(f"  ❌ 无法列出目录内容: {e}")

def main():
    """主测试函数"""
    print("=== 插件比较测试 ===")
    
    # 检查文件结构
    test_plugin_files()
    
    # 测试各个插件
    plugins_to_test = ['snake_game', 'pid_code_generator', 'can_bus', 'game2048']
    
    for plugin in plugins_to_test:
        test_individual_plugin(plugin)
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()