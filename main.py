import struct
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QMessageBox, QGroupBox, QScrollArea, QFileDialog,
    QDialog, QDialogButtonBox, QPlainTextEdit, QInputDialog,
    QDockWidget, QTabWidget
)
from PySide6.QtCore import Slot, QByteArray, Qt, QEvent, QObject
from PySide6.QtGui import QAction, QTextCursor

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
from core.protocol_handler import ProtocolAnalyzer, FrameParser, get_data_type_byte_length, calculate_checksums, \
    calculate_frame_crc16, calculate_original_checksums_python
from core.data_recorder import DataRecorder


# --- ParsePanelWidget Class (from previous refactoring) ---
class ParsePanelWidget(QWidget):
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
            self.parse_id_edit.setText(f"C{self.panel_id}")  # Default parse ID
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
        if dock:
            dock.setWindowTitle(new_title)

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
            if PYQTGRAPH_AVAILABLE and container.plot_checkbox:
                container.plot_checkbox.setChecked(config.get("plot_enabled", False))

        self.recv_containers_layout.addWidget(container)
        self.receive_data_containers.append(container)
        self.remove_recv_container_button.setEnabled(True)

        targets_for_dropdown = {pid: pw.plot_name for pid, pw in self.main_window_ref.plot_widgets_map.items()}
        container.update_plot_targets(targets_for_dropdown)

        if config and PYQTGRAPH_AVAILABLE and container.plot_target_combo:
            plot_target_id = config.get("plot_target_id")
            if plot_target_id is not None:
                idx = container.plot_target_combo.findData(plot_target_id)
                if idx != -1:
                    container.plot_target_combo.setCurrentIndex(idx)
                container.plot_target_combo.setEnabled(
                    container.plot_checkbox.isChecked() and bool(targets_for_dropdown))

        if not silent and self.error_logger:
            self.error_logger.log_info(f"Parse Panel {self.panel_id}: Added receive container {container_id}")

    def remove_receive_data_container(self, silent: bool = False) -> None:
        if self.receive_data_containers:
            container_to_remove = self.receive_data_containers.pop()
            container_id_removed = container_to_remove.container_id
            self.recv_containers_layout.removeWidget(container_to_remove)
            container_to_remove.deleteLater()
            self.main_window_ref.clear_plot_curves_for_container(container_id_removed)
            if not self.receive_data_containers:
                self.remove_recv_container_button.setEnabled(False)
            if not silent and self.error_logger:
                self.error_logger.log_info(
                    f"Parse Panel {self.panel_id}: Removed receive container {container_id_removed}")

    def get_target_func_id(self) -> str:
        return self.parse_id_edit.text()

    def dispatch_data(self, data_payload_ba: QByteArray) -> None:
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
                    if current_offset < data_payload_ba.length():
                        segment = data_payload_ba.mid(current_offset)
                        current_offset = data_payload_ba.length()
                elif byte_len > 0:
                    if current_offset + byte_len <= data_payload_ba.length():
                        segment = data_payload_ba.mid(current_offset, byte_len)
                        current_offset += byte_len
                container_widget.set_value(segment, data_type)
                log_key_name = f"P{self.panel_id}_{config['name']}"
                parsed_data_for_log_export[log_key_name] = container_widget.value_edit.text()
                if PYQTGRAPH_AVAILABLE and config["plot_enabled"] and config["plot_target_id"] is not None:
                    target_plot_id = config["plot_target_id"]
                    if target_plot_id in self.main_window_ref.plot_widgets_map:
                        val_float = container_widget.get_value_as_float()
                        if val_float is not None:
                            curve_name = f"P{self.panel_id}:{config['name']}"
                            self.main_window_ref.plot_widgets_map[target_plot_id].update_data(
                                config["id"], val_float, curve_name
                            )
        if parsed_data_for_log_export:
            self.main_window_ref.data_recorder.add_parsed_frame_data(timestamp_now, parsed_data_for_log_export)

    def get_config(self) -> Dict[str, Any]:
        container_configs = [c.get_config() for c in self.receive_data_containers]
        return {
            "panel_id": self.panel_id,
            "parse_func_id": self.parse_id_edit.text(),
            "data_mapping_mode": self.data_mapping_combo.currentText(),
            "receive_containers": container_configs,
        }

    def apply_config(self, config: Dict[str, Any]):
        self.parse_id_edit.setText(config.get("parse_func_id", f"C{self.panel_id}"))
        self._update_panel_title_from_parse_id()
        self.data_mapping_combo.setCurrentText(config.get("data_mapping_mode", "顺序填充 (Sequential)"))
        while self.receive_data_containers:
            self.remove_receive_data_container(silent=True)
        recv_containers_cfg = config.get("receive_containers", [])
        for cfg in recv_containers_cfg:
            self.add_receive_data_container(config=cfg, silent=True)

    def update_children_plot_targets(self):
        targets = {pid: pw.plot_name for pid, pw in self.main_window_ref.plot_widgets_map.items()}
        for container in self.receive_data_containers:
            current_target_id = None
            if container.plot_target_combo and container.plot_target_combo.count() > 0:
                current_target_id_data = container.plot_target_combo.currentData()
                if current_target_id_data is not None:
                    current_target_id = current_target_id_data
            container.update_plot_targets(targets)
            if current_target_id is not None and container.plot_target_combo:
                idx = container.plot_target_combo.findData(current_target_id)
                if idx != -1:
                    container.plot_target_combo.setCurrentIndex(idx)
            if container.plot_checkbox and container.plot_target_combo:
                is_enabled = container.plot_checkbox.isChecked() and bool(targets)
                container.plot_target_combo.setEnabled(is_enabled)


# --- New SendPanelWidget Class ---
class SendPanelWidget(QWidget):
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
            default_func_id = f"C{self.panel_id + 8:X}"
            self.panel_func_id_edit.setText(default_func_id)
            self._update_panel_title()

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
        if dock:
            dock.setWindowTitle(title)

    @Slot()
    def _add_container_action_triggered(self):
        self.add_send_data_container()

    @Slot()
    def _remove_container_action_triggered(self):
        self.remove_send_data_container()

    def add_send_data_container(self, config: Optional[Dict[str, Any]] = None, silent: bool = False):
        container_id = self._next_local_send_container_id
        container = SendDataContainerWidget(container_id, self.main_window_ref)
        if config:
            container.name_edit.setText(config.get("name", f"Data_{container_id}"))
            container.type_combo.setCurrentText(config.get("type", "uint8_t"))
            container.value_edit.setText(config.get("value", ""))

        self.containers_layout.addWidget(container)
        self.send_data_containers.append(container)
        self._next_local_send_container_id += 1
        self.remove_button.setEnabled(True)
        if not silent and self.error_logger:
            self.error_logger.log_info(f"Send Panel {self.panel_id}: Added send data container {container_id}")

    def remove_send_data_container(self, silent: bool = False):
        if self.send_data_containers:
            container_to_remove = self.send_data_containers.pop()
            removed_id = container_to_remove.container_id
            self.containers_layout.removeWidget(container_to_remove)
            container_to_remove.deleteLater()
            if not self.send_data_containers:
                self.remove_button.setEnabled(False)
            if not silent and self.error_logger:
                self.error_logger.log_info(f"Send Panel {self.panel_id}: Removed send data container {removed_id}")

    def get_panel_config(self) -> Dict:
        container_configs = [
            {
                "name": c.name_edit.text(),
                "type": c.type_combo.currentText(),
                "value": c.value_edit.text()
            } for c in self.send_data_containers
        ]
        return {
            "panel_id": self.panel_id,
            "panel_func_id": self.panel_func_id_edit.text(),
            "send_containers": container_configs,
        }

    def apply_panel_config(self, config: Dict):
        self.panel_func_id_edit.setText(config.get("panel_func_id", f"C{self.panel_id + 8:X}"))
        self._update_panel_title()
        while self.send_data_containers:
            self.remove_send_data_container(silent=True)
        container_configs = config.get("send_containers", [])
        for c_cfg in container_configs:
            self.add_send_data_container(config=c_cfg, silent=True)

    @Slot()
    def _trigger_send_frame(self):
        if not self.main_window_ref.serial_manager.is_connected:
            QMessageBox.warning(self.main_window_ref, "警告", "串口未打开。")
            return

        panel_func_id = self.panel_func_id_edit.text()
        if not panel_func_id:
            QMessageBox.warning(self.main_window_ref, "功能码缺失", "请输入此发送面板的目标功能码。")
            return

        self.main_window_ref.update_current_frame_config_from_ui()

        final_frame = self.main_window_ref._assemble_custom_frame(
            panel_target_func_id_str=panel_func_id,
            panel_send_data_containers=self.send_data_containers
        )

        if final_frame:
            bytes_written = self.main_window_ref.serial_manager.write_data(final_frame)
            if bytes_written == len(final_frame):
                hex_frame_str = final_frame.toHex(' ').data().decode('ascii').upper()
                msg = f"发送面板 {self.panel_id} (ID:{panel_func_id}) 发送 {bytes_written} 字节: {hex_frame_str}"
                self.main_window_ref.status_bar_label.setText(msg)
                if self.error_logger: self.error_logger.log_info(msg)

                self.main_window_ref.protocol_analyzer.analyze_frame(final_frame, 'tx')
                self.main_window_ref.data_recorder.record_raw_frame(datetime.now(), final_frame.data(),
                                                                    f"TX (SendPanel {self.panel_id} ID:{panel_func_id})")
                self.main_window_ref._append_to_custom_protocol_log(hex_frame_str, is_hex=True,
                                                                    source=f"TX P{self.panel_id} ID:{panel_func_id}")


