"""协议解码器模块

将协议解析逻辑从FrameParser中分离，提供独立的解码功能。
"""

import time
import struct
from typing import Optional, Tuple, List
from PySide6.QtCore import QObject, Signal, QByteArray
from enum import Enum

from utils.constants import ChecksumMode
from utils.data_models import FrameConfig
from utils.logger import ErrorLogger
# 导入协议错误枚举和异常类
from core.protocol_errors import ProtocolError, ProtocolException, ChecksumMismatchError, FrameParseError

# 导入CRC计算函数
try:
    from .protocol_handler import calculate_frame_crc16
except ImportError:
    # 如果导入失败，提供一个简单的CRC计算实现
    def calculate_frame_crc16(data) -> int:
        """简单的CRC16计算实现"""
        crc = 0xFFFF
        # 处理 QByteArray 类型
        if hasattr(data, 'data'):
            data = data.data()
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF


class FrameValidationResult:
    """帧验证结果"""
    def __init__(self, is_valid: bool, error_type: Optional[ProtocolError] = None, 
                 error_message: str = "", frame_data: Optional[QByteArray] = None):
        self.is_valid = is_valid
        self.error_type = error_type
        self.error_message = error_message
        self.frame_data = frame_data


class ParsedFrame:
    """解析后的帧数据"""
    def __init__(self, func_id_hex: str, data_payload: QByteArray, 
                 source_addr: int = 0, dest_addr: int = 0, seq_num: int = 0):
        self.func_id_hex = func_id_hex
        self.data_payload = data_payload
        self.source_addr = source_addr
        self.dest_addr = dest_addr
        self.seq_num = seq_num
        self.parse_time = time.time()


