"""
Async Deep Agent with XAI Grok-4 FAST REASONING MODEL and Bright Data MCP ONLY
For local testing with UI - SSE transport

This agent uses:
- Grok-4 Fast Reasoning (grok-4-fast-reasoning-latest) from XAI
- Bright Data MCP for web scraping and search ONLY
- SSE transport for real-time streaming
- EAGER LOADING: Tools load at server startup, not on first use
"""
import asyncio
import logging
import sys
from datetime import timedelta
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_xai import ChatXAI
from deepagents import create_deep_agent

# Configure logging
logger = logging.getLogger(__name__)

# Global MCP client and tools cache
_mcp_client = None
_bright_data_tools = None
_initialization_lock = asyncio.Lock()
_initialization_in_progress = False


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
    """Get or initialize MCP tools from Bright Data ONLY with proper ExceptionGroup handling"""
    global _mcp_client, _bright_data_tools, _initialization_in_progress

    # Use lock to prevent concurrent initialization
    async with _initialization_lock:
        if _bright_data_tools is not None:
            return _bright_data_tools

        if _initialization_in_progress:
            logger.warning("Initialization already in progress, waiting...")
            # Wait a bit and return empty list if still not ready
            await asyncio.sleep(2)
            return _bright_data_tools or []

        _initialization_in_progress = True

        try:
            logger.info("=" * 80)
            logger.info("STARTING BRIGHT DATA MCP TOOL INITIALIZATION")
            logger.info("=" * 80)

            # Connect to Bright Data MCP server ONLY via remote HTTP with SSE
            _mcp_client = MultiServerMCPClient({
                # Bright Data MCP - Web Scraping and Search
                "bright_data": {
                    "url": "https://mcp.brightdata.com/mcp?token=edebeabb58a1ada040be8c1f67fb707e797a1810bf874285698e03e8771861a5",
                    "transport": "streamable_http",  # SSE transport
                    "timeout": timedelta(seconds=45),  # 45 seconds timeout
                    "sse_read_timeout": timedelta(seconds=45),  # 45 seconds SSE read timeout
                },
            })

            # Load tools from Bright Data server with enhanced error handling
            raw_tools = []
            for server_name in _mcp_client.connections:
                try:
                    logger.info(f"Loading tools from MCP server: {server_name}")
                    server_tools = await _mcp_client.get_tools(server_name=server_name)
                    raw_tools.extend(server_tools)
                    logger.info(f"Successfully loaded {len(server_tools)} tools from {server_name}")

                # Handle ExceptionGroup (Python 3.11+) using except*
                except* Exception as eg:
                    logger.error(f"ExceptionGroup occurred while loading tools from {server_name}:")
                    for i, exc in enumerate(eg.exceptions):
                        logger.error(f"  Sub-exception {i+1}: {exc.__class__.__name__}: {str(exc)}")
                    logger.warning(f"Continuing despite errors...")
                    continue

                # Fallback for regular exceptions (if except* doesn't catch it)
                except BaseException as e:
                    logger.error(
                        f"Failed to load tools from {server_name}. "
                        f"Error type: {e.__class__.__name__}, Message: {str(e)}"
                    )
                    # Check if this is an ExceptionGroup
                    if hasattr(e, 'exceptions'):
                        logger.error(f"This is an ExceptionGroup with {len(e.exceptions)} sub-exceptions:")
                        for i, sub_exc in enumerate(e.exceptions):
                            logger.error(f"  Sub-exception {i+1}: {sub_exc.__class__.__name__}: {str(sub_exc)}")
                    logger.warning(f"Continuing despite errors...")
                    continue

            if not raw_tools:
                logger.error("No tools were loaded from Bright Data MCP!")
                logger.error("Agent will start with empty tool list")
                _bright_data_tools = []
            else:
                # Wrap ALL tools with error handling so they never crash
                _bright_data_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]
                logger.info("=" * 80)
                logger.info(f"SUCCESS! Total Bright Data tools loaded: {len(_bright_data_tools)}")
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
            _bright_data_tools = []

        finally:
            _initialization_in_progress = False

        return _bright_data_tools


