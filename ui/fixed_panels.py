import re
from typing import Optional, Dict, TYPE_CHECKING  # Added Set

from PySide6.QtCore import Slot, Qt, Signal, QRegularExpression, QTimer
from PySide6.QtGui import QTextCursor, QIntValidator, QFont, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QMessageBox, QGroupBox, QPlainTextEdit, QFileDialog,
    QSplitter,
    # For Plugin Management Dialog
)

if TYPE_CHECKING:
    from main import SerialDebugger  # Forward reference for type hinting
# Core imports from your project structure

try:
    import pyqtgraph as pg  # type: ignore

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    pg = None
    PYQTGRAPH_AVAILABLE = False
    print("警告：pyqtgraph 未安装，波形图功能将不可用。请运行 'pip install pyqtgraph'")

from utils.constants import Constants, ChecksumMode
from utils.data_models import SerialPortConfig, FrameConfig


# Updated Plugin Architecture Imports


class SerialConfigDefinitionPanelWidget(QWidget):  # Full implementation
    connect_button_toggled = Signal(bool)
    refresh_ports_requested = Signal()
    config_changed = Signal()

    def __init__(self, parent_main_window: 'SerialDebugger', parent: QWidget = None):
        super().__init__(parent)
        self.main_window_ref = parent_main_window
        self.port_combo = QComboBox()
        self.baud_combo = QComboBox()
        self.data_bits_combo = QComboBox()
        self.parity_combo = QComboBox()
        self.stop_bits_combo = QComboBox()
        self.refresh_ports_button = QPushButton("刷新")
        self.connect_button = QPushButton("打开串口")
        self.head_edit = QLineEdit()
        self.saddr_edit = QLineEdit()
        self.daddr_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.sum_check_display = QLineEdit()
        self.add_check_display = QLineEdit()
        self.checksum_mode_combo = QComboBox()
        self._init_ui()

    def _init_ui(self):
        main_panel_layout = QVBoxLayout(self)
        config_group = QGroupBox("串口配置")
        config_layout = QGridLayout()
        config_layout.addWidget(QLabel("端口:"), 0, 0)
        self.port_combo.currentTextChanged.connect(self._emit_config_changed_if_valid_port)
        config_layout.addWidget(self.port_combo, 0, 1)
        config_layout.addWidget(QLabel("波特率:"), 1, 0)
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.baud_combo.setEditable(True)
        if self.baud_combo.lineEdit(): self.baud_combo.lineEdit().setValidator(QIntValidator(0, 4000000, self))
        self.baud_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.baud_combo, 1, 1)
        config_layout.addWidget(QLabel("数据位:"), 2, 0)
        self.data_bits_combo.addItems(["8", "7", "6", "5"])
        self.data_bits_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.data_bits_combo, 2, 1)
        config_layout.addWidget(QLabel("校验位:"), 3, 0)
        self.parity_combo.addItems(["None", "Even", "Odd", "Space", "Mark"])
        self.parity_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.parity_combo, 3, 1)
        config_layout.addWidget(QLabel("停止位:"), 4, 0)
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.stop_bits_combo, 4, 1)
        self.refresh_ports_button.clicked.connect(self.refresh_ports_requested.emit)
        config_layout.addWidget(self.refresh_ports_button, 5, 0)
        self.connect_button.setCheckable(True)
        # self.connect_button.toggled.connect(self.connect_button_toggled.emit())
        self.connect_button.clicked.connect(self._handle_internal_connect_button_click)  # <--- 新的连接方式

        config_layout.addWidget(self.connect_button, 5, 1)
        config_layout.setColumnStretch(1, 1)
        config_group.setLayout(config_layout)
        main_panel_layout.addWidget(config_group)
        frame_def_group = QGroupBox("全局帧结构定义 (发送用)")
        frame_def_layout = QGridLayout()
        frame_def_layout.addWidget(QLabel("帧头(H)[Hex,1B]:"), 0, 0)
        self.head_edit.setPlaceholderText("AA")
        # 添加Hex输入验证器，只允许1字节（2个Hex字符）
        hex_validator = QRegularExpressionValidator(QRegularExpression("[0-9a-fA-F]{1,2}"), self)
        self.head_edit.setValidator(hex_validator)
        self.head_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.head_edit, 0, 1)
        frame_def_layout.addWidget(QLabel("源地址(S)[Hex,1B]:"), 1, 0)
        self.saddr_edit.setPlaceholderText("01")
        self.saddr_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.saddr_edit, 1, 1)
        frame_def_layout.addWidget(QLabel("目标地址(D)[Hex,1B]:"), 2, 0)
        self.daddr_edit.setPlaceholderText("FE")
        self.daddr_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.daddr_edit, 2, 1)
        frame_def_layout.addWidget(QLabel("默认发送功能码(ID):"), 3, 0)
        self.id_edit.setPlaceholderText("面板可覆盖, e.g., C0")
        self.id_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.id_edit, 3, 1)
        frame_def_layout.addWidget(QLabel("最后帧校验1/CRC高:"), 4, 0)
        self.sum_check_display.setPlaceholderText("自动")
        self.sum_check_display.setReadOnly(True)
        frame_def_layout.addWidget(self.sum_check_display, 4, 1)
        frame_def_layout.addWidget(QLabel("最后帧校验2/CRC低:"), 5, 0)
        self.add_check_display.setPlaceholderText("自动")
        self.add_check_display.setReadOnly(True)
        frame_def_layout.addWidget(self.add_check_display, 5, 1)
        frame_def_layout.addWidget(QLabel("校验模式:"), 6, 0)
        self.checksum_mode_combo.addItem("原始校验 (Sum/Add)", ChecksumMode.ORIGINAL_SUM_ADD)
        self.checksum_mode_combo.addItem("CRC-16/CCITT-FALSE", ChecksumMode.CRC16_CCITT_FALSE)
        self.checksum_mode_combo.currentIndexChanged.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.checksum_mode_combo, 6, 1)
        frame_def_layout.setColumnStretch(1, 1)
        frame_def_group.setLayout(frame_def_layout)
        main_panel_layout.addWidget(frame_def_group)
        main_panel_layout.addStretch(1)
        self.setLayout(main_panel_layout)

    def _emit_config_changed(self):
        self.config_changed.emit()

    def _emit_config_changed_if_valid_port(self, port_text: str):
        if port_text != "无可用端口": self.config_changed.emit()

    def update_ui_from_main_configs(self, serial_cfg: SerialPortConfig, frame_cfg: FrameConfig,
                                    active_checksum: ChecksumMode):
        widgets_to_block = [self.port_combo, self.baud_combo, self.data_bits_combo, self.parity_combo,
                            self.stop_bits_combo, self.head_edit, self.saddr_edit, self.daddr_edit, self.id_edit,
                            self.checksum_mode_combo]
        for widget in widgets_to_block: widget.blockSignals(True)
        if serial_cfg.port_name:
            idx = self.port_combo.findData(serial_cfg.port_name)
            if idx != -1:
                self.port_combo.setCurrentIndex(idx)
            else:
                idx_text = self.port_combo.findText(serial_cfg.port_name, Qt.MatchFlag.MatchFixedString)
            if idx_text != -1:
                self.port_combo.setCurrentIndex(idx_text)
            elif self.port_combo.count() > 0 and self.port_combo.itemText(0) != "无可用端口":
                self.port_combo.setCurrentIndex(0)
        baud_rate_str = str(serial_cfg.baud_rate)
        if self.baud_combo.findText(baud_rate_str) == -1: self.baud_combo.addItem(baud_rate_str)
        self.baud_combo.setCurrentText(baud_rate_str)
        self.data_bits_combo.setCurrentText(str(serial_cfg.data_bits))
        self.parity_combo.setCurrentText(serial_cfg.parity)
        self.stop_bits_combo.setCurrentText(str(serial_cfg.stop_bits))
        self.head_edit.setText(frame_cfg.head)
        self.saddr_edit.setText(frame_cfg.s_addr)
        self.daddr_edit.setText(frame_cfg.d_addr)
        self.id_edit.setText(frame_cfg.func_id)

        idx_cs = self.checksum_mode_combo.findData(active_checksum)
        if idx_cs != -1:
            self.checksum_mode_combo.setCurrentIndex(idx_cs)
        else:
            idx_def = -1  # Initialize idx_def
            found_default_idx = self.checksum_mode_combo.findData(Constants.DEFAULT_CHECKSUM_MODE)
            if found_default_idx != -1:
                idx_def = found_default_idx

            if idx_def != -1:
                self.checksum_mode_combo.setCurrentIndex(idx_def)
            # If default is also not found, combo box remains as is.

        for widget in widgets_to_block: widget.blockSignals(False)

    def get_serial_config_from_ui(self) -> SerialPortConfig:
        port_name = None
        port_name_text = self.port_combo.currentText()
        if port_name_text != "无可用端口":
            port_name_data = self.port_combo.currentData()
            port_name = port_name_data if port_name_data is not None else None
            if not port_name: port_name_text_parts = port_name_text.split(" "); port_name = port_name_text_parts[
                0] if port_name_text_parts else None
        try:
            baud_rate = int(self.baud_combo.currentText())
        except ValueError:
            baud_rate = Constants.DEFAULT_BAUD_RATE
            if hasattr(self.main_window_ref, 'error_logger') and self.main_window_ref.error_logger:
                self.main_window_ref.error_logger.log_warning(
                    f"无效的波特率输入: '{self.baud_combo.currentText()}', 使用默认值 {baud_rate}")
            self.baud_combo.setCurrentText(str(baud_rate))
        data_bits = int(self.data_bits_combo.currentText())
        parity = self.parity_combo.currentText()
        stop_bits_str = self.stop_bits_combo.currentText()
        try:
            stop_bits = float(stop_bits_str) if stop_bits_str == "1.5" else int(stop_bits_str)
        except ValueError:
            stop_bits = 1
            if hasattr(self.main_window_ref, 'error_logger') and self.main_window_ref.error_logger:
                self.main_window_ref.error_logger.log_warning(
                    f"无效的停止位输入: '{stop_bits_str}'，使用默认值 1")
        return SerialPortConfig(port_name, baud_rate, data_bits, parity, stop_bits)

    def get_frame_config_from_ui(self) -> FrameConfig:
        raw_head = self.head_edit.text().strip().upper()
        # 确保帧头是长度为2的Hex字符串
        processed_head = ""
        if len(raw_head) == 2 and re.match(r'^[0-9A-F]{2}$', raw_head):
            processed_head = raw_head
        elif len(raw_head) == 1 and re.match(r'^[0-9A-F]{1}$', raw_head):
             processed_head = '0' + raw_head # 补齐一个字符的情况
        else:
             # 如果不符合预期，使用默认值或空字符串，取决于FrameConfig的默认行为
             processed_head = Constants.DEFAULT_FRAME_HEAD # 或者 ""

        return FrameConfig(head=processed_head, s_addr=self.saddr_edit.text().strip(),
                           d_addr=self.daddr_edit.text().strip(), func_id=self.id_edit.text().strip())

    def get_checksum_mode_from_ui(self) -> ChecksumMode:
        mode = self.checksum_mode_combo.currentData()
        if isinstance(mode, ChecksumMode):
            return mode
        return Constants.DEFAULT_CHECKSUM_MODE

    def update_port_combo_display(self, available_ports: list[dict], current_port_name: Optional[str]):
        if self.main_window_ref.error_logger:
            self.main_window_ref.error_logger.log_info(f"update_port_combo_display: 接收到的串口列表: {[port['name'] for port in available_ports]}")
            self.main_window_ref.error_logger.log_info(f"update_port_combo_display: 当前选中的串口: {current_port_name}")
        
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        if not available_ports:
            self.port_combo.addItem("无可用端口")
            self.port_combo.setEnabled(False)
            self.connect_button.setEnabled(False)
            if self.main_window_ref.error_logger:
                self.main_window_ref.error_logger.log_info("update_port_combo_display: 无可用串口")
        else:
            for port_info in available_ports:
                display_text = f"{port_info['name']} ({port_info.get('description', 'N/A')})"
                self.port_combo.addItem(display_text, port_info['name'])
            self.port_combo.setEnabled(True)
            self.connect_button.setEnabled(True)
            idx = -1
            if current_port_name:
                idx = self.port_combo.findData(current_port_name)
                if self.main_window_ref.error_logger:
                    self.main_window_ref.error_logger.log_info(f"update_port_combo_display: 查找当前串口 {current_port_name} 的索引: {idx}")
            if idx != -1:
                self.port_combo.setCurrentIndex(idx)
                if self.main_window_ref.error_logger:
                    self.main_window_ref.error_logger.log_info(f"update_port_combo_display: 设置当前索引为 {idx}")
            elif self.port_combo.count() > 0:
                self.port_combo.setCurrentIndex(0)
                if self.main_window_ref.error_logger:
                    self.main_window_ref.error_logger.log_info("update_port_combo_display: 设置当前索引为 0")
        self.port_combo.blockSignals(False)
        
        # 记录最终的下拉框状态
        if self.main_window_ref.error_logger:
            items = []
            for i in range(self.port_combo.count()):
                items.append(f"{self.port_combo.itemText(i)} (data: {self.port_combo.itemData(i)})")
            self.main_window_ref.error_logger.log_info(f"update_port_combo_display: 最终下拉框项: {items}")
            self.main_window_ref.error_logger.log_info(f"update_port_combo_display: 当前选中项: {self.port_combo.currentText()} (data: {self.port_combo.currentData()})")

    def set_connection_status_display(self, connected: bool):
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.data_bits_combo.setEnabled(not connected)
        self.parity_combo.setEnabled(not connected)
        self.stop_bits_combo.setEnabled(not connected)
        self.refresh_ports_button.setEnabled(not connected)
        self.connect_button.setChecked(connected)
        self.connect_button.setText("关闭串口" if connected else "打开串口")
        
        if connected:
            self.connect_button.setStyleSheet("background-color: green; color: white;")
        else:
            self.connect_button.setStyleSheet("")

        if not connected and (self.port_combo.count() == 0 or self.port_combo.currentText() == "无可用端口"):
            self.connect_button.setEnabled(False)
        elif not connected:
            self.connect_button.setEnabled(True)

    @Slot(bool) # <--- 新增的内部槽函数
    def _handle_internal_connect_button_click(self, checked: bool):
        """Internal slot to explicitly emit the connect_button_toggled signal."""
        self.connect_button_toggled.emit(checked) # 明确用 checked 参数发射信号

    def update_checksum_display(self, sum_check: str, add_check: str):
        self.sum_check_display.setText(sum_check); self.add_check_display.setText(add_check)


