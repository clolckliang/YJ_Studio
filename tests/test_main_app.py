import sys
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app

@pytest.fixture
def mock_serial_manager():
    with patch("main.SerialManager") as MockManager:
        manager = MockManager.return_value
        manager.is_connected = False
        manager.get_available_ports.return_value = [
            {'name': 'COM1', 'description': 'USB Serial Device (COM1)'},
            {'name': '/dev/ttyUSB0', 'description': 'USB to UART (ttyUSB0)'}
        ]
        manager.connect_port.return_value = True
        manager.disconnect_port.return_value = None
        manager.write_data.return_value = 4
        yield manager

@pytest.fixture
def mock_error_logger():
    with patch("main.ErrorLogger") as MockLogger:
        logger = MockLogger.return_value
        logger.log_info = MagicMock()
        logger.log_warning = MagicMock()
        logger.log_error = MagicMock()
        yield logger

@pytest.fixture
def serial_debugger_app(qtbot, mock_serial_manager, mock_error_logger):
    from main import SerialDebugger
    with patch("main.ConfigManager") as MockConfigManager, \
         patch("main.DataRecorder"), patch("main.PluginManager"):
        MockConfigManager.return_value.load_config.return_value = {}
        win = SerialDebugger()
        win.serial_manager = mock_serial_manager
        win.error_logger = mock_error_logger
        qtbot.addWidget(win)
        win.show()
        yield win
        win.close()

def set_serial_config(serial_debugger_app):
    panel = serial_debugger_app.serial_config_panel_widget
    if panel.port_combo.count() > 0:
        panel.port_combo.setCurrentIndex(0)
    if hasattr(panel, 'baudrate_combo') and panel.baudrate_combo.count() > 0:
        panel.baudrate_combo.setCurrentIndex(0)
    if hasattr(panel, 'databits_combo') and panel.databits_combo.count() > 0:
        panel.databits_combo.setCurrentIndex(0)
    if hasattr(panel, 'parity_combo') and panel.parity_combo.count() > 0:
        panel.parity_combo.setCurrentIndex(0)
    if hasattr(panel, 'stopbits_combo') and panel.stopbits_combo.count() > 0:
        panel.stopbits_combo.setCurrentIndex(0)

def test_serial_open_and_close(qtbot, serial_debugger_app, mock_serial_manager):
    set_serial_config(serial_debugger_app)
    qtbot.mouseClick(serial_debugger_app.serial_config_panel_widget.connect_button, Qt.LeftButton)
    mock_serial_manager.connect_port.assert_called()
    serial_debugger_app.serial_manager.is_connected = True
    qtbot.mouseClick(serial_debugger_app.serial_config_panel_widget.connect_button, Qt.LeftButton)
    mock_serial_manager.disconnect_port.assert_called()

def test_serial_send_receive_basic(qtbot, serial_debugger_app, mock_serial_manager):
    set_serial_config(serial_debugger_app)
    serial_debugger_app.serial_manager.is_connected = True
    qtbot.mouseClick(serial_debugger_app.serial_config_panel_widget.connect_button, Qt.LeftButton)
    send_text = "TEST"
    serial_debugger_app.basic_comm_panel_widget.send_text_edit.setPlainText(send_text)
    serial_debugger_app.basic_comm_panel_widget.send_hex_checkbox.setChecked(False)
    qtbot.mouseClick(serial_debugger_app.basic_comm_panel_widget.send_button, Qt.LeftButton)
    mock_serial_manager.write_data.assert_called_with(QByteArray(b"TEST"))
    serial_debugger_app.basic_comm_panel_widget.send_text_edit.setPlainText("DEADBEEF")
    serial_debugger_app.basic_comm_panel_widget.send_hex_checkbox.setChecked(True)
    qtbot.mouseClick(serial_debugger_app.basic_comm_panel_widget.send_button, Qt.LeftButton)
    mock_serial_manager.write_data.assert_called_with(QByteArray.fromHex(b"DEADBEEF"))