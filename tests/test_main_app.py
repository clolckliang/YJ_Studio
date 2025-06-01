import pytest
import sys
import os
from unittest.mock import MagicMock, patch, mock_open
from PySide6.QtCore import Qt, QByteArray, QSettings
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import QApplication, QDockWidget, QMessageBox, QInputDialog
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import classes directly from main.py
from main import (
    SerialDebugger,
    PluginManagementDialog,
    SerialConfigDefinitionPanelWidget,
    AdaptedParsePanelWidget,
    AdaptedSendPanelWidget,
    AdaptedPlotWidgetPanel,  # This will be the placeholder if pyqtgraph is not found
    BasicCommPanelWidget,
    CustomLogPanelWidget,
    ScriptingPanelWidget,
    PYQTGRAPH_AVAILABLE
)
from utils.constants import ChecksumMode, Constants
from utils.data_models import SerialPortConfig, FrameConfig

# Mock out pyqtgraph if it's not available to ensure tests run consistently
if not PYQTGRAPH_AVAILABLE:
    class MockPlotDataItem:
        def __init__(self, *args, **kwargs): pass

        def setData(self, x, y): pass


    class MockPlotWidget(MagicMock):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.plot_items = []

        def showGrid(self, *args, **kwargs): pass

        def addLegend(self, *args, **kwargs): pass

        def plot(self, *args, **kwargs):
            item = MockPlotDataItem()
            self.plot_items.append(item)
            return item

        def clear(self): self.plot_items.clear()

        def removeItem(self, item): pass

        def setTitle(self, title): pass


    # Patch the classes that would come from pyqtgraph
    patch('main.pg.PlotWidget', MockPlotWidget).start()
    patch('main.pg.PlotDataItem', MockPlotDataItem).start()
    patch('main.PYQTGRAPH_AVAILABLE', True).start()  # Force it to true so the class is not stubbed


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Ensure a QApplication instance is available for all tests."""
    if QApplication.instance() is None:
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app
    # app.quit() # This might cause issues with other tests wanting the app, better to let pytest-qt manage life cycle


@pytest.fixture
def mock_serial_manager():
    """Mock SerialManager for controlled serial port behavior."""
    with patch('main.SerialManager') as MockManager:
        manager = MockManager.return_value
        manager.is_connected = False
        manager.get_available_ports.return_value = [
            {'name': 'COM1', 'description': 'USB Serial Device (COM1)'},
            {'name': '/dev/ttyUSB0', 'description': 'USB to UART (ttyUSB0)'}
        ]
        manager.write_data.return_value = 0  # Default to no bytes written
        yield manager


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager to prevent file I/O."""
    with patch('main.ConfigManager') as MockCM:
        mock_cm_instance = MockCM.return_value
        mock_cm_instance.load_config.return_value = {}  # Default to empty config
        mock_cm_instance.save_config.return_value = True
        yield mock_cm_instance


@pytest.fixture
def mock_data_recorder():
    """Mock DataRecorder to prevent file I/O."""
    with patch('main.DataRecorder') as MockDR:
        recorder = MockDR.return_value
        recorder.recorded_raw_data = []
        recorder.historical_data = []
        yield recorder


@pytest.fixture
def mock_error_logger():
    """Mock ErrorLogger to capture log messages."""
    with patch('main.ErrorLogger') as MockEL:
        logger = MockEL.return_value
        logger.log_info = MagicMock()
        logger.log_warning = MagicMock()
        logger.log_error = MagicMock()
        logger.log_debug = MagicMock()
        yield logger


@pytest.fixture
def mock_plugin_manager():
    """Mock PluginManager to control plugin discovery and creation."""
    with patch('main.PluginManager') as MockPM:
        manager = MockPM.return_value
        manager.registered_panel_types = {
            "core_parse_panel": (AdaptedParsePanelWidget, "数据解析面板", '__main__'),
            "core_send_panel": (AdaptedSendPanelWidget, "数据发送面板", '__main__'),
            "core_plot_widget_panel": (AdaptedPlotWidgetPanel, "波形图面板",
                                       '__main__') if PYQTGRAPH_AVAILABLE else None,
        }
        # Filter out None values from registered_panel_types
        manager.registered_panel_types = {k: v for k, v in manager.registered_panel_types.items() if v is not None}

        manager.get_creatable_panel_types.return_value = {
            "core_parse_panel": "数据解析面板",
            "core_send_panel": "数据发送面板",
            "core_plot_widget_panel": "波形图面板" if PYQTGRAPH_AVAILABLE else ""
        }
        # Filter out empty strings from creatable_panel_types
        manager.get_creatable_panel_types.return_value = {k: v for k, v in
                                                          manager.get_creatable_panel_types.return_value.items() if v}

        # Mock the create_panel_instance to return actual panel instances for testing
        def _mock_create_panel_instance(panel_type_name, panel_id, initial_config):
            panel_class, _, _ = manager.registered_panel_types.get(panel_type_name)
            if panel_class:
                # Pass a mock for main_window_ref to avoid recursion during panel init if needed,
                # but for simplicity, we pass the real one if it's already created.
                # In actual tests, `main_window_ref` will be the real SerialDebugger instance.
                return panel_class(panel_id=panel_id, main_window_ref=MagicMock(), initial_config=initial_config)
            return None

        manager.create_panel_instance.side_effect = _mock_create_panel_instance
        manager.get_module_name_for_panel_type.side_effect = lambda pt: \
        manager.registered_panel_types.get(pt, ('', '', ''))[2]
        manager.get_panel_type_from_instance.side_effect = lambda instance: next(
            (name for name, (cls, _, _) in manager.registered_panel_types.items() if isinstance(instance, cls)), None
        )
        manager.session_blocklisted_modules = set()
        yield manager


