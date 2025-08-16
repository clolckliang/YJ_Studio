# -*- coding: utf-8 -*-
"""
VS Code风格的串口调试助手界面布局
专注于串口通信、数据可视化、脚本编辑和调试功能
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QTabWidget, QToolBar, QFrame, QLabel, QPushButton,
    QStackedWidget, QScrollArea, QSizePolicy, QApplication,
    QGroupBox, QListWidget, QListWidgetItem, QComboBox, 
    QCheckBox, QSpinBox
)

from ui.enhanced_script_editor import EnhancedScriptingPanelWidget
from ui.fixed_panels import (
    SerialConfigDefinitionPanelWidget,
    CustomLogPanelWidget,
    BasicCommPanelWidget
)
from ui.enhanced_serial_panel import EnhancedSerialPanel


class SidebarButton(QPushButton):
    """侧边栏按钮组件"""
    
    def __init__(self, text: str, icon_name: str = None, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setMinimumHeight(40)
        self.setMaximumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # 设置样式
        self.setStyleSheet("""
            SidebarButton {
                text-align: left;
                padding: 8px 12px;
                border: none;
                background-color: transparent;
                color: #cccccc;
                font-size: 13px;
            }
            SidebarButton:hover {
                background-color: #2a2d2e;
            }
            SidebarButton:checked {
                background-color: #37373d;
                color: #ffffff;
                border-left: 3px solid #007acc;
            }
        """)


class ActivityBar(QWidget):
    """VS Code风格的活动栏（最左侧）"""
    
    activity_changed = Signal(str)  # 发送活动名称
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(50)
        self.setStyleSheet("""
            ActivityBar {
                background-color: #333333;
                border-right: 1px solid #464647;
            }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)
        
        # 串口配置按钮
        self.serial_btn = self.create_activity_button("串口", "serial")
        layout.addWidget(self.serial_btn)
        
        # 脚本编辑按钮
        self.script_btn = self.create_activity_button("脚本", "script")
        layout.addWidget(self.script_btn)
        
        # 插件管理按钮
        self.plugins_btn = self.create_activity_button("插件", "plugins")
        layout.addWidget(self.plugins_btn)
        
        # 设置按钮
        self.settings_btn = self.create_activity_button("设置", "settings")
        layout.addWidget(self.settings_btn)
        
        layout.addStretch()
        
        # 默认选中串口
        self.serial_btn.setChecked(True)
        
    def create_activity_button(self, text: str, activity_name: str) -> QPushButton:
        btn = QPushButton(text[0])  # 只显示第一个字符
        btn.setFixedSize(40, 40)
        btn.setCheckable(True)
        btn.setToolTip(text)
        btn.clicked.connect(lambda checked, name=activity_name, button=btn: self.on_activity_clicked(name, button))
        
        btn.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #cccccc;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2a2d2e;
            }
            QPushButton:checked {
                background-color: #37373d;
                color: #ffffff;
                border-left: 2px solid #007acc;
            }
        """)
        
        return btn
        
    def on_activity_clicked(self, activity_name: str, clicked_button: QPushButton):
        # 取消其他按钮的选中状态
        for btn in [self.serial_btn, self.script_btn, self.plugins_btn, self.settings_btn]:
            btn.setChecked(False)
            
        # 设置当前按钮为选中状态
        clicked_button.setChecked(True)
        
        self.activity_changed.emit(activity_name)


class SidebarPanel(QWidget):
    """侧边栏面板基类"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标题栏
        title_frame = QFrame()
        title_frame.setFixedHeight(35)
        title_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-bottom: 1px solid #464647;
            }
        """)
        
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(12, 0, 12, 0)
        
        title_label = QLabel(self.title)
        title_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 13px;
                font-weight: bold;
            }
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        layout.addWidget(title_frame)
        
        # 内容区域
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.content_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #252526;
            }
        """)
        
        layout.addWidget(scroll_area)
        
    def add_content_widget(self, widget: QWidget):
        """添加内容组件"""
        self.content_layout.addWidget(widget)


