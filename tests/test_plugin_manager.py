import pytest
import sys
import os
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.plugin_manager import PluginManager
from core.panel_interface import PanelInterface

# 创建测试面板类
class TestPanel(PanelInterface):
    PANEL_TYPE_NAME = "test_panel"
    PANEL_DISPLAY_NAME = "Test Panel"
    
    def get_config(self):
        return {}
        
    def apply_config(self, config):
        pass
        
    def get_initial_dock_title(self):
        return "Test Panel"

@pytest.fixture
def plugin_manager():
    return PluginManager()

class TestPluginManager:
    def test_initialization(self, plugin_manager):
        assert plugin_manager.registered_panel_types == {}
        assert plugin_manager.discovered_plugin_modules == {}
        assert plugin_manager.session_blocklisted_modules == set()

    def test_register_panel_type(self, plugin_manager):
        plugin_manager.register_panel_type(TestPanel, module_name="test_module")
        assert "test_panel" in plugin_manager.registered_panel_types
        panel_info = plugin_manager.registered_panel_types["test_panel"]
        assert panel_info[0] == TestPanel
        assert panel_info[1] == "Test Panel"
        assert panel_info[2] == "test_module"

    def test_discover_plugins(self, plugin_manager, tmp_path):
        # 创建测试插件目录结构
        plugin_dir = tmp_path / "panel_plugins"
        plugin_dir.mkdir()
        (plugin_dir / "test_plugin").mkdir()
        (plugin_dir / "test_plugin" / "__init__.py").write_text("""
from core.panel_interface import PanelInterface

class TestPluginPanel(PanelInterface):
    PANEL_TYPE_NAME = "test_plugin_panel"
    PANEL_DISPLAY_NAME = "Test Plugin Panel"
    
    def get_config(self):
        return {}
        
    def apply_config(self, config):
        pass
        
    def get_initial_dock_title(self):
        return "Test Plugin Panel"
""")

        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.TestPluginPanel = TestPanel
            mock_import.return_value = mock_module
            
            plugin_manager.discover_plugins(str(plugin_dir))
            
            assert "test_plugin" in plugin_manager.discovered_plugin_modules
            mock_import.assert_called_once_with("panel_plugins.test_plugin")

    def test_create_panel_instance(self, plugin_manager):
        plugin_manager.register_panel_type(TestPanel, module_name="test_module")
        
        panel = plugin_manager.create_panel_instance(
            "test_panel", 
            panel_id=1,
            initial_config={},
            main_window_ref=MagicMock()
        )
        
        assert isinstance(panel, TestPanel)
        assert panel.panel_id == 1

    def test_get_creatable_panel_types(self, plugin_manager):
        plugin_manager.register_panel_type(TestPanel, module_name="test_module")
        
        panel_types = plugin_manager.get_creatable_panel_types()
        assert "test_panel" in panel_types
        assert panel_types["test_panel"] == "Test Panel"

    def test_block_unblock_module(self, plugin_manager):
        plugin_manager.block_module_for_session("test_module")
        assert "test_module" in plugin_manager.session_blocklisted_modules
        
        plugin_manager.unblock_module_for_session("test_module")
        assert "test_module" not in plugin_manager.session_blocklisted_modules

    def test_get_panel_type_from_instance(self, plugin_manager):
        plugin_manager.register_panel_type(TestPanel, module_name="test_module")
        panel = TestPanel(panel_id=1, main_window_ref=MagicMock())
        
        panel_type = plugin_manager.get_panel_type_from_instance(panel)
        assert panel_type == "test_panel"
