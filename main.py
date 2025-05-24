import struct
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

from PySide6.QtCore import Slot, QByteArray, Qt, QEvent, QObject, Signal
from PySide6.QtGui import QAction, QTextCursor, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QMessageBox, QGroupBox, QScrollArea, QFileDialog,
    QInputDialog,
    QDockWidget
)

try:
    import pyqtgraph as pg

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    print("警告：pyqtgraph 未安装，波形图功能将不可用。请运行 'pip install pyqtgraph'")

from utils.constants import Constants, ChecksumMode
from utils.data_models import SerialPortConfig, FrameConfig
from utils.logger import ErrorLogger
from utils.config_manager import ConfigManager
from ui.theme_manager import ThemeManager
from ui.widgets import ReceiveDataContainerWidget, SendDataContainerWidget, PlotWidgetContainer
from core.serial_manager import SerialManager
from core.protocol_handler import ProtocolAnalyzer, FrameParser, get_data_type_byte_length, calculate_frame_crc16, calculate_original_checksums_python
from core.data_recorder import DataRecorder


# Assume ParsePanelWidget and SendPanelWidget classes are defined as in your uploaded file.
# For brevity, their full code is not repeated here, but they are essential.

# --- Panel Widget Classes (Ensure these are defined as previously discussed) ---
class ParsePanelWidget(QWidget):  # Placeholder - Use your full class definition
    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', initial_config: Optional[Dict] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.panel_id = panel_id
        self.main_window_ref = main_window_ref
        self.error_logger = main_window_ref.error_logger
        self.receive_data_containers: List[ReceiveDataContainerWidget] = []
        self._init_ui()
        if initial_config:
            self.apply_config(initial_config)
        else:
            self.parse_id_edit.setText(f"C{self.panel_id}")
            self.recv_display_group.setTitle(f"解析面板 {self.panel_id} (ID: C{self.panel_id})")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.recv_display_group = QGroupBox(f"解析面板 {self.panel_id}")
        recv_display_main_layout = QVBoxLayout()
        recv_container_controls_layout = QHBoxLayout()
        self.add_recv_container_button = QPushButton("添加显示项 (+)")
        self.add_recv_container_button.clicked.connect(self._add_container_action_triggered)
        recv_container_controls_layout.addWidget(self.add_recv_container_button)
        self.remove_recv_container_button = QPushButton("删除显示项 (-)")
        self.remove_recv_container_button.clicked.connect(self._remove_container_action_triggered)
        self.remove_recv_container_button.setEnabled(False)
        recv_container_controls_layout.addWidget(self.remove_recv_container_button)
        recv_container_controls_layout.addStretch()
        recv_display_main_layout.addLayout(recv_container_controls_layout)
        self.scroll_area_recv_containers = QScrollArea()
        self.scroll_area_recv_containers.setWidgetResizable(True)
        self.recv_containers_widget = QWidget()
        self.recv_containers_layout = QVBoxLayout(self.recv_containers_widget)
        self.recv_containers_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area_recv_containers.setWidget(self.recv_containers_widget)
        recv_display_main_layout.addWidget(self.scroll_area_recv_containers)
        parse_config_layout = QGridLayout()
        self.parse_id_label = QLabel("解析功能码(ID)[Hex]:")
        parse_config_layout.addWidget(self.parse_id_label, 0, 0)
        self.parse_id_edit = QLineEdit()
        self.parse_id_edit.editingFinished.connect(self._update_panel_title_from_parse_id)
        parse_config_layout.addWidget(self.parse_id_edit, 0, 1)
        parse_config_layout.addWidget(QLabel("数据分配模式:"), 1, 0)
        self.data_mapping_combo = QComboBox()
        self.data_mapping_combo.addItems(["顺序填充 (Sequential)"])
        parse_config_layout.addWidget(self.data_mapping_combo, 1, 1)
        recv_display_main_layout.addLayout(parse_config_layout)
        self.recv_display_group.setLayout(recv_display_main_layout)
        layout.addWidget(self.recv_display_group)
        self.setLayout(layout)

    def _update_panel_title_from_parse_id(self):
        new_title = f"解析面板 {self.panel_id} (ID: {self.get_target_func_id().upper()})"
        self.recv_display_group.setTitle(new_title)
        dock = self.main_window_ref.parse_panel_docks.get(self.panel_id)
        if dock: dock.setWindowTitle(new_title)

    @Slot()
    def _add_container_action_triggered(self):
        self.add_receive_data_container()

    @Slot()
    def _remove_container_action_triggered(self):
        self.remove_receive_data_container()

    def add_receive_data_container(self, config: Optional[Dict[str, Any]] = None, silent: bool = False) -> None:
        container_id = self.main_window_ref.get_next_global_receive_container_id()
        container = ReceiveDataContainerWidget(container_id, self.main_window_ref)
        container.plot_target_changed_signal.connect(self.main_window_ref.handle_recv_container_plot_target_change)
        if config:
            container.name_edit.setText(config.get("name", f"RecvData_{container_id}"))
            container.type_combo.setCurrentText(config.get("type", "uint8_t"))
            if PYQTGRAPH_AVAILABLE and container.plot_checkbox: container.plot_checkbox.setChecked(
                config.get("plot_enabled", False))
        self.recv_containers_layout.addWidget(container)
        self.receive_data_containers.append(container)
        self.remove_recv_container_button.setEnabled(True)
        targets_for_dropdown = {pid: pw.plot_name for pid, pw in self.main_window_ref.plot_widgets_map.items()}
        container.update_plot_targets(targets_for_dropdown)
        if config and PYQTGRAPH_AVAILABLE and container.plot_target_combo:
            plot_target_id = config.get("plot_target_id")
            if plot_target_id is not None:
                idx = container.plot_target_combo.findData(plot_target_id)
                if idx != -1: container.plot_target_combo.setCurrentIndex(idx)
                container.plot_target_combo.setEnabled(
                    container.plot_checkbox.isChecked() and bool(targets_for_dropdown))
        if not silent and self.error_logger: self.error_logger.log_info(
            f"Parse Panel {self.panel_id}: Added receive container {container_id}")

    def remove_receive_data_container(self, silent: bool = False) -> None:
        if self.receive_data_containers:
            container_to_remove = self.receive_data_containers.pop()
            container_id_removed = container_to_remove.container_id
            self.recv_containers_layout.removeWidget(container_to_remove)
            container_to_remove.deleteLater()
            self.main_window_ref.clear_plot_curves_for_container(container_id_removed)
            if not self.receive_data_containers: self.remove_recv_container_button.setEnabled(False)
            if not silent and self.error_logger: self.error_logger.log_info(
                f"Parse Panel {self.panel_id}: Removed receive container {container_id_removed}")

    def get_target_func_id(self) -> str:
        return self.parse_id_edit.text()

    def dispatch_data(self, data_payload_ba: QByteArray) -> None:  # As previously defined
        if not self.receive_data_containers: return
        current_offset = 0
        parsed_data_for_log_export: Dict[str, str] = {}
        timestamp_now = datetime.now()
        if self.data_mapping_combo.currentText() == "顺序填充 (Sequential)":
            for container_widget in self.receive_data_containers:
                config = container_widget.get_config()
                data_type = config["type"]
                byte_len = get_data_type_byte_length(data_type)
                segment = QByteArray()
                if byte_len == -1:
                    if current_offset < data_payload_ba.length(): segment = data_payload_ba.mid(
                        current_offset); current_offset = data_payload_ba.length()
                elif byte_len > 0:
                    if current_offset + byte_len <= data_payload_ba.length(): segment = data_payload_ba.mid(
                        current_offset, byte_len); current_offset += byte_len
                container_widget.set_value(segment, data_type)
                log_key_name = f"P{self.panel_id}_{config['name']}"
                parsed_data_for_log_export[log_key_name] = container_widget.value_edit.text()
                if PYQTGRAPH_AVAILABLE and config["plot_enabled"] and config["plot_target_id"] is not None:
                    target_plot_id = config["plot_target_id"]
                    if target_plot_id in self.main_window_ref.plot_widgets_map:
                        val_float = container_widget.get_value_as_float()
                        if val_float is not None:
                            curve_name = f"P{self.panel_id}:{config['name']}"
                            self.main_window_ref.plot_widgets_map[target_plot_id].update_data(config["id"], val_float,
                                                                                              curve_name)
        if parsed_data_for_log_export: self.main_window_ref.data_recorder.add_parsed_frame_data(timestamp_now,
                                                                                                parsed_data_for_log_export)

    def get_config(self) -> Dict[str, Any]:  # As previously defined
        return {"panel_id": self.panel_id, "parse_func_id": self.parse_id_edit.text(),
                "data_mapping_mode": self.data_mapping_combo.currentText(),
                "receive_containers": [c.get_config() for c in self.receive_data_containers],
                "dock_name": self.recv_display_group.title()}

    def apply_config(self, config: Dict[str, Any]):  # As previously defined
        self.parse_id_edit.setText(config.get("parse_func_id", f"C{self.panel_id}"))
        self._update_panel_title_from_parse_id()
        self.data_mapping_combo.setCurrentText(config.get("data_mapping_mode", "顺序填充 (Sequential)"))
        while self.receive_data_containers: self.remove_receive_data_container(silent=True)
        for cfg in config.get("receive_containers", []): self.add_receive_data_container(config=cfg, silent=True)

    def update_children_plot_targets(self):  # As previously defined
        targets = {pid: pw.plot_name for pid, pw in self.main_window_ref.plot_widgets_map.items()}
        for container in self.receive_data_containers:
            current_target_id_data = container.plot_target_combo.currentData() if container.plot_target_combo and container.plot_target_combo.count() > 0 else None
            current_target_id = current_target_id_data if current_target_id_data is not None else None
            container.update_plot_targets(targets)
            if current_target_id is not None and container.plot_target_combo:
                idx = container.plot_target_combo.findData(current_target_id)
                if idx != -1: container.plot_target_combo.setCurrentIndex(idx)
            if container.plot_checkbox and container.plot_target_combo: container.plot_target_combo.setEnabled(
                container.plot_checkbox.isChecked() and bool(targets))


