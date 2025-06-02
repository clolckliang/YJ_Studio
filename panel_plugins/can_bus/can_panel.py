# panel_plugins/can_bus/can_panel.py
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget, QTableWidget,
                             QTableWidgetItem, QComboBox, QLineEdit,
                             QGroupBox, QSpinBox, QCheckBox)
from PySide6.QtCore import Qt, Signal, QTimer
from typing import Dict, Any, Optional, List
import can
from datetime import datetime

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
        self.received_messages: List[Dict] = []
        self.message_count: int = 0
        
        # UI组件
        self.interface_combo: Optional[QComboBox] = None
        self.channel_input: Optional[QLineEdit] = None
        self.baudrate_combo: Optional[QComboBox] = None
        self.start_button: Optional[QPushButton] = None
        self.message_table: Optional[QTableWidget] = None
        self.id_input: Optional[QSpinBox] = None
        self.data_input: Optional[QLineEdit] = None
        self.send_button: Optional[QPushButton] = None
        
        # 初始化UI
        self._init_ui()
        
        # 应用初始配置
        if initial_config:
            self.apply_config(initial_config)
    
    def _init_ui(self) -> None:
        """构建CAN总线界面"""
        main_layout = QVBoxLayout(self)
        
        # 连接设置区域
        connection_group = QGroupBox("连接设置")
        connection_layout = QVBoxLayout()
        
        # 接口类型选择
        interface_layout = QHBoxLayout()
        interface_layout.addWidget(QLabel("接口类型:"))
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
        self.baudrate_combo.addItems(["500000", "250000", "125000", "1000000"])
        baudrate_layout.addWidget(self.baudrate_combo)
        connection_layout.addLayout(baudrate_layout)
        
        # 开始/停止按钮
        self.start_button = QPushButton("启动")
        self.start_button.clicked.connect(self._toggle_connection)
        connection_layout.addWidget(self.start_button)
        
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)
        
        # 消息接收区域
        receive_group = QGroupBox("接收消息")
        receive_layout = QVBoxLayout()
        
        # 消息表格
        self.message_table = QTableWidget()
        self.message_table.setColumnCount(6)
        self.message_table.setHorizontalHeaderLabels([
            "时间", "ID", "类型", "长度", "数据", "计数"
        ])
        self.message_table.setEditTriggers(QTableWidget.NoEditTriggers)
        receive_layout.addWidget(self.message_table)
        
        receive_group.setLayout(receive_layout)
        main_layout.addWidget(receive_group)
        
        # 消息发送区域
        send_group = QGroupBox("发送消息")
        send_layout = QHBoxLayout()
        
        # ID输入
        send_layout.addWidget(QLabel("ID:"))
        self.id_input = QSpinBox()
        self.id_input.setRange(0, 0x7FF)
        self.id_input.setDisplayIntegerBase(16)
        send_layout.addWidget(self.id_input)
        
        # 数据输入
        send_layout.addWidget(QLabel("数据:"))
        self.data_input = QLineEdit()
        self.data_input.setPlaceholderText("00 11 22 33 44 55 66 77")
        send_layout.addWidget(self.data_input)
        
        # 发送按钮
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self._send_message)
        send_layout.addWidget(self.send_button)
        
        send_group.setLayout(send_layout)
        main_layout.addWidget(send_group)
        
        self.setLayout(main_layout)
        
        # 设置定时器更新界面
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(100)  # 每100ms更新一次界面
    
    def _toggle_connection(self) -> None:
        """切换连接状态"""
        if self.is_running:
            self._stop_bus()
            self.start_button.setText("启动")
        else:
            self._start_bus()
            self.start_button.setText("停止")
    
    def _start_bus(self) -> None:
        """启动CAN总线"""
        try:
            interface = self.interface_combo.currentText()
            channel = self.channel_input.text()
            baudrate = int(self.baudrate_combo.currentText())
            
            self.bus = can.Bus(
                interface=interface,
                channel=channel,
                bitrate=baudrate,
                receive_own_messages=True
            )
            
            # 创建接收线程
            self.notifier = can.Notifier(self.bus, [self._on_message_received])
            self.is_running = True
            self.message_count = 0
            self.received_messages.clear()
            
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"启动CAN总线失败: {str(e)}", self.PANEL_TYPE_NAME)
    
    def _stop_bus(self) -> None:
        """停止CAN总线"""
        try:
            if self.bus:
                self.notifier.stop()
                self.bus.shutdown()
                self.bus = None
                self.is_running = False
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"停止CAN总线失败: {str(e)}", self.PANEL_TYPE_NAME)
    
    def _on_message_received(self, msg: can.Message) -> None:
        """接收到CAN消息时的回调"""
        try:
            message = {
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "id": f"{msg.arbitration_id:03X}",
                "type": "标准帧" if msg.is_extended_id else "扩展帧",
                "length": msg.dlc,
                "data": " ".join(f"{b:02X}" for b in msg.data),
                "count": self.message_count + 1
            }
            self.received_messages.append(message)
            self.message_count += 1
            
            # 限制消息数量
            if len(self.received_messages) > 1000:
                self.received_messages = self.received_messages[-500:]
                
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"处理CAN消息失败: {str(e)}", self.PANEL_TYPE_NAME)
    
    def _update_ui(self) -> None:
        """更新界面显示"""
        if not self.received_messages:
            return
            
        self.message_table.setRowCount(len(self.received_messages))
        
        for row, msg in enumerate(self.received_messages):
            self.message_table.setItem(row, 0, QTableWidgetItem(msg["timestamp"]))
            self.message_table.setItem(row, 1, QTableWidgetItem(msg["id"]))
            self.message_table.setItem(row, 2, QTableWidgetItem(msg["type"]))
            self.message_table.setItem(row, 3, QTableWidgetItem(str(msg["length"])))
            self.message_table.setItem(row, 4, QTableWidgetItem(msg["data"]))
            self.message_table.setItem(row, 5, QTableWidgetItem(str(msg["count"])))
        
        # 自动滚动到最后一行
        self.message_table.scrollToBottom()
    
    def _send_message(self) -> None:
        """发送CAN消息"""
        if not self.is_running or not self.bus:
            return
            
        try:
            # 解析数据
            data_str = self.data_input.text().strip()
            data_bytes = bytes.fromhex(data_str) if data_str else b''
            
            # 创建消息
            msg = can.Message(
                arbitration_id=self.id_input.value(),
                data=data_bytes,
                is_extended_id=False
            )
            
            # 发送消息
            self.bus.send(msg)
            
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"发送CAN消息失败: {str(e)}", self.PANEL_TYPE_NAME)
    
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
