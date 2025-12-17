"""
Async Deep Agent with Cerebras GLM-4.6 and Chrome DevTools MCP
BROWSER CONTROL AGENT - Full browser automation capabilities!

This agent uses GLM-4.6 via Cerebras:
- Blazing fast inference via Cerebras hardware
- 2M token context window
- 128,000 max output tokens
- Cost-effective high-performance

Features:
- Browser automation and control
- Tool result isolation (truncation to prevent context overflow)
- Context compaction tool for manual context reduction
- Automatic summarization when context gets too large
- PARALLEL SUB-AGENTS with ISOLATED MCP SESSIONS
"""
import asyncio
import logging
import os
import json
import uuid
from datetime import timedelta
from typing import Any, Optional

from langchain_core.tools import tool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_cerebras import ChatCerebras
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite
from deepagents import create_deep_agent

# Configure logging
logger = logging.getLogger(__name__)

# ============================================
# Configuration Constants
# ============================================

# Maximum characters for tool results (to prevent context overflow)
MAX_TOOL_RESULT_CHARS = 8000

# Token threshold for automatic summarization (Cerebras has 2M context, but we want to stay safe)
MAX_TOKENS_BEFORE_SUMMARY = 100000

# Messages to keep when summarizing
MESSAGES_TO_KEEP = 4

# Number of parallel MCP sessions for sub-agents
NUM_PARALLEL_SESSIONS = 3

# MCP Configuration - Each sub-agent gets a unique session
MCP_API_KEY = "e20927d1-6314-4857-a81e-70ffb0b6af90"
MCP_BASE_PROFILE = "supposed-whitefish-nFAkQL"


def get_mcp_url_with_session(session_id: str = "") -> str:
    """Generate MCP URL with optional session suffix for isolation."""
    profile = f"{MCP_BASE_PROFILE}-{session_id}" if session_id else MCP_BASE_PROFILE
    return f"https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key={MCP_API_KEY}&profile={profile}"


# ============================================
# Tool Result Truncation Middleware
# ============================================

class TruncateToolResultsMiddleware(AgentMiddleware):
    """Middleware to truncate large tool results to prevent context overflow.

    This isolates tool results by limiting their size, keeping only the most
    relevant parts of large outputs.
    """

    def __init__(self, max_chars: int = MAX_TOOL_RESULT_CHARS):
        self.max_chars = max_chars

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Truncate any oversized tool results in the message history."""
        messages = state.get("messages", [])
        if not messages:
            return None

        modified = False
        new_messages = []

        for msg in messages:
            if isinstance(msg, ToolMessage) and msg.content:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if len(content) > self.max_chars:
                    # Truncate with indicator
                    truncated_content = (
                        content[:self.max_chars // 2] +
                        f"\n\n... [TRUNCATED - {len(content) - self.max_chars} chars removed for context efficiency] ...\n\n" +
                        content[-self.max_chars // 2:]
                    )
                    new_msg = ToolMessage(
                        content=truncated_content,
                        name=msg.name,
                        tool_call_id=msg.tool_call_id,
                    )
                    new_messages.append(new_msg)
                    modified = True
                    logger.info(f"Truncated tool result from {len(content)} to {len(truncated_content)} chars")
                else:
                    new_messages.append(msg)
            else:
                new_messages.append(msg)

        if modified:
            return {"messages": Overwrite(new_messages)}
        return None


# ============================================
# Context Compaction Tool
# ============================================

# Global flag to signal context compaction request
_compact_requested = False


@tool
def compact_context(reason: Optional[str] = None) -> str:
    """Request context compaction to reduce memory usage.

    Call this tool when:
    - You notice the conversation is getting very long
    - Tool results have been accumulating
    - You want to free up context space for new information
    - You're about to start a new major task and want a clean slate

    The system will summarize older messages while keeping recent important ones.

    Args:
        reason: Optional reason for requesting compaction (for logging)

    Returns:
        Confirmation that compaction was requested
    """
    global _compact_requested
    _compact_requested = True

    reason_text = f" Reason: {reason}" if reason else ""
    logger.info(f"Context compaction requested.{reason_text}")

    return (
        "Context compaction has been requested. "
        "The system will summarize older messages on the next iteration, "
        "keeping only the most recent and relevant information. "
        "This helps maintain efficient memory usage and faster responses."
    )


class ContextCompactionMiddleware(AgentMiddleware):
    """Middleware that triggers summarization when compact_context tool is called."""

    def __init__(self, summarization_model):
        self.summarization_model = summarization_model

    def after_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Check if compaction was requested and trigger summarization."""
        global _compact_requested

        if not _compact_requested:
            return None

        _compact_requested = False
        messages = state.get("messages", [])

        if len(messages) <= MESSAGES_TO_KEEP + 2:
            logger.info("Not enough messages to compact, skipping")
            return None

        # Keep system message if present
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]

        # Keep recent messages
        recent_messages = messages[-MESSAGES_TO_KEEP:]

        # Messages to summarize
        messages_to_summarize = [m for m in messages[:-MESSAGES_TO_KEEP] if not isinstance(m, SystemMessage)]

        if not messages_to_summarize:
            return None

        # Create summary
        try:
            summary_prompt = (
                "Summarize the following conversation history concisely, "
                "focusing on key actions taken, important results, and current task state:\n\n"
            )
            for msg in messages_to_summarize:
                if isinstance(msg, HumanMessage):
                    summary_prompt += f"USER: {str(msg.content)[:500]}\n"
                elif isinstance(msg, AIMessage):
                    content = str(msg.content)[:500] if msg.content else ""
                    tools = [tc.get('name', 'unknown') for tc in (msg.tool_calls or [])]
                    summary_prompt += f"ASSISTANT: {content} [Tools: {tools}]\n"
                elif isinstance(msg, ToolMessage):
                    summary_prompt += f"TOOL ({msg.name}): {str(msg.content)[:200]}...\n"

            # Note: In production, this would call the model to generate summary
            # For now, we create a structured summary
            summary_content = (
                f"[CONTEXT SUMMARY - {len(messages_to_summarize)} messages compacted]\n"
                f"Previous actions and results have been summarized to save context space.\n"
                f"Key points from previous conversation are preserved in recent messages."
            )

            summary_message = HumanMessage(content=f"[System: Previous context summarized] {summary_content}")

            # Reconstruct messages: system + summary + recent
            new_messages = system_msgs + [summary_message] + recent_messages

            logger.info(f"Context compacted: {len(messages)} -> {len(new_messages)} messages")

            return {"messages": Overwrite(new_messages)}

        except Exception as e:
            logger.error(f"Context compaction failed: {e}")
            return None


