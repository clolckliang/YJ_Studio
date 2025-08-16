import time
import struct
from typing import Optional, Dict, Any, Tuple
from PySide6.QtCore import QObject, Signal, QByteArray

from core.placeholders import CircularBuffer
from utils.constants import Constants,ChecksumMode
from utils.data_models import FrameConfig
from utils.logger import ErrorLogger
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


def calculate_frame_crc16(frame_part_for_crc: QByteArray) -> int:
    """Calculates CRC-16/CCITT-FALSE over the QByteArray data."""
    return crc16_ccitt_false_func(frame_part_for_crc.data())

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

    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.statistics: Dict[str, Any] = {
            'total_frames_rx': 0,
            'total_frames_tx': 0,
            'error_frames_rx': 0,
            'data_rate_rx_bps': 0,
            'last_rx_time': None,
            'rx_byte_count': 0
        }
        self.error_logger = error_logger

    def analyze_frame(self, frame_data: QByteArray, direction: str, is_error: bool = False) -> None:
        now = time.monotonic() # Using monotonic clock for measuring intervals
        if direction == 'rx':
            self.statistics['total_frames_rx'] += 1
            if is_error:
                self.statistics['error_frames_rx'] += 1

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


class FrameParser(QObject):
    frame_successfully_parsed = Signal(str, QByteArray)  # func_id_hex, data_payload
    frame_parse_error = Signal(str, QByteArray)  # error_message, remaining_buffer_or_faulty_frame
    checksum_error = Signal(str, QByteArray)  # message, faulty_frame

    # (Note: your original had checksum_error_signal)

    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None,
                 buffer_size: int = 1024 * 32):  # Increased default buffer size
        super().__init__(parent)
        self.error_logger = error_logger
        self._parsed_frame_count = 0
        self.buffer = CircularBuffer(buffer_size)  # Using CircularBuffer

    def append_data(self, new_data: QByteArray):
        if not new_data:
            return
        bytes_written = self.buffer.write(new_data)
        if bytes_written < new_data.size():
            # This indicates the circular buffer was full and overwrote old data.
            # This might be acceptable or an error depending on requirements.
            if self.error_logger:
                self.error_logger.log_warning(
                    f"FrameParser: CircularBuffer overflow. Attempted: {new_data.size()}, "
                    f"Written: {bytes_written}. Buffer is full. Oldest data was overwritten."
                )

    def clear_buffer(self):
        self.buffer.clear()
        if self.error_logger:
            self.error_logger.log_debug("FrameParser buffer cleared.")

    def try_parse_frames(self, current_frame_config: FrameConfig,
                         parse_target_func_id_hex: str,  # Kept as per your FrameParser
                         active_checksum_mode: ChecksumMode):
        frame_head_byte = bytes.fromhex(current_frame_config.head)  # 'AB' -> b'\xab'
        frame_head_len = len(frame_head_byte)  # 现在 frame_head_len = 1

        # 检查帧头配置是否为空或长度不为1
        if not frame_head_byte or frame_head_len != 1:
            if self.error_logger:
                self.error_logger.log_error(f"帧头配置无效或长度不为1 ({frame_head_len})，无法解析。", "FRAME_PARSE")
            self.frame_parse_error.emit("帧头配置无效", self.buffer.peek(self.buffer.get_count()))
            return

        head_byte_value = frame_head_byte[0] # 获取帧头字节的整数值

        MAX_ATTEMPTS = 1000
        for _ in range(MAX_ATTEMPTS):
            # 需要至少有帧头长度 (1) 的数据才能尝试匹配帧头
            if self.buffer.get_count() < 1:
                break  # Not enough data for frame head

            # 1. Find Frame Head (single byte)
            # Peek one byte to check if it matches the frame head
            first_byte_ba = self.buffer.peek(1)
            first_byte = first_byte_ba.data() if hasattr(first_byte_ba, 'data') else bytes(first_byte_ba)

            if len(first_byte) < 1 or first_byte[0] != head_byte_value:
                # If the first byte is not the frame head, discard it and continue searching
                self.buffer.discard(1)
                if self.error_logger and len(first_byte) > 0:
                     self.error_logger.log_debug(f"FrameParser: Discarded byte 0x{first_byte[0]:02X}, not frame head 0x{head_byte_value:02X}.")
                elif self.error_logger:
                     self.error_logger.log_debug("FrameParser: Buffer empty or peek failed while looking for head.")
                continue # Continue the while loop to check the next byte

            # At this point, the first byte in the buffer is the frame head.
            # Ensure we have enough data for the minimal header (head + s_addr + d_addr + func_id + len)
            # The minimal header length is Constants.MIN_HEADER_LEN_FOR_DATA_LEN (6 bytes: HEAD(1) + S_ADDR(1) + D_ADDR(1) + FUNC_ID(1) + LEN(2))
            min_header_len = Constants.MIN_HEADER_LEN_FOR_DATA_LEN

            if self.buffer.get_count() < min_header_len:
                if self.error_logger:
                    self.error_logger.log_debug(f"FrameParser: 数据不足以构成最小头部。当前: {self.buffer.get_count()}, 需要: {min_header_len}")
                break

            # Peek the minimal header to get the length field
            header_peek = self.buffer.peek(min_header_len)

            # 2. Extract data length using the correct offset (Constants.OFFSET_LEN = 4 relative to the start of the frame)
            len_field_offset = Constants.OFFSET_LEN # Should be 4

            try:
                # 从 len_field_offset 位置读取2字节长度字段
                len_bytes = header_peek[len_field_offset:len_field_offset + 2]
                if len(len_bytes) < 2:  # This check should ideally be covered by the min_header_len check
                     if self.error_logger: self.error_logger.log_debug("FrameParser: 长度字段不完整")
                     break # Should not happen if previous check passed

                data_len = struct.unpack('<H', len_bytes)[0]  # 小端序 (协议要求)
            except struct.error as e:
                if self.error_logger:
                    self.error_logger.log_error(f"FrameParser: 解析数据长度字段时出错: {e}", "FRAME_PARSE")
                self.frame_parse_error.emit("长度字段解析错误", header_peek)
                self.buffer.discard(1)  # Discard the frame head byte and continue searching
                continue

            # 3. 计算完整帧长度并检查缓冲区数据是否足够
            # 帧总长度 = 最小头部长度 + 数据长度 + 校验和(2字节)
            expected_total_frame_len = Constants.MIN_HEADER_LEN_FOR_DATA_LEN + data_len + Constants.CHECKSUM_FIELD_LENGTH

            if self.buffer.get_count() < expected_total_frame_len:
                # 数据不足以构成完整帧
                if self.error_logger:
                    self.error_logger.log_debug(
                        f"FrameParser: 帧不完整。当前: {self.buffer.get_count()}, 需要: {expected_total_frame_len}")
                break

            # 4. 获取完整帧数据
            current_frame_ba = self.buffer.peek(expected_total_frame_len)
            frame_part_for_calc = current_frame_ba.left(expected_total_frame_len - Constants.CHECKSUM_FIELD_LENGTH)
            received_checksum_ba = current_frame_ba.mid(expected_total_frame_len - Constants.CHECKSUM_FIELD_LENGTH,
                                                        Constants.CHECKSUM_FIELD_LENGTH)

            is_valid = False
            error_msg = ""

            # 在 try_parse_frames 方法中的校验和验证部分
            if active_checksum_mode == ChecksumMode.CRC16_CCITT_FALSE:
                if received_checksum_ba.size() == 2:
                    # 修正：根据协议规范确定字节序
                    # 假设 CRC16 使用小端序存储（与数据长度字段一致）
                    received_crc_val = struct.unpack('<H', received_checksum_ba.data())[0]
                    calculated_crc_val = calculate_frame_crc16(frame_part_for_calc)
                    if received_crc_val == calculated_crc_val:
                        is_valid = True
                    else:
                        error_msg = f"CRC校验失败! Recv:0x{received_crc_val:04X}, Calc:0x{calculated_crc_val:04X}"
                else:
                    error_msg = f"CRC校验错误: 校验和长度不足 (需要 2 字节)"
            else:  # ORIGINAL_SUM_ADD
                if received_checksum_ba.size() == Constants.CHECKSUM_FIELD_LENGTH:
                    received_checksum_data = received_checksum_ba.data()
                    received_sc_val = received_checksum_data[0]
                    received_ac_val = received_checksum_data[1]
                    
                    # 确保字节值正确转换
                    if isinstance(received_sc_val, str):
                        received_sc_val = ord(received_sc_val)
                    if isinstance(received_ac_val, str):
                        received_ac_val = ord(received_ac_val)
                    
                    calculated_sc, calculated_ac = calculate_original_checksums_python(frame_part_for_calc)
                    
                    if received_sc_val == calculated_sc and received_ac_val == calculated_ac:
                        is_valid = True
                    else:
                        error_msg = (f"原始校验失败! RecvSC:0x{received_sc_val:02X},CalcSC:0x{calculated_sc:02X}; "
                                   f"RecvAC:0x{received_ac_val:02X},CalcAC:0x{calculated_ac:02X}")
                else:
                    error_msg = f"原始校验和错误: 校验和长度不足 (需要 {Constants.CHECKSUM_FIELD_LENGTH} 字节)"

            if is_valid:
                self._parsed_frame_count += 1
                # 功能码位置：Constants.OFFSET_FUNC_ID (5)
                func_id_offset = Constants.OFFSET_FUNC_ID
                func_id_recv_ba = frame_part_for_calc.mid(func_id_offset, 1)

                # 数据段位置：Constants.OFFSET_DATA_START (6)
                data_content_offset = Constants.OFFSET_DATA_START
                data_content_recv_ba = frame_part_for_calc.mid(data_content_offset, data_len)

                # 将功能码字节数组转换为十六进制字符串（大写）
                func_id_hex_str = func_id_recv_ba.toHex().data().decode('ascii').upper()

                # 调试日志：记录解析结果
                if self.error_logger:
                    hex_frame = current_frame_ba.toHex(' ').data().decode()
                    self.error_logger.log_info(f"FrameParser: 成功解析帧! FID={func_id_hex_str}, 长度={data_len}, 数据={data_content_recv_ba.toHex(' ').data().decode()}, 完整帧: {hex_frame}")

                # Filter by target FuncID if provided (as per your original FrameParser logic)
                try:
                    target_fid_ba = QByteArray.fromHex(parse_target_func_id_hex.encode('ascii'))
                except ValueError:  # Handle case where parse_target_func_id_hex is invalid hex
                    target_fid_ba = QByteArray()
                    if self.error_logger and parse_target_func_id_hex:
                        self.error_logger.log_warning(
                            f"FrameParser: Invalid target FuncID hex '{parse_target_func_id_hex}' in config.")

                if not parse_target_func_id_hex or func_id_recv_ba == target_fid_ba:  # If no target, or target matches
                    self.frame_successfully_parsed.emit(func_id_hex_str, data_content_recv_ba)

                self.buffer.discard(expected_total_frame_len)  # Consume the valid frame
                if self.error_logger:
                    self.error_logger.log_debug(
                        f"FrameParser: Successfully parsed frame FID {func_id_hex_str}, discarded {expected_total_frame_len} bytes.")
            else:
                self.checksum_error.emit(error_msg, current_frame_ba)  # Emit with specific error message
                if self.error_logger:
                    hex_frame = current_frame_ba.toHex(' ').data().decode()
                    self.error_logger.log_warning(
                        f"FrameParser: {error_msg} Frame: {hex_frame}")
                # Discard the frame head byte and continue searching
                self.buffer.discard(1)
        # End of while loop