class SendPanelWidget(QWidget):  # Placeholder - Use your full class definition
    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', initial_config: Optional[Dict] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.panel_id = panel_id
        self.main_window_ref = main_window_ref
        self.error_logger = main_window_ref.error_logger
        self.send_data_containers: List[SendDataContainerWidget] = []
        self._next_local_send_container_id: int = 1
        self._init_ui()
        if initial_config:
            self.apply_panel_config(initial_config)
        else:
            self.panel_func_id_edit.setText(f"C{self.panel_id + 8:X}"); self._update_panel_title()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.send_data_group = QGroupBox(f"发送面板 {self.panel_id}")
        send_data_main_layout = QVBoxLayout()
        func_id_layout = QHBoxLayout()
        func_id_layout.addWidget(QLabel("本面板功能码 (ID)[Hex,1B]:"))
        self.panel_func_id_edit = QLineEdit()
        self.panel_func_id_edit.setPlaceholderText("例如: C9")
        self.panel_func_id_edit.editingFinished.connect(self._update_panel_title)
        func_id_layout.addWidget(self.panel_func_id_edit)
        send_data_main_layout.addLayout(func_id_layout)
        send_container_controls_layout = QHBoxLayout()
        self.add_button = QPushButton("添加发送项 (+)")
        self.add_button.clicked.connect(self._add_container_action_triggered)
        send_container_controls_layout.addWidget(self.add_button)
        self.remove_button = QPushButton("删除发送项 (-)")
        self.remove_button.clicked.connect(self._remove_container_action_triggered)
        self.remove_button.setEnabled(False)
        send_container_controls_layout.addWidget(self.remove_button)
        send_container_controls_layout.addStretch()
        send_data_main_layout.addLayout(send_container_controls_layout)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.containers_widget = QWidget()
        self.containers_layout = QVBoxLayout(self.containers_widget)
        self.containers_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.containers_widget)
        send_data_main_layout.addWidget(self.scroll_area)
        self.send_frame_button_panel = QPushButton("发送此面板帧")
        self.send_frame_button_panel.clicked.connect(self._trigger_send_frame)
        send_data_main_layout.addWidget(self.send_frame_button_panel)
        self.send_data_group.setLayout(send_data_main_layout)
        layout.addWidget(self.send_data_group)
        self.setLayout(layout)

    def _update_panel_title(self):
        func_id_text = self.panel_func_id_edit.text().upper()
        title = f"发送面板 {self.panel_id} (ID: {func_id_text if func_id_text else '未定义'})"
        self.send_data_group.setTitle(title)
        dock = self.main_window_ref.send_panel_docks.get(self.panel_id)
        if dock: dock.setWindowTitle(title)

    @Slot()
    def _add_container_action_triggered(self):
        self.add_send_data_container()

    @Slot()
    def _remove_container_action_triggered(self):
        self.remove_send_data_container()

    def add_send_data_container(self, config: Optional[Dict[str, Any]] = None,
                                silent: bool = False):  # As previously defined
        container_id = self._next_local_send_container_id
        container = SendDataContainerWidget(container_id, self.main_window_ref)
        if config: container.name_edit.setText(
            config.get("name", f"Data_{container_id}")); container.type_combo.setCurrentText(
            config.get("type", "uint8_t")); container.value_edit.setText(config.get("value", ""))
        self.containers_layout.addWidget(container)
        self.send_data_containers.append(container)
        self._next_local_send_container_id += 1
        self.remove_button.setEnabled(True)
        if not silent and self.error_logger: self.error_logger.log_info(
            f"Send Panel {self.panel_id}: Added send data container {container_id}")

    def remove_send_data_container(self, silent: bool = False):  # As previously defined
        if self.send_data_containers:
            container_to_remove = self.send_data_containers.pop()
            removed_id = container_to_remove.container_id
            self.containers_layout.removeWidget(container_to_remove)
            container_to_remove.deleteLater()
            if not self.send_data_containers: self.remove_button.setEnabled(False)
            if not silent and self.error_logger: self.error_logger.log_info(
                f"Send Panel {self.panel_id}: Removed send data container {removed_id}")

    def get_panel_config(self) -> Dict:  # As previously defined
        return {"panel_id": self.panel_id, "panel_func_id": self.panel_func_id_edit.text(), "send_containers": [
            {"name": c.name_edit.text(), "type": c.type_combo.currentText(), "value": c.value_edit.text()} for c in
            self.send_data_containers], "dock_name": self.send_data_group.title()}

    def apply_panel_config(self, config: Dict):  # As previously defined
        self.panel_func_id_edit.setText(config.get("panel_func_id", f"C{self.panel_id + 8:X}"))
        self._update_panel_title()
        while self.send_data_containers: self.remove_send_data_container(silent=True)
        for c_cfg in config.get("send_containers", []): self.add_send_data_container(config=c_cfg, silent=True)

    @Slot()
    def _trigger_send_frame(self):  # As previously defined
        if not self.main_window_ref.serial_manager.is_connected: QMessageBox.warning(self.main_window_ref, "警告",
                                                                                     "串口未打开。"); return
        panel_func_id = self.panel_func_id_edit.text()
        if not panel_func_id: QMessageBox.warning(self.main_window_ref, "功能码缺失",
                                                  "请输入此发送面板的目标功能码。"); return
        self.main_window_ref.update_current_configs_from_ui_panel()
        final_frame = self.main_window_ref._assemble_custom_frame(panel_target_func_id_str=panel_func_id,
                                                                  panel_send_data_containers=self.send_data_containers)
        if final_frame:
            bytes_written = self.main_window_ref.serial_manager.write_data(final_frame)
            if bytes_written == final_frame.size():
                hex_frame_str = final_frame.toHex(' ').data().decode('ascii').upper()
                msg = f"发送面板 {self.panel_id} (ID:{panel_func_id}) 发送 {bytes_written} 字节: {hex_frame_str}"
                self.main_window_ref.status_bar_label.setText(msg)
                if self.error_logger: self.error_logger.log_info(msg)
                self.main_window_ref.protocol_analyzer.analyze_frame(final_frame, 'tx')
                self.main_window_ref.data_recorder.record_raw_frame(datetime.now(), final_frame.data(),
                                                                    f"TX (SendPanel {self.panel_id} ID:{panel_func_id})")
                self.main_window_ref._append_to_custom_protocol_log_formatted(datetime.now(),
                                                                              "TX P{self.panel_id} ID:{panel_func_id}",
                                                                              hex_frame_str, True)


