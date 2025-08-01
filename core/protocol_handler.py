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
    """ Python equivalent of the C original sum/add checksum """
    s_check = 0
    a_check = 0
    for byte_val in frame_part_data.data(): # Iterate over bytes
        s_check = (s_check + byte_val) & 0xFF
        a_check = (a_check + s_check) & 0xFF
    return s_check, a_check

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
        try:
            head_byte_int = int(current_frame_config.head, 16)
        except ValueError:
            if self.error_logger:
                self.error_logger.log_error(f"帧头配置无效 '{current_frame_config.head}'，无法解析。", "FRAME_PARSE")
            self.frame_parse_error.emit(f"帧头配置无效 '{current_frame_config.head}'",
                                        self.buffer.peek(self.buffer.get_count()))
            return

        while True:  # Loop to parse all possible frames in buffer
            if self.buffer.get_count() < Constants.MIN_HEADER_LEN_FOR_DATA_LEN:
                break  # Not enough data for even the smallest header to read data_len

            # 1. Find Frame Head
            head_found_at_index = -1
            # Peek a reasonable amount or the whole buffer if small. Peeking all can be inefficient if buffer is huge.
            # Let's peek up to a certain limit or current count, whichever is smaller.
            peek_len = min(self.buffer.get_count(), 2048)  # Peek up to 2KB to find head
            peeked_data = self.buffer.peek(peek_len)

            for i in range(peeked_data.size()):
                if peeked_data.data()[i] == head_byte_int:
                    head_found_at_index = i
                    break

            if head_found_at_index == -1:
                # No head found in the peeked data.
                # If buffer is very large and no head, we might want to discard some.
                # Your original logic had a threshold. Let's adapt that.
                if self.buffer.get_count() > 4096:  # Configurable threshold
                    discard_amount = self.buffer.get_count() - 2048  # Keep last 2KB
                    self.buffer.discard(discard_amount)
                    if self.error_logger:
                        self.error_logger.log_warning(
                            f"接收缓冲区 ({self.buffer.get_count()}) 过大且未找到帧头，已丢弃 {discard_amount} 字节。")
                break  # Exit parsing loop, wait for more data

            if head_found_at_index > 0:
                # Discard data before the found frame head
                self.buffer.discard(head_found_at_index)
                if self.error_logger:
                    self.error_logger.log_debug(
                        f"FrameParser: Discarded {head_found_at_index} bytes before frame head.")
                # After discarding, re-check if enough data for header
                if self.buffer.get_count() < Constants.MIN_HEADER_LEN_FOR_DATA_LEN:
                    break

                    # At this point, the head of the frame should be at self.buffer.tail
            # Re-peek for consistent processing from the start of the (potential) frame
            if self.buffer.get_count() < Constants.MIN_HEADER_LEN_FOR_DATA_LEN:  # Should be redundant but safe
                break

            header_peek = self.buffer.peek(Constants.MIN_HEADER_LEN_FOR_DATA_LEN)

            # 2. Extract data length
            try:
                # Assuming OFFSET_LEN_LOW is the start of the 2-byte length field from the beginning of the frame
                len_bytes = header_peek.mid(Constants.OFFSET_LEN_LOW, 2)
                if len_bytes.size() < 2:  # Should not happen due to MIN_HEADER_LEN_FOR_DATA_LEN check
                    if self.error_logger: self.error_logger.log_debug("FrameParser: Incomplete length field.")
                    break
                data_len = struct.unpack('<H', len_bytes.data())[0]  # Little Endian
            except struct.error as e:
                if self.error_logger:
                    self.error_logger.log_error(f"FrameParser: 解析数据长度字段时出错: {e}", "FRAME_PARSE")
                self.frame_parse_error.emit("长度字段解析错误", header_peek)
                self.buffer.discard(1)  # Skip one byte (the assumed head) and retry
                continue  # Try parsing from the next byte

            # 3. Calculate expected total frame length and check if buffer has it
            expected_total_frame_len = Constants.OFFSET_DATA_START + data_len + Constants.CHECKSUM_FIELD_LENGTH

            if self.buffer.get_count() < expected_total_frame_len:
                # Not enough data for the complete frame yet
                if self.error_logger:
                    self.error_logger.log_debug(
                        f"FrameParser: Incomplete frame. Have: {self.buffer.get_count()}, Need: {expected_total_frame_len}")
                break

                # 4. Full frame is potentially available, peek it
            current_frame_ba = self.buffer.peek(expected_total_frame_len)
            frame_part_for_calc = current_frame_ba.left(expected_total_frame_len - Constants.CHECKSUM_FIELD_LENGTH)
            received_checksum_ba = current_frame_ba.mid(expected_total_frame_len - Constants.CHECKSUM_FIELD_LENGTH,
                                                        Constants.CHECKSUM_FIELD_LENGTH)

            is_valid = False
            error_msg = ""

            if active_checksum_mode == ChecksumMode.CRC16_CCITT_FALSE:
                if received_checksum_ba.size() == 2:
                    received_crc_val = struct.unpack('>H', received_checksum_ba.data())[
                        0]  # Assuming Big-Endian for CRC in frame
                    calculated_crc_val = calculate_frame_crc16(frame_part_for_calc)
                    if received_crc_val == calculated_crc_val:
                        is_valid = True
                    else:
                        error_msg = f"CRC校验失败! Recv:0x{received_crc_val:04X}, Calc:0x{calculated_crc_val:04X}"
                else:
                    error_msg = f"CRC校验错误: 校验和长度不足 (需要 {Constants.CHECKSUM_FIELD_LENGTH} 字节)"
            else:  # ORIGINAL_SUM_ADD
                if received_checksum_ba.size() == 2:  # Assuming 2 bytes for SC+AC
                    received_sc_val = received_checksum_ba.data()[0]
                    received_ac_val = received_checksum_ba.data()[1]
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
                # FuncID is at OFFSET_FUNC_ID from the start of the frame
                func_id_recv_ba = frame_part_for_calc.mid(Constants.OFFSET_FUNC_ID, 1)
                # Data content starts at OFFSET_DATA_START and has length data_len
                data_content_recv_ba = frame_part_for_calc.mid(Constants.OFFSET_DATA_START, data_len)

                func_id_hex_str = func_id_recv_ba.toHex().data().decode('ascii').upper()

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
                    self.error_logger.log_warning(
                        f"FrameParser: {error_msg} Frame: {current_frame_ba.toHex(' ').data().decode()}")
                self.buffer.discard(1)  # Skip the assumed faulty head byte and retry
        # End of while loop
