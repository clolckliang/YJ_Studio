import ast
from datetime import datetime
from typing import Optional, Any, List, Dict, Callable, Tuple, Union
from contextlib import contextmanager

import struct
import json
import time
import math
import re
import sys
import traceback
import threading  # Required for QMutex fallback and for ScriptEngine._output_buffer_lock
import signal
import numpy

# 假设 PySide6 可用，如果环境不同，QMutex 可能需要替换
try:
    from PySide6.QtCore import QThread, Signal, QMutex, QByteArray, QTimer, QObject,QRecursiveMutex
except ImportError:
    print("Warning: PySide6 not found. Using basic threading.Lock for QMutex.")


    # Fallback if PySide6 is not available, for basic threading lock
    class QMutex:
        def __init__(self):
            self._lock = threading.Lock()  # Use re-entrant lock

        def lock(self):
            self._lock.acquire()

        def unlock(self):
            self._lock.release()

        def tryLock(self, timeout: Optional[int] = None) -> bool:
            if timeout is None:
                return self._lock.acquire(blocking=False)
            elif timeout == 0:
                return self._lock.acquire(blocking=False)
            else:
                return self._lock.acquire(blocking=True, timeout=timeout / 1000.0)


    class QObject:
        pass  # Placeholder


    class QThread(threading.Thread, QObject):  # Basic QThread placeholder
        def __init__(self, parent: Optional[QObject] = None):
            threading.Thread.__init__(self)
            QObject.__init__(self)  # Not a real QObject, just for structure
            self._parent = parent

        def msleep(self, ms: int): time.sleep(ms / 1000.0)

        def quit(self): pass  # Placeholder

        def wait(self, timeout: Optional[int] = None):  # timeout in ms
            super().join(timeout=timeout / 1000.0 if timeout else None)


    class Signal:  # Basic Signal placeholder
        def __init__(self, *args):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

        def disconnect(self, callback):
            try:
                self.callbacks.remove(callback)
            except ValueError:
                pass

        def emit(self, *args):
            for cb in self.callbacks:
                try:
                    cb(*args)
                except Exception as e:
                    print(f"Error in Signal callback: {e}")


    class QByteArray:  # Basic QByteArray placeholder
        def __init__(self, initial_data=None, fill_value=None):
            if isinstance(initial_data, int) and fill_value is not None:
                # Handle QByteArray(size, fill_value) constructor
                self._data = bytearray([fill_value] * initial_data)
            elif isinstance(initial_data, QByteArray):
                self._data = bytearray(initial_data._data)
            elif isinstance(initial_data, (bytes, bytearray)):
                self._data = bytearray(initial_data)
            elif isinstance(initial_data, str):
                self._data = bytearray(initial_data, 'utf-8')  # Default encoding
            elif initial_data is None:
                self._data = bytearray()
            else:
                raise TypeError("Invalid data type for QByteArray")
                

        def size(self) -> int:
            return len(self._data)

        def append(self, data: Any):
            if isinstance(data, (str, int)):  # Handle single char/byte
                self._data.append(ord(data) if isinstance(data, str) else data)
            elif isinstance(data, (bytes, bytearray, QByteArray)):
                self._data.extend(data._data if isinstance(data, QByteArray) else data)
            else:
                raise TypeError(f"Cannot append type {type(data)} to QByteArray")

        def at(self, i: int) -> int:
            return self._data[i]  # Returns int (byte value)

        def data(self) -> bytes:
            return bytes(self._data)

        def toStdString(self) -> str:
            return self._data.decode('utf-8', errors='replace')  # Common usage

        def replace(self, pos: int, count: int, data: bytes):
            self._data = self._data[:pos] + bytearray(data) + self._data[pos + count:]

        def resize(self, size: int):
            if size > len(self._data):
                self._data.extend(b'\x00' * (size - len(self._data)))
            else:
                self._data = self._data[:size]

        def reserve(self, size: int):
            pass  # Placeholder, bytearray grows automatically

        def clear(self):
            self._data.clear()

        def __bytes__(self):
            return bytes(self._data)

        def __str__(self):
            return self.toStdString()

        def __getitem__(self, index):
            return self._data[index]

        def __setitem__(self, index, value):
            self._data[index] = value


class ProtocolManager:
    """管理协议处理器的注册和获取"""

    def __init__(self):
        self.protocols: Dict[str, Any] = {}
        self._mutex = QMutex()  # 添加线程安全

    def register_protocol(self, name: str, protocol_handler: Any):
        self._mutex.lock()
        try:
            if name in self.protocols:
                print(f"Warning: Protocol '{name}' is being overwritten.")
            self.protocols[name] = protocol_handler
            print(f"Protocol '{name}' registered successfully.")
        finally:
            self._mutex.unlock()

    def get_protocol(self, name: str) -> Optional[Any]:
        self._mutex.lock()
        try:
            protocol = self.protocols.get(name)
            if protocol is None:
                print(f"Warning: Protocol '{name}' not found.")
            return protocol
        finally:
            self._mutex.unlock()

    def unregister_protocol(self, name: str) -> bool:
        self._mutex.lock()
        try:
            if name in self.protocols:
                del self.protocols[name]
                print(f"Protocol '{name}' unregistered successfully.")
                return True
            else:
                print(f"Warning: Protocol '{name}' not found for unregistration.")
                return False
        finally:
            self._mutex.unlock()

    def list_protocols(self) -> List[str]:
        self._mutex.lock()
        try:
            return list(self.protocols.keys())
        finally:
            self._mutex.unlock()

    def clear_protocols(self):
        self._mutex.lock()
        try:
            self.protocols.clear()
            print("All protocols cleared.")
        finally:
            self._mutex.unlock()





