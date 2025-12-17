"""LangGraph + ADK Hybrid Weather Agent with SQLite Session Management."""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from libs import LangGraphAgent
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from google.adk.sessions import DatabaseSessionService

# Import shared components
from weather_shared import ui, create_weather_graph

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Session Middleware
# ============================================================================

async def session_middleware(request: Request, call_next):
    """Extract session ID and set it for streaming."""
    # session_id = (
    #     request.headers.get("X-Session-ID") or
    #     request.query_params.get("session") or
    #     "demo-session"
    # )
    session_id="demo-session"
    ui.set_session(session_id)
    logger.debug(f"Session set: {session_id}")
    response = await call_next(request)
    return response


# ============================================================================
# ADK + LangGraph Hybrid Setup
# ============================================================================

# Create LangGraph workflow (Now uses weather_checkpoints.sqlite)
logger.info("📊 Creating LangGraph workflow...")
weather_graph = create_weather_graph()

# Wrap LangGraph in ADK's LangGraphAgent
logger.info("🔧 Wrapping LangGraph in ADK's LangGraphAgent...")
adk_langgraph_agent = LangGraphAgent(
    name="WeatherAgent",
    graph=weather_graph,
)

# Wrap in ADK middleware for FastAPI
logger.info("🌐 Wrapping in ADK middleware...")

session_service = DatabaseSessionService(db_url="sqlite:///adk_sessions_storage.db")
# ============================================================================
# ADK PERSISTENCE CONFIGURATION
# ============================================================================
adk_weather_agent = ADKAgent(
    adk_agent=adk_langgraph_agent,
    app_name="weather_app",
    user_id="demo_user",
    session_timeout_seconds=3600,
    session_service=session_service,
    # DISABLE In-Memory Services to enforce SQLite usage for ADK sessions
    use_in_memory_services=True,
    
    # (Optional) If ADK allows specifying path, otherwise it defaults to local DB
    # storage_path="./adk_sessions.db" 
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Merged Lifespan:
    1. Manages AsyncSqliteSaver (Database)
    2. Manages UI Manager (Background Tasks)
    """
    # --- 1. DATABASE SETUP ---
    db_path = "weather_checkpoints.sqlite"
    logger.info(f"🔌 Connecting to Async Checkpoint DB: {db_path}")

    async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
        # A. Initialize DB
        await checkpointer.setup()
        
        # B. Compile & Swap Graph
        logger.info("🚀 Compiling Production Graph...")
        prod_graph = create_weather_graph(checkpointer=checkpointer)
        adk_langgraph_agent.graph = prod_graph
        
        # --- 2. UI SDK SETUP ---
        # We enter the UI's lifespan context right here.
        # This ensures the UI SDK starts up now, and shuts down when we exit.
        async with ui.lifespan(app):
            
            logger.info("✅ Systems Ready: DB + UI SDK")
            
            # Yield control to the running application
            yield 
            
            logger.info("🛑 Shutting down UI SDK...")
            
    logger.info("🛑 Database connection closed.")

# Create FastAPI app
app = FastAPI(
    title="LangGraph + ADK Hybrid Weather Agent",
    description="Weather agent using LangGraph workflows with ADK infrastructure",
    lifespan=lifespan
)

# Add session middleware
app.middleware("http")(session_middleware)

# Add UI router
app.include_router(ui.router)

# Add ADK endpoint
add_adk_fastapi_endpoint(app, adk_weather_agent, path="/")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "agent_type": "langgraph_adk_hybrid",
        "features": ["langgraph_workflow", "adk_infrastructure", "memory_checkpointing", "streaming_ui"]
    }


if __name__ == "__main__":
    import uvicorn

    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Set GOOGLE_API_KEY environment variable")
        print("   export GOOGLE_API_KEY='your-key-here'")

    port = int(os.getenv("PORT", 8000))
    print(f"\n{'='*80}")
    print(f"🚀 Starting LangGraph + ADK Hybrid Weather Agent")
    print(f"{'='*80}")
    print(f"✅ LangGraph: Complex workflow with state management")
    print(f"✅ ADK: Session management, auth, callbacks")
    print(f"✅ MemorySaver: In-memory session checkpointing")
    print(f"✅ Streaming UI: Real-time component updates")
    print(f"{'='*80}")
    print(f"Running on http://0.0.0.0:{port}")
    print(f"{'='*80}\n")

    uvicorn.run(app, host="0.0.0.0", port=port)
