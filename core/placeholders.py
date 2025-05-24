from datetime import datetime
from typing import Optional, Any, List, Dict, Callable, Tuple
from contextlib import contextmanager
import datetime
import struct
import json
import time
import math
import re
import sys
import traceback
import threading
import signal

from PySide6.QtCore import QThread, Signal, QMutex, QByteArray, QTimer, QObject


class ProtocolManager:
    """管理协议处理器的注册和获取"""

    def __init__(self):
        self.protocols: Dict[str, Any] = {}
        self._mutex = QMutex()  # 添加线程安全

    def register_protocol(self, name: str, protocol_handler: Any):
        """
        注册新的协议处理器
        Args:
            name: 协议名称
            protocol_handler: 协议处理实例或工厂函数
        """
        self._mutex.lock()
        try:
            if name in self.protocols:
                print(f"Warning: Protocol '{name}' is being overwritten.")
            self.protocols[name] = protocol_handler
            print(f"Protocol '{name}' registered successfully.")
        finally:
            self._mutex.unlock()

    def get_protocol(self, name: str) -> Optional[Any]:
        """获取协议处理器"""
        self._mutex.lock()
        try:
            protocol = self.protocols.get(name)
            if protocol is None:
                print(f"Warning: Protocol '{name}' not found.")
            return protocol
        finally:
            self._mutex.unlock()

    def unregister_protocol(self, name: str) -> bool:
        """
        注销协议
        Returns:
            bool: 成功返回True，协议不存在返回False
        """
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
        """返回已注册协议名称列表"""
        self._mutex.lock()
        try:
            return list(self.protocols.keys())
        finally:
            self._mutex.unlock()

    def clear_protocols(self):
        """清除所有协议"""
        self._mutex.lock()
        try:
            self.protocols.clear()
            print("All protocols cleared.")
        finally:
            self._mutex.unlock()


class CircularBuffer:
    """线程安全的循环缓冲区实现"""

    def __init__(self, size: int):
        if size <= 0:
            raise ValueError("CircularBuffer size must be positive.")

        self.buffer = QByteArray()
        self.buffer.resize(size)
        self.max_size = size
        self.head = 0  # 下一个写入位置
        self.tail = 0  # 下一个读取位置
        self.count = 0  # 当前缓冲区中的字节数
        self.mutex = QMutex()

    def write(self, data: QByteArray) -> int:
        """
        写入数据到缓冲区
        Returns:
            int: 实际写入的字节数
        """
        if not data or data.size() == 0:
            return 0

        self.mutex.lock()
        try:
            data_len = data.size()
            bytes_written = 0

            for i in range(data_len):
                # 如果缓冲区满了，覆盖最旧的数据
                if self.count == self.max_size:
                    self.tail = (self.tail + 1) % self.max_size
                    self.count -= 1

                # 写入单个字节
                byte_value = data.at(i)
                if isinstance(byte_value, int):
                    byte_data = bytes([byte_value])
                else:
                    byte_data = bytes([ord(byte_value)] if isinstance(byte_value, str) else [byte_value])

                self.buffer.replace(self.head, 1, byte_data)
                self.head = (self.head + 1) % self.max_size
                self.count += 1
                bytes_written += 1

            return bytes_written
        finally:
            self.mutex.unlock()

    def read(self, length: int) -> QByteArray:
        """
        从缓冲区读取数据并消费
        Args:
            length: 要读取的字节数
        Returns:
            QByteArray: 读取的数据
        """
        if length <= 0 or self.count == 0:
            return QByteArray()

        self.mutex.lock()
        try:
            bytes_to_read = min(length, self.count)
            result = QByteArray()
            result.reserve(bytes_to_read)

            for _ in range(bytes_to_read):
                byte_value = self.buffer.at(self.tail)
                result.append(byte_value)
                self.tail = (self.tail + 1) % self.max_size
                self.count -= 1

            return result
        finally:
            self.mutex.unlock()

    def peek(self, length: int) -> QByteArray:
        """预览数据而不消费"""
        if length <= 0 or self.count == 0:
            return QByteArray()

        self.mutex.lock()
        try:
            bytes_to_peek = min(length, self.count)
            result = QByteArray()
            result.reserve(bytes_to_peek)

            current_tail = self.tail
            for _ in range(bytes_to_peek):
                byte_value = self.buffer.at(current_tail)
                result.append(byte_value)
                current_tail = (current_tail + 1) % self.max_size

            return result
        finally:
            self.mutex.unlock()

    def discard(self, length: int) -> int:
        """丢弃指定数量的字节"""
        if length <= 0 or self.count == 0:
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
        """获取当前缓冲区中的字节数"""
        self.mutex.lock()
        try:
            return self.count
        finally:
            self.mutex.unlock()

    def get_free_space(self) -> int:
        """获取可用空间"""
        self.mutex.lock()
        try:
            return self.max_size - self.count
        finally:
            self.mutex.unlock()

    def is_empty(self) -> bool:
        """检查缓冲区是否为空"""
        return self.get_count() == 0

    def is_full(self) -> bool:
        """检查缓冲区是否已满"""
        return self.get_count() == self.max_size

    def get_utilization(self) -> float:
        """获取缓冲区使用率 (0.0 - 1.0)"""
        return self.get_count() / self.max_size


