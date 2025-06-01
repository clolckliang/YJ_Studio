import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QByteArray

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.protocol_handler import ProtocolAnalyzer, FrameParser
from utils.constants import ChecksumMode

@pytest.fixture
def mock_serial_config():
    return MagicMock(
        head=0xAB,
        s_addr=0x01,
        d_addr=0x02,
        func_id=0xC0,
        data_len=2,
        data=bytes([0x11, 0x22]),
        received_checksum_bytes=bytes([0x33, 0x44])
    )

@pytest.fixture
def frame_parser():
    return FrameParser(checksum_mode=ChecksumMode.ORIGINAL)

class TestProtocolAnalyzer:
    def test_initialization(self):
        analyzer = ProtocolAnalyzer()
        assert analyzer.active_checksum_mode == ChecksumMode.ORIGINAL
        
    def test_change_checksum_mode(self):
        analyzer = ProtocolAnalyzer()
        analyzer.set_checksum_mode(ChecksumMode.CRC16_CCITT_FALSE)
        assert analyzer.active_checksum_mode == ChecksumMode.CRC16_CCITT_FALSE

class TestFrameParser:
    def test_parse_valid_frame_original_checksum(self, frame_parser, mock_serial_config):
        # 测试原始校验和模式的帧解析
        frame_parser.checksum_mode = ChecksumMode.ORIGINAL
        frame_data = QByteArray(b'\xAB\x01\x02\xC0\x02\x00\x11\x22\x33\x44')
        
        with patch('core.protocol_handler.calculate_original_checksums', 
                  return_value=(0x33, 0x44)) as mock_checksum:
            result = frame_parser.try_parse_frames(frame_data)
            
            assert len(result) == 1
            assert result[0].func_id == 0xC0
            mock_checksum.assert_called_once()
            
    def test_parse_valid_frame_crc16_checksum(self, frame_parser, mock_serial_config):
        # 测试CRC16校验模式的帧解析
        frame_parser.checksum_mode = ChecksumMode.CRC16_CCITT_FALSE
        frame_data = QByteArray(b'\xAB\x01\x02\xC0\x02\x00\x11\x22\x33\x44')
        
        with patch('core.protocol_handler.calculate_crc16', 
                  return_value=0x4433) as mock_crc:
            result = frame_parser.try_parse_frames(frame_data)
            
            assert len(result) == 1
            assert result[0].func_id == 0xC0
            mock_crc.assert_called_once()
            
    def test_parse_invalid_frame(self, frame_parser):
        # 测试无效帧头的情况
        frame_data = QByteArray(b'\xAA\x01\x02\xC0\x02\x00\x11\x22\x33\x44')
        result = frame_parser.try_parse_frames(frame_data)
        assert len(result) == 0
        
    def test_parse_multiple_frames(self, frame_parser):
        # 测试多帧数据解析
        frame_data = QByteArray(b'\xAB\x01\x02\xC0\x02\x00\x11\x22\x33\x44'
                               b'\xAB\x01\x02\xC1\x01\x00\x55\x66\x77')
        with patch('core.protocol_handler.calculate_original_checksums', 
                  side_effect=[(0x33, 0x44), (0x66, 0x77)]):
            result = frame_parser.try_parse_frames(frame_data)
            
            assert len(result) == 2
            assert result[0].func_id == 0xC0
            assert result[1].func_id == 0xC1
            
    def test_parse_partial_frame(self, frame_parser):
        # 测试不完整帧的情况
        frame_data = QByteArray(b'\xAB\x01\x02\xC0\x02\x00\x11')
        result = frame_parser.try_parse_frames(frame_data)
        assert len(result) == 0
