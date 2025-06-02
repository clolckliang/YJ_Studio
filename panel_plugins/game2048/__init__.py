# panel_plugins/game2048/__init__.py
"""
2048游戏插件包

这个模块实现了一个2048游戏面板插件
"""

from typing import Dict, Any, List, Optional, Union
import logging

# 导入面板组件
try:
    from .game2048_panel import Game2048Panel
except ImportError as e:
    logging.error(f"无法导入 Game2048Panel: {e}")
    Game2048Panel = None

# 插件版本和基本信息
PLUGIN_VERSION = "1.0.0"
PLUGIN_NAME = "game2048"
PLUGIN_DISPLAY_NAME = "2048游戏"
PLUGIN_AUTHOR = "YJ Studio"
PLUGIN_DESCRIPTION = "一个简单的2048游戏面板插件"

# 设置日志记录器
logger = logging.getLogger(__name__)

def register_plugin_panels(plugin_manager) -> bool:
    """
    注册2048游戏面板

    Args:
        plugin_manager: 插件管理器实例

    Returns:
        bool: 注册是否成功
    """
    try:
        logger.info(f"开始注册2048游戏面板: {__name__}")

        if Game2048Panel is None:
            logger.error("面板组件 Game2048Panel 导入失败，跳过注册")
            return False

        result = plugin_manager.register_panel_type(
            Game2048Panel,
            module_name=__name__
        )

        if result:
            logger.info(f"2048游戏面板注册成功")
            return True
        else:
            logger.error("2048游戏面板注册失败")
            return False

    except Exception as e:
        logger.exception(f"注册2048游戏面板时发生异常: {str(e)}")
        return False

def get_plugin_metadata() -> Dict[str, Any]:
    """
    获取插件元数据信息

    Returns:
        Dict[str, Any]: 包含插件详细信息的字典
    """
    metadata: Dict[str, Any] = {
        "module_name": __name__,
        "plugin_name": PLUGIN_NAME,
        "display_name": PLUGIN_DISPLAY_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "panel_types_info": [{
            "type_name": Game2048Panel.PANEL_TYPE_NAME,
            "display_name": Game2048Panel.PANEL_DISPLAY_NAME,
            "description": "一个简单的2048游戏实现",
            "features": ["键盘控制", "分数计算", "重新开始"],
            "version": "1.0.0"
        }],
        "dependencies": [],
        "min_app_version": "1.0.0",
        "tags": ["游戏", "2048", "娱乐"]
    }
    return metadata

def get_supported_panel_types() -> List[str]:
    """
    获取此插件支持的面板类型列表

    Returns:
        List[str]: 面板类型名称列表
    """
    if Game2048Panel is not None:
        return [Game2048Panel.PANEL_TYPE_NAME]
    return []

def check_plugin_compatibility(app_version: str) -> Dict[str, Any]:
    """
    检查插件与应用程序的兼容性

    Args:
        app_version: 应用程序版本

    Returns:
        Dict[str, Any]: 兼容性检查结果
    """
    return {
        "compatible": True,
        "plugin_version": PLUGIN_VERSION,
        "min_app_version": "1.0.0",
        "current_app_version": app_version,
        "warnings": [],
        "errors": []
    }

def cleanup_plugin() -> None:
    """
    插件卸载时的清理工作
    """
    logger.info(f"正在清理2048游戏插件")

# 模块级别的信息
__version__ = PLUGIN_VERSION
__author__ = PLUGIN_AUTHOR
__description__ = PLUGIN_DESCRIPTION

# 导出的公共接口
__all__ = [
    'register_plugin_panels',
    'get_plugin_metadata',
    'get_supported_panel_types',
    'check_plugin_compatibility',
    'cleanup_plugin',
    'Game2048Panel'
]
