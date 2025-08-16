#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced PID Code Generator - Refactored Version

This module provides a comprehensive PID controller code generator with:
- Multiple PID instances management
- Advanced parameter configuration
- Real-time code preview
- Template-based code generation
- Export functionality

Author: YJ Studio Team
Version: 3.0.0 (Refactored)
Date: 2024
"""

import copy
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from main import SerialDebugger

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QTabWidget, QTextEdit, QComboBox, QDoubleSpinBox, QCheckBox,
    QSizePolicy, QInputDialog, QMessageBox, QFileDialog, QSplitter
)

from core.panel_interface import PanelInterface
from utils.logger import ErrorLogger


class CSyntaxHighlighter(QSyntaxHighlighter):
    """C/C++语法高亮器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_highlighting_rules()
    
    def _setup_highlighting_rules(self):
        """设置语法高亮规则"""
        self.highlighting_rules = []
        
        # 关键字格式
        keyword_format = QTextCharFormat()
        keyword_format.setColor(QColor(86, 156, 214))  # 蓝色
        keyword_format.setFontWeight(QFont.Bold)
        
        keywords = [
            'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
            'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
            'int', 'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
            'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile', 'while',
            'bool', 'true', 'false', 'NULL'
        ]
        
        for keyword in keywords:
            pattern = f'\\b{keyword}\\b'
            self.highlighting_rules.append((re.compile(pattern), keyword_format))
        
        # 字符串格式
        string_format = QTextCharFormat()
        string_format.setColor(QColor(206, 145, 120))  # 橙色
        self.highlighting_rules.append((re.compile('".*?"'), string_format))
        
        # 注释格式
        comment_format = QTextCharFormat()
        comment_format.setColor(QColor(106, 153, 85))  # 绿色
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile('//[^\n]*'), comment_format))
        self.highlighting_rules.append((re.compile('/\*.*?\*/', re.DOTALL), comment_format))
        
        # 数字格式
        number_format = QTextCharFormat()
        number_format.setColor(QColor(181, 206, 168))  # 浅绿色
        self.highlighting_rules.append((re.compile('\\b\\d+\\.?\\d*[fF]?\\b'), number_format))
    
    def highlightBlock(self, text):
        """高亮文本块"""
        for pattern, format_obj in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format_obj)


class PIDDataModel:
    """PID数据模型类，负责管理PID实例和配置数据"""
    
    # PID参数键常量
    P_PID_TYPE = "pid_type"
    P_WORK_MODE = "work_mode"
    P_KP = "kp"
    P_KI = "ki"
    P_KD = "kd"
    P_KFF = "kff"
    P_FF_WEIGHT = "ff_weight"
    P_SAMPLE_TIME = "sample_time"
    P_MAX_OUT = "max_output"
    P_MIN_OUT = "min_output"
    P_INT_LIM = "integral_limit"
    P_OUT_RAMP = "output_ramp"
    P_DEADBAND = "deadband"
    P_INT_SEP_THRESH = "integral_separation_threshold"
    P_D_FILTER = "d_filter_coef"
    P_IN_FILTER = "input_filter_coef"
    P_SP_FILTER = "setpoint_filter_coef"
    
    # 高级功能参数（占位符）
    P_ADAPTIVE_KP_MIN = "adaptive_kp_min"
    P_ADAPTIVE_KP_MAX = "adaptive_kp_max"
    P_ADAPTIVE_KI_MIN = "adaptive_ki_min"
    P_ADAPTIVE_KI_MAX = "adaptive_ki_max"
    P_ADAPTIVE_KD_MIN = "adaptive_kd_min"
    P_ADAPTIVE_KD_MAX = "adaptive_kd_max"
    P_FUZZY_ERR_RANGE = "fuzzy_error_range"
    P_FUZZY_DERR_RANGE = "fuzzy_derror_range"
    
    # 代码配置键常量
    C_STRUCT_NAME = "struct_name"
    C_FUNC_PREFIX = "function_prefix"
    C_HEADER_NAME = "header_name"
    C_USE_FLOAT = "use_float"
    C_INC_COMMENTS = "include_comments"
    C_DATA_TYPE = "data_type"
    C_FLOAT_SUFFIX = "float_suffix"
    
    def __init__(self):
        self.pid_instances: List[Dict[str, Any]] = []
        self.active_instance_index = -1
        self.code_config = self._get_default_code_config()
    
    def _get_default_pid_params(self) -> Dict[str, Any]:
        """获取默认PID参数"""
        return {
            self.P_PID_TYPE: "standard",
            self.P_WORK_MODE: "position",
            self.P_KP: 1.0,
            self.P_KI: 0.1,
            self.P_KD: 0.01,
            self.P_KFF: 0.0,
            self.P_FF_WEIGHT: 1.0,
            self.P_SAMPLE_TIME: 0.01,
            self.P_MAX_OUT: 100.0,
            self.P_MIN_OUT: -100.0,
            self.P_INT_LIM: 50.0,
            self.P_OUT_RAMP: 0.0,
            self.P_DEADBAND: 0.0,
            self.P_INT_SEP_THRESH: 1000.0,
            self.P_D_FILTER: 0.0,
            self.P_IN_FILTER: 0.0,
            self.P_SP_FILTER: 0.0,
            # 高级功能占位符
            self.P_ADAPTIVE_KP_MIN: 0.1,
            self.P_ADAPTIVE_KP_MAX: 10.0,
            self.P_ADAPTIVE_KI_MIN: 0.01,
            self.P_ADAPTIVE_KI_MAX: 1.0,
            self.P_ADAPTIVE_KD_MIN: 0.001,
            self.P_ADAPTIVE_KD_MAX: 0.1,
            self.P_FUZZY_ERR_RANGE: 10.0,
            self.P_FUZZY_DERR_RANGE: 1.0,
        }
    
    def _get_default_code_config(self) -> Dict[str, Any]:
        """获取默认代码配置"""
        return {
            self.C_STRUCT_NAME: "PID_HandleTypeDef",
            self.C_FUNC_PREFIX: "PID",
            self.C_HEADER_NAME: "pid.h",
            self.C_USE_FLOAT: True,
            self.C_INC_COMMENTS: True,
            self.C_DATA_TYPE: "float",
            self.C_FLOAT_SUFFIX: "f",
        }
    
    def add_instance(self, name: str) -> bool:
        """添加PID实例"""
        if any(inst['name'] == name for inst in self.pid_instances):
            return False
        
        new_instance = {
            'name': name,
            'params': self._get_default_pid_params()
        }
        self.pid_instances.append(new_instance)
        return True
    
    def remove_instance(self, index: int) -> bool:
        """移除PID实例"""
        if 0 <= index < len(self.pid_instances):
            del self.pid_instances[index]
            if self.active_instance_index >= len(self.pid_instances):
                self.active_instance_index = len(self.pid_instances) - 1
            return True
        return False
    
    def rename_instance(self, index: int, new_name: str) -> bool:
        """重命名PID实例"""
        if not (0 <= index < len(self.pid_instances)):
            return False
        
        # 检查名称冲突
        if any(inst['name'] == new_name for i, inst in enumerate(self.pid_instances) if i != index):
            return False
        
        self.pid_instances[index]['name'] = new_name
        return True
    
    def get_active_instance(self) -> Optional[Dict[str, Any]]:
        """获取当前活动实例"""
        if 0 <= self.active_instance_index < len(self.pid_instances):
            return self.pid_instances[self.active_instance_index]
        return None
    
    def update_active_instance_params(self, params: Dict[str, Any]):
        """更新当前活动实例的参数"""
        active_instance = self.get_active_instance()
        if active_instance:
            active_instance['params'].update(params)
    
    def update_code_config(self, config: Dict[str, Any]):
        """更新代码配置"""
        self.code_config.update(config)
        # 更新派生字段
        self.code_config[self.C_DATA_TYPE] = "float" if self.code_config[self.C_USE_FLOAT] else "double"
        self.code_config[self.C_FLOAT_SUFFIX] = "f" if self.code_config[self.C_USE_FLOAT] else ""


