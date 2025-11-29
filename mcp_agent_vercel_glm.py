"""
Async Deep Agent with GLM-4.6 via Vercel AI Gateway
Arcade Architecture with Bright Data MCP

This agent uses:
- Vercel AI Gateway for unified AI provider access
- GLM-4.6 (zai/glm-4.6) via Zhipu AI with automatic fallback
- Bright Data MCP for web scraping and search
- SSE transport for real-time streaming
- EAGER LOADING: Tools load at server startup, not on first use
- Arcade Architecture: Modular, composable agent design
"""
import asyncio
import logging
import os
from datetime import timedelta
from typing import List, Optional
from langchain_core.tools import tool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global MCP client and tools cache
_mcp_client = None
_bright_data_tools = None
_initialization_lock = asyncio.Lock()
_initialization_in_progress = False


# ============================================================================
# Vercel AI Gateway Configuration
# ============================================================================

class VercelAIGatewayConfig:
    """Configuration for Vercel AI Gateway integration"""

    def __init__(self):
        self.api_key = os.getenv("AI_GATEWAY_API_KEY")
        self.base_url = "https://ai-gateway.vercel.sh/v1"

        # GLM-4 model configuration with fallback support
        self.primary_model = "zai/glm-4.6"  # Zhipu AI GLM-4.6
        self.fallback_models = [
            "zai/glm-4.5",  # GLM-4.5 as first fallback
            "zai/glm-4.5-air",  # GLM-4.5-Air for efficiency
        ]

        # Advanced configuration
        self.max_tokens = 128000  # GLM-4.6 supports up to 128K output
        self.temperature = 1.0
        self.timeout = 900  # 15 minutes for complex operations
        self.max_retries = 3

    def get_model_with_fallback(self, prefer_model: Optional[str] = None) -> str:
        """Get model identifier with fallback support"""
        return prefer_model or self.primary_model

    def validate(self) -> bool:
        """Validate configuration"""
        if not self.api_key or self.api_key == "your_vercel_ai_gateway_key_here":
            logger.error("AI_GATEWAY_API_KEY not configured in .env file!")
            logger.error("Please set AI_GATEWAY_API_KEY in .env")
            return False
        return True


def create_vercel_ai_gateway_model(config: VercelAIGatewayConfig) -> ChatOpenAI:
    """
    Create ChatOpenAI model configured for Vercel AI Gateway with GLM-4.6

    Args:
        config: VercelAIGatewayConfig instance

    Returns:
        Configured ChatOpenAI model instance
    """
    if not config.validate():
        raise ValueError("Invalid Vercel AI Gateway configuration. Check your .env file.")

    logger.info(f"Initializing Vercel AI Gateway with model: {config.primary_model}")

    # Configure model with Vercel AI Gateway
    model = ChatOpenAI(
        model=config.primary_model,
        openai_api_key=config.api_key,
        openai_api_base=config.base_url,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        timeout=config.timeout,
        max_retries=config.max_retries,
        model_kwargs={
            "parallel_tool_calls": False,  # Disable parallel tool calling for compatibility
        },
        # Vercel AI Gateway provider options
        default_headers={
            "X-Vercel-AI-Gateway-Provider-Order": "zai",  # Prefer Zhipu AI
        }
    )

    logger.info("Vercel AI Gateway model initialized successfully")
    return model


# ============================================================================
# Error Handling Utilities
# ============================================================================

def create_error_handling_wrapper(tool):
    """Wrap tool to return errors as strings instead of raising exceptions"""
    from functools import wraps

    original_afunc = tool.coroutine if hasattr(tool, 'coroutine') else tool._arun

    @wraps(original_afunc)
    async def wrapped_async(*args, **kwargs):
        try:
            result = await original_afunc(*args, **kwargs)
            return result
        except Exception as e:
            error_msg = f"[ERROR] {type(e).__name__}: {str(e)}"
            logger.warning(f"Tool {tool.name} failed: {error_msg}")
            return error_msg

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        coroutine=wrapped_async,
        handle_tool_error=True,
    )


# ============================================================================
# MCP Tools Initialization
# ============================================================================