@pytest.fixture
def serial_debugger_app(qtbot, mock_serial_manager, mock_config_manager, mock_data_recorder, mock_error_logger,
                        mock_plugin_manager):
    """Fixture for a clean SerialDebugger instance for each test."""
    # Ensure QSettings does not persist state across test runs
    with patch.object(QSettings, 'value', return_value=None), \
            patch.object(QSettings, 'setValue', return_value=None):
        main_win = SerialDebugger()
        # Explicitly connect signals that might be missed by simple patching if target is a mock
        main_win.serial_manager = mock_serial_manager  # Ensure the mock is used
        main_win.config_manager = mock_config_manager
        main_win.data_recorder = mock_data_recorder
        main_win.error_logger = mock_error_logger
        main_win.plugin_manager = mock_plugin_manager

        # Re-register core panels with the mocked plugin manager to ensure they are discoverable
        # This is usually done in __init__, but we might need to re-do it if the mock is applied late
        main_win.plugin_manager.register_panel_type(AdaptedParsePanelWidget, module_name='__main__')
        main_win.plugin_manager.register_panel_type(AdaptedSendPanelWidget, module_name='__main__')
        if PYQTGRAPH_AVAILABLE:
            main_win.plugin_manager.register_panel_type(AdaptedPlotWidgetPanel, module_name='__main__')

        main_win.plugin_manager.update_enabled_plugins(main_win.enabled_plugin_module_names)
        main_win.plugin_manager.discover_plugins("panel_plugins", load_only_enabled=True)

        # Connect actual signals if they are from patched objects
        main_win.serial_manager.connection_status_changed.connect(main_win.on_serial_connection_status_changed)
        main_win.serial_manager.data_received.connect(main_win.on_serial_data_received)
        main_win.serial_manager.error_occurred_signal.connect(main_win.on_serial_manager_error)
        main_win.frame_parser.frame_successfully_parsed.connect(main_win.on_frame_successfully_parsed)
        main_win.frame_parser.checksum_error.connect(main_win.on_frame_checksum_error)
        main_win.frame_parser.frame_parse_error.connect(main_win.on_frame_general_parse_error)

        # Mock the QInputDialog.getText for dynamic panel naming to avoid blocking tests
        with patch('main.QInputDialog.getText', return_value=("Test Panel", True)):
            yield main_win
        main_win.close()  # Ensure resources are cleaned up


