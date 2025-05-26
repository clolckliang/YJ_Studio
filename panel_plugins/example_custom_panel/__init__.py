# panel_plugins/example_custom_panel/__init__.py
from .custom_panel_widget import MyCustomPanelWidget

def register_plugin_panels(plugin_manager):
    print(f"DEBUG: ==> REGISTER_PLUGIN_PANELS CALLED for module: {__name__} <==") # <--- 关键调试打印
    module_full_name = __name__
    plugin_manager.register_panel_type(MyCustomPanelWidget, module_name=module_full_name)
    print(f"DEBUG: ==> Called register_panel_type for {MyCustomPanelWidget.PANEL_DISPLAY_NAME} from {module_full_name} <==") # <--- 关键调试打印

# （可选但推荐）添加 get_plugin_metadata 函数
def get_plugin_metadata():
    return {
        "module_name": __name__,
        "display_name": "我的自定义插件包示例",
        "version": "1.0.0",
        "description": "这是一个自定义面板的简单示例。",
        "author": "您的名字",
        "panel_types_info": [
            {
                "type_name": MyCustomPanelWidget.PANEL_TYPE_NAME,
                "display_name": MyCustomPanelWidget.PANEL_DISPLAY_NAME,
                "description": "自定义面板的主要功能。"
            }
        ]
    }