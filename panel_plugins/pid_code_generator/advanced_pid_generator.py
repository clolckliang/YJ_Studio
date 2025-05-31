# panel_plugins/pid_code_generator/advanced_pid_generator.py
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTextEdit, QComboBox,
    QDoubleSpinBox, QGroupBox, QGridLayout, QFileDialog, QMessageBox, QTabWidget,
    QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QSplitter  # QSplitter Added
)
from PySide6.QtCore import Slot, Qt, QRegularExpression, Signal
from PySide6.QtGui import (
    QFont, QTextCharFormat, QColor, QSyntaxHighlighter, QTextDocument, QBrush
)
from typing import Dict, Any, Optional, Tuple, List, Union
import os
import re
import copy
from datetime import datetime
from pathlib import Path

# 导入 PanelInterface，支持不同的导入路径
try:
    from core.panel_interface import PanelInterface  # type: ignore
except ImportError:
    import sys

    project_root_panel = Path(__file__).resolve().parent.parent
    core_path = project_root_panel.parent / "core"
    if str(core_path) not in sys.path:
        sys.path.insert(0, str(core_path))
    try:
        from panel_interface import PanelInterface  # type: ignore
    except ImportError:
        try:
            from PySide6.QtCore import Signal as pyqtSignal
        except ImportError:
            try:
                from PyQt6.QtCore import pyqtSignal
            except ImportError:
                pyqtSignal = None


        class PanelInterface(QWidget):  # type: ignore
            PANEL_TYPE_NAME: str = "mock_panel"
            PANEL_DISPLAY_NAME: str = "Mock Panel"
            dock_title_changed = pyqtSignal(str) if pyqtSignal else None

            def __init__(self, panel_id, main_window_ref, initial_config=None, parent=None):
                super().__init__(parent)
                self.panel_id = panel_id
                self.main_window_ref = main_window_ref
                self.error_logger = None
                if not hasattr(self, 'error_logger') or self.error_logger is None:
                    self.error_logger = PanelInterface.ErrorLoggerMock()

            def get_config(self) -> Dict[str, Any]: return {}

            def apply_config(self, config: Dict[str, Any]) -> None: pass

            def get_initial_dock_title(self) -> str: return "Mock Panel"

            def on_panel_added(self) -> None: pass

            def on_panel_removed(self) -> None: pass

            def update_theme(self) -> None: pass

            class ErrorLoggerMock:
                def log_error(self, msg, context=""): print(
                    f"ERROR [{context or PanelInterface.PANEL_TYPE_NAME}]: {msg}")

                def log_warning(self, msg, context=""): print(
                    f"WARNING [{context or PanelInterface.PANEL_TYPE_NAME}]: {msg}")

                def log_info(self, msg, context=""): print(f"INFO [{context or PanelInterface.PANEL_TYPE_NAME}]: {msg}")

                def log_debug(self, msg, context=""): print(
                    f"DEBUG [{context or PanelInterface.PANEL_TYPE_NAME}]: {msg}")




class CSyntaxHighlighter(QSyntaxHighlighter):
    """C/C++ 语法高亮器 (改进版)"""

    def __init__(self, parent: QTextDocument):
        super().__init__(parent)
        self.highlighting_rules: List[Tuple[QRegularExpression, QTextCharFormat]] = []
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(86, 156, 214))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "auto", "break", "case", "char", "const", "continue", "default", "do",
            "double", "else", "enum", "extern", "float", "for", "goto", "if",
            "int", "long", "register", "return", "short", "signed", "sizeof", "static",
            "struct", "switch", "typedef", "union", "unsigned", "void", "volatile", "while",
            "asm", "dynamic_cast", "namespace", "reinterpret_cast", "try", "bool",
            "explicit", "new", "static_cast", "typeid", "catch", "false", "operator",
            "template", "typename", "class", "friend", "private", "this", "using",
            "delete", "inline", "public", "throw", "true", "virtual", "wchar_t",
            "uint8_t", "uint16_t", "uint32_t", "uint64_t",
            "int8_t", "int16_t", "int32_t", "int64_t", "NULL"
        ]
        for word in keywords:
            self.highlighting_rules.append((QRegularExpression(f"\\b{word}\\b"), keyword_format))
        type_format = QTextCharFormat()
        type_format.setForeground(QColor(78, 201, 176))
        types = ["PID_HandleTypeDef", "PID_ModeType", "PID_Type", "PID_WorkMode"]
        for word in types:
            self.highlighting_rules.append((QRegularExpression(f"\\b{word}\\b"), type_format))
        preprocessor_format = QTextCharFormat()
        preprocessor_format.setForeground(QColor(155, 155, 155))
        preprocessor_format.setFontItalic(True)
        self.highlighting_rules.append((QRegularExpression("^\\s*#.*"), preprocessor_format))
        single_line_comment_format = QTextCharFormat()
        single_line_comment_format.setForeground(QColor(106, 153, 85))
        self.highlighting_rules.append((QRegularExpression("//[^\n]*"), single_line_comment_format))
        self.multi_line_comment_format = QTextCharFormat()
        self.multi_line_comment_format.setForeground(QColor(106, 153, 85))
        self.comment_start_expression = QRegularExpression("/\\*")
        self.comment_end_expression = QRegularExpression("\\*/")
        quotation_format = QTextCharFormat()
        quotation_format.setForeground(QColor(206, 145, 120))
        self.highlighting_rules.append((QRegularExpression("\".*\""), quotation_format))
        self.highlighting_rules.append((QRegularExpression("'.*?'"), quotation_format))
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(181, 206, 168))
        self.highlighting_rules.append((QRegularExpression("\\b[0-9]+\\.?[0-9]*[fLu]*\\b"), number_format))
        self.highlighting_rules.append((QRegularExpression("\\b0x[0-9a-fA-F]+[Lu]*\\b"), number_format))
        function_format = QTextCharFormat()
        function_format.setForeground(QColor(220, 220, 170))
        self.highlighting_rules.append((QRegularExpression("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()"), function_format))

    def highlightBlock(self, text: str) -> None:
        for pattern, format_rule in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format_rule)
        self.setCurrentBlockState(0)
        start_index = 0
        if self.previousBlockState() != 1:
            match = self.comment_start_expression.match(text)
            start_index = match.capturedStart() if match.hasMatch() else -1
        while start_index >= 0:
            match = self.comment_end_expression.match(text, start_index)
            end_index = match.capturedStart() if match.hasMatch() else -1
            comment_length = 0
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + match.capturedLength()
            self.setFormat(start_index, comment_length, self.multi_line_comment_format)
            match = self.comment_start_expression.match(text, start_index + comment_length)
            start_index = match.capturedStart() if match.hasMatch() else -1


