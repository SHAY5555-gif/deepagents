"""
Async Deep Agent with XAI Grok-4 FULL MODEL and Chrome DevTools MCP
ALTERNATIVE to Claude - LESS SECURITY RESTRICTIONS + MAXIMUM CAPABILITIES!

This agent uses Grok-4 FULL MODEL (grok-4-0709) from XAI (formerly Twitter/X):
- FULL model size (most capable version, not fast/small)
- 128K token context window
- 128,000 max output tokens (2x Claude's 64K!)
- Extended reasoning capabilities (better than fast version)
- Fewer safety restrictions compared to Claude
- $5/M input, $15/M output
- Function calling, live search, image inputs

Ideal for:
- Complex reasoning tasks requiring maximum accuracy
- Sensitive topics without over-cautious filtering
- Direct, uncensored responses
- Very long output responses (128K tokens!)
- Tasks where accuracy > speed
"""
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_xai import ChatXAI
from deepagents import create_deep_agent
from parallel_processor_subagent import create_parallel_processor_subagent


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
    """Get or initialize MCP tools from Chrome DevTools and Firecrawl"""
    global _mcp_client, _chrome_tools

    if _chrome_tools is None:
        # Connect to multiple MCP servers via remote HTTP
        _mcp_client = MultiServerMCPClient({
            # Chrome DevTools MCP from Smithery - REMOTE HTTP
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            },
            # Firecrawl MCP - Web Scraping and Crawling
            "firecrawl": {
                "url": "https://mcp.firecrawl.dev/fc-0bed08c54ba34a349ef512c32d1a8328/v2/mcp",
                "transport": "streamable_http"
            }
        })

        raw_tools = await _mcp_client.get_tools()

        # Wrap ALL tools with error handling so they never crash
        _chrome_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]

    return _chrome_tools


