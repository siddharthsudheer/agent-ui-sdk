"""Tools for push_ui_message functionality"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def create_push_ui_message_tool(graph_name: str):
    """Create a push_ui_message tool for LLM agents

    This creates a tool that the LLM can call to trigger UI rendering.
    The graph_name is baked in so the LLM only needs to specify
    component_name and props.

    Args:
        graph_name: The graph name to use for this tool

    Returns:
        A tool function that can be registered with agent frameworks

    Example:
        from google.adk.tools import FunctionTool

        push_ui_tool = create_push_ui_message_tool("my_app")
        agent = LlmAgent(tools=[push_ui_tool])
    """

    def push_ui_message(component_name: str, props: Dict[str, Any]) -> str:
        """Push a UI component to the frontend.

        This tool allows the agent to dynamically render React components
        in the chat interface.

        Args:
            component_name: The name of the component to render (must match
                a component exported from your UI file)
            props: The props to pass to the component (as a dictionary)

        Returns:
            A JSON string confirming the UI message was sent

        Example:
            To show weather information:
            push_ui_message("weather", {"location": "San Francisco", "temp": 72})
        """
        logger.info(f"[push_ui_message] Tool called: component={component_name}, props={props}")
        print(f"[push_ui_message] Tool called: component={component_name}, props={props}")

        # Return JSON payload that the frontend will intercept
        result = {
            "graph_name": graph_name,
            "component_name": component_name,
            "props": props
        }

        logger.info(f"[push_ui_message] Returning result: {result}")
        print(f"[push_ui_message] Returning result: {result}")

        return json.dumps(result)

    # Set metadata for the tool
    push_ui_message.__name__ = "push_ui_message"
    push_ui_message.__doc__ = f"""Push a UI component to the frontend for graph '{graph_name}'.

    This tool allows you to dynamically render React components in the chat interface.

    Args:
        component_name: The name of the component to render
        props: The props to pass to the component (as a dictionary)

    Returns:
        A JSON string confirming the UI message was sent
    """

    return push_ui_message


# Generic version that requires graph_name each time
def push_ui_message_generic(
    graph_name: str,
    component_name: str,
    props: Dict[str, Any]
) -> str:
    """Push a UI component to the frontend (generic version).

    This is a generic version that requires specifying the graph_name
    each time. Use create_push_ui_message_tool() for a version with
    graph_name baked in.

    Args:
        graph_name: The graph/app name
        component_name: The name of the component to render
        props: The props to pass to the component

    Returns:
        A JSON string containing the UI message payload
    """
    logger.info(f"push_ui_message_generic called: {graph_name}/{component_name} with props: {props}")

    result = {
        "graph_name": graph_name,
        "component_name": component_name,
        "props": props
    }

    return json.dumps(result)
