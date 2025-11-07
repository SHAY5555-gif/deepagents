"""
Async Deep Agent with OpenAI GPT-5 and Chrome DevTools MCP
OPENAI'S LATEST & MOST CAPABLE MODEL - Production-Ready with Built-in Reasoning!

This agent uses GPT-5 from OpenAI:
- Latest model optimized for coding and agentic tasks
- Built-in reasoning capabilities (no separate reasoning tokens!)
- 128K context window
- Adjustable reasoning effort (minimal/low/medium/high)
- Verbosity control for output length
- Function calling for all MCP tools
- Cost-efficient: $1.25/1M input, $10/1M output
- Best performance on coding benchmarks (74.9% SWE-bench)

Advantages:
- PRODUCTION-READY stable model from OpenAI
- Built-in reasoning without extra complexity
- Excellent tool calling and function execution
- Flexible reasoning and verbosity controls
- Strong coding and problem-solving capabilities
- Lower cost than o3 reasoning model

Ideal for:
- Complex web automation tasks
- Multi-step problem solving
- Code generation and debugging
- Production deployments requiring reliability
- Cost-sensitive applications needing reasoning
"""
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent


# Simulated demo tools
@tool
def get_cryptocurrency_price(symbol: str) -> str:
    """Get the current price of a cryptocurrency."""
    prices = {"BTC": "$45,000", "ETH": "$2,500", "ADA": "$0.50"}
    return f"[MCP Tool: CoinCap] {symbol} price: {prices.get(symbol.upper(), 'Unknown')}"

