# panel_plugins/snake_game/__init__.py
"""
贪吃蛇游戏插件包
"""

from typing import Dict, Any, List, Optional, Union
import logging

# 导入面板组件
try:
    from .snake_panel import SnakeGamePanel
except ImportError as e:
    logging.error(f"无法导入 SnakeGamePanel: {e}")
    SnakeGamePanel = None

# 插件基本信息
PLUGIN_VERSION = "1.0.0"
PLUGIN_NAME = "snake_game"
PLUGIN_DISPLAY_NAME = "贪吃蛇游戏"
PLUGIN_AUTHOR = "YJ Studio"
PLUGIN_DESCRIPTION = "经典贪吃蛇游戏实现"

# 日志记录器
logger = logging.getLogger(__name__)

def register_plugin_panels(plugin_manager) -> bool:
    """注册贪吃蛇游戏面板"""
    try:
        logger.info(f"开始注册贪吃蛇游戏面板: {__name__}")

        if SnakeGamePanel is None:
            logger.error("面板组件 SnakeGamePanel 导入失败")
            return False

        result = plugin_manager.register_panel_type(
            SnakeGamePanel,
            module_name=__name__
        )

        if result:
            logger.info("贪吃蛇游戏面板注册成功")
            return True
        return False

    except Exception as e:
        logger.exception(f"注册贪吃蛇游戏面板时发生异常: {str(e)}")
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
            "type_name": SnakeGamePanel.PANEL_TYPE_NAME,
            "display_name": SnakeGamePanel.PANEL_DISPLAY_NAME,
            "description": "经典贪吃蛇游戏实现",
            "features": ["键盘控制", "分数计算", "难度调整"],
            "version": "1.0.0"
        }],
        "dependencies": [],
        "min_app_version": "1.0.0",
        "tags": ["游戏", "贪吃蛇", "经典"]
    }

def get_supported_panel_types() -> List[str]:
    """获取支持的面板类型"""
    if SnakeGamePanel is not None:
        return [SnakeGamePanel.PANEL_TYPE_NAME]
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
    logger.info("正在清理贪吃蛇游戏插件资源")

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
    'SnakeGamePanel'
]
