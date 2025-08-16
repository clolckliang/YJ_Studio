from typing import Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QGridLayout, QFrame, QScrollArea,
    QSizePolicy, QToolTip
)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPalette
from ui.theme_manager import ThemeManager

class ThemePreviewCard(QFrame):
    """主题预览卡片"""
    theme_selected = Signal(str)
    
    def __init__(self, theme_name: str, theme_type: str, theme_manager: ThemeManager, theme_info: dict = None, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self.theme_type = theme_type
        self.theme_manager = theme_manager
        self.theme_info = theme_info or {}
        self.is_current = False
        
        self.setFixedSize(200, 150)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.init_ui()
        self.update_style()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # 主题名称
        display_name = self.theme_info.get('name', self.theme_name)
        self.name_label = QLabel(display_name)
        self.name_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        
        # 主题类型和分类
        type_text = "内置" if self.theme_type == "internal" else "预设" if self.theme_type == "preset" else "自定义"
        if self.theme_info.get('category'):
            type_text += f" · {self.theme_info['category']}"
        
        self.type_label = QLabel(f"({type_text})")
        self.type_label.setFont(QFont("Arial", 8))
        self.type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.type_label)
        
        # 主题描述（如果有）
        if self.theme_info.get('description'):
            desc_label = QLabel(self.theme_info['description'])
            desc_label.setFont(QFont("Arial", 7))
            desc_label.setStyleSheet("color: #888;")
            desc_label.setWordWrap(True)
            desc_label.setMaximumHeight(20)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(desc_label)
        
        # 预览区域
        self.preview_widget = QWidget()
        self.preview_widget.setFixedHeight(60)
        self.preview_widget.setStyleSheet("""
            QWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.preview_widget)
        
        # 应用按钮
        self.apply_btn = QPushButton("应用")
        self.apply_btn.setFixedHeight(25)
        self.apply_btn.clicked.connect(self._apply_theme)
        layout.addWidget(self.apply_btn)
        
        layout.addStretch()
    
    def _apply_theme(self):
        """应用主题"""
        self.theme_selected.emit(self.theme_name)
    
    def set_current(self, is_current: bool):
        """设置是否为当前主题"""
        self.is_current = is_current
        self.update_style()
    
    def update_style(self):
        """更新样式"""
        if self.is_current:
            self.setStyleSheet("""
                ThemePreviewCard {
                    border: 3px solid #3498db;
                    border-radius: 8px;
                    background-color: #e8f4fd;
                }
            """)
            self.apply_btn.setText("当前主题")
            self.apply_btn.setEnabled(False)
        else:
            self.setStyleSheet("""
                ThemePreviewCard {
                    border: 1px solid #bdc3c7;
                    border-radius: 8px;
                    background-color: #ffffff;
                }
                ThemePreviewCard:hover {
                    border: 2px solid #3498db;
                    background-color: #f8f9fa;
                }
            """)
            self.apply_btn.setText("应用")
            self.apply_btn.setEnabled(True)
        
        # 更新预览区域
        self._update_preview()
    
    def _update_preview(self):
        """更新预览区域"""
        theme_content = self.theme_manager.get_theme_content(self.theme_name)
        if theme_content:
            # 简化的预览样式
            preview_style = self._extract_preview_colors(theme_content)
            self.preview_widget.setStyleSheet(preview_style)
    
    def _extract_preview_colors(self, theme_content: str) -> str:
        """从主题内容中提取预览颜色"""
        # 简单的颜色提取逻辑
        import re
        
        # 提取背景色
        bg_match = re.search(r'background-color:\s*([^;]+)', theme_content)
        bg_color = bg_match.group(1).strip() if bg_match else '#f0f0f0'
        
        # 提取文字色
        text_match = re.search(r'color:\s*([^;]+)', theme_content)
        text_color = text_match.group(1).strip() if text_match else '#000000'
        
        return f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #ccc;
                border-radius: 4px;
            }}
        """
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._apply_theme()
        super().mousePressEvent(event)

class ThemeQuickSwitcher(QWidget):
    """主题快速切换器"""
    
    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.theme_cards: Dict[str, ThemePreviewCard] = {}
        
        self.setWindowTitle("主题快速切换")
        self.resize(800, 600)
        
        self.init_ui()
        self._load_themes()
        
        # 连接主题管理器信号
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
        self.theme_manager.theme_list_updated.connect(self._load_themes)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel("主题快速切换")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 分类选择
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "内置主题", "预设主题", "浅色主题", "深色主题", "彩色主题", "无障碍主题", "自定义主题"])
        self.filter_combo.currentTextChanged.connect(self._filter_themes)
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addStretch()
        
        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._load_themes)
        filter_layout.addWidget(refresh_btn)
        
        layout.addLayout(filter_layout)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 主题网格容器
        self.themes_container = QWidget()
        self.themes_layout = QGridLayout(self.themes_container)
        self.themes_layout.setSpacing(10)
        
        scroll_area.setWidget(self.themes_container)
        layout.addWidget(scroll_area)
        
        # 底部按钮
        bottom_layout = QHBoxLayout()
        
        edit_btn = QPushButton("主题编辑器")
        edit_btn.clicked.connect(self._open_theme_editor)
        bottom_layout.addWidget(edit_btn)
        
        bottom_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)
        
        layout.addLayout(bottom_layout)
    
    def _load_themes(self):
        """加载主题列表"""
        # 清除现有卡片
        for card in self.theme_cards.values():
            card.deleteLater()
        self.theme_cards.clear()
        
        # 获取所有主题
        all_themes = self.theme_manager.get_all_themes()
        current_theme = self.theme_manager.current_theme_info.get("name", "")
        
        # 创建主题卡片
        row, col = 0, 0
        max_cols = 3
        
        for theme_name, theme_type in all_themes.items():
            # 获取主题详细信息
            theme_info = self.theme_manager.get_theme_info(theme_name) if hasattr(self.theme_manager, 'get_theme_info') else {}
            
            card = ThemePreviewCard(theme_name, theme_type, self.theme_manager, theme_info)
            card.theme_selected.connect(self._apply_theme)
            card.set_current(theme_name == current_theme)
            
            self.theme_cards[theme_name] = card
            self.themes_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # 添加弹性空间
        self.themes_layout.setRowStretch(row + 1, 1)
        self.themes_layout.setColumnStretch(max_cols, 1)
    
    def _filter_themes(self, filter_text: str):
        """筛选主题"""
        for theme_name, card in self.theme_cards.items():
            should_show = False
            
            if filter_text == "全部":
                should_show = True
            elif filter_text == "内置主题":
                should_show = theme_name in self.theme_manager.themes
            elif filter_text == "预设主题":
                should_show = hasattr(self.theme_manager, 'preset_themes') and theme_name in self.theme_manager.preset_themes
            elif filter_text == "自定义主题":
                should_show = theme_name in self.theme_manager.user_themes
            elif filter_text in ["浅色主题", "深色主题", "彩色主题", "无障碍主题"]:
                # 根据主题分类筛选
                category_map = {
                    "浅色主题": "light",
                    "深色主题": "dark", 
                    "彩色主题": "colorful",
                    "无障碍主题": "accessibility"
                }
                category = category_map.get(filter_text)
                if category and hasattr(self.theme_manager, 'get_themes_by_category'):
                    category_themes = self.theme_manager.get_themes_by_category(category)
                    should_show = theme_name in category_themes
            
            card.setVisible(should_show)
    
    def _apply_theme(self, theme_name: str):
        """应用主题"""
        self.theme_manager.apply_theme(theme_name)
    
    def _on_theme_changed(self, theme_name: str):
        """主题变化事件"""
        # 更新卡片状态
        for name, card in self.theme_cards.items():
            card.set_current(name == theme_name)
    
    def _open_theme_editor(self):
        """打开主题编辑器"""
        from ui.theme_editor_dialog import ThemeEditorDialog
        dialog = ThemeEditorDialog(self.theme_manager, self)
        dialog.exec()