class SerialDebugger(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.active_checksum_mode = ChecksumMode.ORIGINAL_SUM_ADD  # Default
        self.app_instance = QApplication.instance()

        self.error_logger = ErrorLogger()
        self.config_manager = ConfigManager(error_logger=self.error_logger)
        self.theme_manager = ThemeManager(self.app_instance, error_logger=self.error_logger)
        self.data_recorder = DataRecorder(error_logger=self.error_logger)
        self.protocol_analyzer = ProtocolAnalyzer(error_logger=self.error_logger)
        self.serial_manager = SerialManager(error_logger=self.error_logger)
        self.frame_parser = FrameParser(error_logger=self.error_logger)

        self.current_config = self.config_manager.load_config()
        self.current_frame_config = FrameConfig(**self.current_config.get("frame_definition", {}))
        self.current_serial_config = SerialPortConfig(**self.current_config.get("serial_port", {}))

        self.setWindowTitle("YJ_tool (Multi-Panel)")
        self.setDockNestingEnabled(True)
        self._parsed_frame_count: int = 0

        self.parse_panel_widgets: Dict[int, ParsePanelWidget] = {}
        self.parse_panel_docks: Dict[int, QDockWidget] = {}
        self._next_parse_panel_id: int = 1
        self._next_global_receive_container_id: int = 1

        self.send_panel_widgets: Dict[int, SendPanelWidget] = {}
        self.send_panel_docks: Dict[int, QDockWidget] = {}
        self._next_send_panel_id: int = 1
        # Note: SendDataContainerWidget IDs are local to each SendPanelWidget now.

        self.plot_widgets_map: Dict[int, PlotWidgetContainer] = {}
        self.plot_docks_map: Dict[int, QDockWidget] = {}
        self._next_plot_id: int = 1

        self.basic_receive_text_edit: Optional[QTextEdit] = None
        self.basic_recv_hex_checkbox: Optional[QCheckBox] = None
        self.basic_recv_timestamp_checkbox: Optional[QCheckBox] = None
        self.basic_send_text_edit: Optional[QLineEdit] = None
        self.basic_send_hex_checkbox: Optional[QCheckBox] = None

        self._init_ui_dockable_layout()
        self.create_menus()
        self.apply_loaded_config_to_ui()

        self.populate_serial_ports_ui()
        self.update_port_status_ui(False)
        self.update_all_parse_panels_plot_targets()

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
        serial_config_widget = self._create_serial_config_panel()
        self.dw_serial_config = QDockWidget("串口与帧定义", self)
        self.dw_serial_config.setObjectName("SerialConfigDock")
        self.dw_serial_config.setWidget(serial_config_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dw_serial_config)

        # Custom Protocol Log and Basic Serial Panels
        custom_protocol_log_widget = self._create_custom_protocol_log_panel()
        self.dw_custom_log = QDockWidget("协议帧原始数据", self)
        self.dw_custom_log.setObjectName("CustomProtocolLogDock")
        self.dw_custom_log.setWidget(custom_protocol_log_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dw_custom_log)

        basic_serial_widget = self._create_basic_serial_panel()
        self.dw_basic_serial = QDockWidget("基本收发", self)
        self.dw_basic_serial.setObjectName("BasicSerialDock")
        self.dw_basic_serial.setWidget(basic_serial_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dw_basic_serial)
        try:
            self.tabifyDockWidget(self.dw_custom_log, self.dw_basic_serial)
        except AttributeError as e:
            self.error_logger.log_warning(f"无法标签页化停靠窗口: {e}")



        # --- Load/Create Parse Panels (before plots for tabify order) ---
        parse_panel_configs = self.current_config.get("parse_panels", [])
        migrated_from_old_parse_config = False  # Flag to avoid double creation

        if not parse_panel_configs and "receive_containers" in self.current_config:  # Check for old format
            # Migrate old single panel config
            self.add_new_parse_panel_action(config={
                "panel_id": 0,  # Or use self._next_parse_panel_id and let the method increment
                "parse_func_id": self.current_config.get("parse_func_id", "C1"),
                "data_mapping_mode": self.current_config.get("data_mapping_mode", "顺序填充 (Sequential)"),
                "receive_containers": self.current_config.get("receive_containers", []),
                "dock_name": "默认解析面板 (旧)"
            }, from_config=True, is_migration=True)
            migrated_from_old_parse_config = True
        elif parse_panel_configs:
            for panel_cfg in parse_panel_configs:
                # Ensure panel_cfg["panel_id"] is handled correctly by add_new_parse_panel_action
                # or that _next_parse_panel_id is updated if IDs from config are reused.
                self.add_new_parse_panel_action(config=panel_cfg, from_config=True)

        # Create a default one ONLY if no panels were loaded from config AND no migration happened
        if not parse_panel_configs and not migrated_from_old_parse_config:
            self.add_new_parse_panel_action(panel_name_suggestion="默认解析面板 1")

        # Load/Create Send Panels
        send_panel_configs = self.current_config.get("send_panels", [])
        if not send_panel_configs and "send_containers" in self.current_config:
            migrated_send_panel_cfg = {
                "panel_id": 0,
                "panel_func_id": self.current_frame_config.func_id if self.current_frame_config.func_id else f"C{self._next_send_panel_id + 7:X}",
                "send_containers": self.current_config.get("send_containers", []),
                "dock_name": "默认发送面板 (旧)"
            }
            self.add_new_send_panel_action(config=migrated_send_panel_cfg, from_config=True, is_migration=True)
        elif send_panel_configs:
            for panel_cfg in send_panel_configs:
                self.add_new_send_panel_action(config=panel_cfg, from_config=True)
        else:
            self.add_new_send_panel_action(panel_name_suggestion="默认发送面板 1")

        # Tabify serial config with the first send panel dock if any send panel exists
        if self.send_panel_docks:
            # Ensure keys are sorted if order matters, though min should find the first created
            first_send_dock_id = min(self.send_panel_docks.keys(), default=None)
            if first_send_dock_id is not None:
                self.tabifyDockWidget(self.dw_serial_config, self.send_panel_docks[first_send_dock_id])

        # Load/Create Plot Panels
        plot_configs = self.current_config.get("plot_configs", [])
        if not plot_configs and PYQTGRAPH_AVAILABLE:
            self.add_new_plot_widget_action(name="主波形图", from_config=False)
        else:
            for plot_cfg in plot_configs:
                self.add_new_plot_widget_action(name=plot_cfg.get("name", f"波形图 {self._next_plot_id}"),
                                                plot_id_from_config=plot_cfg.get("id"),
                                                from_config=True)

        self.status_bar_label = QLabel("未连接")
        self.statusBar().addWidget(self.status_bar_label)

    @Slot()
    def add_new_parse_panel_action(self, config: Optional[Dict] = None, from_config: bool = False,
                                   panel_name_suggestion: Optional[str] = None, is_migration: bool = False):
        panel_id_to_use = self._next_parse_panel_id
        # print(f"DEBUG: add_new_parse_panel_action STARTING. Current _next_parse_panel_id = {self._next_parse_panel_id}. Using panel_id_to_use = {panel_id_to_use}")

        self._next_parse_panel_id += 1
        # print(f"DEBUG: Incremented _next_parse_panel_id to {self._next_parse_panel_id}")

        # --- Determine actual_panel_name ---
        actual_panel_name = panel_name_suggestion  # Start with suggestion
        if config and config.get("dock_name"):
            actual_panel_name = config["dock_name"]
        elif not actual_panel_name:  # If no suggestion and no dock_name in config
            default_parse_id_for_name = config.get("parse_func_id",
                                                   f"P{panel_id_to_use}") if config else f"P{panel_id_to_use}"
            actual_panel_name = f"解析面板 {panel_id_to_use} (ID: {default_parse_id_for_name.upper()})"

        if not from_config:
            text, ok = QInputDialog.getText(self, "新建解析面板", "输入面板名称:", QLineEdit.EchoMode.Normal,
                                            actual_panel_name)
            if not ok or not text.strip():
                self._next_parse_panel_id -= 1  # Rollback ID
                return
            actual_panel_name = text.strip()

        panel_widget = ParsePanelWidget(panel_id_to_use, main_window_ref=self, initial_config=config)
        # After panel_widget is created and config applied, its internal title might be more accurate
        # if the config contained a parse_func_id that changed the title.
        # So, update actual_panel_name for the dock widget from the panel_widget's own title logic.
        if hasattr(panel_widget, 'recv_display_group'):  # Check if the groupbox attribute exists
            actual_panel_name = panel_widget.recv_display_group.title()

        dw_parse_panel = QDockWidget(actual_panel_name, self)
        dw_parse_panel.setObjectName(f"ParsePanelDock_{panel_id_to_use}")
        dw_parse_panel.setWidget(panel_widget)
        dw_parse_panel.installEventFilter(self)

        all_dynamic_docks = []
        all_dynamic_docks.extend([self.parse_panel_docks.get(pid) for pid in sorted(self.parse_panel_docks.keys())])
        all_dynamic_docks.extend([self.send_panel_docks.get(pid) for pid in
                                  sorted(self.send_panel_docks.keys())])  # Also consider send panels
        all_dynamic_docks.extend([self.plot_docks_map.get(pid) for pid in sorted(self.plot_docks_map.keys())])
        all_dynamic_docks = [d for d in all_dynamic_docks if d]

        if all_dynamic_docks:
            self.tabifyDockWidget(all_dynamic_docks[-1], dw_parse_panel)
        else:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dw_parse_panel)

        self.parse_panel_widgets[panel_id_to_use] = panel_widget
        self.parse_panel_docks[panel_id_to_use] = dw_parse_panel

        if hasattr(self, 'view_menu'):
            action = dw_parse_panel.toggleViewAction()
            self.view_menu.addAction(action)

        panel_widget.update_children_plot_targets()
        dw_parse_panel.show()

        # Now actual_panel_name is guaranteed to be defined before this log line
        if self.error_logger:
            self.error_logger.log_info(f"Added Parse Panel: ID={panel_id_to_use}, Name='{actual_panel_name}'")

    def _create_serial_config_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        config_group = QGroupBox("串口配置")
        config_layout = QGridLayout()
        config_layout.addWidget(QLabel("端口:"), 0, 0)
        self.port_combo = QComboBox()
        config_layout.addWidget(self.port_combo, 0, 1)
        config_layout.addWidget(QLabel("波特率:"), 1, 0)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        config_layout.addWidget(self.baud_combo, 1, 1)
        # ... (Data bits, Parity, Stop bits as before) ...
        config_layout.addWidget(QLabel("数据位:"), 2, 0)
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(["8", "7", "6", "5"])
        config_layout.addWidget(self.data_bits_combo, 2, 1)
        config_layout.addWidget(QLabel("校验位:"), 3, 0)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd", "Space", "Mark"])
        config_layout.addWidget(self.parity_combo, 3, 1)
        config_layout.addWidget(QLabel("停止位:"), 4, 0)
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        config_layout.addWidget(self.stop_bits_combo, 4, 1)

        self.refresh_ports_button = QPushButton("刷新")
        self.refresh_ports_button.clicked.connect(self.populate_serial_ports_ui)
        config_layout.addWidget(self.refresh_ports_button, 5, 0)
        self.connect_button = QPushButton("打开串口")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(self.toggle_connection_action)
        config_layout.addWidget(self.connect_button, 5, 1)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        frame_def_group = QGroupBox("全局帧结构定义 (发送用)")  # Title implies these are global defaults
        frame_def_layout = QGridLayout()
        frame_def_layout.addWidget(QLabel("帧头(H)[Hex,1B]:"), 0, 0)
        self.head_edit = QLineEdit()
        self.head_edit.editingFinished.connect(self.update_current_frame_config_from_ui)
        frame_def_layout.addWidget(self.head_edit, 0, 1)
        frame_def_layout.addWidget(QLabel("源地址(S)[Hex,1B]:"), 1, 0)
        self.saddr_edit = QLineEdit()
        self.saddr_edit.editingFinished.connect(self.update_current_frame_config_from_ui)
        frame_def_layout.addWidget(self.saddr_edit, 1, 1)
        frame_def_layout.addWidget(QLabel("目标地址(D)[Hex,1B]:"), 2, 0)
        self.daddr_edit = QLineEdit()
        self.daddr_edit.editingFinished.connect(self.update_current_frame_config_from_ui)
        frame_def_layout.addWidget(self.daddr_edit, 2, 1)

        # The global Send FuncID is now less critical, could be a default/template
        frame_def_layout.addWidget(QLabel("默认发送功能码(ID):"), 3, 0)
        self.id_edit = QLineEdit()  # This is self.current_frame_config.func_id
        self.id_edit.setPlaceholderText("面板可覆盖")
        self.id_edit.editingFinished.connect(self.update_current_frame_config_from_ui)
        frame_def_layout.addWidget(self.id_edit, 3, 1)

        frame_def_layout.addWidget(QLabel("校验模式:"), 6, 0)
        self.checksum_mode_combo = QComboBox()
        self.checksum_mode_combo.addItem("原始校验 (Sum/Add)", ChecksumMode.ORIGINAL_SUM_ADD)
        self.checksum_mode_combo.addItem("CRC-16/CCITT-FALSE", ChecksumMode.CRC16_CCITT_FALSE)
        self.checksum_mode_combo.currentIndexChanged.connect(
            self.update_current_frame_config_from_ui)
        frame_def_layout.addWidget(self.checksum_mode_combo, 6, 1)

        frame_def_layout.addWidget(QLabel("最后帧校验1/CRC高:"), 4, 0)  # Label indicates it's for last sent
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
        return panel

    # _create_send_data_panel is REMOVED (logic moved to SendPanelWidget)
    # _create_custom_protocol_log_panel and _create_basic_serial_panel remain as they are.

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("文件(&F)")
        load_config_action = QAction("加载配置...", self)
        load_config_action.triggered.connect(self.load_configuration_action)
        file_menu.addAction(load_config_action)
        save_config_action = QAction("保存配置...", self)
        save_config_action.triggered.connect(self.save_configuration_action)
        file_menu.addAction(save_config_action)
        file_menu.addSeparator()
        export_parsed_data_action = QAction("导出已解析数据 (CSV)...", self)
        export_parsed_data_action.triggered.connect(self.export_parsed_data_action)
        file_menu.addAction(export_parsed_data_action)
        save_raw_data_action = QAction("保存原始录制数据 (JSON)...", self)
        save_raw_data_action.triggered.connect(self.save_raw_recorded_data_action)
        file_menu.addAction(save_raw_data_action)
        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        self.view_menu = self.menuBar().addMenu("视图(&V)")
        self.view_menu.addAction(self.dw_serial_config.toggleViewAction())
        # self.dw_send_data action removed
        if hasattr(self, 'dw_custom_log') and self.dw_custom_log:
            self.view_menu.addAction(self.dw_custom_log.toggleViewAction())
        if hasattr(self, 'dw_basic_serial') and self.dw_basic_serial:
            self.view_menu.addAction(self.dw_basic_serial.toggleViewAction())
        self.view_menu.addSeparator()  # For dynamic docks (plots, parse, send panels)

        theme_menu = self.view_menu.addMenu("背景样式")
        basic_themes_menu = theme_menu.addMenu("基础主题")
        for theme_name in ["light", "dark"]:
            action = QAction(f"{theme_name.capitalize()} 主题", self)
            action.triggered.connect(lambda checked=False, tn=theme_name: self.apply_theme_action(tn))
            basic_themes_menu.addAction(action)
        custom_theme_menu = theme_menu.addMenu("自定义背景")
        image_theme_action = QAction("图片背景主题", self)
        image_theme_action.triggered.connect(lambda: self.apply_theme_action("custom_image_theme"))
        custom_theme_menu.addAction(image_theme_action)
        load_external_qss_action = QAction("加载外部QSS文件...", self)
        load_external_qss_action.triggered.connect(self.load_external_qss_file_action)
        custom_theme_menu.addAction(load_external_qss_action)

        tools_menu = self.menuBar().addMenu("工具(&T)")
        add_parse_panel_action = QAction("添加自定义解析面板...", self)
        add_parse_panel_action.triggered.connect(lambda: self.add_new_parse_panel_action())
        tools_menu.addAction(add_parse_panel_action)

        add_send_panel_action = QAction("添加自定义发送面板...", self)
        add_send_panel_action.triggered.connect(lambda: self.add_new_send_panel_action())
        tools_menu.addAction(add_send_panel_action)
        tools_menu.addSeparator()

        add_plot_action = QAction("添加波形图窗口(&P)", self)
        add_plot_action.setEnabled(PYQTGRAPH_AVAILABLE)
        add_plot_action.triggered.connect(lambda: self.add_new_plot_widget_action(from_config=False))
        tools_menu.addAction(add_plot_action)
        clear_all_plots_action = QAction("清空所有波形图", self)
        clear_all_plots_action.setEnabled(PYQTGRAPH_AVAILABLE)
        clear_all_plots_action.triggered.connect(self.clear_all_plots_action)
        tools_menu.addAction(clear_all_plots_action)
        tools_menu.addSeparator()

        self.start_raw_record_action = QAction("开始原始数据录制", self)
        self.start_raw_record_action.setCheckable(True)
        self.start_raw_record_action.triggered.connect(self.toggle_raw_data_recording_action)
        tools_menu.addAction(self.start_raw_record_action)
        tools_menu.addSeparator()
        show_stats_action = QAction("显示统计信息...", self)
        show_stats_action.triggered.connect(self.show_statistics_action)
        tools_menu.addAction(show_stats_action)
        reset_stats_action = QAction("重置统计信息", self)
        reset_stats_action.triggered.connect(self.protocol_analyzer.reset_statistics)
        tools_menu.addAction(reset_stats_action)

    def apply_loaded_config_to_ui(self) -> None:
        sp_conf_dict = self.current_config.get("serial_port", {})
        self.current_serial_config = SerialPortConfig(**sp_conf_dict)
        self.baud_combo.setCurrentText(str(self.current_serial_config.baud_rate))
        self.data_bits_combo.setCurrentText(str(self.current_serial_config.data_bits))
        self.parity_combo.setCurrentText(self.current_serial_config.parity)
        self.stop_bits_combo.setCurrentText(str(self.current_serial_config.stop_bits))

        fd_conf_dict = self.current_config.get("frame_definition", {})
        self.current_frame_config = FrameConfig(**fd_conf_dict)
        self.head_edit.setText(self.current_frame_config.head)
        self.saddr_edit.setText(self.current_frame_config.s_addr)
        self.daddr_edit.setText(self.current_frame_config.d_addr)
        self.id_edit.setText(self.current_frame_config.func_id)  # Global/default send FuncID

        loaded_theme_info = self.current_config.get("ui_theme_info",
                                                    {"type": "internal", "name": "light", "path": None})
        # ... (theme application logic as before) ...
        if loaded_theme_info["type"] == "internal" and loaded_theme_info.get("name"):
            self.theme_manager.apply_theme(loaded_theme_info["name"])
        elif loaded_theme_info["type"] == "external" and loaded_theme_info.get("path"):
            self.theme_manager.apply_external_qss(loaded_theme_info["path"])
        else:
            self.theme_manager.apply_theme("light")

        self._clear_all_parse_panels()
        parse_panel_configs = self.current_config.get("parse_panels", [])
        if not parse_panel_configs and "receive_containers" in self.current_config:
            self.add_new_parse_panel_action(config={
                "panel_id": 0, "parse_func_id": self.current_config.get("parse_func_id", "C1"),
                "data_mapping_mode": self.current_config.get("data_mapping_mode", "顺序填充 (Sequential)"),
                "receive_containers": self.current_config.get("receive_containers", []),
                "dock_name": "默认解析面板 (旧)"
            }, from_config=True, is_migration=True)
        elif parse_panel_configs:
            for panel_cfg in parse_panel_configs:
                self.add_new_parse_panel_action(config=panel_cfg, from_config=True)

        self._clear_all_send_panels()
        send_panel_configs = self.current_config.get("send_panels", [])
        if not send_panel_configs and "send_containers" in self.current_config:  # Old global send config
            migrated_send_panel_cfg = {
                "panel_id": 0,
                "panel_func_id": self.current_frame_config.func_id if self.current_frame_config.func_id else f"C{self._next_send_panel_id + 7:X}",
                # Use global func_id
                "send_containers": self.current_config.get("send_containers", []),
                "dock_name": "默认发送面板 (旧)"
            }
            self.add_new_send_panel_action(config=migrated_send_panel_cfg, from_config=True, is_migration=True)
        elif send_panel_configs:
            for panel_cfg in send_panel_configs:
                self.add_new_send_panel_action(config=panel_cfg, from_config=True)

        checksum_mode_name = self.current_config.get("checksum_mode", Constants.DEFAULT_CHECKSUM_MODE.name)
        # ... (checksum mode application logic as before) ...
        try:
            self.active_checksum_mode = ChecksumMode[checksum_mode_name]
        except KeyError:
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
            if self.error_logger:
                self.error_logger.log_warning(f"Invalid checksum_mode '{checksum_mode_name}' in config, using default.")
        idx = self.checksum_mode_combo.findData(self.active_checksum_mode)
        if idx != -1:
            self.checksum_mode_combo.setCurrentIndex(idx)
        else:  # Fallback if findData fails for some reason
            idx_default = self.checksum_mode_combo.findData(Constants.DEFAULT_CHECKSUM_MODE)
            if idx_default != -1: self.checksum_mode_combo.setCurrentIndex(idx_default)

        self.update_all_parse_panels_plot_targets()
        if self.error_logger:
            self.error_logger.log_info("配置已加载并应用到UI。")

    def gather_current_ui_config(self) -> Dict[str, Any]:
        self.update_current_serial_config_from_ui()
        self.update_current_frame_config_from_ui()

        parse_panel_configs_list = []
        for panel_id, dock_widget in self.parse_panel_docks.items():
            panel_widget = self.parse_panel_widgets.get(panel_id)
            if panel_widget:
                panel_cfg = panel_widget.get_config()
                panel_cfg["dock_name"] = dock_widget.windowTitle()
                parse_panel_configs_list.append(panel_cfg)

        send_panel_configs_list = []
        for panel_id, dock_widget in self.send_panel_docks.items():
            panel_widget = self.send_panel_widgets.get(panel_id)
            if panel_widget:
                panel_cfg = panel_widget.get_panel_config()  # Use the correct method name
                panel_cfg["dock_name"] = dock_widget.windowTitle()
                send_panel_configs_list.append(panel_cfg)

        plot_configs = [{"id": pid, "name": pcontainer.plot_name} for pid, pcontainer in self.plot_widgets_map.items()]

        config_data = {
            "serial_port": vars(self.current_serial_config),
            "frame_definition": vars(self.current_frame_config),
            "ui_theme_info": self.theme_manager.current_theme_info,
            "parse_panels": parse_panel_configs_list,
            "send_panels": send_panel_configs_list,
            "window_geometry": self.saveGeometry().toBase64().data().decode(),
            "window_state": self.saveState().toBase64().data().decode(),
            "plot_configs": plot_configs,
            "checksum_mode": self.checksum_mode_combo.currentData().name if isinstance(
                self.checksum_mode_combo.currentData(), ChecksumMode) else Constants.DEFAULT_CHECKSUM_MODE.name
        }
        return config_data

    def eventFilter(self, watched_object: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close:
            # Plot Docks
            plot_id_to_remove = None
            plot_dock_to_remove = None
            for pid, dock in self.plot_docks_map.items():
                if dock == watched_object:
                    plot_id_to_remove = pid
                    plot_dock_to_remove = dock
                    break
            if plot_id_to_remove is not None and plot_dock_to_remove is not None:
                self.remove_plot_widget_and_update(plot_id_to_remove, plot_dock_to_remove)
                event.accept()
                return True

            # Parse Panel Docks
            parse_panel_id_to_remove = None
            parse_dock_to_remove = None
            for panel_id, dock in self.parse_panel_docks.items():
                if dock == watched_object:
                    parse_panel_id_to_remove = panel_id
                    parse_dock_to_remove = dock
                    break
            if parse_panel_id_to_remove is not None and parse_dock_to_remove is not None:
                self.remove_parse_panel_and_update(parse_panel_id_to_remove, parse_dock_to_remove)
                event.accept()
                return True

            # Send Panel Docks
            send_panel_id_to_remove = None
            send_dock_to_remove = None
            for panel_id, dock in self.send_panel_docks.items():
                if dock == watched_object:
                    send_panel_id_to_remove = panel_id
                    send_dock_to_remove = dock
                    break
            if send_panel_id_to_remove is not None and send_dock_to_remove is not None:
                self.remove_send_panel_and_update(send_panel_id_to_remove, send_dock_to_remove)
                event.accept()
                return True

        return super().eventFilter(watched_object, event)

    def remove_send_panel_and_update(self, panel_id_to_remove: int, associated_dock_widget: QDockWidget):
        panel_widget = self.send_panel_widgets.pop(panel_id_to_remove, None)
        self.send_panel_docks.pop(panel_id_to_remove, None)

        if hasattr(self, 'view_menu') and self.view_menu and associated_dock_widget:
            view_action = associated_dock_widget.toggleViewAction()
            if view_action:
                self.view_menu.removeAction(view_action)

        if panel_widget:  # Ensure panel widget itself is cleaned up
            panel_widget.deleteLater()
        if associated_dock_widget:
            associated_dock_widget.deleteLater()

        if self.error_logger:
            self.error_logger.log_info(
                f"Permanently removed send panel ID: {panel_id_to_remove}, Name: '{associated_dock_widget.windowTitle()}'")

    # add_send_data_container and remove_send_data_container are REMOVED from SerialDebugger
    # (functionality moved to SendPanelWidget)

    def _assemble_custom_frame(self, panel_target_func_id_str: str,
                               panel_send_data_containers: List[SendDataContainerWidget]) -> Optional[QByteArray]:
        # Uses global self.current_frame_config for Head, SAddr, DAddr
        # Uses panel_target_func_id_str for FuncID
        # Uses panel_send_data_containers for Data part
        cfg = self.current_frame_config

        try:
            head_ba = QByteArray.fromHex(cfg.head.encode('ascii'))
            saddr_ba = QByteArray.fromHex(cfg.s_addr.encode('ascii'))
            daddr_ba = QByteArray.fromHex(cfg.d_addr.encode('ascii'))
            id_ba = QByteArray.fromHex(panel_target_func_id_str.encode('ascii'))  # Panel specific FuncID
        except ValueError as e:
            msg = f"帧头/地址/面板功能码({panel_target_func_id_str}) Hex格式错误: {e}"
            self.status_bar_label.setText(msg)
            if self.error_logger: self.error_logger.log_warning(msg)
            return None

        if not (len(head_ba) == 1 and len(saddr_ba) == 1 and len(daddr_ba) == 1 and len(id_ba) == 1):
            msg = "帧头/地址/面板功能码 Hex长度必须为1字节 (2个Hex字符)"
            self.status_bar_label.setText(msg)
            if self.error_logger: self.error_logger.log_warning(msg)
            return None

        data_content_ba = QByteArray()
        for scw_widget in panel_send_data_containers:
            item_bytes = scw_widget.get_bytes()
            if item_bytes is None:
                msg = f"发送面板(ID:{panel_target_func_id_str}) 项 '{scw_widget.name_edit.text()}' 数值错误"
                self.status_bar_label.setText(msg)
                if self.error_logger: self.error_logger.log_warning(msg)
                return None
            data_content_ba.append(item_bytes)

        len_val = len(data_content_ba)
        len_ba = QByteArray(struct.pack('<H', len_val))

        frame_part_for_checksum = QByteArray()
        frame_part_for_checksum.append(head_ba)
        frame_part_for_checksum.append(saddr_ba)
        frame_part_for_checksum.append(daddr_ba)
        frame_part_for_checksum.append(id_ba)
        frame_part_for_checksum.append(len_ba)
        frame_part_for_checksum.append(data_content_ba)

        checksum_bytes_to_append = QByteArray()
        active_mode = self.checksum_mode_combo.currentData()

        if active_mode == ChecksumMode.CRC16_CCITT_FALSE:
            crc_val = calculate_frame_crc16(frame_part_for_checksum)
            checksum_bytes_to_append.append(struct.pack('>H', crc_val))
            self.sum_check_display.setText(f"0x{crc_val:04X}")  # Update global display
            self.add_check_display.clear()
        else:  # Default to ORIGINAL_SUM_ADD
            sc_val, ac_val = calculate_original_checksums_python(frame_part_for_checksum)
            checksum_bytes_to_append.append(bytes([sc_val]))
            checksum_bytes_to_append.append(bytes([ac_val]))
            self.sum_check_display.setText(f"0x{sc_val:02X}")  # Update global display
            self.add_check_display.setText(f"0x{ac_val:02X}")

        final_frame = QByteArray(frame_part_for_checksum)
        final_frame.append(checksum_bytes_to_append)
        return final_frame

    # send_custom_protocol_data_action is REMOVED (triggered by SendPanelWidget now)

    # --- Send Panel Management (New Methods) ---
    @Slot()
    def add_new_send_panel_action(self, config: Optional[Dict] = None, from_config: bool = False,
                                  panel_name_suggestion: Optional[str] = None, is_migration: bool = False):
        panel_id_to_use = self._next_send_panel_id
        self._next_send_panel_id += 1

        actual_panel_name = panel_name_suggestion
        # Determine initial name for the dock/panel title
        if config and config.get("dock_name"):
            actual_panel_name = config.get("dock_name")
        elif not actual_panel_name:  # Default name generation
            default_func_id_for_name = config.get("panel_func_id",
                                                  f"S{panel_id_to_use}") if config else f"S{panel_id_to_use}"
            actual_panel_name = f"发送面板 {panel_id_to_use} (ID: {default_func_id_for_name.upper()})"

        if not from_config:  # Prompt for name if adding manually
            text, ok = QInputDialog.getText(self, "新建发送面板", "输入面板名称:", QLineEdit.EchoMode.Normal,
                                            actual_panel_name)
            if not ok or not text.strip():
                self._next_send_panel_id -= 1  # Rollback ID
                return
            actual_panel_name = text.strip()

        panel_widget = SendPanelWidget(panel_id_to_use, main_window_ref=self, initial_config=config)
        # After initial_config, the panel_widget title might be more specific. Update actual_panel_name for the dock.
        actual_panel_name = panel_widget.send_data_group.title()

        dw_send_panel = QDockWidget(actual_panel_name, self)
        dw_send_panel.setObjectName(f"SendPanelDock_{panel_id_to_use}")
        dw_send_panel.setWidget(panel_widget)
        dw_send_panel.installEventFilter(self)

        # Docking and Tabifying Logic: Try to tab with other send panels or the main serial config panel
        existing_send_docks = [self.send_panel_docks.get(pid) for pid in sorted(self.send_panel_docks.keys()) if
                               pid in self.send_panel_docks]

        if not existing_send_docks:
            if self.dw_serial_config:
                self.tabifyDockWidget(self.dw_serial_config, dw_send_panel)
            else:
                self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dw_send_panel)
        else:
            self.tabifyDockWidget(existing_send_docks[-1], dw_send_panel)

        self.send_panel_widgets[panel_id_to_use] = panel_widget
        self.send_panel_docks[panel_id_to_use] = dw_send_panel

        if hasattr(self, 'view_menu'):
            action = dw_send_panel.toggleViewAction()
            self.view_menu.addAction(action)

        dw_send_panel.show()
        if self.error_logger:
            self.error_logger.log_info(f"Added Send Panel: ID={panel_id_to_use}, Name='{dw_send_panel.windowTitle()}'")

    def _clear_all_send_panels(self):
        for panel_id in list(self.send_panel_docks.keys()):  # Iterate over a copy for safe removal
            dock = self.send_panel_docks.get(panel_id)
            if dock:
                self.remove_send_panel_and_update(panel_id, dock)
        self._next_send_panel_id = 1

    # --- Other methods (on_serial_data_received, populate_serial_ports_ui, etc.) mostly unchanged from previous refactor ---
    # Ensure all plot related calls use update_all_parse_panels_plot_targets
    # Ensure FrameParser.try_parse_frames is called without target_fid if it's generic enough.
    @Slot(QByteArray)
    def on_serial_data_received(self, data: QByteArray):
        self._append_to_basic_receive(data, source="RX")
        self.data_recorder.record_raw_frame(datetime.now(), data.data(), "RX")
        self.frame_parser.append_data(data)
        self.update_current_frame_config_from_ui()  # For general frame structure

        current_ui_checksum_mode = self.checksum_mode_combo.currentData()
        if not isinstance(current_ui_checksum_mode, ChecksumMode):
            current_ui_checksum_mode = self.active_checksum_mode if self.active_checksum_mode else Constants.DEFAULT_CHECKSUM_MODE

        # FrameParser should parse any valid frame based on structure, then on_frame_successfully_parsed dispatches.
        self.frame_parser.try_parse_frames(self.current_frame_config, current_ui_checksum_mode)

    # The rest of the SerialDebugger methods (load_config, save_config, theme actions, plot management, etc.)
    # should be reviewed to ensure they integrate correctly with the new panel structures but mostly remain
    # functionally the same as after the ParsePanel refactoring.
    # For brevity, I'm omitting the unchanged methods from the previous complete code block.
    # Ensure all methods like update_all_recv_containers_plot_targets are replaced by update_all_parse_panels_plot_targets.

    # Placeholder for methods that are largely unchanged from the previous refactoring pass
    # but would be part of the full file:
    def update_current_frame_config_from_ui(self):  # Unchanged
        self.current_frame_config.head = self.head_edit.text()
        self.current_frame_config.s_addr = self.saddr_edit.text()
        self.current_frame_config.d_addr = self.daddr_edit.text()
        self.current_frame_config.func_id = self.id_edit.text()  # This is global/default send func_id
        selected_mode_data = self.checksum_mode_combo.currentData()
        if isinstance(selected_mode_data, ChecksumMode):
            self.active_checksum_mode = selected_mode_data
        else:
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE

    def update_current_serial_config_from_ui(self):  # Unchanged
        port_data = self.port_combo.currentData()
        self.current_serial_config.port_name = port_data if port_data else self.port_combo.currentText()  # Handle case where port_data might be None
        self.current_serial_config.baud_rate = int(self.baud_combo.currentText())
        self.current_serial_config.data_bits = int(self.data_bits_combo.currentText())
        self.current_serial_config.parity = self.parity_combo.currentText()
        s_bits = self.stop_bits_combo.currentText()
        self.current_serial_config.stop_bits = float(s_bits) if s_bits == "1.5" else int(s_bits)

    def restore_geometry_and_state(self) -> None:  # Unchanged
        geom_b64 = self.current_config.get("window_geometry")
        state_b64 = self.current_config.get("window_state")
        if geom_b64: self.restoreGeometry(QByteArray.fromBase64(geom_b64.encode()))
        if state_b64: self.restoreState(QByteArray.fromBase64(state_b64.encode()))

    def remove_plot_widget_and_update(self, plot_id_to_remove: int,
                                      associated_dock_widget: QDockWidget):  # Unchanged (but calls updated plot target func)
        self.plot_widgets_map.pop(plot_id_to_remove, None)
        self.plot_docks_map.pop(plot_id_to_remove, None)
        if hasattr(self, 'view_menu') and self.view_menu and associated_dock_widget:
            view_action = associated_dock_widget.toggleViewAction()
            if view_action: self.view_menu.removeAction(view_action)
        if associated_dock_widget: associated_dock_widget.deleteLater()
        self.update_all_parse_panels_plot_targets()  # Ensure this is the correct call
        if self.error_logger:
            self.error_logger.log_info(
                f"Permanently removed plot widget ID: {plot_id_to_remove}, Name: '{associated_dock_widget.windowTitle()}'")

    def remove_parse_panel_and_update(self, panel_id_to_remove: int, associated_dock_widget: QDockWidget):  # Unchanged
        panel_widget = self.parse_panel_widgets.pop(panel_id_to_remove, None)
        self.parse_panel_docks.pop(panel_id_to_remove, None)
        if hasattr(self, 'view_menu') and self.view_menu and associated_dock_widget:
            view_action = associated_dock_widget.toggleViewAction()
            if view_action: self.view_menu.removeAction(view_action)
        if panel_widget: panel_widget.deleteLater()
        if associated_dock_widget: associated_dock_widget.deleteLater()
        if self.error_logger:
            self.error_logger.log_info(
                f"Permanently removed parse panel ID: {panel_id_to_remove}, Name: '{associated_dock_widget.windowTitle()}'")

    def load_configuration_action(self) -> None:  # Unchanged
        file_path, _ = QFileDialog.getOpenFileName(self, "加载配置文件", "", "JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            temp_loader = ConfigManager(filename=file_path, error_logger=self.error_logger)
            loaded_cfg = temp_loader.load_config()
            if loaded_cfg != temp_loader.default_config or Path(file_path).exists():
                self.current_config = loaded_cfg
                self.apply_loaded_config_to_ui()  # This now handles all panel types
                QMessageBox.information(self, "配置加载", f"配置已从 '{file_path}' 加载。")
            else:
                QMessageBox.warning(self, "配置加载", f"无法从 '{file_path}' 加载有效配置。")

    def save_configuration_action(self) -> None:  # Unchanged
        current_config_path = self.config_manager.config_file
        file_path, _ = QFileDialog.getSaveFileName(self, "保存配置文件", str(current_config_path),
                                                   "JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            current_ui_cfg = self.gather_current_ui_config()  # This now gathers all panel types
            temp_saver = ConfigManager(filename=file_path, error_logger=self.error_logger)
            temp_saver.save_config(current_ui_cfg)
            QMessageBox.information(self, "配置保存", f"配置已保存到 {file_path}。")

    def apply_theme_action(self, theme_name: str) -> None:
        self.theme_manager.apply_theme(theme_name)  # Unchanged

    def load_external_qss_file_action(self) -> None:  # Unchanged
        file_path, _ = QFileDialog.getOpenFileName(self, "选择QSS样式文件", "", "QSS 文件 (*.qss);;所有文件 (*)")
        if file_path: self.theme_manager.apply_external_qss(file_path)

    def export_parsed_data_action(self) -> None:  # Unchanged (DataRecorder handles aggregated data)
        if not self.data_recorder.historical_data:
            QMessageBox.information(self, "导出数据", "没有可导出的已解析数据。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存已解析数据", "", "CSV 文件 (*.csv)")
        if path:
            if self.data_recorder.export_parsed_data_to_csv(path):
                QMessageBox.information(self, "导出成功", f"数据已成功导出到:\n{path}")
            else:
                QMessageBox.warning(self, "导出失败", "导出已解析数据失败，请查看日志。")

    def save_raw_recorded_data_action(self) -> None:  # Unchanged
        if not self.data_recorder.recorded_raw_data:
            QMessageBox.information(self, "保存原始数据", "没有已录制的原始数据。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存原始录制数据", "",
                                              "JSON Log 文件 (*.jsonl *.json);;所有文件 (*)")
        if path:
            self.data_recorder.save_raw_to_file(path)
            QMessageBox.information(self, "保存成功", f"原始录制数据已保存到:\n{path}")

    def show_statistics_action(self) -> None:  # Unchanged
        stats = self.protocol_analyzer.get_statistics()
        stats_str_parts = [f"接收总帧数 (自定义协议): {stats['total_frames_rx']}",
                           f"发送总帧数 (自定义协议): {stats['total_frames_tx']}",
                           f"接收错误帧数 (自定义协议): {stats['error_frames_rx']}",
                           f"当前接收速率 (自定义协议): {stats['data_rate_rx_bps']:.2f} bps",
                           f"总接收字节 (自定义协议): {stats['rx_byte_count']} B"]
        QMessageBox.information(self, "自定义协议统计信息", "\n".join(stats_str_parts))

    @Slot(int, int)
    def handle_recv_container_plot_target_change(self, container_id: int, target_plot_id: int) -> None:  # Unchanged
        if self.error_logger: self.error_logger.log_info(f"接收容器 {container_id} 目标波形图更改为 {target_plot_id}")

    @Slot()
    def add_new_plot_widget_action(self, name: Optional[str] = None, plot_id_from_config: Optional[int] = None,
                                   from_config: bool = False) -> None:  # Unchanged (but calls updated plot target func)
        if not PYQTGRAPH_AVAILABLE:
            QMessageBox.information(self, "提示", "pyqtgraph未安装，无法添加波形图。")
            return
        plot_id_to_use = plot_id_from_config if plot_id_from_config is not None else self._next_plot_id
        while plot_id_to_use in self.plot_widgets_map:
            plot_id_to_use = self._next_plot_id
            self._next_plot_id += 1
        plot_name_input = name
        if not from_config and name is None:
            text, ok = QInputDialog.getText(self, "新波形图", "输入波形图名称:", QLineEdit.EchoMode.Normal,
                                            f"波形图 {plot_id_to_use}")
            if not ok or not text.strip(): return
            plot_name_input = text.strip()
        elif name is None:
            plot_name_input = f"波形图 {plot_id_to_use}"
        plot_container = PlotWidgetContainer(plot_id_to_use, plot_name_input, self)
        dw_plot = QDockWidget(plot_name_input, self)
        dw_plot.setObjectName(f"PlotDock_{plot_id_to_use}")
        dw_plot.setWidget(plot_container)
        dw_plot.installEventFilter(self)
        all_dynamic_docks = ([self.parse_panel_docks.get(pid) for pid in sorted(self.parse_panel_docks.keys())] +
                             [self.send_panel_docks.get(pid) for pid in
                              sorted(self.send_panel_docks.keys())] +  # Include send panels
                             [self.plot_docks_map.get(pid) for pid in sorted(self.plot_docks_map.keys())])
        all_dynamic_docks = [d for d in all_dynamic_docks if d]
        if all_dynamic_docks:
            self.tabifyDockWidget(all_dynamic_docks[-1], dw_plot)
        else:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dw_plot)
        self.plot_widgets_map[plot_id_to_use] = plot_container
        self.plot_docks_map[plot_id_to_use] = dw_plot
        if plot_id_from_config is None or plot_id_to_use >= self._next_plot_id:
            self._next_plot_id = plot_id_to_use + 1
        if hasattr(self, 'view_menu'):
            action = dw_plot.toggleViewAction()
            self.view_menu.addAction(action)
        self.update_all_parse_panels_plot_targets()  # Correct method
        dw_plot.show()
        if not from_config and self.error_logger:
            self.error_logger.log_info(f"添加新波形图: ID={plot_id_to_use}, Name='{plot_name_input}'")

    def update_all_parse_panels_plot_targets(self) -> None:  # Unchanged from previous refactor
        for panel_widget in self.parse_panel_widgets.values():
            panel_widget.update_children_plot_targets()

    @Slot()
    def clear_all_plots_action(self) -> None:  # Unchanged
        if not PYQTGRAPH_AVAILABLE: return
        for plot_container in self.plot_widgets_map.values():
            plot_container.clear_plot()
        if self.error_logger: self.error_logger.log_info("所有波形图已清空。")

    @Slot()
    def populate_serial_ports_ui(self) -> None:  # Unchanged
        self.port_combo.clear()
        available_ports = self.serial_manager.get_available_ports()
        if not available_ports:
            self.port_combo.addItem("无可用端口");
            self.port_combo.setEnabled(False)
        else:
            for port_info in available_ports: self.port_combo.addItem(
                f"{port_info['name']} ({port_info['description']})", port_info['name'])
            self.port_combo.setEnabled(True)
            if self.current_serial_config.port_name:
                idx = self.port_combo.findData(self.current_serial_config.port_name)
                if idx != -1: self.port_combo.setCurrentIndex(idx)
        self.update_port_status_ui(self.serial_manager.is_connected)

    def update_port_status_ui(self,
                              connected: bool) -> None:  # Unchanged (send_frame_button removed, panel buttons handle enabling)
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.data_bits_combo.setEnabled(not connected)
        self.parity_combo.setEnabled(not connected)
        self.stop_bits_combo.setEnabled(not connected)
        self.refresh_ports_button.setEnabled(not connected)
        self.connect_button.setChecked(connected)
        self.connect_button.setText("关闭串口" if connected else "打开串口")
        # self.send_frame_button.setEnabled(connected) # Removed global send button
        # Each SendPanelWidget's send button should be enabled/disabled based on connection status
        for panel in self.send_panel_widgets.values():
            panel.send_frame_button_panel.setEnabled(connected)
        if hasattr(self,
                   'basic_send_button') and self.basic_send_button:  # Basic send button is from _create_basic_serial_panel
            basic_send_button_in_layout = self.dw_basic_serial.widget().findChild(QPushButton,
                                                                                  "发送")  # More robust way if objectName is set
            if basic_send_button_in_layout: basic_send_button_in_layout.setEnabled(connected)

        if not self.port_combo.count() or self.port_combo.currentText() == "无可用端口":
            self.connect_button.setEnabled(False)
            if not connected: self.status_bar_label.setText("无可用串口")

    @Slot()
    def toggle_connection_action(self) -> None:  # Unchanged
        if self.serial_manager.is_connected:
            self.serial_manager.disconnect_port()
        else:
            self.update_current_serial_config_from_ui()
            self.serial_manager.connect_port(self.current_serial_config)
            if self.serial_manager.is_connected: self.frame_parser.clear_buffer(); self._parsed_frame_count = 0

    @Slot()
    def send_basic_serial_data_action(self) -> None:  # Unchanged
        if not self.serial_manager.is_connected: QMessageBox.warning(self, "警告",
                                                                     "串口未打开。"); self._append_to_basic_receive(
            QByteArray("错误: 串口未打开。\n".encode('utf-8')), source="INFO"); return
        text_to_send = self.basic_send_text_edit.text()
        if not text_to_send: return
        data_to_write = QByteArray()
        is_hex_send = self.basic_send_hex_checkbox.isChecked()
        if is_hex_send:
            hex_clean = "".join(text_to_send.replace("0x", "").replace("0X", "").split())
            if len(hex_clean) % 2 != 0: hex_clean = "0" + hex_clean
            try:
                data_to_write = QByteArray.fromHex(hex_clean.encode('ascii'))
            except ValueError:
                QMessageBox.warning(self, "Hex格式错误",
                                    f"'{text_to_send}' 包含无效Hex字符."); self._append_to_basic_receive(
                    QByteArray(f"错误: 无效Hex\n".encode('utf-8')), source="INFO"); return
        else:
            data_to_write.append(text_to_send.encode('utf-8', errors='replace'))
        if data_to_write:
            bytes_written = self.serial_manager.write_data(data_to_write)
            if bytes_written == len(data_to_write):
                display_sent_data = data_to_write.toHex(' ').data().decode(
                    'ascii').upper() if is_hex_send else text_to_send
                if len(display_sent_data) > 60: display_sent_data = display_sent_data[:60] + "..."
                msg = f"基本发送 {bytes_written} 字节: {display_sent_data}"
                self.status_bar_label.setText(msg)
                if self.error_logger: self.error_logger.log_info(msg)
                self._append_to_basic_receive(data_to_write, source="TX")
                self.data_recorder.record_raw_frame(datetime.now(), data_to_write.data(), "TX (Basic)")

    @Slot(str, QByteArray)
    def on_frame_successfully_parsed(self, func_id_hex: str,
                                     data_payload_ba: QByteArray):  # Unchanged from previous refactor
        self._parsed_frame_count += 1
        hex_payload_str = data_payload_ba.toHex(' ').data().decode('ascii').upper()
        self._append_to_custom_protocol_log(f"FID:{func_id_hex} Payload:{hex_payload_str}", is_hex=True,
                                            source="RX Parsed")
        msg = f"成功解析帧 (自定义协议): #{self._parsed_frame_count}, FID: {func_id_hex.upper()}"
        self.status_bar_label.setText(msg)
        if self.error_logger: self.error_logger.log_info(f"{msg} Payload len: {len(data_payload_ba)}")
        self.protocol_analyzer.analyze_frame(data_payload_ba, 'rx')  # Or full frame if available
        dispatched_to_a_panel = False
        for panel_widget in self.parse_panel_widgets.values():
            if func_id_hex.upper() == panel_widget.get_target_func_id().upper():
                panel_widget.dispatch_data(data_payload_ba)
                dispatched_to_a_panel = True
        if not dispatched_to_a_panel and self.error_logger: self.error_logger.log_debug(
            f"Frame with FID {func_id_hex} received but no parse panel is targeting it.")

    @Slot(str, QByteArray)
    def on_frame_checksum_error(self, error_message: str, faulty_frame: QByteArray):  # Unchanged
        self.status_bar_label.setText("校验和错误!")
        hex_frame_str = faulty_frame.toHex(' ').data().decode('ascii').upper()
        self._append_to_custom_protocol_log(f"ChecksumError: {error_message} Frame: {hex_frame_str}", is_hex=True,
                                            source="RX Error")
        self.protocol_analyzer.analyze_frame(faulty_frame, 'rx', is_error=True)

    @Slot(str, QByteArray)
    def on_frame_general_parse_error(self, error_message: str, buffer_state: QByteArray):  # Unchanged
        self.status_bar_label.setText(f"协议解析错误: {error_message}")

    @Slot(str)
    def on_serial_manager_error(self, error_message: str):  # Unchanged
        self.status_bar_label.setText(error_message)
        QMessageBox.warning(self, "串口通讯警告", error_message)

    @Slot(bool, str)
    def on_serial_connection_status_changed(self, is_connected: bool, message: str):  # Unchanged
        self.update_port_status_ui(is_connected)
        self.status_bar_label.setText(message)
        if not is_connected and "资源错误" in message: QMessageBox.critical(self, "串口错误", message)

    def _append_to_basic_receive(self, data_to_append: QByteArray, source: str = "RX"):  # Unchanged
        if not hasattr(self, 'basic_receive_text_edit') or self.basic_receive_text_edit is None: return
        display_text_parts = []
        if self.basic_recv_timestamp_checkbox and self.basic_recv_timestamp_checkbox.isChecked(): display_text_parts.append(
            datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] ")
        if source == "TX":
            display_text_parts.append("TX: ")
        elif source == "RX":
            display_text_parts.append("RX: ")
        raw_text_to_display = ""
        if self.basic_recv_hex_checkbox and self.basic_recv_hex_checkbox.isChecked():
            raw_text_to_display = data_to_append.toHex(' ').data().decode('ascii', errors='ignore').upper()
        else:
            try:
                raw_text_to_display = data_to_append.data().decode('utf-8')
            except UnicodeDecodeError:
                try:
                    raw_text_to_display = data_to_append.data().decode('gbk', errors='replace')
                except UnicodeDecodeError:
                    raw_text_to_display = data_to_append.data().decode('latin-1', errors='replace')
        display_text_parts.append(raw_text_to_display)
        final_text = "".join(display_text_parts)
        if not final_text.endswith('\n'): final_text += '\n'
        self.basic_receive_text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.basic_receive_text_edit.insertPlainText(final_text)
        self.basic_receive_text_edit.moveCursor(QTextCursor.MoveOperation.End)

    @Slot(bool)
    def toggle_raw_data_recording_action(self, checked: bool):  # Unchanged
        if checked:
            self.data_recorder.start_raw_recording();
            self.start_raw_record_action.setText("停止原始数据录制");
            self.status_bar_label.setText("原始数据录制已开始...")
        else:
            self.data_recorder.stop_raw_recording();
            self.start_raw_record_action.setText("开始原始数据录制");
            self.status_bar_label.setText("原始数据录制已停止。")
            if self.data_recorder.recorded_raw_data:
                if QMessageBox.question(self, "保存录制数据", "是否立即保存已录制的原始数据?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
                    self.save_raw_recorded_data_action()

    def closeEvent(self, event: Any) -> None:  # Unchanged
        if self.error_logger: self.error_logger.log_info("应用程序正在关闭。")
        if self.serial_manager.is_connected: self.serial_manager.disconnect_port()
        if self.data_recorder.recording_raw: self.data_recorder.stop_raw_recording()
        current_ui_cfg = self.gather_current_ui_config()
        self.config_manager.save_config(current_ui_cfg)
        if self.error_logger: self.error_logger.log_info("配置已在退出时自动保存。")
        event.accept()

    def _clear_all_parse_panels(self):
        for panel_id in list(self.parse_panel_docks.keys()):
            dock = self.parse_panel_docks.get(panel_id)
            if dock:
                self.remove_parse_panel_and_update(panel_id, dock)
        self._next_parse_panel_id = 1
        self._next_global_receive_container_id = 1

    def _clear_all_send_panels(self):
        for panel_id in list(self.send_panel_docks.keys()):
            dock = self.send_panel_docks.get(panel_id)
            if dock:
                self.remove_send_panel_and_update(panel_id, dock)
        self._next_send_panel_id = 1

    # _create_custom_protocol_log_panel and _create_basic_serial_panel are unchanged.
    # _append_to_custom_protocol_log is unchanged.
    def _create_custom_protocol_log_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        log_group = QGroupBox("自定义协议原始帧记录")
        log_layout = QVBoxLayout()
        self.custom_protocol_raw_log_text_edit = QTextEdit()
        self.custom_protocol_raw_log_text_edit.setReadOnly(True)
        self.custom_protocol_raw_log_text_edit.setFontFamily("Courier New")
        log_layout.addWidget(self.custom_protocol_raw_log_text_edit)
        options_layout = QHBoxLayout()
        self.custom_log_hex_checkbox = QCheckBox("Hex显示")
        options_layout.addWidget(self.custom_log_hex_checkbox)
        self.custom_log_timestamp_checkbox = QCheckBox("显示时间戳")
        options_layout.addWidget(self.custom_log_timestamp_checkbox)
        clear_button = QPushButton("清空记录区")
        clear_button.clicked.connect(self.custom_protocol_raw_log_text_edit.clear)
        options_layout.addWidget(clear_button)
        options_layout.addStretch()
        log_layout.addLayout(options_layout)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        return panel

    def _create_basic_serial_panel(self) -> QWidget:
        panel = QWidget()
        main_layout = QVBoxLayout(panel)
        recv_group = QGroupBox("基本接收 (原始串行数据)")
        recv_layout = QVBoxLayout()
        self.basic_receive_text_edit = QTextEdit()
        self.basic_receive_text_edit.setReadOnly(True)
        self.basic_receive_text_edit.setFontFamily("Courier New")
        recv_layout.addWidget(self.basic_receive_text_edit)
        recv_options_layout = QHBoxLayout()
        self.basic_recv_hex_checkbox = QCheckBox("Hex显示")
        self.basic_recv_timestamp_checkbox = QCheckBox("显示时间戳")
        recv_options_layout.addWidget(self.basic_recv_hex_checkbox)
        recv_options_layout.addWidget(self.basic_recv_timestamp_checkbox)
        recv_options_layout.addStretch()
        clear_basic_recv_button = QPushButton("清空接收区")
        clear_basic_recv_button.clicked.connect(self.basic_receive_text_edit.clear)
        recv_options_layout.addWidget(clear_basic_recv_button)
        recv_layout.addLayout(recv_options_layout)
        recv_group.setLayout(recv_layout)
        main_layout.addWidget(recv_group)
        send_group = QGroupBox("基本发送 (原始串行数据)")
        send_layout = QVBoxLayout()
        self.basic_send_text_edit = QLineEdit()
        self.basic_send_text_edit.setPlaceholderText("输入要发送的文本或Hex数据")
        send_layout.addWidget(self.basic_send_text_edit)
        send_options_layout = QHBoxLayout()
        self.basic_send_hex_checkbox = QCheckBox("Hex发送")
        send_options_layout.addWidget(self.basic_send_hex_checkbox)
        send_options_layout.addStretch()
        basic_send_button = QPushButton("发送")  # Could setObjectName("basicSendButton")
        basic_send_button.setObjectName("basicSendButtonActual")  # For robust findChild
        basic_send_button.clicked.connect(self.send_basic_serial_data_action)
        send_options_layout.addWidget(basic_send_button)
        send_layout.addLayout(send_options_layout)
        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)
        return panel

    def _append_to_custom_protocol_log(self, text: str, is_hex: bool, source: str = "RX"):
        if not hasattr(self,
                       'custom_protocol_raw_log_text_edit') or self.custom_protocol_raw_log_text_edit is None: return
        display_text = ""
        if self.custom_log_timestamp_checkbox and self.custom_log_timestamp_checkbox.isChecked(): display_text += datetime.now().strftime(
            "[%H:%M:%S.%f")[:-3] + "] "
        display_text += f"{source}: "
        display_text += text
        if not text.endswith('\n'): display_text += '\n'
        self.custom_protocol_raw_log_text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.custom_protocol_raw_log_text_edit.insertPlainText(display_text)
        self.custom_protocol_raw_log_text_edit.moveCursor(QTextCursor.MoveOperation.End)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = SerialDebugger()
    main_win.show()
    sys.exit(app.exec())