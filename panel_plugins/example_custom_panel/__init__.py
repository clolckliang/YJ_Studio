# panel_plugins/example_custom_panel/__init__.py
"""
自定义面板插件包

这个模块提供了一个示例自定义面板的完整实现，包括：
- 面板组件的定义和实现
- 插件注册逻辑
- 元数据管理
"""

from typing import Dict, Any, List, Optional, Union
import logging

# 导入面板组件
try:
    from .custom_panel_widget import MyCustomPanelWidget
except ImportError as e:
    logging.error(f"无法导入 MyCustomPanelWidget: {e}")
    MyCustomPanelWidget = None

# 插件版本和基本信息
PLUGIN_VERSION = "1.0.0"
PLUGIN_NAME = "example_custom_panel"
PLUGIN_DISPLAY_NAME = "我的自定义插件包示例"
PLUGIN_AUTHOR = "您的名字"

# 设置日志记录器
logger = logging.getLogger(__name__)

# 调试模式开关 - 设置为 False 可关闭所有调试输出
DEBUG_MODE = False


def _debug_print(message: str) -> None:
    """
    条件调试打印函数

    Args:
        message: 要打印的调试信息
    """
    if DEBUG_MODE:
        print(f"DEBUG: {message}")


def register_plugin_panels(plugin_manager) -> bool:
    """
    注册插件提供的所有面板类型

    Args:
        plugin_manager: 插件管理器实例

    Returns:
        bool: 注册是否成功
    """
    try:
        _debug_print(f"==> REGISTER_PLUGIN_PANELS CALLED for module: {__name__} <==")
        logger.info(f"开始注册插件面板: {__name__}")

        # 检查组件是否成功导入
        if MyCustomPanelWidget is None:
            error_msg = f"面板组件 MyCustomPanelWidget 导入失败，跳过注册"
            logger.error(error_msg)
            return False

        # 验证面板组件的必要属性
        if not _validate_panel_widget(MyCustomPanelWidget):
            return False

        module_full_name = __name__

        # 注册面板类型
        try:
            _debug_print(f"==> Attempting to register panel type: {MyCustomPanelWidget.PANEL_TYPE_NAME} <==")
            _debug_print(f"==> Panel display name: {MyCustomPanelWidget.PANEL_DISPLAY_NAME} <==")
            _debug_print(f"==> Module name: {module_full_name} <==")

            result = plugin_manager.register_panel_type(
                MyCustomPanelWidget,
                module_name=module_full_name
            )

            _debug_print(f"==> register_panel_type returned: {result} (type: {type(result)}) <==")

            # 处理不同的返回值类型
            if result is None:
                # 如果返回 None，假设注册成功（某些实现可能不返回值）
                _debug_print(f"==> register_panel_type returned None, assuming success <==")
                success = True
            elif isinstance(result, bool):
                success = result
            else:
                # 如果返回其他类型，转换为布尔值
                success = bool(result)
                _debug_print(f"==> register_panel_type returned non-boolean: {result}, converted to: {success} <==")

            if success:
                _debug_print(
                    f"==> Successfully registered {MyCustomPanelWidget.PANEL_DISPLAY_NAME} from {module_full_name} <==")
                logger.info(f"面板类型注册成功: {MyCustomPanelWidget.PANEL_DISPLAY_NAME}")
                return True
            else:
                logger.error(f"面板类型注册失败: {MyCustomPanelWidget.PANEL_DISPLAY_NAME}")
                return False

        except Exception as reg_error:
            logger.exception(f"面板注册过程中发生异常: {str(reg_error)}")
            return False

    except Exception as e:
        error_msg = f"注册插件面板时发生异常: {str(e)}"
        logger.exception(error_msg)
        return False


def _validate_panel_widget(panel_class) -> bool:
    """
    验证面板组件类是否符合接口要求

    Args:
        panel_class: 要验证的面板类

    Returns:
        bool: 验证是否通过
    """
    try:
        _debug_print(f"==> Validating panel class: {panel_class.__name__} <==")

        # 检查必要的类属性
        required_attrs = ['PANEL_TYPE_NAME', 'PANEL_DISPLAY_NAME']
        for attr in required_attrs:
            if not hasattr(panel_class, attr):
                logger.error(f"面板类验证失败: 缺少属性 {attr}")
                return False

            # 检查属性值是否为空
            value = getattr(panel_class, attr)
            _debug_print(f"==> {attr} = '{value}' (type: {type(value)}) <==")
            if not value or not isinstance(value, str):
                logger.error(f"面板类验证失败: 属性 {attr} 值无效")
                return False

        # 检查必要的方法
        required_methods = ['get_config', 'apply_config', 'get_initial_dock_title']
        for method in required_methods:
            if not hasattr(panel_class, method):
                logger.error(f"面板类验证失败: 缺少方法 {method}")
                return False
            elif not callable(getattr(panel_class, method)):
                logger.error(f"面板类验证失败: {method} 不可调用")
                return False
            else:
                _debug_print(f"==> Method {method} found and callable <==")

        # 检查是否继承自正确的基类
        try:
            # 尝试检查是否有 PanelInterface 基类
            mro = panel_class.__mro__
            base_class_names = [cls.__name__ for cls in mro]
            _debug_print(f"==> Panel class MRO: {base_class_names} <==")

            if 'PanelInterface' not in base_class_names:
                logger.warning(f"面板类可能没有继承正确的基类: {panel_class.__name__}")
        except Exception as e:
            _debug_print(f"==> Could not check base class inheritance: {e} <==")

        _debug_print(f"==> Panel class {panel_class.__name__} validation passed <==")
        logger.debug(f"面板类 {panel_class.__name__} 验证通过")
        return True

    except Exception as e:
        logger.exception("面板类验证异常")
        return False