class SerialConfigDefinitionPanelWidget(QWidget):
    connect_button_toggled = Signal(bool)
    refresh_ports_requested = Signal()
    config_changed = Signal()

    def __init__(self, parent_main_window: 'SerialDebugger', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = parent_main_window
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        config_group = QGroupBox("串口配置")
        config_layout = QGridLayout()
        config_layout.addWidget(QLabel("端口:"), 0, 0)
        self.port_combo = QComboBox()
        config_layout.addWidget(self.port_combo, 0, 1)
        config_layout.addWidget(QLabel("波特率:"), 1, 0)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.baud_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.baud_combo, 1, 1)
        config_layout.addWidget(QLabel("数据位:"), 2, 0)
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(["8", "7", "6", "5"])
        self.data_bits_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.data_bits_combo, 2, 1)
        config_layout.addWidget(QLabel("校验位:"), 3, 0)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd", "Space", "Mark"])
        self.parity_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.parity_combo, 3, 1)
        config_layout.addWidget(QLabel("停止位:"), 4, 0)
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.currentTextChanged.connect(self._emit_config_changed)
        config_layout.addWidget(self.stop_bits_combo, 4, 1)
        self.refresh_ports_button = QPushButton("刷新")
        self.refresh_ports_button.clicked.connect(self.refresh_ports_requested.emit)
        config_layout.addWidget(self.refresh_ports_button, 5, 0)
        self.connect_button = QPushButton("打开串口")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(lambda checked: self.connect_button_toggled.emit(checked))
        config_layout.addWidget(self.connect_button, 5, 1)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        frame_def_group = QGroupBox("全局帧结构定义 (发送用)")
        frame_def_layout = QGridLayout()
        frame_def_layout.addWidget(QLabel("帧头(H)[Hex,1B]:"), 0, 0)
        self.head_edit = QLineEdit()
        self.head_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.head_edit, 0, 1)
        frame_def_layout.addWidget(QLabel("源地址(S)[Hex,1B]:"), 1, 0)
        self.saddr_edit = QLineEdit()
        self.saddr_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.saddr_edit, 1, 1)
        frame_def_layout.addWidget(QLabel("目标地址(D)[Hex,1B]:"), 2, 0)
        self.daddr_edit = QLineEdit()
        self.daddr_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.daddr_edit, 2, 1)
        frame_def_layout.addWidget(QLabel("默认发送功能码(ID):"), 3, 0)
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("面板可覆盖")
        self.id_edit.editingFinished.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.id_edit, 3, 1)
        frame_def_layout.addWidget(QLabel("校验模式:"), 6, 0)
        self.checksum_mode_combo = QComboBox()
        self.checksum_mode_combo.addItem("原始校验 (Sum/Add)", ChecksumMode.ORIGINAL_SUM_ADD)
        self.checksum_mode_combo.addItem("CRC-16/CCITT-FALSE", ChecksumMode.CRC16_CCITT_FALSE)
        self.checksum_mode_combo.currentIndexChanged.connect(self._emit_config_changed)
        frame_def_layout.addWidget(self.checksum_mode_combo, 6, 1)
        frame_def_layout.addWidget(QLabel("最后帧校验1/CRC高:"), 4, 0)
        self.sum_check_display = QLineEdit()
        self.sum_check_display.setPlaceholderText("自动")
        self.sum_check_display.setReadOnly(True)
        frame_def_layout.addWidget(self.sum_check_display, 4, 1)
        frame_def_layout.addWidget(QLabel("最后帧校验2/CRC低:"), 5, 0)
        self.add_check_display = QLineEdit()
        self.add_check_display.setPlaceholderText("自动")
        self.add_check_display.setReadOnly(True)
        frame_def_layout.addWidget(self.add_check_display, 5, 1)
        frame_def_group.setLayout(frame_def_layout)
        layout.addWidget(frame_def_group)
        layout.addStretch()
        self.setLayout(layout)

    def _emit_config_changed(self):
        self.config_changed.emit()

    def update_ui_from_main_configs(self, serial_cfg: SerialPortConfig, frame_cfg: FrameConfig,
                                    active_checksum: ChecksumMode):  # As defined
        self.baud_combo.setCurrentText(str(serial_cfg.baud_rate))
        self.data_bits_combo.setCurrentText(str(serial_cfg.data_bits))
        self.parity_combo.setCurrentText(serial_cfg.parity)
        self.stop_bits_combo.setCurrentText(str(serial_cfg.stop_bits))
        if serial_cfg.port_name:
            idx = self.port_combo.findData(serial_cfg.port_name)
            if idx != -1: self.port_combo.setCurrentIndex(idx)
        self.head_edit.setText(frame_cfg.head)
        self.saddr_edit.setText(frame_cfg.s_addr)
        self.daddr_edit.setText(frame_cfg.d_addr)
        self.id_edit.setText(frame_cfg.func_id)
        idx_cs = self.checksum_mode_combo.findData(active_checksum)
        if idx_cs != -1:
            self.checksum_mode_combo.setCurrentIndex(idx_cs)
        else:
            idx_def = self.checksum_mode_combo.findData(Constants.DEFAULT_CHECKSUM_MODE)
            if idx_def != -1: self.checksum_mode_combo.setCurrentIndex(idx_def)

    def get_serial_config_from_ui(self) -> SerialPortConfig:  # As defined
        pn = self.port_combo.currentData()
        port_name = pn if pn is not None else (
            self.port_combo.currentText() if self.port_combo.currentText() != "无可用端口" else None)
        return SerialPortConfig(port_name, int(self.baud_combo.currentText()), int(self.data_bits_combo.currentText()),
                                self.parity_combo.currentText(), float(
                self.stop_bits_combo.currentText()) if self.stop_bits_combo.currentText() == "1.5" else int(
                self.stop_bits_combo.currentText()))

    def get_frame_config_from_ui(self) -> FrameConfig:  # As defined
        return FrameConfig(self.head_edit.text(), self.saddr_edit.text(), self.daddr_edit.text(), self.id_edit.text())

    def get_checksum_mode_from_ui(self) -> ChecksumMode:  # As defined
        mode = self.checksum_mode_combo.currentData()
        return mode if isinstance(mode, ChecksumMode) else Constants.DEFAULT_CHECKSUM_MODE

    def update_port_combo_display(self, available_ports: List[Dict], current_port_name: Optional[str]):  # As defined
        self.port_combo.clear()
        if not available_ports:
            self.port_combo.addItem("无可用端口"); self.port_combo.setEnabled(False)
        else:
            for port_info in available_ports: self.port_combo.addItem(
                f"{port_info['name']} ({port_info['description']})", port_info['name'])
            self.port_combo.setEnabled(True)
            if current_port_name:
                idx = self.port_combo.findData(current_port_name)
                if idx != -1:
                    self.port_combo.setCurrentIndex(idx)
                elif self.port_combo.count() > 0:
                    self.port_combo.setCurrentIndex(0)

    def set_connection_status_display(self, connected: bool):  # As defined
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.data_bits_combo.setEnabled(not connected)
        self.parity_combo.setEnabled(not connected)
        self.stop_bits_combo.setEnabled(not connected)
        self.refresh_ports_button.setEnabled(not connected)
        self.connect_button.setChecked(connected)
        self.connect_button.setText("关闭串口" if connected else "打开串口")
        if not self.port_combo.count() or self.port_combo.currentText() == "无可用端口": self.connect_button.setEnabled(
            False)

    def update_checksum_display(self, sum_check: str, add_check: str):
        self.sum_check_display.setText(sum_check); self.add_check_display.setText(add_check)


class CustomLogPanelWidget(QWidget):
    def __init__(self, main_window_ref: 'SerialDebugger', parent: Optional[QWidget] = None): # 添加 main_window_ref
        super().__init__(parent)
        self.main_window_ref = main_window_ref # 存储引用
        self.error_logger = main_window_ref.error_logger
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
        self.hex_checkbox = QCheckBox("Hex显示")
        options_layout.addWidget(self.hex_checkbox)
        self.timestamp_checkbox = QCheckBox("显示时间戳")
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


class BasicCommPanelWidget(QWidget):
    send_basic_data_requested = Signal(str, bool)

    def __init__(self, main_window_ref: 'SerialDebugger', parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window_ref = main_window_ref  # 存储主窗口引用
        self._init_ui()


    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        recv_group = QGroupBox("基本接收 (原始串行数据)")
        recv_layout = QVBoxLayout()
        self.receive_text_edit = QTextEdit()
        self.receive_text_edit.setReadOnly(True)
        self.receive_text_edit.setFontFamily("Courier New")
        recv_layout.addWidget(self.receive_text_edit)
        recv_options_layout = QHBoxLayout()
        self.recv_hex_checkbox = QCheckBox("Hex显示")
        self.recv_timestamp_checkbox = QCheckBox("显示时间戳")
        recv_options_layout.addWidget(self.recv_hex_checkbox)
        recv_options_layout.addWidget(self.recv_timestamp_checkbox)
        recv_options_layout.addStretch()
        clear_basic_recv_button = QPushButton("清空接收区")
        clear_basic_recv_button.clicked.connect(self.receive_text_edit.clear)
        recv_options_layout.addWidget(clear_basic_recv_button)
        recv_layout.addLayout(recv_options_layout)
        recv_group.setLayout(recv_layout)
        main_layout.addWidget(recv_group)
        send_group = QGroupBox("基本发送 (原始串行数据)")
        send_layout = QVBoxLayout()
        self.send_text_edit = QLineEdit()
        self.send_text_edit.setPlaceholderText("输入要发送的文本或Hex数据")
        send_layout.addWidget(self.send_text_edit)
        send_options_layout = QHBoxLayout()
        self.send_hex_checkbox = QCheckBox("Hex发送")
        send_options_layout.addWidget(self.send_hex_checkbox)
        send_options_layout.addStretch()
        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("basicSendButtonActual")
        self.send_button.clicked.connect(self._on_send_clicked)
        send_options_layout.addWidget(self.send_button)
        send_layout.addLayout(send_options_layout)
        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)
        self.setLayout(main_layout)

    @Slot()
    def _on_send_clicked(self):
        # 首先检查串口连接状态
        if not self.main_window_ref.serial_manager.is_connected:
            QMessageBox.warning(self.main_window_ref, "警告", "串口未打开，无法发送数据。")
            return  # 如果未连接，则不执行后续操作

        # 如果串口已连接，再发射信号请求发送数据
        text_to_send = self.send_text_edit.text()
        is_hex = self.send_hex_checkbox.isChecked()
        self.send_basic_data_requested.emit(text_to_send, is_hex)

    def append_receive_text(self, text: str): self.receive_text_edit.moveCursor(
        QTextCursor.MoveOperation.End); self.receive_text_edit.insertPlainText(text); self.receive_text_edit.moveCursor(
        QTextCursor.MoveOperation.End)

    def set_send_enabled(self, enabled: bool): self.send_button.setEnabled(enabled)

    def get_config(self) -> Dict: return {"recv_hex_display": self.recv_hex_checkbox.isChecked(),
                                          "recv_timestamp_display": self.recv_timestamp_checkbox.isChecked()}

    def apply_config(self, config: Dict): self.recv_hex_checkbox.setChecked(
        config.get("recv_hex_display", False)); self.recv_timestamp_checkbox.setChecked(
        config.get("recv_timestamp_display", False))


# Presume all necessary imports and other PanelWidget classes
# (ParsePanelWidget, SendPanelWidget, SerialConfigDefinitionPanelWidget,
#  CustomLogPanelWidget, BasicCommPanelWidget, PlotWidgetContainer)
# are correctly defined above this SerialDebugger class, as in your provided file.

