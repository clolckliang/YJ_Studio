# panel_interface.py
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, QObject # QObject for typing main_window_ref
from typing import Dict, Any, Optional

class PanelInterface(QWidget):
    """
    Abstract base class (or interface) for all dynamic panels
    that can be managed by the PluginManager.
    """
    # Emitted by the panel when its preferred dock title changes
    # The string argument will be the new suggested title for the QDockWidget
    dock_title_changed = Signal(str)

    # Emitted by the panel when it wants to be removed/closed by the user
    # (e.g., if it has its own close button, though standard QDockWidget close is preferred)
    # removal_requested = Signal() # Optional: if panels have internal close mechanisms

    # --- Static properties for plugin registration ---
    # Unique internal name for this panel type (e.g., "parse_data_panel")
    # This MUST be overridden by concrete panel implementations.
    PANEL_TYPE_NAME: str = "base_panel_type"

    # User-friendly name for display in menus (e.g., "Add Parse Panel")
    # This MUST be overridden by concrete panel implementations.
    PANEL_DISPLAY_NAME: str = "Base Panel"

    def __init__(self, panel_id: int, main_window_ref: 'SerialDebugger', # Use forward reference for SerialDebugger
                 initial_config: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        """
        Constructor for a panel.

        Args:
            panel_id: A unique integer ID assigned to this panel instance by the SerialDebugger.
            main_window_ref: A reference to the main SerialDebugger window.
                             Provides access to shared resources like error_logger, serial_manager, etc.
            initial_config: Optional dictionary containing configuration to apply to this panel upon creation.
                            This is typically used when loading panels from a saved configuration file.
            parent: The parent widget, usually the QDockWidget that will host this panel.
        """
        super().__init__(parent)
        self.panel_id = panel_id
        self.main_window_ref = main_window_ref
        if hasattr(main_window_ref, 'error_logger'):
            self.error_logger = main_window_ref.error_logger
        else:
            # Fallback if error_logger is not found, though it should be.
            print(f"Warning: main_window_ref for Panel ID {panel_id} does not have 'error_logger'.")
            self.error_logger = None # Or a dummy logger

        # Concrete panel implementations should call their own _init_ui() method here
        # and then apply initial_config if provided.

    def _init_ui(self) -> None:
        """
        Initializes the user interface elements specific to this panel.
        This method MUST be implemented by concrete panel classes.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement _init_ui")

    def get_config(self) -> Dict[str, Any]:
        """
        Retrieves the current configuration of the panel as a dictionary.
        This dictionary should be serializable (e.g., to JSON) for saving.
        It should NOT include 'panel_id', 'panel_type_name', or 'dock_name' as these
        will be managed and stored by the SerialDebugger or PluginManager.

        Returns:
            A dictionary representing the panel's specific configuration.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_config")

    def apply_config(self, config: Dict[str, Any]) -> None:
        """
        Applies a given configuration dictionary to the panel.
        This is used to restore the panel's state, typically when loading from a file.

        Args:
            config: A dictionary containing the configuration to apply.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement apply_config")

    def get_initial_dock_title(self) -> str:
        """
        Returns the default or initial title for the QDockWidget that will host this panel.
        This can be a generic title based on the panel type and its ID.
        Concrete panels can override this to provide a more specific default title,
        possibly based on their initial_config.

        Returns:
            A string for the initial dock widget title.
        """
        return f"{self.PANEL_DISPLAY_NAME} {self.panel_id}"

    def on_panel_added(self) -> None:
        """
        Called by SerialDebugger after the panel has been successfully added to the UI
        and its dock widget is visible. Panels can perform any post-addition setup here,
        like connecting to signals of other services if needed.
        """
        pass # Optional for panels to implement

    def on_panel_removed(self) -> None:
        """
        Called by SerialDebugger just before this panel instance and its associated
        QDockWidget are removed from the UI and deleted.
        The panel should perform any necessary cleanup here, such as:
        - Disconnecting its signals from other components.
        - Releasing resources.
        - Informing other services if it was a provider of some data (e.g., clearing plot curves it owned).
        """
        pass # Optional for panels to implement

    def update_theme(self) -> None:
        """
        Called when the application theme changes. Panels can override this
        to update their specific styling if not handled by global QSS.
        """
        pass # Optional for panels to implement