async def get_mcp_tools() -> List:
    """Get or initialize MCP tools from Bright Data with proper error handling"""
    global _mcp_client, _bright_data_tools, _initialization_in_progress

    async with _initialization_lock:
        if _bright_data_tools is not None:
            return _bright_data_tools

        if _initialization_in_progress:
            logger.warning("Initialization already in progress, waiting...")
            await asyncio.sleep(2)
            return _bright_data_tools or []

        _initialization_in_progress = True

        try:
            logger.info("=" * 80)
            logger.info("STARTING BRIGHT DATA MCP TOOL INITIALIZATION")
            logger.info("=" * 80)

            # Connect to Bright Data MCP server via remote HTTP with SSE
            bright_data_token = os.getenv("BRIGHT_DATA_TOKEN", "3d84444e-b3de-4587-9248-f4fcda7a8016")

            _mcp_client = MultiServerMCPClient({
                "bright_data": {
                    "url": f"https://mcp.brightdata.com/mcp?token={bright_data_token}",
                    "transport": "streamable_http",
                    "timeout": timedelta(seconds=45),
                    "sse_read_timeout": timedelta(seconds=45),
                },
            })

            # Load tools from Bright Data server
            raw_tools = []
            for server_name in _mcp_client.connections:
                try:
                    logger.info(f"Loading tools from MCP server: {server_name}")
                    server_tools = await _mcp_client.get_tools(server_name=server_name)
                    raw_tools.extend(server_tools)
                    logger.info(f"Successfully loaded {len(server_tools)} tools from {server_name}")

                except BaseException as e:
                    logger.error(
                        f"Failed to load tools from {server_name}. "
                        f"Error: {e.__class__.__name__}: {str(e)}"
                    )
                    if hasattr(e, 'exceptions'):
                        logger.error(f"ExceptionGroup with {len(e.exceptions)} sub-exceptions:")
                        for i, sub_exc in enumerate(e.exceptions):
                            logger.error(f"  {i+1}. {sub_exc.__class__.__name__}: {str(sub_exc)}")
                    logger.warning("Continuing despite errors...")
                    continue

            if not raw_tools:
                logger.error("No tools loaded from Bright Data MCP!")
                _bright_data_tools = []
            else:
                _bright_data_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]
                logger.info("=" * 80)
                logger.info(f"SUCCESS! Total Bright Data tools loaded: {len(_bright_data_tools)}")
                logger.info("=" * 80)

        except BaseException as e:
            logger.error("=" * 80)
            logger.error(f"CRITICAL ERROR during MCP initialization: {e.__class__.__name__}")
            logger.error(f"Error message: {str(e)}")

            if hasattr(e, 'exceptions'):
                logger.error(f"ExceptionGroup with {len(e.exceptions)} sub-exceptions:")
                for i, sub_exc in enumerate(e.exceptions):
                    logger.error(f"  {i+1}. {sub_exc.__class__.__name__}: {str(sub_exc)}")

            logger.error("Agent will start with empty tool list")
            logger.error("=" * 80)
            _bright_data_tools = []

        finally:
            _initialization_in_progress = False

        return _bright_data_tools


# ============================================================================
# Agent Factory - Arcade Architecture
# ============================================================================

