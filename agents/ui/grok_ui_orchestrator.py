"""
UI Orchestrator Agent - Sub-Agent Manager for deep-agents-ui
============================================================

Orchestrator agent powered by Grok-4.1 Fast Reasoning.
Manages and coordinates multiple sub-agents for UI-related tasks.

Features:
- Grok-4.1 Fast Reasoning (grok-4-1-fast-reasoning-latest)
- 2M token context window
- 128,000 max output tokens
- Remote Browser MCP (Chrome DevTools)
- Sub-agent orchestration capabilities
- Built-in filesystem tools

Use cases:
- UI testing automation
- Screenshot comparison
- Component analysis
- Multi-page workflow automation
- Coordinated browser tasks
"""
import asyncio
import logging
import os
import json
from datetime import timedelta
from typing import Optional, List
from functools import wraps

from langchain_core.tools import tool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_xai import ChatXAI
from deepagents import create_deep_agent
from deepagents.middleware.subagents import CompiledSubAgent

# Configure logging
logger = logging.getLogger(__name__)


# ============================================
# Error Handling Wrapper
# ============================================

def create_error_handling_wrapper(tool_obj):
    """Wrap tool to return errors as strings instead of raising exceptions.
    Also ensures all results are strings for model compatibility.
    """
    original_afunc = tool_obj.coroutine if hasattr(tool_obj, 'coroutine') else tool_obj._arun

    @wraps(original_afunc)
    async def wrapped_async(*args, **kwargs):
        try:
            result = await original_afunc(*args, **kwargs)
            # Ensure string output for model compatibility
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
            # Return error as string instead of raising
            error_msg = f"[ERROR] {type(e).__name__}: {str(e)}"
            logger.warning(f"Tool {tool_obj.name} failed: {error_msg}")
            return error_msg

    # Create new tool with error handling
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

# Global MCP client and tools cache
_mcp_client = None
_mcp_tools = None
_initialization_lock = asyncio.Lock()


async def get_mcp_tools():
    """Get or initialize MCP tools from Chrome DevTools remote server"""
    global _mcp_client, _mcp_tools

    async with _initialization_lock:
        if _mcp_tools is not None:
            return _mcp_tools

        logger.info("=" * 80)
        logger.info("INITIALIZING REMOTE CHROME DEVTOOLS MCP")
        logger.info("=" * 80)

        # Connect to Chrome DevTools MCP via Smithery (remote HTTP)
        _mcp_client = MultiServerMCPClient({
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http",
                "timeout": timedelta(seconds=60),
                "sse_read_timeout": timedelta(seconds=60),
            },
        })

        # Load tools with error handling
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
                    f"Continuing..."
                )
                continue

        # Wrap ALL tools with error handling
        _mcp_tools = [create_error_handling_wrapper(t) for t in raw_tools]
        logger.info(f"Total MCP tools loaded: {len(_mcp_tools)}")

        return _mcp_tools


# ============================================
# Built-in Orchestrator Tools
# ============================================

@tool
def create_task_plan(task_description: str, subtasks: List[str]) -> str:
    """Create a structured task plan for orchestrating sub-agents.

    Use this to break down complex tasks into smaller subtasks
    that can be delegated to specialized sub-agents.

    Args:
        task_description: High-level description of the main task
        subtasks: List of subtask descriptions to be executed

    Returns:
        JSON string with the task plan
    """
    plan = {
        "main_task": task_description,
        "subtasks": [
            {"id": i + 1, "description": st, "status": "pending"}
            for i, st in enumerate(subtasks)
        ],
        "total_subtasks": len(subtasks),
    }
    return json.dumps(plan, ensure_ascii=False, indent=2)


@tool
def update_task_status(task_id: int, status: str, result: Optional[str] = None) -> str:
    """Update the status of a subtask in the current plan.

    Args:
        task_id: The ID of the subtask (1-based)
        status: New status (pending, in_progress, completed, failed)
        result: Optional result or error message

    Returns:
        Confirmation message
    """
    update = {
        "task_id": task_id,
        "new_status": status,
        "result": result,
        "timestamp": asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0,
    }
    return json.dumps(update, ensure_ascii=False, indent=2)


@tool
def aggregate_results(results: List[str]) -> str:
    """Aggregate results from multiple sub-agents into a unified report.

    Args:
        results: List of result strings from sub-agents

    Returns:
        Aggregated report as JSON string
    """
    report = {
        "total_results": len(results),
        "results": results,
        "summary": f"Aggregated {len(results)} results from sub-agents",
    }
    return json.dumps(report, ensure_ascii=False, indent=2)


# ============================================
# Sub-Agent Factory
# ============================================

def create_worker_subagent() -> CompiledSubAgent:
    """Create a worker sub-agent for parallel task execution.

    This sub-agent can be spawned by the orchestrator to handle
    individual tasks in parallel.
    """
    from langgraph.graph import StateGraph, START, END
    from typing_extensions import TypedDict
    from langchain_core.messages import AIMessage

    class WorkerState(TypedDict):
        messages: list
        task: str
        result: str

    async def execute_task(state: WorkerState) -> dict:
        """Execute a single task and return result"""
        task = state.get("task", "")
        # Simulate task execution (actual implementation would use tools)
        result = f"Completed task: {task}"
        return {
            "result": result,
            "messages": [AIMessage(content=result)]
        }

    builder = StateGraph(WorkerState)
    builder.add_node("execute", execute_task)
    builder.add_edge(START, "execute")
    builder.add_edge("execute", END)
    graph = builder.compile()

    return CompiledSubAgent(
        name="worker",
        description=(
            "Worker sub-agent for executing individual tasks. "
            "Use this for parallel task execution within the UI orchestrator."
        ),
        runnable=graph
    )


