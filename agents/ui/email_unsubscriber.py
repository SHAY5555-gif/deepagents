"""
Email Unsubscriber Agent - Specialized for Gmail unsubscribe tasks
==================================================================

Agent that unsubscribes from email mailing lists via Gmail.
Uses Chrome DevTools MCP for browser automation.

Workflow:
1. Navigate to Gmail Promotions tab
2. Search for emails from specific sender
3. Open the email
4. Find and click unsubscribe link
5. Complete unsubscribe form if needed
"""
import asyncio
import logging
import os
import json
from datetime import timedelta
from functools import wraps

from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_xai import ChatXAI
from deepagents import create_deep_agent

logger = logging.getLogger(__name__)

# ============================================
# Error Handling Wrapper
# ============================================

def create_error_handling_wrapper(tool_obj):
    """Wrap tool to return errors as strings instead of raising exceptions"""
    original_afunc = tool_obj.coroutine if hasattr(tool_obj, 'coroutine') else tool_obj._arun

    @wraps(original_afunc)
    async def wrapped_async(*args, **kwargs):
        try:
            result = await original_afunc(*args, **kwargs)
            if result is None:
                return "null"
            if isinstance(result, (list, dict)):
                return json.dumps(result, ensure_ascii=False, indent=2)
            if not isinstance(result, str):
                return str(result)
            if result == "":
                return "(empty result)"
            return result
        except Exception as e:
            error_msg = f"[ERROR] {type(e).__name__}: {str(e)}"
            logger.warning(f"Tool {tool_obj.name} failed: {error_msg}")
            return error_msg

    return StructuredTool(
        name=tool_obj.name,
        description=tool_obj.description,
        args_schema=tool_obj.args_schema,
        coroutine=wrapped_async,
        handle_tool_error=True,
    )


# ============================================
# MCP Tools Setup
# ============================================

_mcp_client = None
_mcp_tools = None
_initialization_lock = asyncio.Lock()


async def get_mcp_tools():
    """Get Chrome DevTools MCP tools"""
    global _mcp_client, _mcp_tools

    async with _initialization_lock:
        if _mcp_tools is not None:
            return _mcp_tools

        logger.info("=" * 80)
        logger.info("INITIALIZING CHROME DEVTOOLS MCP FOR EMAIL UNSUBSCRIBER")
        logger.info("=" * 80)

        _mcp_client = MultiServerMCPClient({
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@anthropics/claude-code-mcp-adapters/chrome-devtools/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http",
                "timeout": timedelta(seconds=60),
                "sse_read_timeout": timedelta(seconds=60),
            },
        })

        raw_tools = []
        for server_name in _mcp_client.connections:
            try:
                logger.info(f"Loading tools from MCP server: {server_name}")
                server_tools = await _mcp_client.get_tools(server_name=server_name)
                raw_tools.extend(server_tools)
                logger.info(f"Successfully loaded {len(server_tools)} tools from {server_name}")
            except Exception as e:
                logger.warning(f"Failed to load tools from {server_name}: {e}")
                continue

        _mcp_tools = [create_error_handling_wrapper(t) for t in raw_tools]
        logger.info(f"Total MCP tools loaded: {len(_mcp_tools)}")

        return _mcp_tools