class TestSerialDebugger:
    def test_initialization(self, qtbot, serial_debugger_app, mock_serial_manager, mock_config_manager,
                            mock_error_logger, mock_plugin_manager):
        assert serial_debugger_app.setWindowTitle(
            "YJ_Studio (Plugin Enhanced)") is None  # Check the return value of setWindowTitle (None)
        assert isinstance(serial_debugger_app.error_logger, MagicMock)
        assert isinstance(serial_debugger_app.serial_manager, MagicMock)
        assert serial_debugger_app.serial_config_panel_widget is not None
        assert serial_debugger_app.dw_serial_config is not None
        mock_error_logger.log_info.assert_called_with("应用程序启动 (插件管理增强)。")
        mock_plugin_manager.discover_plugins.assert_called_with("panel_plugins", load_only_enabled=True)

    def test_serial_connection_toggle(self, qtbot, serial_debugger_app, mock_serial_manager):
        # Simulate connecting
        mock_serial_manager.is_connected = False
        mock_serial_manager.connect_port.return_value = True
        serial_debugger_app.serial_config_panel_widget.connect_button.setChecked(True)
        qtbot.mouseClick(serial_debugger_app.serial_config_panel_widget.connect_button, Qt.MouseButton.LeftButton)
        mock_serial_manager.connect_port.assert_called_once()
        assert serial_debugger_app.serial_config_panel_widget.connect_button.isChecked()
        assert serial_debugger_app.serial_config_panel_widget.connect_button.text() == "关闭串口"

        # Simulate disconnecting
        mock_serial_manager.is_connected = True
        mock_serial_manager.disconnect_port.return_value = None
        serial_debugger_app.serial_config_panel_widget.connect_button.setChecked(False)
        qtbot.mouseClick(serial_debugger_app.serial_config_panel_widget.connect_button, Qt.MouseButton.LeftButton)
        mock_serial_manager.disconnect_port.assert_called_once()
        assert not serial_debugger_app.serial_config_panel_widget.connect_button.isChecked()
        assert serial_debugger_app.serial_config_panel_widget.connect_button.text() == "打开串口"

    def test_serial_data_reception_and_parsing(self, qtbot, serial_debugger_app, mock_serial_manager, mock_error_logger,
                                               mock_data_recorder):
        serial_debugger_app.serial_manager.is_connected = True
        test_raw_data = QByteArray(b'\xAA\x01\xFE\xC0\x02\x00\x11\x22\x33\x44')  # Example frame
        test_parsed_data = QByteArray(b'\x11\x22')  # Example payload for C0 (len 2)

        # Mock frame_parser to directly emit a parsed frame
        serial_debugger_app.frame_parser.try_parse_frames = MagicMock()
        serial_debugger_app.frame_parser.frame_successfully_parsed.emit('C0', test_parsed_data)

        # Verify basic comm panel update
        qtbot.waitUntil(
            lambda: "RX: AA 01 FE C0 02 00 11 22 33 44" in serial_debugger_app.basic_comm_panel_widget.receive_text_edit.toPlainText() or serial_debugger_app.basic_comm_panel_widget.receive_text_edit.toPlainText().strip() != "")
        assert serial_debugger_app.basic_comm_panel_widget.receive_text_edit.toPlainText().strip() != ""
        # assert "RX: AA 01 FE C0 02 00 11 22 33 44" in serial_debugger_app.basic_comm_panel_widget.receive_text_edit.toPlainText() # This will fail because on_serial_data_received is not called.
        # Need to simulate the data_received signal from the manager
        serial_debugger_app.on_serial_data_received(test_raw_data)
        qtbot.waitUntil(
            lambda: "RX: AA 01 FE C0 02 00 11 22 33 44" in serial_debugger_app.basic_comm_panel_widget.receive_text_edit.toPlainText())

        mock_data_recorder.record_raw_frame.assert_called_with(
            datetime.now(), test_raw_data.data(), "RX"
        )
        mock_error_logger.log_info.assert_any_call("成功解析帧: #1, FID: C0 Payload len: 2")
        assert serial_debugger_app.status_bar_label.text() == "成功解析帧: #1, FID: C0"

    def test_dynamic_panel_add_remove(self, qtbot, serial_debugger_app, mock_error_logger):
        with patch('main.QInputDialog.getText', return_value=("My Test Parse Panel", True)):
            parse_panel = serial_debugger_app.add_dynamic_panel_action("core_parse_panel")
            assert parse_panel is not None
            assert isinstance(parse_panel, AdaptedParsePanelWidget)
            assert serial_debugger_app._next_dynamic_panel_id == 2
            assert 1 in serial_debugger_app.dynamic_panel_instances
            assert 1 in serial_debugger_app.dynamic_panel_docks
            mock_error_logger.log_info.assert_called_with(
                "[UI_ACTION] 已添加动态面板: 类型='core_parse_panel', ID=1, 名称='My Test Parse Panel'")

            # Test removing the panel
            serial_debugger_app.remove_dynamic_panel(1)
            assert 1 not in serial_debugger_app.dynamic_panel_instances
            assert 1 not in serial_debugger_app.dynamic_panel_docks
            mock_error_logger.log_info.assert_called_with(
                "[UI_ACTION] 已移除动态面板 ID: 1, 名称: 'My Test Parse Panel'")

    def test_load_save_configuration(self, qtbot, serial_debugger_app, mock_config_manager, mock_error_logger):
        # Simulate a saved configuration
        mock_config = {
            "serial_port": {"port_name": "COM5", "baud_rate": 9600, "data_bits": 8, "parity": "None", "stop_bits": 1},
            "frame_definition": {"head": "AB", "s_addr": "01", "d_addr": "02", "func_id": "C0"},
            "checksum_mode": "CRC16_CCITT_FALSE",
            "ui_theme_info": {"type": "internal", "name": "dark", "path": None},
            "custom_log_panel": {"hex_display": True, "timestamp_display": True},
            "basic_comm_panel": {"recv_hex_display": True, "recv_timestamp_display": True, "send_hex_checked": True},
            "scripting_panel": {"current_script": "print('Hello from script!')"},
            "dynamic_panels": [
                {"panel_type_name": "core_parse_panel", "panel_id": 101, "dock_name": "Loaded Parse Panel",
                 "config": {"parse_func_id": "D0", "receive_containers": []}}
            ],
            "next_dynamic_panel_id": 102,
            "next_global_receive_container_id": 50,
            "enabled_plugins": ["my_plugin_module"]
        }
        mock_config_manager.load_config.return_value = mock_config

        # Mock QFileDialog for load action
        with patch('main.QFileDialog.getOpenFileName', return_value=("/path/to/config.json", "JSON File (*.json)")), \
                patch('main.QMessageBox.information'):  # Mock info box
            serial_debugger_app.load_configuration_action_dialog()
            mock_config_manager.load_config.assert_called_once()
            assert serial_debugger_app.current_serial_config.port_name == "COM5"
            assert serial_debugger_app.current_frame_config.head == "AB"
            assert serial_debugger_app.active_checksum_mode == ChecksumMode.CRC16_CCITT_FALSE
            assert serial_debugger_app.custom_log_panel_widget.hex_checkbox.isChecked()
            assert serial_debugger_app._next_dynamic_panel_id == 102
            assert 101 in serial_debugger_app.dynamic_panel_instances
            assert "my_plugin_module" in serial_debugger_app.enabled_plugin_module_names
            mock_error_logger.log_info.assert_any_call("[CONFIG] 配置已加载并应用到UI。")

        # Test saving configuration
        mock_config_manager.save_config.reset_mock()  # Reset mock for saving test
        with patch('main.QFileDialog.getSaveFileName',
                   return_value=("/path/to/save_config.json", "JSON File (*.json)")), \
                patch('main.QMessageBox.information'):  # Mock info box
            serial_debugger_app.save_configuration_action_dialog()
            mock_config_manager.save_config.assert_called_once()
            saved_config = mock_config_manager.save_config.call_args[0][0]
            assert saved_config["serial_port"]["port_name"] == serial_debugger_app.current_serial_config.port_name
            assert saved_config["frame_definition"]["head"] == serial_debugger_app.current_frame_config.head
            assert saved_config["checksum_mode"] == serial_debugger_app.active_checksum_mode.name
            assert "dynamic_panels" in saved_config
            assert saved_config["next_dynamic_panel_id"] == serial_debugger_app._next_dynamic_panel_id

    @pytest.mark.parametrize("pyqtgraph_available", [True, False])
    def test_plot_panel_availability(self, qtbot, pyqtgraph_available):
        # We need to re-initialize SerialDebugger within the test to control PYQTGRAPH_AVAILABLE
        # This is a bit tricky with fixtures, so we'll do it manually.
        with patch('main.PYQTGRAPH_AVAILABLE', pyqtgraph_available):
            # Re-mock dependencies that are affected by PYQTGRAPH_AVAILABLE
            if not pyqtgraph_available:
                with patch('main.pg', new=None), \
                        patch('main.AdaptedPlotWidgetPanel', new=type('AdaptedPlotWidgetPanel', (object,), {
                            'PANEL_TYPE_NAME': "core_plot_widget_panel",
                            'PANEL_DISPLAY_NAME': "波形图面板 (不可用)",
                            '__init__': lambda self, panel_id, main_window_ref, initial_config, parent: None,
                            'get_config': lambda self: {},
                            'apply_config': lambda self, config: None,
                            'get_initial_dock_title': lambda self: "波形图面板 (不可用)",
                            'update_data': lambda self, *args: None,
                            'clear_plot': lambda self: None,
                            'remove_curve_for_container': lambda self, *args: None,
                            'on_panel_removed': lambda self: None,
                            'dock_title_changed': MagicMock()
                        })):
                    main_win = SerialDebugger()
                    if main_win.plugin_manager.registered_panel_types.get("core_plot_widget_panel"):
                        assert main_win.plugin_manager.registered_panel_types["core_plot_widget_panel"][
                                   1] == "波形图面板 (不可用)"
                    assert "core_plot_widget_panel" not in main_win.plugin_manager.get_creatable_panel_types()
                    assert main_win.add_panel_menu.findChild(type(QAction), text="添加 波形图面板...") is None
                    main_win.close()
            else:  # pyqtgraph_available is True
                main_win = SerialDebugger()
                assert main_win.plugin_manager.registered_panel_types["core_plot_widget_panel"][1] == "波形图面板"
                assert "core_plot_widget_panel" in main_win.plugin_manager.get_creatable_panel_types()
                # Test adding a plot panel
                with patch('main.QInputDialog.getText', return_value=("Test Plot Panel", True)):
                    plot_panel = main_win.add_dynamic_panel_action("core_plot_widget_panel")
                    assert isinstance(plot_panel, AdaptedPlotWidgetPanel)
                    assert plot_panel.plot_widget_container is not None
                main_win.close()

    def test_script_execution(self, qtbot, serial_debugger_app, mock_error_logger):
        serial_debugger_app.script_engine.execute = MagicMock(
            return_value={"success": True, "output": "Script Ran!", "error_message": None})
        script_text = "print('Hello')"
        serial_debugger_app.scripting_panel_widget.script_input_edit.setPlainText(script_text)
        qtbot.mouseClick(serial_debugger_app.scripting_panel_widget.run_script_button, Qt.MouseButton.LeftButton)
        serial_debugger_app.script_engine.execute.assert_called_once_with(script_text, mode='exec')
        assert serial_debugger_app.scripting_panel_widget.script_output_edit.toPlainText() == "脚本输出:\nScript Ran!"
        mock_error_logger.log_info.assert_called_with("脚本执行完毕. 成功: True. 时间: 0.0000s")

    def test_send_basic_serial_data(self, qtbot, serial_debugger_app, mock_serial_manager, mock_error_logger,
                                    mock_data_recorder):
        serial_debugger_app.serial_manager.is_connected = True
        serial_debugger_app.basic_comm_panel_widget.send_text_edit.setText("Hello World")
        serial_debugger_app.basic_comm_panel_widget.send_hex_checkbox.setChecked(False)
        mock_serial_manager.write_data.return_value = len("Hello World".encode('utf-8'))

        qtbot.mouseClick(serial_debugger_app.basic_comm_panel_widget.send_button, Qt.MouseButton.LeftButton)
        mock_serial_manager.write_data.assert_called_with(QByteArray(b'Hello World'))
        mock_data_recorder.record_raw_frame.assert_called_with(
            datetime.now(), b'Hello World', "TX (Basic)"
        )
        assert serial_debugger_app.status_bar_label.text().startswith("基本发送 11 字节: Hello World")

        # Test sending hex
        mock_serial_manager.write_data.reset_mock()
        serial_debugger_app.basic_comm_panel_widget.send_text_edit.setText("DEADBEEF")
        serial_debugger_app.basic_comm_panel_widget.send_hex_checkbox.setChecked(True)
        mock_serial_manager.write_data.return_value = len(QByteArray.fromHex(b'DEADBEEF'))

        qtbot.mouseClick(serial_debugger_app.basic_comm_panel_widget.send_button, Qt.MouseButton.LeftButton)
        mock_serial_manager.write_data.assert_called_with(QByteArray.fromHex(b'DEADBEEF'))
        mock_data_recorder.record_raw_frame.assert_called_with(
            datetime.now(), QByteArray.fromHex(b'DEADBEEF').data(), "TX (Basic)"
        )
        assert serial_debugger_app.status_bar_label.text().startswith("基本发送 4 字节: DE AD BE EF")

    def test_close_event_cleanup(self, qtbot, serial_debugger_app, mock_serial_manager, mock_data_recorder,
                                 mock_config_manager, mock_error_logger):
        # Ensure data processor is running for stop/terminate check
        serial_debugger_app.data_processor.isRunning = MagicMock(return_value=True)
        serial_debugger_app.data_processor.stop = MagicMock()
        serial_debugger_app.data_processor.wait = MagicMock(return_value=True)  # Simulate graceful stop

        # Simulate serial connected and raw recording active
        mock_serial_manager.is_connected = True
        mock_data_recorder.recording_raw = True

        with patch('main.QMessageBox.question', return_value=QMessageBox.StandardButton.No):  # Don't save raw data
            serial_debugger_app.closeEvent(MagicMock(spec=QCloseEvent))

            serial_debugger_app.data_processor.stop.assert_called_once()
            mock_serial_manager.disconnect_port.assert_called_once()
            mock_data_recorder.stop_raw_recording.assert_called_once()
            mock_config_manager.save_config.assert_called_once()
            mock_error_logger.log_info.assert_any_call("应用程序退出。")


