"""Sidd Agent UI SDK - Generic backend SDK for dynamic UI components

This SDK is framework-agnostic and can be used with any Python backend.
It provides utilities for bundling React components and serving them dynamically.

Example usage:
    from sidd_agent_ui_sdk import UIManager

    # Simple setup
    ui = UIManager(graph_name="my_app", ui_path="./ui/index.tsx")

    # Use with your agent and app
    agent = LlmAgent(tools=[my_tool, ui.tool])
    app = FastAPI(lifespan=ui.lifespan)
    app.include_router(ui.router)
"""

from .bundler import UIBundler, get_ui_bundler
from .server import UIServer
from .config import UIConfig
from .manager import UIManager

__all__ = [
    # Simplified API (recommended)
    "UIManager",

    # Advanced API (for customization)
    "UIBundler",
    "get_ui_bundler",
    "UIServer",
    "UIConfig",
]

__version__ = "0.1.0"
