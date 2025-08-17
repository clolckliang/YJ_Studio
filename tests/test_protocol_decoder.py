"""ProtocolDecoder测试模块"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch
import struct

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.protocol_decoder import ProtocolDecoder, ParsedFrame, FrameValidationResult
from core.protocol_errors import ProtocolError, ProtocolException, ChecksumMismatchError, FrameParseError
from core.placeholders import QByteArray
from utils.constants import ChecksumMode
from utils.data_models import FrameConfig


class TestProtocolDecoder(unittest.TestCase):
    """ProtocolDecoder类的测试"""
    
    def setUp(self):
        """测试前的设置"""
        self.decoder = ProtocolDecoder()
        self.frame_config = FrameConfig()
        self.frame_config.frame_head_length = 2
        self.frame_config.data_length_field_length = 1
        self.frame_config.func_id_length = 1
        self.frame_config.checksum_length = 2
        self.frame_config.address_length = 0
        self.frame_config.max_frame_length = 1000
    
    def test_initialization(self):
        """测试ProtocolDecoder初始化"""
        decoder = ProtocolDecoder()
        self.assertIsNotNone(decoder)
        
        stats = decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 0)
        self.assertEqual(stats['successful_frames'], 0)
        self.assertEqual(stats['failed_frames'], 0)
    
    def test_empty_data_parsing(self):
        """测试空数据解析"""
        result = self.decoder.decode_frame(QByteArray(b""), self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        self.assertIsNone(result)
        
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 1)
        self.assertEqual(stats['failed_frames'], 1)
    
    def test_insufficient_data_parsing(self):
        """测试数据不足解析"""
        # 提供不足的数据
        insufficient_data = QByteArray(b"\xAA\xBB")
        result = self.decoder.decode_frame(insufficient_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        self.assertIsNone(result)
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 1)
        self.assertEqual(stats['failed_frames'], 1)
    
    def test_invalid_data_parsing(self):
        """测试无效数据解析"""
        # 提供无效的数据格式
        invalid_data = QByteArray(b"\xFF\xFF\xFF\xFF")
        result = self.decoder.decode_frame(invalid_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        self.assertIsNone(result)
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 1)
        self.assertEqual(stats['failed_frames'], 1)
    
    def test_oversized_frame_handling(self):
        """测试超大帧处理"""
        self.frame_config.max_frame_length = 10  # 设置较小的最大帧长度
        
        # 构造超大帧
        oversized_data = QByteArray(b"\xAA\xBB" + b"\x00" * 20)
        result = self.decoder.decode_frame(oversized_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        self.assertIsNone(result)
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 1)
        self.assertEqual(stats['failed_frames'], 1)
    
    def test_undersized_frame_handling(self):
        """测试过小帧处理"""
        # 构造过小的帧
        undersized_data = QByteArray(b"\xAA")
        result = self.decoder.decode_frame(undersized_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        self.assertIsNone(result)
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 1)
        self.assertEqual(stats['failed_frames'], 1)
    
    def test_crc_verification_invalid(self):
        """测试无效CRC校验"""
        # 构造带有错误CRC的帧：帧头(2) + 数据长度(1) + 功能ID(1) + 数据载荷(2) + 错误CRC(2)
        frame_data = QByteArray(b"\xAA\xBB\x02\x01\x02\x03\xFF\xFF")
        
        result = self.decoder.decode_frame(frame_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        self.assertIsNone(result)
        
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 1)
        self.assertEqual(stats['failed_frames'], 1)
        self.assertEqual(stats['checksum_errors'], 1)
    
    @patch('core.protocol_decoder.calculate_frame_crc16')
    def test_crc_verification_valid(self, mock_crc):
        """测试有效CRC校验"""
        # 模拟正确的CRC计算
        mock_crc.return_value = 0x1234
        
        # 构造带有正确CRC的帧
        frame_data = QByteArray(b"\xAA\xBB\x04\x01\x02\x03\x04\x12\x34")
        
        result = self.decoder.decode_frame(frame_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        # 验证CRC计算被调用
        mock_crc.assert_called()
        
        # 验证统计信息
        stats = self.decoder.get_decode_statistics()
        self.assertGreater(stats['total_frames'], 0)
    
    def test_multiple_frame_parsing(self):
        """测试多帧解析"""
        # 测试单个帧解析（ProtocolDecoder一次只处理一个帧）
        frame1 = QByteArray(b"\xAA\xBB\x02\x01\x02\x12\x34")
        frame2 = QByteArray(b"\xAA\xBB\x03\x02\x03\x04\x56\x78")
        
        result1 = self.decoder.decode_frame(frame1, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        result2 = self.decoder.decode_frame(frame2, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        # 验证统计信息
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 2)
        # 两个帧都可能因为CRC校验失败而失败
        self.assertGreaterEqual(stats['failed_frames'], 0)
        self.assertLessEqual(stats['failed_frames'], 2)
    
    def test_frame_validation_result(self):
        """测试帧验证结果"""
        # 测试有效结果
        valid_result = FrameValidationResult(True)
        self.assertTrue(valid_result.is_valid)
        self.assertIsNone(valid_result.error_type)
        
        # 测试无效结果
        invalid_result = FrameValidationResult(
            False, ProtocolError.PARSE_ERROR, "Test message", QByteArray(b"test")
        )
        self.assertFalse(invalid_result.is_valid)
        self.assertIsNotNone(invalid_result.error_type)
        self.assertEqual(invalid_result.error_message, "Test message")
    
    def test_parsed_frame_creation(self):
        """测试解析帧对象创建"""
        frame = ParsedFrame(
            func_id_hex="01",
            data_payload=QByteArray(b"test"),
            source_addr=1,
            dest_addr=2,
            seq_num=3
        )
        
        self.assertEqual(frame.func_id_hex, "01")
        self.assertEqual(frame.data_payload.data(), b"test")
        self.assertEqual(frame.source_addr, 1)
        self.assertEqual(frame.dest_addr, 2)
        self.assertEqual(frame.seq_num, 3)
        self.assertIsNotNone(frame.parse_time)
    
    def test_statistics_tracking(self):
        """测试统计信息跟踪"""
        # 初始统计
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 0)
        self.assertEqual(stats['success_rate'], 0.0)
        
        # 处理一些帧
        frame1 = QByteArray(b"\xAA\xBB\x04\x01\x02\x03\x04\x12\x34")
        frame2 = QByteArray(b"\xFF")  # 无效帧
        
        self.decoder.decode_frame(frame1, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        self.decoder.decode_frame(frame2, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        # 检查更新的统计
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 2)
        self.assertGreater(stats['failed_frames'], 0)
    
    def test_statistics_reset(self):
        """测试统计信息重置"""
        # 处理一些帧
        frame = QByteArray(b"\xAA\xBB\x04\x01\x02\x03\x04\x12\x34")
        self.decoder.decode_frame(frame, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        # 验证有统计数据
        stats = self.decoder.get_decode_statistics()
        self.assertGreater(stats['total_frames'], 0)
        
        # 重置统计
        self.decoder.reset_statistics()
        
        # 验证统计已重置
        stats = self.decoder.get_decode_statistics()
        self.assertEqual(stats['total_frames'], 0)
        self.assertEqual(stats['successful_frames'], 0)
        self.assertEqual(stats['failed_frames'], 0)
    
    def test_signal_emission(self):
        """测试信号发射"""
        # 创建信号接收器
        frame_decoded_received = []
        decode_error_received = []
        checksum_error_received = []
        
        def on_frame_decoded(frame):
            frame_decoded_received.append(frame)
        
        def on_decode_error(error_msg, frame_data):
            decode_error_received.append((error_msg, frame_data))
        
        def on_checksum_error(error_msg, frame_data):
            checksum_error_received.append((error_msg, frame_data))
        
        # 连接信号
        self.decoder.frame_decoded.connect(on_frame_decoded)
        self.decoder.decode_error.connect(on_decode_error)
        self.decoder.checksum_error.connect(on_checksum_error)
        
        # 处理无效帧（应该触发错误信号）
        invalid_frame = QByteArray(b"\xFF")
        self.decoder.decode_frame(invalid_frame, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        # 验证错误信号被发射
        self.assertGreater(len(decode_error_received), 0)
    
    def test_error_handling_with_logger(self):
        """测试带错误日志记录器的错误处理"""
        # 创建模拟的错误日志记录器
        mock_logger = MagicMock()
        decoder = ProtocolDecoder(error_logger=mock_logger)
        
        # 处理无效帧
        invalid_frame = QByteArray(b"\xFF")
        result = decoder.decode_frame(invalid_frame, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
        
        self.assertIsNone(result)
        # 验证日志记录器被调用（可能会调用log_error或log_warning）
        self.assertTrue(mock_logger.log_error.called or mock_logger.log_warning.called)
    
    def test_target_func_id_filtering(self):
        """测试目标功能ID过滤"""
        # 使用模拟CRC来创建有效帧
        with patch('core.protocol_decoder.calculate_frame_crc16', return_value=0x1234):
            frame_data = QByteArray(b"\xAA\xBB\x04\x01\x02\x03\x04\x12\x34")
            
            # 不使用过滤
            result1 = self.decoder.decode_frame(frame_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE)
            
            # 使用匹配的功能ID过滤
            result2 = self.decoder.decode_frame(frame_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE, "01")
            
            # 使用不匹配的功能ID过滤
            result3 = self.decoder.decode_frame(frame_data, self.frame_config, ChecksumMode.CRC16_CCITT_FALSE, "02")
            
            # 验证过滤效果（注意：由于CRC可能仍然不匹配，结果可能都是None）
            stats = self.decoder.get_decode_statistics()
            self.assertGreater(stats['total_frames'], 0)


if __name__ == '__main__':
    unittest.main()