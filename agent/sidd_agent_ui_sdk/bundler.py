"""UI component bundler service (esbuild-based, ESM/React-safe)

- Uses esbuild if available (via `node` + local `esbuild` or `npx esbuild`)
- Bundles React and ReactDOM into the component
- Emits IIFE suitable for dynamic loading on the client
- Caches results by content hash
"""
import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Union
import tempfile
import shutil

logger = logging.getLogger(__name__)


def _which(cmd: str) -> Optional[str]:
    """Check if a command is available in PATH"""
    return shutil.which(cmd)


class UIBundler:
    """Service for bundling UI components using esbuild"""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """Initialize the bundler

        Args:
            cache_dir: Directory for caching bundled components
        """
        self._cache: Dict[str, str] = {}
        self._cache_dir = Path(cache_dir or Path(tempfile.gettempdir()) / "sidd-agent-ui-cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._esbuild_cmd = self._detect_esbuild()

    # ------------------------------- Public API -------------------------------
    async def bundle_component(self, graph_name: str, component_path: Union[Path, str, os.PathLike]) -> str:
        """Bundle a UI component into a loadable format.

        Args:
            graph_name: A unique name for the component/graph
            component_path: Path to the entry .tsx/.jsx/.ts/.js file

        Returns:
            The bundled JS code that creates window.__LGUI_{graph_name}.

        Raises:
            FileNotFoundError: If component file doesn't exist
            RuntimeError: If bundling fails
        """
        # Coerce to Path if a string/os.PathLike was passed
        if not isinstance(component_path, Path):
            component_path = Path(component_path)
        component_path = component_path.expanduser().resolve()

        if not component_path.exists():
            raise FileNotFoundError(f"UI component not found: {component_path}")

        # Cache key: file content hash + esbuild cmd + env
        file_hash = self._get_file_hash(component_path)
        env_key = f"{self._esbuild_cmd}|{os.getenv('SIDD_UI_ENV','dev')}"
        cache_key = hashlib.sha256((file_hash + env_key + graph_name).encode()).hexdigest()

        if cache_key in self._cache:
            logger.debug("Using cached bundle for %s (%s)", graph_name, component_path)
            return self._cache[cache_key]

        # Bundle with esbuild (creates __SIDD_COMPONENT__ IIFE)
        bundled_code = await self._bundle_with_esbuild(component_path)

        # Create valid JS identifier from graph name
        valid_js_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in graph_name)

        # Wrap with rendering interface
        wrapper = f"""
// Sidd Agent UI Component Wrapper for {graph_name}
{bundled_code}

// Initialize global shadow root registry
window.__SIDD_SHADOW_ROOTS__ = window.__SIDD_SHADOW_ROOTS__ || new Map();

// Create the rendering interface
window.__LGUI_{valid_js_name} = {{
  render: function(componentName, shadowRootId, componentProps) {{
    console.log('[Sidd Agent UI] Render called:', componentName, 'shadowRootId:', shadowRootId, 'props:', componentProps);

    try {{
      // Get React and ReactDOM from the bundled exports
      const React = __SIDD_COMPONENT__.React;
      const ReactDOM = __SIDD_COMPONENT__.ReactDOM;

      if (!React || !ReactDOM) {{
        console.error('[Sidd Agent UI] React/ReactDOM not found in bundle');
        return;
      }}

      // Get the component from the bundle's default export
      const components = __SIDD_COMPONENT__.default || __SIDD_COMPONENT__;
      const Component = components[componentName];

      if (!Component) {{
        console.error(`[Sidd Agent UI] Component "${{componentName}}" not found. Available:`, Object.keys(components));
        return;
      }}

      // Get the shadow root from the global registry (NOT from DOM)
      // This avoids race conditions with React unmounting/remounting
      const shadowRoot = window.__SIDD_SHADOW_ROOTS__.get(shadowRootId);

      if (!shadowRoot) {{
        console.error(`[Sidd Agent UI] Shadow root not found in registry: ${{shadowRootId}}`);
        console.log('[Sidd Agent UI] Available shadow roots:', Array.from(window.__SIDD_SHADOW_ROOTS__.keys()));
        return;
      }}

      console.log('[Sidd Agent UI] Found shadow root in registry:', shadowRootId);

      // Clear any existing content to prevent duplicate renders
      shadowRoot.innerHTML = '';

      // Create a container div to render into
      const container = document.createElement('div');
      shadowRoot.appendChild(container);

      // Render the component using bundled React
      const root = ReactDOM.createRoot(container);
      root.render(React.createElement(Component, componentProps || {{}}));

      console.log('[Sidd Agent UI] Component rendered successfully:', componentName);

      // Clean up registry entry after rendering
      window.__SIDD_SHADOW_ROOTS__.delete(shadowRootId);
    }} catch (error) {{
      console.error('[Sidd Agent UI] Error rendering component:', error);
    }}
  }}
}};
"""

        self._cache[cache_key] = wrapper
        return wrapper

    def invalidate_component(self, component_path: Union[Path, str, os.PathLike]) -> None:
        """Invalidate the cache for a specific component.

        Args:
            component_path: Path to the component file to invalidate
        """
        self._cache.clear()
        logger.info(f"Cache invalidated for component: {component_path}")

    # ------------------------------ Internal Methods -----------------------------
    def _get_file_hash(self, path: Union[Path, str, os.PathLike]) -> str:
        """Get SHA256 hash of file contents"""
        h = hashlib.sha256()
        path = Path(path)
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def _detect_esbuild(self) -> Optional[list]:
        """Return a command list usable with subprocess for esbuild, or None."""
        # Prefer local esbuild
        if _which('esbuild'):
            return ['esbuild']
        # Try npx esbuild
        if _which('npx'):
            return ['npx', 'esbuild']
        return None

    async def _bundle_with_esbuild(self, entry: Path) -> str:
        """Bundle component using esbuild"""
        if not self._esbuild_cmd:
            raise RuntimeError(
                "esbuild is required to bundle UI components. "
                "Install it with: npm install -g esbuild"
            )

        is_dev = os.getenv('SIDD_UI_ENV', 'dev').lower() in ('dev', 'development')
        target = os.getenv('SIDD_UI_TARGET', 'es2020')

        with tempfile.TemporaryDirectory() as td:
            # Create a wrapper entry file that includes React and ReactDOM
            component_dir = entry.parent
            wrapper_entry = component_dir / '.sidd_entry_temp.jsx'

            try:
                wrapper_entry.write_text(f"""
import React from 'react';
import ReactDOM from 'react-dom/client';
import components from './{entry.name}';

export {{ React, ReactDOM }};
export default components;
""", encoding='utf-8')

                out_file = Path(td) / 'bundle.js'

                cmd = [
                    *self._esbuild_cmd,
                    str(wrapper_entry),
                    '--bundle',
                    '--format=iife',
                    '--global-name=__SIDD_COMPONENT__',
                    f'--target={target}',
                    '--platform=browser',
                    '--jsx=automatic',
                    # Don't generate source maps at all to avoid 404 issues
                    f'--outfile={out_file}',
                ]

                logger.debug("Running esbuild: %s", ' '.join(cmd))

                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()
                except Exception as e:
                    raise RuntimeError(f"Failed to execute esbuild: {e}") from e

                if proc.returncode != 0:
                    raise RuntimeError(
                        f"esbuild failed (code {proc.returncode}).\n"
                        f"STDOUT:\n{stdout.decode()}\nSTDERR:\n{stderr.decode()}"
                    )

                code = out_file.read_text(encoding='utf-8')
            finally:
                # Clean up the temporary wrapper entry file
                if wrapper_entry.exists():
                    wrapper_entry.unlink()

        return code


# Global singleton instance
_bundler_instance: Optional[UIBundler] = None


def get_ui_bundler() -> UIBundler:
    """Get the global UIBundler instance"""
    global _bundler_instance
    if _bundler_instance is None:
        _bundler_instance = UIBundler()
    return _bundler_instance