class PIDCodeGenerator:
    """PID代码生成器类，负责从模板生成代码"""
    
    def __init__(self, data_model: PIDDataModel):
        self.data_model = data_model
        self.template_dir = Path(__file__).parent / "templates"
    
    def generate_header_code(self) -> str:
        """生成头文件代码"""
        template_path = self.template_dir / "advanced_pid_template.h"
        if not template_path.exists():
            return "// Error: Header template not found."
        return self._generate_from_template(template_path)
    
    def generate_source_code(self) -> str:
        """生成源文件代码"""
        template_path = self.template_dir / "advanced_pid_template.c"
        if not template_path.exists():
            return "// Error: Source template not found."
        return self._generate_from_template(template_path)
    
    def generate_main_code(self) -> str:
        """生成主函数示例代码"""
        template_path = self.template_dir / "user_main_template.c"
        if not template_path.exists():
            return "// Error: Main template not found."
        return self._generate_main_from_template(template_path)
    
    def _generate_from_template(self, template_path: Path) -> str:
        """从模板生成代码（库文件）"""
        try:
            template_content = template_path.read_text(encoding='utf-8')
            
            # 使用默认参数填充模板
            default_params = self.data_model._get_default_pid_params()
            replacements = self._get_template_replacements(default_params)
            
            for key, value in replacements.items():
                template_content = template_content.replace(key, str(value))
            
            # 处理注释
            if not self.data_model.code_config[self.data_model.C_INC_COMMENTS]:
                template_content = self._remove_comments(template_content)
            
            return template_content
        except Exception as e:
            return f"// Error generating from template {template_path.name}: {e}"
    
    def _generate_main_from_template(self, template_path: Path) -> str:
        """从模板生成主函数代码"""
        try:
            template_content = template_path.read_text(encoding='utf-8')
            
            # 全局替换
            global_replacements = {
                '{{HEADER_NAME}}': self.data_model.code_config[self.data_model.C_HEADER_NAME],
                '{{STRUCT_NAME}}': self.data_model.code_config[self.data_model.C_STRUCT_NAME],
                '{{FUNCTION_PREFIX}}': self.data_model.code_config[self.data_model.C_FUNC_PREFIX],
                '{{DATA_TYPE}}': self.data_model.code_config[self.data_model.C_DATA_TYPE],
                '{{TIMESTAMP}}': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                '{{SFX}}': self.data_model.code_config[self.data_model.C_FLOAT_SUFFIX]
            }
            
            for key, value in global_replacements.items():
                template_content = template_content.replace(key, str(value))
            
            # 生成实例相关代码
            declarations = self._generate_instance_declarations()
            initializations = self._generate_instance_initializations()
            computations = self._generate_instance_computations()
            
            template_content = template_content.replace('{{PID_INSTANCE_DECLARATIONS}}', declarations)
            template_content = template_content.replace('{{PID_INSTANCE_INITIALIZATIONS}}', initializations)
            template_content = template_content.replace('{{PID_EXAMPLE_COMPUTATIONS}}', computations)
            
            return template_content
        except Exception as e:
            return f"// Error generating main code: {e}"
    
    def _get_template_replacements(self, params: Dict[str, Any]) -> Dict[str, str]:
        """获取模板替换字典"""
        config = self.data_model.code_config
        sfx = config[self.data_model.C_FLOAT_SUFFIX]
        
        return {
            '{{STRUCT_NAME}}': config[self.data_model.C_STRUCT_NAME],
            '{{FUNCTION_PREFIX}}': config[self.data_model.C_FUNC_PREFIX],
            '{{DATA_TYPE}}': config[self.data_model.C_DATA_TYPE],
            '{{HEADER_NAME}}': config[self.data_model.C_HEADER_NAME],
            '{{TIMESTAMP}}': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            '{{SFX}}': sfx,
            '{{KFF_DEFAULT}}': f"{params[self.data_model.P_KFF]}{sfx}",
            '{{FF_WEIGHT_DEFAULT}}': f"{params[self.data_model.P_FF_WEIGHT]}{sfx}",
            '{{OUTPUT_LIMIT_DEFAULT}}': f"{params[self.data_model.P_MAX_OUT]}{sfx}",
            '{{INTEGRAL_LIMIT_DEFAULT}}': f"{params[self.data_model.P_INT_LIM]}{sfx}",
            '{{OUTPUT_RAMP_DEFAULT}}': f"{params[self.data_model.P_OUT_RAMP]}{sfx}",
            '{{DEADBAND_DEFAULT}}': f"{params[self.data_model.P_DEADBAND]}{sfx}",
            '{{INTEGRAL_SEPARATION_THRESHOLD_DEFAULT}}': f"{params[self.data_model.P_INT_SEP_THRESH]}{sfx}",
            '{{D_FILTER_COEF_DEFAULT}}': f"{params[self.data_model.P_D_FILTER]}{sfx}",
            '{{INPUT_FILTER_COEF_DEFAULT}}': f"{params[self.data_model.P_IN_FILTER]}{sfx}",
            '{{SETPOINT_FILTER_COEF_DEFAULT}}': f"{params[self.data_model.P_SP_FILTER]}{sfx}",
            '{{ADAPTIVE_ENABLE}}': 'false',
            '{{FUZZY_ENABLE}}': 'false',
            '{{ADAPTIVE_KP_MIN_DEFAULT}}': f"{params[self.data_model.P_ADAPTIVE_KP_MIN]}{sfx}",
            '{{ADAPTIVE_KP_MAX_DEFAULT}}': f"{params[self.data_model.P_ADAPTIVE_KP_MAX]}{sfx}",
            '{{ADAPTIVE_KI_MIN_DEFAULT}}': f"{params[self.data_model.P_ADAPTIVE_KI_MIN]}{sfx}",
            '{{ADAPTIVE_KI_MAX_DEFAULT}}': f"{params[self.data_model.P_ADAPTIVE_KI_MAX]}{sfx}",
            '{{ADAPTIVE_KD_MIN_DEFAULT}}': f"{params[self.data_model.P_ADAPTIVE_KD_MIN]}{sfx}",
            '{{ADAPTIVE_KD_MAX_DEFAULT}}': f"{params[self.data_model.P_ADAPTIVE_KD_MAX]}{sfx}",
            '{{FUZZY_ERROR_RANGE_DEFAULT}}': f"{params[self.data_model.P_FUZZY_ERR_RANGE]}{sfx}",
            '{{FUZZY_DERROR_RANGE_DEFAULT}}': f"{params[self.data_model.P_FUZZY_DERR_RANGE]}{sfx}",
        }
    
    def _generate_instance_declarations(self) -> str:
        """生成实例声明代码"""
        if not self.data_model.pid_instances:
            return "    // 未配置任何PID实例"
        
        struct_name = self.data_model.code_config[self.data_model.C_STRUCT_NAME]
        declarations = []
        for instance in self.data_model.pid_instances:
            declarations.append(f"    {struct_name} {instance['name']};")
        return "\n".join(declarations)
    
    def _generate_instance_initializations(self) -> str:
        """生成实例初始化代码"""
        if not self.data_model.pid_instances:
            return "    // 未配置任何PID实例，无初始化代码生成。"
        
        init_lines = []
        for instance in self.data_model.pid_instances:
            init_lines.extend(self._get_instance_init_code(instance))
        return "\n".join(init_lines)
    
    def _generate_instance_computations(self) -> str:
        """生成实例计算示例代码"""
        if not self.data_model.pid_instances:
            return "    // 未配置任何PID实例，无示例代码生成。"
        
        comp_lines = []
        for instance in self.data_model.pid_instances:
            comp_lines.extend(self._get_instance_sim_code(instance))
        return "\n".join(comp_lines)
    
    def _get_instance_init_code(self, instance: Dict[str, Any]) -> List[str]:
        """为单个实例生成初始化代码"""
        name = instance['name']
        params = instance['params']
        config = self.data_model.code_config
        sfx = config[self.data_model.C_FLOAT_SUFFIX]
        prefix = config[self.data_model.C_FUNC_PREFIX]
        sample_time = max(params[self.data_model.P_SAMPLE_TIME], 1e-6)
        
        lines = [f"    // 初始化PID实例: {name}"]
        lines.append(f"    {prefix}_Init(&{name}, {params[self.data_model.P_KP]}{sfx}, {params[self.data_model.P_KI]}{sfx}, {params[self.data_model.P_KD]}{sfx}, {sample_time}{sfx});")
        lines.append(f"    {prefix}_SetOutputLimits(&{name}, {params[self.data_model.P_MAX_OUT]}{sfx});")
        lines.append(f"    {prefix}_SetIntegralLimits(&{name}, {params[self.data_model.P_INT_LIM]}{sfx});")
        
        # 可选参数设置
        if params[self.data_model.P_OUT_RAMP] > 0:
            lines.append(f"    {prefix}_SetOutputRamp(&{name}, {params[self.data_model.P_OUT_RAMP]}{sfx});")
        if params[self.data_model.P_DEADBAND] > 0:
            lines.append(f"    {prefix}_SetDeadband(&{name}, {params[self.data_model.P_DEADBAND]}{sfx});")
        if params[self.data_model.P_INT_SEP_THRESH] < 1000.0:
            lines.append(f"    {prefix}_SetIntegralSeparationThreshold(&{name}, {params[self.data_model.P_INT_SEP_THRESH]}{sfx});")
        if params[self.data_model.P_D_FILTER] > 0:
            lines.append(f"    {prefix}_SetDFilter(&{name}, {params[self.data_model.P_D_FILTER]}{sfx});")
        if params[self.data_model.P_IN_FILTER] > 0:
            lines.append(f"    {prefix}_SetInputFilter(&{name}, {params[self.data_model.P_IN_FILTER]}{sfx});")
        if params[self.data_model.P_SP_FILTER] > 0:
            lines.append(f"    {prefix}_SetSetpointFilter(&{name}, {params[self.data_model.P_SP_FILTER]}{sfx});")
        if params[self.data_model.P_KFF] != 0 or params[self.data_model.P_FF_WEIGHT] != 1.0:
            lines.append(f"    {prefix}_SetFeedForwardParams(&{name}, {params[self.data_model.P_KFF]}{sfx}, {params[self.data_model.P_FF_WEIGHT]}{sfx});")
        
        # PID类型和工作模式
        pid_type_map = {"standard": "PID_TYPE_STANDARD", "pi_d": "PID_TYPE_PI_D", "i_pd": "PID_TYPE_I_PD"}
        work_mode_map = {"position": "PID_MODE_POSITION", "velocity": "PID_MODE_VELOCITY"}
        lines.append(f"    {prefix}_SetType(&{name}, {pid_type_map[params[self.data_model.P_PID_TYPE]]});")
        lines.append(f"    {prefix}_SetWorkMode(&{name}, {work_mode_map[params[self.data_model.P_WORK_MODE]]});")
        
        lines.append(f"    printf(\"Initialized PID: {name} (Kp=%.4f, Ki_cont=%.4f, Kd_cont=%.4f, Ts=%.4f)\\n\", (double){params[self.data_model.P_KP]}{sfx}, (double){params[self.data_model.P_KI]}{sfx}, (double){params[self.data_model.P_KD]}{sfx}, (double){sample_time}{sfx});")
        lines.append("")
        return lines
    
    def _get_instance_sim_code(self, instance: Dict[str, Any]) -> List[str]:
        """为单个实例生成仿真代码"""
        name = instance['name']
        params = instance['params']
        config = self.data_model.code_config
        sfx = config[self.data_model.C_FLOAT_SUFFIX]
        prefix = config[self.data_model.C_FUNC_PREFIX]
        data_type = config[self.data_model.C_DATA_TYPE]
        sample_time = max(params[self.data_model.P_SAMPLE_TIME], 1e-6)
        
        return [
            f"    // 示例计算 for {name}",
            f"    {data_type} {name}_setpoint = 50.0{sfx};",
            f"    {data_type} {name}_measurement = 0.0{sfx};",
            f"    printf(\"\\n--- Running simulation for {name} ---\\n\");",
            "    for (int j = 0; j < 5; ++j) {",
            f"        {data_type} {name}_output = {prefix}_Compute(&{name}, {name}_setpoint, {name}_measurement);",
            f"        {name}_measurement = simulate_system_response({name}_measurement, {name}_output, {sample_time}{sfx});",
            f"        printf(\"  {name}: Step %d, SP=%.2f, PV=%.2f, Out=%.2f\\n\", j+1, (double){name}_setpoint, (double){name}_measurement, (double){name}_output);",
            "    }", ""
        ]
    
    def _remove_comments(self, content: str) -> str:
        """移除代码中的注释"""
        # 移除多行注释
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        # 移除单行注释
        content = re.sub(r'//[^\n]*', '', content)
        # 清理多余的空行
        content = re.sub(r'\n\s*\n', '\n\n', content)
        return content


