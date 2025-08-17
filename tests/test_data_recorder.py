import pytest
import sys
import os
from unittest.mock import MagicMock, patch, mock_open
from datetime import datetime
from PySide6.QtCore import QByteArray

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.data_recorder import DataRecorder

@pytest.fixture
def data_recorder(tmp_path):
    # 使用临时目录进行测试
    recorder = DataRecorder()
    recorder.recording_dir = str(tmp_path)
    return recorder

class TestDataRecorder:
    def test_initialization(self, data_recorder):
        assert not data_recorder.recording_raw
        assert not data_recorder.recording_parsed
        assert data_recorder.recorded_raw_data == []
        assert data_recorder.historical_data == []

    def test_start_stop_raw_recording(self, data_recorder):
        data_recorder.start_raw_recording()
        assert data_recorder.recording_raw
        assert data_recorder.record_start_time is not None

        data_recorder.stop_raw_recording()
        assert not data_recorder.recording_raw
        assert len(data_recorder.recorded_raw_data) == 0

    def test_record_raw_frame(self, data_recorder):
        test_time = datetime.now()
        test_data = QByteArray(b'\x01\x02\x03')
        data_recorder.record_raw_frame(test_time, test_data, "RX")
        
        assert len(data_recorder.recorded_raw_data) == 1
        record = data_recorder.recorded_raw_data[0]
        assert record['timestamp'] == test_time
        assert record['data'] == test_data.data()
        assert record['direction'] == "RX"

    def test_add_parsed_frame_data(self, data_recorder):
        test_time = datetime.now()
        test_data = {"temp": 25.5, "humidity": 60.0}
        data_recorder.add_parsed_frame_data(test_time, test_data)
        
        assert len(data_recorder.historical_data) == 1
        record = data_recorder.historical_data[0]
        assert record['timestamp'] == test_time
        assert record['data'] == test_data

    @patch("builtins.open", new_callable=mock_open)
    def test_save_raw_data_to_file(self, mock_file, data_recorder, tmp_path):
        # 添加测试数据
        test_time = datetime.now()
        data_recorder.record_raw_frame(test_time, QByteArray(b'\x01\x02\x03'), "RX")
        data_recorder.record_raw_frame(test_time, QByteArray(b'\x04\x05\x06'), "TX")

        # 测试保存
        save_path = tmp_path / "test_save.raw"
        data_recorder.save_raw_data_to_file(str(save_path))

        # 验证文件写入
        mock_file.assert_called_once_with(str(save_path), 'w', encoding='utf-8')
        handle = mock_file()
        assert handle.write.call_count == 2  # 两行数据

    @patch("builtins.open", new_callable=mock_open)
    def test_save_parsed_data_to_csv(self, mock_file, data_recorder, tmp_path):
        # 添加测试数据
        test_time = datetime.now()
        data_recorder.add_parsed_frame_data(test_time, {"temp": 25.5, "humidity": 60.0})
        data_recorder.add_parsed_frame_data(test_time, {"temp": 26.0, "humidity": 58.0})

        # 测试保存
        save_path = tmp_path / "test_save.csv"
        data_recorder.save_parsed_data_to_csv(str(save_path))

        # 验证文件写入
        mock_file.assert_called_once_with(str(save_path), 'w', encoding='utf-8', newline='')
        handle = mock_file()
        assert handle.write.call_count == 3  # 表头 + 两行数据