class SerialSidebarPanel(SidebarPanel):
    """串口配置侧边栏面板"""
    
    def __init__(self, main_window=None, parent=None):
        super().__init__("串口配置", parent)
        
        # 使用增强的串口面板
        self.enhanced_panel = EnhancedSerialPanel(main_window=main_window)
        self.add_content_widget(self.enhanced_panel)
        
        # 连接信号
        self.enhanced_panel.connection_toggle_requested.connect(self.on_connection_toggle)
        self.enhanced_panel.config_changed.connect(self.on_config_changed)
        self.enhanced_panel.data_send_requested.connect(self.on_data_send)
        
    def on_connection_toggle(self, connect: bool):
        """处理连接切换请求"""
        # 这里可以连接到主应用的串口管理器
        print(f"Connection toggle requested: {connect}")
        
    def on_config_changed(self):
        """处理配置变更"""
        print("Serial config changed")
        
    def on_data_send(self, data: str, is_hex: bool):
        """处理数据发送请求"""
        print(f"Data send requested: {data}, hex: {is_hex}")
        
    def get_enhanced_panel(self) -> EnhancedSerialPanel:
        """获取增强面板实例"""
        return self.enhanced_panel


class ScriptSidebarPanel(SidebarPanel):
    """脚本管理侧边栏面板"""
    
    def __init__(self, main_window=None, parent=None):
        super().__init__("脚本管理", parent)
        self.main_window = main_window
        self.setup_script_panel()
        
    def setup_script_panel(self):
        """设置脚本面板内容"""
        # 脚本状态组
        status_group = QGroupBox("脚本状态")
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
        
        # 脚本统计信息
        self.total_scripts_label = QLabel("总脚本数: 0")
        self.total_scripts_label.setStyleSheet("color: #4ec9b0; padding: 4px;")
        status_layout.addWidget(self.total_scripts_label)
        
        self.running_scripts_label = QLabel("运行中: 0")
        self.running_scripts_label.setStyleSheet("color: #dcdcaa; padding: 4px;")
        status_layout.addWidget(self.running_scripts_label)
        
        self.add_content_widget(status_group)
        
        # 脚本列表组
        scripts_group = QGroupBox("脚本列表")
        scripts_group.setStyleSheet("""
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
        
        scripts_layout = QVBoxLayout(scripts_group)
        
        # 脚本列表
        self.scripts_list = QListWidget()
        self.scripts_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #464647;
                border-radius: 2px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #464647;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
        """)
        self.scripts_list.setMaximumHeight(120)
        scripts_layout.addWidget(self.scripts_list)
        
        self.add_content_widget(scripts_group)
        
        # 脚本操作组
        actions_group = QGroupBox("脚本操作")
        actions_group.setStyleSheet("""
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
        
        actions_layout = QVBoxLayout(actions_group)
        
        # 新建脚本按钮
        new_script_btn = QPushButton("新建脚本")
        new_script_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        new_script_btn.clicked.connect(self.new_script)
        actions_layout.addWidget(new_script_btn)
        
        # 运行脚本按钮
        run_script_btn = QPushButton("运行脚本")
        run_script_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        run_script_btn.clicked.connect(self.run_selected_script)
        actions_layout.addWidget(run_script_btn)
        
        # 停止脚本按钮
        stop_script_btn = QPushButton("停止脚本")
        stop_script_btn.setStyleSheet("""
            QPushButton {
                background-color: #d73a49;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #e85d75;
            }
        """)
        stop_script_btn.clicked.connect(self.stop_selected_script)
        actions_layout.addWidget(stop_script_btn)
        
        # 刷新脚本列表按钮
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_scripts)
        actions_layout.addWidget(refresh_btn)
        
        self.add_content_widget(actions_group)
        
        # 初始化脚本列表
        self.refresh_scripts()
        
    def new_script(self):
        """新建脚本"""
        if self.main_window and hasattr(self.main_window, 'create_new_script'):
            self.main_window.create_new_script()
        else:
            print("新建脚本功能")
            
    def run_selected_script(self):
        """运行选中的脚本"""
        current_item = self.scripts_list.currentItem()
        if current_item:
            script_name = current_item.text()
            if self.main_window and hasattr(self.main_window, 'run_script'):
                self.main_window.run_script(script_name)
            else:
                print(f"运行脚本: {script_name}")
            self.refresh_scripts()
            
    def stop_selected_script(self):
        """停止选中的脚本"""
        current_item = self.scripts_list.currentItem()
        if current_item:
            script_name = current_item.text()
            if self.main_window and hasattr(self.main_window, 'stop_script'):
                self.main_window.stop_script(script_name)
            else:
                print(f"停止脚本: {script_name}")
            self.refresh_scripts()
            
    def refresh_scripts(self):
        """刷新脚本列表"""
        self.scripts_list.clear()
        
        # 示例脚本列表
        example_scripts = [
            "数据处理脚本.py",
            "串口监控脚本.py",
            "自动化测试.py",
            "数据分析.py"
        ]
        
        for script in example_scripts:
            item = QListWidgetItem(script)
            self.scripts_list.addItem(item)
            
        # 更新统计信息
        total_count = len(example_scripts)
        running_count = 0  # 这里应该从实际的脚本引擎获取
        
        if self.main_window and hasattr(self.main_window, 'script_engine'):
            script_engine = self.main_window.script_engine
            if hasattr(script_engine, 'running_scripts'):
                running_count = len(script_engine.running_scripts)
                
        self.total_scripts_label.setText(f"总脚本数: {total_count}")
        self.running_scripts_label.setText(f"运行中: {running_count}")


class PluginsSidebarPanel(SidebarPanel):
    """插件管理侧边栏面板"""
    
    def __init__(self, main_window=None, parent=None):
        super().__init__("插件管理", parent)
        self.main_window = main_window
        self.setup_plugins_panel()
        
    def setup_plugins_panel(self):
        """设置插件面板内容"""
        # 插件状态组
        status_group = QGroupBox("插件状态")
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
        
        # 已加载插件列表
        self.loaded_plugins_label = QLabel("已加载插件: 0")
        self.loaded_plugins_label.setStyleSheet("color: #4ec9b0; padding: 4px;")
        status_layout.addWidget(self.loaded_plugins_label)
        
        # 可用插件列表
        self.available_plugins_label = QLabel("可用插件: 0")
        self.available_plugins_label.setStyleSheet("color: #dcdcaa; padding: 4px;")
        status_layout.addWidget(self.available_plugins_label)
        
        self.add_content_widget(status_group)
        
        # 插件操作组
        actions_group = QGroupBox("插件操作")
        actions_group.setStyleSheet("""
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
        
        actions_layout = QVBoxLayout(actions_group)
        
        # 插件管理按钮
        plugin_manager_btn = QPushButton("插件管理器")
        plugin_manager_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        plugin_manager_btn.clicked.connect(self.open_plugin_manager)
        actions_layout.addWidget(plugin_manager_btn)
        
        # 重新加载插件按钮
        reload_plugins_btn = QPushButton("重新加载插件")
        reload_plugins_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        reload_plugins_btn.clicked.connect(self.reload_plugins)
        actions_layout.addWidget(reload_plugins_btn)
        
        # 刷新插件状态按钮
        refresh_btn = QPushButton("刷新状态")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_plugin_status)
        actions_layout.addWidget(refresh_btn)
        
        self.add_content_widget(actions_group)
        
        # 初始化插件状态
        self.refresh_plugin_status()
        
    def open_plugin_manager(self):
        """打开插件管理器"""
        if self.main_window and hasattr(self.main_window, 'open_plugin_manager_dialog'):
            self.main_window.open_plugin_manager_dialog()
            
    def reload_plugins(self):
        """重新加载插件"""
        if self.main_window and hasattr(self.main_window, 'reload_all_plugins_action'):
            self.main_window.reload_all_plugins_action()
            self.refresh_plugin_status()
            
    def refresh_plugin_status(self):
        """刷新插件状态"""
        if self.main_window and hasattr(self.main_window, 'plugin_manager'):
            plugin_manager = self.main_window.plugin_manager
            loaded_count = len(plugin_manager.loaded_plugins) if hasattr(plugin_manager, 'loaded_plugins') else 0
            available_count = len(plugin_manager.available_panel_types) if hasattr(plugin_manager, 'available_panel_types') else 0
            
            self.loaded_plugins_label.setText(f"已加载插件: {loaded_count}")
            self.available_plugins_label.setText(f"可用插件: {available_count}")
        else:
            self.loaded_plugins_label.setText("已加载插件: 0")
            self.available_plugins_label.setText("可用插件: 0")


