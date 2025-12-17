"""Configuration management for UI components"""
from pathlib import Path
from typing import Optional, Union
import os


class UIConfig:
    """Simple configuration for UI components"""

    def __init__(self, graph_name: str, ui_path: Union[str, Path, os.PathLike]):
        """Initialize UI configuration

        Args:
            graph_name: Unique identifier for the graph/app
            ui_path: Path to the UI component entry file (relative or absolute)
        """
        self.graph_name = graph_name
        self._ui_path = Path(ui_path)

    @property
    def ui_path(self) -> Path:
        """Get the absolute path to the UI component"""
        if self._ui_path.is_absolute():
            return self._ui_path

        # If relative, resolve from the caller's directory
        # Look for the file relative to current working directory
        resolved = Path.cwd() / self._ui_path
        if resolved.exists():
            return resolved

        # Try relative to this file's directory (for package usage)
        package_dir = Path(__file__).parent.parent
        resolved = package_dir / self._ui_path
        if resolved.exists():
            return resolved

        # Return original path and let caller handle if it doesn't exist
        return self._ui_path.resolve()

    def exists(self) -> bool:
        """Check if the UI component file exists"""
        return self.ui_path.exists()

    def __repr__(self) -> str:
        return f"UIConfig(graph_name={self.graph_name!r}, ui_path={self.ui_path!r})"
