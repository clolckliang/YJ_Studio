import json
import struct
from datetime import datetime
from typing import Optional, Dict, Any, List  # Added List for type hinting

from PySide6.QtCore import QThread, Signal, QMutex, QByteArray, QTimer, QObject  # Added QTimer


# from PySide6.QtWidgets import QMessageBox # Example import if scripts use UI

# Forward declaration for type hint if SerialDebugger is in another module
# class SerialDebugger: pass

class ProtocolManager:
    def __init__(self):
        self.protocols: Dict[str, Any] = {}  # Store protocol instances or factories

    def register_protocol(self, name: str, protocol_handler: Any):
        """
        Registers a new protocol handler.
        'protocol_handler' could be an instance of a protocol class or a factory function.
        """
        if name in self.protocols:
            # Handle overwrite or raise error, depending on desired behavior
            print(f"Warning: Protocol '{name}' is being overwritten.")
        self.protocols[name] = protocol_handler
        print(f"Protocol '{name}' registered.")

    def get_protocol(self, name: str) -> Optional[Any]:
        protocol = self.protocols.get(name)
        if protocol is None:
            print(f"Warning: Protocol '{name}' not found.")
        return protocol

    def unregister_protocol(self, name: str):
        """Unregisters a protocol."""
        if name in self.protocols:
            del self.protocols[name]
            print(f"Protocol '{name}' unregistered.")
        else:
            print(f"Warning: Protocol '{name}' not found for unregistration.")

    def list_protocols(self) -> List[str]:
        """Returns a list of registered protocol names."""
        return list(self.protocols.keys())


class ScriptEngine:
    def __init__(self, debugger_instance: Any):  # debugger_instance: 'SerialDebugger'
        self.debugger = debugger_instance
        self.available_modules = {
            'datetime': datetime,
            'struct': struct,
            'json': json,
            # Add other safe and useful modules here
            # For UI interactions from script (use with extreme caution):
            # 'QMessageBox': QMessageBox # Example, ensure debugger_instance provides a safe way to call this
        }
        # Provide access to some debugger methods safely if needed
        # e.g., self.debugger_api = {'send_data': self.debugger.some_safe_send_method}

    def execute(self, script_text: str):
        """
        Executes the provided script text.

        WARNING: Using 'exec' directly with arbitrary script text is a major security risk
        if the scripts can come from untrusted sources. The script will have access to
        the 'debugger' instance (SerialDebugger) and any global/local variables
        defined here. For production or publicly distributed applications,
        a sandboxed environment or a custom domain-specific language (DSL) is strongly recommended.
        """
        if not script_text.strip():
            if hasattr(self.debugger, 'error_logger') and self.debugger.error_logger:
                self.debugger.error_logger.log_warning("ScriptEngine: Attempted to execute an empty script.")
            else:
                print("ScriptEngine: Attempted to execute an empty script.")
            return

        local_scope = {
            'debugger': self.debugger,  # Provides access to the SerialDebugger instance
            'print': print,  # Allow basic printing from script
            **self.available_modules  # Make selected modules available
            # Add other functions or objects you want the script to access here
            # 'send_command': self.debugger.send_custom_protocol_data_action # Example unsafe direct access
        }
        global_scope = {}  # Scripts run with their own global scope for safety

        try:
            # Consider wrapping script_text in a function to better control its scope
            # compiled_script = compile(script_text, '<script>', 'exec')
            # exec(compiled_script, global_scope, local_scope)
            exec(script_text, global_scope, local_scope)

            if hasattr(self.debugger, 'error_logger') and self.debugger.error_logger:
                self.debugger.error_logger.log_info("ScriptEngine: Script executed successfully.")
            else:
                print("ScriptEngine: Script executed successfully.")

        except Exception as e:
            error_message = f"ScriptEngine: Error during script execution: {e}"
            if hasattr(self.debugger, 'error_logger') and self.debugger.error_logger:
                self.debugger.error_logger.log_error(error_message, "SCRIPT_ERROR")
            else:
                print(error_message)
            # Optionally, display error to user via a QMessageBox if debugger provides a safe way
            # if hasattr(self.debugger, 'show_message_box'):
            #     self.debugger.show_message_box("Script Error", error_message, "warning")


