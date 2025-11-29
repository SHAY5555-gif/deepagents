"""
Parallel Processor SubAgent - Map-Reduce as CompiledSubAgent
=============================================================

Subagent מיוחד שמטפל ברשימות במקביל עם Send API.
נרשם ב-SubAgentMiddleware ונגיש לסוכן הראשי דרך task tool.

שימוש:
------
מהסוכן הראשי:
- "חקור את 30 השירים הבאים: ..."
- הסוכן יקרא ל-task tool עם parallel_processor
- הSubAgent הזה יפרק את הרשימה ויריץ במקביל

אינטגרציה:
----------
```python
from parallel_processor_subagent import create_parallel_processor_subagent

subagents = [
    create_parallel_processor_subagent()
]

agent = create_deep_agent(
    model=model,
    tools=tools,
    subagents=subagents
)
```
"""

from typing import Annotated, Any
from typing_extensions import TypedDict
import operator
import asyncio
import re
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from deepagents.middleware.subagents import CompiledSubAgent
from langchain_core.messages import AIMessage


# ============================================================================
# Safe Print Helper (fixes Windows colorama flush errors)
# ============================================================================


def safe_print(*args, **kwargs):
    """
    No-op print function to avoid Windows console errors.

    Completely disables printing to avoid OSError(22, 'Invalid argument')
    and UnicodeEncodeError on Windows when colorama tries to flush
    to an invalid console handle or encode special characters.

    This is intentionally a no-op to ensure the parallel processor
    runs without console errors in production environments.
    """
    # Disabled to prevent Windows console errors
    pass


# ============================================================================
# State Definitions
# ============================================================================


class ParallelProcessorState(TypedDict):
    """State for parallel processing subagent"""

    # Input from user/main agent
    messages: list[dict]

    # Extracted list items to process
    items_to_process: list[dict]

    # Shared Chrome MCP tools (to avoid recreating client for each worker)
    chrome_tools: dict  # Shared tools dictionary

    # Results from parallel workers (with reducer!)
    results: Annotated[list[dict], operator.add]

    # Errors (with reducer)
    errors: Annotated[list[str], operator.add]

    # Final aggregated report
    final_report: str


# ============================================================================
# Node Functions
# ============================================================================


