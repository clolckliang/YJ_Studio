# panel_plugins/example_custom_panel/custom_panel_widget.py
from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtCore import Slot
from typing import Dict, Any, Optional

# 导入 PanelInterface，支持不同的导入路径
try:
    from core.panel_interface import PanelInterface
except ImportError:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from core.panel_interface import PanelInterface




class MyCustomPanelWidget(PanelInterface):
    """
    自定义面板示例组件

    这个组件演示了如何实现一个完整的自定义面板，包括：
    - UI初始化
    - 配置管理
    - 与主窗口交互
    - 资源清理
    """

    # PanelInterface 必须定义的静态属性
    PANEL_TYPE_NAME: str = "example_custom_panel"
    PANEL_DISPLAY_NAME: str = "我的自定义面板"

    def __init__(self,
                 panel_id: int,
                 main_window_ref: 'SerialDebugger',#  SerialDebugger的实际引用在PanelInterface中已经实现，该警告可以忽略
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        """
        初始化自定义面板

        Args:
            panel_id: 面板唯一标识符
            main_window_ref: 主窗口引用
            initial_config: 初始配置数据
            parent: 父级组件
        """
        super().__init__(panel_id, main_window_ref, initial_config, parent)

        # 记录初始化日志
        if self.error_logger:
            self.error_logger.log_debug(
                f"MyCustomPanelWidget (ID: {panel_id}) 开始初始化",
                self.PANEL_TYPE_NAME
            )

        # 初始化组件特定属性
        self.custom_setting: str = "初始默认值"
        self._click_count: int = 0

        # 初始化UI组件引用
        self.info_label: Optional[QLabel] = None
        self.my_button: Optional[QPushButton] = None
        self.config_display_label: Optional[QLabel] = None

        # 构建用户界面
        self._init_ui()

        # 应用初始配置或设置默认状态
        if initial_config:
            self.apply_config(initial_config)
        else:
            self._update_ui_state()

        # 更新标题
        self._update_title()

    def _init_ui(self) -> None:
        """构建和初始化面板的用户界面"""
        try:
            if self.error_logger:
                self.error_logger.log_debug(
                    f"MyCustomPanelWidget (ID: {self.panel_id}) 开始构建UI",
                    self.PANEL_TYPE_NAME
                )

            layout = QVBoxLayout(self)

            # 创建信息标签
            self.info_label = QLabel(f"这是 {self.PANEL_DISPLAY_NAME} (ID: {self.panel_id})")
            self.info_label.setWordWrap(True)
            layout.addWidget(self.info_label)

            # 创建操作按钮
            self.my_button = QPushButton("点击我!")
            self.my_button.clicked.connect(self._on_my_button_clicked)
            layout.addWidget(self.my_button)

            # 创建配置显示标签
            self.config_display_label = QLabel(f"当前设置: {self.custom_setting}")
            self.config_display_label.setWordWrap(True)
            layout.addWidget(self.config_display_label)

            self.setLayout(layout)

        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    f"MyCustomPanelWidget UI初始化失败: {str(e)}",
                    self.PANEL_TYPE_NAME
                )
            raise

    def _update_ui_state(self) -> None:
        """更新UI状态以反映当前配置"""
        if self.config_display_label:
            self.config_display_label.setText(f"当前设置: {self.custom_setting}")

        if self.info_label:
            self.info_label.setText(
                f"这是 {self.PANEL_DISPLAY_NAME} (ID: {self.panel_id})\n"
                f"点击次数: {self._click_count}"
            )

    def _update_title(self) -> None:
        """根据内部状态更新停靠窗口标题"""
        try:
            # 构建新标题，限制长度避免UI过于拥挤
            setting_preview = self.custom_setting[:15]
            if len(self.custom_setting) > 15:
                setting_preview += "..."

            new_title = f"{self.PANEL_DISPLAY_NAME} [{self.panel_id}] - {setting_preview}"
            self.dock_title_changed.emit(new_title)

        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    f"更新面板标题失败: {str(e)}",
                    self.PANEL_TYPE_NAME
                )

    @Slot()
    def _on_my_button_clicked(self) -> None:
        """处理按钮点击事件"""
        try:
            if self.error_logger:
                self.error_logger.log_info(
                    f"自定义面板 {self.panel_id} 的按钮被点击",
                    self.PANEL_TYPE_NAME
                )

            # 获取当前串口连接状态
            port_info = self._get_port_info()

            # 更新点击计数和设置
            self._click_count += 1
            self.custom_setting = f"点击次数: {self._click_count}"

            # 更新UI显示
            if self.info_label:
                self.info_label.setText(f"按钮已点击! 串口: {port_info}")

            self._update_ui_state()
            self._update_title()

        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    f"按钮点击处理失败: {str(e)}",
                    self.PANEL_TYPE_NAME
                )

    def _get_port_info(self) -> str:
        """获取当前串口连接信息"""
        try:
            if (hasattr(self.main_window_ref, 'serial_manager') and
                    self.main_window_ref.serial_manager.is_connected and
                    hasattr(self.main_window_ref, 'current_serial_config') and
                    self.main_window_ref.current_serial_config):
                return self.main_window_ref.current_serial_config.port_name or "未知端口"
            return "未连接"
        except Exception:
            return "状态未知"

    # === PanelInterface 必须实现的方法 ===

    def get_config(self) -> Dict[str, Any]:
        """返回面板当前状态的配置数据"""
        return {
            "version": "1.0",
            "custom_setting": self.custom_setting,
            "click_count": self._click_count,
            "panel_type": self.PANEL_TYPE_NAME
        }

    def apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置数据恢复面板状态"""
        try:
            # 验证配置版本（可选）
            config_version = config.get("version", "1.0")
            if config_version != "1.0":
                if self.error_logger:
                    self.error_logger.log_warning(
                        f"配置版本不匹配: {config_version}, 预期: 1.0",
                        self.PANEL_TYPE_NAME
                    )

            # 应用配置值
            self.custom_setting = config.get("custom_setting", "从配置加载的默认值")
            self._click_count = config.get("click_count", 0)

            # 更新UI状态
            self._update_ui_state()
            self._update_title()

            if self.error_logger:
                self.error_logger.log_debug(
                    f"面板 {self.panel_id} 配置应用成功",
                    self.PANEL_TYPE_NAME
                )

        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    f"应用配置失败: {str(e)}",
                    self.PANEL_TYPE_NAME
                )

    def get_initial_dock_title(self) -> str:
        """返回面板停靠窗口的初始标题"""
        return f"{self.PANEL_DISPLAY_NAME} ({self.panel_id})"

    # === PanelInterface 可选实现的方法 ===

    def on_panel_added(self) -> None:
        """面板被添加到主窗口后的回调"""
        super().on_panel_added()

        if self.error_logger:
            self.error_logger.log_info(
                f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 已成功添加",
                self.PANEL_TYPE_NAME
            )

        # 可以在这里执行需要主窗口完全初始化后才能进行的操作
        # 例如：连接主窗口的特定信号、获取初始数据等

    def on_panel_removed(self) -> None:
        """面板即将被移除前的清理回调"""
        super().on_panel_removed()

        if self.error_logger:
            self.error_logger.log_info(
                f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 正在清理资源",
                self.PANEL_TYPE_NAME
            )

        try:
            # 断开信号连接（通常Qt会自动处理，但手动断开更安全）
            if self.my_button:
                self.my_button.clicked.disconnect()

            # 清理其他资源
            # 例如：停止定时器、关闭文件句柄、断开网络连接等

        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    f"资源清理时发生错误: {str(e)}",
                    self.PANEL_TYPE_NAME
                )

    def update_theme(self) -> None:
        """主题变化时的更新回调"""
        super().update_theme()

        if self.error_logger:
            self.error_logger.log_debug(
                f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 主题更新",
                self.PANEL_TYPE_NAME
            )

        # 根据主题更新样式
        try:
            if hasattr(self.main_window_ref, 'theme_manager'):
                theme_manager = self.main_window_ref.theme_manager

                # 示例：根据主题调整样式
                if hasattr(theme_manager, 'is_dark_theme') and theme_manager.is_dark_theme():
                    # 深色主题样式
                    if self.info_label:
                        self.info_label.setStyleSheet("QLabel { color: #ffffff; }")
                else:
                    # 浅色主题样式
                    if self.info_label:
                        self.info_label.setStyleSheet("QLabel { color: #000000; }")

        except Exception as e:
            if self.error_logger:
                self.error_logger.log_error(
                    f"主题更新失败: {str(e)}",
                    self.PANEL_TYPE_NAME
                )