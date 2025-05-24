import json
from pathlib import Path
from typing import Optional, Dict, Any

# 确保这些导入路径相对于您的项目结构是正确的
from utils.constants import Constants, ChecksumMode
from utils.data_models import SerialPortConfig, FrameConfig
from utils.logger import ErrorLogger


class ConfigManager:
    def __init__(self, filename: str = Constants.CONFIG_FILE_NAME, error_logger: Optional[ErrorLogger] = None):
        self.config_file = Path(filename)
        self.error_logger = error_logger

        # 更新的 default_config 结构
        self.default_config: Dict[str, Any] = {
            # 全局/默认 设置
            "serial_port": vars(SerialPortConfig()),
            "frame_definition": vars(FrameConfig()),  # 仍然包含全局/默认的发送功能码
            "checksum_mode": Constants.DEFAULT_CHECKSUM_MODE.name,
            "ui_theme_info": {"type": "internal", "name": "light", "path": None},

            # 动态面板的列表
            "parse_panels": [],  # ParsePanelWidget 配置列表
            "send_panels": [],  # SendPanelWidget 配置列表
            "plot_configs": [],  # PlotWidgetContainer 配置列表 (例如: id, name, dock_name)

            # 已抽象化的原静态面板的配置
            "custom_log_panel": {  # CustomLogPanelWidget 的默认配置
                "hex_display": False,
                "timestamp_display": False
            },
            "basic_comm_panel": {  # BasicCommPanelWidget 的默认配置
                "recv_hex_display": False,
                "recv_timestamp_display": False
                # 发送文本和hex复选框通常是瞬态的，默认不保存其状态
            },

            # 窗口几何形状和状态
            "window_geometry": None,
            "window_state": None,

            # 已废弃的键 (不再出现在默认配置中, 但 load_config 会处理旧文件中的这些键)
            # "receive_containers": [],
            # "send_containers": [],
            # "parse_func_id": "C1",
            # "data_mapping_mode": "顺序填充 (Sequential)",
        }

    def load_config(self) -> Dict[str, Any]:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # 创建一个新的配置字典，以默认配置为基础，然后用加载的值更新它。
                # 这确保了如果加载的文件中缺少某些键，所有默认键都会存在，
                # 也有助于将新的默认部分添加到现有配置中。
                config_to_return = self.default_config.copy()

                for key, default_value in self.default_config.items():
                    if key in loaded_config:
                        # 如果默认值是字典，并且加载的值也是字典，
                        # 则执行浅合并，以确保加载的子字典中缺少的默认子键能够被保留。
                        if isinstance(default_value, dict) and isinstance(loaded_config[key], dict):
                            merged_dict = default_value.copy()
                            merged_dict.update(loaded_config[key])
                            config_to_return[key] = merged_dict
                        else:
                            # 对于非字典类型或类型不匹配的情况（例如，加载的不是字典而默认的是），
                            # 直接采用加载的值。
                            config_to_return[key] = loaded_config[key]
                    # 如果键不在 loaded_config 中，则保留来自 config_to_return (从 default_config 复制而来) 的默认值。

                # 添加 loaded_config 中存在但 default_config 中不存在的任何键（例如，用于迁移的旧键）
                for key, value in loaded_config.items():
                    if key not in config_to_return:
                        config_to_return[key] = value

                if self.error_logger:
                    self.error_logger.log_info(f"配置已从 '{self.config_file}' 加载。")
                return config_to_return

            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(f"加载配置文件 '{self.config_file}' 失败: {e}. 使用默认配置。", "CONFIG")
                return self.default_config.copy()  # 出错时返回一份新的默认配置副本

        # 如果配置文件不存在，返回一份新的默认配置副本
        if self.error_logger:
            self.error_logger.log_info(
                f"配置文件 '{self.config_file}' 未找到。使用默认配置。")  # Corrected: Removed the "CONFIG" argument
        return self.default_config.copy()

    def save_config(self, config: Dict[str, Any]) -> None:
        try:
            # 确保父目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)  # 使用 indent=4 以提高可读性
            if self.error_logger:
                self.error_logger.log_info(f"配置已保存到 '{self.config_file}'。")
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"保存配置文件到 '{self.config_file}' 失败: {e}", "CONFIG")