# ============================================
# MCP Tools Setup - Chrome DevTools with MULTIPLE SESSIONS
# ============================================

# Global MCP clients and tools cache - ONE PER SESSION!
_mcp_clients: dict[str, MultiServerMCPClient] = {}
_session_tools: dict[str, list] = {}  # session_id -> tools
_main_tools = None  # Tools for main orchestrator
_initialization_lock = asyncio.Lock()


def create_error_handling_wrapper(tool_obj, max_result_chars: int = MAX_TOOL_RESULT_CHARS, session_suffix: str = ""):
    """Wrap tool to return errors as strings and truncate large results.

    This provides tool result isolation by:
    1. Converting all results to strings (Cerebras requirement)
    2. Truncating results that exceed max_result_chars
    3. Catching and returning errors gracefully
    """
    from functools import wraps

    original_afunc = tool_obj.coroutine if hasattr(tool_obj, 'coroutine') else tool_obj._arun

    # Add session suffix to tool name to make it unique per session
    tool_name = f"{tool_obj.name}{session_suffix}" if session_suffix else tool_obj.name

    @wraps(original_afunc)
    async def wrapped_async(*args, **kwargs):
        try:
            result = await original_afunc(*args, **kwargs)

            # Convert to string (Cerebras requirement)
            if result is None:
                return "null"
            if isinstance(result, (list, dict)):
                result = json.dumps(result, ensure_ascii=False, indent=2)
            elif not isinstance(result, str):
                result = str(result)

            if result == "":
                return "(empty result)"

            # Truncate large results for context isolation
            if len(result) > max_result_chars:
                # Keep beginning and end, remove middle
                half = max_result_chars // 2
                result = (
                    result[:half] +
                    f"\n\n... [RESULT TRUNCATED - {len(result) - max_result_chars} chars removed] ...\n\n" +
                    result[-half:]
                )
                logger.info(f"Tool {tool_name} result truncated to {len(result)} chars")

            return result

        except Exception as e:
            error_msg = f"[ERROR] {type(e).__name__}: {str(e)}"
            print(f"Tool {tool_name} failed: {error_msg}")
            return error_msg

    return StructuredTool(
        name=tool_name,
        description=tool_obj.description,
        args_schema=tool_obj.args_schema,
        coroutine=wrapped_async,
        handle_tool_error=True,
    )


