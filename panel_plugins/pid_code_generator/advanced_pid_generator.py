# panel_plugins/pid_code_generator/advanced_pid_generator.py
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTextEdit, QComboBox,
    QDoubleSpinBox, QGroupBox, QGridLayout, QFileDialog, QMessageBox, QTabWidget,
    QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QSplitter,
    QSizePolicy
)
from PySide6.QtCore import Slot, Qt, QRegularExpression, Signal, QTimer
from PySide6.QtGui import (
    QFont, QTextCharFormat, QColor, QSyntaxHighlighter, QTextDocument
)
from typing import Dict, Any, Optional, Tuple, List
import os
import re
import copy
from datetime import datetime
from pathlib import Path

# 导入 PanelInterface，支持不同的导入路径
try:
    from core.panel_interface import PanelInterface
except ImportError:
    import sys
    project_root_panel = Path(__file__).resolve().parent.parent
    core_path = project_root_panel.parent / "core"
    if str(core_path) not in sys.path:
        sys.path.insert(0, str(core_path))
    try:
        from panel_interface import PanelInterface
    except ImportError:
        # 提供一个备用的 PanelInterface 类，以便在独立环境中测试
        try:
            from PySide6.QtCore import Signal as pyqtSignal
        except ImportError:
            pyqtSignal = None

        class PanelInterface(QWidget):
            PANEL_TYPE_NAME: str = "mock_panel"
            PANEL_DISPLAY_NAME: str = "Mock Panel"
            dock_title_changed = pyqtSignal(str) if pyqtSignal else None
            def __init__(self, panel_id, main_window_ref, initial_config=None, parent=None):
                super().__init__(parent)
                self.panel_id = panel_id
                self.main_window_ref = main_window_ref
                self.error_logger = self.ErrorLoggerMock()
            def get_config(self) -> Dict[str, Any]: return {}
            def apply_config(self, config: Dict[str, Any]) -> None: pass
            def get_initial_dock_title(self) -> str: return "Mock Panel"
            class ErrorLoggerMock:
                def log_error(self, msg, context=""): print(f"ERROR [{context}]: {msg}")
                def log_warning(self, msg, context=""): print(f"WARNING [{context}]: {msg}")
                def log_info(self, msg, context=""): print(f"INFO [{context}]: {msg}")
                def log_debug(self, msg, context=""): print(f"DEBUG [{context}]: {msg}")


# 定义常量
DEFAULT_FLOAT_SUFFIX = "f"
DEFAULT_DOUBLE_SUFFIX = ""
DEFAULT_SAMPLE_TIME = 0.01