class DataProcessor(QThread):
    """数据处理线程类"""

    processed_data_signal = Signal(str, QByteArray)  # Emits (original_func_id, processed_payload)
    processing_error_signal = Signal(str)  # Emits error messages
    processing_stats_signal = Signal(dict)  # Emits processing statistics

    def __init__(self, parent: Optional[QObject] = None, batch_size: int = 5):  # Smaller batch for responsiveness
        super().__init__(parent)
        # from collections import deque # Using deque is more efficient for pop(0)
        # self.queue: deque[Tuple[str, QByteArray]] = deque() # func_id, payload
        self.queue: List[Tuple[str, QByteArray]] = []  # (func_id, payload)
        self.mutex = QMutex()
        self._running = False
        self._batch_size = batch_size  # How many items to process before a small sleep or stats update
        self._stats = {
            'processed_count': 0,
            'error_count': 0,
            'start_time': None,
            'last_activity': None,
            'queue_size_history': []  # Optional: for monitoring queue buildup
        }
        self.MAX_QUEUE_HISTORY = 100

    def add_data(self, func_id: str, data: QByteArray):
        """添加数据 (功能码和负载) 到处理队列"""
        if not data or data.size() == 0:
            return

        self.mutex.lock()
        try:
            self.queue.append((func_id, data))  # Store as a tuple
            self._stats['last_activity'] = datetime.datetime.now()
            if len(self._stats['queue_size_history']) > self.MAX_QUEUE_HISTORY:
                self._stats['queue_size_history'].pop(0)
            self.stats['queue_size_history'].append(len(self.queue))
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
            stats_copy['uptime_seconds'] = (datetime.datetime.now() - stats_copy['start_time']).total_seconds()
        stats_copy['current_queue_size'] = self.get_queue_size()
        return stats_copy

    def run(self):
        self._running = True
        self._stats['start_time'] = datetime.datetime.now()
        if hasattr(self, 'main_window_ref') and self.main_window_ref.error_logger:  # Check if logger accessible
            self.main_window_ref.error_logger.log_info("DataProcessor thread started.")
        else:
            print("DataProcessor thread started.")

        try:
            while self._running:
                processed_in_this_cycle = 0

                for _ in range(self._batch_size):  # Process a batch of items
                    item_to_process = None
                    self.mutex.lock()
                    try:
                        if self.queue:
                            item_to_process = self.queue.pop(0)  # FIFO
                        else:
                            # Queue is empty, break from batch processing
                            self.mutex.unlock()
                            break
                    finally:
                        # Ensure mutex is unlocked if break happens or if queue was empty initially
                        if self.mutex.tryLock():  # Check if it was locked by this path
                            self.mutex.unlock()

                    if item_to_process:
                        func_id, data_payload = item_to_process
                        try:
                            # --- ACTUAL DATA PROCESSING LOGIC GOES HERE ---
                            # This is where you'd put your computationally intensive task.
                            # For this example, let's just log it and emit the original data.
                            # You could, for example, perform complex calculations,
                            # write to a database, make a network request (non-blocking if possible), etc.

                            # Example: Simulate some work and create a "result"
                            # QThread.msleep(5) # Simulate work
                            processed_result_payload = QByteArray(data_payload)  # Make a copy or transform
                            # processed_result_payload.append(" [Processed]".encode())

                            self.processed_data_signal.emit(func_id, processed_result_payload)
                            self._stats['processed_count'] += 1
                            processed_in_this_cycle += 1
                        except Exception as e:
                            error_msg = f"DataProcessor: Error during _process_single_data for FID {func_id}: {e}"
                            self.processing_error_signal.emit(error_msg)
                            self._stats['error_count'] += 1

                if processed_in_this_cycle > 0:
                    self._stats['last_activity'] = datetime.datetime.now()
                    # Optionally emit stats less frequently
                    if self._stats['processed_count'] % 10 == 0:  # Emit stats every 10 items
                        self.processing_stats_signal.emit(self.get_stats())

                if processed_in_this_cycle == 0:  # No data was processed from queue
                    self.msleep(50)  # Sleep longer if queue was empty
                else:
                    self.msleep(10)  # Shorter sleep if data was processed, to stay responsive

        except Exception as e:  # Catch any unexpected error in the run loop itself
            fatal_error_msg = f"DataProcessor thread encountered a fatal error: {e}"
            self.processing_error_signal.emit(fatal_error_msg)
            if hasattr(self, 'main_window_ref') and self.main_window_ref.error_logger:
                self.main_window_ref.error_logger.log_error(fatal_error_msg, "DATA_PROCESSOR_FATAL")
            else:
                print(fatal_error_msg)
        finally:
            final_stats = self.get_stats()
            self.processing_stats_signal.emit(final_stats)  # Emit final stats
            log_msg = f"DataProcessor thread stopped. Processed: {final_stats.get('processed_count', 0)}, Errors: {final_stats.get('error_count', 0)}."
            if hasattr(self, 'main_window_ref') and self.main_window_ref.error_logger:
                self.main_window_ref.error_logger.log_info(log_msg)
            else:
                print(log_msg)

    def stop(self):
        if hasattr(self, 'main_window_ref') and self.main_window_ref.error_logger:
            self.main_window_ref.error_logger.log_info("DataProcessor: Stop requested.")
        else:
            print("DataProcessor: Stop requested.")
        self._running = False
        # Don't call self.wait() from within the thread's own methods if called by main thread.
        # SerialDebugger will call self.wait() on the thread instance.

