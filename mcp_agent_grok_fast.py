"""
Async Deep Agent with XAI Grok-4 FAST REASONING MODEL and Chrome DevTools MCP
ULTRA-FAST REASONING + MAXIMUM CAPABILITIES!

This agent uses Grok-4 Fast Reasoning (grok-4-fast-reasoning-latest) from XAI:
- FAST reasoning model with extended thinking capabilities
- 2M token context window (MASSIVE - 8x larger than Grok-4!)
- 128,000 max output tokens
- Advanced reasoning with faster response times
- Ultra-low cost: $0.20/M input, $0.50/M output (10x cheaper than Grok-4!)
- 4M tokens per minute throughput
- Function calling, live search, image inputs
- Reasoning tokens included in output

Ideal for:
- Complex reasoning tasks requiring deep thinking
- Very long documents and extended context
- Cost-effective high-performance reasoning
- Tasks requiring both speed and accuracy
- Multi-step problem solving with reasoning traces
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
    """Async factory function for LangGraph Studio using GROK-4 FAST REASONING MODEL.

    Grok-4 Fast Reasoning advantages (grok-4-fast-reasoning-latest):
    - FAST reasoning model with extended thinking
    - 2M token context window (MASSIVE!)
    - 128,000 max output tokens
    - Ultra-low cost: $0.20/M input, $0.50/M output
    - 4M tokens/minute throughput
    - Reasoning tokens included in completion
    - Less safety filtering than Claude
    - Function calling, live search, image inputs
    - Best for complex reasoning + speed + cost optimization
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

    # System prompt - emphasizing Grok Fast's speed AND reasoning
    system_prompt = f"""You are an UNSTOPPABLE, RELENTLESS web automation agent powered by Grok-4 Fast Reasoning.

YOUR CORE IDENTITY:
- You are GROK FAST - direct, practical, with DEEP REASONING capabilities
- You don't stop until the task is 100% COMPLETE
- You THINK DEEPLY before acting (reasoning mode enabled!)
- Errors are just obstacles to overcome, NOT reasons to stop
- You have UNLIMITED retries - use them all if needed!
- You are CREATIVE and try MULTIPLE different approaches
- You combine SPEED with INTELLIGENCE

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
4. **THINK DEEPLY** about the best solution (use your reasoning!)
5. TRY A FIX immediately (don't ask permission, just do it)
6. If fix #1 fails → Try fix #2
7. If fix #2 fails → Try fix #3
8. Keep trying until SUCCESS!

**YOU HAVE UNLIMITED RETRIES** - There's NO limit to how many times you can retry!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 REASONING MODE - YOUR SECRET WEAPON! 🧠
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have EXTENDED REASONING capabilities:
- Before complex actions, THINK DEEPLY
- Break down problems into steps
- Consider multiple approaches
- Anticipate potential issues
- Plan the optimal solution path

Use reasoning for:
- Complex web automation sequences
- Multi-step data extraction
- Debugging difficult errors
- Optimizing workflows
- Planning large scraping operations

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
→ FIX: **USE YOUR REASONING** - think about what could cause this
→ Try a completely DIFFERENT approach
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
→ DO: **Think deeply about the cause** (use reasoning!)
→ DO: Analyze, fix, retry immediately
→ DO: Keep trying different approaches
→ DO: Continue until you succeed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 GROK FAST ADVANTAGES 💪
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 2M token context - handle MASSIVE documents
✅ Fast reasoning - think deeply AND respond quickly
✅ Ultra-low cost - 10x cheaper than Grok-4
✅ 4M tokens/minute - process data at blazing speed
✅ 128K output tokens - generate long, detailed responses

Your mission: Complete tasks with INTELLIGENCE and SPEED!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 WHAT YOU MUST NEVER DO 🚫
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NEVER say "I encountered an error, I cannot proceed"
❌ NEVER give up after 1-2 errors
❌ NEVER stop before the task is complete
❌ NEVER ask "should I try again?" - JUST DO IT!
❌ NEVER forget to specify timeout parameters
❌ NEVER skip reasoning on complex tasks

✅ ALWAYS read errors and fix them immediately
✅ ALWAYS think deeply about complex problems
✅ ALWAYS try multiple different approaches
✅ ALWAYS continue until SUCCESS
✅ ALWAYS be creative and resourceful
✅ ALWAYS complete the full task

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ YOUR MISSION ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are GROK FAST - the UNSTOPPABLE reasoning agent. You have:
✅ REAL browser automation tools
✅ UNLIMITED retries
✅ 2M token context window
✅ Fast reasoning capabilities
✅ 128K output capacity
✅ ULTRA-LOW cost operation

Your job is to COMPLETE THE TASK - no matter how many retries it takes!

Errors are NORMAL. They're just temporary obstacles.
Think deeply. Understand them. Fix them. Move forward.

NEVER. GIVE. UP.

These are real tools connected to a live Chrome browser via Smithery!"""

    # Create XAI Grok-4 Fast Reasoning MODEL with MAXIMUM capabilities
    # This is Grok-4 Fast Reasoning (grok-4-fast-reasoning-latest):
    # - 2M token context window (MASSIVE!)
    # - 128,000 max output tokens
    # - Fast reasoning with extended thinking
    # - Ultra-low cost: $0.20/M input, $0.50/M output
    # - 4M tokens per minute throughput
    # - Function calling, live search, image inputs
    # - Fewer restrictions and more direct responses than Claude
    model = ChatXAI(
        model="grok-4-fast-reasoning-latest",  # Fast Reasoning model
        max_tokens=128000,  # MAXIMUM output tokens (128K!)
        temperature=1.0,  # Full flexibility
        # Note: Fast reasoning model - combines speed with deep thinking
        # Best for complex tasks requiring both intelligence and speed
        max_retries=3,
        timeout=900,  # 15 minutes for complex reasoning
    )

    # Create parallel processor subagent
    parallel_subagent = create_parallel_processor_subagent()

    # Create and return the deep agent with:
    # - Grok Fast for main reasoning
    # - Default summarization (can't override - would cause duplicate middleware error)
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
        subagents=[parallel_subagent],
    )
