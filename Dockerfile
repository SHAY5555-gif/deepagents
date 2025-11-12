# Use LangGraph base image
FROM langchain/langgraph-api:3.11

# Add dependencies - copy to parent directory to preserve package structure
ADD . /deps/__outer_default

# Install dependencies from requirements.txt first
RUN pip install -c /api/constraints.txt -r /deps/__outer_default/requirements.txt

# Install the package in editable mode using the actual pyproject.toml
RUN pip install -c /api/constraints.txt -e /deps/__outer_default

# Set environment
ENV LANGSERVE_GRAPHS='{"mcp_agent_async": "/deps/__outer_default/mcp_agent_async.py:agent", "simple_parallel_agent": "/deps/__outer_default/simple_parallel_agent.py:agent", "mcp_agent_example": "/deps/__outer_default/mcp_agent_example.py:agent", "mcp_agent_grok": "/deps/__outer_default/mcp_agent_grok.py:agent", "mcp_agent_grok_fast": "/deps/__outer_default/mcp_agent_grok_fast.py:agent", "mcp_agent_grok_fast_with_retry": "/deps/__outer_default/mcp_agent_grok_fast_with_retry.py:agent", "mcp_agent_bright_data_only": "/deps/__outer_default/mcp_agent_bright_data_only.py:agent"}'

WORKDIR /deps/__outer_default

# Override CMD to run uvicorn directly instead of langgraph up
CMD ["uvicorn", "langgraph_api.server:app", "--host", "0.0.0.0", "--port", "8000"]
