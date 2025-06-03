# panel_plugins/pid_code_generator/advanced_pid_generator.py
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTextEdit, QComboBox,
    QDoubleSpinBox, QGroupBox, QGridLayout, QFileDialog, QMessageBox, QTabWidget,
    QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QSplitter,
    QSizePolicy # 导入 QSizePolicy
)
from PySide6.QtCore import Slot, Qt, QRegularExpression, Signal, QTimer # 导入 QTimer 用于防抖
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


# 定义一些常量，提高可读性和可维护性
DEFAULT_FLOAT_SUFFIX = "f"
DEFAULT_DOUBLE_SUFFIX = ""
DEFAULT_SAMPLE_TIME = 0.01

# C/C++ 语法高亮器
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
            "int8_t", "int16_t", "int32_t", "int64_t", "NULL",
            # 新增的PID相关类型和宏
            "PID_HandleTypeDef", "PID_ModeType", "PID_Type", "PID_WorkMode",
            "PID_MODE_MANUAL", "PID_MODE_AUTOMATIC",
            "PID_TYPE_STANDARD", "PID_TYPE_PI_D", "PID_TYPE_I_PD",
            "PID_MODE_POSITION", "PID_MODE_VELOCITY", "INFINITY"
        ]
        for word in keywords:
            self.highlighting_rules.append((QRegularExpression(f"\\b{word}\\b"), keyword_format))

        type_format = QTextCharFormat()
        type_format.setForeground(QColor(78, 201, 176))
        # 移除了重复的PID类型，因为它们已包含在keywords中
        # types = ["PID_HandleTypeDef", "PID_ModeType", "PID_Type", "PID_WorkMode"]
        # for word in types:
        #     self.highlighting_rules.append((QRegularExpression(f"\\b{word}\\b"), type_format))

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
    PANEL_TYPE_NAME: str = "advanced_pid_code_generator_"
    PANEL_DISPLAY_NAME: str = "PID代码生成器 "

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

        # 设置一个防抖定时器
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(10)  # 10ms 延迟
        self.debounce_timer.timeout.connect(self._trigger_full_code_generation_and_preview_update)

        if initial_config:
            self.apply_config(initial_config)
        else:
            self._add_pid_instance("default_pid")
            if self.pid_instance_list_widget and self.pid_instance_list_widget.count() > 0:
                self.pid_instance_list_widget.setCurrentRow(0)
            self._load_global_code_config_to_ui()
            self._trigger_full_code_generation_and_preview_update() # 初始加载时立即生成

        self._update_title()
        self._log_debug(f"{self.PANEL_DISPLAY_NAME} initialization complete.")

    def _get_default_pid_params(self) -> Dict[str, Any]:
        """获取默认的PID参数配置。"""
        return {
            "kp": 1.0, "ki": 0.1, "kd": 0.01,
            "max_output": 100.0, "min_output": -100.0,
            "integral_limit": 50.0, "sample_time": DEFAULT_SAMPLE_TIME,
            "algorithm_type": "advanced", # 默认使用高级PID模板
            "kff": 0.0, "ff_weight": 1.0,
            "output_ramp": 0.0, "deadband": 0.0,
            "integral_separation_threshold": 1000.0,
            "d_filter_coef": 0.1, "input_filter_coef": 0.0, "setpoint_filter_coef": 0.0,
            "pid_type": "standard", # PID_Type
            "work_mode": "position", # PID_WorkMode
            "adaptive_enable": False, "adaptive_kp_min": 0.1, "adaptive_kp_max": 10.0,
            "adaptive_ki_min": 0.01, "adaptive_ki_max": 1.0,
            "adaptive_kd_min": 0.001, "adaptive_kd_max": 0.1,
            "fuzzy_enable": False, "fuzzy_error_range": 100.0, "fuzzy_derror_range": 10.0,
        }

    def _get_default_code_config(self) -> Dict[str, Any]:
        """获取默认的代码生成配置。"""
        return {
            "struct_name": "PID_HandleTypeDef", "function_prefix": "PID",
            "use_float": True, "include_comments": True, "include_header": True,
            "header_name": "pid.h", "use_template": True, "optimization_level": "standard",
            "float_suffix": DEFAULT_FLOAT_SUFFIX, # 新增浮点数后缀配置
            "data_type": "float" # 新增数据类型配置
        }

    def _init_ui_element_references(self):
        """初始化UI元素引用，避免在__init__中直接创建以保持清晰。"""
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
        self.status_label: Optional[QLabel] = None # 用于显示状态信息

    def _init_ui(self) -> None:
        """构建用户界面。"""
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
        self.param_tabs.currentChanged.connect(self._on_tab_changed) # 切换标签页时触发
        # 增加 QTabWidget 的最小高度，以确保它有足够的垂直空间
        self.param_tabs.setMinimumHeight(600) # 从400增加到600

        right_panel_layout.addWidget(self.param_tabs)

        splitter.addWidget(right_panel_widget)

        # 设置 QSplitter 的初始大小比例 (例如，左侧占1份，右侧占3份)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

        # --- 底部操作按钮和状态栏 ---
        bottom_layout = QVBoxLayout()
        bottom_button_layout = QHBoxLayout()
        self.generate_button = QPushButton("生成/刷新所有预览")
        self.generate_button.clicked.connect(self._on_generate_code_button_clicked)
        bottom_button_layout.addWidget(self.generate_button)

        self.export_button = QPushButton("导出代码文件")
        self.export_button.clicked.connect(self._on_export_code_button_clicked)
        bottom_button_layout.addWidget(self.export_button)
        bottom_button_layout.addStretch()
        bottom_layout.addLayout(bottom_button_layout)

        self.status_label = QLabel("准备就绪。")
        self.status_label.setStyleSheet("color: gray; padding: 5px;")
        bottom_layout.addWidget(self.status_label)

        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)
        self._log_debug("UI built with layout optimizations.")

    def _create_basic_params_tab(self) -> QWidget:
        """创建PID参数配置标签页。"""
        self._log_debug("Creating PID Parameters Tab...")
        widget = QWidget()
        main_tab_layout = QVBoxLayout(widget)

        # 核心PID参数
        core_params_group = QGroupBox("核心PID参数")
        core_layout = QGridLayout(core_params_group)
        core_layout.addWidget(QLabel("PID算法:"), 0, 0)
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["高级PID", "位置式PID (内置)", "增量式PID (内置)"])
        self.algorithm_combo.currentTextChanged.connect(self._queue_param_change)
        core_layout.addWidget(self.algorithm_combo, 0, 1)

        core_layout.addWidget(QLabel("PID类型 (P,D作用):"), 1, 0)
        self.pid_type_combo = QComboBox()
        self.pid_type_combo.addItems(["标准 (Perr, Derr)", "PI-D (Perr, Dmeas)", "I-PD (Pmeas, Dmeas)"])
        self.pid_type_combo.currentTextChanged.connect(self._queue_param_change)
        core_layout.addWidget(self.pid_type_combo, 1, 1)

        core_layout.addWidget(QLabel("工作模式 (输出):"), 2, 0)
        self.work_mode_combo = QComboBox()
        self.work_mode_combo.addItems(["位置模式", "速度模式 (增量)"])
        self.work_mode_combo.currentTextChanged.connect(self._queue_param_change)
        core_layout.addWidget(self.work_mode_combo, 2, 1)

        # Kp, Ki, Kd, Sample Time
        core_layout.addWidget(QLabel("比例 (Kp):"), 0, 2)
        self.kp_spinbox = QDoubleSpinBox()
        self.kp_spinbox.setRange(-1000.0, 1000.0)
        self.kp_spinbox.setDecimals(6)
        self.kp_spinbox.valueChanged.connect(self._queue_param_change)
        core_layout.addWidget(self.kp_spinbox, 0, 3)

        core_layout.addWidget(QLabel("积分 (Ki, 连续域):"), 1, 2)
        self.ki_spinbox = QDoubleSpinBox()
        self.ki_spinbox.setRange(0, 1000.0)
        self.ki_spinbox.setDecimals(6)
        self.ki_spinbox.valueChanged.connect(self._queue_param_change)
        core_layout.addWidget(self.ki_spinbox, 1, 3)

        core_layout.addWidget(QLabel("微分 (Kd, 连续域):"), 2, 2)
        self.kd_spinbox = QDoubleSpinBox()
        self.kd_spinbox.setRange(0, 1000.0)
        self.kd_spinbox.setDecimals(6)
        self.kd_spinbox.valueChanged.connect(self._queue_param_change)
        core_layout.addWidget(self.kd_spinbox, 2, 3)

        core_layout.addWidget(QLabel("采样时间 (s):"), 3, 2)
        self.sample_time_spinbox = QDoubleSpinBox()
        self.sample_time_spinbox.setRange(0.000001, 10.0)
        self.sample_time_spinbox.setDecimals(6)
        self.sample_time_spinbox.valueChanged.connect(self._queue_param_change)
        core_layout.addWidget(self.sample_time_spinbox, 3, 3)
        main_tab_layout.addWidget(core_params_group)

        # 输出与积分限制
        limits_group = QGroupBox("输出与积分限制")
        limits_layout = QGridLayout(limits_group)
        limits_layout.addWidget(QLabel("最大输出:"), 0, 0)
        self.max_output_spinbox = QDoubleSpinBox()
        self.max_output_spinbox.setRange(0, 10000.0)
        self.max_output_spinbox.setDecimals(2)
        self.max_output_spinbox.valueChanged.connect(self._queue_param_change)
        limits_layout.addWidget(self.max_output_spinbox, 0, 1)

        limits_layout.addWidget(QLabel("最小输出:"), 0, 2)
        self.min_output_spinbox = QDoubleSpinBox()
        self.min_output_spinbox.setRange(-10000.0, 0)
        self.min_output_spinbox.setDecimals(2)
        self.min_output_spinbox.valueChanged.connect(self._queue_param_change)
        limits_layout.addWidget(self.min_output_spinbox, 0, 3)

        limits_layout.addWidget(QLabel("积分限幅 (绝对值):"), 1, 0)
        self.integral_limit_spinbox = QDoubleSpinBox()
        self.integral_limit_spinbox.setRange(0.0, 10000.0)
        self.integral_limit_spinbox.setDecimals(2)
        self.integral_limit_spinbox.valueChanged.connect(self._queue_param_change)
        limits_layout.addWidget(self.integral_limit_spinbox, 1, 1)

        limits_layout.addWidget(QLabel("输出变化率限制 (单位/秒, 0不限制):"), 1, 2)
        self.output_ramp_spinbox = QDoubleSpinBox()
        self.output_ramp_spinbox.setRange(0.0, 10000.0)
        self.output_ramp_spinbox.setDecimals(3)
        self.output_ramp_spinbox.valueChanged.connect(self._queue_param_change)
        limits_layout.addWidget(self.output_ramp_spinbox, 1, 3)
        main_tab_layout.addWidget(limits_group)

        # 高级控制与滤波器
        adv_filter_group = QGroupBox("高级控制与滤波器")
        adv_filter_layout = QGridLayout(adv_filter_group)
        adv_filter_layout.addWidget(QLabel("前馈 (Kff):"), 0, 0)
        self.kff_spinbox = QDoubleSpinBox()
        self.kff_spinbox.setRange(-1000.0, 1000.0)
        self.kff_spinbox.setDecimals(6)
        self.kff_spinbox.valueChanged.connect(self._queue_param_change)
        adv_filter_layout.addWidget(self.kff_spinbox, 0, 1)

        adv_filter_layout.addWidget(QLabel("前馈权重 (0-1):"), 0, 2)
        self.ff_weight_spinbox = QDoubleSpinBox()
        self.ff_weight_spinbox.setRange(0.0, 1.0)
        self.ff_weight_spinbox.setDecimals(3)
        self.ff_weight_spinbox.valueChanged.connect(self._queue_param_change)
        adv_filter_layout.addWidget(self.ff_weight_spinbox, 0, 3)

        adv_filter_layout.addWidget(QLabel("死区大小:"), 1, 0)
        self.deadband_spinbox = QDoubleSpinBox()
        self.deadband_spinbox.setRange(0.0, 1000.0)
        self.deadband_spinbox.setDecimals(6)
        self.deadband_spinbox.valueChanged.connect(self._queue_param_change)
        adv_filter_layout.addWidget(self.deadband_spinbox, 1, 1)

        adv_filter_layout.addWidget(QLabel("积分分离阈值 (误差绝对值):"), 1, 2)
        self.integral_separation_spinbox = QDoubleSpinBox()
        self.integral_separation_spinbox.setRange(0.0, 10000.0)
        self.integral_separation_spinbox.setDecimals(3)
        self.integral_separation_spinbox.valueChanged.connect(self._queue_param_change)
        adv_filter_layout.addWidget(self.integral_separation_spinbox, 1, 3)

        adv_filter_layout.addWidget(QLabel("微分滤波系数 (0-1, 0无):"), 2, 0)
        self.d_filter_spinbox = QDoubleSpinBox()
        self.d_filter_spinbox.setRange(0.0, 1.0)
        self.d_filter_spinbox.setDecimals(3)
        self.d_filter_spinbox.valueChanged.connect(self._queue_param_change)
        adv_filter_layout.addWidget(self.d_filter_spinbox, 2, 1)

        adv_filter_layout.addWidget(QLabel("输入滤波系数 (0-1, 0无):"), 2, 2)
        self.input_filter_spinbox = QDoubleSpinBox()
        self.input_filter_spinbox.setRange(0.0, 1.0)
        self.input_filter_spinbox.setDecimals(3)
        self.input_filter_spinbox.valueChanged.connect(self._queue_param_change)
        adv_filter_layout.addWidget(self.input_filter_spinbox, 2, 3)

        adv_filter_layout.addWidget(QLabel("设定值滤波系数 (0-1, 0无):"), 3, 0)
        self.setpoint_filter_spinbox = QDoubleSpinBox()
        self.setpoint_filter_spinbox.setRange(0.0, 1.0)
        self.setpoint_filter_spinbox.setDecimals(3)
        self.setpoint_filter_spinbox.valueChanged.connect(self._queue_param_change)
        adv_filter_layout.addWidget(self.setpoint_filter_spinbox, 3, 1)
        main_tab_layout.addWidget(adv_filter_group)
        main_tab_layout.addStretch()
        return widget

    def _create_advanced_features_tab(self) -> QWidget:
        """创建高级特性（自适应/模糊PID）标签页。"""
        self._log_debug("Creating Advanced Features Tab (Adaptive/Fuzzy)...")
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 自适应控制
        adaptive_group = QGroupBox("自适应控制 (C代码需自行实现逻辑)")
        adaptive_layout = QGridLayout(adaptive_group)
        self.adaptive_enable_checkbox = QCheckBox("启用自适应控制")
        self.adaptive_enable_checkbox.stateChanged.connect(self._queue_param_change)
        adaptive_layout.addWidget(self.adaptive_enable_checkbox, 0, 0, 1, 4)

        adaptive_layout.addWidget(QLabel("Kp 最小值:"), 1, 0)
        self.adaptive_kp_min_spinbox = QDoubleSpinBox()
        self.adaptive_kp_min_spinbox.setRange(0.001, 100)
        self.adaptive_kp_min_spinbox.setDecimals(6)
        self.adaptive_kp_min_spinbox.valueChanged.connect(self._queue_param_change)
        adaptive_layout.addWidget(self.adaptive_kp_min_spinbox, 1, 1)

        adaptive_layout.addWidget(QLabel("Kp 最大值:"), 1, 2)
        self.adaptive_kp_max_spinbox = QDoubleSpinBox()
        self.adaptive_kp_max_spinbox.setRange(0.001, 100)
        self.adaptive_kp_max_spinbox.setDecimals(6)
        self.adaptive_kp_max_spinbox.valueChanged.connect(self._queue_param_change)
        adaptive_layout.addWidget(self.adaptive_kp_max_spinbox, 1, 3)

        adaptive_layout.addWidget(QLabel("Ki 最小值:"), 2, 0)
        self.adaptive_ki_min_spinbox = QDoubleSpinBox()
        self.adaptive_ki_min_spinbox.setRange(0.001, 10)
        self.adaptive_ki_min_spinbox.setDecimals(6)
        self.adaptive_ki_min_spinbox.valueChanged.connect(self._queue_param_change)
        adaptive_layout.addWidget(self.adaptive_ki_min_spinbox, 2, 1)

        adaptive_layout.addWidget(QLabel("Ki 最大值:"), 2, 2)
        self.adaptive_ki_max_spinbox = QDoubleSpinBox()
        self.adaptive_ki_max_spinbox.setRange(0.001, 10)
        self.adaptive_ki_max_spinbox.setDecimals(6)
        self.adaptive_ki_max_spinbox.valueChanged.connect(self._queue_param_change)
        adaptive_layout.addWidget(self.adaptive_ki_max_spinbox, 2, 3)

        adaptive_layout.addWidget(QLabel("Kd 最小值:"), 3, 0)
        self.adaptive_kd_min_spinbox = QDoubleSpinBox()
        self.adaptive_kd_min_spinbox.setRange(0.001, 1)
        self.adaptive_kd_min_spinbox.setDecimals(6)
        self.adaptive_kd_min_spinbox.valueChanged.connect(self._queue_param_change)
        adaptive_layout.addWidget(self.adaptive_kd_min_spinbox, 3, 1)

        adaptive_layout.addWidget(QLabel("Kd 最大值:"), 3, 2)
        self.adaptive_kd_max_spinbox = QDoubleSpinBox()
        self.adaptive_kd_max_spinbox.setRange(0.001, 1)
        self.adaptive_kd_max_spinbox.setDecimals(6)
        self.adaptive_kd_max_spinbox.valueChanged.connect(self._queue_param_change)
        adaptive_layout.addWidget(self.adaptive_kd_max_spinbox, 3, 3)
        layout.addWidget(adaptive_group)

        # 模糊PID控制
        fuzzy_group = QGroupBox("模糊PID控制 (C代码需自行实现逻辑)")
        fuzzy_layout = QGridLayout(fuzzy_group)
        self.fuzzy_enable_checkbox = QCheckBox("启用模糊PID控制")
        self.fuzzy_enable_checkbox.stateChanged.connect(self._queue_param_change)
        fuzzy_layout.addWidget(self.fuzzy_enable_checkbox, 0, 0, 1, 2)

        fuzzy_layout.addWidget(QLabel("模糊误差范围:"), 1, 0)
        self.fuzzy_error_range_spinbox = QDoubleSpinBox()
        self.fuzzy_error_range_spinbox.setRange(1, 1000)
        self.fuzzy_error_range_spinbox.setDecimals(2)
        self.fuzzy_error_range_spinbox.valueChanged.connect(self._queue_param_change)
        fuzzy_layout.addWidget(self.fuzzy_error_range_spinbox, 1, 1)

        fuzzy_layout.addWidget(QLabel("模糊误差变化率范围:"), 2, 0)
        self.fuzzy_derror_range_spinbox = QDoubleSpinBox()
        self.fuzzy_derror_range_spinbox.setRange(1, 100)
        self.fuzzy_derror_range_spinbox.setDecimals(2)
        self.fuzzy_derror_range_spinbox.valueChanged.connect(self._queue_param_change)
        fuzzy_layout.addWidget(self.fuzzy_derror_range_spinbox, 2, 1)
        layout.addWidget(fuzzy_group)
        layout.addStretch()
        return widget

    def _create_code_config_tab(self) -> QWidget:
        """创建代码生成配置标签页。"""
        self._log_debug("Creating Code Config Tab...")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("全局代码生成选项 (应用于所有实例的库文件)")
        grid_layout = QGridLayout(group)

        grid_layout.addWidget(QLabel("库结构体名称:"), 0, 0)
        self.struct_name_edit = QLineEdit()
        self.struct_name_edit.textChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.struct_name_edit, 0, 1)

        grid_layout.addWidget(QLabel("库函数前缀:"), 1, 0)
        self.function_prefix_edit = QLineEdit()
        self.function_prefix_edit.textChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.function_prefix_edit, 1, 1)

        grid_layout.addWidget(QLabel("库头文件名称 (.h):"), 2, 0)
        self.header_name_edit = QLineEdit()
        self.header_name_edit.textChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.header_name_edit, 2, 1)

        grid_layout.addWidget(QLabel("优化级别 (概念性):"), 3, 0)
        self.optimization_combo = QComboBox()
        self.optimization_combo.addItems(["基础", "标准", "高级"])
        self.optimization_combo.currentTextChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.optimization_combo, 3, 1)

        self.use_float_checkbox = QCheckBox("使用 float 类型 (否则 double)")
        self.use_float_checkbox.stateChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.use_float_checkbox, 4, 0)

        self.include_comments_checkbox = QCheckBox("包含注释 (内置生成器)")
        self.include_comments_checkbox.stateChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.include_comments_checkbox, 4, 1)

        self.include_header_checkbox = QCheckBox("生成头文件内容")
        self.include_header_checkbox.stateChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.include_header_checkbox, 5, 0)

        self.use_template_checkbox = QCheckBox("使用模板生成库代码")
        self.use_template_checkbox.stateChanged.connect(self._queue_global_config_change)
        grid_layout.addWidget(self.use_template_checkbox, 5, 1)

        layout.addWidget(group)
        layout.addStretch() # 确保该标签页的垂直空间被充分利用
        return widget

    def _create_preview_tab(self) -> QWidget:
        """创建代码预览标签页。"""
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
        # 显式设置 QTextEdit 的垂直大小策略为 Expanding
        self.code_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.code_preview.setMinimumHeight(600) # 增加最小高度，以确保有足够的显示空间
        self.highlighter = CSyntaxHighlighter(self.code_preview.document())
        layout.addWidget(self.code_preview)
        layout.addStretch() # 确保代码预览区域的垂直空间被充分利用
        return widget

    @Slot()
    def _queue_param_change(self):
        """当PID参数UI发生变化时，启动防抖定时器。"""
        self._on_pid_param_ui_changed() # 立即更新内部数据模型
        self.debounce_timer.start() # 延迟触发代码生成和预览更新

    @Slot()
    def _queue_global_config_change(self):
        """当全局代码配置UI发生变化时，启动防抖定时器。"""
        self._on_global_code_config_changed() # 立即更新内部数据模型
        self.debounce_timer.start() # 延迟触发代码生成和预览更新

    @Slot(int)
    def _on_tab_changed(self, index: int):
        """当标签页切换时，如果切换到预览标签页，则立即更新预览。"""
        if self.param_tabs and self.param_tabs.tabText(index) == "代码预览":
            self._trigger_full_code_generation_and_preview_update()

    @Slot()
    def _on_add_instance_button_clicked(self):
        """处理添加PID实例按钮点击事件。"""
        instance_name_text = self.instance_name_edit.text().strip() if self.instance_name_edit else ""
        name_to_add = instance_name_text
        ok_pressed = True

        if not name_to_add:
            name_to_add, ok_pressed = QInputDialog.getText(self, "添加PID实例", "输入实例名称 (例如 motor_pid):")

        if ok_pressed and name_to_add:
            # 验证名称是否符合C语言标识符规范
            if not re.fullmatch(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name_to_add):
                QMessageBox.warning(self, "名称无效", "实例名称必须以字母或下划线开头，且只包含字母、数字和下划线。")
                return

            if any(inst['name'] == name_to_add for inst in self.pid_instance_configs):
                QMessageBox.warning(self, "名称冲突", f"名为 '{name_to_add}' 的PID实例已存在。")
                return

            self._add_pid_instance(name_to_add)
            if self.instance_name_edit:
                self.instance_name_edit.clear()
            self._trigger_full_code_generation_and_preview_update() # 添加实例后刷新预览
        elif ok_pressed and not name_to_add:
            QMessageBox.warning(self, "名称无效", "PID实例名称不能为空。")

    def _add_pid_instance(self, name: str):
        """向内部数据模型和UI列表添加一个PID实例。"""
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
        # _on_selected_pid_instance_changed will be called by setCurrentItem

    @Slot()
    def _on_remove_instance_button_clicked(self):
        """处理移除PID实例按钮点击事件。"""
        if not self.pid_instance_list_widget:
            return

        row_to_remove = self.pid_instance_list_widget.currentRow()

        if row_to_remove < 0:
            QMessageBox.information(self, "移除实例", "请先选择一个要移除的PID实例。")
            return

        # 关键检查：确保row_to_remove是数据列表的有效索引
        if not (0 <= row_to_remove < len(self.pid_instance_configs)):
            self._log_error(f"CRITICAL: Mismatch between QListWidget selection and internal data. "
                            f"Attempting to remove QListWidget row {row_to_remove}, "
                            f"but len(pid_instance_configs) is {len(self.pid_instance_configs)}.")
            QMessageBox.critical(self, "内部错误", "列表数据不一致，无法移除。请尝试重新选择。")
            return

        instance_name = self.pid_instance_configs[row_to_remove]['name']
        reply = QMessageBox.question(self, "确认移除",
                                     f"确定要移除PID实例 '{instance_name}' 吗？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._log_debug(f"Removing PID instance: {instance_name} at actual list index {row_to_remove}")

            # 先从数据列表移除
            del self.pid_instance_configs[row_to_remove]

            # 再从QListWidget移除，暂时阻塞信号以避免不必要的触发
            self.pid_instance_list_widget.blockSignals(True)
            item_widget = self.pid_instance_list_widget.takeItem(row_to_remove)
            if item_widget:
                del item_widget  # 确保QListWidgetItem被删除
            self.pid_instance_list_widget.blockSignals(False)

            # 移除后，确定新的选中项
            new_count = len(self.pid_instance_configs)
            if new_count == 0:
                self.active_pid_instance_index = -1
                self._load_params_to_ui(-1)  # 加载默认/清空UI
                if self.instance_name_edit: self.instance_name_edit.clear()
            else:
                # 尝试选择相同索引的项，如果超出范围则选择最后一个
                new_selection_index = min(row_to_remove, new_count - 1)
                self.pid_instance_list_widget.setCurrentRow(new_selection_index)
                # 如果setCurrentRow没有触发currentItemChanged（例如，删除的是最后一个，且新选中的也是最后一个），
                # 则手动触发更新
                if self.pid_instance_list_widget.currentRow() == new_selection_index:
                    self._on_selected_pid_instance_changed(self.pid_instance_list_widget.currentItem(), None)

            self._update_title()
            self._trigger_full_code_generation_and_preview_update() # 移除实例后刷新预览

    @Slot()
    def _on_rename_instance_button_clicked(self):
        """处理重命名PID实例按钮点击事件。"""
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
            # 验证名称是否符合C语言标识符规范
            if not re.fullmatch(r"^[a-zA-Z_][a-zA-Z0-9_]*$", new_name):
                QMessageBox.warning(self, "名称无效", "实例名称必须以字母或下划线开头，且只包含字母、数字和下划线。")
                return

            if any(inst['name'] == new_name for i, inst in enumerate(self.pid_instance_configs) if i != current_row):
                QMessageBox.warning(self, "名称冲突", f"名为 '{new_name}' 的PID实例已存在。")
                return
            self._log_debug(f"Renaming PID instance '{old_name}' to '{new_name}'")
            self.pid_instance_configs[current_row]['name'] = new_name
            current_list_item = self.pid_instance_list_widget.item(current_row)
            if current_list_item:
                current_list_item.setText(new_name)
            if self.instance_name_edit:
                self.instance_name_edit.setText(new_name)
            self._update_title()
            self._trigger_full_code_generation_and_preview_update() # 重命名后刷新预览
        elif ok and not new_name:
            QMessageBox.warning(self, "名称无效", "PID实例名称不能为空。")

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_selected_pid_instance_changed(self, current: Optional[QListWidgetItem],
                                          previous: Optional[QListWidgetItem]):
        """处理PID实例列表选中项变化事件。"""
        if not self.pid_instance_list_widget:
            self.active_pid_instance_index = -1
            self._load_params_to_ui(-1)
            self._update_title()
            return

        instance_name_to_edit = ""
        if current is None:
            self.active_pid_instance_index = -1
        else:
            current_row_in_widget = self.pid_instance_list_widget.row(current)
            if 0 <= current_row_in_widget < len(self.pid_instance_configs):
                self.active_pid_instance_index = current_row_in_widget
                instance_name_to_edit = self.pid_instance_configs[self.active_pid_instance_index]['name']
                self._log_debug(
                    f"Selected PID instance: {instance_name_to_edit} at actual list index {self.active_pid_instance_index}")
            else:
                self._log_error(f"Desync on selection: QListWidget row {current_row_in_widget} "
                                f"is out of bounds for pid_instance_configs (len {len(self.pid_instance_configs)}). "
                                f"Resetting active_pid_instance_index.")
                self.active_pid_instance_index = -1

        if self.instance_name_edit:
            self.instance_name_edit.setText(instance_name_to_edit)

        self._load_params_to_ui(self.active_pid_instance_index)  # 这将正确处理-1
        self._update_title()
        self._trigger_full_code_generation_and_preview_update() # 选中实例变化后刷新预览

    def _load_params_to_ui(self, instance_index: int):
        """根据给定的实例索引加载PID参数到UI。"""
        self._log_debug(f"Loading params to UI for instance index: {instance_index}")
        params_to_load: Dict[str, Any]
        is_valid_instance = instance_index >= 0 and instance_index < len(self.pid_instance_configs)
        if is_valid_instance:
            params_to_load = self.pid_instance_configs[instance_index]['params']
        else:
            # 如果没有有效实例，加载默认参数并禁用编辑
            params_to_load = self._get_default_pid_params()

        # 阻塞信号，防止在加载过程中触发多次 _queue_param_change
        self.blockSignals(True)

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

        # 启用/禁用 PID 参数和高级特性标签页
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

        self.blockSignals(False) # 解除信号阻塞
        self._log_debug(f"UI updated with params for index {instance_index}. Editing enabled: {enable_editing}")

    def _load_global_code_config_to_ui(self):
        """加载当前全局代码配置到UI。"""
        self._log_debug("Loading current self.code_config to UI...")
        # 阻塞信号，防止在加载过程中触发多次 _queue_global_config_change
        self.blockSignals(True)

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

        self.blockSignals(False) # 解除信号阻塞

    @Slot() # Explicitly add Slot decorator
    def _on_pid_param_ui_changed(self):
        """当PID参数UI值变化时，更新内部数据模型。"""
        if self.active_pid_instance_index < 0 or self.active_pid_instance_index >= len(self.pid_instance_configs):
            return
        current_config = self.pid_instance_configs[self.active_pid_instance_index]
        params = current_config['params']

        if self.algorithm_combo:
            params["algorithm_type"] = {"高级PID": "advanced", "位置式PID (内置)": "positional",
                                         "增量式PID (内置)": "incremental"}.get(
                self.algorithm_combo.currentText(), "advanced")
            # 如果切换到非高级PID，强制不使用模板
            if self.use_template_checkbox:
                is_advanced = (params["algorithm_type"] == "advanced")
                # 暂时阻塞信号，避免死循环
                self.use_template_checkbox.blockSignals(True)
                self.use_template_checkbox.setChecked(is_advanced)
                self.use_template_checkbox.blockSignals(False)
                self.code_config["use_template"] = is_advanced

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

        self._log_debug(f"PID params for instance '{current_config['name']}' updated from UI.")

    @Slot() # Explicitly add Slot decorator
    def _on_global_code_config_changed(self):
        """当全局代码配置UI值变化时，更新内部数据模型。"""
        if self.struct_name_edit: self.code_config[
            "struct_name"] = self.struct_name_edit.text().strip() or "PID_HandleTypeDef"
        if self.function_prefix_edit: self.code_config[
            "function_prefix"] = self.function_prefix_edit.text().strip() or "PID"
        if self.header_name_edit: self.code_config["header_name"] = self.header_name_edit.text().strip() or "pid.h"
        if self.optimization_combo: self.code_config[
            "optimization_level"] = self.optimization_combo.currentText().lower()
        if self.use_float_checkbox:
            self.code_config["use_float"] = self.use_float_checkbox.isChecked()
            self.code_config["data_type"] = "float" if self.use_float_checkbox.isChecked() else "double"
            self.code_config["float_suffix"] = DEFAULT_FLOAT_SUFFIX if self.use_float_checkbox.isChecked() else DEFAULT_DOUBLE_SUFFIX

        if self.include_comments_checkbox: self.code_config[
            "include_comments"] = self.include_comments_checkbox.isChecked()
        if self.include_header_checkbox: self.code_config["include_header"] = self.include_header_checkbox.isChecked()
        if self.use_template_checkbox: self.code_config["use_template"] = self.use_template_checkbox.isChecked()
        self._log_debug("Global code config updated from UI.")

    @Slot()
    def _on_generate_code_button_clicked(self):
        """处理生成/刷新所有预览按钮点击事件。"""
        self._log_debug("Generate/Refresh Preview button clicked.")
        self._trigger_full_code_generation_and_preview_update()
        self._show_status("所有代码预览已更新。", 2000)

    def _trigger_full_code_generation_and_preview_update(self):
        """触发完整的代码生成和预览更新。"""
        self._show_status("正在生成代码...", 0) # 显示状态信息
        self._on_pid_param_ui_changed() # 确保当前选中的实例参数已保存
        self._on_global_code_config_changed() # 确保全局配置已保存

        self.generated_c_code = self._generate_c_code()
        self.generated_h_code = self._generate_h_code()
        self.generated_main_c_code = self._generate_main_c_code_for_all_instances()
        self._update_preview_content()
        self._show_status("代码生成完成。", 2000)

    @Slot()
    def _on_preview_file_selected(self):
        """处理预览文件选择器变化事件。"""
        self._update_preview_content()

    def _update_preview_content(self):
        """根据选择器更新代码预览内容。"""
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
        """处理导出代码文件按钮点击事件。"""
        self._log_debug("Export Code button clicked.")
        self._trigger_full_code_generation_and_preview_update() # 导出前确保代码最新

        if not self.pid_instance_configs:
            QMessageBox.information(self, "导出提示", "请至少添加并配置一个PID实例。")
            return

        self._show_status("正在导出文件...", 0)

        suggested_base_name = Path(self.code_config.get("header_name", "pid_controller.h")).stem
        user_path_suggestion = str(Path(os.getcwd()) / suggested_base_name)
        file_path_base, _ = QFileDialog.getSaveFileName(
            self, "选择保存位置和基础文件名 (例如 pid_control)", user_path_suggestion, "All Files (*)"
        )

        if not file_path_base:
            self._show_status("导出已取消。", 2000)
            return

        save_dir = Path(file_path_base).parent
        base_name_selected = Path(file_path_base).stem
        save_dir.mkdir(parents=True, exist_ok=True) # 确保目录存在

        h_content = self.generated_h_code
        c_content = self.generated_c_code
        main_c_content = self.generated_main_c_code

        h_file_name = self.code_config.get("header_name", f"{base_name_selected}_lib.h")
        c_file_name = f"{Path(h_file_name).stem}.c" # C文件与H文件同名，只是后缀不同
        main_c_file_name = f"{base_name_selected}_main.c"

        files_to_write = []
        # 检查生成内容是否是错误消息
        if self.code_config.get("include_header", True) and h_content and not h_content.startswith("// Error"):
            files_to_write.append((save_dir / h_file_name, h_content))
        if c_content and not c_content.startswith("// Error"):
            files_to_write.append((save_dir / c_file_name, c_content))
        if main_c_content and not main_c_content.startswith("// Error"):
            files_to_write.append((save_dir / main_c_file_name, main_c_content))

        if not files_to_write:
            QMessageBox.warning(self, "导出警告", "未能生成任何有效代码文件。请检查配置和模板。")
            self._log_warning("Export failed, no valid content generated.", self.PANEL_TYPE_NAME)
            self._show_status("导出失败：无有效代码。", 2000)
            return

        exported_files_paths = []
        try:
            for file_path, content in files_to_write:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                exported_files_paths.append(str(file_path))
            QMessageBox.information(self, "导出成功", "代码已导出到以下文件:\n" + "\n".join(exported_files_paths))
            self._log_info(f"Code exported to: {', '.join(exported_files_paths)}", self.PANEL_TYPE_NAME)
            self._show_status("代码导出成功。", 2000)
        except IOError as e:
            QMessageBox.critical(self, "导出失败", f"写入文件时发生IO错误:\n{str(e)}")
            self._log_error(f"Multi-file export failed (IO Error): {str(e)}", self.PANEL_TYPE_NAME)
            self._show_status("导出失败：写入文件错误。", 2000)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出代码时发生未知错误:\n{str(e)}")
            self._log_error(f"Multi-file export failed (General Error): {str(e)}", self.PANEL_TYPE_NAME)
            self._show_status("导出失败：未知错误。", 2000)

    def _generate_h_code(self) -> str:
        """生成C头文件（库）代码。"""
        self._log_debug("Generating H code (library)...")
        if not self.code_config.get("include_header"):
            return "// Header file generation skipped by global configuration."
        if not self.code_config.get("use_template"):
            return "// Built-in generator does not produce separate H file for library."

        # 库文件总是使用高级PID模板（如果存在）
        algo_for_lib_template = "advanced"
        h_template_path = self._get_template_path(algo_type_override=algo_for_lib_template, extension="h")

        if not (h_template_path and h_template_path.exists()):
            return f"// Error: Library Header template not found: {h_template_path}"

        return self._generate_from_template_file(h_template_path, use_instance_params=False)

    def _generate_c_code(self) -> str:
        """生成C源文件（库）代码。"""
        self._log_debug("Generating C code (library)...")
        if not self.code_config.get("use_template"):
            return self._generate_builtin_code(use_instance_params=False)

        # 库文件总是使用高级PID模板（如果存在）
        algo_for_lib_template = "advanced"
        c_template_path = self._get_template_path(algo_type_override=algo_for_lib_template, extension="c")

        if not (c_template_path and c_template_path.exists()):
            self._log_warning(f"Library C template not found ({c_template_path}), falling back to built-in.",
                              self.PANEL_TYPE_NAME)
            return self._generate_builtin_code(use_instance_params=False)

        return self._generate_from_template_file(c_template_path, use_instance_params=False)

    def _generate_main_c_code_for_all_instances(self) -> str:
        """为所有PID实例生成示例Main C代码。"""
        self._log_debug("Generating Main C code for all instances...")
        main_template_path = Path(__file__).parent / "templates" / "user_main_template.c"
        if not main_template_path.exists():
            return f"// Error: Main C template not found: {main_template_path}"

        try:
            template_content = main_template_path.read_text(encoding='utf-8')
            data_t = self.code_config.get("data_type", "float")
            sfx = self.code_config.get("float_suffix", DEFAULT_FLOAT_SUFFIX)

            global_replacements = {
                '{{HEADER_NAME}}': self.code_config.get("header_name", "pid.h"),
                '{{STRUCT_NAME}}': self.code_config.get("struct_name", "PID_HandleTypeDef"),
                '{{FUNCTION_PREFIX}}': self.code_config.get("function_prefix", "PID"),
                '{{DATA_TYPE}}': data_t,
                '{{TIMESTAMP}}': self._get_current_time(),
                '{{SFX}}': sfx # 传递浮点数后缀
            }

            processed_code = template_content
            for placeholder, value in global_replacements.items():
                processed_code = re.sub(re.escape(placeholder), str(value), processed_code)

            declarations_block = []
            initializations_block = []
            example_computations_block = []

            if not self.pid_instance_configs:
                example_computations_block.append("    // 未配置任何PID实例，无示例代码生成。")
            else:
                for i, instance_config in enumerate(self.pid_instance_configs):
                    instance_name = instance_config['name']
                    params = instance_config['params']
                    sample_t = max(params.get("sample_time", DEFAULT_SAMPLE_TIME), 0.000001)

                    declarations_block.append(f"    {self.code_config.get('struct_name')} {instance_name};")

                    kp_val = params.get('kp', 1.0)
                    ki_val = params.get('ki', 0.1)
                    kd_val = params.get('kd', 0.01)
                    max_output_val = params.get('max_output', 100.0)
                    integral_limit_val = params.get('integral_limit', 50.0)
                    output_ramp_val = params.get('output_ramp', 0.0)
                    deadband_val = params.get('deadband', 0.0)
                    integral_separation_val = params.get('integral_separation_threshold', 1000.0)
                    d_filter_coef_val = params.get('d_filter_coef', 0.1)
                    input_filter_coef_val = params.get('input_filter_coef', 0.0)
                    setpoint_filter_coef_val = params.get('setpoint_filter_coef', 0.0)
                    kff_val = params.get('kff', 0.0)
                    ff_weight_val = params.get('ff_weight', 1.0)

                    # 初始化调用
                    initializations_block.append(f"    // 初始化PID实例: {instance_name}")
                    init_call = (
                        f"    {self.code_config.get('function_prefix')}_Init(&{instance_name}, "
                        f"{kp_val}{sfx}, {ki_val}{sfx}, {kd_val}{sfx}, {sample_t}{sfx});"
                    )
                    initializations_block.append(init_call)
                    initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetOutputLimits(&{instance_name}, {max_output_val}{sfx});")
                    initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetIntegralLimits(&{instance_name}, {integral_limit_val}{sfx});")
                    if output_ramp_val > 0:
                        initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetOutputRamp(&{instance_name}, {output_ramp_val}{sfx});")
                    if deadband_val > 0:
                        initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetDeadband(&{instance_name}, {deadband_val}{sfx});")
                    if integral_separation_val > 0 and integral_separation_val < 1000.0: # 默认1000太大了，只有用户改了才生成
                        initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetIntegralSeparationThreshold(&{instance_name}, {integral_separation_val}{sfx});")
                    if d_filter_coef_val > 0:
                        initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetDFilter(&{instance_name}, {d_filter_coef_val}{sfx});")
                    if input_filter_coef_val > 0:
                        initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetInputFilter(&{instance_name}, {input_filter_coef_val}{sfx});")
                    if setpoint_filter_coef_val > 0:
                        initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetSetpointFilter(&{instance_name}, {setpoint_filter_coef_val}{sfx});")
                    if kff_val != 0 or ff_weight_val != 1.0:
                         initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetFeedForwardParams(&{instance_name}, {kff_val}{sfx}, {ff_weight_val}{sfx});")

                    # 设置PID类型和工作模式
                    pid_type_map = {"standard": "PID_TYPE_STANDARD", "pi_d": "PID_TYPE_PI_D", "i_pd": "PID_TYPE_I_PD"}
                    work_mode_map = {"position": "PID_MODE_POSITION", "velocity": "PID_MODE_VELOCITY"}
                    initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetType(&{instance_name}, {pid_type_map.get(params.get('pid_type'), 'PID_TYPE_STANDARD')});")
                    initializations_block.append(f"    {self.code_config.get('function_prefix')}_SetWorkMode(&{instance_name}, {work_mode_map.get(params.get('work_mode'), 'PID_MODE_POSITION')});")

                    # 打印初始化信息
                    initializations_block.append(
                        f"    printf(\"Initialized PID: {instance_name} (Kp=%.4f, Ki_cont=%.4f, Kd_cont=%.4f, Ts=%.4f)\\n\", "
                        f"(double){kp_val}{sfx}, (double){ki_val}{sfx}, (double){kd_val}{sfx}, (double){sample_t}{sfx});")
                    initializations_block.append("") # 空行分隔

                    # 示例计算
                    example_computations_block.append(f"    // 示例计算 for {instance_name}")
                    example_computations_block.append(f"    {data_t} {instance_name}_setpoint = 50.0{sfx};")
                    example_computations_block.append(f"    {data_t} {instance_name}_measurement = 0.0{sfx};")
                    example_computations_block.append(f"    printf(\"\\n--- Running simulation for {instance_name} ---\\n\");")
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

            # 移除旧的、不再需要的占位符（如果存在）
            old_placeholders = [
                '{{KP_UI_VALUE}}', '{{KI_UI_VALUE}}', '{{KD_UI_VALUE}}', '{{MAX_OUTPUT_UI_VALUE}}',
                '{{INTEGRAL_LIMIT_UI_VALUE}}', '{{SAMPLE_TIME_UI_VALUE}}', '{{DEADBAND_UI_VALUE}}',
                '{{D_FILTER_COEF_UI_VALUE}}'
            ]
            for placeholder in old_placeholders:
                processed_code = re.sub(re.escape(placeholder), '', processed_code)

            return processed_code
        except Exception as e:
            self._log_error(f"user_main.c generation for all instances failed: {e}", self.PANEL_TYPE_NAME)
            return f"// Error generating user_main.c for all instances: {e}"

    def _get_template_path(self, algo_type_override: Optional[str] = None, extension: str = "c") -> Optional[Path]:
        """获取指定算法类型和扩展名的模板文件路径。"""
        template_dir = Path(__file__).parent / "templates"
        algo_type_to_use = algo_type_override
        if not algo_type_to_use:
            if self.active_pid_instance_index != -1 and self.active_pid_instance_index < len(
                    self.pid_instance_configs):
                algo_type_to_use = self.pid_instance_configs[self.active_pid_instance_index]['params'].get(
                    "algorithm_type", "advanced")
            else:
                algo_type_to_use = "advanced" # 默认使用高级PID模板

        base_name_map = {
            "advanced": "advanced_pid_template",
            "positional": "positional_pid_template", # 预留给未来可能的内置模板
            "incremental": "incremental_pid_template" # 预留给未来可能的内置模板
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
        """从模板文件生成代码。"""
        self._log_debug(
            f"Generating from template: {template_path}, use_instance_params: {use_instance_params}, instance_idx: {instance_index_for_params}")
        try:
            template_content = template_path.read_text(encoding='utf-8')
            data_t = self.code_config.get("data_type", "float")
            sfx = self.code_config.get("float_suffix", DEFAULT_FLOAT_SUFFIX)

            params_source: Dict[str, Any]
            if use_instance_params:
                idx_to_use = instance_index_for_params if instance_index_for_params != -1 else self.active_pid_instance_index
                if idx_to_use != -1 and idx_to_use < len(self.pid_instance_configs):
                    params_source = self.pid_instance_configs[idx_to_use]['params']
                else:
                    params_source = self._get_default_pid_params() # 使用默认参数
            else:
                params_source = self._get_default_pid_params() # 不使用实例参数，使用默认参数

            sample_t = max(params_source.get("sample_time", DEFAULT_SAMPLE_TIME), 0.000001)

            # 获取高级特性启用状态
            adaptive_enabled = params_source.get("adaptive_enable", False)
            fuzzy_enabled = params_source.get("fuzzy_enable", False)

            replacements = {
                '{{STRUCT_NAME}}': self.code_config.get("struct_name", "PID_HandleTypeDef"),
                '{{FUNCTION_PREFIX}}': self.code_config.get("function_prefix", "PID"),
                '{{DATA_TYPE}}': data_t,
                '{{HEADER_NAME}}': self.code_config.get("header_name", "pid.h"),
                '{{TIMESTAMP}}': self._get_current_time(),
                '{{SFX}}': sfx, # 传递浮点数后缀
                '{{KP_DEFAULT}}': f"{params_source.get('kp', 1.0)}{sfx}",
                '{{KI_DEFAULT}}': f"{params_source.get('ki', 0.1) * sample_t}{sfx}", # 离散Ki
                '{{KD_DEFAULT}}': f"{params_source.get('kd', 0.01) / sample_t}{sfx}", # 离散Kd
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
                # 高级特性参数
                '{{ADAPTIVE_ENABLE}}': 'true' if adaptive_enabled else 'false',
                '{{ADAPTIVE_KP_MIN_DEFAULT}}': f"{params_source.get('adaptive_kp_min', 0.1)}{sfx}",
                '{{ADAPTIVE_KP_MAX_DEFAULT}}': f"{params_source.get('adaptive_kp_max', 10.0)}{sfx}",
                '{{ADAPTIVE_KI_MIN_DEFAULT}}': f"{params_source.get('adaptive_ki_min', 0.01)}{sfx}",
                '{{ADAPTIVE_KI_MAX_DEFAULT}}': f"{params_source.get('adaptive_ki_max', 1.0)}{sfx}",
                '{{ADAPTIVE_KD_MIN_DEFAULT}}': f"{params_source.get('adaptive_kd_min', 0.001)}{sfx}",
                '{{ADAPTIVE_KD_MAX_DEFAULT}}': f"{params_source.get('adaptive_kd_max', 0.1)}{sfx}",
                '{{FUZZY_ENABLE}}': 'true' if fuzzy_enabled else 'false',
                '{{FUZZY_ERROR_RANGE_DEFAULT}}': f"{params_source.get('fuzzy_error_range', 100.0)}{sfx}",
                '{{FUZZY_DERROR_RANGE_DEFAULT}}': f"{params_source.get('fuzzy_derror_range', 10.0)}{sfx}",
            }

            # 替换模板中的所有占位符
            generated_code = template_content
            for placeholder, value in replacements.items():
                escaped_placeholder = re.escape(placeholder)
                generated_code = re.sub(escaped_placeholder, str(value), generated_code)

            # 根据 include_comments 决定是否移除注释
            if not self.code_config.get("include_comments"):
                # 移除 /* ... */ 多行注释
                generated_code = re.sub(r'/\*.*?\*/', '', generated_code, flags=re.DOTALL)
                # 移除 // 单行注释
                generated_code = re.sub(r'//[^\n]*', '', generated_code)
                # 移除多余的空行
                generated_code = re.sub(r'\n\s*\n', '\n\n', generated_code)

            return generated_code
        except FileNotFoundError:
            self._log_error(f"Template file not found: {template_path}", self.PANEL_TYPE_NAME)
            return f"// Error: Template file not found: {template_path}"
        except Exception as e:
            self._log_error(f"Failed to generate from template {template_path.name}: {e}", self.PANEL_TYPE_NAME)
            return f"// Error generating from template {template_path.name}: {e}"

    def _generate_builtin_code(self, use_instance_params: bool = True, instance_index_for_params: int = -1) -> str:
        """使用内置逻辑生成C代码（作为模板缺失时的备用）。"""
        self._log_debug("Generating C code using built-in logic...")
        params_source: Dict[str, Any]
        if use_instance_params:
            idx_to_use = instance_index_for_params if instance_index_for_params != -1 else self.active_pid_instance_index
            if idx_to_use != -1 and idx_to_use < len(self.pid_instance_configs):
                params_source = self.pid_instance_configs[idx_to_use]['params']
            else:
                params_source = self._get_default_pid_params()
        else:
            params_source = self._get_default_pid_params()

        data_type = self.code_config.get("data_type", "float")
        sfx = self.code_config.get("float_suffix", DEFAULT_FLOAT_SUFFIX)
        struct_name = self.code_config.get("struct_name", "Builtin_PID_Controller")
        func_prefix = self.code_config.get("function_prefix", "Builtin_PID")
        sample_t = max(params_source.get("sample_time", DEFAULT_SAMPLE_TIME), 0.000001)

        code = []
        if self.code_config.get("include_comments"):
            code.append(f"// Built-in PID Controller ({params_source.get('algorithm_type')}) - {self._get_current_time()}\n")
        if self.code_config.get("include_header") and self.code_config.get("header_name"):
            code.append(f"#include \"{self.code_config.get('header_name')}\"\n")
        code.append("#include <math.h> \n")

        code.append(f"typedef struct {{")
        code.append(f"  {data_type} Kp, Ki_d, Kd_d; ")
        code.append(f"  {data_type} setpoint, integral, prev_error, prev_measure;")
        code.append(f"  {data_type} out_min, out_max, integral_limit;")
        code.append(f"}} {struct_name};\n")

        code.append(f"void {func_prefix}_Init({struct_name} *pid, {data_type} kp, {data_type} ki_c, {data_type} kd_c) {{")
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
        """获取当前时间字符串。"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _update_title(self) -> None:
        """更新面板标题以反映当前选中的PID实例。"""
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

    def _show_status(self, message: str, timeout_ms: int = 0):
        """在状态栏显示消息。"""
        if self.status_label:
            self.status_label.setText(message)
            if timeout_ms > 0:
                QTimer.singleShot(timeout_ms, lambda: self.status_label.setText("准备就绪。"))

    # 日志方法与PanelInterface的ErrorLoggerMock兼容
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
        """获取当前面板的配置。"""
        self._log_debug("Getting config...")
        # 在获取配置前，确保当前UI状态已同步到内部数据模型
        if self.active_pid_instance_index != -1 and self.active_pid_instance_index < len(
                self.pid_instance_configs):
            self._on_pid_param_ui_changed()
        self._on_global_code_config_changed()

        config = {
            "version": "5.0.4",  # 版本号递增，表示修改
            "pid_instance_configs": copy.deepcopy(self.pid_instance_configs),
            "active_pid_instance_index": self.pid_instance_list_widget.currentRow() if self.pid_instance_list_widget else -1,
            "global_code_config": self.code_config.copy(),
            "panel_type": self.PANEL_TYPE_NAME,
            "ui_selections": {
                "preview_file_selector_index": self.preview_file_selector.currentIndex() if self.preview_file_selector else 0,
            }
        }
        return config

    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用给定的配置到面板。"""
        self._log_debug(f"Applying config (version: {config.get('version')})...")

        # 1. 加载全局代码配置
        global_code_cfg = config.get("global_code_config")
        if global_code_cfg:
            self.code_config.update(global_code_cfg)
        else:
            self.code_config = self._get_default_code_config()
        self._load_global_code_config_to_ui()

        # 2. 加载PID实例配置
        self.pid_instance_configs = copy.deepcopy(config.get("pid_instance_configs", []))

        # 3. 填充QListWidget
        if self.pid_instance_list_widget:
            self.pid_instance_list_widget.clear()
            for instance_cfg in self.pid_instance_configs:
                self.pid_instance_list_widget.addItem(QListWidgetItem(instance_cfg['name']))

        # 4. 恢复选中实例
        restored_active_index = config.get("active_pid_instance_index", -1)
        new_list_count = len(self.pid_instance_configs)

        if new_list_count == 0:
            self.active_pid_instance_index = -1
        elif 0 <= restored_active_index < new_list_count:
            self.active_pid_instance_index = restored_active_index
        else:
            # 无效索引或-1，如果列表不为空，则选中第一个
            self.active_pid_instance_index = 0 if new_list_count > 0 else -1

        if self.pid_instance_list_widget and self.active_pid_instance_index != -1:
            # setCurrentRow会触发_on_selected_pid_instance_changed，进而加载参数到UI
            self.pid_instance_list_widget.setCurrentRow(self.active_pid_instance_index)
        else:
            # 没有实例或没有有效选中，加载默认UI参数
            self._load_params_to_ui(-1)

        # 5. 恢复UI选择（例如预览文件选择）
        ui_selections = config.get("ui_selections", {})
        if self.preview_file_selector and "preview_file_selector_index" in ui_selections:
            # 暂时阻塞信号，避免在加载时触发不必要的预览更新
            self.preview_file_selector.blockSignals(True)
            self.preview_file_selector.setCurrentIndex(ui_selections["preview_file_selector_index"])
            self.preview_file_selector.blockSignals(False)

        # 6. 触发代码生成和预览更新
        self._trigger_full_code_generation_and_preview_update()
        self._update_title()
        self._log_debug("Config applied.")

    # 以下两个方法被废弃，因为参数加载和代码配置加载已经包含在其他地方
    def _update_ui_from_params(self):
        pass

    def _update_ui_from_code_config(self):
        pass

    def get_initial_dock_title(self) -> str:
        """获取面板的初始停靠标题。"""
        return f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]"

    def on_panel_added(self) -> None:
        """面板添加到主窗口时调用。"""
        super().on_panel_added()
        self._log_info(f"Panel added to main window.", self.PANEL_TYPE_NAME)

    def on_panel_removed(self) -> None:
        """面板从主窗口移除时调用。"""
        self._log_info(f"Panel removed. Cleaning up...", self.PANEL_TYPE_NAME)
        super().on_panel_removed()

    def update_theme(self) -> None:
        """更新UI主题。"""
        super().update_theme()
        self._log_debug("Theme update requested.")
        if self.code_preview and self.code_preview.document():
            # 重新应用高亮器以适应新主题
            self.highlighter = CSyntaxHighlighter(self.code_preview.document())
            # 强制重新高亮
            current_text = self.code_preview.toPlainText()
            self.code_preview.setPlainText("") # 清空再设置，强制高亮器重新处理
            self.code_preview.setPlainText(current_text)

