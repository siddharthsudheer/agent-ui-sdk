"""ADK Weather Agent using LlmAgent with CopilotKit Integration."""

from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI, Request
from sidd_agent_ui_sdk import UIManager
import os
import logging
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize UI Manager
ui = UIManager(graph_name="weather_app", ui_path="./ui/index.tsx")


# ============================================================================
# Tool Implementation
# ============================================================================

def get_weather(tool_context: ToolContext, location: str) -> dict:
    """Get current weather information for a city.

    Call this tool when the user asks about weather in any location.
    This will return the current temperature for the specified city.

    Args:
        location: The city name (e.g., "Boston", "San Francisco")

    Returns:
        Dictionary with status, location, and temperature keys.
        Example: {"status": "success", "location": "Boston", "temperature": 72}
    """
    logger.info(f"[get_weather] location={location}")

    # Generate random temperature
    temp = random.randint(45, 70)
    
    # STREAMING: Emit skeleton immediately
    component_id = f"weather-{location.lower()}"
    logger.info(f"📡 Emitting skeleton for {location}")
    ui.emit("weather", {
        "location": location,
        "temp": "Loading..."
    }, id=component_id)

    result = {
        "status": "success",
        "location": location,
        "temperature": temp
    }

    logger.info(f"[get_weather] result={result}")

    # Emit merge with real data
    logger.info(f"🔄 Emitting merge for {location}")
    ui.emit("weather", {
        "location": location,
        "temp": temp
    }, id=component_id, merge=True)

    return result


def push_ui_message(tool_context: ToolContext, component_name: str, props: dict) -> dict:
    """Push a UI component to render in the chat.

    Call this tool to display a visual component in the chat interface.
    This should be called AFTER get_weather to show the weather card in chat history.

    Args:
        component_name: Name of the component to render (e.g., "weather")
        props: Props to pass to the component (e.g., {"location": "Boston", "temp": 72})

    Returns:
        Dictionary with status, graph_name, component_name, and props keys.
        Example: {"status": "success", "graph_name": "weather_app", ...}
    """
    logger.info(f"[push_ui_message] component={component_name}, props={props}")

    result = {
        "status": "success",
        "graph_name": "weather_app",
        "component_name": component_name,
        "props": props
    }

    logger.info(f"[push_ui_message] result={result}")
    return result


# ============================================================================
# Session Middleware
# ============================================================================

async def session_middleware(request: Request, call_next):
    """Extract session ID and set it for streaming."""
    session_id = (
        request.headers.get("X-Session-ID") or
        request.query_params.get("session") or
        "demo-session"
    )
    ui.set_session(session_id)
    logger.debug(f"Session set: {session_id}")
    response = await call_next(request)
    return response


# ============================================================================
# ADK Agent Setup
# ============================================================================

# Create LlmAgent with tools
weather_agent = LlmAgent(
    name="WeatherAgent",
    model="gemini-2.0-flash-exp",
    instruction="""You are a weather assistant that provides weather information with visual components.

IMPORTANT WORKFLOW:
When a user asks about weather, you MUST follow these steps IN ORDER:

1. Call get_weather(location="City Name") to fetch the temperature
2. Wait for the result
3. Call push_ui_message(component_name="weather", props={"location": "City Name", "temp": <temperature>})
   using the ACTUAL temperature from step 1
4. Provide a brief, conversational response

Example:
User: "What's the weather in Boston?"

Step 1: Call get_weather(location="Boston")
Step 2: Receive {"status": "success", "location": "Boston", "temperature": 67}
Step 3: Call push_ui_message(component_name="weather", props={"location": "Boston", "temp": 67})
Step 4: Respond: "The weather in Boston is 67°F. I've displayed the weather card above."

RULES:
- ALWAYS call both tools for every weather request
- Use the ACTUAL temperature from get_weather in push_ui_message
- Keep text responses concise and natural
- Do not make up temperatures - use only what get_weather returns
""",
    tools=[get_weather, push_ui_message],
)

# Wrap in ADK middleware
adk_weather_agent = ADKAgent(
    adk_agent=weather_agent,
    app_name="weather_app",
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True
)

# Create FastAPI app
app = FastAPI(lifespan=ui.lifespan)

# Add session middleware
app.middleware("http")(session_middleware)

# Add UI router
app.include_router(ui.router)

# Add ADK agent endpoint
add_adk_fastapi_endpoint(app, adk_weather_agent, path="/")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "agent": "adk_llm"}


if __name__ == "__main__":
    import uvicorn
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Set GOOGLE_API_KEY environment variable")
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Starting ADK Weather Agent (LlmAgent) on port {port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
