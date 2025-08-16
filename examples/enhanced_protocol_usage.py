#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强协议处理器使用示例

本示例展示如何使用新增的协议优化功能：
1. 统一错误处理机制
2. 重传和ACK机制
3. 性能监控和优化

作者: YJ Studio
日期: 2024
"""

import sys
import time
from typing import Optional
from PySide6.QtCore import QObject, QByteArray, QTimer, QCoreApplication
from PySide6.QtWidgets import QApplication

# 添加项目根目录到路径
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from core.protocol_handler import (
    FrameParser, ProtocolSender, ProtocolAnalyzer, 
    PendingFrame, ProtocolError
)
from utils.constants import ChecksumMode
from utils.data_models import FrameConfig
from utils.logger import ErrorLogger
from utils.protocol_config_manager import ProtocolConfigManager, get_global_config_manager

class EnhancedProtocolDemo(QObject):
    """增强协议演示类"""
    
    def __init__(self, config_file_path=None):
        super().__init__()
        
        # 初始化配置管理器
        self.config_manager = ProtocolConfigManager(config_file_path)
        
        # 初始化日志记录器
        self.logger = ErrorLogger()
        
        # 初始化帧解析器
        self.frame_parser = FrameParser(
            error_logger=self.logger,
            buffer_size=1024 * 64,  # 64KB缓冲区
            config_manager=self.config_manager
        )
        
        # 初始化协议发送器
        self.protocol_sender = ProtocolSender(
            frame_parser=self.frame_parser,
            send_func=self.mock_send_function,
            error_logger=self.logger,
            config_manager=self.config_manager
        )
        
        # 初始化协议分析器
        self.analyzer = ProtocolAnalyzer(
            error_logger=self.logger
        )
        
        # 配置帧格式
        self.frame_config = FrameConfig(
            head="AB",
            s_addr="01",
            d_addr="02",
            func_id="C1"
        )
        
        # 连接信号
        self._connect_signals()
        
        # 性能监控定时器
        stats_interval = self.config_manager.performance.stats_update_interval_ms
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.print_performance_stats)
        self.stats_timer.start(stats_interval)
        
        self.logger.log_info("增强协议演示初始化完成")
    
    def _connect_signals(self):
        """连接信号槽"""
        # 帧解析信号
        self.frame_parser.frame_successfully_parsed.connect(self.on_frame_parsed)
        self.frame_parser.checksum_error.connect(self.on_checksum_error)
        self.frame_parser.ack_received.connect(self.on_ack_received)
        self.frame_parser.nack_received.connect(self.on_nack_received)
        self.frame_parser.retransmission_needed.connect(self.on_retransmission_needed)
        
        # 发送器信号
        self.protocol_sender.frame_sent.connect(self.on_frame_sent)
        self.protocol_sender.send_failed.connect(self.on_send_failed)
        
        # 分析器信号
        self.analyzer.performance_warning.connect(self.on_performance_warning)
    
    def mock_send_function(self, data: bytes):
        """模拟发送函数"""
        self.logger.log_debug(f"模拟发送: {data.hex(' ').upper()}")
        
        # 模拟网络延迟
        QTimer.singleShot(10, lambda: self.simulate_response(data))
    
    def simulate_response(self, sent_data: bytes):
        """模拟接收响应"""
        # 模拟90%的成功率
        import random
        if random.random() < 0.9:
            # 模拟ACK响应
            if len(sent_data) >= 8:  # 确保有足够的数据
                # 提取序列号（如果存在）
                try:
                    # 假设序列号在数据段的前2字节
                    seq_bytes = sent_data[8:10] if len(sent_data) >= 10 else b'\x00\x00'
                    ack_frame = self.build_ack_frame(seq_bytes)
                    self.simulate_receive(ack_frame)
                except Exception as e:
                    self.logger.log_warning(f"模拟ACK生成失败: {e}")
        else:
            # 模拟NACK响应
            if len(sent_data) >= 8:
                try:
                    seq_bytes = sent_data[8:10] if len(sent_data) >= 10 else b'\x00\x00'
                    nack_frame = self.build_nack_frame(seq_bytes, "模拟传输错误")
                    self.simulate_receive(nack_frame)
                except Exception as e:
                    self.logger.log_warning(f"模拟NACK生成失败: {e}")
    
    def build_ack_frame(self, seq_bytes: bytes) -> bytes:
        """构建ACK帧"""
        frame = bytearray()
        frame.append(0xAB)  # 帧头
        frame.append(0x02)  # 源地址
        frame.append(0x01)  # 目标地址
        frame.append(0xF0)  # ACK功能码
        frame.extend(b'\x02\x00')  # 数据长度=2
        frame.extend(seq_bytes)  # 序列号
        
        # 计算校验和
        sc = sum(frame) & 0xFF
        ac = 0
        for b in frame:
            ac = (ac + sc) & 0xFF
        frame.extend([sc, ac])
        
        return bytes(frame)
    
    def build_nack_frame(self, seq_bytes: bytes, error_msg: str) -> bytes:
        """构建NACK帧"""
        error_data = error_msg.encode('utf-8')[:20]  # 限制错误信息长度
        data_len = 2 + len(error_data)
        
        frame = bytearray()
        frame.append(0xAB)  # 帧头
        frame.append(0x02)  # 源地址
        frame.append(0x01)  # 目标地址
        frame.append(0xF1)  # NACK功能码
        frame.extend(data_len.to_bytes(2, 'little'))  # 数据长度
        frame.extend(seq_bytes)  # 序列号
        frame.extend(error_data)  # 错误信息
        
        # 计算校验和
        sc = sum(frame) & 0xFF
        ac = 0
        for b in frame:
            ac = (ac + sc) & 0xFF
        frame.extend([sc, ac])
        
        return bytes(frame)
    
    def simulate_receive(self, data: bytes):
        """模拟接收数据"""
        self.logger.log_debug(f"模拟接收: {data.hex(' ').upper()}")
        qdata = QByteArray(data)
        self.frame_parser.append_data(qdata)
        self.frame_parser.try_parse_frames(
            self.frame_config,
            "",  # 不过滤功能码
            ChecksumMode.ORIGINAL_SUM_ADD
        )
    
    def demo_basic_sending(self):
        """演示基本发送功能"""
        self.logger.log_info("=== 演示基本发送功能 ===")
        
        # 显示当前配置
        config_summary = self.config_manager.get_config_summary()
        self.logger.log_info(f"当前配置: {config_summary}")
        
        # 发送不需要ACK的帧
        test_data = b"Hello, World!"
        dest_addr = int(self.config_manager.frame_format.default_dest_addr, 16)
        success = self.protocol_sender.send_frame(
            dest_addr=dest_addr,
            func_id=0x10,
            data=test_data,
            use_ack=False
        )
        
        self.logger.log_info(f"基本发送结果: {'成功' if success else '失败'}")
    
    def demo_ack_mechanism(self):
        """演示ACK机制"""
        self.logger.log_info("=== 演示ACK重传机制 ===")
        
        if not self.config_manager.ack_mechanism.enabled:
            self.logger.log_info("ACK机制已禁用，跳过演示")
            return
        
        # 配置ACK机制
        window_size = self.config_manager.ack_mechanism.window_size
        self.frame_parser.set_ack_enabled(True)
        self.frame_parser.set_window_size(window_size)
        
        self.logger.log_info(f"ACK窗口大小: {window_size}")
        self.logger.log_info(f"超时时间: {self.config_manager.ack_mechanism.default_timeout_ms}ms")
        self.logger.log_info(f"最大重试次数: {self.config_manager.ack_mechanism.max_retries}")
        
        # 发送需要ACK的帧
        dest_addr = int(self.config_manager.frame_format.default_dest_addr, 16)
        for i in range(min(3, window_size)):
            test_data = f"ACK测试数据 {i+1}".encode('utf-8')
            success = self.protocol_sender.send_frame(
                dest_addr=dest_addr,
                func_id=0x20,
                data=test_data,
                use_ack=True,
                max_retries=self.config_manager.ack_mechanism.max_retries,
                timeout_ms=self.config_manager.ack_mechanism.default_timeout_ms
            )
            
            self.logger.log_info(f"ACK发送 {i+1} 结果: {'成功' if success else '失败'}")
            time.sleep(0.1)
    
    def demo_performance_monitoring(self):
        """演示性能监控"""
        self.logger.log_info("=== 演示性能监控 ===")
        
        if not self.config_manager.optimization.enable_performance_monitoring:
            self.logger.log_info("性能监控已禁用，跳过演示")
            return
        
        # 发送大量数据测试性能
        start_time = time.time()
        dest_addr = int(self.config_manager.frame_format.default_dest_addr, 16)
        
        for i in range(50):
            test_data = f"性能测试数据包 {i:03d} - " + "X" * 100
            test_data = test_data.encode('utf-8')
            
            self.protocol_sender.send_frame(
                dest_addr=dest_addr,
                func_id=0x30,
                data=test_data,
                use_ack=False
            )
            
            # 模拟接收数据进行解析性能测试
            if i % 10 == 0:
                self.simulate_large_data_receive()
        
        elapsed = time.time() - start_time
        self.logger.log_info(f"性能测试完成，耗时: {elapsed:.2f}秒")
    
    def simulate_large_data_receive(self):
        """模拟接收大量数据"""
        # 构建一个大的数据包
        large_data = b"Large data test: " + b"X" * 200
        frame_data = self.protocol_sender._build_frame(0x01, 0x40, large_data)
        
        qdata = QByteArray(frame_data)
        self.frame_parser.append_data(qdata)
        self.frame_parser.try_parse_frames(
            self.frame_config,
            "",
            ChecksumMode.ORIGINAL_SUM_ADD
        )
    
    def demo_error_handling(self):
        """演示错误处理"""
        self.logger.log_info("=== 演示错误处理机制 ===")
        
        # 发送损坏的帧数据
        corrupted_frame = b"\xAB\x01\x02\x50\x05\x00Hello\xFF\xFF"  # 错误的校验和
        qdata = QByteArray(corrupted_frame)
        self.frame_parser.append_data(qdata)
        self.frame_parser.try_parse_frames(
            self.frame_config,
            "",
            ChecksumMode.ORIGINAL_SUM_ADD
        )
        
        # 发送长度错误的帧
        invalid_length_frame = b"\xAB\x01\x02\x60\xFF\xFF"  # 长度字段错误
        qdata = QByteArray(invalid_length_frame)
        self.frame_parser.append_data(qdata)
        self.frame_parser.try_parse_frames(
            self.frame_config,
            "",
            ChecksumMode.ORIGINAL_SUM_ADD
        )
    
    def demo_configuration_management(self):
        """演示配置管理"""
        self.logger.log_info("=== 演示配置管理 ===")
        
        # 显示当前配置
        self.logger.log_info("当前配置摘要:")
        config_summary = self.config_manager.get_config_summary()
        for key, value in config_summary.items():
            self.logger.log_info(f"  {key}: {value}")
        
        # 动态修改配置
        self.logger.log_info("\n修改ACK超时时间...")
        original_timeout = self.config_manager.ack_mechanism.default_timeout_ms
        self.config_manager.update_ack_mechanism(default_timeout_ms=2000)
        self.logger.log_info(f"超时时间: {original_timeout}ms -> {self.config_manager.ack_mechanism.default_timeout_ms}ms")
        
        # 修改性能配置
        self.logger.log_info("\n修改缓冲区大小...")
        original_buffer = self.config_manager.performance.buffer_size
        self.config_manager.update_performance(buffer_size=128*1024)
        self.logger.log_info(f"缓冲区大小: {original_buffer} -> {self.config_manager.performance.buffer_size}")
        
        # 保存配置
        self.logger.log_info("\n保存配置...")
        if self.config_manager.save_config():
            self.logger.log_info("配置保存成功")
        else:
            self.logger.log_info("配置保存失败")
        
        # 恢复原始配置
        self.config_manager.update_ack_mechanism(default_timeout_ms=original_timeout)
        self.config_manager.update_performance(buffer_size=original_buffer)
    
    def print_performance_stats(self):
        """打印性能统计信息"""
        parser_stats = self.frame_parser.get_performance_stats()
        analyzer_stats = self.analyzer.get_statistics()
        
        self.logger.log_info("=== 性能统计 ===")
        self.logger.log_info(f"解析器统计: {parser_stats}")
        self.logger.log_info(f"分析器统计: {analyzer_stats}")
        self.logger.log_info(f"待确认帧数: {self.protocol_sender.get_pending_count()}")
    
    # 信号处理函数
    def on_frame_parsed(self, func_id: str, data: QByteArray):
        """帧解析成功处理"""
        data_hex = data.toHex(' ').data().decode().upper()
        self.logger.log_info(f"帧解析成功 - 功能码: {func_id}, 数据: {data_hex}")
    
    def on_checksum_error(self, error_msg: str, frame_data: QByteArray):
        """校验和错误处理"""
        frame_hex = frame_data.toHex(' ').data().decode().upper()
        self.logger.log_warning(f"校验和错误: {error_msg}, 帧: {frame_hex}")
    
    def on_ack_received(self, seq_num: int):
        """ACK接收处理"""
        self.logger.log_info(f"收到ACK确认 - 序列号: {seq_num}")
    
    def on_nack_received(self, seq_num: int, error_reason: str):
        """NACK接收处理"""
        self.logger.log_warning(f"收到NACK - 序列号: {seq_num}, 原因: {error_reason}")
    
    def on_retransmission_needed(self, seq_num: int):
        """重传需求处理"""
        self.logger.log_warning(f"需要重传 - 序列号: {seq_num}")
    
    def on_frame_sent(self, seq_num: int, frame_data: bytes):
        """帧发送成功处理"""
        self.logger.log_debug(f"帧发送成功 - 序列号: {seq_num}, 长度: {len(frame_data)}")
    
    def on_send_failed(self, seq_num: int, error_reason: str):
        """发送失败处理"""
        self.logger.log_error(f"帧发送失败 - 序列号: {seq_num}, 原因: {error_reason}")
    
    def on_performance_warning(self, warning_msg: str):
        """性能警告处理"""
        self.logger.log_warning(f"性能警告: {warning_msg}")
    
    def run_all_demos(self):
        """运行所有演示"""
        self.logger.log_info("开始增强协议功能演示")
        
        # 配置管理演示
        self.demo_configuration_management()
        time.sleep(1)
        
        # 基本发送演示
        self.demo_basic_sending()
        time.sleep(1)
        
        # ACK机制演示
        self.demo_ack_mechanism()
        time.sleep(2)
        
        # 错误处理演示
        self.demo_error_handling()
        time.sleep(1)
        
        # 性能监控演示
        self.demo_performance_monitoring()
        time.sleep(1)
        
        self.logger.log_info("所有演示完成")

def main():
    """主函数"""
    app = QCoreApplication(sys.argv)
    
    # 创建演示实例
    demo = EnhancedProtocolDemo()
    
    # 延迟启动演示，让Qt事件循环先运行
    QTimer.singleShot(100, demo.run_all_demos)
    
    # 10秒后退出
    QTimer.singleShot(10000, app.quit)
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())