# 脚本引擎相关异常类
class ScriptExecutionTimeout(Exception):
    """脚本执行超时异常"""
    pass


class ScriptSecurityError(Exception):
    """脚本安全违规异常"""
    pass


class RestrictedImport:
    """受限制的导入处理器"""

    ALLOWED_MODULES = {
        'datetime', 'struct', 'json', 'time', 'math', 're',
        'random', 'itertools', 'collections', 'functools',
        'decimal', 'fractions', 'statistics'
    }

    def __init__(self, original_import):
        self.original_import = original_import

    def __call__(self, name, *args, **kwargs):
        # 允许子模块导入
        base_module = name.split('.')[0]
        if base_module not in self.ALLOWED_MODULES:
            raise ScriptSecurityError(f"Import of module '{name}' is not allowed")
        return self.original_import(name, *args, **kwargs)


class SafeBuiltins:
    """提供安全的内置函数集合"""

    SAFE_BUILTINS = {
        'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'dir', 'divmod',
        'enumerate', 'filter', 'float', 'format', 'frozenset', 'getattr',
        'hasattr', 'hash', 'hex', 'int', 'isinstance', 'issubclass', 'iter',
        'len', 'list', 'map', 'max', 'min', 'oct', 'ord', 'pow', 'print',
        'range', 'repr', 'reversed', 'round', 'set', 'sorted', 'str', 'sum',
        'tuple', 'type', 'zip', 'vars'
    }

    @classmethod
    def get_safe_builtins(cls):
        """返回安全内置函数字典"""
        import builtins
        safe_builtins = {}
        for name in cls.SAFE_BUILTINS:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)
        return safe_builtins


