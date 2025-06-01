from typing import Optional, TYPE_CHECKING  # Added Set

from PySide6.QtCore import Slot, Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QDialog, QListWidget, QListWidgetItem,  # For Plugin Management Dialog
    QSizePolicy
)
# Core imports from your project structure
if TYPE_CHECKING:
    from main import SerialDebugger  # Forward reference for type hinting
try:
    import pyqtgraph as pg  # type: ignore

    PYQTGRAPH_AVAILABLE = True
except ImportError:
    pg = None
    PYQTGRAPH_AVAILABLE = False
    print("警告：pyqtgraph 未安装，波形图功能将不可用。请运行 'pip install pyqtgraph'")

# Updated Plugin Architecture Imports
from core.plugin_manager import PluginManager  # Assumes plugin_manager_hot_reload_v2 is used
# --- Plugin Management Dialog ---
class PluginManagementDialog(QDialog):
    """
    A dialog for managing plugins: enabling/disabling and session-blocking.
    """
    plugin_status_changed_signal = Signal(str, str)  # module_name, new_status

    def __init__(self, plugin_manager_ref: PluginManager, main_window_ref: 'SerialDebugger',
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager_ref
        self.main_window_ref = main_window_ref
        self.setWindowTitle("插件管理器")
        self.setMinimumSize(600, 400)
        self._init_ui()
        self._populate_plugin_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.plugin_list_widget = QListWidget()
        self.plugin_list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.plugin_list_widget)

        buttons_layout = QHBoxLayout()
        self.enable_button = QPushButton("启用选中插件")
        self.enable_button.clicked.connect(lambda: self._change_plugin_status_action("enable"))
        buttons_layout.addWidget(self.enable_button)

        self.disable_button = QPushButton("禁用选中插件")
        self.disable_button.clicked.connect(lambda: self._change_plugin_status_action("disable"))
        buttons_layout.addWidget(self.disable_button)

        self.session_block_button = QPushButton("会话阻止选中插件")
        self.session_block_button.setToolTip("在当前应用会话中阻止此插件模块被加载，即使它被标记为已启用。")
        self.session_block_button.clicked.connect(lambda: self._change_plugin_status_action("session_block"))
        buttons_layout.addWidget(self.session_block_button)

        self.unblock_button = QPushButton("取消会话阻止")
        self.unblock_button.clicked.connect(lambda: self._change_plugin_status_action("unblock"))
        buttons_layout.addWidget(self.unblock_button)

        buttons_layout.addStretch()
        self.refresh_button = QPushButton("刷新列表")
        self.refresh_button.clicked.connect(self._populate_plugin_list)
        buttons_layout.addWidget(self.refresh_button)

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_button)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def _populate_plugin_list(self):
        self.plugin_list_widget.clear()
        discovered_plugins = self.plugin_manager.get_all_discovered_plugin_modules_metadata()

        if not discovered_plugins:
            self.plugin_list_widget.addItem("未发现任何插件模块。")
            self.enable_button.setEnabled(False)
            self.disable_button.setEnabled(False)
            self.session_block_button.setEnabled(False)
            self.unblock_button.setEnabled(False)
            return

        self.enable_button.setEnabled(True)
        self.disable_button.setEnabled(True)
        self.session_block_button.setEnabled(True)
        self.unblock_button.setEnabled(True)

        for plugin_meta in discovered_plugins:
            module_name = plugin_meta.get("module_name", "未知模块")
            display_name = plugin_meta.get("display_name", module_name.split('.')[-1])
            version = plugin_meta.get("version", "N/A")
            description = plugin_meta.get("description", "无描述。")
            status = plugin_meta.get("status", "discovered")

            item_text = f"{display_name} (v{version}) - {module_name}\n  状态: {status.upper()}\n  描述: {description}"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, module_name)

            font = list_item.font()
            if status == "enabled":
                list_item.setForeground(Qt.GlobalColor.darkGreen)
            elif status == "disabled":
                list_item.setForeground(Qt.GlobalColor.darkGray)
                font.setItalic(True)
            elif status == "blocklisted (session)":
                list_item.setForeground(Qt.GlobalColor.red)
                font.setStrikeOut(True)
            list_item.setFont(font)

            self.plugin_list_widget.addItem(list_item)

    def _get_selected_module_name(self) -> Optional[str]:
        current_item = self.plugin_list_widget.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None

    @Slot()
    def _change_plugin_status_action(self, action_type: str):
        module_name = self._get_selected_module_name()
        if not module_name:
            QMessageBox.warning(self, "操作插件", "请先从列表中选择一个插件模块。")
            return

        if action_type == "enable":
            self.main_window_ref.update_plugin_enabled_status(module_name, True)
            self.plugin_status_changed_signal.emit(module_name, "enabled")
        elif action_type == "disable":
            self.main_window_ref.update_plugin_enabled_status(module_name, False)
            self.plugin_status_changed_signal.emit(module_name, "disabled")
        elif action_type == "session_block":
            self.main_window_ref.session_block_plugin_module(module_name)
            self.plugin_status_changed_signal.emit(module_name, "session_blocked")
        elif action_type == "unblock":
            self.plugin_manager.unblock_module_for_session(module_name)
            QMessageBox.information(self, "取消阻止",
                                    f"模块 {module_name} 已从会话阻止列表中移除。\n如果之前已禁用，您可能需要重新启用它并通过“扫描/重载插件”来使其生效。")
            self.plugin_status_changed_signal.emit(module_name, "unblocked_needs_scan")
        self._populate_plugin_list()