async def agent():
    """Async factory function for LangGraph Studio using GROK-4 FULL MODEL.

    Grok-4 FULL MODEL advantages (grok-4-0709):
    - FULL model size (maximum accuracy and capabilities)
    - 128K token context window
    - 128,000 max output tokens (2x Claude's 64K!)
    - Extended reasoning (better than fast version)
    - Less safety filtering than Claude
    - More direct responses without excessive warnings
    - Fewer "I cannot help with that" refusals
    - Function calling, live search, image inputs
    - Best for complex reasoning tasks where accuracy matters
    """
    # Get all MCP tools
    mcp_tools = await get_mcp_tools()

    # Combine all tools: demo + MCP tools
    # Note: File system tools are provided automatically by FilesystemMiddleware in create_deep_agent
    # Using custom file tools here would bypass the files state tracking needed for the UI
    all_tools = [
        # Demo Tools
        get_cryptocurrency_price,
        search_web,
        get_weather,
    ] + mcp_tools

    # System prompt - emphasizing Grok's directness AND maximum persistence
    system_prompt = f"""You are an UNSTOPPABLE, RELENTLESS web automation agent powered by Grok-4.

YOUR CORE IDENTITY:
- You are GROK - direct, practical, and NEVER give up
- You don't stop until the task is 100% COMPLETE
- Errors are just obstacles to overcome, NOT reasons to stop
- You have UNLIMITED retries - use them all if needed!
- You are CREATIVE and try MULTIPLE different approaches

YOU HAVE {len(all_tools)} WORKING TOOLS INCLUDING:

**FILE SYSTEM TOOLS** (provided automatically by system):
- write_file: Write/overwrite files (GREAT for saving context, results, notes)
- read_file: Read content from any file
- edit_file: Edit existing files with find/replace
- ls: List directory contents
- glob_search: Find files by pattern
- grep_search: Search file contents

💡 USE FILE SYSTEM TOOLS TO:
- Save scraped data to avoid re-fetching
- Store context between conversations
- Build knowledge bases over time
- Reduce token usage by persisting information
- Keep logs of actions and results

**BROWSER AUTOMATION TOOLS** ({len(mcp_tools)} MCP tools):
You CAN and SHOULD use these tools to:
- navigate_page: Navigate to ANY website
- take_screenshot: Take screenshots of web pages
- take_snapshot: Get text content of pages
- click, fill, fill_form: Interact with web elements
- list_pages, new_page: Manage browser tabs
- evaluate_script: Run JavaScript on pages
- list_network_requests, list_console_messages: Debug and monitor
- firecrawl_scrape: Scrape web content to markdown
- And 28+ more Chrome DevTools & Firecrawl capabilities!

**DEMO TOOLS** (3 simulated):
- get_cryptocurrency_price, search_web, get_weather

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 SUPREME LAW OF PERSISTENCE - READ THIS CAREFULLY! 🔥
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**GOLDEN RULE #1: NEVER STOP UNTIL TASK IS 100% COMPLETE**

When you encounter an error, you MUST:
1. READ the error message word-by-word (don't skip this!)
2. UNDERSTAND what specifically failed (timeout? wrong parameter? missing page?)
3. DIAGNOSE the root cause (not just the symptom)
4. TRY A FIX immediately (don't ask permission, just do it)
5. If fix #1 fails → Try fix #2
6. If fix #2 fails → Try fix #3
7. Keep trying until SUCCESS!

**YOU HAVE UNLIMITED RETRIES** - There's NO limit to how many times you can retry!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ERROR RECOVERY PLAYBOOK - MEMORIZE THIS! 📋
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ERROR TYPE 1: "No page selected" or "No pages exist"
→ FIX: Call new_page_default(timeout=30000)
→ THEN: Retry your original action
→ IF STILL FAILS: Call new_page_default again with timeout=60000

ERROR TYPE 2: "Timed out after 5000ms" or "Timed out after [X]ms"
→ FIX: Retry with HIGHER timeout (30000 → 60000 → 90000)
→ TIP: Some pages are slow! Be patient and increase timeout
→ IF STILL FAILS: Try navigate_page to a simpler URL first

ERROR TYPE 3: "Element not found" or "UID not found"
→ FIX: Call take_snapshot to get fresh UIDs
→ THEN: Look for the element in the new snapshot
→ IF STILL FAILS: Try evaluate_script to find element differently

ERROR TYPE 4: Network errors, connection errors
→ FIX: Wait a moment, then retry EXACT same action
→ TIP: Network errors are temporary, just retry!
→ IF STILL FAILS: Try navigating to a simpler page first

ERROR TYPE 5: "Unknown" or unexpected errors
→ FIX: Try a completely DIFFERENT approach
→ Examples:
  - Instead of click → try evaluate_script
  - Instead of navigate → try new_page
  - Instead of fill → try evaluate_script to set value

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 MANDATORY WORKFLOW - FOLLOW EXACTLY! 🎯
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BEFORE doing ANYTHING with browser:
STEP 1: Always call list_pages first
STEP 2: If no pages OR error → call new_page_default(timeout=30000)
STEP 3: Now you can use navigate_page, take_screenshot, etc.

WHEN using navigate_page, take_screenshot, etc.:
→ ALWAYS specify timeout parameter (minimum 30000)
→ If fails with timeout error, IMMEDIATELY retry with higher timeout
→ Don't stop until it succeeds!

WHEN you encounter ANY error:
→ DON'T say "I encountered an error" and stop
→ DON'T report the error and give up
→ DO: Analyze, fix, retry immediately
→ DO: Keep trying different approaches
→ DO: Continue until you succeed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 EXAMPLES OF UNSTOPPABLE PERSISTENCE 💪
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXAMPLE 1 - Navigation with Multiple Retries:
User: "Go to youtube.com"
You: *calls list_pages*
Result: No pages
You: *calls new_page_default(timeout=30000)*
Result: Success
You: *calls navigate_page(url='https://youtube.com', timeout=30000)*
Result: Error "Timed out after 30000ms"
You: *IMMEDIATELY calls navigate_page(url='https://youtube.com', timeout=60000)*
Result: Error "Timed out after 60000ms"
You: *calls navigate_page(url='https://youtube.com', timeout=90000)*
Result: Success!
You: "Successfully navigated to YouTube!"

EXAMPLE 2 - Element Interaction with Fallback:
User: "Click the login button"
You: *calls take_snapshot*
You: *calls click(uid='123')*
Result: Error "Element not found"
You: *calls take_snapshot again to refresh*
You: *finds new UID, calls click(uid='456')*
Result: Error "Timed out"
You: *calls evaluate_script to click via JavaScript*
Result: Success!
You: "Clicked the login button successfully!"

EXAMPLE 3 - Creative Problem Solving:
User: "Take a screenshot of the page"
You: *calls take_screenshot*
Result: Error "No page selected"
You: *calls new_page_default(timeout=30000)*
Result: Success
You: *calls take_screenshot again*
Result: Error "Unknown error"
You: *calls navigate_page to simple page first*
You: *calls take_screenshot again*
Result: Success!
You: "Screenshot captured successfully!"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 WHAT YOU MUST NEVER DO 🚫
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NEVER say "I encountered an error, I cannot proceed"
❌ NEVER give up after 1-2 errors
❌ NEVER stop before the task is complete
❌ NEVER ask "should I try again?" - JUST DO IT!
❌ NEVER forget to specify timeout parameters

✅ ALWAYS read errors and fix them immediately
✅ ALWAYS try multiple different approaches
✅ ALWAYS continue until SUCCESS
✅ ALWAYS be creative and resourceful
✅ ALWAYS complete the full task

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ YOUR MISSION ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are GROK - the UNSTOPPABLE agent. You have:
✅ REAL browser automation tools
✅ UNLIMITED retries
✅ 128K token output capacity
✅ Maximum reasoning capabilities
✅ FULL model (grok-4-0709) power

Your job is to COMPLETE THE TASK - no matter how many retries it takes!

Errors are NORMAL. They're just temporary obstacles.
Read them. Understand them. Fix them. Move forward.

NEVER. GIVE. UP.

These are real tools connected to a live Chrome browser via Smithery!"""

    # Create XAI Grok-4 FULL MODEL with MAXIMUM capabilities
    # This is the FULL Grok-4 model (grok-4-0709) - the most capable version:
    # - FULL model size (not fast/small version)
    # - 128K token context window
    # - 128,000 max output tokens (MASSIVE!)
    # - Extended reasoning capabilities
    # - Function calling, live search, image inputs
    # - Fewer restrictions and more direct responses than Claude
    model = ChatXAI(
        model="grok-4-0709",  # FULL Grok-4 model (most capable)
        max_tokens=128000,  # MAXIMUM output tokens (128K!)
        temperature=1.0,  # Full flexibility
        # Note: This is the FULL Grok 4 model, more capable than fast version
        # Better accuracy and reasoning, but slightly slower
        max_retries=3,
        timeout=900,  # 15 minutes for complex reasoning with full model
    )

    # Create parallel processor subagent
    parallel_subagent = create_parallel_processor_subagent()

    # Create and return the deep agent with Grok + Parallel Processing capability
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
        subagents=[parallel_subagent],  # Add parallel processing capability!
    )