class PIDParameterWidget(QWidget):
    """PID参数配置组件"""
    
    params_changed = Signal(dict)
    
    def __init__(self, data_model: PIDDataModel, parent=None):
        super().__init__(parent)
        self.data_model = data_model
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 基本参数组
        basic_group = self._create_basic_params_group()
        layout.addWidget(basic_group)
        
        # 输出限制组
        output_group = self._create_output_limits_group()
        layout.addWidget(output_group)
        
        # 高级控制组
        advanced_group = self._create_advanced_control_group()
        layout.addWidget(advanced_group)
        
        layout.addStretch()
    
    def _create_basic_params_group(self) -> QGroupBox:
        """创建基本参数组"""
        group = QGroupBox("基本PID参数")
        layout = QGridLayout(group)
        
        # PID类型
        layout.addWidget(QLabel("PID类型:"), 0, 0)
        self.pid_type_combo = QComboBox()
        self.pid_type_combo.addItems(["标准 (Perr, Derr)", "PI-D (Perr, Dmeas)", "I-PD (Pmeas, Dmeas)"])
        layout.addWidget(self.pid_type_combo, 0, 1)
        
        # 工作模式
        layout.addWidget(QLabel("工作模式:"), 0, 2)
        self.work_mode_combo = QComboBox()
        self.work_mode_combo.addItems(["位置模式", "速度模式 (增量)"])
        layout.addWidget(self.work_mode_combo, 0, 3)
        
        # PID参数
        layout.addWidget(QLabel("Kp:"), 1, 0)
        self.kp_spinbox = QDoubleSpinBox()
        self.kp_spinbox.setRange(-1000.0, 1000.0)
        self.kp_spinbox.setDecimals(6)
        self.kp_spinbox.setValue(1.0)
        layout.addWidget(self.kp_spinbox, 1, 1)
        
        layout.addWidget(QLabel("Ki:"), 1, 2)
        self.ki_spinbox = QDoubleSpinBox()
        self.ki_spinbox.setRange(-1000.0, 1000.0)
        self.ki_spinbox.setDecimals(6)
        self.ki_spinbox.setValue(0.1)
        layout.addWidget(self.ki_spinbox, 1, 3)
        
        layout.addWidget(QLabel("Kd:"), 2, 0)
        self.kd_spinbox = QDoubleSpinBox()
        self.kd_spinbox.setRange(-1000.0, 1000.0)
        self.kd_spinbox.setDecimals(6)
        self.kd_spinbox.setValue(0.01)
        layout.addWidget(self.kd_spinbox, 2, 1)
        
        layout.addWidget(QLabel("采样时间(s):"), 2, 2)
        self.sample_time_spinbox = QDoubleSpinBox()
        self.sample_time_spinbox.setRange(0.000001, 10.0)
        self.sample_time_spinbox.setDecimals(6)
        self.sample_time_spinbox.setValue(0.01)
        layout.addWidget(self.sample_time_spinbox, 2, 3)
        
        return group
    
    def _create_output_limits_group(self) -> QGroupBox:
        """创建输出限制组"""
        group = QGroupBox("输出与积分限制")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("最大输出:"), 0, 0)
        self.max_output_spinbox = QDoubleSpinBox()
        self.max_output_spinbox.setRange(-10000.0, 10000.0)
        self.max_output_spinbox.setValue(100.0)
        layout.addWidget(self.max_output_spinbox, 0, 1)
        
        layout.addWidget(QLabel("最小输出:"), 0, 2)
        self.min_output_spinbox = QDoubleSpinBox()
        self.min_output_spinbox.setRange(-10000.0, 10000.0)
        self.min_output_spinbox.setValue(-100.0)
        layout.addWidget(self.min_output_spinbox, 0, 3)
        
        layout.addWidget(QLabel("积分限制:"), 1, 0)
        self.integral_limit_spinbox = QDoubleSpinBox()
        self.integral_limit_spinbox.setRange(0.0, 10000.0)
        self.integral_limit_spinbox.setValue(50.0)
        layout.addWidget(self.integral_limit_spinbox, 1, 1)
        
        layout.addWidget(QLabel("输出变化率:"), 1, 2)
        self.output_ramp_spinbox = QDoubleSpinBox()
        self.output_ramp_spinbox.setRange(0.0, 10000.0)
        self.output_ramp_spinbox.setValue(0.0)
        layout.addWidget(self.output_ramp_spinbox, 1, 3)
        
        return group
    
    def _create_advanced_control_group(self) -> QGroupBox:
        """创建高级控制组"""
        group = QGroupBox("高级控制与滤波器")
        layout = QGridLayout(group)
        
        # 前馈控制
        layout.addWidget(QLabel("前馈增益:"), 0, 0)
        self.kff_spinbox = QDoubleSpinBox()
        self.kff_spinbox.setRange(-1000.0, 1000.0)
        self.kff_spinbox.setDecimals(6)
        self.kff_spinbox.setValue(0.0)
        layout.addWidget(self.kff_spinbox, 0, 1)
        
        layout.addWidget(QLabel("前馈权重:"), 0, 2)
        self.ff_weight_spinbox = QDoubleSpinBox()
        self.ff_weight_spinbox.setRange(0.0, 1.0)
        self.ff_weight_spinbox.setDecimals(3)
        self.ff_weight_spinbox.setValue(1.0)
        layout.addWidget(self.ff_weight_spinbox, 0, 3)
        
        # 死区和积分分离
        layout.addWidget(QLabel("死区:"), 1, 0)
        self.deadband_spinbox = QDoubleSpinBox()
        self.deadband_spinbox.setRange(0.0, 1000.0)
        self.deadband_spinbox.setDecimals(3)
        self.deadband_spinbox.setValue(0.0)
        layout.addWidget(self.deadband_spinbox, 1, 1)
        
        layout.addWidget(QLabel("积分分离阈值:"), 1, 2)
        self.integral_separation_spinbox = QDoubleSpinBox()
        self.integral_separation_spinbox.setRange(0.0, 10000.0)
        self.integral_separation_spinbox.setValue(1000.0)
        layout.addWidget(self.integral_separation_spinbox, 1, 3)
        
        # 滤波器
        layout.addWidget(QLabel("微分滤波:"), 2, 0)
        self.d_filter_spinbox = QDoubleSpinBox()
        self.d_filter_spinbox.setRange(0.0, 1.0)
        self.d_filter_spinbox.setDecimals(3)
        self.d_filter_spinbox.setValue(0.0)
        layout.addWidget(self.d_filter_spinbox, 2, 1)
        
        layout.addWidget(QLabel("输入滤波:"), 2, 2)
        self.input_filter_spinbox = QDoubleSpinBox()
        self.input_filter_spinbox.setRange(0.0, 1.0)
        self.input_filter_spinbox.setDecimals(3)
        self.input_filter_spinbox.setValue(0.0)
        layout.addWidget(self.input_filter_spinbox, 2, 3)
        
        layout.addWidget(QLabel("设定值滤波:"), 3, 0)
        self.setpoint_filter_spinbox = QDoubleSpinBox()
        self.setpoint_filter_spinbox.setRange(0.0, 1.0)
        self.setpoint_filter_spinbox.setDecimals(3)
        self.setpoint_filter_spinbox.setValue(0.0)
        layout.addWidget(self.setpoint_filter_spinbox, 3, 1)
        
        return group
    
    def _connect_signals(self):
        """连接信号"""
        # 连接所有控件的信号到参数变化处理函数
        controls = [
            self.pid_type_combo, self.work_mode_combo,
            self.kp_spinbox, self.ki_spinbox, self.kd_spinbox, self.sample_time_spinbox,
            self.max_output_spinbox, self.min_output_spinbox, self.integral_limit_spinbox,
            self.output_ramp_spinbox, self.kff_spinbox, self.ff_weight_spinbox,
            self.deadband_spinbox, self.integral_separation_spinbox,
            self.d_filter_spinbox, self.input_filter_spinbox, self.setpoint_filter_spinbox
        ]
        
        for control in controls:
            if isinstance(control, QComboBox):
                control.currentTextChanged.connect(self._on_params_changed)
            elif isinstance(control, QDoubleSpinBox):
                control.valueChanged.connect(self._on_params_changed)
    
    @Slot()
    def _on_params_changed(self):
        """参数变化处理"""
        params = self._collect_params()
        self.params_changed.emit(params)
    
    def _collect_params(self) -> Dict[str, Any]:
        """收集当前参数"""
        pid_type_map = {
            "标准 (Perr, Derr)": "standard",
            "PI-D (Perr, Dmeas)": "pi_d",
            "I-PD (Pmeas, Dmeas)": "i_pd"
        }
        
        work_mode_map = {
            "位置模式": "position",
            "速度模式 (增量)": "velocity"
        }
        
        return {
            self.data_model.P_PID_TYPE: pid_type_map[self.pid_type_combo.currentText()],
            self.data_model.P_WORK_MODE: work_mode_map[self.work_mode_combo.currentText()],
            self.data_model.P_KP: self.kp_spinbox.value(),
            self.data_model.P_KI: self.ki_spinbox.value(),
            self.data_model.P_KD: self.kd_spinbox.value(),
            self.data_model.P_SAMPLE_TIME: self.sample_time_spinbox.value(),
            self.data_model.P_MAX_OUT: self.max_output_spinbox.value(),
            self.data_model.P_MIN_OUT: self.min_output_spinbox.value(),
            self.data_model.P_INT_LIM: self.integral_limit_spinbox.value(),
            self.data_model.P_OUT_RAMP: self.output_ramp_spinbox.value(),
            self.data_model.P_KFF: self.kff_spinbox.value(),
            self.data_model.P_FF_WEIGHT: self.ff_weight_spinbox.value(),
            self.data_model.P_DEADBAND: self.deadband_spinbox.value(),
            self.data_model.P_INT_SEP_THRESH: self.integral_separation_spinbox.value(),
            self.data_model.P_D_FILTER: self.d_filter_spinbox.value(),
            self.data_model.P_IN_FILTER: self.input_filter_spinbox.value(),
            self.data_model.P_SP_FILTER: self.setpoint_filter_spinbox.value(),
        }
    
    def load_params(self, params: Dict[str, Any]):
        """加载参数到UI"""
        # 阻塞信号防止循环触发
        self.blockSignals(True)
        
        # 映射字典
        pid_type_map = {
            "standard": "标准 (Perr, Derr)",
            "pi_d": "PI-D (Perr, Dmeas)",
            "i_pd": "I-PD (Pmeas, Dmeas)"
        }
        
        work_mode_map = {
            "position": "位置模式",
            "velocity": "速度模式 (增量)"
        }
        
        # 设置值
        self.pid_type_combo.setCurrentText(pid_type_map.get(params.get(self.data_model.P_PID_TYPE, "standard"), "标准 (Perr, Derr)"))
        self.work_mode_combo.setCurrentText(work_mode_map.get(params.get(self.data_model.P_WORK_MODE, "position"), "位置模式"))
        
        self.kp_spinbox.setValue(params.get(self.data_model.P_KP, 1.0))
        self.ki_spinbox.setValue(params.get(self.data_model.P_KI, 0.1))
        self.kd_spinbox.setValue(params.get(self.data_model.P_KD, 0.01))
        self.sample_time_spinbox.setValue(params.get(self.data_model.P_SAMPLE_TIME, 0.01))
        self.max_output_spinbox.setValue(params.get(self.data_model.P_MAX_OUT, 100.0))
        self.min_output_spinbox.setValue(params.get(self.data_model.P_MIN_OUT, -100.0))
        self.integral_limit_spinbox.setValue(params.get(self.data_model.P_INT_LIM, 50.0))
        self.output_ramp_spinbox.setValue(params.get(self.data_model.P_OUT_RAMP, 0.0))
        self.kff_spinbox.setValue(params.get(self.data_model.P_KFF, 0.0))
        self.ff_weight_spinbox.setValue(params.get(self.data_model.P_FF_WEIGHT, 1.0))
        self.deadband_spinbox.setValue(params.get(self.data_model.P_DEADBAND, 0.0))
        self.integral_separation_spinbox.setValue(params.get(self.data_model.P_INT_SEP_THRESH, 1000.0))
        self.d_filter_spinbox.setValue(params.get(self.data_model.P_D_FILTER, 0.0))
        self.input_filter_spinbox.setValue(params.get(self.data_model.P_IN_FILTER, 0.0))
        self.setpoint_filter_spinbox.setValue(params.get(self.data_model.P_SP_FILTER, 0.0))
        
        self.blockSignals(False)


