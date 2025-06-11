from typing import Dict, List, Any
import pyqtgraph as pg # Keep for PLOT_COLORS if pyqtgraph types are used
from enum import Enum

class ChecksumMode(Enum):
    ORIGINAL_SUM_ADD = 0
    CRC16_CCITT_FALSE = 1

class Constants:
    """应用常量定义"""
    MAX_PLOT_POINTS: int = 200
    MAX_HISTORY_SIZE: int = 10000
    MIN_FRAME_LENGTH: int = 7 # Head(1) SAddr(1) DAddr(1) FID(1) Len(2) SC(1) AC(1) = 8. Original was 7, might assume checksum is outside fixed part.
                               # If MIN_FRAME_LENGTH refers to Head to Len (inclusive) for parsing, then it's 1+1+1+1+2 = 6.
                               # The original code used MIN_FRAME_LENGTH = 7 for `_received_data_buffer.length() >= Constants.MIN_FRAME_LENGTH`
                               # and `expected_total_frame_len = Constants.MIN_FRAME_LENGTH - 2 + data_len`
                               # This implies MIN_FRAME_LENGTH = Fixed_Header_Part + Data_Len_Placeholder + Checksums
                               # Let's assume it's: Head(1) + SAddr(1) + DAddr(1) + FuncID(1) + Len(2) + SumChk(1) + AddChk(1) = 8
                               # The original try_parse_frames uses 6 for initial length check before reading data_len.
                               # HEAD_LEN=1, SADDR_LEN=1, DADDR_LEN=1, FID_LEN=1, LEN_FIELD_LEN=2, SC_LEN=1, AC_LEN=1
                               # MIN_FRAME_PARSE_LEN = HEAD_LEN + SADDR_LEN + DADDR_LEN + FID_LEN + LEN_FIELD_LEN = 6 (to read data_len)
                               # MIN_TOTAL_FRAME_LEN = MIN_FRAME_PARSE_LEN + SC_LEN + AC_LEN = 8 (for a frame with 0 data bytes)
                               # Let's use a more descriptive constant name if needed later. For now, stick to original.
    DEFAULT_BAUD_RATE: int = 115200
    CONFIG_FILE_NAME: str = "serial_debugger_config_v5.json"
    LOG_FILE_PREFIX: str = "serial_debug_"
    DEFAULT_PLOT_UPDATE_INTERVAL_MS: int = 100
    DEFAULT_CHECKSUM_MODE = ChecksumMode.ORIGINAL_SUM_ADD  # Or CRC16 by default
    CHECKSUM_FIELD_LENGTH: int = 2  # Both modes use 2 bytes for the checksum field

    DATA_TYPE_SIZES: Dict[str, int] = {
        "uint8_t": 1, "int8_t": 1,
        "uint16_t": 2, "int16_t": 2,
        "uint32_t": 4, "int32_t": 4,
        "float (4B)": 4, "double (8B)": 8,
        "string (UTF-8)": -1, # Indicates variable length, read till end
        "Hex String": -1,     # Indicates variable length, read till end
        "string": -1,         # Kept for compatibility, prefer string (UTF-8)
        "Hex (raw)": -1       # Kept for compatibility, prefer Hex String
    }
    PLOT_COLORS: List[Any] = ['b', 'g', 'r', 'c', 'm', 'y', (255, 165, 0), (128, 0, 128), 'k', (200, 200, 0),
                              (0, 200, 200)]
    THEME_OPTIONS = [
        "light",
        "dark",
        "pink",
        "forest",
        "ocean",
        "amethyst",
        "sunset",
        "midnight",
        "custom_image_theme"
        # This list should match the themes your ThemeManager can apply.
        # The names here will be used to generate the menu items.
    ]

    # 修正帧解析偏移量（基于实际协议结构）
    OFFSET_HEAD: int = 0
    OFFSET_SADDR: int = 1
    OFFSET_DADDR: int = 2
    OFFSET_FUNC_ID: int = 3
    OFFSET_LEN: int = 4  # 长度字段是2字节，统一处理
    OFFSET_DATA_START: int = 6  # 数据段起始位置
    CHECKSUM_LENGTH: int = 2  # 校验和长度固定为2字节
    MIN_HEADER_LEN_FOR_DATA_LEN: int = 6  # 解析数据长度所需的最小头部长度
