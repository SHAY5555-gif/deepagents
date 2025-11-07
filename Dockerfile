# Use LangGraph base image
FROM langchain/langgraph-api:3.11

# Add dependencies
ADD . /deps/__outer_default/src
RUN set -ex && \
    for line in '[project]' \
                'name = "default"' \
                'version = "0.1"' \
                '[tool.setuptools.package-data]' \
                '"*" = ["**/*"]'; do \
        echo "$line" >> /deps/__outer_default/pyproject.toml; \
    done

# Install dependencies from requirements.txt first
RUN pip install -c /api/constraints.txt -r /deps/__outer_default/src/requirements.txt

# Install the package in editable mode
RUN pip install -c /api/constraints.txt -e /deps/*

# Set environment
ENV LANGSERVE_GRAPHS='{"mcp_agent_async": "/deps/__outer_default/src/mcp_agent_async.py:agent", "simple_parallel_agent": "/deps/__outer_default/src/simple_parallel_agent.py:agent", "mcp_agent_example": "/deps/__outer_default/src/mcp_agent_example.py:agent", "mcp_agent_grok": "/deps/__outer_default/src/mcp_agent_grok.py:agent", "mcp_agent_grok_fast": "/deps/__outer_default/src/mcp_agent_grok_fast.py:agent", "mcp_agent_grok_fast_with_retry": "/deps/__outer_default/src/mcp_agent_grok_fast_with_retry.py:agent"}'

WORKDIR /deps/__outer_default/src

# Override CMD to run uvicorn directly instead of langgraph up
CMD ["uvicorn", "langgraph_api.server:app", "--host", "0.0.0.0", "--port", "8000"]
