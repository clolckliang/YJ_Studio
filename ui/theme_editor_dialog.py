from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QComboBox, QColorDialog, QGroupBox, QGridLayout,
    QMessageBox, QFileDialog, QTabWidget, QWidget, QListWidget,
    QListWidgetItem, QSplitter, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap, QPainter
from ui.theme_manager import ThemeManager

class ColorButton(QPushButton):
    """颜色选择按钮"""
    color_changed = Signal(QColor)
    
    def __init__(self, color: QColor = QColor(255, 255, 255), parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(40, 30)
        self.clicked.connect(self._choose_color)
        self._update_button_style()
    
    def _update_button_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color.name()};
                border: 2px solid #666666;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #999999;
            }}
        """)
    
    def _choose_color(self):
        color = QColorDialog.getColor(self._color, self, "选择颜色")
        if color.isValid():
            self._color = color
            self._update_button_style()
            self.color_changed.emit(color)
    
    def get_color(self) -> QColor:
        return self._color
    
    def set_color(self, color: QColor):
        self._color = color
        self._update_button_style()

class ThemePreviewWidget(QWidget):
    """主题预览窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 创建预览组件
        group = QGroupBox("预览效果")
        group_layout = QGridLayout(group)
        
        # 标签
        group_layout.addWidget(QLabel("标签文本:"), 0, 0)
        
        # 输入框
        line_edit = QLineEdit("输入框示例")
        group_layout.addWidget(line_edit, 0, 1)
        
        # 按钮
        button = QPushButton("按钮示例")
        group_layout.addWidget(button, 1, 0)
        
        # 下拉框
        combo = QComboBox()
        combo.addItems(["选项1", "选项2", "选项3"])
        group_layout.addWidget(combo, 1, 1)
        
        # 文本编辑器
        text_edit = QTextEdit()
        text_edit.setPlainText("这是一个文本编辑器的示例内容。\n可以在这里输入多行文本。")
        text_edit.setMaximumHeight(80)
        group_layout.addWidget(text_edit, 2, 0, 1, 2)
        
        layout.addWidget(group)
        
        # 添加一些填充
        layout.addStretch()

