# panel_plugins/can_bus/__init__.py
"""
CAN总线插件包
"""

from typing import Dict, Any, List, Optional, Union
import logging

# 导入面板组件
try:
    from .can_panel import CANBusPanel
except ImportError as e:
    logging.error(f"无法导入 CANBusPanel: {e}")
    CANBusPanel = None

# 插件基本信息
PLUGIN_VERSION = "1.0.0"
PLUGIN_NAME = "can_bus"
PLUGIN_DISPLAY_NAME = "CAN总线工具"
PLUGIN_AUTHOR = "YJ Studio"
PLUGIN_DESCRIPTION = "CAN总线通信和分析工具"

# 日志记录器
logger = logging.getLogger(__name__)

def register_plugin_panels(plugin_manager) -> bool:
    """注册CAN总线面板"""
    try:
        logger.info(f"开始注册CAN总线面板: {__name__}")

        if CANBusPanel is None:
            logger.error("面板组件 CANBusPanel 导入失败")
            return False

        result = plugin_manager.register_panel_type(
            CANBusPanel,
            module_name=__name__
        )

        if result:
            logger.info("CAN总线面板注册成功")
            return True
        return False

    except Exception as e:
        logger.exception(f"注册CAN总线面板时发生异常: {str(e)}")
        return False

def get_plugin_metadata() -> Dict[str, Any]:
    """获取插件元数据"""
    return {
        "module_name": __name__,
        "plugin_name": PLUGIN_NAME,
        "display_name": PLUGIN_DISPLAY_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "panel_types_info": [{
            "type_name": CANBusPanel.PANEL_TYPE_NAME,
            "display_name": CANBusPanel.PANEL_DISPLAY_NAME,
            "description": "CAN总线通信和分析工具",
            "features": ["消息收发", "数据解析", "统计图表"],
            "version": "1.0.0"
        }],
        "dependencies": ["python-can"],
        "min_app_version": "1.0.0",
        "tags": ["CAN", "总线", "汽车电子"]
    }

def get_supported_panel_types() -> List[str]:
    """获取支持的面板类型"""
    if CANBusPanel is not None:
        return [CANBusPanel.PANEL_TYPE_NAME]
    return []

def check_plugin_compatibility(app_version: str) -> Dict[str, Any]:
    """检查插件兼容性"""
    return {
        "compatible": True,
        "plugin_version": PLUGIN_VERSION,
        "min_app_version": "1.0.0",
        "current_app_version": app_version,
        "warnings": [],
        "errors": []
    }

def cleanup_plugin() -> None:
    """清理插件资源"""
    logger.info("正在清理CAN总线插件资源")

# 模块信息
__version__ = PLUGIN_VERSION
__author__ = PLUGIN_AUTHOR
__description__ = PLUGIN_DESCRIPTION

# 导出接口
__all__ = [
    'register_plugin_panels',
    'get_plugin_metadata',
    'get_supported_panel_types',
    'check_plugin_compatibility',
    'cleanup_plugin',
    'CANBusPanel'
]