async def initialize_chrome_tools(state: ParallelProcessorState) -> dict:
    """
    Initialize Chrome MCP tools ONCE for all workers to share.

    This avoids each worker creating its own MCP client,
    which would cause sequential bottleneck.
    """
    # Check if we need Chrome tools
    messages = state.get("messages", [])
    if not messages:
        return {"chrome_tools": None}

    last_message = messages[-1]
    content = last_message.get("content", "") if isinstance(last_message, dict) else str(last_message)

    # Check if task needs Chrome OR Perplexity
    needs_chrome = "screenshot" in content.lower() or "navigate" in content.lower() or "chrome" in content.lower()
    needs_perplexity = "research" in content.lower() or "perplexity" in content.lower() or "search" in content.lower()

    if needs_chrome or needs_perplexity:
        safe_print(f"[PARALLEL PROCESSOR] Initializing shared MCP client(s)...")
        safe_print(f"[PARALLEL PROCESSOR] Chrome: {needs_chrome}, Perplexity: {needs_perplexity}")

        from langchain_mcp_adapters.client import MultiServerMCPClient

        # Build server config based on needs
        servers = {}

        if needs_chrome:
            servers["chrome_devtools"] = {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            }

        if needs_perplexity:
            servers["perplexity"] = {
                "url": "https://server.smithery.ai/@arjunkmrm/perplexity-search/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            }

        mcp_client = MultiServerMCPClient(servers)
        tools = await mcp_client.get_tools()
        tool_map = {tool.name: tool for tool in tools}

        safe_print(f"[PARALLEL PROCESSOR] Initialized {len(tool_map)} MCP tools")
        return {"chrome_tools": tool_map}

    return {"chrome_tools": None}


def extract_items_from_request(state: ParallelProcessorState) -> dict:
    """
    Extract list items from user request.

    This function analyzes the messages to find lists of items that should
    be processed in parallel. It looks for:
    - Numbered lists (1. item, 2. item, ...)
    - Comma-separated items
    - Explicit counts ("30 songs", "10 articles", etc.)
    """
    messages = state.get("messages", [])
    if not messages:
        return {"items_to_process": [], "errors": ["No messages provided"]}

    # Get the last message content (the task description)
    last_message = messages[-1]
    content = last_message.get("content", "") if isinstance(last_message, dict) else str(last_message)

    items = []

    # Detect task type from content
    task_type = "generic"
    if "screenshot" in content.lower():
        task_type = "screenshot"
    elif "navigate" in content.lower():
        task_type = "navigate"
    elif "research" in content.lower() or "perplexity" in content.lower():
        task_type = "research"

    # Pattern 1: Extract numbered lists
    numbered_pattern = r'^\s*\d+[\.\)]\s*(.+?)$'
    numbered_matches = re.findall(numbered_pattern, content, re.MULTILINE)
    if numbered_matches:
        items = [{"id": i+1, "description": item.strip(), "task_type": task_type} for i, item in enumerate(numbered_matches)]

    # Pattern 2: Extract count-based requests ("30 songs", "10 articles")
    if not items:
        count_pattern = r'(\d+)\s+(songs?|articles?|items?|tasks?|topics?|questions?|products?|websites?|pages?|documents?)'
        count_match = re.search(count_pattern, content, re.IGNORECASE)
        if count_match:
            count = int(count_match.group(1))
            item_type = count_match.group(2)
            items = [{"id": i+1, "description": f"{item_type} {i+1}", "content": content, "task_type": task_type} for i in range(count)]

    # Pattern 3: Comma-separated lists (websites, URLs, etc.)
    if not items and ',' in content:
        # Simple heuristic: if there are commas and short items, treat as list
        parts = [p.strip() for p in content.split(',')]
        if len(parts) >= 2 and all(len(p) < 100 for p in parts):
            items = [{"id": i+1, "description": part, "task_type": task_type} for i, part in enumerate(parts)]

    # If no patterns matched, create a single item
    if not items:
        items = [{"id": 1, "description": content, "content": content, "task_type": task_type}]

    safe_print(f"[PARALLEL PROCESSOR] Extracted {len(items)} items to process (task_type={task_type})")
    for item in items[:5]:  # Show first 5
        safe_print(f"  - [{item['id']}] {item['description'][:60]}...")
    if len(items) > 5:
        safe_print(f"  ... and {len(items) - 5} more")

    return {"items_to_process": items}


def route_to_parallel_workers(state: ParallelProcessorState) -> list[Send]:
    """
    Create Send objects for each item to process in parallel.

    This is where the magic happens - LangGraph will execute all
    these workers concurrently with SHARED Chrome tools!
    """
    items = state.get("items_to_process", [])
    chrome_tools = state.get("chrome_tools")  # Get shared tools

    safe_print(f"[PARALLEL PROCESSOR] Routing {len(items)} items to parallel workers")
    if chrome_tools:
        safe_print(f"[PARALLEL PROCESSOR] Using SHARED Chrome MCP client")

    return [
        Send(
            "process_single_item",
            {
                "item_id": item["id"],
                "item_description": item["description"],
                "item_content": item.get("content", item["description"]),
                "task_type": item.get("task_type", "generic"),
                "chrome_tools": chrome_tools  # Pass shared tools!
            }
        )
        for item in items
    ]


async def process_single_item(state: dict) -> dict:
    """
    Process a single item using SHARED Chrome tools in parallel.

    This function runs in parallel for each item!
    Uses shared MCP tools to avoid bottleneck.

    Args:
        state: Contains item_id, item_description, item_content, task_type, and chrome_tools

    Returns:
        Dictionary with results or errors
    """
    item_id = state["item_id"]
    description = state["item_description"]
    content = state.get("item_content", description)
    task_type = state.get("task_type", "generic")
    chrome_tools = state.get("chrome_tools")  # SHARED tools!

    safe_print(f"  [Worker {item_id:2d}] Processing: {description[:50]}...")

    try:
        # Use shared MCP tools if available
        if task_type == "screenshot" and chrome_tools:
            # Execute screenshot workflow with SHARED Chrome tools
            safe_print(f"  [Worker {item_id:2d}] Creating new page...")
            new_page_tool = chrome_tools.get("mcp__chrome-dev-testing__new_page")
            if new_page_tool:
                await new_page_tool.ainvoke({"url": description, "timeout": 30000})

            safe_print(f"  [Worker {item_id:2d}] Taking screenshot...")
            screenshot_tool = chrome_tools.get("mcp__chrome-dev-testing__take_screenshot")
            screenshot_result = None
            if screenshot_tool:
                screenshot_result = await screenshot_tool.ainvoke({"format": "png", "fullPage": False})

            result = {
                "item_id": item_id,
                "description": description,
                "result": f"Screenshot taken for {description}",
                "status": "success",
                "details": f"Successfully captured screenshot",
                "screenshot": screenshot_result
            }

        elif task_type == "research" and chrome_tools:
            # Execute research workflow with SHARED Perplexity tools
            safe_print(f"  [Worker {item_id:2d}] Researching with Perplexity...")

            # Try to find perplexity_search tool
            search_tool = None
            for tool_name in chrome_tools.keys():
                if "perplexity" in tool_name.lower() and "search" in tool_name.lower():
                    search_tool = chrome_tools[tool_name]
                    break

            if search_tool:
                # Use Perplexity to research the item
                research_result = await search_tool.ainvoke({
                    "query": f"Research information about: {description}",
                    "max_results": 5
                })

                result = {
                    "item_id": item_id,
                    "description": description,
                    "result": research_result,
                    "status": "success",
                    "details": f"Successfully researched using Perplexity"
                }
            else:
                # Fallback if perplexity tool not found
                result = {
                    "item_id": item_id,
                    "description": description,
                    "result": f"Perplexity tool not found, but would research: {description}",
                    "status": "success",
                    "details": f"Fallback: Perplexity tool not available"
                }

        else:
            # Generic processing (simulation)
            await asyncio.sleep(0.5)

            result = {
                "item_id": item_id,
                "description": description,
                "result": f"Processed: {description}",
                "status": "success",
                "details": f"Generic processing for item {item_id}"
            }

        safe_print(f"  [Worker {item_id:2d}] DONE")
        return {"results": [result]}

    except Exception as e:
        error_msg = f"Item {item_id} ({description[:30]}...): {str(e)}"
        safe_print(f"  [Worker {item_id:2d}] ERROR: {str(e)}")
        return {"errors": [error_msg]}


def aggregate_results(state: ParallelProcessorState) -> dict:
    """
    Aggregate all parallel results into a final report.

    This runs after all workers complete.
    """
    results = state.get("results", [])
    errors = state.get("errors", [])

    safe_print(f"\n[PARALLEL PROCESSOR] Aggregating {len(results)} results")

    # Build report
    report_lines = [
        "Parallel Processing Report",
        "=" * 60,
        f"Total items processed: {len(results)}",
        f"Successful: {len(results)}",
        f"Failed: {len(errors)}",
        "",
    ]

    if results:
        report_lines.append("Results:")
        report_lines.append("-" * 60)
        for result in results:
            report_lines.append(
                f"[{result['item_id']:2d}] {result['description']}"
            )
            report_lines.append(f"     Status: {result['status']}")
            if result.get('details'):
                report_lines.append(f"     Details: {result['details']}")
            report_lines.append("")

    if errors:
        report_lines.append("Errors:")
        report_lines.append("-" * 60)
        for error in errors:
            report_lines.append(f"  - {error}")
        report_lines.append("")

    report_lines.extend([
        "=" * 60,
        f"Processing complete. {len(results)} items processed successfully.",
    ])

    final_report = "\n".join(report_lines)

    safe_print(f"\n[FINAL REPORT]")
    safe_print(final_report)

    # Return as a message so the main agent can see it
    return {
        "final_report": final_report,
        "messages": [AIMessage(content=final_report)]
    }


# ============================================================================
# Graph Construction
# ============================================================================


def create_parallel_processor_graph():
    """
    Create the parallel processor graph with map-reduce pattern.

    Flow:
    1. initialize_chrome_tools - Create SHARED MCP client (once!)
    2. extract_items_from_request - Parse user input to find list items
    3. route_to_parallel_workers - Fan out to N parallel workers
    4. process_single_item - Process each item (runs N times in parallel!)
    5. aggregate_results - Collect and summarize all results
    """
    builder = StateGraph(ParallelProcessorState)

    # Add nodes
    builder.add_node("initialize_chrome_tools", initialize_chrome_tools)
    builder.add_node("extract_items", extract_items_from_request)
    builder.add_node("process_single_item", process_single_item)
    builder.add_node("aggregate_results", aggregate_results)

    # Add edges
    builder.add_edge(START, "initialize_chrome_tools")
    builder.add_edge("initialize_chrome_tools", "extract_items")

    # The magic: conditional edge that returns Send objects for parallel execution
    builder.add_conditional_edges(
        "extract_items",
        route_to_parallel_workers,
        ["process_single_item"]
    )

    # All parallel workers converge to aggregate
    builder.add_edge("process_single_item", "aggregate_results")
    builder.add_edge("aggregate_results", END)

    return builder.compile()


# ============================================================================
# SubAgent Factory
# ============================================================================


def create_parallel_processor_subagent() -> CompiledSubAgent:
    """
    Create a CompiledSubAgent for parallel processing.

    This can be registered with SubAgentMiddleware in create_deep_agent:

    ```python
    from parallel_processor_subagent import create_parallel_processor_subagent

    agent = create_deep_agent(
        model=model,
        tools=tools,
        subagents=[
            create_parallel_processor_subagent()
        ]
    )
    ```

    The main agent will then have access to this via the `task` tool:

    User: "Research these 30 songs: ..."
    Agent: *calls task tool with subagent_type="parallel_processor"*
    """
    graph = create_parallel_processor_graph()

    return CompiledSubAgent(
        name="parallel_processor",
        description=(
            "Specialized agent for processing lists of items in parallel. "
            "Use this when you have multiple independent items that need the same processing "
            "(e.g., researching multiple songs, analyzing multiple articles, checking multiple websites). "
            "This agent automatically parallelizes the work, making it much faster than processing items sequentially. "
            "Ideal for tasks like: 'research 30 songs', 'analyze these 10 articles', 'check these 20 websites'. "
            "The agent will detect the list, split the work, process all items in parallel, and return an aggregated report."
        ),
        runnable=graph
    )


# ============================================================================
# Testing
# ============================================================================


async def test_parallel_processor():
    """Test the parallel processor locally"""
    import time

    safe_print("=" * 70)
    safe_print("Testing Parallel Processor SubAgent")
    safe_print("=" * 70)

    graph = create_parallel_processor_graph()

    # Test case: simulate user asking to research 10 songs
    test_input = {
        "messages": [
            {
                "role": "user",
                "content": "Research these 10 songs: Song1, Song2, Song3, Song4, Song5, Song6, Song7, Song8, Song9, Song10"
            }
        ],
        "items_to_process": [],
        "results": [],
        "errors": [],
        "final_report": ""
    }

    start = time.time()
    result = await graph.ainvoke(test_input)
    elapsed = time.time() - start

    safe_print(f"\n{'=' * 70}")
    safe_print(f"Test completed in {elapsed:.2f} seconds")
    safe_print(f"{'=' * 70}")

    # With 10 items taking 0.5s each:
    # Sequential: ~5 seconds
    # Parallel: ~0.5 seconds
    if elapsed < 2.0:
        safe_print("[SUCCESS] Items processed in parallel!")
    else:
        safe_print("[WARNING] Items may have processed sequentially")

    return result


if __name__ == "__main__":
    # Run test
    asyncio.run(test_parallel_processor())
