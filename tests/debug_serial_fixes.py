"""
串口修复调试工具
用于测试和验证串口逻辑修复
"""
import sys
import struct
from PySide6.QtCore import QByteArray, QCoreApplication
from PySide6.QtWidgets import QApplication

# 添加项目路径
sys.path.insert(0, '.')

from core.placeholders import CircularBuffer
from core.protocol_handler import (
    calculate_frame_crc16, 
    calculate_original_checksums_python,
    FrameParser
)
from utils.constants import ChecksumMode
from utils.data_models import FrameConfig
from utils.logger import ErrorLogger


def test_circular_buffer():
    """测试环形缓冲区"""
    print("=== 测试环形缓冲区 ===")
    
    buffer = CircularBuffer(10)
    print(f"初始状态: 大小={buffer.max_size}, 使用={buffer.get_count()}")
    
    # 测试写入
    test_data = QByteArray(b'\x01\x02\x03\x04\x05')
    written = buffer.write(test_data)
    print(f"写入 {test_data.size()} 字节，实际写入 {written} 字节")
    print(f"缓冲区状态: 使用={buffer.get_count()}")
    
    # 测试查看
    peeked = buffer.peek(3)
    print(f"查看前3字节: {peeked.toHex(' ').data().decode().upper()}")
    print(f"查看后缓冲区状态: 使用={buffer.get_count()}")
    
    # 测试读取
    read_data = buffer.read(2)
    print(f"读取2字节: {read_data.toHex(' ').data().decode().upper()}")
    print(f"读取后缓冲区状态: 使用={buffer.get_count()}")
    
    print()


def test_checksum_calculations():
    """测试校验和计算"""
    print("=== 测试校验和计算 ===")
    
    # 测试数据
    test_frame = QByteArray(b'\xAB\x01\x02\xC0\x02\x00\x11\x22')
    print(f"测试帧: {test_frame.toHex(' ').data().decode().upper()}")
    
    # 原始校验和
    sc, ac = calculate_original_checksums_python(test_frame)
    print(f"原始校验和: SC=0x{sc:02X}, AC=0x{ac:02X}")
    
    # 手动验证
    manual_sc = 0
    manual_ac = 0
    for byte_val in test_frame.data():
        manual_sc = (manual_sc + byte_val) & 0xFF
        manual_ac = (manual_ac + manual_sc) & 0xFF
    print(f"手动计算: SC=0x{manual_sc:02X}, AC=0x{manual_ac:02X}")
    print(f"原始校验和计算 {'正确' if (sc == manual_sc and ac == manual_ac) else '错误'}")
    
    # CRC16校验
    crc_val = calculate_frame_crc16(test_frame)
    print(f"CRC16校验和: 0x{crc_val:04X}")
    
    print()