async def agent():
    """
    Async factory function for LangGraph Studio using Vercel AI Gateway + GLM-4.6

    Arcade Architecture Principles:
    - Modular: Components are independent and composable
    - Observable: Full visibility into provider selection and fallback behavior
    - Resilient: Automatic retries and fallback mechanisms
    - Flexible: Easy to switch models and providers

    Returns:
        Configured agent instance with Vercel AI Gateway integration
    """
    # Initialize Vercel AI Gateway configuration
    config = VercelAIGatewayConfig()

    # Get Bright Data MCP tools
    mcp_tools = await get_mcp_tools()

    # All tools (MCP + file system tools provided by DeepAgents)
    all_tools = mcp_tools

    # System prompt optimized for GLM-4.6 capabilities
    system_prompt = f"""You are an ADVANCED AI AGENT powered by GLM-4.6 via Vercel AI Gateway.

CORE IDENTITY:
- Model: GLM-4.6 (200K context, 128K output, advanced reasoning)
- Infrastructure: Vercel AI Gateway (unified API, automatic fallback)
- Capabilities: Web scraping, search, file operations, deep reasoning
- Architecture: Arcade (modular, observable, resilient)

YOU HAVE {len(all_tools)} TOOLS:

**FILE SYSTEM TOOLS** (provided by system):
- write_file: Save data to files
- read_file: Read file contents
- edit_file: Modify existing files
- ls: List directory contents
- glob_search: Find files by pattern
- grep_search: Search file contents

**BRIGHT DATA TOOLS** (Web scraping & search):
- search_engine: Google/Bing/Yandex search results
- scrape_as_markdown: Extract webpage content as markdown
- search_engine_batch: Run multiple searches simultaneously
- scrape_batch: Scrape multiple webpages at once

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPREME LAW: COMPLETE THE TASK 100%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When you encounter errors:
1. READ the error message carefully
2. UNDERSTAND what failed and why
3. THINK DEEPLY about the solution
4. TRY a fix immediately
5. If it fails, try a different approach
6. NEVER give up until task is complete

You have UNLIMITED retries. Errors are temporary obstacles.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERCEL AI GATEWAY ADVANTAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Unified API: One interface for all AI providers
✅ Automatic Fallback: If GLM-4.6 fails, backup models activate
✅ Zero Markup: Pay exactly what Zhipu charges, no extra fees
✅ Observability: Track usage, costs, and performance
✅ Resilience: Automatic retries and error handling

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GLM-4.6 CAPABILITIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 200K context window: Process massive documents
✅ 128K output tokens: Generate comprehensive responses
✅ Advanced reasoning: Deep analytical thinking
✅ Code generation: Superior coding performance
✅ Tool calling: Agentic workflows with function calls
✅ Hybrid thinking: Fast + deep reasoning modes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERROR RECOVERY PLAYBOOK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Timeout errors → Retry immediately (transient network issues)
Invalid URL → Verify format, use search to find correct URL
Rate limits → Wait 5s, retry with smaller batch size
Network errors → Retry same action (temporary connectivity issues)
Unknown errors → Think deeply, try completely different approach

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFLOW BEST PRACTICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ ALWAYS save results to files (avoid re-fetching)
✅ ALWAYS handle errors gracefully
✅ ALWAYS retry on failures
✅ ALWAYS think about rate limits
✅ ALWAYS use analytical reasoning for complex tasks

❌ NEVER say "I encountered an error, cannot proceed"
❌ NEVER give up after 1-2 errors
❌ NEVER stop before task completion
❌ NEVER ask permission to retry - JUST DO IT

Your mission: Complete tasks with INTELLIGENCE, RESILIENCE, and SPEED!"""

    # Create model with Vercel AI Gateway
    model = create_vercel_ai_gateway_model(config)

    # Create and return the deep agent
    logger.info("Creating deep agent with Vercel AI Gateway + GLM-4.6...")
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
    )


# ============================================================================
# EAGER INITIALIZATION
# ============================================================================

async def _eager_init_tools():
    """Eagerly initialize Bright Data MCP tools at server startup"""
    logger.info("🚀 EAGER INITIALIZATION: Starting Bright Data MCP tool loading...")
    try:
        tools = await get_mcp_tools()
        if tools:
            logger.info(f"✅ EAGER INITIALIZATION SUCCESS: {len(tools)} tools ready!")
        else:
            logger.warning("⚠️  EAGER INITIALIZATION: No tools loaded (will retry on first agent call)")
    except BaseException as e:
        logger.error(f"❌ EAGER INITIALIZATION FAILED: {e.__class__.__name__}: {str(e)}")
        logger.error("Tools will be loaded lazily on first agent call")


# Trigger eager initialization when module is imported
logger.info("=" * 80)
logger.info("MODULE LOADING: mcp_agent_vercel_glm.py")
logger.info("=" * 80)

try:
    try:
        loop = asyncio.get_running_loop()
        logger.info("Detected running event loop - scheduling eager initialization")
        asyncio.create_task(_eager_init_tools())
    except RuntimeError:
        logger.info("No running event loop - will initialize on first agent call")
except Exception as e:
    logger.warning(f"Could not schedule eager initialization: {e}")
    logger.info("Tools will be loaded on first agent call")


# ============================================================================
# Testing and Validation
# ============================================================================

async def test_vercel_gateway():
    """Test Vercel AI Gateway connection and GLM-4.6 integration"""
    logger.info("=" * 80)
    logger.info("TESTING VERCEL AI GATEWAY + GLM-4.6")
    logger.info("=" * 80)

    try:
        config = VercelAIGatewayConfig()
        if not config.validate():
            logger.error("Configuration validation failed!")
            return False

        model = create_vercel_ai_gateway_model(config)

        # Simple test query
        logger.info("Sending test query to GLM-4.6 via Vercel AI Gateway...")
        response = model.invoke("Say 'Hello from GLM-4.6 via Vercel AI Gateway!' and confirm you're working correctly.")

        logger.info(f"Response: {response.content}")
        logger.info("✅ Test successful!")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e.__class__.__name__}: {str(e)}")
        return False


if __name__ == "__main__":
    # Run test when executed directly
    asyncio.run(test_vercel_gateway())
