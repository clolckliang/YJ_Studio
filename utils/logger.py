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

    def log_error(self, error_msg: str, error_type: str = "GENERAL") -> None:
        self.logger.error(f"[{error_type}] {error_msg}")

    def log_info(self, info_msg: str) -> None:
        self.logger.info(info_msg)

    def log_warning(self, warn_msg: str) -> None:
        self.logger.warning(warn_msg)