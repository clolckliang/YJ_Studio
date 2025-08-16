"""
串口逻辑修复验证测试
测试 CircularBuffer、校验和计算、帧解析等关键组件
"""
import pytest
import sys
import os
import struct
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QByteArray

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.placeholders import CircularBuffer
from core.protocol_handler import (
    ProtocolAnalyzer, FrameParser, 
    calculate_frame_crc16, calculate_original_checksums_python
)
from utils.constants import ChecksumMode
from utils.data_models import FrameConfig


class TestCircularBufferFixes:
    """测试 CircularBuffer 修复"""
    
    def test_buffer_initialization(self):
        """测试缓冲区初始化"""
        buffer = CircularBuffer(10)
        assert buffer.max_size == 10
        assert buffer.get_count() == 0
        assert buffer.is_empty()
        assert not buffer.is_full()
    
    def test_write_and_read(self):
        """测试写入和读取操作"""
        buffer = CircularBuffer(10)
        test_data = QByteArray(b'\x01\x02\x03\x04')
        
        # 写入数据
        written = buffer.write(test_data)
        assert written == 4
        assert buffer.get_count() == 4
        
        # 读取数据
        read_data = buffer.read(4)
        assert read_data.data() == b'\x01\x02\x03\x04'
        assert buffer.get_count() == 0
    
    def test_peek_operation(self):
        """测试查看操作（不移除数据）"""
        buffer = CircularBuffer(10)
        test_data = QByteArray(b'\xAB\xCD\xEF')
        
        buffer.write(test_data)
        
        # 查看数据但不移除
        peeked = buffer.peek(3)
        assert peeked.data() == b'\xAB\xCD\xEF'
        assert buffer.get_count() == 3  # 数据仍在缓冲区中
        
        # 再次查看部分数据
        partial = buffer.peek(2)
        assert partial.data() == b'\xAB\xCD'
    
    def test_circular_overflow(self):
        """测试环形缓冲区溢出处理"""
        buffer = CircularBuffer(5)
        
        # 写入超过缓冲区大小的数据
        data1 = QByteArray(b'\x01\x02\x03')
        data2 = QByteArray(b'\x04\x05\x06\x07')
        
        buffer.write(data1)
        buffer.write(data2)
        
        # 应该只保留最新的5个字节
        assert buffer.get_count() == 5
        result = buffer.read(5)
        assert result.data() == b'\x03\x04\x05\x06\x07'


class TestChecksumCalculationFixes:
    """测试校验和计算修复"""
    
    def test_original_checksum_calculation(self):
        """测试原始求和/累加校验算法"""
        test_frame = QByteArray(b'\xAB\x01\x02\xC0\x02\x00\x11\x22')
        
        sc, ac = calculate_original_checksums_python(test_frame)
        
        # 验证计算结果
        expected_sc = (0xAB + 0x01 + 0x02 + 0xC0 + 0x02 + 0x00 + 0x11 + 0x22) & 0xFF
        expected_ac = 0
        temp_sum = 0
        for byte_val in test_frame.data():
            temp_sum = (temp_sum + byte_val) & 0xFF
            expected_ac = (expected_ac + temp_sum) & 0xFF
        
        assert sc == expected_sc
        assert ac == expected_ac
    
    def test_crc16_calculation(self):
        """测试 CRC16 校验计算"""
        test_frame = QByteArray(b'\xAB\x01\x02\xC0\x02\x00\x11\x22')
        
        crc_result = calculate_frame_crc16(test_frame)
        
        # CRC16 应该返回一个16位整数
        assert isinstance(crc_result, int)
        assert 0 <= crc_result <= 0xFFFF
    
    def test_checksum_consistency(self):
        """测试校验和计算的一致性"""
        test_data = [
            b'\xAB\x01\x02\xC0\x00\x00',
            b'\xAB\x01\x02\xC1\x04\x00\x11\x22\x33\x44',
            b'\xAB\x02\x01\xC2\x01\x00\xFF'
        ]
        
        for data in test_data:
            frame = QByteArray(data)
            
            # 多次计算应该得到相同结果
            sc1, ac1 = calculate_original_checksums_python(frame)
            sc2, ac2 = calculate_original_checksums_python(frame)
            
            assert sc1 == sc2
            assert ac1 == ac2
            
            crc1 = calculate_frame_crc16(frame)
            crc2 = calculate_frame_crc16(frame)
            
            assert crc1 == crc2


