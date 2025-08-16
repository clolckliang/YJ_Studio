# panel_plugins/can_bus/can_panel.py
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget, QTableWidget,
                             QTableWidgetItem, QComboBox, QLineEdit,
                             QGroupBox, QSpinBox, QCheckBox, QSplitter,
                             QTextEdit, QProgressBar, QTabWidget,
                             QHeaderView, QMessageBox, QFileDialog,
                             QFrame, QSlider, QDoubleSpinBox)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, Slot
from PySide6.QtGui import QFont, QColor, QPalette
from typing import Dict, Any, Optional, List, Tuple
import can
from datetime import datetime
import json
import csv
import threading
import time
from collections import defaultdict, deque

# 导入 PanelInterface
try:
    from core.panel_interface import PanelInterface
except ImportError:
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from core.panel_interface import PanelInterface

# 导入错误日志记录器
try:
    from utils.logger import ErrorLogger
except ImportError:
    ErrorLogger = None


class CANMessageReceiver(QThread):
    """CAN消息接收线程"""
    message_received = Signal(object)  # 接收到消息的信号
    error_occurred = Signal(str)  # 错误信号
    
    def __init__(self, bus: can.Bus):
        super().__init__()
        self.bus = bus
        self.running = False
        self.message_buffer = deque(maxlen=10000)  # 消息缓冲区
    
    def run(self):
        """线程运行函数"""
        self.running = True
        try:
            while self.running:
                msg = self.bus.recv(timeout=0.1)
                if msg:
                    self.message_buffer.append(msg)
                    self.message_received.emit(msg)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        """停止接收线程"""
        self.running = False
        self.wait()


class CANMessageFilter:
    """CAN消息过滤器"""
    
    def __init__(self):
        self.enabled = False
        self.id_filters = set()  # ID过滤器
        self.data_filters = []   # 数据过滤器
        self.min_dlc = 0
        self.max_dlc = 8
    
    def add_id_filter(self, can_id: int):
        """添加ID过滤器"""
        self.id_filters.add(can_id)
    
    def remove_id_filter(self, can_id: int):
        """移除ID过滤器"""
        self.id_filters.discard(can_id)
    
    def set_dlc_range(self, min_dlc: int, max_dlc: int):
        """设置数据长度范围"""
        self.min_dlc = min_dlc
        self.max_dlc = max_dlc
    
    def should_display(self, msg: can.Message) -> bool:
        """判断消息是否应该显示"""
        if not self.enabled:
            return True
        
        # ID过滤
        if self.id_filters and msg.arbitration_id not in self.id_filters:
            return False
        
        # 数据长度过滤
        if not (self.min_dlc <= msg.dlc <= self.max_dlc):
            return False
        
        return True


class CANStatistics:
    """CAN总线统计信息"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置统计信息"""
        self.total_messages = 0
        self.message_rate = 0.0
        self.error_count = 0
        self.id_statistics = defaultdict(int)
        self.last_update_time = time.time()
        self.message_times = deque(maxlen=1000)
    
    def add_message(self, msg_or_id):
        """添加消息到统计"""
        current_time = time.time()
        self.total_messages += 1
        
        # 支持传入消息对象或ID
        if hasattr(msg_or_id, 'arbitration_id'):
            msg_id = msg_or_id.arbitration_id
        else:
            msg_id = msg_or_id
            
        self.id_statistics[msg_id] += 1
        self.message_times.append(current_time)
        
        # 计算消息速率
        if len(self.message_times) > 1:
            time_span = self.message_times[-1] - self.message_times[0]
            if time_span > 0:
                self.message_rate = len(self.message_times) / time_span
    
    def get_top_ids(self, count: int = 10) -> List[Tuple[int, int]]:
        """获取消息数量最多的ID"""
        return sorted(self.id_statistics.items(), key=lambda x: x[1], reverse=True)[:count]


