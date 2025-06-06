from datetime import datetime
from typing import Optional, Dict, List, Any, TYPE_CHECKING  # Added Set
from PySide6.QtCore import Slot, QByteArray, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QLineEdit, QPushButton, QMessageBox, QGroupBox, QScrollArea,
    QInputDialog,  # For Plugin Management Dialog
)
# Core imports from your project structure
try:
    import pyqtgraph as pg  # type: ignore
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    pg = None
    PYQTGRAPH_AVAILABLE = False
    print("警告：pyqtgraph 未安装，波形图功能将不可用。请运行 'pip install pyqtgraph'")
from ui.widgets import ReceiveDataContainerWidget, SendDataContainerWidget
from core.protocol_handler import get_data_type_byte_length
# Updated Plugin Architecture Imports
from core.panel_interface import PanelInterface
if TYPE_CHECKING:
    from main import SerialDebugger  # Forward reference for type hinting
# Core imports from your project structure



# --- Adapted Panel Widget Classes (Full Implementations) ---
class AdaptedParsePanelWidget(PanelInterface):
    PANEL_TYPE_NAME = "core_parse_panel"
    PANEL_DISPLAY_NAME = "数据解析面板"

    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', initial_config: Optional[Dict] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        self.receive_data_containers: List[ReceiveDataContainerWidget] = []
        self._init_ui()  # Initialize UI elements first
        if initial_config:
            self.apply_config(initial_config)
        else:
            if hasattr(self, 'parse_id_edit'):  # Ensure UI element exists
                self.parse_id_edit.setText(f"C{self.panel_id}")
            self._update_panel_title_from_parse_id()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.recv_display_group = QGroupBox()
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
        self._update_panel_title_from_parse_id()  # Call after all UI elements are created

    def _update_panel_title_from_parse_id(self):
        func_id_str = self.get_target_func_id().upper() if hasattr(self,
                                                                   'parse_id_edit') and self.get_target_func_id() else "N/A"
        new_title = f"{self.PANEL_DISPLAY_NAME} {self.panel_id} (ID: {func_id_str})"
        if hasattr(self, 'recv_display_group'):
            self.recv_display_group.setTitle(new_title)
        self.dock_title_changed.emit(new_title)

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
            if PYQTGRAPH_AVAILABLE and hasattr(container, 'plot_checkbox') and container.plot_checkbox:
                container.plot_checkbox.setChecked(config.get("plot_enabled", False))
        else:
            container.name_edit.setText(f"RecvData_{container_id}")
            if PYQTGRAPH_AVAILABLE and hasattr(container, 'plot_checkbox') and container.plot_checkbox:
                container.plot_checkbox.setChecked(False)

        self.recv_containers_layout.addWidget(container)
        self.receive_data_containers.append(container)
        self.remove_recv_container_button.setEnabled(True)

        targets_for_dropdown = self.main_window_ref.get_available_plot_targets()
        container.update_plot_targets(targets_for_dropdown)

        if config and PYQTGRAPH_AVAILABLE and hasattr(container, 'plot_target_combo') and container.plot_target_combo:
            plot_target_id = config.get("plot_target_id")
            if plot_target_id is not None:
                idx = container.plot_target_combo.findData(plot_target_id)
                if idx != -1:
                    container.plot_target_combo.setCurrentIndex(idx)
            if hasattr(container, 'plot_checkbox'):
                container.plot_target_combo.setEnabled(
                    container.plot_checkbox.isChecked() and bool(targets_for_dropdown))
        elif PYQTGRAPH_AVAILABLE and hasattr(container,
                                             'plot_target_combo') and container.plot_target_combo and hasattr(container,
                                                                                                              'plot_checkbox'):
            container.plot_target_combo.setEnabled(container.plot_checkbox.isChecked() and bool(targets_for_dropdown))

        if not silent and self.error_logger:
            self.error_logger.log_info(f"Parse Panel {self.panel_id}: Added receive container {container_id}")

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
        if hasattr(self, 'parse_id_edit'):
            return self.parse_id_edit.text()
        return ""

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
                    if current_offset < data_payload_ba.size(): segment = data_payload_ba.mid(
                        current_offset); current_offset = data_payload_ba.size()
                elif byte_len > 0:
                    if current_offset + byte_len <= data_payload_ba.size(): segment = data_payload_ba.mid(
                        current_offset, byte_len); current_offset += byte_len
                container_widget.set_value(segment, data_type)
                log_key_name = f"P{self.panel_id}_{config['name']}"
                parsed_data_for_log_export[log_key_name] = container_widget.value_edit.text()
                if PYQTGRAPH_AVAILABLE and config.get("plot_enabled", False) and config.get(
                        "plot_target_id") is not None:
                    target_plot_id = config["plot_target_id"]
                    if target_plot_id in self.main_window_ref.dynamic_panel_instances:
                        plot_panel_candidate = self.main_window_ref.dynamic_panel_instances[target_plot_id]
                        if isinstance(plot_panel_candidate,
                                      AdaptedPlotWidgetPanel) and plot_panel_candidate.plot_widget_container:
                            val_float = container_widget.get_value_as_float()
                            if val_float is not None: curve_name = f"P{self.panel_id}:{config['name']}"; plot_panel_candidate.update_data(
                                config["id"], val_float, curve_name)
        if parsed_data_for_log_export and hasattr(self.main_window_ref,
                                                  'data_recorder'): self.main_window_ref.data_recorder.add_parsed_frame_data(
            timestamp_now, parsed_data_for_log_export)

    def get_config(self) -> Dict[str, Any]:
        return {"parse_func_id": self.parse_id_edit.text() if hasattr(self, 'parse_id_edit') else "",
                "data_mapping_mode": self.data_mapping_combo.currentText() if hasattr(self,
                                                                                      'data_mapping_combo') else "顺序填充 (Sequential)",
                "receive_containers": [c.get_config() for c in self.receive_data_containers]}

    def apply_config(self, config: Dict[str, Any]):
        if hasattr(self, 'parse_id_edit'): self.parse_id_edit.setText(config.get("parse_func_id", f"C{self.panel_id}"))
        if hasattr(self, 'data_mapping_combo'): self.data_mapping_combo.setCurrentText(
            config.get("data_mapping_mode", "顺序填充 (Sequential)"))
        while self.receive_data_containers: self.remove_receive_data_container(silent=True)
        for container_cfg in config.get("receive_containers", []): self.add_receive_data_container(config=container_cfg,
                                                                                                   silent=True)
        self._update_panel_title_from_parse_id()

    def get_initial_dock_title(self) -> str:
        func_id_text = self.parse_id_edit.text() if hasattr(self,
                                                            'parse_id_edit') and self.parse_id_edit.text() else f"C{self.panel_id}"
        return f"{self.PANEL_DISPLAY_NAME} {self.panel_id} (ID: {func_id_text.upper()})"

    def update_children_plot_targets(self):
        targets = self.main_window_ref.get_available_plot_targets()
        for container in self.receive_data_containers:
            current_target_id_data = None
            if hasattr(container,
                       'plot_target_combo') and container.plot_target_combo and container.plot_target_combo.count() > 0: current_target_id_data = container.plot_target_combo.currentData()
            current_target_id = current_target_id_data if current_target_id_data is not None else None
            container.update_plot_targets(targets)
            if current_target_id is not None and hasattr(container,
                                                         'plot_target_combo') and container.plot_target_combo:
                idx = container.plot_target_combo.findData(current_target_id)
                if idx != -1: container.plot_target_combo.setCurrentIndex(idx)
            if hasattr(container, 'plot_checkbox') and hasattr(container,
                                                               'plot_target_combo') and container.plot_checkbox and container.plot_target_combo: container.plot_target_combo.setEnabled(
                container.plot_checkbox.isChecked() and bool(targets))

    def on_panel_removed(self) -> None:
        for container in self.receive_data_containers: self.main_window_ref.clear_plot_curves_for_container(
            container.container_id)
        if self.error_logger: self.error_logger.log_info(
            f"Parse Panel {self.panel_id} removed. Cleaned up associated plot curves.")


