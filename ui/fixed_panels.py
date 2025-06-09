import re
from typing import Optional, Dict, TYPE_CHECKING  # Added Set

from PySide6.QtCore import Slot, Qt, Signal
from PySide6.QtGui import QTextCursor, QIntValidator, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QMessageBox, QGroupBox, QPlainTextEdit,
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
        return FrameConfig(head=self.head_edit.text().strip(), s_addr=self.saddr_edit.text().strip(),
                           d_addr=self.daddr_edit.text().strip(), func_id=self.id_edit.text().strip())

    def get_checksum_mode_from_ui(self) -> ChecksumMode:
        mode = self.checksum_mode_combo.currentData()
        if isinstance(mode, ChecksumMode):
            return mode
        return Constants.DEFAULT_CHECKSUM_MODE

    def update_port_combo_display(self, available_ports: list[dict], current_port_name: Optional[str]):
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        if not available_ports:
            self.port_combo.addItem("无可用端口")
            self.port_combo.setEnabled(False)
            self.connect_button.setEnabled(False)
        else:
            for port_info in available_ports:
                display_text = f"{port_info['name']} ({port_info.get('description', 'N/A')})"
                self.port_combo.addItem(display_text, port_info['name'])
            self.port_combo.setEnabled(True)
            self.connect_button.setEnabled(True)
            idx = -1
            if current_port_name:
                idx = self.port_combo.findData(current_port_name)
            if idx != -1:
                self.port_combo.setCurrentIndex(idx)
            elif self.port_combo.count() > 0:
                self.port_combo.setCurrentIndex(0)
        self.port_combo.blockSignals(False)

    def set_connection_status_display(self, connected: bool):
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.data_bits_combo.setEnabled(not connected)
        self.parity_combo.setEnabled(not connected)
        self.stop_bits_combo.setEnabled(not connected)
        self.refresh_ports_button.setEnabled(not connected)
        self.connect_button.setChecked(connected)
        self.connect_button.setText("关闭串口" if connected else "打开串口")
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


class BasicCommPanelWidget(QWidget):  # Full implementation
    send_basic_data_requested = Signal(str, bool)

    def __init__(self, main_window_ref: 'SerialDebugger', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref
        self.recv_hex_checkbox = QCheckBox("Hex显示")
        self.recv_timestamp_checkbox = QCheckBox("显示时间戳")
        self.send_hex_checkbox = QCheckBox("Hex发送")
        self.terminal_mode_checkbox = QCheckBox("终端模式")
        self.send_button = QPushButton("发送")
        self.receive_text_edit: Optional[QTextEdit] = None
        self.send_text_edit: Optional[QPlainTextEdit] = None
        
        # 终端模式相关变量初始化
        self.command_history = []  # 存储命令历史
        self.history_index = -1    # 当前浏览的历史命令索引
        self.max_history_size = 100  # 最大历史记录数量
        
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        self._create_receive_group(main_layout)
        self._create_send_group(main_layout)
        self.setLayout(main_layout)

    def _create_receive_group(self, main_layout: QVBoxLayout):
        recv_group = QGroupBox("基本接收 (原始串行数据)")
        recv_layout = QVBoxLayout()
        self.receive_text_edit = QTextEdit()
        self.receive_text_edit.setReadOnly(True)
        font = QFont("Courier New", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.receive_text_edit.setFont(font)
        recv_layout.addWidget(self.receive_text_edit)
        recv_options_layout = QHBoxLayout()
        recv_options_layout.addWidget(self.recv_hex_checkbox)
        recv_options_layout.addWidget(self.recv_timestamp_checkbox)
        recv_options_layout.addStretch()
        clear_basic_recv_button = QPushButton("清空接收区")
        clear_basic_recv_button.clicked.connect(self.receive_text_edit.clear)
        recv_options_layout.addWidget(clear_basic_recv_button)
        recv_layout.addLayout(recv_options_layout)
        recv_group.setLayout(recv_layout)
        main_layout.addWidget(recv_group)

    def _create_send_group(self, main_layout: QVBoxLayout):
        send_group = QGroupBox("基本发送 (原始串行数据)")
        send_layout = QVBoxLayout()
        
        # 创建发送文本框，根据终端模式切换类型
        self.send_text_edit = QPlainTextEdit()
        self.send_text_edit.setMaximumHeight(100)
        self.send_text_edit.setPlaceholderText("输入要发送的文本或Hex数据 (如: AB CD EF 或 Hello)")
        self.send_text_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                font-family: Consolas, 'Courier New', monospace;
            }
        """)
        
        send_layout.addWidget(self.send_text_edit)
        
        send_options_layout = QHBoxLayout()
        send_options_layout.addWidget(self.send_hex_checkbox)
        send_options_layout.addWidget(self.terminal_mode_checkbox)
        send_options_layout.addStretch()
        
        clear_send_button = QPushButton("清空")
        clear_send_button.clicked.connect(self.clear_send_area)
        send_options_layout.addWidget(clear_send_button)
        
        self.send_button.clicked.connect(self._on_send_clicked)
        send_options_layout.addWidget(self.send_button)
        send_layout.addLayout(send_options_layout)
        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)

    def _connect_signals(self):
        if self.send_text_edit:
            self.send_text_edit.keyPressEvent = self._on_send_text_key_press
        self.send_hex_checkbox.toggled.connect(self._on_hex_mode_toggled)
        self.terminal_mode_checkbox.toggled.connect(self._on_terminal_mode_toggled)

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

        # 如果是终端模式，处理多行发送和命令历史
        if self.terminal_mode_checkbox.isChecked():
            # 添加到命令历史
            if not self.command_history or self.command_history[0] != text_to_send:
                self.command_history.insert(0, text_to_send)
                if len(self.command_history) > 100:  # 限制历史记录数量
                    self.command_history.pop()
            self.history_index = -1
            
            # 发送后清空输入框
            self.send_text_edit.clear()
        else:
            # 非终端模式保持原有行为
            self.send_text_edit.clear()

        self.send_basic_data_requested.emit(text_to_send, is_hex)


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
        return self.send_text_edit.text() if self.send_text_edit else ""

    def set_send_text(self, text: str):
        if self.send_text_edit: self.send_text_edit.setText(text)


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