class CircularBuffer:
    """基于 bytearray 的线程安全环形缓冲区实现，优化内存管理和数据拷贝操作"""
    
    def __init__(self, size: int):
        if size <= 0:
            raise ValueError("Buffer size must be positive")
        
        # 使用 bytearray 作为内部存储，更高效且支持索引赋值
        self._internal_buffer = bytearray(size)
        self.max_size = size
        self.capacity = size  # 添加 capacity 属性以兼容现有代码
        self.head = 0
        self.tail = 0
        self.count = 0
        self.mutex = QRecursiveMutex()  # 使用递归锁防止嵌套调用死锁
        
        # 性能优化：预分配临时缓冲区，避免频繁内存分配
        self._temp_buffer_size = min(size // 4, 4096)  # 最大4KB临时缓冲区
        self._temp_buffer = bytearray(self._temp_buffer_size)
        
        # 性能统计
        self._stats = {
            'total_writes': 0,
            'total_reads': 0,
            'bytes_written': 0,
            'bytes_read': 0,
            'buffer_overflows': 0
        }

    def write(self, data: QByteArray) -> int:
        """写入数据，返回实际写入字节数，优化批量写入操作"""
        if data.size() == 0:
            return 0

        self.mutex.lock()
        try:
            data_bytes = data.data()  # 获取字节数据
            data_len = len(data_bytes)
            
            # 更新统计信息
            self._stats['total_writes'] += 1
            self._stats['bytes_written'] += data_len
            
            # 处理缓冲区溢出
            if data_len > self.max_size:
                # 数据太大，只保留最后的部分
                data_bytes = data_bytes[-self.max_size:]
                data_len = self.max_size
                self._stats['buffer_overflows'] += 1
            
            # 计算可写入的数据量
            available = self.max_size - self.count
            if data_len > available:
                # 缓冲区满，覆盖旧数据
                overflow = data_len - available
                self.tail = (self.tail + overflow) % self.max_size
                self.count = self.max_size - data_len
                self._stats['buffer_overflows'] += 1
            
            # 优化：批量写入数据，减少循环开销
            if self.head + data_len <= self.max_size:
                # 数据可以连续写入
                self._internal_buffer[self.head:self.head + data_len] = data_bytes
                self.head = (self.head + data_len) % self.max_size
            else:
                # 数据需要分两段写入
                first_part = self.max_size - self.head
                self._internal_buffer[self.head:] = data_bytes[:first_part]
                self._internal_buffer[:data_len - first_part] = data_bytes[first_part:]
                self.head = data_len - first_part
            
            self.count = min(self.count + data_len, self.max_size)
            return data_len
        finally:
            self.mutex.unlock()

    def read(self, length: int) -> QByteArray:
        """读取并移除数据，返回 QByteArray，优化内存分配"""
        self.mutex.lock()
        try:
            # 更新统计信息
            self._stats['total_reads'] += 1
            
            data = self.peek(length)
            actual_read = min(length, self.count)
            self.discard(actual_read)
            
            # 更新读取字节统计
            self._stats['bytes_read'] += actual_read
            return data
        finally:
            self.mutex.unlock()

    def peek(self, length: int) -> QByteArray:
        """查看但不移除数据，返回 QByteArray，优化批量数据拷贝"""
        if length <= 0 or self.count == 0:
            return QByteArray()

        self.mutex.lock()
        try:
            bytes_to_peek = min(length, self.count)
            
            # 优化：使用预分配的临时缓冲区或直接分配
            if bytes_to_peek <= self._temp_buffer_size:
                result_bytes = self._temp_buffer[:bytes_to_peek]
            else:
                result_bytes = bytearray(bytes_to_peek)
            
            # 优化：批量拷贝数据，减少循环开销
            if self.tail + bytes_to_peek <= self.max_size:
                # 数据是连续的，可以直接拷贝
                result_bytes[:] = self._internal_buffer[self.tail:self.tail + bytes_to_peek]
            else:
                # 数据跨越缓冲区边界，需要分两段拷贝
                first_part = self.max_size - self.tail
                result_bytes[:first_part] = self._internal_buffer[self.tail:]
                result_bytes[first_part:] = self._internal_buffer[:bytes_to_peek - first_part]
                
            return QByteArray(bytes(result_bytes))
        finally:
            self.mutex.unlock()

    def mid(self, pos: int, length: int = -1) -> QByteArray:
        """从指定位置提取数据（不移动指针），优化批量拷贝"""
        self.mutex.lock()
        try:
            if pos < 0 or pos >= self.count:
                return QByteArray()
            
            available_length = self.count - pos
            if length < 0 or length > available_length:
                length = available_length
            
            if length <= 0:
                return QByteArray()
            
            physical_pos = (self.tail + pos) % self.max_size
            
            # 优化：使用预分配的临时缓冲区或直接分配
            if length <= self._temp_buffer_size:
                result_bytes = self._temp_buffer[:length]
            else:
                result_bytes = bytearray(length)
            
            # 优化：批量拷贝数据
            if physical_pos + length <= self.max_size:
                # 数据是连续的，可以直接拷贝
                result_bytes[:] = self._internal_buffer[physical_pos:physical_pos + length]
            else:
                # 数据跨越缓冲区边界，需要分两段拷贝
                first_part = self.max_size - physical_pos
                result_bytes[:first_part] = self._internal_buffer[physical_pos:]
                result_bytes[first_part:] = self._internal_buffer[:length - first_part]
            
            return QByteArray(bytes(result_bytes))
        finally:
            self.mutex.unlock()

    def left(self, length: int) -> QByteArray:
        """获取缓冲区开头的数据"""
        return self.mid(0, length)

    def right(self, length: int) -> QByteArray:
        """获取缓冲区末尾的数据"""
        return self.mid(max(0, self.count - length))

    def discard(self, length: int) -> int:
        """丢弃指定长度的数据，返回实际丢弃字节数"""
        if length <= 0:
            return 0

        self.mutex.lock()
        try:
            bytes_to_discard = min(length, self.count)
            self.tail = (self.tail + bytes_to_discard) % self.max_size
            self.count -= bytes_to_discard
            return bytes_to_discard
        finally:
            self.mutex.unlock()

    def clear(self):
        """清空缓冲区"""
        self.mutex.lock()
        try:
            self.head = 0
            self.tail = 0
            self.count = 0
        finally:
            self.mutex.unlock()

    def get_count(self) -> int:
        """获取当前数据量"""
        self.mutex.lock()
        try:
            return self.count
        finally:
            self.mutex.unlock()

    def get_free_space(self) -> int:
        """获取剩余空间"""
        self.mutex.lock()
        try:
            return self.max_size - self.count
        finally:
            self.mutex.unlock()

    def is_empty(self) -> bool:
        """检查是否为空"""
        return self.get_count() == 0

    def is_full(self) -> bool:
        """检查是否已满"""
        return self.get_count() == self.max_size

    def get_stats(self) -> dict:
        """获取性能统计信息"""
        self.mutex.lock()
        try:
            stats = self._stats.copy()
            stats.update({
                'current_usage': self.count,
                'usage_percentage': (self.count / self.max_size) * 100,
                'buffer_size': self.max_size,
                'free_space': self.max_size - self.count
            })
            return stats
        finally:
            self.mutex.unlock()
    
    def reset_stats(self):
        """重置性能统计信息"""
        self.mutex.lock()
        try:
            self._stats = {
                'total_writes': 0,
                'total_reads': 0,
                'bytes_written': 0,
                'bytes_read': 0,
                'buffer_overflows': 0
            }
        finally:
            self.mutex.unlock()

    def debug_dump(self) -> str:
        """调试用：打印缓冲区状态和性能统计"""
        self.mutex.lock()
        try:
            stats = self.get_stats()
            return (f"CircularBuffer(size={self.max_size}, used={self.count})\n"
                   f"Head: {self.head}, Tail: {self.tail}\n"
                   f"Usage: {stats['usage_percentage']:.1f}%\n"
                   f"Stats: Writes={stats['total_writes']}, Reads={stats['total_reads']}, "
                   f"Overflows={stats['buffer_overflows']}\n"
                   f"Data: {self._internal_buffer.hex(' ')}")
        finally:
            self.mutex.unlock()
class DataProcessor(QThread):
    """数据处理线程类"""
    processed_data_signal = Signal(str, QByteArray)
    processing_error_signal = Signal(str)
    processing_stats_signal = Signal(dict)

    def __init__(self, parent: Optional[QObject] = None, batch_size: int = 5):
        super().__init__(parent)
        self.queue: List[Tuple[str, QByteArray]] = []
        self.mutex = QMutex()
        self._running = False
        self._batch_size = batch_size
        self._stats: Dict[str, Any] = {
            'processed_count': 0, 'error_count': 0,
            'start_time': None, 'last_activity': None,
            'queue_size_history': []
        }
        self.MAX_QUEUE_HISTORY = 100
        self.main_window_ref: Optional[Any] = parent if hasattr(parent, 'error_logger') else None

    def add_data(self, func_id: str, data: QByteArray):
        if not data or data.size() == 0: return
        self.mutex.lock()
        try:
            self.queue.append((func_id, data))
            self._stats['last_activity'] = datetime.now()
            if len(self._stats['queue_size_history']) > self.MAX_QUEUE_HISTORY:
                self._stats['queue_size_history'].pop(0)
            self._stats['queue_size_history'].append(len(self.queue))
        finally:
            self.mutex.unlock()

    def get_queue_size(self) -> int:
        self.mutex.lock()
        try:
            return len(self.queue)
        finally:
            self.mutex.unlock()

    def clear_queue(self):
        self.mutex.lock()
        try:
            self.queue.clear()
            self._stats['queue_size_history'].clear()
        finally:
            self.mutex.unlock()

    def get_stats(self) -> Dict:
        stats_copy = self._stats.copy()
        if stats_copy['start_time']:
            stats_copy['uptime_seconds'] = (datetime.now() - stats_copy['start_time']).total_seconds()
        stats_copy['current_queue_size'] = self.get_queue_size()
        return stats_copy

    def run(self):
        self._running = True
        self._stats['start_time'] = datetime.now()
        logger = getattr(self.main_window_ref, 'error_logger', None)
        if logger:
            logger.log_info("DataProcessor thread started.")
        else:
            print("DataProcessor thread started.")

        try:
            while self._running:
                processed_in_this_cycle = 0
                items_to_process_batch = []
                self.mutex.lock()
                try:
                    count = 0
                    while self.queue and count < self._batch_size:
                        items_to_process_batch.append(self.queue.pop(0))
                        count += 1
                finally:
                    self.mutex.unlock()

                # noinspection PyUnreachableCode
                for item_to_process in items_to_process_batch:
                    if not self._running: break
                    func_id, data_payload = item_to_process
                    try:
                        processed_result_payload = QByteArray(data_payload)
                        self.processed_data_signal.emit(func_id, processed_result_payload)
                        self._stats['processed_count'] += 1
                        processed_in_this_cycle += 1
                    except Exception as e:
                        error_msg = f"DataProcessor: Error during processing for FID {func_id}: {e}"
                        self.processing_error_signal.emit(error_msg)
                        self._stats['error_count'] += 1

                if not self._running and items_to_process_batch:
                    self._stats['last_activity'] = datetime.now()

                if processed_in_this_cycle > 0:
                    self._stats['last_activity'] = datetime.now()
                    if self._stats['processed_count'] % 10 == 0:
                        self.processing_stats_signal.emit(self.get_stats())

                if not items_to_process_batch:
                    self.msleep(50)
                else:
                    self.msleep(10)

        except Exception as e:
            fatal_error_msg = f"DataProcessor thread encountered a fatal error: {e}\n{traceback.format_exc()}"
            self.processing_error_signal.emit(fatal_error_msg)
            if logger:
                logger.log_error(fatal_error_msg, "DATA_PROCESSOR_FATAL")
            else:
                print(fatal_error_msg)
        finally:
            final_stats = self.get_stats()
            self.processing_stats_signal.emit(final_stats)
            log_msg = f"DataProcessor thread stopped. Processed: {final_stats.get('processed_count', 0)}, Errors: {final_stats.get('error_count', 0)}."
            if logger:
                logger.log_info(log_msg)
            else:
                print(log_msg)

    def stop(self):
        logger = getattr(self.main_window_ref, 'error_logger', None)
        if logger:
            logger.log_info("DataProcessor: Stop requested.")
        else:
            print("DataProcessor: Stop requested.")
        self._running = False


# --- 脚本引擎相关异常类 ---
class ScriptExecutionTimeout(Exception):
    """脚本执行超时异常"""
    pass


class ScriptSecurityError(Exception):
    """脚本安全违规异常"""
    pass


class ScriptExecutionError(Exception):
    """脚本执行期间发生的一般错误"""
    pass


# --- 安全和环境辅助类 ---
class RestrictedImport:
    """受限制的导入处理器"""
    ALLOWED_MODULES = {
        'datetime', 'struct', 'json', 'time', 'math', 're',
        'random', 'itertools', 'collections', 'functools',
        'decimal', 'fractions', 'statistics',
        'threading','numpy',  # <-- 添加想用的模块
    }

    def __init__(self, original_import_func: Callable):
        self.original_import = original_import_func

    def __call__(self, name: str, globals_dict: Optional[Dict] = None, locals_dict: Optional[Dict] = None,
                 fromlist: Tuple[str, ...] = (), level: int = 0):
        base_module = name.split('.')[0]
        if base_module not in self.ALLOWED_MODULES:
            raise ScriptSecurityError(f"Import of module '{name}' (base: '{base_module}') is not allowed.")
        return self.original_import(name, globals_dict, locals_dict, fromlist, level)


class SafeBuiltins:
    """提供安全的内置函数集合"""
    SAFE_BUILTINS_NAMES = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes', 'callable', 'chr',
        'complex', 'dict', 'dir', 'divmod', 'enumerate', 'filter', 'float', 'format',
        'frozenset', 'getattr', 'hasattr', 'hash', 'hex', 'id', 'int', 'isinstance',
        'issubclass', 'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'object',
        'oct', 'ord', 'pow', 'print', 'range', 'repr', 'reversed', 'round', 'set',
        'slice', 'sorted', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip',
    }

    @classmethod
    def get_safe_builtins(cls) -> Dict[str, Any]:
        import builtins  # noqa
        safe_builtins_dict: Dict[str, Any] = {}

        for name in dir(builtins):
            attr = getattr(builtins, name)
            if isinstance(attr, type) and issubclass(attr, BaseException):
                safe_builtins_dict[name] = attr

        if hasattr(builtins, '__build_class__'):
            safe_builtins_dict['__build_class__'] = getattr(builtins, '__build_class__')
        else:
            print("Critical Warning: builtins.__build_class__ not found. Class definitions will fail.", file=sys.stderr)

        for name in cls.SAFE_BUILTINS_NAMES:
            if hasattr(builtins, name):
                attr = getattr(builtins, name)
                if callable(attr):
                    safe_builtins_dict[name] = attr
                elif name in {'None', 'True', 'False'}:
                    pass

        if hasattr(builtins, 'classmethod'):
            safe_builtins_dict['classmethod'] = getattr(builtins, 'classmethod')
        else:
            print("Warning: builtins.classmethod not found. @classmethod decorator will not work.", file=sys.stderr)

        if hasattr(builtins, 'staticmethod'):
            safe_builtins_dict['staticmethod'] = getattr(builtins, 'staticmethod')
        else:
            print("Warning: builtins.staticmethod not found. @staticmethod decorator will not work.", file=sys.stderr)

        original_import_func = getattr(builtins, '__import__', None)
        if original_import_func:
            safe_builtins_dict['__import__'] = RestrictedImport(original_import_func)
        else:
            try:
                original_import_func = __import__.__class__.__bases__[0].__import__  # type: ignore
                safe_builtins_dict['__import__'] = RestrictedImport(original_import_func)
            except (AttributeError, IndexError, TypeError):
                print("Warning: Could not retrieve __import__ function for sandboxing. Imports will fail.",
                      file=sys.stderr)

        return safe_builtins_dict