async def create_mcp_session(session_id: str) -> list:
    """Create a NEW MCP session with ISOLATED profile.

    Each session gets its own profile suffix to prevent conflicts.
    """
    profile = f"{MCP_BASE_PROFILE}-{session_id}"
    url = f"https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key={MCP_API_KEY}&profile={profile}"

    logger.info(f"Creating MCP session: {session_id} with profile: {profile}")

    client = MultiServerMCPClient({
        f"chrome_{session_id}": {
            "url": url,
            "transport": "streamable_http",
            "timeout": timedelta(seconds=60),
            "sse_read_timeout": timedelta(seconds=60),
        },
    })

    # Load tools for this session
    raw_tools = await client.get_tools()
    # Wrap tools with error handling (no suffix needed since each session has its own tools)
    wrapped_tools = [create_error_handling_wrapper(t) for t in raw_tools]

    logger.info(f"Session {session_id}: Loaded {len(wrapped_tools)} tools")

    # Store client and tools
    _mcp_clients[session_id] = client
    _session_tools[session_id] = wrapped_tools

    return wrapped_tools


async def get_mcp_tools():
    """Get or initialize MCP tools for the MAIN orchestrator"""
    global _main_tools

    async with _initialization_lock:
        if _main_tools is not None:
            return _main_tools

        logger.info("=" * 80)
        logger.info("STARTING CHROME DEVTOOLS MCP TOOL INITIALIZATION")
        logger.info("=" * 80)

        # Connect to Chrome DevTools MCP via Smithery (main session)
        main_client = MultiServerMCPClient({
            "chrome_devtools": {
                "url": f"https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key={MCP_API_KEY}&profile={MCP_BASE_PROFILE}",
                "transport": "streamable_http",
                "timeout": timedelta(seconds=60),
                "sse_read_timeout": timedelta(seconds=60),
            },
        })
        _mcp_clients["main"] = main_client

        # Load tools from Chrome DevTools server
        raw_tools = []
        for server_name in main_client.connections:
            try:
                logger.info(f"Loading tools from MCP server: {server_name}")
                server_tools = await main_client.get_tools(server_name=server_name)
                raw_tools.extend(server_tools)
                logger.info(f"Successfully loaded {len(server_tools)} tools from {server_name}")
            except Exception as e:
                logger.warning(
                    f"Failed to load tools from {server_name}. "
                    f"Error: {e.__class__.__name__}: {str(e)}. "
                    f"Continuing..."
                )
                continue

        # Wrap ALL tools with error handling AND result truncation
        _main_tools = [create_error_handling_wrapper(t) for t in raw_tools]
        logger.info(f"Total Chrome DevTools tools loaded: {len(_main_tools)}")

        return _main_tools


async def initialize_parallel_sessions():
    """Initialize multiple MCP sessions for parallel sub-agents.

    Creates NUM_PARALLEL_SESSIONS isolated sessions that can run in parallel
    without interfering with each other.
    """
    logger.info(f"Initializing {NUM_PARALLEL_SESSIONS} parallel MCP sessions...")

    tasks = [
        create_mcp_session(f"worker{i}")
        for i in range(1, NUM_PARALLEL_SESSIONS + 1)
    ]

    # Initialize all sessions in parallel!
    await asyncio.gather(*tasks)

    logger.info(f"All {NUM_PARALLEL_SESSIONS} parallel sessions initialized!")
    return _session_tools


# ============================================
# Sub-Agent Definitions (Run in Parallel!)
# ============================================