class SettingsSidebarPanel(SidebarPanel):
    """设置侧边栏面板"""
    
    def __init__(self, main_window=None, parent=None):
        super().__init__("设置", parent)
        self.main_window = main_window
        self.setup_settings_panel()
        
    def setup_settings_panel(self):
        """设置面板内容"""
        # 主题设置组
        theme_group = QGroupBox("主题设置")
        theme_group.setStyleSheet("""
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
        
        theme_layout = QVBoxLayout(theme_group)
        
        # 主题选择
        theme_label = QLabel("选择主题:")
        theme_label.setStyleSheet("color: #cccccc; padding: 4px;")
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["VS Code Dark", "VS Code Light", "Monokai", "Solarized Dark"])
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #464647;
                padding: 4px 8px;
                margin: 2px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #cccccc;
            }
        """)
        theme_layout.addWidget(self.theme_combo)
        
        # 主题编辑器按钮
        theme_btn = QPushButton("主题编辑器")
        theme_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        theme_btn.clicked.connect(self.open_theme_editor)
        theme_layout.addWidget(theme_btn)
        
        self.add_content_widget(theme_group)
        
        # 编辑器设置组
        editor_group = QGroupBox("编辑器设置")
        editor_group.setStyleSheet("""
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
        
        editor_layout = QVBoxLayout(editor_group)
        
        # 字体大小设置
        font_label = QLabel("字体大小:")
        font_label.setStyleSheet("color: #cccccc; padding: 4px;")
        editor_layout.addWidget(font_label)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(12)
        self.font_size_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #464647;
                padding: 4px 8px;
                margin: 2px;
            }
        """)
        editor_layout.addWidget(self.font_size_spin)
        
        # 自动保存
        self.auto_save_check = QCheckBox("自动保存")
        self.auto_save_check.setStyleSheet("""
            QCheckBox {
                color: #cccccc;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #3c3c3c;
                border: 1px solid #464647;
            }
            QCheckBox::indicator:checked {
                background-color: #007acc;
                border: 1px solid #007acc;
            }
        """)
        self.auto_save_check.setChecked(True)
        editor_layout.addWidget(self.auto_save_check)
        
        # 显示行号
        self.line_numbers_check = QCheckBox("显示行号")
        self.line_numbers_check.setStyleSheet("""
            QCheckBox {
                color: #cccccc;
                padding: 4px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #3c3c3c;
                border: 1px solid #464647;
            }
            QCheckBox::indicator:checked {
                background-color: #007acc;
                border: 1px solid #007acc;
            }
        """)
        self.line_numbers_check.setChecked(True)
        editor_layout.addWidget(self.line_numbers_check)
        
        self.add_content_widget(editor_group)
        
        # 应用设置按钮
        apply_btn = QPushButton("应用设置")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 8px 2px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        apply_btn.clicked.connect(self.apply_settings)
        self.add_content_widget(apply_btn)
        
    def open_theme_editor(self):
        """打开主题编辑器"""
        if self.main_window and hasattr(self.main_window, 'open_theme_editor_dialog'):
            self.main_window.open_theme_editor_dialog()
            
    def apply_settings(self):
        """应用设置"""
        # 应用主题
        theme_name = self.theme_combo.currentText()
        
        # 应用编辑器设置
        font_size = self.font_size_spin.value()
        auto_save = self.auto_save_check.isChecked()
        line_numbers = self.line_numbers_check.isChecked()
        
        if self.main_window:
            # 通知主窗口应用设置
            if hasattr(self.main_window, 'apply_theme'):
                self.main_window.apply_theme(theme_name)
            if hasattr(self.main_window, 'apply_editor_settings'):
                self.main_window.apply_editor_settings({
                    'font_size': font_size,
                    'auto_save': auto_save,
                    'line_numbers': line_numbers
                })
        
        print(f"应用设置: 主题={theme_name}, 字体大小={font_size}, 自动保存={auto_save}, 行号={line_numbers}")


