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
# Updated paths to match actual file locations in agents/ folder
ENV LANGSERVE_GRAPHS='{"genius_lyrics": "/deps/__outer_default/agents/zamar/genius_lyrics_agent.py:agent", "cerebras_brightdata_genius": "/deps/__outer_default/agents/cerebras_brightdata_genius.py:agent", "cerebras_zamar": "/deps/__outer_default/agents/zamar/cerebras_zamar.py:agent", "gemini3_flash": "/deps/__outer_default/agents/gemini3_flash_brightdata_genius.py:agent", "browser_agent": "/deps/__outer_default/agents/zamar/cerebras_browser_agent.py:agent"}'

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