def create_unsubscribe_prompt(sender_name: str) -> str:
    """Create a focused prompt for unsubscribing from a specific sender"""

    return f'''You are an EMAIL UNSUBSCRIBE SPECIALIST. Your ONLY task is to unsubscribe from emails sent by: **{sender_name}**

CRITICAL RULES:
1. You MUST use browser tools - no shortcuts, no excuses
2. Every action requires a tool call - DO NOT skip steps
3. After EVERY action, call take_snapshot to see the result
4. If something fails, TRY AGAIN with a different approach
5. DO NOT stop until you complete the unsubscribe OR confirm it's impossible

EXACT WORKFLOW - FOLLOW STEP BY STEP:

STEP 1: CHECK BROWSER STATE
- Call: list_pages
- If no pages or error: call new_page with url="https://mail.google.com"
- If page exists: call take_snapshot to see current state

STEP 2: NAVIGATE TO GMAIL (if not already there)
- Call: navigate_page with url="https://mail.google.com" and timeout=30000
- Call: take_snapshot to verify Gmail loaded
- Look for "Promotions" tab in the snapshot

STEP 3: GO TO PROMOTIONS TAB
- Call: take_snapshot to find elements
- Look for element with text "Promotions" or "קידומי מכירות"
- Call: click with the uid of the Promotions tab
- Call: take_snapshot to verify you're in Promotions

STEP 4: SEARCH FOR SENDER "{sender_name}"
- Look for search box (usually has placeholder "Search mail" or "חיפוש בדואר")
- Call: click on the search box uid
- Call: fill with uid of search box and value="from:{sender_name}"
- Press Enter by calling: evaluate_script with function="() => document.querySelector('input[aria-label*=\"Search\"]')?.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', keyCode: 13}}))"
- OR click the search button if visible
- Call: take_snapshot to see search results

STEP 5: OPEN AN EMAIL FROM "{sender_name}"
- Call: take_snapshot to find email list
- Look for email row/item from the sender
- Call: click on the email uid to open it
- Call: take_snapshot to verify email is open

STEP 6: FIND UNSUBSCRIBE LINK
- Call: take_snapshot with the email open
- Look for ANY of these patterns in the snapshot:
  * "Unsubscribe" link/button
  * "הסרה מרשימת תפוצה"
  * "Click here to unsubscribe"
  * "Manage preferences"
  * "Update subscription"
  * Link at bottom of email
- If you see "Unsubscribe" text near sender at TOP of email, click it (Gmail's built-in unsubscribe)
- Call: click on the unsubscribe element uid

STEP 7: COMPLETE UNSUBSCRIBE PROCESS
- Call: take_snapshot after clicking unsubscribe
- You may see:
  a) Gmail popup asking to confirm - click "Unsubscribe" button
  b) New tab/page with unsubscribe form - fill it and submit
  c) Confirmation message - you're done!
- If there's a form, fill required fields and click submit/confirm
- Call: take_snapshot to verify completion

STEP 8: REPORT RESULT
- Report SUCCESS if you see confirmation message
- Report FAILURE only if you tried everything and it's truly impossible

TOOL USAGE EXAMPLES:

To click an element:
call click with uid="abc123"

To fill a text field:
call fill with uid="xyz789" and value="some text"

To take a snapshot:
call take_snapshot (no parameters needed)

To navigate:
call navigate_page with url="https://..." and timeout=30000

ERROR RECOVERY:
- "Element not found" -> call take_snapshot and find the correct uid
- "Timeout" -> increase timeout to 60000 and retry
- "No pages" -> call new_page first
- Page not loading -> call navigate_page again

SENDER TO UNSUBSCRIBE FROM: **{sender_name}**

START NOW. Call list_pages first.'''


async def agent():
    """Create Email Unsubscriber agent"""
    mcp_tools = await get_mcp_tools()

    # Default prompt - will be overridden by user message
    system_prompt = '''You are an EMAIL UNSUBSCRIBE SPECIALIST powered by Grok-4.1 Fast Reasoning.

Your job: Unsubscribe from email mailing lists using Gmail browser automation.

CORE PRINCIPLES:
1. ALWAYS use browser tools - take_snapshot, click, fill, navigate_page
2. NEVER assume - always verify with take_snapshot
3. NEVER give up - try multiple approaches
4. ALWAYS follow the step-by-step workflow

AVAILABLE TOOLS (USE THEM!):
- list_pages: Check browser state
- new_page: Create new browser tab
- navigate_page: Go to a URL
- take_snapshot: See page content and get element UIDs
- click: Click an element by uid
- fill: Type text into an element
- evaluate_script: Run JavaScript

WORKFLOW:
1. list_pages -> new_page if needed
2. navigate_page to Gmail
3. take_snapshot -> find Promotions tab
4. click Promotions
5. take_snapshot -> find search box
6. fill search with "from:SENDER_NAME"
7. take_snapshot -> find email
8. click email to open
9. take_snapshot -> find unsubscribe link
10. click unsubscribe
11. take_snapshot -> complete any form
12. Report result

START WITH: list_pages'''

    MODEL_NAME = "grok-4-1-fast-reasoning-latest"

    print(f"\n{'='*80}")
    print(f"[EMAIL-UNSUBSCRIBER] Starting with model: {MODEL_NAME}")
    print(f"{'='*80}\n")

    model = ChatXAI(
        model=MODEL_NAME,
        max_tokens=128000,
        temperature=0.7,  # Lower for more focused responses
        max_retries=3,
        timeout=900,
    )

    return create_deep_agent(
        model=model,
        tools=mcp_tools,
        system_prompt=system_prompt,
    )


# Export prompt generator for external use
__all__ = ['agent', 'create_unsubscribe_prompt']
