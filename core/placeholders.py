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
        self._stats['start_time'] = datetime.now()
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
                            processed_result_payload = QByteArray(data_payload)  # Make a copy or transform

                            self.processed_data_signal.emit(func_id, processed_result_payload)
                            self._stats['processed_count'] += 1
                            processed_in_this_cycle += 1
                        except Exception as e:
                            error_msg = f"DataProcessor: Error during _process_single_data for FID {func_id}: {e}"
                            self.processing_error_signal.emit(error_msg)
                            self._stats['error_count'] += 1

                if processed_in_this_cycle > 0:
                    self._stats['last_activity'] = datetime.now()
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


from datetime import datetime
from typing import Optional, Any, List, Dict, Callable, Tuple
from contextlib import contextmanager
import struct
import json
import time
import math
import re
import sys
import traceback
import threading
import signal
import ast  # For potential future advanced validation

# Assuming PySide6 is available as per the original imports.
# If not, QMutex might need a standard library alternative for broader use.
try:
    from PySide6.QtCore import QMutex
except ImportError:
    # Fallback if PySide6 is not available, for basic threading lock
    class QMutex:
        def __init__(self):
            self._lock = threading.Lock()

        def lock(self):
            self._lock.acquire()

        def unlock(self):
            self._lock.release()

        def tryLock(self, timeout: Optional[int] = None) -> bool:
            if timeout is None:
                return self._lock.acquire(blocking=False)
            elif timeout == 0:  # Qt's tryLock with 0 timeout
                return self._lock.acquire(blocking=False)
            else:  # Qt's tryLock with timeout in ms
                return self._lock.acquire(blocking=True, timeout=timeout / 1000.0)


# --- Script Engine Related Exception Classes ---
class ScriptExecutionTimeout(Exception):
    """脚本执行超时异常"""
    pass


class ScriptSecurityError(Exception):
    """脚本安全违规异常"""
    pass


class ScriptExecutionError(Exception):
    """脚本执行期间发生的一般错误"""
    pass


