import time
import struct
from typing import Optional, Dict, Any, Tuple, List
from PySide6.QtCore import QObject, Signal, QByteArray, QTimer
from dataclasses import dataclass
from enum import Enum

from core.placeholders import CircularBuffer
from utils.constants import Constants,ChecksumMode
from utils.data_models import FrameConfig
from utils.logger import ErrorLogger
from utils.protocol_config_manager import get_global_config_manager, ProtocolConfigManager
from core.protocol_errors import ProtocolError, ProtocolException, ChecksumMismatchError, FrameParseError, BufferOverflowError
from core.protocol_decoder import ProtocolDecoder
from utils.config_accessor import ConfigManager
import crcmod


# --- CRC-16/CCITT-FALSE Function ---
# Define it once, can be reused
crc16_func = crcmod.predefined.mkCrcFun('crc-ccitt-false')
# Alternative manual definition if 'crc-ccitt-false' is not directly available
# or if you need specific parameters:
# crc16_func = crcmod.mkCrcFun(poly=0x11021, initCrc=0xFFFF, rev=False, xorOut=0x0000)
# Note: Standard CRC-16/CCITT-FALSE (often just "crc-ccitt") uses poly 0x1021.
# crcmod's 'crc-ccitt-false' might be an alias or a specific interpretation.
# Let's use the standard 0x1021 polynomial.
# Standard CRC-16 CCITT: poly=0x1021, initCrc=0xFFFF, rev=False, xorOut=0x0000
# If you want the result as used in X.25, Kermit, then initCrc might be 0x0000 or rev=True.
# For "CCITT-FALSE", typically initCrc=0xFFFF, rev=False.

# Sticking to the common CRC-16/CCITT-FALSE (often referred to as Kermit's variant of CCITT)
# Poly: 0x1021, Initial Value: 0xFFFF (some use 0x0000 then XOR, but 0xFFFF is common)
# Reflected Input: No, Reflected Output: No, XOR Out: 0x0000
# Let's define it explicitly to ensure parameters are clear:
crc16_ccitt_false_func = crcmod.mkCrcFun(poly=0x11021, initCrc=0xFFFF, rev=False, xorOut=0x0000)


@dataclass
class PendingFrame:
    """待重传帧数据结构"""
    data: bytes
    dest_addr: int
    func_id: int
    send_time: float
    retry_count: int = 0
    seq_num: int = 0
    max_retries: int = 3
    timeout_ms: int = 1000

def calculate_original_checksums_python(frame_part_data: QByteArray) -> Tuple[int, int]:
    """Python 实现的原始求和/累加校验算法，与 C 语言实现保持一致"""
    s_check = 0
    a_check = 0
    
    # 确保与 C 语言实现的字节处理方式一致
    data_bytes = frame_part_data.data()
    for byte_val in data_bytes:
        # 确保字节值在 0-255 范围内
        if isinstance(byte_val, int):
            byte_val = byte_val & 0xFF
        else:
            byte_val = ord(byte_val) & 0xFF
            
        s_check = (s_check + byte_val) & 0xFF
        a_check = (a_check + s_check) & 0xFF
    
    return s_check, a_check

def calculate_frame_crc16(frame_part_for_crc: QByteArray) -> int:
    """计算 CRC-16/CCITT-FALSE 校验和"""
    try:
        data_bytes = frame_part_for_crc.data()
        return crc16_ccitt_false_func(data_bytes)
    except Exception as e:
        # 如果出现错误，返回0并记录日志
        print(f"CRC16 计算错误: {e}")
        return 0

# 移除旧的有问题的 calculate_checksums 函数
# def calculate_checksums(frame_without_checksums: QByteArray) -> Tuple[bytes, bytes]:
#     # 这个函数有问题，已被 calculate_original_checksums_python 替代