class ScriptEngine:
    """
    增强的脚本执行引擎，支持函数定义、调用、安全执行环境和与宿主应用的交互。
    使用统一的 `execute` 方法。
    """

    def __init__(self, debugger_instance: Optional[Any] = None, config: Optional[Dict] = None):
        self.debugger = debugger_instance
        self.config = config if config is not None else {}

        self.timeout: int = self.config.get('timeout', 30)
        self.max_total_output_length: int = self.config.get('max_output_length', 10000)
        self.max_line_length: int = self.config.get('max_line_length', 1000)
        self.max_history: int = self.config.get('max_history', 100)

        self._script_output_buffer: List[str] = []

        self.available_modules: Dict[str, Any] = {
            'datetime': datetime, 'struct': struct, 'json': json,
            'time': time, 'math': math, 're': re,
        }
        if 'initial_modules' in self.config and isinstance(self.config['initial_modules'], dict):
            self.available_modules.update(self.config['initial_modules'])

        self.host_functions: Dict[str, Callable] = {}
        if 'initial_host_functions' in self.config and isinstance(self.config['initial_host_functions'], dict):
            self.host_functions.update(self.config['initial_host_functions'])

        self.execution_history: List[Dict] = []
        self._execution_lock = QMutex()
        self._output_buffer_lock = QMutex()  # <-- Lock for script_output_buffer

        self.pre_execution_hooks: List[Callable[[str], None]] = []
        self.post_execution_hooks: List[Callable[[Dict], None]] = []

        self._stats: Dict[str, Any] = {
            'total_executions': 0, 'successful_executions': 0,
            'failed_executions': 0, 'total_execution_time_seconds': 0.0
        }

    def add_module(self, name: str, module_instance: Any):
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValueError("Invalid module name.")
        self.available_modules[name] = module_instance
        self._log_message('info', f"Module '{name}' added.")

    def remove_module(self, name: str) -> bool:
        if name in self.available_modules:
            del self.available_modules[name]
            self._log_message('info', f"Module '{name}' removed.")
            return True
        self._log_message('warning', f"Module '{name}' not found for removal.")
        return False

    def register_host_function(self, name: str, func: Callable):
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValueError("Invalid host function name.")
        if not callable(func):
            raise ValueError("Provided host function is not callable.")
        self.host_functions[name] = func
        self._log_message('info', f"Host function '{name}' registered.")

    def unregister_host_function(self, name: str) -> bool:
        if name in self.host_functions:
            del self.host_functions[name]
            self._log_message('info', f"Host function '{name}' unregistered.")
            return True
        self._log_message('warning', f"Host function '{name}' not found for unregistration.")
        return False

    def add_pre_execution_hook(self, hook: Callable[[str], None]):
        if callable(hook): self.pre_execution_hooks.append(hook)

    def add_post_execution_hook(self, hook: Callable[[Dict], None]):
        if callable(hook): self.post_execution_hooks.append(hook)

    def get_stats(self) -> Dict[str, Any]:
        return self._stats.copy()

    def reset_stats(self):
        self._stats = {
            'total_executions': 0, 'successful_executions': 0,
            'failed_executions': 0, 'total_execution_time_seconds': 0.0
        }
        self._log_message('info', "Execution statistics reset.")

    def _safe_print(self, *args, **kwargs):
        self._output_buffer_lock.lock()  # <-- Acquire lock
        try:
            sep = kwargs.get('sep', ' ')
            end = kwargs.get('end', '\n')
            message_parts = [str(arg) for arg in args]
            message = sep.join(message_parts)

            if len(message) > self.max_line_length:
                message = message[:self.max_line_length] + "... [行已截断]"

            current_buffer_len = sum(len(s) + len(end) for s in self._script_output_buffer)

            if current_buffer_len + len(message) + len(end) <= self.max_total_output_length:
                self._script_output_buffer.append(message)
            elif not self._script_output_buffer or not self._script_output_buffer[-1].endswith("... [总输出已截断]"):
                if self._script_output_buffer and current_buffer_len < self.max_total_output_length:
                    remaining_space = self.max_total_output_length - current_buffer_len
                    trunc_msg = "... [总输出已截断]"
                    if remaining_space > len(trunc_msg) + len(end):
                        self._script_output_buffer.append(trunc_msg)
                elif not self._script_output_buffer:
                    self._script_output_buffer.append("... [总输出已截断]")
        except Exception as e:
            try:
                # To prevent _safe_print from causing issues if an error occurs within it,
                # we keep this internal error handling minimal.
                # Avoid re-locking or complex operations here.
                err_msg = f"[Error during script print: {str(e)[:50]}]"
                # Try to append error to buffer if space allows, but don't let this fail further.
                if sum(len(s) for s in self._script_output_buffer) + len(err_msg) < self.max_total_output_length:
                    if not self._script_output_buffer or not self._script_output_buffer[-1].startswith(
                            "[Error during script print"):
                        self._script_output_buffer.append(err_msg)
            except:
                pass  # Fallback: if internal print error handling fails, do nothing to avoid further issues.
        finally:
            self._output_buffer_lock.unlock()  # <-- Release lock

    def _create_safe_environment(self) -> Dict[str, Any]:
        safe_builtins_from_class = SafeBuiltins.get_safe_builtins()
        safe_builtins_from_class['print'] = self._safe_print

        execution_scope = {
            '__builtins__': safe_builtins_from_class,
            '__name__': '<script>',
            **self.available_modules,
            **self.host_functions,
            'sleep': time.sleep,  # Provided via time module, but also as a direct alias
            'now': datetime.now,  # Provided via datetime module, but also as a direct alias
        }
        if self.debugger:
            execution_scope['debugger'] = self.debugger

        return execution_scope

    @contextmanager
    def _timeout_context(self, seconds: int):
        if seconds <= 0 or not hasattr(signal, 'SIGALRM'):
            if seconds > 0 and not hasattr(signal, 'SIGALRM'):
                self._log_message('warning',
                                  "Timeout via signal.SIGALRM not supported on this platform. Timeout will not be enforced.")
            yield
            return

        def signal_handler(signum, frame):
            raise ScriptExecutionTimeout(f"Execution timed out after {seconds} seconds.")

        original_handler = signal.getsignal(signal.SIGALRM)
        try:
            signal.signal(signal.SIGALRM, signal_handler)
            signal.alarm(seconds)
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, original_handler)

    def _log_message(self, level: str, message: str, category: Optional[str] = "ScriptEngine"):
        log_entry = f"[{level.upper()}] [{category}] {message}"
        print(log_entry, file=sys.stderr)
        if self.debugger and hasattr(self.debugger, 'log_message') and callable(self.debugger.log_message):
            try:
                self.debugger.log_message(level.upper(), message, category)
            except Exception as e:
                print(f"[ERROR] Failed to call debugger.log_message: {e}", file=sys.stderr)

    def _add_to_history(self, script_text_snippet: str, success: bool, result_summary: Optional[str] = None,
                        error_message: Optional[str] = None, output_summary: Optional[str] = None):
        if len(self.execution_history) >= self.max_history: self.execution_history.pop(0)
        entry = {
            'timestamp': datetime.now().isoformat(),
            'script_snippet': script_text_snippet[:200] + ('...' if len(script_text_snippet) > 200 else ''),
            'success': success, 'result_summary': result_summary,
            'output_summary': output_summary, 'error': error_message,
        }
        self.execution_history.append(entry)

    def _prepare_execution_result(self, success: bool, script_text: str,
                                  return_value: Optional[Any] = None,
                                  error: Optional[Exception] = None,
                                  execution_time_sec: float = 0.0,
                                  custom_message: Optional[str] = None) -> Dict:
        error_str, error_type_str = None, None
        if error:
            success = False
            if isinstance(error, ScriptExecutionTimeout):
                error_str, error_type_str = f"TimeoutError: {error}", "TimeoutError"
            elif isinstance(error, ScriptSecurityError):
                error_str, error_type_str = f"SecurityError: {error}", "SecurityError"
            elif isinstance(error, SyntaxError):
                tb_lines = traceback.format_exception_only(type(error), error)
                error_str = "".join(tb_lines).strip()
                error_type_str = "SyntaxError"
            else:
                error_type_str = type(error).__name__
                error_str = f"ExecutionError: {error_type_str}: {error}\n{traceback.format_exc(limit=5)}"

        captured_output = "\n".join(self._script_output_buffer)
        self._stats['total_executions'] += 1
        self._stats['total_execution_time_seconds'] += execution_time_sec
        if success:
            self._stats['successful_executions'] += 1
        else:
            self._stats['failed_executions'] += 1

        result_dict = {
            "success": success, "return_value": return_value, "output": captured_output,
            "error_message": error_str, "error_type": error_type_str,
            "execution_time_seconds": round(execution_time_sec, 6),
            "custom_message": custom_message
        }
        self._add_to_history(script_text, success, str(return_value)[:100] if return_value is not None else None,
                             error_str[:200] if error_str else None, captured_output[:100] if captured_output else None)
        for hook in self.post_execution_hooks:
            try:
                hook(result_dict.copy())
            except Exception as hook_e:
                self._log_message('error', f"Post-execution hook failed: {hook_e}")
        return result_dict

    def validate_script_syntax(self, script_text: str) -> Tuple[bool, Optional[str]]:
        try:
            ast.parse(script_text)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} (line {e.lineno}, offset {e.offset})\nNear: {e.text.strip() if e.text else '<no text>'}"
        except Exception as e:
            return False, f"Validation Error: {type(e).__name__}: {e}"

    def _execute_statements_internal(self, script_text: str) -> Dict:
        start_time = time.perf_counter()
        execution_scope = self._create_safe_environment()
        execution_error = None
        try:
            with self._timeout_context(self.timeout):
                compiled_code = compile(script_text, '<script_exec>', 'exec')
                exec(compiled_code, execution_scope, execution_scope)
        except Exception as e:
            execution_error = e
        exec_time = time.perf_counter() - start_time
        return self._prepare_execution_result(True if execution_error is None else False, script_text,
                                              error=execution_error, execution_time_sec=exec_time)

    def _evaluate_expression_internal(self, expression_text: str) -> Dict:
        start_time = time.perf_counter()
        execution_scope = self._create_safe_environment()
        return_val, execution_error = None, None
        try:
            with self._timeout_context(self.timeout):
                compiled_code = compile(expression_text, '<script_eval>', 'eval')
                return_val = eval(compiled_code, execution_scope, execution_scope)
        except Exception as e:
            execution_error = e
        exec_time = time.perf_counter() - start_time
        return self._prepare_execution_result(True if execution_error is None else False, expression_text,
                                              return_value=return_val, error=execution_error,
                                              execution_time_sec=exec_time)

    def _run_function_internal(self, script_text: str, function_name: str, args: Tuple, kwargs: Dict) -> Dict:
        start_time = time.perf_counter()
        full_context_script_text = f"{script_text}\n# Attempting to call: {function_name}"

        execution_scope = self._create_safe_environment()
        return_val, execution_error = None, None
        try:
            with self._timeout_context(self.timeout):
                script_compiled_code = compile(script_text, '<script_defs_for_func_call>', 'exec')
                exec(script_compiled_code, execution_scope, execution_scope)

                if function_name not in execution_scope:
                    raise NameError(f"Function '{function_name}' not defined in the script or provided environment.")
                target_func = execution_scope[function_name]
                if not callable(target_func):
                    raise TypeError(f"'{function_name}' is defined but is not a callable function.")

                return_val = target_func(*args, **kwargs)
        except Exception as e:
            execution_error = e
        exec_time = time.perf_counter() - start_time
        return self._prepare_execution_result(True if execution_error is None else False, full_context_script_text,
                                              return_value=return_val, error=execution_error,
                                              execution_time_sec=exec_time)

    def execute(self, script_text: str,
                mode: str = 'exec',
                function_name: Optional[str] = None,
                args: Optional[Tuple] = None,
                kwargs: Optional[Dict] = None) -> Dict:
        self._execution_lock.lock()
        try:
            self._script_output_buffer.clear()

            _args = args if args is not None else tuple()
            _kwargs = kwargs if kwargs is not None else {}

            hook_script_info = script_text
            if mode == 'run_function' and function_name:
                hook_script_info = f"{script_text}\n# Mode: run_function, Target: {function_name}"
            elif mode == 'eval':
                hook_script_info = f"# Mode: eval\n{script_text}"

            for hook in self.pre_execution_hooks:
                try:
                    hook(hook_script_info)
                except Exception as hook_e:
                    self._log_message('error', f"Pre-execution hook failed: {hook_e}")

            if mode == 'exec':
                return self._execute_statements_internal(script_text)
            elif mode == 'eval':
                return self._evaluate_expression_internal(script_text)
            elif mode == 'run_function':
                if not function_name:
                    start_time = time.perf_counter()
                    exec_time = time.perf_counter() - start_time
                    return self._prepare_execution_result(False, script_text,
                                                          error=ValueError(
                                                              "function_name must be provided for 'run_function' mode."),
                                                          execution_time_sec=exec_time)
                return self._run_function_internal(script_text, function_name, _args, _kwargs)
            else:
                start_time = time.perf_counter()
                exec_time = time.perf_counter() - start_time
                return self._prepare_execution_result(False, script_text,
                                                      error=ValueError(
                                                          f"Invalid execution mode: {mode}. Must be 'exec', 'eval', or 'run_function'."),
                                                      execution_time_sec=exec_time)
        finally:
            self._execution_lock.unlock()


