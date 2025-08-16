# -*- coding: utf-8 -*-
"""
增强的串口配置和监控面板
集成连接状态、数据格式化显示、协议解析等功能
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QTabWidget, QPushButton, QFrame
)

from ui.fixed_panels import SerialConfigDefinitionPanelWidget
from ui.serial_status_widget import SerialStatusWidget
from ui.data_format_widget import DataFormatWidget
from utils.data_models import SerialPortConfig, FrameConfig
from utils.constants import ChecksumMode


class EnhancedSerialPanel(QWidget):
    """增强的串口面板"""
    
    # 信号定义
    connection_toggle_requested = Signal(bool)
    config_changed = Signal()
    data_send_requested = Signal(str, bool)
    
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建主分割器
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 上半部分：配置和状态
        top_widget = self.create_top_section()
        main_splitter.addWidget(top_widget)
        
        # 下半部分：数据显示
        bottom_widget = self.create_bottom_section()
        main_splitter.addWidget(bottom_widget)
        
        # 设置分割器比例 - 优化配置区域和数据显示区域的比例
        main_splitter.setSizes([280, 450])
        main_splitter.setStretchFactor(0, 2)  # 配置区域
        main_splitter.setStretchFactor(1, 3)  # 数据显示区域占更多空间
        main_splitter.setChildrenCollapsible(False)
        
        layout.addWidget(main_splitter)
        
    def create_top_section(self) -> QWidget:
        """创建顶部配置和状态区域"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)  # 增加组件间距
        
        # 左侧：串口配置
        config_group = QGroupBox("串口配置")
        config_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #464647;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(10, 12, 10, 10)
        
        # 创建串口配置组件
        self.serial_config_widget = SerialConfigDefinitionPanelWidget(parent_main_window=self.main_window)
        config_layout.addWidget(self.serial_config_widget)
        
        # 右侧：状态监控
        status_group = QGroupBox("状态监控")
        status_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #464647;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(10, 12, 10, 10)
        
        # 创建状态监控组件
        self.status_widget = SerialStatusWidget()
        status_layout.addWidget(self.status_widget)
        
        # 添加到布局
        layout.addWidget(config_group, 1)
        layout.addWidget(status_group, 1)
        
        return widget
        
    def create_bottom_section(self) -> QWidget:
        """创建底部数据显示区域"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        # 数据显示组
        data_group = QGroupBox("数据监控")
        data_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #464647;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        
        data_layout = QVBoxLayout(data_group)
        data_layout.setContentsMargins(10, 12, 10, 10)
        
        # 创建数据格式化组件
        self.data_format_widget = DataFormatWidget()
        data_layout.addWidget(self.data_format_widget)
        
        # 控制按钮栏
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 4, 0, 0)
        
        # 清除数据按钮
        clear_data_btn = QPushButton("清除数据")
        clear_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        clear_data_btn.clicked.connect(self.data_format_widget.clear_all_data)
        
        # 导出数据按钮
        export_data_btn = QPushButton("导出数据")
        export_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        export_data_btn.clicked.connect(self.export_data)
        
        # 重置统计按钮
        reset_stats_btn = QPushButton("重置统计")
        reset_stats_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        reset_stats_btn.clicked.connect(self.status_widget.clear_statistics)
        
        button_layout.addWidget(clear_data_btn)
        button_layout.addWidget(export_data_btn)
        button_layout.addWidget(reset_stats_btn)
        button_layout.addStretch()
        
        data_layout.addWidget(button_frame)
        layout.addWidget(data_group)
        
        return widget
        
    def setup_connections(self):
        """设置信号连接"""
        # 串口配置信号
        if hasattr(self.serial_config_widget, 'connection_toggle_requested'):
            self.serial_config_widget.connection_toggle_requested.connect(
                self.connection_toggle_requested.emit
            )
        if hasattr(self.serial_config_widget, 'config_changed'):
            self.serial_config_widget.config_changed.connect(
                self.config_changed.emit
            )
            
        # 数据发送信号
        if hasattr(self.data_format_widget, 'data_sent'):
            self.data_format_widget.data_sent.connect(
                self.data_send_requested.emit
            )
            
    # 公共接口方法
    def get_serial_config(self) -> Optional[SerialPortConfig]:
        """获取串口配置"""
        if hasattr(self.serial_config_widget, 'get_current_serial_config'):
            return self.serial_config_widget.get_current_serial_config()
        return None
        
    def get_frame_config(self) -> Optional[FrameConfig]:
        """获取帧配置"""
        if hasattr(self.serial_config_widget, 'get_current_frame_config'):
            return self.serial_config_widget.get_current_frame_config()
        return None
        
    def get_checksum_mode(self) -> Optional[ChecksumMode]:
        """获取校验模式"""
        if hasattr(self.serial_config_widget, 'get_current_checksum_mode'):
            return self.serial_config_widget.get_current_checksum_mode()
        return None
        
    def update_port_list(self, ports: list, current_port: str = None):
        """更新端口列表"""
        if hasattr(self.serial_config_widget, 'update_port_combo_display'):
            self.serial_config_widget.update_port_combo_display(ports, current_port)
            
    def set_connection_status(self, connected: bool, port: str = "-", baudrate: str = "-", baud_int: int = 0):
        """设置连接状态"""
        # 更新配置面板状态
        if hasattr(self.serial_config_widget, 'set_connection_status_display'):
            self.serial_config_widget.set_connection_status_display(connected)
            
        # 更新状态监控
        self.status_widget.set_connection_status(connected, port, baudrate, baud_int)
        
    @Slot(bytes, str, str)
    def on_data_received(self, data: bytes, direction: str = "RX", timestamp: str = ""):
        """处理接收到的数据"""
        # 更新数据显示
        self.data_format_widget.append_data(data, direction, timestamp)
        
        # 更新统计
        if direction == "RX":
            self.status_widget.update_rx_statistics(len(data))
        else:
            self.status_widget.update_tx_statistics(len(data))
            
    @Slot(str, dict)
    def on_protocol_parsed(self, func_id: str, parsed_data: dict):
        """处理协议解析结果"""
        self.data_format_widget.append_protocol_data(func_id, parsed_data)
        
    @Slot(str)
    def on_checksum_error(self, error_message: str):
        """处理校验错误"""
        self.status_widget.update_checksum_error()
        
    @Slot(str)
    def on_parse_error(self, error_message: str):
        """处理解析错误"""
        self.status_widget.update_parse_error()
        
    @Slot(float)
    def on_data_rate_updated(self, rate_bps: float):
        """更新数据速率"""
        self.status_widget.update_data_rate(rate_bps)
        
    @Slot()
    def export_data(self):
        """导出数据"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import json
        from datetime import datetime
        
        # 选择保存文件
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出数据",
            f"serial_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            # 准备导出数据
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'statistics': self.status_widget.statistics,
                'raw_data': [],
                'byte_distribution': self.data_format_widget.byte_distribution
            }
            
            # 导出原始数据（转换为可序列化格式）
            for entry in self.data_format_widget.raw_data_list:
                export_entry = {
                    'data': list(entry['data']),  # 转换bytes为list
                    'direction': entry['direction'],
                    'timestamp': entry['timestamp'],
                    'length': entry['length']
                }
                export_data['raw_data'].append(export_entry)
                
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            QMessageBox.information(self, "导出成功", f"数据已成功导出到:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出数据时发生错误:\n{str(e)}")
            
    def update_ui_from_configs(self, serial_cfg: SerialPortConfig, frame_cfg: FrameConfig, checksum_mode: ChecksumMode):
        """从配置更新UI"""
        if hasattr(self.serial_config_widget, 'update_ui_from_main_configs'):
            self.serial_config_widget.update_ui_from_main_configs(serial_cfg, frame_cfg, checksum_mode)