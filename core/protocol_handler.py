import time
import struct
from typing import Optional, Dict, Any, Tuple
from PySide6.QtCore import QObject, Signal, QByteArray
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
    frame_successfully_parsed = Signal(str, QByteArray) # func_id_hex, data_payload
    frame_parse_error = Signal(str, QByteArray)       # error_message, remaining_buffer_or_faulty_frame
    checksum_error = Signal(str, QByteArray)          # message, faulty_frame

    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._received_data_buffer = QByteArray()
        self.error_logger = error_logger
        self._parsed_frame_count = 0 # Internal counter, main app can have its own

    def append_data(self, new_data: QByteArray):
        self._received_data_buffer.append(new_data)

    def get_buffer(self) -> QByteArray:
        return self._received_data_buffer

    def clear_buffer(self):
        self._received_data_buffer.clear()


    def try_parse_frames(self, current_frame_config: FrameConfig,
                         parse_target_func_id_hex: str,
                         active_checksum_mode: ChecksumMode):  # Added active_checksum_mode
        # Convert configured head to QByteArray for indexOf
        try:
            head_byte = int(current_frame_config.head, 16)
            head_ba_config = QByteArray(1, bytes([head_byte]))
        except ValueError:
            if self.error_logger:
                self.error_logger.log_error(f"帧头配置无效 '{current_frame_config.head}'，无法解析。")
            self.frame_parse_error.emit(f"帧头配置无效 '{current_frame_config.head}'", self._received_data_buffer)
            return

        while True:  # Loop to parse all possible frames in buffer
            if self._received_data_buffer.length() < Constants.MIN_HEADER_LEN_FOR_DATA_LEN:  # Min length to read data_len field
                break  # Not enough data for even the smallest header

            head_index = self._received_data_buffer.indexOf(head_ba_config, 0)

            if head_index == -1:  # No frame head found
                # Buffer management: if too large and no head, discard some old data
                if len(self._received_data_buffer) > 4096:  # Configurable threshold
                    self._received_data_buffer = self._received_data_buffer.mid(len(self._received_data_buffer) - 2048)  # Keep last 2KB
                    if self.error_logger:
                        self.error_logger.log_warning("接收缓冲区过大且未找到帧头，已部分丢弃。")
                break  # Exit parsing loop

            if head_index > 0:  # Discard data before the found frame head
                self._received_data_buffer = self._received_data_buffer.mid(head_index)

            # Check again if enough data for header after discarding
            if self._received_data_buffer.length() < Constants.MIN_HEADER_LEN_FOR_DATA_LEN:
                break

            # Extract data length from frame: Big Endian or Little Endian? Assuming Little Endian from original.
            try:
                len_bytes = self._received_data_buffer.mid(Constants.OFFSET_LEN_LOW, 2)
                if len(len_bytes) < 2:
                    break  # Should not happen if MIN_HEADER_LEN_FOR_DATA_LEN is correct
                data_len = struct.unpack('<H', len_bytes.data())[0]
            except struct.error:
                if self.error_logger:
                    self.error_logger.log_error("解析数据长度字段时出错。")
                self._received_data_buffer = self._received_data_buffer.mid(1)  # Skip one byte and retry
                continue

            # Full_Header_Len_Before_Data + Data_Len + Checksum_Len
            expected_total_frame_len = Constants.OFFSET_DATA_START + data_len + Constants.CHECKSUM_FIELD_LENGTH

            if self._received_data_buffer.length() < expected_total_frame_len:
                break  # Not enough data for the complete frame

            current_frame_ba = self._received_data_buffer.left(expected_total_frame_len)
            frame_part_for_calc = current_frame_ba.left(expected_total_frame_len - Constants.CHECKSUM_FIELD_LENGTH)
            received_checksum_ba = current_frame_ba.mid(expected_total_frame_len - Constants.CHECKSUM_FIELD_LENGTH, Constants.CHECKSUM_FIELD_LENGTH)

            is_valid = False
            error_msg = ""

            if active_checksum_mode == ChecksumMode.CRC16_CCITT_FALSE:
                if len(received_checksum_ba) == 2:
                    received_crc_val = struct.unpack('>H', received_checksum_ba.data())[0]  # Big-Endian
                    calculated_crc_val = calculate_frame_crc16(frame_part_for_calc)
                    if received_crc_val == calculated_crc_val:
                        is_valid = True
                    else:
                        error_msg = f"CRC校验失败! Recv:0x{received_crc_val:04X}, Calc:0x{calculated_crc_val:04X}"
                else:
                    error_msg = "CRC长度不足"  # Should not happen with length check
            else:  # ORIGINAL_SUM_ADD
                if len(received_checksum_ba) == 2:
                    received_sc_val = int.from_bytes(received_checksum_ba.mid(0, 1).data(), 'big')
                    received_ac_val = int.from_bytes(received_checksum_ba.mid(1, 1).data(), 'big')

                    calculated_sc, calculated_ac = calculate_original_checksums_python(frame_part_for_calc)
                    if received_sc_val == calculated_sc and received_ac_val == calculated_ac:
                        is_valid = True
                    else:
                        error_msg = (f"原始校验失败! RecvSC:0x{received_sc_val:02X},CalcSC:0x{calculated_sc:02X}; "
                                     f"RecvAC:0x{received_ac_val:02X},CalcAC:0x{calculated_ac:02X}")
                else:
                    error_msg = "原始校验和长度不足"

            if is_valid:
                self._parsed_frame_count += 1
                func_id_recv_ba = frame_part_for_calc.mid(Constants.OFFSET_FUNC_ID, 1)
                data_content_recv_ba = frame_part_for_calc.mid(Constants.OFFSET_DATA_START)

                try:
                    target_fid_ba = QByteArray.fromHex(parse_target_func_id_hex.encode('ascii'))
                except ValueError:
                    target_fid_ba = QByteArray()  # Invalid target FID config

                if func_id_recv_ba == target_fid_ba or not parse_target_func_id_hex or not target_fid_ba:
                    self.frame_successfully_parsed.emit(func_id_recv_ba.toHex().data().decode('ascii'), data_content_recv_ba)

                self._received_data_buffer = self._received_data_buffer.mid(expected_total_frame_len)
            else:
                self.checksum_error_signal.emit(error_msg, current_frame_ba)  # Emit generic signal
                if self.error_logger:
                    self.error_logger.log_warning(f"{error_msg} Frame: {current_frame_ba.toHex(' ').data().decode()}")
                self._received_data_buffer = self._received_data_buffer.mid(1)  # Skip and retry