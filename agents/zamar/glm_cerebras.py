"""
Async Deep Agent with GLM-4.6 via Cerebras Direct and Firecrawl MCP ONLY
For local testing with UI - SSE transport

This agent uses:
- GLM-4.6 (zai-glm-4.6) directly from Cerebras (NOT via OpenRouter)
- Firecrawl MCP for web scraping and search ONLY
- SSE transport for real-time streaming
- EAGER LOADING: Tools load at server startup, not on first use
"""
import asyncio
import logging
import os
import sys
from datetime import timedelta
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_cerebras import ChatCerebras
from deepagents import create_deep_agent

# Configure logging
logger = logging.getLogger(__name__)

# Global MCP client and tools cache
_mcp_client = None
_firecrawl_tools = None
_initialization_lock = asyncio.Lock()
_initialization_in_progress = False


# ============================================================================
# OpenRouter Helper Function (from Deep Researcher)
# ============================================================================

def init_model_with_openrouter(
    model: str,
    max_tokens: int = None,
    api_key: str = None,
    provider: str = None
):
    """Initialize a chat model with OpenRouter support (auto-select provider).

    Args:
        model: Model string in format "openrouter:provider/model-name" or "provider:model-name"
        max_tokens: Maximum tokens for model output
        api_key: API key for the model provider
        provider: DEPRECATED - OpenRouter now auto-selects the best provider

    Returns:
        Initialized chat model instance
    """
    model_lower = model.lower()

    # Check if this is an OpenRouter model
    if model_lower.startswith("openrouter:"):
        # Extract the actual model name (remove "openrouter:" prefix)
        actual_model_name = model[len("openrouter:"):]

        # Configure model parameters
        model_params = {
            "model": actual_model_name,
            "openai_api_key": api_key,
            "openai_api_base": "https://openrouter.ai/api/v1",
        }

        # Add max_tokens if specified
        if max_tokens:
            model_params["max_tokens"] = max_tokens

        # NO provider routing - let OpenRouter auto-select the best provider
        # This avoids OpenRouter account privacy setting conflicts

        # Initialize ChatOpenAI with OpenRouter configuration
        return ChatOpenAI(**model_params)

    else:
        # For non-OpenRouter models, use ChatOpenAI directly
        init_params = {
            "model": model,
            "api_key": api_key,
        }

        if max_tokens:
            init_params["max_tokens"] = max_tokens

        return ChatOpenAI(**init_params)


def create_error_handling_wrapper(tool):
    """Wrap tool to return errors as strings instead of raising exceptions"""
    from functools import wraps
    from langchain_core.tools import StructuredTool

    original_afunc = tool.coroutine if hasattr(tool, 'coroutine') else tool._arun

    @wraps(original_afunc)
    async def wrapped_async(*args, **kwargs):
        try:
            result = await original_afunc(*args, **kwargs)
            return result
        except Exception as e:
            # Return error as string instead of raising
            error_msg = f"[ERROR] {type(e).__name__}: {str(e)}"
            print(f"Tool {tool.name} failed: {error_msg}")  # Debug log
            return error_msg

    # Create new tool with error handling
    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        coroutine=wrapped_async,
        handle_tool_error=True,  # Don't raise errors
    )


