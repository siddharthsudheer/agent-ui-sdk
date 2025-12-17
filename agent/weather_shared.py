"""Shared components for the Weather Agent."""

import os
import random
import logging
from typing import TypedDict, Annotated, Literal
import json
import sqlite3 # <--- ADDED

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver # <--- ADDED

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import tool
import asyncio
from sidd_agent_ui_sdk import UIManager

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize UI Manager
ui = UIManager(graph_name="weather_app", ui_path="./ui/index.tsx")


# ============================================================================
# State Definition
# ============================================================================

class WeatherState(TypedDict):
    """State for the weather agent graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    weather_location: str | None
    weather_temp: int | None


# ============================================================================
# Tools
# ============================================================================

@tool
def push_ui_message(component_name: str, props: dict) -> dict:
    """Push a UI message to render a component.

    Args:
        component_name: Name of the component to render (e.g., "weather")
        props: Props to pass to the component (e.g., {"location": "Boston", "temp": 55})

    Returns:
        Dict with graph_name, component_name, and props
    """
    logger.info(f"[push_ui_message] component={component_name}, props={props}")

    result = {
        "graph_name": "weather_app",
        "component_name": component_name,
        "props": props
    }

    logger.info(f"[push_ui_message] result={result}")
    return result


@tool
def get_weather(location: str) -> dict:
    """Get weather information for a location.

    Args:
        location: The city name

    Returns:
        Dict with location and temperature
    """
    logger.info(f"[get_weather] location={location}")

    # Mock weather data
    temp = random.randint(45, 70)

    result = {
        "location": location,
        "temperature": temp,
        "status": "success"
    }

    logger.info(f"[get_weather] result={result}")
    return result


# ============================================================================
# Agent Nodes
# ============================================================================

async def weather_agent(state: WeatherState) -> WeatherState:
    """Main weather agent that processes user requests."""
    logger.info("="*80)
    logger.info("WEATHER AGENT NODE")
    logger.info("="*80)

    messages = state["messages"]
    logger.info(f"Processing {len(messages)} messages")

    # Initialize LLM with tools and system instruction
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite-preview-09-2025",
        temperature=0,
    )
    # llm = ChatGoogleGenerativeAI(
    #     model="gemini-2.0-flash-exp",
    #     temperature=0.7,
    # )
    # llm = ChatAnthropic(
    #     temperature=0,
    #     model_name="claude-sonnet-4-5-20250929",
    #     timeout=None,
    #     stop=None
    # )

    # Add system instruction to prevent city confusion
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        system_msg = SystemMessage(content="""You are a weather assistant.
When the user asks about a city's weather:
1. Call get_weather(location="CityName") to get the current data
2. Call push_ui_message with the weather data
3. Respond ONLY about the city the user JUST asked about - do NOT mention previous cities

