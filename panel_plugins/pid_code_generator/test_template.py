#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PID代码生成器模板测试脚本
演示如何使用模板文件生成C语言PID代码
"""

import os
from datetime import datetime

def generate_code_from_template(algorithm_type="positional", 
                               struct_name="PID_Controller",
                               function_prefix="PID",
                               use_float=True,
                               kp=1.0, ki=0.1, kd=0.01,
                               max_output=100.0, min_output=-100.0,
                               integral_limit=50.0, sample_time=0.01):
    """使用模板文件生成PID代码"""
    
    # 确定模板文件路径
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    if algorithm_type == "positional":
        template_file = os.path.join(template_dir, "positional_pid_template.c")
    else:
        template_file = os.path.join(template_dir, "incremental_pid_template.c")
    
    # 检查模板文件是否存在
    if not os.path.exists(template_file):
        raise FileNotFoundError(f"模板文件不存在: {template_file}")
    
    # 读取模板文件
    with open(template_file, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # 准备替换参数
    data_type = "float" if use_float else "double"
    replacements = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_type": data_type,
        "struct_name": struct_name,
        "function_prefix": function_prefix,
        "max_output": str(max_output),
        "min_output": str(min_output),
        "integral_limit": str(integral_limit),
        "sample_time": str(sample_time),
        "kp": str(kp),
        "ki": str(ki),
        "kd": str(kd)
    }
    
    # 执行模板替换
    generated_code = template_content
    for key, value in replacements.items():
        generated_code = generated_code.replace(f"{{{key}}}", value)
    
    return generated_code

def main():
    """主函数 - 测试模板功能"""
    print("=== PID代码生成器模板测试 ===\n")
    
    # 测试位置式PID
    print("1. 生成位置式PID代码:")
    try:
        positional_code = generate_code_from_template(
            algorithm_type="positional",
            struct_name="PositionalPID",
            function_prefix="PosPID",
            kp=2.0, ki=0.5, kd=0.1
        )
        print("✓ 位置式PID代码生成成功")
        print(f"代码长度: {len(positional_code)} 字符\n")
        
        # 保存到文件
        with open("generated_positional_pid.c", "w", encoding="utf-8") as f:
            f.write(positional_code)
        print("✓ 位置式PID代码已保存到 generated_positional_pid.c\n")
        
    except Exception as e:
        print(f"✗ 位置式PID代码生成失败: {e}\n")
    
    # 测试增量式PID
    print("2. 生成增量式PID代码:")
    try:
        incremental_code = generate_code_from_template(
            algorithm_type="incremental",
            struct_name="IncrementalPID",
            function_prefix="IncPID",
            use_float=False,  # 使用double类型
            kp=1.5, ki=0.3, kd=0.05
        )
        print("✓ 增量式PID代码生成成功")
        print(f"代码长度: {len(incremental_code)} 字符\n")
        
        # 保存到文件
        with open("generated_incremental_pid.c", "w", encoding="utf-8") as f:
            f.write(incremental_code)
        print("✓ 增量式PID代码已保存到 generated_incremental_pid.c\n")
        
    except Exception as e:
        print(f"✗ 增量式PID代码生成失败: {e}\n")
    
    print("=== 测试完成 ===")

if __name__ == "__main__":
    main()