def test_frame_parsing():
    """测试帧解析"""
    print("=== 测试帧解析 ===")
    
    logger = ErrorLogger()
    frame_parser = FrameParser(error_logger=logger)
    
    # 配置帧格式
    frame_config = FrameConfig()
    frame_config.head = "AB"
    frame_config.s_addr = "01"
    frame_config.d_addr = "02"
    frame_config.func_id = "C0"
    
    # 构造测试帧
    frame = QByteArray()
    frame.append(b'\xAB')  # 帧头
    frame.append(b'\x01')  # 源地址
    frame.append(b'\x02')  # 目标地址
    frame.append(b'\xC0')  # 功能码
    frame.append(struct.pack('<H', 4))  # 数据长度（小端序）
    frame.append(b'\x11\x22\x33\x44')  # 数据
    
    # 计算并添加校验和
    sc, ac = calculate_original_checksums_python(frame)
    frame.append(bytes([sc, ac]))
    
    print(f"完整测试帧: {frame.toHex(' ').data().decode().upper()}")
    print(f"帧长度: {frame.size()} 字节")
    
    # 设置解析结果收集
    parsed_frames = []
    checksum_errors = []
    parse_errors = []
    
    def on_frame_parsed(func_id, data):
        parsed_frames.append((func_id, data))
        print(f"解析成功: 功能码={func_id}, 数据={data.toHex(' ').data().decode().upper()}")
    
    def on_checksum_error(error_msg, frame_data):
        checksum_errors.append((error_msg, frame_data))
        print(f"校验和错误: {error_msg}")
    
    def on_parse_error(error_msg, buffer_data):
        parse_errors.append((error_msg, buffer_data))
        print(f"解析错误: {error_msg}")
    
    # 连接信号
    frame_parser.frame_successfully_parsed.connect(on_frame_parsed)
    frame_parser.checksum_error.connect(on_checksum_error)
    frame_parser.frame_parse_error.connect(on_parse_error)
    
    # 测试完整帧解析
    print("\n--- 测试完整帧解析 ---")
    frame_parser.append_data(frame)
    frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
    
    print(f"解析结果: {len(parsed_frames)} 个成功帧, {len(checksum_errors)} 个校验错误, {len(parse_errors)} 个解析错误")
    
    # 测试分段接收
    print("\n--- 测试分段接收 ---")
    frame_parser.clear_buffer()
    parsed_frames.clear()
    
    # 分3段发送
    chunk1 = frame.left(6)
    chunk2 = frame.mid(6, 4)
    chunk3 = frame.mid(10)
    
    print(f"分段1: {chunk1.toHex(' ').data().decode().upper()}")
    frame_parser.append_data(chunk1)
    frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
    print(f"分段1解析结果: {len(parsed_frames)} 个帧")
    
    print(f"分段2: {chunk2.toHex(' ').data().decode().upper()}")
    frame_parser.append_data(chunk2)
    frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
    print(f"分段2解析结果: {len(parsed_frames)} 个帧")
    
    print(f"分段3: {chunk3.toHex(' ').data().decode().upper()}")
    frame_parser.append_data(chunk3)
    frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
    print(f"分段3解析结果: {len(parsed_frames)} 个帧")
    
    # 测试错误校验和
    print("\n--- 测试错误校验和 ---")
    frame_parser.clear_buffer()
    parsed_frames.clear()
    checksum_errors.clear()
    
    bad_frame = QByteArray(frame)
    bad_frame.data()[-1] = 0xFF  # 修改最后一个校验字节
    print(f"错误校验和帧: {bad_frame.toHex(' ').data().decode().upper()}")
    
    frame_parser.append_data(bad_frame)
    frame_parser.try_parse_frames(frame_config, "C0", ChecksumMode.ORIGINAL_SUM_ADD)
    print(f"错误校验和测试结果: {len(parsed_frames)} 个成功帧, {len(checksum_errors)} 个校验错误")
    
    print()


def test_crc16_mode():
    """测试CRC16模式"""
    print("=== 测试CRC16模式 ===")
    
    logger = ErrorLogger()
    frame_parser = FrameParser(error_logger=logger)
    
    frame_config = FrameConfig()
    frame_config.head = "AB"
    frame_config.func_id = "C1"
    
    # 构造CRC16模式的帧
    frame = QByteArray()
    frame.append(b'\xAB\x01\x02\xC1')
    frame.append(struct.pack('<H', 2))
    frame.append(b'\x55\xAA')
    
    # 计算CRC16
    crc_val = calculate_frame_crc16(frame)
    frame.append(struct.pack('<H', crc_val))  # 小端序CRC
    
    print(f"CRC16测试帧: {frame.toHex(' ').data().decode().upper()}")
    print(f"CRC16值: 0x{crc_val:04X}")
    
    parsed_frames = []
    def on_frame_parsed(func_id, data):
        parsed_frames.append((func_id, data))
        print(f"CRC16解析成功: 功能码={func_id}, 数据={data.toHex(' ').data().decode().upper()}")
    
    frame_parser.frame_successfully_parsed.connect(on_frame_parsed)
    frame_parser.append_data(frame)
    frame_parser.try_parse_frames(frame_config, "C1", ChecksumMode.CRC16_CCITT_FALSE)
    
    print(f"CRC16模式解析结果: {len(parsed_frames)} 个成功帧")
    print()


def main():
    """主函数"""
    print("串口逻辑修复验证工具")
    print("=" * 50)
    
    # 创建Qt应用（某些组件需要）
    app = QCoreApplication(sys.argv)
    
    try:
        test_circular_buffer()
        test_checksum_calculations()
        test_frame_parsing()
        test_crc16_mode()
        
        print("所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())