# --- Security and Environment Helpers ---
class RestrictedImport:
    """受限制的导入处理器"""
    ALLOWED_MODULES = {
        'datetime', 'struct', 'json', 'time', 'math', 're',
        'random', 'itertools', 'collections', 'functools',
        'decimal', 'fractions', 'statistics',
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
    def get_safe_builtins(cls) -> Dict[str, Callable]:
        import builtins
        safe_builtins_dict = {}
        for name in cls.SAFE_BUILTINS_NAMES:
            if hasattr(builtins, name):
                safe_builtins_dict[name] = getattr(builtins, name)

        if hasattr(builtins, '__import__'):
            safe_builtins_dict['__import__'] = RestrictedImport(getattr(builtins, '__import__'))
        else:
            try:
                original_import = __import__.__class__.__bases__[0].__import__  # type: ignore
                safe_builtins_dict['__import__'] = RestrictedImport(original_import)
            except Exception:
                pass

        return safe_builtins_dict


class ScriptEngine:
    """
    增强的脚本执行引擎，支持函数定义、调用、安全执行环境和与宿主应用的交互。
    使用统一的 `execute` 方法。
    """

    def __init__(self, debugger_instance: Optional[Any] = None, config: Optional[Dict] = None):
        self.debugger = debugger_instance
        self.config = config if config is not None else {}

        self.timeout: int = self.config.get('timeout', 30)  # seconds
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
        try:
            sep = kwargs.get('sep', ' ')
            end = kwargs.get('end', '\n')
            message_parts = [str(arg) for arg in args]
            message = sep.join(message_parts)

            if len(message) > self.max_line_length:
                message = message[:self.max_line_length] + "... [行已截断]"

            current_buffer_len = sum(len(s) + len(end) for s in self._script_output_buffer)
            if current_buffer_len + len(message) + len(end) < self.max_total_output_length:
                self._script_output_buffer.append(message)
            elif not self._script_output_buffer or not self._script_output_buffer[-1].endswith("... [总输出已截断]"):
                if self._script_output_buffer and current_buffer_len < self.max_total_output_length:
                    self._script_output_buffer.append("... [总输出已截断]")
                elif not self._script_output_buffer:
                    self._script_output_buffer.append("... [总输出已截断]")
        except Exception as e:
            err_msg = f"[Error during script print: {e}]"
            if sum(len(s) for s in self._script_output_buffer) + len(err_msg) < self.max_total_output_length:
                self._script_output_buffer.append(err_msg)

    def _create_safe_environment(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        safe_builtins_dict = SafeBuiltins.get_safe_builtins()
        safe_builtins_dict['print'] = self._safe_print

        global_scope = {'__builtins__': safe_builtins_dict}
        local_scope = {
            **self.available_modules, **self.host_functions,
            'sleep': time.sleep, 'now': datetime.now,
        }
        if self.debugger: local_scope['debugger'] = self.debugger
        return global_scope, local_scope

    @contextmanager
    def _timeout_context(self, seconds: int):
        if seconds <= 0 or not hasattr(signal, 'SIGALRM'):
            if seconds > 0 and not hasattr(signal, 'SIGALRM'):
                self._log_message('warning', "Timeout via signal.SIGALRM not supported. Timeout will not be enforced.")
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
        if self.debugger and hasattr(self.debugger, 'log_message'):
            self.debugger.log_message(level, message, category)

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
        error_str, error_type = None, None
        if error:
            success = False
            if isinstance(error, ScriptExecutionTimeout):
                error_str, error_type = f"TimeoutError: {error}", "TimeoutError"
            elif isinstance(error, ScriptSecurityError):
                error_str, error_type = f"SecurityError: {error}", "SecurityError"
            elif isinstance(error, SyntaxError):
                error_str, error_type = f"SyntaxError: {error.msg} (line {error.lineno}, offset {error.offset})\n{error.text}", "SyntaxError"
            else:
                error_str, error_type = f"ExecutionError: {type(error).__name__}: {error}\n{traceback.format_exc(limit=5)}", type(
                    error).__name__

        captured_output = "\n".join(self._script_output_buffer)
        self._stats['total_executions'] += 1
        self._stats['total_execution_time_seconds'] += execution_time_sec
        if success:
            self._stats['successful_executions'] += 1
        else:
            self._stats['failed_executions'] += 1

        result_dict = {
            "success": success, "return_value": return_value, "output": captured_output,
            "error_message": error_str, "error_type": error_type,
            "execution_time_seconds": round(execution_time_sec, 4),
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
            return False, f"SyntaxError: {e.msg} (line {e.lineno}, offset {e.offset})\nNear: {e.text}"
        except Exception as e:
            return False, f"Validation Error: {e}"

    # --- Internal Execution Logic Methods ---
    def _execute_statements_internal(self, script_text: str) -> Dict:
        start_time = time.perf_counter()
        is_valid_syntax, syntax_error_msg = self.validate_script_syntax(script_text)
        if not is_valid_syntax:
            exec_time = time.perf_counter() - start_time
            return self._prepare_execution_result(False, script_text, error=SyntaxError(syntax_error_msg),
                                                  execution_time_sec=exec_time)

        global_scope, local_scope = self._create_safe_environment()
        execution_error = None
        try:
            with self._timeout_context(self.timeout):
                compiled_code = compile(script_text, '<script_exec>', 'exec')
                exec(compiled_code, global_scope, local_scope)
        except Exception as e:
            execution_error = e
        exec_time = time.perf_counter() - start_time
        return self._prepare_execution_result(True if execution_error is None else False, script_text,
                                              error=execution_error, execution_time_sec=exec_time)

    def _evaluate_expression_internal(self, expression_text: str) -> Dict:
        start_time = time.perf_counter()
        is_valid_syntax, syntax_error_msg = self.validate_script_syntax(expression_text)
        if not is_valid_syntax:  # eval can also raise SyntaxError, this is a pre-check.
            exec_time = time.perf_counter() - start_time
            return self._prepare_execution_result(False, expression_text, error=SyntaxError(syntax_error_msg),
                                                  execution_time_sec=exec_time)

        global_scope, local_scope = self._create_safe_environment()
        return_val, execution_error = None, None
        try:
            with self._timeout_context(self.timeout):
                compiled_code = compile(expression_text, '<script_eval>', 'eval')
                return_val = eval(compiled_code, global_scope, local_scope)
        except Exception as e:
            execution_error = e
        exec_time = time.perf_counter() - start_time
        return self._prepare_execution_result(True if execution_error is None else False, expression_text,
                                              return_value=return_val, error=execution_error,
                                              execution_time_sec=exec_time)

    def _run_function_internal(self, script_text: str, function_name: str, args: Tuple, kwargs: Dict) -> Dict:
        start_time = time.perf_counter()
        full_context_script_text = f"{script_text}\n# Attempting to call: {function_name}"
        is_valid_syntax, syntax_error_msg = self.validate_script_syntax(script_text)
        if not is_valid_syntax:
            exec_time = time.perf_counter() - start_time
            return self._prepare_execution_result(False, full_context_script_text, error=SyntaxError(syntax_error_msg),
                                                  execution_time_sec=exec_time)

        global_scope, local_scope = self._create_safe_environment()
        return_val, execution_error = None, None
        try:
            with self._timeout_context(self.timeout):
                script_compiled_code = compile(script_text, '<script_defs>', 'exec')
                exec(script_compiled_code, global_scope, local_scope)
                if function_name not in local_scope: raise NameError(f"Function '{function_name}' not defined.")
                target_func = local_scope[function_name]
                if not callable(target_func): raise TypeError(f"'{function_name}' is not callable.")
                return_val = target_func(*args, **kwargs)
        except Exception as e:
            execution_error = e
        exec_time = time.perf_counter() - start_time
        return self._prepare_execution_result(True if execution_error is None else False, full_context_script_text,
                                              return_value=return_val, error=execution_error,
                                              execution_time_sec=exec_time)

    # --- Unified Public Execution Method ---
    def execute(self, script_text: str,
                mode: str = 'exec',
                function_name: Optional[str] = None,
                args: Optional[Tuple] = None,
                kwargs: Optional[Dict] = None) -> Dict:
        """
        Executes a script or evaluates an expression based on the specified mode.

        Args:
            script_text (str): The Python script or expression to execute.
            mode (str): Execution mode. One of 'exec', 'eval', 'run_function'.
                        Defaults to 'exec'.
            function_name (Optional[str]): Name of the function to call if mode is 'run_function'.
            args (Optional[Tuple]): Positional arguments for the function if mode is 'run_function'.
            kwargs (Optional[Dict]): Keyword arguments for the function if mode is 'run_function'.

        Returns:
            Dict: A dictionary containing execution results including success status,
                  output, return value (for 'eval' and 'run_function'), error details,
                  and execution time.
        """
        self._execution_lock.lock()
        try:
            self._script_output_buffer.clear()

            # Ensure args and kwargs are not None if mode is 'run_function'
            _args = args if args is not None else tuple()
            _kwargs = kwargs if kwargs is not None else {}

            # Pre-execution hooks (pass relevant info based on mode)
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
                    start_time = time.perf_counter()  # Minimal time for pre-check
                    exec_time = time.perf_counter() - start_time
                    return self._prepare_execution_result(False, script_text,
                                                          error=ValueError(
                                                              "function_name must be provided for 'run_function' mode."),
                                                          execution_time_sec=exec_time)
                return self._run_function_internal(script_text, function_name, _args, _kwargs)
            else:
                start_time = time.perf_counter()  # Minimal time for pre-check
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
            short_info = script_info[:150]
            clean_info = short_info.replace('\n', ' ')  # 先在变量中处理转义
            engine._log_message('info', f"Executing (info: {clean_info})...")

        def log_post_exec(result: Dict):
            status = "SUCCESS" if result['success'] else "FAILED"
            engine._log_message('info',
                              f"Execution {status}. Time: {result['execution_time_seconds']:.4f}s. Error: {result['error_message'] if result['error_message'] else 'None'}")

        engine.add_pre_execution_hook(log_pre_exec)
        engine.add_post_execution_hook(log_post_exec)
        engine._log_message('info', "Added example logging hooks to ScriptEngine.")
    return engine


# --- Example Usage (Illustrative) ---
if __name__ == '__main__':
    print("--- ScriptEngine Refactored Example Usage ---")


    class MyDebugger:
        def __init__(self): self.data_store, self.call_count = {"value": 100}, 0

        def get_host_value(self, key: str) -> Any: self.call_count += 1; return self.data_store.get(key, None)

        def set_host_value(self, key: str, value: Any):
            self.call_count += 1;
            self.data_store[key] = value;
            print(f"[MyDebugger] Set '{key}' to '{value}'")

        def log_message(self, level: str, message: str, category: Optional[str] = None):
            print(f"[DebuggerLOG-{level.upper()}-{category or 'APP'}] {message}")


    my_debugger_instance = MyDebugger()
    engine_config = {
        'timeout': 5,
        'initial_host_functions': {'read_data': my_debugger_instance.get_host_value,
                                   'write_data': my_debugger_instance.set_host_value},
        'add_example_logging_hooks': True
    }
    script_engine = create_script_engine(my_debugger_instance, **engine_config)

    print("\n--- Test 1: Execute Script (mode='exec') ---")
    script1 = """
print("Hello from script1!")
a = 10; b = 20; print(f"a + b = {a + b}")
def my_script_func(x, y): print(f"my_script_func called with {x}, {y}"); return x * y + read_data("value")
write_data("script_run_time", now().strftime("%Y-%m-%d %H:%M:%S"))
"""
    result1 = script_engine.execute(script1, mode='exec')  # Explicitly 'exec', or default
    # result1 = script_engine.execute(script1) # Also works, 'exec' is default
    print(f"Result1 Success: {result1['success']}\nResult1 Output:\n{result1['output']}")
    if result1['error_message']: print(f"Result1 Error: {result1['error_message']}")
    print(f"Debugger call count: {my_debugger_instance.call_count}, data_store: {my_debugger_instance.data_store}")

    print("\n--- Test 2: Evaluate Expression (mode='eval') ---")
    expr1 = "100 * 2 + read_data('value')"
    result2 = script_engine.execute(expr1, mode='eval')
    print(f"Result2 Success: {result2['success']}, Return Value: {result2['return_value']}")
    if result2['error_message']: print(f"Result2 Error: {result2['error_message']}")

    print("\n--- Test 3: Run Function in Script (mode='run_function') ---")
    script_with_func = """
def complex_calculation(a, b, factor=1):
    print(f"Performing complex_calculation with a={a}, b={b}, factor={factor}")
    intermediate = (a + b) * factor; host_val = read_data("value") 
    if host_val is None: host_val = 0
    print(f"Read host_val: {host_val}"); return intermediate + host_val
"""
    result3 = script_engine.execute(script_with_func, mode='run_function', function_name="complex_calculation",
                                    args=(5, 10), kwargs={'factor': 3})
    print(
        f"Result3 Success: {result3['success']}, Return Value: {result3['return_value']}\nResult3 Output:\n{result3['output']}")
    if result3['error_message']: print(f"Result3 Error: {result3['error_message']}")

    print("\n--- Test 4: Function Not Found (mode='run_function') ---")
    result4 = script_engine.execute(script_with_func, mode='run_function', function_name="non_existent_function")
    print(f"Result4 Success: {result4['success']}, Error: {result4['error_message']}")

    print("\n--- Test 5: Timeout (mode='exec') ---")
    script_timeout = "print('Starting long loop...'); import time; c = 0\nwhile True: c += 1; time.sleep(0.0001)"
    if hasattr(signal, 'SIGALRM'):
        result5 = script_engine.execute(script_timeout, mode='exec')
        print(
            f"Result5 Success: {result5['success']}, Error Type: {result5['error_type']}, Error: {result5['error_message']}")
    else:
        print("Skipping timeout test as signal.SIGALRM is not available.")

    print("\n--- Test 6: Disallowed Import (mode='exec') ---")
    result6 = script_engine.execute("import os; print(os.getcwd())", mode='exec')
    print(
        f"Result6 Success: {result6['success']}, Error Type: {result6['error_type']}, Error: {result6['error_message']}")

    print("\n--- Test 7: Syntax Error (mode='exec') ---")
    result7 = script_engine.execute("print('Hello'", mode='exec')  # Syntax error
    print(
        f"Result7 Success: {result7['success']}, Error Type: {result7['error_type']}, Error: {result7['error_message']}")

    print("\n--- Test 8: Invalid Mode ---")
    result8 = script_engine.execute("print('test')", mode='invalid_mode')
    print(
        f"Result8 Success: {result8['success']}, Error Type: {result8['error_type']}, Error: {result8['error_message']}")

    print("\n--- Execution History ---")
    for i, entry in enumerate(script_engine.execution_history):
        print(
            f"{i + 1}. [{entry['timestamp']}] Success: {entry['success']}, Script: '{entry['script_snippet']}', Error: {entry['error']}")
    print("\n--- Execution Stats ---");
    stats = script_engine.get_stats()
    for k, v in stats.items(): print(f"{k}: {v}")

