# plugin_manager.py
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type, Optional, List, Tuple, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from main import SerialDebugger # Forward reference for type hinting
    from panel_interface import PanelInterface # Actual import for PanelInterface

class PluginManager:
    """
    Manages the discovery, registration, and instantiation of panel plugins.
    """
    def __init__(self, main_window_ref: 'SerialDebugger'):
        """
        Initializes the PluginManager.

        Args:
            main_window_ref: A reference to the main SerialDebugger application instance.
        """
        self.main_window_ref = main_window_ref
        self.error_logger = main_window_ref.error_logger
        # Stores: {panel_type_name: (PanelClass, display_name)}
        self.registered_panel_types: Dict[str, Tuple[Type['PanelInterface'], str]] = {}

    def register_panel_type(self, panel_class: Type['PanelInterface']) -> None:
        """
        Registers a panel class with the manager.

        Args:
            panel_class: The class of the panel to register. It must inherit from PanelInterface
                         and define PANEL_TYPE_NAME and PANEL_DISPLAY_NAME.
        """
        from panel_interface import PanelInterface

        if not issubclass(panel_class, PanelInterface):
            if self.error_logger:
                self.error_logger.log_error(
                    f"Panel class {panel_class.__name__} does not inherit from PanelInterface. Registration failed.",
                    "PLUGIN_MANAGER"
                )
            return

        type_name = getattr(panel_class, 'PANEL_TYPE_NAME', None)
        display_name = getattr(panel_class, 'PANEL_DISPLAY_NAME', None)

        if not type_name or type_name == PanelInterface.PANEL_TYPE_NAME:
            if self.error_logger:
                self.error_logger.log_error(
                    f"Panel class {panel_class.__name__} must define a unique PANEL_TYPE_NAME. Registration failed.",
                    "PLUGIN_MANAGER"
                )
            return
        if not display_name or display_name == PanelInterface.PANEL_DISPLAY_NAME:
             if self.error_logger:
                self.error_logger.log_error(
                    f"Panel class {panel_class.__name__} must define PANEL_DISPLAY_NAME. Registration failed.",
                    "PLUGIN_MANAGER"
                )
             return

        if type_name in self.registered_panel_types:
            if self.error_logger:
                self.error_logger.log_warning(
                    f"Panel type '{type_name}' (from {panel_class.__name__}) is already registered "
                    f"(was {self.registered_panel_types[type_name][0].__name__}). Overwriting.",
                    "PLUGIN_MANAGER"
                )
        self.registered_panel_types[type_name] = (panel_class, display_name)
        if self.error_logger:
            # Corrected call: removed third argument
            self.error_logger.log_info(
                f"Registered panel type: '{type_name}' ({display_name}) from class {panel_class.__name__}"
            )

    def discover_plugins(self, plugin_dir_name: str = "panel_plugins") -> None:
        """
        Discovers and attempts to load panel plugins from a specified directory.
        Each subdirectory in plugin_dir_name is considered a potential plugin package.
        A plugin package must contain an __init__.py with a `register_plugin_panels(plugin_manager)` function.

        Args:
            plugin_dir_name: The name of the directory (relative to main.py's location)
                             where plugin packages are stored.
        """
        script_dir = Path(__file__).resolve().parent
        plugins_path = script_dir.parent / plugin_dir_name


        if not plugins_path.is_dir():
            if self.error_logger:
                # Corrected call: removed third argument
                self.error_logger.log_info(
                    f"Plugin directory '{plugins_path}' not found. No external panels will be loaded."
                )
            return

        if self.error_logger:
            # Corrected call: removed third argument
            self.error_logger.log_info(f"Scanning for plugins in: {plugins_path}")

        for finder, name, ispkg in pkgutil.iter_modules([str(plugins_path)]):
            if ispkg:
                full_module_name = f"{plugin_dir_name}.{name}"
                try:
                    plugin_module = importlib.import_module(full_module_name)
                    if hasattr(plugin_module, 'register_plugin_panels') and callable(plugin_module.register_plugin_panels):
                        plugin_module.register_plugin_panels(self)
                        if self.error_logger:
                            # Corrected call: removed third argument
                            self.error_logger.log_info(
                                f"Successfully processed plugin module: {full_module_name}"
                            )
                    else:
                        if self.error_logger:
                            self.error_logger.log_warning(
                                f"Plugin module {full_module_name} does not have a callable 'register_plugin_panels' function.",
                                "PLUGIN_MANAGER"
                            )
                except Exception as e:
                    if self.error_logger:
                        self.error_logger.log_error(
                            f"Error loading or registering plugin module {full_module_name}: {e}", "PLUGIN_MANAGER", exc_info=True
                        )

    def get_creatable_panel_types(self) -> Dict[str, str]:
        """
        Returns a dictionary of panel types that can be dynamically added via the UI.

        Returns:
            A dictionary where keys are `PANEL_TYPE_NAME` and values are `PANEL_DISPLAY_NAME`.
        """
        return {type_name: info[1] for type_name, info in self.registered_panel_types.items()}

    def create_panel_instance(self, panel_type_name: str, panel_id: int,
                              initial_config: Optional[Dict[str, Any]] = None) -> Optional['PanelInterface']:
        """
        Creates an instance of a registered panel type.

        Args:
            panel_type_name: The `PANEL_TYPE_NAME` of the panel to create.
            panel_id: The unique ID to assign to this panel instance.
            initial_config: Optional configuration dictionary to pass to the panel's constructor.

        Returns:
            An instance of the panel, or None if creation fails.
        """
        from panel_interface import PanelInterface

        if panel_type_name in self.registered_panel_types:
            panel_class, _ = self.registered_panel_types[panel_type_name]
            try:
                instance = panel_class(panel_id=panel_id,
                                       main_window_ref=self.main_window_ref,
                                       initial_config=initial_config)
                if not isinstance(instance, PanelInterface):
                    if self.error_logger:
                        self.error_logger.log_error(
                            f"Instantiated panel '{panel_type_name}' (ID: {panel_id}) is not a PanelInterface. This should not happen.",
                            "PLUGIN_MANAGER"
                        )
                    return None
                return instance
            except Exception as e:
                if self.error_logger:
                    self.error_logger.log_error(
                        f"Error instantiating panel '{panel_type_name}' with ID {panel_id}: {e}",
                        "PLUGIN_MANAGER",
                        exc_info=True
                    )
                return None
        else:
            if self.error_logger:
                self.error_logger.log_warning(
                    f"Panel type '{panel_type_name}' not found for instantiation.", "PLUGIN_MANAGER"
                )
            return None

    def get_panel_type_from_instance(self, panel_instance: 'PanelInterface') -> Optional[str]:
        """
        Helper to get the `PANEL_TYPE_NAME` from a panel instance.

        Args:
            panel_instance: An instance of a panel.

        Returns:
            The `PANEL_TYPE_NAME` of the panel, or None if not found.
        """
        return getattr(type(panel_instance), 'PANEL_TYPE_NAME', None)