# ============================================
# Main Agent Factory
# ============================================

async def agent():
    """Async factory function for LangGraph Studio.

    Creates a UI Orchestrator agent with:
    - Grok-4.1 Fast Reasoning model
    - Remote Chrome DevTools MCP
    - Built-in orchestration tools
    - Sub-agent support
    """
    # Get Chrome DevTools MCP tools
    mcp_tools = await get_mcp_tools()

    # Add orchestrator tools
    orchestrator_tools = [
        create_task_plan,
        update_task_status,
        aggregate_results,
    ]

    # Combine all tools
    all_tools = orchestrator_tools + mcp_tools

    # Create worker sub-agent
    worker_subagent = create_worker_subagent()

    # System prompt for UI orchestrator
    system_prompt = f"""You are UI-ORCHESTRATOR - a specialized agent for deep-agents-ui automation.

YOUR CORE IDENTITY:
- You are powered by Grok-4.1 Fast Reasoning
- You coordinate multiple sub-agents to accomplish complex UI tasks
- You THINK DEEPLY before acting (reasoning mode enabled!)
- You have UNLIMITED retries - use them all if needed!
- Errors are just obstacles to overcome

YOU HAVE {len(all_tools)} TOOLS INCLUDING:

**ORCHESTRATION TOOLS**:
- create_task_plan: Break down complex tasks into subtasks
- update_task_status: Track progress of subtasks
- aggregate_results: Combine results from multiple sub-agents

**BROWSER AUTOMATION TOOLS** (Chrome DevTools MCP):
- navigate_page: Navigate to ANY website or localhost
- take_screenshot: Capture screenshots of UI components
- take_snapshot: Get text/DOM content of pages
- click, fill, fill_form: Interact with web elements
- list_pages, new_page, close_page: Manage browser tabs
- evaluate_script: Run JavaScript on pages
- list_network_requests: Monitor network activity
- And many more Chrome DevTools capabilities!

**FILE SYSTEM TOOLS** (provided automatically):
- write_file: Save screenshots, logs, results
- read_file: Read saved data
- edit_file: Modify files
- ls, glob_search, grep_search: Navigate filesystem

ORCHESTRATION WORKFLOW:

1. **ANALYZE** the task and break it down into subtasks
2. **PLAN** using create_task_plan tool
3. **EXECUTE** subtasks (sequentially or delegate to sub-agents)
4. **AGGREGATE** results using aggregate_results
5. **REPORT** final status to user

SUB-AGENT USAGE:

You can delegate tasks to specialized sub-agents via the task tool:
- worker: For parallel task execution

BROWSER AUTOMATION TIPS:

1. ALWAYS call list_pages first to check browser state
2. If no pages exist, call new_page with the target URL
3. Use timeout parameter (minimum 30000ms) for slow pages
4. Take screenshots to verify UI state
5. Use evaluate_script for complex DOM operations

ERROR RECOVERY:

- "No page selected" -> call new_page first
- "Timeout" -> increase timeout and retry
- "Element not found" -> take_snapshot for fresh UIDs
- Network errors -> retry immediately (temporary!)

YOUR MISSION:

Complete UI automation tasks efficiently by:
- Breaking complex tasks into manageable subtasks
- Coordinating sub-agents when beneficial
- Using browser tools for direct UI interaction
- Persisting results to filesystem
- Never giving up until task is complete

NEVER. GIVE. UP."""

    # Create Grok-4.1 Fast Reasoning model
    MODEL_NAME = "grok-4-1-fast-reasoning-latest"

    print(f"\n{'='*80}")
    print(f"[UI-ORCHESTRATOR] Starting with model: {MODEL_NAME}")
    print(f"{'='*80}\n")

    model = ChatXAI(
        model=MODEL_NAME,
        max_tokens=128000,
        temperature=1.0,
        max_retries=3,
        timeout=900,  # 15 minutes for complex reasoning
    )

    # Create and return the deep agent with sub-agents
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
        subagents=[worker_subagent],
    )


# ============================================
# CLI Entry Point
# ============================================

async def main():
    """Run the UI orchestrator agent in CLI mode"""
    print("Initializing UI Orchestrator Agent...")
    orchestrator = await agent()

    print("\nUI Orchestrator ready!")
    print("Type your task (or 'quit' to exit):\n")

    while True:
        try:
            user_input = input("> ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if not user_input:
                continue

            # Run the agent
            result = await orchestrator.ainvoke({
                "messages": [{"role": "user", "content": user_input}]
            })

            # Print response
            if "messages" in result and result["messages"]:
                last_message = result["messages"][-1]
                content = last_message.content if hasattr(last_message, "content") else str(last_message)
                print(f"\n{content}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