class CodeConfigWidget(QWidget):
    """代码配置组件"""
    
    config_changed = Signal(dict)
    
    def __init__(self, data_model: PIDDataModel, parent=None):
        super().__init__(parent)
        self.data_model = data_model
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        group = QGroupBox("全局代码生成选项")
        grid_layout = QGridLayout(group)
        
        # 结构体名称
        grid_layout.addWidget(QLabel("结构体名称:"), 0, 0)
        self.struct_name_edit = QLineEdit("PID_HandleTypeDef")
        grid_layout.addWidget(self.struct_name_edit, 0, 1)
        
        # 函数前缀
        grid_layout.addWidget(QLabel("函数前缀:"), 0, 2)
        self.function_prefix_edit = QLineEdit("PID")
        grid_layout.addWidget(self.function_prefix_edit, 0, 3)
        
        # 头文件名
        grid_layout.addWidget(QLabel("头文件名:"), 1, 0)
        self.header_name_edit = QLineEdit("pid.h")
        grid_layout.addWidget(self.header_name_edit, 1, 1)
        
        # 选项
        self.use_float_checkbox = QCheckBox("使用float类型")
        self.use_float_checkbox.setChecked(True)
        grid_layout.addWidget(self.use_float_checkbox, 1, 2)
        
        self.include_comments_checkbox = QCheckBox("包含注释")
        self.include_comments_checkbox.setChecked(True)
        grid_layout.addWidget(self.include_comments_checkbox, 1, 3)
        
        layout.addWidget(group)
        layout.addStretch()
    
    def _connect_signals(self):
        """连接信号"""
        self.struct_name_edit.textChanged.connect(self._on_config_changed)
        self.function_prefix_edit.textChanged.connect(self._on_config_changed)
        self.header_name_edit.textChanged.connect(self._on_config_changed)
        self.use_float_checkbox.toggled.connect(self._on_config_changed)
        self.include_comments_checkbox.toggled.connect(self._on_config_changed)
    
    @Slot()
    def _on_config_changed(self):
        """配置变化处理"""
        config = self._collect_config()
        self.config_changed.emit(config)
    
    def _collect_config(self) -> Dict[str, Any]:
        """收集当前配置"""
        return {
            self.data_model.C_STRUCT_NAME: self.struct_name_edit.text().strip() or "PID_HandleTypeDef",
            self.data_model.C_FUNC_PREFIX: self.function_prefix_edit.text().strip() or "PID",
            self.data_model.C_HEADER_NAME: self.header_name_edit.text().strip() or "pid.h",
            self.data_model.C_USE_FLOAT: self.use_float_checkbox.isChecked(),
            self.data_model.C_INC_COMMENTS: self.include_comments_checkbox.isChecked(),
        }
    
    def load_config(self, config: Dict[str, Any]):
        """加载配置到UI"""
        self.blockSignals(True)
        
        self.struct_name_edit.setText(config.get(self.data_model.C_STRUCT_NAME, "PID_HandleTypeDef"))
        self.function_prefix_edit.setText(config.get(self.data_model.C_FUNC_PREFIX, "PID"))
        self.header_name_edit.setText(config.get(self.data_model.C_HEADER_NAME, "pid.h"))
        self.use_float_checkbox.setChecked(config.get(self.data_model.C_USE_FLOAT, True))
        self.include_comments_checkbox.setChecked(config.get(self.data_model.C_INC_COMMENTS, True))
        
        self.blockSignals(False)