class CustomLogPanelWidget(QWidget):  # Full implementation
    def __init__(self, main_window_ref: 'SerialDebugger', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
        self.hex_checkbox = QCheckBox("Hex显示")
        self.timestamp_checkbox = QCheckBox("时间戳")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        log_group = QGroupBox("自定义协议原始帧记录")
        log_layout = QVBoxLayout()
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setFontFamily("Courier New")
        log_layout.addWidget(self.log_text_edit)
        options_layout = QHBoxLayout()
        options_layout.addWidget(self.hex_checkbox)
        options_layout.addWidget(self.timestamp_checkbox)
        clear_button = QPushButton("清空记录区")
        clear_button.clicked.connect(self.log_text_edit.clear)
        options_layout.addWidget(clear_button)
        options_layout.addStretch()
        log_layout.addLayout(options_layout)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        self.setLayout(layout)

    def append_log(self, text: str): self.log_text_edit.moveCursor(
        QTextCursor.MoveOperation.End); self.log_text_edit.insertPlainText(text); self.log_text_edit.moveCursor(
        QTextCursor.MoveOperation.End)

    def get_config(self) -> Dict: return {"hex_display": self.hex_checkbox.isChecked(),
                                          "timestamp_display": self.timestamp_checkbox.isChecked()}

    def apply_config(self, config: Dict): self.hex_checkbox.setChecked(
        config.get("hex_display", False)); self.timestamp_checkbox.setChecked(config.get("timestamp_display", False))

    def hex_checkbox_is_checked(self) -> bool: return self.hex_checkbox.isChecked()

    def timestamp_checkbox_is_checked(self) -> bool: return self.timestamp_checkbox.isChecked()


class BasicCommPanelWidget(QWidget):  # Enhanced implementation
    send_basic_data_requested = Signal(str, bool)
    
    def __init__(self, main_window_ref: 'SerialDebugger', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
        
        # 接收区域控件
        self.recv_hex_checkbox = QCheckBox("Hex显示")
        self.recv_timestamp_checkbox = QCheckBox("显示时间戳")
        self.recv_auto_scroll_checkbox = QCheckBox("自动滚动")
        self.recv_word_wrap_checkbox = QCheckBox("自动换行")
        self.receive_text_edit: Optional[QTextEdit] = None
        
        # 发送区域控件
        self.send_hex_checkbox = QCheckBox("Hex发送")
        self.terminal_mode_checkbox = QCheckBox("终端模式")
        self.auto_send_checkbox = QCheckBox("自动发送")
        self.send_button = QPushButton("发送")
        self.send_text_edit: Optional[QPlainTextEdit] = None
        
        # 快捷发送按钮
        self.quick_send_buttons = []
        self.quick_send_data = [
            ("心跳包", "AA BB CC DD", True),
            ("查询状态", "01 03 00 00", True),
            ("复位命令", "FF FF FF FF", True),
            ("Hello", "Hello World!", False)
        ]
        
        # 终端模式相关变量
        self.command_history = []
        self.history_index = -1
        self.max_history_size = 100
        
        # 自动发送相关
        self.auto_send_timer = None
        self.auto_send_interval = 1000  # 默认1秒
        
        # 统计信息
        self.tx_count = 0
        self.rx_count = 0
        self.tx_bytes = 0
        self.rx_bytes = 0
        
        self._init_ui()
        self._connect_signals()
        self._setup_auto_send_timer()
        self._setup_stats_timer()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        self._create_receive_group(main_layout)
        self._create_send_group(main_layout)
        self.setLayout(main_layout)

    def _create_receive_group(self, main_layout: QVBoxLayout):
        recv_group = QGroupBox("数据接收区域")
        recv_layout = QVBoxLayout()
        
        # 统计信息栏
        stats_layout = QHBoxLayout()
        self.rx_count_label = QLabel("接收: 0 包")
        self.rx_bytes_label = QLabel("字节: 0")
        self.rx_rate_label = QLabel("速率: 0 B/s")
        stats_layout.addWidget(self.rx_count_label)
        stats_layout.addWidget(self.rx_bytes_label)
        stats_layout.addWidget(self.rx_rate_label)
        stats_layout.addStretch()
        recv_layout.addLayout(stats_layout)
        
        # 接收文本框
        self.receive_text_edit = QTextEdit()
        self.receive_text_edit.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.receive_text_edit.setFont(font)
        self.receive_text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #00FF00;
                border: 1px solid #3F3F3F;
                selection-background-color: #264F78;
            }
        """)
        recv_layout.addWidget(self.receive_text_edit)
        
        # 接收选项
        recv_options_layout = QHBoxLayout()
        self.recv_hex_checkbox.setChecked(True)
        self.recv_auto_scroll_checkbox.setChecked(True)
        self.recv_word_wrap_checkbox.setChecked(False)
        
        recv_options_layout.addWidget(self.recv_hex_checkbox)
        recv_options_layout.addWidget(self.recv_timestamp_checkbox)
        recv_options_layout.addWidget(self.recv_auto_scroll_checkbox)
        recv_options_layout.addWidget(self.recv_word_wrap_checkbox)
        recv_options_layout.addStretch()
        
        # 接收区域按钮
        clear_recv_button = QPushButton("清空")
        clear_recv_button.setMaximumWidth(60)
        clear_recv_button.clicked.connect(self.clear_receive_area)
        save_recv_button = QPushButton("保存")
        save_recv_button.setMaximumWidth(60)
        save_recv_button.clicked.connect(self._save_receive_data)
        
        recv_options_layout.addWidget(save_recv_button)
        recv_options_layout.addWidget(clear_recv_button)
        
        recv_layout.addLayout(recv_options_layout)
        recv_group.setLayout(recv_layout)
        main_layout.addWidget(recv_group)

    def _create_send_group(self, main_layout: QVBoxLayout):
        send_group = QGroupBox("数据发送区域")
        send_layout = QVBoxLayout()
        
        # 统计信息栏
        send_stats_layout = QHBoxLayout()
        self.tx_count_label = QLabel("发送: 0 包")
        self.tx_bytes_label = QLabel("字节: 0")
        self.tx_rate_label = QLabel("速率: 0 B/s")
        send_stats_layout.addWidget(self.tx_count_label)
        send_stats_layout.addWidget(self.tx_bytes_label)
        send_stats_layout.addWidget(self.tx_rate_label)
        send_stats_layout.addStretch()
        send_layout.addLayout(send_stats_layout)
        
        # 快捷发送按钮区域
        quick_send_group = QGroupBox("快捷发送")
        quick_send_layout = QHBoxLayout()
        
        for i, (name, data, is_hex) in enumerate(self.quick_send_data):
            btn = QPushButton(name)
            btn.setMaximumWidth(80)
            btn.clicked.connect(lambda checked, d=data, h=is_hex: self._quick_send(d, h))
            self.quick_send_buttons.append(btn)
            quick_send_layout.addWidget(btn)
        
        quick_send_layout.addStretch()
        edit_quick_btn = QPushButton("编辑")
        edit_quick_btn.setMaximumWidth(60)
        edit_quick_btn.clicked.connect(self._edit_quick_send)
        quick_send_layout.addWidget(edit_quick_btn)
        
        quick_send_group.setLayout(quick_send_layout)
        send_layout.addWidget(quick_send_group)
        
        # 发送文本框
        self.send_text_edit = QPlainTextEdit()
        self.send_text_edit.setMaximumHeight(120)
        self.send_text_edit.setPlaceholderText("输入要发送的文本或Hex数据 (如: AB CD EF 或 Hello)\nCtrl+Enter快速发送")
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.send_text_edit.setFont(font)
        self.send_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #3F3F3F;
                selection-background-color: #264F78;
            }
        """)
        send_layout.addWidget(self.send_text_edit)
        
        # 发送选项第一行
        send_options1_layout = QHBoxLayout()
        self.send_hex_checkbox.setChecked(True)
        send_options1_layout.addWidget(self.send_hex_checkbox)
        send_options1_layout.addWidget(self.terminal_mode_checkbox)
        send_options1_layout.addWidget(self.auto_send_checkbox)
        
        # 自动发送间隔设置
        send_options1_layout.addWidget(QLabel("间隔(ms):"))
        self.auto_send_interval_edit = QLineEdit("1000")
        self.auto_send_interval_edit.setMaximumWidth(80)
        self.auto_send_interval_edit.setValidator(QIntValidator(100, 60000, self))
        send_options1_layout.addWidget(self.auto_send_interval_edit)
        
        send_options1_layout.addStretch()
        send_layout.addLayout(send_options1_layout)
        
        # 发送选项第二行
        send_options2_layout = QHBoxLayout()
        
        # 发送格式选择
        format_group = QGroupBox("发送格式")
        format_layout = QHBoxLayout()
        self.format_raw_radio = QPushButton("原始")
        self.format_crlf_radio = QPushButton("+CRLF")
        self.format_lf_radio = QPushButton("+LF")
        self.format_cr_radio = QPushButton("+CR")
        
        for btn in [self.format_raw_radio, self.format_crlf_radio, self.format_lf_radio, self.format_cr_radio]:
            btn.setCheckable(True)
            btn.setMaximumWidth(60)
            format_layout.addWidget(btn)
        
        self.format_raw_radio.setChecked(True)
        format_group.setLayout(format_layout)
        send_options2_layout.addWidget(format_group)
        
        send_options2_layout.addStretch()
        
        # 发送按钮区域
        clear_send_button = QPushButton("清空")
        clear_send_button.clicked.connect(self.clear_send_area)
        send_options2_layout.addWidget(clear_send_button)
        
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        self.send_button.clicked.connect(self._on_send_clicked)
        send_options2_layout.addWidget(self.send_button)
        
        send_layout.addLayout(send_options2_layout)
        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)

    def _connect_signals(self):
        if self.send_text_edit:
            self.send_text_edit.keyPressEvent = self._on_send_text_key_press
        self.send_hex_checkbox.toggled.connect(self._on_hex_mode_toggled)
        self.terminal_mode_checkbox.toggled.connect(self._on_terminal_mode_toggled)
        self.auto_send_checkbox.toggled.connect(self._on_auto_send_toggled)
        self.recv_auto_scroll_checkbox.toggled.connect(self._on_auto_scroll_toggled)
        self.recv_word_wrap_checkbox.toggled.connect(self._on_auto_wrap_toggled)
        
        # 连接发送格式按钮
        self.format_raw_radio.clicked.connect(lambda: self._set_send_format('raw'))
        self.format_crlf_radio.clicked.connect(lambda: self._set_send_format('crlf'))
        self.format_lf_radio.clicked.connect(lambda: self._set_send_format('lf'))
        self.format_cr_radio.clicked.connect(lambda: self._set_send_format('cr'))

    @Slot(bool)
    def _on_hex_mode_toggled(self, checked: bool):
        if self.send_text_edit:
            if checked:
                self.send_text_edit.setPlaceholderText("输入Hex数据 (如: AB CD EF 或 ABCDEF)")
            else:
                self.send_text_edit.setPlaceholderText("输入要发送的文本")

    @Slot(bool)
    def _on_terminal_mode_toggled(self, checked: bool):
        if self.send_text_edit:
            if checked:
                self.send_text_edit.setMaximumHeight(200)
                self.send_text_edit.setPlaceholderText("终端模式 - 输入命令后按Enter发送 (上下箭头可浏览历史命令)")
                self.send_text_edit.setStyleSheet("""
                    QPlainTextEdit {
                        background-color: #0C0C0C;
                        color: #CCCCCC;
                        font-family: Consolas, 'Courier New', monospace;
                        border: 1px solid #3F3F3F;
                    }
                """)
                # 添加初始提示符
                self.send_text_edit.setPlainText("> ")
            else:
                self.send_text_edit.setMaximumHeight(100)
                self.send_text_edit.setPlaceholderText("输入要发送的文本或Hex数据 (如: AB CD EF 或 Hello)")
                self.send_text_edit.setStyleSheet("""
                    QPlainTextEdit {
                        background-color: #1E1E1E;
                        color: #CCCCCC;
                        font-family: Consolas, 'Courier New', monospace;
                    }
                """)

    def _on_send_text_key_press(self, event):
        # Ctrl+Enter 快速发送
        if (event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter) and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._on_send_clicked()
            event.accept()
            return
            
        if not self.terminal_mode_checkbox.isChecked():
            # 非终端模式，保持原有行为
            QPlainTextEdit.keyPressEvent(self.send_text_edit, event)
            return

        # 终端模式下的特殊按键处理
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
            self.send_text_edit.setPlainText(current_text)
            self._on_send_clicked()
            # 发送后添加新的提示符
            self.send_text_edit.setPlainText("> ")
            event.accept()
        else:
            # 其他按键保持默认行为
            current_text = self.send_text_edit.toPlainText()
            if not current_text.startswith("> "):
                self.send_text_edit.setPlainText("> " + current_text)
            QPlainTextEdit.keyPressEvent(self.send_text_edit, event)

    @Slot()
    def _on_send_clicked(self):
        if not hasattr(self.main_window_ref, 'serial_manager'):
            QMessageBox.warning(self, "错误",  "串口管理器未初始化。")
            return
        if not self.main_window_ref.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "串口未打开，请先打开串口连接。")
            return
        if not self.send_text_edit:
            return
            
        # 获取要发送的文本
        text_to_send = self.send_text_edit.toPlainText().strip()
        if not text_to_send:
            QMessageBox.information(self, "提示", "请输入要发送的数据。")
            return
            
        is_hex = self.send_hex_checkbox.isChecked()
        if is_hex and not self._validate_hex_input(text_to_send):
            QMessageBox.warning(self, "输入错误", "Hex数据格式不正确。\n请输入有效的十六进制数据，如: AB CD EF 或 ABCDEF")
            return

        # 添加发送格式处理
        formatted_text = self._apply_send_format(text_to_send)

        # 如果是终端模式，处理多行发送和命令历史
        if self.terminal_mode_checkbox.isChecked():
            # 添加到命令历史
            if not self.command_history or self.command_history[0] != text_to_send:
                self.command_history.insert(0, text_to_send)
                if len(self.command_history) > 100:  # 限制历史记录数量
                    self.command_history.pop()
            self.history_index = -1
            
            # 发送后清空输入框
            if not self.auto_send_checkbox.isChecked():
                self.send_text_edit.clear()
        else:
            # 非终端模式保持原有行为
            if not self.auto_send_checkbox.isChecked():
                self.send_text_edit.clear()

        # 更新发送统计
        if is_hex:
            hex_data = re.sub(r'[\s\-:,]', '', formatted_text.upper())
            byte_count = len(hex_data) // 2
        else:
            byte_count = len(formatted_text.encode('utf-8'))
        
        self.update_tx_stats(byte_count)
        self.send_basic_data_requested.emit(formatted_text, is_hex)


    def _validate_hex_input(self, text: str) -> bool:
        if not text:
            return False  # Handles empty string case explicitly

        # hex_text will now always be assigned if text is not empty
        hex_text = re.sub(r'[\s\-:,]', '', text.upper())

        if not re.match(r'^[0-9A-F]*$', hex_text):
            return False  # Handles non-hex characters

        # Handles empty string after stripping (e.g., if input was just spaces)
        # and ensures even length for valid hex.
        if not hex_text:  # Check if hex_text became empty after re.sub (e.g. input was only spaces)
            return False

        return len(hex_text) % 2 == 0  # No need for `and len(hex_text) > 0` due to the `if not hex_text` check above

    def append_receive_text(self, text: str):
        if self.main_window_ref.error_logger:
            self.main_window_ref.error_logger.log_info(f"append_receive_text triggered with text: {text}")
        if self.receive_text_edit is None:
            return
        cursor = self.receive_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.receive_text_edit.setTextCursor(cursor)
        self.receive_text_edit.insertPlainText(text)
        self.receive_text_edit.ensureCursorVisible()
    def set_send_enabled(self, enabled: bool):
        self.send_button.setEnabled(enabled)
        if self.send_text_edit:
            self.send_text_edit.setEnabled(enabled)
        self.send_hex_checkbox.setEnabled(enabled)
    def get_config(self) -> Dict:
        return {"recv_hex_display": self.recv_hex_checkbox.isChecked(),
                "recv_timestamp_display": self.recv_timestamp_checkbox.isChecked(),
                "send_hex_checked": self.send_hex_checkbox.isChecked()}

    def apply_config(self, config: Dict):
        self.recv_hex_checkbox.setChecked(config.get("recv_hex_display", False))
        self.recv_timestamp_checkbox.setChecked(config.get("recv_timestamp_display", False))
        self.send_hex_checkbox.setChecked(config.get("send_hex_checked", False))
        self._on_hex_mode_toggled(self.send_hex_checkbox.isChecked())
    def recv_hex_checkbox_is_checked(self) -> bool:
        return self.recv_hex_checkbox.isChecked()

    def recv_timestamp_checkbox_is_checked(self) -> bool:
        return self.recv_timestamp_checkbox.isChecked()

    def clear_receive_area(self):
        if self.receive_text_edit: self.receive_text_edit.clear()

    def clear_send_area(self):
        if self.send_text_edit: 
            if self.terminal_mode_checkbox.isChecked():
                self.send_text_edit.setPlainText("> ")
            else:
                self.send_text_edit.clear()

    def get_send_text(self) -> str:
        return self.send_text_edit.toPlainText() if self.send_text_edit else ""

    def set_send_text(self, text: str):
        if self.send_text_edit: self.send_text_edit.setPlainText(text)

    def _setup_auto_send_timer(self):
        self.auto_send_timer = QTimer()
        self.auto_send_timer.timeout.connect(self._auto_send_timeout)

    def _setup_stats_timer(self):
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # 每秒更新一次统计信息

    @Slot(bool)
    def _on_auto_send_toggled(self, checked: bool):
        if checked:
            # 检查串口连接状态
            if not hasattr(self.main_window_ref, 'serial_manager') or not self.main_window_ref.serial_manager.is_connected:
                self.auto_send_checkbox.setChecked(False)
                QMessageBox.warning(self, "错误", "请先连接串口后再启用自动发送功能")
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
        # 自动滚动功能实现
        pass

    @Slot(bool)
    def _on_auto_wrap_toggled(self, checked: bool):
        if self.receive_text_edit:
            if checked:
                self.receive_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            else:
                self.receive_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

    def _set_send_format(self, format_type: str):
        # 重置所有按钮状态
        for btn in [self.format_raw_radio, self.format_crlf_radio, self.format_lf_radio, self.format_cr_radio]:
            btn.setChecked(False)
        
        # 设置选中的按钮
        if format_type == 'raw':
            self.format_raw_radio.setChecked(True)
        elif format_type == 'crlf':
            self.format_crlf_radio.setChecked(True)
        elif format_type == 'lf':
            self.format_lf_radio.setChecked(True)
        elif format_type == 'cr':
            self.format_cr_radio.setChecked(True)

    def _auto_send_timeout(self):
        if self.auto_send_checkbox.isChecked():
            # 检查串口连接状态，如果断开则停止自动发送
            if not hasattr(self.main_window_ref, 'serial_manager') or not self.main_window_ref.serial_manager.is_connected:
                self.auto_send_checkbox.setChecked(False)
                self.auto_send_timer.stop()
                return
            self._on_send_clicked()

    def _update_stats(self):
        # 更新统计信息显示
        self.tx_count_label.setText(f"发送: {self.tx_count} 包")
        self.tx_bytes_label.setText(f"字节: {self.tx_bytes}")
        self.rx_count_label.setText(f"接收: {self.rx_count} 包")
        self.rx_bytes_label.setText(f"字节: {self.rx_bytes}")

    def _quick_send(self, data: str, is_hex: bool):
        if not hasattr(self.main_window_ref, 'serial_manager'):
            QMessageBox.warning(self, "错误", "串口管理器未初始化。")
            return
        if not self.main_window_ref.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "串口未打开，请先打开串口连接。")
            return
        
        self.send_basic_data_requested.emit(data, is_hex)
        self.tx_count += 1
        if is_hex:
            hex_data = re.sub(r'[\s\-:,]', '', data.upper())
            self.tx_bytes += len(hex_data) // 2
        else:
            self.tx_bytes += len(data.encode('utf-8'))

    def _edit_quick_send(self):
        # 编辑快捷发送按钮的功能
        QMessageBox.information(self, "提示", "快捷发送编辑功能待实现")

    def _save_receive_data(self):
        if not self.receive_text_edit or not self.receive_text_edit.toPlainText():
            QMessageBox.information(self, "提示", "没有数据可保存")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存接收数据", "", "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.receive_text_edit.toPlainText())
                QMessageBox.information(self, "成功", f"数据已保存到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def update_rx_stats(self, byte_count: int):
        self.rx_count += 1
        self.rx_bytes += byte_count

    def update_tx_stats(self, byte_count: int):
        self.tx_count += 1
        self.tx_bytes += byte_count
    
    def on_serial_connection_changed(self, connected: bool):
        """当串口连接状态改变时调用此方法"""
        if not connected and self.auto_send_checkbox.isChecked():
            # 串口断开时自动停止自动发送
            self.auto_send_checkbox.setChecked(False)
            self.auto_send_timer.stop()

    def _apply_send_format(self, text: str) -> str:
        """根据选择的发送格式处理文本"""
        if self.format_crlf_radio.isChecked():
            return text + '\r\n'
        elif self.format_lf_radio.isChecked():
            return text + '\n'
        elif self.format_cr_radio.isChecked():
            return text + '\r'
        else:  # raw format
            return text


class ScriptingPanelWidget(QWidget):  # Full implementation
    execute_script_requested = Signal(str)

    def __init__(self, main_window_ref: 'SerialDebugger', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
        self.script_input_edit = QPlainTextEdit()
        self.script_output_edit = QPlainTextEdit()
        self._init_ui()

    def _init_ui(self):
        panel_layout = QVBoxLayout(self)
        script_group = QGroupBox("脚本引擎")
        group_layout = QVBoxLayout()
        group_layout.addWidget(QLabel("脚本输入:"))
        self.script_input_edit.setPlaceholderText("在此输入Python脚本...")
        font = QFont("Courier New", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.script_input_edit.setFont(font)
        group_layout.addWidget(self.script_input_edit, 1)
        self.run_script_button = QPushButton("执行脚本 (Run Script)")
        self.run_script_button.clicked.connect(self._on_run_script_clicked)
        group_layout.addWidget(self.run_script_button)
        group_layout.addWidget(QLabel("脚本输出/结果:"))
        self.script_output_edit.setReadOnly(True)
        self.script_output_edit.setFont(font)
        group_layout.addWidget(self.script_output_edit, 1)
        clear_output_button = QPushButton("清空输出")
        clear_output_button.clicked.connect(self.script_output_edit.clear)
        group_layout.addWidget(clear_output_button)
        script_group.setLayout(group_layout)
        panel_layout.addWidget(script_group)
        self.setLayout(panel_layout)

    @Slot()
    def _on_run_script_clicked(self):
        script_text = self.script_input_edit.toPlainText()
        if script_text.strip():
            self.execute_script_requested.emit(script_text)
        elif self.main_window_ref.error_logger:
            self.main_window_ref.error_logger.log_warning("尝试执行空脚本。")
            self.display_script_result("错误：脚本内容为空。")


    def display_script_result(self, result_text: str):
        self.script_output_edit.setPlainText(result_text)

    def get_config(self) -> Dict:
        return {"current_script": self.script_input_edit.toPlainText()}

    def apply_config(self, config: Dict):
        self.script_input_edit.setPlainText(config.get("current_script", ""))