class SerialDebugger(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_application_icon(self,"image.png")
        self.setWindowTitle("YJ_tool (Modular Panels)")
        self.active_checksum_mode = ChecksumMode.ORIGINAL_SUM_ADD
        self.app_instance = QApplication.instance()
        self.error_logger = ErrorLogger()
        self.config_manager = ConfigManager(error_logger=self.error_logger)
        self.theme_manager = ThemeManager(self.app_instance, error_logger=self.error_logger)
        self.data_recorder = DataRecorder(error_logger=self.error_logger)
        self.protocol_analyzer = ProtocolAnalyzer(error_logger=self.error_logger)
        self.serial_manager = SerialManager(error_logger=self.error_logger)
        self.frame_parser = FrameParser(error_logger=self.error_logger)

        self.current_config = self.config_manager.load_config()
        self.current_serial_config = SerialPortConfig(**self.current_config.get("serial_port", {}))
        self.current_frame_config = FrameConfig(**self.current_config.get("frame_definition", {}))
        checksum_mode_name = self.current_config.get("checksum_mode", Constants.DEFAULT_CHECKSUM_MODE.name)
        try:
            self.active_checksum_mode = ChecksumMode[checksum_mode_name]
        except KeyError:
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
        self.setDockNestingEnabled(True)
        self._parsed_frame_count: int = 0

        self.parse_panel_widgets: Dict[int, ParsePanelWidget] = {}
        self.parse_panel_docks: Dict[int, QDockWidget] = {}
        self._next_parse_panel_id: int = 1
        self._next_global_receive_container_id: int = 1

        self.send_panel_widgets: Dict[int, SendPanelWidget] = {}
        self.send_panel_docks: Dict[int, QDockWidget] = {}
        self._next_send_panel_id: int = 1

        self.plot_widgets_map: Dict[int, PlotWidgetContainer] = {}
        self.plot_docks_map: Dict[int, QDockWidget] = {}
        self._next_plot_id: int = 1

        self.serial_config_panel_widget: Optional[SerialConfigDefinitionPanelWidget] = None
        self.dw_serial_config: Optional[QDockWidget] = None
        self.custom_log_panel_widget: Optional[CustomLogPanelWidget] = None
        self.dw_custom_log: Optional[QDockWidget] = None
        self.basic_comm_panel_widget: Optional[BasicCommPanelWidget] = None
        self.dw_basic_serial: Optional[QDockWidget] = None

        self._init_ui_dockable_layout()
        self.create_menus()
        self.apply_loaded_config_to_ui()

        self.populate_serial_ports_ui()
        self.update_port_status_ui(False)
        self.update_all_parse_panels_plot_targets()

        # Connect signals from core components
        self.serial_manager.connection_status_changed.connect(self.on_serial_connection_status_changed)
        self.serial_manager.data_received.connect(self.on_serial_data_received)
        self.serial_manager.error_occurred_signal.connect(self.on_serial_manager_error)
        self.frame_parser.frame_successfully_parsed.connect(self.on_frame_successfully_parsed)
        self.frame_parser.checksum_error.connect(self.on_frame_checksum_error)
        self.frame_parser.frame_parse_error.connect(self.on_frame_general_parse_error)

        self.error_logger.log_info("应用程序启动。")
        self.restore_geometry_and_state()

    def get_next_global_receive_container_id(self) -> int:
        current_id = self._next_global_receive_container_id
        self._next_global_receive_container_id += 1
        return current_id

    def clear_plot_curves_for_container(self, container_id: int):
        for plot_widget_container in self.plot_widgets_map.values():
            plot_widget_container.remove_curve_for_container(container_id)

    def _init_ui_dockable_layout(self) -> None:
        self.serial_config_panel_widget = SerialConfigDefinitionPanelWidget(parent_main_window=self, parent=self)
        self.dw_serial_config = QDockWidget("串口与帧定义", self)
        self.dw_serial_config.setObjectName("SerialConfigDock")
        self.dw_serial_config.setWidget(self.serial_config_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dw_serial_config)
        self.serial_config_panel_widget.connect_button_toggled.connect(self.toggle_connection_action_handler)
        self.serial_config_panel_widget.refresh_ports_requested.connect(self.populate_serial_ports_ui)
        self.serial_config_panel_widget.config_changed.connect(self.update_current_configs_from_ui_panel)

        self.custom_log_panel_widget = CustomLogPanelWidget(main_window_ref=self, parent=self)
        self.dw_custom_log = QDockWidget("协议帧原始数据", self)
        self.dw_custom_log.setObjectName("CustomProtocolLogDock")
        self.dw_custom_log.setWidget(self.custom_log_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dw_custom_log)

        self.basic_comm_panel_widget = BasicCommPanelWidget(main_window_ref=self, parent=self)
        self.dw_basic_serial = QDockWidget("基本收发", self)
        self.dw_basic_serial.setObjectName("BasicSerialDock")
        self.dw_basic_serial.setWidget(self.basic_comm_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dw_basic_serial)
        self.basic_comm_panel_widget.send_basic_data_requested.connect(self.send_basic_serial_data_action)

        try:
            self.tabifyDockWidget(self.dw_custom_log, self.dw_basic_serial)
        except AttributeError as e:
            self.error_logger.log_warning(f"无法标签页化停靠窗口 (日志/基本): {e}")

        # --- Dynamic Panels ---
        parse_panel_configs = self.current_config.get("parse_panels", [])
        migrated_old_parse = False
        if not parse_panel_configs and "receive_containers" in self.current_config:  # Old format check
            self.add_new_parse_panel_action(config={
                "parse_func_id": self.current_config.get("parse_func_id", "C1"),
                "data_mapping_mode": self.current_config.get("data_mapping_mode", "顺序填充 (Sequential)"),
                "receive_containers": self.current_config.get("receive_containers", []),
                "dock_name": "默认解析面板 (旧)"  # This name will be used for QDockWidget
            }, from_config=True, is_migration=True)
            migrated_old_parse = True
        elif parse_panel_configs:
            for panel_cfg in parse_panel_configs:
                self.add_new_parse_panel_action(config=panel_cfg, from_config=True)
        if not self.parse_panel_docks and not migrated_old_parse:
            self.add_new_parse_panel_action(panel_name_suggestion="默认解析面板 1", from_config=True)

        send_panel_configs = self.current_config.get("send_panels", [])
        migrated_old_send = False
        if not send_panel_configs and "send_containers" in self.current_config:  # Old format check
            migrated_send_panel_cfg = {
                "panel_func_id": self.current_frame_config.func_id if self.current_frame_config.func_id else f"S{self._next_send_panel_id}",
                "send_containers": self.current_config.get("send_containers", []),
                "dock_name": "默认发送面板 (旧)"}  # This name will be used for QDockWidget
            self.add_new_send_panel_action(config=migrated_send_panel_cfg, from_config=True, is_migration=True)
            migrated_old_send = True
        elif send_panel_configs:
            for panel_cfg in send_panel_configs:
                self.add_new_send_panel_action(config=panel_cfg, from_config=True)
        if not self.send_panel_docks and not migrated_old_send:
            self.add_new_send_panel_action(panel_name_suggestion="默认发送面板 1", from_config=True)

        if self.dw_serial_config and self.send_panel_docks:
            first_send_dock_id = min(self.send_panel_docks.keys(), default=None)
            if first_send_dock_id is not None:
                try:
                    self.tabifyDockWidget(self.dw_serial_config, self.send_panel_docks[first_send_dock_id])
                except AttributeError as e:
                    self.error_logger.log_warning(f"无法标签页化停靠窗口 (串口/发送): {e}")
        elif self.dw_serial_config and self.parse_panel_docks:
            first_parse_dock_id = min(self.parse_panel_docks.keys(), default=None)
            if first_parse_dock_id is not None:
                try:
                    self.tabifyDockWidget(self.dw_serial_config, self.parse_panel_docks[first_parse_dock_id])
                except AttributeError as e:
                    self.error_logger.log_warning(f"无法标签页化停靠窗口 (串口/解析): {e}")

        plot_configs = self.current_config.get("plot_configs", [])
        if not plot_configs and PYQTGRAPH_AVAILABLE:
            self.add_new_plot_widget_action(name="主波形图", from_config=False)
        elif plot_configs and PYQTGRAPH_AVAILABLE:
            for plot_cfg in plot_configs:
                self.add_new_plot_widget_action(name=plot_cfg.get("name", f"波形图 {self._next_plot_id}"),
                                                plot_id_from_config=plot_cfg.get("id"), from_config=True)

        self.status_bar_label = QLabel("未连接")
        self.statusBar().addWidget(self.status_bar_label)

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("文件(&F)")
        load_config_action = QAction("加载配置...", self);
        load_config_action.triggered.connect(self.load_configuration_action);
        file_menu.addAction(load_config_action)
        save_config_action = QAction("保存配置...", self);
        save_config_action.triggered.connect(self.save_configuration_action);
        file_menu.addAction(save_config_action)
        file_menu.addSeparator()
        export_parsed_data_action = QAction("导出已解析数据 (CSV)...", self);
        export_parsed_data_action.triggered.connect(self.export_parsed_data_action);
        file_menu.addAction(export_parsed_data_action)
        save_raw_data_action = QAction("保存原始录制数据 (JSON)...", self);
        save_raw_data_action.triggered.connect(self.save_raw_recorded_data_action);
        file_menu.addAction(save_raw_data_action)
        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self);
        exit_action.triggered.connect(self.close);
        file_menu.addAction(exit_action)

        self.view_menu = self.menuBar().addMenu("视图(&V)")
        if self.dw_serial_config: self.view_menu.addAction(self.dw_serial_config.toggleViewAction())
        if self.dw_custom_log: self.view_menu.addAction(self.dw_custom_log.toggleViewAction())
        if self.dw_basic_serial: self.view_menu.addAction(self.dw_basic_serial.toggleViewAction())
        self.view_menu.addSeparator()

        theme_menu = self.view_menu.addMenu("背景样式")
        for theme_name in Constants.THEME_OPTIONS:  # Assuming THEME_OPTIONS is defined in constants
            action = QAction(f"{theme_name.replace('_', ' ').capitalize()} 主题", self)
            action.triggered.connect(lambda checked=False, tn=theme_name: self.apply_theme_action(tn))
            theme_menu.addAction(action)
        load_external_qss_action = QAction("加载外部QSS文件...", self)
        load_external_qss_action.triggered.connect(self.load_external_qss_file_action)
        theme_menu.addAction(load_external_qss_action)

        tools_menu = self.menuBar().addMenu("工具(&T)")
        add_parse_panel_action = QAction("添加自定义解析面板...", self);
        add_parse_panel_action.triggered.connect(lambda: self.add_new_parse_panel_action());
        tools_menu.addAction(add_parse_panel_action)
        add_send_panel_action = QAction("添加自定义发送面板...", self);
        add_send_panel_action.triggered.connect(lambda: self.add_new_send_panel_action());
        tools_menu.addAction(add_send_panel_action)
        tools_menu.addSeparator()
        add_plot_action = QAction("添加波形图窗口(&P)", self);
        add_plot_action.setEnabled(PYQTGRAPH_AVAILABLE);
        add_plot_action.triggered.connect(lambda: self.add_new_plot_widget_action(from_config=False));
        tools_menu.addAction(add_plot_action)
        clear_all_plots_action = QAction("清空所有波形图", self);
        clear_all_plots_action.setEnabled(PYQTGRAPH_AVAILABLE);
        clear_all_plots_action.triggered.connect(self.clear_all_plots_action);
        tools_menu.addAction(clear_all_plots_action)
        tools_menu.addSeparator()
        self.start_raw_record_action = QAction("开始原始数据录制", self);
        self.start_raw_record_action.setCheckable(True);
        self.start_raw_record_action.triggered.connect(self.toggle_raw_data_recording_action);
        tools_menu.addAction(self.start_raw_record_action)
        tools_menu.addSeparator()
        show_stats_action = QAction("显示统计信息...", self);
        show_stats_action.triggered.connect(self.show_statistics_action);
        tools_menu.addAction(show_stats_action)
        reset_stats_action = QAction("重置统计信息", self);
        reset_stats_action.triggered.connect(self.protocol_analyzer.reset_statistics);
        tools_menu.addAction(reset_stats_action)

    @Slot()
    def update_current_configs_from_ui_panel(self):
        """Called when config in SerialConfigDefinitionPanelWidget changes."""
        if not self.serial_config_panel_widget: return
        self.current_serial_config = self.serial_config_panel_widget.get_serial_config_from_ui()
        self.current_frame_config = self.serial_config_panel_widget.get_frame_config_from_ui()
        self.active_checksum_mode = self.serial_config_panel_widget.get_checksum_mode_from_ui()
        if self.error_logger:
            self.error_logger.log_debug(
                f"Main configs updated from panel. Serial: {vars(self.current_serial_config)}, Frame: {vars(self.current_frame_config)}, Checksum: {self.active_checksum_mode.name}")

    def apply_loaded_config_to_ui(self) -> None:
        # Update master config objects first from the loaded self.current_config
        self.current_serial_config = SerialPortConfig(**self.current_config.get("serial_port", {}))
        self.current_frame_config = FrameConfig(**self.current_config.get("frame_definition", {}))
        checksum_mode_name = self.current_config.get("checksum_mode", Constants.DEFAULT_CHECKSUM_MODE.name)
        try:
            self.active_checksum_mode = ChecksumMode[checksum_mode_name]
        except KeyError:
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
            if self.error_logger: self.error_logger.log_warning(
                f"Invalid checksum_mode '{checksum_mode_name}' in config, using default.")

        # Apply to SerialConfigDefinitionPanelWidget (it will set its own UI elements)
        if self.serial_config_panel_widget:
            self.serial_config_panel_widget.update_ui_from_main_configs(
                self.current_serial_config,
                self.current_frame_config,
                self.active_checksum_mode
            )
        # Apply to CustomLogPanelWidget
        if self.custom_log_panel_widget:
            self.custom_log_panel_widget.apply_config(self.current_config.get("custom_log_panel", {}))
        # Apply to BasicCommPanelWidget
        if self.basic_comm_panel_widget:
            self.basic_comm_panel_widget.apply_config(self.current_config.get("basic_comm_panel", {}))

        loaded_theme_info = self.current_config.get("ui_theme_info",
                                                    {"type": "internal", "name": "light", "path": None})
        if loaded_theme_info["type"] == "internal" and loaded_theme_info.get("name"):
            self.theme_manager.apply_theme(loaded_theme_info["name"])
        elif loaded_theme_info["type"] == "external" and loaded_theme_info.get("path"):
            self.theme_manager.apply_external_qss(loaded_theme_info["path"])
        else:
            self.theme_manager.apply_theme("light")

        self._clear_all_parse_panels()
        parse_panel_configs = self.current_config.get("parse_panels", [])
        migrated_old_parse = False
        if not parse_panel_configs and "receive_containers" in self.current_config:  # Migration
            self.add_new_parse_panel_action(config={
                "parse_func_id": self.current_config.get("parse_func_id", "C1"),
                "data_mapping_mode": self.current_config.get("data_mapping_mode", "顺序填充 (Sequential)"),
                "receive_containers": self.current_config.get("receive_containers", []),
                "dock_name": self.current_config.get("parse_panel_dock_name", "默认解析面板 (旧)")
                # Use saved dock_name if available
            }, from_config=True, is_migration=True)
            migrated_old_parse = True
        elif parse_panel_configs:
            for panel_cfg in parse_panel_configs: self.add_new_parse_panel_action(config=panel_cfg, from_config=True)

        # If still no parse panels after load/migration, create a default one.
        if not self.parse_panel_docks and not migrated_old_parse:
            self.add_new_parse_panel_action(panel_name_suggestion="默认解析面板 1", from_config=True)

        self._clear_all_send_panels()
        send_panel_configs = self.current_config.get("send_panels", [])
        migrated_old_send = False
        if not send_panel_configs and "send_containers" in self.current_config:  # Migration
            migrated_send_cfg = {
                "panel_func_id": self.current_frame_config.func_id,
                "send_containers": self.current_config.get("send_containers", []),
                "dock_name": self.current_config.get("send_panel_dock_name",
                                                     "默认发送面板 (旧)")}  # Use saved dock_name
            self.add_new_send_panel_action(config=migrated_send_cfg, from_config=True, is_migration=True)
            migrated_old_send = True
        elif send_panel_configs:
            for panel_cfg in send_panel_configs: self.add_new_send_panel_action(config=panel_cfg, from_config=True)

        # If still no send panels after load/migration, create a default one.
        if not self.send_panel_docks and not migrated_old_send:
            self.add_new_send_panel_action(panel_name_suggestion="默认发送面板 1", from_config=True)

        # Plots are loaded in _init_ui_dockable_layout
        # We just need to make sure their plot targets are updated after parse panels are loaded
        self.update_all_parse_panels_plot_targets()
        if self.error_logger: self.error_logger.log_info("配置已加载并应用到UI。")

    def gather_current_ui_config(self) -> Dict[str, Any]:
        # Get latest values from the SerialConfigDefinitionPanelWidget
        if self.serial_config_panel_widget:
            self.current_serial_config = self.serial_config_panel_widget.get_serial_config_from_ui()
            self.current_frame_config = self.serial_config_panel_widget.get_frame_config_from_ui()
            self.active_checksum_mode = self.serial_config_panel_widget.get_checksum_mode_from_ui()

        parse_panel_configs_list = [p.get_config() for p in self.parse_panel_widgets.values()]
        send_panel_configs_list = [p.get_panel_config() for p in self.send_panel_widgets.values()]
        # For plot_configs, ensure 'dock_name' is saved if that's used for restoring titles.
        # PlotWidgetContainer.get_config() would need to provide this if desired.
        # Assuming PlotWidgetContainer has a plot_name and the dock widget title is derived from it.
        plot_configs = []
        for pid, p_container in self.plot_widgets_map.items():
            dock = self.plot_docks_map.get(pid)
            plot_cfg = {"id": pid, "name": p_container.plot_name}
            if dock:
                plot_cfg["dock_name"] = dock.windowTitle()
            plot_configs.append(plot_cfg)

        config_data = {
            "serial_port": vars(self.current_serial_config),
            "frame_definition": vars(self.current_frame_config),
            "checksum_mode": self.active_checksum_mode.name,
            "ui_theme_info": self.theme_manager.current_theme_info,
            "parse_panels": parse_panel_configs_list,
            "send_panels": send_panel_configs_list,
            "plot_configs": plot_configs,
            "custom_log_panel": self.custom_log_panel_widget.get_config() if self.custom_log_panel_widget else {},
            "basic_comm_panel": self.basic_comm_panel_widget.get_config() if self.basic_comm_panel_widget else {},
            "window_geometry": self.saveGeometry().toBase64().data().decode(),
            "window_state": self.saveState().toBase64().data().decode(),
        }
        return config_data

    @Slot(bool)
    def toggle_connection_action_handler(self, connect_request: bool):
        if connect_request:
            if not self.serial_manager.is_connected:
                self.update_current_configs_from_ui_panel()
                if not self.current_serial_config.port_name or self.current_serial_config.port_name == "无可用端口":
                    QMessageBox.warning(self, "连接错误", "未选择有效的串口。")
                    if self.serial_config_panel_widget: self.serial_config_panel_widget.connect_button.setChecked(False)
                    return
                self.serial_manager.connect_port(self.current_serial_config)
                if self.serial_manager.is_connected:
                    self.frame_parser.clear_buffer(); self._parsed_frame_count = 0
                else:
                    if self.serial_config_panel_widget: self.serial_config_panel_widget.connect_button.setChecked(False)
        else:
            if self.serial_manager.is_connected: self.serial_manager.disconnect_port()

    @Slot()
    def populate_serial_ports_ui(self) -> None:
        available_ports = self.serial_manager.get_available_ports()
        # Ensure current_serial_config is up-to-date if called before config load (e.g. initial refresh)
        if hasattr(self, 'current_serial_config') and self.serial_config_panel_widget:
            self.serial_config_panel_widget.update_port_combo_display(available_ports,
                                                                      self.current_serial_config.port_name)
        elif self.serial_config_panel_widget:  # Fallback if current_serial_config not fully ready
            self.serial_config_panel_widget.update_port_combo_display(available_ports, None)
        self.update_port_status_ui(self.serial_manager.is_connected)

    def update_port_status_ui(self, connected: bool) -> None:
        if self.serial_config_panel_widget:
            self.serial_config_panel_widget.set_connection_status_display(connected)
        for panel in self.send_panel_widgets.values():
            panel.send_frame_button_panel.setEnabled(connected)
        if self.basic_comm_panel_widget:
            self.basic_comm_panel_widget.set_send_enabled(connected)

        if hasattr(self, 'status_bar_label'):
            if not connected and self.serial_config_panel_widget and \
                    (not self.serial_config_panel_widget.port_combo.count() or \
                     self.serial_config_panel_widget.port_combo.currentText() == "无可用端口"):
                self.status_bar_label.setText("无可用串口")
            # else: self.status_bar_label.setText("已连接" if connected else "未连接") # This is handled by on_serial_connection_status_changed

    @Slot(str, bool)
    def send_basic_serial_data_action(self, text_to_send: str, is_hex: bool) -> None:
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "串口未打开。")
            if self.basic_comm_panel_widget: self.basic_comm_panel_widget.append_receive_text("错误: 串口未打开。\n")
            return
        if not text_to_send: return
        data_to_write = QByteArray()
        if is_hex:
            hex_clean = "".join(text_to_send.replace("0x", "").replace("0X", "").split())
            if len(hex_clean) % 2 != 0: hex_clean = "0" + hex_clean
            try:
                data_to_write = QByteArray.fromHex(hex_clean.encode('ascii'))
            except ValueError:
                msg = f"Hex发送错误: '{text_to_send}' 包含无效Hex字符."
                QMessageBox.warning(self, "Hex格式错误", msg)
                if self.basic_comm_panel_widget: self.basic_comm_panel_widget.append_receive_text(f"错误: {msg}\n")
                return
        else:
            data_to_write.append(text_to_send.encode('utf-8', errors='replace'))
        if data_to_write:
            bytes_written = self.serial_manager.write_data(data_to_write)
            if bytes_written == data_to_write.size():  # Use .size() for QByteArray
                display_sent_data = data_to_write.toHex(' ').data().decode('ascii').upper() if is_hex else text_to_send
                if len(display_sent_data) > 60: display_sent_data = display_sent_data[:60] + "..."
                if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(
                    f"基本发送 {bytes_written} 字节: {display_sent_data}")
                if self.error_logger: self.error_logger.log_info(f"基本发送 {bytes_written} 字节")
                self._append_to_basic_receive(data_to_write, source="TX")
                self.data_recorder.record_raw_frame(datetime.now(), data_to_write.data(), "TX (Basic)")

    def _append_to_basic_receive(self, data: QByteArray, source: str = "RX"):
        if not self.basic_comm_panel_widget: return
        final_log_string = ""
        if self.basic_comm_panel_widget.recv_timestamp_checkbox.isChecked():
            final_log_string += datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] "
        final_log_string += f"{source}: "
        if self.basic_comm_panel_widget.recv_hex_checkbox.isChecked():
            final_log_string += data.toHex(' ').data().decode('ascii', errors='ignore').upper()
        else:
            try:
                final_log_string += data.data().decode('utf-8')
            except UnicodeDecodeError:
                try:
                    final_log_string += data.data().decode('gbk', errors='replace')
                except UnicodeDecodeError:
                    final_log_string += data.data().decode('latin-1', errors='replace')
        if not final_log_string.endswith('\n'): final_log_string += '\n'
        self.basic_comm_panel_widget.append_receive_text(final_log_string)

    def _append_to_custom_protocol_log_formatted(self, timestamp: datetime, source: str, content: str,
                                                 is_content_hex: bool):
        if not self.custom_log_panel_widget: return
        final_log_string = ""
        if self.custom_log_panel_widget.timestamp_checkbox.isChecked():
            final_log_string += timestamp.strftime("[%H:%M:%S.%f")[:-3] + "] "
        final_log_string += f"{source}: "

        # If the custom log panel's hex checkbox is checked, we assume 'content' should be hex.
        # If 'is_content_hex' is True, 'content' is already hex.
        # If checkbox is checked but 'is_content_hex' is False, this implies 'content' might be raw bytes needing hex conversion.
        # This logic can be complex. For now, assuming 'content' is mostly ready.
        # A more robust solution would involve passing raw QByteArray to CustomLogPanelWidget and letting it format.
        if self.custom_log_panel_widget.hex_checkbox.isChecked():
            if not is_content_hex:  # If content is not already hex but should be
                try:  # Try to interpret content as bytes then hexify (this is speculative)
                    final_log_string += QByteArray(content.encode('latin-1')).toHex(' ').data().decode().upper()
                except:
                    final_log_string += content  # Fallback to content as is
            else:
                final_log_string += content  # Content is already hex
        else:  # Not hex display
            if is_content_hex:  # If content is hex but should be text (needs de-hexify or indicate it's hex)
                final_log_string += content  # Show hex as is, or attempt to de-hexify if possible
            else:
                final_log_string += content  # Content is already text

        if not final_log_string.endswith('\n'): final_log_string += '\n'
        self.custom_log_panel_widget.append_log(final_log_string)

    @Slot(QByteArray)
    def on_serial_data_received(self, data: QByteArray):
        self._append_to_basic_receive(data, source="RX")
        self.data_recorder.record_raw_frame(datetime.now(), data.data(), "RX")
        self.frame_parser.append_data(data)
        self.update_current_configs_from_ui_panel()  # Get latest frame config from panel
        current_ui_checksum_mode = self.active_checksum_mode
        self.frame_parser.try_parse_frames(self.current_frame_config, current_ui_checksum_mode)

    @Slot(str, QByteArray)
    def on_frame_successfully_parsed(self, func_id_hex: str, data_payload_ba: QByteArray):
        self._parsed_frame_count += 1
        hex_payload_str = data_payload_ba.toHex(' ').data().decode('ascii').upper()
        self._append_to_custom_protocol_log_formatted(datetime.now(), "RX Parsed",
                                                      f"FID:{func_id_hex} Payload:{hex_payload_str}", True)
        msg = f"成功解析帧: #{self._parsed_frame_count}, FID: {func_id_hex.upper()}"
        if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(msg)
        if self.error_logger: self.error_logger.log_info(f"{msg} Payload len: {data_payload_ba.size()}")
        self.protocol_analyzer.analyze_frame(data_payload_ba, 'rx')
        dispatched_to_a_panel = False
        for panel_widget in self.parse_panel_widgets.values():
            if func_id_hex.upper() == panel_widget.get_target_func_id().upper():
                panel_widget.dispatch_data(data_payload_ba);
                dispatched_to_a_panel = True
        if not dispatched_to_a_panel and self.error_logger: self.error_logger.log_debug(
            f"Frame FID {func_id_hex} no target panel.")

    def eventFilter(self, watched_object: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close:
            processed = False
            for dock_map, remove_method in [
                (self.plot_docks_map, self.remove_plot_widget_and_update),
                (self.parse_panel_docks, self.remove_parse_panel_and_update),
                (self.send_panel_docks, self.remove_send_panel_and_update)
            ]:
                for item_id, dock in list(dock_map.items()):
                    if dock == watched_object:
                        remove_method(item_id, dock)
                        processed = True
                        break
                if processed: break
            if processed: event.accept(); return True
        return super().eventFilter(watched_object, event)

    def restore_geometry_and_state(self) -> None:
        geom_b64 = self.current_config.get("window_geometry")
        state_b64 = self.current_config.get("window_state")
        if geom_b64:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geom_b64.encode()))
            except Exception as e:
                if self.error_logger: self.error_logger.log_warning(f"Error restoring geometry: {e}")
        if state_b64:
            try:
                self.restoreState(QByteArray.fromBase64(state_b64.encode()))
            except Exception as e:
                if self.error_logger: self.error_logger.log_warning(f"Error restoring state: {e}")

    def remove_plot_widget_and_update(self, plot_id_to_remove: int, associated_dock_widget: QDockWidget):
        self.plot_widgets_map.pop(plot_id_to_remove, None)
        self.plot_docks_map.pop(plot_id_to_remove, None)
        if hasattr(self, 'view_menu') and self.view_menu and associated_dock_widget:
            view_action = associated_dock_widget.toggleViewAction()
            if view_action: self.view_menu.removeAction(view_action)
        if associated_dock_widget: associated_dock_widget.deleteLater()
        self.update_all_parse_panels_plot_targets()
        if self.error_logger: self.error_logger.log_info(
            f"Removed plot widget ID: {plot_id_to_remove}, Name: '{associated_dock_widget.windowTitle()}'")

    def remove_parse_panel_and_update(self, panel_id_to_remove: int, associated_dock_widget: QDockWidget):
        panel_widget = self.parse_panel_widgets.pop(panel_id_to_remove, None)
        self.parse_panel_docks.pop(panel_id_to_remove, None)
        if hasattr(self, 'view_menu') and self.view_menu and associated_dock_widget:
            view_action = associated_dock_widget.toggleViewAction()
            if view_action: self.view_menu.removeAction(view_action)
        if panel_widget: panel_widget.deleteLater()
        if associated_dock_widget: associated_dock_widget.deleteLater()
        if self.error_logger: self.error_logger.log_info(
            f"Removed parse panel ID: {panel_id_to_remove}, Name: '{associated_dock_widget.windowTitle()}'")

    def remove_send_panel_and_update(self, panel_id_to_remove: int, associated_dock_widget: QDockWidget):
        panel_widget = self.send_panel_widgets.pop(panel_id_to_remove, None)
        self.send_panel_docks.pop(panel_id_to_remove, None)
        if hasattr(self, 'view_menu') and self.view_menu and associated_dock_widget:
            view_action = associated_dock_widget.toggleViewAction()
            if view_action: self.view_menu.removeAction(view_action)
        if panel_widget: panel_widget.deleteLater()
        if associated_dock_widget: associated_dock_widget.deleteLater()
        if self.error_logger: self.error_logger.log_info(
            f"Removed send panel ID: {panel_id_to_remove}, Name: '{associated_dock_widget.windowTitle()}'")

    def load_configuration_action(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "加载配置文件", "", "JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            temp_loader = ConfigManager(filename=file_path, error_logger=self.error_logger)
            loaded_cfg = temp_loader.load_config()
            if loaded_cfg != temp_loader.default_config or Path(file_path).exists():
                self.current_config = loaded_cfg;
                self.apply_loaded_config_to_ui()
                QMessageBox.information(self, "配置加载", f"配置已从 '{file_path}' 加载。")
            else:
                QMessageBox.warning(self, "配置加载", f"无法从 '{file_path}' 加载有效配置。")

    def save_configuration_action(self) -> None:
        current_config_path = self.config_manager.config_file
        file_path, _ = QFileDialog.getSaveFileName(self, "保存配置文件", str(current_config_path),
                                                   "JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            current_ui_cfg = self.gather_current_ui_config()
            temp_saver = ConfigManager(filename=file_path, error_logger=self.error_logger)
            temp_saver.save_config(current_ui_cfg)
            QMessageBox.information(self, "配置保存", f"配置已保存到 {file_path}。")

    def apply_theme_action(self, theme_name: str) -> None:
        self.theme_manager.apply_theme(theme_name)

    def load_external_qss_file_action(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择QSS样式文件", "", "QSS 文件 (*.qss);;所有文件 (*)")
        if file_path: self.theme_manager.apply_external_qss(file_path)

    def export_parsed_data_action(self) -> None:
        if not self.data_recorder.historical_data: QMessageBox.information(self, "导出数据",
                                                                           "没有可导出的已解析数据。"); return
        path, _ = QFileDialog.getSaveFileName(self, "保存已解析数据", "", "CSV 文件 (*.csv)")
        if path:
            if self.data_recorder.export_parsed_data_to_csv(path):
                QMessageBox.information(self, "导出成功", f"数据已成功导出到:\n{path}")
            else:
                QMessageBox.warning(self, "导出失败", "导出已解析数据失败，请查看日志。")

    def save_raw_recorded_data_action(self) -> None:
        if not self.data_recorder.recorded_raw_data: QMessageBox.information(self, "保存原始数据",
                                                                             "没有已录制的原始数据。"); return
        path, _ = QFileDialog.getSaveFileName(self, "保存原始录制数据", "",
                                              "JSON Log 文件 (*.jsonl *.json);;所有文件 (*)")
        if path: self.data_recorder.save_raw_to_file(path); QMessageBox.information(self, "保存成功",
                                                                                    f"原始录制数据已保存到:\n{path}")

    def show_statistics_action(self) -> None:
        stats = self.protocol_analyzer.get_statistics()
        stats_str_parts = [f"接收总帧数: {stats['total_frames_rx']}", f"发送总帧数: {stats['total_frames_tx']}",
                           f"错误帧数: {stats['error_frames_rx']}", f"接收速率: {stats['data_rate_rx_bps']:.2f} bps",
                           f"总接收字节: {stats['rx_byte_count']} B"]
        QMessageBox.information(self, "协议统计信息", "\n".join(stats_str_parts))

    @Slot(int, int)
    def handle_recv_container_plot_target_change(self, container_id: int, target_plot_id: int) -> None:
        if self.error_logger: self.error_logger.log_info(f"接收容器 {container_id} 目标图更改为 {target_plot_id}")

    @Slot()
    def add_new_plot_widget_action(self, name: Optional[str] = None, plot_id_from_config: Optional[int] = None,
                                   from_config: bool = False) -> None:
        if not PYQTGRAPH_AVAILABLE: QMessageBox.information(self, "提示", "pyqtgraph未安装。"); return
        plot_id_to_use = plot_id_from_config if plot_id_from_config is not None else self._next_plot_id
        while plot_id_to_use in self.plot_widgets_map: plot_id_to_use = self._next_plot_id; self._next_plot_id += 1
        plot_name_input = name
        if not from_config and name is None:
            text, ok = QInputDialog.getText(self, "新波形图", "名称:", QLineEdit.EchoMode.Normal,
                                            f"波形图 {plot_id_to_use}")
            if not ok or not text.strip(): return
            plot_name_input = text.strip()
        elif name is None:
            plot_name_input = f"波形图 {plot_id_to_use}"
        plot_container = PlotWidgetContainer(plot_id_to_use, plot_name_input, self);
        dw_plot = QDockWidget(plot_name_input, self)
        dw_plot.setObjectName(f"PlotDock_{plot_id_to_use}");
        dw_plot.setWidget(plot_container);
        dw_plot.installEventFilter(self)
        all_dyn_docks = (
                    [d for d in self.parse_panel_docks.values()] + [d for d in self.send_panel_docks.values()] + [d for
                                                                                                                  d in
                                                                                                                  self.plot_docks_map.values()])
        if all_dyn_docks:
            self.tabifyDockWidget(all_dyn_docks[-1], dw_plot)
        else:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dw_plot)
        self.plot_widgets_map[plot_id_to_use] = plot_container;
        self.plot_docks_map[plot_id_to_use] = dw_plot
        if plot_id_from_config is None or plot_id_to_use >= self._next_plot_id: self._next_plot_id = plot_id_to_use + 1
        if hasattr(self, 'view_menu'): self.view_menu.addAction(dw_plot.toggleViewAction())
        self.update_all_parse_panels_plot_targets();
        dw_plot.show()
        if not from_config and self.error_logger: self.error_logger.log_info(
            f"添加波形图: ID={plot_id_to_use}, Name='{plot_name_input}'")

    def update_all_parse_panels_plot_targets(self) -> None:
        for panel_widget in self.parse_panel_widgets.values(): panel_widget.update_children_plot_targets()

    @Slot()
    def clear_all_plots_action(self) -> None:
        if not PYQTGRAPH_AVAILABLE: return
        for plot_container in self.plot_widgets_map.values(): plot_container.clear_plot()
        if self.error_logger: self.error_logger.log_info("所有波形图已清空。")

    @Slot(str, QByteArray)
    def on_frame_checksum_error(self, error_message: str, faulty_frame: QByteArray):
        if hasattr(self, 'status_bar_label'): self.status_bar_label.setText("校验和错误!")
        hex_frame_str = faulty_frame.toHex(' ').data().decode('ascii').upper()
        self._append_to_custom_protocol_log_formatted(datetime.now(), "RX Error",
                                                      f"ChecksumError: {error_message} Frame: {hex_frame_str}", True)
        self.protocol_analyzer.analyze_frame(faulty_frame, 'rx', is_error=True)

    @Slot(str, QByteArray)
    def on_frame_general_parse_error(self, error_message: str, buffer_state: QByteArray):
        if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(f"协议解析错误: {error_message}")

    @Slot(str)
    def on_serial_manager_error(self, error_message: str):
        if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(error_message)
        QMessageBox.warning(self, "串口通讯警告", error_message)

    @Slot(bool, str)
    def on_serial_connection_status_changed(self, is_connected: bool, message: str):
        self.update_port_status_ui(is_connected)
        if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(message)
        if not is_connected and "资源错误" in message: QMessageBox.critical(self, "串口错误", message)

    @Slot(bool)
    def toggle_raw_data_recording_action(self, checked: bool):
        if checked:
            self.data_recorder.start_raw_recording();
            self.start_raw_record_action.setText("停止录制");
            if hasattr(self, 'status_bar_label'): self.status_bar_label.setText("录制中...")
        else:
            self.data_recorder.stop_raw_recording();
            self.start_raw_record_action.setText("开始录制");
            if hasattr(self, 'status_bar_label'): self.status_bar_label.setText("录制停止。")
            if self.data_recorder.recorded_raw_data:
                if QMessageBox.question(self, "保存数据", "保存已录制的原始数据?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
                    self.save_raw_recorded_data_action()

    def closeEvent(self, event: Any) -> None:
        if self.error_logger: self.error_logger.log_info("关闭应用程序。")
        if self.serial_manager.is_connected: self.serial_manager.disconnect_port()
        if self.data_recorder.recording_raw: self.data_recorder.stop_raw_recording()
        current_ui_cfg = self.gather_current_ui_config()
        self.config_manager.save_config(current_ui_cfg)
        if self.error_logger: self.error_logger.log_info("配置已自动保存。")
        event.accept()

    def _clear_all_parse_panels(self):
        for panel_id in list(self.parse_panel_docks.keys()):
            dock = self.parse_panel_docks.get(panel_id)
            if dock: self.remove_parse_panel_and_update(panel_id, dock)
        self._next_parse_panel_id = 1;
        self._next_global_receive_container_id = 1

    def _clear_all_send_panels(self):
        for panel_id in list(self.send_panel_docks.keys()):
            dock = self.send_panel_docks.get(panel_id)
            if dock: self.remove_send_panel_and_update(panel_id, dock)
        self._next_send_panel_id = 1

    @Slot()
    def add_new_send_panel_action(self, config: Optional[Dict] = None, from_config: bool = False,
                                  panel_name_suggestion: Optional[str] = None, is_migration: bool = False):
        panel_id_to_use = self._next_send_panel_id
        self._next_send_panel_id += 1
        actual_panel_name = panel_name_suggestion
        if config and config.get("dock_name"):
            actual_panel_name = config["dock_name"]
        elif not actual_panel_name:
            default_func_id_for_name = config.get("panel_func_id",
                                                  f"S{panel_id_to_use}") if config else f"S{panel_id_to_use}"
            actual_panel_name = f"发送面板 {panel_id_to_use} (ID: {default_func_id_for_name.upper()})"
        if not from_config:
            text, ok = QInputDialog.getText(self, "新建发送面板", "名称:", QLineEdit.EchoMode.Normal, actual_panel_name)
            if not ok or not text.strip(): self._next_send_panel_id -= 1; return
            actual_panel_name = text.strip()
        panel_widget = SendPanelWidget(panel_id_to_use, main_window_ref=self, initial_config=config)
        if hasattr(panel_widget, 'send_data_group'): actual_panel_name = panel_widget.send_data_group.title()
        dw_send_panel = QDockWidget(actual_panel_name, self)
        dw_send_panel.setObjectName(f"SendPanelDock_{panel_id_to_use}");
        dw_send_panel.setWidget(panel_widget);
        dw_send_panel.installEventFilter(self)
        existing_send_docks = [self.send_panel_docks.get(pid) for pid in sorted(self.send_panel_docks.keys()) if
                               pid in self.send_panel_docks]
        if not existing_send_docks:
            if self.dw_serial_config:
                self.tabifyDockWidget(self.dw_serial_config, dw_send_panel)
            else:
                self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dw_send_panel)
        else:
            self.tabifyDockWidget(existing_send_docks[-1], dw_send_panel)
        self.send_panel_widgets[panel_id_to_use] = panel_widget;
        self.send_panel_docks[panel_id_to_use] = dw_send_panel
        if hasattr(self, 'view_menu'): self.view_menu.addAction(dw_send_panel.toggleViewAction())
        dw_send_panel.show()
        if self.error_logger: self.error_logger.log_info(
            f"Added Send Panel: ID={panel_id_to_use}, Name='{actual_panel_name}'")

    @Slot()
    def add_new_parse_panel_action(self, config: Optional[Dict] = None, from_config: bool = False,
                                   panel_name_suggestion: Optional[str] = None, is_migration: bool = False):
        panel_id_to_use = self._next_parse_panel_id
        self._next_parse_panel_id += 1
        actual_panel_name = panel_name_suggestion
        if config and config.get("dock_name"):
            actual_panel_name = config["dock_name"]
        elif not actual_panel_name:
            default_parse_id_for_name = config.get("parse_func_id",
                                                   f"P{panel_id_to_use}") if config else f"P{panel_id_to_use}"
            actual_panel_name = f"解析面板 {panel_id_to_use} (ID: {default_parse_id_for_name.upper()})"
        if not from_config:
            text, ok = QInputDialog.getText(self, "新建解析面板", "名称:", QLineEdit.EchoMode.Normal, actual_panel_name)
            if not ok or not text.strip(): self._next_parse_panel_id -= 1; return
            actual_panel_name = text.strip()
        panel_widget = ParsePanelWidget(panel_id_to_use, main_window_ref=self, initial_config=config)
        if hasattr(panel_widget, 'recv_display_group'): actual_panel_name = panel_widget.recv_display_group.title()
        dw_parse_panel = QDockWidget(actual_panel_name, self)
        dw_parse_panel.setObjectName(f"ParsePanelDock_{panel_id_to_use}");
        dw_parse_panel.setWidget(panel_widget);
        dw_parse_panel.installEventFilter(self)
        all_dyn_docks = (
                    [d for d in self.parse_panel_docks.values()] + [d for d in self.send_panel_docks.values()] + [d for
                                                                                                                  d in
                                                                                                                  self.plot_docks_map.values()])
        if all_dyn_docks:
            self.tabifyDockWidget(all_dyn_docks[-1], dw_parse_panel)
        else:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dw_parse_panel)
        self.parse_panel_widgets[panel_id_to_use] = panel_widget;
        self.parse_panel_docks[panel_id_to_use] = dw_parse_panel
        if hasattr(self, 'view_menu'): self.view_menu.addAction(dw_parse_panel.toggleViewAction())
        panel_widget.update_children_plot_targets();
        dw_parse_panel.show()
        if self.error_logger: self.error_logger.log_info(
            f"Added Parse Panel: ID={panel_id_to_use}, Name='{actual_panel_name}'")

    # ... (ensure _assemble_custom_frame is complete as per previous fix)
    def _assemble_custom_frame(self, panel_target_func_id_str: str,
                               panel_send_data_containers: List[SendDataContainerWidget]) -> Optional[QByteArray]:
        # This should be the full implementation from the previous fix
        cfg = self.current_frame_config
        try:
            head_ba = QByteArray.fromHex(cfg.head.encode('ascii'))
            saddr_ba = QByteArray.fromHex(cfg.s_addr.encode('ascii'))
            daddr_ba = QByteArray.fromHex(cfg.d_addr.encode('ascii'))
            id_ba = QByteArray.fromHex(panel_target_func_id_str.encode('ascii'))
        except ValueError as e:
            msg = f"帧头/地址/面板功能码({panel_target_func_id_str}) Hex格式错误: {e}"
            if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(msg)
            if self.error_logger: self.error_logger.log_warning(msg)
            return None
        if not (
                head_ba.size() == 1 and saddr_ba.size() == 1 and daddr_ba.size() == 1 and id_ba.size() == 1):  # Use .size() for QByteArray
            msg = "帧头/地址/面板功能码 Hex长度必须为1字节 (2个Hex字符)"
            if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(msg)
            if self.error_logger: self.error_logger.log_warning(msg)
            return None
        data_content_ba = QByteArray()
        for scw_widget in panel_send_data_containers:
            item_bytes = scw_widget.get_bytes()
            if item_bytes is None:
                msg = f"发送面板(ID:{panel_target_func_id_str}) 项 '{scw_widget.name_edit.text()}' 数值错误"
                if hasattr(self, 'status_bar_label'): self.status_bar_label.setText(msg)
                if self.error_logger: self.error_logger.log_warning(msg)
                return None
            data_content_ba.append(item_bytes)
        len_val = data_content_ba.size()  # Use .size() for QByteArray
        len_ba = QByteArray(struct.pack('<H', len_val))
        frame_part_for_checksum = QByteArray()
        frame_part_for_checksum.append(head_ba);
        frame_part_for_checksum.append(saddr_ba);
        frame_part_for_checksum.append(daddr_ba)
        frame_part_for_checksum.append(id_ba);
        frame_part_for_checksum.append(len_ba);
        frame_part_for_checksum.append(data_content_ba)
        checksum_bytes_to_append = QByteArray()
        active_mode = self.active_checksum_mode
        sum_check_text = "";
        add_check_text = ""
        if active_mode == ChecksumMode.CRC16_CCITT_FALSE:
            crc_val = calculate_frame_crc16(frame_part_for_checksum)
            checksum_bytes_to_append.append(struct.pack('>H', crc_val))
            sum_check_text = f"0x{crc_val:04X}"
        else:
            sc_val, ac_val = calculate_original_checksums_python(frame_part_for_checksum)
            checksum_bytes_to_append.append(bytes([sc_val]));
            checksum_bytes_to_append.append(bytes([ac_val]))
            sum_check_text = f"0x{sc_val:02X}";
            add_check_text = f"0x{ac_val:02X}"
        if self.serial_config_panel_widget:
            self.serial_config_panel_widget.update_checksum_display(sum_check_text, add_check_text)
        final_frame = QByteArray(frame_part_for_checksum);
        final_frame.append(checksum_bytes_to_append)
        return final_frame



    def _setup_application_icon(self,window, icon_filename):
        """
        设置应用程序窗口的图标。

        参数:
            window: PyQt5窗口对象，例如QMainWindow或QWidget。
            icon_filename: 图标文件的文件名，例如"app_icon.png"。
        """
        try:
            # 获取脚本所在目录
            script_dir = Path(__file__).resolve().parent
            # 构建图标文件的完整路径
            icon_path = script_dir / icon_filename

            if icon_path.exists():
                # 如果图标文件存在，设置窗口图标
                app_icon = QIcon(str(icon_path))  # QIcon 需要字符串路径
                window.setWindowIcon(app_icon)
            else:
                # 如果图标文件未找到，记录警告
                if hasattr(window, 'error_logger') and window.error_logger:
                    window.error_logger.log_warning(f"应用程序图标文件未找到: {icon_path}")
                else:
                    print(f"警告: 应用程序图标文件未找到: {icon_path}")
        except Exception as e:
            # 记录设置图标时可能发生的任何其他错误
            if hasattr(window, 'error_logger') and window.error_logger:
                window.error_logger.log_error(f"设置应用程序图标时出错: {e}")
            else:
                print(f"错误: 设置应用程序图标时出错: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = SerialDebugger()
    main_win.show()
    sys.exit(app.exec())