@tool
def search_web_for_task_help(task_description: str) -> str:
    """Search the web for HOW TO perform a specific task or action.
    Use this BEFORE attempting complex tasks to learn the best approach.

    Args:
        task_description: Description of what you want to accomplish

    Returns:
        Step-by-step instructions and best practices for the task

    Example: search_web_for_task_help("how to scrape data from a website using Python")
    """
    import requests
    try:
        # Use DuckDuckGo instant answer API for quick how-to searches
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": f"how to {task_description}", "format": "json"},
            timeout=10
        )
        data = response.json()

        if data.get("AbstractText"):
            return f"[Web Search Result]\n\n{data['AbstractText']}\n\nSource: {data.get('AbstractURL', 'DuckDuckGo')}"
        elif data.get("RelatedTopics"):
            topics = data["RelatedTopics"][:3]
            result = "[Web Search - Related Information]\n\n"
            for i, topic in enumerate(topics, 1):
                if isinstance(topic, dict) and "Text" in topic:
                    result += f"{i}. {topic['Text']}\n"
            return result
        else:
            return f"[Web Search] Search completed for: {task_description}\n\nSuggestion: Try breaking down the task into smaller steps or use specific technical terms."
    except Exception as e:
        return f"[Web Search] Could not search at this time. Proceeding with task based on internal knowledge."

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
    """Get or initialize MCP tools from Chrome DevTools"""
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
    """Async factory function for LangGraph Studio using OPENAI GPT-5.

    GPT-5 MAXIMUM CAPABILITIES:
    - Latest OpenAI model optimized for coding and agents
    - Built-in reasoning (adjustable effort: minimal/low/medium/high)
    - Verbosity control (low/medium/high) for output length
    - 128K context window
    - Function calling for all MCP tools
    - Best coding performance (74.9% SWE-bench Verified)
    - Production-ready with excellent reliability
    - Cost-efficient compared to o3 ($1.25 vs $2.00 input)
    """
    # Get all MCP tools
    mcp_tools = await get_mcp_tools()

    # Combine simulated tools with real MCP tools
    all_tools = [
        search_web_for_task_help,  # WEB SEARCH - Use FIRST for complex tasks!
        get_cryptocurrency_price,
        get_weather,
    ] + mcp_tools

    # System prompt - emphasizing GPT-5's capabilities with CLEAR STOP CONDITIONS
    system_prompt = f"""You are an INTELLIGENT, FOCUSED web automation agent powered by OpenAI GPT-5.

YOUR EXTRAORDINARY CAPABILITIES:
- You are OPENAI GPT-5 - the latest, most capable production model
- Built-in reasoning capabilities for complex problem-solving
- 128K context window - you remember extensive context
- You complete tasks EFFICIENTLY without getting stuck in loops
- You use CLEAR, DIRECT approaches - not endless retries
- You STOP when a task is COMPLETE or after 3 failed attempts

🎯 CRITICAL: BEFORE STARTING ANY COMPLEX TASK:
1. Use search_web_for_task_help to learn the BEST approach
2. Make a CLEAR PLAN with specific steps
3. Execute the plan ONCE - don't repeat the same failed approach
4. If something fails 3 times - STOP and report the issue
5. When task is COMPLETE - STOP immediately, don't add extra steps

YOU HAVE {len(all_tools)} WORKING TOOLS INCLUDING:

**BROWSER AUTOMATION TOOLS** ({len(mcp_tools)} Chrome DevTools tools):
You CAN and SHOULD use these tools to:
- navigate_page: Navigate to ANY website
- take_screenshot: Take screenshots of web pages
- take_snapshot: Get text content of pages
- click, fill, fill_form: Interact with web elements
- list_pages, new_page, new_page_default: Manage browser tabs
- evaluate_script: Run JavaScript on pages
- list_network_requests, list_console_messages: Debug and monitor
- And 19 more Chrome DevTools capabilities!

**DEMO TOOLS** (4 including web search):
- get_cryptocurrency_price, search_web_for_task_help, get_weather
- search_web_for_task_help - USE THIS to learn how to do complex tasks!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 SMART EXECUTION - NO LOOPS, NO ENDLESS RETRIES! 🎯
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**GOLDEN RULE #1: COMPLETE TASKS EFFICIENTLY WITHOUT LOOPS**

When you encounter an error, you MUST:
1. READ the error message carefully - understand WHAT failed
2. If it's a complex task you're unsure about - STOP and use search_web_for_task_help first!
3. DIAGNOSE the root cause - don't just retry blindly
4. TRY FIX #1 with a DIFFERENT approach (not the same thing again!)
5. If fix #1 fails → Try FIX #2 with ANOTHER different approach
6. If fix #2 fails → Try FIX #3 (last attempt)
7. If all 3 attempts fail → STOP and report the issue clearly

**YOU HAVE 3 SMART RETRIES** - After 3 different approaches, STOP and report!

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
💪 EXAMPLES OF SMART, EFFICIENT EXECUTION 💪
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXAMPLE 1 - Using Web Search BEFORE Complex Task:
User: "Scrape product prices from amazon.com"
You: STEP 1 - Research first!
You: *calls search_web_for_task_help("web scraping best practices")*
Result: [Web Search] Use API when available, respect robots.txt, etc.
You: STEP 2 - Execute with knowledge
You: *follows best practices from search result*
You: "Task completed following best practices!"

EXAMPLE 2 - Smart Retry with Different Approaches:
User: "Click the login button"
You: Attempt 1: *calls take_snapshot* → *calls click(uid='123')*
Result: Error "Element not found"
You: Attempt 2 - DIFFERENT approach: *takes new snapshot with different selector*
Result: Still fails
You: Attempt 3 - COMPLETELY different: *uses evaluate_script to click via JavaScript*
Result: Success!
You: "Login button clicked successfully on attempt 3!"

EXAMPLE 3 - Knowing When to STOP:
User: "Navigate to a non-existent page"
You: Attempt 1: *calls navigate_page with timeout=30000*
Result: Error "Page not found"
You: Attempt 2: *tries with different URL format*
Result: Still error "Page not found"
You: Attempt 3: *tries with http instead of https*
Result: Still error
You: STOP - Report: "Unable to navigate to page after 3 different approaches. Page may not exist."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚫 WHAT YOU MUST NEVER DO (CRITICAL FOR AVOIDING LOOPS!) 🚫
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ NEVER retry the SAME failed approach more than once
❌ NEVER continue after 3 different failed attempts - STOP and report!
❌ NEVER skip using search_web_for_task_help for complex/unfamiliar tasks
❌ NEVER add extra steps after task is COMPLETE - STOP immediately!
❌ NEVER forget to specify timeout parameters (minimum 30000)

✅ ALWAYS use search_web_for_task_help BEFORE complex tasks
✅ ALWAYS try DIFFERENT approaches when retrying (not the same thing!)
✅ ALWAYS STOP and report after 3 failed attempts
✅ ALWAYS make a CLEAR PLAN before executing
✅ ALWAYS STOP immediately when task is COMPLETE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ YOUR MISSION ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are GPT-5 - OpenAI's INTELLIGENT, EFFICIENT agent. You have:
✅ REAL browser automation tools (22+ Chrome DevTools!)
✅ Web search capability to learn HOW to do tasks
✅ Built-in reasoning capabilities (medium effort for balance)
✅ 128K context window to remember everything
✅ Low temperature (0.2) for focused, deterministic execution
✅ Anti-loop penalties to prevent repetitive behavior

Your job is to COMPLETE TASKS EFFICIENTLY AND SMARTLY:
1. RESEARCH first (use search_web_for_task_help for complex tasks)
2. PLAN clearly (know exactly what you'll do)
3. EXECUTE once (don't repeat the same failed approach)
4. STOP when done OR after 3 different failed attempts

Errors are normal - but LEARN from them. Try DIFFERENT approaches.
STOP when task is complete. Don't loop. Be efficient.

These are real tools connected to a live Chrome browser via Smithery!"""

    # Create OpenAI GPT-5 with OPTIMIZED configuration to prevent loops
    # This is OpenAI's latest production model with:
    # - Built-in reasoning (adjustable effort)
    # - 128K context window
    # - Excellent function calling
    # - Production stability
    # - Cost-efficient compared to o3
    #
    # CRITICAL CONFIGURATION FOR PREVENTING LOOPS AND IMPROVING COMPLETION:
    # - temperature: 0.2 - LOW to avoid randomness and loops (NOT 1.0!)
    # - reasoning_effort: "medium" - balanced reasoning (high is too slow)
    # - frequency_penalty: 0.5 - prevent repeating same actions
    # - presence_penalty: 0.5 - encourage new approaches, not loops
    # - max_retries: 5 - reduced from 10 (too many retries cause loops)
    # - timeout: 600 - 10 minutes (not 30, too long causes confusion)
    model = ChatOpenAI(
        model="gpt-5",  # Latest OpenAI model
        temperature=0.2,  # LOW temperature for focused, deterministic output (prevents loops!)
        # Medium reasoning effort - balanced speed and quality
        # Options: 'minimal', 'low', 'medium', 'high'
        # Use 'medium' for good balance - 'high' is too slow and expensive
        reasoning_effort="medium",  # Balanced reasoning (not high - causes slowness)
        # Anti-loop parameters - CRITICAL for preventing repetitive behavior
        frequency_penalty=0.5,  # Discourage repeating same actions/words
        presence_penalty=0.5,   # Encourage new approaches, not loops
        max_retries=5,  # Reduced retries - too many cause loops
        timeout=600,  # 10 minute timeout - shorter prevents confusion
        request_timeout=600,  # Match timeout
    )

    # Create and return the deep agent with optimized model
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
    )