class TestFrameParserFixes:
    """测试帧解析器修复"""
    
    def setup_method(self):
        """测试前准备"""
        self.frame_parser = FrameParser()
        self.frame_config = FrameConfig()
        self.frame_config.head = "AB"
        self.frame_config.s_addr = "01"
        self.frame_config.d_addr = "02"
        self.frame_config.func_id = "C0"
    
    def test_valid_frame_parsing_original_checksum(self):
        """测试有效帧解析（原始校验模式）"""
        # 构造一个有效的帧
        frame_data = QByteArray()
        frame_data.append(b'\xAB')  # 帧头
        frame_data.append(b'\x01')  # 源地址
        frame_data.append(b'\x02')  # 目标地址
        frame_data.append(b'\xC0')  # 功能码
        frame_data.append(struct.pack('<H', 2))  # 数据长度（小端序）
        frame_data.append(b'\x11\x22')  # 数据
        
        # 计算校验和
        sc, ac = calculate_original_checksums_python(frame_data)
        frame_data.append(bytes([sc, ac]))
        
        # 添加数据到解析器
        self.frame_parser.append_data(frame_data)
        
        # 模拟信号连接
        parsed_frames = []
        def on_frame_parsed(func_id, data):
            parsed_frames.append((func_id, data))
        
        self.frame_parser.frame_successfully_parsed.connect(on_frame_parsed)
        
        # 尝试解析
        self.frame_parser.try_parse_frames(
            self.frame_config, 
            "C0", 
            ChecksumMode.ORIGINAL_SUM_ADD
        )
        
        # 验证解析结果
        assert len(parsed_frames) == 1
        func_id, data = parsed_frames[0]
        assert func_id == "C0"
        assert data.data() == b'\x11\x22'
    
    def test_invalid_checksum_handling(self):
        """测试无效校验和处理"""
        # 构造一个校验和错误的帧
        frame_data = QByteArray()
        frame_data.append(b'\xAB\x01\x02\xC0')
        frame_data.append(struct.pack('<H', 2))
        frame_data.append(b'\x11\x22')
        frame_data.append(b'\xFF\xFF')  # 错误的校验和
        
        checksum_errors = []
        def on_checksum_error(error_msg, frame):
            checksum_errors.append((error_msg, frame))
        
        self.frame_parser.checksum_error.connect(on_checksum_error)
        self.frame_parser.append_data(frame_data)
        
        self.frame_parser.try_parse_frames(
            self.frame_config,
            "C0",
            ChecksumMode.ORIGINAL_SUM_ADD
        )
        
        # 应该检测到校验和错误
        assert len(checksum_errors) == 1
    
    def test_partial_frame_handling(self):
        """测试不完整帧处理"""
        # 只发送帧的一部分
        partial_frame = QByteArray(b'\xAB\x01\x02')
        
        self.frame_parser.append_data(partial_frame)
        
        parsed_frames = []
        def on_frame_parsed(func_id, data):
            parsed_frames.append((func_id, data))
        
        self.frame_parser.frame_successfully_parsed.connect(on_frame_parsed)
        
        # 尝试解析不完整的帧
        self.frame_parser.try_parse_frames(
            self.frame_config,
            "C0",
            ChecksumMode.ORIGINAL_SUM_ADD
        )
        
        # 不应该解析出任何帧
        assert len(parsed_frames) == 0
        
        # 缓冲区中应该还有数据等待更多字节
        assert self.frame_parser.buffer.get_count() == 3


class TestIntegrationFixes:
    """集成测试"""
    
    def test_complete_frame_processing_workflow(self):
        """测试完整的帧处理工作流"""
        # 创建组件
        buffer = CircularBuffer(1024)
        frame_parser = FrameParser()
        frame_config = FrameConfig()
        frame_config.head = "AB"
        frame_config.func_id = "C0"
        
        # 构造测试帧
        test_frame = QByteArray()
        test_frame.append(b'\xAB\x01\x02\xC0')
        test_frame.append(struct.pack('<H', 4))
        test_frame.append(b'\x11\x22\x33\x44')
        
        # 计算校验和
        sc, ac = calculate_original_checksums_python(test_frame)
        test_frame.append(bytes([sc, ac]))
        
        # 模拟分段接收数据
        chunk1 = test_frame.left(5)
        chunk2 = test_frame.mid(5, 5)
        chunk3 = test_frame.mid(10)
        
        parsed_results = []
        def on_parsed(func_id, data):
            parsed_results.append((func_id, data.data()))
        
        frame_parser.frame_successfully_parsed.connect(on_parsed)
        
        # 分段添加数据
        frame_parser.append_data(chunk1)
        frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
        assert len(parsed_results) == 0  # 数据不完整
        
        frame_parser.append_data(chunk2)
        frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
        assert len(parsed_results) == 0  # 仍然不完整
        
        frame_parser.append_data(chunk3)
        frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
        assert len(parsed_results) == 1  # 现在应该解析成功
        
        func_id, data = parsed_results[0]
        assert func_id == "C0"
        assert data == b'\x11\x22\x33\x44'


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])