class AdvancedPIDGeneratorWidget(PanelInterface):
    PANEL_TYPE_NAME: str = "advanced_pid_code_generator_v5"
    PANEL_DISPLAY_NAME: str = "PID代码生成器 v5 (多实例)"

    def __init__(self,
                 panel_id: int,
                 main_window_ref: 'SerialDebugger',
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        self._log_debug(f"Initializing {self.PANEL_DISPLAY_NAME}...")

        self.pid_instance_configs: List[Dict[str, Any]] = []
        self.active_pid_instance_index: int = -1
        self.code_config: Dict[str, Any] = self._get_default_code_config()

        self.generated_c_code: str = "// C source code will appear here."
        self.generated_h_code: str = "// Header file code will appear here."
        self.generated_main_c_code: str = "// Example main code will appear here."

        self._init_ui_element_references()
        self._init_ui()

        if initial_config:
            self.apply_config(initial_config)
        else:
            self._add_pid_instance("default_pid")
            if self.pid_instance_list_widget and self.pid_instance_list_widget.count() > 0:
                self.pid_instance_list_widget.setCurrentRow(0)
            self._load_global_code_config_to_ui()
            self._trigger_full_code_generation_and_preview_update()

        self._update_title()
        self._log_debug(f"{self.PANEL_DISPLAY_NAME} initialization complete.")

    def _get_default_pid_params(self) -> Dict[str, Any]:
        return {
            "kp": 1.0, "ki": 0.1, "kd": 0.01,
            "max_output": 100.0, "min_output": -100.0,
            "integral_limit": 50.0, "sample_time": 0.01,
            "algorithm_type": "advanced",
            "kff": 0.0, "ff_weight": 1.0,
            "output_ramp": 0.0, "deadband": 0.0,
            "integral_separation_threshold": 1000.0,
            "d_filter_coef": 0.1, "input_filter_coef": 0.0, "setpoint_filter_coef": 0.0,
            "pid_type": "standard",
            "work_mode": "position",
            "adaptive_enable": False, "adaptive_kp_min": 0.1, "adaptive_kp_max": 10.0,
            "adaptive_ki_min": 0.01, "adaptive_ki_max": 1.0,
            "adaptive_kd_min": 0.001, "adaptive_kd_max": 0.1,
            "fuzzy_enable": False, "fuzzy_error_range": 100.0, "fuzzy_derror_range": 10.0,
        }

    def _get_default_code_config(self) -> Dict[str, Any]:
        return {
            "struct_name": "PID_HandleTypeDef", "function_prefix": "PID",
            "use_float": True, "include_comments": True, "include_header": True,
            "header_name": "pid.h", "use_template": True, "optimization_level": "standard",
        }

    def _init_ui_element_references(self):
        self.pid_instance_list_widget: Optional[QListWidget] = None
        self.add_instance_button: Optional[QPushButton] = None
        self.remove_instance_button: Optional[QPushButton] = None
        self.rename_instance_button: Optional[QPushButton] = None
        self.instance_name_edit: Optional[QLineEdit] = None
        self.algorithm_combo: Optional[QComboBox] = None
        self.pid_type_combo: Optional[QComboBox] = None
        self.work_mode_combo: Optional[QComboBox] = None
        self.kp_spinbox: Optional[QDoubleSpinBox] = None
        self.ki_spinbox: Optional[QDoubleSpinBox] = None
        self.kd_spinbox: Optional[QDoubleSpinBox] = None
        self.kff_spinbox: Optional[QDoubleSpinBox] = None
        self.ff_weight_spinbox: Optional[QDoubleSpinBox] = None
        self.sample_time_spinbox: Optional[QDoubleSpinBox] = None
        self.max_output_spinbox: Optional[QDoubleSpinBox] = None
        self.min_output_spinbox: Optional[QDoubleSpinBox] = None
        self.integral_limit_spinbox: Optional[QDoubleSpinBox] = None
        self.output_ramp_spinbox: Optional[QDoubleSpinBox] = None
        self.deadband_spinbox: Optional[QDoubleSpinBox] = None
        self.integral_separation_spinbox: Optional[QDoubleSpinBox] = None
        self.d_filter_spinbox: Optional[QDoubleSpinBox] = None
        self.input_filter_spinbox: Optional[QDoubleSpinBox] = None
        self.setpoint_filter_spinbox: Optional[QDoubleSpinBox] = None
        self.adaptive_enable_checkbox: Optional[QCheckBox] = None
        self.adaptive_kp_min_spinbox: Optional[QDoubleSpinBox] = None
        self.adaptive_kp_max_spinbox: Optional[QDoubleSpinBox] = None
        self.adaptive_ki_min_spinbox: Optional[QDoubleSpinBox] = None
        self.adaptive_ki_max_spinbox: Optional[QDoubleSpinBox] = None
        self.adaptive_kd_min_spinbox: Optional[QDoubleSpinBox] = None
        self.adaptive_kd_max_spinbox: Optional[QDoubleSpinBox] = None
        self.fuzzy_enable_checkbox: Optional[QCheckBox] = None
        self.fuzzy_error_range_spinbox: Optional[QDoubleSpinBox] = None
        self.fuzzy_derror_range_spinbox: Optional[QDoubleSpinBox] = None
        self.struct_name_edit: Optional[QLineEdit] = None
        self.function_prefix_edit: Optional[QLineEdit] = None
        self.header_name_edit: Optional[QLineEdit] = None
        self.optimization_combo: Optional[QComboBox] = None
        self.use_float_checkbox: Optional[QCheckBox] = None
        self.include_comments_checkbox: Optional[QCheckBox] = None
        self.include_header_checkbox: Optional[QCheckBox] = None
        self.use_template_checkbox: Optional[QCheckBox] = None
        self.code_preview: Optional[QTextEdit] = None
        self.highlighter: Optional[CSyntaxHighlighter] = None
        self.preview_file_selector: Optional[QComboBox] = None
        self.preview_label: Optional[QLabel] = None
        self.generate_button: Optional[QPushButton] = None
        self.export_button: Optional[QPushButton] = None

    def _init_ui(self) -> None:
        self._log_debug("Building UI with layout optimizations...")
        main_layout = QVBoxLayout(self)  # 主垂直布局

        # --- 使用 QSplitter 分隔实例管理和参数配置 ---
        splitter = QSplitter(Qt.Horizontal)  # 水平分割器

        # --- 左侧: PID 实例管理部分 ---
        instance_management_container = QWidget()  # 使用 QWidget 作为容器以应用布局
        instance_management_layout = QVBoxLayout(instance_management_container)
        instance_management_layout.setContentsMargins(0, 0, 0, 0)  # 移除容器的边距

        instance_management_group = QGroupBox("PID 控制器实例")  # 卡片式分组
        instance_group_layout = QVBoxLayout(instance_management_group)  # 垂直布局按钮和列表

        # 列表
        self.pid_instance_list_widget = QListWidget()
        self.pid_instance_list_widget.currentItemChanged.connect(self._on_selected_pid_instance_changed)
        self.pid_instance_list_widget.setMinimumWidth(180)  # 固定最小宽度
        self.pid_instance_list_widget.setMaximumWidth(250)  # 固定最大宽度 (可调整)
        instance_group_layout.addWidget(self.pid_instance_list_widget)

        # 名称输入
        name_input_layout = QHBoxLayout()
        name_input_layout.addWidget(QLabel("实例名:"))
        self.instance_name_edit = QLineEdit()
        self.instance_name_edit.setPlaceholderText("例如: motor_pid")
        name_input_layout.addWidget(self.instance_name_edit)
        instance_group_layout.addLayout(name_input_layout)

        # 按钮区域
        instance_buttons_layout = QHBoxLayout()  # 横向排列按钮
        instance_buttons_layout.setSpacing(10)  # 按钮间距
        self.add_instance_button = QPushButton("添加")
        self.add_instance_button.clicked.connect(self._on_add_instance_button_clicked)
        self.remove_instance_button = QPushButton("移除")
        self.remove_instance_button.clicked.connect(self._on_remove_instance_button_clicked)
        self.rename_instance_button = QPushButton("重命名")
        self.rename_instance_button.clicked.connect(self._on_rename_instance_button_clicked)
        instance_buttons_layout.addWidget(self.add_instance_button)
        instance_buttons_layout.addWidget(self.remove_instance_button)
        instance_buttons_layout.addWidget(self.rename_instance_button)
        instance_buttons_layout.addStretch()
        instance_group_layout.addLayout(instance_buttons_layout)

        instance_management_layout.addWidget(instance_management_group)
        splitter.addWidget(instance_management_container)

        # --- 右侧: 参数配置和预览选项卡 ---
        right_panel_widget = QWidget()  # 容器
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)

        self.param_tabs = QTabWidget()
        self.param_tabs.setTabPosition(QTabWidget.West)  # 标签页在左侧纵向排列
        self.param_tabs.addTab(self._create_basic_params_tab(), "PID 参数")
        self.param_tabs.addTab(self._create_advanced_features_tab(), "高级特性")
        self.param_tabs.addTab(self._create_code_config_tab(), "代码生成配置")
        self.param_tabs.addTab(self._create_preview_tab(), "代码预览")
        right_panel_layout.addWidget(self.param_tabs)

        splitter.addWidget(right_panel_widget)

        # 设置 QSplitter 的初始大小比例 (例如，左侧占1份，右侧占3份)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

        # --- 底部操作按钮 ---
        bottom_button_layout = QHBoxLayout()
        self.generate_button = QPushButton("生成/刷新所有预览")
        self.generate_button.clicked.connect(self._on_generate_code_button_clicked)
        bottom_button_layout.addWidget(self.generate_button)

        self.export_button = QPushButton("导出代码文件")
        self.export_button.clicked.connect(self._on_export_code_button_clicked)
        bottom_button_layout.addWidget(self.export_button)
        bottom_button_layout.addStretch()
        main_layout.addLayout(bottom_button_layout)

        self.setLayout(main_layout)
        self._log_debug("UI built with layout optimizations.")

    def _create_basic_params_tab(self) -> QWidget:
        self._log_debug("Creating PID Parameters Tab...")
        widget = QWidget()
        main_tab_layout = QVBoxLayout(widget)
        core_params_group = QGroupBox("核心PID参数")
        core_layout = QGridLayout(core_params_group)
        core_layout.addWidget(QLabel("PID算法:"), 0, 0);
        self.algorithm_combo = QComboBox();
        self.algorithm_combo.addItems(["高级PID", "位置式PID (内置)", "增量式PID (内置)"]);
        self.algorithm_combo.currentTextChanged.connect(self._on_pid_param_ui_changed);
        core_layout.addWidget(self.algorithm_combo, 0, 1)
        core_layout.addWidget(QLabel("PID类型 (P,D作用):"), 1, 0);
        self.pid_type_combo = QComboBox();
        self.pid_type_combo.addItems(["标准 (Perr, Derr)", "PI-D (Perr, Dmeas)", "I-PD (Pmeas, Dmeas)"]);
        self.pid_type_combo.currentTextChanged.connect(self._on_pid_param_ui_changed);
        core_layout.addWidget(self.pid_type_combo, 1, 1)
        core_layout.addWidget(QLabel("工作模式 (输出):"), 2, 0);
        self.work_mode_combo = QComboBox();
        self.work_mode_combo.addItems(["位置模式", "速度模式 (增量)"]);
        self.work_mode_combo.currentTextChanged.connect(self._on_pid_param_ui_changed);
        core_layout.addWidget(self.work_mode_combo, 2, 1)
        core_layout.addWidget(QLabel("比例 (Kp):"), 0, 2);
        self.kp_spinbox = QDoubleSpinBox();
        self.kp_spinbox.setRange(-1000.0, 1000.0);
        self.kp_spinbox.setDecimals(6);
        self.kp_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        core_layout.addWidget(self.kp_spinbox, 0, 3)
        core_layout.addWidget(QLabel("积分 (Ki, 连续域):"), 1, 2);
        self.ki_spinbox = QDoubleSpinBox();
        self.ki_spinbox.setRange(0, 1000.0);
        self.ki_spinbox.setDecimals(6);
        self.ki_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        core_layout.addWidget(self.ki_spinbox, 1, 3)
        core_layout.addWidget(QLabel("微分 (Kd, 连续域):"), 2, 2);
        self.kd_spinbox = QDoubleSpinBox();
        self.kd_spinbox.setRange(0, 1000.0);
        self.kd_spinbox.setDecimals(6);
        self.kd_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        core_layout.addWidget(self.kd_spinbox, 2, 3)
        core_layout.addWidget(QLabel("采样时间 (s):"), 3, 2);
        self.sample_time_spinbox = QDoubleSpinBox();
        self.sample_time_spinbox.setRange(0.000001, 10.0);
        self.sample_time_spinbox.setDecimals(6);
        self.sample_time_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        core_layout.addWidget(self.sample_time_spinbox, 3, 3)
        main_tab_layout.addWidget(core_params_group)
        limits_group = QGroupBox("输出与积分限制")
        limits_layout = QGridLayout(limits_group)
        limits_layout.addWidget(QLabel("最大输出:"), 0, 0);
        self.max_output_spinbox = QDoubleSpinBox();
        self.max_output_spinbox.setRange(0, 10000.0);
        self.max_output_spinbox.setDecimals(2);
        self.max_output_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        limits_layout.addWidget(self.max_output_spinbox, 0, 1)
        limits_layout.addWidget(QLabel("最小输出:"), 0, 2);
        self.min_output_spinbox = QDoubleSpinBox();
        self.min_output_spinbox.setRange(-10000.0, 0);
        self.min_output_spinbox.setDecimals(2);
        self.min_output_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        limits_layout.addWidget(self.min_output_spinbox, 0, 3)
        limits_layout.addWidget(QLabel("积分限幅 (绝对值):"), 1, 0);
        self.integral_limit_spinbox = QDoubleSpinBox();
        self.integral_limit_spinbox.setRange(0.0, 10000.0);
        self.integral_limit_spinbox.setDecimals(2);
        self.integral_limit_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        limits_layout.addWidget(self.integral_limit_spinbox, 1, 1)
        limits_layout.addWidget(QLabel("输出变化率限制 (单位/秒, 0不限制):"), 1, 2);
        self.output_ramp_spinbox = QDoubleSpinBox();
        self.output_ramp_spinbox.setRange(0.0, 10000.0);
        self.output_ramp_spinbox.setDecimals(3);
        self.output_ramp_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        limits_layout.addWidget(self.output_ramp_spinbox, 1, 3)
        main_tab_layout.addWidget(limits_group)
        adv_filter_group = QGroupBox("高级控制与滤波器")
        adv_filter_layout = QGridLayout(adv_filter_group)
        adv_filter_layout.addWidget(QLabel("前馈 (Kff):"), 0, 0);
        self.kff_spinbox = QDoubleSpinBox();
        self.kff_spinbox.setRange(-1000.0, 1000.0);
        self.kff_spinbox.setDecimals(6);
        self.kff_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adv_filter_layout.addWidget(self.kff_spinbox, 0, 1)
        adv_filter_layout.addWidget(QLabel("前馈权重 (0-1):"), 0, 2);
        self.ff_weight_spinbox = QDoubleSpinBox();
        self.ff_weight_spinbox.setRange(0.0, 1.0);
        self.ff_weight_spinbox.setDecimals(3);
        self.ff_weight_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adv_filter_layout.addWidget(self.ff_weight_spinbox, 0, 3)
        adv_filter_layout.addWidget(QLabel("死区大小:"), 1, 0);
        self.deadband_spinbox = QDoubleSpinBox();
        self.deadband_spinbox.setRange(0.0, 1000.0);
        self.deadband_spinbox.setDecimals(6);
        self.deadband_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adv_filter_layout.addWidget(self.deadband_spinbox, 1, 1)
        adv_filter_layout.addWidget(QLabel("积分分离阈值 (误差绝对值):"), 1, 2);
        self.integral_separation_spinbox = QDoubleSpinBox();
        self.integral_separation_spinbox.setRange(0.0, 10000.0);
        self.integral_separation_spinbox.setDecimals(3);
        self.integral_separation_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adv_filter_layout.addWidget(self.integral_separation_spinbox, 1, 3)
        adv_filter_layout.addWidget(QLabel("微分滤波系数 (0-1, 0无):"), 2, 0);
        self.d_filter_spinbox = QDoubleSpinBox();
        self.d_filter_spinbox.setRange(0.0, 1.0);
        self.d_filter_spinbox.setDecimals(3);
        self.d_filter_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adv_filter_layout.addWidget(self.d_filter_spinbox, 2, 1)
        adv_filter_layout.addWidget(QLabel("输入滤波系数 (0-1, 0无):"), 2, 2);
        self.input_filter_spinbox = QDoubleSpinBox();
        self.input_filter_spinbox.setRange(0.0, 1.0);
        self.input_filter_spinbox.setDecimals(3);
        self.input_filter_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adv_filter_layout.addWidget(self.input_filter_spinbox, 2, 3)
        adv_filter_layout.addWidget(QLabel("设定值滤波系数 (0-1, 0无):"), 3, 0);
        self.setpoint_filter_spinbox = QDoubleSpinBox();
        self.setpoint_filter_spinbox.setRange(0.0, 1.0);
        self.setpoint_filter_spinbox.setDecimals(3);
        self.setpoint_filter_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adv_filter_layout.addWidget(self.setpoint_filter_spinbox, 3, 1)
        main_tab_layout.addWidget(adv_filter_group)
        main_tab_layout.addStretch()
        return widget

    def _create_advanced_features_tab(self) -> QWidget:
        self._log_debug("Creating Advanced Features Tab (Adaptive/Fuzzy)...")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        adaptive_group = QGroupBox("自适应控制 (概念性, C逻辑需自行实现)")
        adaptive_layout = QGridLayout(adaptive_group)
        self.adaptive_enable_checkbox = QCheckBox("启用自适应控制");
        self.adaptive_enable_checkbox.stateChanged.connect(self._on_pid_param_ui_changed);
        adaptive_layout.addWidget(self.adaptive_enable_checkbox, 0, 0, 1, 4)
        adaptive_layout.addWidget(QLabel("Kp 最小值:"), 1, 0);
        self.adaptive_kp_min_spinbox = QDoubleSpinBox();
        self.adaptive_kp_min_spinbox.setRange(0.001, 100);
        self.adaptive_kp_min_spinbox.setDecimals(6);
        self.adaptive_kp_min_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adaptive_layout.addWidget(self.adaptive_kp_min_spinbox, 1, 1)
        adaptive_layout.addWidget(QLabel("Kp 最大值:"), 1, 2);
        self.adaptive_kp_max_spinbox = QDoubleSpinBox();
        self.adaptive_kp_max_spinbox.setRange(0.001, 100);
        self.adaptive_kp_max_spinbox.setDecimals(6);
        self.adaptive_kp_max_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adaptive_layout.addWidget(self.adaptive_kp_max_spinbox, 1, 3)
        adaptive_layout.addWidget(QLabel("Ki 最小值:"), 2, 0);
        self.adaptive_ki_min_spinbox = QDoubleSpinBox();
        self.adaptive_ki_min_spinbox.setRange(0.001, 10);
        self.adaptive_ki_min_spinbox.setDecimals(6);
        self.adaptive_ki_min_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adaptive_layout.addWidget(self.adaptive_ki_min_spinbox, 2, 1)
        adaptive_layout.addWidget(QLabel("Ki 最大值:"), 2, 2);
        self.adaptive_ki_max_spinbox = QDoubleSpinBox();
        self.adaptive_ki_max_spinbox.setRange(0.001, 10);
        self.adaptive_ki_max_spinbox.setDecimals(6);
        self.adaptive_ki_max_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adaptive_layout.addWidget(self.adaptive_ki_max_spinbox, 2, 3)
        adaptive_layout.addWidget(QLabel("Kd 最小值:"), 3, 0);
        self.adaptive_kd_min_spinbox = QDoubleSpinBox();
        self.adaptive_kd_min_spinbox.setRange(0.001, 1);
        self.adaptive_kd_min_spinbox.setDecimals(6);
        self.adaptive_kd_min_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adaptive_layout.addWidget(self.adaptive_kd_min_spinbox, 3, 1)
        adaptive_layout.addWidget(QLabel("Kd 最大值:"), 3, 2);
        self.adaptive_kd_max_spinbox = QDoubleSpinBox();
        self.adaptive_kd_max_spinbox.setRange(0.001, 1);
        self.adaptive_kd_max_spinbox.setDecimals(6);
        self.adaptive_kd_max_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        adaptive_layout.addWidget(self.adaptive_kd_max_spinbox, 3, 3)
        layout.addWidget(adaptive_group)
        fuzzy_group = QGroupBox("模糊PID控制 (概念性, C逻辑需自行实现)")
        fuzzy_layout = QGridLayout(fuzzy_group)
        self.fuzzy_enable_checkbox = QCheckBox("启用模糊PID控制");
        self.fuzzy_enable_checkbox.stateChanged.connect(self._on_pid_param_ui_changed);
        fuzzy_layout.addWidget(self.fuzzy_enable_checkbox, 0, 0, 1, 2)
        fuzzy_layout.addWidget(QLabel("模糊误差范围:"), 1, 0);
        self.fuzzy_error_range_spinbox = QDoubleSpinBox();
        self.fuzzy_error_range_spinbox.setRange(1, 1000);
        self.fuzzy_error_range_spinbox.setDecimals(2);
        self.fuzzy_error_range_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        fuzzy_layout.addWidget(self.fuzzy_error_range_spinbox, 1, 1)
        fuzzy_layout.addWidget(QLabel("模糊误差变化率范围:"), 2, 0);
        self.fuzzy_derror_range_spinbox = QDoubleSpinBox();
        self.fuzzy_derror_range_spinbox.setRange(1, 100);
        self.fuzzy_derror_range_spinbox.setDecimals(2);
        self.fuzzy_derror_range_spinbox.valueChanged.connect(self._on_pid_param_ui_changed);
        fuzzy_layout.addWidget(self.fuzzy_derror_range_spinbox, 2, 1)
        layout.addWidget(fuzzy_group)
        layout.addStretch()
        return widget

    def _create_code_config_tab(self) -> QWidget:
        self._log_debug("Creating Code Config Tab...")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("全局代码生成选项 (应用于所有实例的库文件)")
        grid_layout = QGridLayout(group)
        grid_layout.addWidget(QLabel("库结构体名称:"), 0, 0);
        self.struct_name_edit = QLineEdit();
        self.struct_name_edit.textChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.struct_name_edit, 0, 1)
        grid_layout.addWidget(QLabel("库函数前缀:"), 1, 0);
        self.function_prefix_edit = QLineEdit();
        self.function_prefix_edit.textChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.function_prefix_edit, 1, 1)
        grid_layout.addWidget(QLabel("库头文件名称 (.h):"), 2, 0);
        self.header_name_edit = QLineEdit();
        self.header_name_edit.textChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.header_name_edit, 2, 1)
        grid_layout.addWidget(QLabel("优化级别 (概念性):"), 3, 0);
        self.optimization_combo = QComboBox();
        self.optimization_combo.addItems(["基础", "标准", "高级"]);
        self.optimization_combo.currentTextChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.optimization_combo, 3, 1)
        self.use_float_checkbox = QCheckBox("使用 float 类型 (否则 double)");
        self.use_float_checkbox.stateChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.use_float_checkbox, 4, 0)
        self.include_comments_checkbox = QCheckBox("包含注释 (内置生成器)");
        self.include_comments_checkbox.stateChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.include_comments_checkbox, 4, 1)
        self.include_header_checkbox = QCheckBox("生成头文件内容");
        self.include_header_checkbox.stateChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.include_header_checkbox, 5, 0)
        self.use_template_checkbox = QCheckBox("使用模板生成库代码");
        self.use_template_checkbox.stateChanged.connect(self._on_global_code_config_changed);
        grid_layout.addWidget(self.use_template_checkbox, 5, 1)
        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _create_preview_tab(self) -> QWidget:
        self._log_debug("Creating Preview Tab with selector...")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("预览文件:"))
        self.preview_file_selector = QComboBox()
        self.preview_file_selector.addItems(["C 源文件 (库)", "头文件 (库)", "示例 Main (.c)"])
        self.preview_file_selector.currentIndexChanged.connect(self._on_preview_file_selected)
        selector_layout.addWidget(self.preview_file_selector)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        self.preview_label = QLabel("当前预览: C 源文件 (库)")
        layout.addWidget(self.preview_label)
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Consolas", 10))
        self.code_preview.setLineWrapMode(QTextEdit.NoWrap)
        self.highlighter = CSyntaxHighlighter(self.code_preview.document())
        layout.addWidget(self.code_preview)
        return widget

    @Slot()
    def _on_add_instance_button_clicked(self):
        instance_name_text = self.instance_name_edit.text().strip() if self.instance_name_edit else ""
        name_to_add = instance_name_text
        ok_pressed = True
        if not name_to_add:
            name_to_add, ok_pressed = QInputDialog.getText(self, "添加PID实例", "输入实例名称 (例如 motor_pid):")
        if ok_pressed and name_to_add:
            if any(inst['name'] == name_to_add for inst in self.pid_instance_configs):
                QMessageBox.warning(self, "名称冲突", f"名为 '{name_to_add}' 的PID实例已存在。")
                return
            self._add_pid_instance(name_to_add)
            if self.instance_name_edit: self.instance_name_edit.clear()
        elif ok_pressed and not name_to_add:
            QMessageBox.warning(self, "名称无效", "PID实例名称不能为空。")

    def _add_pid_instance(self, name: str):
        self._log_debug(f"Adding PID instance: {name}")
        new_config = {
            'name': name,
            'params': copy.deepcopy(self._get_default_pid_params()),
        }
        self.pid_instance_configs.append(new_config)
        if self.pid_instance_list_widget:
            item = QListWidgetItem(name)
            self.pid_instance_list_widget.addItem(item)
            self.pid_instance_list_widget.setCurrentItem(item)
        self.active_pid_instance_index = len(self.pid_instance_configs) - 1
        # _on_selected_pid_instance_changed will call _load_params_to_ui

    @Slot()
    def _on_remove_instance_button_clicked(self):
        if not self.pid_instance_list_widget:
            return

        row_to_remove = self.pid_instance_list_widget.currentRow()

        if row_to_remove < 0:
            QMessageBox.information(self, "移除实例", "请先选择一个要移除的PID实例。")
            return

        # Critical check: ensure row_to_remove is a valid index for the data list
        if not (0 <= row_to_remove < len(self.pid_instance_configs)):
            self._log_error(f"CRITICAL: Mismatch between QListWidget selection and internal data. "
                            f"Attempting to remove QListWidget row {row_to_remove}, "
                            f"but len(pid_instance_configs) is {len(self.pid_instance_configs)}.")
            # Attempt to re-sync or warn user
            # For now, just prevent the crash
            QMessageBox.critical(self, "内部错误", "列表数据不一致，无法移除。请尝试重新选择。")
            return

        instance_name = self.pid_instance_configs[row_to_remove]['name']
        reply = QMessageBox.question(self, "确认移除",
                                     f"确定要移除PID实例 '{instance_name}' 吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._log_debug(f"Removing PID instance: {instance_name} at actual list index {row_to_remove}")

            # Remove from data list first
            del self.pid_instance_configs[row_to_remove]

            # Then remove from QListWidget; this might trigger currentItemChanged
            # Block signals temporarily if direct handling is preferred after this.
            self.pid_instance_list_widget.blockSignals(True)
            item_widget = self.pid_instance_list_widget.takeItem(row_to_remove)
            if item_widget:
                del item_widget  # Ensure QListWidgetItem is deleted
            self.pid_instance_list_widget.blockSignals(False)

            # After removal, determine the new selection
            new_count = len(self.pid_instance_configs)
            if new_count == 0:
                self.active_pid_instance_index = -1
                self._load_params_to_ui(-1)  # Load defaults/clear UI
                if self.instance_name_edit: self.instance_name_edit.clear()
            else:
                # Try to select the item at the same index, or the last item if index is now out of bounds
                new_selection_index = min(row_to_remove, new_count - 1)
                self.pid_instance_list_widget.setCurrentRow(new_selection_index)
                # _on_selected_pid_instance_changed will be called by setCurrentRow if the row actually changes
                # or if it's the same row but content might need refresh (though _load_params_to_ui handles it)
                if self.pid_instance_list_widget.currentRow() == new_selection_index:
                    # If setCurrentRow didn't change the index (e.g., last item removed, selection stays on new last)
                    # we might need to manually trigger the update if the signal isn't emitted.
                    self._on_selected_pid_instance_changed(self.pid_instance_list_widget.currentItem(), None)

            self._update_title()

    @Slot()
    def _on_rename_instance_button_clicked(self):
        if not self.pid_instance_list_widget or self.pid_instance_list_widget.currentRow() < 0:
            QMessageBox.information(self, "重命名实例", "请先选择一个要重命名的PID实例。")
            return

        current_row = self.pid_instance_list_widget.currentRow()
        if not (0 <= current_row < len(self.pid_instance_configs)):
            self._log_error(f"Rename error: QListWidget row {current_row} out of sync with configs.")
            return

        old_name = self.pid_instance_configs[current_row]['name']
        suggested_new_name = self.instance_name_edit.text().strip() if self.instance_name_edit and self.instance_name_edit.text().strip() else old_name
        new_name, ok = QInputDialog.getText(self, "重命名PID实例", "输入新名称:", QLineEdit.Normal, suggested_new_name)

        if ok and new_name and new_name != old_name:
            if any(inst['name'] == new_name for i, inst in enumerate(self.pid_instance_configs) if i != current_row):
                QMessageBox.warning(self, "名称冲突", f"名为 '{new_name}' 的PID实例已存在。")
                return
            self._log_debug(f"Renaming PID instance '{old_name}' to '{new_name}'")
            self.pid_instance_configs[current_row]['name'] = new_name
            current_list_item = self.pid_instance_list_widget.item(current_row)
            if current_list_item: current_list_item.setText(new_name)
            if self.instance_name_edit: self.instance_name_edit.setText(new_name)
            self._update_title()
        elif ok and not new_name:
            QMessageBox.warning(self, "名称无效", "PID实例名称不能为空。")

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_selected_pid_instance_changed(self, current: Optional[QListWidgetItem],
                                          previous: Optional[QListWidgetItem]):
        if not self.pid_instance_list_widget:
            self.active_pid_instance_index = -1
            self._load_params_to_ui(-1)
            self._update_title()
            return

        instance_name_to_edit = ""
        if current is None:
            self.active_pid_instance_index = -1
        else:
            # Get index directly from QListWidget, this is the source of truth for UI selection
            current_row_in_widget = self.pid_instance_list_widget.row(current)

            # Validate this index against our data list
            if 0 <= current_row_in_widget < len(self.pid_instance_configs):
                self.active_pid_instance_index = current_row_in_widget
                instance_name_to_edit = self.pid_instance_configs[self.active_pid_instance_index]['name']
                self._log_debug(
                    f"Selected PID instance: {instance_name_to_edit} at actual list index {self.active_pid_instance_index}")
            else:
                # This case indicates a desynchronization. Log it and try to recover.
                self._log_error(f"Desync on selection: QListWidget row {current_row_in_widget} "
                                f"is out of bounds for pid_instance_configs (len {len(self.pid_instance_configs)}). "
                                f"Resetting active_pid_instance_index.")
                self.active_pid_instance_index = -1

        if self.instance_name_edit:
            self.instance_name_edit.setText(instance_name_to_edit)

        self._load_params_to_ui(self.active_pid_instance_index)  # This will handle -1 correctly
        self._update_title()

    def _load_params_to_ui(self, instance_index: int):
        self._log_debug(f"Loading params to UI for instance index: {instance_index}")
        params_to_load: Dict[str, Any]
        is_valid_instance = instance_index >= 0 and instance_index < len(self.pid_instance_configs)
        if is_valid_instance:
            params_to_load = self.pid_instance_configs[instance_index]['params']
        else:
            params_to_load = self._get_default_pid_params()

        if self.algorithm_combo: self.algorithm_combo.setCurrentText(
            {"advanced": "高级PID", "positional": "位置式PID (内置)", "incremental": "增量式PID (内置)"}.get(
                params_to_load.get("algorithm_type"), "高级PID"))
        if self.pid_type_combo: self.pid_type_combo.setCurrentText(
            {"standard": "标准 (Perr, Derr)", "pi_d": "PI-D (Perr, Dmeas)", "i_pd": "I-PD (Pmeas, Dmeas)"}.get(
                params_to_load.get("pid_type"), "标准 (Perr, Derr)"))
        if self.work_mode_combo: self.work_mode_combo.setCurrentText(
            {"position": "位置模式", "velocity": "速度模式 (增量)"}.get(params_to_load.get("work_mode"), "位置模式"))
        param_spinbox_map = {
            "kp": self.kp_spinbox, "ki": self.ki_spinbox, "kd": self.kd_spinbox,
            "kff": self.kff_spinbox, "ff_weight": self.ff_weight_spinbox,
            "sample_time": self.sample_time_spinbox, "max_output": self.max_output_spinbox,
            "min_output": self.min_output_spinbox, "integral_limit": self.integral_limit_spinbox,
            "output_ramp": self.output_ramp_spinbox, "deadband": self.deadband_spinbox,
            "integral_separation_threshold": self.integral_separation_spinbox,
            "d_filter_coef": self.d_filter_spinbox, "input_filter_coef": self.input_filter_spinbox,
            "setpoint_filter_coef": self.setpoint_filter_spinbox,
            "adaptive_kp_min": self.adaptive_kp_min_spinbox, "adaptive_kp_max": self.adaptive_kp_max_spinbox,
            "adaptive_ki_min": self.adaptive_ki_min_spinbox, "adaptive_ki_max": self.adaptive_ki_max_spinbox,
            "adaptive_kd_min": self.adaptive_kd_min_spinbox, "adaptive_kd_max": self.adaptive_kd_max_spinbox,
            "fuzzy_error_range": self.fuzzy_error_range_spinbox, "fuzzy_derror_range": self.fuzzy_derror_range_spinbox,
        }
        for key, spinbox in param_spinbox_map.items():
            if spinbox: spinbox.setValue(params_to_load.get(key, self._get_default_pid_params().get(key, 0.0)))
        if self.adaptive_enable_checkbox: self.adaptive_enable_checkbox.setChecked(
            params_to_load.get("adaptive_enable", False))
        if self.fuzzy_enable_checkbox: self.fuzzy_enable_checkbox.setChecked(params_to_load.get("fuzzy_enable", False))
        enable_editing = is_valid_instance
        pid_params_tab_index = -1
        adv_features_tab_index = -1
        if self.param_tabs:
            for i in range(self.param_tabs.count()):
                if self.param_tabs.tabText(i) == "PID 参数":
                    pid_params_tab_index = i
                elif self.param_tabs.tabText(i) == "高级特性":
                    adv_features_tab_index = i
            if pid_params_tab_index != -1 and self.param_tabs.widget(pid_params_tab_index):
                self.param_tabs.widget(pid_params_tab_index).setEnabled(enable_editing)
            if adv_features_tab_index != -1 and self.param_tabs.widget(adv_features_tab_index):
                self.param_tabs.widget(adv_features_tab_index).setEnabled(enable_editing)
        self._log_debug(f"UI updated with params for index {instance_index}. Editing enabled: {enable_editing}")

    def _load_global_code_config_to_ui(self):
        self._log_debug("Loading current self.code_config to UI...")
        if self.struct_name_edit: self.struct_name_edit.setText(
            self.code_config.get("struct_name", "PID_HandleTypeDef"))
        if self.function_prefix_edit: self.function_prefix_edit.setText(self.code_config.get("function_prefix", "PID"))
        if self.header_name_edit: self.header_name_edit.setText(self.code_config.get("header_name", "pid.h"))
        if self.optimization_combo: self.optimization_combo.setCurrentText(
            self.code_config.get("optimization_level", "标准").capitalize())
        checkbox_map = {
            "use_float": self.use_float_checkbox, "include_comments": self.include_comments_checkbox,
            "include_header": self.include_header_checkbox, "use_template": self.use_template_checkbox,
        }
        for key, checkbox in checkbox_map.items():
            if checkbox: checkbox.setChecked(self.code_config.get(key, True))

    @Slot()
    def _on_pid_param_ui_changed(self):
        if self.active_pid_instance_index < 0 or self.active_pid_instance_index >= len(self.pid_instance_configs):
            return
        current_config = self.pid_instance_configs[self.active_pid_instance_index]
        params = current_config['params']
        if self.algorithm_combo: params["algorithm_type"] = {"高级PID": "advanced", "位置式PID (内置)": "positional",
                                                             "增量式PID (内置)": "incremental"}.get(
            self.algorithm_combo.currentText(), "advanced")
        if self.pid_type_combo: params["pid_type"] = {"标准 (Perr, Derr)": "standard", "PI-D (Perr, Dmeas)": "pi_d",
                                                      "I-PD (Pmeas, Dmeas)": "i_pd"}.get(
            self.pid_type_combo.currentText(), "standard")
        if self.work_mode_combo: params["work_mode"] = {"位置模式": "position", "速度模式 (增量)": "velocity"}.get(
            self.work_mode_combo.currentText(), "position")
        if self.kp_spinbox: params["kp"] = self.kp_spinbox.value()
        if self.ki_spinbox: params["ki"] = self.ki_spinbox.value()
        if self.kd_spinbox: params["kd"] = self.kd_spinbox.value()
        if self.kff_spinbox: params["kff"] = self.kff_spinbox.value()
        if self.ff_weight_spinbox: params["ff_weight"] = self.ff_weight_spinbox.value()
        if self.sample_time_spinbox: params["sample_time"] = self.sample_time_spinbox.value()
        if self.max_output_spinbox: params["max_output"] = self.max_output_spinbox.value()
        if self.min_output_spinbox: params["min_output"] = self.min_output_spinbox.value()
        if self.integral_limit_spinbox: params["integral_limit"] = self.integral_limit_spinbox.value()
        if self.output_ramp_spinbox: params["output_ramp"] = self.output_ramp_spinbox.value()
        if self.deadband_spinbox: params["deadband"] = self.deadband_spinbox.value()
        if self.integral_separation_spinbox: params[
            "integral_separation_threshold"] = self.integral_separation_spinbox.value()
        if self.d_filter_spinbox: params["d_filter_coef"] = self.d_filter_spinbox.value()
        if self.input_filter_spinbox: params["input_filter_coef"] = self.input_filter_spinbox.value()
        if self.setpoint_filter_spinbox: params["setpoint_filter_coef"] = self.setpoint_filter_spinbox.value()
        if self.adaptive_enable_checkbox: params["adaptive_enable"] = self.adaptive_enable_checkbox.isChecked()
        if self.adaptive_kp_min_spinbox: params["adaptive_kp_min"] = self.adaptive_kp_min_spinbox.value()
        if self.adaptive_kp_max_spinbox: params["adaptive_kp_max"] = self.adaptive_kp_max_spinbox.value()
        if self.adaptive_ki_min_spinbox: params["adaptive_ki_min"] = self.adaptive_ki_min_spinbox.value()
        if self.adaptive_ki_max_spinbox: params["adaptive_ki_max"] = self.adaptive_ki_max_spinbox.value()
        if self.adaptive_kd_min_spinbox: params["adaptive_kd_min"] = self.adaptive_kd_min_spinbox.value()
        if self.adaptive_kd_max_spinbox: params["adaptive_kd_max"] = self.adaptive_kd_max_spinbox.value()
        if self.fuzzy_enable_checkbox: params["fuzzy_enable"] = self.fuzzy_enable_checkbox.isChecked()
        if self.fuzzy_error_range_spinbox: params["fuzzy_error_range"] = self.fuzzy_error_range_spinbox.value()
        if self.fuzzy_derror_range_spinbox: params["fuzzy_derror_range"] = self.fuzzy_derror_range_spinbox.value()
        if self.sender() == self.algorithm_combo:
            self._update_title()
            if self.use_template_checkbox:
                is_advanced = (params["algorithm_type"] == "advanced")
                self.use_template_checkbox.setChecked(is_advanced)
                self.code_config["use_template"] = is_advanced
        self._log_debug(f"PID params for instance '{current_config['name']}' updated from UI.")

    @Slot()
    def _on_global_code_config_changed(self):
        if self.struct_name_edit: self.code_config[
            "struct_name"] = self.struct_name_edit.text().strip() or "PID_HandleTypeDef"
        if self.function_prefix_edit: self.code_config[
            "function_prefix"] = self.function_prefix_edit.text().strip() or "PID"
        if self.header_name_edit: self.code_config["header_name"] = self.header_name_edit.text().strip() or "pid.h"
        if self.optimization_combo: self.code_config[
            "optimization_level"] = self.optimization_combo.currentText().lower()
        if self.use_float_checkbox: self.code_config["use_float"] = self.use_float_checkbox.isChecked()
        if self.include_comments_checkbox: self.code_config[
            "include_comments"] = self.include_comments_checkbox.isChecked()
        if self.include_header_checkbox: self.code_config["include_header"] = self.include_header_checkbox.isChecked()
        if self.use_template_checkbox: self.code_config["use_template"] = self.use_template_checkbox.isChecked()
        self._log_debug("Global code config updated from UI.")

    @Slot()
    def _on_generate_code_button_clicked(self):
        self._log_debug("Generate/Refresh Preview button clicked.")
        self._trigger_full_code_generation_and_preview_update()
        self._log_info("All code previews updated.", self.PANEL_TYPE_NAME)

    def _trigger_full_code_generation_and_preview_update(self):
        self._on_pid_param_ui_changed()
        self._on_global_code_config_changed()
        self.generated_c_code = self._generate_c_code()
        self.generated_h_code = self._generate_h_code()
        self.generated_main_c_code = self._generate_main_c_code_for_all_instances()
        self._update_preview_content()

    @Slot()
    def _on_preview_file_selected(self):
        self._update_preview_content()

    def _update_preview_content(self):
        if not self.preview_file_selector or not self.code_preview or not self.preview_label:
            return
        selected_index = self.preview_file_selector.currentIndex()
        content_to_display = ""
        label_text = "当前预览: "
        if selected_index == 0:
            content_to_display = self.generated_c_code
            label_text += "C 源文件 (库)"
        elif selected_index == 1:
            content_to_display = self.generated_h_code
            label_text += "头文件 (库)"
        elif selected_index == 2:
            content_to_display = self.generated_main_c_code
            label_text += "示例 Main (.c)"
        self.code_preview.setPlainText(content_to_display)
        self.preview_label.setText(label_text)
        self._log_debug(f"Preview updated to show: {self.preview_file_selector.currentText()}")

    @Slot()
    def _on_export_code_button_clicked(self):
        self._log_debug("Export Code button clicked.")
        self._trigger_full_code_generation_and_preview_update()
        if not self.pid_instance_configs:
            QMessageBox.information(self, "导出提示", "请至少添加并配置一个PID实例。")
            return
        suggested_base_name = Path(self.code_config.get("header_name", "pid_controller.h")).stem
        user_path_suggestion = str(Path(os.getcwd()) / suggested_base_name)
        file_path_base, _ = QFileDialog.getSaveFileName(
            self, "选择保存位置和基础文件名 (例如 pid_control)", user_path_suggestion, "All Files (*)"
        )
        if not file_path_base: return
        save_dir = Path(file_path_base).parent
        base_name_selected = Path(file_path_base).stem
        save_dir.mkdir(parents=True, exist_ok=True)
        h_content = self.generated_h_code
        c_content = self.generated_c_code
        main_c_content = self.generated_main_c_code
        h_file_name = self.code_config.get("header_name", f"{base_name_selected}_lib.h")
        c_file_name = f"{Path(h_file_name).stem}.c"
        main_c_file_name = f"{base_name_selected}_main.c"
        files_to_write = []
        if self.code_config.get("include_header", True) and h_content and not h_content.startswith("// Error"):
            files_to_write.append((save_dir / h_file_name, h_content))
        if c_content and not c_content.startswith("// Error"):
            files_to_write.append((save_dir / c_file_name, c_content))
        if main_c_content and not main_c_content.startswith("// Error"):
            files_to_write.append((save_dir / main_c_file_name, main_c_content))
        if not files_to_write:
            QMessageBox.warning(self, "导出警告", "未能生成任何有效代码文件。请检查配置和模板。")
            self._log_warning("Export failed, no valid content generated.", self.PANEL_TYPE_NAME)
            return
        exported_files_paths = []
        try:
            for file_path, content in files_to_write:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                exported_files_paths.append(str(file_path))
            QMessageBox.information(self, "导出成功", "代码已导出到以下文件:\n" + "\n".join(exported_files_paths))
            self._log_info(f"Code exported to: {', '.join(exported_files_paths)}", self.PANEL_TYPE_NAME)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出代码时发生错误:\n{str(e)}")
            self._log_error(f"Multi-file export failed: {str(e)}", self.PANEL_TYPE_NAME)

    def _generate_h_code(self) -> str:
        self._log_debug("Generating H code (library)...")
        if not self.code_config.get("include_header"):
            return "// Header file generation skipped by global configuration."
        if not self.code_config.get("use_template"):
            return "// Built-in generator does not produce separate H file for library."
        algo_for_lib_template = "advanced"
        h_template_path = self._get_template_path(algo_type_override=algo_for_lib_template, extension="h")
        if not (h_template_path and h_template_path.exists()):
            return f"// Error: Library Header template not found: {h_template_path}"
        return self._generate_from_template_file(h_template_path, use_instance_params=False)

    def _generate_c_code(self) -> str:
        self._log_debug("Generating C code (library)...")
        if not self.code_config.get("use_template"):
            return self._generate_builtin_code(use_instance_params=False)
        algo_for_lib_template = "advanced"
        c_template_path = self._get_template_path(algo_type_override=algo_for_lib_template, extension="c")
        if not (c_template_path and c_template_path.exists()):
            self._log_warning(f"Library C template not found ({c_template_path}), falling back to built-in.",
                              self.PANEL_TYPE_NAME)
            return self._generate_builtin_code(use_instance_params=False)
        return self._generate_from_template_file(c_template_path, use_instance_params=False)

    def _generate_main_c_code_for_all_instances(self) -> str:
        self._log_debug("Generating Main C code for all instances...")
        main_template_path = Path(__file__).parent / "templates" / "user_main_template.c"
        if not main_template_path.exists():
            return f"// Error: Main C template not found: {main_template_path}"
        try:
            template_content = main_template_path.read_text(encoding='utf-8')
            data_t = "float" if self.code_config.get("use_float") else "double"
            global_replacements = {
                '{{HEADER_NAME}}': self.code_config.get("header_name", "pid.h"),
                '{{STRUCT_NAME}}': self.code_config.get("struct_name", "PID_HandleTypeDef"),
                '{{FUNCTION_PREFIX}}': self.code_config.get("function_prefix", "PID"),
                '{{DATA_TYPE}}': data_t,
                '{{TIMESTAMP}}': self._get_current_time(),
            }
            processed_code = template_content
            for placeholder, value in global_replacements.items():
                processed_code = re.sub(re.escape(placeholder), str(value), processed_code)
            declarations_block = []
            initializations_block = []
            example_computations_block = []
            sfx = "f" if data_t == "float" else ""
            for i, instance_config in enumerate(self.pid_instance_configs):
                instance_name = instance_config['name']
                params = instance_config['params']
                sample_t = max(params.get("sample_time", 0.01), 0.000001)
                declarations_block.append(f"    {self.code_config.get('struct_name')} {instance_name};")
                kp_val = params.get('kp', 1.0)
                ki_val = params.get('ki', 0.1)
                kd_val = params.get('kd', 0.01)
                init_call = (
                    f"    {self.code_config.get('function_prefix')}_Init(&{instance_name}, "
                    f"{kp_val}{sfx}, {ki_val}{sfx}, {kd_val}{sfx}, {sample_t}{sfx});"
                )
                initializations_block.append(init_call)
                initializations_block.append(
                    f"    {self.code_config.get('function_prefix')}_SetOutputLimits(&{instance_name}, {params.get('max_output', 100.0)}{sfx});")
                initializations_block.append(
                    f"    {self.code_config.get('function_prefix')}_SetIntegralLimits(&{instance_name}, {params.get('integral_limit', 50.0)}{sfx});")
                initializations_block.append(
                    f"    printf(\"Initialized PID: {instance_name} with Kp={kp_val}, Ki_cont={ki_val}, Kd_cont={kd_val}, Ts={sample_t}\\n\");")
                if i == 0:
                    example_computations_block.append(f"    // Example computation for {instance_name}")
                    example_computations_block.append(f"    {data_t} {instance_name}_setpoint = 50.0{sfx};")
                    example_computations_block.append(f"    {data_t} {instance_name}_measurement = 0.0{sfx};")
                    example_computations_block.append(f"    for (int j = 0; j < 5; ++j) {{")
                    example_computations_block.append(
                        f"        {data_t} {instance_name}_output = {self.code_config.get('function_prefix')}_Compute(&{instance_name}, {instance_name}_setpoint, {instance_name}_measurement);")
                    example_computations_block.append(
                        f"        {instance_name}_measurement = simulate_system_response({instance_name}_measurement, {instance_name}_output, {sample_t}{sfx}); ")
                    example_computations_block.append(
                        f"        printf(\"  {instance_name}: Step %d, SP=%.2f, PV=%.2f, Out=%.2f\\n\", j+1, (double){instance_name}_setpoint, (double){instance_name}_measurement, (double){instance_name}_output);")
                    example_computations_block.append(f"    }}")
                    example_computations_block.append(f"")
            processed_code = re.sub(re.escape('{{PID_INSTANCE_DECLARATIONS}}'), "\n".join(declarations_block),
                                    processed_code)
            processed_code = re.sub(re.escape('{{PID_INSTANCE_INITIALIZATIONS}}'), "\n".join(initializations_block),
                                    processed_code)
            processed_code = re.sub(re.escape('{{PID_EXAMPLE_COMPUTATIONS}}'), "\n".join(example_computations_block),
                                    processed_code)
            single_instance_params = self.pid_instance_configs[0][
                'params'] if self.pid_instance_configs else self._get_default_pid_params()
            sample_t_single = max(single_instance_params.get("sample_time", 0.01), 0.000001)
            old_placeholders_replacements = {
                '{{KP_UI_VALUE}}': f"{single_instance_params.get('kp', 1.0)}{sfx}",
                '{{KI_UI_VALUE}}': f"{single_instance_params.get('ki', 0.1)}{sfx}",
                '{{KD_UI_VALUE}}': f"{single_instance_params.get('kd', 0.01)}{sfx}",
                '{{MAX_OUTPUT_UI_VALUE}}': f"{single_instance_params.get('max_output', 100.0)}{sfx}",
                '{{INTEGRAL_LIMIT_UI_VALUE}}': f"{single_instance_params.get('integral_limit', 50.0)}{sfx}",
                '{{SAMPLE_TIME_UI_VALUE}}': f"{sample_t_single}{sfx}",
                '{{DEADBAND_UI_VALUE}}': f"{single_instance_params.get('deadband', 0.0)}{sfx}",
            }
            for placeholder, value in old_placeholders_replacements.items():
                processed_code = re.sub(re.escape(placeholder), str(value), processed_code)
            return processed_code
        except Exception as e:
            self._log_error(f"user_main.c generation for all instances failed: {e}", self.PANEL_TYPE_NAME)
            return f"// Error generating user_main.c for all instances: {e}"

    def _get_template_path(self, algo_type_override: Optional[str] = None, extension: str = "c") -> Optional[Path]:
        template_dir = Path(__file__).parent / "templates"
        algo_type_to_use = algo_type_override
        if not algo_type_to_use:
            if self.active_pid_instance_index != -1 and self.active_pid_instance_index < len(
                    self.pid_instance_configs):  # Check bounds
                algo_type_to_use = self.pid_instance_configs[self.active_pid_instance_index]['params'].get(
                    "algorithm_type", "advanced")
            else:
                algo_type_to_use = "advanced"
        base_name_map = {
            "advanced": "advanced_pid_template",
            "positional": "positional_pid_template",
            "incremental": "incremental_pid_template"
        }
        base_name = base_name_map.get(algo_type_to_use)
        if not base_name:
            self._log_warning(f"No template base name defined for algorithm: {algo_type_to_use}", self.PANEL_TYPE_NAME)
            return None
        template_file = template_dir / f"{base_name}.{extension}"
        if template_file.exists():
            return template_file
        else:
            self._log_warning(f"Template file not found: {template_file} for algorithm {algo_type_to_use}",
                              self.PANEL_TYPE_NAME)
            return None

    def _generate_from_template_file(self, template_path: Path, use_instance_params: bool = True,
                                     instance_index_for_params: int = -1) -> str:
        self._log_debug(
            f"Generating from template: {template_path}, use_instance_params: {use_instance_params}, instance_idx: {instance_index_for_params}")
        try:
            template_content = template_path.read_text(encoding='utf-8')
            data_t = "float" if self.code_config.get("use_float") else "double"
            sfx = "f" if data_t == "float" else ""
            params_source: Dict[str, Any]
            if use_instance_params:
                idx_to_use = instance_index_for_params if instance_index_for_params != -1 else self.active_pid_instance_index
                if idx_to_use != -1 and idx_to_use < len(self.pid_instance_configs):  # Check bounds
                    params_source = self.pid_instance_configs[idx_to_use]['params']
                else:
                    params_source = self._get_default_pid_params()
            else:
                params_source = self._get_default_pid_params()
            sample_t = max(params_source.get("sample_time", 0.01), 0.000001)
            replacements = {
                '{{STRUCT_NAME}}': self.code_config.get("struct_name", "PID_HandleTypeDef"),
                '{{FUNCTION_PREFIX}}': self.code_config.get("function_prefix", "PID"),
                '{{DATA_TYPE}}': data_t,
                '{{HEADER_NAME}}': self.code_config.get("header_name", "pid.h"),
                '{{TIMESTAMP}}': self._get_current_time(),
                '{{KP_DEFAULT}}': f"{params_source.get('kp', 1.0)}{sfx}",
                '{{KI_DEFAULT}}': f"{params_source.get('ki', 0.1) * sample_t}{sfx}",
                '{{KD_DEFAULT}}': f"{params_source.get('kd', 0.01) / sample_t}{sfx}",
                '{{KFF_DEFAULT}}': f"{params_source.get('kff', 0.0)}{sfx}",
                '{{FF_WEIGHT_DEFAULT}}': f"{params_source.get('ff_weight', 1.0)}{sfx}",
                '{{OUTPUT_LIMIT_DEFAULT}}': f"{params_source.get('max_output', 100.0)}{sfx}",
                '{{INTEGRAL_LIMIT_DEFAULT}}': f"{params_source.get('integral_limit', 50.0)}{sfx}",
                '{{OUTPUT_RAMP_DEFAULT}}': f"{params_source.get('output_ramp', 0.0)}{sfx}",
                '{{DEADBAND_DEFAULT}}': f"{params_source.get('deadband', 0.0)}{sfx}",
                '{{INTEGRAL_SEPARATION_THRESHOLD_DEFAULT}}': f"{params_source.get('integral_separation_threshold', 1000.0)}{sfx}",
                '{{D_FILTER_COEF_DEFAULT}}': f"{params_source.get('d_filter_coef', 0.1)}{sfx}",
                '{{INPUT_FILTER_COEF_DEFAULT}}': f"{params_source.get('input_filter_coef', 0.0)}{sfx}",
                '{{SETPOINT_FILTER_COEF_DEFAULT}}': f"{params_source.get('setpoint_filter_coef', 0.0)}{sfx}",
                '{{SAMPLE_TIME_DEFAULT}}': f"{sample_t}{sfx}",
                '{{KP_UI_VALUE}}': f"{params_source.get('kp', 1.0)}{sfx}",
                '{{KI_UI_VALUE}}': f"{params_source.get('ki', 0.1)}{sfx}",
                '{{KD_UI_VALUE}}': f"{params_source.get('kd', 0.01)}{sfx}",
                '{{MAX_OUTPUT_UI_VALUE}}': f"{params_source.get('max_output', 100.0)}{sfx}",
                '{{MIN_OUTPUT_UI_VALUE}}': f"{params_source.get('min_output', -100.0)}{sfx}",
                '{{INTEGRAL_LIMIT_UI_VALUE}}': f"{params_source.get('integral_limit', 50.0)}{sfx}",
                '{{SAMPLE_TIME_UI_VALUE}}': f"{sample_t}{sfx}",
                '{{DEADBAND_UI_VALUE}}': f"{params_source.get('deadband', 0.0)}{sfx}",
                '{{D_FILTER_COEF_UI_VALUE}}': f"{params_source.get('d_filter_coef', 0.1)}{sfx}",
            }
            generated_code = template_content
            for placeholder, value in replacements.items():
                escaped_placeholder = re.escape(placeholder)
                generated_code = re.sub(escaped_placeholder, str(value), generated_code)
            return generated_code
        except FileNotFoundError:
            self._log_error(f"Template file not found: {template_path}", self.PANEL_TYPE_NAME)
            return f"// Error: Template file not found: {template_path}"
        except Exception as e:
            self._log_error(f"Failed to generate from template {template_path.name}: {e}", self.PANEL_TYPE_NAME)
            return f"// Error generating from template {template_path.name}: {e}"

    def _generate_builtin_code(self, use_instance_params: bool = True, instance_index_for_params: int = -1) -> str:
        self._log_debug("Generating C code using built-in logic...")
        params_source: Dict[str, Any]
        if use_instance_params:
            idx_to_use = instance_index_for_params if instance_index_for_params != -1 else self.active_pid_instance_index
            if idx_to_use != -1 and idx_to_use < len(self.pid_instance_configs):  # Check bounds
                params_source = self.pid_instance_configs[idx_to_use]['params']
            else:
                params_source = self._get_default_pid_params()
        else:
            params_source = self._get_default_pid_params()
        data_type = "float" if self.code_config.get("use_float") else "double"
        sfx = "f" if data_type == "float" else ""
        struct_name = self.code_config.get("struct_name", "Builtin_PID_Controller")
        func_prefix = self.code_config.get("function_prefix", "Builtin_PID")
        sample_t = max(params_source.get("sample_time", 0.01), 0.000001)
        code = []
        if self.code_config.get("include_comments"):
            code.append(
                f"// Built-in PID Controller ({params_source.get('algorithm_type')}) - {self._get_current_time()}\n")
        if self.code_config.get("include_header") and self.code_config.get("header_name"):
            code.append(f"#include \"{self.code_config.get('header_name')}\"\n")
        code.append("#include <math.h> \n")
        code.append(f"typedef struct {{")
        code.append(f"  {data_type} Kp, Ki_d, Kd_d; ")
        code.append(f"  {data_type} setpoint, integral, prev_error, prev_measure;")
        code.append(f"  {data_type} out_min, out_max, integral_limit;")
        code.append(f"}} {struct_name};\n")
        code.append(
            f"void {func_prefix}_Init({struct_name} *pid, {data_type} kp, {data_type} ki_c, {data_type} kd_c) {{")
        code.append(f"  pid->Kp = kp;")
        code.append(f"  pid->Ki_d = ki_c * {sample_t}{sfx};")
        code.append(f"  pid->Kd_d = kd_c / {sample_t}{sfx};")
        code.append(f"  pid->out_min = {params_source.get('min_output', -100.0)}{sfx};")
        code.append(f"  pid->out_max = {params_source.get('max_output', 100.0)}{sfx};")
        code.append(f"  pid->integral_limit = {params_source.get('integral_limit', 50.0)}{sfx};")
        code.append(f"  pid->integral = 0.0{sfx}; pid->prev_error = 0.0{sfx}; pid->prev_measure = 0.0{sfx};")
        code.append(f"}}\n")
        code.append(f"{data_type} {func_prefix}_Compute({struct_name} *pid, {data_type} sp, {data_type} pv) {{")
        code.append(f"  pid->setpoint = sp;")
        code.append(f"  {data_type} error = pid->setpoint - pv;")
        code.append(f"  pid->integral += pid->Ki_d * error;")
        code.append(f"  if (pid->integral > pid->integral_limit) pid->integral = pid->integral_limit;")
        code.append(f"  else if (pid->integral < -pid->integral_limit) pid->integral = -pid->integral_limit;")
        code.append(f"  {data_type} derivative = (pv - pid->prev_measure) / {sample_t}{sfx}; // D on measurement")
        code.append(f"  {data_type} output = pid->Kp * error + pid->integral - pid->Kd_d * derivative;")
        code.append(f"  if (output > pid->out_max) output = pid->out_max;")
        code.append(f"  else if (output < pid->out_min) output = pid->out_min;")
        code.append(f"  pid->prev_error = error; pid->prev_measure = pv;")
        code.append(f"  return output;")
        code.append(f"}}\n")
        return "\n".join(code)

    def _get_current_time(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _update_title(self) -> None:
        try:
            title_suffix = ""
            current_row = -1
            if self.pid_instance_list_widget:
                current_row = self.pid_instance_list_widget.currentRow()

            if current_row != -1 and current_row < len(self.pid_instance_configs):
                title_suffix = f" - 编辑: {self.pid_instance_configs[current_row]['name']}"

            new_title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]{title_suffix}"
            if self.dock_title_changed:
                self.dock_title_changed.emit(new_title)
        except Exception as e:
            self._log_error(f"Failed to update panel title: {e}", self.PANEL_TYPE_NAME)

    def _log_error(self, message: str, context: Optional[str] = None):
        effective_context = context or self.PANEL_TYPE_NAME
        if self.error_logger and hasattr(self.error_logger, 'log_error'):
            self.error_logger.log_error(message, effective_context)
        else:
            print(f"ERROR [{effective_context}]: {message}")

    def _log_warning(self, message: str, context: Optional[str] = None):
        effective_context = context or self.PANEL_TYPE_NAME
        if self.error_logger and hasattr(self.error_logger, 'log_warning'):
            self.error_logger.log_warning(message, effective_context)
        else:
            print(f"WARNING [{effective_context}]: {message}")

    def _log_info(self, message: str, context: Optional[str] = None):
        effective_context = context or self.PANEL_TYPE_NAME
        if self.error_logger and hasattr(self.error_logger, 'log_info'):
            self.error_logger.log_info(message, effective_context)
        else:
            print(f"INFO [{effective_context}]: {message}")

    def _log_debug(self, message: str, context: Optional[str] = None):
        effective_context = context or self.PANEL_TYPE_NAME
        if self.error_logger and hasattr(self.error_logger, 'log_debug'):
            self.error_logger.log_debug(message, effective_context)

    def get_config(self) -> Dict[str, Any]:
        self._log_debug("Getting config...")
        if self.active_pid_instance_index != -1 and self.active_pid_instance_index < len(
                self.pid_instance_configs):  # Check bounds
            self._on_pid_param_ui_changed()
        self._on_global_code_config_changed()
        config = {
            "version": "5.0.1",  # Incremented version for this fix
            "pid_instance_configs": copy.deepcopy(self.pid_instance_configs),
            "active_pid_instance_index": self.pid_instance_list_widget.currentRow() if self.pid_instance_list_widget else -1,
            # Get current row directly
            "global_code_config": self.code_config.copy(),
            "panel_type": self.PANEL_TYPE_NAME,
            "ui_selections": {
                "preview_file_selector_index": self.preview_file_selector.currentIndex() if self.preview_file_selector else 0,
            }
        }
        return config

    def apply_config(self, config: Dict[str, Any]) -> None:
        self._log_debug(f"Applying config (version: {config.get('version')})...")
        self.pid_instance_configs = copy.deepcopy(config.get("pid_instance_configs", []))

        # Load global code config first
        global_code_cfg = config.get("global_code_config")
        if global_code_cfg:
            self.code_config.update(global_code_cfg)
        else:
            self.code_config = self._get_default_code_config()
        self._load_global_code_config_to_ui()

        # Populate QListWidget
        if self.pid_instance_list_widget:
            self.pid_instance_list_widget.clear()
            for instance_cfg in self.pid_instance_configs:
                self.pid_instance_list_widget.addItem(QListWidgetItem(instance_cfg['name']))

        # Restore active_pid_instance_index and selection
        # Ensure the index is valid for the newly populated list
        restored_active_index = config.get("active_pid_instance_index", -1)
        new_list_count = len(self.pid_instance_configs)

        if new_list_count == 0:
            self.active_pid_instance_index = -1
        elif 0 <= restored_active_index < new_list_count:
            self.active_pid_instance_index = restored_active_index
        else:  # Invalid index from config or -1, select first if possible
            self.active_pid_instance_index = 0 if new_list_count > 0 else -1  # Corrected: only set to 0 if list not empty

        if self.pid_instance_list_widget and self.active_pid_instance_index != -1:
            self.pid_instance_list_widget.setCurrentRow(self.active_pid_instance_index)
            # _on_selected_pid_instance_changed will be called by setCurrentRow
        else:  # No items or no valid selection, load defaults to UI
            self._load_params_to_ui(-1)

        ui_selections = config.get("ui_selections", {})
        if self.preview_file_selector and "preview_file_selector_index" in ui_selections:
            self.preview_file_selector.setCurrentIndex(ui_selections["preview_file_selector_index"])

        self._trigger_full_code_generation_and_preview_update()
        self._update_title()
        self._log_debug("Config applied.")

    def _update_ui_from_params(self):
        pass

    def _update_ui_from_code_config(self):
        pass

    def get_initial_dock_title(self) -> str:
        return f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]"

    def on_panel_added(self) -> None:
        super().on_panel_added()
        self._log_info(f"Panel added to main window.", self.PANEL_TYPE_NAME)

    def on_panel_removed(self) -> None:
        self._log_info(f"Panel removed. Cleaning up...", self.PANEL_TYPE_NAME)
        super().on_panel_removed()

    def update_theme(self) -> None:
        super().update_theme()
        self._log_debug("Theme update requested.")
        if self.code_preview and self.code_preview.document():
            self.highlighter = CSyntaxHighlighter(self.code_preview.document())
            current_text = self.code_preview.toPlainText()
            self.code_preview.setPlainText("")
            self.code_preview.setPlainText(current_text)