class Sidebar(QWidget):
    """侧边栏容器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)
        self.setFixedWidth(320)  # 增加侧边栏宽度以容纳更多内容
        self.setStyleSheet("""
            Sidebar {
                background-color: #252526;
                border-right: 1px solid #464647;
            }
        """)
        
        self.panels = {}
        self.setup_ui()
        
    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
    def add_panel(self, name: str, panel: SidebarPanel):
        """添加侧边栏面板"""
        self.panels[name] = panel
        self.stacked_widget.addWidget(panel)
        
    def show_panel(self, name: str):
        """显示指定面板"""
        if name in self.panels:
            self.stacked_widget.setCurrentWidget(self.panels[name])


class BottomPanel(QWidget):
    """底部面板（日志、终端等）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setMaximumHeight(400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #464647;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #37373d;
            }
        """)
        
        layout.addWidget(self.tab_widget)
        
    def add_tab(self, widget: QWidget, title: str):
        """添加标签页"""
        self.tab_widget.addTab(widget, title)


class VSCodeStyleLayout(QWidget):
    """VS Code风格的主布局"""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.load_vscode_theme()
        self.setup_ui()
        self.setup_shortcuts()
        self.setup_drag_drop()
        self.load_layout_state()
        
    def setup_ui(self):
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 活动栏
        self.activity_bar = ActivityBar()
        self.activity_bar.activity_changed.connect(self.on_activity_changed)
        main_layout.addWidget(self.activity_bar)
        
        # 侧边栏
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)
        
        # 主分割器（编辑器区域和底部面板）
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #464647;
                height: 1px;
            }
        """)
        
        # 编辑器区域
        self.editor_area = QWidget()
        self.editor_area.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        
        editor_layout = QVBoxLayout(self.editor_area)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        
        # 脚本编辑器
        self.script_editor = EnhancedScriptingPanelWidget(main_window_ref=self.main_window)
        editor_layout.addWidget(self.script_editor)
        
        main_splitter.addWidget(self.editor_area)
        
        # 底部面板
        self.bottom_panel = BottomPanel()
        main_splitter.addWidget(self.bottom_panel)
        
        # 设置分割器比例 - 优化编辑器和底部面板的比例
        main_splitter.setSizes([500, 250])
        main_splitter.setStretchFactor(0, 3)  # 编辑器区域占更多空间
        main_splitter.setStretchFactor(1, 1)  # 底部面板相对较小
        
        main_layout.addWidget(main_splitter)
        
        # 初始化侧边栏面板
        self.init_sidebar_panels()
        
    def init_sidebar_panels(self):
        """初始化侧边栏面板"""
        # 串口配置面板
        serial_panel = SerialSidebarPanel(main_window=self.main_window)
        self.sidebar.add_panel("serial", serial_panel)
        
        # 脚本管理面板
        script_panel = ScriptSidebarPanel(main_window=self.main_window)
        self.sidebar.add_panel("script", script_panel)
        
        # 插件管理面板
        plugins_panel = PluginsSidebarPanel(main_window=self.main_window)
        self.sidebar.add_panel("plugins", plugins_panel)
        
        # 设置面板
        settings_panel = SettingsSidebarPanel(main_window=self.main_window)
        self.sidebar.add_panel("settings", settings_panel)
        
        # 默认显示串口面板
        self.sidebar.show_panel("serial")
        
    def load_vscode_theme(self):
        """加载VS Code主题样式"""
        try:
            theme_path = Path(__file__).parent / "vscode_dark_theme.qss"
            if theme_path.exists():
                with open(theme_path, 'r', encoding='utf-8') as f:
                    style = f.read()
                QApplication.instance().setStyleSheet(style)
        except Exception as e:
            print(f"加载VS Code主题失败: {e}")
        
    def init_bottom_panels(self):
        """初始化底部面板"""
        # 协议帧原始数据
        self.bottom_panel.add_tab(self.main_window.custom_log_panel_widget, "协议日志")
        
        # 基本收发
        self.bottom_panel.add_tab(self.main_window.basic_comm_panel_widget, "基本收发")
        
    @Slot(str)
    def on_activity_changed(self, activity_name: str):
        """活动栏切换事件"""
        self.sidebar.show_panel(activity_name)
        
    def setup_shortcuts(self):
        """设置快捷键"""
        from PySide6.QtGui import QShortcut, QKeySequence
        
        # Ctrl+N: 新建脚本
        new_script_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_script_shortcut.activated.connect(self.new_script)
        
        # Ctrl+O: 打开脚本
        open_script_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_script_shortcut.activated.connect(self.open_script)
        
        # Ctrl+S: 保存脚本
        save_script_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_script_shortcut.activated.connect(self.save_script)
        
        # F5: 运行脚本
        run_script_shortcut = QShortcut(QKeySequence("F5"), self)
        run_script_shortcut.activated.connect(self.run_script)
        
        # Shift+F5: 停止脚本
        stop_script_shortcut = QShortcut(QKeySequence("Shift+F5"), self)
        stop_script_shortcut.activated.connect(self.stop_script)
        
        # Ctrl+`: 切换底部面板
        toggle_bottom_shortcut = QShortcut(QKeySequence("Ctrl+`"), self)
        toggle_bottom_shortcut.activated.connect(self.toggle_bottom_panel)
        
        # Ctrl+B: 切换侧边栏
        toggle_sidebar_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        toggle_sidebar_shortcut.activated.connect(self.toggle_sidebar)
        
        # Ctrl+Shift+P: 命令面板
        command_palette_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        command_palette_shortcut.activated.connect(self.show_command_palette)
        
        # Ctrl+1-4: 切换活动栏
        for i in range(1, 5):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(lambda checked, idx=i-1: self.switch_activity(idx))
    
    def new_script(self):
        """新建脚本"""
        if hasattr(self.main_window, 'create_new_script'):
            self.main_window.create_new_script()
        else:
            self.script_editor.new_script()
    
    def open_script(self):
        """打开脚本"""
        if hasattr(self.main_window, 'open_script_dialog'):
            self.main_window.open_script_dialog()
        else:
            self.script_editor.open_script()
    
    def save_script(self):
        """保存脚本"""
        if hasattr(self.main_window, 'save_current_script'):
            self.main_window.save_current_script()
        else:
            self.script_editor.save_current_script()
    
    def run_script(self):
        """运行脚本"""
        if hasattr(self.main_window, 'run_current_script'):
            self.main_window.run_current_script()
        else:
            self.script_editor.run_current_script()
    
    def stop_script(self):
        """停止脚本"""
        if hasattr(self.main_window, 'stop_current_script'):
            self.main_window.stop_current_script()
        else:
            self.script_editor.stop_current_script()
    
    def toggle_bottom_panel(self):
        """切换底部面板显示/隐藏"""
        if self.bottom_panel.isVisible():
            self.bottom_panel.hide()
        else:
            self.bottom_panel.show()
    
    def toggle_sidebar(self):
        """切换侧边栏显示/隐藏"""
        if self.sidebar.isVisible():
            self.sidebar.hide()
        else:
            self.sidebar.show()
    
    def show_command_palette(self):
        """显示命令面板"""
        if hasattr(self.main_window, 'show_command_palette'):
            self.main_window.show_command_palette()
        else:
            print("命令面板功能待实现")
    
    def switch_activity(self, index: int):
        """切换活动栏"""
        activities = ["serial", "script", "plugins", "settings"]
        if 0 <= index < len(activities):
            activity_name = activities[index]
            self.sidebar.show_panel(activity_name)
            
            # 更新活动栏按钮状态
            buttons = [self.activity_bar.serial_btn, self.activity_bar.script_btn, 
                      self.activity_bar.plugins_btn, self.activity_bar.settings_btn]
            for btn in buttons:
                btn.setChecked(False)
            if index < len(buttons):
                buttons[index].setChecked(True)
    
    def get_script_editor(self) -> EnhancedScriptingPanelWidget:
        """获取脚本编辑器实例"""
        return self.script_editor
    
    def setup_drag_drop(self):
        """设置拖拽功能"""
        self.setAcceptDrops(True)
        
        # 为编辑器区域启用拖拽
        self.editor_area.setAcceptDrops(True)
        
        # 为脚本编辑器启用拖拽
        if hasattr(self.script_editor, 'setAcceptDrops'):
            self.script_editor.setAcceptDrops(True)
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            # 检查是否为支持的文件类型
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.endswith(('.py', '.txt', '.json', '.xml', '.csv')):
                        event.acceptProposedAction()
                        return
        event.ignore()
    
    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """拖拽放下事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    self.handle_dropped_file(file_path)
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def handle_dropped_file(self, file_path: str):
        """处理拖拽的文件"""
        try:
            if file_path.endswith('.py'):
                # Python脚本文件，在脚本编辑器中打开
                if hasattr(self.script_editor, 'open_file'):
                    self.script_editor.open_file(file_path)
                elif hasattr(self.main_window, 'open_script_file'):
                    self.main_window.open_script_file(file_path)
                else:
                    print(f"打开Python脚本: {file_path}")
            
            elif file_path.endswith(('.txt', '.log')):
                # 文本文件，可能是日志文件
                if hasattr(self.main_window, 'import_log_file'):
                    self.main_window.import_log_file(file_path)
                else:
                    print(f"导入日志文件: {file_path}")
            
            elif file_path.endswith(('.json', '.xml')):
                # 配置文件
                if hasattr(self.main_window, 'import_config_file'):
                    self.main_window.import_config_file(file_path)
                else:
                    print(f"导入配置文件: {file_path}")
            
            elif file_path.endswith('.csv'):
                # CSV数据文件
                if hasattr(self.main_window, 'import_data_file'):
                    self.main_window.import_data_file(file_path)
                else:
                    print(f"导入数据文件: {file_path}")
            
            else:
                print(f"不支持的文件类型: {file_path}")
                
        except Exception as e:
            print(f"处理拖拽文件时出错: {e}")
    
    def load_layout_state(self):
        """加载布局状态"""
        try:
            import json
            import os
            
            config_file = "layout_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 恢复分割器状态
                if 'main_splitter_sizes' in config:
                    self.main_splitter.setSizes(config['main_splitter_sizes'])
                
                # 恢复侧边栏状态
                if 'sidebar_visible' in config:
                    if config['sidebar_visible']:
                        self.sidebar.show()
                    else:
                        self.sidebar.hide()
                
                if 'sidebar_width' in config:
                    self.sidebar.setFixedWidth(config['sidebar_width'])
                
                # 恢复底部面板状态
                if 'bottom_panel_visible' in config:
                    if config['bottom_panel_visible']:
                        self.bottom_panel.show()
                    else:
                        self.bottom_panel.hide()
                
                if 'bottom_panel_height' in config:
                    self.bottom_panel.setFixedHeight(config['bottom_panel_height'])
                
                # 恢复活动面板
                if 'active_panel' in config:
                    self.sidebar.show_panel(config['active_panel'])
                
                print("布局状态已恢复")
        except Exception as e:
            print(f"加载布局状态时出错: {e}")
    
    def save_layout_state(self):
        """保存布局状态"""
        try:
            import json
            
            config = {
                'main_splitter_sizes': self.main_splitter.sizes(),
                'sidebar_visible': self.sidebar.isVisible(),
                'sidebar_width': self.sidebar.width(),
                'bottom_panel_visible': self.bottom_panel.isVisible(),
                'bottom_panel_height': self.bottom_panel.height(),
                'active_panel': self.sidebar.current_panel_name if hasattr(self.sidebar, 'current_panel_name') else 'serial'
            }
            
            with open("layout_config.json", 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print("布局状态已保存")
        except Exception as e:
            print(f"保存布局状态时出错: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.save_layout_state()
        super().closeEvent(event)