class ProtocolAnalyzer(QObject): # Making it a QObject if it needs to emit signals later
    # statistics_updated = Signal(dict) # Example if stats updates were signaled
    checksum_error_signal = Signal(str, QByteArray)  # Generic name
    performance_warning = Signal(str)  # 性能警告信号

    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.statistics: Dict[str, Any] = {
            'total_frames_rx': 0,
            'total_frames_tx': 0,
            'error_frames_rx': 0,
            'data_rate_rx_bps': 0,
            'last_rx_time': None,
            'rx_byte_count': 0,
            'buffer_overflows': 0,
            'retransmissions': 0,
            'timeouts': 0,
            'avg_parse_time_ms': 0.0,
            'max_parse_time_ms': 0.0
        }
        self.error_logger = error_logger

    def analyze_frame(self, frame_data: QByteArray, direction: str, is_error: bool = False, 
                     parse_time_ms: float = 0.0, error_type: Optional[ProtocolError] = None) -> None:
        now = time.monotonic() # Using monotonic clock for measuring intervals
        
        # 更新解析时间统计
        if parse_time_ms > 0:
            if direction == 'rx':
                current_avg = self.statistics['avg_parse_time_ms']
                total_frames = self.statistics['total_frames_rx']
                if total_frames > 0:
                    self.statistics['avg_parse_time_ms'] = (current_avg * (total_frames - 1) + parse_time_ms) / total_frames
                else:
                    self.statistics['avg_parse_time_ms'] = parse_time_ms
                self.statistics['max_parse_time_ms'] = max(self.statistics['max_parse_time_ms'], parse_time_ms)
                
                # 性能警告
                if parse_time_ms > 10.0:  # 超过10ms警告
                    self.performance_warning.emit(f"帧解析耗时过长: {parse_time_ms:.2f}ms")
        
        if direction == 'rx':
            self.statistics['total_frames_rx'] += 1
            if is_error:
                self.statistics['error_frames_rx'] += 1
                if error_type == ProtocolError.BUFFER_OVERFLOW:
                    self.statistics['buffer_overflows'] += 1
                elif error_type == ProtocolError.TIMEOUT:
                    self.statistics['timeouts'] += 1

            current_byte_count = len(frame_data)
            self.statistics['rx_byte_count'] += current_byte_count

            if self.statistics['last_rx_time'] is not None:
                time_delta = now - self.statistics['last_rx_time']
                if time_delta > 0:
                    # bps for this frame, or average? Original code implies for current frame based on time since last.
                    self.statistics['data_rate_rx_bps'] = (current_byte_count * 8) / time_delta
            self.statistics['last_rx_time'] = now
            # self.statistics_updated.emit(self.statistics.copy())
        elif direction == 'tx':
            self.statistics['total_frames_tx'] += 1
            if error_type == ProtocolError.TIMEOUT:
                self.statistics['retransmissions'] += 1
            # self.statistics_updated.emit(self.statistics.copy())


    def get_statistics(self) -> Dict[str, Any]:
        return self.statistics.copy() # Return a copy

    def reset_statistics(self) -> None:
        for key in self.statistics:
            if isinstance(self.statistics[key], (int, float)):
                self.statistics[key] = 0
            elif isinstance(self.statistics[key], dict): # Should not happen with current structure
                 self.statistics[key].clear()
        self.statistics['last_rx_time'] = None
        if self.error_logger:
            self.error_logger.log_info("协议分析统计已重置。")
        # self.statistics_updated.emit(self.statistics.copy())


def calculate_checksums(frame_without_checksums: QByteArray) -> Tuple[bytes, bytes]:
    sum_check = 0
    add_check = 0
    for i in range(frame_without_checksums.length()):
        byte_val = frame_without_checksums.at(i) # This returns a char, need to convert to int
        # QByteArray.at() returns a char. Convert to int using ord()
        # Or, iterate over the QByteArray as bytes:
    # Corrected checksum calculation
    data_bytes = frame_without_checksums.data() # Get as bytes
    for byte_val in data_bytes:
        sum_check = (sum_check + byte_val) & 0xFF
        add_check = (add_check + sum_check) & 0xFF
    return bytes([sum_check]), bytes([add_check])


def get_data_type_byte_length(data_type_str: str) -> int:
    return Constants.DATA_TYPE_SIZES.get(data_type_str, 0)


# ProtocolSender 类将在 FrameParser 类之后定义