class ThemeQuickSwitcherWidget(QWidget):
    """可嵌入的主题快速切换器组件"""
    
    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        
        self.init_ui()
        self._update_current_theme()
        
        # 连接信号
        self.theme_manager.theme_changed.connect(self._update_current_theme)
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # 当前主题显示
        layout.addWidget(QLabel("当前主题:"))
        
        self.current_theme_label = QLabel("light")
        self.current_theme_label.setStyleSheet("""
            QLabel {
                padding: 4px 8px;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #ecf0f1;
            }
        """)
        layout.addWidget(self.current_theme_label)
        
        # 快速切换按钮
        quick_switch_btn = QPushButton("快速切换")
        quick_switch_btn.clicked.connect(self._open_quick_switcher)
        layout.addWidget(quick_switch_btn)
        
        # 主题编辑器按钮
        editor_btn = QPushButton("编辑器")
        editor_btn.clicked.connect(self._open_theme_editor)
        layout.addWidget(editor_btn)
        
        layout.addStretch()
    
    def _update_current_theme(self):
        """更新当前主题显示"""
        current_theme = self.theme_manager.current_theme_info.get("name", "未知")
        theme_type = self.theme_manager.current_theme_info.get("type", "internal")
        type_text = "内置" if theme_type == "internal" else "自定义" if theme_type == "user_custom" else "外部"
        
        self.current_theme_label.setText(f"{current_theme} ({type_text})")
    
    def _open_quick_switcher(self):
        """打开快速切换器"""
        switcher = ThemeQuickSwitcher(self.theme_manager, self)
        switcher.show()
    
    def _open_theme_editor(self):
        """打开主题编辑器"""
        from ui.theme_editor_dialog import ThemeEditorDialog
        dialog = ThemeEditorDialog(self.theme_manager, self)
        dialog.exec()