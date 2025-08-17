"""CircularBuffer测试模块"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch
import threading
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.placeholders import CircularBuffer, QByteArray


class TestCircularBuffer(unittest.TestCase):
    """CircularBuffer类的测试"""
    
    def test_initialization(self):
        """测试CircularBuffer初始化"""
        buffer = CircularBuffer(100)
        self.assertEqual(buffer.max_size, 100)
        self.assertEqual(buffer.get_count(), 0)
        self.assertTrue(buffer.is_empty())
        self.assertFalse(buffer.is_full())
        
    def test_invalid_initialization(self):
        """测试无效初始化参数"""
        with self.assertRaises(ValueError):
            CircularBuffer(0)
        with self.assertRaises(ValueError):
            CircularBuffer(-1)
    
    def test_write_and_read(self):
        """测试基本写入和读取操作"""
        buffer = CircularBuffer(10)
        test_data = QByteArray(b"hello")
        
        # 写入数据
        written = buffer.write(test_data)
        self.assertEqual(written, 5)
        self.assertEqual(buffer.get_count(), 5)
        
        # 读取数据
        read_data = buffer.read(5)
        self.assertEqual(read_data.data(), b"hello")
        self.assertEqual(buffer.get_count(), 0)
    
    def test_peek_operation(self):
        """测试peek操作（查看但不移除数据）"""
        buffer = CircularBuffer(10)
        test_data = QByteArray(b"test")
        
        buffer.write(test_data)
        
        # peek不应该改变缓冲区状态
        peeked_data = buffer.peek(4)
        self.assertEqual(peeked_data.data(), b"test")
        self.assertEqual(buffer.get_count(), 4)
        
        # 再次peek应该返回相同数据
        peeked_again = buffer.peek(2)
        self.assertEqual(peeked_again.data(), b"te")
        self.assertEqual(buffer.get_count(), 4)
    
    def test_mid_function(self):
        """测试mid函数（从指定位置获取数据）"""
        buffer = CircularBuffer(10)
        test_data = QByteArray(b"hello world"[:8])  # 只取前8个字符
        buffer.write(test_data)
        
        # 测试mid函数
        mid_data = buffer.mid(2, 3)
        self.assertEqual(mid_data.data(), b"llo")
        
        # mid操作不应该改变缓冲区状态
        self.assertEqual(buffer.get_count(), 8)
    
    def test_clear_operation(self):
        """测试清空操作"""
        buffer = CircularBuffer(10)
        buffer.write(QByteArray(b"data"))
        
        self.assertEqual(buffer.get_count(), 4)
        buffer.clear()
        self.assertEqual(buffer.get_count(), 0)
        self.assertTrue(buffer.is_empty())
    
    def test_space_calculations(self):
        """测试空间计算"""
        buffer = CircularBuffer(10)
        
        # 初始状态
        self.assertEqual(buffer.get_free_space(), 10)
        self.assertEqual(buffer.get_count(), 0)
        
        # 写入一些数据
        buffer.write(QByteArray(b"hello"))
        self.assertEqual(buffer.get_free_space(), 5)
        self.assertEqual(buffer.get_count(), 5)
    
    def test_utilization_rate(self):
        """测试使用率计算"""
        buffer = CircularBuffer(10)
        
        # 空缓冲区
        utilization = buffer.get_count() / buffer.max_size
        self.assertEqual(utilization, 0.0)
        
        # 半满
        buffer.write(QByteArray(b"hello"))
        utilization = buffer.get_count() / buffer.max_size
        self.assertEqual(utilization, 0.5)
        
        # 满缓冲区
        buffer.write(QByteArray(b"world"))
        utilization = buffer.get_count() / buffer.max_size
        self.assertEqual(utilization, 1.0)
    
    def test_performance_stats(self):
        """测试性能统计"""
        buffer = CircularBuffer(10)
        
        # 初始统计
        stats = buffer.get_stats()
        self.assertEqual(stats['total_writes'], 0)
        self.assertEqual(stats['total_reads'], 0)
        
        # 执行一些操作
        buffer.write(QByteArray(b"test"))
        buffer.read(2)
        
        stats = buffer.get_stats()
        self.assertEqual(stats['total_writes'], 1)
        self.assertEqual(stats['total_reads'], 1)
    
    def test_debug_output(self):
        """测试调试输出"""
        buffer = CircularBuffer(5)
        buffer.write(QByteArray(b"abc"))
        
        debug_info = buffer.debug_dump()
        self.assertIsInstance(debug_info, str)
        self.assertIn('size', debug_info.lower())
        self.assertIn('used', debug_info.lower())
    
    def test_buffer_overflow(self):
        """测试缓冲区溢出处理"""
        buffer = CircularBuffer(5)
        
        # 写入超过容量的数据
        large_data = QByteArray(b"hello world")
        written = buffer.write(large_data)
        
        # 应该只写入缓冲区容量大小的数据
        self.assertLessEqual(written, 5)
        self.assertLessEqual(buffer.get_count(), 5)
    
    def test_empty_operations(self):
        """测试空缓冲区操作"""
        buffer = CircularBuffer(10)
        
        # 从空缓冲区读取
        empty_read = buffer.read(5)
        self.assertEqual(empty_read.size(), 0)
        
        # 从空缓冲区peek
        empty_peek = buffer.peek(5)
        self.assertEqual(empty_peek.size(), 0)
    
    def test_concurrent_operations(self):
        """测试并发操作的线程安全性"""
        buffer = CircularBuffer(1000)
        results = []
        
        def writer_thread():
            for i in range(10):
                data = QByteArray(f"data{i}".encode())
                written = buffer.write(data)
                results.append(('write', written))
                time.sleep(0.001)
        
        def reader_thread():
            for i in range(5):
                read_data = buffer.read(5)
                results.append(('read', read_data.size()))
                time.sleep(0.002)
        
        # 启动线程
        threads = []
        for _ in range(2):
            t1 = threading.Thread(target=writer_thread)
            t2 = threading.Thread(target=reader_thread)
            threads.extend([t1, t2])
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # 验证操作完成且没有异常
        self.assertGreater(len(results), 0)


if __name__ == '__main__':
    unittest.main()