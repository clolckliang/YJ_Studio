# panel_plugins/pid_code_generator/__init__.py

"""
高级PID代码生成器插件包

这个模块提供了一个功能完整的C语言PID控制器代码生成器，包括：
- 位置式、增量式和高级PID算法支持
- 丰富的PID参数配置选项
- 高级控制功能（滤波、抗积分饱和、自适应控制等）
- 基于模板的代码生成
- C语言语法高亮
- 实时代码预览和导出功能
"""

from typing import Dict, Any, List, Optional, Union
import logging

# 导入面板组件
try:
    from .advanced_pid_generator import AdvancedPIDGeneratorWidget
except ImportError as e:
    logging.error(f"无法导入 AdvancedPIDGeneratorWidget: {e}")
    AdvancedPIDGeneratorWidget = None

# 插件版本和基本信息
PLUGIN_VERSION = "2.0.0"
PLUGIN_NAME = "advanced_pid_code_generator"
PLUGIN_DISPLAY_NAME = "高级PID代码生成器"
PLUGIN_AUTHOR = "YJ Studio Team"

# 设置日志记录器
logger = logging.getLogger(__name__)

# 调试模式开关
DEBUG_MODE = False


def _debug_print(message: str) -> None:
    """条件调试打印函数"""
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
        if AdvancedPIDGeneratorWidget is None:
            error_msg = f"面板组件 AdvancedPIDGeneratorWidget 导入失败，跳过注册"
            logger.error(error_msg)
            return False

        # 验证面板组件的必要属性
        if not _validate_panel_widget(AdvancedPIDGeneratorWidget):
            return False

        module_full_name = __name__

        # 注册面板类型
        try:
            _debug_print(f"==> Attempting to register panel type: {AdvancedPIDGeneratorWidget.PANEL_TYPE_NAME} <==")
            _debug_print(f"==> Panel display name: {AdvancedPIDGeneratorWidget.PANEL_DISPLAY_NAME} <==")
            _debug_print(f"==> Module name: {module_full_name} <==")

            result = plugin_manager.register_panel_type(
                AdvancedPIDGeneratorWidget,
                module_name=module_full_name
            )

            _debug_print(f"==> register_panel_type returned: {result} (type: {type(result)}) <==")

            # 处理不同的返回值类型
            if result is None:
                _debug_print(f"==> register_panel_type returned None, assuming success <==")
                success = True
            elif isinstance(result, bool):
                success = result
            else:
                success = bool(result)
                _debug_print(f"==> register_panel_type returned non-boolean: {result}, converted to: {success} <==")

            if success:
                _debug_print(
                    f"==> Successfully registered {AdvancedPIDGeneratorWidget.PANEL_DISPLAY_NAME} from {module_full_name} <==")
                logger.info(f"面板类型注册成功: {AdvancedPIDGeneratorWidget.PANEL_DISPLAY_NAME}")
                return True
            else:
                logger.error(f"面板类型注册失败: {AdvancedPIDGeneratorWidget.PANEL_DISPLAY_NAME}")
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
    panel_types_info: List[Dict[str, Any]] = []

    metadata: Dict[str, Any] = {
        "module_name": __name__,
        "plugin_name": PLUGIN_NAME,
        "display_name": PLUGIN_DISPLAY_NAME,
        "version": PLUGIN_VERSION,
        "description": "功能完整的C语言PID控制器代码生成器，支持位置式、增量式和高级PID算法，提供丰富的参数配置选项和高级控制功能。",
        "author": PLUGIN_AUTHOR,
        "panel_types_info": panel_types_info,
        "dependencies": [],
        "min_app_version": "1.0.0",
        "tags": ["代码生成", "PID控制", "C语言", "控制算法", "高级功能", "自适应控制", "模糊控制"]
    }

    # 动态添加面板类型信息
    if AdvancedPIDGeneratorWidget is not None:
        try:
            panel_info: Dict[str, Any] = {
                "type_name": AdvancedPIDGeneratorWidget.PANEL_TYPE_NAME,
                "display_name": AdvancedPIDGeneratorWidget.PANEL_DISPLAY_NAME,
                "description": "功能完整的高级PID代码生成器，支持多种PID算法和高级控制功能，提供参数配置、代码预览和导出功能。",
                "features": [
                    "位置式、增量式和高级PID算法",
                    "丰富的PID参数配置",
                    "高级控制功能（滤波、抗积分饱和等）",
                    "自适应控制参数调节",
                    "模糊PID控制支持",
                    "基于模板的代码生成",
                    "C语言语法高亮",
                    "实时代码预览",
                    "代码导出功能",
                    "配置保存和加载",
                    "主题适配",
                    "多选项卡界面设计"
                ],
                "version": "2.0.0",
                "algorithm_types": [
                    "位置式PID",
                    "增量式PID", 
                    "高级PID"
                ],
                "advanced_features": [
                    "输出变化率限制",
                    "死区处理",
                    "积分分离",
                    "微分滤波",
                    "输入滤波",
                    "设定值滤波",
                    "抗积分饱和（限幅法、反算法、条件积分法）",
                    "自适应参数调节",
                    "模糊PID控制"
                ]
            }
            panel_types_info.append(panel_info)
        except AttributeError as e:
            logger.warning(f"获取面板类型信息时出错: {e}")
            error_panel_info: Dict[str, Any] = {
                "type_name": "advanced_pid_code_generator",
                "display_name": "高级PID代码生成器",
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
    if AdvancedPIDGeneratorWidget is not None:
        try:
            return [AdvancedPIDGeneratorWidget.PANEL_TYPE_NAME]
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
        metadata = get_plugin_metadata()
        min_version = metadata.get("min_app_version", "1.0.0")

        # 简化的版本比较
        compatible = True

        result = {
            "compatible": compatible,
            "plugin_version": PLUGIN_VERSION,
            "min_app_version": min_version,
            "current_app_version": app_version,
            "warnings": [],
            "errors": []
        }

        # 检查面板组件是否可用
        if AdvancedPIDGeneratorWidget is None:
            result["compatible"] = False
            result["errors"].append("高级PID代码生成器面板组件导入失败")

        return result

    except Exception as e:
        logger.exception("兼容性检查失败")
        return {
            "compatible": False,
            "error": str(e),
            "plugin_version": PLUGIN_VERSION
        }


def cleanup_plugin() -> None:
    """
    插件卸载时的清理工作
    """
    try:
        logger.info(f"正在清理插件: {PLUGIN_DISPLAY_NAME}")
        # 执行必要的清理工作
        logger.info(f"插件清理完成: {PLUGIN_DISPLAY_NAME}")
    except Exception as e:
        logger.exception(f"插件清理时发生错误: {e}")


# 模块级别的信息
__version__ = PLUGIN_VERSION
__author__ = PLUGIN_AUTHOR
__description__ = "功能完整的C语言PID控制器代码生成器插件，支持高级控制功能"

# 导出的公共接口
__all__ = [
    'register_plugin_panels',
    'get_plugin_metadata',
    'get_supported_panel_types',
    'check_plugin_compatibility',
    'cleanup_plugin',
    'AdvancedPIDGeneratorWidget'
]