class AdaptedSendPanelWidget(PanelInterface):  # Full implementation
    PANEL_TYPE_NAME = "core_send_panel"
    PANEL_DISPLAY_NAME = "数据发送面板"

    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', initial_config: Optional[Dict] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        self.send_data_containers: List[SendDataContainerWidget] = []
        self._next_local_send_container_id: int = 1
        self._init_ui()
        if initial_config:
            self.apply_config(initial_config)
        else:
            if hasattr(self, 'panel_func_id_edit'): self.panel_func_id_edit.setText(f"S{self.panel_id:X}")
            self._update_panel_title()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.send_data_group = QGroupBox()
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
        self.send_frame_button_panel.setEnabled(self.main_window_ref.serial_manager.is_connected)
        send_data_main_layout.addWidget(self.send_frame_button_panel)
        self.send_data_group.setLayout(send_data_main_layout)
        layout.addWidget(self.send_data_group)
        self.setLayout(layout)
        self._update_panel_title()

    def _update_panel_title(self):
        func_id_text = self.panel_func_id_edit.text().upper() if hasattr(self, 'panel_func_id_edit') else ""
        title = f"{self.PANEL_DISPLAY_NAME} {self.panel_id} (ID: {func_id_text if func_id_text else '未定义'})"
        if hasattr(self, 'send_data_group'): self.send_data_group.setTitle(title)
        self.dock_title_changed.emit(title)

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
        else:
            container.name_edit.setText(f"Data_{container_id}")
        self.containers_layout.addWidget(container)
        self.send_data_containers.append(container)
        self._next_local_send_container_id += 1
        self.remove_button.setEnabled(True)
        if not silent and self.error_logger: self.error_logger.log_info(
            f"Send Panel {self.panel_id}: Added send data container {container_id}")

    def remove_send_data_container(self, silent: bool = False):
        if self.send_data_containers:
            container_to_remove = self.send_data_containers.pop()
            removed_id = container_to_remove.container_id
            self.containers_layout.removeWidget(container_to_remove)
            container_to_remove.deleteLater()
            if not self.send_data_containers: self.remove_button.setEnabled(False)
            if not silent and self.error_logger: self.error_logger.log_info(
                f"Send Panel {self.panel_id}: Removed send data container {removed_id}")

    @Slot()
    def _trigger_send_frame(self):
        if not self.main_window_ref.serial_manager.is_connected: QMessageBox.warning(self.main_window_ref, "警告",
                                                                                     "串口未打开。"); return
        panel_func_id_str = self.panel_func_id_edit.text()
        if not panel_func_id_str: QMessageBox.warning(self.main_window_ref, "功能码缺失",
                                                      "请输入此发送面板的目标功能码。"); return
        self.main_window_ref.update_current_serial_frame_configs_from_ui()
        final_frame = self.main_window_ref.assemble_custom_frame_from_send_panel_data(
            panel_target_func_id_str=panel_func_id_str, panel_send_data_containers=self.send_data_containers)
        if final_frame:
            bytes_written = self.main_window_ref.serial_manager.write_data(final_frame)
            if bytes_written == final_frame.size():
                hex_frame_str = final_frame.toHex(' ').data().decode('ascii').upper()
                msg = f"发送面板 {self.panel_id} (ID:{panel_func_id_str}) 发送 {bytes_written} 字节: {hex_frame_str}"
                self.main_window_ref.status_bar_label.setText(msg)
                if self.error_logger: self.error_logger.log_info(msg)
                self.main_window_ref.protocol_analyzer.analyze_frame(final_frame, 'tx')
                self.main_window_ref.data_recorder.record_raw_frame(datetime.now(), final_frame.data(),
                                                                    f"TX (SendPanel {self.panel_id} ID:{panel_func_id_str})")
                self.main_window_ref.append_to_custom_protocol_log_formatted(datetime.now(),
                                                                             f"TX P{self.panel_id} ID:{panel_func_id_str}",
                                                                             hex_frame_str, is_content_hex=True)
            else:
                if self.error_logger: self.error_logger.log_warning(
                    f"Send Panel {self.panel_id}: Partial write. Expected {final_frame.size()}, wrote {bytes_written}")
                self.main_window_ref.status_bar_label.setText(f"发送面板 {self.panel_id}: 写入错误")

    def get_config(self) -> Dict[str, Any]:
        return {"panel_func_id": self.panel_func_id_edit.text() if hasattr(self, 'panel_func_id_edit') else "",
                "send_containers": [c.get_config() for c in self.send_data_containers]}

    def apply_config(self, config: Dict[str, Any]):
        if hasattr(self, 'panel_func_id_edit'): self.panel_func_id_edit.setText(
            config.get("panel_func_id", f"S{self.panel_id:X}"))
        while self.send_data_containers: self.remove_send_data_container(silent=True)
        for c_cfg in config.get("send_containers", []): self.add_send_data_container(config=c_cfg, silent=True)
        self._update_panel_title()

    def get_initial_dock_title(self) -> str:
        func_id_text = self.panel_func_id_edit.text().upper() if hasattr(self,
                                                                         'panel_func_id_edit') and self.panel_func_id_edit.text() else f"S{self.panel_id:X}"
        return f"{self.PANEL_DISPLAY_NAME} {self.panel_id} (ID: {func_id_text})"

    def update_send_button_state(self, serial_connected: bool):
        if hasattr(self, 'send_frame_button_panel'): self.send_frame_button_panel.setEnabled(serial_connected)


