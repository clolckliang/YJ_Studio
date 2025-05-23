from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
from PySide6.QtCore import QObject, Signal, QIODevice, QByteArray, Slot
from typing import Optional, List, Dict

from utils.data_models import SerialPortConfig
from utils.logger import ErrorLogger

class SerialManager(QObject):
    connection_status_changed = Signal(bool, str) # is_connected, message
    data_received = Signal(QByteArray)
    error_occurred_signal = Signal(str) # For non-critical errors to display

    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.serial_port = QSerialPort(self)
        self.error_logger = error_logger
        self.is_connected = False

        self.serial_port.readyRead.connect(self._read_data)
        self.serial_port.errorOccurred.connect(self._handle_serial_error)

    def get_available_ports(self) -> List[Dict[str, str]]:
        ports_info = []
        ports = QSerialPortInfo.availablePorts()
        for port in ports:
            ports_info.append({"name": port.portName(), "description": port.description()})
        return ports_info

    def connect_port(self, config: SerialPortConfig) -> bool:
        if self.is_connected:
            self.disconnect_port()

        if not config.port_name:
            self.connection_status_changed.emit(False, "错误: 未选择串口。")
            return False

        self.serial_port.setPortName(config.port_name)
        self.serial_port.setBaudRate(config.baud_rate)

        data_bits_map = {"8": QSerialPort.Data8, "7": QSerialPort.Data7,
                         "6": QSerialPort.Data6, "5": QSerialPort.Data5}
        self.serial_port.setDataBits(data_bits_map.get(str(config.data_bits), QSerialPort.Data8))

        parity_map = {"None": QSerialPort.NoParity, "Even": QSerialPort.EvenParity,
                      "Odd": QSerialPort.OddParity, "Space": QSerialPort.SpaceParity,
                      "Mark": QSerialPort.MarkParity}
        self.serial_port.setParity(parity_map.get(config.parity, QSerialPort.NoParity))

        stop_bits_map = {"1": QSerialPort.OneStop, "1.5": QSerialPort.OneAndHalfStop,
                         "2": QSerialPort.TwoStop}
        self.serial_port.setStopBits(stop_bits_map.get(str(config.stop_bits), QSerialPort.OneStop))

        if self.serial_port.open(QIODevice.OpenModeFlag.ReadWrite):
            self.is_connected = True
            msg = f"已连接 {config.port_name} @ {config.baud_rate}"
            self.connection_status_changed.emit(True, msg)
            if self.error_logger: self.error_logger.log_info(msg)
            return True
        else:
            self.is_connected = False
            err_str = self.serial_port.errorString()
            msg = f"打开串口失败: {err_str}"
            self.connection_status_changed.emit(False, msg)
            if self.error_logger: self.error_logger.log_error(msg, "CONNECTION")
            return False

    def disconnect_port(self) -> None:
        if self.serial_port.isOpen():
            self.serial_port.close()
        self.is_connected = False
        msg = "串口已关闭"
        self.connection_status_changed.emit(False, msg)
        if self.error_logger: self.error_logger.log_info(msg)


    def write_data(self, data: QByteArray) -> int:
        if not self.is_connected:
            if self.error_logger: self.error_logger.log_warning("尝试在未连接的串口上写入数据。")
            return -1 # Indicate error or not connected

        bytes_written = self.serial_port.write(data)
        if bytes_written == -1:
             if self.error_logger: self.error_logger.log_error(f"串口写入错误: {self.serial_port.errorString()}", "SEND")
        elif bytes_written != len(data):
             if self.error_logger: self.error_logger.log_warning(f"串口部分写入: {bytes_written}/{len(data)}字节。", "SEND")
        return bytes_written


    @Slot()
    def _read_data(self) -> None:
        if self.serial_port.bytesAvailable() > 0:
            data = self.serial_port.readAll()
            self.data_received.emit(data)

    @Slot(QSerialPort.SerialPortError)
    def _handle_serial_error(self, error_code: QSerialPort.SerialPortError) -> None:
        if error_code != QSerialPort.SerialPortError.NoError:
            err_str = self.serial_port.errorString()
            # ResourceError often means the device was unplugged.
            if error_code == QSerialPort.SerialPortError.ResourceError and self.is_connected:
                # Port might have been closed automatically or became unusable
                self.is_connected = False # Update internal state
                msg = f"串口资源错误/已断开: {err_str}"
                self.connection_status_changed.emit(False, msg) # Emit status change
                if self.error_logger: self.error_logger.log_error(msg, "SERIAL_RESOURCE")

            elif error_code not in [QSerialPort.SerialPortError.NoError, QSerialPort.SerialPortError.TimeoutError]:
                # Other errors that might not lead to immediate disconnect but should be reported
                self.error_occurred_signal.emit(f"串口发生错误: {err_str}")
                if self.error_logger: self.error_logger.log_warning(f"串口错误: {err_str} (Code: {error_code})", "SERIAL_GENERAL")