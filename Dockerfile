# ============================================
# Stage 1: Base image with cached dependencies
# ============================================
FROM langchain/langgraph-api:3.11 as dependencies

# Set working directory for dependency installation
WORKDIR /tmp

# Copy ONLY dependency files first (maximize cache hit rate)
COPY requirements.txt pyproject.toml ./

# Install dependencies with optimizations:
# --no-cache-dir: Don't store cache (reduces image size)
# --compile: Pre-compile Python files (faster startup)
# This layer will be cached unless requirements change
RUN pip install --no-cache-dir --compile \
    -c /api/constraints.txt \
    -r requirements.txt

# ============================================
# Stage 2: Application code
# ============================================
FROM dependencies as application

# Create application directory
WORKDIR /deps/__outer_default

# Copy application code (this changes frequently, so it's last)
# Using COPY instead of ADD for better caching behavior
COPY . .

# Install the package in editable mode
# This is fast because dependencies are already installed
RUN pip install --no-cache-dir --compile \
    -c /api/constraints.txt \
    -e .

# Set environment variables for LangGraph agents
ENV LANGSERVE_GRAPHS='{"mcp_agent_async": "/deps/__outer_default/mcp_agent_async.py:agent", "simple_parallel_agent": "/deps/__outer_default/simple_parallel_agent.py:agent", "mcp_agent_example": "/deps/__outer_default/mcp_agent_example.py:agent", "mcp_agent_grok": "/deps/__outer_default/mcp_agent_grok.py:agent", "mcp_agent_grok_fast": "/deps/__outer_default/mcp_agent_grok_fast.py:agent", "mcp_agent_grok_fast_with_retry": "/deps/__outer_default/mcp_agent_grok_fast_with_retry.py:agent", "mcp_agent_bright_data_only": "/deps/__outer_default/mcp_agent_bright_data_only.py:agent", "mcp_agent_bright_data_glm": "/deps/__outer_default/mcp_agent_bright_data_glm.py:agent"}'

# Python optimizations for faster startup
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Health check (optional)
# Note: LangGraph API typically exposes health checks at /health or /ok
# If your endpoint is different, update the URL below
# Uncomment if you want Docker health checks:
# HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
#     CMD python -c "import httpx; httpx.get('http://localhost:8000/ok', timeout=5.0)" || exit 1

# Run uvicorn with optimized settings
CMD ["uvicorn", "langgraph_api.server:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--no-access-log"]
