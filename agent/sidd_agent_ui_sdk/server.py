"""FastAPI server integration for UI components"""
import json
import logging
import re
from typing import Union, Optional
from pathlib import Path
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from .config import UIConfig
from .bundler import get_ui_bundler

logger = logging.getLogger(__name__)


class UIServer:
    """Server for dynamically bundling and serving UI components

    This class provides a FastAPI router with endpoints for serving
    bundled UI components. It's framework-agnostic and can be used with
    any FastAPI application.

    Example:
        ui_server = UIServer(graph_name="my_app", ui_path="./ui/index.tsx")
        app.include_router(ui_server.router)
    """

    def __init__(
        self,
        graph_name: str,
        ui_path: Union[str, Path, os.PathLike],
        prefix: str = "",
        preload: bool = True,
    ):
        """Initialize the UI server

        Args:
            graph_name: Unique identifier for the graph/app
            ui_path: Path to the UI component entry file
            prefix: URL prefix for the router (default: "")
            preload: Whether to pre-bundle components on initialization (default: True)
        """
        self.config = UIConfig(graph_name=graph_name, ui_path=ui_path)
        self.router = APIRouter(prefix=prefix)
        self._setup_routes()
        self._preload = preload

    def _setup_routes(self):
        """Setup FastAPI routes"""

        @self.router.get("/ui/{graph_name}/entrypoint.js")
        async def get_ui_entrypoint(graph_name: str):
            """Get bundled UI component entrypoint (GET method)"""
            return await self._serve_ui_component(graph_name)

        @self.router.post("/ui/{graph_name}/entrypoint.js")
        async def post_ui_entrypoint(graph_name: str):
            """Get bundled UI component entrypoint (POST method)"""
            return await self._serve_ui_component(graph_name)

        @self.router.post("/ui/{graph_name}")
        async def post_ui_component(graph_name: str, request: Request):
            """Serve UI HTML with script tag"""
            return await self._serve_ui_html(graph_name, request)

        @self.router.options("/ui/{graph_name}")
        async def options_ui_component(graph_name: str):
            """Handle CORS preflight for UI component endpoint"""
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        @self.router.options("/ui/{graph_name}/entrypoint.js")
        async def options_ui_entrypoint(graph_name: str):
            """Handle CORS preflight for entrypoint endpoint"""
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        @self.router.get("/ui/{graph_name}/invalidate")
        async def invalidate_ui_cache(graph_name: str):
            """Invalidate the UI component cache"""
            if graph_name != self.config.graph_name:
                raise HTTPException(
                    status_code=404,
                    detail=f"No UI component configured for graph '{graph_name}'"
                )

            bundler = get_ui_bundler()
            bundler.invalidate_component(self.config.ui_path)

            return {
                "status": "success",
                "message": f"Cache invalidated for graph '{graph_name}'"
            }

    async def _serve_ui_component(self, graph_name: str) -> Response:
        """Internal function to serve bundled UI component

        Args:
            graph_name: Name of the graph to get UI component for

        Returns:
            Response with bundled JavaScript code

        Raises:
            HTTPException: If graph not found or UI not configured
        """
        logger.info(f"UI component requested for graph: {graph_name}")

        # Check if this is the configured graph
        if graph_name != self.config.graph_name:
            logger.warning(f"No UI component configured for graph: {graph_name}")
            raise HTTPException(
                status_code=404,
                detail=f"No UI component configured for graph '{graph_name}'"
            )

        # Check if component file exists
        if not self.config.exists():
            logger.error(f"UI component file not found: {self.config.ui_path}")
            raise HTTPException(
                status_code=404,
                detail=f"UI component file not found for graph '{graph_name}'"
            )

        # Bundle the component
        try:
            import time
            start_time = time.time()

            bundler = get_ui_bundler()
            bundled_code = await bundler.bundle_component(graph_name, self.config.ui_path)

            elapsed = time.time() - start_time
            logger.info(f"[UI Bundler] Bundled {graph_name} in {elapsed:.2f}s")
            print(f"[UI Bundler] Bundled {graph_name} in {elapsed:.2f}s")
        except FileNotFoundError as e:
            logger.error(f"Component file not found: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error bundling UI component: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error bundling UI component: {str(e)}"
            )

        # Return bundled JavaScript
        return Response(
            content=bundled_code,
            media_type="application/javascript; charset=utf-8",
            headers={
                "Cache-Control": "public, max-age=3600, must-revalidate",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "X-Content-Type-Options": "nosniff",
                "Content-Type": "application/javascript; charset=utf-8",
            }
        )

    async def _serve_ui_html(self, graph_name: str, request: Request) -> Response:
        """Serve UI HTML with script tag

        Args:
            graph_name: Name of the graph to get UI component for
            request: FastAPI request object

        Returns:
            HTML with script tag pointing to entrypoint.js

        Raises:
            HTTPException: If graph not found or UI not configured
        """
        # Get the message from request body
        message = await request.json()

        logger.info(f"UI POST request for graph: {graph_name}")
        logger.debug(f"Message: {message}")

        # Check if this is the configured graph
        if graph_name != self.config.graph_name:
            logger.warning(f"UI not found for graph '{graph_name}'")
            raise HTTPException(
                status_code=404,
                detail=f"UI not found for graph '{graph_name}'"
            )

        # Get host header
        host = request.headers.get('host')

        # Determine protocol
        def is_host(needle: str) -> bool:
            if not isinstance(host, str):
                return False
            return host.startswith(needle + ':') or host == needle

        protocol = 'http:' if is_host('localhost') or is_host('127.0.0.1') else ''

        # Create valid JavaScript identifier from graph name
        valid_js_name = re.sub(r'[^a-zA-Z0-9]', '_', graph_name)

        # Build the script tag
        entrypoint_url = f"{protocol}//{host}/ui/{graph_name}/entrypoint.js"

        # Parse message to get component name and props
        message_name = message.get("name", "")
        try:
            # Try to parse as JSON (custom workaround format)
            ui_payload = json.loads(message_name)
            component_name = ui_payload.get("name", "")
            component_props = ui_payload.get("props", {})
            logger.info(f"Parsed JSON payload - component: {component_name}")
        except (json.JSONDecodeError, AttributeError):
            # Fallback to direct usage (standard format)
            component_name = message_name
            component_props = message.get("props", {})
            logger.info(f"Using standard format - component: {component_name}")

        # Validate component name
        if not component_name:
            logger.error(f"Empty component name in request. Message: {message}")
            raise HTTPException(
                status_code=400,
                detail="component_name is required and cannot be empty"
            )

        # Build script tag with onload handler
        script_tag = f'<script src="{entrypoint_url}" onload=\'__LGUI_{valid_js_name}.render({json.dumps(component_name)}, "{{{{shadowRootId}}}}", {json.dumps(component_props)})\'></script>'

        return Response(
            content=script_tag,
            headers={
                'Content-Type': 'text/html',
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )

    async def preload_bundle(self):
        """Pre-bundle the UI component to warm the cache.

        This should be called during application startup to avoid slow first renders.
        The bundled code is cached, so subsequent requests are instant.

        Example:
            ui_server = UIServer(graph_name="my_app", ui_path="./ui/index.tsx")
            await ui_server.preload_bundle()
        """
        if not self._preload:
            logger.info(f"[UI Server] Preloading disabled for {self.config.graph_name}")
            return

        logger.info(f"[UI Server] Pre-bundling components for {self.config.graph_name}...")
        print(f"[UI Server] ⚡ Pre-bundling UI components for {self.config.graph_name}...")

        try:
            import time
            start_time = time.time()

            bundler = get_ui_bundler()
            await bundler.bundle_component(self.config.graph_name, self.config.ui_path)

            elapsed = time.time() - start_time
            logger.info(f"[UI Server] ✓ Pre-bundled {self.config.graph_name} in {elapsed:.2f}s")
            print(f"[UI Server] ✓ Pre-bundled {self.config.graph_name} in {elapsed:.2f}s (cached for instant renders)")
        except Exception as e:
            logger.error(f"[UI Server] Failed to pre-bundle {self.config.graph_name}: {e}")
            print(f"[UI Server] ✗ Failed to pre-bundle {self.config.graph_name}: {e}")
            print(f"[UI Server]   Components will bundle on-demand instead.")

    def create_tool(self):
        """Create a push_ui_message tool for use with LLM agents

        Returns:
            A tool function that can be used with agent frameworks

        Example:
            push_ui_tool = ui_server.create_tool()
            agent = LlmAgent(tools=[my_tool, push_ui_tool])
        """
        from .tools import create_push_ui_message_tool
        return create_push_ui_message_tool(self.config.graph_name)

    def push_ui_message(self, tool_context, component_name: str, props: dict):
        """Push a UI message from developer code (manual usage)

        This is for developers to call directly in their tool implementations,
        not for the LLM to call.

        Args:
            tool_context: The tool context (framework-specific)
            component_name: Name of the component to render
            props: Props to pass to the component

        Note:
            This requires framework-specific implementation to actually
            send the message to the frontend. By default, it just logs.
        """
        logger.info(f"push_ui_message called: {component_name} with props: {props}")
        logger.warning(
            "push_ui_message developer API not yet implemented for this framework. "
            "Use create_tool() for LLM-callable version."
        )
        # TODO: Implement framework-specific message pushing
        # For ADK/CopilotKit, this would need to integrate with the message stream
