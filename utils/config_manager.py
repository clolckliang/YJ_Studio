import json
from pathlib import Path
from typing import Optional, Dict, Any

from utils.constants import Constants,ChecksumMode
from utils.data_models import SerialPortConfig, FrameConfig
from utils.logger import ErrorLogger

class ConfigManager:
    def __init__(self, filename: str = Constants.CONFIG_FILE_NAME, error_logger: Optional[ErrorLogger] = None):
        self.config_file = Path(filename)
        self.error_logger = error_logger
        self.default_config: Dict[str, Any] = {
            "serial_port": vars(SerialPortConfig()),
            "frame_definition": vars(FrameConfig()),
            "ui_theme_info": {"type": "internal", "name": "light", "path": None}, # Updated from ui_theme
            "receive_containers": [],
            "send_containers": [],
            "parse_func_id": "C1",
            "data_mapping_mode": "顺序填充 (Sequential)",
            "window_geometry": None,
            "window_state": None,
            "checksum_mode": Constants.DEFAULT_CHECKSUM_MODE.name,
            "plot_configs": []
        }

    def load_config(self) -> Dict[str, Any]:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge with defaults to ensure all keys are present
                for key, value in self.default_config.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict): # shallow merge for nested dicts like serial_port
                        for sub_key, sub_value in value.items():
                            if key in config and isinstance(config[key], dict) and sub_key not in config[key]:
                                config[key][sub_key] = sub_value
                            elif key not in config or not isinstance(config[key],dict): # if type mismatch or key missing
                                config[key] = value # reset to default dict
                return config
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(f"加载配置文件失败: {e}", "CONFIG")
                return self.default_config.copy() # Return a copy
        return self.default_config.copy() # Return a copy

    def save_config(self, config: Dict[str, Any]) -> None:
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            if self.error_logger:
                self.error_logger.log_info("配置已保存。")
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"保存配置文件失败: {e}", "CONFIG")