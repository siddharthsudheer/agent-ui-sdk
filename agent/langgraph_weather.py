"""LangGraph Weather Agent with UI Components."""

import os
import sys
import logging
from fastapi import FastAPI, Request
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from langchain_core.messages import HumanMessage

# Import shared components
from weather_shared import ui, create_weather_graph

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


# ============================================================================
# FastAPI Integration with CopilotKit
# ============================================================================

# Create the graph
weather_graph = create_weather_graph()

# Session middleware for streaming
async def session_middleware(request: Request, call_next):
    """Extract session ID and set it for streaming.

    Phase 1: Uses demo-session for single-user scenarios
    Phase 2: Will extract from auth headers for multi-user
    """
    # Try to get from header, query param, or use default
    session_id = (
        request.headers.get("X-Session-ID") or
        request.query_params.get("session") or
        "demo-session"  # Default for Phase 1
    )
    ui.set_session(session_id)
    logger.debug(f"Session set: {session_id}")
    response = await call_next(request)
    return response

# Create FastAPI app
app = FastAPI(
    title="LangGraph Weather Agent",
    description="Weather agent built with LangGraph with STREAMING",
    lifespan=ui.lifespan
)

# Add session middleware (IMPORTANT for streaming!)
app.middleware("http")(session_middleware)

# Add UI router (includes /ui/stream endpoint!)
app.include_router(ui.router)

# Create CopilotKit remote endpoint
sdk = CopilotKitRemoteEndpoint(
    agents=[
        # Future: Add other agent types here (CrewAI, custom agents, etc.)
    ],
)

# Add the LangGraph agent endpoint with AG-UI integration
add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name="weather_agent",
        description="Weather assistant that provides weather information with UI components.",
        graph=weather_graph
    ),
    path="/"
)

# # Add CopilotKit endpoint for other agents
# add_fastapi_endpoint(app, sdk, "/copilotkit")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ============================================================================
# Standalone Runner (for testing)
# ============================================================================

async def run_standalone():
    """Run the graph standalone for testing."""

    print("\n" + "="*60)
    print("LangGraph Weather Agent - Standalone Test")
    print("="*60 + "\n")

    # Create initial state
    state = {
        "messages": [HumanMessage(content="What's the weather in Boston?")]
    }

    # Run the graph
    config = {"configurable": {"thread_id": "test-thread"}}

    async for event in weather_graph.astream(state, config):
        print(f"\nEvent: {event}")

    print("\n" + "="*60)
    print("Test complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    import uvicorn
    import asyncio

    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Set GOOGLE_API_KEY environment variable")
        print("   export GOOGLE_API_KEY='your-key-here'")
        sys.exit(1)

    # Run FastAPI server
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Starting LangGraph Weather Agent on port {port}\n")
    uvicorn.run("langgraph_weather:app", host="0.0.0.0", port=port, reload=True)