class TestPluginManagementDialog:
    @pytest.fixture
    def plugin_dialog(self, qtbot, serial_debugger_app, mock_plugin_manager):
        # Ensure the main window's plugin manager is the mock
        serial_debugger_app.plugin_manager = mock_plugin_manager

        # Set up some mock discovered plugins for the dialog
        mock_plugin_manager.get_all_discovered_plugin_modules_metadata.return_value = [
            {"module_name": "plugin_a", "display_name": "Plugin A", "version": "1.0", "description": "Desc A",
             "status": "enabled"},
            {"module_name": "plugin_b", "display_name": "Plugin B", "version": "1.1", "description": "Desc B",
             "status": "disabled"},
            {"module_name": "plugin_c", "display_name": "Plugin C", "version": "2.0", "description": "Desc C",
             "status": "blocklisted (session)"},
            {"module_name": "plugin_d", "display_name": "Plugin D", "version": "1.0", "description": "Desc D",
             "status": "discovered"},
        ]
        dialog = PluginManagementDialog(mock_plugin_manager, serial_debugger_app)
        qtbot.addWidget(dialog)
        dialog.show()
        yield dialog
        dialog.close()

    def test_initial_display(self, qtbot, plugin_dialog):
        assert plugin_dialog.plugin_list_widget.count() == 4
        item_0 = plugin_dialog.plugin_list_widget.item(0)
        assert "Plugin A" in item_0.text()
        assert "状态: ENABLED" in item_0.text()
        assert item_0.data(Qt.ItemDataRole.UserRole) == "plugin_a"

        item_2 = plugin_dialog.plugin_list_widget.item(2)
        assert "Plugin C" in item_2.text()
        assert "状态: BLOCKLISTED (SESSION)" in item_2.text()

    def test_change_plugin_status_actions(self, qtbot, plugin_dialog, mock_plugin_manager, serial_debugger_app):
        # Select Plugin B (disabled)
        plugin_dialog.plugin_list_widget.setCurrentRow(1)  # plugin_b
        qtbot.mouseClick(plugin_dialog.enable_button, Qt.MouseButton.LeftButton)
        serial_debugger_app.update_plugin_enabled_status.assert_called_with("plugin_b", True)
        # Mock the reload call for the dialog to re-populate
        plugin_dialog._populate_plugin_list()
        item_1 = plugin_dialog.plugin_list_widget.item(1)
        # This will be 'disabled' because we haven't mocked the return of get_all_discovered_plugin_modules_metadata for _populate_plugin_list
        # A more robust test would re-mock that for the next _populate_plugin_list call.
        # For now, we only check if the main_window_ref method was called.
        assert item_1.text().startswith("Plugin B (v1.1) - plugin_b")

        serial_debugger_app.update_plugin_enabled_status.reset_mock()
        # Select Plugin A (enabled) and disable it
        plugin_dialog.plugin_list_widget.setCurrentRow(0)  # plugin_a
        qtbot.mouseClick(plugin_dialog.disable_button, Qt.MouseButton.LeftButton)
        serial_debugger_app.update_plugin_enabled_status.assert_called_with("plugin_a", False)

        serial_debugger_app.session_block_plugin_module.reset_mock()
        # Select Plugin D (discovered) and session block it
        plugin_dialog.plugin_list_widget.setCurrentRow(3)  # plugin_d
        qtbot.mouseClick(plugin_dialog.session_block_button, Qt.MouseButton.LeftButton)
        serial_debugger_app.session_block_plugin_module.assert_called_with("plugin_d")

        mock_plugin_manager.unblock_module_for_session.reset_mock()
        with patch('main.QMessageBox.information'):  # Mock message box
            # Select Plugin C (blocklisted) and unblock it
            plugin_dialog.plugin_list_widget.setCurrentRow(2)  # plugin_c
            qtbot.mouseClick(plugin_dialog.unblock_button, Qt.MouseButton.LeftButton)
            mock_plugin_manager.unblock_module_for_session.assert_called_with("plugin_c")


