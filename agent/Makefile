.PHONY: run install run-multi run-single run-langgraph test-langgraph

install:
	uv sync

# Run the single-agent ADK version (default)
run:
# 	uv run python3 weather_agent.py
	uv run python3 langgraph_adk_weather.py

# Run the multi-agent ADK version
run-multi:
	uv run python3 multi_agent_weather.py

# Run the single-agent version (alias)
run-single:
	uv run python3 weather_agent.py

# Run the LangGraph version
run-langgraph:
	uv run python3 langgraph_weather.py

run-adk:
	uv run python3 adk_weather.py

# Test LangGraph standalone (without server)
test-langgraph:
	uv run python3 langgraph_weather.py --test