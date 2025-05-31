# main.py
import struct
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Set  # Added Set
import re

from PySide6.QtCore import Slot, QByteArray, Qt, QEvent, QObject, Signal, QSettings
from PySide6.QtGui import QAction, QTextCursor, QIcon, QIntValidator, QCloseEvent, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QMessageBox, QGroupBox, QScrollArea, QFileDialog,
    QInputDialog, QDockWidget, QPlainTextEdit,
    QDialog, QListWidget, QListWidgetItem,  # For Plugin Management Dialog
    QSizePolicy
)

# Core imports from your project structure
from core.placeholders import DataProcessor, create_script_engine

try:
    import pyqtgraph as pg  # type: ignore

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    pg = None
    PYQTGRAPH_AVAILABLE = False
    print("警告：pyqtgraph 未安装，波形图功能将不可用。请运行 'pip install pyqtgraph'")

from utils.constants import Constants, ChecksumMode
from utils.data_models import SerialPortConfig, FrameConfig
from utils.logger import ErrorLogger
from utils.config_manager import ConfigManager
from ui.theme_manager import ThemeManager
from ui.widgets import ReceiveDataContainerWidget, SendDataContainerWidget

from core.serial_manager import SerialManager
from core.protocol_handler import ProtocolAnalyzer, FrameParser, get_data_type_byte_length, calculate_frame_crc16, \
    calculate_original_checksums_python
from core.data_recorder import DataRecorder

# Updated Plugin Architecture Imports
from core.panel_interface import PanelInterface
from core.plugin_manager import PluginManager  # Assumes plugin_manager_hot_reload_v2 is used


# --- Plugin Management Dialog ---
class PluginManagementDialog(QDialog):
    """
    A dialog for managing plugins: enabling/disabling and session-blocking.
    """
    plugin_status_changed_signal = Signal(str, str)  # module_name, new_status

    def __init__(self, plugin_manager_ref: PluginManager, main_window_ref: 'SerialDebugger',
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager_ref
        self.main_window_ref = main_window_ref
        self.setWindowTitle("插件管理器")
        self.setMinimumSize(600, 400)
        self._init_ui()
        self._populate_plugin_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.plugin_list_widget = QListWidget()
        self.plugin_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.plugin_list_widget)

        buttons_layout = QHBoxLayout()
        self.enable_button = QPushButton("启用选中插件")
        self.enable_button.clicked.connect(lambda: self._change_plugin_status_action("enable"))
        buttons_layout.addWidget(self.enable_button)

        self.disable_button = QPushButton("禁用选中插件")
        self.disable_button.clicked.connect(lambda: self._change_plugin_status_action("disable"))
        buttons_layout.addWidget(self.disable_button)

        self.session_block_button = QPushButton("会话阻止选中插件")
        self.session_block_button.setToolTip("在当前应用会话中阻止此插件模块被加载，即使它被标记为已启用。")
        self.session_block_button.clicked.connect(lambda: self._change_plugin_status_action("session_block"))
        buttons_layout.addWidget(self.session_block_button)

        self.unblock_button = QPushButton("取消会话阻止")
        self.unblock_button.clicked.connect(lambda: self._change_plugin_status_action("unblock"))
        buttons_layout.addWidget(self.unblock_button)

        buttons_layout.addStretch()
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.clicked.connect(self._populate_plugin_list)
        buttons_layout.addWidget(self.refresh_button)

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_button)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def _populate_plugin_list(self):
        self.plugin_list_widget.clear()
        discovered_plugins = self.plugin_manager.get_all_discovered_plugin_modules_metadata()

        if not discovered_plugins:
            self.plugin_list_widget.addItem("未发现任何插件模块。")
            self.enable_button.setEnabled(False)
            self.disable_button.setEnabled(False)
            self.session_block_button.setEnabled(False)
            self.unblock_button.setEnabled(False)
            return

        self.enable_button.setEnabled(True)
        self.disable_button.setEnabled(True)
        self.session_block_button.setEnabled(True)
        self.unblock_button.setEnabled(True)

        for plugin_meta in discovered_plugins:
            module_name = plugin_meta.get("module_name", "未知模块")
            display_name = plugin_meta.get("display_name", module_name.split('.')[-1])
            version = plugin_meta.get("version", "N/A")
            description = plugin_meta.get("description", "无描述。")
            status = plugin_meta.get("status", "discovered")

            item_text = f"{display_name} (v{version}) - {module_name}\n  状态: {status.upper()}\n  描述: {description}"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, module_name)

            font = list_item.font()
            if status == "enabled":
                list_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status == "disabled":
                list_item.setForeground(Qt.GlobalColor.darkGray)
                font.setItalic(True)
            elif status == "blocklisted (session)":
                list_item.setForeground(Qt.GlobalColor.red)
                font.setStrikeOut(True)
            list_item.setFont(font)

            self.plugin_list_widget.addItem(list_item)

    def _get_selected_module_name(self) -> Optional[str]:
        current_item = self.plugin_list_widget.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None

    @Slot()
    def _change_plugin_status_action(self, action_type: str):
        module_name = self._get_selected_module_name()
        if not module_name:
            QMessageBox.warning(self, "操作插件", "请先从列表中选择一个插件模块。")
            return

        if action_type == "enable":
            self.main_window_ref.update_plugin_enabled_status(module_name, True)
            self.plugin_status_changed_signal.emit(module_name, "enabled")
        elif action_type == "disable":
            self.main_window_ref.update_plugin_enabled_status(module_name, False)
            self.plugin_status_changed_signal.emit(module_name, "disabled")
        elif action_type == "session_block":
            self.main_window_ref.session_block_plugin_module(module_name)
            self.plugin_status_changed_signal.emit(module_name, "session_blocked")
        elif action_type == "unblock":
            self.plugin_manager.unblock_module_for_session(module_name)
            QMessageBox.information(self, "取消阻止",
                                    f"模块 {module_name} 已从会话阻止列表中移除。\n如果之前已禁用，您可能需要重新启用它并通过“扫描/重载插件”来使其生效。")
            self.plugin_status_changed_signal.emit(module_name, "unblocked_needs_scan")
        self._populate_plugin_list()


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
        self.connect_button.toggled.connect(self.connect_button_toggled)
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
        if hasattr(self.main_window_ref,
                   'error_logger') and self.main_window_ref.error_logger: self.main_window_ref.error_logger.log_warning(
            f"无效的波特率输入: '{self.baud_combo.currentText()}', 使用默认值 {baud_rate}"); self.baud_combo.setCurrentText(
            str(baud_rate))
        data_bits = int(self.data_bits_combo.currentText())
        parity = self.parity_combo.currentText()
        stop_bits_str = self.stop_bits_combo.currentText()
        try:
            stop_bits = float(stop_bits_str) if stop_bits_str == "1.5" else int(stop_bits_str)
        except ValueError:
            stop_bits = 1
        if hasattr(self.main_window_ref,
                   'error_logger') and self.main_window_ref.error_logger: self.main_window_ref.error_logger.log_warning(
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
        self.send_button = QPushButton("发送")
        self.receive_text_edit: Optional[QTextEdit] = None
        self.send_text_edit: Optional[QLineEdit] = None
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
        self.send_text_edit = QLineEdit()
        self.send_text_edit.setPlaceholderText("输入要发送的文本或Hex数据 (如: AB CD EF 或 Hello)")
        send_layout.addWidget(self.send_text_edit)
        send_options_layout = QHBoxLayout()
        send_options_layout.addWidget(self.send_hex_checkbox)
        send_options_layout.addStretch()
        clear_send_button = QPushButton("清空")
        clear_send_button.clicked.connect(self.send_text_edit.clear)
        send_options_layout.addWidget(clear_send_button)
        self.send_button.clicked.connect(self._on_send_clicked)
        send_options_layout.addWidget(self.send_button)
        send_layout.addLayout(send_options_layout)
        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)

    def _connect_signals(self):
        if self.send_text_edit:
            self.send_text_edit.returnPressed.connect(self._on_send_clicked)
        self.send_hex_checkbox.toggled.connect(self._on_hex_mode_toggled)

    @Slot(bool)
    def _on_hex_mode_toggled(self, checked: bool):
        if self.send_text_edit:
            if checked:
                self.send_text_edit.setPlaceholderText("输入Hex数据 (如: AB CD EF 或 ABCDEF)")
            else:
                self.send_text_edit.setPlaceholderText("输入要发送的文本")

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
        text_to_send = self.send_text_edit.text().strip()
        if not text_to_send:
            QMessageBox.information(self, "提示", "请输入要发送的数据。")
            return
        is_hex = self.send_hex_checkbox.isChecked()
        if is_hex and not self._validate_hex_input(text_to_send):
            QMessageBox.warning(self, "输入错误", "Hex数据格式不正确。\n请输入有效的十六进制数据，如: AB CD EF 或 ABCDEF")
            return

        self.send_basic_data_requested.emit(text_to_send, is_hex)

    def _validate_hex_input(self, text: str) -> bool:
        if not text: return False; hex_text = re.sub(r'[\s\-:,]', '', text.upper())
        if not re.match(r'^[0-9A-F]*$', hex_text): return False
        return len(hex_text) % 2 == 0 and len(hex_text) > 0

    def append_receive_text(self, text: str):
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
        if self.send_text_edit: self.send_text_edit.clear()

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


