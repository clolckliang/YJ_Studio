from pathlib import Path
from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import QApplication, QMessageBox, QColorDialog
from PySide6.QtCore import QSettings, Signal, QObject
from PySide6.QtGui import QColor
import json
import os

class ThemeManager(QObject):
    # 信号定义
    theme_changed = Signal(str)  # 主题变化信号
    theme_list_updated = Signal()  # 主题列表更新信号
    
    def __init__(self, app: QApplication, error_logger: Optional[Any] = None): # ErrorLogger type hint
        super().__init__()
        self.app = app
        self.error_logger = error_logger # from utils.logger
        self.settings = QSettings("YJ_Studio", "ThemeManager")
        self.custom_themes_dir = "themes"  # 自定义主题目录
        self.user_themes: Dict[str, str] = {}  # 用户自定义主题
        
        # 确保主题目录存在
        os.makedirs(self.custom_themes_dir, exist_ok=True)
        
        # 加载用户自定义主题
        self._load_user_themes()
        self.themes: Dict[str, str] = {
            "light": """ QWidget{background-color:#f0f0f0;color:#000000;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:white;border:1px solid #cccccc;} QPushButton{background-color:#e0e0e0;border:1px solid #adadad;padding:4px;} QPushButton:hover{background-color:#f0f0f0;} QPushButton:pressed{background-color:#cccccc;} QGroupBox{border:1px solid #c0c0c0;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;} QMenuBar{background-color:#e0e0e0;} QStatusBar{background-color:#e0e0e0;} QDockWidget::title{background-color:#d0d0d0;padding:4px;} QTabWidget::pane{border:1px solid #c0c0c0;} QTabBar::tab{background-color:#e0e0e0;padding:5px;border:1px solid #c0c0c0;border-bottom:none;} QTabBar::tab:selected{background-color:#f0f0f0;} """,
            "dark": """ QWidget{background-color:#2b2b2b;color:#ffffff;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:#3c3f41;color:#bbbbbb;border:1px solid #555555;} QPushButton{background-color:#555555;border:1px solid #666666;padding:4px;color:#ffffff;} QPushButton:hover{background-color:#656565;} QPushButton:pressed{background-color:#454545;} QGroupBox{border:1px solid #505050;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;color:#ffffff;} QMenuBar{background-color:#3c3f41;color:#ffffff;} QStatusBar{background-color:#3c3f41;color:#ffffff;} QDockWidget::title{background-color:#333333;padding:4px;color:white;} QTabWidget::pane{border:1px solid #505050;} QTabBar::tab{background-color:#3c3f41;padding:5px;border:1px solid #505050;border-bottom:none;color:white;} QTabBar::tab:selected{background-color:#2b2b2b;} """,
            "pink": """ QWidget{background-color:#fff0f5;color:#000000;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:#ffffff;color:#000000;border:1px solid #ff69b4;} QPushButton{background-color:#ffb6c1;border:1px solid #ff1493;padding:4px;color:#000000;} QPushButton:hover{background-color:#ffc0cb;} QPushButton:pressed{background-color:#ff69b4;} QGroupBox{border:1px solid #ff69b4;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;color:#ff1493;} QMenuBar{background-color:#ffb6c1;color:#000000;} QStatusBar{background-color:#ffb6c1;color:#000000;} QDockWidget::title{background-color:#ff69b4;padding:4px;color:#000000;} QTabWidget::pane{border:1px solid #ff69b4;} QTabBar::tab{background-color:#ffc0cb;padding:5px;border:1px solid #ff69b4;border-bottom:none;color:#000000;} QTabBar::tab:selected{background-color:#fff0f5;} """,
            "ocean": """ QWidget{background-color:#e6f7ff;color:#003366;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:#ffffff;color:#003366;border:1px solid #66b3ff;} QPushButton{background-color:#99ccff;border:1px solid #3399ff;padding:4px;color:#003366;} QPushButton:hover{background-color:#b3d9ff;} QPushButton:pressed{background-color:#66b3ff;} QGroupBox{border:1px solid #66b3ff;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;color:#0066cc;} QMenuBar{background-color:#99ccff;color:#003366;} QStatusBar{background-color:#99ccff;color:#003366;} QDockWidget::title{background-color:#66b3ff;padding:4px;color:#003366;} QTabWidget::pane{border:1px solid #66b3ff;} QTabBar::tab{background-color:#b3d9ff;padding:5px;border:1px solid #66b3ff;border-bottom:none;color:#003366;} QTabBar::tab:selected{background-color:#e6f7ff;} """,
            "forest": """ QWidget{background-color:#e8f5e9;color:#1b5e20;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:#ffffff;color:#1b5e20;border:1px solid #81c784;} QPushButton{background-color:#a5d6a7;border:1px solid #66bb6a;padding:4px;color:#1b5e20;} QPushButton:hover{background-color:#c8e6c9;} QPushButton:pressed{background-color:#81c784;} QGroupBox{border:1px solid #81c784;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;color:#2e7d32;} QMenuBar{background-color:#a5d6a7;color:#1b5e20;} QStatusBar{background-color:#a5d6a7;color:#1b5e20;} QDockWidget::title{background-color:#81c784;padding:4px;color:#1b5e20;} QTabWidget::pane{border:1px solid #81c784;} QTabBar::tab{background-color:#c8e6c9;padding:5px;border:1px solid #81c784;border-bottom:none;color:#1b5e20;} QTabBar::tab:selected{background-color:#e8f5e9;} """,
            "amethyst": """ QWidget{background-color:#f3e5f5;color:#4a148c;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:#ffffff;color:#4a148c;border:1px solid #ba68c8;} QPushButton{background-color:#ce93d8;border:1px solid #ab47bc;padding:4px;color:#4a148c;} QPushButton:hover{background-color:#e1bee7;} QPushButton:pressed{background-color:#ba68c8;} QGroupBox{border:1px solid #ba68c8;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;color:#7b1fa2;} QMenuBar{background-color:#ce93d8;color:#4a148c;} QStatusBar{background-color:#ce93d8;color:#4a148c;} QDockWidget::title{background-color:#ba68c8;padding:4px;color:#4a148c;} QTabWidget::pane{border:1px solid #ba68c8;} QTabBar::tab{background-color:#e1bee7;padding:5px;border:1px solid #ba68c8;border-bottom:none;color:#4a148c;} QTabBar::tab:selected{background-color:#f3e5f5;} """,
            "sunset": """ QWidget{background-color:#fff3e0;color:#e65100;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:#ffffff;color:#e65100;border:1px solid #ffb74d;} QPushButton{background-color:#ffcc80;border:1px solid #ff9800;padding:4px;color:#e65100;} QPushButton:hover{background-color:#ffe0b2;} QPushButton:pressed{background-color:#ffb74d;} QGroupBox{border:1px solid #ffb74d;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;color:#ef6c00;} QMenuBar{background-color:#ffcc80;color:#e65100;} QStatusBar{background-color:#ffcc80;color:#e65100;} QDockWidget::title{background-color:#ffb74d;padding:4px;color:#e65100;} QTabWidget::pane{border:1px solid #ffb74d;} QTabBar::tab{background-color:#ffe0b2;padding:5px;border:1px solid #ffb74d;border-bottom:none;color:#e65100;} QTabBar::tab:selected{background-color:#fff3e0;} """,
            "midnight": """ QWidget{background-color:#0a192f;color:#ccd6f6;} QLineEdit,QTextEdit,QComboBox,QPlainTextEdit{background-color:#172a45;color:#ccd6f6;border:1px solid #1f4068;} QPushButton{background-color:#1f4068;border:1px solid #1f4068;padding:4px;color:#ccd6f6;} QPushButton:hover{background-color:#2a4a7a;} QPushButton:pressed{background-color:#172a45;} QGroupBox{border:1px solid #1f4068;margin-top:0.5em;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px 0 3px;color:#64ffda;} QMenuBar{background-color:#172a45;color:#ccd6f6;} QStatusBar{background-color:#172a45;color:#ccd6f6;} QDockWidget::title{background-color:#1f4068;padding:4px;color:#ccd6f6;} QTabWidget::pane{border:1px solid #1f4068;} QTabBar::tab{background-color:#172a45;padding:5px;border:1px solid #1f4068;border-bottom:none;color:#ccd6f6;} QTabBar::tab:selected{background-color:#0a192f;} """,
            "custom_image_theme": """
                  QMainWindow {
                      background-image: url(./image.png); /* 替换为你的图片路径 */
                      background-repeat: no-repeat; /* 不重复平铺 */
                      background-position: center;  /* 居中显示，虽然拉伸后效果不明显但习惯性设置 */
                      background-attachment: fixed; /* 图片固定，不随内容滚动 */
                      background-size: 100% 100%; /* 关键：横向和纵向都拉伸到100% */
                  }
                  /* 你也可以为其他组件定义样式，例如让它们半透明以显示背景 */
                  QGroupBox, QWidget {
                      background-color: rgba(43, 43, 43, 0.5); /* 例如，深色半透明 */
                      color: #ffffff;
                  }
                  QLineEdit, QTextEdit, QComboBox, QPlainTextEdit {
                      background-color: rgba(60, 63, 65, 0.6);
                      color: #bbbbbb;
                      border: 1px solid #555555;
                  }
                  /* ... 其他你想要自定义的组件样式 ... */
              """,
        }
        self._current_theme_info: Dict[str, Optional[str]] = {"type": "internal", "name": "light", "path": None}


    @property
    def current_theme_info(self) -> Dict[str, Optional[str]]:
        return self._current_theme_info

    def apply_theme(self, theme_name: str) -> None:
        theme_content = None
        theme_type = "internal"
        
        # 检查预设主题
        if hasattr(self, 'preset_themes') and theme_name in self.preset_themes:
            theme_data = self.preset_themes[theme_name]
            theme_content = theme_data.get('css', theme_data) if isinstance(theme_data, dict) else theme_data
            theme_type = "preset"
        # 检查内置主题
        elif theme_name in self.themes:
            theme_content = self.themes[theme_name]
        # 检查用户自定义主题
        elif theme_name in self.user_themes:
            theme_data = self.user_themes[theme_name]
            theme_content = theme_data.get('css', theme_data) if isinstance(theme_data, dict) else theme_data
            theme_type = "user_custom"
        
        if theme_content:
            try:
                self.app.setStyleSheet(theme_content)
                self._current_theme_info = {"type": theme_type, "name": theme_name, "path": None}
                # 保存最后使用的主题
                self.settings.setValue("last_theme", theme_name)
                self.settings.setValue("last_theme_type", theme_type)
                
                # 发射主题变化信号
                self.theme_changed.emit(theme_name)
                
                if self.error_logger:
                    self.error_logger.log_info(f"主题已应用: {theme_name} ({theme_type})")
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(f"应用主题失败 '{theme_name}': {e}", "THEME")
        elif self.error_logger:
            self.error_logger.log_warning(f"未知主题: {theme_name}")

    def apply_external_qss(self, qss_file_path: str) -> None:
        """从外部QSS文件加载并应用样式表。"""
        try:
            with open(qss_file_path, 'r', encoding='utf-8') as f:
                qss_content = f.read()
            self.app.setStyleSheet(qss_content)
            self._current_theme_info = {"type": "external", "name": Path(qss_file_path).name, "path": qss_file_path} # Store name and path
            
            # 保存外部QSS文件路径到设置中，以便下次启动时恢复
            self.settings.setValue("last_theme", Path(qss_file_path).name)
            self.settings.setValue("last_theme_type", "external")
            self.settings.setValue("last_external_qss_path", qss_file_path)
            
            # 发射主题变化信号
            self.theme_changed.emit(Path(qss_file_path).name)
            
            if self.error_logger:
                self.error_logger.log_info(f"已从外部文件加载并应用QSS样式: {qss_file_path}")
        except FileNotFoundError:
            msg = f"QSS文件未找到: {qss_file_path}"
            # Assuming activeWindow() might not always be available or suitable here
            # Consider passing the main window reference if error dialogs are crucial from ThemeManager
            # For now, will rely on logger.
            if self.app.activeWindow(): # Check if an active window exists
                 QMessageBox.warning(self.app.activeWindow(), "错误", msg)
            if self.error_logger:
                self.error_logger.log_error(msg, "THEME_EXTERNAL_FILE")
        except Exception as e:
            msg = f"加载或应用外部QSS文件失败 '{qss_file_path}': {e}"
            if self.app.activeWindow():
                QMessageBox.critical(self.app.activeWindow(), "错误", msg)
            if self.error_logger:
                self.error_logger.log_error(msg, "THEME_EXTERNAL_LOAD")
    
    def _load_user_themes(self) -> None:
        """加载用户自定义主题"""
        try:
            themes_config_file = os.path.join(self.custom_themes_dir, "user_themes.json")
            if os.path.exists(themes_config_file):
                with open(themes_config_file, 'r', encoding='utf-8') as f:
                    self.user_themes = json.load(f)
                if self.error_logger:
                    self.error_logger.log_info(f"已加载 {len(self.user_themes)} 个用户自定义主题")
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"加载用户主题失败: {e}", "THEME_USER_LOAD")
        
        # 加载预设主题
        self._load_preset_themes()
    
    def _load_preset_themes(self) -> None:
        """加载预设主题"""
        preset_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'theme_presets.json')
        if os.path.exists(preset_file):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    preset_data = json.load(f)
                    self.preset_themes = preset_data.get('theme_presets', {})
                    self.theme_categories = preset_data.get('theme_categories', {})
                    self.theme_settings = preset_data.get('theme_settings', {})
                if self.error_logger:
                    self.error_logger.log_info(f"已加载 {len(self.preset_themes)} 个预设主题")
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(f"加载预设主题失败: {e}", "THEME_PRESET_LOAD")
                self.preset_themes = {}
                self.theme_categories = {}
                self.theme_settings = {}
        else:
            self.preset_themes = {}
            self.theme_categories = {}
            self.theme_settings = {}
    
    def _save_user_themes(self) -> None:
        """保存用户自定义主题"""
        try:
            themes_config_file = os.path.join(self.custom_themes_dir, "user_themes.json")
            with open(themes_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_themes, f, ensure_ascii=False, indent=2)
            if self.error_logger:
                self.error_logger.log_info("用户主题已保存")
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"保存用户主题失败: {e}", "THEME_USER_SAVE")
    
    def get_all_themes(self) -> Dict[str, str]:
        """获取所有可用主题（内置+预设+用户自定义）"""
        all_themes = {}
        # 添加内置主题
        for name in self.themes.keys():
            all_themes[name] = "内置主题"
        # 添加预设主题
        for name in self.preset_themes.keys():
            all_themes[name] = "预设主题"
        # 添加用户自定义主题
        for name in self.user_themes.keys():
            all_themes[name] = "自定义主题"
        return all_themes
    
    def get_themes_by_category(self, category: str = None) -> List[str]:
        """根据分类获取主题列表"""
        if category and hasattr(self, 'theme_categories') and category in self.theme_categories:
            return self.theme_categories[category]
        return list(self.get_all_themes().keys())
    
    def get_theme_info(self, theme_name: str) -> Dict[str, Any]:
        """获取主题详细信息"""
        # 检查预设主题
        if hasattr(self, 'preset_themes') and theme_name in self.preset_themes:
            theme_data = self.preset_themes[theme_name].copy()
            theme_data['type'] = 'preset'
            theme_data['category'] = self._get_theme_category(theme_name)
            return theme_data
        
        # 检查用户自定义主题
        if theme_name in self.user_themes:
            theme_data = self.user_themes[theme_name].copy()
            theme_data['type'] = 'custom'
            return theme_data
        
        # 内置主题
        if theme_name in self.themes:
            return {
                'name': theme_name,
                'type': 'builtin',
                'description': f'内置主题: {theme_name}'
            }
        
        return {}
    
    def _get_theme_category(self, theme_name: str) -> str:
        """获取主题所属分类"""
        if hasattr(self, 'theme_categories'):
            for category, themes in self.theme_categories.items():
                if theme_name in themes:
                    return category
        return 'other'
    
    def create_custom_theme(self, theme_name: str, base_theme: str = "dark") -> str:
        """创建自定义主题，返回主题内容用于编辑"""
        if base_theme in self.themes:
            base_content = self.themes[base_theme]
        elif base_theme in self.user_themes:
            base_content = self.user_themes[base_theme]
        else:
            base_content = self.themes["dark"]  # 默认使用深色主题
        
        # 如果主题名已存在，添加数字后缀
        original_name = theme_name
        counter = 1
        while theme_name in self.themes or theme_name in self.user_themes:
            theme_name = f"{original_name}_{counter}"
            counter += 1
        
        self.user_themes[theme_name] = base_content
        self._save_user_themes()
        self.theme_list_updated.emit()
        
        if self.error_logger:
            self.error_logger.log_info(f"已创建自定义主题: {theme_name}")
        
        return base_content
    
    def update_custom_theme(self, theme_name: str, theme_content: str) -> bool:
        """更新自定义主题内容"""
        if theme_name not in self.user_themes:
            return False
        
        try:
            self.user_themes[theme_name] = theme_content
            self._save_user_themes()
            
            # 如果当前正在使用这个主题，立即应用更新
            if (self._current_theme_info.get("name") == theme_name and 
                self._current_theme_info.get("type") == "user_custom"):
                self.app.setStyleSheet(theme_content)
                self.theme_changed.emit(theme_name)
            
            if self.error_logger:
                self.error_logger.log_info(f"已更新自定义主题: {theme_name}")
            return True
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"更新自定义主题失败 '{theme_name}': {e}", "THEME_UPDATE")
            return False
    
    def delete_custom_theme(self, theme_name: str) -> bool:
        """删除自定义主题"""
        if theme_name not in self.user_themes:
            return False
        
        try:
            del self.user_themes[theme_name]
            self._save_user_themes()
            self.theme_list_updated.emit()
            
            # 如果当前正在使用被删除的主题，切换到默认主题
            if (self._current_theme_info.get("name") == theme_name and 
                self._current_theme_info.get("type") == "user_custom"):
                self.apply_theme("light")
            
            if self.error_logger:
                self.error_logger.log_info(f"已删除自定义主题: {theme_name}")
            return True
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"删除自定义主题失败 '{theme_name}': {e}", "THEME_DELETE")
            return False
    
    def export_theme(self, theme_name: str, file_path: str) -> bool:
        """导出主题到文件"""
        theme_content = None
        if theme_name in self.themes:
            theme_content = self.themes[theme_name]
        elif theme_name in self.user_themes:
            theme_content = self.user_themes[theme_name]
        
        if not theme_content:
            return False
        
        try:
            theme_data = {
                "name": theme_name,
                "version": "1.0",
                "author": "YJ Studio User",
                "description": f"Exported theme: {theme_name}",
                "content": theme_content
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(theme_data, f, ensure_ascii=False, indent=2)
            
            if self.error_logger:
                self.error_logger.log_info(f"主题已导出: {theme_name} -> {file_path}")
            return True
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"导出主题失败 '{theme_name}': {e}", "THEME_EXPORT")
            return False
    
    def import_theme(self, file_path: str) -> Optional[str]:
        """从文件导入主题，返回导入的主题名称"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                theme_data = json.load(f)
            
            theme_name = theme_data.get("name", "imported_theme")
            theme_content = theme_data.get("content", "")
            
            if not theme_content:
                if self.error_logger:
                    self.error_logger.log_error("导入的主题文件内容为空", "THEME_IMPORT")
                return None
            
            # 确保主题名唯一
            original_name = theme_name
            counter = 1
            while theme_name in self.themes or theme_name in self.user_themes:
                theme_name = f"{original_name}_{counter}"
                counter += 1
            
            self.user_themes[theme_name] = theme_content
            self._save_user_themes()
            self.theme_list_updated.emit()
            
            if self.error_logger:
                self.error_logger.log_info(f"主题已导入: {theme_name}")
            return theme_name
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"导入主题失败: {e}", "THEME_IMPORT")
            return None
    
    def get_theme_content(self, theme_name: str) -> Optional[str]:
        """获取主题内容"""
        if theme_name in self.themes:
            return self.themes[theme_name]
        elif theme_name in self.user_themes:
            return self.user_themes[theme_name]
        return None
    
    def restore_last_theme(self) -> None:
        """恢复上次使用的主题"""
        last_theme = self.settings.value("last_theme", "light")
        last_theme_type = self.settings.value("last_theme_type", "internal")
        
        if last_theme_type == "external":
            # 恢复外部QSS文件
            last_external_qss_path = self.settings.value("last_external_qss_path", "")
            if last_external_qss_path and os.path.exists(last_external_qss_path):
                try:
                    self.apply_external_qss(last_external_qss_path)
                    if self.error_logger:
                        self.error_logger.log_info(f"已恢复外部QSS主题: {last_external_qss_path}")
                    return
                except Exception as e:
                    if self.error_logger:
                        self.error_logger.log_error(f"恢复外部QSS主题失败: {e}", "THEME_RESTORE")
                    # 如果外部QSS文件加载失败，继续使用默认主题
            else:
                if self.error_logger:
                    self.error_logger.log_warning(f"外部QSS文件不存在或路径为空: {last_external_qss_path}")
        elif last_theme_type == "preset" and hasattr(self, 'preset_themes') and last_theme in self.preset_themes:
            self.apply_theme(last_theme)
        elif last_theme_type == "internal" and last_theme in self.themes:
            self.apply_theme(last_theme)
        elif last_theme_type == "user_custom" and last_theme in self.user_themes:
            self.apply_theme(last_theme)
        else:
            self.apply_theme("light")  # 默认主题
    
    def generate_theme_from_colors(self, primary_color: QColor, secondary_color: QColor, 
                                 background_color: QColor, text_color: QColor) -> str:
        """根据颜色生成主题CSS"""
        primary_hex = primary_color.name()
        secondary_hex = secondary_color.name()
        background_hex = background_color.name()
        text_hex = text_color.name()
        
        # 生成渐变色
        primary_light = primary_color.lighter(120).name()
        primary_dark = primary_color.darker(120).name()
        secondary_light = secondary_color.lighter(110).name()
        
        theme_template = f"""
        QWidget {{
            background-color: {background_hex};
            color: {text_hex};
            font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
        }}
        
        QLineEdit, QTextEdit, QComboBox, QPlainTextEdit {{
            background-color: {secondary_hex};
            color: {text_hex};
            border: 1px solid {primary_hex};
            border-radius: 4px;
            padding: 4px;
        }}
        
        QPushButton {{
            background-color: {primary_hex};
            border: 1px solid {primary_dark};
            padding: 6px 12px;
            color: {text_hex};
            border-radius: 4px;
        }}
        
        QPushButton:hover {{
            background-color: {primary_light};
        }}
        
        QPushButton:pressed {{
            background-color: {primary_dark};
        }}
        
        QGroupBox {{
            border: 1px solid {primary_hex};
            margin-top: 0.5em;
            border-radius: 4px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
            color: {primary_hex};
        }}
        
        QMenuBar {{
            background-color: {secondary_hex};
            color: {text_hex};
        }}
        
        QStatusBar {{
            background-color: {secondary_hex};
            color: {text_hex};
        }}
        
        QDockWidget::title {{
            background-color: {secondary_light};
            padding: 4px;
            color: {text_hex};
        }}
        
        QTabWidget::pane {{
            border: 1px solid {primary_hex};
        }}
        
        QTabBar::tab {{
            background-color: {secondary_hex};
            padding: 5px;
            border: 1px solid {primary_hex};
            border-bottom: none;
            color: {text_hex};
        }}
        
        QTabBar::tab:selected {{
            background-color: {background_hex};
        }}
        """
        
        return theme_template.strip()