IMPORTANT: Always respond about the CURRENT query, not previous queries in the conversation.""")
        messages = [system_msg] + messages

    # Hybrid approach: streaming for live updates, tool for chat history
    tools = [get_weather, push_ui_message]

    # 3. DYNAMIC CONFIGURATION LOGIC
    # Default: Model calls tools if it wants to ("AUTO")
    tool_mode = "AUTO" 

    # Check the history to see if we are done with tools
    if messages:
        last_msg = messages[-1]
        
        # If the last message was a ToolMessage (the result of a tool)
        if hasattr(last_msg, 'tool_call_id'):
            
            # We need to determine WHICH tool just finished. 
            # In LangChain, we have to look back at the AIMessage preceding this ToolMessage
            # to find the name, OR verify the artifact.
            
            # Heuristic: If we see a ToolMessage, checking if the graph has done its job.
            # Since your flow is Get Weather -> Push UI -> Done, we can simply check
            # if 'push_ui_message' was the tool that just ran.
            
            # Find the AIMessage that triggered this tool
            # (We look at the second to last message)
            if len(messages) >= 2:
                preceding_ai_msg = messages[-2]
                if hasattr(preceding_ai_msg, 'tool_calls'):
                    for tc in preceding_ai_msg.tool_calls:
                        if tc['name'] == 'push_ui_message':
                            logger.info("🛑 Detected push_ui_message completion. Forcing mode=NONE")
                            tool_mode = "NONE"

    # 4. Bind tools with the DYNAMIC configuration
    # 'mode': 'NONE' tells the API: "Do NOT generate a tool call, you MUST generate text."
    llm_with_tools = llm.bind_tools(
        tools, 
        tool_config={
            "function_calling_config": {
                "mode": tool_mode
            }
        }
    )

    # Call LLM
    response = await llm_with_tools.ainvoke(messages)
    
    # STREAMING (Phase 2): Emit skeleton immediately!
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call['name'] == 'get_weather':
                location = tool_call['args'].get('location', 'Unknown')
                # Generate stable ID based on location
                component_id = f"weather-{location.lower()}"
                logger.info(f"📡 STREAMING: Skeleton for {location} (id={component_id})")
                # ============================================================================
                # UI SDK Emit Loading
                # ============================================================================
                ui.emit("weather", {"location": location, "temp": "Loading..."}, id=component_id)
                await asyncio.sleep(0.1)

    logger.info(f"Agent response: {response}")
    logger.info("="*80)

    return {"messages": [response]}


async def tool_handler(state: WeatherState) -> WeatherState:
    """Execute tools and update streaming UI with real data."""
    messages = state["messages"]
    last_message = messages[-1]

    # Execute tools (both get_weather and push_ui_message)
    tool_node = ToolNode([get_weather, push_ui_message])
    result = tool_node.invoke(state)
    
    # STREAMING: Update with real data after tool completes (Phase 2: merge!)
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call['name'] == 'get_weather':
                # Use SAME location from tool args (not result) to ensure ID matches skeleton!
                original_location = tool_call['args'].get('location', 'Unknown')
                component_id = f"weather-{original_location.lower()}"

                # Parse the tool result to get real weather data
                for msg in result['messages']:
                    if hasattr(msg, 'content') and msg.content:
                        try:
                            weather_data = json.loads(msg.content)
                            logger.info(f"📡 STREAMING: Merging real data for {original_location} (id={component_id})")
                            # ============================================================================
                            # UI SDK Emit Data and Merge Component
                            # ============================================================================
                            ui.emit("weather", {
                                "location": weather_data['location'],  # Display normalized name
                                "temp": weather_data['temperature']
                            }, id=component_id, merge=True)
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            logger.error(f"Failed to parse tool result: {e}")

    return result


def should_continue(state: WeatherState) -> Literal["tools", "end"]:
    """Determine if we should continue to tools or end."""
    messages = state["messages"]
    last_message = messages[-1]

    # If there are tool calls, continue to tools
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info(f"→ Routing to tools ({len(last_message.tool_calls)} calls)")
        return "tools"

    # Otherwise, end
    logger.info("→ Routing to END")
    return "end"


# ============================================================================
# Graph Construction
# ============================================================================

def create_weather_graph(checkpointer = None):
    """
    Create the weather agent graph.
    
    Args:
        checkpointer: An initialized LangGraph checkpointer.
                      MUST be an AsyncSqliteSaver instance for production.
    """

    workflow = StateGraph(WeatherState)

    workflow.add_node("agent", weather_agent)
    workflow.add_node("tools", tool_handler)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        }
    )
    workflow.add_edge("tools", "agent")

    # Fallback to Memory if no checkpointer provided (e.g. for testing)
    if checkpointer is None:
        logger.warning("⚠️ No checkpointer provided. Using ephemeral MemorySaver.")
        checkpointer = MemorySaver()

    # Compile with the provided checkpointer
    graph = workflow.compile(checkpointer=checkpointer)

    return graph
