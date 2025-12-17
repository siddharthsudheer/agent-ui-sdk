# Copyright 2025 Google LLC
# ... (Keep License Header) ...

import json
import logging
from typing import AsyncGenerator, Union, Any, List

from google.genai import types
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from pydantic import ConfigDict
from typing_extensions import override

from google.adk.events import Event
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext

logger = logging.getLogger(__name__)

def _get_last_human_message(events: list[Event], agent_name: str) -> list[HumanMessage]:
    """
    Extracts the last VALID human message.
    - Stops if it hits an Agent message (turn is over).
    - Skips User events with no text (UI events/pings).
    """
    for event in reversed(events):
        if event.author == agent_name:
            return []

        if event.author == 'user':
            if event.content and event.content.parts:
                part = event.content.parts[0]
                # Check if text exists and is not empty
                if part.text and part.text.strip():
                    return [HumanMessage(content=part.text)]
                # Ignore empty UI events
                continue
            
    return []

class LangGraphAgent(BaseAgent):
    """
    Official implementation supporting Tool-Based Generative UI.
    Requires 'available: "frontend"' in the React useCopilotAction hook.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    graph: CompiledStateGraph
    instruction: str = ''

    @override
    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        
        # --- GUARD CLAUSE ---
        if ctx.session.events:
            last_event = ctx.session.events[-1]
            if last_event.author == self.name:
                return

        # 1. Setup Configuration
        config: RunnableConfig = {'configurable': {'thread_id': ctx.session.id}}

        # 2. Input Logic
        messages = self._get_messages(ctx.session.events)
        
        if not messages:
            return

        if self.instruction:
            state = await self.graph.aget_state(config)
            if not state.values:
                messages.insert(0, SystemMessage(content=self.instruction))

        # 3. Streaming Logic
        # We map Tool Call IDs to track them between "Call" and "Result" events
        # Note: In streaming, matching these perfectly can be tricky. 
        # We rely on the fact that LangGraph executes sequentially.
        current_tool_calls = {}

        async for event in self.graph.astream_events(
            {'messages': messages}, config, version="v2"
        ):
            event_type = event["event"]
            event_data = event["data"]

            # --- Case A: Model Decides to Call a Tool ---
            if event_type == "on_chat_model_stream":
                # We generally wait for 'on_chat_model_end' for the full tool call
                pass

            elif event_type == "on_chat_model_end":
                output = event_data.get("output")
                
                if output and isinstance(output, AIMessage):
                    # 1. Handle Text Content
                    if isinstance(output.content, str) and output.content.strip():
                         yield self._create_text_event(ctx, output.content)
                    
                    elif isinstance(output.content, list):
                        for block in output.content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    text_val = block.get("text", "")
                                    if text_val.strip():
                                        yield self._create_text_event(ctx, text_val)

                    # 2. Handle Tool Calls (The Official Way)
                    # We Emit 'function_call' to trigger the UI "Calling..." state
                    if output.tool_calls:
                        for tool_call in output.tool_calls:
                            t_id = tool_call["id"]
                            t_name = tool_call["name"]
                            t_args = tool_call["args"]
                            
                            # Store mapping for the response later
                            current_tool_calls[t_name] = t_id

                            yield Event(
                                invocation_id=ctx.invocation_id,
                                author=self.name,
                                branch=ctx.branch,
                                content=types.Content(
                                    role='model',
                                    parts=[
                                        types.Part(
                                            function_call=types.FunctionCall(
                                                id=t_id,
                                                name=t_name,
                                                args=t_args
                                            )
                                        )
                                    ]
                                )
                            )

            # --- Case B: Tool Execution Finished ---
            elif event_type == "on_tool_end":
                tool_output = event_data.get("output")
                tool_name = event["name"]
                
                # Attempt to find the matching Call ID
                # LangGraph v2 often doesn't pass the Call ID in 'on_tool_end'
                # We assume the last seen call for this tool name is the one responding.
                call_id = current_tool_calls.get(tool_name, "unknown_id")
                
                # Serialize Output
                final_output = tool_output
                if hasattr(tool_output, "content"): 
                    final_output = tool_output.content
                
                if not isinstance(final_output, (str, dict, list, int, float, bool)):
                    final_output = str(final_output)

                # Emit Result
                yield Event(
                    invocation_id=ctx.invocation_id,
                    author=self.name,
                    branch=ctx.branch,
                    content=types.Content(
                        role='function',
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    id=call_id, # Must match the function_call ID
                                    name=tool_name,
                                    response={'result': final_output} 
                                )
                            )
                        ]
                    )
                )

    def _create_text_event(self, ctx, text: str) -> Event:
        return Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(
                role='model',
                parts=[types.Part.from_text(text=text)],
            ),
        )

    def _get_messages(
        self, events: list[Event]
    ) -> list[Union[HumanMessage, AIMessage, SystemMessage]]:
        if self.graph.checkpointer:
            return _get_last_human_message(events, self.name)
        else:
            return self._get_conversation_with_agent(events)

    def _get_conversation_with_agent(
        self, events: list[Event]
    ) -> list[Union[HumanMessage, AIMessage]]:
        messages = []
        for event in events:
            if not event.content or not event.content.parts:
                continue
            part = event.content.parts[0]
            text = part.text if part.text else "..."
            
            if event.author == 'user':
                messages.append(HumanMessage(content=text))
            elif event.author == self.name:
                messages.append(AIMessage(content=text))
        return messages