# -*- coding: utf-8 -*-
"""
数据格式化显示组件
支持多种数据格式的实时显示、转换和分析
"""

import re
import struct
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QComboBox, QPushButton, QCheckBox, QSpinBox, QGroupBox,
    QTabWidget, QSplitter, QFrame, QGridLayout
)


class DataFormatWidget(QWidget):
    """数据格式化显示组件"""
    
    data_sent = Signal(str, bool)  # data, is_hex
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #464647;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #3e3e42;
            }
        """)
        
        # 原始数据标签页
        self.create_raw_data_tab()
        
        # 格式化数据标签页
        self.create_formatted_data_tab()
        
        # 协议解析标签页
        self.create_protocol_tab()
        
        # 数据分析标签页
        self.create_analysis_tab()
        
        layout.addWidget(self.tab_widget)
        
    def create_raw_data_tab(self):
        """创建原始数据标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 控制面板
        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # 显示格式选择
        format_label = QLabel("显示格式:")
        format_label.setStyleSheet("color: #cccccc;")
        self.raw_format_combo = QComboBox()
        self.raw_format_combo.addItems(["HEX", "ASCII", "UTF-8", "二进制", "十进制"])
        self.raw_format_combo.setCurrentText("HEX")
        
        # 时间戳选项
        self.timestamp_checkbox = QCheckBox("显示时间戳")
        self.timestamp_checkbox.setChecked(True)
        self.timestamp_checkbox.setStyleSheet("color: #cccccc;")
        
        # 自动滚动选项
        self.auto_scroll_checkbox = QCheckBox("自动滚动")
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.setStyleSheet("color: #cccccc;")
        
        # 清除按钮
        clear_btn = QPushButton("清除")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        clear_btn.clicked.connect(self.clear_raw_data)
        
        control_layout.addWidget(format_label)
        control_layout.addWidget(self.raw_format_combo)
        control_layout.addWidget(self.timestamp_checkbox)
        control_layout.addWidget(self.auto_scroll_checkbox)
        control_layout.addStretch()
        control_layout.addWidget(clear_btn)
        
        layout.addWidget(control_frame)
        
        # 数据显示区域
        self.raw_data_display = QTextEdit()
        self.raw_data_display.setReadOnly(True)
        self.raw_data_display.setFont(QFont("Consolas", 9))
        self.raw_data_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #464647;
                selection-background-color: #264f78;
            }
        """)
        
        layout.addWidget(self.raw_data_display)
        
        self.tab_widget.addTab(tab, "原始数据")
        
    def create_formatted_data_tab(self):
        """创建格式化数据标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 格式化选项
        options_frame = QFrame()
        options_layout = QGridLayout(options_frame)
        options_layout.setContentsMargins(0, 0, 0, 0)
        
        # 字节分组
        group_label = QLabel("字节分组:")
        group_label.setStyleSheet("color: #cccccc;")
        self.byte_group_spin = QSpinBox()
        self.byte_group_spin.setRange(1, 16)
        self.byte_group_spin.setValue(4)
        
        # 行宽度
        width_label = QLabel("行宽度:")
        width_label.setStyleSheet("color: #cccccc;")
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(8, 64)
        self.line_width_spin.setValue(16)
        
        # 大小写
        case_label = QLabel("大小写:")
        case_label.setStyleSheet("color: #cccccc;")
        self.case_combo = QComboBox()
        self.case_combo.addItems(["大写", "小写"])
        
        # 分隔符
        separator_label = QLabel("分隔符:")
        separator_label.setStyleSheet("color: #cccccc;")
        self.separator_combo = QComboBox()
        self.separator_combo.addItems(["空格", "-", ":", "无"])
        
        options_layout.addWidget(group_label, 0, 0)
        options_layout.addWidget(self.byte_group_spin, 0, 1)
        options_layout.addWidget(width_label, 0, 2)
        options_layout.addWidget(self.line_width_spin, 0, 3)
        options_layout.addWidget(case_label, 1, 0)
        options_layout.addWidget(self.case_combo, 1, 1)
        options_layout.addWidget(separator_label, 1, 2)
        options_layout.addWidget(self.separator_combo, 1, 3)
        
        layout.addWidget(options_frame)
        
        # 格式化显示区域
        self.formatted_display = QTextEdit()
        self.formatted_display.setReadOnly(True)
        self.formatted_display.setFont(QFont("Consolas", 9))
        self.formatted_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #464647;
                selection-background-color: #264f78;
            }
        """)
        
        layout.addWidget(self.formatted_display)
        
        self.tab_widget.addTab(tab, "格式化")
        
    def create_protocol_tab(self):
        """创建协议解析标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 协议字段显示
        self.protocol_display = QTextEdit()
        self.protocol_display.setReadOnly(True)
        self.protocol_display.setFont(QFont("Consolas", 9))
        self.protocol_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #464647;
                selection-background-color: #264f78;
            }
        """)
        
        layout.addWidget(self.protocol_display)
        
        self.tab_widget.addTab(tab, "协议解析")
        
    def create_analysis_tab(self):
        """创建数据分析标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 统计信息
        stats_group = QGroupBox("统计信息")
        stats_group.setStyleSheet("""
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
        
        stats_layout = QGridLayout(stats_group)
        
        # 字节统计
        self.total_bytes_label = QLabel("0")
        self.total_bytes_label.setStyleSheet("color: #4ec9b0;")
        stats_layout.addWidget(QLabel("总字节数:"), 0, 0)
        stats_layout.addWidget(self.total_bytes_label, 0, 1)
        
        # 帧统计
        self.total_frames_label = QLabel("0")
        self.total_frames_label.setStyleSheet("color: #569cd6;")
        stats_layout.addWidget(QLabel("总帧数:"), 1, 0)
        stats_layout.addWidget(self.total_frames_label, 1, 1)
        
        # 平均帧长
        self.avg_frame_length_label = QLabel("0")
        self.avg_frame_length_label.setStyleSheet("color: #dcdcaa;")
        stats_layout.addWidget(QLabel("平均帧长:"), 2, 0)
        stats_layout.addWidget(self.avg_frame_length_label, 2, 1)
        
        layout.addWidget(stats_group)
        
        # 字节分布图
        distribution_group = QGroupBox("字节分布")
        distribution_group.setStyleSheet("""
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
        
        distribution_layout = QVBoxLayout(distribution_group)
        
        self.distribution_display = QTextEdit()
        self.distribution_display.setReadOnly(True)
        self.distribution_display.setMaximumHeight(150)
        self.distribution_display.setFont(QFont("Consolas", 8))
        self.distribution_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid #464647;
            }
        """)
        
        distribution_layout.addWidget(self.distribution_display)
        layout.addWidget(distribution_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "数据分析")
        
    def setup_connections(self):
        """设置信号连接"""
        self.raw_format_combo.currentTextChanged.connect(self.update_raw_display)
        self.byte_group_spin.valueChanged.connect(self.update_formatted_display)
        self.line_width_spin.valueChanged.connect(self.update_formatted_display)
        self.case_combo.currentTextChanged.connect(self.update_formatted_display)
        self.separator_combo.currentTextChanged.connect(self.update_formatted_display)
        
        # 初始化数据存储
        self.raw_data_list = []
        self.byte_distribution = [0] * 256
        self.total_bytes = 0
        self.total_frames = 0
        
    @Slot(bytes, str, str)
    def append_data(self, data: bytes, direction: str = "RX", timestamp: str = ""):
        """添加新数据"""
        if not data:
            return
            
        # 存储原始数据
        data_entry = {
            'data': data,
            'direction': direction,
            'timestamp': timestamp,
            'length': len(data)
        }
        self.raw_data_list.append(data_entry)
        
        # 更新统计
        self.total_bytes += len(data)
        self.total_frames += 1
        
        # 更新字节分布
        for byte_val in data:
            self.byte_distribution[byte_val] += 1
            
        # 更新显示
        self.update_raw_display()
        self.update_formatted_display()
        self.update_analysis_display()
        
    @Slot(str, dict)
    def append_protocol_data(self, func_id: str, parsed_data: dict):
        """添加协议解析数据"""
        protocol_text = f"功能ID: {func_id}\n"
        for key, value in parsed_data.items():
            protocol_text += f"{key}: {value}\n"
        protocol_text += "-" * 40 + "\n"
        
        self.protocol_display.append(protocol_text)
        
        if self.auto_scroll_checkbox.isChecked():
            cursor = self.protocol_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.protocol_display.setTextCursor(cursor)
            
    def update_raw_display(self):
        """更新原始数据显示"""
        if not self.raw_data_list:
            return
            
        format_type = self.raw_format_combo.currentText()
        show_timestamp = self.timestamp_checkbox.isChecked()
        
        # 只显示最后几条数据以提高性能
        recent_data = self.raw_data_list[-100:] if len(self.raw_data_list) > 100 else self.raw_data_list
        
        display_text = ""
        for entry in recent_data:
            line = ""
            
            if show_timestamp and entry['timestamp']:
                line += f"[{entry['timestamp']}] "
                
            direction_color = "#4ec9b0" if entry['direction'] == "RX" else "#569cd6"
            line += f"<span style='color: {direction_color}'>{entry['direction']}</span>: "
            
            # 格式化数据
            formatted_data = self.format_data(entry['data'], format_type)
            line += formatted_data + "\n"
            
            display_text += line
            
        self.raw_data_display.setHtml(display_text)
        
        if self.auto_scroll_checkbox.isChecked():
            cursor = self.raw_data_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.raw_data_display.setTextCursor(cursor)
            
    def update_formatted_display(self):
        """更新格式化显示"""
        if not self.raw_data_list:
            return
            
        # 合并所有数据
        all_data = b''.join([entry['data'] for entry in self.raw_data_list[-10:]])  # 只显示最后10帧
        
        formatted_text = self.format_hex_dump(all_data)
        self.formatted_display.setPlainText(formatted_text)
        
    def update_analysis_display(self):
        """更新分析显示"""
        # 更新统计标签
        self.total_bytes_label.setText(str(self.total_bytes))
        self.total_frames_label.setText(str(self.total_frames))
        
        if self.total_frames > 0:
            avg_length = self.total_bytes / self.total_frames
            self.avg_frame_length_label.setText(f"{avg_length:.1f}")
        else:
            self.avg_frame_length_label.setText("0")
            
        # 更新字节分布
        distribution_text = "字节值分布 (前20个最常见):\n"
        
        # 找出最常见的字节
        byte_counts = [(i, count) for i, count in enumerate(self.byte_distribution) if count > 0]
        byte_counts.sort(key=lambda x: x[1], reverse=True)
        
        for i, (byte_val, count) in enumerate(byte_counts[:20]):
            percentage = (count / self.total_bytes * 100) if self.total_bytes > 0 else 0
            distribution_text += f"0x{byte_val:02X}: {count:6d} ({percentage:5.1f}%)\n"
            
        self.distribution_display.setPlainText(distribution_text)
        
    def format_data(self, data: bytes, format_type: str) -> str:
        """格式化数据显示"""
        if format_type == "HEX":
            return ' '.join(f'{b:02X}' for b in data)
        elif format_type == "ASCII":
            return ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data)
        elif format_type == "UTF-8":
            try:
                return data.decode('utf-8', errors='replace')
            except:
                return str(data)
        elif format_type == "二进制":
            return ' '.join(f'{b:08b}' for b in data)
        elif format_type == "十进制":
            return ' '.join(str(b) for b in data)
        else:
            return str(data)
            
    def format_hex_dump(self, data: bytes) -> str:
        """格式化十六进制转储"""
        if not data:
            return ""
            
        line_width = self.line_width_spin.value()
        byte_group = self.byte_group_spin.value()
        is_upper = self.case_combo.currentText() == "大写"
        separator = self.get_separator()
        
        lines = []
        for i in range(0, len(data), line_width):
            line_data = data[i:i+line_width]
            
            # 地址
            addr = f"{i:08X}: "
            
            # 十六进制数据
            hex_parts = []
            for j in range(0, len(line_data), byte_group):
                group_data = line_data[j:j+byte_group]
                if is_upper:
                    hex_str = separator.join(f'{b:02X}' for b in group_data)
                else:
                    hex_str = separator.join(f'{b:02x}' for b in group_data)
                hex_parts.append(hex_str)
            
            hex_section = '  '.join(hex_parts)
            hex_section = hex_section.ljust(line_width * 3)  # 对齐
            
            # ASCII数据
            ascii_section = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in line_data)
            
            lines.append(f"{addr}{hex_section} |{ascii_section}|")
            
        return '\n'.join(lines)
        
    def get_separator(self) -> str:
        """获取分隔符"""
        separator_map = {
            "空格": " ",
            "-": "-",
            ":": ":",
            "无": ""
        }
        return separator_map.get(self.separator_combo.currentText(), " ")
        
    @Slot()
    def clear_raw_data(self):
        """清除原始数据"""
        self.raw_data_display.clear()
        
    @Slot()
    def clear_all_data(self):
        """清除所有数据"""
        self.raw_data_list.clear()
        self.byte_distribution = [0] * 256
        self.total_bytes = 0
        self.total_frames = 0
        
        self.raw_data_display.clear()
        self.formatted_display.clear()
        self.protocol_display.clear()
        self.distribution_display.clear()
        
        self.update_analysis_display()