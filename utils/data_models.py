from dataclasses import dataclass, field
from typing import Optional
from utils.constants import Constants

@dataclass
class FrameConfig:
    """帧配置数据类"""
    head: str = "AB"
    s_addr: str = "01"
    d_addr: str = "02"
    func_id: str = "C1"
    # Checksums are calculated, not stored as part of base config for sending

@dataclass
class SerialPortConfig:
    """串口配置数据类"""
    port_name: Optional[str] = None
    baud_rate: int = Constants.DEFAULT_BAUD_RATE
    data_bits: int = 8
    parity: str = "None"
    stop_bits: int = 1