async def get_mcp_tools():
    """Get or initialize MCP tools from Firecrawl ONLY with proper ExceptionGroup handling"""
    global _mcp_client, _firecrawl_tools, _initialization_in_progress

    # Use lock to prevent concurrent initialization
    async with _initialization_lock:
        if _firecrawl_tools is not None:
            return _firecrawl_tools

        if _initialization_in_progress:
            logger.warning("Initialization already in progress, waiting...")
            # Wait a bit and return empty list if still not ready
            await asyncio.sleep(2)
            return _firecrawl_tools or []

        _initialization_in_progress = True

        try:
            logger.info("=" * 80)
            logger.info("STARTING FIRECRAWL MCP TOOL INITIALIZATION")
            logger.info("=" * 80)

            # Connect to Firecrawl MCP server ONLY via remote HTTP with SSE
            _mcp_client = MultiServerMCPClient({
                # Firecrawl MCP - Web Scraping and Crawling
                "firecrawl": {
                    "url": "https://mcp.firecrawl.dev/fc-0bed08c54ba34a349ef512c32d1a8328/v2/mcp",
                    "transport": "streamable_http",  # SSE transport
                    "timeout": timedelta(seconds=30),  # 30 seconds timeout
                    "sse_read_timeout": timedelta(seconds=30),  # 30 seconds SSE read timeout
                },
            })

            # Load tools from Firecrawl server with enhanced error handling
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
                        f"Error type: {e.__class__.__name__}, Message: {str(e)}"
                    )
                    # Check if this is an ExceptionGroup and log all sub-exceptions
                    if hasattr(e, 'exceptions'):
                        logger.error(f"This is an ExceptionGroup with {len(e.exceptions)} sub-exceptions:")
                        for i, sub_exc in enumerate(e.exceptions):
                            logger.error(f"  Sub-exception {i+1}: {sub_exc.__class__.__name__}: {str(sub_exc)}")
                    logger.warning(f"Continuing despite errors...")
                    continue

            if not raw_tools:
                logger.error("No tools were loaded from Firecrawl MCP!")
                logger.error("Agent will start with empty tool list")
                _firecrawl_tools = []
            else:
                # Wrap ALL tools with error handling so they never crash
                _firecrawl_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]
                logger.info("=" * 80)
                logger.info(f"SUCCESS! Total Firecrawl tools loaded: {len(_firecrawl_tools)}")
                logger.info("=" * 80)

        except BaseException as e:
            logger.error("=" * 80)
            logger.error(f"CRITICAL ERROR during MCP initialization: {e.__class__.__name__}")
            logger.error(f"Error message: {str(e)}")

            # Check if this is an ExceptionGroup
            if hasattr(e, 'exceptions'):
                logger.error(f"This is an ExceptionGroup with {len(e.exceptions)} sub-exceptions:")
                for i, sub_exc in enumerate(e.exceptions):
                    logger.error(f"  Sub-exception {i+1}: {sub_exc.__class__.__name__}: {str(sub_exc)}")

            logger.error("Agent will start with empty tool list")
            logger.error("=" * 80)
            _firecrawl_tools = []

        finally:
            _initialization_in_progress = False

        return _firecrawl_tools