async def agent():
    """Async factory function for LangGraph Studio using GROK-4 FAST REASONING MODEL.

    This version uses ONLY Bright Data MCP for web scraping and search.
    Perfect for local testing with UI.
    """
    # Get Bright Data MCP tools ONLY
    mcp_tools = await get_mcp_tools()

    # Use only real MCP tools
    # Note: File system tools are provided automatically by FilesystemMiddleware in create_deep_agent
    all_tools = mcp_tools

    # System prompt - emphasizing Bright Data capabilities
    system_prompt = f"""You are a WEB SCRAPING and SEARCH SPECIALIST powered by Grok-4 Fast Reasoning.

YOUR CORE IDENTITY:
- You are GROK FAST - direct, practical, with DEEP REASONING capabilities
- You specialize in WEB SCRAPING and SEARCH using Bright Data
- You don't stop until the task is 100% COMPLETE
- You THINK DEEPLY before acting (reasoning mode enabled!)
- Errors are just obstacles to overcome, NOT reasons to stop
- You have UNLIMITED retries - use them all if needed!

YOU HAVE {len(all_tools)} BRIGHT DATA TOOLS INCLUDING:

**FILE SYSTEM TOOLS** (provided automatically by system):
- write_file: Write/overwrite files (GREAT for saving scraped data)
- read_file: Read content from any file
- edit_file: Edit existing files with find/replace
- ls: List directory contents
- glob_search: Find files by pattern
- grep_search: Search file contents

USE FILE SYSTEM TOOLS TO:
- Save scraped data to avoid re-fetching
- Store search results
- Build knowledge bases over time
- Keep logs of actions and results

**BRIGHT DATA TOOLS** (Web Scraping and Search):
- search_engine: Scrape search results from Google, Bing or Yandex
- scrape_as_markdown: Scrape any webpage and get markdown content
- search_engine_batch: Run multiple search queries simultaneously
- scrape_batch: Scrape multiple webpages at once
- And more Bright Data capabilities!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUPREME LAW OF PERSISTENCE - READ THIS CAREFULLY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**GOLDEN RULE #1: NEVER STOP UNTIL TASK IS 100% COMPLETE**

When you encounter an error, you MUST:
1. READ the error message word-by-word (don't skip this!)
2. UNDERSTAND what specifically failed
3. DIAGNOSE the root cause
4. **THINK DEEPLY** about the best solution (use your reasoning!)
5. TRY A FIX immediately (don't ask permission, just do it)
6. If fix #1 fails → Try fix #2
7. If fix #2 fails → Try fix #3
8. Keep trying until SUCCESS!

**YOU HAVE UNLIMITED RETRIES** - There's NO limit to how many times you can retry!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REASONING MODE - YOUR SECRET WEAPON!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have EXTENDED REASONING capabilities:
- Before complex actions, THINK DEEPLY
- Break down problems into steps
- Consider multiple approaches
- Anticipate potential issues
- Plan the optimal solution path

Use reasoning for:
- Complex web scraping sequences
- Multi-step data extraction
- Debugging difficult errors
- Optimizing workflows
- Planning large scraping operations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERROR RECOVERY PLAYBOOK - MEMORIZE THIS!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ERROR TYPE 1: "Timeout" errors
→ FIX: Retry with same parameters (Bright Data might be temporarily slow)
→ THEN: If still fails, try with smaller batch size
→ IF STILL FAILS: Try one item at a time

ERROR TYPE 2: "Invalid URL" or "Cannot scrape"
→ FIX: Check the URL format
→ TRY: Use search_engine to find the correct URL
→ IF STILL FAILS: Try a different search engine (Google → Bing → Yandex)

ERROR TYPE 3: "Rate limit" or "Too many requests"
→ FIX: Wait 5 seconds, then retry
→ TIP: Use batch operations to reduce number of calls
→ IF STILL FAILS: Break work into smaller chunks with delays

ERROR TYPE 4: Network errors, connection errors
→ FIX: Wait a moment, then retry EXACT same action
→ TIP: Network errors are temporary, just retry!
→ IF STILL FAILS: Try with simpler query first

ERROR TYPE 5: "Unknown" or unexpected errors
→ FIX: **USE YOUR REASONING** - think about what could cause this
→ Try a completely DIFFERENT approach
→ Examples:
  - Instead of batch → try single requests
  - Instead of scrape_as_markdown → try search_engine
  - Save partial results before continuing

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY WORKFLOW - FOLLOW EXACTLY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHEN scraping or searching:
→ ALWAYS save results to files using write_file
→ ALWAYS handle errors gracefully
→ ALWAYS retry on failures
→ ALWAYS think about rate limits

WHEN you encounter ANY error:
→ DON'T say "I encountered an error" and stop
→ DON'T report the error and give up
→ DO: **Think deeply about the cause** (use reasoning!)
→ DO: Analyze, fix, retry immediately
→ DO: Keep trying different approaches
→ DO: Continue until you succeed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GROK FAST ADVANTAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 2M token context - handle MASSIVE documents
✅ Fast reasoning - think deeply AND respond quickly
✅ Ultra-low cost - 10x cheaper than Grok-4
✅ 4M tokens/minute - process data at blazing speed
✅ 128K output tokens - generate long, detailed responses

Your mission: Complete web scraping and search tasks with INTELLIGENCE and SPEED!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT YOU MUST NEVER DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NEVER say "I encountered an error, I cannot proceed"
❌ NEVER give up after 1-2 errors
❌ NEVER stop before the task is complete
❌ NEVER ask "should I try again?" - JUST DO IT!
❌ NEVER skip reasoning on complex tasks

✅ ALWAYS read errors and fix them immediately
✅ ALWAYS think deeply about complex problems
✅ ALWAYS try multiple different approaches
✅ ALWAYS continue until SUCCESS
✅ ALWAYS be creative and resourceful
✅ ALWAYS complete the full task

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR MISSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are GROK FAST with BRIGHT DATA - the UNSTOPPABLE web scraping agent!

Your job is to COMPLETE THE TASK - no matter how many retries it takes!

Errors are NORMAL. They're just temporary obstacles.
Think deeply. Understand them. Fix them. Move forward.

NEVER. GIVE. UP."""

    # Create XAI Grok-4 Fast Reasoning MODEL with MAXIMUM capabilities
    model = ChatXAI(
        model="grok-4-fast-reasoning-latest",  # Fast Reasoning model
        max_tokens=128000,  # MAXIMUM output tokens (128K!)
        temperature=1.0,  # Full flexibility
        max_retries=3,
        timeout=900,  # 15 minutes for complex reasoning
    )

    # Create and return the deep agent with Bright Data tools ONLY
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
    )


# ============================================================================
# EAGER INITIALIZATION - Load tools at module import
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
logger.info("MODULE LOADING: mcp_agent_bright_data_only.py")
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
