# panel_plugins/example_custom_panel/custom_panel_widget.py

from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Slot
from typing import Dict, Any, Optional

# To import PanelInterface, Python's import system needs to find it.
# If panel_interface.py is in the root directory (alongside main.py),
# and panel_plugins is also in the root, you might need to adjust sys.path
# or structure your project as a proper package.
# For a simple setup where main.py, panel_interface.py are at root:
# Assuming the main application adds the project root to sys.path or uses relative imports correctly.
# A common way is if your main app is run as 'python -m my_project.main'
# and panel_interface is 'my_project.panel_interface'.
# For this example, let's assume PanelInterface can be imported.
# You might need: from ...panel_interface import PanelInterface if panel_plugins is a sub-package of a larger app package.
# Or, if main.py adds its directory to sys.path, 'from panel_interface import PanelInterface' might work.

# Try a direct import assuming it's findable (e.g. main.py's dir is in PYTHONPATH)
try:
    from panel_interface import PanelInterface
except ImportError:
    # Fallback for development if paths are tricky.
    # This is not ideal for production.
    import sys
    from pathlib import Path

    # Add project root (assuming main.py is one level up from panel_plugins/example_custom_panel)
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from panel_interface import PanelInterface


class MyCustomPanelWidget(PanelInterface):
    # --- PanelInterface Implementation ---
    PANEL_TYPE_NAME: str = "example_custom_panel"  # Unique type name
    PANEL_DISPLAY_NAME: str = "我的自定义面板"  # User-friendly name for menus

    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger',
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(panel_id, main_window_ref, initial_config, parent)

        self.custom_setting = "Default Value"
        self._init_ui()  # Initialize UI elements

        if initial_config:
            self.apply_config(initial_config)

        # After UI is initialized and config applied, set initial title
        self._update_title()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.info_label = QLabel(f"这是 {self.PANEL_DISPLAY_NAME} (ID: {self.panel_id})")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.my_button = QPushButton("点击我!")
        self.my_button.clicked.connect(self._on_my_button_clicked)
        layout.addWidget(self.my_button)

        self.config_display_label = QLabel(f"当前设置: {self.custom_setting}")
        layout.addWidget(self.config_display_label)

        self.setLayout(layout)

    def _update_title(self):
        """Helper to update internal state and emit title change if needed."""
        # Example: title could depend on custom_setting
        new_dock_title = f"{self.PANEL_DISPLAY_NAME} {self.panel_id} - [{self.custom_setting[:10]}]"
        # self.info_label.setText(f"这是 {self.PANEL_DISPLAY_NAME} (ID: {self.panel_id})\n设置: {self.custom_setting}")
        self.dock_title_changed.emit(new_dock_title)

    @Slot()
    def _on_my_button_clicked(self):
        if self.error_logger:
            self.error_logger.log_info(f"自定义面板 {self.panel_id} 的按钮被点击了!", "CUSTOM_PANEL")

        # Example of interacting with main_window_ref
        if self.main_window_ref.serial_manager.is_connected:
            self.info_label.setText(f"按钮已点击! 串口已连接到: {self.main_window_ref.current_serial_config.port_name}")
        else:
            self.info_label.setText("按钮已点击! 串口未连接。")

        # Example of changing a setting and updating title
        count = getattr(self, '_click_count', 0) + 1
        setattr(self, '_click_count', count)
        self.custom_setting = f"点击次数: {count}"
        self.config_display_label.setText(f"当前设置: {self.custom_setting}")
        self._update_title()

    def get_config(self) -> Dict[str, Any]:
        """Return configuration specific to this panel."""
        return {
            "custom_setting": self.custom_setting,
            "click_count": getattr(self, '_click_count', 0)
            # Add any other settings this panel needs to save
        }

    def apply_config(self, config: Dict[str, Any]) -> None:
        """Apply loaded configuration."""
        self.custom_setting = config.get("custom_setting", "Loaded Default")
        setattr(self, '_click_count', config.get("click_count", 0))

        # Update UI based on loaded config
        self.config_display_label.setText(f"当前设置: {self.custom_setting}")
        self.info_label.setText(f"这是 {self.PANEL_DISPLAY_NAME} (ID: {self.panel_id})\n设置: {self.custom_setting}")
        # Title will be updated by _update_title called from __init__ after apply_config,
        # or you can call it here if needed.

    def get_initial_dock_title(self) -> str:
        """Return the initial title for the dock widget."""
        # Could be based on initial_config if provided
        return f"{self.PANEL_DISPLAY_NAME} {self.panel_id}"

    def on_panel_added(self) -> None:
        if self.error_logger:
            self.error_logger.log_info(f"{self.PANEL_DISPLAY_NAME} (ID: {self.panel_id}) 已添加到UI。", "CUSTOM_PANEL")

    def on_panel_removed(self) -> None:
        if self.error_logger:
            self.error_logger.log_info(f"{self.PANEL_DISPLAY_NAME} (ID: {self.panel_id}) 已从UI移除。", "CUSTOM_PANEL")
        # Perform any cleanup specific to this panel

    def update_theme(self) -> None:
        # Example: if this panel has custom styling needs based on theme
        if self.error_logger:
            self.error_logger.log_debug(f"{self.PANEL_DISPLAY_NAME} (ID: {self.panel_id}) 主题更新回调。",
                                        "CUSTOM_PANEL")
        # self.my_button.setStyleSheet("...") # Update styles if needed

