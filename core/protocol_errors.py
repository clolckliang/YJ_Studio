#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协议错误定义模块

定义协议处理中使用的异常类和错误枚举，避免循环导入问题。

作者: YJ Studio
日期: 2024
"""

from enum import Enum
from typing import Optional


class ProtocolError(Enum):
    """协议错误类型枚举"""
    CHECKSUM_MISMATCH = "checksum_mismatch"
    FRAME_TOO_LONG = "frame_too_long"
    INVALID_LENGTH = "invalid_length"
    BUFFER_OVERFLOW = "buffer_overflow"
    TIMEOUT = "timeout"
    INVALID_SEQUENCE = "invalid_sequence"
    INVALID_FRAME_HEAD = "invalid_frame_head"
    INCOMPLETE_FRAME = "incomplete_frame"
    PARSE_ERROR = "parse_error"
    CONFIG_ERROR = "config_error"
    SEND_FAILED = "send_failed"


class ProtocolException(Exception):
    """协议处理异常基类"""
    def __init__(self, error_type: ProtocolError, message: str, data: Optional[bytes] = None):
        self.error_type = error_type
        self.data = data
        super().__init__(f"[{error_type.value}] {message}")


class ChecksumMismatchError(ProtocolException):
    """校验和不匹配异常"""
    def __init__(self, message: str, received: int, calculated: int, data: Optional[bytes] = None):
        self.received = received
        self.calculated = calculated
        super().__init__(ProtocolError.CHECKSUM_MISMATCH, message, data)


class FrameParseError(ProtocolException):
    """帧解析异常"""
    def __init__(self, message: str, data: Optional[bytes] = None):
        super().__init__(ProtocolError.PARSE_ERROR, message, data)


class BufferOverflowError(ProtocolException):
    """缓冲区溢出异常"""
    def __init__(self, message: str, buffer_size: int, attempted_size: int):
        self.buffer_size = buffer_size
        self.attempted_size = attempted_size
        super().__init__(ProtocolError.BUFFER_OVERFLOW, message)