class CSyntaxHighlighter(QSyntaxHighlighter):
    """C/C++ 语法高亮器"""
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
            "PID_HandleTypeDef", "PID_ModeType", "PID_Type", "PID_WorkMode",
            "PID_MODE_MANUAL", "PID_MODE_AUTOMATIC",
            "PID_TYPE_STANDARD", "PID_TYPE_PI_D", "PID_TYPE_I_PD",
            "PID_MODE_POSITION", "PID_MODE_VELOCITY", "INFINITY", "true", "false"
        ]
        for word in keywords:
            self.highlighting_rules.append((QRegularExpression(f"\\b{word}\\b"), keyword_format))

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
    PANEL_TYPE_NAME: str = "advanced_pid_code_generator"
    PANEL_DISPLAY_NAME: str = "PID代码生成器"

    # --- 用于字典键和UI文本的常量 ---
    _CONFIG_VERSION = "5.1.0"
    # PID参数键
    _P_KP = "kp"
    _P_KI = "ki"
    _P_KD = "kd"
    _P_MAX_OUT = "max_output"
    _P_MIN_OUT = "min_output"
    _P_INT_LIM = "integral_limit"
    _P_SAMPLE_TIME = "sample_time"
    _P_ALGO_TYPE = "algorithm_type"
    _P_KFF = "kff"
    _P_FF_WEIGHT = "ff_weight"
    _P_OUT_RAMP = "output_ramp"
    _P_DEADBAND = "deadband"
    _P_INT_SEP_THRESH = "integral_separation_threshold"
    _P_D_FILTER = "d_filter_coef"
    _P_IN_FILTER = "input_filter_coef"
    _P_SP_FILTER = "setpoint_filter_coef"
    _P_PID_TYPE = "pid_type"
    _P_WORK_MODE = "work_mode"
    _P_ADAPTIVE_EN = "adaptive_enable"
    _P_ADAPTIVE_KP_MIN = "adaptive_kp_min"
    _P_ADAPTIVE_KP_MAX = "adaptive_kp_max"
    _P_ADAPTIVE_KI_MIN = "adaptive_ki_min"
    _P_ADAPTIVE_KI_MAX = "adaptive_ki_max"
    _P_ADAPTIVE_KD_MIN = "adaptive_kd_min"
    _P_ADAPTIVE_KD_MAX = "adaptive_kd_max"
    _P_FUZZY_EN = "fuzzy_enable"
    _P_FUZZY_ERR_RANGE = "fuzzy_error_range"
    _P_FUZZY_DERR_RANGE = "fuzzy_derror_range"

    # 代码配置键
    _C_STRUCT_NAME = "struct_name"
    _C_FUNC_PREFIX = "function_prefix"
    _C_USE_FLOAT = "use_float"
    _C_INC_COMMENTS = "include_comments"
    _C_INC_HEADER = "include_header"
    _C_HEADER_NAME = "header_name"
    _C_USE_TEMPLATE = "use_template"
    _C_OPTIMIZATION = "optimization_level"
    _C_FLOAT_SUFFIX = "float_suffix"
    _C_DATA_TYPE = "data_type"

    def __init__(self, panel_id: int, main_window_ref, initial_config: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
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

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(10)
        self.debounce_timer.timeout.connect(self._trigger_full_code_generation_and_preview_update)

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
            self._P_KP: 1.0, self._P_KI: 0.1, self._P_KD: 0.01,
            self._P_MAX_OUT: 100.0, self._P_MIN_OUT: -100.0,
            self._P_INT_LIM: 50.0, self._P_SAMPLE_TIME: DEFAULT_SAMPLE_TIME,
            self._P_ALGO_TYPE: "advanced",
            self._P_KFF: 0.0, self._P_FF_WEIGHT: 1.0,
            self._P_OUT_RAMP: 0.0, self._P_DEADBAND: 0.0,
            self._P_INT_SEP_THRESH: 1000.0,
            self._P_D_FILTER: 0.1, self._P_IN_FILTER: 0.0, self._P_SP_FILTER: 0.0,
            self._P_PID_TYPE: "standard",
            self._P_WORK_MODE: "position",
            self._P_ADAPTIVE_EN: False, self._P_ADAPTIVE_KP_MIN: 0.1, self._P_ADAPTIVE_KP_MAX: 10.0,
            self._P_ADAPTIVE_KI_MIN: 0.01, self._P_ADAPTIVE_KI_MAX: 1.0,
            self._P_ADAPTIVE_KD_MIN: 0.001, self._P_ADAPTIVE_KD_MAX: 0.1,
            self._P_FUZZY_EN: False, self._P_FUZZY_ERR_RANGE: 100.0, self._P_FUZZY_DERR_RANGE: 10.0,
        }

    def _get_default_code_config(self) -> Dict[str, Any]:
        return {
            self._C_STRUCT_NAME: "PID_HandleTypeDef", self._C_FUNC_PREFIX: "PID",
            self._C_USE_FLOAT: True, self._C_INC_COMMENTS: True, self._C_INC_HEADER: True,
            self._C_HEADER_NAME: "pid.h", self._C_USE_TEMPLATE: True, self._C_OPTIMIZATION: "standard",
            self._C_FLOAT_SUFFIX: DEFAULT_FLOAT_SUFFIX,
            self._C_DATA_TYPE: "float"
        }

    def _init_ui_element_references(self):
        """初始化所有UI元素引用为None"""
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
        self.status_label: Optional[QLabel] = None

    def _init_ui(self) -> None:
        """构建用户界面"""
        self._log_debug("Building UI...")
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # 左侧: PID 实例管理
        instance_management_container = QWidget()
        instance_management_layout = QVBoxLayout(instance_management_container)
        instance_management_layout.setContentsMargins(0, 0, 0, 0)
        instance_management_group = QGroupBox("PID 控制器实例")
        instance_group_layout = QVBoxLayout(instance_management_group)
        self.pid_instance_list_widget = QListWidget()
        self.pid_instance_list_widget.currentItemChanged.connect(self._on_selected_pid_instance_changed)
        self.pid_instance_list_widget.setMinimumWidth(180)
        self.pid_instance_list_widget.setMaximumWidth(250)
        instance_group_layout.addWidget(self.pid_instance_list_widget)
        name_input_layout = QHBoxLayout()
        name_input_layout.addWidget(QLabel("实例名:"))
        self.instance_name_edit = QLineEdit()
        self.instance_name_edit.setPlaceholderText("例如: motor_pid")
        name_input_layout.addWidget(self.instance_name_edit)
        instance_group_layout.addLayout(name_input_layout)
        instance_buttons_layout = QHBoxLayout()
        instance_buttons_layout.setSpacing(10)
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

        # 右侧: 参数配置和预览选项卡
        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.param_tabs = QTabWidget()
        self.param_tabs.setTabPosition(QTabWidget.West)
        self.param_tabs.addTab(self._create_basic_params_tab(), "PID 参数")
        self.param_tabs.addTab(self._create_advanced_features_tab(), "高级特性")
        self.param_tabs.addTab(self._create_code_config_tab(), "代码生成配置")
        self.param_tabs.addTab(self._create_preview_tab(), "代码预览")
        self.param_tabs.currentChanged.connect(self._on_tab_changed)
        self.param_tabs.setMinimumHeight(600)
        right_panel_layout.addWidget(self.param_tabs)
        splitter.addWidget(right_panel_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter)

        # 底部操作按钮和状态栏
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
        self._log_debug("UI built.")

    def _create_basic_params_tab(self) -> QWidget:
        """创建PID参数配置标签页"""
        self._log_debug("Creating PID Parameters Tab...")
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 核心PID参数
        core_group = QGroupBox("核心PID参数")
        core_layout = QGridLayout(core_group)
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["高级PID"]) # 简化，只保留高级模板
        self.pid_type_combo = QComboBox()
        self.pid_type_combo.addItems(["标准 (Perr, Derr)", "PI-D (Perr, Dmeas)", "I-PD (Pmeas, Dmeas)"])
        self.work_mode_combo = QComboBox()
        self.work_mode_combo.addItems(["位置模式", "速度模式 (增量)"])
        self.kp_spinbox, self.ki_spinbox, self.kd_spinbox, self.sample_time_spinbox = (QDoubleSpinBox() for _ in range(4))
        
        # 布局
        core_layout.addWidget(QLabel("PID类型 (P,D作用):"), 0, 0); core_layout.addWidget(self.pid_type_combo, 0, 1)
        core_layout.addWidget(QLabel("工作模式 (输出):"), 1, 0); core_layout.addWidget(self.work_mode_combo, 1, 1)
        core_layout.addWidget(QLabel("比例 (Kp):"), 0, 2); core_layout.addWidget(self.kp_spinbox, 0, 3)
        core_layout.addWidget(QLabel("积分 (Ki, 连续域):"), 1, 2); core_layout.addWidget(self.ki_spinbox, 1, 3)
        core_layout.addWidget(QLabel("微分 (Kd, 连续域):"), 2, 2); core_layout.addWidget(self.kd_spinbox, 2, 3)
        core_layout.addWidget(QLabel("采样时间 (s):"), 3, 2); core_layout.addWidget(self.sample_time_spinbox, 3, 3)
        layout.addWidget(core_group)

        # 输出与积分限制
        limits_group = QGroupBox("输出与积分限制")
        limits_layout = QGridLayout(limits_group)
        self.max_output_spinbox, self.min_output_spinbox, self.integral_limit_spinbox, self.output_ramp_spinbox = (QDoubleSpinBox() for _ in range(4))
        limits_layout.addWidget(QLabel("最大输出:"), 0, 0); limits_layout.addWidget(self.max_output_spinbox, 0, 1)
        limits_layout.addWidget(QLabel("最小输出:"), 0, 2); limits_layout.addWidget(self.min_output_spinbox, 0, 3)
        limits_layout.addWidget(QLabel("积分限幅 (绝对值):"), 1, 0); limits_layout.addWidget(self.integral_limit_spinbox, 1, 1)
        limits_layout.addWidget(QLabel("输出变化率限制 (单位/秒, 0不限制):"), 1, 2); limits_layout.addWidget(self.output_ramp_spinbox, 1, 3)
        layout.addWidget(limits_group)

        # 高级控制与滤波器
        adv_filter_group = QGroupBox("高级控制与滤波器")
        adv_filter_layout = QGridLayout(adv_filter_group)
        self.kff_spinbox, self.ff_weight_spinbox, self.deadband_spinbox, self.integral_separation_spinbox, self.d_filter_spinbox, self.input_filter_spinbox, self.setpoint_filter_spinbox = (QDoubleSpinBox() for _ in range(7))
        adv_filter_layout.addWidget(QLabel("前馈 (Kff):"), 0, 0); adv_filter_layout.addWidget(self.kff_spinbox, 0, 1)
        adv_filter_layout.addWidget(QLabel("前馈权重 (0-1):"), 0, 2); adv_filter_layout.addWidget(self.ff_weight_spinbox, 0, 3)
        adv_filter_layout.addWidget(QLabel("死区大小:"), 1, 0); adv_filter_layout.addWidget(self.deadband_spinbox, 1, 1)
        adv_filter_layout.addWidget(QLabel("积分分离阈值 (误差绝对值):"), 1, 2); adv_filter_layout.addWidget(self.integral_separation_spinbox, 1, 3)
        adv_filter_layout.addWidget(QLabel("微分滤波系数 (0-1, 0无):"), 2, 0); adv_filter_layout.addWidget(self.d_filter_spinbox, 2, 1)
        adv_filter_layout.addWidget(QLabel("输入滤波系数 (0-1, 0无):"), 2, 2); adv_filter_layout.addWidget(self.input_filter_spinbox, 2, 3)
        adv_filter_layout.addWidget(QLabel("设定值滤波系数 (0-1, 0无):"), 3, 0); adv_filter_layout.addWidget(self.setpoint_filter_spinbox, 3, 1)
        layout.addWidget(adv_filter_group)

        # 连接信号
        for spinbox in self.findChildren(QDoubleSpinBox):
            spinbox.setDecimals(6)
            spinbox.setRange(-1e6, 1e6)
            spinbox.valueChanged.connect(self._queue_param_change)
        for combo in self.findChildren(QComboBox):
            combo.currentTextChanged.connect(self._queue_param_change)
        
        self.ff_weight_spinbox.setRange(0.0, 1.0); self.d_filter_spinbox.setRange(0.0, 1.0)
        self.input_filter_spinbox.setRange(0.0, 1.0); self.setpoint_filter_spinbox.setRange(0.0, 1.0)
        self.max_output_spinbox.setRange(0.0, 1e6); self.min_output_spinbox.setRange(-1e6, 0.0)
        self.integral_limit_spinbox.setRange(0, 1e6); self.output_ramp_spinbox.setRange(0, 1e6)
        self.sample_time_spinbox.setRange(1e-6, 10.0);
        
        layout.addStretch()
        return widget

    def _create_advanced_features_tab(self) -> QWidget:
        """创建高级特性标签页（禁用未实现功能）"""
        self._log_debug("Creating Advanced Features Tab (with disabled sections)...")
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 自适应控制 (禁用)
        adaptive_group = QGroupBox("自适应控制")
        adaptive_group.setToolTip("此功能正在开发中，当前版本不可用。\n代码中仅提供参数占位符。")
        adaptive_group.setEnabled(False)
        adaptive_layout = QGridLayout(adaptive_group)
        self.adaptive_enable_checkbox = QCheckBox("启用自适应控制")
        adaptive_layout.addWidget(self.adaptive_enable_checkbox, 0, 0, 1, 4)
        adaptive_layout.addWidget(QLabel("Kp 范围:"), 1, 0)
        self.adaptive_kp_min_spinbox, self.adaptive_kp_max_spinbox = QDoubleSpinBox(), QDoubleSpinBox()
        adaptive_layout.addWidget(self.adaptive_kp_min_spinbox, 1, 1); adaptive_layout.addWidget(self.adaptive_kp_max_spinbox, 1, 2)
        layout.addWidget(adaptive_group)

        # 模糊PID控制 (禁用)
        fuzzy_group = QGroupBox("模糊PID控制")
        fuzzy_group.setToolTip("此功能正在开发中，当前版本不可用。\n代码中仅提供参数占位符。")
        fuzzy_group.setEnabled(False)
        fuzzy_layout = QGridLayout(fuzzy_group)
        self.fuzzy_enable_checkbox = QCheckBox("启用模糊PID控制")
        fuzzy_layout.addWidget(self.fuzzy_enable_checkbox, 0, 0, 1, 2)
        fuzzy_layout.addWidget(QLabel("模糊误差范围:"), 1, 0)
        self.fuzzy_error_range_spinbox = QDoubleSpinBox()
        fuzzy_layout.addWidget(self.fuzzy_error_range_spinbox, 1, 1)
        layout.addWidget(fuzzy_group)
        
        layout.addStretch()
        return widget

    def _create_code_config_tab(self) -> QWidget:
        """创建代码生成配置标签页"""
        self._log_debug("Creating Code Config Tab...")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("全局代码生成选项 (应用于所有实例的库文件)")
        grid = QGridLayout(group)
        self.struct_name_edit = QLineEdit()
        self.function_prefix_edit = QLineEdit()
        self.header_name_edit = QLineEdit()
        self.optimization_combo = QComboBox()
        self.optimization_combo.addItems(["标准"]) # 简化
        self.use_float_checkbox = QCheckBox("使用 float 类型 (否则 double)")
        self.include_comments_checkbox = QCheckBox("包含注释")
        
        grid.addWidget(QLabel("库结构体名称:"), 0, 0); grid.addWidget(self.struct_name_edit, 0, 1)
        grid.addWidget(QLabel("库函数前缀:"), 1, 0); grid.addWidget(self.function_prefix_edit, 1, 1)
        grid.addWidget(QLabel("库头文件名称 (.h):"), 2, 0); grid.addWidget(self.header_name_edit, 2, 1)
        grid.addWidget(self.use_float_checkbox, 4, 0)
        grid.addWidget(self.include_comments_checkbox, 4, 1)

        for w in [self.struct_name_edit, self.function_prefix_edit, self.header_name_edit, self.optimization_combo, self.use_float_checkbox, self.include_comments_checkbox]:
            if isinstance(w, QLineEdit): w.textChanged.connect(self._queue_global_config_change)
            elif isinstance(w, QComboBox): w.currentTextChanged.connect(self._queue_global_config_change)
            elif isinstance(w, QCheckBox): w.stateChanged.connect(self._queue_global_config_change)
        
        self.use_template_checkbox = QCheckBox() # Hidden, always true
        self.include_header_checkbox = QCheckBox() # Hidden, always true

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _create_preview_tab(self) -> QWidget:
        """创建代码预览标签页"""
        self._log_debug("Creating Preview Tab...")
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
        self.code_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.code_preview.setMinimumHeight(600)
        self.highlighter = CSyntaxHighlighter(self.code_preview.document())
        layout.addWidget(self.code_preview)
        return widget

    # --- 事件处理和逻辑 ---
    
    @Slot()
    def _queue_param_change(self):
        """当PID参数UI变化时，启动防抖定时器"""
        self._on_pid_param_ui_changed()
        self.debounce_timer.start()

    @Slot()
    def _queue_global_config_change(self):
        """当全局代码配置UI变化时，启动防抖定时器"""
        self._on_global_code_config_changed()
        self.debounce_timer.start()

    @Slot(int)
    def _on_tab_changed(self, index: int):
        """当标签页切换时，如果切换到预览标签页，则立即更新预览"""
        if self.param_tabs and self.param_tabs.tabText(index) == "代码预览":
            self._trigger_full_code_generation_and_preview_update()

    def _update_controls_based_on_selection(self, is_valid_selection: bool):
        """根据是否有选中项来启用/禁用UI控件"""
        for tab_index in range(self.param_tabs.count()):
            tab_name = self.param_tabs.tabText(tab_index)
            if tab_name in ["PID 参数"]:
                self.param_tabs.widget(tab_index).setEnabled(is_valid_selection)
        self.rename_instance_button.setEnabled(is_valid_selection)
        self.remove_instance_button.setEnabled(is_valid_selection)


    @Slot()
    def _on_add_instance_button_clicked(self):
        """处理添加PID实例按钮点击事件"""
        instance_name = self.instance_name_edit.text().strip()
        if not instance_name:
            instance_name, ok = QInputDialog.getText(self, "添加PID实例", "输入实例名称 (例如 motor_pid):")
            if not (ok and instance_name): return

        if not re.fullmatch(r"^[a-zA-Z_][a-zA-Z0-9_]*$", instance_name):
            QMessageBox.warning(self, "名称无效", "实例名称必须以字母或下划线开头，且只包含字母、数字和下划线。")
            return
        if any(inst['name'] == instance_name for inst in self.pid_instance_configs):
            QMessageBox.warning(self, "名称冲突", f"名为 '{instance_name}' 的PID实例已存在。")
            return

        self._add_pid_instance(instance_name)
        self.instance_name_edit.clear()
        self._trigger_full_code_generation_and_preview_update()

    def _add_pid_instance(self, name: str):
        """向数据模型和UI列表添加一个PID实例"""
        self._log_debug(f"Adding PID instance: {name}")
        new_config = {'name': name, 'params': self._get_default_pid_params()}
        self.pid_instance_configs.append(new_config)
        item = QListWidgetItem(name)
        self.pid_instance_list_widget.addItem(item)
        self.pid_instance_list_widget.setCurrentItem(item)

    @Slot()
    def _on_remove_instance_button_clicked(self):
        """处理移除PID实例按钮点击事件"""
        current_row = self.pid_instance_list_widget.currentRow()
        if current_row < 0: return

        instance_name = self.pid_instance_configs[current_row]['name']
        reply = QMessageBox.question(self, "确认移除", f"确定要移除PID实例 '{instance_name}' 吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.pid_instance_list_widget.takeItem(current_row)
            del self.pid_instance_configs[current_row]
            self._trigger_full_code_generation_and_preview_update()

    @Slot()
    def _on_rename_instance_button_clicked(self):
        """处理重命名PID实例按钮点击事件"""
        current_row = self.pid_instance_list_widget.currentRow()
        if current_row < 0: return

        old_name = self.pid_instance_configs[current_row]['name']
        new_name, ok = QInputDialog.getText(self, "重命名PID实例", "输入新名称:", text=old_name)
        if not (ok and new_name and new_name != old_name): return

        if not re.fullmatch(r"^[a-zA-Z_][a-zA-Z0-9_]*$", new_name):
            QMessageBox.warning(self, "名称无效", "名称格式不正确。")
            return
        if any(inst['name'] == new_name for i, inst in enumerate(self.pid_instance_configs) if i != current_row):
            QMessageBox.warning(self, "名称冲突", f"实例 '{new_name}' 已存在。")
            return
        
        self.pid_instance_configs[current_row]['name'] = new_name
        self.pid_instance_list_widget.item(current_row).setText(new_name)
        self.instance_name_edit.setText(new_name)
        self._update_title()
        self._trigger_full_code_generation_and_preview_update()

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_selected_pid_instance_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]):
        """处理PID实例列表选中项变化事件"""
        is_valid_selection = current is not None
        self._update_controls_based_on_selection(is_valid_selection)

        if not is_valid_selection:
            self.active_pid_instance_index = -1
            self.instance_name_edit.clear()
            self._load_params_to_ui(None)
        else:
            self.active_pid_instance_index = self.pid_instance_list_widget.row(current)
            self.instance_name_edit.setText(current.text())
            self._load_params_to_ui(self.pid_instance_configs[self.active_pid_instance_index]['params'])
        
        self._update_title()

    def _load_params_to_ui(self, params: Optional[Dict[str, Any]]):
        """根据给定的参数字典加载到UI"""
        params_to_load = params or self._get_default_pid_params()

        # 阻塞信号，防止循环触发
        for w in self.findChildren(QWidget):
            if isinstance(w, (QDoubleSpinBox, QComboBox, QCheckBox)):
                w.blockSignals(True)

        self.pid_type_combo.setCurrentText({"standard": "标准 (Perr, Derr)", "pi_d": "PI-D (Perr, Dmeas)", "i_pd": "I-PD (Pmeas, Dmeas)"}.get(params_to_load[self._P_PID_TYPE], "标准 (Perr, Derr)"))
        self.work_mode_combo.setCurrentText({"position": "位置模式", "velocity": "速度模式 (增量)"}.get(params_to_load[self._P_WORK_MODE], "位置模式"))

        spinbox_map = {
            self._P_KP: self.kp_spinbox, self._P_KI: self.ki_spinbox, self._P_KD: self.kd_spinbox,
            self._P_KFF: self.kff_spinbox, self._P_FF_WEIGHT: self.ff_weight_spinbox,
            self._P_SAMPLE_TIME: self.sample_time_spinbox, self._P_MAX_OUT: self.max_output_spinbox,
            self._P_MIN_OUT: self.min_output_spinbox, self._P_INT_LIM: self.integral_limit_spinbox,
            self._P_OUT_RAMP: self.output_ramp_spinbox, self._P_DEADBAND: self.deadband_spinbox,
            self._P_INT_SEP_THRESH: self.integral_separation_spinbox,
            self._P_D_FILTER: self.d_filter_spinbox, self._P_IN_FILTER: self.input_filter_spinbox,
            self._P_SP_FILTER: self.setpoint_filter_spinbox,
        }
        for key, spinbox in spinbox_map.items():
            if spinbox: spinbox.setValue(params_to_load.get(key, 0.0))
        
        for w in self.findChildren(QWidget):
            if isinstance(w, (QDoubleSpinBox, QComboBox, QCheckBox)):
                w.blockSignals(False)

    def _load_global_code_config_to_ui(self):
        """加载当前全局代码配置到UI"""
        cfg = self.code_config
        self.struct_name_edit.setText(cfg[self._C_STRUCT_NAME])
        self.function_prefix_edit.setText(cfg[self._C_FUNC_PREFIX])
        self.header_name_edit.setText(cfg[self._C_HEADER_NAME])
        self.use_float_checkbox.setChecked(cfg[self._C_USE_FLOAT])
        self.include_comments_checkbox.setChecked(cfg[self._C_INC_COMMENTS])

    @Slot()
    def _on_pid_param_ui_changed(self):
        """当PID参数UI值变化时，更新内部数据模型"""
        if self.active_pid_instance_index < 0: return
        params = self.pid_instance_configs[self.active_pid_instance_index]['params']
        
        params[self._P_PID_TYPE] = {v: k for k, v in {"standard": "标准 (Perr, Derr)", "pi_d": "PI-D (Perr, Dmeas)", "i_pd": "I-PD (Pmeas, Dmeas)"}.items()}[self.pid_type_combo.currentText()]
        params[self._P_WORK_MODE] = {v: k for k, v in {"position": "位置模式", "velocity": "速度模式 (增量)"}.items()}[self.work_mode_combo.currentText()]
        
        spinbox_map = { self._P_KP: self.kp_spinbox, self._P_KI: self.ki_spinbox, self._P_KD: self.kd_spinbox, self._P_KFF: self.kff_spinbox, self._P_FF_WEIGHT: self.ff_weight_spinbox, self._P_SAMPLE_TIME: self.sample_time_spinbox, self._P_MAX_OUT: self.max_output_spinbox, self._P_MIN_OUT: self.min_output_spinbox, self._P_INT_LIM: self.integral_limit_spinbox, self._P_OUT_RAMP: self.output_ramp_spinbox, self._P_DEADBAND: self.deadband_spinbox, self._P_INT_SEP_THRESH: self.integral_separation_spinbox, self._P_D_FILTER: self.d_filter_spinbox, self._P_IN_FILTER: self.input_filter_spinbox, self._P_SP_FILTER: self.setpoint_filter_spinbox }
        for key, spinbox in spinbox_map.items():
            if spinbox: params[key] = spinbox.value()

    @Slot()
    def _on_global_code_config_changed(self):
        """当全局代码配置UI值变化时，更新内部数据模型"""
        self.code_config[self._C_STRUCT_NAME] = self.struct_name_edit.text().strip() or "PID_HandleTypeDef"
        self.code_config[self._C_FUNC_PREFIX] = self.function_prefix_edit.text().strip() or "PID"
        self.code_config[self._C_HEADER_NAME] = self.header_name_edit.text().strip() or "pid.h"
        self.code_config[self._C_USE_FLOAT] = self.use_float_checkbox.isChecked()
        self.code_config[self._C_INC_COMMENTS] = self.include_comments_checkbox.isChecked()
        self.code_config[self._C_DATA_TYPE] = "float" if self.use_float_checkbox.isChecked() else "double"
        self.code_config[self._C_FLOAT_SUFFIX] = DEFAULT_FLOAT_SUFFIX if self.use_float_checkbox.isChecked() else DEFAULT_DOUBLE_SUFFIX

    @Slot()
    def _on_generate_code_button_clicked(self):
        """处理生成/刷新所有预览按钮点击事件"""
        self._trigger_full_code_generation_and_preview_update()
        self._show_status("所有代码预览已更新。", 2000)

    def _trigger_full_code_generation_and_preview_update(self):
        """触发完整的代码生成和预览更新"""
        self._show_status("正在生成代码...", 0)
        self._on_pid_param_ui_changed()
        self._on_global_code_config_changed()
        self.generated_c_code = self._generate_c_code()
        self.generated_h_code = self._generate_h_code()
        self.generated_main_c_code = self._generate_main_c_code_for_all_instances()
        self._update_preview_content()
        self._show_status("代码生成完成。", 2000)

    @Slot()
    def _on_preview_file_selected(self):
        self._update_preview_content()

    def _update_preview_content(self):
        """根据选择器更新代码预览内容"""
        if not self.preview_file_selector or not self.code_preview or not self.preview_label: return
        selected_index = self.preview_file_selector.currentIndex()
        content, label = "", "当前预览: "
        if selected_index == 0:
            content, label = self.generated_c_code, label + "C 源文件 (库)"
        elif selected_index == 1:
            content, label = self.generated_h_code, label + "头文件 (库)"
        elif selected_index == 2:
            content, label = self.generated_main_c_code, label + "示例 Main (.c)"
        self.code_preview.setPlainText(content)
        self.preview_label.setText(label)

    @Slot()
    def _on_export_code_button_clicked(self):
        """处理导出代码文件按钮点击事件"""
        self._trigger_full_code_generation_and_preview_update()
        if not self.pid_instance_configs:
            QMessageBox.information(self, "导出提示", "请至少添加并配置一个PID实例。")
            return
        self._show_status("正在导出文件...", 0)

        suggested_base_name = Path(self.code_config[self._C_HEADER_NAME]).stem
        file_path_base, _ = QFileDialog.getSaveFileName(self, "选择保存位置和基础文件名", str(Path.cwd() / suggested_base_name), "All Files (*)")
        if not file_path_base:
            self._show_status("导出已取消。", 2000)
            return

        save_dir, base_name = Path(file_path_base).parent, Path(file_path_base).stem
        save_dir.mkdir(parents=True, exist_ok=True)
        h_file_name = self.code_config[self._C_HEADER_NAME]
        c_file_name = f"{Path(h_file_name).stem}.c"
        main_c_file_name = f"{base_name}_main.c"

        files_to_write = [
            (save_dir / h_file_name, self.generated_h_code),
            (save_dir / c_file_name, self.generated_c_code),
            (save_dir / main_c_file_name, self.generated_main_c_code)
        ]
        try:
            for path, content in files_to_write:
                if content and not content.startswith("// Error"):
                    path.write_text(content, encoding='utf-8')
            QMessageBox.information(self, "导出成功", f"代码已导出到:\n{save_dir}")
            self._show_status("代码导出成功。", 2000)
        except IOError as e:
            QMessageBox.critical(self, "导出失败", f"写入文件时发生IO错误:\n{e}")
            self._show_status("导出失败：写入文件错误。", 2000)

    # --- 代码生成核心逻辑 ---

    def _generate_h_code(self) -> str:
        """生成C头文件（库）代码"""
        h_template_path = self._get_template_path(extension="h")
        if not h_template_path: return "// Error: Library Header template not found."
        return self._generate_from_template_file(h_template_path)

    def _generate_c_code(self) -> str:
        """生成C源文件（库）代码"""
        c_template_path = self._get_template_path(extension="c")
        if not c_template_path: return "// Error: Library C source template not found."
        return self._generate_from_template_file(c_template_path)

    def _generate_main_c_code_for_all_instances(self) -> str:
        """为所有PID实例生成示例Main C代码"""
        main_template_path = Path(__file__).parent / "templates" / "user_main_template.c"
        if not main_template_path.exists():
            return f"// Error: Main C template not found: {main_template_path}"
        try:
            template = main_template_path.read_text(encoding='utf-8')
            global_replacements = {
                '{{HEADER_NAME}}': self.code_config[self._C_HEADER_NAME],
                '{{STRUCT_NAME}}': self.code_config[self._C_STRUCT_NAME],
                '{{FUNCTION_PREFIX}}': self.code_config[self._C_FUNC_PREFIX],
                '{{DATA_TYPE}}': self.code_config[self._C_DATA_TYPE],
                '{{TIMESTAMP}}': self._get_current_time(),
                '{{SFX}}': self.code_config[self._C_FLOAT_SUFFIX]
            }
            for key, val in global_replacements.items():
                template = template.replace(key, str(val))
            
            declarations = "\n".join([f"    {self.code_config[self._C_STRUCT_NAME]} {inst['name']};" for inst in self.pid_instance_configs])
            
            init_lines, sim_lines = [], []
            if not self.pid_instance_configs:
                sim_lines.append("    // 未配置任何PID实例，无示例代码生成。")
            else:
                for inst in self.pid_instance_configs:
                    init_lines.extend(self._get_instance_init_code(inst))
                    sim_lines.extend(self._get_instance_sim_code(inst))
            
            template = template.replace('{{PID_INSTANCE_DECLARATIONS}}', declarations)
            template = template.replace('{{PID_INSTANCE_INITIALIZATIONS}}', "\n".join(init_lines))
            template = template.replace('{{PID_EXAMPLE_COMPUTATIONS}}', "\n".join(sim_lines))
            return template
        except Exception as e:
            self._log_error(f"user_main.c generation failed: {e}")
            return f"// Error generating user_main.c: {e}"

    def _get_instance_init_code(self, inst_cfg: Dict) -> List[str]:
        """为单个实例生成初始化C代码片段"""
        name = inst_cfg['name']
        p = inst_cfg['params']
        sfx = self.code_config[self._C_FLOAT_SUFFIX]
        prefix = self.code_config[self._C_FUNC_PREFIX]
        sample_t = max(p[self._P_SAMPLE_TIME], 1e-6)

        lines = [f"    // 初始化PID实例: {name}"]
        lines.append(f"    {prefix}_Init(&{name}, {p[self._P_KP]}{sfx}, {p[self._P_KI]}{sfx}, {p[self._P_KD]}{sfx}, {sample_t}{sfx});")
        lines.append(f"    {prefix}_SetOutputLimits(&{name}, {p[self._P_MAX_OUT]}{sfx});") # Note: Min output is handled inside by taking abs
        lines.append(f"    {prefix}_SetIntegralLimits(&{name}, {p[self._P_INT_LIM]}{sfx});")
        if p[self._P_OUT_RAMP] > 0: lines.append(f"    {prefix}_SetOutputRamp(&{name}, {p[self._P_OUT_RAMP]}{sfx});")
        if p[self._P_DEADBAND] > 0: lines.append(f"    {prefix}_SetDeadband(&{name}, {p[self._P_DEADBAND]}{sfx});")
        if p[self._P_INT_SEP_THRESH] < 1000.0: lines.append(f"    {prefix}_SetIntegralSeparationThreshold(&{name}, {p[self._P_INT_SEP_THRESH]}{sfx});")
        if p[self._P_D_FILTER] > 0: lines.append(f"    {prefix}_SetDFilter(&{name}, {p[self._P_D_FILTER]}{sfx});")
        if p[self._P_IN_FILTER] > 0: lines.append(f"    {prefix}_SetInputFilter(&{name}, {p[self._P_IN_FILTER]}{sfx});")
        if p[self._P_SP_FILTER] > 0: lines.append(f"    {prefix}_SetSetpointFilter(&{name}, {p[self._P_SP_FILTER]}{sfx});")
        if p[self._P_KFF] != 0 or p[self._P_FF_WEIGHT] != 1.0: lines.append(f"    {prefix}_SetFeedForwardParams(&{name}, {p[self._P_KFF]}{sfx}, {p[self._P_FF_WEIGHT]}{sfx});")

        pid_type_map = {"standard": "PID_TYPE_STANDARD", "pi_d": "PID_TYPE_PI_D", "i_pd": "PID_TYPE_I_PD"}
        work_mode_map = {"position": "PID_MODE_POSITION", "velocity": "PID_MODE_VELOCITY"}
        lines.append(f"    {prefix}_SetType(&{name}, {pid_type_map[p[self._P_PID_TYPE]]});")
        lines.append(f"    {prefix}_SetWorkMode(&{name}, {work_mode_map[p[self._P_WORK_MODE]]});")
        lines.append(f"    printf(\"Initialized PID: {name} (Kp=%.4f, Ki_cont=%.4f, Kd_cont=%.4f, Ts=%.4f)\\n\", (double){p[self._P_KP]}{sfx}, (double){p[self._P_KI]}{sfx}, (double){p[self._P_KD]}{sfx}, (double){sample_t}{sfx});")
        lines.append("")
        return lines

    def _get_instance_sim_code(self, inst_cfg: Dict) -> List[str]:
        """为单个实例生成仿真C代码片段"""
        name = inst_cfg['name']
        p = inst_cfg['params']
        sfx = self.code_config[self._C_FLOAT_SUFFIX]
        prefix = self.code_config[self._C_FUNC_PREFIX]
        data_t = self.code_config[self._C_DATA_TYPE]
        sample_t = max(p[self._P_SAMPLE_TIME], 1e-6)

        return [
            f"    // 示例计算 for {name}",
            f"    {data_t} {name}_setpoint = 50.0{sfx};",
            f"    {data_t} {name}_measurement = 0.0{sfx};",
            f"    printf(\"\\n--- Running simulation for {name} ---\\n\");",
            "    for (int j = 0; j < 5; ++j) {",
            f"        {data_t} {name}_output = {prefix}_Compute(&{name}, {name}_setpoint, {name}_measurement);",
            f"        {name}_measurement = simulate_system_response({name}_measurement, {name}_output, {sample_t}{sfx});",
            f"        printf(\"  {name}: Step %d, SP=%.2f, PV=%.2f, Out=%.2f\\n\", j+1, (double){name}_setpoint, (double){name}_measurement, (double){name}_output);",
            "    }", ""
        ]

    def _get_template_path(self, extension: str = "c") -> Optional[Path]:
        """获取模板文件路径（仅使用高级模板）"""
        template_dir = Path(__file__).parent / "templates"
        template_file = template_dir / f"advanced_pid_template.{extension}"
        if template_file.exists():
            return template_file
        self._log_warning(f"Template file not found: {template_file}", self.PANEL_TYPE_NAME)
        return None

    def _generate_from_template_file(self, template_path: Path) -> str:
        """从模板文件生成代码（通用逻辑）"""
        try:
            template_content = template_path.read_text(encoding='utf-8')
            params = self._get_default_pid_params() # 库文件使用默认参数来填充默认值
            sfx = self.code_config[self._C_FLOAT_SUFFIX]
            sample_t = max(params[self._P_SAMPLE_TIME], 1e-6)

            replacements = {
                '{{STRUCT_NAME}}': self.code_config[self._C_STRUCT_NAME],
                '{{FUNCTION_PREFIX}}': self.code_config[self._C_FUNC_PREFIX],
                '{{DATA_TYPE}}': self.code_config[self._C_DATA_TYPE],
                '{{HEADER_NAME}}': self.code_config[self._C_HEADER_NAME],
                '{{TIMESTAMP}}': self._get_current_time(),
                '{{SFX}}': sfx,
                '{{KFF_DEFAULT}}': f"{params[self._P_KFF]}{sfx}",
                '{{FF_WEIGHT_DEFAULT}}': f"{params[self._P_FF_WEIGHT]}{sfx}",
                '{{OUTPUT_LIMIT_DEFAULT}}': f"{params[self._P_MAX_OUT]}{sfx}",
                '{{INTEGRAL_LIMIT_DEFAULT}}': f"{params[self._P_INT_LIM]}{sfx}",
                '{{OUTPUT_RAMP_DEFAULT}}': f"{params[self._P_OUT_RAMP]}{sfx}",
                '{{DEADBAND_DEFAULT}}': f"{params[self._P_DEADBAND]}{sfx}",
                '{{INTEGRAL_SEPARATION_THRESHOLD_DEFAULT}}': f"{params[self._P_INT_SEP_THRESH]}{sfx}",
                '{{D_FILTER_COEF_DEFAULT}}': f"{params[self._P_D_FILTER]}{sfx}",
                '{{INPUT_FILTER_COEF_DEFAULT}}': f"{params[self._P_IN_FILTER]}{sfx}",
                '{{SETPOINT_FILTER_COEF_DEFAULT}}': f"{params[self._P_SP_FILTER]}{sfx}",
                '{{ADAPTIVE_ENABLE}}': 'false', # 模板中此功能默认关闭
                '{{FUZZY_ENABLE}}': 'false', # 模板中此功能默认关闭
                '{{ADAPTIVE_KP_MIN_DEFAULT}}': f"{params[self._P_ADAPTIVE_KP_MIN]}{sfx}",
                '{{ADAPTIVE_KP_MAX_DEFAULT}}': f"{params[self._P_ADAPTIVE_KP_MAX]}{sfx}",
                '{{ADAPTIVE_KI_MIN_DEFAULT}}': f"{params[self._P_ADAPTIVE_KI_MIN]}{sfx}",
                '{{ADAPTIVE_KI_MAX_DEFAULT}}': f"{params[self._P_ADAPTIVE_KI_MAX]}{sfx}",
                '{{ADAPTIVE_KD_MIN_DEFAULT}}': f"{params[self._P_ADAPTIVE_KD_MIN]}{sfx}",
                '{{ADAPTIVE_KD_MAX_DEFAULT}}': f"{params[self._P_ADAPTIVE_KD_MAX]}{sfx}",
                '{{FUZZY_ERROR_RANGE_DEFAULT}}': f"{params[self._P_FUZZY_ERR_RANGE]}{sfx}",
                '{{FUZZY_DERROR_RANGE_DEFAULT}}': f"{params[self._P_FUZZY_DERR_RANGE]}{sfx}",
            }
            
            for key, value in replacements.items():
                template_content = template_content.replace(key, str(value))

            if not self.code_config[self._C_INC_COMMENTS]:
                template_content = re.sub(r'/\*.*?\*/', '', template_content, flags=re.DOTALL)
                template_content = re.sub(r'//[^\n]*', '', template_content)
                template_content = re.sub(r'\n\s*\n', '\n\n', template_content)
            
            return template_content
        except Exception as e:
            self._log_error(f"Failed to generate from template {template_path.name}: {e}")
            return f"// Error generating from template {template_path.name}: {e}"

    # --- 辅助和面板接口方法 ---

    def _get_current_time(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _update_title(self) -> None:
        """更新面板标题"""
        title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]"
        if self.active_pid_instance_index != -1:
            title += f" - 编辑: {self.pid_instance_configs[self.active_pid_instance_index]['name']}"
        if self.dock_title_changed:
            self.dock_title_changed.emit(title)

    def _show_status(self, message: str, timeout_ms: int = 0):
        """在状态栏显示消息"""
        if self.status_label:
            self.status_label.setText(message)
            if timeout_ms > 0:
                QTimer.singleShot(timeout_ms, lambda: self.status_label.setText("准备就绪。"))

    def _log_error(self, message: str): self.error_logger.log_error(message, self.PANEL_TYPE_NAME)
    def _log_warning(self, message: str): self.error_logger.log_warning(message, self.PANEL_TYPE_NAME)
    def _log_info(self, message: str): self.error_logger.log_info(message, self.PANEL_TYPE_NAME)
    def _log_debug(self, message: str): self.error_logger.log_debug(message, self.PANEL_TYPE_NAME)

    def get_config(self) -> Dict[str, Any]:
        """获取当前面板的配置"""
        self._log_debug("Getting config...")
        self._on_pid_param_ui_changed()
        self._on_global_code_config_changed()
        return {
            "version": self._CONFIG_VERSION,
            "pid_instance_configs": copy.deepcopy(self.pid_instance_configs),
            "active_pid_instance_index": self.pid_instance_list_widget.currentRow(),
            "global_code_config": self.code_config.copy(),
            "panel_type": self.PANEL_TYPE_NAME,
            "ui_selections": { "preview_file_selector_index": self.preview_file_selector.currentIndex() }
        }

    def apply_config(self, config: Dict[str, Any]):
        """应用给定的配置到面板"""
        self._log_debug(f"Applying config (version: {config.get('version')})...")
        self.code_config.update(config.get("global_code_config", {}))
        self._load_global_code_config_to_ui()
        self.pid_instance_configs = copy.deepcopy(config.get("pid_instance_configs", []))
        self.pid_instance_list_widget.clear()
        for inst_cfg in self.pid_instance_configs:
            self.pid_instance_list_widget.addItem(QListWidgetItem(inst_cfg['name']))
        
        active_index = config.get("active_pid_instance_index", -1)
        if 0 <= active_index < len(self.pid_instance_configs):
            self.pid_instance_list_widget.setCurrentRow(active_index)
        
        ui_selections = config.get("ui_selections", {})
        if "preview_file_selector_index" in ui_selections:
            self.preview_file_selector.setCurrentIndex(ui_selections["preview_file_selector_index"])

        self._trigger_full_code_generation_and_preview_update()
        self._update_title()

    def get_initial_dock_title(self) -> str:
        return f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}]"