def get_plugin_metadata() -> Dict[str, Any]:
    """
    获取插件元数据信息

    Returns:
        Dict[str, Any]: 包含插件详细信息的字典
    """
    # 定义面板类型信息的类型
    panel_types_info: List[Dict[str, Any]] = []

    metadata: Dict[str, Any] = {
        "module_name": __name__,
        "plugin_name": PLUGIN_NAME,
        "display_name": PLUGIN_DISPLAY_NAME,
        "version": PLUGIN_VERSION,
        "description": "这是一个自定义面板的完整示例插件，演示了如何创建、注册和管理自定义面板组件。",
        "author": PLUGIN_AUTHOR,
        "panel_types_info": panel_types_info,
        "dependencies": [],
        "min_app_version": "1.0.0",
        "tags": ["示例", "自定义面板", "教程"]
    }

    # 动态添加面板类型信息
    if MyCustomPanelWidget is not None:
        try:
            panel_info: Dict[str, Any] = {
                "type_name": MyCustomPanelWidget.PANEL_TYPE_NAME,
                "display_name": MyCustomPanelWidget.PANEL_DISPLAY_NAME,
                "description": "一个功能完整的自定义面板示例，包含配置管理、主题支持和与主窗口的交互功能。",
                "features": [
                    "配置保存和加载",
                    "主题适配",
                    "串口状态监控",
                    "动态标题更新",
                    "资源自动清理"
                ],
                "version": "1.0.0"
            }
            panel_types_info.append(panel_info)
        except AttributeError as e:
            logger.warning(f"获取面板类型信息时出错: {e}")
            # 如果面板类属性不完整，提供基本信息
            error_panel_info: Dict[str, Any] = {
                "type_name": "example_custom_panel",
                "display_name": "自定义面板示例",
                "description": "面板类型信息不完整",
                "error": str(e)
            }
            panel_types_info.append(error_panel_info)

    return metadata


def get_supported_panel_types() -> List[str]:
    """
    获取此插件支持的面板类型列表

    Returns:
        List[str]: 面板类型名称列表
    """
    if MyCustomPanelWidget is not None:
        try:
            return [MyCustomPanelWidget.PANEL_TYPE_NAME]
        except AttributeError:
            logger.warning("无法获取面板类型名称")
            return []
    return []


def check_plugin_compatibility(app_version: str) -> Dict[str, Any]:
    """
    检查插件与应用程序的兼容性

    Args:
        app_version: 应用程序版本

    Returns:
        Dict[str, Any]: 兼容性检查结果
    """
    try:
        # 简单的版本比较（实际项目中可能需要更复杂的版本解析）
        metadata = get_plugin_metadata()
        min_version = metadata.get("min_app_version", "1.0.0")

        # 这里简化处理，实际应用中应该有更严格的版本比较逻辑
        compatible = True  # 假设兼容

        result = {
            "compatible": compatible,
            "plugin_version": PLUGIN_VERSION,
            "min_app_version": min_version,
            "current_app_version": app_version,
            "warnings": [],
            "errors": []
        }

        # 检查面板组件是否可用
        if MyCustomPanelWidget is None:
            result["compatible"] = False
            result["errors"].append("面板组件导入失败")

        return result

    except Exception as e:
        logger.exception("兼容性检查失败")
        return {
            "compatible": False,
            "error": str(e),
            "plugin_version": PLUGIN_VERSION
        }


# 插件卸载清理函数（可选）
def cleanup_plugin() -> None:
    """
    插件卸载时的清理工作
    """
    try:
        logger.info(f"正在清理插件: {PLUGIN_DISPLAY_NAME}")
        # 执行必要的清理工作
        # 例如：关闭文件、断开连接、清理缓存等
        logger.info(f"插件清理完成: {PLUGIN_DISPLAY_NAME}")
    except Exception as e:
        logger.exception(f"插件清理时发生错误: {e}")


# 模块级别的信息（用于调试和文档）
__version__ = PLUGIN_VERSION
__author__ = PLUGIN_AUTHOR
__description__ = "自定义面板插件示例"

# 导出的公共接口
__all__ = [
    'register_plugin_panels',
    'get_plugin_metadata',
    'get_supported_panel_types',
    'check_plugin_compatibility',
    'cleanup_plugin',
    'MyCustomPanelWidget'
]