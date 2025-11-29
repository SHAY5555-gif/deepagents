"""
Async Deep Agent with XAI Grok-4.1 FAST REASONING MODEL and Chrome DevTools MCP
ULTRA-FAST REASONING + MAXIMUM CAPABILITIES!

This agent uses Grok-4.1 Fast Reasoning (grok-4-1-fast-reasoning-latest) from XAI:
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
from firecrawl import Firecrawl
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
# from parallel_processor_subagent import create_parallel_processor_subagent


# ============================================
# FireCrawl SDK Tools - Direct API Integration
# ============================================

# Global FireCrawl client cache
_firecrawl_client = None


def get_firecrawl_client():
    """Get or initialize FireCrawl SDK client"""
    global _firecrawl_client

    if _firecrawl_client is None:
        # Initialize with API key from environment
        # Set FIRECRAWL_API_KEY environment variable
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY environment variable not set. "
                "Get your API key from https://firecrawl.dev"
            )
        _firecrawl_client = Firecrawl(api_key=api_key)

    return _firecrawl_client


@tool
def firecrawl_scrape_url(url: str, formats: Optional[List[str]] = None) -> str:
    """Scrape a single webpage and extract content.

    Args:
        url: The URL to scrape
        formats: Optional list of formats to extract. Options: 'markdown', 'html', 'rawHtml', 'screenshot', 'links'
                Default: ['markdown']

    Returns:
        JSON string with scraped content
    """
    try:
        client = get_firecrawl_client()

        if formats is None:
            formats = ['markdown']

        result = client.scrape_url(
            url=url,
            params={
                'formats': formats,
                'onlyMainContent': True  # Extract only main content, filter out navigation/footers
            }
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def firecrawl_extract_structured_data(
    url: str,
    prompt: str,
    schema: Optional[str] = None
) -> str:
    """Extract structured data from a webpage using AI (EXTRACT feature).

    This is the most powerful feature - uses LLM to extract exactly what you need
    from web pages without writing CSS selectors or parsing HTML.

    Args:
        url: The URL to extract data from (use 'https://example.com/*' for full site)
        prompt: Natural language description of what data to extract
        schema: Optional JSON schema as string defining the expected output structure

    Returns:
        JSON string with extracted structured data

    Examples:
        Extract product info:
        firecrawl_extract_structured_data(
            url="https://shop.example.com/products",
            prompt="Extract all product names, prices, and descriptions",
            schema='{"type": "object", "properties": {"products": {"type": "array"}}}'
        )

        Extract from entire website:
        firecrawl_extract_structured_data(
            url="https://blog.example.com/*",
            prompt="Extract all blog posts with titles and authors"
        )
    """
    try:
        client = get_firecrawl_client()

        # Parse schema if provided
        schema_dict = None
        if schema:
            try:
                schema_dict = json.loads(schema)
            except json.JSONDecodeError:
                return json.dumps({
                    'success': False,
                    'error': 'Invalid JSON schema provided'
                }, ensure_ascii=False)

        # Extract data using AI
        result = client.extract(
            urls=[url],
            prompt=prompt,
            schema=schema_dict
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def firecrawl_extract_with_pydantic_schema(
    url: str,
    prompt: str,
    schema_name: str,
    schema_properties: str
) -> str:
    """Extract structured data with a Pydantic-style schema definition.

    This is the RECOMMENDED way to use EXTRACT - provides better type validation
    and more consistent results than prompt-only extraction.

    Args:
        url: The URL to extract data from
        prompt: Description of what to extract
        schema_name: Name of the main schema object
        schema_properties: JSON string describing the schema properties

    Returns:
        JSON string with extracted data matching the schema

    Example:
        firecrawl_extract_with_pydantic_schema(
            url="https://news.example.com",
            prompt="Extract article information",
            schema_name="Article",
            schema_properties='''{
                "title": {"type": "string", "description": "Article title"},
                "author": {"type": "string", "description": "Author name"},
                "content": {"type": "string", "description": "Article content"}
            }'''
        )
    """
    try:
        client = get_firecrawl_client()

        # Parse schema properties
        try:
            properties = json.loads(schema_properties)
        except json.JSONDecodeError:
            return json.dumps({
                'success': False,
                'error': 'Invalid JSON in schema_properties'
            }, ensure_ascii=False)

        # Build JSON schema
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys())
        }

        # Extract data
        result = client.extract(
            urls=[url],
            prompt=prompt,
            schema=schema
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


# NOTE: firecrawl_crawl_website and firecrawl_map_website are DISABLED
# These tools can consume thousands of credits by crawling multiple pages
# Use only single-page extraction tools (firecrawl_scrape_url, firecrawl_extract_structured_data)


# No demo tools - using only real MCP and FireCrawl SDK tools



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
    """Get or initialize MCP tools from Chrome DevTools only (FireCrawl now via SDK)"""
    global _mcp_client, _chrome_tools

    if _chrome_tools is None:
        from datetime import timedelta
        import logging

        logger = logging.getLogger(__name__)

        # Connect to Chrome DevTools MCP only - FireCrawl is now via SDK
        _mcp_client = MultiServerMCPClient({
            # Chrome DevTools MCP from Smithery - REMOTE HTTP with SSE
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http",  # SSE transport
                "timeout": timedelta(seconds=30),  # 30 seconds timeout
                "sse_read_timeout": timedelta(seconds=30),  # 30 seconds SSE read timeout
            },
            # NOTE: FireCrawl is now integrated via SDK instead of MCP for better performance
            # The SDK provides:
            # - 50x faster performance compared to MCP
            # - Direct API access without MCP overhead
            # - Better error handling and retry logic
            # - More reliable connection management
        })

        # Load tools from each server individually with error handling
        # This allows the agent to work even if some MCP servers are unavailable
        raw_tools = []
        for server_name in _mcp_client.connections:
            try:
                logger.info(f"Loading tools from MCP server: {server_name}")
                server_tools = await _mcp_client.get_tools(server_name=server_name)
                raw_tools.extend(server_tools)
                logger.info(f"Successfully loaded {len(server_tools)} tools from {server_name}")
            except Exception as e:
                logger.warning(
                    f"Failed to load tools from {server_name}. "
                    f"Error: {e.__class__.__name__}: {str(e)}. "
                    f"Continuing with other servers..."
                )
                continue

        # Wrap ALL tools with error handling so they never crash
        _chrome_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]

        logger.info(f"Total tools loaded: {len(_chrome_tools)}")

    return _chrome_tools


async def agent():
    """Async factory function for LangGraph Studio using GROK-4.1 FAST REASONING MODEL.

    Grok-4.1 Fast Reasoning advantages (grok-4-1-fast-reasoning-latest):
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
    # Get all MCP tools (Chrome DevTools only)
    mcp_tools = await get_mcp_tools()

    # Add FireCrawl SDK tools (direct API access - much faster than MCP!)
    # NOTE: Only single-page tools enabled to prevent accidental credit consumption
    firecrawl_tools = [
        firecrawl_scrape_url,
        firecrawl_extract_structured_data,
        firecrawl_extract_with_pydantic_schema,
        # firecrawl_crawl_website - DISABLED (can consume thousands of credits)
        # firecrawl_map_website - DISABLED (can consume thousands of credits)
    ]

    # Combine MCP tools with FireCrawl SDK tools
    # Note: File system tools are provided automatically by FilesystemMiddleware in create_deep_agent
    # Using custom file tools here would bypass the files state tracking needed for the UI
    all_tools = mcp_tools + firecrawl_tools

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

