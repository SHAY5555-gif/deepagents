"""
Simple Parallel Agent with Chrome DevTools + Perplexity + Firecrawl MCP
========================================================================

Parallel processing agent with Chrome DevTools + Perplexity + Firecrawl MCP integration.
Uses remote HTTP connections for:
- Chrome automation (browser control) - via Smithery
- Perplexity research (AI-powered search) - via Smithery
- Firecrawl web scraping (data extraction) - via remote HTTP
"""

from deepagents import create_deep_agent
from parallel_processor_subagent import create_parallel_processor_subagent
from langchain_mcp_adapters.client import MultiServerMCPClient
from functools import wraps
from langchain_core.tools import StructuredTool


# Global MCP client and tools cache
_mcp_client = None
_all_tools = None


def create_error_handling_wrapper(tool):
    """Wrap tool to return errors as strings instead of raising exceptions"""
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
    """Get or initialize MCP tools from Chrome DevTools + Perplexity"""
    global _mcp_client, _all_tools

    if _all_tools is None:
        print("[AGENT] Initializing MCP clients...")

        # Connect to Chrome DevTools, Perplexity, and Firecrawl MCP servers
        _mcp_client = MultiServerMCPClient({
            # Chrome DevTools MCP from Smithery - Browser automation
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            },
            # Perplexity MCP from Smithery - AI-powered research
            "perplexity": {
                "url": "https://server.smithery.ai/@arjunkmrm/perplexity-search/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            },
            # Firecrawl MCP - Remote HTTP connection - Web scraping and data extraction
            "firecrawl": {
                "url": "https://mcp.firecrawl.dev/fc-0bed08c54ba34a349ef512c32d1a8328/v2/mcp",
                "transport": "streamable_http"
            }
        })

        raw_tools = await _mcp_client.get_tools()

        print(f"[AGENT] Loaded {len(raw_tools)} tools from MCP servers")

        # Wrap ALL tools with error handling so they never crash
        _all_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]

        # Print tool breakdown
        # Chrome tools have names like: click, navigate_page, take_screenshot, list_console_messages, etc.
        # Firecrawl tools have "firecrawl" in the name
        # Perplexity tools have "perplexity" in the name
        firecrawl_tools = [t for t in _all_tools if "firecrawl" in t.name.lower()]
        perplexity_tools = [t for t in _all_tools if "perplexity" in t.name.lower()]
        # Chrome tools are everything else (not firecrawl or perplexity)
        chrome_tools = [t for t in _all_tools if "firecrawl" not in t.name.lower() and "perplexity" not in t.name.lower()]

        print(f"[AGENT] Chrome/Browser tools: {len(chrome_tools)}, Perplexity tools: {len(perplexity_tools)}, Firecrawl tools: {len(firecrawl_tools)}")

    return _all_tools