class FrameParser(QObject):
    frame_successfully_parsed = Signal(str, QByteArray)  # func_id_hex, data_payload
    frame_parse_error = Signal(str, QByteArray)  # error_message, remaining_buffer_or_faulty_frame
    checksum_error = Signal(str, QByteArray)  # message, faulty_frame
    ack_received = Signal(int)  # sequence_number
    nack_received = Signal(int, str)  # sequence_number, error_reason
    retransmission_needed = Signal(int)  # sequence_number

    # (Note: your original had checksum_error_signal)

    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None,
                 buffer_size: int = 1024 * 32, config_manager: Optional[ProtocolConfigManager] = None):  # Increased default buffer size
        super().__init__(parent)
        self.error_logger = error_logger
        self._parsed_frame_count = 0
        
        # 配置管理器
        self.config_manager = config_manager or get_global_config_manager()
        self.config = ConfigManager(self.config_manager)
        
        # 根据配置初始化缓冲区
        actual_buffer_size = self.config.performance.buffer_size
        self.buffer = CircularBuffer(actual_buffer_size)  # Using CircularBuffer
        
        # 重传和ACK机制
        self._pending_frames: Dict[int, PendingFrame] = {}
        self._next_seq_num = 0
        self._ack_enabled = self.config.ack_mechanism.enabled
        self._window_size = self.config.ack_mechanism.window_size
        self._retry_timer = QTimer()
        self._retry_timer.timeout.connect(self._check_timeouts)
        self._retry_timer.start(100)  # 每100ms检查一次超时
        
        # 性能优化
        self._max_buffer_usage = 0
        self._parse_time_samples = []
        self._analyzer = ProtocolAnalyzer(error_logger, self)
        
        # 初始化协议解码器
        self._decoder = ProtocolDecoder(error_logger=self.error_logger, parent=self)
        self._decoder.frame_decoded.connect(self._on_frame_decoded)
        self._decoder.decode_error.connect(self._on_decode_error)
        self._decoder.checksum_error.connect(self._on_checksum_error)
        
        # 连接配置更新信号
        self.config.connect_config_updated(self._on_config_updated)
    
    def __del__(self):
        """析构函数，确保资源正确释放"""
        self.cleanup()
    
    def cleanup(self):
        """清理资源，防止内存泄漏"""
        try:
            # 停止并清理定时器
            if hasattr(self, '_retry_timer') and self._retry_timer:
                self._retry_timer.stop()
                self._retry_timer.timeout.disconnect()
                self._retry_timer.deleteLater()
                self._retry_timer = None
            
            # 断开配置管理器信号连接
            if hasattr(self, 'config') and self.config.has_config_updated_signal():
                try:
                    self.config.disconnect_config_updated(self._on_config_updated)
                except (TypeError, RuntimeError):
                    pass  # 信号可能已经断开
            
            # 清理缓冲区
            if hasattr(self, 'buffer'):
                self.buffer.clear()
            
            # 清理待重传帧
            if hasattr(self, '_pending_frames'):
                self._pending_frames.clear()
            
            # 清理分析器
            if hasattr(self, '_analyzer'):
                self._analyzer = None
            
            # 清理解码器
            if hasattr(self, '_decoder'):
                try:
                    self._decoder.frame_decoded.disconnect(self._on_frame_decoded)
                    self._decoder.decode_error.disconnect(self._on_decode_error)
                    self._decoder.checksum_error.disconnect(self._on_checksum_error)
                except (TypeError, RuntimeError):
                    pass
                self._decoder = None
                
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"FrameParser cleanup error: {e}", "CLEANUP")

    def append_data(self, new_data: QByteArray):
        if not new_data:
            return
        
        # 性能监控：缓冲区使用率
        current_usage = (self.buffer.get_count() + new_data.size()) / self.buffer.capacity * 100
        self._max_buffer_usage = max(self._max_buffer_usage, current_usage)
        
        warning_threshold = self.config.performance.buffer_usage_warning_percent
        if current_usage > warning_threshold:  # 缓冲区使用率超过阈值警告
            self._analyzer.performance_warning.emit(f"缓冲区使用率过高: {current_usage:.1f}%")
        
        bytes_written = self.buffer.write(new_data)
        if bytes_written < new_data.size():
            # This indicates the circular buffer was full and overwrote old data.
            # This might be acceptable or an error depending on requirements.
            self._analyzer.analyze_frame(new_data, "rx", True, 0.0, ProtocolError.BUFFER_OVERFLOW)
            if self.error_logger:
                self.error_logger.log_warning(
                    f"FrameParser: CircularBuffer overflow. Attempted: {new_data.size()}, "
                    f"Written: {bytes_written}. Buffer is full. Oldest data was overwritten."
                )

    def clear_buffer(self):
        self.buffer.clear()
        if self.error_logger:
            self.error_logger.log_debug("FrameParser buffer cleared.")
    
    def _check_timeouts(self):
        """检查超时的待重传帧"""
        current_time = time.time() * 1000  # 转换为毫秒
        timeout_frames = []
        
        default_timeout = self.config.ack_mechanism.default_timeout_ms
        
        for seq_num, frame in self._pending_frames.items():
            timeout_ms = getattr(frame, 'timeout_ms', default_timeout)
            if current_time - frame.send_time > timeout_ms:
                timeout_frames.append(seq_num)
        
        for seq_num in timeout_frames:
            frame = self._pending_frames[seq_num]
            max_retries = self.config.ack_mechanism.max_retries
            if frame.retry_count < max_retries:
                frame.retry_count += 1
                frame.send_time = current_time
                self.retransmission_needed.emit(seq_num)
                if self.error_logger and self.config.debugging.verbose_error_messages:
                    self.error_logger.log_warning(f"帧重传 seq={seq_num}, 重试次数={frame.retry_count}")
            else:
                del self._pending_frames[seq_num]
                self._analyzer.analyze_frame(QByteArray(), "tx", True, 0.0, ProtocolError.TIMEOUT)
                if self.error_logger and self.config.debugging.verbose_error_messages:
                    self.error_logger.log_error(f"帧传输失败 seq={seq_num}, 超过最大重试次数")
    
    def send_frame_with_ack(self, dest_addr: int, func_id: int, data: bytes, 
                           max_retries: int = None, timeout_ms: int = None) -> int:
        """发送需要ACK确认的帧"""
        if not self._ack_enabled:
            return -1
        
        if len(self._pending_frames) >= self._window_size:
            if self.error_logger and self.config.debugging.verbose_error_messages:
                self.error_logger.log_warning("发送窗口已满，无法发送新帧")
            return -1
        
        seq_num = self._next_seq_num
        self._next_seq_num = (self._next_seq_num + 1) % 65536
        
        # 使用配置管理器的默认值
        if max_retries is None:
            max_retries = self.config.ack_mechanism.max_retries
        if timeout_ms is None:
            timeout_ms = self.config.ack_mechanism.default_timeout_ms
        
        frame = PendingFrame(
            data=data,
            dest_addr=dest_addr,
            func_id=func_id,
            send_time=time.time() * 1000,
            seq_num=seq_num,
            max_retries=max_retries,
            timeout_ms=timeout_ms
        )
        
        self._pending_frames[seq_num] = frame
        return seq_num
    
    def handle_ack(self, seq_num: int):
        """处理ACK确认"""
        if seq_num in self._pending_frames:
            del self._pending_frames[seq_num]
            self.ack_received.emit(seq_num)
            if self.error_logger:
                self.error_logger.log_debug(f"收到ACK确认 seq={seq_num}")
    
    def handle_nack(self, seq_num: int, error_reason: str):
        """处理NACK否定确认"""
        if seq_num in self._pending_frames:
            frame = self._pending_frames[seq_num]
            if frame.retry_count < frame.max_retries:
                frame.retry_count += 1
                frame.send_time = time.time() * 1000
                self.retransmission_needed.emit(seq_num)
                self.nack_received.emit(seq_num, error_reason)
                if self.error_logger:
                    self.error_logger.log_warning(f"收到NACK seq={seq_num}, 原因={error_reason}, 重试={frame.retry_count}")
            else:
                del self._pending_frames[seq_num]
                if self.error_logger:
                    self.error_logger.log_error(f"NACK重试失败 seq={seq_num}, 超过最大重试次数")
    
    def set_ack_enabled(self, enabled: bool):
        """启用/禁用ACK机制"""
        self._ack_enabled = enabled
        if not enabled:
            self._pending_frames.clear()
    
    def set_window_size(self, size: int):
        """设置滑动窗口大小"""
        self._window_size = max(1, min(size, 32))  # 限制在1-32之间
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            'max_buffer_usage_percent': self._max_buffer_usage,
            'pending_frames_count': len(self._pending_frames),
            'window_size': self._window_size,
            'ack_enabled': self._ack_enabled,
            'parsed_frame_count': self._parsed_frame_count,
            'config_manager_active': self.config_manager is not None
        }
    
    def _on_config_updated(self):
        """配置更新时的回调函数"""
        self._ack_enabled = self.config.ack_mechanism.enabled
        self._window_size = self.config.ack_mechanism.window_size
        
        if self.error_logger:
            self.error_logger.log_info("协议处理器配置已更新")
    
    def _on_frame_decoded(self, parsed_frame):
        """处理解码成功的帧"""
        # 发射原有的信号以保持兼容性
        self.frame_successfully_parsed.emit(parsed_frame.func_id_hex, parsed_frame.data_payload)
        
        # 检查是否为ACK/NACK帧
        if parsed_frame.func_id_hex in ['ACK', 'NACK']:  # 根据实际协议调整
            self._handle_ack_nack_frame(parsed_frame)
    
    def _on_decode_error(self, error_message: str, frame_data):
        """处理解码错误"""
        self.frame_parse_error.emit(error_message, frame_data)
    
    def _on_checksum_error(self, error_message: str, frame_data):
        """处理校验和错误"""
        self.checksum_error.emit(error_message, frame_data)
    
    def _handle_ack_nack_frame(self, parsed_frame):
        """处理ACK/NACK帧"""
        try:
            # 这里需要根据实际协议格式解析序列号
            # 示例实现，需要根据具体协议调整
            if len(parsed_frame.data_payload) >= 2:
                seq_num = struct.unpack('>H', parsed_frame.data_payload[:2])[0]
                
                if parsed_frame.func_id_hex == 'ACK':
                    self.ack_received.emit(seq_num)
                elif parsed_frame.func_id_hex == 'NACK':
                    error_reason = parsed_frame.data_payload[2:].data().decode('utf-8', errors='ignore') if len(parsed_frame.data_payload) > 2 else "Unknown error"
                    self.nack_received.emit(seq_num, error_reason)
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"ACK/NACK frame handling error: {e}", "ACK_NACK")

    def try_parse_frames(self, current_frame_config: FrameConfig,
                         parse_target_func_id_hex: str,  # Kept as per your FrameParser
                         active_checksum_mode: ChecksumMode):
        """尝试解析缓冲区中的帧数据（使用ProtocolDecoder）"""
        parse_start_time = time.time()
        frames_parsed_this_call = 0
        
        # 限制单次解析的帧数，防止阻塞
        max_frames_per_parse = self.config.performance.max_frames_per_parse
        
        frame_head_byte = bytes.fromhex(current_frame_config.head)
        frame_head_len = len(frame_head_byte)

        # 检查帧头配置
        if not frame_head_byte or frame_head_len != 1:
            if self.error_logger:
                self.error_logger.log_error(f"帧头配置无效或长度不为1 ({frame_head_len})，无法解析。", "FRAME_PARSE")
            self.frame_parse_error.emit("帧头配置无效", self.buffer.peek(self.buffer.get_count()))
            return

        head_byte_value = frame_head_byte[0]
        
        # 使用新的解析逻辑
        for _ in range(max_frames_per_parse):
            # 检查是否有足够数据
            if self.buffer.get_count() < 1:
                break

            # 查找帧头
            first_byte_ba = self.buffer.peek(1)
            first_byte = first_byte_ba.data() if hasattr(first_byte_ba, 'data') else bytes(first_byte_ba)

            if len(first_byte) < 1 or first_byte[0] != head_byte_value:
                self.buffer.discard(1)
                if self.error_logger and len(first_byte) > 0:
                    self.error_logger.log_debug(f"FrameParser: Discarded byte 0x{first_byte[0]:02X}, not frame head 0x{head_byte_value:02X}.")
                continue

            # 尝试提取完整帧
            frame_data = self._extract_complete_frame(current_frame_config)
            if not frame_data:
                break  # 数据不足，等待更多数据
            
            # 使用ProtocolDecoder解析帧
            parsed_frame = self._decoder.decode_frame(
                frame_data, current_frame_config, active_checksum_mode, parse_target_func_id_hex
            )
            
            if parsed_frame:
                frames_parsed_this_call += 1
                # 性能统计
                frame_parse_time = (time.time() - parse_start_time) * 1000
                self._analyzer.analyze_frame(frame_data, "rx", False, frame_parse_time)
            
            # 从缓冲区移除已处理的帧
            self.buffer.discard(len(frame_data))
        
        # 总体性能统计
        total_parse_time = (time.time() - parse_start_time) * 1000
        parse_warning_threshold = self.config.performance.parse_timeout_warning_ms
        if total_parse_time > parse_warning_threshold:
            self._analyzer.performance_warning.emit(f"帧解析总耗时过长: {total_parse_time:.2f}ms, 解析帧数: {frames_parsed_this_call}")
    
    def _extract_complete_frame(self, frame_config: FrameConfig) -> Optional[QByteArray]:
        """从缓冲区提取完整的帧数据"""
        try:
            # 检查最小头部长度
            min_header_len = Constants.MIN_HEADER_LEN_FOR_DATA_LEN
            if self.buffer.get_count() < min_header_len:
                return None
            
            # 获取头部数据以解析数据长度
            header_peek = self.buffer.peek(min_header_len)
            
            # 解析数据长度（偏移量为Constants.OFFSET_LEN）
            len_field_offset = Constants.OFFSET_LEN
            
            # 从头部数据中提取数据长度
            len_bytes = header_peek[len_field_offset:len_field_offset + 2]
            if len(len_bytes) < 2:
                return None
            
            try:
                data_len = struct.unpack('<H', len_bytes)[0]  # 小端序
            except struct.error:
                return None
            
            # 计算完整帧长度
            expected_total_frame_len = Constants.MIN_HEADER_LEN_FOR_DATA_LEN + data_len + Constants.CHECKSUM_FIELD_LENGTH
            
            # 检查缓冲区是否有足够数据
            if self.buffer.get_count() < expected_total_frame_len:
                return None
            
            # 检查帧长度是否超过最大限制
            if expected_total_frame_len > frame_config.max_frame_length:
                if self.error_logger:
                    self.error_logger.log_warning(f"Frame too long: {expected_total_frame_len} > {frame_config.max_frame_length}")
                return None
            
            # 提取完整帧数据
            return self.buffer.peek(expected_total_frame_len)
            
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"Extract frame error: {str(e)}", "EXTRACT")
            return None