class CANBusPanel(PanelInterface):
    """
    CAN总线面板实现
    
    实现了一个完整的CAN总线通信工具，包括：
    - CAN消息发送/接收
    - 消息过滤和解析
    - 数据可视化
    - 总线状态监控
    """
    
    # PanelInterface 必须定义的静态属性
    PANEL_TYPE_NAME: str = "can_bus"
    PANEL_DISPLAY_NAME: str = "CAN总线工具"
    
    def __init__(self,
                 panel_id: int,
                 main_window_ref: 'SerialDebugger',
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        """
        初始化CAN总线面板
        
        Args:
            panel_id: 面板唯一标识符
            main_window_ref: 主窗口引用
            initial_config: 初始配置数据
            parent: 父级组件
        """
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        
        # CAN总线状态
        self.bus: Optional[can.Bus] = None
        self.is_running: bool = False
        self.receiver_thread: Optional[CANMessageReceiver] = None
        self.received_messages: deque = deque(maxlen=5000)
        self.filtered_messages: List[Dict] = []
        self.message_count: int = 0
        
        # 功能组件
        self.message_filter = CANMessageFilter()
        self.statistics = CANStatistics()
        
        # UI组件 - 连接设置
        self.interface_combo: Optional[QComboBox] = None
        self.channel_input: Optional[QLineEdit] = None
        self.baudrate_combo: Optional[QComboBox] = None
        self.start_button: Optional[QPushButton] = None
        
        # UI组件 - 消息显示
        self.tab_widget: Optional[QTabWidget] = None
        self.message_table: Optional[QTableWidget] = None
        self.statistics_table: Optional[QTableWidget] = None
        self.log_text: Optional[QTextEdit] = None
        
        # UI组件 - 消息发送
        self.id_input: Optional[QSpinBox] = None
        self.data_input: Optional[QLineEdit] = None
        self.send_button: Optional[QPushButton] = None
        self.extended_id_checkbox: Optional[QCheckBox] = None
        self.repeat_checkbox: Optional[QCheckBox] = None
        self.repeat_interval: Optional[QDoubleSpinBox] = None
        
        # UI组件 - 过滤器
        self.filter_enabled_checkbox: Optional[QCheckBox] = None
        self.filter_id_input: Optional[QLineEdit] = None
        self.min_dlc_input: Optional[QSpinBox] = None
        self.max_dlc_input: Optional[QSpinBox] = None
        
        # UI组件 - 统计信息
        self.total_messages_label: Optional[QLabel] = None
        self.message_rate_label: Optional[QLabel] = None
        self.error_count_label: Optional[QLabel] = None
        
        # 定时器
        self.update_timer: Optional[QTimer] = None
        self.repeat_timer: Optional[QTimer] = None
        
        # 初始化UI
        self._init_ui()
        self._setup_connections()
        
        # 应用初始配置
        if initial_config:
            self.apply_config(initial_config)
    
    def _init_ui(self) -> None:
        """构建CAN总线界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        
        # 创建主分割器
        main_splitter = QSplitter(Qt.Vertical)
        
        # 上半部分：连接设置和控制
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        # 连接设置区域
        self._create_connection_group(top_layout)
        
        # 统计信息区域
        self._create_statistics_group(top_layout)
        
        # 过滤器设置区域
        self._create_filter_group(top_layout)
        
        main_splitter.addWidget(top_widget)
        
        # 下半部分：选项卡界面
        self.tab_widget = QTabWidget()
        
        # 消息接收选项卡
        self._create_message_tab()
        
        # 统计分析选项卡
        self._create_statistics_tab()
        
        # 日志选项卡
        self._create_log_tab()
        
        main_splitter.addWidget(self.tab_widget)
        
        # 底部：消息发送区域
        send_widget = self._create_send_widget()
        main_splitter.addWidget(send_widget)
        
        # 设置分割器比例
        main_splitter.setSizes([150, 400, 100])
        
        main_layout.addWidget(main_splitter)
        
        # 设置定时器
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(100)  # 每100ms更新一次界面
        
        # 重复发送定时器
        self.repeat_timer = QTimer(self)
        self.repeat_timer.timeout.connect(self._send_message)
    
    def _create_connection_group(self, parent_layout: QHBoxLayout) -> None:
        """创建连接设置组"""
        connection_group = QGroupBox("连接设置")
        connection_layout = QVBoxLayout()
        
        # 接口类型选择
        interface_layout = QHBoxLayout()
        interface_layout.addWidget(QLabel("接口:"))
        self.interface_combo = QComboBox()
        self.interface_combo.addItems([
            "socketcan", "virtual", "pcan", "ixxat", 
            "nican", "iscan", "kvaser", "serial", "usb2can"
        ])
        interface_layout.addWidget(self.interface_combo)
        connection_layout.addLayout(interface_layout)
        
        # 通道设置
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("通道:"))
        self.channel_input = QLineEdit("can0")
        channel_layout.addWidget(self.channel_input)
        connection_layout.addLayout(channel_layout)
        
        # 波特率设置
        baudrate_layout = QHBoxLayout()
        baudrate_layout.addWidget(QLabel("波特率:"))
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["500000", "250000", "125000", "1000000", "100000", "50000"])
        baudrate_layout.addWidget(self.baudrate_combo)
        connection_layout.addLayout(baudrate_layout)
        
        # 开始/停止按钮
        self.start_button = QPushButton("启动")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        connection_layout.addWidget(self.start_button)
        
        connection_group.setLayout(connection_layout)
        connection_group.setMaximumWidth(200)
        parent_layout.addWidget(connection_group)
    
    def _create_statistics_group(self, parent_layout: QHBoxLayout) -> None:
        """创建统计信息组"""
        stats_group = QGroupBox("统计信息")
        stats_layout = QVBoxLayout()
        
        self.total_messages_label = QLabel("总消息数: 0")
        self.message_rate_label = QLabel("消息速率: 0.0 msg/s")
        self.error_count_label = QLabel("错误计数: 0")
        
        stats_layout.addWidget(self.total_messages_label)
        stats_layout.addWidget(self.message_rate_label)
        stats_layout.addWidget(self.error_count_label)
        
        # 重置按钮
        reset_button = QPushButton("重置统计")
        reset_button.clicked.connect(self._reset_statistics)
        stats_layout.addWidget(reset_button)
        
        stats_group.setLayout(stats_layout)
        stats_group.setMaximumWidth(150)
        parent_layout.addWidget(stats_group)
    
    def _create_filter_group(self, parent_layout: QHBoxLayout) -> None:
        """创建过滤器组"""
        filter_group = QGroupBox("消息过滤")
        filter_layout = QVBoxLayout()
        
        # 启用过滤器
        self.filter_enabled_checkbox = QCheckBox("启用过滤")
        filter_layout.addWidget(self.filter_enabled_checkbox)
        
        # ID过滤器
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("ID过滤:"))
        self.filter_id_input = QLineEdit()
        self.filter_id_input.setPlaceholderText("123,456,789")
        id_layout.addWidget(self.filter_id_input)
        filter_layout.addLayout(id_layout)
        
        # DLC范围
        dlc_layout = QHBoxLayout()
        dlc_layout.addWidget(QLabel("DLC:"))
        self.min_dlc_input = QSpinBox()
        self.min_dlc_input.setRange(0, 8)
        self.max_dlc_input = QSpinBox()
        self.max_dlc_input.setRange(0, 8)
        self.max_dlc_input.setValue(8)
        dlc_layout.addWidget(self.min_dlc_input)
        dlc_layout.addWidget(QLabel("-"))
        dlc_layout.addWidget(self.max_dlc_input)
        filter_layout.addLayout(dlc_layout)
        
        filter_group.setLayout(filter_layout)
        filter_group.setMaximumWidth(200)
        parent_layout.addWidget(filter_group)
        
        # 添加弹性空间
        parent_layout.addStretch()
    
    def _create_message_tab(self) -> None:
        """创建消息接收选项卡"""
        message_widget = QWidget()
        message_layout = QVBoxLayout(message_widget)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        clear_button = QPushButton("清空消息")
        clear_button.clicked.connect(self._clear_messages)
        toolbar_layout.addWidget(clear_button)
        
        export_button = QPushButton("导出消息")
        export_button.clicked.connect(self._export_messages)
        toolbar_layout.addWidget(export_button)
        
        toolbar_layout.addStretch()
        message_layout.addLayout(toolbar_layout)
        
        # 消息表格
        self.message_table = QTableWidget()
        self.message_table.setColumnCount(7)
        self.message_table.setHorizontalHeaderLabels([
            "时间", "ID", "类型", "DLC", "数据", "周期(ms)", "计数"
        ])
        self.message_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.message_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.message_table.setAlternatingRowColors(True)
        
        # 设置列宽
        header = self.message_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 类型
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # DLC
        header.setSectionResizeMode(4, QHeaderView.Stretch)          # 数据
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 周期
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 计数
        
        message_layout.addWidget(self.message_table)
        
        self.tab_widget.addTab(message_widget, "消息接收")
    
    def _create_statistics_tab(self) -> None:
        """创建统计分析选项卡"""
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        
        # 统计表格
        self.statistics_table = QTableWidget()
        self.statistics_table.setColumnCount(3)
        self.statistics_table.setHorizontalHeaderLabels(["ID", "消息数", "频率(Hz)"])
        self.statistics_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.statistics_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        stats_layout.addWidget(self.statistics_table)
        
        self.tab_widget.addTab(stats_widget, "统计分析")
    
    def _create_log_tab(self) -> None:
        """创建日志选项卡"""
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(1000)  # 限制日志行数
        
        # 设置等宽字体
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        self.log_text.setFont(font)
        
        log_layout.addWidget(self.log_text)
        
        # 日志控制按钮
        log_controls = QHBoxLayout()
        
        clear_log_button = QPushButton("清空日志")
        clear_log_button.clicked.connect(self._clear_log)
        log_controls.addWidget(clear_log_button)
        
        save_log_button = QPushButton("保存日志")
        save_log_button.clicked.connect(self._save_log)
        log_controls.addWidget(save_log_button)
        
        log_controls.addStretch()
        log_layout.addLayout(log_controls)
        
        self.tab_widget.addTab(log_widget, "日志")
    
    def _create_send_widget(self) -> QWidget:
        """创建消息发送组件"""
        send_widget = QWidget()
        send_layout = QVBoxLayout(send_widget)
        
        send_group = QGroupBox("发送消息")
        group_layout = QHBoxLayout()
        
        # ID输入
        group_layout.addWidget(QLabel("ID:"))
        self.id_input = QSpinBox()
        self.id_input.setRange(0, 0x1FFFFFFF)
        self.id_input.setDisplayIntegerBase(16)
        self.id_input.setPrefix("0x")
        group_layout.addWidget(self.id_input)
        
        # 扩展帧复选框
        self.extended_id_checkbox = QCheckBox("扩展帧")
        group_layout.addWidget(self.extended_id_checkbox)
        
        # 数据输入
        group_layout.addWidget(QLabel("数据:"))
        self.data_input = QLineEdit()
        self.data_input.setPlaceholderText("00 11 22 33 44 55 66 77")
        group_layout.addWidget(self.data_input)
        
        # 发送按钮
        self.send_button = QPushButton("发送")
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)
        group_layout.addWidget(self.send_button)
        
        # 重复发送
        self.repeat_checkbox = QCheckBox("重复发送")
        group_layout.addWidget(self.repeat_checkbox)
        
        group_layout.addWidget(QLabel("间隔(s):"))
        self.repeat_interval = QDoubleSpinBox()
        self.repeat_interval.setRange(0.001, 60.0)
        self.repeat_interval.setValue(1.0)
        self.repeat_interval.setDecimals(3)
        group_layout.addWidget(self.repeat_interval)
        
        send_group.setLayout(group_layout)
        send_layout.addWidget(send_group)
        
        return send_widget
    
    def _setup_connections(self) -> None:
        """设置信号连接"""
        # 连接按钮
        self.start_button.clicked.connect(self._toggle_connection)
        
        # 发送按钮
        self.send_button.clicked.connect(self._send_message)
        
        # 过滤器变化
        self.filter_enabled_checkbox.toggled.connect(self._update_filter)
        self.filter_id_input.textChanged.connect(self._update_filter)
        self.min_dlc_input.valueChanged.connect(self._update_filter)
        self.max_dlc_input.valueChanged.connect(self._update_filter)
        
        # 重复发送
        self.repeat_checkbox.toggled.connect(self._toggle_repeat_send)
        
        # 扩展帧ID范围调整
        self.extended_id_checkbox.toggled.connect(self._update_id_range)
    
    def _toggle_connection(self) -> None:
        """切换连接状态"""
        if self.is_running:
            self._stop_bus()
        else:
            self._start_bus()
    
    def _start_bus(self) -> None:
        """启动CAN总线"""
        try:
            interface = self.interface_combo.currentText()
            channel = self.channel_input.text().strip()
            baudrate = int(self.baudrate_combo.currentText())
            
            if not channel:
                self._log_message("错误: 通道名称不能为空", "error")
                return
            
            self._log_message(f"正在启动CAN总线: {interface} - {channel} @ {baudrate}bps", "info")
            
            # 创建CAN总线
            self.bus = can.Bus(
                interface=interface,
                channel=channel,
                bitrate=baudrate,
                receive_own_messages=True
            )
            
            # 创建并启动接收线程
            self.receiver_thread = CANMessageReceiver(self.bus)
            self.receiver_thread.message_received.connect(self._on_message_received)
            self.receiver_thread.error_occurred.connect(self._on_receiver_error)
            self.receiver_thread.start()
            
            # 更新状态
            self.is_running = True
            self.message_count = 0
            self.received_messages.clear()
            self.filtered_messages.clear()
            self.statistics.reset()
            
            # 更新UI
            self.start_button.setText("停止")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
            """)
            self.send_button.setEnabled(True)
            
            self._log_message("CAN总线启动成功", "success")
            
        except Exception as e:
            error_msg = f"启动CAN总线失败: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
    
    def _stop_bus(self) -> None:
        """停止CAN总线"""
        try:
            self._log_message("正在停止CAN总线...", "info")
            
            # 停止重复发送
            if self.repeat_timer.isActive():
                self.repeat_timer.stop()
                self.repeat_checkbox.setChecked(False)
            
            # 停止接收线程
            if self.receiver_thread:
                self.receiver_thread.stop()
                self.receiver_thread = None
            
            # 关闭总线
            if self.bus:
                self.bus.shutdown()
                self.bus = None
            
            # 更新状态
            self.is_running = False
            
            # 更新UI
            self.start_button.setText("启动")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.send_button.setEnabled(False)
            
            self._log_message("CAN总线已停止", "info")
            
        except Exception as e:
            error_msg = f"停止CAN总线失败: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
    
    def _on_message_received(self, msg: can.Message) -> None:
        """接收到CAN消息时的回调"""
        try:
            # 更新统计信息
            self.statistics.add_message(msg)
            self.message_count += 1
            
            # 检查过滤器
            if not self.message_filter.should_display(msg):
                return
            
            # 计算消息周期（如果有相同ID的历史消息）
            period_ms = self._calculate_message_period(msg.arbitration_id)
            
            # 创建消息记录
            message = {
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "id": f"{msg.arbitration_id:08X}" if msg.is_extended_id else f"{msg.arbitration_id:03X}",
                "type": "扩展帧" if msg.is_extended_id else "标准帧",
                "dlc": msg.dlc,
                "data": " ".join(f"{b:02X}" for b in msg.data),
                "period": period_ms,
                "count": self.statistics.id_statistics[msg.arbitration_id],
                "raw_msg": msg  # 保存原始消息用于导出
            }
            
            # 添加到消息列表
            self.received_messages.append(message)
            
            # 记录日志
            log_msg = f"RX: ID={message['id']} DLC={msg.dlc} Data=[{message['data']}]"
            self._log_message(log_msg, "rx")
            
        except Exception as e:
            error_msg = f"处理CAN消息失败: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
    
    def _on_receiver_error(self, error_msg: str) -> None:
        """接收线程错误处理"""
        self.statistics.error_count += 1
        self._log_message(f"接收错误: {error_msg}", "error")
        if self.error_logger:
            self.error_logger.log_error(f"CAN接收错误: {error_msg}", self.PANEL_TYPE_NAME)
    
    def _calculate_message_period(self, can_id: int) -> str:
        """计算消息周期"""
        try:
            # 查找最近的相同ID消息
            current_time = time.time()
            for i in range(len(self.received_messages) - 1, -1, -1):
                msg = self.received_messages[i]
                if 'raw_msg' in msg and msg['raw_msg'].arbitration_id == can_id:
                    # 计算时间差
                    last_time = time.mktime(datetime.strptime(
                        msg['timestamp'], "%H:%M:%S.%f").timetuple())
                    period_s = current_time - last_time
                    if period_s > 0:
                        return f"{period_s * 1000:.1f}"
                    break
            return "-"
        except:
            return "-"
    
    def _update_ui(self) -> None:
        """更新界面显示"""
        # 更新统计信息标签
        self.total_messages_label.setText(f"总消息数: {self.statistics.total_messages}")
        self.message_rate_label.setText(f"消息速率: {self.statistics.message_rate:.1f} msg/s")
        self.error_count_label.setText(f"错误计数: {self.statistics.error_count}")
        
        # 更新消息表格（只显示最近的消息以提高性能）
        if self.received_messages:
            # 限制显示的消息数量
            display_messages = list(self.received_messages)[-1000:]  # 最近1000条
            
            self.message_table.setRowCount(len(display_messages))
            
            for row, msg in enumerate(display_messages):
                self.message_table.setItem(row, 0, QTableWidgetItem(msg["timestamp"]))
                self.message_table.setItem(row, 1, QTableWidgetItem(msg["id"]))
                self.message_table.setItem(row, 2, QTableWidgetItem(msg["type"]))
                self.message_table.setItem(row, 3, QTableWidgetItem(str(msg["dlc"])))
                self.message_table.setItem(row, 4, QTableWidgetItem(msg["data"]))
                self.message_table.setItem(row, 5, QTableWidgetItem(str(msg["period"])))
                self.message_table.setItem(row, 6, QTableWidgetItem(str(msg["count"])))
            
            # 自动滚动到最后一行
            self.message_table.scrollToBottom()
        
        # 更新统计表格
        self._update_statistics_table()
    
    def _update_statistics_table(self) -> None:
        """更新统计表格"""
        top_ids = self.statistics.get_top_ids(20)  # 显示前20个最活跃的ID
        
        self.statistics_table.setRowCount(len(top_ids))
        
        for row, (can_id, count) in enumerate(top_ids):
            # 计算频率
            if len(self.statistics.message_times) > 1:
                time_span = self.statistics.message_times[-1] - self.statistics.message_times[0]
                frequency = count / time_span if time_span > 0 else 0
            else:
                frequency = 0
            
            self.statistics_table.setItem(row, 0, QTableWidgetItem(f"{can_id:03X}"))
            self.statistics_table.setItem(row, 1, QTableWidgetItem(str(count)))
            self.statistics_table.setItem(row, 2, QTableWidgetItem(f"{frequency:.2f}"))
    
    def _send_message(self) -> None:
        """发送CAN消息"""
        if not self.is_running or not self.bus:
            self._log_message("错误: CAN总线未连接", "error")
            return
            
        try:
            # 获取消息ID
            msg_id = self.id_input.value()
            
            # 获取数据
            data_str = self.data_input.text().strip()
            if data_str:
                # 解析十六进制数据
                data_str = data_str.replace(" ", "").replace(",", "")
                if len(data_str) % 2 != 0:
                    self._log_message("错误: 数据长度必须是偶数", "error")
                    return
                
                data_bytes = bytes.fromhex(data_str)
                if len(data_bytes) > 8:
                    self._log_message("错误: CAN数据长度不能超过8字节", "error")
                    return
            else:
                data_bytes = b""
            
            # 检查扩展帧
            is_extended = self.extended_id_checkbox.isChecked()
            if is_extended and msg_id > 0x1FFFFFFF:
                self._log_message("错误: 扩展帧ID不能超过0x1FFFFFFF", "error")
                return
            elif not is_extended and msg_id > 0x7FF:
                self._log_message("错误: 标准帧ID不能超过0x7FF", "error")
                return
            
            # 创建消息
            msg = can.Message(
                arbitration_id=msg_id,
                data=data_bytes,
                is_extended_id=is_extended
            )
            
            # 发送消息
            self.bus.send(msg)
            
            # 记录发送的消息
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            msg_info = {
                "timestamp": timestamp,
                "id": f"{msg_id:08X}" if is_extended else f"{msg_id:03X}",
                "type": "发送",
                "dlc": len(data_bytes),
                "data": data_str.upper(),
                "period": 0,
                "count": 1,
                "raw_msg": msg
            }
            
            self.received_messages.append(msg_info)
            self.statistics.add_message(msg)
            
            # 记录日志
            log_msg = f"TX: ID={msg_info['id']} DLC={len(data_bytes)} Data=[{data_str.upper()}]"
            self._log_message(log_msg, "tx")
            
            # 检查重复发送
            if self.repeat_checkbox.isChecked():
                interval = int(self.repeat_interval.value() * 1000)  # 转换为毫秒
                if not self.repeat_timer.isActive():
                    self.repeat_timer.start(interval)
                    self._log_message(f"开始重复发送，间隔: {self.repeat_interval.value()}s", "info")
            
        except ValueError as e:
            error_msg = f"数据格式错误: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
        except Exception as e:
            error_msg = f"发送消息失败: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
            self.statistics.error_count += 1
    
    def _log_message(self, message: str, level: str = "info") -> None:
        """记录日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # 设置颜色
        color_map = {
            "info": "black",
            "success": "green",
            "warning": "orange",
            "error": "red",
            "rx": "blue",
            "tx": "purple"
        }
        
        color = color_map.get(level, "black")
        formatted_msg = f"<span style='color: {color}'>[{timestamp}] {message}</span>"
        
        if self.log_text:
            self.log_text.append(formatted_msg)
            # 限制日志行数
            if self.log_text.document().blockCount() > 1000:
                cursor = self.log_text.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.select(cursor.BlockUnderCursor)
                cursor.removeSelectedText()
    
    def _clear_messages(self) -> None:
        """清空消息列表"""
        self.received_messages.clear()
        self.filtered_messages.clear()
        self.message_table.setRowCount(0)
        self._log_message("消息列表已清空", "info")
    
    def _export_messages(self) -> None:
        """导出消息到CSV文件"""
        if not self.received_messages:
            self._log_message("没有消息可导出", "warning")
            return
        
        try:
            from PySide6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "导出消息", f"can_messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV文件 (*.csv)"
            )
            
            if file_path:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["时间", "ID", "类型", "DLC", "数据", "周期(ms)", "计数"])
                    
                    for msg in self.received_messages:
                        writer.writerow([
                            msg["timestamp"],
                            msg["id"],
                            msg["type"],
                            msg["dlc"],
                            msg["data"],
                            msg["period"],
                            msg["count"]
                        ])
                
                self._log_message(f"消息已导出到: {file_path}", "success")
        
        except Exception as e:
            error_msg = f"导出消息失败: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
    
    def _update_filter(self) -> None:
        """更新消息过滤器"""
        try:
            self.message_filter.enabled = self.filter_enabled_checkbox.isChecked()
            
            # 更新ID过滤器
            filter_text = self.filter_id_input.text().strip()
            self.message_filter.id_filters.clear()
            
            if filter_text:
                # 支持多个ID，用逗号分隔
                id_list = filter_text.split(',')
                for id_str in id_list:
                    id_str = id_str.strip()
                    if id_str:
                        try:
                            can_id = int(id_str, 16)
                            self.message_filter.add_id_filter(can_id)
                        except ValueError:
                            self._log_message(f"无效的ID格式: {id_str}", "warning")
            
            # 更新DLC范围
            min_dlc = self.min_dlc_input.value()
            max_dlc = self.max_dlc_input.value()
            self.message_filter.set_dlc_range(min_dlc, max_dlc)
            
            self._log_message(f"过滤器已更新: 启用={self.message_filter.enabled}", "info")
            
        except Exception as e:
            error_msg = f"更新过滤器失败: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
    
    def _reset_statistics(self) -> None:
        """重置统计信息"""
        self.statistics.reset()
        self._update_ui()
        self._log_message("统计信息已重置", "info")
    
    def _toggle_repeat_send(self, enabled: bool) -> None:
        """切换重复发送状态"""
        if not enabled and self.repeat_timer.isActive():
            self.repeat_timer.stop()
            self._log_message("重复发送已停止", "info")
    
    def _update_id_range(self, is_extended: bool) -> None:
        """更新ID输入范围"""
        if is_extended:
            self.id_input.setRange(0, 0x1FFFFFFF)
            self._log_message("切换到扩展帧模式 (29位ID)", "info")
        else:
            self.id_input.setRange(0, 0x7FF)
            self._log_message("切换到标准帧模式 (11位ID)", "info")
    
    def _clear_log(self) -> None:
        """清空日志"""
        if self.log_text:
            self.log_text.clear()
            self._log_message("日志已清空", "info")
    
    def _save_log(self) -> None:
        """保存日志到文件"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存日志", f"can_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt)"
            )
            
            if file_path and self.log_text:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                
                self._log_message(f"日志已保存到: {file_path}", "success")
        
        except Exception as e:
            error_msg = f"保存日志失败: {str(e)}"
            self._log_message(error_msg, "error")
            if self.error_logger:
                self.error_logger.log_error(error_msg, self.PANEL_TYPE_NAME)
    
    # === PanelInterface 必须实现的方法 ===
    
    def get_config(self) -> Dict[str, Any]:
        """返回当前面板配置"""
        return {
            "version": "1.0",
            "interface": self.interface_combo.currentText(),
            "channel": self.channel_input.text(),
            "baudrate": self.baudrate_combo.currentText(),
            "is_running": self.is_running,
            "panel_type": self.PANEL_TYPE_NAME
        }
    
    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置恢复面板状态"""
        try:
            interface = config.get("interface", "socketcan")
            channel = config.get("channel", "can0")
            baudrate = config.get("baudrate", "500000")
            
            self.interface_combo.setCurrentText(interface)
            self.channel_input.setText(channel)
            self.baudrate_combo.setCurrentText(baudrate)
            
            if config.get("is_running", False):
                self._start_bus()
                self.start_button.setText("停止")
            
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"应用配置失败: {str(e)}", self.PANEL_TYPE_NAME)
    
    def get_initial_dock_title(self) -> str:
        """返回初始停靠窗口标题"""
        return f"{self.PANEL_DISPLAY_NAME} ({self.panel_id})"
    
    # === PanelInterface 可选实现的方法 ===
    
    def on_panel_added(self) -> None:
        """面板被添加后的回调"""
        super().on_panel_added()
        if self.error_logger:
            self.error_logger.log_info(
                f"CAN总线面板 (ID: {self.panel_id}) 已添加",
                self.PANEL_TYPE_NAME
            )
    
    def on_panel_removed(self) -> None:
        """面板被移除前的清理"""
        super().on_panel_removed()
        self._stop_bus()
        if self.error_logger:
            self.error_logger.log_info(
                f"CAN总线面板 (ID: {self.panel_id}) 正在清理",
                self.PANEL_TYPE_NAME
            )
    
    def update_theme(self) -> None:
        """主题变化时的更新"""
        super().update_theme()
        # 可以添加主题相关的UI更新逻辑
