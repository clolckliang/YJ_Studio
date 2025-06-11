import struct
from typing import Optional, Dict, List, Any

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox, QLineEdit, QCheckBox, QMessageBox, QDockWidget, QVBoxLayout
)
from PySide6.QtCore import Signal, Slot, QByteArray

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    pass

from utils.logger import ErrorLogger # 导入ErrorLogger
from utils.constants import Constants # Assuming Constants is in utils
from core.protocol_handler import get_data_type_byte_length  # 添加缺失的导入

class ReceiveDataContainerWidget(QWidget):
    plot_target_changed_signal = Signal(int, int)  # container_id, target_plot_id

    def __init__(self, container_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container_id = container_id
        self.available_plots: Dict[int, str] = {} # {plot_id: plot_name}
        self.logger = ErrorLogger() # 创建ErrorLogger实例
        self.init_ui()

    def init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.name_edit = QLineEdit(f"RecvData_{self.container_id}")
        self.name_edit.setPlaceholderText("数据名称")
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(Constants.DATA_TYPE_SIZES.keys()))
        self.value_edit = QLineEdit()
        self.value_edit.setReadOnly(True)
        self.value_edit.setPlaceholderText("数据值")

        layout.addWidget(self.name_edit, 2)
        layout.addWidget(self.type_combo, 2)
        layout.addWidget(self.value_edit, 3)

        if PYQTGRAPH_AVAILABLE:
            self.plot_checkbox = QCheckBox("绘图")
            self.plot_target_combo = QComboBox()
            self.plot_target_combo.setToolTip("选择此数据显示在哪个波形图上")
            self.plot_checkbox.toggled.connect(self.plot_target_combo.setEnabled)
            self.plot_target_combo.setEnabled(False)
            self.plot_target_combo.currentIndexChanged.connect(self._emit_plot_target_change)
            layout.addWidget(self.plot_checkbox, 0)
            layout.addWidget(QLabel("到:"), 0)
            layout.addWidget(self.plot_target_combo, 1)
        else:
            self.plot_checkbox = None # Ensure attribute exists
            self.plot_target_combo = None


    def update_plot_targets(self, targets: Dict[int, str]):  # targets = {plot_id: plot_name}
        if not PYQTGRAPH_AVAILABLE or not self.plot_target_combo:
            return
        self.available_plots = targets
        current_selection_id = self.plot_target_combo.currentData()
        self.plot_target_combo.clear()
        for plot_id, plot_name in targets.items():
            self.plot_target_combo.addItem(plot_name, plot_id)

        if current_selection_id in targets:
            self.plot_target_combo.setCurrentIndex(self.plot_target_combo.findData(current_selection_id))
        elif targets: # If there are targets and previous selection is gone, select first
            self.plot_target_combo.setCurrentIndex(0)

        self.plot_target_combo.setEnabled(self.plot_checkbox.isChecked() and bool(targets))


    @Slot()
    def _emit_plot_target_change(self):
        if PYQTGRAPH_AVAILABLE and self.plot_target_combo and self.plot_target_combo.count() > 0 :
            target_plot_id = self.plot_target_combo.currentData() # Returns user data (plot_id)
            if target_plot_id is not None:
                self.plot_target_changed_signal.emit(self.container_id, target_plot_id)

    def get_config(self) -> Dict[str, Any]:
        target_plot_id = None
        plot_enabled = False
        if PYQTGRAPH_AVAILABLE and self.plot_checkbox and self.plot_target_combo:
            plot_enabled = self.plot_checkbox.isChecked()
            if plot_enabled and self.plot_target_combo.count() > 0:
                target_plot_id = self.plot_target_combo.currentData()

        return {
            "id": self.container_id,
            "name": self.name_edit.text(),
            "type": self.type_combo.currentText(),
            "plot_enabled": plot_enabled,
            "plot_target_id": target_plot_id
        }

    def set_value(self, value_bytes: QByteArray, data_type: str) -> None:
        self.logger.info(f"ReceiveDataContainerWidget {self.container_id}: set_value called with data_type='{data_type}', value_bytes length={len(value_bytes)}")
        if not value_bytes or value_bytes.isEmpty():
            self.logger.info(f"ReceiveDataContainerWidget {self.container_id}: value_bytes is empty, setting text to '无数据'")
            # 在主线程更新UI
            self.value_edit.setText("无数据")
            return
            
        try:
            byte_data = value_bytes.data()
            self.logger.info(f"ReceiveDataContainerWidget {self.container_id}: byte_data = {byte_data.hex()}")
            byte_len = len(byte_data)
            val_str = "N/A"
            
            # 获取数据类型所需的最小字节数
            required_bytes = get_data_type_byte_length(data_type)
            
            # 智能数据类型适应 - 当数据长度不匹配时尝试自动转换
            if required_bytes > 0 and byte_len < required_bytes:
                self.logger.info(f"ReceiveDataContainerWidget {self.container_id}: Data length ({byte_len}) is less than required ({required_bytes}), attempting automatic conversion.")
                # 尝试自动转换到匹配数据长度的类型
                if byte_len == 1:
                    # 1字节数据尝试uint8_t或int8_t
                    try:
                        val_str = str(struct.unpack('<B', byte_data[:1])[0])
                        # 在主线程更新UI
                        self.value_edit.setText(f"{val_str} (自动: uint8_t)")
                        return
                    except Exception as e:
                        self.logger.warning(f"ReceiveDataContainerWidget {self.container_id}: Auto convert 1-byte to uint8_t failed: {e}")
                        pass
                elif byte_len == 2:
                    # 2字节数据尝试uint16_t或int16_t
                    try:
                        val_str = str(struct.unpack('<H', byte_data[:2])[0])
                        # 在主线程更新UI
                        self.value_edit.setText(f"{val_str} (自动: uint16_t)")
                        return
                    except Exception as e:
                        self.logger.warning(f"ReceiveDataContainerWidget {self.container_id}: Auto convert 2-byte to uint16_t failed: {e}")
                        pass
                elif byte_len == 4:
                    # 4字节数据尝试uint32_t、int32_t或float
                    try:
                        val_str = str(struct.unpack('<I', byte_data[:4])[0])
                        # 在主线程更新UI
                        self.value_edit.setText(f"{val_str} (自动: uint32_t)")
                        return
                    except Exception as e:
                        self.logger.warning(f"ReceiveDataContainerWidget {self.container_id}: Auto convert 4-byte to uint32_t failed: {e}")
                        pass
                    try:
                        val_str = f"{struct.unpack('<f', byte_data[:4])[0]:.4f}"
                        # 在主线程更新UI
                        self.value_edit.setText(f"{val_str} (自动: float)")
                        return
                    except Exception as e:
                        self.logger.warning(f"ReceiveDataContainerWidget {self.container_id}: Auto convert 4-byte to float failed: {e}")
                        pass
                
                # 如果自动转换失败，显示详细错误
                self.value_edit.setText(f"长度不足 ({byte_len}<{required_bytes}) - 请检查数据类型配置")
                return
                
            # 正常处理
            if data_type == "uint8_t":
                val_str = str(struct.unpack('<B', byte_data[:1])[0])
            elif data_type == "int8_t":
                val_str = str(struct.unpack('<b', byte_data[:1])[0])
            elif data_type == "uint16_t":
                try:
                    value = struct.unpack('<H', byte_data[:2])[0]
                    val_str = str(value)
                    self.logger.info(f"ReceiveDataContainerWidget {self.container_id}: uint16_t parse successful, value='{val_str}'")
                except Exception as e:
                    self.logger.error(f"ReceiveDataContainerWidget {self.container_id}: uint16_t parse failed: {e}")
                    val_str = "解析错误: uint16_t"
            elif data_type == "int16_t":
                # Parse as int16_t, then convert to float for display as requested
                int_val = struct.unpack('<h', byte_data[:2])[0]
                val_str = f"{float(int_val):.4f}" # Convert to float and format
                self.logger.info(f"ReceiveDataContainerWidget {self.container_id}: int16_t parse - int_val={int_val}, val_str='{val_str}'")
            elif data_type == "uint32_t":
                val_str = str(struct.unpack('<I', byte_data[:4])[0])
            elif data_type == "int32_t":
                val_str = str(struct.unpack('<i', byte_data[:4])[0])
            elif data_type == "float (4B)":
                val_str = f"{struct.unpack('<f', byte_data[:4])[0]:.4f}"
            elif data_type == "double (8B)":
                val_str = f"{struct.unpack('<d', byte_data[:8])[0]:.6f}"
            elif data_type == "string" or data_type == "string (UTF-8)":
                val_str = value_bytes.data().decode('utf-8', errors='replace')
            elif data_type == "Hex (raw)" or data_type == "Hex String":
                val_str = value_bytes.toHex(' ').data().decode('ascii').upper()
            else:
                val_str = "未知类型"
        except struct.error:
            val_str = "解析错误"
        except Exception as e:
            val_str = f"解析错误: {str(e)}"
            self.logger.error(f"ReceiveDataContainerWidget {self.container_id}: 解析错误 - {e}")
            
        # 确保在主线程更新UI
        self.value_edit.setText(val_str)
        self.logger.info(f"ReceiveDataContainerWidget {self.container_id}: set_value finished, setting text to '{val_str}'")

    def get_value_as_float(self) -> Optional[float]:
        try:
            return float(self.value_edit.text())
        except ValueError:
            return None

    def get_config(self) -> Dict[str, Any]:
        target_plot_id = None
        plot_enabled = False
        if PYQTGRAPH_AVAILABLE and self.plot_checkbox and self.plot_target_combo:
            plot_enabled = self.plot_checkbox.isChecked()
            if plot_enabled and self.plot_target_combo.count() > 0:
                target_plot_id = self.plot_target_combo.currentData()

        return {
            "id": self.container_id,
            "name": self.name_edit.text(),
            "type": self.type_combo.currentText(),
            "plot_enabled": plot_enabled,
            "plot_target_id": target_plot_id
        }

