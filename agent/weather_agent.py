"""Custom ADK Weather Agent with Full Granular Control."""

from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from google.genai import Client
from google.genai import types
from fastapi import FastAPI, Request
from sidd_agent_ui_sdk import UIManager
import os
import logging
import random
import json
from typing import AsyncGenerator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize UI Manager
ui = UIManager(graph_name="weather_app", ui_path="./ui/index.tsx")


# ============================================================================
# Tool Implementation
# ============================================================================

def get_weather(location: str) -> dict:
    """Get weather information for a location."""
    logger.info(f"[get_weather] location={location}")
    temp = random.randint(45, 85)

    result = {
        "location": location,
        "temperature": temp,
        "status": "success"
    }

    logger.info(f"[get_weather] result={result}")
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
# Custom Weather Agent with Full Control
# ============================================================================

class CustomWeatherAgent(BaseAgent):
    """
    Custom ADK agent with full granular control over execution.

    This agent explicitly controls:
    1. When to call the LLM
    2. When to emit skeleton (streaming)
    3. When to execute functions
    4. When to emit merge (streaming)
    5. When to generate final response

    No callbacks needed - we control everything!
    """

    name: str = "CustomWeatherAgent"
    description: str = "Weather agent with streaming UI and clean execution flow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Initialize Google GenAI Client (use object.__setattr__ for Pydantic models)
        object.__setattr__(self, 'client', Client(api_key=os.getenv("GOOGLE_API_KEY")))
        object.__setattr__(self, 'model_id', "gemini-2.0-flash-exp")

    def _get_weather_tool_declaration(self):
        """Get the function declaration for get_weather."""
        return types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="get_weather",
                description="Get current weather information for a city",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "location": types.Schema(
                            type=types.Type.STRING,
                            description="The city name"
                        )
                    },
                    required=["location"]
                )
            )
        ])

    async def _run_async_impl(self, context: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Main execution loop with full granular control.

        Flow:
        1. Get user message
        2. Call LLM with tools
        3. If function_call → emit skeleton, execute, emit merge
        4. Call LLM again with function result
        5. Yield final text response
        """
        try:
            # DON'T override the session! The middleware already set it to 'demo-session'
            # ADK's context.session.id is an INTERNAL session ID that doesn't match the frontend
            # The frontend connects with session=demo-session, so we must emit to that session
            logger.info(f"🔐 Using middleware session (NOT overriding with ADK session)")

            # Get the user's message from InvocationContext
            user_content = context.user_content
            # Extract text from Content object
            user_message = user_content.parts[0].text if user_content and user_content.parts else ""
            logger.info(f"📨 User message: {user_message}")

            # Build conversation history
            contents = self._build_conversation_history(context)
            contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

            # STEP 1: Call LLM with tools
            logger.info("🤖 Calling LLM with tools...")
            config = types.GenerateContentConfig(
                tools=[self._get_weather_tool_declaration()],
                temperature=0.7
            )
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=config
            )

            # Check if LLM wants to call a function
            if response.candidates[0].content.parts:
                first_part = response.candidates[0].content.parts[0]

                if hasattr(first_part, 'function_call') and first_part.function_call:
                    func_call = first_part.function_call
                    logger.info(f"🔧 Function call detected: {func_call.name}")

                    if func_call.name == "get_weather":
                        location = func_call.args.get("location", "Unknown")
                        component_id = f"weather-{location.lower()}"

                        # STEP 2: Emit skeleton (streaming)
                        logger.info(f"📡 Emitting skeleton for {location}")
                        ui.emit("weather", {
                            "location": location,
                            "temp": "Loading..."
                        }, id=component_id)

                        # Yield control to allow SSE stream to flush the skeleton event
                        import asyncio
                        await asyncio.sleep(0.1)  # Small delay to ensure event is sent

                        # STEP 3: Execute function
                        logger.info(f"⚙️ Executing get_weather({location})")
                        weather_data = get_weather(location)

                        # STEP 4: Emit merge (streaming)
                        logger.info(f"🔄 Emitting merge for {location}")
                        ui.emit("weather", {
                            "location": weather_data["location"],
                            "temp": weather_data["temperature"]
                        }, id=component_id, merge=True)

                        # STEP 5: Add function call to history
                        contents.append(types.Content(
                            role="model",
                            parts=[types.Part(function_call=func_call)]
                        ))

                        # STEP 6: Add function response to history
                        func_response = types.FunctionResponse(
                            name="get_weather",
                            response=weather_data
                        )
                        contents.append(types.Content(
                            role="user",
                            parts=[types.Part(function_response=func_response)]
                        ))

                        # STEP 7: Call LLM again for final response
                        logger.info("🤖 Calling LLM for final response...")
                        final_response = self.client.models.generate_content(
                            model=self.model_id,
                            contents=contents,
                            config=types.GenerateContentConfig(temperature=0.7)
                        )

                        # Extract text
                        final_text = final_response.text
                        logger.info(f"✅ Final response: {final_text}")

                        # STEP 8: Yield final response as Event
                        yield Event(
                            author=self.name,
                            content=types.Content(role="model", parts=[types.Part(text=final_text)])
                        )
                        return

            # No function call - direct response
            text = response.text
            logger.info(f"✅ Direct response: {text}")
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=text)])
            )

        except Exception as e:
            logger.error(f"❌ Error in agent execution: {e}", exc_info=True)
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=f"Sorry, an error occurred: {str(e)}")])
            )

    def _build_conversation_history(self, context: InvocationContext) -> list:
        """Build conversation history from context."""
        # System instruction as first message
        return [
            types.Content(
                role="user",
                parts=[types.Part(text="""You are a weather assistant. When asked about weather:
1. ALWAYS call get_weather(location) FIRST
2. Then provide a conversational response using the actual temperature from the function result
3. Be concise and accurate""")]
            )
        ]


# ============================================================================
# FastAPI Setup
# ============================================================================

# Create custom agent instance
weather_agent = CustomWeatherAgent()

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
    return {"status": "ok", "agent": "custom"}


if __name__ == "__main__":
    import uvicorn
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Set GOOGLE_API_KEY environment variable")
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Starting Custom Weather Agent on port {port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
