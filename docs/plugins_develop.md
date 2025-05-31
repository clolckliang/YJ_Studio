# SerialDebugger 插件开发指南

## 1. 概述

SerialDebugger 采用插件化架构设计，允许开发者通过创建独立功能模块来扩展核心功能。本指南详细说明插件开发规范，帮助您快速构建符合标准的插件。

## 2. 插件架构

### 2.1 目录结构规范

```
project_root/
├── main.py                  # 主程序入口
├── panel_interface.py       # 面板接口定义
└── panel_plugins/           # 插件目录
    └── plugin_sample/       # 插件包名（小写+下划线）
        ├── __init__.py      # 注册入口
        └── panel_impl.py    # 面板实现
```

### 2.2 命名规范
- 插件包名：全小写，使用下划线分隔（如 `data_visualizer`）
- 面板类型名：全局唯一标识符（如 `"advanced_plotter"`）

## 3. 核心接口实现

### 3.1 PanelInterface 实现要求

```python
from core.panel_interface import PanelInterface
from PySide6.QtWidgets import QWidget


class SamplePanel(PanelInterface):
  # 必须实现的静态属性
  PANEL_TYPE_NAME = "sample_panel"
  PANEL_DISPLAY_NAME = "示例面板"

  def __init__(self, panel_id, main_window_ref, initial_config=None, parent=None):
    super().__init__(panel_id, main_window_ref, initial_config, parent)
    # 初始化逻辑
    self._init_ui()

  def _init_ui(self):
    """构建用户界面"""
    # 实现UI布局
    pass

  def get_config(self) -> dict:
    """返回当前配置状态"""
    return {"key": "value"}

  def apply_config(self, config: dict):
    """应用配置数据"""
    pass
```

### 3.2 关键方法说明

| 方法 | 必须实现 | 说明 |
|------|----------|------|
| `get_config()` | 是 | 返回可JSON序列化的配置字典 |
| `apply_config()` | 是 | 处理配置恢复逻辑 |
| `get_initial_dock_title()` | 是 | 返回面板默认标题 |
| `on_panel_added()` | 否 | 面板加载完成回调 |
| `on_panel_removed()` | 否 | 面板移除前清理 |
| `update_theme()` | 否 | 主题变更处理 |

## 4. 插件注册机制

在 `__init__.py` 中实现注册函数：

```python
from .panel_impl import SamplePanel

def register_plugin_panels(manager):
    """插件入口函数"""
    manager.register_panel_type(SamplePanel)
```



## 5. 插件的加载与使用流程 (新增章节)

一旦您按照上述规范开发并放置了插件，主应用程序 `SerialDebugger` 将按以下流程处理它：

### 5.1 插件发现
- 当 `SerialDebugger` 启动时，其实例化的 `PluginManager` (在 `main.py` 中为 `self.plugin_manager`) 会调用其 `discover_plugins("panel_plugins")` 方法。
- 此方法会扫描位于主应用程序根目录下的 `panel_plugins/` 文件夹。

### 5.2 插件加载与注册
- 对于 `panel_plugins/` 中的每一个子目录（即每个插件包），`PluginManager` 会尝试导入该包。
- 如果导入成功，`PluginManager` 会查找并调用该插件包内 `__init__.py` 文件中定义的 `register_plugin_panels(manager)` 函数。
- `PluginManager` 实例自身 (即 `manager`) 会作为参数传递给 `register_plugin_panels` 函数。
- 在插件的 `register_plugin_panels` 函数内部，您通过调用 `manager.register_panel_type(YourPanelClass)` 来将您的面板类注册到 `PluginManager` 中。

### 5.3 在用户界面中呈现
- `SerialDebugger` 主窗口通过 `PluginManager` 获取所有已成功注册的面板类型。
- 例如，在构建“工具” -> “添加面板”菜单时，`SerialDebugger` 会调用 `self.plugin_manager.get_creatable_panel_types()`。此方法返回一个字典，其中包含每个已注册面板的 `PANEL_TYPE_NAME` (作为键) 和 `PANEL_DISPLAY_NAME` (作为值)。
- `PANEL_DISPLAY_NAME` 将用于在菜单中显示给用户。

