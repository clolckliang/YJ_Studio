from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QApplication, QMessageBox

class ThemeManager:
    def __init__(self, app: QApplication, error_logger: Optional[Any] = None): # ErrorLogger type hint
        self.app = app
        self.error_logger = error_logger # from utils.logger
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
        if theme_name in self.themes:
            try:
                self.app.setStyleSheet(self.themes[theme_name])
                self._current_theme_info = {"type": "internal", "name": theme_name, "path": None}
                if self.error_logger:
                    self.error_logger.log_info(f"主题已应用: {theme_name}")
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