if PYQTGRAPH_AVAILABLE and pg is not None:  # Full implementation
    class AdaptedPlotWidgetPanel(PanelInterface):
        PANEL_TYPE_NAME = "core_plot_widget_panel"
        PANEL_DISPLAY_NAME = "波形图面板"

        def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', initial_config: Optional[Dict] = None,
                     parent: Optional[QWidget] = None):
            super().__init__(panel_id, main_window_ref, initial_config, parent)
            if initial_config:
                self.plot_name = initial_config.get("name", f"波形图 {self.panel_id}")
                self.max_data_points = initial_config.get("max_data_points", 300)
            else:
                self.plot_name = f"波形图 {self.panel_id}"
                self.max_data_points = 300
            self.curves: Dict[int, pg.PlotDataItem] = {}
            self.data: Dict[int, Dict[str, list]] = {}
            self.plot_widget_container: Optional[pg.PlotWidget] = None
            self._init_ui()

        def _init_ui(self):
            layout = QVBoxLayout(self)
            self.plot_widget_container = pg.PlotWidget(title=self.plot_name)
            self.plot_widget_container.showGrid(x=True, y=True)
            self.plot_widget_container.addLegend()
            layout.addWidget(self.plot_widget_container)
            controls_layout = QHBoxLayout()
            self.rename_button = QPushButton("重命名图表")
            self.rename_button.clicked.connect(self._rename_plot_action)
            controls_layout.addWidget(self.rename_button)
            self.clear_button = QPushButton("清空图表")
            self.clear_button.clicked.connect(self.clear_plot)
            controls_layout.addWidget(self.clear_button)
            controls_layout.addStretch()
            layout.addLayout(controls_layout)
            self.setLayout(layout)

        @Slot()
        def _rename_plot_action(self):
            current_name = self.plot_name
            new_name, ok = QInputDialog.getText(self, "重命名波形图", "新名称:", QLineEdit.EchoMode.Normal,
                                                current_name)
            if ok and new_name and new_name != current_name:
                self.plot_name = new_name
                if self.plot_widget_container: self.plot_widget_container.setTitle(self.plot_name)
                self.dock_title_changed.emit(self.plot_name)
                self.main_window_ref.notify_plot_target_renamed(self.panel_id, self.plot_name)

        def update_data(self, container_id: int, value: float, curve_name: str):
            if not self.plot_widget_container: return
            if container_id not in self.data: self.data[container_id] = {'x': [], 'y': []}; pen_color = pg.intColor(
                len(self.curves) % 9, hues=9, values=1, alpha=200); self.curves[
                container_id] = self.plot_widget_container.plot(name=curve_name, pen=pen_color)
            self.data[container_id]['y'].append(value)
            x_val = len(self.data[container_id]['y'])
            self.data[container_id]['x'].append(x_val)
            if len(self.data[container_id]['y']) > self.max_data_points: self.data[container_id]['y'].pop(0);
            self.data[container_id]['x'].pop(0)
            if container_id in self.curves: self.curves[container_id].setData(self.data[container_id]['x'],
                                                                              self.data[container_id]['y'])

        def clear_plot(self):
            if not self.plot_widget_container: return
            for cid in list(self.curves.keys()): self.remove_curve_for_container(cid, silent=True)
            self.plot_widget_container.clear()
            self.plot_widget_container.addLegend()
            if self.error_logger: self.error_logger.log_info(
                f"Plot Panel {self.panel_id} ('{self.plot_name}') cleared.")

        def remove_curve_for_container(self, container_id: int, silent: bool = False):
            if not self.plot_widget_container: return
            if container_id in self.curves:
                curve_to_remove = self.curves.pop(container_id)
                self.plot_widget_container.removeItem(curve_to_remove)
                self.data.pop(container_id, None)
                if not silent and self.error_logger: self.error_logger.log_debug(
                    f"[Plot Panel {self.panel_id}] Removed curve for container {container_id}.")

        def get_config(self) -> Dict[str, Any]:
            return {"name": self.plot_name, "max_data_points": self.max_data_points}

        def apply_config(self, config: Dict[str, Any]):
            self.plot_name = config.get("name", f"波形图 {self.panel_id}")
            self.max_data_points = config.get("max_data_points", 300)
            if self.plot_widget_container:
                self.plot_widget_container.setTitle(self.plot_name)
            self.dock_title_changed.emit(self.plot_name)

        def get_initial_dock_title(self) -> str:
            return self.plot_name

        def on_panel_removed(self) -> None:
            self.main_window_ref.notify_plot_target_removed(self.panel_id)
            if self.error_logger: self.error_logger.log_info(
                f"Plot Panel {self.panel_id} ('{self.plot_name}') removed.")