### 5.4 面板实例化与显示
- 当用户从菜单中选择添加某个特定类型的面板时（例如，点击“添加示例面板...”），会触发 `SerialDebugger` 中的一个动作。
- 此动作会调用 `self.plugin_manager.create_panel_instance(panel_type_name, panel_id, initial_config)`。
    - `panel_type_name` 是您在插件类中定义的 `PANEL_TYPE_NAME`。
    - `panel_id` 是主程序分配的唯一ID。
    - `initial_config` 通常在从配置文件加载面板时提供，新创建时为 `None`。
- 如果 `create_panel_instance` 成功返回一个面板部件实例：
    - `SerialDebugger` 会提示用户输入一个停靠窗口 (Dock Widget) 的名称，或者使用面板的 `get_initial_dock_title()` 作为默认建议。
    - 然后，主程序会创建一个 `QDockWidget`，将您的面板实例设置为其内容部件。
    - 此 `QDockWidget` 会被添加到主窗口的某个停靠区域，并显示出来。
    - 您的面板的 `on_panel_added()` 方法（如果实现）会被调用。

### 5.5 用户交互与配置
- 用户现在可以与您的插件面板进行交互。
- 当主应用程序保存配置时，会调用您面板的 `get_config()` 方法获取其状态。
- 当主应用程序加载配置时，会使用保存的配置通过 `create_panel_instance` 重新创建您的面板，并通过其 `__init__` 和 `apply_config` 方法恢复状态。

**简而言之，作为插件开发者，您只需确保：**
1.  插件包位于 `panel_plugins/` 目录中。
2.  插件包内有 `__init__.py`，其中包含 `register_plugin_panels` 函数。
3.  在 `register_plugin_panels` 中正确调用 `manager.register_panel_type(YourPanelClass)`。

主应用程序的 `PluginManager` 和 `SerialDebugger` 类会负责其余的发现、加载、菜单集成和实例化工作。








## 6. 开发最佳实践

### 6.1 资源访问
通过 `main_window_ref` 访问主程序资源：
- `self.main_window_ref.serial_manager` 串口管理
- `self.main_window_ref.error_logger` 日志记录
- `self.main_window_ref.status_bar_label` 状态栏

### 6.2 配置管理
- 配置键名使用小写下划线命名法
- 包含版本号字段便于后续升级
- 示例配置：
```python
{
    "version": "1.0",
    "display_mode": "advanced",
    "color_settings": {
        "line_color": "#FF0000"
    }
}
```

### 6.3 错误处理
```python
try:
    # 风险操作
except Exception as e:
    self.error_logger.log_error(f"操作失败: {str(e)}")
    self.main_window_ref.status_bar_label.setText("插件操作出错")
```

## 7. 调试与测试

### 7.1 测试清单
1. 面板多次创建/销毁测试
2. 配置保存/加载循环测试
3. 主题切换兼容性测试
4. 高DPI显示测试
5. 多语言支持测试（如需要）

### 7.2 性能建议
- 避免在 `apply_config()` 中执行耗时操作
- 大数据处理使用后台线程
- 定期调用 `QApplication.processEvents()` 保持响应

## 8. 发布规范

1. 包含 `README.md` 说明文档
2. 提供示例配置文件（如有）
3. 版本号遵循语义化版本规范
4. 建议包含单元测试模块

## 附录A 示例插件结构

完整示例可参考：
```
panel_plugins/
└── serial_monitor/
    ├── __init__.py
    ├── monitor_panel.py
    ├── resources/
    │   └── icons/
    └── README.md
```

## 附录B 可用资源

通过主程序可访问的公共服务：
- 串口配置管理
- 数据协议解析器
- 主题颜色常量
- 多语言翻译接口

如需进一步开发支持，请联系项目维护团队。

#  附录C 插件开发示例

```python
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
  from core.panel_interface import PanelInterface
except ImportError:
  # Fallback for development if paths are tricky.
  # This is not ideal for production.
  import sys
  from pathlib import Path

  # Add project root (assuming main.py is one level up from panel_plugins/example_custom_panel)
  project_root = Path(__file__).resolve().parent.parent.parent
  if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
  from core.panel_interface import PanelInterface


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


```