class ScriptEngine:
    """增强的脚本执行引擎"""

    def __init__(self, debugger_instance: Any, config: Optional[Dict] = None):
        """
        初始化脚本引擎
        Args:
            debugger_instance: 调试器实例
            config: 配置字典
        """
        self.debugger = debugger_instance
        self.config = config if config is not None else {}  # 确保 config 是字典

        # 执行设置
        self.timeout = self.config.get('timeout', 30)
        self.max_iterations = self.config.get('max_iterations', 1000000)  # 当前未直接使用，但可保留
        self.enable_debugging = self.config.get('enable_debugging', True)

        # 输出限制 (这些是在我之前的建议中添加的，确保它们在这里)
        self.max_total_output_length = self.config.get('max_output_length', 10000)  # 旧称 max_output_length
        self.max_line_length = self.config.get('max_line_length', 1000)

        self._script_output_buffer: List[str] = []  # 新增：用于捕获脚本的print输出

        # 可用模块 (与您提供的版本一致)
        self.available_modules = {
            'datetime': datetime,  # 确保 datetime 已导入
            'struct': struct,  # 确保 struct 已导入
            'json': json,  # 确保 json 已导入
            'time': time,  # 确保 time 已导入
            'math': math,  # 确保 math 已导入
            're': re,  # 确保 re 已导入
        }
        if 'additional_modules' in self.config:
            self.available_modules.update(self.config['additional_modules'])

        # 执行历史 (与您提供的版本一致)
        self.execution_history: List[Dict] = []
        self.max_history = self.config.get('max_history', 100)

        # 线程安全 (与您提供的版本一致)
        self._execution_lock = threading.Lock()  # 确保 threading 已导入

        # 钩子函数 (与您提供的版本一致)
        self.pre_execution_hooks: List[Callable] = []  # 确保 Callable 已从 typing 导入
        self.post_execution_hooks: List[Callable] = []

        # 统计信息 (与您提供的版本一致)
        self._stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_execution_time': 0.0
        }

    # ... (add_module, remove_module, add_pre_execution_hook, add_post_execution_hook, _timeout_context, _create_safe_environment 保持不变) ...
    # ... (_log_message, _add_to_history, validate_script 保持不变) ...

    def _create_safe_environment(self) -> tuple:  # 与您提供的版本一致
        """创建安全的执行环境"""
        safe_builtins = SafeBuiltins.get_safe_builtins()
        if '__builtins__' in globals() and hasattr(__builtins__, '__import__'):
            original_import = __builtins__.__import__
        else:
            import builtins  # Python 3
            original_import = builtins.__import__
        safe_builtins['__import__'] = RestrictedImport(original_import)
        local_scope = {
            'debugger': self.debugger,
            'print': self._safe_print,  # 关键：使用我们自定义的 _safe_print
            **self.available_modules,
            'sleep': time.sleep,  # 确保 time 已导入
            'now': datetime.datetime.now,  # 确保 datetime 已导入
        }
        global_scope = {
            '__builtins__': safe_builtins,
            '__name__': '__script__',
        }
        return global_scope, local_scope

    def _safe_print(self, *args, **kwargs):
        """
        安全的打印函数，捕获输出到缓冲区，并可选地记录到日志。
        """
        try:
            message = ' '.join(str(arg) for arg in args)  # kwargs 在 print 中通常是 sep, end, file, flush

            # 考虑 kwargs 中的 end 和 sep (尽管脚本中的简单 print 可能不会用复杂kwargs)
            # end = kwargs.get('end', '\n')
            # sep = kwargs.get('sep', ' ')
            # message = sep.join(str(arg) for arg in args) + end # 更精确的模拟

            if len(message) > self.max_line_length:
                message = message[:self.max_line_length] + "... [行已截断]"

            current_buffer_len = sum(len(s) + 1 for s in self._script_output_buffer)  # +1 for newline
            if current_buffer_len + len(message) < self.max_total_output_length:
                self._script_output_buffer.append(message)
            elif not self._script_output_buffer or not self._script_output_buffer[-1].endswith("... [总输出已截断]"):
                self._script_output_buffer.append("... [总输出已截断]")

            # 仍然可以记录到应用的日志以供调试，但主要输出通过缓冲区返回
            if hasattr(self.debugger, 'error_logger') and self.debugger.error_logger:
                # 避免重复记录或选择性记录
                # self.debugger.error_logger.log_info(f"Script Printed: {message}", "SCRIPT_PRINT")
                pass  # 主要通过返回的 output 字段在UI显示
            else:
                print(f"[SCRIPT (via _safe_print)] {message}")  # 控制台回显（如果需要）
        except Exception as e:
            self._script_output_buffer.append(f"[Print Error: {e}]")

    def validate_script(self, script_text: str) -> Tuple[bool, Optional[str]]:
        """验证脚本安全性
        Args:
            script_text: 要验证的脚本代码
        Returns:
            Tuple[是否有效, 错误信息(如果有)]
        """
        if not script_text or not script_text.strip():
            return False, "Empty script"

        # 检查禁止的关键字
        banned_keywords = {
            'import', 'eval', 'exec', 'open', 'os.', 'sys.',
            'subprocess', '__import__', 'compile', 'globals'
        }
        for keyword in banned_keywords:
            if keyword in script_text:
                return False, f"Script contains banned keyword: {keyword}"

        return True, None

    def _log_message(self, level: str, message: str, category: Optional[str] = None):
        """内部日志记录方法
        Args:
            level: 日志级别 (info/warning/error)
            message: 日志消息
            category: 可选分类标签
        """
        log_msg = f"[ScriptEngine] {message}"
        if category:
            log_msg = f"[{category}] {log_msg}"

        if hasattr(self.debugger, 'error_logger') and self.debugger.error_logger:
            getattr(self.debugger.error_logger, f'log_{level}')(log_msg)
        else:
            print(f"[{level.upper()}] {log_msg}")

    @contextmanager
    def _timeout_context(self, timeout):
        """超时控制上下文管理器"""
        if timeout <= 0:
            yield  # 无超时限制
            return

        def signal_handler(signum, frame):
            raise ScriptExecutionTimeout(f"Execution timed out after {timeout} seconds")

        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(timeout)
        try:
            yield
        finally:
            signal.alarm(0)  # 取消超时
    def _add_to_history(self, script_text: str, success: bool, result: Optional[str] = None, error: Optional[str] = None):
        """添加执行记录到历史"""
        entry = {
            'script': script_text[:500] + '...' if len(script_text) > 500 else script_text,
            'timestamp': datetime.datetime.now(),
            'success': success,
            'result': result,
            'error': error
        }
        self.execution_history.append(entry)
        if len(self.execution_history) > self.max_history:
            self.execution_history.pop(0)



    def add_pre_execution_hook(self, hook: Callable):
        """添加预执行钩子函数"""
        if hook not in self.pre_execution_hooks:
            self.pre_execution_hooks.append(hook)

    def add_post_execution_hook(self, hook: Callable):
        """添加后执行钩子函数"""
        if hook not in self.post_execution_hooks:
            self.post_execution_hooks.append(hook)

    def execute(self, script_text: str, timeout: Optional[int] = None) -> Dict:
        """
        执行脚本文本
        Args:
            script_text: 要执行的脚本代码
            timeout: 执行超时时间（覆盖默认值）
        Returns:
            包含执行结果、输出和元数据的字典
        """
        self._script_output_buffer = []  # 为本次执行清空输出缓冲区
        execution_timeout = timeout if timeout is not None else self.timeout
        start_time = datetime.datetime.now()  # 确保 datetime 已导入

        self._stats['total_executions'] += 1
        final_result: Dict[str, Any] = {}  # 初始化

        with self._execution_lock:
            is_valid, error_msg_validation = self.validate_script(script_text)
            if not is_valid:
                self._log_message('error', f"Script validation failed: {error_msg_validation}")
                final_result = {'success': False, 'output': "\n".join(self._script_output_buffer),
                                'error': error_msg_validation, 'execution_time': 0, 'timestamp': start_time}
                self._add_to_history(script_text, False, error=error_msg_validation)
                self._stats['failed_executions'] += 1
                return final_result

            try:
                for hook in self.pre_execution_hooks: hook(script_text)
            except Exception as e:
                self._log_message('warning', f"Pre-execution hook failed: {e}")

            global_scope, local_scope = self._create_safe_environment()
            execution_error = None

            try:
                if sys.platform != 'win32':  # 确保 sys 已导入
                    with self._timeout_context(execution_timeout):  # 确保 contextmanager 已导入
                        exec(script_text, global_scope, local_scope)
                else:
                    result_container = {'exception': None, 'completed': False}

                    def execute_script_thread_target():
                        try:
                            exec(script_text, global_scope, local_scope)
                            result_container['completed'] = True
                        except Exception as e_thread:
                            result_container['exception'] = e_thread

                    thread = threading.Thread(target=execute_script_thread_target);
                    thread.daemon = True  # 确保 threading 已导入
                    thread.start();
                    thread.join(timeout=execution_timeout)
                    if thread.is_alive(): raise ScriptExecutionTimeout(
                        f"Script execution timed out after {execution_timeout} seconds")
                    if result_container['exception']: raise result_container['exception']
                    if not result_container['completed']: raise Exception(
                        "Script execution did not complete (Windows thread).")

                execution_time = (datetime.datetime.now() - start_time).total_seconds()
                self._log_message('info', f"Script executed successfully in {execution_time:.2f} seconds")
                final_result = {'success': True, 'output': "\n".join(self._script_output_buffer), 'error': None,
                                'execution_time': execution_time, 'timestamp': start_time}
                self._stats['successful_executions'] += 1;
                self._stats['total_execution_time'] += execution_time
                self._add_to_history(script_text, True, result=f"Executed in {execution_time:.2f}s")

            except ScriptExecutionTimeout as e_timeout:
                execution_error = str(e_timeout);
                self._log_message('error', execution_error, "SCRIPT_TIMEOUT");
                self._stats['failed_executions'] += 1
                final_result = {'success': False, 'output': "\n".join(self._script_output_buffer),
                                'error': execution_error, 'execution_time': execution_timeout, 'timestamp': start_time}
                self._add_to_history(script_text, False, error=execution_error)
            except ScriptSecurityError as e_security:
                execution_error = f"Security violation: {e_security}";
                self._log_message('error', execution_error, "SCRIPT_SECURITY");
                self._stats['failed_executions'] += 1
                final_result = {'success': False, 'output': "\n".join(self._script_output_buffer),
                                'error': execution_error,
                                'execution_time': (datetime.datetime.now() - start_time).total_seconds(),
                                'timestamp': start_time}
                self._add_to_history(script_text, False, error=execution_error)
            except Exception as e_general:
                execution_error = f"Script execution error: {e_general}"
                if self.enable_debugging: execution_error += f"\n{traceback.format_exc()}"  # 确保 traceback 已导入
                self._log_message('error', execution_error, "SCRIPT_ERROR");
                self._stats['failed_executions'] += 1
                final_result = {'success': False, 'output': "\n".join(self._script_output_buffer),
                                'error': execution_error,
                                'execution_time': (datetime.datetime.now() - start_time).total_seconds(),
                                'timestamp': start_time}
                self._add_to_history(script_text, False, error=execution_error)

            try:
                for hook in self.post_execution_hooks: hook(script_text, final_result)
            except Exception as e:
                self._log_message('warning', f"Post-execution hook failed: {e}")

            return final_result
