import pytest
import sys
import os
from unittest.mock import MagicMock, patch, mock_open
from PySide6.QtWidgets import QApplication, QMainWindow

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ui.theme_manager import ThemeManager

@pytest.fixture
def mock_app():
    app = QApplication.instance() or QApplication([])
    yield app
    # app.quit()  # 避免影响其他测试

@pytest.fixture 
def mock_main_window():
    return MagicMock(spec=QMainWindow)

@pytest.fixture
def theme_manager(mock_main_window):
    return ThemeManager(mock_main_window)

class TestThemeManager:
    def test_initialization(self, theme_manager, mock_main_window):
        assert theme_manager.main_window == mock_main_window
        assert theme_manager.current_theme == "light"
        assert isinstance(theme_manager.available_themes, dict)
        assert "light" in theme_manager.available_themes
        assert "dark" in theme_manager.available_themes

    def test_switch_theme(self, theme_manager, mock_main_window):
        # 测试切换到暗色主题
        with patch.object(theme_manager, 'load_theme_stylesheet') as mock_load:
            theme_manager.switch_theme("dark")
            assert theme_manager.current_theme == "dark"
            mock_load.assert_called_once()
            mock_main_window.setStyleSheet.assert_called_once()

        # 测试切换到无效主题
        with patch.object(theme_manager, 'load_theme_stylesheet') as mock_load:
            theme_manager.switch_theme("invalid")
            assert theme_manager.current_theme == "light"  # 应回退到默认
            mock_load.assert_not_called()

    @patch("builtins.open", mock_open(read_data="QWidget { background: white; }"))
    def test_load_theme_stylesheet_internal(self, theme_manager):
        # 测试加载内置主题
        stylesheet = theme_manager.load_theme_stylesheet("light")
        assert "QWidget { background: white; }" in stylesheet

    @patch("builtins.open", mock_open(read_data="QWidget { background: black; }")) 
    def test_load_theme_stylesheet_custom(self, theme_manager, tmp_path):
        # 测试加载自定义主题文件
        custom_theme = tmp_path / "custom.qss"
        custom_theme.write_text("QWidget { background: black; }")
        
        theme_manager.available_themes["custom"] = {
            "type": "file",
            "path": str(custom_theme)
        }
        
        stylesheet = theme_manager.load_theme_stylesheet("custom")
        assert "QWidget { background: black; }" in stylesheet

    def test_get_current_theme(self, theme_manager):
        theme_manager.current_theme = "dark"
        assert theme_manager.get_current_theme() == "dark"

    def test_get_available_themes(self, theme_manager):
        themes = theme_manager.get_available_themes()
        assert isinstance(themes, list)
        assert "light" in themes
        assert "dark" in themes
