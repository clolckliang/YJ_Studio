#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试应用程序菜单状态
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_manager import ConfigManager
from utils.logger import ErrorLogger
from core.plugin_manager import PluginManager
from PySide6.QtWidgets import QApplication
import time

class MockMainWindow:
    def __init__(self):
        self.error_logger = ErrorLogger()
        self.config_manager = ConfigManager(error_logger=self.error_logger, filename="serial_debugger_config_v2.json")
        self.enabled_plugin_module_names = set()
        self.plugin_manager = PluginManager(self)

def test_menu_simulation():
    """模拟菜单更新过程"""
    print("=== 模拟菜单更新过程 ===")
    
    # 创建QApplication（如果不存在）
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建模拟主窗口
    mock_window = MockMainWindow()
    
    # 加载配置
    config_data = mock_window.config_manager.load_config()
    enabled_plugin_module_names = set(config_data.get("enabled_plugins", []))
    print(f"配置中启用的插件: {enabled_plugin_module_names}")
    
    # 更新启用的插件
    mock_window.plugin_manager.update_enabled_plugins(enabled_plugin_module_names)
    print(f"插件管理器中启用的插件: {mock_window.plugin_manager.enabled_plugin_modules}")
    
    # 发现插件
    print("\n=== 插件发现过程 ===")
    discovered_modules = mock_window.plugin_manager.discover_plugins("panel_plugins", load_only_enabled=True)
    print(f"发现的插件模块: {discovered_modules}")
    
    # 模拟_update_add_panel_menu方法
    print("\n=== 模拟菜单更新 ===")
    available_panel_types = mock_window.plugin_manager.get_creatable_panel_types()
    print(f"可用动态面板插件: {available_panel_types}")
    
    if not available_panel_types:
        print("❌ 没有可用的动态面板插件")
    else:
        print("✅ 菜单项将包含:")
        for type_name, display_name in available_panel_types.items():
            print(f"  - 添加 {display_name}... (类型: {type_name})")
    
    # 检查PID插件状态
    print("\n=== PID插件状态检查 ===")
    if "advanced_pid_generator" in available_panel_types:
        print(f"✅ PID插件在菜单中: {available_panel_types['advanced_pid_generator']}")
    else:
        print("❌ PID插件不在菜单中")
        print("已注册的插件类型:", list(mock_window.plugin_manager.registered_panel_types.keys()))
        print("会话阻止的模块:", mock_window.plugin_manager.session_blocklisted_modules)
    
    # 检查插件管理器的详细状态
    print("\n=== 插件管理器详细状态 ===")
    print(f"注册的面板类型数量: {len(mock_window.plugin_manager.registered_panel_types)}")
    for type_name, (panel_class, display_name, module_name) in mock_window.plugin_manager.registered_panel_types.items():
        print(f"  {type_name}: {display_name} (来自 {module_name})")
    
    print(f"\n启用的插件模块: {mock_window.plugin_manager.enabled_plugin_modules}")
    print(f"会话阻止的模块: {mock_window.plugin_manager.session_blocklisted_modules}")
    
    return available_panel_types

def test_direct_plugin_creation():
    """测试直接创建PID插件实例"""
    print("\n=== 测试直接创建PID插件实例 ===")
    
    try:
        # 创建QApplication（如果不存在）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建模拟主窗口
        mock_window = MockMainWindow()
        
        # 加载和发现插件
        config_data = mock_window.config_manager.load_config()
        enabled_plugin_module_names = set(config_data.get("enabled_plugins", []))
        mock_window.plugin_manager.update_enabled_plugins(enabled_plugin_module_names)
        mock_window.plugin_manager.discover_plugins("panel_plugins", load_only_enabled=True)
        
        # 尝试创建PID插件实例
        panel_instance = mock_window.plugin_manager.create_panel_instance(
            "advanced_pid_generator", 
            mock_window, 
            panel_id=999
        )
        
        if panel_instance:
            print(f"✅ 成功创建PID插件实例: {panel_instance}")
            print(f"插件类型: {type(panel_instance)}")
            print(f"插件标题: {panel_instance.get_initial_dock_title()}")
        else:
            print("❌ 无法创建PID插件实例")
            
    except Exception as e:
        print(f"❌ 创建PID插件实例时出错: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主测试函数"""
    print("=== 应用程序菜单状态测试 ===")
    
    # 测试菜单模拟
    available_types = test_menu_simulation()
    
    # 测试直接创建插件
    test_direct_plugin_creation()
    
    print("\n=== 测试完成 ===")
    
    # 如果PID插件不在菜单中，提供诊断信息
    if "advanced_pid_generator" not in available_types:
        print("\n=== 诊断信息 ===")
        print("PID插件未出现在菜单中的可能原因:")
        print("1. 插件未正确注册")
        print("2. 插件被会话阻止")
        print("3. 插件配置问题")
        print("4. 插件类验证失败")
        print("\n建议检查:")
        print("- 插件的register_plugin_panels函数")
        print("- 插件类是否继承自PanelInterface")
        print("- 插件是否在配置文件中启用")

if __name__ == "__main__":
    main()