class ThemeEditorDialog(QDialog):
    """主题编辑器对话框"""
    
    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.current_theme_name = ""
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._apply_preview)
        
        self.setWindowTitle("主题编辑器")
        self.setModal(True)
        self.resize(1000, 700)
        
        self.init_ui()
        self._load_theme_list()
        
        # 连接主题管理器信号
        self.theme_manager.theme_list_updated.connect(self._load_theme_list)
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        
        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 左侧面板
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板（标签页）
        self.tab_widget = QTabWidget()
        
        # 代码编辑标签页
        self.code_tab = self._create_code_editor_tab()
        self.tab_widget.addTab(self.code_tab, "代码编辑")
        
        # 可视化编辑标签页
        self.visual_tab = self._create_visual_editor_tab()
        self.tab_widget.addTab(self.visual_tab, "可视化编辑")
        
        # 预览标签页
        self.preview_tab = ThemePreviewWidget()
        self.tab_widget.addTab(self.preview_tab, "预览效果")
        
        splitter.addWidget(self.tab_widget)
        
        # 设置分割器比例
        splitter.setSizes([300, 700])
    
    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 主题分类过滤
        layout.addWidget(QLabel("主题分类:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("所有主题", "all")
        self.category_combo.addItem("内置主题", "builtin")
        self.category_combo.addItem("预设主题", "preset")
        self.category_combo.addItem("浅色主题", "light")
        self.category_combo.addItem("深色主题", "dark")
        self.category_combo.addItem("彩色主题", "colorful")
        self.category_combo.addItem("无障碍主题", "accessibility")
        self.category_combo.addItem("自定义主题", "custom")
        self.category_combo.currentTextChanged.connect(self._filter_themes)
        layout.addWidget(self.category_combo)
        
        # 主题列表
        layout.addWidget(QLabel("主题列表:"))
        self.theme_list = QListWidget()
        self.theme_list.itemClicked.connect(self._on_theme_selected)
        layout.addWidget(self.theme_list)
        
        # 操作按钮
        btn_layout = QVBoxLayout()
        
        self.new_theme_btn = QPushButton("新建主题")
        self.new_theme_btn.clicked.connect(self._new_theme)
        btn_layout.addWidget(self.new_theme_btn)
        
        self.save_theme_btn = QPushButton("保存主题")
        self.save_theme_btn.clicked.connect(self._save_theme)
        self.save_theme_btn.setEnabled(False)
        btn_layout.addWidget(self.save_theme_btn)
        
        self.delete_theme_btn = QPushButton("删除主题")
        self.delete_theme_btn.clicked.connect(self._delete_theme)
        self.delete_theme_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_theme_btn)
        
        btn_layout.addWidget(QLabel(""))  # 分隔符
        
        self.import_theme_btn = QPushButton("导入主题")
        self.import_theme_btn.clicked.connect(self._import_theme)
        btn_layout.addWidget(self.import_theme_btn)
        
        self.export_theme_btn = QPushButton("导出主题")
        self.export_theme_btn.clicked.connect(self._export_theme)
        self.export_theme_btn.setEnabled(False)
        btn_layout.addWidget(self.export_theme_btn)
        
        btn_layout.addWidget(QLabel(""))  # 分隔符
        
        self.apply_theme_btn = QPushButton("应用主题")
        self.apply_theme_btn.clicked.connect(self._apply_theme)
        self.apply_theme_btn.setEnabled(False)
        btn_layout.addWidget(self.apply_theme_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        return widget
    
    def _update_color_selectors(self, css_content):
        """从CSS内容更新颜色选择器"""
        # 简单的颜色提取逻辑
        import re
        
        # 提取常见的颜色值
        color_patterns = {
            'primary': r'#[0-9a-fA-F]{6}',
            'background': r'background-color:\s*([^;]+)',
            'text': r'color:\s*([^;]+)',
        }
        
        color_buttons = {
            'primary': self.primary_color_btn,
            'background': self.background_color_btn,
            'text': self.text_color_btn,
        }
        
        for color_name, button in color_buttons.items():
            if color_name in color_patterns:
                pattern = color_patterns[color_name]
                matches = re.findall(pattern, css_content)
                if matches:
                    color_value = matches[0].strip()
                    if color_value.startswith('#'):
                        color = QColor(color_value)
                        if color.isValid():
                            button.set_color(color)
    
    def _update_color_selectors_from_info(self, colors_dict):
        """从主题信息中的颜色字典更新颜色选择器"""
        color_buttons = {
            'primary': self.primary_color_btn,
            'secondary': self.secondary_color_btn,
            'background': self.background_color_btn,
            'text': self.text_color_btn,
        }
        
        for color_name, button in color_buttons.items():
            if color_name in colors_dict:
                color_value = colors_dict[color_name]
                if isinstance(color_value, str) and color_value.startswith('#'):
                    color = QColor(color_value)
                    if color.isValid():
                        button.set_color(color)
    
    def _create_code_editor_tab(self) -> QWidget:
        """创建代码编辑标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 主题名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("主题名称:"))
        self.theme_name_edit = QLineEdit()
        self.theme_name_edit.textChanged.connect(self._on_theme_name_changed)
        name_layout.addWidget(self.theme_name_edit)
        layout.addLayout(name_layout)
        
        # CSS代码编辑器
        layout.addWidget(QLabel("CSS样式代码:"))
        self.css_editor = QTextEdit()
        self.css_editor.setFont(QFont("Consolas", 10))
        self.css_editor.textChanged.connect(self._on_css_changed)
        layout.addWidget(self.css_editor)
        
        # 实时预览选项
        self.live_preview_cb = QCheckBox("实时预览 (可能影响性能)")
        self.live_preview_cb.setChecked(False)
        layout.addWidget(self.live_preview_cb)
        
        return widget
    
    def _create_visual_editor_tab(self) -> QWidget:
        """创建可视化编辑标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 基础颜色设置
        color_group = QGroupBox("基础颜色设置")
        color_layout = QGridLayout(color_group)
        
        # 主色调
        color_layout.addWidget(QLabel("主色调:"), 0, 0)
        self.primary_color_btn = ColorButton(QColor("#3498db"))
        self.primary_color_btn.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self.primary_color_btn, 0, 1)
        
        # 次要颜色
        color_layout.addWidget(QLabel("次要颜色:"), 0, 2)
        self.secondary_color_btn = ColorButton(QColor("#2c3e50"))
        self.secondary_color_btn.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self.secondary_color_btn, 0, 3)
        
        # 背景颜色
        color_layout.addWidget(QLabel("背景颜色:"), 1, 0)
        self.background_color_btn = ColorButton(QColor("#ecf0f1"))
        self.background_color_btn.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self.background_color_btn, 1, 1)
        
        # 文字颜色
        color_layout.addWidget(QLabel("文字颜色:"), 1, 2)
        self.text_color_btn = ColorButton(QColor("#2c3e50"))
        self.text_color_btn.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self.text_color_btn, 1, 3)
        
        layout.addWidget(color_group)
        
        # 生成按钮
        generate_btn = QPushButton("根据颜色生成主题")
        generate_btn.clicked.connect(self._generate_theme_from_colors)
        layout.addWidget(generate_btn)
        
        # 预设主题模板
        template_group = QGroupBox("预设模板")
        template_layout = QVBoxLayout(template_group)
        
        self.template_combo = QComboBox()
        self.template_combo.addItems([
            "选择模板...",
            "现代深色",
            "清新浅色",
            "科技蓝",
            "温暖橙",
            "自然绿",
            "优雅紫"
        ])
        self.template_combo.currentTextChanged.connect(self._on_template_selected)
        template_layout.addWidget(self.template_combo)
        
        layout.addWidget(template_group)
        
        layout.addStretch()
        
        return widget
    
    def _load_theme_list(self):
        """加载主题列表"""
        self.theme_list.clear()
        all_themes = self.theme_manager.get_all_themes()
        
        for theme_name, theme_type in all_themes.items():
            item = QListWidgetItem(f"{theme_name} ({theme_type})")
            item.setData(Qt.ItemDataRole.UserRole, theme_name)
            
            # 根据主题类型设置图标颜色
            if theme_type == "预设主题":
                item.setForeground(QColor("#3498db"))
            elif theme_type == "自定义主题":
                item.setForeground(QColor("#e74c3c"))
            else:
                item.setForeground(QColor("#2c3e50"))
            
            self.theme_list.addItem(item)
    
    def _filter_themes(self):
        """根据分类过滤主题"""
        category = self.category_combo.currentData()
        if not category:
            category = self.category_combo.currentText()
        
        self.theme_list.clear()
        
        if category == "all" or category == "所有主题":
            # 显示所有主题
            all_themes = self.theme_manager.get_all_themes()
            for theme_name, theme_type in all_themes.items():
                item = QListWidgetItem(f"{theme_name} ({theme_type})")
                item.setData(Qt.ItemDataRole.UserRole, theme_name)
                self.theme_list.addItem(item)
        elif category == "builtin" or category == "内置主题":
            # 显示内置主题
            for theme_name in self.theme_manager.themes.keys():
                item = QListWidgetItem(f"{theme_name} (内置主题)")
                item.setData(Qt.ItemDataRole.UserRole, theme_name)
                self.theme_list.addItem(item)
        elif category == "preset" or category == "预设主题":
            # 显示预设主题
            if hasattr(self.theme_manager, 'preset_themes'):
                for theme_name in self.theme_manager.preset_themes.keys():
                    item = QListWidgetItem(f"{theme_name} (预设主题)")
                    item.setData(Qt.ItemDataRole.UserRole, theme_name)
                    item.setForeground(QColor("#3498db"))
                    self.theme_list.addItem(item)
        elif category == "custom" or category == "自定义主题":
            # 显示自定义主题
            for theme_name in self.theme_manager.user_themes.keys():
                item = QListWidgetItem(f"{theme_name} (自定义主题)")
                item.setData(Qt.ItemDataRole.UserRole, theme_name)
                item.setForeground(QColor("#e74c3c"))
                self.theme_list.addItem(item)
        else:
            # 根据预设分类过滤
            if hasattr(self.theme_manager, 'get_themes_by_category'):
                themes = self.theme_manager.get_themes_by_category(category)
                for theme_name in themes:
                    theme_info = self.theme_manager.get_theme_info(theme_name)
                    theme_type = theme_info.get('type', 'unknown')
                    type_text = {
                        'builtin': '内置主题',
                        'preset': '预设主题', 
                        'custom': '自定义主题'
                    }.get(theme_type, '未知主题')
                    
                    item = QListWidgetItem(f"{theme_name} ({type_text})")
                    item.setData(Qt.ItemDataRole.UserRole, theme_name)
                    
                    if theme_type == 'preset':
                        item.setForeground(QColor("#3498db"))
                    elif theme_type == 'custom':
                        item.setForeground(QColor("#e74c3c"))
                    
                    self.theme_list.addItem(item)
    
    def _on_theme_selected(self, item: QListWidgetItem):
        """主题选中事件"""
        theme_name = item.data(Qt.ItemDataRole.UserRole)
        self.current_theme_name = theme_name
        
        # 获取主题信息
        theme_info = self.theme_manager.get_theme_info(theme_name) if hasattr(self.theme_manager, 'get_theme_info') else {}
        
        # 加载主题内容
        theme_content = self.theme_manager.get_theme_content(theme_name)
        if theme_content:
            self.css_editor.setPlainText(theme_content)
            self.theme_name_edit.setText(theme_name)
            
            # 更新颜色选择器（如果是基于颜色的主题）
            if theme_info.get('colors'):
                self._update_color_selectors_from_info(theme_info['colors'])
            else:
                self._update_color_selectors(theme_content)
        
        # 更新按钮状态
        is_custom = theme_name in self.theme_manager.user_themes
        is_preset = hasattr(self.theme_manager, 'preset_themes') and theme_name in self.theme_manager.preset_themes
        
        self.save_theme_btn.setEnabled(is_custom or is_preset)
        self.delete_theme_btn.setEnabled(is_custom)
        self.export_theme_btn.setEnabled(True)
        self.apply_theme_btn.setEnabled(True)
    
    def _new_theme(self):
        """新建主题"""
        from PySide6.QtWidgets import QInputDialog
        
        theme_name, ok = QInputDialog.getText(
            self, "新建主题", "请输入主题名称:", text="我的主题"
        )
        
        if ok and theme_name.strip():
            base_theme = "dark"  # 默认基于深色主题
            if self.current_theme_name:
                base_theme = self.current_theme_name
            
            content = self.theme_manager.create_custom_theme(theme_name.strip(), base_theme)
            self.css_editor.setPlainText(content)
            self.theme_name_edit.setText(theme_name.strip())
            self.current_theme_name = theme_name.strip()
            
            # 更新按钮状态
            self.save_theme_btn.setEnabled(True)
            self.delete_theme_btn.setEnabled(True)
            self.export_theme_btn.setEnabled(True)
            self.apply_theme_btn.setEnabled(True)
    
    def _save_theme(self):
        """保存主题"""
        if not self.current_theme_name:
            QMessageBox.warning(self, "警告", "请先选择或创建一个主题")
            return
        
        theme_content = self.css_editor.toPlainText()
        if self.theme_manager.update_custom_theme(self.current_theme_name, theme_content):
            QMessageBox.information(self, "成功", f"主题 '{self.current_theme_name}' 已保存")
        else:
            QMessageBox.critical(self, "错误", "保存主题失败")
    
    def _delete_theme(self):
        """删除主题"""
        if not self.current_theme_name:
            return
        
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除主题 '{self.current_theme_name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.theme_manager.delete_custom_theme(self.current_theme_name):
                QMessageBox.information(self, "成功", "主题已删除")
                self.current_theme_name = ""
                self.css_editor.clear()
                self.theme_name_edit.clear()
                self._update_button_states()
            else:
                QMessageBox.critical(self, "错误", "删除主题失败")
    
    def _import_theme(self):
        """导入主题"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入主题文件", "", "JSON 文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            theme_name = self.theme_manager.import_theme(file_path)
            if theme_name:
                QMessageBox.information(self, "成功", f"主题 '{theme_name}' 已导入")
            else:
                QMessageBox.critical(self, "错误", "导入主题失败")
    
    def _export_theme(self):
        """导出主题"""
        if not self.current_theme_name:
            QMessageBox.warning(self, "警告", "请先选择一个主题")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出主题文件", f"{self.current_theme_name}.json", 
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        
        if file_path:
            if self.theme_manager.export_theme(self.current_theme_name, file_path):
                QMessageBox.information(self, "成功", "主题已导出")
            else:
                QMessageBox.critical(self, "错误", "导出主题失败")
    
    def _apply_theme(self):
        """应用主题"""
        if not self.current_theme_name:
            return
        
        self.theme_manager.apply_theme(self.current_theme_name)
        QMessageBox.information(self, "成功", f"主题 '{self.current_theme_name}' 已应用")
    
    def _on_theme_name_changed(self):
        """主题名称变化"""
        # 这里可以添加名称验证逻辑
        pass
    
    def _on_css_changed(self):
        """CSS代码变化"""
        if self.live_preview_cb.isChecked():
            # 延迟预览，避免频繁更新
            self.preview_timer.start(500)
    
    def _apply_preview(self):
        """应用预览"""
        css_content = self.css_editor.toPlainText()
        if css_content.strip():
            try:
                # 只在预览标签页应用样式
                self.preview_tab.setStyleSheet(css_content)
            except Exception as e:
                pass  # 忽略预览错误
    
    def _on_color_changed(self):
        """颜色变化事件"""
        # 可以在这里添加实时颜色预览
        pass
    
    def _generate_theme_from_colors(self):
        """根据颜色生成主题"""
        primary = self.primary_color_btn.get_color()
        secondary = self.secondary_color_btn.get_color()
        background = self.background_color_btn.get_color()
        text = self.text_color_btn.get_color()
        
        theme_css = self.theme_manager.generate_theme_from_colors(
            primary, secondary, background, text
        )
        
        self.css_editor.setPlainText(theme_css)
    
    def _on_template_selected(self, template_name: str):
        """模板选择事件"""
        if template_name == "选择模板...":
            return
        
        # 预设颜色方案
        color_schemes = {
            "现代深色": {
                "primary": QColor("#3498db"),
                "secondary": QColor("#2c3e50"),
                "background": QColor("#34495e"),
                "text": QColor("#ecf0f1")
            },
            "清新浅色": {
                "primary": QColor("#2ecc71"),
                "secondary": QColor("#ecf0f1"),
                "background": QColor("#ffffff"),
                "text": QColor("#2c3e50")
            },
            "科技蓝": {
                "primary": QColor("#3498db"),
                "secondary": QColor("#34495e"),
                "background": QColor("#2c3e50"),
                "text": QColor("#ecf0f1")
            },
            "温暖橙": {
                "primary": QColor("#e67e22"),
                "secondary": QColor("#f39c12"),
                "background": QColor("#fdf2e9"),
                "text": QColor("#2c3e50")
            },
            "自然绿": {
                "primary": QColor("#27ae60"),
                "secondary": QColor("#2ecc71"),
                "background": QColor("#e8f8f5"),
                "text": QColor("#1e8449")
            },
            "优雅紫": {
                "primary": QColor("#9b59b6"),
                "secondary": QColor("#8e44ad"),
                "background": QColor("#f4ecf7"),
                "text": QColor("#6c3483")
            }
        }
        
        if template_name in color_schemes:
            scheme = color_schemes[template_name]
            self.primary_color_btn.set_color(scheme["primary"])
            self.secondary_color_btn.set_color(scheme["secondary"])
            self.background_color_btn.set_color(scheme["background"])
            self.text_color_btn.set_color(scheme["text"])
            
            # 自动生成主题
            self._generate_theme_from_colors()
    
    def _update_button_states(self):
        """更新按钮状态"""
        has_theme = bool(self.current_theme_name)
        is_custom = self.current_theme_name in self.theme_manager.user_themes
        
        self.save_theme_btn.setEnabled(is_custom)
        self.delete_theme_btn.setEnabled(is_custom)
        self.export_theme_btn.setEnabled(has_theme)
        self.apply_theme_btn.setEnabled(has_theme)