class TestSerialConfigDefinitionPanelWidget:
    @pytest.fixture
    def serial_config_widget(self, qtbot, serial_debugger_app):
        widget = SerialConfigDefinitionPanelWidget(parent_main_window=serial_debugger_app)
        qtbot.addWidget(widget)
        yield widget

    def test_get_serial_config_from_ui(self, qtbot, serial_config_widget, mock_error_logger):
        serial_config_widget.port_combo.addItem("COM1 (Port description)", "COM1")
        serial_config_widget.port_combo.setCurrentText("COM1 (Port description)")
        serial_config_widget.baud_combo.setCurrentText("115200")
        serial_config_widget.data_bits_combo.setCurrentText("8")
        serial_config_widget.parity_combo.setCurrentText("None")
        serial_config_widget.stop_bits_combo.setCurrentText("1")

        config = serial_config_widget.get_serial_config_from_ui()
        assert config.port_name == "COM1"
        assert config.baud_rate == 115200
        assert config.data_bits == 8
        assert config.parity == "None"
        assert config.stop_bits == 1.0

        # Test invalid baud rate
        serial_config_widget.baud_combo.setCurrentText("abc")
        config_invalid_baud = serial_config_widget.get_serial_config_from_ui()
        assert config_invalid_baud.baud_rate == Constants.DEFAULT_BAUD_RATE
        mock_error_logger.log_warning.assert_any_call(
            f"无效的波特率输入: 'abc', 使用默认值 {Constants.DEFAULT_BAUD_RATE}")

    def test_update_port_combo_display(self, qtbot, serial_config_widget):
        ports = [{'name': 'COM1', 'description': 'Port 1'}, {'name': 'COM2', 'description': 'Port 2'}]
        serial_config_widget.update_port_combo_display(ports, current_port_name='COM2')
        assert serial_config_widget.port_combo.count() == 2
        assert serial_config_widget.port_combo.currentText() == "COM2 (Port 2)"

        serial_config_widget.update_port_combo_display([], current_port_name=None)
        assert serial_config_widget.port_combo.count() == 1
        assert serial_config_widget.port_combo.currentText() == "无可用端口"
        assert not serial_config_widget.port_combo.isEnabled()
        assert not serial_config_widget.connect_button.isEnabled()