class ProtocolSender(QObject):
    """协议发送器，支持重传和ACK机制"""
    frame_sent = Signal(int, bytes)  # seq_num, frame_data
    send_failed = Signal(int, str)   # seq_num, error_reason
    
    def __init__(self, frame_parser: FrameParser, send_func, error_logger: Optional[ErrorLogger] = None, config_manager: Optional[ProtocolConfigManager] = None):
        super().__init__()
        self.frame_parser = frame_parser
        self.send_func = send_func  # 实际发送函数
        self.error_logger = error_logger
        self.config_manager = config_manager or get_global_config_manager()
        self.config = ConfigManager(self.config_manager)
        
        # 连接信号
        self.frame_parser.retransmission_needed.connect(self._handle_retransmission)
        self.frame_parser.ack_received.connect(self._handle_ack_received)
        self.frame_parser.nack_received.connect(self._handle_nack_received)
    
    def __del__(self):
        """析构函数，确保资源正确释放"""
        self.cleanup()
    
    def cleanup(self):
        """清理资源，防止内存泄漏"""
        try:
            # 断开与FrameParser的信号连接
            if hasattr(self, 'frame_parser') and self.frame_parser:
                try:
                    self.frame_parser.retransmission_needed.disconnect(self._handle_retransmission)
                    self.frame_parser.ack_received.disconnect(self._handle_ack_received)
                    self.frame_parser.nack_received.disconnect(self._handle_nack_received)
                except (TypeError, RuntimeError):
                    pass  # 信号可能已经断开
            
            # 清理引用
            self.frame_parser = None
            self.send_func = None
            self.error_logger = None
            self.config_manager = None
                
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"ProtocolSender cleanup error: {e}", "CLEANUP")
        
        # 连接配置更新信号
        self.config.connect_config_updated(self._on_config_updated)
    
    def send_frame(self, dest_addr: int, func_id: int, data: bytes, 
                  use_ack: bool = True, max_retries: int = 3, timeout_ms: int = 1000) -> bool:
        """发送帧数据，支持ACK机制"""
        try:
            if use_ack and self.frame_parser._ack_enabled:
                # 使用ACK机制发送
                seq_num = self.frame_parser.send_frame_with_ack(
                    dest_addr, func_id, data, max_retries, timeout_ms
                )
                return seq_num >= 0
            else:
                # 直接发送，不等待ACK
                frame_data = self._build_frame(dest_addr, func_id, data)
                success = self._send_raw_frame(frame_data)
                if success:
                    self.frame_sent.emit(0, frame_data)  # seq_num=0 表示无ACK
                return success
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    "SEND_FAILED", 
                    f"发送帧失败: {str(e)}",
                    {"dest_addr": dest_addr, "func_id": func_id, "data_len": len(data)}
                )
            self.send_failed.emit(0, str(e))
            return False
    
    def send_ack(self, seq_num: int, dest_addr: int) -> bool:
        """发送ACK确认帧"""
        ack_func_code = getattr(self.config_manager.frame_format, 'ack_func_code', 0xF0)
        ack_data = struct.pack('<H', seq_num)  # 序列号作为数据
        return self.send_frame(dest_addr, ack_func_code, ack_data, use_ack=False)
    
    def send_nack(self, seq_num: int, dest_addr: int, error_reason: str = "") -> bool:
        """发送NACK否定确认帧"""
        nack_func_code = getattr(self.config_manager.frame_format, 'nack_func_code', 0xF1)
        nack_data = struct.pack('<H', seq_num) + error_reason.encode('utf-8')[:32]  # 序列号+错误原因
        return self.send_frame(dest_addr, nack_func_code, nack_data, use_ack=False)
    
    def _build_frame(self, dest_addr: int, func_id: int, data: bytes) -> bytes:
        """构建标准帧"""
        frame_header = getattr(self.config_manager.frame_format, 'frame_header', [0xAA, 0x55])
        source_addr = getattr(self.config_manager.frame_format, 'source_addr', 0x01)
        
        frame = bytearray()
        
        # 帧头
        frame.extend(frame_header)
        
        # 地址和功能码
        frame.append(dest_addr)
        frame.append(source_addr)
        frame.append(func_id)
        
        # 数据长度和数据
        frame.extend(struct.pack('<H', len(data)))
        frame.extend(data)
        
        # 计算并添加校验和
        checksum = self._calculate_checksum(frame)
        frame.extend(checksum)
        
        return bytes(frame)
    
    def _build_frame_with_seq(self, dest_addr: int, func_id: int, data: bytes, seq_num: int) -> bytes:
        """构建带序列号的帧"""
        # 在数据前添加序列号
        seq_data = struct.pack('<H', seq_num) + data
        return self._build_frame(dest_addr, func_id, seq_data)
    
    def _calculate_checksum(self, frame_data: bytearray) -> bytes:
        """计算校验和"""
        checksum_mode = getattr(self.config_manager.frame_format, 'checksum_mode', 'original')
        
        if checksum_mode == 'crc16':
            # CRC16校验
            crc_value = crc16_func(frame_data)
            return struct.pack('<H', crc_value)
        else:
            # 原始校验模式
            checksum1 = sum(frame_data) & 0xFF
            checksum2 = 0
            for i, byte_val in enumerate(frame_data):
                checksum2 += (i + 1) * byte_val
            checksum2 &= 0xFF
            return bytes([checksum1, checksum2])
    
    def _send_raw_frame(self, frame_data: bytes) -> bool:
        """发送原始帧数据"""
        try:
            if self.send_func:
                self.send_func(frame_data)
                return True
            return False
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    "RAW_SEND_FAILED", 
                    f"原始帧发送失败: {str(e)}",
                    {"frame_len": len(frame_data)}
                )
            return False
    
    def _handle_retransmission(self, seq_num: int):
        """处理重传请求"""
        # 这个方法由FrameParser调用，实际重传逻辑在FrameParser中
        pass
    
    def _handle_ack_received(self, seq_num: int):
        """处理ACK接收"""
        # 这个方法由FrameParser调用，实际处理逻辑在FrameParser中
        pass
    
    def _handle_nack_received(self, seq_num: int, error_reason: str):
        """处理NACK接收"""
        # 这个方法由FrameParser调用，实际处理逻辑在FrameParser中
        pass
    
    def get_pending_count(self) -> int:
        """获取待发送帧数量"""
        return len(getattr(self.frame_parser, 'pending_frames', {}))
    
    def clear_pending_frames(self):
        """清除所有待发送帧"""
        if hasattr(self.frame_parser, 'pending_frames'):
            self.frame_parser.pending_frames.clear()
    
    def _on_config_updated(self):
        """配置更新回调"""
        # 重新获取配置参数
        pass
