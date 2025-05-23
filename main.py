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
from PySide6.QtCore import Slot, QByteArray, Qt
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
from core.protocol_handler import ProtocolAnalyzer, FrameParser, get_data_type_byte_length, calculate_checksums
from core.data_recorder import DataRecorder


# from core.placeholders import ... # If you use them

class SerialDebugger(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.active_checksum_mode = None
        self.app_instance = QApplication.instance()

        # Initialize core components
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

        self.setWindowTitle("YJ_tool (Refactored)")
        self.setDockNestingEnabled(True)

        self._parsed_frame_count: int = 0  # Frames successfully parsed by custom protocol

        self.receive_data_containers: List[ReceiveDataContainerWidget] = []
        self._next_receive_container_id: int = 1

        self.send_data_containers: List[SendDataContainerWidget] = []
        self._next_send_container_id: int = 1

        self.plot_widgets_map: Dict[int, PlotWidgetContainer] = {}
        self.plot_docks_map: Dict[int, QDockWidget] = {}
        self._next_plot_id: int = 1

        # For basic serial panel (raw text)
        self.basic_receive_text_edit: Optional[QTextEdit] = None
        self.basic_recv_hex_checkbox: Optional[QCheckBox] = None
        self.basic_recv_timestamp_checkbox: Optional[QCheckBox] = None
        self.basic_send_text_edit: Optional[QLineEdit] = None
        self.basic_send_hex_checkbox: Optional[QCheckBox] = None

        # UI Initialization
        self._init_ui_dockable_layout()
        self.create_menus()
        self.apply_loaded_config_to_ui()  # Changed name for clarity

        self.populate_serial_ports_ui()
        self.update_port_status_ui(False)  # Initial state is disconnected
        self.update_all_recv_containers_plot_targets()

        # Connect signals from core components
        self.serial_manager.connection_status_changed.connect(self.on_serial_connection_status_changed)
        self.serial_manager.data_received.connect(self.on_serial_data_received)
        self.serial_manager.error_occurred_signal.connect(self.on_serial_manager_error)

        self.frame_parser.frame_successfully_parsed.connect(self.on_frame_successfully_parsed)
        self.frame_parser.checksum_error.connect(self.on_frame_checksum_error)
        self.frame_parser.frame_parse_error.connect(self.on_frame_general_parse_error)

        self.error_logger.log_info("应用程序启动。")
        self.restore_geometry_and_state()

    def _init_ui_dockable_layout(self) -> None:
        serial_config_widget = self._create_serial_config_panel()
        self.dw_serial_config = QDockWidget("串口与帧定义", self)
        self.dw_serial_config.setObjectName("SerialConfigDock")
        self.dw_serial_config.setWidget(serial_config_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dw_serial_config)

        send_data_widget = self._create_send_data_panel()
        self.dw_send_data = QDockWidget("自定义发送", self)
        self.dw_send_data.setObjectName("SendDataDock")
        self.dw_send_data.setWidget(send_data_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dw_send_data)

        recv_data_widget = self._create_receive_data_panel()
        self.dw_recv_data = QDockWidget("自定义接收与解析", self)
        self.dw_recv_data.setObjectName("ReceiveDataDock")
        self.dw_recv_data.setWidget(recv_data_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dw_recv_data)

        # Original "Raw Received Data" is now part of Basic Serial Panel or could be a log
        # self.receive_text_edit for custom protocol raw data (before parsing or raw log of it)
        # is different from basic_receive_text_edit
        # For this refactor, let's assume the original receive_text_edit was for raw custom protocol data.
        # It's currently not explicitly created in the new structure, basic_receive_text_edit serves general raw.
        # Let's keep one for custom protocol frame log.
        custom_protocol_log_widget = self._create_custom_protocol_log_panel()
        self.dw_custom_log = QDockWidget("协议帧原始数据", self)  # Renamed
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

        self.tabifyDockWidget(self.dw_serial_config, self.dw_send_data)

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
        self.connect_button.clicked.connect(self.toggle_connection_action)  # Changed
        config_layout.addWidget(self.connect_button, 5, 1)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        frame_def_group = QGroupBox("帧结构定义 (自定义协议)")
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
        frame_def_layout.addWidget(QLabel("功能码(ID)[Hex,1B]:"), 3, 0)  # This is for SENDING
        self.id_edit = QLineEdit()  # FuncID for sending
        self.id_edit.editingFinished.connect(self.update_current_frame_config_from_ui)
        frame_def_layout.addWidget(self.id_edit, 3, 1)

        # Add Checksum Mode ComboBox
        frame_def_layout.addWidget(QLabel("校验模式:"), 6, 0)  # Adjust row index as needed
        self.checksum_mode_combo = QComboBox()
        self.checksum_mode_combo.addItem("原始校验 (Sum/Add)", ChecksumMode.ORIGINAL_SUM_ADD)
        self.checksum_mode_combo.addItem("CRC-16/CCITT-FALSE", ChecksumMode.CRC16_CCITT_FALSE)
        self.checksum_mode_combo.currentIndexChanged.connect(
            self.update_current_frame_config_from_ui)  # Or a dedicated handler
        frame_def_layout.addWidget(self.checksum_mode_combo, 6, 1)

        frame_def_layout.addWidget(QLabel("校验和1/CRC高位:"), 4, 0)  # Relabel for clarity
        self.sum_check_display = QLineEdit()  # Will show SC or CRC MSB or full CRC
        self.sum_check_display.setPlaceholderText("自动")
        self.sum_check_display.setReadOnly(True)
        frame_def_layout.addWidget(self.sum_check_display, 4, 1)

        frame_def_layout.addWidget(QLabel("校验和2/CRC低位:"), 5, 0)  # Relabel for clarity
        self.add_check_display = QLineEdit()  # Will show AC or CRC LSB or be empty
        self.add_check_display.setPlaceholderText("自动")
        self.add_check_display.setReadOnly(True)
        frame_def_layout.addWidget(self.add_check_display, 5, 1)

        frame_def_group.setLayout(frame_def_layout)
        layout.addWidget(frame_def_group)
        layout.addStretch()
        return panel

    def _create_send_data_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        send_data_group = QGroupBox("自定义协议发送数据 (DATA部分)")
        send_data_main_layout = QVBoxLayout()
        send_container_controls_layout = QHBoxLayout()
        self.add_send_container_button = QPushButton("添加发送项 (+)")
        self.add_send_container_button.clicked.connect(self.add_send_data_container)
        send_container_controls_layout.addWidget(self.add_send_container_button)
        self.remove_send_container_button = QPushButton("删除发送项 (-)")
        self.remove_send_container_button.clicked.connect(self.remove_send_data_container)
        self.remove_send_container_button.setEnabled(False)
        send_container_controls_layout.addWidget(self.remove_send_container_button)
        send_container_controls_layout.addStretch()
        send_data_main_layout.addLayout(send_container_controls_layout)

        self.scroll_area_send_containers = QScrollArea()
        self.scroll_area_send_containers.setWidgetResizable(True)
        self.send_containers_widget = QWidget()
        self.send_containers_layout = QVBoxLayout(self.send_containers_widget)
        self.send_containers_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area_send_containers.setWidget(self.send_containers_widget)
        send_data_main_layout.addWidget(self.scroll_area_send_containers)

        self.send_frame_button = QPushButton("发送组装帧 (自定义协议)")
        self.send_frame_button.clicked.connect(self.send_custom_protocol_data_action)
        send_data_main_layout.addWidget(self.send_frame_button)
        send_data_group.setLayout(send_data_main_layout)
        layout.addWidget(send_data_group)
        return panel

    def _create_receive_data_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        recv_display_group = QGroupBox("自定义协议数据显示与解析")
        recv_display_main_layout = QVBoxLayout()
        recv_container_controls_layout = QHBoxLayout()
        self.add_recv_container_button = QPushButton("添加显示项 (+)")
        self.add_recv_container_button.clicked.connect(self.add_receive_data_container)
        recv_container_controls_layout.addWidget(self.add_recv_container_button)
        self.remove_recv_container_button = QPushButton("删除显示项 (-)")
        self.remove_recv_container_button.clicked.connect(self.remove_receive_data_container)
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
        parse_config_layout.addWidget(QLabel("解析功能码(ID)[Hex]:"), 0, 0)  # FuncID to look for in received frames
        self.parse_id_edit = QLineEdit()  # Target FuncID for parsing into containers
        parse_config_layout.addWidget(self.parse_id_edit, 0, 1)
        parse_config_layout.addWidget(QLabel("数据分配模式:"), 1, 0)
        self.data_mapping_combo = QComboBox()
        self.data_mapping_combo.addItems(["顺序填充 (Sequential)"])  # Add more if implemented
        parse_config_layout.addWidget(self.data_mapping_combo, 1, 1)
        recv_display_main_layout.addLayout(parse_config_layout)
        recv_display_group.setLayout(recv_display_main_layout)
        layout.addWidget(recv_display_group)
        return panel

    def _create_custom_protocol_log_panel(self) -> QWidget:  # Formerly _create_raw_receive_panel
        panel = QWidget()
        layout = QVBoxLayout(panel)
        log_group = QGroupBox("自定义协议原始帧记录")
        log_layout = QVBoxLayout()
        self.custom_protocol_raw_log_text_edit = QTextEdit()  # Renamed from receive_text_edit
        self.custom_protocol_raw_log_text_edit.setReadOnly(True)
        self.custom_protocol_raw_log_text_edit.setFontFamily("Courier New")
        # self.custom_protocol_raw_log_text_edit.setFixedHeight(150) # Let dock manage height

        log_layout.addWidget(self.custom_protocol_raw_log_text_edit)

        options_layout = QHBoxLayout()
        self.custom_log_hex_checkbox = QCheckBox("Hex显示")  # Renamed from receive_hex_checkbox
        # self.custom_log_hex_checkbox.toggled.connect(self.update_custom_log_display_format) # TODO: implement this
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

    def _append_to_custom_protocol_log(self, text: str, is_hex: bool, source: str = "RX"):
        if not hasattr(self, 'custom_protocol_raw_log_text_edit') or self.custom_protocol_raw_log_text_edit is None:
            return

        display_text = ""
        if self.custom_log_timestamp_checkbox and self.custom_log_timestamp_checkbox.isChecked():
            display_text += datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] "

        display_text += f"{source}: "
        display_text += text

        if not text.endswith('\n'):
            display_text += '\n'

        self.custom_protocol_raw_log_text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.custom_protocol_raw_log_text_edit.insertPlainText(display_text)
        self.custom_protocol_raw_log_text_edit.moveCursor(QTextCursor.MoveOperation.End)

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
        basic_send_button = QPushButton("发送")
        basic_send_button.clicked.connect(self.send_basic_serial_data_action)
        send_options_layout.addWidget(basic_send_button)
        send_layout.addLayout(send_options_layout)
        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)
        return panel

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
        # Add action for saving raw recorded data
        save_raw_data_action = QAction("保存原始录制数据 (JSON)...", self)
        save_raw_data_action.triggered.connect(self.save_raw_recorded_data_action)
        file_menu.addAction(save_raw_data_action)

        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        self.view_menu = self.menuBar().addMenu("视图(&V)")
        self.view_menu.addAction(self.dw_serial_config.toggleViewAction())
        self.view_menu.addAction(self.dw_send_data.toggleViewAction())
        self.view_menu.addAction(self.dw_recv_data.toggleViewAction())
        if hasattr(self, 'dw_custom_log') and self.dw_custom_log:
            self.view_menu.addAction(self.dw_custom_log.toggleViewAction())
        if hasattr(self, 'dw_basic_serial') and self.dw_basic_serial:
            self.view_menu.addAction(self.dw_basic_serial.toggleViewAction())
        self.view_menu.addSeparator()  # For plot docks

        theme_menu = self.view_menu.addMenu("背景样式")
        # ... (theme actions - same as original, ensure apply_theme_action is connected)
        basic_themes_menu = theme_menu.addMenu("基础主题")
        for theme_name in ["light", "dark"]:  # Example
            action = QAction(f"{theme_name.capitalize()} 主题", self)
            action.triggered.connect(lambda checked=False, tn=theme_name: self.apply_theme_action(tn))
            basic_themes_menu.addAction(action)
        # Add other theme menus and actions similarly...
        custom_theme_menu = theme_menu.addMenu("自定义背景")
        image_theme_action = QAction("图片背景主题", self)
        image_theme_action.triggered.connect(lambda: self.apply_theme_action("custom_image_theme"))
        custom_theme_menu.addAction(image_theme_action)
        load_external_qss_action = QAction("加载外部QSS文件...", self)
        load_external_qss_action.triggered.connect(self.load_external_qss_file_action)
        custom_theme_menu.addAction(load_external_qss_action)

        tools_menu = self.menuBar().addMenu("工具(&T)")
        add_plot_action = QAction("添加波形图窗口(&P)", self)
        add_plot_action.setEnabled(PYQTGRAPH_AVAILABLE)
        add_plot_action.triggered.connect(lambda: self.add_new_plot_widget_action(from_config=False))
        tools_menu.addAction(add_plot_action)

        clear_all_plots_action = QAction("清空所有波形图", self)
        clear_all_plots_action.setEnabled(PYQTGRAPH_AVAILABLE)
        clear_all_plots_action.triggered.connect(self.clear_all_plots_action)
        tools_menu.addAction(clear_all_plots_action)
        tools_menu.addSeparator()

        # Raw data recording controls
        self.start_raw_record_action = QAction("开始原始数据录制", self)
        self.start_raw_record_action.setCheckable(True)
        self.start_raw_record_action.triggered.connect(self.toggle_raw_data_recording_action)
        tools_menu.addAction(self.start_raw_record_action)
        # (stop action is implicit in the checkable action)

        tools_menu.addSeparator()
        show_stats_action = QAction("显示统计信息...", self)
        show_stats_action.triggered.connect(self.show_statistics_action)
        tools_menu.addAction(show_stats_action)
        reset_stats_action = QAction("重置统计信息", self)
        reset_stats_action.triggered.connect(self.protocol_analyzer.reset_statistics)  # Direct call ok
        tools_menu.addAction(reset_stats_action)

    # --- Configuration Persistence ---
    def update_current_frame_config_from_ui(self):
        self.current_frame_config.head = self.head_edit.text()
        self.current_frame_config.s_addr = self.saddr_edit.text()
        self.current_frame_config.d_addr = self.daddr_edit.text()
        self.current_frame_config.func_id = self.id_edit.text()
        selected_mode_data = self.checksum_mode_combo.currentData()
        if isinstance(selected_mode_data, ChecksumMode):
            self.active_checksum_mode = selected_mode_data
        else:
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
        # print(f"Active checksum mode set to: {self.active_checksum_mode}")

    def update_current_serial_config_from_ui(self):
        self.current_serial_config.port_name = self.port_combo.currentData()
        self.current_serial_config.baud_rate = int(self.baud_combo.currentText())
        self.current_serial_config.data_bits = int(self.data_bits_combo.currentText())
        self.current_serial_config.parity = self.parity_combo.currentText()
        s_bits = self.stop_bits_combo.currentText()
        self.current_serial_config.stop_bits = float(s_bits) if s_bits == "1.5" else int(s_bits)

    def apply_loaded_config_to_ui(self) -> None:
        # Serial Port Config
        sp_conf_dict = self.current_config.get("serial_port", {})
        self.current_serial_config = SerialPortConfig(**sp_conf_dict)  # Update current_serial_config object
        self.baud_combo.setCurrentText(str(self.current_serial_config.baud_rate))
        self.data_bits_combo.setCurrentText(str(self.current_serial_config.data_bits))
        self.parity_combo.setCurrentText(self.current_serial_config.parity)
        self.stop_bits_combo.setCurrentText(str(self.current_serial_config.stop_bits))
        # Port name will be selected if available during populate_serial_ports_ui

        # Frame Definition Config
        fd_conf_dict = self.current_config.get("frame_definition", {})
        self.current_frame_config = FrameConfig(**fd_conf_dict)  # Update current_frame_config object
        self.head_edit.setText(self.current_frame_config.head)
        self.saddr_edit.setText(self.current_frame_config.s_addr)
        self.daddr_edit.setText(self.current_frame_config.d_addr)
        self.id_edit.setText(self.current_frame_config.func_id)  # FuncID for sending

        # Theme
        loaded_theme_info = self.current_config.get("ui_theme_info",
                                                    {"type": "internal", "name": "light", "path": None})
        if loaded_theme_info["type"] == "internal" and loaded_theme_info.get("name"):
            self.theme_manager.apply_theme(loaded_theme_info["name"])
        elif loaded_theme_info["type"] == "external" and loaded_theme_info.get("path"):
            self.theme_manager.apply_external_qss(loaded_theme_info["path"])
        else:
            self.theme_manager.apply_theme("light")  # Fallback

        # Clear existing dynamic UI elements before loading from config
        # Plots are handled by _init_ui_dockable_layout based on plot_configs
        # Receive Containers
        for _ in range(len(self.receive_data_containers)): self.remove_receive_data_container(silent=True)
        recv_containers_cfg = self.current_config.get("receive_containers", [])
        for cfg in recv_containers_cfg: self.add_receive_data_container(config=cfg, silent=True)

        # Send Containers
        for _ in range(len(self.send_data_containers)): self.remove_send_data_container(silent=True)
        send_containers_cfg = self.current_config.get("send_containers", [])
        for cfg in send_containers_cfg: self.add_send_data_container(config=cfg, silent=True)

        # Parsing Config
        self.parse_id_edit.setText(self.current_config.get("parse_func_id", "C1"))
        self.data_mapping_combo.setCurrentText(self.current_config.get("data_mapping_mode", "顺序填充 (Sequential)"))

        # Checksum Mode
        checksum_mode_name = self.current_config.get("checksum_mode", Constants.DEFAULT_CHECKSUM_MODE.name)
        try:
            self.active_checksum_mode = ChecksumMode[checksum_mode_name]
        except KeyError:
            self.active_checksum_mode = Constants.DEFAULT_CHECKSUM_MODE
            if self.error_logger:
                self.error_logger.log_warning(f"Invalid checksum_mode '{checksum_mode_name}' in config, using default.")

        idx = self.checksum_mode_combo.findData(self.active_checksum_mode)
        if idx != -1:
            self.checksum_mode_combo.setCurrentIndex(idx)
        else:
            idx = self.checksum_mode_combo.findData(Constants.DEFAULT_CHECKSUM_MODE)
            if idx != -1:
                self.checksum_mode_combo.setCurrentIndex(idx)

        self.update_all_recv_containers_plot_targets()
        if self.error_logger:
            self.error_logger.log_info("配置已加载并应用到UI。")

    def gather_current_ui_config(self) -> Dict[str, Any]:
        # Ensure serial_config and frame_config objects are up-to-date
        self.update_current_serial_config_from_ui()
        self.update_current_frame_config_from_ui()

        # Gather other configurations
        recv_containers_cfg = [c.get_config() for c in self.receive_data_containers]
        send_containers_cfg = [
            {
                "name": c.name_edit.text(),
                "type": c.type_combo.currentText(),
                "value": c.value_edit.text()  # Save current value from send container
            } for c in self.send_data_containers
        ]
        plot_configs = [{"id": pid, "name": pcontainer.plot_name} for pid, pcontainer in self.plot_widgets_map.items()]

        # Base configuration gathering (if using inheritance)
        config_data = super().gather_current_ui_config() if hasattr(super(), 'gather_current_ui_config') else {}

        # Update the base configuration with current UI settings
        config_data.update({
            "serial_port": vars(self.current_serial_config),
            "frame_definition": vars(self.current_frame_config),
            "ui_theme_info": self.theme_manager.current_theme_info,
            "receive_containers": recv_containers_cfg,
            "send_containers": send_containers_cfg,
            "parse_func_id": self.parse_id_edit.text(),
            "data_mapping_mode": self.data_mapping_combo.currentText(),
            "window_geometry": self.saveGeometry().toBase64().data().decode(),
            "window_state": self.saveState().toBase64().data().decode(),
            "plot_configs": plot_configs
        })

        # Gather checksum mode configuration
        selected_mode_data = self.checksum_mode_combo.currentData()
        if isinstance(selected_mode_data, ChecksumMode):
            config_data["checksum_mode"] = selected_mode_data.name
        else:  # Fallback, though UI should provide ChecksumMode enum value
            config_data["checksum_mode"] = Constants.DEFAULT_CHECKSUM_MODE.name

        return config_data  # Return the modified dictionary

    def restore_geometry_and_state(self) -> None:
        geom_b64 = self.current_config.get("window_geometry")
        state_b64 = self.current_config.get("window_state")
        if geom_b64: self.restoreGeometry(QByteArray.fromBase64(geom_b64.encode()))
        if state_b64: self.restoreState(QByteArray.fromBase64(state_b64.encode()))
        # if self.error_logger and (geom_b64 or state_b64): self.error_logger.log_info("窗口几何/状态已恢复。")

    @Slot()
    def load_configuration_action(self) -> None:
        # Ask user to save current changes? Or load directly?
        # For now, direct load.
        file_path, _ = QFileDialog.getOpenFileName(self, "加载配置文件", "", f"JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            # Temporarily use a new config manager to load from a different file
            # Or modify current config_manager to load from a specific path
            # For simplicity, let's assume ConfigManager loads its default or we update its path
            # self.config_manager.config_file = Path(file_path) # Not ideal if it's a one-time load
            temp_loader = ConfigManager(filename=file_path, error_logger=self.error_logger)
            loaded_cfg = temp_loader.load_config()
            if loaded_cfg != temp_loader.default_config or Path(file_path).exists():  # check if load was successful
                self.current_config = loaded_cfg
                self.apply_loaded_config_to_ui()
                QMessageBox.information(self, "配置加载", f"配置已从 '{file_path}' 加载。")
            else:
                QMessageBox.warning(self, "配置加载", f"无法从 '{file_path}' 加载有效配置。")

    @Slot()
    def save_configuration_action(self) -> None:
        # Allow "Save As"
        current_config_path = self.config_manager.config_file
        file_path, _ = QFileDialog.getSaveFileName(self, "保存配置文件", str(current_config_path),
                                                   f"JSON 文件 (*.json);;所有文件 (*)")
        if file_path:
            current_ui_cfg = self.gather_current_ui_config()
            # Save to the new path using a temporary manager or update current manager's path
            # For now, save directly to chosen path.
            # If the chosen path is the same as default, it will overwrite.
            temp_saver = ConfigManager(filename=file_path, error_logger=self.error_logger)
            temp_saver.save_config(current_ui_cfg)
            # If saved to a new path, should it become the default for next auto-save?
            # self.config_manager.config_file = Path(file_path) # Update default path
            # self.current_config = current_ui_cfg # Update in-memory config
            QMessageBox.information(self, "配置保存", f"配置已保存到 {file_path}。")

    @Slot(str)
    def apply_theme_action(self, theme_name: str) -> None:
        self.theme_manager.apply_theme(theme_name)
        # Config will be updated with theme_manager.current_theme_info upon saving

    @Slot()
    def load_external_qss_file_action(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "选择QSS样式文件", "", "QSS 文件 (*.qss);;所有文件 (*)")
        if file_path:
            self.theme_manager.apply_external_qss(file_path)

    @Slot()
    def export_parsed_data_action(self) -> None:
        if not self.data_recorder.historical_data:
            QMessageBox.information(self, "导出数据", "没有可导出的已解析数据。")
            self.error_logger.log_info("尝试导出数据，但历史记录为空。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存已解析数据", "", "CSV 文件 (*.csv)")
        if path:
            if self.data_recorder.export_parsed_data_to_csv(path):
                QMessageBox.information(self, "导出成功", f"数据已成功导出到:\n{path}")
            else:
                QMessageBox.warning(self, "导出失败", "导出已解析数据失败，请查看日志。")

    @Slot()
    def save_raw_recorded_data_action(self) -> None:
        if not self.data_recorder.recorded_raw_data:
            QMessageBox.information(self, "保存原始数据", "没有已录制的原始数据。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存原始录制数据", "",
                                              "JSON Log 文件 (*.jsonl *.json);;所有文件 (*)")
        if path:
            self.data_recorder.save_raw_to_file(path)  # Error handling is inside this method
            QMessageBox.information(self, "保存成功", f"原始录制数据已保存到:\n{path}")

    @Slot()
    def show_statistics_action(self) -> None:
        stats = self.protocol_analyzer.get_statistics()
        stats_str_parts = [
            f"接收总帧数 (自定义协议): {stats['total_frames_rx']}",
            f"发送总帧数 (自定义协议): {stats['total_frames_tx']}",
            f"接收错误帧数 (自定义协议): {stats['error_frames_rx']}",
            f"当前接收速率 (自定义协议): {stats['data_rate_rx_bps']:.2f} bps",
            f"总接收字节 (自定义协议): {stats['rx_byte_count']} B"
        ]
        QMessageBox.information(self, "自定义协议统计信息", "\n".join(stats_str_parts))

    # --- Data Container Management ---
    @Slot()
    def add_receive_data_container(self, config: Optional[Dict[str, Any]] = None, silent: bool = False) -> None:
        container = ReceiveDataContainerWidget(self._next_receive_container_id, self)
        container.plot_target_changed_signal.connect(self.handle_recv_container_plot_target_change)
        if config:
            container.name_edit.setText(config.get("name", f"RecvData_{self._next_receive_container_id}"))
            container.type_combo.setCurrentText(config.get("type", "uint8_t"))
            if PYQTGRAPH_AVAILABLE and container.plot_checkbox:  # Check if plot_checkbox exists
                container.plot_checkbox.setChecked(config.get("plot_enabled", False))

        self.recv_containers_layout.addWidget(container)
        self.receive_data_containers.append(container)
        self._next_receive_container_id += 1
        self.remove_recv_container_button.setEnabled(True)

        # Update plot targets for the new container
        targets_for_dropdown = {pid: pw.plot_name for pid, pw in self.plot_widgets_map.items()}
        container.update_plot_targets(targets_for_dropdown)

        if config and PYQTGRAPH_AVAILABLE and container.plot_target_combo:
            plot_target_id = config.get("plot_target_id")
            if plot_target_id is not None:
                idx = container.plot_target_combo.findData(plot_target_id)
                if idx != -1:
                    container.plot_target_combo.setCurrentIndex(idx)
                # Ensure combo is enabled if checkbox is checked
                container.plot_target_combo.setEnabled(
                    container.plot_checkbox.isChecked() and bool(targets_for_dropdown))

        if not silent and self.error_logger: self.error_logger.log_info(f"添加接收容器 {container.container_id}")

    @Slot()
    def remove_receive_data_container(self, silent: bool = False) -> None:
        if self.receive_data_containers:
            container_to_remove = self.receive_data_containers.pop()
            container_id_removed = container_to_remove.container_id
            self.recv_containers_layout.removeWidget(container_to_remove)
            container_to_remove.deleteLater()
            # Remove from any plot it might be on
            for plot_widget_container in self.plot_widgets_map.values():
                plot_widget_container.remove_curve_for_container(container_id_removed)

            if not self.receive_data_containers:
                self.remove_recv_container_button.setEnabled(False)
            if not silent and self.error_logger: self.error_logger.log_info(f"移除接收容器 {container_id_removed}")

    @Slot(int, int)
    def handle_recv_container_plot_target_change(self, container_id: int, target_plot_id: int) -> None:
        # This signal is mostly for information or if complex logic is needed when target changes.
        # The actual plotting happens based on the container's current config when data arrives.
        # One might want to clear the curve from an *old* plot if a container is moved.
        # For now, simply log.
        if self.error_logger:
            self.error_logger.log_info(f"接收容器 {container_id} 目标波形图更改为 {target_plot_id}")

    @Slot()
    def add_send_data_container(self, config: Optional[Dict[str, Any]] = None, silent: bool = False) -> None:
        container = SendDataContainerWidget(self._next_send_container_id, self)
        if config:
            container.name_edit.setText(config.get("name", f"SendData_{self._next_send_container_id}"))
            container.type_combo.setCurrentText(config.get("type", "uint8_t"))
            container.value_edit.setText(config.get("value", ""))  # Restore value

        self.send_containers_layout.addWidget(container)
        self.send_data_containers.append(container)
        self._next_send_container_id += 1
        self.remove_send_container_button.setEnabled(True)
        if not silent and self.error_logger: self.error_logger.log_info(f"添加发送容器 {container.container_id}")

    @Slot()
    def remove_send_data_container(self, silent: bool = False) -> None:
        if self.send_data_containers:
            container_to_remove = self.send_data_containers.pop()
            self.send_containers_layout.removeWidget(container_to_remove)
            container_to_remove.deleteLater()
            if not self.send_data_containers:
                self.remove_send_container_button.setEnabled(False)
            if not silent and self.error_logger:
                self.error_logger.log_info(f"移除发送容器 {container_to_remove.container_id}")

    # --- Plot Management ---
    @Slot()
    def add_new_plot_widget_action(self, name: Optional[str] = None, plot_id_from_config: Optional[int] = None,
                                   from_config: bool = False) -> None:
        if not PYQTGRAPH_AVAILABLE:
            QMessageBox.information(self, "提示", "pyqtgraph未安装，无法添加波形图。")
            return

        plot_id_to_use = plot_id_from_config if plot_id_from_config is not None else self._next_plot_id

        # Avoid duplicate plot IDs if loading from config and then adding new
        while plot_id_to_use in self.plot_widgets_map:
            plot_id_to_use = self._next_plot_id  # Ensure _next_plot_id is always fresh
            self._next_plot_id += 1

        plot_name_input = name
        if not from_config and name is None:
            text, ok = QInputDialog.getText(self, "新波形图", "输入波形图名称:", QLineEdit.EchoMode.Normal,
                                            f"波形图 {plot_id_to_use}")
            if not ok or not text: return
            plot_name_input = text
        elif name is None:  # Default name if from_config but no name specified OR for auto-incremented new
            plot_name_input = f"波形图 {plot_id_to_use}"

        plot_container = PlotWidgetContainer(plot_id_to_use, plot_name_input, self)
        dw_plot = QDockWidget(plot_name_input, self)
        dw_plot.setObjectName(f"PlotDock_{plot_id_to_use}")
        dw_plot.setWidget(plot_container)

        existing_plot_docks = [self.plot_docks_map[pid] for pid in sorted(self.plot_docks_map.keys()) if
                               pid in self.plot_docks_map]
        if existing_plot_docks:
            self.tabifyDockWidget(existing_plot_docks[-1], dw_plot)
        else:  # First plot, try to dock right of receive data, or just RightDockWidgetArea
            # self.splitDockWidget(self.dw_recv_data, dw_plot, Qt.Orientation.Horizontal) # Example
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dw_plot)

        self.plot_widgets_map[plot_id_to_use] = plot_container
        self.plot_docks_map[plot_id_to_use] = dw_plot

        if plot_id_from_config is None or plot_id_to_use >= self._next_plot_id:
            self._next_plot_id = plot_id_to_use + 1

        if hasattr(self, 'view_menu'):
            action = dw_plot.toggleViewAction()
            self.view_menu.addAction(action)
            # TODO: Manage removal of this action if plot is removed permanently

        self.update_all_recv_containers_plot_targets()
        dw_plot.show()
        if not from_config and self.error_logger:
            self.error_logger.log_info(f"添加新波形图: ID={plot_id_to_use}, Name='{plot_name_input}'")

    def update_all_recv_containers_plot_targets(self) -> None:
        targets = {pid: pwidget_container.plot_name for pid, pwidget_container in self.plot_widgets_map.items()}
        for container in self.receive_data_containers:
            container.update_plot_targets(targets)
            # Restore selection if possible after targets update
            cfg = container.get_config()
            if cfg.get("plot_target_id") is not None and container.plot_target_combo:
                idx = container.plot_target_combo.findData(cfg["plot_target_id"])
                if idx != -1: container.plot_target_combo.setCurrentIndex(idx)

    @Slot()
    def clear_all_plots_action(self) -> None:
        if not PYQTGRAPH_AVAILABLE: return
        for plot_container in self.plot_widgets_map.values():
            plot_container.clear_plot()
        self.status_bar_label.setText("所有波形图已清空")
        if self.error_logger: self.error_logger.log_info("所有波形图已清空。")

    # --- Serial Port UI and Actions ---
    @Slot()
    def populate_serial_ports_ui(self) -> None:
        self.port_combo.clear()
        available_ports = self.serial_manager.get_available_ports()
        if not available_ports:
            self.port_combo.addItem("无可用端口")
            self.port_combo.setEnabled(False)
        else:
            for port_info in available_ports:
                self.port_combo.addItem(f"{port_info['name']} ({port_info['description']})", port_info['name'])
            self.port_combo.setEnabled(True)
            # Try to reselect configured port
            if self.current_serial_config.port_name:
                idx = self.port_combo.findData(self.current_serial_config.port_name)
                if idx != -1:
                    self.port_combo.setCurrentIndex(idx)
        self.update_port_status_ui(self.serial_manager.is_connected)

    def update_port_status_ui(self, connected: bool) -> None:
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.data_bits_combo.setEnabled(not connected)
        self.parity_combo.setEnabled(not connected)
        self.stop_bits_combo.setEnabled(not connected)
        self.refresh_ports_button.setEnabled(not connected)
        self.connect_button.setChecked(connected)
        self.connect_button.setText("关闭串口" if connected else "打开串口")
        self.send_frame_button.setEnabled(connected)  # For custom protocol send

        # Enable basic send button if connected (assuming it exists)
        if hasattr(self, 'basic_send_button') and self.basic_send_button:
            self.basic_send_button.setEnabled(connected)

        if not self.port_combo.count() or self.port_combo.currentText() == "无可用端口":
            self.connect_button.setEnabled(False)  # No ports to connect to
            if not connected: self.status_bar_label.setText("无可用串口")

    @Slot()
    def toggle_connection_action(self) -> None:
        if self.serial_manager.is_connected:
            self.serial_manager.disconnect_port()
        else:
            self.update_current_serial_config_from_ui()  # Get latest settings from UI
            self.serial_manager.connect_port(self.current_serial_config)
            if self.serial_manager.is_connected:
                self.frame_parser.clear_buffer()  # Clear parser buffer on new connection
                self._parsed_frame_count = 0
                # self.data_recorder.clear_parsed_data_history() # Optional: clear history on new connect

    # --- Data Sending Actions ---
    def _assemble_custom_frame(self) -> Optional[QByteArray]:
        self.update_current_frame_config_from_ui()  # Ensure current_frame_config is fresh for sending
        cfg = self.current_frame_config

        try:
            head_ba = QByteArray.fromHex(cfg.head.encode('ascii'))
            saddr_ba = QByteArray.fromHex(cfg.s_addr.encode('ascii'))
            daddr_ba = QByteArray.fromHex(cfg.d_addr.encode('ascii'))
            id_ba = QByteArray.fromHex(cfg.func_id.encode('ascii'))  # FuncID for sending
        except ValueError as e:
            msg = f"帧头/地址/ID Hex格式错误: {e}"
            self.status_bar_label.setText(msg)
            if self.error_logger:
                self.error_logger.log_warning(msg)
            return None

        if not (len(head_ba) == 1 and len(saddr_ba) == 1 and len(daddr_ba) == 1 and len(id_ba) == 1):
            msg = "帧头/地址/ID Hex长度必须为1字节 (2个Hex字符)"
            self.status_bar_label.setText(msg)
            if self.error_logger:
                self.error_logger.log_warning(msg)
            return None

        data_content_ba = QByteArray()
        for scw_widget in self.send_data_containers:
            item_bytes = scw_widget.get_bytes()
            if item_bytes is None:
                # Error message already shown by SendDataContainerWidget.get_bytes()
                msg = f"发送项 '{scw_widget.name_edit.text()}' 数值错误"
                self.status_bar_label.setText(msg)
                if self.error_logger:
                    self.error_logger.log_warning(msg)
                return None
            data_content_ba.append(item_bytes)

        len_val = len(data_content_ba)
        # Assuming length is 2 bytes, little-endian
        len_ba = QByteArray(struct.pack('<H', len_val))

        frame_part_for_checksum = QByteArray()
        frame_part_for_checksum.append(head_ba)
        frame_part_for_checksum.append(saddr_ba)
        frame_part_for_checksum.append(daddr_ba)
        frame_part_for_checksum.append(id_ba)
        frame_part_for_checksum.append(len_ba)
        frame_part_for_checksum.append(data_content_ba)

        checksum_bytes_to_append = QByteArray()
        active_mode = self.checksum_mode_combo.currentData()  # Get selected mode

        if active_mode == ChecksumMode.CRC16_CCITT_FALSE:
            crc_val = calculate_frame_crc16(frame_part_for_checksum)  # From protocol_handler
            checksum_bytes_to_append.append(struct.pack('>H', crc_val))  # Big-Endian
            self.sum_check_display.setText(f"0x{crc_val:04X}")
            self.add_check_display.clear()  # Clear the second checksum display
        else:  # Default to ORIGINAL_SUM_ADD
            # Assuming calculate_original_checksums_python is available in protocol_handler.py
            sc_val, ac_val = calculate_original_checksums_python(frame_part_for_checksum)
            checksum_bytes_to_append.append(bytes([sc_val]))
            checksum_bytes_to_append.append(bytes([ac_val]))
            self.sum_check_display.setText(f"0x{sc_val:02X}")
            self.add_check_display.setText(f"0x{ac_val:02X}")

        final_frame = QByteArray(frame_part_for_checksum)
        final_frame.append(checksum_bytes_to_append)
        return final_frame
    @Slot()
    def send_custom_protocol_data_action(self) -> None:
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "串口未打开。")
            return

        final_frame = self._assemble_custom_frame()
        if final_frame:
            bytes_written = self.serial_manager.write_data(final_frame)
            if bytes_written == len(final_frame):
                hex_frame_str = final_frame.toHex(' ').data().decode('ascii').upper()
                msg = f"自定义协议发送 {bytes_written} 字节: {hex_frame_str}"
                self.status_bar_label.setText(msg)
                if self.error_logger: self.error_logger.log_info(msg)
                self.protocol_analyzer.analyze_frame(final_frame, 'tx')
                self.data_recorder.record_raw_frame(datetime.now(), final_frame.data(), "TX (Custom)")
                self._append_to_custom_protocol_log(hex_frame_str, is_hex=True, source="TX")

    @Slot()
    def send_basic_serial_data_action(self) -> None:
        if not self.serial_manager.is_connected:
            QMessageBox.warning(self, "警告", "串口未打开。")
            self._append_to_basic_receive(QByteArray("错误: 串口未打开。\n".encode('utf-8')), source="INFO")
            return

        text_to_send = self.basic_send_text_edit.text()
        if not text_to_send: return

        data_to_write = QByteArray()
        is_hex_send = self.basic_send_hex_checkbox.isChecked()

        if is_hex_send:
            hex_clean = "".join(text_to_send.replace("0x", "").replace("0X", "").split())
            if len(hex_clean) % 2 != 0: hex_clean = "0" + hex_clean  # Pad
            try:
                data_to_write = QByteArray.fromHex(hex_clean.encode('ascii'))
            except ValueError:
                msg = f"Hex发送错误: '{text_to_send}' 包含无效Hex字符。"
                QMessageBox.warning(self, "Hex格式错误", msg)
                self._append_to_basic_receive(QByteArray(f"错误: {msg}\n".encode('utf-8')), source="INFO")
                return
        else:
            # Consider allowing user to choose encoding for basic send (UTF-8, GBK, ASCII etc.)
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

                self._append_to_basic_receive(data_to_write, source="TX")  # Show in basic display
                # self.protocol_analyzer.analyze_frame(data_to_write, 'tx_basic') # Separate category?
                self.data_recorder.record_raw_frame(datetime.now(), data_to_write.data(), "TX (Basic)")

    # --- Data Receiving and Parsing Callbacks ---
    @Slot(QByteArray)
    def on_serial_data_received(self, data: QByteArray):
        # Append to basic view (raw data from port)
        self._append_to_basic_receive(data, source="RX")
        # Record raw RX data if enabled
        self.data_recorder.record_raw_frame(datetime.now(), data.data(), "RX")

        # Append to custom frame parser's buffer
        self.frame_parser.append_data(data)
        # Try to parse frames using current frame config and target parse ID
        self.update_current_frame_config_from_ui()  # Ensure latest config is used by parser
        target_parse_fid = self.parse_id_edit.text()
        # Ensure self.active_checksum_mode is correctly set from the UI selection
        current_ui_checksum_mode = self.checksum_mode_combo.currentData()
        if not isinstance(current_ui_checksum_mode, ChecksumMode):  # Fallback if UI not ready
            current_ui_checksum_mode = self.active_checksum_mode  # Use the last known good mode

        self.frame_parser.try_parse_frames(self.current_frame_config, target_parse_fid, current_ui_checksum_mode)

    @Slot(str, QByteArray)  # func_id_hex, data_payload
    def on_frame_successfully_parsed(self, func_id_hex: str, data_payload_ba: QByteArray):
        self._parsed_frame_count += 1
        # Log the raw bytes of the successfully parsed frame (from parser buffer before it's consumed)
        # This requires FrameParser to also emit the full frame that was parsed.
        # For now, just log that a frame was parsed.
        # The data_payload_ba is just the DATA part.

        # For logging the full frame, FrameParser would need to emit it.
        # Let's log the payload for now.
        hex_payload_str = data_payload_ba.toHex(' ').data().decode('ascii').upper()
        self._append_to_custom_protocol_log(f"FID:{func_id_hex} Payload:{hex_payload_str}", is_hex=True,
                                            source="RX Parsed")

        msg = f"成功解析帧 (自定义协议): #{self._parsed_frame_count}, FID: {func_id_hex.upper()}"
        self.status_bar_label.setText(msg)
        if self.error_logger: self.error_logger.log_info(f"{msg} Payload len: {len(data_payload_ba)}")

        self.protocol_analyzer.analyze_frame(data_payload_ba, 'rx')  # Analyze based on payload or full frame?
        # Original analyzed full frame.
        # This would require FrameParser to emit full frame.
        # For now, using payload for stats.

        self.dispatch_data_to_receive_containers(data_payload_ba)

    def dispatch_data_to_receive_containers(self, data_payload_ba: QByteArray) -> None:
        if not self.receive_data_containers: return

        current_offset = 0
        parsed_data_for_log_export: Dict[str, str] = {}  # For CSV export
        timestamp_now = datetime.now()

        # Assuming "顺序填充 (Sequential)" mapping mode
        if self.data_mapping_combo.currentText() == "顺序填充 (Sequential)":
            for container_widget in self.receive_data_containers:
                config = container_widget.get_config()
                data_type = config["type"]
                byte_len = get_data_type_byte_length(data_type)  # Use the function from protocol_handler
                segment = QByteArray()

                if byte_len == -1:  # Variable length (string, hex string) - consumes rest of payload for this item
                    if current_offset < data_payload_ba.length():
                        segment = data_payload_ba.mid(current_offset)
                        current_offset = data_payload_ba.length()  # Consumed all
                    # else: segment remains empty if no more data
                elif byte_len > 0:  # Fixed length type
                    if current_offset + byte_len <= data_payload_ba.length():
                        segment = data_payload_ba.mid(current_offset, byte_len)
                        current_offset += byte_len
                    # else: segment remains empty if not enough data for this fixed type

                container_widget.set_value(segment, data_type)
                parsed_data_for_log_export[config["name"]] = container_widget.value_edit.text()

                # Plotting
                if PYQTGRAPH_AVAILABLE and config["plot_enabled"] and config["plot_target_id"] is not None:
                    target_plot_id = config["plot_target_id"]
                    if target_plot_id in self.plot_widgets_map:
                        val_float = container_widget.get_value_as_float()
                        if val_float is not None:
                            self.plot_widgets_map[target_plot_id].update_data(
                                config["id"], val_float, config["name"]
                            )
        # else: handle other mapping modes if any

        if parsed_data_for_log_export:
            self.data_recorder.add_parsed_frame_data(timestamp_now, parsed_data_for_log_export)

    @Slot(str, QByteArray)  # error_message, faulty_frame_or_buffer
    def on_frame_checksum_error(self, error_message: str, faulty_frame: QByteArray):
        self.status_bar_label.setText("校验和错误!")
        # Log the raw bytes of the frame that failed checksum
        hex_frame_str = faulty_frame.toHex(' ').data().decode('ascii').upper()
        self._append_to_custom_protocol_log(f"ChecksumError: {error_message} Frame: {hex_frame_str}", is_hex=True,
                                            source="RX Error")
        self.protocol_analyzer.analyze_frame(faulty_frame, 'rx', is_error=True)

    @Slot(str, QByteArray)  # error_message, buffer_state
    def on_frame_general_parse_error(self, error_message: str, buffer_state: QByteArray):
        self.status_bar_label.setText(f"协议解析错误: {error_message}")
        # Log for debugging
        # self._append_to_custom_protocol_log(f"ParseError: {error_message}", is_hex=False, source="RX System")

    @Slot(str)
    def on_serial_manager_error(self, error_message: str):
        # Display non-critical serial errors (e.g., not resource errors that cause disconnect)
        self.status_bar_label.setText(error_message)
        QMessageBox.warning(self, "串口通讯警告", error_message)

    @Slot(bool, str)
    def on_serial_connection_status_changed(self, is_connected: bool, message: str):
        self.update_port_status_ui(is_connected)
        self.status_bar_label.setText(message)
        if not is_connected and "资源错误" in message:  # Specific handling for resource errors
            QMessageBox.critical(self, "串口错误", message)

    # --- Basic Receive/Send Panel Helpers ---
    def _append_to_basic_receive(self, data_to_append: QByteArray, source: str = "RX"):
        if not hasattr(self, 'basic_receive_text_edit') or self.basic_receive_text_edit is None:
            return

        display_text_parts = []
        if self.basic_recv_timestamp_checkbox and self.basic_recv_timestamp_checkbox.isChecked():
            display_text_parts.append(datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] ")

        if source == "TX":
            display_text_parts.append("TX: ")
        elif source == "RX":
            display_text_parts.append("RX: ")
        # else INFO source has no prefix other than timestamp

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

    # --- Raw Data Recording Action ---
    @Slot(bool)
    def toggle_raw_data_recording_action(self, checked: bool):
        if checked:
            self.data_recorder.start_raw_recording()
            self.start_raw_record_action.setText("停止原始数据录制")
            self.status_bar_label.setText("原始数据录制已开始...")
        else:
            self.data_recorder.stop_raw_recording()
            self.start_raw_record_action.setText("开始原始数据录制")
            self.status_bar_label.setText("原始数据录制已停止。")
            # Optionally, prompt to save file here or rely on File menu action
            if self.data_recorder.recorded_raw_data:
                reply = QMessageBox.question(self, "保存录制数据",
                                             "是否立即保存已录制的原始数据?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    self.save_raw_recorded_data_action()

    # --- Application Close Event ---
    def closeEvent(self, event: Any) -> None:  # QCloseEvent type hint
        if self.error_logger: self.error_logger.log_info("应用程序正在关闭。")
        if self.serial_manager.is_connected:
            self.serial_manager.disconnect_port()

        # Stop data recorder if active
        if self.data_recorder.recording_raw:
            self.data_recorder.stop_raw_recording()
            # Ask to save if data exists and not yet saved? Or rely on menu.

        current_ui_cfg = self.gather_current_ui_config()
        self.config_manager.save_config(current_ui_cfg)  # Auto-save default config
        if self.error_logger: self.error_logger.log_info("配置已在退出时自动保存。")
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = SerialDebugger()
    main_win.show()
    sys.exit(app.exec())