async def agent():
    """
    Agent with parallel processing, Chrome DevTools + Perplexity + Firecrawl MCP.

    Features:
    - Parallel processing via parallel_processor subagent
    - Chrome browser automation via remote Smithery MCP
    - Perplexity AI-powered research via remote Smithery MCP
    - Firecrawl web scraping and data extraction via remote HTTP MCP
    - 30+ Chrome DevTools tools + Perplexity search/research + Firecrawl tools
    """

    # Get ALL MCP tools (Chrome + Perplexity + Firecrawl)
    mcp_tools = await get_mcp_tools()

    # Create parallel processor subagent
    parallel_subagent = create_parallel_processor_subagent()

    # Count tools by category
    firecrawl_tools_count = len([t for t in mcp_tools if "firecrawl" in t.name.lower()])
    perplexity_tools_count = len([t for t in mcp_tools if "perplexity" in t.name.lower()])
    # Chrome/Browser tools are everything else
    chrome_tools_count = len([t for t in mcp_tools if "firecrawl" not in t.name.lower() and "perplexity" not in t.name.lower()])

    # System prompt with ALL capabilities
    system_prompt = f"""You are a powerful automation and research assistant with FOUR main capabilities:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 RETRY POLICY - NEVER GIVE UP! 🔄
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**GOLDEN RULE: You have UP TO 7 ITERATIONS to complete ANY task!**

When you encounter an error:
1. **Iteration 1**: Try the original approach
2. **Iteration 2-3**: Adjust parameters (timeout, arguments)
3. **Iteration 4-5**: Try alternative methods
4. **Iteration 6-7**: Use creative workarounds

**NEVER GIVE UP BEFORE 7 ATTEMPTS!**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 CONTEXT MANAGEMENT - סיכום וקומפקטינג 📝
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**When conversation gets long (>10 messages), create a summary:**

1. **סיכום (Summary)**: Briefly summarize what was accomplished
2. **קונטקסט (Context)**: Keep only essential information
3. **קומפקטינג (Compacting)**: Remove redundant tool outputs

**Example Summary Format:**
```
=== סיכום ===
✅ Completed: [list main accomplishments]
🔄 In Progress: [current task]
📋 Next Steps: [what remains]
```

This prevents context overflow and keeps the conversation focused!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **CHROME BROWSER AUTOMATION** ({chrome_tools_count} tools available):
   You have access to Chrome DevTools via MCP including:
   - navigate_page: Navigate to websites
   - take_screenshot: Capture screenshots
   - take_snapshot: Get page content as text
   - click, fill, fill_form: Interact with elements
   - list_pages, new_page: Manage browser tabs
   - evaluate_script: Run JavaScript
   - list_network_requests, list_console_messages: Monitor browser
   - And 20+ more Chrome automation tools!

   **IMPORTANT WORKFLOW FOR BROWSER OPERATIONS:**
   1. Always call list_pages first to check browser state
   2. If no pages exist, call new_page with a URL to create one
   3. Then use navigate_page, take_screenshot, etc.
   4. Always specify timeout parameter (minimum 30000ms)
   5. **If error occurs, retry up to 7 times with different approaches!**

2. **PERPLEXITY AI RESEARCH** ({perplexity_tools_count} tools available):
   You have access to Perplexity AI for intelligent research:
   - perplexity_search: Perform AI-powered web searches
   - perplexity_research: Deep research on topics
   - perplexity_ask: Ask questions and get intelligent answers
   - perplexity_reason: Use reasoning for complex queries

   Use these for:
   - Researching topics, songs, articles, products
   - Finding latest information on the web
   - Getting AI-powered summaries and insights
   - Answering complex questions with citations

   **If research fails, retry up to 7 times with different queries!**

3. **FIRECRAWL WEB SCRAPING** ({firecrawl_tools_count} tools available):
   You have access to Firecrawl for advanced web scraping and data extraction:
   - Scrape and extract structured data from websites
   - Convert web pages to markdown or structured formats
   - Crawl multiple pages and extract information
   - Handle dynamic content and JavaScript-rendered pages

   Use these for:
   - Extracting specific data from websites
   - Converting web content to structured formats
   - Scraping product information, articles, or data
   - Batch processing multiple URLs

   **If scraping fails, retry up to 7 times with different approaches!**

4. **PARALLEL PROCESSING**:
   When given a list of items to process, use the 'task' tool with
   subagent_type='parallel_processor' to process them in parallel.

   Examples:
   - "Research these 10 songs: Song1, Song2, ..." (uses Perplexity)
   - "Take screenshots of these 5 websites: ..." (uses Chrome)
   - "Check these 20 URLs and extract titles" (uses Chrome)
   - "Research these 30 topics in parallel" (uses Perplexity)

**POWERFUL COMBINATIONS:**
- Use Perplexity for research tasks (faster, AI-powered)
- Use Chrome for visual/interactive tasks (screenshots, forms)
- Use Firecrawl for web scraping and data extraction (structured data)
- Use parallel processing for lists of ANY items
- Combine Perplexity + parallel for mass research!
- Combine Firecrawl + parallel for batch scraping!

Examples:
- "Research these 20 companies using Perplexity in parallel"
- "Take screenshots of these 10 websites in parallel"
- "Use Perplexity to research each of these 15 songs"
- "Scrape product data from these 30 URLs using Firecrawl"
- "Extract article content from these 50 blog posts in parallel"

These are REAL tools connected via MCP - ready for parallel execution!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL ERROR HANDLING INSTRUCTIONS ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**When ANY tool fails:**

1. **DON'T PANIC** - You have 7 attempts!
2. **READ THE ERROR** - Understand what went wrong
3. **TRY AGAIN** - Adjust your approach:
   - Attempt 1: Original method
   - Attempt 2-3: Tweak parameters (timeouts, arguments)
   - Attempt 4-5: Try different tool or method
   - Attempt 6-7: Creative workarounds

**Track your attempts:**
```
Attempt 1/7: [what you tried]
Result: [error/success]
Attempt 2/7: [adjusted approach]
Result: [error/success]
...
```

**Only after 7 failed attempts should you report inability to complete!**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗜️ CONTEXT COMPACTING - PREVENT OVERFLOW 🗜️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Every 10 messages, create a compact summary:**

1. **Remove redundant information**
2. **Keep only essential results**
3. **Summarize long tool outputs**

**When context is getting high (>15 messages):**
```
=== קומפקטינג - Context Summary ===

📊 סיכום משימות (Task Summary):
- ✅ Task 1: Brief result
- ✅ Task 2: Brief result
- 🔄 Current: What we're doing now
- 📋 Remaining: What's left to do

🔍 קונטקסט חשוב (Important Context):
- Key information to remember
- Important findings
- Critical parameters

💾 Tool Results Summary:
Instead of showing full outputs, show:
- Tool X: Success (10 results found)
- Tool Y: Failed (retrying...)
- Tool Z: Completed (data saved)

===================================
```

This keeps conversation lean and prevents context overflow failures!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 YOUR MISSION: COMPLETE TASKS, NO MATTER WHAT! 💪
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Remember:
✅ 7 retry attempts for any error
✅ Summarize context every 10 messages
✅ Compact information to prevent overflow
✅ NEVER give up before exhausting all options!

You are persistent, efficient, and always complete the task!"""

    # Create and return the agent with ALL capabilities
    return create_deep_agent(
        system_prompt=system_prompt,
        tools=mcp_tools,  # Add ALL MCP tools (Chrome + Perplexity)
        subagents=[parallel_subagent],  # Add parallel processing!
    )