class CodePreviewWidget(QWidget):
    """代码预览组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        
        # 文件选择器
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("预览文件:"))
        self.file_selector = QComboBox()
        self.file_selector.addItems(["C 源文件 (库)", "头文件 (库)", "示例 Main (.c)"])
        self.file_selector.currentIndexChanged.connect(self._on_file_selected)
        selector_layout.addWidget(self.file_selector)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
        # 预览标签
        self.preview_label = QLabel("当前预览: C 源文件 (库)")
        layout.addWidget(self.preview_label)
        
        # 代码预览区
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Consolas", 10))
        self.code_preview.setLineWrapMode(QTextEdit.NoWrap)
        self.code_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.code_preview.setMinimumHeight(400)
        
        # 语法高亮
        self.highlighter = CSyntaxHighlighter(self.code_preview.document())
        
        layout.addWidget(self.code_preview)
        
        # 存储生成的代码
        self.generated_codes = {
            0: "",  # C源文件
            1: "",  # 头文件
            2: ""   # 主函数
        }
    
    @Slot()
    def _on_file_selected(self):
        """文件选择变化处理"""
        self.update_preview()
    
    def update_preview(self):
        """更新预览内容"""
        selected_index = self.file_selector.currentIndex()
        content = self.generated_codes.get(selected_index, "")
        
        labels = ["C 源文件 (库)", "头文件 (库)", "示例 Main (.c)"]
        label_text = f"当前预览: {labels[selected_index]}"
        
        self.code_preview.setPlainText(content)
        self.preview_label.setText(label_text)
    
    def set_generated_codes(self, source_code: str, header_code: str, main_code: str):
        """设置生成的代码"""
        self.generated_codes[0] = source_code
        self.generated_codes[1] = header_code
        self.generated_codes[2] = main_code
        self.update_preview()


class AdvancedPIDGeneratorWidget(PanelInterface):
    """高级PID代码生成器主组件 - 重构版本"""
    
    PANEL_TYPE_NAME = "advanced_pid_generator"
    PANEL_DISPLAY_NAME = "高级PID代码生成器"
    
    dock_title_changed = Signal(str)
    
    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', 
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        # error_logger is available through self.error_logger from parent class
        
        # 初始化数据模型和代码生成器
        self.data_model = PIDDataModel()
        self.code_generator = PIDCodeGenerator(self.data_model)
        
        # 防抖定时器
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._generate_and_update_preview)
        self.debounce_timer.setInterval(500)  # 500ms防抖
        
        self._setup_ui()
        self._connect_signals()
        self._log_info("Advanced PID Generator initialized (Refactored Version)")
    
    def _setup_ui(self):
        """设置UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：实例管理
        left_widget = self._create_instance_management_widget()
        splitter.addWidget(left_widget)
        
        # 右侧：参数配置和预览
        right_widget = self._create_config_and_preview_widget()
        splitter.addWidget(right_widget)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        layout.addWidget(splitter)
        
        # 状态标签
        self.status_label = QLabel("准备就绪。")
        
        # 初始状态
        self._update_controls_state()
    
    def _create_instance_management_widget(self) -> QWidget:
        """创建实例管理组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 实例管理组
        group = QGroupBox("PID实例管理")
        group_layout = QVBoxLayout(group)
        
        # 实例列表
        self.instance_list = QListWidget()
        self.instance_list.setMaximumHeight(200)
        group_layout.addWidget(self.instance_list)
        
        # 实例名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("实例名称:"))
        self.instance_name_edit = QLineEdit()
        self.instance_name_edit.setPlaceholderText("例如: motor_pid")
        name_layout.addWidget(self.instance_name_edit)
        group_layout.addLayout(name_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("添加")
        self.remove_button = QPushButton("移除")
        self.rename_button = QPushButton("重命名")
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.rename_button)
        group_layout.addLayout(button_layout)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _create_config_and_preview_widget(self) -> QWidget:
        """创建配置和预览组件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 选项卡
        self.tab_widget = QTabWidget()
        
        # PID参数选项卡
        self.param_widget = PIDParameterWidget(self.data_model)
        self.tab_widget.addTab(self.param_widget, "PID 参数")
        
        # 代码配置选项卡
        self.config_widget = CodeConfigWidget(self.data_model)
        self.tab_widget.addTab(self.config_widget, "代码配置")
        
        # 代码预览选项卡
        self.preview_widget = CodePreviewWidget()
        self.tab_widget.addTab(self.preview_widget, "代码预览")
        
        layout.addWidget(self.tab_widget)
        
        # 操作按钮
        self.generate_button.clicked.connect(self._on_generate_code)
        self.export_button.clicked.connect(self._on_export_code)
    
    @Slot()
    def _on_add_instance(self):
        """添加PID实例"""
        name = self.instance_name_edit.text().strip()
        if not name:
            name, ok = QInputDialog.getText(self, "添加PID实例", "输入实例名称 (例如 motor_pid):")
            if not (ok and name):
                return
        
        # 验证名称格式
        if not re.fullmatch(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
            QMessageBox.warning(self, "名称无效", "实例名称必须以字母或下划线开头，且只包含字母、数字和下划线。")
            return
        
        # 添加实例
        if self.data_model.add_instance(name):
            item = QListWidgetItem(name)
            self.instance_list.addItem(item)
            self.instance_list.setCurrentItem(item)
            self.instance_name_edit.clear()
            self._trigger_code_generation()
            self._log_info(f"Added PID instance: {name}")
        else:
            QMessageBox.warning(self, "名称冲突", f"名为 '{name}' 的PID实例已存在。")
    
    @Slot()
    def _on_remove_instance(self):
        """移除PID实例"""
        current_row = self.instance_list.currentRow()
        if current_row < 0:
            return
        
        instance_name = self.data_model.pid_instances[current_row]['name']
        reply = QMessageBox.question(
            self, "确认移除", 
            f"确定要移除PID实例 '{instance_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.data_model.remove_instance(current_row)
            self.instance_list.takeItem(current_row)
            self._trigger_code_generation()
            self._log_info(f"Removed PID instance: {instance_name}")
    
    @Slot()
    def _on_rename_instance(self):
        """重命名PID实例"""
        current_row = self.instance_list.currentRow()
        if current_row < 0:
            return
        
        old_name = self.data_model.pid_instances[current_row]['name']
        new_name, ok = QInputDialog.getText(self, "重命名PID实例", "输入新名称:", text=old_name)
        
        if not (ok and new_name and new_name != old_name):
            return
        
        # 验证名称格式
        if not re.fullmatch(r"^[a-zA-Z_][a-zA-Z0-9_]*$", new_name):
            QMessageBox.warning(self, "名称无效", "名称格式不正确。")
            return
        
        # 重命名实例
        if self.data_model.rename_instance(current_row, new_name):
            self.instance_list.item(current_row).setText(new_name)
            self.instance_name_edit.setText(new_name)
            self._trigger_code_generation()
            self._update_title()
            self._log_info(f"Renamed PID instance: {old_name} -> {new_name}")
        else:
            QMessageBox.warning(self, "名称冲突", f"实例 '{new_name}' 已存在。")
    
    @Slot()
    def _on_instance_selection_changed(self):
        """实例选择变化处理"""
        current_row = self.instance_list.currentRow()
        
        if current_row >= 0:
            self.data_model.active_instance_index = current_row
            instance = self.data_model.get_active_instance()
            if instance:
                self.instance_name_edit.setText(instance['name'])
                self.param_widget.load_params(instance['params'])
        else:
            self.data_model.active_instance_index = -1
            self.instance_name_edit.clear()
        
        self._update_controls_state()
        self._update_title()
    
    @Slot(dict)
    def _on_params_changed(self, params: Dict[str, Any]):
        """参数变化处理"""
        self.data_model.update_active_instance_params(params)
        self._trigger_code_generation()
    
    @Slot(dict)
    def _on_config_changed(self, config: Dict[str, Any]):
        """配置变化处理"""
        self.data_model.update_code_config(config)
        self._trigger_code_generation()
    
    @Slot(int)
    def _on_tab_changed(self, index: int):
        """选项卡切换处理"""
        if self.tab_widget.tabText(index) == "代码预览":
            self._generate_and_update_preview()
    
    @Slot()
    def _on_generate_code(self):
        """生成代码按钮处理"""
        self._generate_and_update_preview()
        self._show_status("所有代码预览已更新。", 2000)
    
    @Slot()
    def _on_export_code(self):
        """导出代码按钮处理"""
        if not self.data_model.pid_instances:
            QMessageBox.information(self, "导出提示", "请至少添加并配置一个PID实例。")
            return
        
        self._generate_and_update_preview()
        self._show_status("正在导出文件...", 0)
        
        # 选择保存位置
        suggested_name = Path(self.data_model.code_config[self.data_model.C_HEADER_NAME]).stem
        file_path_base, _ = QFileDialog.getSaveFileName(
            self, "选择保存位置和基础文件名", 
            str(Path.cwd() / suggested_name), 
            "All Files (*)"
        )
        
        if not file_path_base:
            self._show_status("导出已取消。", 2000)
            return
        
        try:
            save_dir = Path(file_path_base).parent
            base_name = Path(file_path_base).stem
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            header_name = self.data_model.code_config[self.data_model.C_HEADER_NAME]
            source_name = f"{Path(header_name).stem}.c"
            main_name = f"{base_name}_main.c"
            
            # 生成代码
            header_code = self.code_generator.generate_header_code()
            source_code = self.code_generator.generate_source_code()
            main_code = self.code_generator.generate_main_code()
            
            # 写入文件
            files_to_write = [
                (save_dir / header_name, header_code),
                (save_dir / source_name, source_code),
                (save_dir / main_name, main_code)
            ]
            
            for file_path, content in files_to_write:
                if content and not content.startswith("// Error"):
                    file_path.write_text(content, encoding='utf-8')
            
            QMessageBox.information(self, "导出成功", f"代码已导出到:\n{save_dir}")
            self._show_status("代码导出成功。", 2000)
            self._log_info(f"Code exported to: {save_dir}")
            
        except IOError as e:
            QMessageBox.critical(self, "导出失败", f"写入文件时发生IO错误:\n{e}")
            self._show_status("导出失败：写入文件错误。", 2000)
            self._log_error(f"Export failed: {e}")
    
    def _trigger_code_generation(self):
        """触发代码生成（防抖）"""
        self.debounce_timer.start()
    
    @Slot()
    def _generate_and_update_preview(self):
        """生成代码并更新预览"""
        self._show_status("正在生成代码...", 0)
        
        try:
            # 生成代码
            header_code = self.code_generator.generate_header_code()
            source_code = self.code_generator.generate_source_code()
            main_code = self.code_generator.generate_main_code()
            
            # 更新预览
            self.preview_widget.set_generated_codes(source_code, header_code, main_code)
            
            self._show_status("代码生成完成。", 2000)
            
        except Exception as e:
            self._log_error(f"Code generation failed: {e}")
            self._show_status(f"代码生成失败: {e}", 3000)
    
    def _update_controls_state(self):
        """更新控件状态"""
        has_selection = self.data_model.active_instance_index >= 0
        
        # 启用/禁用参数配置选项卡
        self.param_widget.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)
        self.rename_button.setEnabled(has_selection)
    
    def _update_title(self):
        """更新面板标题"""
        title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]"
        if self.data_model.active_instance_index >= 0:
            active_instance = self.data_model.get_active_instance()
            if active_instance:
                title += f" - 编辑: {active_instance['name']}"
        
        if hasattr(self, 'dock_title_changed'):
            self.dock_title_changed.emit(title)
    
    def _show_status(self, message: str, timeout_ms: int = 0):
        """显示状态消息"""
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(message)
            if timeout_ms > 0:
                QTimer.singleShot(timeout_ms, lambda: self.status_label.setText("准备就绪。"))
    
    # 日志方法
    def _log_error(self, message: str):
        self.error_logger.log_error(message, self.PANEL_TYPE_NAME)
    
    def _log_warning(self, message: str):
        self.error_logger.log_warning(message, self.PANEL_TYPE_NAME)
    
    def _log_info(self, message: str):
        self.error_logger.log_info(message, self.PANEL_TYPE_NAME)
    
    def _log_debug(self, message: str):
        self.error_logger.log_debug(message, self.PANEL_TYPE_NAME)
    
    # PanelInterface 实现
    def get_config(self) -> Dict[str, Any]:
        """获取面板配置"""
        self._log_debug("Getting config...")
        return {
            "version": "3.0.0",
            "pid_instance_configs": copy.deepcopy(self.data_model.pid_instances),
            "active_pid_instance_index": self.data_model.active_instance_index,
            "global_code_config": self.data_model.code_config.copy(),
            "panel_type": self.PANEL_TYPE_NAME,
            "ui_selections": {
                "preview_file_selector_index": self.preview_widget.file_selector.currentIndex()
            }
        }
    
    def apply_config(self, config: Dict[str, Any]):
        """应用面板配置"""
        self._log_debug(f"Applying config (version: {config.get('version')})...")
        
        # 更新数据模型
        self.data_model.code_config.update(config.get("global_code_config", {}))
        self.data_model.pid_instances = copy.deepcopy(config.get("pid_instance_configs", []))
        self.data_model.active_instance_index = config.get("active_pid_instance_index", -1)
        
        # 更新UI
        self.config_widget.load_config(self.data_model.code_config)
        
        # 重建实例列表
        self.instance_list.clear()
        for instance in self.data_model.pid_instances:
            self.instance_list.addItem(QListWidgetItem(instance['name']))
        
        # 设置活动实例
        if 0 <= self.data_model.active_instance_index < len(self.data_model.pid_instances):
            self.instance_list.setCurrentRow(self.data_model.active_instance_index)
        
        # 恢复UI选择
        ui_selections = config.get("ui_selections", {})
        if "preview_file_selector_index" in ui_selections:
            self.preview_widget.file_selector.setCurrentIndex(ui_selections["preview_file_selector_index"])
        
        # 更新状态和生成代码
        self._update_controls_state()
        self._update_title()
        self._trigger_code_generation()
    
    def get_initial_dock_title(self) -> str:
        """获取初始停靠标题"""
        return f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]"


