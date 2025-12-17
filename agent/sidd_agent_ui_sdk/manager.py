"""Simplified UI management with UIManager"""
import logging
from typing import Union
from pathlib import Path
import os
from contextlib import asynccontextmanager
from contextvars import ContextVar
import asyncio
import json
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

from .server import UIServer

logger = logging.getLogger(__name__)

# Session context for framework-agnostic session tracking
_session_id: ContextVar[str | None] = ContextVar('session_id', default=None)


class UIManager:
    """Simplified manager for UI components with all-in-one setup.

    This class provides a clean API for setting up UI components with
    minimal boilerplate. It handles routing, tool creation, and preloading.

    Example:
        ui = UIManager(graph_name="my_app", ui_path="./ui/index.tsx")

        agent = LlmAgent(tools=[my_tool, ui.tool])
        app = FastAPI(lifespan=ui.lifespan)
        app.include_router(ui.router)
    """

    def __init__(
        self,
        graph_name: str,
        ui_path: Union[str, Path, os.PathLike],
        prefix: str = "",
        preload: bool = True,
    ):
        """Initialize the UI manager

        Args:
            graph_name: Unique identifier for the graph/app
            ui_path: Path to the UI component entry file
            prefix: URL prefix for the router (default: "")
            preload: Whether to pre-bundle components on initialization (default: True)
        """
        self._server = UIServer(
            graph_name=graph_name,
            ui_path=ui_path,
            prefix=prefix,
            preload=preload,
        )
        self.graph_name = graph_name
        self._sessions: dict[str, asyncio.Queue] = {}  # Streaming support
        self._add_streaming_endpoint()  # Add SSE endpoint to router

    def _add_streaming_endpoint(self):
        """Add SSE streaming endpoint to the router (KISS)"""

        @self._server.router.get("/ui/stream")
        async def stream_ui_events(request: Request):
            """SSE endpoint for streaming UI updates

            Query params:
                session: Session ID for this connection
            """
            session_id = request.query_params.get("session")
            if not session_id:
                raise HTTPException(status_code=400, detail="session parameter required")

            return StreamingResponse(
                self.stream_events(session_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                },
            )

    @property
    def router(self):
        """Get the FastAPI router for UI endpoints"""
        return self._server.router

    @property
    def tool(self):
        """Get the push_ui_message tool for LLM agents"""
        return self._server.create_tool()

    @property
    def lifespan(self):
        """Get the lifespan context manager for FastAPI app initialization

        This handles pre-bundling components on startup.

        Example:
            ui = UIManager(graph_name="my_app", ui_path="./ui/index.tsx")
            app = FastAPI(lifespan=ui.lifespan)
        """
        @asynccontextmanager
        async def _lifespan(app: FastAPI):
            # Startup: Pre-bundle UI components
            print("\n" + "="*60)
            print(f"🚀 Starting UI Server for '{self.graph_name}'")
            print("="*60)
            await self._server.preload_bundle()
            print("="*60 + "\n")
            yield
            # Shutdown: cleanup if needed
            print(f"\n👋 Shutting down UI Server for '{self.graph_name}'")

        return _lifespan

    async def preload_bundle(self):
        """Manually pre-bundle the UI component (if not using lifespan)"""
        return await self._server.preload_bundle()

    def invalidate_cache(self):
        """Invalidate the component cache to force re-bundling"""
        from .bundler import get_ui_bundler
        bundler = get_ui_bundler()
        bundler.invalidate_component(self._server.config.ui_path)

    # ========================================================================
    # Streaming API (Framework-Agnostic)
    # ========================================================================

    def set_session(self, session_id: str):
        """Set the current session ID for streaming (call at request start)

        Args:
            session_id: Unique session identifier
        """
        _session_id.set(session_id)
        if session_id not in self._sessions:
            self._sessions[session_id] = asyncio.Queue()

    def emit(self, component_name: str, props: dict, id: str | None = None, merge: bool = False):
        """Emit a UI component update (framework-agnostic streaming)

        This is the simple API for agents to call. Works with any framework.

        Args:
            component_name: Name of the component to render
            props: Props to pass to the component
            id: Optional component ID (generated if not provided)
            merge: If True and component exists, merge props instead of replacing

        Example:
            # New component
            ui.emit("weather", {"location": "Boston", "temp": "Loading..."}, id="w1")

            # Update with merge
            ui.emit("weather", {"temp": 47}, id="w1", merge=True)
        """
        session_id = _session_id.get()
        if not session_id:
            logger.warning("emit() called without session - call set_session() first")
            return

        evt = {
            "type": "ui",
            "id": id or str(uuid4()),
            "graph_name": self.graph_name,
            "component_name": component_name,
            "props": props,
            "merge": merge,
        }

        if session_id in self._sessions:
            self._sessions[session_id].put_nowait(evt)
            action = "Merged" if merge else "Emitted"
            logger.info(f"{action} UI event: {component_name} (id={evt['id']}) to session {session_id}")

    def remove(self, id: str):
        """Remove a UI component by ID

        Args:
            id: Component ID to remove

        Example:
            ui.remove("w1")
        """
        session_id = _session_id.get()
        if not session_id:
            logger.warning("remove() called without session - call set_session() first")
            return

        evt = {
            "type": "remove-ui",
            "id": id,
        }

        if session_id in self._sessions:
            self._sessions[session_id].put_nowait(evt)
            logger.info(f"Removed UI component: {id} from session {session_id}")

    async def stream_events(self, session_id: str):
        """SSE generator for streaming events to frontend

        Args:
            session_id: Session to stream events for

        Yields:
            SSE-formatted event strings
        """
        # Ensure session queue exists
        if session_id not in self._sessions:
            self._sessions[session_id] = asyncio.Queue()

        queue = self._sessions[session_id]

        try:
            while True:
                # Wait for next event (blocks until available)
                evt = await queue.get()

                # Format as SSE
                yield f"data: {json.dumps(evt)}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            logger.info(f"Stream cancelled for session {session_id}")
            raise
