# enhanced_basic_comm_panel.py
# 重构后的基础收发面板 - 更清晰的架构和更丰富的功能

import re
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple, TYPE_CHECKING
from dataclasses import dataclass

from PySide6.QtCore import Slot, Qt, Signal, QTimer, QSettings
from PySide6.QtGui import QTextCursor, QIntValidator, QFont, QAction, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QMessageBox, QGroupBox, QPlainTextEdit, 
    QFileDialog, QSplitter, QTabWidget, QSpinBox,
    QProgressBar, QSlider, QToolButton, QMenu
)

# 导入快捷发送编辑对话框
try:
    from ui.quick_send_editor_dialog import QuickSendEditorDialog, QuickSendItem as DialogQuickSendItem
except ImportError:
    # 如果导入失败，使用本地定义
    DialogQuickSendItem = None
    QuickSendEditorDialog = None

if TYPE_CHECKING:
    from main import SerialDebugger


@dataclass
class QuickSendItem:
    """快捷发送项数据类"""
    name: str
    data: str
    is_hex: bool
    description: str = ""
    hotkey: str = ""  # 快捷键
    category: str = "默认"  # 分类


@dataclass
class CommStats:
    """通信统计数据类"""
    tx_count: int = 0
    rx_count: int = 0
    tx_bytes: int = 0
    rx_bytes: int = 0
    tx_rate: float = 0.0
    rx_rate: float = 0.0
    last_tx_time: Optional[datetime] = None
    last_rx_time: Optional[datetime] = None