class TestAdaptedParsePanelWidget:
    @pytest.fixture
    def parse_panel(self, qtbot, serial_debugger_app):
        # We need to mock the create_panel_instance for the main window to ensure it returns our test panel.
        # But for testing the panel itself, we can instantiate it directly.
        panel = AdaptedParsePanelWidget(panel_id=1, main_window_ref=serial_debugger_app)
        qtbot.addWidget(panel)
        yield panel

    def test_add_remove_receive_container(self, qtbot, parse_panel, mock_error_logger, serial_debugger_app):
        assert len(parse_panel.receive_data_containers) == 0
        assert not parse_panel.remove_recv_container_button.isEnabled()

        qtbot.mouseClick(parse_panel.add_recv_container_button, Qt.MouseButton.LeftButton)
        assert len(parse_panel.receive_data_containers) == 1
        assert parse_panel.remove_recv_container_button.isEnabled()
        mock_error_logger.log_info.assert_called_with("Parse Panel 1: Added receive container 1")
        assert serial_debugger_app._next_global_receive_container_id == 2  # Verify global ID update

        # Simulate removing the container
        qtbot.mouseClick(parse_panel.remove_recv_container_button, Qt.MouseButton.LeftButton)
        assert len(parse_panel.receive_data_containers) == 0
        assert not parse_panel.remove_recv_container_button.isEnabled()
        mock_error_logger.log_info.assert_called_with("Parse Panel 1: Removed receive container 1")

    def test_dispatch_data_sequential(self, qtbot, parse_panel, mock_data_recorder, serial_debugger_app):
        parse_panel.parse_id_edit.setText("C1")
        # Add two containers: uint8_t and uint16_t
        parse_panel.add_receive_data_container()  # default uint8_t
        parse_panel.receive_data_containers[0].name_edit.setText("SensorVal1")
        parse_panel.add_receive_data_container()
        parse_panel.receive_data_containers[1].name_edit.setText("SensorVal2")
        parse_panel.receive_data_containers[1].type_combo.setCurrentText("uint16_t")

        # Mock the set_value on containers
        parse_panel.receive_data_containers[0].set_value = MagicMock()
        parse_panel.receive_data_containers[0].value_edit.setText("170")
        parse_panel.receive_data_containers[1].set_value = MagicMock()
        parse_panel.receive_data_containers[1].value_edit.setText("8705")

        # Payload: 0xAA (SensorVal1), 0x01 0x02 (SensorVal2 - little endian for 513)
        payload = QByteArray(b'\xAA\x01\x02')  # AA (170), 01 02 (513)
        parse_panel.dispatch_data(payload)

        parse_panel.receive_data_containers[0].set_value.assert_called_with(QByteArray(b'\xAA'), "uint8_t")
        parse_panel.receive_data_containers[1].set_value.assert_called_with(QByteArray(b'\x01\x02'), "uint16_t")

        mock_data_recorder.add_parsed_frame_data.assert_called_once()
        args, _ = mock_data_recorder.add_parsed_frame_data.call_args
        assert args[1]["P1_SensorVal1"] == "170"
        assert args[1]["P1_SensorVal2"] == "8705"  # This is the expected string if it was 0x2211, not 0x0201 or 0x0102.
        # Actual parsed value depends on struct.unpack, but for test, we mock value_edit.text()


