from PySide6.QtCore import QObject, Signal, QThread, QByteArray, Slot, QIODevice
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
import serial
import serial.tools.list_ports
from typing import Optional, List, Dict
from utils.data_models import SerialPortConfig
from utils.logger import ErrorLogger

class SerialManager(QObject):
    connection_status_changed = Signal(bool, str)  # is_connected, message
    data_received = Signal(QByteArray)
    error_occurred_signal = Signal(str)  # For non-critical errors to display

    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None, use_pyserial: bool = False):
        super().__init__(parent)
        self.error_logger = error_logger
        self.is_connected = False
        self.use_pyserial = use_pyserial
        if self.use_pyserial:
            self.serial_port = None
            self.read_thread = None
        else:
            self.serial_port = QSerialPort(self)
            self.serial_port.setReadBufferSize(4096)  # 设置为4kB缓冲区
            self.serial_port.readyRead.connect(self._read_data)
            self.serial_port.errorOccurred.connect(self._handle_serial_error)

    def get_available_ports(self) -> List[Dict[str, str]]:
        ports_info = []
        if self.use_pyserial:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                ports_info.append({"name": port.device, "description": port.description})
        else:
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

        if self.use_pyserial:
            try:
                self.serial_port = serial.Serial(
                    port=config.port_name,
                    baudrate=config.baud_rate,
                    bytesize=config.data_bits,
                    parity=config.parity[0].upper() if config.parity != "None" else 'N',
                    stopbits=1.5 if config.stop_bits == 1.5 else int(config.stop_bits),
                    timeout=0.1,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False,
                )
                self.is_connected = True
                self.connection_status_changed.emit(True, f"已连接 {config.port_name} @ {config.baud_rate}")
                if self.error_logger:
                    self.error_logger.log_info(f"已连接 {config.port_name} @ {config.baud_rate} (pyserial)")
                # 启动读取线程
                self.read_thread = SerialReadThread(self.serial_port, self)
                self.read_thread.data_received.connect(self.data_received)
                self.read_thread.start()
                return True
            except Exception as e:
                self.is_connected = False
                msg = f"打开串口失败: {e}"
                self.connection_status_changed.emit(False, msg)
                if self.error_logger:
                    self.error_logger.log_error(msg, "CONNECTION")
                return False
        else:
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

            # 明确禁用硬件流控制
            self.serial_port.setFlowControl(QSerialPort.NoFlowControl)

            # 添加日志输出流控制设置
            if self.error_logger:
                flow_control = "无" if self.serial_port.flowControl() == QSerialPort.NoFlowControl else "启用"
                self.error_logger.log_info(f"串口流控制设置: {flow_control}")

            if self.serial_port.open(QIODevice.OpenModeFlag.ReadWrite):
                self.is_connected = True
                msg = f"已连接 {config.port_name} @ {config.baud_rate}"
                self.connection_status_changed.emit(True, msg)
                if self.error_logger:
                    self.error_logger.log_info(msg)
                    # 记录详细的串口配置
                    self.error_logger.log_info(
                        f"串口详细配置: "
                        f"数据位={self.serial_port.dataBits()}, "
                        f"校验位={self.serial_port.parity()}, "
                        f"停止位={self.serial_port.stopBits()}, "
                        f"流控制={self.serial_port.flowControl()}"
                    )
                return True
            else:
                self.is_connected = False
                err_str = self.serial_port.errorString()
                msg = f"打开串口失败: {err_str}"
                self.connection_status_changed.emit(False, msg)
                if self.error_logger:
                    self.error_logger.log_error(msg, "CONNECTION")
                return False

    def disconnect_port(self) -> None:
        if self.use_pyserial:
            if self.read_thread and self.read_thread.isRunning():
                self.read_thread.stop()
                self.read_thread.wait()
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.is_connected = False
            self.connection_status_changed.emit(False, "串口已关闭")
            if self.error_logger:
                self.error_logger.log_info("串口已关闭 (pyserial)")
        else:
            if self.serial_port.isOpen():
                self.serial_port.close()
            self.is_connected = False
            self.connection_status_changed.emit(False, "串口已关闭")
            if self.error_logger:
                self.error_logger.log_info("串口已关闭")

    def write_data(self, data: QByteArray) -> int:
        if not self.is_connected:
            if self.error_logger:
                self.error_logger.log_warning("尝试在未连接的串口上写入数据。")
            return -1  # Indicate error or not connected

        if self.use_pyserial:
            try:
                bytes_written = self.serial_port.write(data.data())
                return bytes_written
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(f"串口写入错误: {e}", "SEND")
                return -1
        else:
            bytes_written = self.serial_port.write(data)
            if bytes_written == -1:
                if self.error_logger:
                    self.error_logger.log_error(f"串口写入错误: {self.serial_port.errorString()}", "SEND")
            elif bytes_written != len(data):
                if self.error_logger:
                    self.error_logger.log_warning(f"串口部分写入: {bytes_written}/{len(data)}字节。", "SEND")
            return bytes_written


class SerialReadThread(QThread):
    data_received = Signal(QByteArray)

    def __init__(self, serial_port: serial.Serial, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.serial_port = serial_port
        self._running = True

    def run(self):
        while self._running:
            if self.serial_port.in_waiting > 0:
                data = self.serial_port.read(self.serial_port.in_waiting)
                self.data_received.emit(QByteArray(data))
            self.msleep(10)

    def stop(self):
        self._running = False
