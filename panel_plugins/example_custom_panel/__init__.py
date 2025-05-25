# panel_plugins/example_custom_panel/__init__.py

# Import the panel widget class from this plugin package
from .custom_panel_widget import MyCustomPanelWidget

def register_plugin_panels(plugin_manager):
    """
    This function is called by the PluginManager during plugin discovery.
    It should register all panel types provided by this plugin.

    Args:
        plugin_manager: The instance of the PluginManager from the main application.
    """
    plugin_manager.register_panel_type(MyCustomPanelWidget)
    # If this plugin provides multiple panel types, register them all here:
    # plugin_manager.register_panel_type(AnotherCustomPanelWidget)
