# -*- coding: utf-8 -*-
"""
串口状态指示器组件
提供实时的串口连接状态、数据流量、错误统计等信息显示
"""

import time
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QProgressBar, QGroupBox, QGridLayout
)


class SerialStatusWidget(QWidget):
    """串口状态指示器组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_timer()
        self.reset_statistics()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 连接状态组
        self.create_connection_status_group(layout)
        
        # 数据统计组
        self.create_data_statistics_group(layout)
        
        # 错误统计组
        self.create_error_statistics_group(layout)
        
        layout.addStretch()
        
    def create_connection_status_group(self, parent_layout):
        """创建连接状态组"""
        group = QGroupBox("连接状态")
        group.setStyleSheet("""
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
        
        layout = QGridLayout(group)
        layout.setSpacing(4)
        
        # 连接状态指示器
        self.connection_indicator = QLabel("●")
        self.connection_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.connection_indicator.setFixedSize(20, 20)
        
        self.connection_label = QLabel("未连接")
        self.connection_label.setStyleSheet("color: #cccccc;")
        
        layout.addWidget(QLabel("状态:"), 0, 0)
        layout.addWidget(self.connection_indicator, 0, 1)
        layout.addWidget(self.connection_label, 0, 2)
        
        # 端口信息
        self.port_label = QLabel("-")
        self.port_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(QLabel("端口:"), 1, 0)
        layout.addWidget(self.port_label, 1, 1, 1, 2)
        
        # 波特率信息
        self.baudrate_label = QLabel("-")
        self.baudrate_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(QLabel("波特率:"), 2, 0)
        layout.addWidget(self.baudrate_label, 2, 1, 1, 2)
        
        parent_layout.addWidget(group)
        
        # 设置初始连接状态（在所有UI元素创建完成后）
        self.set_connection_status(False)
        
    def create_data_statistics_group(self, parent_layout):
        """创建数据统计组"""
        group = QGroupBox("数据统计")
        group.setStyleSheet("""
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
        
        layout = QGridLayout(group)
        layout.setSpacing(4)
        
        # 接收统计
        self.rx_count_label = QLabel("0")
        self.rx_count_label.setStyleSheet("color: #4ec9b0;")
        layout.addWidget(QLabel("接收帧数:"), 0, 0)
        layout.addWidget(self.rx_count_label, 0, 1)
        
        self.rx_bytes_label = QLabel("0 B")
        self.rx_bytes_label.setStyleSheet("color: #4ec9b0;")
        layout.addWidget(QLabel("接收字节:"), 1, 0)
        layout.addWidget(self.rx_bytes_label, 1, 1)
        
        # 发送统计
        self.tx_count_label = QLabel("0")
        self.tx_count_label.setStyleSheet("color: #569cd6;")
        layout.addWidget(QLabel("发送帧数:"), 2, 0)
        layout.addWidget(self.tx_count_label, 2, 1)
        
        self.tx_bytes_label = QLabel("0 B")
        self.tx_bytes_label.setStyleSheet("color: #569cd6;")
        layout.addWidget(QLabel("发送字节:"), 3, 0)
        layout.addWidget(self.tx_bytes_label, 3, 1)
        
        # 数据速率
        self.data_rate_label = QLabel("0 bps")
        self.data_rate_label.setStyleSheet("color: #dcdcaa;")
        layout.addWidget(QLabel("数据速率:"), 4, 0)
        layout.addWidget(self.data_rate_label, 4, 1)
        
        parent_layout.addWidget(group)
        
    def create_error_statistics_group(self, parent_layout):
        """创建错误统计组"""
        group = QGroupBox("错误统计")
        group.setStyleSheet("""
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
        
        layout = QGridLayout(group)
        layout.setSpacing(4)
        
        # 校验错误
        self.checksum_error_label = QLabel("0")
        self.checksum_error_label.setStyleSheet("color: #f44747;")
        layout.addWidget(QLabel("校验错误:"), 0, 0)
        layout.addWidget(self.checksum_error_label, 0, 1)
        
        # 解析错误
        self.parse_error_label = QLabel("0")
        self.parse_error_label.setStyleSheet("color: #f44747;")
        layout.addWidget(QLabel("解析错误:"), 1, 0)
        layout.addWidget(self.parse_error_label, 1, 1)
        
        # 错误率
        self.error_rate_label = QLabel("0.0%")
        self.error_rate_label.setStyleSheet("color: #f44747;")
        layout.addWidget(QLabel("错误率:"), 2, 0)
        layout.addWidget(self.error_rate_label, 2, 1)
        
        parent_layout.addWidget(group)
        
    def setup_timer(self):
        """设置更新定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # 每秒更新一次
        
    def reset_statistics(self):
        """重置统计数据"""
        self.statistics = {
            'rx_count': 0,
            'rx_bytes': 0,
            'tx_count': 0,
            'tx_bytes': 0,
            'checksum_errors': 0,
            'parse_errors': 0,
            'last_update_time': time.time(),
            'data_rate_bps': 0
        }
        
    @Slot(bool, str, str, int)
    def set_connection_status(self, connected: bool, port: str = "-", baudrate: str = "-", baud_int: int = 0):
        """设置连接状态"""
        if connected:
            self.connection_indicator.setStyleSheet("""
                QLabel {
                    color: #4ec9b0;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            self.connection_label.setText("已连接")
            self.port_label.setText(port)
            self.baudrate_label.setText(f"{baudrate} bps" if baudrate != "-" else f"{baud_int} bps")
        else:
            self.connection_indicator.setStyleSheet("""
                QLabel {
                    color: #f44747;
                    font-size: 16px;
                    font-weight: bold;
                }
            """)
            self.connection_label.setText("未连接")
            self.port_label.setText("-")
            self.baudrate_label.setText("-")
            
    @Slot(int)
    def update_rx_statistics(self, byte_count: int):
        """更新接收统计"""
        self.statistics['rx_count'] += 1
        self.statistics['rx_bytes'] += byte_count
        
    @Slot(int)
    def update_tx_statistics(self, byte_count: int):
        """更新发送统计"""
        self.statistics['tx_count'] += 1
        self.statistics['tx_bytes'] += byte_count
        
    @Slot()
    def update_checksum_error(self):
        """更新校验错误计数"""
        self.statistics['checksum_errors'] += 1
        
    @Slot()
    def update_parse_error(self):
        """更新解析错误计数"""
        self.statistics['parse_errors'] += 1
        
    @Slot(float)
    def update_data_rate(self, rate_bps: float):
        """更新数据速率"""
        self.statistics['data_rate_bps'] = rate_bps
        
    def format_bytes(self, byte_count: int) -> str:
        """格式化字节数显示"""
        if byte_count < 1024:
            return f"{byte_count} B"
        elif byte_count < 1024 * 1024:
            return f"{byte_count / 1024:.1f} KB"
        else:
            return f"{byte_count / (1024 * 1024):.1f} MB"
            
    def format_rate(self, rate_bps: float) -> str:
        """格式化速率显示"""
        if rate_bps < 1000:
            return f"{rate_bps:.0f} bps"
        elif rate_bps < 1000000:
            return f"{rate_bps / 1000:.1f} Kbps"
        else:
            return f"{rate_bps / 1000000:.1f} Mbps"
            
    @Slot()
    def update_display(self):
        """更新显示内容"""
        # 更新统计显示
        self.rx_count_label.setText(str(self.statistics['rx_count']))
        self.rx_bytes_label.setText(self.format_bytes(self.statistics['rx_bytes']))
        
        self.tx_count_label.setText(str(self.statistics['tx_count']))
        self.tx_bytes_label.setText(self.format_bytes(self.statistics['tx_bytes']))
        
        self.data_rate_label.setText(self.format_rate(self.statistics['data_rate_bps']))
        
        # 更新错误统计
        self.checksum_error_label.setText(str(self.statistics['checksum_errors']))
        self.parse_error_label.setText(str(self.statistics['parse_errors']))
        
        # 计算错误率
        total_frames = self.statistics['rx_count'] + self.statistics['tx_count']
        total_errors = self.statistics['checksum_errors'] + self.statistics['parse_errors']
        
        if total_frames > 0:
            error_rate = (total_errors / total_frames) * 100
            self.error_rate_label.setText(f"{error_rate:.1f}%")
        else:
            self.error_rate_label.setText("0.0%")
            
    @Slot()
    def clear_statistics(self):
        """清除统计数据"""
        self.reset_statistics()
        self.update_display()