def create_script_engine(debugger_instance, **kwargs):
    """工厂函数创建配置好的ScriptEngine
    
    Args:
        debugger_instance: 调试器实例
        **kwargs: 可选配置参数
            timeout: 执行超时时间(秒)
            max_iterations: 最大迭代次数 
            enable_debugging: 是否启用调试
            max_history: 最大历史记录数
            max_output_length: 最大输出长度
            additional_modules: 额外可用模块字典
            add_example_hooks: 是否添加示例钩子
    Returns:
        ScriptEngine: 配置好的脚本引擎实例
    """
    config = {
        'timeout': kwargs.get('timeout', 30),
        'max_iterations': kwargs.get('max_iterations', 1000000),
        'enable_debugging': kwargs.get('enable_debugging', True),
        'max_history': kwargs.get('max_history', 100),
        'max_output_length': kwargs.get('max_output_length', 10000),
        'additional_modules': kwargs.get('additional_modules', {}),
    }

    engine = ScriptEngine(debugger_instance, config)

    # 添加示例钩子
    if kwargs.get('add_example_hooks', False):
        engine.add_pre_execution_hook(
            lambda script: print(f"About to execute: {script[:50]}...")
        )
        engine.add_post_execution_hook(
            lambda script, result: print(f"Execution completed with status: {'Success' if result['success'] else 'Failed'}")
        )
    
    return engine
