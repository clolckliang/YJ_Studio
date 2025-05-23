import csv
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
from utils.constants import Constants
from utils.logger import ErrorLogger # Assuming ErrorLogger is in utils.logger

class DataRecorder:
    def __init__(self, error_logger: Optional[ErrorLogger] = None):
        self.historical_data: List[Tuple[str, Dict[str, str]]] = [] # (timestamp_str, {name: value_str})
        self.recording_raw: bool = False
        self.recorded_raw_data: List[Dict[str, Any]] = [] # {'timestamp': dt, 'data': hex_str, 'direction': str}
        self.error_logger = error_logger

    def add_parsed_frame_data(self, timestamp: datetime, parsed_data: Dict[str, str]) -> None:
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.historical_data.append((timestamp_str, parsed_data))
        if len(self.historical_data) > Constants.MAX_HISTORY_SIZE:
            self.historical_data.pop(0)

    def clear_parsed_data_history(self) -> None:
        self.historical_data.clear()

    def export_parsed_data_to_csv(self, filename: str) -> bool:
        if not self.historical_data:
            if self.error_logger:
                self.error_logger.log_warning("没有可导出的已解析数据。")
            return False
        try:
            all_container_names = set()
            for _, data_dict in self.historical_data:
                all_container_names.update(data_dict.keys())
            sorted_container_names = sorted(list(all_container_names))
            headers = ["时间戳"] + sorted_container_names

            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow(headers)
                for timestamp_str, data_dict in self.historical_data:
                    row = [timestamp_str]
                    for name in sorted_container_names:
                        row.append(data_dict.get(name, "")) # Use get for safety
                    csv_writer.writerow(row)
            if self.error_logger:
                self.error_logger.log_info(f"已解析数据已导出到: {filename}")
            return True
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"导出已解析数据失败: {e}", "RECORDER")
            return False

    def start_raw_recording(self) -> None:
        self.recording_raw = True
        self.recorded_raw_data.clear()
        if self.error_logger:
            self.error_logger.log_info("开始原始数据录制。")


    def stop_raw_recording(self) -> None:
        self.recording_raw = False
        if self.error_logger:
            self.error_logger.log_info("停止原始数据录制。")


    def record_raw_frame(self, timestamp: datetime, data_bytes: bytes, direction: str) -> None: # Changed data to data_bytes
        if self.recording_raw:
            self.recorded_raw_data.append({
                'timestamp': timestamp, # Store as datetime object
                'data': data_bytes.hex(),
                'direction': direction
            })

    def save_raw_to_file(self, filename: str) -> None:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for entry in self.recorded_raw_data:
                    # Convert datetime to isoformat string for JSON serialization
                    entry_to_save = entry.copy()
                    entry_to_save['timestamp'] = entry['timestamp'].isoformat()
                    json.dump(entry_to_save, f)
                    f.write('\n')
            if self.error_logger:
                self.error_logger.log_info(f"原始数据已记录到: {filename}")
        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(f"保存原始数据失败: {e}", "RECORDER")