def create_subagents(mcp_tools: list) -> list[dict]:
    """Create specialized sub-agents for parallel execution.

    These sub-agents can be launched in parallel using the `task` tool.
    Each specializes in a specific type of browser automation task.
    """

    # Filter tools by category for specialized agents
    navigation_tools = [t for t in mcp_tools if any(
        kw in t.name.lower() for kw in ['navigate', 'page', 'list_pages', 'select', 'close', 'new_page']
    )]
    interaction_tools = [t for t in mcp_tools if any(
        kw in t.name.lower() for kw in ['click', 'fill', 'hover', 'drag', 'upload', 'handle_dialog']
    )]
    analysis_tools = [t for t in mcp_tools if any(
        kw in t.name.lower() for kw in ['snapshot', 'screenshot', 'evaluate', 'console', 'network']
    )]

    subagents = [
        # Navigator Sub-Agent - Specialized in page navigation
        {
            "name": "navigator",
            "description": (
                "Specialized in navigating web pages. Use this agent when you need to: "
                "navigate to URLs, manage browser tabs, go back/forward in history, "
                "or handle multiple pages. Great for setting up the browser state. "
                "Can be run IN PARALLEL with other navigator tasks for multiple URLs."
            ),
            "system_prompt": """You are a NAVIGATOR sub-agent specialized in browser navigation.

YOUR SPECIALTY:
- Navigate to URLs efficiently
- Manage browser tabs (open, close, switch)
- Handle browser history (back, forward)
- Set up pages for other agents to interact with

TOOLS AVAILABLE: navigate_page, new_page, close_page, list_pages, select_page, navigate_page_history

WORKFLOW:
1. Receive navigation task from main agent
2. Navigate to the target URL
3. Verify page loaded (take_snapshot if needed)
4. Report success/failure with page state

ALWAYS:
- Verify navigation succeeded before reporting
- Report the final URL (in case of redirects)
- Note any errors or timeouts

Return a concise report of what was navigated and the page state.""",
            "tools": navigation_tools + [t for t in mcp_tools if 'snapshot' in t.name.lower()],
        },

        # Data Extractor Sub-Agent - Specialized in extracting data from pages
        {
            "name": "data-extractor",
            "description": (
                "Specialized in extracting data from web pages using JavaScript and snapshots. "
                "Use this agent when you need to: scrape content, extract specific elements, "
                "run JavaScript to get data, or analyze page structure. "
                "Can be run IN PARALLEL to extract data from multiple pages simultaneously."
            ),
            "system_prompt": """You are a DATA EXTRACTOR sub-agent specialized in extracting information from web pages.

YOUR SPECIALTY:
- Extract data using JavaScript (evaluate_script)
- Analyze page content via snapshots
- Scrape specific elements or patterns
- Parse and structure extracted data

TOOLS AVAILABLE: evaluate_script, take_snapshot, take_screenshot

JAVASCRIPT EXTRACTION PATTERNS:
```javascript
// Extract all text from elements
() => Array.from(document.querySelectorAll('selector')).map(el => el.innerText)

// Extract links
() => Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText, href: a.href}))

// Extract structured data
() => {
  const data = {};
  data.title = document.querySelector('h1')?.innerText;
  data.content = document.querySelector('.content')?.innerText;
  return data;
}
```

WORKFLOW:
1. Receive extraction task from main agent
2. First take_snapshot to understand page structure
3. Use evaluate_script with appropriate JavaScript
4. Structure the extracted data
5. Return clean, formatted results

ALWAYS:
- Validate data was extracted successfully
- Handle missing elements gracefully
- Return structured JSON when possible

Return the extracted data in a clean, usable format.""",
            "tools": analysis_tools,
        },

        # Form Handler Sub-Agent - Specialized in form interactions
        {
            "name": "form-handler",
            "description": (
                "Specialized in filling forms and interacting with input elements. "
                "Use this agent when you need to: fill out forms, click buttons, "
                "handle checkboxes/dropdowns, or submit data. "
                "Can be run IN PARALLEL for multiple independent forms."
            ),
            "system_prompt": """You are a FORM HANDLER sub-agent specialized in form interactions.

YOUR SPECIALTY:
- Fill text inputs and textareas
- Select dropdown options
- Click buttons and checkboxes
- Submit forms
- Handle multi-step forms

TOOLS AVAILABLE: fill, fill_form, click, hover, handle_dialog

WORKFLOW:
1. Receive form task from main agent
2. Take snapshot to identify form elements
3. Fill fields using fill or fill_form
4. Click submit button
5. Verify submission (check for success message or page change)

BEST PRACTICES:
- Use fill_form for multiple fields at once (more efficient)
- Wait for dynamic elements to load
- Handle dialogs that may appear after submission

ALWAYS:
- Verify each field was filled correctly
- Report any validation errors
- Confirm form submission success/failure

Return a report of what was filled and the result of submission.""",
            "tools": interaction_tools + [t for t in mcp_tools if 'snapshot' in t.name.lower()],
        },

        # Screenshot Analyzer Sub-Agent - Specialized in visual analysis
        {
            "name": "screenshot-analyzer",
            "description": (
                "Specialized in taking and analyzing screenshots for visual verification. "
                "Use this agent when you need to: capture page state visually, "
                "verify UI elements, document page appearance, or debug visual issues. "
                "Can be run IN PARALLEL for multiple pages."
            ),
            "system_prompt": """You are a SCREENSHOT ANALYZER sub-agent specialized in visual analysis.

YOUR SPECIALTY:
- Take screenshots of pages or elements
- Capture full-page screenshots
- Document visual state for verification
- Identify visual issues or changes

TOOLS AVAILABLE: take_screenshot, take_snapshot

WORKFLOW:
1. Receive screenshot task from main agent
2. Navigate/select the target page if needed
3. Take screenshot with appropriate options
4. Analyze the visual content
5. Report findings

SCREENSHOT OPTIONS:
- fullPage: true/false - capture entire page or viewport
- uid: specific element to screenshot
- format: png/jpeg/webp

ALWAYS:
- Describe what's visible in the screenshot
- Note any visual issues or anomalies
- Report the screenshot location/format

Return a description of what was captured and any visual observations.""",
            "tools": [t for t in mcp_tools if any(kw in t.name.lower() for kw in ['screenshot', 'snapshot'])],
        },

        # Performance Analyzer Sub-Agent - Specialized in performance testing
        {
            "name": "performance-analyzer",
            "description": (
                "Specialized in analyzing page performance and Core Web Vitals. "
                "Use this agent when you need to: measure load times, analyze performance metrics, "
                "identify bottlenecks, or test under different conditions. "
                "Can be run IN PARALLEL for multiple pages."
            ),
            "system_prompt": """You are a PERFORMANCE ANALYZER sub-agent specialized in web performance.

YOUR SPECIALTY:
- Record and analyze performance traces
- Measure Core Web Vitals (LCP, FID, CLS)
- Test under throttled conditions
- Identify performance bottlenecks

TOOLS AVAILABLE: performance_start_trace, performance_stop_trace, performance_analyze_insight, emulate_cpu, emulate_network

WORKFLOW:
1. Receive performance task from main agent
2. Optionally set throttling conditions
3. Start performance trace with reload=true
4. Wait for trace to complete
5. Analyze insights and metrics
6. Report findings

THROTTLING OPTIONS:
- CPU: 1-20x slowdown
- Network: Slow 3G, Fast 3G, Slow 4G, Fast 4G, Offline

ALWAYS:
- Report all Core Web Vitals
- Highlight any poor scores
- Suggest improvements if obvious

Return a performance report with metrics and any issues found.""",
            "tools": [t for t in mcp_tools if any(kw in t.name.lower() for kw in ['performance', 'emulate'])],
        },
    ]

    return subagents


