# main.py
import re
import struct
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Set  # Added Set
from PySide6.QtCore import Slot, QByteArray, Qt, QEvent, QObject, Signal, QSettings
from PySide6.QtGui import QAction, QIcon, QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QMessageBox, QFileDialog,
    QInputDialog, QDockWidget, QDialog,  # For Plugin Management Dialog
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
from ui.widgets import SendDataContainerWidget
from ui.fixed_panels import (
    SerialConfigDefinitionPanelWidget,
    CustomLogPanelWidget,
    BasicCommPanelWidget,
    ScriptingPanelWidget
)
from ui.adaptable_panels import (
    AdaptedParsePanelWidget,
    AdaptedSendPanelWidget,
    AdaptedPlotWidgetPanel
)
from ui.dialogs import PluginManagementDialog
from core.serial_manager import SerialManager
from core.protocol_handler import ProtocolAnalyzer, FrameParser, calculate_frame_crc16, \
    calculate_original_checksums_python
from core.data_recorder import DataRecorder
# Updated Plugin Architecture Imports
from core.panel_interface import PanelInterface
from core.plugin_manager import PluginManager  # Assumes plugin_manager_hot_reload_v2 is used



class SerialDebugger(QMainWindow):
    plot_target_renamed_signal = Signal(int, str)
    plot_target_removed_signal = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.app_instance = QApplication.instance()
        if self.app_instance is None: self.app_instance = QApplication(sys.argv)

        self.error_logger = ErrorLogger()
        self._setup_application_icon("resources/image.png")
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
        self.frame_parser.try_parse_frames( current_frame_config=self.current_frame_config, 
                                            parse_target_func_id_hex= self.current_frame_config.func_id,  # 添加缺失的参数
                                            active_checksum_mode=self.active_checksum_mode
                                            )

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
        data_to_write = QByteArray()
        if not self.serial_manager.is_connected: 
            QMessageBox.warning(self, "警告", "串口未打开。");
            if self.basic_comm_panel_widget: 
                self.basic_comm_panel_widget.append_receive_text("错误: 串口未打开。\n")
            return
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