# 导出函数
def create_panel_widget(panel_id: int, main_window_ref, initial_config: Optional[Dict[str, Any]] = None) -> AdvancedPIDGeneratorWidget:
    """创建面板组件实例"""
    return AdvancedPIDGeneratorWidget(panel_id, main_window_ref, initial_config)


def get_panel_info() -> Dict[str, Any]:
    """获取面板信息"""
    return {
        "name": "Advanced PID Code Generator",
        "display_name": "高级PID代码生成器",
        "version": "3.0.0",
        "description": "生成高性能C语言PID控制器代码，支持多实例管理和高级配置",
        "author": "YJ Studio",
        "category": "Code Generator",
        "tags": ["PID", "Control", "C", "Code Generation", "Embedded"]
    }


if __name__ == "__main__":
    # 测试代码
    import sys
    from PySide6.QtWidgets import QApplication
    
    class MockErrorLogger:
        def log_error(self, msg, source): print(f"ERROR [{source}]: {msg}")
        def log_warning(self, msg, source): print(f"WARNING [{source}]: {msg}")
        def log_info(self, msg, source): print(f"INFO [{source}]: {msg}")
        def log_debug(self, msg, source): print(f"DEBUG [{source}]: {msg}")
    
    class MockMainWindow:
        def __init__(self):
            self.error_logger = MockErrorLogger()
    
    app = QApplication(sys.argv)
    widget = create_panel_widget(1, MockMainWindow())
    widget.show()
    sys.exit(app.exec())