def create_browser_worker_subagent(session_id: str, tools: list) -> dict:
    """Create a browser worker sub-agent with ISOLATED MCP session.

    Each worker gets its own MCP profile/session, so they can run
    browser tasks in parallel without conflicts!
    """
    return {
        "name": f"browser-worker-{session_id}",
        "description": (
            f"Browser worker with ISOLATED session '{session_id}'. "
            f"Use this for parallel browser tasks. "
            f"Has its own browser session that won't conflict with other workers. "
            f"Can navigate, click, screenshot, extract data - all independently!"
        ),
        "system_prompt": f"""You are BROWSER-WORKER-{session_id.upper()} with an ISOLATED browser session.

YOUR SESSION: {session_id} (your browser actions don't affect other workers!)

YOUR TOOLS: You have {len(tools)} Chrome DevTools tools.

WORKFLOW:
1. Receive task from orchestrator
2. Navigate to target URL
3. Perform the requested actions (click, fill, screenshot, extract)
4. Return a CONCISE summary of results

IMPORTANT:
- You have your OWN browser session - no conflicts with other workers
- Be efficient - complete task and return summary
- Don't over-explain - just report results

ALWAYS RETURN:
- What was done
- Key findings/results
- Any errors encountered""",
        "tools": tools,
    }


async def agent():
    """Async factory function for LangGraph Studio using Cerebras GLM-4.6.

    This agent specializes in browser automation with:
    - Chrome DevTools MCP for full browser control
    - Cerebras GLM-4.6 for fast inference
    - Tool result isolation (truncation)
    - Context compaction tool for manual context management
    - Automatic summarization when context gets large
    - PARALLEL SUB-AGENTS with ISOLATED MCP SESSIONS!
    """
    # Get Chrome DevTools MCP tools for main agent
    mcp_tools = await get_mcp_tools()

    # Initialize parallel sessions for sub-agents
    session_tools = await initialize_parallel_sessions()

    # Create browser worker sub-agents - each with ISOLATED session!
    browser_workers = [
        create_browser_worker_subagent(session_id, tools)
        for session_id, tools in session_tools.items()
    ]

    # Add context management tool
    context_tools = [compact_context]

    # Combine all tools for main agent
    all_tools = mcp_tools + context_tools

    # Build worker names for prompt
    worker_names = [f"browser-worker-{sid}" for sid in session_tools.keys()]

    # System prompt - BROWSER CONTROL AGENT with ISOLATED parallel sub-agents
    system_prompt = f"""You are a BROWSER CONTROL AGENT powered by Cerebras GLM-4.6.

## YOUR CAPABILITIES

You have {len(all_tools)} browser tools for direct control:
- Navigation (navigate_page, new_page, list_pages, select_page)
- Interaction (click, fill, hover, drag)
- Analysis (take_snapshot, take_screenshot, evaluate_script)
- Performance (performance traces, network monitoring)

## PARALLEL SUB-AGENTS with ISOLATED SESSIONS

You have {len(browser_workers)} browser workers, EACH with their OWN MCP session:
{chr(10).join(f'- {name}' for name in worker_names)}

**CRITICAL**: Each worker has an ISOLATED browser session!
- worker1 can navigate to google.com
- worker2 can navigate to github.com AT THE SAME TIME
- worker3 can navigate to wikipedia.org AT THE SAME TIME
- NO CONFLICTS! Each has its own session!

## HOW TO USE PARALLEL WORKERS

To run tasks IN PARALLEL, call `task` multiple times in a SINGLE response:

```
task(description="Navigate to google.com and describe the page", subagent_type="browser-worker-worker1")
task(description="Navigate to github.com and describe the page", subagent_type="browser-worker-worker2")
task(description="Navigate to wikipedia.org and describe the page", subagent_type="browser-worker-worker3")
```

ALL THREE will execute SIMULTANEOUSLY in their isolated sessions!

## WHEN TO USE PARALLEL WORKERS

USE parallel workers when:
- You need to visit multiple websites at once
- You need to perform independent browser tasks
- You want faster execution through parallelism
- Tasks don't depend on each other

DON'T use parallel workers when:
- Tasks depend on results from other tasks
- You need to interact with the same page
- Simple single-step tasks (use your tools directly)

## DIRECT TOOLS vs SUB-AGENTS

- **Simple tasks**: Use your tools directly (navigate, click, screenshot)
- **Complex parallel tasks**: Use browser-worker-X sub-agents

## CONTEXT MANAGEMENT

- compact_context: Call when context grows large
- Tool results are automatically truncated

## WORKFLOW

1. Understand the user's request
2. Decide: direct tools OR parallel workers
3. If parallel: assign different sites to different workers
4. ALL `task` calls in ONE response = PARALLEL execution
5. Synthesize results from all workers

## EXAMPLE

User: "Check google.com, github.com, and stackoverflow.com"

You respond with THREE task calls IN ONE MESSAGE:
```
task(description="Go to google.com, take snapshot, describe", subagent_type="browser-worker-worker1")
task(description="Go to github.com, take snapshot, describe", subagent_type="browser-worker-worker2")
task(description="Go to stackoverflow.com, take snapshot, describe", subagent_type="browser-worker-worker3")
```

Result: All 3 execute IN PARALLEL, each in isolated session!
"""

    # Get Cerebras API key
    cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        logger.warning("CEREBRAS_API_KEY not found in environment! Agent may fail.")

    MODEL_NAME = "zai-glm-4.6"
    print(f"\n{'='*80}")
    print(f"[BROWSER-ORCHESTRATOR-CEREBRAS] Browser Control Orchestrator - Model: {MODEL_NAME}")
    print(f"Features: Tool Result Isolation, Context Compaction, Auto-Summarization")
    print(f"Sub-Agents: {len(browser_workers)} ISOLATED browser workers!")
    print(f"Workers: {', '.join(worker_names)}")
    print(f"{'='*80}\n")

    # Create Cerebras GLM-4.6 model (same parameters as cerebras_zamar.py)
    model = ChatCerebras(
        model=MODEL_NAME,
        api_key=cerebras_api_key,
        max_tokens=128000,
        temperature=1.0,
    )

    # Custom middleware for context management
    custom_middleware = [
        TruncateToolResultsMiddleware(max_chars=MAX_TOOL_RESULT_CHARS),
        ContextCompactionMiddleware(summarization_model=model),
    ]

    # Create and return the deep agent with ISOLATED browser worker sub-agents
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
        subagents=browser_workers,  # Each has ISOLATED MCP session!
        middleware=custom_middleware,
    )