**BROWSER AUTOMATION TOOLS** (Chrome DevTools MCP):
- navigate_page: Navigate to ANY website
- take_screenshot: Take screenshots of web pages
- take_snapshot: Get text content of pages
- click, fill, fill_form: Interact with web elements
- list_pages, new_page: Manage browser tabs
- evaluate_script: Run JavaScript on pages
- list_network_requests, list_console_messages: Debug and monitor
- And 100+ more Chrome DevTools capabilities!

**WEB SCRAPING TOOLS** (FireCrawl SDK - Direct API, 50x Faster!):
- firecrawl_scrape_url: Scrape a single webpage and extract content
- firecrawl_extract_structured_data: Extract structured data using AI (EXTRACT feature!)
- firecrawl_extract_with_pydantic_schema: Extract with Pydantic schema for best results
- Direct SDK integration = Much faster than MCP!
- No MCP overhead = Better reliability and performance!

⚠️ IMPORTANT - CREDIT PROTECTION:
- Only SINGLE-PAGE extraction is enabled
- Multi-page crawling tools are DISABLED to prevent accidental credit consumption
- Always extract from ONE URL at a time
- Use wildcards (*) in URLs with EXTREME caution - can consume thousands of credits!

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

    # Create XAI Grok-4.1 Fast Reasoning MODEL with MAXIMUM capabilities
    # This is Grok-4.1 Fast Reasoning (grok-4-1-fast-reasoning-latest):
    # - 2M token context window (MASSIVE!)
    # - 128,000 max output tokens
    # - Fast reasoning with extended thinking
    # - Ultra-low cost: $0.20/M input, $0.50/M output
    # - 4M tokens per minute throughput
    # - Function calling, live search, image inputs
    # - Fewer restrictions and more direct responses than Claude

    MODEL_NAME = "grok-4-1-fast-reasoning-latest"
    print(f"\n{'='*80}")
    print(f"[mcp_agent_grok_fast] Creating agent with model: {MODEL_NAME}")
    print(f"{'='*80}\n")

    model = ChatXAI(
        model=MODEL_NAME,  # Fast Reasoning model - UPDATED to 4.1
        max_tokens=128000,  # MAXIMUM output tokens (128K!)
        temperature=1.0,  # Full flexibility
        # Note: Fast reasoning model - combines speed with deep thinking
        # Best for complex tasks requiring both intelligence and speed
        max_retries=3,
        timeout=900,  # 15 minutes for complex reasoning
    )

    # Create parallel processor subagent
    # parallel_subagent = create_parallel_processor_subagent()

    # Create and return the deep agent with:
    # - Grok Fast for main reasoning
    # - Default summarization (can't override - would cause duplicate middleware error)
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
        # subagents=[parallel_subagent],  # Disabled for production compatibility
    )
