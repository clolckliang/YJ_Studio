#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLineEdit, QComboBox, QGroupBox, QLabel, QProgressBar,
    QCheckBox, QRadioButton, QSlider, QSpinBox, QTextEdit
)
from PySide6.QtCore import Qt
from ui.theme_manager import ThemeManager

class NeumorphismTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("拟物化主题测试")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建主题管理器
        self.theme_manager = ThemeManager(QApplication.instance())
        
        self.setup_ui()
        
        # 应用拟物化主题
        self.apply_neumorphism_theme()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("拟物化主题演示")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        layout.addWidget(title)
        
        # 按钮组
        button_group = QGroupBox("按钮控件")
        button_layout = QHBoxLayout(button_group)
        
        btn1 = QPushButton("普通按钮")
        btn2 = QPushButton("悬停按钮")
        btn3 = QPushButton("按下按钮")
        
        button_layout.addWidget(btn1)
        button_layout.addWidget(btn2)
        button_layout.addWidget(btn3)
        layout.addWidget(button_group)
        
        # 输入控件组
        input_group = QGroupBox("输入控件")
        input_layout = QVBoxLayout(input_group)
        
        line_edit = QLineEdit("文本输入框")
        combo_box = QComboBox()
        combo_box.addItems(["选项1", "选项2", "选项3"])
        
        input_layout.addWidget(line_edit)
        input_layout.addWidget(combo_box)
        layout.addWidget(input_group)
        
        # 选择控件组
        choice_group = QGroupBox("选择控件")
        choice_layout = QHBoxLayout(choice_group)
        
        checkbox = QCheckBox("复选框")
        radio1 = QRadioButton("单选按钮1")
        radio2 = QRadioButton("单选按钮2")
        
        choice_layout.addWidget(checkbox)
        choice_layout.addWidget(radio1)
        choice_layout.addWidget(radio2)
        layout.addWidget(choice_group)
        
        # 数值控件组
        value_group = QGroupBox("数值控件")
        value_layout = QVBoxLayout(value_group)
        
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(50)
        
        spinbox = QSpinBox()
        spinbox.setRange(0, 100)
        spinbox.setValue(25)
        
        progress = QProgressBar()
        progress.setValue(75)
        
        value_layout.addWidget(QLabel("滑块控件:"))
        value_layout.addWidget(slider)
        value_layout.addWidget(QLabel("数字输入框:"))
        value_layout.addWidget(spinbox)
        value_layout.addWidget(QLabel("进度条:"))
        value_layout.addWidget(progress)
        layout.addWidget(value_group)
        
        # 文本区域
        text_group = QGroupBox("文本区域")
        text_layout = QVBoxLayout(text_group)
        
        text_edit = QTextEdit()
        text_edit.setPlainText("这是一个多行文本编辑器\n展示拟物化风格的效果")
        text_edit.setMaximumHeight(100)
        
        text_layout.addWidget(text_edit)
        layout.addWidget(text_group)
        
        # 主题切换按钮
        theme_layout = QHBoxLayout()
        
        light_btn = QPushButton("浅色主题")
        dark_btn = QPushButton("深色主题")
        neumorphism_btn = QPushButton("拟物化主题")
        
        light_btn.clicked.connect(lambda: self.apply_theme("light"))
        dark_btn.clicked.connect(lambda: self.apply_theme("dark"))
        neumorphism_btn.clicked.connect(lambda: self.apply_theme("neumorphism"))
        
        theme_layout.addWidget(light_btn)
        theme_layout.addWidget(dark_btn)
        theme_layout.addWidget(neumorphism_btn)
        
        layout.addLayout(theme_layout)
    
    def apply_theme(self, theme_name):
        """应用指定主题"""
        try:
            if theme_name in self.theme_manager.themes:
                style = self.theme_manager.themes[theme_name]
                QApplication.instance().setStyleSheet(style)
                print(f"已应用 {theme_name} 主题")
            else:
                print(f"主题 {theme_name} 不存在")
        except Exception as e:
            print(f"应用主题时出错: {e}")
    
    def apply_neumorphism_theme(self):
        """应用拟物化主题"""
        self.apply_theme("neumorphism")

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("拟物化主题测试")
    app.setApplicationVersion("1.0")
    
    window = NeumorphismTestWindow()
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())