#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试当前运行应用程序的插件状态
"""

import sys
import os
import importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config_manager import ConfigManager

def test_current_plugin_state():
    """测试当前插件状态"""
    print("=== 测试当前插件状态 ===")
    
    # 加载配置
    config_manager = ConfigManager()
    config_data = config_manager.load_config()
    enabled_plugin_module_names = set(config_data.get("enabled_plugins", []))
    print(f"从配置文件加载的启用插件: {enabled_plugin_module_names}")
    
    # 检查插件文件是否存在
    print("\n=== 检查插件文件 ===")
    plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel_plugins")
    print(f"插件目录: {plugin_dir}")
    
    if os.path.exists(plugin_dir):
        print(f"✅ 插件目录存在")
        plugin_files = [f for f in os.listdir(plugin_dir) if f.endswith('.py') and not f.startswith('__')]
        print(f"发现的插件文件: {plugin_files}")
    else:
        print(f"❌ 插件目录不存在")
        return
    
    # 检查PID插件文件
    pid_plugin_file = os.path.join(plugin_dir, "pid_code_generator.py")
    if os.path.exists(pid_plugin_file):
        print(f"✅ PID插件文件存在: {pid_plugin_file}")
    else:
        print(f"❌ PID插件文件不存在: {pid_plugin_file}")
        return
    
    # 尝试导入PID插件模块
    print("\n=== 测试插件导入 ===")
    try:
        pid_module = importlib.import_module("panel_plugins.pid_code_generator")
        print("✅ PID插件模块导入成功")
        
        # 检查注册函数
        if hasattr(pid_module, 'register_plugin_panels'):
            print("✅ 找到register_plugin_panels函数")
            
            # 检查插件信息函数
            if hasattr(pid_module, 'get_panel_info'):
                panel_info = pid_module.get_panel_info()
                print(f"✅ 插件信息: {panel_info}")
            else:
                print("⚠️ 未找到get_panel_info函数")
                
        else:
            print("❌ 未找到register_plugin_panels函数")
            
    except Exception as e:
        print(f"❌ PID插件模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 检查插件是否在启用列表中
    print("\n=== 检查插件启用状态 ===")
    if "panel_plugins.pid_code_generator" in enabled_plugin_module_names:
        print("✅ PID插件在启用列表中")
    else:
        print("❌ PID插件不在启用列表中")
        print(f"当前启用的插件: {enabled_plugin_module_names}")
    
    print("\n=== 总结 ===")
    print("如果以上所有检查都通过，但界面中仍然看不到PID插件，")
    print("可能是主应用程序的日志级别设置导致插件加载信息没有显示。")

if __name__ == "__main__":
    test_current_plugin_state()