def create_script_engine(debugger_instance: Optional[Any] = None, **kwargs_config) -> ScriptEngine:
    default_config = {
        'timeout': 30, 'max_output_length': 10000, 'max_line_length': 1000,
        'max_history': 100, 'initial_modules': {}, 'initial_host_functions': {}
    }
    final_config = {**default_config, **kwargs_config}
    engine = ScriptEngine(debugger_instance, final_config)

    if final_config.get('add_example_logging_hooks', False):
        def log_pre_exec(script_info: str):
            short_info = script_info[:150].replace('\n', '\\n')
            engine._log_message('info', f"Executing (info: {short_info})...")

        def log_post_exec(result: Dict):
            status = "SUCCESS" if result['success'] else "FAILED"
            error_msg_summary = result['error_message']
            if error_msg_summary:
                error_msg_summary = error_msg_summary.split('\n', 1)[0][:100]
            engine._log_message('info',
                                f"Execution {status}. Time: {result['execution_time_seconds']:.4f}s. Error: {error_msg_summary if error_msg_summary else 'None'}")

        engine.add_pre_execution_hook(log_pre_exec)
        engine.add_post_execution_hook(log_post_exec)
        engine._log_message('info', "Added example logging hooks to ScriptEngine.")
    return engine


# --- 示例用法 (说明性) ---
if __name__ == '__main__':
    print("--- ScriptEngine Refactored Example Usage ---")


    class MyDebugger:
        def __init__(self):
            self.data_store: Dict[str, Any] = {"value": 100}
            self.call_count: int = 0
            # Add a lock for thread-safety if host functions are to be called from script threads
            self._lock = QMutex()

        def get_host_value(self, key: str) -> Any:
            self._lock.lock()
            try:
                self.call_count += 1
                print(f"[MyDebugger] Attempting to read '{key}' (Thread-safe)")
                return self.data_store.get(key, None)
            finally:
                self._lock.unlock()

        def set_host_value(self, key: str, value: Any):
            self._lock.lock()
            try:
                self.call_count += 1
                self.data_store[key] = value
                print(f"[MyDebugger] Set '{key}' to '{value}' (Thread-safe)")
            finally:
                self._lock.unlock()

        def log_message(self, level: str, message: str, category: Optional[str] = None):
            cat_str = category if category else "APP"
            print(f"[DebuggerLOG-{level.upper()}-{cat_str.upper()}] {message}")


    my_debugger_instance = MyDebugger()
    engine_config = {
        'timeout': 5,
        'initial_host_functions': {
            'read_data': my_debugger_instance.get_host_value,
            'write_data': my_debugger_instance.set_host_value
        },
        'add_example_logging_hooks': True
    }
    script_engine = create_script_engine(my_debugger_instance, **engine_config)

    # ... (Tests 1-9 remain the same) ...
    print("\n--- Test 1: Execute Script (mode='exec') ---")
    script1 = """
print("Hello from script1!")
a = 10; b = 20; print(f"a + b = {a + b}")
script_global_var = 50 
def my_script_func(x, y):
    print(f"my_script_func called with {x}, {y}")
    host_val = read_data("value") 
    if host_val is None: host_val = 0
    print(f"Accessing script_global_var: {script_global_var}")
    return x * y + host_val + script_global_var

result_from_func = my_script_func(3, 4)
print(f"Result from my_script_func: {result_from_func}")
write_data("script_run_time", now().strftime("%Y-%m-%d %H:%M:%S"))
write_data("func_result", result_from_func)
"""
    result1 = script_engine.execute(script1, mode='exec')
    print(f"Result1 Success: {result1['success']}")
    print(f"Result1 Output:\n{result1['output']}")
    if result1['error_message']: print(f"Result1 Error: {result1['error_message']}")
    print(f"Debugger call count: {my_debugger_instance.call_count}, data_store: {my_debugger_instance.data_store}")

    print("\n--- Test 2: Evaluate Expression (mode='eval') ---")
    my_debugger_instance.data_store['value'] = 200
    expr1 = "100 * 2 + read_data('value')"
    result2 = script_engine.execute(expr1, mode='eval')
    print(f"Result2 Success: {result2['success']}, Return Value: {result2['return_value']}")
    if result2['error_message']: print(f"Result2 Error: {result2['error_message']}")

    print("\n--- Test 3: Run Function in Script (mode='run_function') ---")
    my_debugger_instance.data_store['value'] = 300
    script_with_func = """
script_level_var = 10 

def complex_calculation(a, b, factor=1):
    print(f"Performing complex_calculation with a={a}, b={b}, factor={factor}")
    print(f"Accessing script_level_var: {script_level_var}") 
    intermediate = (a + b) * factor
    host_val = read_data("value")  
    if host_val is None: host_val = 0
    print(f"Read host_val: {host_val}")
    return intermediate + host_val + script_level_var
"""
    result3 = script_engine.execute(script_with_func, mode='run_function', function_name="complex_calculation",
                                    args=(5, 10), kwargs={'factor': 3})
    print(f"Result3 Success: {result3['success']}, Return Value: {result3['return_value']}")
    print(f"Result3 Output:\n{result3['output']}")
    if result3['error_message']: print(f"Result3 Error: {result3['error_message']}")

    print("\n--- Test 4: Function Not Found (mode='run_function') ---")
    result4 = script_engine.execute(script_with_func, mode='run_function', function_name="non_existent_function")
    print(f"Result4 Success: {result4['success']}, Error: {result4['error_message']}")

    print("\n--- Test 5: Timeout (mode='exec') ---")
    script_timeout = "print('Starting long loop...'); import time; c = 0\nwhile True: c += 1; time.sleep(0.0001)"  # time.sleep is from builtins
    if hasattr(signal, 'SIGALRM'):
        print("Testing timeout (will take a few seconds if it works)...")
        result5 = script_engine.execute(script_timeout, mode='exec')
        print(
            f"Result5 Success: {result5['success']}, Error Type: {result5['error_type']}, Error: {result5['error_message']}")
    else:
        print("Skipping timeout test as signal.SIGALRM is not available or not supported on this platform.")

    print("\n--- Test 6: Disallowed Import (mode='exec') ---")
    result6 = script_engine.execute("import os; print(os.getcwd())", mode='exec')  # os is not in ALLOWED_MODULES
    print(
        f"Result6 Success: {result6['success']}, Error Type: {result6['error_type']}, Error: {result6['error_message']}")

    print("\n--- Test 7: Syntax Error (mode='exec') ---")
    result7 = script_engine.execute("print('Hello'", mode='exec')
    print(
        f"Result7 Success: {result7['success']}, Error Type: {result7['error_type']}, Error: {result7['error_message']}")

    print("\n--- Test 8: Invalid Mode ---")
    result8 = script_engine.execute("print('test')", mode='invalid_mode')
    print(
        f"Result8 Success: {result8['success']}, Error Type: {result8['error_type']}, Error: {result8['error_message']}")

    print("\n--- Test 9: Accessing script-defined variable in another function (mode='exec') ---")
    script9 = """
global_val = "I am global in script"

def set_global_val(new_val):
    global global_val 
    global_val = new_val
    print(f"global_val set to: {global_val}")

def print_global_val():
    print(f"global_val is: {global_val}") 

print_global_val() 
set_global_val("New Value Set!")
print_global_val() 
"""
    result9 = script_engine.execute(script9, mode='exec')
    print(f"Result9 Success: {result9['success']}")
    print(f"Result9 Output:\n{result9['output']}")
    if result9['error_message']: print(f"Result9 Error: {result9['error_message']}")

    print("\n--- Test 10: Script-internal Exception Handling (mode='exec') ---")
    script10 = """
print("Attempting an operation that will cause an error...")
result_val = None # Renamed to avoid conflict with 'result' from engine
try:
    a = 10
    b = 0
    print("Trying to divide by zero...")
    div_result = a / b # This will raise ZeroDivisionError
    print(f"This won't be printed. Result: {div_result}")
except ZeroDivisionError as e: # This should be found in builtins now
    print(f"Caught expected ZeroDivisionError: {e}")
    result_val = "Handled ZeroDivisionError"
except Exception as e:
    print(f"Caught an unexpected exception: {e}")
    result_val = "Handled Unexpected Exception"
finally:
    print("Inside finally block.")
print(f"Final result_val after try-except: {result_val}")
if result_val is not None: # Only write if it was set
    write_data("test10_result", result_val)
"""
    result10 = script_engine.execute(script10, mode='exec')
    print(f"Result10 Success: {result10['success']}")
    print(f"Result10 Output:\n{result10['output']}")
    if result10['error_message']: print(f"Result10 Error from engine: {result10['error_message']}")
    print(f"Debugger data_store after Test 10: {my_debugger_instance.data_store}")

    print("\n--- Test 11: Class and Object Definition/Usage (mode='exec') ---")
    script11 = """
print("Defining a simple class 'MyItem'...")

class MyItem:
    class_attribute = "This is a class attribute"

    def __init__(self, name, value):
        print(f"MyItem constructor called for {name}")
        self.name = name 
        self.value = value 

    def get_description(self):
        return f"Item '{self.name}' has value {self.value}."

    def update_value(self, new_value):
        print(f"Updating value of '{self.name}' from {self.value} to {new_value}")
        self.value = new_value
        return self.value

    @classmethod
    def get_class_attr(cls): # @classmethod should be found now
        return cls.class_attribute

    @staticmethod
    def static_helper(): # @staticmethod should be found now
        return "This is a static helper method."

print(f"Accessing class attribute directly: {MyItem.class_attribute}")
print(f"Calling class method: {MyItem.get_class_attr()}")
print(f"Calling static method: {MyItem.static_helper()}")

print("\\nCreating an instance of MyItem...")
item1 = MyItem("Apple", 10)
print(item1.get_description())

print("\\nUpdating item1's value...")
item1.update_value(15)
print(item1.get_description())

write_data("item1_name", item1.name)
write_data("item1_value", item1.value)
"""
    result11 = script_engine.execute(script11, mode='exec')
    print(f"Result11 Success: {result11['success']}")
    print(f"Result11 Output:\n{result11['output']}")
    if result11['error_message']: print(f"Result11 Error from engine: {result11['error_message']}")
    print(f"Debugger data_store after Test 11: {my_debugger_instance.data_store}")

    # --- Test 12: Script using threading (mode='exec') ---
    print("\n--- Test 12: Script using threading (mode='exec') ---")
    script12 = """
import threading # Should be allowed now
import time 

print("Main script: Preparing to start threads.")

# Using a list to collect messages from threads (for demonstration)
# In a real scenario with complex shared data, use threading.Lock for access
thread_messages = [""] * 2 # Adjusted for 2 threads

def worker(thread_id, delay):
    global thread_messages # To modify the list in the outer scope
    print(f"Thread {thread_id}: starting, will sleep for {delay}s.")
    time.sleep(delay) 
    message = f"Thread {thread_id}: finished work after {delay}s."
    print(message)
    # For this test, direct assignment is okay as each thread writes to a unique index.
    # If multiple threads could write to the same index or append, a lock would be essential.
    if thread_id < len(thread_messages):
      thread_messages[thread_id] = message

threads = []
t1 = threading.Thread(target=worker, args=(0, 0.2)) # Thread 0
threads.append(t1)
t2 = threading.Thread(target=worker, args=(1, 0.1)) # Thread 1
threads.append(t2)

print("Main script: Starting thread 0.")
t1.start()
print("Main script: Starting thread 1.")
t2.start()

print("Main script: All threads started. Waiting for them to join.")
for i, t in enumerate(threads):
    t.join() 
    print(f"Main script: Thread {i} has joined.")

print("Main script: All threads completed.")
print(f"Collected messages: {thread_messages}")
# Example of calling a (presumably now thread-safe) host function
write_data("threading_test_completed", True) 
write_data("thread_messages", " | ".join(thread_messages))
"""
    result12 = script_engine.execute(script12, mode='exec')
    print(f"Result12 Success: {result12['success']}")
    print(f"Result12 Output:\n{result12['output']}")
    if result12['error_message']: print(f"Result12 Error from engine: {result12['error_message']}")
    print(f"Debugger data_store after Test 12: {my_debugger_instance.data_store}")

    print("\n--- Execution History (Final) ---")
    for i, entry in enumerate(script_engine.execution_history):
        print(
            f"{i + 1}. [{entry['timestamp']}] Success: {entry['success']}, Script: '{entry['script_snippet']}', Error: {entry['error']}")

    print("\n--- Execution Stats (Final) ---")
    stats = script_engine.get_stats()
    for k, v in stats.items(): print(f"{k}: {v}")