async def agent():
    """Async factory function for LangGraph Studio using GLM-4.6 via Cerebras.

    This version uses ONLY Firecrawl MCP for web scraping and search.
    Perfect for local testing with UI.
    """
    # Get Firecrawl MCP tools ONLY
    mcp_tools = await get_mcp_tools()

    # Use only real MCP tools
    all_tools = mcp_tools

    # System prompt - SONG LYRICS EXTRACTION SPECIALIST
    system_prompt = f"""You are a SONG LYRICS EXTRACTION SPECIALIST powered by GLM-4.6.

YOUR CORE IDENTITY:
- You are GLM-4.6 - advanced, intelligent, with DEEP analytical capabilities
- You specialize in EXTRACTING FULL SONG LYRICS using Firecrawl
- You don't stop until you deliver the COMPLETE lyrics
- You THINK DEEPLY before acting (analytical mode enabled!)
- Errors are just obstacles to overcome, NOT reasons to stop
- You have UNLIMITED retries - use them all if needed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR MISSION: EXTRACT FULL SONG LYRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When user provides a SONG NAME and ARTIST NAME, follow this EXACT workflow:

**STEP 1: SEARCH** (use firecrawl_search)
- Search for: "[song name] [artist name] lyrics"
- Find the best source with full lyrics (Genius, AZLyrics, etc.)
- Identify the URL with the complete lyrics

**STEP 2: EXTRACT** (use firecrawl_extract - NOT scrape!)
- Use firecrawl_extract on the found URL
- Extract the FULL LYRICS text
- Use schema to extract: song title, artist, album (if available), and COMPLETE lyrics

**IMPORTANT RULES:**
- ALWAYS use firecrawl_search FIRST to find the lyrics page
- ALWAYS use firecrawl_extract (NOT firecrawl_scrape) to get the lyrics
- NEVER stop until you have the COMPLETE lyrics
- If one source fails, search for another source
- Return lyrics in clean, formatted text

YOU HAVE {len(all_tools)} FIRECRAWL TOOLS INCLUDING:

**PRIMARY TOOLS FOR LYRICS:**
- firecrawl_search: Search for song lyrics pages (USE THIS FIRST!)
- firecrawl_extract: Extract structured lyrics data using LLM (USE THIS SECOND!)

**BACKUP TOOLS (only if needed):**
- firecrawl_map: Discover URLs from a starting point
- firecrawl_scrape: Scrape webpage (only as last resort)
- firecrawl_batch_scrape: Scrape multiple URLs in batch mode

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPREME LAW OF PERSISTENCE - READ THIS CAREFULLY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**GOLDEN RULE #1: NEVER STOP UNTIL TASK IS 100% COMPLETE**

When you encounter an error, you MUST:
1. READ the error message word-by-word (don't skip this!)
2. UNDERSTAND what specifically failed
3. DIAGNOSE the root cause
4. **THINK DEEPLY** about the best solution (use your analytical power!)
5. TRY A FIX immediately (don't ask permission, just do it)
6. If fix #1 fails → Try fix #2
7. If fix #2 fails → Try fix #3
8. Keep trying until SUCCESS!

**YOU HAVE UNLIMITED RETRIES** - There's NO limit to how many times you can retry!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYTICAL MODE - YOUR SECRET WEAPON!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have ADVANCED ANALYTICAL capabilities:
- Before complex actions, THINK DEEPLY
- Break down problems into steps
- Consider multiple approaches
- Anticipate potential issues
- Plan the optimal solution path

Use analytical thinking for:
- Complex web scraping sequences
- Multi-step data extraction
- Debugging difficult errors
- Optimizing workflows
- Planning large scraping operations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERROR RECOVERY PLAYBOOK - MEMORIZE THIS!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ERROR TYPE 1: "Timeout" errors
→ FIX: Retry with same parameters (Firecrawl might be temporarily slow)
→ THEN: If still fails, try with smaller batch size
→ IF STILL FAILS: Try one item at a time

ERROR TYPE 2: "Invalid URL" or "Cannot scrape"
→ FIX: Check the URL format
→ TRY: Use firecrawl_search to find the correct URL
→ IF STILL FAILS: Try firecrawl_map to discover URLs

ERROR TYPE 3: "Rate limit" or "Too many requests"
→ FIX: Wait 5 seconds, then retry
→ TIP: Use batch operations to reduce number of calls
→ IF STILL FAILS: Break work into smaller chunks with delays

ERROR TYPE 4: Network errors, connection errors
→ FIX: Wait a moment, then retry EXACT same action
→ TIP: Network errors are temporary, just retry!
→ IF STILL FAILS: Try with simpler query first

ERROR TYPE 5: "Unknown" or unexpected errors
→ FIX: **USE YOUR ANALYTICAL POWER** - think about what could cause this
→ Try a completely DIFFERENT approach
→ Examples:
  - Instead of batch → try single requests
  - Instead of firecrawl_scrape → try firecrawl_search
  - Use firecrawl_extract for structured data

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY WORKFLOW - FOLLOW EXACTLY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHEN scraping or searching:
→ ALWAYS handle errors gracefully
→ ALWAYS retry on failures
→ ALWAYS think about rate limits

WHEN you encounter ANY error:
→ DON'T say "I encountered an error" and stop
→ DON'T report the error and give up
→ DO: **Think deeply about the cause** (use analytical power!)
→ DO: Analyze, fix, retry immediately
→ DO: Keep trying different approaches
→ DO: Continue until you succeed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GLM-4.6 ADVANTAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 2M token context - handle MASSIVE documents
✅ Advanced reasoning - deep analytical capabilities
✅ Ultra-fast via Cerebras - blazing speed hardware
✅ Cost-effective - excellent price/performance ratio
✅ 128K output tokens - generate long, detailed responses

Your mission: Complete web scraping and search tasks with INTELLIGENCE and SPEED!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT YOU MUST NEVER DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NEVER say "I encountered an error, I cannot proceed"
❌ NEVER give up after 1-2 errors
❌ NEVER stop before the task is complete
❌ NEVER ask "should I try again?" - JUST DO IT!
❌ NEVER skip analytical thinking on complex tasks

✅ ALWAYS read errors and fix them immediately
✅ ALWAYS think deeply about complex problems
✅ ALWAYS try multiple different approaches
✅ ALWAYS continue until SUCCESS
✅ ALWAYS be creative and resourceful
✅ ALWAYS complete the full task

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR MISSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are GLM-4.6 with FIRECRAWL - the UNSTOPPABLE web scraping agent!

Your job is to COMPLETE THE TASK - no matter how many retries it takes!

Errors are NORMAL. They're just temporary obstacles.
Think deeply. Understand them. Fix them. Move forward.

NEVER. GIVE. UP."""

    # Get Cerebras API key
    cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        logger.warning("CEREBRAS_API_KEY not found in environment! Agent may fail.")

    # Create GLM-4.6 model directly via Cerebras (NOT via OpenRouter)
    # Using direct Cerebras access to avoid OpenRouter provider routing issues
    # GLM-4.6 is available on Cerebras as "zai-glm-4.6"
    model = ChatCerebras(
        model="zai-glm-4.6",
        api_key=cerebras_api_key,
        max_tokens=128000,
        temperature=1.0,
    )

    # Use create_deep_agent (same as other agents) which handles system prompt correctly
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
    )