class ProtocolDecoder(QObject):
    """协议解码器
    
    负责协议帧的解析和验证，从FrameParser中分离出来的独立组件。
    """
    
    # 信号定义
    frame_decoded = Signal(ParsedFrame)  # 成功解码的帧
    decode_error = Signal(str, QByteArray)  # 解码错误
    checksum_error = Signal(str, QByteArray)  # 校验和错误
    
    def __init__(self, error_logger: Optional[ErrorLogger] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.error_logger = error_logger
        
        # 性能统计
        self._decode_stats = {
            'total_frames': 0,
            'successful_frames': 0,
            'failed_frames': 0,
            'checksum_errors': 0,
            'avg_decode_time_ms': 0.0
        }
    
    def decode_frame(self, frame_data: QByteArray, frame_config: FrameConfig, 
                    checksum_mode: ChecksumMode, target_func_id_hex: str = "") -> Optional[ParsedFrame]:
        """解码单个帧
        
        Args:
            frame_data: 完整的帧数据
            frame_config: 帧配置
            checksum_mode: 校验模式
            target_func_id_hex: 目标功能ID（可选过滤）
            
        Returns:
            解析成功返回ParsedFrame对象，失败返回None
        """
        decode_start_time = time.time()
        self._decode_stats['total_frames'] += 1
        
        try:
            # 验证帧
            validation_result = self._validate_frame(frame_data, frame_config, checksum_mode)
            if not validation_result.is_valid:
                self._handle_decode_error(validation_result)
                decode_time_ms = (time.time() - decode_start_time) * 1000
                self._decode_stats['avg_decode_time_ms'] = (self._decode_stats['avg_decode_time_ms'] * (self._decode_stats['total_frames'] - 1) + decode_time_ms) / self._decode_stats['total_frames']
                return None
            
            # 解析帧内容
            parsed_frame = self._parse_frame_content(frame_data, frame_config)
            if not parsed_frame:
                decode_time_ms = (time.time() - decode_start_time) * 1000
                self._update_decode_stats(decode_time_ms, False)
                return None
            
            # 检查目标功能ID过滤
            if target_func_id_hex and parsed_frame.func_id_hex != target_func_id_hex:
                decode_time_ms = (time.time() - decode_start_time) * 1000
                self._update_decode_stats(decode_time_ms, False)
                return None
            
            # 更新统计信息
            decode_time_ms = (time.time() - decode_start_time) * 1000
            self._update_decode_stats(decode_time_ms, True)
            
            self.frame_decoded.emit(parsed_frame)
            return parsed_frame
            
        except Exception as e:
            self._update_decode_stats((time.time() - decode_start_time) * 1000, False)
            error_msg = f"Frame decode exception: {str(e)}"
            if self.error_logger:
                self.error_logger.log_error(error_msg, "DECODE")
            self.decode_error.emit(error_msg, frame_data)
            return None
    
    def _validate_frame(self, frame_data: QByteArray, frame_config: FrameConfig, 
                       checksum_mode: ChecksumMode) -> FrameValidationResult:
        """验证帧的完整性和校验和"""
        try:
            # 检查最小长度
            min_frame_length = frame_config.frame_head_length + frame_config.data_length_field_length + \
                             frame_config.address_length + frame_config.func_id_length + \
                             frame_config.checksum_length
            
            if len(frame_data) < min_frame_length:
                return FrameValidationResult(
                    False, ProtocolError.INCOMPLETE_FRAME, 
                    f"Frame too short: {len(frame_data)} < {min_frame_length}", frame_data
                )
            
            # 检查最大长度
            if len(frame_data) > frame_config.max_frame_length:
                return FrameValidationResult(
                    False, ProtocolError.FRAME_TOO_LONG,
                    f"Frame too long: {len(frame_data)} > {frame_config.max_frame_length}", frame_data
                )
            
            # 校验和验证
            if not self._verify_checksum(frame_data, frame_config, checksum_mode):
                return FrameValidationResult(
                    False, ProtocolError.CHECKSUM_MISMATCH,
                    "Checksum verification failed", frame_data
                )
            
            return FrameValidationResult(True)
            
        except Exception as e:
            return FrameValidationResult(
                False, ProtocolError.PARSE_ERROR,
                f"Frame validation error: {str(e)}", frame_data
            )
    
    def _verify_checksum(self, frame_data: QByteArray, frame_config: FrameConfig, 
                        checksum_mode: ChecksumMode) -> bool:
        """验证帧校验和"""
        try:
            if checksum_mode == ChecksumMode.CRC16_CCITT_FALSE:
                # CRC16校验
                frame_without_checksum = frame_data[:-frame_config.checksum_length]
                calculated_crc = calculate_frame_crc16(frame_without_checksum)
                
                # 提取接收到的CRC
                received_crc_bytes = frame_data[-frame_config.checksum_length:]
                received_crc = struct.unpack('>H', received_crc_bytes)[0]
                
                if calculated_crc != received_crc:
                    error_msg = f"CRC16 mismatch: calculated={calculated_crc:04X}, received={received_crc:04X}"
                    self.checksum_error.emit(error_msg, frame_data)
                    return False
                    
            elif checksum_mode == ChecksumMode.ORIGINAL_SUM_ADD:
                # 原始校验和
                frame_without_checksum = frame_data[:-frame_config.checksum_length]
                calc_sum, calc_xor = calculate_original_checksums_python(frame_without_checksum)
                
                # 提取接收到的校验和
                received_checksums = frame_data[-frame_config.checksum_length:]
                received_sum = received_checksums[0]
                received_xor = received_checksums[1]
                
                if calc_sum != received_sum or calc_xor != received_xor:
                    error_msg = f"Original checksum mismatch: calc_sum={calc_sum:02X}, recv_sum={received_sum:02X}, calc_xor={calc_xor:02X}, recv_xor={received_xor:02X}"
                    self.checksum_error.emit(error_msg, frame_data)
                    return False
            
            return True
            
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"Checksum verification error: {str(e)}", "CHECKSUM")
            return False
    
    def _parse_frame_content(self, frame_data: QByteArray, frame_config: FrameConfig) -> Optional[ParsedFrame]:
        """解析帧内容"""
        try:
            offset = frame_config.frame_head_length
            
            # 解析数据长度
            data_length_bytes = frame_data[offset:offset + frame_config.data_length_field_length]
            if frame_config.data_length_field_length == 1:
                data_length = data_length_bytes[0]
            elif frame_config.data_length_field_length == 2:
                data_length = struct.unpack('>H', data_length_bytes)[0]
            else:
                raise FrameParseError(f"Unsupported data length field size: {frame_config.data_length_field_length}")
            
            offset += frame_config.data_length_field_length
            
            # 解析地址
            if frame_config.address_length > 0:
                addr_bytes = frame_data[offset:offset + frame_config.address_length]
                if frame_config.address_length == 1:
                    dest_addr = addr_bytes[0]
                elif frame_config.address_length == 2:
                    dest_addr = struct.unpack('>H', addr_bytes)[0]
                else:
                    dest_addr = 0
                offset += frame_config.address_length
            else:
                dest_addr = 0
            
            # 解析功能ID
            func_id_bytes = frame_data[offset:offset + frame_config.func_id_length]
            func_id_hex = func_id_bytes.toHex().data().decode().upper()
            offset += frame_config.func_id_length
            
            # 提取数据载荷
            data_payload = frame_data[offset:offset + data_length]
            
            return ParsedFrame(
                func_id_hex=func_id_hex,
                data_payload=data_payload,
                dest_addr=dest_addr
            )
            
        except Exception as e:
            error_msg = f"Frame content parsing error: {str(e)}"
            if self.error_logger:
                self.error_logger.log_error(error_msg, "PARSE")
            self.decode_error.emit(error_msg, frame_data)
            return None
    
    def _handle_decode_error(self, validation_result: FrameValidationResult):
        """处理解码错误"""
        self._decode_stats['failed_frames'] += 1
        
        if validation_result.error_type == ProtocolError.CHECKSUM_MISMATCH:
            self._decode_stats['checksum_errors'] += 1
        
        if self.error_logger:
            self.error_logger.log_warning(f"Decode error: {validation_result.error_message}")
        
        self.decode_error.emit(validation_result.error_message, validation_result.frame_data or QByteArray())
    
    def _update_decode_stats(self, decode_time_ms: float, success: bool):
        """更新解码统计信息"""
        if success:
            self._decode_stats['successful_frames'] += 1
        else:
            self._decode_stats['failed_frames'] += 1
        
        # 更新平均解码时间
        total_frames = self._decode_stats['total_frames']
        current_avg = self._decode_stats['avg_decode_time_ms']
        self._decode_stats['avg_decode_time_ms'] = (current_avg * (total_frames - 1) + decode_time_ms) / total_frames
    
    def get_decode_statistics(self) -> dict:
        """获取解码统计信息"""
        stats = self._decode_stats.copy()
        if stats['total_frames'] > 0:
            stats['success_rate'] = stats['successful_frames'] / stats['total_frames']
            stats['error_rate'] = stats['failed_frames'] / stats['total_frames']
            stats['checksum_error_rate'] = stats['checksum_errors'] / stats['total_frames']
        else:
            stats['success_rate'] = 0.0
            stats['error_rate'] = 0.0
            stats['checksum_error_rate'] = 0.0
        
        return stats
    
    def reset_statistics(self):
        """重置统计信息"""
        self._decode_stats = {
            'total_frames': 0,
            'successful_frames': 0,
            'failed_frames': 0,
            'checksum_errors': 0,
            'avg_decode_time_ms': 0.0
        }