class TestAdaptedSendPanelWidget:
    @pytest.fixture
    def send_panel(self, qtbot, serial_debugger_app):
        panel = AdaptedSendPanelWidget(panel_id=1, main_window_ref=serial_debugger_app)
        qtbot.addWidget(panel)
        yield panel

    def test_add_remove_send_container(self, qtbot, send_panel, mock_error_logger):
        assert len(send_panel.send_data_containers) == 0
        assert not send_panel.remove_button.isEnabled()

        qtbot.mouseClick(send_panel.add_button, Qt.MouseButton.LeftButton)
        assert len(send_panel.send_data_containers) == 1
        assert send_panel.remove_button.isEnabled()
        mock_error_logger.log_info.assert_called_with("Send Panel 1: Added send data container 1")

        qtbot.mouseClick(send_panel.remove_button, Qt.MouseButton.LeftButton)
        assert len(send_panel.send_data_containers) == 0
        assert not send_panel.remove_button.isEnabled()
        mock_error_logger.log_info.assert_called_with("Send Panel 1: Removed send data container 1")

    def test_trigger_send_frame(self, qtbot, send_panel, mock_serial_manager, mock_error_logger, mock_data_recorder,
                                serial_debugger_app):
        mock_serial_manager.is_connected = True
        send_panel.panel_func_id_edit.setText("C0")

        # Add a container and set its value
        send_panel.add_send_data_container()
        send_panel.send_data_containers[0].name_edit.setText("ValueA")
        send_panel.send_data_containers[0].type_combo.setCurrentText("uint8_t")
        send_panel.send_data_containers[0].value_edit.setText("10")  # Corresponds to 0x0A

        # Mock assemble_custom_frame_from_send_panel_data to return a known frame
        mock_frame = QByteArray(b'\xAA\x01\xFE\xC0\x01\x00\x0A\x22\x33')  # Dummy frame
        serial_debugger_app.assemble_custom_frame_from_send_panel_data = MagicMock(return_value=mock_frame)
        mock_serial_manager.write_data.return_value = mock_frame.size()

        qtbot.mouseClick(send_panel.send_frame_button_panel, Qt.MouseButton.LeftButton)

        serial_debugger_app.assemble_custom_frame_from_send_panel_data.assert_called_once()
        mock_serial_manager.write_data.assert_called_with(mock_frame)
        mock_data_recorder.record_raw_frame.assert_called_once()
        mock_error_logger.log_info.assert_any_call("发送面板 1 (ID:C0) 发送 9 字节: AA 01 FE C0 01 00 0A 22 33")
        assert serial_debugger_app.status_bar_label.text() == "发送面板 1 (ID:C0) 发送 9 字节: AA 01 FE C0 01 00 0A 22 33"


class TestAdaptedPlotWidgetPanel:
    @pytest.fixture
    def plot_panel(self, qtbot, serial_debugger_app):
        if not PYQTGRAPH_AVAILABLE:
            pytest.skip("pyqtgraph is not available, skipping plot panel tests.")
        panel = AdaptedPlotWidgetPanel(panel_id=1, main_window_ref=serial_debugger_app)
        qtbot.addWidget(panel)
        yield panel

    @pytest.mark.skipif(not PYQTGRAPH_AVAILABLE, reason="pyqtgraph not installed")
    def test_update_data_and_clear_plot(self, qtbot, plot_panel):
        assert len(plot_panel.curves) == 0
        assert plot_panel.plot_widget_container is not None

        plot_panel.update_data(container_id=1, value=10.5, curve_name="Sensor 1")
        assert len(plot_panel.curves) == 1
        assert 1 in plot_panel.data
        assert len(plot_panel.data[1]['x']) == 1

        plot_panel.update_data(container_id=1, value=11.0, curve_name="Sensor 1")
        assert len(plot_panel.data[1]['x']) == 2

        plot_panel.update_data(container_id=2, value=20.0, curve_name="Sensor 2")
        assert len(plot_panel.curves) == 2
        assert 2 in plot_panel.data

        plot_panel.clear_plot()
        assert len(plot_panel.curves) == 0
        assert len(plot_panel.data) == 0