class CircularBuffer:
    def __init__(self, size: int):
        if size <= 0:
            raise ValueError("CircularBuffer size must be positive.")
        self.buffer = QByteArray()
        self.buffer.resize(size)  # Allocates and fills with '\0'
        self.max_size = size
        self.head = 0  # Index of the next writable position
        self.tail = 0  # Index of the next readable position
        self.count = 0  # Number of bytes currently in buffer
        self.mutex = QMutex()  # For thread-safe operations if accessed by multiple threads

    def write(self, data: QByteArray) -> int:
        """Writes data to the buffer. Returns number of bytes written."""
        if not data:
            return 0

        self.mutex.lock()
        try:
            data_len = data.size()
            bytes_to_write = 0

            for i in range(data_len):
                if self.count == self.max_size:  # Buffer is full
                    self.tail = (self.tail + 1) % self.max_size
                    self.count -= 1

                # 使用replace方法修改单个字节
                byte_to_write = bytes([data.at(i)])  # 获取单个字节
                self.buffer.replace(self.head, 1, byte_to_write)
                self.head = (self.head + 1) % self.max_size
                self.count += 1
                bytes_to_write += 1

            return bytes_to_write
        finally:
            self.mutex.unlock()

    def read(self, length: int) -> QByteArray:
        """Reads up to 'length' bytes from the buffer. Consumes the data."""
        if length <= 0 or self.count == 0:
            return QByteArray()

        self.mutex.lock()
        try:
            bytes_to_read = min(length, self.count)
            result = QByteArray()

            for _ in range(bytes_to_read):
                result.append(self.buffer.at(self.tail))  # 使用at方法获取单个字节
                self.tail = (self.tail + 1) % self.max_size
                self.count -= 1

            return result
        finally:
            self.mutex.unlock()

    def peek(self, length: int) -> QByteArray:
        """Peeks up to 'length' bytes from the buffer without consuming."""
        if length <= 0 or self.count == 0:
            return QByteArray()

        self.mutex.lock()
        try:
            bytes_to_peek = min(length, self.count)
            result = QByteArray()
            result.reserve(bytes_to_peek)

            current_tail = self.tail
            for _ in range(bytes_to_peek):
                # 修复：使用at()方法获取字节并转换为bytes格式
                result.append(bytes([self.buffer.at(current_tail)]))
                current_tail = (current_tail + 1) % self.max_size

            return result
        finally:
            self.mutex.unlock()

    def discard(self, length: int) -> int:
        """Discards up to 'length' bytes from the read end. Returns number of bytes discarded."""
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
        """Clears the buffer."""
        self.mutex.lock()
        try:
            self.head = 0
            self.tail = 0
            self.count = 0
        finally:
            self.mutex.unlock()

    def get_count(self) -> int:
        """Returns the number of bytes currently in the buffer."""
        self.mutex.lock()
        try:
            return self.count
        finally:
            self.mutex.unlock()

    def get_free_space(self) -> int:
        """Returns the number of free bytes in the buffer."""
        self.mutex.lock()
        try:
            return self.max_size - self.count
        finally:
            self.mutex.unlock()

    def is_empty(self) -> bool:
        return self.get_count() == 0

    def is_full(self) -> bool:
        return self.get_count() == self.max_size


class DataProcessor(QThread):
    processed_data_signal = Signal(QByteArray)  # Example: emits processed data
    processing_error_signal = Signal(str)  # Example: emits error messages

    def __init__(self, parent: Optional[QObject] = None):  # Added parent for QObject
        super().__init__(parent)
        # Using collections.deque is generally better for thread-safe pop(0) operations
        # from collections import deque
        # self.queue = deque()
        self.queue: List[QByteArray] = []  # Sticking to list as per original placeholder
        self.mutex = QMutex()
        self._running = False
        self._timer: Optional[QTimer] = None  # For event-driven processing instead of msleep

    def add_data(self, data: QByteArray):
        self.mutex.lock()
        try:
            self.queue.append(data)
        finally:
            self.mutex.unlock()
        # If using an event-driven approach in run(), you might trigger processing here
        # For example, if run() waits on a QWaitCondition, signal it here.

    def run(self):
        """
        Main processing loop for the thread.
        This implementation uses polling with msleep. For more advanced scenarios,
        consider using QWaitCondition for a more event-driven approach if data
        arrival is infrequent, or process all available data in each wake-up.
        """
        self._running = True
        print("DataProcessor thread started.")
        while self._running:
            had_data = False  # Track if we processed any data in this iteration

            while True:  # Inner loop to process all queued data
                data_to_process = None
                self.mutex.lock()
                try:
                    if self.queue:
                        data_to_process = self.queue.pop(0)  # FIFO
                    else:
                        break  # No more data in queue
                finally:
                    self.mutex.unlock()

                # Process the data if valid
                if data_to_process and data_to_process.size() > 0:  # Combined validity check
                    try:
                        processed_result = QByteArray(data_to_process)  # Make a copy
                        self.processed_data_signal.emit(processed_result)
                        had_data = True
                    except Exception as e:
                        error_msg = f"DataProcessor: Error processing data: {e}"
                        print(error_msg)
                        self.processing_error_signal.emit(error_msg)
                elif data_to_process:  # Only print if data exists but is empty
                    print("DataProcessor: Received empty data, skipping")

            # Only sleep if no data was processed in this iteration
            if not had_data:
                self.msleep(20)  # Sleep for a short duration (e.g., 20ms)

        print("DataProcessor thread stopped.")

    def stop(self):
        print("DataProcessor: Stop requested.")
        self._running = False
        # self.wait() # QThread.wait() can block. Ensure the run loop exits promptly.
        # If run loop depends on external events or long sleeps,
        # a more robust shutdown (e.g. with QWaitCondition.wakeAll()) might be needed.
        # For this simple polling loop, setting _running to False and a short wait should be okay.
        if self.isRunning():
            if not self.wait(1000):  # Wait for max 1 second
                print("DataProcessor: Thread did not finish in time, terminating.")
                self.terminate()  # Force terminate if wait times out
                self.wait()  # Wait again after terminate