class SendDataContainerWidget(QWidget):
    def __init__(self, container_id: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.container_id = container_id
        self.init_ui()

    def init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        self.name_edit = QLineEdit(f"SendData_{self.container_id}")
        self.name_edit.setPlaceholderText("数据标签 (可选)")
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(Constants.DATA_TYPE_SIZES.keys()))
        self.type_combo.setToolTip("选择要发送数据的类型")
        # Filter out types that don't make sense for sending defined values, like raw string/hex without knowing length
        sendable_types = [k for k,v in Constants.DATA_TYPE_SIZES.items() if v != -1 or k in ["string (UTF-8)", "Hex String"]]
        self.type_combo.clear()
        self.type_combo.addItems(sendable_types)

        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("输入值")
        layout.addWidget(self.name_edit, 2)
        layout.addWidget(self.type_combo, 2)
        layout.addWidget(self.value_edit, 3)

    def get_bytes(self) -> Optional[QByteArray]:
        value_str = self.value_edit.text()
        data_type = self.type_combo.currentText()
        ba = QByteArray()
        try:
            if data_type == "uint8_t":
                ba.append(struct.pack('<B', int(value_str)))
            elif data_type == "int8_t":
                ba.append(struct.pack('<b', int(value_str)))
            elif data_type == "uint16_t":
                ba.append(struct.pack('<H', int(value_str)))
            elif data_type == "int16_t":
                ba.append(struct.pack('<h', int(value_str)))
            elif data_type == "uint32_t":
                ba.append(struct.pack('<I', int(value_str)))
            elif data_type == "int32_t":
                ba.append(struct.pack('<i', int(value_str)))
            elif data_type == "float (4B)":
                ba.append(struct.pack('<f', float(value_str)))
            elif data_type == "double (8B)":
                ba.append(struct.pack('<d', float(value_str)))
            elif data_type == "string (UTF-8)":
                ba.append(value_str.encode('utf-8'))
            elif data_type == "Hex String":
                hex_clean = "".join(value_str.replace("0x", "").replace("0X", "").split())
                if len(hex_clean) % 2 != 0:
                    hex_clean = "0" + hex_clean # Pad if odd length
                ba = QByteArray.fromHex(hex_clean.encode('ascii'))
            else:
                QMessageBox.warning(self, "类型错误", f"未知或不支持的发送类型: {data_type}")
                return None
            return ba
        except ValueError as e: # More specific error for int/float conversion
            QMessageBox.warning(self, "数值错误", f"无法将 '{value_str}' 转为 {data_type}: {e}")
            return None
        except struct.error as e: # Error during packing (e.g. out of range)
             QMessageBox.warning(self, "打包错误", f"无法打包 '{value_str}' 为 {data_type}: {e}")
             return None
        except Exception as e:
            QMessageBox.warning(self, "转换错误", f"转换 '{value_str}' 到 {data_type} 失败: {e}")
            return None

    def get_config(self) -> Dict[str, Any]:
        return {
            "id": self.container_id,
            "name": self.name_edit.text(),
            "type": self.type_combo.currentText(),
            "value": self.value_edit.text()
        }