else:  # Fallback if PYQTGRAPH_AVAILABLE is False
    class AdaptedPlotWidgetPanel(PanelInterface):
        PANEL_TYPE_NAME = "core_plot_widget_panel"
        PANEL_DISPLAY_NAME = "波形图面板 (不可用)"

        def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', initial_config: Optional[Dict] = None,
                     parent: Optional[QWidget] = None):
            super().__init__(panel_id, main_window_ref, initial_config, parent)
            if initial_config:
                self.plot_name = initial_config.get("name", f"波形图 {self.panel_id}")
            else:
                self.plot_name = f"波形图 {self.panel_id}"
            self._init_ui()

        def _init_ui(self):
            layout = QVBoxLayout(self)
            label = QLabel("PyQtGraph 未安装，波形图功能不可用。")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label); self.setLayout(layout)

        def get_config(self):
            return {"name": self.plot_name}

        def apply_config(self, config):
            self.plot_name = config.get("name", f"波形图 {self.panel_id}")
            self.dock_title_changed.emit(self.plot_name + " (不可用)")

        def get_initial_dock_title(self):
            return self.plot_name + " (不可用)"

        def update_data(self, container_id: int, value: float, curve_name: str):
            pass

        def clear_plot(self):
            pass

        def remove_curve_for_container(self, container_id: int, silent: bool = False):
            pass