class SerialDebugger(QMainWindow):
    plot_target_renamed_signal = Signal(int, str)
    plot_target_removed_signal = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.app_instance = QApplication.instance()
        if self.app_instance is None: self.app_instance = QApplication(sys.argv)

        self.error_logger = ErrorLogger()
        self._setup_application_icon("resources/icon/image.png")
        self.setWindowTitle("YJ_Studio (Plugin Enhanced)")

        self.config_manager = ConfigManager(error_logger=self.error_logger, filename="serial_debugger_config_v2.json")
        self.theme_manager = ThemeManager(self.app_instance, error_logger=self.error_logger)
        self.data_recorder = DataRecorder(error_logger=self.error_logger)
        self.protocol_analyzer = ProtocolAnalyzer(error_logger=self.error_logger)
        self.serial_manager = SerialManager(error_logger=self.error_logger)
        self.frame_parser = FrameParser(error_logger=self.error_logger)

        self.current_serial_config = SerialPortConfig()
        self.current_frame_config = FrameConfig()
        self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
        self._parsed_frame_count: int = 0

        self.data_processor = DataProcessor(parent=self)
        self.data_processor.processed_data_signal.connect(self.on_data_processor_processed_data)
        self.data_processor.processing_error_signal.connect(self.on_data_processor_error)
        self.data_processor.processing_stats_signal.connect(self.on_data_processor_stats)
        self.data_processor.start()

        script_engine_host_functions = {
            'log_info': lambda msg: self.error_logger.log_info(f"[SCRIPT] {msg}"),
            'log_error': lambda msg: self.error_logger.log_error(f"[SCRIPT] {msg}", "SCRIPT_ERROR"),
            'send_serial_hex': self.send_serial_data_from_script_hex,
            'send_serial_text': self.send_serial_data_from_script_text,
            'get_panel_instance': self.get_dynamic_panel_instance_by_id,
        }
        self.script_engine = create_script_engine(
            debugger_instance=self,
            initial_host_functions=script_engine_host_functions,
            add_example_logging_hooks=True
        )

        self.plugin_manager = PluginManager(self)
        self._register_core_panels()

        self.enabled_plugin_module_names: Set[str] = set()

        self.dynamic_panel_instances: Dict[int, PanelInterface] = {}
        self.dynamic_panel_docks: Dict[int, QDockWidget] = {}
        self._next_dynamic_panel_id: int = 1
        self._next_global_receive_container_id: int = 1

        self.serial_config_panel_widget: Optional[SerialConfigDefinitionPanelWidget] = None
        self.dw_serial_config: Optional[QDockWidget] = None
        self.custom_log_panel_widget: Optional[CustomLogPanelWidget] = None
        self.dw_custom_log: Optional[QDockWidget] = None
        self.basic_comm_panel_widget: Optional[BasicCommPanelWidget] = None
        self.dw_basic_serial: Optional[QDockWidget] = None
        self.scripting_panel_widget: Optional[ScriptingPanelWidget] = None
        self.dw_scripting_panel: Optional[QDockWidget] = None

        self.status_bar_label = QLabel("未连接")
        self.setDockNestingEnabled(True)
        self._init_fixed_panels_ui()
        self.create_menus()

        self._load_configuration()

        self.plugin_manager.update_enabled_plugins(self.enabled_plugin_module_names)
        self.plugin_manager.discover_plugins("panel_plugins", load_only_enabled=True)
        self._update_add_panel_menu()

        self.populate_serial_ports_ui()
        self.update_fixed_panels_connection_status(False)

        self.serial_manager.connection_status_changed.connect(self.on_serial_connection_status_changed)
        self.serial_manager.data_received.connect(self.on_serial_data_received)
        self.serial_manager.error_occurred_signal.connect(self.on_serial_manager_error)
        self.frame_parser.frame_successfully_parsed.connect(self.on_frame_successfully_parsed)
        self.frame_parser.checksum_error.connect(self.on_frame_checksum_error)
        self.frame_parser.frame_parse_error.connect(self.on_frame_general_parse_error)

        self.error_logger.log_info("应用程序启动 (插件管理增强)。")

    def _register_core_panels(self):
        core_modules_to_enable = set()
        self.plugin_manager.register_panel_type(AdaptedParsePanelWidget, module_name='__main__')
        core_modules_to_enable.add('__main__')
        self.plugin_manager.register_panel_type(AdaptedSendPanelWidget, module_name='__main__')
        if PYQTGRAPH_AVAILABLE:
            self.plugin_manager.register_panel_type(AdaptedPlotWidgetPanel, module_name='__main__')

    def _init_fixed_panels_ui(self):
        self.serial_config_panel_widget = SerialConfigDefinitionPanelWidget(parent_main_window=self)
        self.dw_serial_config = QDockWidget("串口与帧定义", self)
        self.dw_serial_config.setObjectName("SerialConfigDock")
        self.dw_serial_config.setWidget(self.serial_config_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dw_serial_config)
        self.serial_config_panel_widget.connect_button_toggled.connect(self.toggle_connection_action_handler)
        self.serial_config_panel_widget.refresh_ports_requested.connect(self.populate_serial_ports_ui)
        self.serial_config_panel_widget.config_changed.connect(self.update_current_serial_frame_configs_from_ui)

        self.custom_log_panel_widget = CustomLogPanelWidget(main_window_ref=self)
        self.dw_custom_log = QDockWidget("协议帧原始数据", self)
        self.dw_custom_log.setObjectName("CustomProtocolLogDock")
        self.dw_custom_log.setWidget(self.custom_log_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dw_custom_log)

        self.basic_comm_panel_widget = BasicCommPanelWidget(main_window_ref=self)
        self.dw_basic_serial = QDockWidget("基本收发", self)
        self.dw_basic_serial.setObjectName("BasicSerialDock")
        self.dw_basic_serial.setWidget(self.basic_comm_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dw_basic_serial)
        self.basic_comm_panel_widget.send_basic_data_requested.connect(self.send_basic_serial_data_action)

        try:
            self.tabifyDockWidget(self.dw_custom_log, self.dw_basic_serial)
        except AttributeError as e:
            self.error_logger.log_warning(f"[UI_SETUP] 无法标签页化停靠窗口 (日志/基本): {e}")

        self.scripting_panel_widget = ScriptingPanelWidget(main_window_ref=self)
        self.dw_scripting_panel = QDockWidget("脚本引擎", self)
        self.dw_scripting_panel.setObjectName("ScriptingPanelDock")
        self.dw_scripting_panel.setWidget(self.scripting_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dw_scripting_panel)
        if self.scripting_panel_widget: self.scripting_panel_widget.execute_script_requested.connect(
            self._handle_script_execution_request)

        self.statusBar().addWidget(self.status_bar_label)

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("文件(&F)")
        load_config_action = QAction("加载配置...", self)
        load_config_action.triggered.connect(self.load_configuration_action_dialog)
        file_menu.addAction(load_config_action)
        save_config_action = QAction("保存配置...", self)
        save_config_action.triggered.connect(self.save_configuration_action_dialog)
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
        if self.dw_serial_config: self.view_menu.addAction(self.dw_serial_config.toggleViewAction())
        if self.dw_custom_log: self.view_menu.addAction(self.dw_custom_log.toggleViewAction())
        if self.dw_basic_serial: self.view_menu.addAction(self.dw_basic_serial.toggleViewAction())
        if self.dw_scripting_panel: self.view_menu.addAction(self.dw_scripting_panel.toggleViewAction())
        self.view_menu.addSeparator()

        theme_menu = self.view_menu.addMenu("背景样式")
        for theme_name in Constants.THEME_OPTIONS:
            action = QAction(f"{theme_name.replace('_', ' ').capitalize()} 主题", self)
            action.triggered.connect(lambda checked=False, tn=theme_name: self.apply_theme_action(tn))
            theme_menu.addAction(action)
        load_external_qss_action = QAction("加载外部QSS文件...", self)
        load_external_qss_action.triggered.connect(self.load_external_qss_file_action)
        theme_menu.addAction(load_external_qss_action)

        tools_menu = self.menuBar().addMenu("工具(&T)")
        self.add_panel_menu = tools_menu.addMenu("添加面板")
        self._update_add_panel_menu()

        manage_plugins_action = QAction("插件管理器...", self)
        manage_plugins_action.triggered.connect(self.open_plugin_manager_dialog)
        tools_menu.addAction(manage_plugins_action)

        reload_plugins_action = QAction("扫描/重载插件", self)
        reload_plugins_action.triggered.connect(self.reload_all_plugins_action)
        tools_menu.addAction(reload_plugins_action)
        tools_menu.addSeparator()

        if PYQTGRAPH_AVAILABLE:
            clear_all_plots_action = QAction("清空所有波形图", self)
            clear_all_plots_action.triggered.connect(self.clear_all_plot_panels_action)
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

    def _update_add_panel_menu(self):
        if not hasattr(self, 'add_panel_menu'): return
        self.add_panel_menu.clear()
        available_panel_types = self.plugin_manager.get_creatable_panel_types()
        self.error_logger.log_info(f"[UI_SETUP] 可用动态面板插件: {available_panel_types}")
        if not available_panel_types:
            no_panels_action = QAction("无可用动态面板插件", self)
            no_panels_action.setEnabled(False)
            self.add_panel_menu.addAction(no_panels_action)
        else:
            for type_name, display_name in available_panel_types.items():
                action = QAction(f"添加 {display_name}...", self)
                action.triggered.connect(
                    lambda checked=False, pt=type_name: self.add_dynamic_panel_action(panel_type_name=pt))
                self.add_panel_menu.addAction(action)

    def _load_configuration(self):
        config_data = self.config_manager.load_config()
        if not config_data:
            self.error_logger.log_warning("[CONFIG] 未能加载配置文件，使用默认设置。")
            self.current_serial_config = SerialPortConfig()
            self.current_frame_config = FrameConfig()
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
            if self.serial_config_panel_widget: self.serial_config_panel_widget.update_ui_from_main_configs(
                self.current_serial_config, self.current_frame_config, self.active_checksum_mode)
            self._next_dynamic_panel_id = 1
            self._next_global_receive_container_id = 1
            self.enabled_plugin_module_names = set()
            return

        self.current_serial_config = SerialPortConfig(**config_data.get("serial_port", {}))
        self.current_frame_config = FrameConfig(**config_data.get("frame_definition", {}))
        checksum_mode_name = config_data.get("checksum_mode", Constants.DEFAULT_CHECKSUM_MODE.name)
        try:
            self.active_checksum_mode = ChecksumMode[checksum_mode_name]
        except KeyError:
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE

        if self.serial_config_panel_widget: self.serial_config_panel_widget.update_ui_from_main_configs(
            self.current_serial_config, self.current_frame_config, self.active_checksum_mode)
        if self.custom_log_panel_widget: self.custom_log_panel_widget.apply_config(
            config_data.get("custom_log_panel", {}))
        if self.basic_comm_panel_widget: self.basic_comm_panel_widget.apply_config(
            config_data.get("basic_comm_panel", {}))
        if self.scripting_panel_widget: self.scripting_panel_widget.apply_config(config_data.get("scripting_panel", {}))

        loaded_theme_info = config_data.get("ui_theme_info", {"type": "internal", "name": "light", "path": None})
        if loaded_theme_info["type"] == "internal" and loaded_theme_info.get("name"):
            self.theme_manager.apply_theme(loaded_theme_info["name"])
        elif loaded_theme_info["type"] == "external" and loaded_theme_info.get("path"):
            self.theme_manager.apply_external_qss(loaded_theme_info["path"])

        self.enabled_plugin_module_names = set(config_data.get("enabled_plugins", []))
        # self.plugin_manager.update_enabled_plugins(self.enabled_plugin_module_names) # Moved to after __init__

        dynamic_panels_config = config_data.get("dynamic_panels", [])
        highest_panel_id = 0
        for panel_cfg_item in dynamic_panels_config:
            panel_type = panel_cfg_item.get("panel_type_name")
            panel_id = panel_cfg_item.get("panel_id")
            dock_name = panel_cfg_item.get("dock_name")
            specific_config = panel_cfg_item.get("config", {})

            module_name_of_panel_type = self.plugin_manager.get_module_name_for_panel_type(
                panel_type) if panel_type else None
            can_load_from_config = False
            if module_name_of_panel_type == "__main__":
                can_load_from_config = True
            elif module_name_of_panel_type:
                can_load_from_config = module_name_of_panel_type in self.enabled_plugin_module_names and \
                                       module_name_of_panel_type not in self.plugin_manager.session_blocklisted_modules

            if panel_type and panel_id is not None and can_load_from_config:
                self.add_dynamic_panel_action(panel_type_name=panel_type, initial_config=specific_config,
                                              panel_id_override=panel_id, dock_name_override=dock_name,
                                              from_config_load=True)
                if panel_id > highest_panel_id: highest_panel_id = panel_id
            elif panel_type and panel_id is not None and not can_load_from_config:
                self.error_logger.log_info(
                    f"[CONFIG_LOAD] 面板 ID {panel_id} (类型: {panel_type}) 由于其模块未启用或被阻止而未加载。")

        self._next_dynamic_panel_id = config_data.get("next_dynamic_panel_id", highest_panel_id + 1)
        self._next_global_receive_container_id = config_data.get("next_global_receive_container_id", 1)

        settings = QSettings("MyCompany", "SerialDebuggerProV2")
        geom_b64_str = settings.value("window_geometry")
        state_b64_str = settings.value("window_state")
        if isinstance(geom_b64_str, str): self.restoreGeometry(QByteArray.fromBase64(geom_b64_str.encode()))
        if isinstance(state_b64_str, str): self.restoreState(QByteArray.fromBase64(state_b64_str.encode()))

        self.error_logger.log_info("[CONFIG] 配置已加载并应用到UI。")
        self.update_all_parse_panels_plot_targets()

    def _gather_current_configuration(self) -> Dict[str, Any]:
        self.update_current_serial_frame_configs_from_ui()
        dynamic_panels_list = []
        for panel_id, panel_instance in self.dynamic_panel_instances.items():
            panel_type = self.plugin_manager.get_panel_type_from_instance(panel_instance)
            dock_widget = self.dynamic_panel_docks.get(panel_id)
            if panel_type and dock_widget:
                dynamic_panels_list.append(
                    {"panel_type_name": panel_type, "panel_id": panel_id, "dock_name": dock_widget.windowTitle(),
                     "config": panel_instance.get_config()})

        config_data = {
            "serial_port": vars(self.current_serial_config), "frame_definition": vars(self.current_frame_config),
            "checksum_mode": self.active_checksum_mode.name, "ui_theme_info": self.theme_manager.current_theme_info,
            "custom_log_panel": self.custom_log_panel_widget.get_config() if self.custom_log_panel_widget else {},
            "basic_comm_panel": self.basic_comm_panel_widget.get_config() if self.basic_comm_panel_widget else {},
            "scripting_panel": self.scripting_panel_widget.get_config() if self.scripting_panel_widget else {},
            "dynamic_panels": dynamic_panels_list,
            "next_dynamic_panel_id": self._next_dynamic_panel_id,
            "next_global_receive_container_id": self._next_global_receive_container_id,
            "enabled_plugins": list(self.enabled_plugin_module_names)
        }
        return config_data

    @Slot()
    def open_plugin_manager_dialog(self):
        dialog = PluginManagementDialog(self.plugin_manager, self, self)
        dialog.plugin_status_changed_signal.connect(self._handle_plugin_status_change_from_dialog)
        dialog.exec()

    @Slot(str, str)
    def _handle_plugin_status_change_from_dialog(self, module_name: str, new_status: str):
        self.error_logger.log_info(f"插件管理器请求更新模块 '{module_name}' 状态为 '{new_status}'。", "PLUGIN_MGMT")
        if new_status in ["enabled", "disabled", "session_blocked", "unblocked_needs_scan"]:
            QMessageBox.information(self, "插件状态变更",
                                    f"插件模块 '{module_name}' 的状态已更新。\n"
                                    "将执行插件重载以应用更改。活动的面板实例可能会被关闭和尝试恢复。")
            self.reload_all_plugins_action(preserve_configs=True)
        self._update_add_panel_menu()

    def update_plugin_enabled_status(self, module_name: str, enable: bool):
        if enable:
            self.enabled_plugin_module_names.add(module_name)
            if module_name in self.plugin_manager.session_blocklisted_modules:
                self.plugin_manager.unblock_module_for_session(module_name)
            self.error_logger.log_info(f"模块 '{module_name}' 已标记为启用。", "PLUGIN_MGMT")
        else:
            self.enabled_plugin_module_names.discard(module_name)
            self.error_logger.log_info(f"模块 '{module_name}' 已标记为禁用。", "PLUGIN_MGMT")
            self._process_module_disable_or_block(module_name)

        self.plugin_manager.update_enabled_plugins(self.enabled_plugin_module_names)
        # Persist the change to enabled_plugins list in the main config
        current_app_config = self.config_manager.load_config()  # Load current full config
        if not current_app_config: current_app_config = {}  # Handle case where config doesn't exist
        current_app_config["enabled_plugins"] = list(self.enabled_plugin_module_names)
        self.config_manager.save_config(current_app_config)  # Save updated full config

    def session_block_plugin_module(self, module_name: str):
        self.error_logger.log_info(f"请求会话级阻止模块: {module_name}", "PLUGIN_MGMT")
        self._process_module_disable_or_block(module_name)
        self.plugin_manager.block_module_for_session(module_name)
        # Update enabled_plugins in config as blocking also implies disabling for persistence
        if module_name in self.enabled_plugin_module_names:
            self.enabled_plugin_module_names.discard(module_name)
            self.plugin_manager.update_enabled_plugins(self.enabled_plugin_module_names)
            current_app_config = self.config_manager.load_config()
            if not current_app_config: current_app_config = {}
            current_app_config["enabled_plugins"] = list(self.enabled_plugin_module_names)
            self.config_manager.save_config(current_app_config)

    def _process_module_disable_or_block(self, module_name: str):
        panel_ids_to_remove = []
        for panel_id, panel_instance in list(self.dynamic_panel_instances.items()):
            instance_panel_type = self.plugin_manager.get_panel_type_from_instance(panel_instance)
            if instance_panel_type:
                instance_module_name = self.plugin_manager.get_module_name_for_panel_type(instance_panel_type)
                if instance_module_name == module_name:
                    panel_ids_to_remove.append(panel_id)

        if panel_ids_to_remove:
            self.error_logger.log_info(f"正在关闭模块 {module_name} 的 {len(panel_ids_to_remove)} 个活动面板实例...",
                                       "PLUGIN_MGMT")
            for panel_id in panel_ids_to_remove:
                self.remove_dynamic_panel(panel_id)

        types_to_unregister = [
            pt_name for pt_name, (_, _, mod_name) in self.plugin_manager.registered_panel_types.items()
            if mod_name == module_name
        ]
        for pt_name in types_to_unregister:
            self.plugin_manager.unregister_panel_type(pt_name)

        self._update_add_panel_menu()

    @Slot()
    def reload_all_plugins_action(self, preserve_configs: bool = True):
        self.error_logger.log_info("开始插件热重载流程...")

        if preserve_configs:
            self.plugin_manager.store_active_panel_configs(self.dynamic_panel_instances)

        active_panel_ids = list(self.dynamic_panel_instances.keys())
        if active_panel_ids:
            self.error_logger.log_info(f"将要移除 {len(active_panel_ids)} 个活动面板实例...")
            for panel_id in active_panel_ids:
                self.remove_dynamic_panel(panel_id)

        if self.dynamic_panel_instances or self.dynamic_panel_docks:
            self.error_logger.log_warning(
                f"热重载后仍有残留面板实例或停靠窗口! Instances: {len(self.dynamic_panel_instances)}, Docks: {len(self.dynamic_panel_docks)}")
            self.dynamic_panel_instances.clear()
            self.dynamic_panel_docks.clear()

        self.plugin_manager.update_enabled_plugins(self.enabled_plugin_module_names)

        self.error_logger.log_info("正在重新扫描和加载插件模块...")
        reloaded_panel_type_names = self.plugin_manager.discover_plugins(
            "panel_plugins",
            reload_modules=True,
            load_only_enabled=True
        )
        self.error_logger.log_info(
            f"插件模块扫描/重载完毕。活动类型: {list(self.plugin_manager.get_creatable_panel_types().keys())}")

        self._update_add_panel_menu()
        self.error_logger.log_info("“添加面板”菜单已更新。")

        restored_count = 0
        if preserve_configs:
            self.error_logger.log_info("正在尝试恢复之前活动的面板...")
            for panel_type_name_to_restore in self.plugin_manager.get_creatable_panel_types().keys():
                stored_configs = self.plugin_manager.get_stored_configs_for_reload(panel_type_name_to_restore)
                for panel_data in stored_configs:
                    restored_panel = self.add_dynamic_panel_action(
                        panel_type_name=panel_type_name_to_restore,
                        initial_config=panel_data.get("config"),
                        panel_id_override=panel_data.get("panel_id"),
                        dock_name_override=panel_data.get("dock_name"),
                        from_config_load=True
                    )
                    if restored_panel: restored_count += 1
            self.plugin_manager.clear_stored_configs()

        self.error_logger.log_info(f"插件热重载流程完毕。成功恢复 {restored_count} 个面板实例。")
        sender_obj = self.sender()
        if not isinstance(sender_obj, QDialog) or (
                isinstance(sender_obj, QDialog) and sender_obj.windowTitle() != "插件管理器"):
            QMessageBox.information(self, "插件重载", f"插件已重新加载。\n成功恢复 {restored_count} 个面板实例。")

    def _setup_application_icon(self, icon_filename: str):
        try:
            base_path = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else Path(
                __file__).resolve().parent
            icon_path = base_path / icon_filename
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
            else:
                self.error_logger.log_warning(f"应用程序图标文件未找到: {icon_path}")
        except Exception as e:
            self.error_logger.log_error(f"设置应用程序图标时出错: {e}", "APPLICATION_ICON_SETUP")

    @Slot(str)
    def add_dynamic_panel_action(self, panel_type_name: str, initial_config: Optional[Dict[str, Any]] = None,
                                 panel_id_override: Optional[int] = None, dock_name_override: Optional[str] = None,
                                 from_config_load: bool = False) -> Optional[PanelInterface]:
        panel_id_to_use = panel_id_override if panel_id_override is not None else self._next_dynamic_panel_id
        panel_widget = self.plugin_manager.create_panel_instance(panel_type_name, panel_id_to_use, initial_config)
        if not panel_widget: self.error_logger.log_error(f"创建面板实例失败: {panel_type_name}",
                                                         "UI_ACTION"); return None
        actual_dock_title = dock_name_override
        if not actual_dock_title:
            if not from_config_load:
                default_title_from_panel = panel_widget.get_initial_dock_title()
                text, ok = QInputDialog.getText(self, f"新{panel_widget.PANEL_DISPLAY_NAME}", "面板显示名称:",
                                                QLineEdit.EchoMode.Normal, default_title_from_panel)
                if not ok or not text.strip(): self.error_logger.log_info(
                    f"[UI_ACTION] 用户取消添加新面板 '{panel_type_name}'."); return None
                actual_dock_title = text.strip()
            else:
                actual_dock_title = panel_widget.get_initial_dock_title()
        dw_panel = QDockWidget(actual_dock_title, self)
        dw_panel.setObjectName(f"{panel_type_name}_Dock_{panel_id_to_use}")
        dw_panel.setWidget(panel_widget)
        dw_panel.installEventFilter(self)
        panel_widget.dock_title_changed.connect(dw_panel.setWindowTitle)
        all_current_dynamic_docks = list(self.dynamic_panel_docks.values())
        target_tab_dock = None
        if all_current_dynamic_docks:
            target_tab_dock = all_current_dynamic_docks[-1]
        elif self.dw_scripting_panel:
            target_tab_dock = self.dw_scripting_panel
        if target_tab_dock:
            self.tabifyDockWidget(target_tab_dock, dw_panel)
        else:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dw_panel)
        self.dynamic_panel_instances[panel_id_to_use] = panel_widget
        self.dynamic_panel_docks[panel_id_to_use] = dw_panel
        if panel_id_override is None:
            self._next_dynamic_panel_id += 1
        elif panel_id_to_use >= self._next_dynamic_panel_id:
            self._next_dynamic_panel_id = panel_id_to_use + 1
        if hasattr(self, 'view_menu'): self.view_menu.addAction(dw_panel.toggleViewAction())
        panel_widget.on_panel_added()
        dw_panel.show()
        if isinstance(panel_widget, AdaptedParsePanelWidget): panel_widget.update_children_plot_targets()
        if isinstance(panel_widget, AdaptedPlotWidgetPanel): self.update_all_parse_panels_plot_targets()
        if self.error_logger and not from_config_load: self.error_logger.log_info(
            f"[UI_ACTION] 已添加动态面板: 类型='{panel_type_name}', ID={panel_id_to_use}, 名称='{actual_dock_title}'")
        return panel_widget

    def remove_dynamic_panel(self, panel_id_to_remove: int):
        panel_widget = self.dynamic_panel_instances.pop(panel_id_to_remove, None)
        dock_widget = self.dynamic_panel_docks.pop(panel_id_to_remove, None)
        if panel_widget: panel_widget.on_panel_removed(); panel_widget.deleteLater()
        if dock_widget:
            if hasattr(self, 'view_menu'): view_action = dock_widget.toggleViewAction();
            if view_action: self.view_menu.removeAction(view_action)
            self.removeDockWidget(dock_widget)
            dock_widget.deleteLater()
            self.error_logger.log_info(
                f"[UI_ACTION] 已移除动态面板 ID: {panel_id_to_remove}, 名称: '{dock_widget.windowTitle()}'")
        self.update_all_parse_panels_plot_targets()
        if PYQTGRAPH_AVAILABLE and isinstance(panel_widget,
                                              AdaptedPlotWidgetPanel): self.plot_target_removed_signal.emit(
            panel_id_to_remove)

    def eventFilter(self, watched_object: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Close and isinstance(watched_object, QDockWidget):
            panel_id_to_remove = None
            for pid, dock in self.dynamic_panel_docks.items():
                if dock == watched_object:
                    reply = QMessageBox.question(self, "关闭/卸载面板确认",
                                                 f"您确定要关闭并卸载面板 '{dock.windowTitle()}' 吗？\n此操作将移除该面板实例，并且在下次保存配置前不会自动加载。",
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                 QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.Yes:
                        panel_id_to_remove = pid
                    else:
                        event.ignore(); return True
                    break
            if panel_id_to_remove is not None: self.remove_dynamic_panel(
                panel_id_to_remove); event.accept(); return True
        return super().eventFilter(watched_object, event)

    @Slot()
    def load_configuration_action_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "加载配置文件", "", "JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            # Clear existing dynamic panels before loading new config
            for panel_id in list(self.dynamic_panel_instances.keys()):  # Iterate over a copy of keys
                self.remove_dynamic_panel(panel_id)

            # Reset panel ID counters before loading
            self._next_dynamic_panel_id = 1
            self._next_global_receive_container_id = 1
            self.plugin_manager.session_blocklisted_modules.clear()  # Clear session blocklist on full config load

            temp_loader = ConfigManager(filename=file_path, error_logger=self.error_logger)
            loaded_cfg = temp_loader.load_config()
            if loaded_cfg:
                self.current_serial_config = SerialPortConfig(**loaded_cfg.get("serial_port", {}))
                self.current_frame_config = FrameConfig(**loaded_cfg.get("frame_definition", {}))
                checksum_mode_name = loaded_cfg.get("checksum_mode", Constants.DEFAULT_CHECKSUM_MODE.name)
                try:
                    self.active_checksum_mode = ChecksumMode[checksum_mode_name]
                except KeyError:
                    self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
                if self.custom_log_panel_widget: self.custom_log_panel_widget.apply_config(
                    loaded_cfg.get("custom_log_panel", {}))
                if self.basic_comm_panel_widget: self.basic_comm_panel_widget.apply_config(
                    loaded_cfg.get("basic_comm_panel", {}))
                if self.scripting_panel_widget: self.scripting_panel_widget.apply_config(
                    loaded_cfg.get("scripting_panel", {}))
                loaded_theme_info = loaded_cfg.get("ui_theme_info", {"type": "internal", "name": "light", "path": None})
                if loaded_theme_info["type"] == "internal" and loaded_theme_info.get("name"):
                    self.theme_manager.apply_theme(loaded_theme_info["name"])
                elif loaded_theme_info["type"] == "external" and loaded_theme_info.get("path"):
                    self.theme_manager.apply_external_qss(loaded_theme_info["path"])

                self.enabled_plugin_module_names = set(loaded_cfg.get("enabled_plugins", []))
                self.plugin_manager.update_enabled_plugins(self.enabled_plugin_module_names)
                # Re-discover based on the *newly loaded* enabled list
                # Do not reload modules here, just discover based on new enabled list after clearing old registrations
                self.plugin_manager.clear_all_registered_types()  # Clear old types
                self._register_core_panels()  # Re-register core panels
                self.plugin_manager.discover_plugins("panel_plugins", reload_modules=False, load_only_enabled=True)
                self._update_add_panel_menu()

                dynamic_panels_config = loaded_cfg.get("dynamic_panels", [])
                highest_panel_id = 0
                for panel_cfg_item in dynamic_panels_config:
                    panel_type = panel_cfg_item.get("panel_type_name")
                    panel_id = panel_cfg_item.get("panel_id")
                    dock_name = panel_cfg_item.get("dock_name")
                    specific_config = panel_cfg_item.get("config", {})

                    # Check if the panel type is actually available (registered) after discovery
                    if panel_type in self.plugin_manager.get_creatable_panel_types():
                        self.add_dynamic_panel_action(panel_type_name=panel_type, initial_config=specific_config,
                                                      panel_id_override=panel_id, dock_name_override=dock_name,
                                                      from_config_load=True)
                        if panel_id > highest_panel_id: highest_panel_id = panel_id
                    else:
                        self.error_logger.log_warning(
                            f"[CONFIG_LOAD] 面板类型 '{panel_type}' 在配置中，但在当前已启用/可用的插件中未找到，跳过加载。")

                self._next_dynamic_panel_id = loaded_cfg.get("next_dynamic_panel_id", highest_panel_id + 1)
                self._next_global_receive_container_id = loaded_cfg.get("next_global_receive_container_id", 1)
                if self.serial_config_panel_widget: self.serial_config_panel_widget.update_ui_from_main_configs(
                    self.current_serial_config, self.current_frame_config, self.active_checksum_mode)
                self.update_all_parse_panels_plot_targets()
                self.config_manager.config_file = Path(file_path)
                QMessageBox.information(self, "配置加载", f"配置已从 '{file_path}' 加载。")
            else:
                QMessageBox.warning(self, "配置加载", f"无法从 '{file_path}' 加载有效配置，或文件为空/默认。")

    @Slot()
    def save_configuration_action_dialog(self):
        current_config_path = str(self.config_manager.config_file)
        file_path, _ = QFileDialog.getSaveFileName(self, "保存配置文件", current_config_path,
                                                   "JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            config_to_save = self._gather_current_configuration()
            temp_saver = ConfigManager(filename=file_path, error_logger=self.error_logger)
            temp_saver.save_config(config_to_save)
            self.config_manager.config_file = Path(file_path)
            QMessageBox.information(self, "配置保存", f"配置已保存到 {file_path}。")

    @Slot(bool)
    def toggle_connection_action_handler(self, connect_request: bool):
        if connect_request:
            if not self.serial_manager.is_connected:
                self.update_current_serial_frame_configs_from_ui()
                if not self.current_serial_config.port_name or self.current_serial_config.port_name == "无可用端口": QMessageBox.warning(
                    self, "连接错误", "未选择有效的串口。");
                if self.serial_config_panel_widget and hasattr(self.serial_config_panel_widget,
                                                               'connect_button'): self.serial_config_panel_widget.connect_button.setChecked(
                    False); return
                self.serial_manager.connect_port(self.current_serial_config)
                if self.serial_manager.is_connected: self.frame_parser.clear_buffer(); self._parsed_frame_count = 0
        else:
            if self.serial_manager.is_connected: self.serial_manager.disconnect_port()

    @Slot()
    def populate_serial_ports_ui(self) -> None:
        available_ports = self.serial_manager.get_available_ports()
        if self.serial_config_panel_widget: current_port = self.current_serial_config.port_name if self.current_serial_config else None; self.serial_config_panel_widget.update_port_combo_display(
            available_ports, current_port)
        self.update_fixed_panels_connection_status(self.serial_manager.is_connected)

    @Slot(bool, str)
    def on_serial_connection_status_changed(self, is_connected: bool, message: str):
        self.update_fixed_panels_connection_status(is_connected)
        self.status_bar_label.setText(message)
        if not is_connected and "资源错误" in message: QMessageBox.critical(self, "串口错误", message)

    def update_fixed_panels_connection_status(self, connected: bool):
        if self.serial_config_panel_widget: self.serial_config_panel_widget.set_connection_status_display(connected)
        if self.basic_comm_panel_widget: self.basic_comm_panel_widget.set_send_enabled(connected)
        for panel_instance in self.dynamic_panel_instances.values():
            if isinstance(panel_instance, AdaptedSendPanelWidget): panel_instance.update_send_button_state(connected)
        if not connected and self.serial_config_panel_widget:
            if hasattr(self.serial_config_panel_widget, 'port_combo') and (
                    not self.serial_config_panel_widget.port_combo.count() or self.serial_config_panel_widget.port_combo.currentText() == "无可用端口"): self.status_bar_label.setText(
                "无可用串口")

    @Slot(QByteArray)
    def on_serial_data_received(self, data: QByteArray):
        if self.basic_comm_panel_widget: self._append_to_basic_receive_text_edit(data, source="RX")
        if hasattr(self, 'data_recorder'): self.data_recorder.record_raw_frame(datetime.now(), data.data(), "RX")
        self.frame_parser.append_data(data)
        self.update_current_serial_frame_configs_from_ui()
        self.frame_parser.try_parse_frames(self.current_frame_config, self.active_checksum_mode)

    @Slot(str, QByteArray)
    def on_frame_successfully_parsed(self, func_id_hex: str, data_payload_ba: QByteArray):
        self._parsed_frame_count += 1
        hex_payload_str = data_payload_ba.toHex(' ').data().decode('ascii').upper()
        self.append_to_custom_protocol_log_formatted(datetime.now(), "RX Parsed",
                                                     f"FID:{func_id_hex} Payload:{hex_payload_str}", True)
        msg = f"成功解析帧: #{self._parsed_frame_count}, FID: {func_id_hex.upper()}"
        self.status_bar_label.setText(msg)
        if self.error_logger: self.error_logger.log_info(f"{msg} Payload len: {data_payload_ba.size()}")
        if hasattr(self, 'protocol_analyzer'): self.protocol_analyzer.analyze_frame(data_payload_ba, 'rx')
        dispatched_to_a_panel = False
        for panel_instance in self.dynamic_panel_instances.values():
            if isinstance(panel_instance, AdaptedParsePanelWidget):
                if func_id_hex.upper() == panel_instance.get_target_func_id().upper(): panel_instance.dispatch_data(
                    data_payload_ba); dispatched_to_a_panel = True
        if not dispatched_to_a_panel and self.error_logger: self.error_logger.log_debug(
            f"[FRAME_PARSER] Frame FID {func_id_hex} no target parse panel.")
        if hasattr(self, 'data_processor'): self.data_processor.add_data(func_id_hex, QByteArray(data_payload_ba))

    @Slot(str, QByteArray)
    def on_frame_checksum_error(self, error_message: str, faulty_frame: QByteArray):
        self.status_bar_label.setText("校验和错误!")
        hex_frame_str = faulty_frame.toHex(' ').data().decode('ascii').upper()
        self.append_to_custom_protocol_log_formatted(datetime.now(), "RX Error",
                                                     f"ChecksumError: {error_message} Frame: {hex_frame_str}", True)
        if hasattr(self, 'protocol_analyzer'): self.protocol_analyzer.analyze_frame(faulty_frame, 'rx', is_error=True)

    @Slot(str, QByteArray)
    def on_frame_general_parse_error(self, error_message: str, buffer_state: QByteArray):
        self.status_bar_label.setText(f"协议解析错误: {error_message}")

    @Slot(str)
    def on_serial_manager_error(self, error_message: str):
        self.status_bar_label.setText(error_message); QMessageBox.warning(self, "串口通讯警告", error_message)

    def get_next_global_receive_container_id(self) -> int:
        current_id = self._next_global_receive_container_id; self._next_global_receive_container_id += 1; return current_id

    def update_current_serial_frame_configs_from_ui(self):
        if not self.serial_config_panel_widget: return
        self.current_serial_config = self.serial_config_panel_widget.get_serial_config_from_ui()
        self.current_frame_config = self.serial_config_panel_widget.get_frame_config_from_ui()
        self.active_checksum_mode = self.serial_config_panel_widget.get_checksum_mode_from_ui()

    def _append_to_basic_receive_text_edit(self, data: QByteArray, source: str = "RX"):
        if not self.basic_comm_panel_widget or not self.basic_comm_panel_widget.receive_text_edit: return
        final_log_string = ""
        if self.basic_comm_panel_widget.recv_timestamp_checkbox_is_checked(): final_log_string += datetime.now().strftime(
            "[%H:%M:%S.%f")[:-3] + "] "
        final_log_string += f"{source}: "
        if self.basic_comm_panel_widget.recv_hex_checkbox_is_checked():
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

    def append_to_custom_protocol_log_formatted(self, timestamp: datetime, source: str, content: str,
                                                is_content_hex: bool):
        if not self.custom_log_panel_widget: return; final_log_string = ""
        if self.custom_log_panel_widget.timestamp_checkbox_is_checked(): final_log_string += timestamp.strftime(
            "[%H:%M:%S.%f")[:-3] + "] "
        final_log_string += f"{source}: "
        if self.custom_log_panel_widget.hex_checkbox_is_checked():
            if not is_content_hex:
                try:
                    final_log_string += QByteArray(content.encode('latin-1')).toHex(' ').data().decode().upper()
                except Exception:
                    final_log_string += content
            else:
                final_log_string += content
        else:
            if is_content_hex:
                final_log_string += content
            else:
                final_log_string += content
        if not final_log_string.endswith('\n'): final_log_string += '\n'
        self.custom_log_panel_widget.append_log(final_log_string)

    def assemble_custom_frame_from_send_panel_data(self, panel_target_func_id_str: str,
                                                   panel_send_data_containers: List[SendDataContainerWidget]) -> \
    Optional[QByteArray]:
        self.update_current_serial_frame_configs_from_ui()
        cfg = self.current_frame_config
        try:
            head_ba = QByteArray.fromHex(cfg.head.encode('ascii'))
            saddr_ba = QByteArray.fromHex(cfg.s_addr.encode('ascii')) 
            daddr_ba = QByteArray.fromHex(cfg.d_addr.encode('ascii'))
            id_ba = QByteArray.fromHex(panel_target_func_id_str.encode('ascii'))
        except ValueError as e:
            msg = f"帧头/地址/面板功能码({panel_target_func_id_str}) Hex格式错误: {e}"
            self.status_bar_label.setText(msg)
            if self.error_logger: 
                self.error_logger.log_warning(msg)
            return None
        if not (head_ba.size() == 1 and saddr_ba.size() == 1 and daddr_ba.size() == 1 and id_ba.size() == 1):
            msg = "帧头/地址/面板功能码 Hex长度必须为1字节 (2个Hex字符)"; self.status_bar_label.setText(msg)
        if self.error_logger:
            self.error_logger.log_warning(msg)
            return None
        data_content_ba = QByteArray()
        for scw_widget in panel_send_data_containers:
            item_bytes = scw_widget.get_bytes()
            if item_bytes is None: msg = f"发送面板(ID:{panel_target_func_id_str}) 项 '{scw_widget.name_edit.text()}' 数值错误"; self.status_bar_label.setText(
                msg);
            if self.error_logger: self.error_logger.log_warning(msg); return None
            data_content_ba.append(item_bytes)
        len_val = data_content_ba.size()
        len_ba = QByteArray(struct.pack('<H', len_val))
        frame_part_for_checksum = QByteArray()
        frame_part_for_checksum.append(head_ba)
        frame_part_for_checksum.append(saddr_ba)
        frame_part_for_checksum.append(daddr_ba)
        frame_part_for_checksum.append(id_ba)
        frame_part_for_checksum.append(len_ba)
        frame_part_for_checksum.append(data_content_ba)
        checksum_bytes_to_append = QByteArray()
        active_mode = self.active_checksum_mode
        sum_check_text, add_check_text = "", ""
        if active_mode == ChecksumMode.CRC16_CCITT_FALSE:
            crc_val = calculate_frame_crc16(frame_part_for_checksum)
            checksum_bytes_to_append.append(struct.pack('>H', crc_val))
            sum_check_text = f"0x{crc_val:04X}"
        else:
            sc_val, ac_val = calculate_original_checksums_python(frame_part_for_checksum)
            checksum_bytes_to_append.append(bytes([sc_val]))
            checksum_bytes_to_append.append(bytes([ac_val]))
            sum_check_text = f"0x{sc_val:02X}"
            add_check_text = f"0x{ac_val:02X}"
        if self.serial_config_panel_widget:
            self.serial_config_panel_widget.update_checksum_display(sum_check_text, add_check_text)
        final_frame = QByteArray(frame_part_for_checksum)
        final_frame.append(checksum_bytes_to_append)
        return final_frame

    def get_available_plot_targets(self) -> Dict[int, str]:
        targets = {}
        if not PYQTGRAPH_AVAILABLE: return targets
        for panel_id, panel_instance in self.dynamic_panel_instances.items():
            if isinstance(panel_instance, AdaptedPlotWidgetPanel): targets[panel_id] = panel_instance.plot_name
        return targets

    def update_all_parse_panels_plot_targets(self):
        if not PYQTGRAPH_AVAILABLE: return
        for panel_instance in self.dynamic_panel_instances.values():
            if isinstance(panel_instance, AdaptedParsePanelWidget): panel_instance.update_children_plot_targets()

    @Slot(int, str)
    def notify_plot_target_renamed(self, plot_panel_id: int, new_plot_name: str):
        if self.error_logger: self.error_logger.log_info(
            f"Plot panel {plot_panel_id} renamed to '{new_plot_name}'. Updating parse panels.")
        self.update_all_parse_panels_plot_targets()

    @Slot(int)
    def notify_plot_target_removed(self, plot_panel_id: int):
        if self.error_logger: self.error_logger.log_info(f"Plot panel {plot_panel_id} removed. Updating parse panels.")
        self.update_all_parse_panels_plot_targets()

    def clear_plot_curves_for_container(self, receive_container_id: int):
        if not PYQTGRAPH_AVAILABLE: return
        for plot_panel in self.dynamic_panel_instances.values():
            if isinstance(plot_panel, AdaptedPlotWidgetPanel): plot_panel.remove_curve_for_container(
                receive_container_id)

    @Slot(int, int)
    def handle_recv_container_plot_target_change(self, container_id: int, target_plot_id: int) -> None:
        if self.error_logger: self.error_logger.log_info(
            f"接收容器 {container_id} 的绘图目标已更改为 Plot Panel ID: {target_plot_id}")

    @Slot()
    def clear_all_plot_panels_action(self):
        if not PYQTGRAPH_AVAILABLE: return
        for panel_instance in self.dynamic_panel_instances.values():
            if isinstance(panel_instance, AdaptedPlotWidgetPanel): panel_instance.clear_plot()
        if self.error_logger: self.error_logger.log_info("所有波形图面板已清空。")

    @Slot(str)
    def apply_theme_action(self, theme_name: str):
        self.theme_manager.apply_theme(theme_name)
        for panel in self.dynamic_panel_instances.values(): panel.update_theme()

    @Slot()
    def load_external_qss_file_action(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择QSS样式文件", "", "QSS 文件 (*.qss);;所有文件 (*)")
        if file_path: self.theme_manager.apply_external_qss(file_path);
        for panel in self.dynamic_panel_instances.values(): panel.update_theme()

    @Slot()
    def export_parsed_data_action(self):
        if not self.data_recorder.historical_data: QMessageBox.information(self, "导出数据",
                                                                           "没有可导出的已解析数据。"); return
        path, _ = QFileDialog.getSaveFileName(self, "保存已解析数据", "", "CSV 文件 (*.csv)")
        if path:
            if self.data_recorder.export_parsed_data_to_csv(path):
                QMessageBox.information(self, "导出成功", f"数据已成功导出到:\n{path}")
            else:
                QMessageBox.warning(self, "导出失败", "导出已解析数据失败，请查看日志。")

    @Slot()
    def save_raw_recorded_data_action(self):
        if not self.data_recorder.recorded_raw_data: QMessageBox.information(self, "保存原始数据",
                                                                             "没有已录制的原始数据。"); return
        path, _ = QFileDialog.getSaveFileName(self, "保存原始录制数据", "",
                                              "JSON Log 文件 (*.jsonl *.json);;所有文件 (*)")
        if path: self.data_recorder.save_raw_to_file(path); QMessageBox.information(self, "保存成功",
                                                                                    f"原始录制数据已保存到:\n{path}")

    @Slot(bool)
    def toggle_raw_data_recording_action(self, checked: bool):
        if checked:
            self.data_recorder.start_raw_recording()
            self.start_raw_record_action.setText("停止录制")
            self.status_bar_label.setText("录制中...")
        else:
            self.data_recorder.stop_raw_recording()
            self.start_raw_record_action.setText("开始录制")
            self.status_bar_label.setText("录制停止。")
            if self.data_recorder.recorded_raw_data:
                if QMessageBox.question(self, "保存数据", "保存已录制的原始数据?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes:
                    self.save_raw_recorded_data_action()

    @Slot()
    def show_statistics_action(self):
        stats = self.protocol_analyzer.get_statistics()
        stats_str_parts = [f"接收总帧数: {stats['total_frames_rx']}", f"发送总帧数: {stats['total_frames_tx']}",
                           f"错误帧数: {stats['error_frames_rx']}", f"接收速率: {stats['data_rate_rx_bps']:.2f} bps",
                           f"总接收字节: {stats['rx_byte_count']} B"]
        QMessageBox.information(self, "协议统计信息", "\n".join(stats_str_parts))

    @Slot(str)
    def _handle_script_execution_request(self, script_text: str):
        if not self.scripting_panel_widget: return
        if not self.script_engine:
            if self.error_logger: self.error_logger.log_error("Script engine not initialized!", "SCRIPTING")
            self.scripting_panel_widget.display_script_result("错误: 脚本引擎未初始化。")
            return
        result = self.script_engine.execute(script_text, mode='exec')
        output_display = []
        if result.get("output"): output_display.append("脚本输出:\n" + result["output"])
        if result.get("error_message"):
            output_display.append("错误:\n" + result["error_message"])
        elif not result.get("success"):
            output_display.append("脚本执行失败，未返回特定错误。")
        if not output_display: output_display.append("脚本执行完毕，无明确输出。")
        self.scripting_panel_widget.display_script_result("\n\n".join(output_display).strip())
        if self.error_logger: self.error_logger.log_info(
            f"脚本执行完毕. 成功: {result['success']}. 时间: {result.get('execution_time_seconds', 0):.4f}s")

    def send_serial_data_from_script_hex(self, hex_string: str) -> bool:
        if not self.serial_manager.is_connected: self.error_logger.log_warning(
            "[SCRIPT_SEND] Serial port not connected. Cannot send hex data.", "SCRIPTING"); return False
        try:
            data_to_write = QByteArray.fromHex(hex_string.encode('ascii'))
            bytes_written = self.serial_manager.write_data(data_to_write)
            success = bytes_written == data_to_write.size()
            if success:
                self.error_logger.log_info(f"[SCRIPT_SEND_HEX] Sent {bytes_written} bytes: {hex_string}",
                                           "SCRIPTING")
                self._append_to_basic_receive_text_edit(data_to_write,source="TX (ScriptHex)")
                self.data_recorder.record_raw_frame(
                    datetime.now(), data_to_write.data(), "TX (ScriptHex)")
            else:
                self.error_logger.log_warning(
                    f"[SCRIPT_SEND_HEX] Partial write. Expected {data_to_write.size()}, wrote {bytes_written}",
                    "SCRIPTING")
            return success
        except Exception as e:
            self.error_logger.log_error(f"[SCRIPT_SEND_HEX] Error sending hex data '{hex_string}': {e}",
                                        "SCRIPTING"); return False

    def send_serial_data_from_script_text(self, text_string: str, encoding: str = 'utf-8') -> bool:
        if not self.serial_manager.is_connected: self.error_logger.log_warning(
            "[SCRIPT_SEND] Serial port not connected. Cannot send text data.", "SCRIPTING"); return False
        try:
            data_to_write = QByteArray(text_string.encode(encoding, errors='replace'))
            bytes_written = self.serial_manager.write_data(data_to_write)
            success = bytes_written == data_to_write.size()
            if success:
                self.error_logger.log_info(
                    f"[SCRIPT_SEND_TEXT] Sent {bytes_written} bytes (encoding: {encoding}): {text_string[:50]}...",
                    "SCRIPTING")
                self._append_to_basic_receive_text_edit(data_to_write,source="TX (ScriptTxt)")

                self.data_recorder.record_raw_frame(
                    datetime.now(), data_to_write.data(), f"TX (ScriptTxt {encoding})")
            else:
                self.error_logger.log_warning(
                    f"[SCRIPT_SEND_TEXT] Partial write. Expected {data_to_write.size()}, wrote {bytes_written}",
                    "SCRIPTING")
            return success
        except Exception as e:
            self.error_logger.log_error(f"[SCRIPT_SEND_TEXT] Error sending text data '{text_string[:50]}...': {e}",
                                        "SCRIPTING"); return False

    def get_dynamic_panel_instance_by_id(self, panel_id: int) -> Optional[PanelInterface]:
        return self.dynamic_panel_instances.get(panel_id)

    @Slot(str, QByteArray)
    def on_data_processor_processed_data(self, original_func_id: str, processed_payload: QByteArray):
        if self.error_logger: self.error_logger.log_info(
            f"DataProcessor result for FID {original_func_id}: Processed payload size {processed_payload.size()}")

    @Slot(str)
    def on_data_processor_error(self, error_message: str):
        if self.error_logger:
            self.error_logger.log_error(f"DataProcessor Error: {error_message}", "DATA_PROCESSOR")

    @Slot(dict)
    def on_data_processor_stats(self, stats: dict):
        if self.error_logger:
            self.error_logger.log_debug(f"[DATA_PROCESSOR] Stats: {stats}")

    @Slot(str, bool)
    def send_basic_serial_data_action(self, text_to_send: str, is_hex: bool) -> None:
        if not self.serial_manager.is_connected: QMessageBox.warning(self, "警告", "串口未打开。");
        if self.basic_comm_panel_widget: self.basic_comm_panel_widget.append_receive_text("错误: 串口未打开。\n"); return
        if not text_to_send:
            return; data_to_write = QByteArray()
        if is_hex:
            hex_clean = "".join(text_to_send.replace("0x", "").replace("0X", "").split());
            hex_clean = re.sub(r'[\s\-:,]', '', hex_clean.upper())
            if len(hex_clean) % 2 != 0: hex_clean = "0" + hex_clean
            try:
                data_to_write = QByteArray.fromHex(hex_clean.encode('ascii'))
            except ValueError:
                msg = f"Hex发送错误: '{text_to_send}' 包含无效Hex字符."
                QMessageBox.warning(self, "Hex格式错误", msg)
            if self.basic_comm_panel_widget:
                self.basic_comm_panel_widget.append_receive_text(f"错误: {msg}\n")
                return
        else:
            data_to_write.append(text_to_send.encode('utf-8', errors='replace'))
        if data_to_write:
            bytes_written = self.serial_manager.write_data(data_to_write)
            if bytes_written == data_to_write.size():
                display_sent_data = data_to_write.toHex(' ').data().decode('ascii').upper() if is_hex else text_to_send
                if len(display_sent_data) > 60: display_sent_data = display_sent_data[:60] + "..."
                self.status_bar_label.setText(f"基本发送 {bytes_written} 字节: {display_sent_data}")
                if self.error_logger: self.error_logger.log_info(f"基本发送 {bytes_written} 字节")
                self._append_to_basic_receive_text_edit(data_to_write, source="TX (Basic)")
                self.data_recorder.record_raw_frame(datetime.now(), data_to_write.data(), "TX (Basic)")
            else:
                self.status_bar_label.setText(f"基本发送错误: 写入{bytes_written}/{data_to_write.size()}字节")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.error_logger.log_info("关闭应用程序，正在停止后台线程...")
        if hasattr(self, 'data_processor') and self.data_processor.isRunning(): self.data_processor.stop();
        if not self.data_processor.wait(2000): self.error_logger.log_warning(
            "DataProcessor 线程未优雅停止，正在终止。"); self.data_processor.terminate(); self.data_processor.wait()
        if self.serial_manager.is_connected: self.serial_manager.disconnect_port()
        if hasattr(self, 'data_recorder') and self.data_recorder.recording_raw: self.data_recorder.stop_raw_recording()
        config_to_save = self._gather_current_configuration()
        self.config_manager.save_config(config_to_save)
        settings = QSettings("MyCompany", "SerialDebuggerProV2")
        settings.setValue("window_geometry", self.saveGeometry().toBase64().data().decode())
        settings.setValue("window_state", self.saveState().toBase64().data().decode())
        self.error_logger.log_info("配置已自动保存。应用程序退出。")
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = SerialDebugger()
    main_win.show()
    sys.exit(app.exec())
