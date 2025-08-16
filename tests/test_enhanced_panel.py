#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重构后的基础收发面板

功能测试：
1. 基础UI组件创建
2. 快捷发送功能
3. 快捷发送编辑对话框
4. 配置保存和加载
5. 数据发送和接收
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QTextEdit
from PySide6.QtCore import QTimer, Signal

from ui.enhanced_basic_comm_panel import EnhancedBasicCommPanel


class MockSerialDebugger:
    """模拟主窗口类"""
    def __init__(self):
        self.serial_connected = False
        self.current_port = None
    
    def is_serial_connected(self):
        return self.serial_connected
    
    def get_current_port(self):
        return self.current_port


class TestMainWindow(QMainWindow):
    """测试主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("重构后基础收发面板测试")
        self.setGeometry(100, 100, 1000, 700)
        
        # 创建模拟的主窗口引用
        self.mock_main = MockSerialDebugger()
        
        self._init_ui()
        self._init_connections()
        self._start_test_timer()
    
    def _init_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 创建重构后的基础收发面板
        self.comm_panel = EnhancedBasicCommPanel(self.mock_main)
        layout.addWidget(self.comm_panel)
        
        # 添加测试控制按钮
        test_layout = QVBoxLayout()
        
        # 连接/断开按钮
        self.connect_btn = QPushButton("模拟连接串口")
        self.connect_btn.clicked.connect(self._toggle_connection)
        test_layout.addWidget(self.connect_btn)
        
        # 模拟接收数据按钮
        self.receive_btn = QPushButton("模拟接收数据")
        self.receive_btn.clicked.connect(self._simulate_receive_data)
        test_layout.addWidget(self.receive_btn)
        
        # 测试日志
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setPlaceholderText("测试日志将显示在这里...")
        test_layout.addWidget(self.log_text)
        
        layout.addLayout(test_layout)
    
    def _init_connections(self):
        """初始化信号连接"""
        # 连接面板信号
        self.comm_panel.send_data_requested.connect(self._on_data_send_requested)
        self.comm_panel.stats_updated.connect(self._on_stats_updated)
    
    def _start_test_timer(self):
        """启动测试定时器"""
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self._periodic_test)
        self.test_timer.start(5000)  # 每5秒执行一次测试
        
        self._log("测试定时器已启动，每5秒会模拟接收数据")
    
    def _toggle_connection(self):
        """切换连接状态"""
        self.mock_main.serial_connected = not self.mock_main.serial_connected
        
        if self.mock_main.serial_connected:
            self.mock_main.current_port = "COM3"
            self.connect_btn.setText("断开串口")
            self.comm_panel.set_send_enabled(True)
            self._log("✓ 模拟串口已连接 (COM3)")
        else:
            self.mock_main.current_port = None
            self.connect_btn.setText("模拟连接串口")
            self.comm_panel.set_send_enabled(False)
            self._log("✗ 模拟串口已断开")
    
    def _simulate_receive_data(self):
        """模拟接收数据"""
        import random
        
        # 随机选择数据类型
        data_types = [
            (b"\xAA\xBB\xCC\xDD", "心跳包响应"),
            (b"\x01\x03\x02\x00\x01", "状态查询响应"),
            (b"Hello from device!", "设备文本消息"),
            (b"\xFF\xFE\xFD\xFC", "复位确认"),
            ("温度: 25.6°C\n".encode('utf-8'), "传感器数据")
        ]
        
        data, description = random.choice(data_types)
        
        # 模拟接收数据
        self.comm_panel.append_receive_text(data)
        self._log(f"📥 模拟接收: {description} ({len(data)} 字节)")
    
    def _periodic_test(self):
        """定期测试"""
        if self.mock_main.serial_connected:
            self._simulate_receive_data()
    
    def _on_data_send_requested(self, data: str, is_hex: bool):
        """数据发送请求处理"""
        data_type = "Hex" if is_hex else "文本"
        byte_count = self._calculate_byte_count(data, is_hex)
        
        self._log(f"📤 发送请求: {data_type}数据 '{data}' ({byte_count} 字节)")
        
        # 模拟发送成功后的响应
        if self.mock_main.serial_connected:
            QTimer.singleShot(500, lambda: self._simulate_send_response(data, is_hex))
    
    def _simulate_send_response(self, original_data: str, was_hex: bool):
        """模拟发送后的响应"""
        # 根据发送的数据模拟相应的响应
        if was_hex:
            if "AA BB CC DD" in original_data.upper():
                response = b"\xAA\xBB\xCC\xDD\x00"  # 心跳响应
                self._log("📥 自动响应: 心跳包确认")
            elif "01 03" in original_data.upper():
                response = b"\x01\x03\x02\x12\x34"  # 查询响应
                self._log("📥 自动响应: 状态查询结果")
            else:
                response = b"\x06"  # ACK
                self._log("📥 自动响应: ACK确认")
        else:
            if "Hello" in original_data:
                response = b"Hello from device!"
                self._log("📥 自动响应: 设备问候")
            else:
                response = b"OK\r\n"
                self._log("📥 自动响应: OK确认")
        
        self.comm_panel.append_receive_text(response)
    
    def _calculate_byte_count(self, data: str, is_hex: bool) -> int:
        """计算字节数"""
        if is_hex:
            import re
            hex_text = re.sub(r'[\s\-:,]', '', data.upper())
            if len(hex_text) % 2 == 0 and all(c in '0123456789ABCDEF' for c in hex_text):
                return len(hex_text) // 2
            return 0
        else:
            return len(data.encode('utf-8'))
    
    def _on_stats_updated(self, stats):
        """统计信息更新"""
        # 这里可以处理统计信息更新
        pass
    
    def _log(self, message: str):
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        print(log_message)  # 同时输出到控制台
    
    def closeEvent(self, event):
        """关闭事件"""
        self._log("测试窗口关闭")
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("Enhanced Basic Comm Panel Test")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("YJ_Studio")
    
    # 创建并显示测试窗口
    window = TestMainWindow()
    window.show()
    
    print("重构后基础收发面板测试启动")
    print("功能测试项目:")
    print("1. 点击'模拟连接串口'按钮连接/断开")
    print("2. 连接后可以测试发送功能")
    print("3. 点击'模拟接收数据'按钮模拟数据接收")
    print("4. 测试快捷发送按钮功能")
    print("5. 点击'编辑'按钮测试快捷发送编辑对话框")
    print("6. 测试各种显示选项和发送格式")
    print("7. 测试终端模式和自动发送功能")
    print("\n注意: 每5秒会自动模拟接收数据")
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()