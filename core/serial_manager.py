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
            if self.error_logger:
                self.error_logger.log_info(f"pyserial找到的串口: {[port.device for port in ports]}")
            for port in ports:
                ports_info.append({"name": port.device, "description": port.description})
        else:
            ports = QSerialPortInfo.availablePorts()
            if self.error_logger:
                self.error_logger.log_info(f"QtSerialPort找到的串口: {[port.portName() for port in ports]}")
            for port in ports:
                ports_info.append({"name": port.portName(), "description": port.description()})
        
        # 直接添加COM1和COM2用于测试
        ports_info.append({"name": "COM1", "description": "Virtual Test Port"})
        ports_info.append({"name": "COM2", "description": "Virtual Test Port"})

        if self.error_logger:
            self.error_logger.log_info(f"返回的串口列表: {[port['name'] for port in ports_info]}")
        return ports_info

    def connect_port(self, config: SerialPortConfig) -> bool:
        if self.error_logger:
            self.error_logger.log_info(f"connect_port: 尝试连接串口: {config.port_name} @ {config.baud_rate}")
        if self.is_connected:
            self.disconnect_port()

        if not config.port_name:
            if self.error_logger:
                self.error_logger.log_error("connect_port: 未选择串口", "CONNECTION")
            self.connection_status_changed.emit(False, "错误: 未选择串口。")
            return False

        # 参数验证
        if not isinstance(config.baud_rate, int) or config.baud_rate <= 0:
            self._log_and_emit_error(f"无效的波特率: {config.baud_rate}", "CONNECTION")
            return False
        if config.data_bits not in [5, 6, 7, 8]:
            self._log_and_emit_error(f"无效的数据位: {config.data_bits}", "CONNECTION")
            return False
        if config.parity not in ["None", "Even", "Odd", "Mark", "Space"]:
            self._log_and_emit_error(f"无效的校验位: {config.parity}", "CONNECTION")
            return False
        if config.stop_bits not in [1, 1.5, 2]:
            self._log_and_emit_error(f"无效的停止位: {config.stop_bits}", "CONNECTION")
            return False

        if self.use_pyserial:
            try:
                # pyserial的bytesize参数是serial.FIVEBITS, serial.EIGHTBITS等，但pyserial库会自动处理整数
                # parity参数是'N', 'E', 'O', 'M', 'S'
                pyserial_parity = config.parity[0].upper() if config.parity != "None" else 'N'
                # stopbits参数是serial.STOPBITS_ONE, serial.STOPBITS_ONE_POINT_FIVE, serial.STOPBITS_TWO
                pyserial_stopbits = serial.STOPBITS_ONE
                if config.stop_bits == 1.5:
                    pyserial_stopbits = serial.STOPBITS_ONE_POINT_FIVE
                elif config.stop_bits == 2:
                    pyserial_stopbits = serial.STOPBITS_TWO

                self.serial_port = serial.Serial(
                    port=config.port_name,
                    baudrate=config.baud_rate,
                    bytesize=config.data_bits,
                    parity=pyserial_parity,
                    stopbits=pyserial_stopbits,
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
            from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
            from PySide6.QtCore import QIODevice # Import QIODevice here for local scope

            self.serial_port = QSerialPort(self) # Re-initialize QSerialPort if not pyserial
            self.serial_port.setReadBufferSize(4096)
            self.serial_port.readyRead.connect(self._read_data)
            self.serial_port.errorOccurred.connect(self._handle_serial_error)

            self.serial_port.setPortName(config.port_name)
            self.serial_port.setBaudRate(config.baud_rate)

            data_bits_map = {
                8: QSerialPort.Data8, 7: QSerialPort.Data7,
                6: QSerialPort.Data6, 5: QSerialPort.Data5
            }
            self.serial_port.setDataBits(data_bits_map.get(config.data_bits, QSerialPort.Data8))

            parity_map = {
                "None": QSerialPort.NoParity, "Even": QSerialPort.EvenParity,
                "Odd": QSerialPort.OddParity, "Space": QSerialPort.SpaceParity,
                "Mark": QSerialPort.MarkParity
            }
            self.serial_port.setParity(parity_map.get(config.parity, QSerialPort.NoParity))

            stop_bits_map = {
                1: QSerialPort.OneStop, 1.5: QSerialPort.OneAndHalfStop,
                2: QSerialPort.TwoStop
            }
            self.serial_port.setStopBits(stop_bits_map.get(config.stop_bits, QSerialPort.OneStop))

            # 明确禁用硬件流控制
            self.serial_port.setFlowControl(QSerialPort.NoFlowControl)

            # 添加日志输出流控制设置
            if self.error_logger:
                flow_control = "无" if self.serial_port.flowControl() == QSerialPort.NoFlowControl else "启用"
                self.error_logger.log_info(f"串口流控制设置: {flow_control}")

            if self.serial_port.open(QIODevice.OpenModeFlag.ReadWrite):
                self.is_connected = True
                msg = f"已连接 {config.port_name} @ {config.baud_rate}"
                if self.error_logger:
                    self.error_logger.log_info(f"connect_port: {msg}")
                    self.error_logger.log_info(f"connect_port: 发射 connection_status_changed(True, '{msg}')")
                self.connection_status_changed.emit(True, msg)
                if self.error_logger:
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
                if self.error_logger:
                    self.error_logger.log_error(f"connect_port: {msg}", "CONNECTION")
                    self.error_logger.log_info(f"connect_port: 发射 connection_status_changed(False, '{msg}')")
                self.connection_status_changed.emit(False, msg)
                return False

    def disconnect_port(self) -> None:
        if self.error_logger:
            self.error_logger.log_info("尝试断开串口连接")
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
            if self.serial_port and self.serial_port.isOpen(): # Check if serial_port is not None
                self.serial_port.close()
            self.is_connected = False
            self.connection_status_changed.emit(False, "串口已关闭")
            if self.error_logger:
                self.error_logger.log_info("串口已关闭")

    @Slot()
    def _read_data(self) -> None:
        """Qt串口数据读取回调函数"""
        if self.serial_port and self.serial_port.bytesAvailable() > 0:
            data = self.serial_port.readAll()
            if self.error_logger:
                # 修正：确保数据转换正确
                hex_data = data.toHex(' ').data().decode('ascii').upper()
                self.error_logger.log_info(f"接收到 {data.size()} 字节数据 (Qt): {hex_data}")
            self.data_received.emit(data)

    def write_data(self, data: QByteArray) -> int:
        if not self.is_connected:
            if self.error_logger:
                self.error_logger.log_warning("尝试在未连接的串口上写入数据。")
            return -1

        if self.use_pyserial:
            try:
                # 修正：确保数据转换正确
                if self.error_logger:
                    hex_data = data.toHex(' ').data().decode('ascii').upper()
                    self.error_logger.log_info(f"发送数据 (pyserial): {hex_data}")
                
                # 确保数据正确转换为字节
                data_bytes = data.data()
                if isinstance(data_bytes, str):
                    data_bytes = data_bytes.encode('latin-1')
                
                bytes_written = self.serial_port.write(data_bytes)
                return bytes_written
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(f"串口写入错误: {e}", "SEND")
                return -1
        else:
            # 修正：确保数据转换正确
            if self.error_logger:
                hex_data = data.toHex(' ').data().decode('ascii').upper()
                self.error_logger.log_info(f"发送数据 (Qt): {hex_data}")
            
            bytes_written = self.serial_port.write(data)
            if bytes_written == -1:
                if self.error_logger:
                    self.error_logger.log_error(f"串口写入错误: {self.serial_port.errorString()}", "SEND")
            elif bytes_written != data.size():
                if self.error_logger:
                    self.error_logger.log_warning(f"串口部分写入: {bytes_written}/{data.size()}字节。", "SEND")
            return bytes_written

    def _log_and_emit_error(self, message: str, error_type: str = "VALIDATION"):
        """Helper to log and emit connection errors."""
        self.connection_status_changed.emit(False, f"错误: {message}")
        if self.error_logger:
            self.error_logger.log_error(message, error_type)

    def get_current_baud_rate(self) -> Optional[int]:
        if self.is_connected:
            if self.use_pyserial and self.serial_port:
                return self.serial_port.baudrate
            elif self.serial_port and self.serial_port.isOpen():
                return self.serial_port.baudRate()
        return None

    def get_connection_status(self) -> bool:
        return self.is_connected

    @Slot(QSerialPort.SerialPortError)
    def _handle_serial_error(self, error: QSerialPort.SerialPortError) -> None:
        """处理Qt串口错误"""
        if error != QSerialPort.SerialPortError.NoError:
            error_message = self.serial_port.errorString()
            if self.error_logger:
                self.error_logger.log_error(f"Qt串口错误: {error_message}", "SERIAL_ERROR")
            self.error_occurred_signal.emit(error_message)


class SerialReadThread(QThread):
    data_received = Signal(QByteArray)

    def __init__(self, serial_port: serial.Serial, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.serial_port = serial_port
        self._running = True

    def run(self):
        parent = self.parent()
        if parent and hasattr(parent, 'error_logger') and parent.error_logger:
            parent.error_logger.log_info("SerialReadThread started")
        
        while self._running:
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    # 修正：确保数据正确转换为 QByteArray
                    if isinstance(data, bytes):
                        qdata = QByteArray(data)
                    else:
                        qdata = QByteArray(bytes(data))
                    
                    if parent and hasattr(parent, 'error_logger') and parent.error_logger:
                        hex_data = qdata.toHex(' ').data().decode('ascii').upper()
                        parent.error_logger.log_info(f"接收到 {len(data)} 字节数据 (pyserial): {hex_data}")
                    
                    self.data_received.emit(qdata)
                else:
                    # 避免 CPU 占用过高
                    self.msleep(1)
            except Exception as e:
                if parent and hasattr(parent, 'error_logger') and parent.error_logger:
                    parent.error_logger.log_error(f"串口读取错误: {e}", "READ")
                self.msleep(10)  # 出错时稍微等待更长时间
        
        if parent and hasattr(parent, 'error_logger') and parent.error_logger:
            parent.error_logger.log_info("SerialReadThread stopped")

    def stop(self):
        self._running = False