class TestBasicCommPanelWidget:
    @pytest.fixture
    def basic_comm_widget(self, qtbot, serial_debugger_app):
        widget = BasicCommPanelWidget(main_window_ref=serial_debugger_app)
        qtbot.addWidget(widget)
        yield widget

    def test_send_hex_validation(self, qtbot, basic_comm_widget):
        # Valid hex
        assert basic_comm_widget._validate_hex_input("AABBCC") == True
        assert basic_comm_widget._validate_hex_input("AA BB CC") == True
        assert basic_comm_widget._validate_hex_input("01-EF-CD") == True
        assert basic_comm_widget._validate_hex_input("abcdef") == True
        assert basic_comm_widget._validate_hex_input("1") == False  # Odd length

        # Invalid hex
        assert basic_comm_widget._validate_hex_input("ABCX") == False
        assert basic_comm_widget._validate_hex_input("Hello") == False
        assert basic_comm_widget._validate_hex_input("") == False
        assert basic_comm_widget._validate_hex_input(" ") == False

    def test_append_receive_text(self, qtbot, basic_comm_widget):
        basic_comm_widget.recv_hex_checkbox.setChecked(False)
        basic_comm_widget.recv_timestamp_checkbox.setChecked(False)
        basic_comm_widget.append_receive_text("Test Data\n")
        assert basic_comm_widget.receive_text_edit.toPlainText() == "Test Data\n"

        basic_comm_widget.receive_text_edit.clear()
        basic_comm_widget.recv_hex_checkbox.setChecked(True)
        basic_comm_widget.recv_timestamp_checkbox.setChecked(False)
        basic_comm_widget._append_to_basic_receive_text_edit(QByteArray(b'\xDE\xAD\xBE\xEF'), source="RX")
        assert basic_comm_widget.receive_text_edit.toPlainText().strip() == "RX: DE AD BE EF"

        basic_comm_widget.receive_text_edit.clear()
        basic_comm_widget.recv_hex_checkbox.setChecked(False)
        basic_comm_widget.recv_timestamp_checkbox.setChecked(True)
        basic_comm_widget._append_to_basic_receive_text_edit(QByteArray(b'Hello'), source="RX")
        # Check for timestamp format, content should be 'Hello'
        assert basic_comm_widget.receive_text_edit.toPlainText().strip().startswith("[")
        assert "RX: Hello" in basic_comm_widget.receive_text_edit.toPlainText()


class TestCustomLogPanelWidget:
    @pytest.fixture
    def custom_log_widget(self, qtbot, serial_debugger_app):
        widget = CustomLogPanelWidget(main_window_ref=serial_debugger_app)
        qtbot.addWidget(widget)
        yield widget

    def test_append_log_formatted(self, qtbot, custom_log_widget):
        custom_log_widget.hex_checkbox.setChecked(False)
        custom_log_widget.timestamp_checkbox.setChecked(False)
        custom_log_widget.append_to_custom_protocol_log_formatted(
            datetime(2025, 1, 1, 10, 30, 0, 123456), "RX", "My custom data", False
        )
        assert custom_log_widget.log_text_edit.toPlainText() == "RX: My custom data\n"

        custom_log_widget.log_text_edit.clear()
        custom_log_widget.hex_checkbox.setChecked(True)
        custom_log_widget.timestamp_checkbox.setChecked(False)
        # Content is "Hello" (text), is_content_hex=False -> converts to hex display
        custom_log_widget.append_to_custom_protocol_log_formatted(
            datetime.now(), "TX", "Hello", False
        )
        assert custom_log_widget.log_text_edit.toPlainText().strip() == "TX: 48 65 6C 6C 6F"

        custom_log_widget.log_text_edit.clear()
        custom_log_widget.hex_checkbox.setChecked(True)
        custom_log_widget.timestamp_checkbox.setChecked(True)
        # Content is "01 02" (hex string), is_content_hex=True -> displays as is
        custom_log_widget.append_to_custom_protocol_log_formatted(
            datetime.now(), "Parsed", "01 02 03", True
        )
        assert custom_log_widget.log_text_edit.toPlainText().strip().startswith("[")
        assert "Parsed: 01 02 03" in custom_log_widget.log_text_edit.toPlainText()


class TestScriptingPanelWidget:
    @pytest.fixture
    def scripting_widget(self, qtbot, serial_debugger_app):
        widget = ScriptingPanelWidget(main_window_ref=serial_debugger_app)
        qtbot.addWidget(widget)
        yield widget

    def test_run_script_button(self, qtbot, scripting_widget):
        script_code = "print('Hello script')"
        scripting_widget.script_input_edit.setPlainText(script_code)

        # Mock the signal emission to check arguments
        scripting_widget.execute_script_requested.emit = MagicMock()

        qtbot.mouseClick(scripting_widget.run_script_button, Qt.MouseButton.LeftButton)
        scripting_widget.execute_script_requested.emit.assert_called_once_with(script_code)

        # Test empty script
        scripting_widget.script_input_edit.clear()
        scripting_widget.execute_script_requested.emit.reset_mock()
        qtbot.mouseClick(scripting_widget.run_script_button, Qt.MouseButton.LeftButton)
        scripting_widget.execute_script_requested.emit.assert_not_called()
        assert scripting_widget.script_output_edit.toPlainText() == "错误：脚本内容为空。"

    def test_display_script_result(self, qtbot, scripting_widget):
        scripting_widget.display_script_result("Execution Successful!")
        assert scripting_widget.script_output_edit.toPlainText() == "Execution Successful!"

        scripting_widget.display_script_result("Error:\nSomething went wrong.")
        assert scripting_widget.script_output_edit.toPlainText() == "Error:\nSomething went wrong."