class PlotWidgetContainer(QWidget):
    """一个封装了 PlotWidget 及其控制逻辑的 QWidget。"""
    def __init__(self, plot_id: int, plot_name: str = "波形图", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.plot_id = plot_id
        self._plot_name = plot_name
        self.setObjectName(f"PlotWidgetContainer_{plot_id}")

        self.curves: Dict[int, pg.PlotDataItem] = {}  # {recv_container_id: PlotDataItem}
        self.data_lists: Dict[int, List[float]] = {} # {recv_container_id: List_of_data_points}

        self.init_ui()

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # No internal margins for the container
        if PYQTGRAPH_AVAILABLE:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setLabel('left', '数值')
            self.plot_widget.setLabel('bottom', '采样点')
            self.plot_widget.showGrid(x=True, y=True)
            self.plot_widget.addLegend(offset=(-10, 10))
            main_layout.addWidget(self.plot_widget)
        else:
            main_layout.addWidget(QLabel(f"{self.plot_name}: pyqtgraph 不可用"))

    @property
    def plot_name(self) -> str:
        return self._plot_name

    @plot_name.setter
    def plot_name(self, name: str) -> None:
        self._plot_name = name
        if PYQTGRAPH_AVAILABLE:
            # self.plot_widget.setTitle(name) # Optional: set title on plot item too
            pass
        # Update parent QDockWidget title if this PlotWidgetContainer is inside one
        parent_dock = self.parent()
        while parent_dock is not None and not isinstance(parent_dock, QDockWidget):
            parent_dock = parent_dock.parent()
        if isinstance(parent_dock, QDockWidget):
            parent_dock.setWindowTitle(name)


    def update_data(self, recv_container_id: int, value: float, recv_container_name: str) -> None:
        if not PYQTGRAPH_AVAILABLE:
            return

        if recv_container_id not in self.curves:
            # Find a color that's not already in use in this specific plot if possible,
            # or cycle through PLOT_COLORS.
            num_existing_curves = len(self.curves)
            pen_color = Constants.PLOT_COLORS[num_existing_curves % len(Constants.PLOT_COLORS)]
            try:
                self.curves[recv_container_id] = self.plot_widget.plot(pen=pen_color, name=recv_container_name)
                self.data_lists[recv_container_id] = []
            except Exception as e:
                # print(f"Error adding curve to plot {self.plot_id} for container {recv_container_id}: {e}")
                return


        self.data_lists[recv_container_id].append(value)
        if len(self.data_lists[recv_container_id]) > Constants.MAX_PLOT_POINTS:
            self.data_lists[recv_container_id] = self.data_lists[recv_container_id][-Constants.MAX_PLOT_POINTS:]

        self.curves[recv_container_id].setData(self.data_lists[recv_container_id])

    def clear_plot(self) -> None:
        if not PYQTGRAPH_AVAILABLE:
            return
        for cid in list(self.curves.keys()): # Iterate over a copy of keys
            if self.curves[cid]:
                self.plot_widget.removeItem(self.curves[cid])
        self.curves.clear()
        self.data_lists.clear()
        # self.plot_widget.clear() # This removes axes labels too, usually not desired.

    def remove_curve_for_container(self, recv_container_id: int) -> None:
        if PYQTGRAPH_AVAILABLE and recv_container_id in self.curves:
            if self.curves[recv_container_id]:
                 self.plot_widget.removeItem(self.curves[recv_container_id])
            del self.curves[recv_container_id]
            if recv_container_id in self.data_lists:
                del self.data_lists[recv_container_id]
            # Rebuild legend? Or it updates automatically? pyqtgraph legend usually needs to be cleared and re-added or items removed individually.
            # For simplicity, removing item should update legend if 'name' was set.

    def get_config(self) -> Dict[str, Any]:
        return {
            "id": self.plot_id,
            "name": self.plot_name,
        }