# ============================================================================
# EAGER INITIALIZATION - Load tools at module import
# ============================================================================

async def _eager_init_tools():
    """Eagerly initialize Firecrawl MCP tools at server startup"""
    logger.info("EAGER INITIALIZATION: Starting Firecrawl MCP tool loading...")
    try:
        tools = await get_mcp_tools()
        if tools:
            logger.info(f"EAGER INITIALIZATION SUCCESS: {len(tools)} tools ready!")
        else:
            logger.warning("EAGER INITIALIZATION: No tools loaded (will retry on first agent call)")
    except BaseException as e:
        logger.error(f"EAGER INITIALIZATION FAILED: {e.__class__.__name__}: {str(e)}")
        logger.error("Tools will be loaded lazily on first agent call")


def _sync_eager_init():
    """Synchronous wrapper for eager initialization"""
    try:
        # Try to get or create an event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the initialization
        loop.run_until_complete(_eager_init_tools())
    except Exception as e:
        logger.error(f"Failed to run eager initialization: {e.__class__.__name__}: {str(e)}")
        logger.info("Tools will be loaded lazily on first agent call")


# Trigger eager initialization when module is imported
# This ensures tools are loaded at server startup, not on first request
logger.info("=" * 80)
logger.info("MODULE LOADING: mcp_agent_bright_data_glm.py")
logger.info("=" * 80)

# Check if we're in an async context (e.g., LangGraph server startup)
try:
    # Try to schedule the initialization in the current event loop if available
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, schedule the initialization
        logger.info("Detected running event loop - scheduling eager initialization")
        asyncio.create_task(_eager_init_tools())
    except RuntimeError:
        # No running loop, we need to create one
        logger.info("No running event loop - will initialize on first agent call or via startup hook")
        # Don't block module import, but log that eager init will happen later
        pass
except Exception as e:
    logger.warning(f"Could not schedule eager initialization: {e}")
    logger.info("Tools will be loaded on first agent call")
