# SerialDebugger 插件开发专业指南 (修订版)

## 1. 架构概述

SerialDebugger 采用模块化插件架构，旨在提供一个可扩展的核心平台，允许开发者通过创建和集成独立的功能模块（面板插件）来增强应用程序的能力。本指南详细阐述了插件开发的标准规范、完整的生命周期管理机制以及与主程序高效交互的最佳实践，助力开发者构建高质量、易于维护的插件。

## 2. 开发规范

### 2.1 目录结构

所有外部插件都应作为独立的Python包（包含[__init__.py](file://..\ui\__init__.py)的目录）存放于主应用程序根目录下的 `panel_plugins/` 文件夹内。推荐的结构如下：

```
project_root/
├── main.py                  # 主程序入口
├── panel_interface.py       # 面板接口定义 (所有插件面板必须继承)
├── plugin_manager.py        # 插件管理器实现
└── panel_plugins/           # 外部插件标准存放目录
    └── my_data_monitor/     # 示例插件包名 (遵循命名约定)
        ├── __init__.py      # 插件注册入口，必须存在
        ├── monitor_panel.py # 插件面板核心实现 (文件名可自定义)
        ├── resources/       # (可选) 存放图标、qss等静态资源
        │   └── icons/
        │       └── monitor_icon.png
        └── README.md        # (推荐) 插件说明文档
```

### 2.2 命名约定

- **插件包名 (目录名)**: 全小写，单词间使用下划线分隔 (例如：`data_monitor`, `advanced_plotter`)
- **插件模块名 (导入时使用)**: 例如 `panel_plugins.data_monitor`
- **面板类名**: 遵循Python的PascalCase命名规范 (例如 `DataMonitorPanel`)
- **PANEL_TYPE_NAME (静态类属性)**: 
  - 必须在插件面板类中定义
  - 全局唯一的字符串标识符，用于系统内部识别面板类型
  - 推荐使用小写字母和下划线 (例如："data_monitor_panel")
- **PANEL_DISPLAY_NAME (静态类属性)**:
  - 必须在插件面板类中定义
  - 用户友好的名称，将显示在菜单、插件管理器等UI界面中 (例如："数据监视器")

## 3. 核心接口实现 (PanelInterface)

所有插件面板必须继承自项目根目录 [panel_interface.py](file://..\panel_interface.py) 中定义的 [PanelInterface](file://..\panel_interface.py#L5-L119) 类。
## 3.1 基础模板

```python
# 在您的插件实现文件中 (例如 panel_plugins/my_data_monitor/monitor_panel.py)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton  # 根据需要导入Qt部件
from PySide6.QtCore import Slot  # 如果使用了槽函数
from typing import Dict, Any, Optional, List  # 引入 List

# 假设 panel_interface.py 在项目根目录，并且项目根目录已在Python路径中
# 或者根据您的项目结构调整导入
try:
  from core.panel_interface import PanelInterface, SerialDebugger  # SerialDebugger 用于类型提示
except ImportError:
  # 开发时的备用导入路径 (不推荐用于生产)
  import sys
  from pathlib import Path

  project_root = Path(__file__).resolve().parent.parent.parent
  if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
  from core.panel_interface import PanelInterface, SerialDebugger


class DataMonitorPanel(PanelInterface):
  # --- PanelInterface 必须定义的静态类属性 ---
  PANEL_TYPE_NAME: str = "data_monitor_panel"
  PANEL_DISPLAY_NAME: str = "数据监视器"

  def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger',
               initial_config: Optional[Dict[str, Any]] = None,
               parent: Optional[QWidget] = None):
    super().__init__(panel_id, main_window_ref, initial_config, parent)

    self.monitor_active: bool = False
    self.data_points: List[Any] = []  # 示例属性

    self._init_ui()

    if initial_config:
      self.apply_config(initial_config)

    # self._update_dynamic_dock_title()  # 可以在配置应用后调用

  def _init_ui(self) -> None:
    """构建和初始化面板的用户界面。"""
    layout = QVBoxLayout(self)
    self.info_label = QLabel(f"监视器面板 (ID: {self.panel_id}) - 等待数据...")
    self.info_label.setWordWrap(True)

    self.toggle_button = QPushButton("开始监视")
    self.toggle_button.setCheckable(True)
    self.toggle_button.clicked.connect(self._on_toggle_monitoring)

    layout.addWidget(self.info_label)
    layout.addWidget(self.toggle_button)
    self.setLayout(layout)

  @Slot(bool)
  def _on_toggle_monitoring(self, checked: bool):
    self.monitor_active = checked
    self.toggle_button.setText("停止监视" if checked else "开始监视")
    self.info_label.setText(f"监视状态: {'活动' if checked else '停止'}")
    if self.error_logger:
      self.error_logger.log_info(f"数据监视器 {self.panel_id} 状态变为: {self.monitor_active}", self.PANEL_TYPE_NAME)
    # self._update_dynamic_dock_title() 

  def get_config(self) -> Dict[str, Any]:
    """返回一个包含此面板当前状态的可JSON序列化字典。"""
    return {
      "version": "1.0",
      "monitor_active_on_load": self.monitor_active,
      "saved_data_points_count": len(self.data_points)
    }

  def apply_config(self, config: Dict[str, Any]) -> None:
    """应用从配置文件加载的配置数据来恢复面板状态。"""
    self.monitor_active = config.get("monitor_active_on_load", False)
    self.toggle_button.setChecked(self.monitor_active)
    self._on_toggle_monitoring(self.monitor_active)
    if self.error_logger:
      self.error_logger.log_info(f"数据监视器 {self.panel_id} 配置已应用。", self.PANEL_TYPE_NAME)

  def get_initial_dock_title(self) -> str:
    """返回此面板停靠窗口的默认标题。"""
    return f"{self.PANEL_DISPLAY_NAME} ({self.panel_id})"

  def on_panel_added(self) -> None:
    super().on_panel_added()
    if self.error_logger:
      self.error_logger.log_info(f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 已添加。", "PLUGIN_LIFECYCLE")

  def on_panel_removed(self) -> None:
    super().on_panel_removed()
    if self.error_logger:
      self.error_logger.log_info(f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 即将移除。正在清理资源...",
                                 "PLUGIN_LIFECYCLE")
    self.data_points.clear()

  def update_theme(self) -> None:
    super().update_theme()
    if self.error_logger:
      self.error_logger.log_debug(f"面板 '{self.PANEL_DISPLAY_NAME}' (ID: {self.panel_id}) 主题更新。",
                                  "PLUGIN_LIFECYCLE")
```
3.2 生命周期与回调方法

| 方法/属性             | 类型/签名                                                                                                                            | 必须实现 | 说明                                                                 |
|----------------------|----------------------------------------------------------------------------------------------------------------------------------|----------|----------------------------------------------------------------------|
| PANEL_TYPE_NAME      | `str` (静态类属性)                                                                                                                    | ✓        | 全局唯一的内部类型名。                                               |
| PANEL_DISPLAY_NAME   | `str` (静态类属性)                                                                                                                    | ✓        | 显示给用户的名称。                                                   |
| __init__             | [__init__(self, panel_id, main_window_ref, initial_config=None, parent=None)](file://E:\MY_projects\YJ_toolV4\main.py#L864-L869) | ✓        | 构造函数，必须调用 `super().__init__(...)`。                          |
| _init_ui              | [_init_ui(self) -> None](file://..\main.py#L1043-L1065)                                                                          | ✓        | 构建和初始化面板的用户界面。                                         |
| get_config           | [get_config(self) -> Dict[str, Any]](file://..\main.py#L1079-L1080)                                                              | ✓        | 返回面板当前状态的 JSON 可序列化字典。                               |
| apply_config         | [apply_config(self, config: Dict[str, Any]) -> None](file://..\main.py#L1082-L1083)                                              | ✓        | 从字典加载并应用配置，恢复面板状态。                                 |