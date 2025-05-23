# ui/__init__.py

# This makes the directory a Python package.

# Optional: You can make classes from submodules available directly from the package.
# This allows imports like `from ui import ReceiveDataContainerWidget`
# instead of `from ui.widgets import ReceiveDataContainerWidget`.

from .widgets import ReceiveDataContainerWidget, SendDataContainerWidget, PlotWidgetContainer
from .theme_manager import ThemeManager

__all__ = [
    "ReceiveDataContainerWidget",
    "SendDataContainerWidget",
    "PlotWidgetContainer",
    "ThemeManager",
]