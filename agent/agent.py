"""Shared State feature."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()
import json
from enum import Enum
from typing import Dict, List, Any, Optional
from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

# ADK imports
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.sessions import InMemorySessionService, Session
from google.adk.runners import Runner
from google.adk.events import Event, EventActions
from google.adk.tools import FunctionTool, ToolContext
from google.genai.types import Content, Part , FunctionDeclaration
from google.adk.models import LlmResponse, LlmRequest
from google.genai import types

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

# Import the UI SDK
from sidd_agent_ui_sdk import UIManager


class ProverbsState(BaseModel):
    """List of the proverbs being written."""
    proverbs: list[str] = Field(
        default_factory=list,
        description='The list of already written proverbs',
    )


def set_proverbs(
  tool_context: ToolContext,
  new_proverbs: list[str]
) -> Dict[str, str]:
    """
    Set the list of provers using the provided new list.

    Args:
        "new_proverbs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The new list of proverbs to maintain",
        }

    Returns:
        Dict indicating success status and message
    """
    try:
        # Put this into a state object just to confirm the shape
        new_state = { "proverbs": new_proverbs}
        tool_context.state["proverbs"] = new_state["proverbs"]
        return {"status": "success", "message": "Proverbs updated successfully"}

    except Exception as e:
        return {"status": "error", "message": f"Error updating proverbs: {str(e)}"}



def get_weather(tool_context: ToolContext, location: str) -> Dict[str, str]:
    """Get the weather for a given location. Ensure location is fully spelled out."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[get_weather] Called with location: {location}")
    return {"status": "success", "message": f"The weather in {location} is sunny."}



def on_before_agent(callback_context: CallbackContext):
    """
    Initialize proverbs state if it doesn't exist.
    """

    if "proverbs" not in callback_context.state:
        # Initialize with default recipe
        default_proverbs =     []
        callback_context.state["proverbs"] = default_proverbs


    return None




# --- Define the Callback Function ---
#  modifying the agent's system prompt to incude the current state of the proverbs list
def before_model_modifier(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Inspects/modifies the LLM request or skips the call."""
    agent_name = callback_context.agent_name
    if agent_name == "ProverbsAgent":
        proverbs_json = "No proverbs yet"
        if "proverbs" in callback_context.state and callback_context.state["proverbs"] is not None:
            try:
                proverbs_json = json.dumps(callback_context.state["proverbs"], indent=2)
            except Exception as e:
                proverbs_json = f"Error serializing proverbs: {str(e)}"
        # --- Modification Example ---
        # Add a prefix to the system instruction
        original_instruction = llm_request.config.system_instruction or types.Content(role="system", parts=[])
        prefix = f"""You are a helpful assistant for maintaining a list of proverbs.
        This is the current state of the list of proverbs: {proverbs_json}
        When you modify the list of proverbs (wether to add, remove, or modify one or more proverbs), use the set_proverbs tool to update the list."""
        # Ensure system_instruction is Content and parts list exists
        if not isinstance(original_instruction, types.Content):
            # Handle case where it might be a string (though config expects Content)
            original_instruction = types.Content(role="system", parts=[types.Part(text=str(original_instruction))])
        if not original_instruction.parts:
            original_instruction.parts.append(types.Part(text="")) # Add an empty part if none exist

        # Modify the text of the first part
        modified_text = prefix + (original_instruction.parts[0].text or "")
        original_instruction.parts[0].text = modified_text
        llm_request.config.system_instruction = original_instruction



    return None






# --- Define the Callback Function ---
def simple_after_model_modifier(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """Control when to end agent invocation - allow tool calls to complete"""
    agent_name = callback_context.agent_name

    if agent_name == "ProverbsAgent":
        if llm_response.content and llm_response.content.parts:
            # Check if there are any function calls in the response
            has_function_calls = False
            has_text = False

            for part in llm_response.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    has_function_calls = True
                if hasattr(part, 'text') and part.text:
                    has_text = True

            # Only end invocation if we have text response and NO function calls
            # This allows the agent to make multiple tool calls
            if has_text and not has_function_calls:
                print(f"[Callback] Ending invocation: has_text={has_text}, has_function_calls={has_function_calls}")
                callback_context._invocation_context.end_invocation = True
            else:
                print(f"[Callback] Continuing: has_text={has_text}, has_function_calls={has_function_calls}")

    return None


# Initialize UI Manager
ui = UIManager(graph_name="proverbs_app", ui_path="./ui/index.tsx")

proverbs_agent = LlmAgent(
        name="ProverbsAgent",
        model="gemini-2.5-flash",
        instruction=f"""
        When a user asks you to do anything regarding proverbs, you MUST use the set_proverbs tool.

        IMPORTANT RULES ABOUT PROVERBS AND THE SET_PROVERBS TOOL:
        1. Always use the set_proverbs tool for any proverbs-related requests
        2. Always pass the COMPLETE LIST of proverbs to the set_proverbs tool. If the list had 5 proverbs and you removed one, you must pass the complete list of 4 remaining proverbs.
        3. You can use existing proverbs if one is relevant to the user's request, but you can also create new proverbs as required.
        4. Be creative and helpful in generating complete, practical proverbs
        5. After using the tool, provide a brief summary of what you create, removed, or changed        7.

        Examples of when to use the set_proverbs tool:
        - "Add a proverb about soap" → Use tool with an array containing the existing list of proverbs with the new proverb about soap at the end.
        - "Remove the first proverb" → Use tool with an array containing the all of the existing proverbs except the first one"
        - "Change any proverbs about cats to mention that they have 18 lives" → If no proverbs mention cats, do not use the tool. If one or more proverbs do mention cats, change them to mention cats having 18 lives, and use the tool with an array of all of the proverbs, including ones that were changed and ones that did not require changes.

        Do your best to ensure proverbs plausibly make sense.


        IMPORTANT RULES ABOUT WEATHER:
        When the user asks about weather, you MUST call BOTH tools in the SAME turn (parallel):
        - get_weather(location="City Name")
        - push_ui_message(component_name="weather", props={{"location": "City Name", "temp": 55}})

        Do NOT respond with text until AFTER both tools complete. Only respond ONCE at the end.

        Examples:
        User: "What's the weather in San Francisco?"
        Actions in single turn:
        - Call get_weather(location="San Francisco")
        - Call push_ui_message(component_name="weather", props={{"location": "San Francisco", "temp": 72}})
        Then respond ONCE: "I've fetched the weather for San Francisco and displayed it above."
        """,
        tools=[set_proverbs, get_weather, ui.tool],
        before_agent_callback=on_before_agent,
        before_model_callback=before_model_modifier
    )

# Create ADK middleware agent instance
adk_proverbs_agent = ADKAgent(
    adk_agent=proverbs_agent,
    app_name="proverbs_app",
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True
)

# Create FastAPI app with UI lifespan
app = FastAPI(title="ADK Middleware Proverbs Agent", lifespan=ui.lifespan)

# Add the UI router (for serving bundled UI components)
app.include_router(ui.router)

# Add the ADK endpoint
add_adk_fastapi_endpoint(app, adk_proverbs_agent, path="/")

if __name__ == "__main__":
    import os
    import uvicorn

    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Warning: GOOGLE_API_KEY environment variable not set!")
        print("   Set it with: export GOOGLE_API_KEY='your-key-here'")
        print("   Get a key from: https://makersuite.google.com/app/apikey")
        print()

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
