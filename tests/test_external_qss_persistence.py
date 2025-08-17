#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import tempfile

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLineEdit, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QSettings
from ui.theme_manager import ThemeManager

class ExternalQSSTestWindow(QMainWindow):
    """外部QSS持久化测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.app = QApplication.instance()
        self.theme_manager = ThemeManager(self.app)
        
        self.setWindowTitle("外部QSS持久化测试")
        self.setGeometry(100, 100, 600, 400)
        
        self.setup_ui()
        
        # 测试恢复上次主题
        self.theme_manager.restore_last_theme()
        
    def setup_ui(self):
        """设置UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title_label = QLabel("外部QSS文件持久化测试")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 当前主题信息
        self.current_theme_label = QLabel("当前主题: 未知")
        layout.addWidget(self.current_theme_label)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 加载外部QSS按钮
        load_qss_btn = QPushButton("加载外部QSS文件")
        load_qss_btn.clicked.connect(self.load_external_qss)
        button_layout.addWidget(load_qss_btn)
        
        # 切换到内置主题按钮
        switch_builtin_btn = QPushButton("切换到深色主题")
        switch_builtin_btn.clicked.connect(lambda: self.theme_manager.apply_theme("dark"))
        button_layout.addWidget(switch_builtin_btn)
        
        # 重启测试按钮
        restart_test_btn = QPushButton("模拟重启(恢复上次主题)")
        restart_test_btn.clicked.connect(self.simulate_restart)
        button_layout.addWidget(restart_test_btn)
        
        layout.addLayout(button_layout)
        
        # 测试控件区域
        test_group = QWidget()
        test_layout = QVBoxLayout(test_group)
        
        test_layout.addWidget(QLabel("测试控件:"))
        test_layout.addWidget(QLineEdit("这是一个输入框"))
        
        test_btn = QPushButton("测试按钮")
        test_layout.addWidget(test_btn)
        
        layout.addWidget(test_group)
        
        # 说明文本
        info_label = QLabel(
            "测试步骤:\n"
            "1. 点击'加载外部QSS文件'选择一个QSS文件\n"
            "2. 观察界面样式变化\n"
            "3. 点击'模拟重启'测试是否能恢复外部QSS主题\n"
            "4. 重新运行此程序，检查是否自动恢复了外部QSS主题"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("margin: 10px; padding: 10px; border: 1px solid gray;")
        layout.addWidget(info_label)
        
        # 连接主题变化信号
        self.theme_manager.theme_changed.connect(self.update_theme_info)
        
        # 初始化主题信息
        self.update_theme_info()
        
    def load_external_qss(self):
        """加载外部QSS文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择QSS文件", "", "QSS Files (*.qss);;All Files (*)"
        )
        
        if file_path:
            try:
                self.theme_manager.apply_external_qss(file_path)
                QMessageBox.information(self, "成功", f"已加载外部QSS文件:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载QSS文件失败:\n{str(e)}")
    
    def simulate_restart(self):
        """模拟重启，测试主题恢复"""
        # 清除当前样式
        self.app.setStyleSheet("")
        
        # 重新创建ThemeManager并恢复主题
        self.theme_manager = ThemeManager(self.app)
        self.theme_manager.theme_changed.connect(self.update_theme_info)
        self.theme_manager.restore_last_theme()
        
        QMessageBox.information(self, "模拟重启", "已模拟重启并尝试恢复上次使用的主题")
    
    def update_theme_info(self, theme_name=None):
        """更新主题信息显示"""
        current_info = self.theme_manager.current_theme_info
        theme_type = current_info.get("type", "未知")
        theme_name = current_info.get("name", "未知")
        theme_path = current_info.get("path", "")
        
        info_text = f"当前主题: {theme_name} (类型: {theme_type})"
        if theme_path:
            info_text += f"\n路径: {theme_path}"
            
        self.current_theme_label.setText(info_text)

def main():
    app = QApplication(sys.argv)
    
    # 创建一个临时的测试QSS文件
    test_qss_content = """
    QWidget {
        background-color: #2d3748;
        color: #e2e8f0;
        font-family: "Consolas", "Monaco", monospace;
    }
    
    QPushButton {
        background-color: #4a5568;
        border: 2px solid #718096;
        border-radius: 8px;
        padding: 8px 16px;
        color: #e2e8f0;
        font-weight: bold;
    }
    
    QPushButton:hover {
        background-color: #2b6cb0;
        border-color: #3182ce;
    }
    
    QPushButton:pressed {
        background-color: #2c5282;
    }
    
    QLineEdit {
        background-color: #1a202c;
        border: 2px solid #4a5568;
        border-radius: 6px;
        padding: 6px;
        color: #e2e8f0;
    }
    
    QLabel {
        color: #e2e8f0;
    }
    """
    
    # 创建测试QSS文件
    temp_dir = tempfile.gettempdir()
    test_qss_path = os.path.join(temp_dir, "test_external_theme.qss")
    
    try:
        with open(test_qss_path, 'w', encoding='utf-8') as f:
            f.write(test_qss_content)
        print(f"已创建测试QSS文件: {test_qss_path}")
    except Exception as e:
        print(f"创建测试QSS文件失败: {e}")
    
    window = ExternalQSSTestWindow()
    window.show()
    
    print("\n=== 外部QSS持久化测试说明 ===")
    print(f"1. 可以使用测试QSS文件: {test_qss_path}")
    print("2. 或者选择项目中的其他QSS文件进行测试")
    print("3. 加载外部QSS后，重新运行此程序检查是否自动恢复")
    print("4. 检查QSettings中是否正确保存了外部QSS路径")
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())