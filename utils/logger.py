import logging
from pathlib import Path
from datetime import datetime
from utils.constants import Constants

class ErrorLogger:
    def __init__(self, log_file_prefix: str = Constants.LOG_FILE_PREFIX):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_filename = log_dir / f'{log_file_prefix}{datetime.now().strftime("%Y%m%d")}.log'
        logging.basicConfig(filename=log_filename, level=logging.INFO,
                            format='%(asctime)s-%(levelname)s-%(module)s-%(funcName)s-%(message)s', encoding='utf-8')
        self.logger = logging.getLogger("SerialDebuggerApp_v5") # Or a more generic name

    def log_error(self, error_msg: str, error_type: str = "GENERAL", exc_info: bool = False) -> None:
        self.logger.error(f"[{error_type}] {error_msg}", exc_info=exc_info) # 错误日志记录

    def log_info(self, info_msg: str, info_type: str = "INFO", exc_info: bool = False) -> None:
        self.logger.info(f"[{info_type}] {info_msg}", exc_info=exc_info) # 信息日志记录

    def log_debug(self, debug_msg: str, debug_type: str = "DEBUG", exc_info: bool = False) -> None:
        self.logger.debug(f"[{debug_type}] {debug_msg}", exc_info=exc_info) # 调试日志记录



    def log_warning(self, warn_msg: str, warn_type: str = "WARNING", exc_info: bool = False) -> None:
        self.logger.warning(f"[{warn_type}] {warn_msg}", exc_info=exc_info) # 警告日志记录


