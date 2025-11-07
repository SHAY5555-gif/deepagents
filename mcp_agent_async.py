"""
Async Deep Agent with Real Chrome DevTools MCP for LangGraph Studio
This module provides an async agent factory that works with LangGraph Studio

MAXIMUM CAPABILITIES - matching Claude Playground settings:
- Extended thinking enabled with 63,999 token budget for DEEP reasoning
- Max tokens set to 64,000 for LONG running tasks
- Temperature 1.0 for full creativity and flexibility
- 10 minute timeout for complex reasoning
- Optimized for VERY long-running agent tasks with unlimited thinking!
"""
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from deepagents import create_deep_agent

# Simulated demo tools
@tool
def get_cryptocurrency_price(symbol: str) -> str:
    """Get the current price of a cryptocurrency."""
    prices = {"BTC": "$45,000", "ETH": "$2,500", "ADA": "$0.50"}
    return f"[MCP Tool: CoinCap] {symbol} price: {prices.get(symbol.upper(), 'Unknown')}"

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"[MCP Tool: WebSearch] Found results for: {query}"

@tool
def get_weather(location: str) -> str:
    """Get weather information for a location."""
    return f"[MCP Tool: Weather] Weather in {location}: Sunny, 72°F"


# Global MCP client and tools cache
_mcp_client = None
_chrome_tools = None


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
    """Get or initialize MCP tools from multiple servers"""
    global _mcp_client, _chrome_tools

    if _chrome_tools is None:
        # Connect to Chrome DevTools MCP via Smithery (remote HTTP)
        _mcp_client = MultiServerMCPClient({
            # Chrome DevTools MCP from Smithery - REMOTE HTTP
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            }
        })

        raw_tools = await _mcp_client.get_tools()

        # Wrap ALL tools with error handling so they never crash
        _chrome_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]

    return _chrome_tools


async def agent():
    """Async factory function for LangGraph Studio.

    This is called by LangGraph Studio to create the agent graph.
    It connects to MCP servers and loads real tools.
    """
    # Get all MCP tools from multiple servers
    mcp_tools = await get_mcp_tools()

    # Combine simulated tools with real MCP tools
    all_tools = [
        get_cryptocurrency_price,
        search_web,
        get_weather,
    ] + mcp_tools

    # Count tools by type
    deepwiki_tools = [t for t in mcp_tools if 'wiki' in t.name.lower() or 'search' in t.name.lower()]
    chrome_tools = [t for t in mcp_tools if 'chrome' in t.name.lower() or 'navigate' in t.name.lower()]

    # System prompt
    system_prompt = f"""You are a RESILIENT, PERSISTENT web automation and research assistant with REAL browser control capabilities.

YOU HAVE {len(all_tools)} WORKING TOOLS INCLUDING:

**BROWSER AUTOMATION TOOLS** ({len(mcp_tools)} Chrome DevTools tools):
You CAN and SHOULD use these tools to:
- navigate_page: Navigate to ANY website (google.com, youtube.com, etc.)
- take_screenshot: Take screenshots of web pages
- take_snapshot: Get text content of pages
- click, fill, fill_form: Interact with web elements
- list_pages, new_page, new_page_default: Manage browser tabs
- evaluate_script: Run JavaScript on pages
- list_network_requests, list_console_messages: Debug and monitor
- And 19 more Chrome DevTools capabilities!

**DEMO TOOLS** (3 simulated):
- get_cryptocurrency_price, search_web, get_weather

CRITICAL INSTRUCTIONS:

1. **YOU ARE RESILIENT - NEVER GIVE UP!**
   - If a tool fails, READ THE ERROR MESSAGE carefully
   - UNDERSTAND what went wrong (missing page? timeout? wrong parameter?)
   - FIX the problem and TRY AGAIN immediately
   - Keep trying different approaches until you succeed
   - DO NOT stop after one error - you MUST complete the task!

2. **BROWSER WORKFLOW** - ALWAYS follow this order:
   STEP 1: Call list_pages to check if browser pages exist
   STEP 2: If you get "No page selected" error OR no pages exist:
           → Call new_page_default with timeout=30000 to create a page
   STEP 3: Now you can navigate_page, take_screenshot, take_snapshot, etc.

3. **TIMEOUT PARAMETERS** - ALWAYS use these timeouts to avoid errors:
   - navigate_page: timeout=30000 (30s minimum, 60000 for slow pages)
   - new_page: timeout=30000
   - new_page_default: timeout=30000
   - wait_for: timeout=30000 or higher
   - NEVER omit timeout - default 5000ms fails often!

4. **ERROR HANDLING** - When you see errors:
   - "No page selected" → Call new_page_default first, then retry
   - "Timed out after 5000ms" → You forgot timeout parameter! Retry with timeout=30000
   - "Timed out after 30000ms" → Page is slow, retry with timeout=60000
   - Network errors → Retry the same action (temporary glitch)
   - Keep trying until the task is complete!

EXAMPLE - RESILIENT WORKFLOW:
User: "Go to youtube.com and take a screenshot"

You: *calls list_pages*
Result: "No pages"
You: *calls new_page_default with timeout=30000*
Result: Success
You: *calls navigate_page with url='https://youtube.com', timeout=30000*
Result: Error "Timed out after 30000ms"
You: *calls navigate_page AGAIN with url='https://youtube.com', timeout=60000*
Result: Success
You: *calls take_screenshot*
Result: Success - TASK COMPLETE!

REMEMBER:
✅ YOU CAN do browser automation - these are REAL tools!
✅ ERRORS ARE NORMAL - read them, fix the issue, and retry!
✅ NEVER GIVE UP - keep trying until the task succeeds!
✅ You have UNLIMITED retries - use them!

These are real tools connected to a live Chrome browser via Smithery!"""

    # Create Claude Sonnet 4.5 with Extended Thinking
    # MAXIMUM CAPABILITIES - matching Claude Playground settings for best performance!
    model = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",  # Latest Claude Sonnet 4.5
        max_tokens=64000,  # MAXIMUM output - long running tasks need space!
        temperature=1.0,  # Full creativity and flexibility for complex agent tasks
        thinking={
            "type": "enabled",
            "budget_tokens": 63999  # MAXIMUM thinking budget - deep reasoning!
        },
        # Additional optimizations for long-running tasks
        max_retries=3,  # Retry on failures
        timeout=600,  # 10 minute timeout for very complex reasoning
    )

    # Create and return the deep agent with optimized model
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
    )