class EnhancedBasicCommPanel(QWidget):
    """重构后的基础收发面板
    
    主要改进：
    1. 更清晰的代码结构和模块化设计
    2. 增强的UI布局和用户体验
    3. 更丰富的功能（数据过滤、高级统计等）
    4. 更好的配置管理和持久化
    5. 支持插件式的数据处理器
    """
    
    # 信号定义
    send_data_requested = Signal(str, bool)  # data, is_hex
    data_received = Signal(bytes)  # 接收到数据
    stats_updated = Signal(object)  # 统计信息更新
    
    def __init__(self, main_window_ref: 'SerialDebugger', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
        
        # 核心数据
        self.stats = CommStats()
        self.quick_send_items: List[QuickSendItem] = []
        self.command_history: List[str] = []
        self.history_index = -1
        self.max_history_size = 100
        
        # UI组件引用
        self.receive_text_edit: Optional[QTextEdit] = None
        self.send_text_edit: Optional[QPlainTextEdit] = None
        self.stats_labels: Dict[str, QLabel] = {}
        
        # 定时器
        self.auto_send_timer = QTimer()
        self.stats_timer = QTimer()
        self.rate_calc_timer = QTimer()
        
        # 配置
        self.settings = QSettings("YJ_Studio", "BasicCommPanel")
        
        # 初始化
        self._init_data()
        self._init_ui()
        self._init_connections()
        self._init_timers()
        self._load_settings()
    
    def _init_data(self):
        """初始化数据"""
        # 默认快捷发送项
        self.quick_send_items = [
            QuickSendItem("心跳", "AA BB CC DD", True, "心跳包测试", "Ctrl+1", "通信"),
            QuickSendItem("查询", "01 03 00 00", True, "状态查询", "Ctrl+2", "查询"),
            QuickSendItem("复位", "FF FF FF FF", True, "设备复位", "Ctrl+3", "控制"),
            QuickSendItem("Hello", "Hello World!", False, "文本测试", "Ctrl+4", "测试")
        ]
    
    def _init_ui(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)  # 减少边距
        main_layout.setSpacing(5)  # 减少间距
        
        # 创建选项卡界面
        tab_widget = QTabWidget()
        tab_widget.setMaximumHeight(600)  # 限制选项卡最大高度
        
        # 基础收发选项卡
        basic_tab = self._create_basic_tab()
        tab_widget.addTab(basic_tab, "基础收发")
        
        # 高级功能选项卡
        advanced_tab = self._create_advanced_tab()
        tab_widget.addTab(advanced_tab, "高级功能")
        
        # 统计信息选项卡
        stats_tab = self._create_stats_tab()
        tab_widget.addTab(stats_tab, "统计信息")
        
        main_layout.addWidget(tab_widget)
        self.setLayout(main_layout)
    
    def _create_basic_tab(self) -> QWidget:
        """创建基础收发选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 接收区域
        recv_group = self._create_receive_group()
        layout.addWidget(recv_group)
        
        # 发送区域
        send_group = self._create_send_group()
        layout.addWidget(send_group)
        
        return widget
    
    def _create_receive_group(self) -> QGroupBox:
        """创建接收区域组件"""
        group = QGroupBox("数据接收区域")
        layout = QVBoxLayout()
        
        # 统计信息栏
        stats_layout = self._create_stats_bar()
        layout.addLayout(stats_layout)
        
        # 接收文本框
        self.receive_text_edit = QTextEdit()
        self.receive_text_edit.setReadOnly(True)
        self.receive_text_edit.setMaximumHeight(200)  # 限制接收区域高度
        self.receive_text_edit.setFont(self._get_monospace_font())
        self.receive_text_edit.setStyleSheet(self._get_receive_text_style())
        layout.addWidget(self.receive_text_edit)
        
        # 接收选项
        recv_options = self._create_receive_options()
        layout.addLayout(recv_options)
        
        group.setLayout(layout)
        return group
    
    def _create_send_group(self) -> QGroupBox:
        """创建发送区域组件"""
        group = QGroupBox("数据发送区域")
        layout = QVBoxLayout()
        
        # 快捷发送区域
        quick_send = self._create_quick_send_area()
        layout.addWidget(quick_send)
        
        # 发送文本框
        self.send_text_edit = QPlainTextEdit()
        self.send_text_edit.setMaximumHeight(80)  # 减少高度从120到80
        self.send_text_edit.setFont(self._get_monospace_font())
        self.send_text_edit.setStyleSheet(self._get_send_text_style())
        self.send_text_edit.setPlaceholderText(
            "输入要发送的数据\n" +
            "Hex模式: AB CD EF 或 ABCDEF\n" +
            "文本模式: Hello World\n" +
            "快捷键: Ctrl+Enter发送, 上下箭头浏览历史"
        )
        layout.addWidget(self.send_text_edit)
        
        # 发送选项
        send_options = self._create_send_options()
        layout.addLayout(send_options)
        
        group.setLayout(layout)
        return group
    
    def _create_stats_bar(self) -> QHBoxLayout:
        """创建统计信息栏"""
        layout = QHBoxLayout()
        
        # 接收统计
        self.stats_labels['rx_count'] = QLabel("接收: 0 包")
        self.stats_labels['rx_bytes'] = QLabel("字节: 0")
        self.stats_labels['rx_rate'] = QLabel("速率: 0 B/s")
        
        layout.addWidget(self.stats_labels['rx_count'])
        layout.addWidget(self.stats_labels['rx_bytes'])
        layout.addWidget(self.stats_labels['rx_rate'])
        layout.addStretch()
        
        # 发送统计
        self.stats_labels['tx_count'] = QLabel("发送: 0 包")
        self.stats_labels['tx_bytes'] = QLabel("字节: 0")
        self.stats_labels['tx_rate'] = QLabel("速率: 0 B/s")
        
        layout.addWidget(self.stats_labels['tx_count'])
        layout.addWidget(self.stats_labels['tx_bytes'])
        layout.addWidget(self.stats_labels['tx_rate'])
        
        return layout
    
    def _create_receive_options(self) -> QHBoxLayout:
        """创建接收选项"""
        layout = QHBoxLayout()
        
        # 显示选项
        self.recv_hex_checkbox = QCheckBox("Hex显示")
        self.recv_hex_checkbox.setChecked(True)
        self.recv_timestamp_checkbox = QCheckBox("显示时间戳")
        self.recv_auto_scroll_checkbox = QCheckBox("自动滚动")
        self.recv_auto_scroll_checkbox.setChecked(True)
        self.recv_word_wrap_checkbox = QCheckBox("自动换行")
        
        layout.addWidget(self.recv_hex_checkbox)
        layout.addWidget(self.recv_timestamp_checkbox)
        layout.addWidget(self.recv_auto_scroll_checkbox)
        layout.addWidget(self.recv_word_wrap_checkbox)
        layout.addStretch()
        
        # 操作按钮
        save_btn = QPushButton("保存")
        save_btn.setMaximumWidth(60)
        save_btn.clicked.connect(self._save_receive_data)
        
        clear_btn = QPushButton("清空")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self.clear_receive_area)
        
        layout.addWidget(save_btn)
        layout.addWidget(clear_btn)
        
        return layout
    
    def _create_quick_send_area(self) -> QGroupBox:
        """创建快捷发送区域"""
        group = QGroupBox("快捷发送")
        self.quick_send_layout = QHBoxLayout()
        
        # 创建快捷发送按钮
        self._create_quick_send_buttons()
        
        group.setLayout(self.quick_send_layout)
        return group
    
    def _create_quick_send_buttons(self):
        """创建快捷发送按钮"""
        # 清除现有按钮
        while self.quick_send_layout.count():
            child = self.quick_send_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # 动态创建快捷发送按钮（最多显示8个）
        self.quick_send_buttons = []
        for i, item in enumerate(self.quick_send_items[:8]):
            btn = QPushButton(item.name)
            btn.setMaximumWidth(80)
            btn.setToolTip(f"{item.description}\n数据: {item.data[:30]}{'...' if len(item.data) > 30 else ''}")
            btn.clicked.connect(lambda checked, idx=i: self._quick_send_by_index(idx))
            
            # 设置快捷键
            if item.hotkey:
                try:
                    btn.setShortcut(QKeySequence(item.hotkey))
                except:
                    pass  # 忽略无效的快捷键
            
            self.quick_send_buttons.append(btn)
            self.quick_send_layout.addWidget(btn)
        
        self.quick_send_layout.addStretch()
        
        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setMaximumWidth(60)
        edit_btn.clicked.connect(self._edit_quick_send)
        self.quick_send_layout.addWidget(edit_btn)
    
    def _create_send_options(self) -> QVBoxLayout:
        """创建发送选项"""
        layout = QVBoxLayout()
        
        # 第一行选项
        options1_layout = QHBoxLayout()
        
        self.send_hex_checkbox = QCheckBox("Hex发送")
        self.send_hex_checkbox.setChecked(True)
        self.terminal_mode_checkbox = QCheckBox("终端模式")
        self.auto_send_checkbox = QCheckBox("自动发送")
        
        options1_layout.addWidget(self.send_hex_checkbox)
        options1_layout.addWidget(self.terminal_mode_checkbox)
        options1_layout.addWidget(self.auto_send_checkbox)
        
        # 自动发送间隔
        options1_layout.addWidget(QLabel("间隔(ms):"))
        self.auto_send_interval_edit = QLineEdit("1000")
        self.auto_send_interval_edit.setMaximumWidth(80)
        self.auto_send_interval_edit.setValidator(QIntValidator(100, 60000))
        options1_layout.addWidget(self.auto_send_interval_edit)
        
        options1_layout.addStretch()
        layout.addLayout(options1_layout)
        
        # 第二行选项
        options2_layout = QHBoxLayout()
        
        # 发送格式
        format_group = QGroupBox("发送格式")
        format_layout = QHBoxLayout()
        
        self.format_buttons = {
            'raw': QPushButton("原始"),
            'crlf': QPushButton("+CRLF"),
            'lf': QPushButton("+LF"),
            'cr': QPushButton("+CR")
        }
        
        for name, btn in self.format_buttons.items():
            btn.setCheckable(True)
            btn.setMaximumWidth(60)
            format_layout.addWidget(btn)
        
        self.format_buttons['raw'].setChecked(True)
        format_group.setLayout(format_layout)
        options2_layout.addWidget(format_group)
        
        options2_layout.addStretch()
        
        # 操作按钮
        clear_send_btn = QPushButton("清空")
        clear_send_btn.clicked.connect(self.clear_send_area)
        options2_layout.addWidget(clear_send_btn)
        
        self.send_button = QPushButton("发送")
        self.send_button.setStyleSheet(self._get_send_button_style())
        self.send_button.clicked.connect(self._on_send_clicked)
        options2_layout.addWidget(self.send_button)
        
        layout.addLayout(options2_layout)
        return layout
    
    def _create_advanced_tab(self) -> QWidget:
        """创建高级功能选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 数据过滤器
        filter_group = QGroupBox("数据过滤器")
        filter_layout = QVBoxLayout()
        
        self.filter_enabled_checkbox = QCheckBox("启用数据过滤")
        filter_layout.addWidget(self.filter_enabled_checkbox)
        
        filter_options_layout = QHBoxLayout()
        filter_options_layout.addWidget(QLabel("过滤规则:"))
        self.filter_rule_edit = QLineEdit()
        self.filter_rule_edit.setPlaceholderText("正则表达式或关键字")
        filter_options_layout.addWidget(self.filter_rule_edit)
        
        self.filter_mode_combo = QComboBox()
        self.filter_mode_combo.addItems(["包含", "排除", "正则匹配"])
        filter_options_layout.addWidget(self.filter_mode_combo)
        
        filter_layout.addLayout(filter_options_layout)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # 数据转换器
        converter_group = QGroupBox("数据转换器")
        converter_layout = QVBoxLayout()
        
        converter_options_layout = QHBoxLayout()
        converter_options_layout.addWidget(QLabel("输入格式:"))
        self.input_format_combo = QComboBox()
        self.input_format_combo.addItems(["Hex", "ASCII", "UTF-8", "Base64"])
        converter_options_layout.addWidget(self.input_format_combo)
        
        converter_options_layout.addWidget(QLabel("输出格式:"))
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["Hex", "ASCII", "UTF-8", "Base64", "Binary"])
        converter_options_layout.addWidget(self.output_format_combo)
        
        convert_btn = QPushButton("转换")
        convert_btn.clicked.connect(self._convert_data)
        converter_options_layout.addWidget(convert_btn)
        
        converter_layout.addLayout(converter_options_layout)
        
        self.converter_input_edit = QPlainTextEdit()
        self.converter_input_edit.setPlaceholderText("输入要转换的数据")
        self.converter_input_edit.setMaximumHeight(60)  # 减少高度
        converter_layout.addWidget(self.converter_input_edit)
        
        self.converter_output_edit = QPlainTextEdit()
        self.converter_output_edit.setPlaceholderText("转换结果")
        self.converter_output_edit.setReadOnly(True)
        self.converter_output_edit.setMaximumHeight(60)  # 减少高度
        converter_layout.addWidget(self.converter_output_edit)
        
        converter_group.setLayout(converter_layout)
        layout.addWidget(converter_group)
        
        layout.addStretch()
        return widget
    
    def _create_stats_tab(self) -> QWidget:
        """创建统计信息选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 详细统计信息
        stats_group = QGroupBox("详细统计")
        stats_layout = QGridLayout()
        
        # 统计标签
        stats_items = [
            ("总接收包数:", "detailed_rx_count"),
            ("总接收字节:", "detailed_rx_bytes"),
            ("平均接收速率:", "avg_rx_rate"),
            ("总发送包数:", "detailed_tx_count"),
            ("总发送字节:", "detailed_tx_bytes"),
            ("平均发送速率:", "avg_tx_rate"),
            ("连接时长:", "connection_time"),
            ("错误计数:", "error_count")
        ]
        
        for i, (label_text, key) in enumerate(stats_items):
            row, col = i // 2, (i % 2) * 2
            stats_layout.addWidget(QLabel(label_text), row, col)
            self.stats_labels[key] = QLabel("0")
            stats_layout.addWidget(self.stats_labels[key], row, col + 1)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # 操作按钮
        buttons_layout = QHBoxLayout()
        
        reset_stats_btn = QPushButton("重置统计")
        reset_stats_btn.clicked.connect(self._reset_stats)
        buttons_layout.addWidget(reset_stats_btn)
        
        export_stats_btn = QPushButton("导出统计")
        export_stats_btn.clicked.connect(self._export_stats)
        buttons_layout.addWidget(export_stats_btn)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        layout.addStretch()
        return widget
    
    def _init_connections(self):
        """初始化信号连接"""
        # 复选框连接
        self.send_hex_checkbox.toggled.connect(self._on_hex_mode_toggled)
        self.terminal_mode_checkbox.toggled.connect(self._on_terminal_mode_toggled)
        self.auto_send_checkbox.toggled.connect(self._on_auto_send_toggled)
        self.recv_auto_scroll_checkbox.toggled.connect(self._on_auto_scroll_toggled)
        self.recv_word_wrap_checkbox.toggled.connect(self._on_word_wrap_toggled)
        
        # 发送格式按钮连接
        for name, btn in self.format_buttons.items():
            btn.clicked.connect(lambda checked, fmt=name: self._set_send_format(fmt))
        
        # 文本框事件
        if self.send_text_edit:
            self.send_text_edit.keyPressEvent = self._on_send_text_key_press
    
    def _init_timers(self):
        """初始化定时器"""
        # 自动发送定时器
        self.auto_send_timer.timeout.connect(self._auto_send_timeout)
        
        # 统计更新定时器
        self.stats_timer.timeout.connect(self._update_stats_display)
        self.stats_timer.start(1000)  # 每秒更新
        
        # 速率计算定时器
        self.rate_calc_timer.timeout.connect(self._calculate_rates)
        self.rate_calc_timer.start(1000)  # 每秒计算速率
    
    def _load_settings(self):
        """加载设置"""
        # 加载界面设置
        self.recv_hex_checkbox.setChecked(
            self.settings.value("recv_hex_display", True, bool)
        )
        self.recv_timestamp_checkbox.setChecked(
            self.settings.value("recv_timestamp_display", False, bool)
        )
        self.send_hex_checkbox.setChecked(
            self.settings.value("send_hex_checked", True, bool)
        )
        
        # 加载快捷发送项
        quick_send_data = self.settings.value("quick_send_items", "")
        if quick_send_data:
            try:
                items_data = json.loads(quick_send_data)
                self.quick_send_items = []
                for item_data in items_data:
                    item = QuickSendItem(
                        name=item_data.get('name', '未命名'),
                        data=item_data.get('data', ''),
                        is_hex=item_data.get('is_hex', False),
                        description=item_data.get('description', ''),
                        hotkey=item_data.get('hotkey', ''),
                        category=item_data.get('category', '默认')
                    )
                    self.quick_send_items.append(item)
            except (json.JSONDecodeError, TypeError):
                pass  # 使用默认值
    
    def _save_settings(self):
        """保存设置"""
        self.settings.setValue("recv_hex_display", self.recv_hex_checkbox.isChecked())
        self.settings.setValue("recv_timestamp_display", self.recv_timestamp_checkbox.isChecked())
        self.settings.setValue("send_hex_checked", self.send_hex_checkbox.isChecked())
        
        # 保存快捷发送项
        items_data = [
            {
                "name": item.name,
                "data": item.data,
                "is_hex": item.is_hex,
                "description": item.description,
                "hotkey": getattr(item, 'hotkey', ''),
                "category": getattr(item, 'category', '默认')
            }
            for item in self.quick_send_items
        ]
        self.settings.setValue("quick_send_items", json.dumps(items_data))
    
    # 样式方法
    def _get_monospace_font(self) -> QFont:
        """获取等宽字体"""
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        return font
    
    def _get_receive_text_style(self) -> str:
        """获取接收文本框样式"""
        return """
            QTextEdit {
                background-color: #1E1E1E;
                color: #00FF00;
                border: 1px solid #3F3F3F;
                selection-background-color: #264F78;
            }
        """
    
    def _get_send_text_style(self) -> str:
        """获取发送文本框样式"""
        return """
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #3F3F3F;
                selection-background-color: #264F78;
            }
        """
    
    def _get_send_button_style(self) -> str:
        """获取发送按钮样式"""
        return """
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #AAAAAA;
            }
        """
    
    # 事件处理方法
    @Slot(bool)
    def _on_hex_mode_toggled(self, checked: bool):
        """Hex模式切换"""
        if self.send_text_edit:
            if checked:
                self.send_text_edit.setPlaceholderText(
                    "输入Hex数据 (如: AB CD EF 或 ABCDEF)\n" +
                    "支持空格、冒号、短横线分隔"
                )
            else:
                self.send_text_edit.setPlaceholderText(
                    "输入要发送的文本\n" +
                    "支持多行文本和特殊字符"
                )
    
    @Slot(bool)
    def _on_terminal_mode_toggled(self, checked: bool):
        """终端模式切换"""
        if not self.send_text_edit:
            return
            
        if checked:
            self.send_text_edit.setMaximumHeight(200)
            self.send_text_edit.setPlaceholderText(
                "终端模式 - 输入命令后按Enter发送\n" +
                "上下箭头浏览历史命令\n" +
                "支持命令历史和自动补全"
            )
            self.send_text_edit.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #0C0C0C;
                    color: #00FF00;
                    font-family: 'Consolas', 'Courier New', monospace;
                    border: 1px solid #3F3F3F;
                }
            """)
            # 添加终端提示符
            if not self.send_text_edit.toPlainText().startswith("> "):
                self.send_text_edit.setPlainText("> ")
        else:
            self.send_text_edit.setMaximumHeight(120)
            self.send_text_edit.setStyleSheet(self._get_send_text_style())
            self._on_hex_mode_toggled(self.send_hex_checkbox.isChecked())
    
    def _on_send_text_key_press(self, event):
        """发送文本框按键事件"""
        # Ctrl+Enter 快速发送
        if ((event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter) 
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            self._on_send_clicked()
            event.accept()
            return
        
        if not self.terminal_mode_checkbox.isChecked():
            # 非终端模式，保持原有行为
            QPlainTextEdit.keyPressEvent(self.send_text_edit, event)
            return
        
        # 终端模式特殊处理
        self._handle_terminal_key_press(event)
    
    def _handle_terminal_key_press(self, event):
        """处理终端模式按键"""
        if event.key() == Qt.Key.Key_Up:
            # 上箭头 - 浏览历史命令
            if self.command_history and self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                self.send_text_edit.setPlainText("> " + self.command_history[self.history_index])
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            # 下箭头 - 浏览历史命令
            if self.history_index > 0:
                self.history_index -= 1
                self.send_text_edit.setPlainText("> " + self.command_history[self.history_index])
            elif self.history_index == 0:
                self.history_index = -1
                self.send_text_edit.setPlainText("> ")
            event.accept()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Enter键 - 发送当前文本
            current_text = self.send_text_edit.toPlainText()
            if current_text.startswith("> "):
                current_text = current_text[2:]  # 移除提示符
            
            if current_text.strip():  # 只有非空命令才发送
                self.send_text_edit.setPlainText(current_text)
                self._on_send_clicked()
                
                # 添加到命令历史
                if current_text not in self.command_history:
                    self.command_history.insert(0, current_text)
                    if len(self.command_history) > self.max_history_size:
                        self.command_history.pop()
                self.history_index = -1
            
            # 发送后添加新的提示符
            self.send_text_edit.setPlainText("> ")
            event.accept()
        else:
            # 其他按键保持默认行为，但确保提示符存在
            current_text = self.send_text_edit.toPlainText()
            if not current_text.startswith("> "):
                self.send_text_edit.setPlainText("> " + current_text)
            QPlainTextEdit.keyPressEvent(self.send_text_edit, event)
    
    @Slot()
    def _on_send_clicked(self):
        """发送按钮点击事件"""
        if not self._validate_send_conditions():
            return
        
        text_to_send = self._get_send_text()
        if not text_to_send:
            QMessageBox.information(self, "提示", "请输入要发送的数据。")
            return
        
        is_hex = self.send_hex_checkbox.isChecked()
        
        # 验证Hex格式
        if is_hex and not self._validate_hex_input(text_to_send):
            QMessageBox.warning(self, "输入错误", 
                              "Hex数据格式不正确。\n" +
                              "请输入有效的十六进制数据，如: AB CD EF 或 ABCDEF")
            return
        
        # 应用发送格式
        formatted_text = self._apply_send_format(text_to_send)
        
        # 更新统计
        byte_count = self._calculate_byte_count(formatted_text, is_hex)
        self._update_tx_stats(byte_count)
        
        # 发送数据
        self.send_data_requested.emit(formatted_text, is_hex)
        
        # 清空输入框（根据模式）
        if not self.auto_send_checkbox.isChecked():
            self._clear_send_input()
    
    def _validate_send_conditions(self) -> bool:
        """验证发送条件"""
        if not hasattr(self.main_window_ref, 'serial_manager'):
            QMessageBox.warning(self, "错误", "串口管理器未初始化。")
            return False
        
        if not self.main_window_ref.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "串口未打开，请先打开串口连接。")
            return False
        
        return True
    
    def _get_send_text(self) -> str:
        """获取要发送的文本"""
        if not self.send_text_edit:
            return ""
        
        text = self.send_text_edit.toPlainText().strip()
        
        # 终端模式下移除提示符
        if self.terminal_mode_checkbox.isChecked() and text.startswith("> "):
            text = text[2:]
        
        return text
    
    def _validate_hex_input(self, text: str) -> bool:
        """验证Hex输入格式"""
        if not text:
            return False
        
        # 移除分隔符
        hex_text = re.sub(r'[\s\-:,]', '', text.upper())
        
        # 检查是否为有效的十六进制字符
        if not re.match(r'^[0-9A-F]*$', hex_text):
            return False
        
        # 检查长度是否为偶数
        return len(hex_text) % 2 == 0 and len(hex_text) > 0
    
    def _apply_send_format(self, text: str) -> str:
        """应用发送格式"""
        for name, btn in self.format_buttons.items():
            if btn.isChecked():
                if name == 'crlf':
                    return text + '\r\n'
                elif name == 'lf':
                    return text + '\n'
                elif name == 'cr':
                    return text + '\r'
        return text  # raw format
    
    def _calculate_byte_count(self, text: str, is_hex: bool) -> int:
        """计算字节数"""
        if is_hex:
            hex_data = re.sub(r'[\s\-:,]', '', text.upper())
            return len(hex_data) // 2
        else:
            return len(text.encode('utf-8'))
    
    def _clear_send_input(self):
        """清空发送输入框"""
        if not self.send_text_edit:
            return
        
        if self.terminal_mode_checkbox.isChecked():
            self.send_text_edit.setPlainText("> ")
        else:
            self.send_text_edit.clear()
    
    @Slot(bool)
    def _on_auto_send_toggled(self, checked: bool):
        """自动发送切换"""
        if checked:
            if not self._validate_send_conditions():
                self.auto_send_checkbox.setChecked(False)
                return
            
            try:
                interval = int(self.auto_send_interval_edit.text())
                if interval < 100:
                    interval = 100
                    self.auto_send_interval_edit.setText("100")
                self.auto_send_timer.start(interval)
            except ValueError:
                self.auto_send_checkbox.setChecked(False)
                QMessageBox.warning(self, "错误", "无效的发送间隔时间")
        else:
            self.auto_send_timer.stop()
    
    @Slot(bool)
    def _on_auto_scroll_toggled(self, checked: bool):
        """自动滚动切换"""
        # 自动滚动在append_receive_text中实现
        pass
    
    @Slot(bool)
    def _on_word_wrap_toggled(self, checked: bool):
        """自动换行切换"""
        if self.receive_text_edit:
            if checked:
                self.receive_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            else:
                self.receive_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    
    def _set_send_format(self, format_type: str):
        """设置发送格式"""
        # 重置所有按钮
        for btn in self.format_buttons.values():
            btn.setChecked(False)
        
        # 设置选中的按钮
        if format_type in self.format_buttons:
            self.format_buttons[format_type].setChecked(True)
    
    def _auto_send_timeout(self):
        """自动发送超时"""
        if self.auto_send_checkbox.isChecked():
            # 检查连接状态
            if not self._validate_send_conditions():
                self.auto_send_checkbox.setChecked(False)
                self.auto_send_timer.stop()
                return
            self._on_send_clicked()
    
    def _quick_send_by_index(self, index: int):
        """根据索引快捷发送"""
        if 0 <= index < len(self.quick_send_items):
            item = self.quick_send_items[index]
            self._quick_send(item.data, item.is_hex)
    
    def _quick_send(self, data: str, is_hex: bool):
        """快捷发送"""
        if not self._validate_send_conditions():
            return
        
        byte_count = self._calculate_byte_count(data, is_hex)
        self._update_tx_stats(byte_count)
        self.send_data_requested.emit(data, is_hex)
    
    def _edit_quick_send(self):
        """编辑快捷发送"""
        if QuickSendEditorDialog is None:
            QMessageBox.warning(self, "错误", "快捷发送编辑对话框未找到")
            return
        
        # 转换数据格式
        dialog_items = []
        for item in self.quick_send_items:
            dialog_item = DialogQuickSendItem(
                name=item.name,
                data=item.data,
                is_hex=item.is_hex,
                description=item.description,
                hotkey=getattr(item, 'hotkey', ''),
                category=getattr(item, 'category', '默认')
            )
            dialog_items.append(dialog_item)
        
        dialog = QuickSendEditorDialog(dialog_items, self)
        dialog.items_changed.connect(self._on_quick_send_items_changed)
        
        if dialog.exec() == QuickSendEditorDialog.DialogCode.Accepted:
            # 转换回本地格式
            new_items = []
            for dialog_item in dialog.get_items():
                item = QuickSendItem(
                    name=dialog_item.name,
                    data=dialog_item.data,
                    is_hex=dialog_item.is_hex,
                    description=dialog_item.description,
                    hotkey=dialog_item.hotkey,
                    category=dialog_item.category
                )
                new_items.append(item)
            
            self.quick_send_items = new_items
            self._create_quick_send_buttons()
            self._save_settings()
    
    def _on_quick_send_items_changed(self, dialog_items):
        """快捷发送项目改变事件"""
        # 转换回本地格式
        new_items = []
        for dialog_item in dialog_items:
            item = QuickSendItem(
                name=dialog_item.name,
                data=dialog_item.data,
                is_hex=dialog_item.is_hex,
                description=dialog_item.description,
                hotkey=dialog_item.hotkey,
                category=dialog_item.category
            )
            new_items.append(item)
        
        self.quick_send_items = new_items
        self._create_quick_send_buttons()
    
    def _save_receive_data(self):
        """保存接收数据"""
        if not self.receive_text_edit or not self.receive_text_edit.toPlainText():
            QMessageBox.information(self, "提示", "没有数据可保存")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存接收数据", 
            f"receive_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.receive_text_edit.toPlainText())
                QMessageBox.information(self, "成功", f"数据已保存到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def _convert_data(self):
        """数据转换"""
        input_text = self.converter_input_edit.toPlainText().strip()
        if not input_text:
            QMessageBox.information(self, "提示", "请输入要转换的数据")
            return
        
        input_format = self.input_format_combo.currentText()
        output_format = self.output_format_combo.currentText()
        
        try:
            # 简单的数据转换实现
            if input_format == "Hex" and output_format == "ASCII":
                hex_data = re.sub(r'[\s\-:,]', '', input_text)
                bytes_data = bytes.fromhex(hex_data)
                result = bytes_data.decode('ascii', errors='replace')
            elif input_format == "ASCII" and output_format == "Hex":
                bytes_data = input_text.encode('ascii')
                result = ' '.join(f'{b:02X}' for b in bytes_data)
            else:
                result = "暂不支持此转换格式"
            
            self.converter_output_edit.setPlainText(result)
        except Exception as e:
            QMessageBox.warning(self, "转换错误", f"数据转换失败: {str(e)}")
    
    def _update_stats_display(self):
        """更新统计显示"""
        # 基础统计
        self.stats_labels['rx_count'].setText(f"接收: {self.stats.rx_count} 包")
        self.stats_labels['rx_bytes'].setText(f"字节: {self.stats.rx_bytes}")
        self.stats_labels['rx_rate'].setText(f"速率: {self.stats.rx_rate:.1f} B/s")
        
        self.stats_labels['tx_count'].setText(f"发送: {self.stats.tx_count} 包")
        self.stats_labels['tx_bytes'].setText(f"字节: {self.stats.tx_bytes}")
        self.stats_labels['tx_rate'].setText(f"速率: {self.stats.tx_rate:.1f} B/s")
        
        # 详细统计（如果存在）
        if 'detailed_rx_count' in self.stats_labels:
            self.stats_labels['detailed_rx_count'].setText(str(self.stats.rx_count))
            self.stats_labels['detailed_rx_bytes'].setText(str(self.stats.rx_bytes))
            self.stats_labels['detailed_tx_count'].setText(str(self.stats.tx_count))
            self.stats_labels['detailed_tx_bytes'].setText(str(self.stats.tx_bytes))
    
    def _calculate_rates(self):
        """计算传输速率"""
        # 简单的速率计算，可以改进为更精确的滑动窗口算法
        current_time = datetime.now()
        
        if hasattr(self, '_last_rate_calc_time'):
            time_diff = (current_time - self._last_rate_calc_time).total_seconds()
            if time_diff > 0:
                rx_diff = self.stats.rx_bytes - getattr(self, '_last_rx_bytes', 0)
                tx_diff = self.stats.tx_bytes - getattr(self, '_last_tx_bytes', 0)
                
                self.stats.rx_rate = rx_diff / time_diff
                self.stats.tx_rate = tx_diff / time_diff
        
        self._last_rate_calc_time = current_time
        self._last_rx_bytes = self.stats.rx_bytes
        self._last_tx_bytes = self.stats.tx_bytes
    
    def _update_tx_stats(self, byte_count: int):
        """更新发送统计"""
        self.stats.tx_count += 1
        self.stats.tx_bytes += byte_count
        self.stats.last_tx_time = datetime.now()
        self.stats_updated.emit(self.stats)
    
    def _update_rx_stats(self, byte_count: int):
        """更新接收统计"""
        self.stats.rx_count += 1
        self.stats.rx_bytes += byte_count
        self.stats.last_rx_time = datetime.now()
        self.stats_updated.emit(self.stats)
    
    def _reset_stats(self):
        """重置统计"""
        self.stats = CommStats()
        self._update_stats_display()
    
    def _export_stats(self):
        """导出统计"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出统计数据",
            f"comm_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if file_path:
            try:
                stats_data = {
                    'tx_count': self.stats.tx_count,
                    'rx_count': self.stats.rx_count,
                    'tx_bytes': self.stats.tx_bytes,
                    'rx_bytes': self.stats.rx_bytes,
                    'tx_rate': self.stats.tx_rate,
                    'rx_rate': self.stats.rx_rate,
                    'export_time': datetime.now().isoformat()
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(stats_data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "成功", f"统计数据已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    # 公共接口方法
    def append_receive_text(self, text):
        """添加接收文本"""
        if not self.receive_text_edit:
            return
        
        # 处理bytes类型输入
        if isinstance(text, bytes):
            try:
                display_text = text.decode('utf-8', errors='replace')
                byte_count = len(text)
            except Exception:
                display_text = str(text)
                byte_count = len(text)
        else:
            display_text = str(text)
            byte_count = len(text.encode('utf-8'))
        
        cursor = self.receive_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.receive_text_edit.setTextCursor(cursor)
        self.receive_text_edit.insertPlainText(display_text)
        
        # 自动滚动
        if self.recv_auto_scroll_checkbox.isChecked():
            self.receive_text_edit.ensureCursorVisible()
        
        # 更新接收统计
        self._update_rx_stats(byte_count)
    
    def clear_receive_area(self):
        """清空接收区域"""
        if self.receive_text_edit:
            self.receive_text_edit.clear()
    
    def clear_send_area(self):
        """清空发送区域"""
        self._clear_send_input()
    
    def set_send_enabled(self, enabled: bool):
        """设置发送功能启用状态"""
        self.send_button.setEnabled(enabled)
        if self.send_text_edit:
            self.send_text_edit.setEnabled(enabled)
        self.send_hex_checkbox.setEnabled(enabled)
        
        # 如果禁用且正在自动发送，停止自动发送
        if not enabled and self.auto_send_checkbox.isChecked():
            self.auto_send_checkbox.setChecked(False)
            self.auto_send_timer.stop()
    
    def on_serial_connection_changed(self, connected: bool):
        """串口连接状态改变"""
        self.set_send_enabled(connected)
        
        if not connected:
            # 连接断开时重置一些状态
            if self.auto_send_checkbox.isChecked():
                self.auto_send_checkbox.setChecked(False)
                self.auto_send_timer.stop()
    
    def get_config(self) -> Dict:
        """获取配置"""
        return {
            "recv_hex_display": self.recv_hex_checkbox.isChecked(),
            "recv_timestamp_display": self.recv_timestamp_checkbox.isChecked(),
            "recv_auto_scroll": self.recv_auto_scroll_checkbox.isChecked(),
            "recv_word_wrap": self.recv_word_wrap_checkbox.isChecked(),
            "send_hex_checked": self.send_hex_checkbox.isChecked(),
            "terminal_mode": self.terminal_mode_checkbox.isChecked(),
            "auto_send_interval": self.auto_send_interval_edit.text(),
            "quick_send_items": [
                {
                    "name": item.name,
                    "data": item.data,
                    "is_hex": item.is_hex,
                    "description": item.description
                }
                for item in self.quick_send_items
            ]
        }
    
    def apply_config(self, config: Dict):
        """应用配置"""
        self.recv_hex_checkbox.setChecked(config.get("recv_hex_display", True))
        self.recv_timestamp_checkbox.setChecked(config.get("recv_timestamp_display", False))
        self.recv_auto_scroll_checkbox.setChecked(config.get("recv_auto_scroll", True))
        self.recv_word_wrap_checkbox.setChecked(config.get("recv_word_wrap", False))
        self.send_hex_checkbox.setChecked(config.get("send_hex_checked", True))
        self.terminal_mode_checkbox.setChecked(config.get("terminal_mode", False))
        self.auto_send_interval_edit.setText(config.get("auto_send_interval", "1000"))
        
        # 应用快捷发送项配置
        quick_send_items = config.get("quick_send_items", [])
        if quick_send_items:
            self.quick_send_items = [
                QuickSendItem(**item) for item in quick_send_items
            ]
        
        # 触发相关事件
        self._on_hex_mode_toggled(self.send_hex_checkbox.isChecked())
        self._on_terminal_mode_toggled(self.terminal_mode_checkbox.isChecked())
        self._on_word_wrap_toggled(self.recv_word_wrap_checkbox.isChecked())
    
    def closeEvent(self, event):
        """关闭事件"""
        self._save_settings()
        super().closeEvent(event)
    
    # 兼容性方法（保持与原有接口的兼容性）
    def recv_hex_checkbox_is_checked(self) -> bool:
        """接收Hex显示是否选中"""
        return self.recv_hex_checkbox.isChecked()
    
    def recv_timestamp_checkbox_is_checked(self) -> bool:
        """接收时间戳显示是否选中"""
        return self.recv_timestamp_checkbox.isChecked()
    
    def get_send_text(self) -> str:
        """获取发送文本"""
        return self._get_send_text()
    
    def set_send_text(self, text: str):
        """设置发送文本"""
        if self.send_text_edit:
            if self.terminal_mode_checkbox.isChecked():
                self.send_text_edit.setPlainText("> " + text)
            else:
                self.send_text_edit.setPlainText(text)
    
    def update_rx_stats(self, byte_count: int):
        """更新接收统计（兼容性方法）"""
        self._update_rx_stats(byte_count)
    
    def update_tx_stats(self, byte_count: int):
        """更新发送统计（兼容性方法）"""
        self._update_tx_stats(byte_count)