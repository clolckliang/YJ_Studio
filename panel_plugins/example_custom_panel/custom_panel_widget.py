# panel_plugins/example_custom_panel/custom_panel_widget.py

from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Slot
from typing import Dict, Any, Optional, TYPE_CHECKING  # Added List for type hinting if needed

# 导入 PanelInterface 和 SerialDebugger (用于类型提示)
# 这个导入块是为了在不同环境下都能找到 panel_interface
try:
    from core.panel_interface import PanelInterface
except ImportError:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from core.panel_interface import PanelInterface, SerialDebugger


if TYPE_CHECKING:
    from main import SerialDebugger # 假设 SerialDebugger 在 main.py 中


class MyCustomPanelWidget(PanelInterface):
    # --- PanelInterface 必须定义的静态类属性 ---
    PANEL_TYPE_NAME: str = "example_custom_panel"  # 全局唯一的类型名称
    PANEL_DISPLAY_NAME: str = "我的自定义面板"  # 用户友好的显示名称

    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger',
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        super().__init__(panel_id, main_window_ref, initial_config, parent)
        print(f"DEBUG: MyCustomPanelWidget (ID: {panel_id}) __init__ called.")  # 新增一个调试信息
        # 插件特定属性初始化
        self.custom_setting: str = "初始默认值"
        self._click_count: int = 0  # 用于演示配置保存和加载

        self._init_ui()  # 构建UI

        if initial_config:
            self.apply_config(initial_config)
        else:
            # 如果没有初始配置，设置一些默认值或状态
            self.config_display_label.setText(f"当前设置: {self.custom_setting}")

        # 在UI和配置都设置好后，可以更新一次标题（如果需要）
        # 确保在调用 _update_title 之前，所有依赖的属性都已初始化
        self._update_title()

    def _init_ui(self) -> None:
        """构建和初始化面板的用户界面。"""
        print(f"DEBUG: MyCustomPanelWidget (ID: {self.panel_id}) _init_ui called.")  # 新增一个调试信息
        layout = QVBoxLayout(self)
        self.info_label = QLabel(f"这是 {self.PANEL_DISPLAY_NAME} (ID: {self.panel_id})")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.my_button = QPushButton("点击我!")
        self.my_button.clicked.connect(self._on_my_button_clicked)
        layout.addWidget(self.my_button)

        self.config_display_label = QLabel(f"当前设置: {self.custom_setting}")  # 在 init 中初始化
        layout.addWidget(self.config_display_label)

        self.setLayout(layout)

    def _update_title(self):
        """辅助方法，用于根据内部状态更新停靠窗口标题。"""
        # 示例：标题可以依赖于 custom_setting 或其他状态
        new_dock_title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}] - {self.custom_setting[:15]}"
        if len(self.custom_setting) > 15:
            new_dock_title += "..."
        self.dock_title_changed.emit(new_dock_title)  # 发出信号通知主窗口更新标题

    @Slot()
    def _on_my_button_clicked(self):
        if self.error_logger:  # 使用从 PanelInterface 继承的 error_logger
            self.error_logger.log_info(f"自定义面板 {self.panel_id} 的按钮被点击了!", self.PANEL_TYPE_NAME)

        # 示例：与主窗口交互
        port_info = "未连接"
        if self.main_window_ref.serial_manager.is_connected and self.main_window_ref.current_serial_config:
            port_info = self.main_window_ref.current_serial_config.port_name or "未知端口"

        self.info_label.setText(f"按钮已点击! 串口: {port_info}")

        # 示例：改变设置并更新UI和标题
        self._click_count += 1
        self.custom_setting = f"点击次数: {self._click_count}"
        self.config_display_label.setText(f"当前设置: {self.custom_setting}")
        self._update_title()  # 标题中也反映这个变化

    # --- PanelInterface 必须实现的方法 ---
    def get_config(self) -> Dict[str, Any]:
        """返回一个包含此面板当前状态的可JSON序列化字典。"""
        return {
            "version": "1.0",  # 推荐包含版本号
            "custom_setting": self.custom_setting,
            "click_count": self._click_count
        }

    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用从配置文件加载的配置数据来恢复面板状态。"""
        self.custom_setting = config.get("custom_setting", "从配置加载的默认值")
        self._click_count = config.get("click_count", 0)

        # 确保UI元素已创建后再更新它们
        if hasattr(self, 'config_display_label'):
            self.config_display_label.setText(f"当前设置: {self.custom_setting}")
        if hasattr(self, 'info_label'):  # info_label 可能也需要根据配置更新
            self.info_label.setText(
                f"这是 {self.PANEL_DISPLAY_NAME} (ID: {self.panel_id})\n设置: {self.custom_setting}")

        self._update_title()  # 应用配置后更新标题

    def get_initial_dock_title(self) -> str:
        """返回此面板停靠窗口的默认标题。"""
        return f"{self.PANEL_DISPLAY_NAME} ({self.panel_id})"

    # --- PanelInterface 可选实现的方法 ---
    def on_panel_added(self) -> None:
        """当此面板实例被成功添加到主窗口后调用。"""
        super().on_panel_added()  # 调用基类方法（如果有的话，例如基类也可能记录日志）
        if self.error_logger:
            self.error_logger.log_info(f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 已添加。",
                                       self.PANEL_TYPE_NAME)
        # 可以在这里执行面板添加到UI后需要的初始化操作
        # 例如，如果您的面板需要从主窗口获取一些初始数据或连接到主窗口的特定信号

    def on_panel_removed(self) -> None:
        """
        当此面板实例即将从主窗口移除前调用。
        **关键**: 在此方法中执行所有必要的资源清理！
        """
        super().on_panel_removed()  # 调用基类方法
        if self.error_logger:
            self.error_logger.log_info(
                f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 即将移除。正在清理资源...",
                self.PANEL_TYPE_NAME)
        # 示例：断开任何信号连接，停止定时器，释放外部资源等
        # self.my_button.clicked.disconnect(self._on_my_button_clicked) # 如果需要手动断开

    def update_theme(self) -> None:
        """当主应用程序的主题发生变化时调用。"""
        super().update_theme()  # 调用基类方法
        if self.error_logger:
            self.error_logger.log_debug(f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 主题更新回调。",
                                        self.PANEL_TYPE_NAME)
        # 如果您的面板有自定义样式，可以在这里根据 self.main_window_ref.theme_manager.current_theme_info 更新
        # 例如:
        # if self.main_window_ref.theme_manager.is_dark_theme():
        #     self.info_label.setStyleSheet("color: white;")
        # else:
        #     self.info_label.setStyleSheet("color: black;")