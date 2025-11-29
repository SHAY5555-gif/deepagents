"""
Simple Deep Agent WITHOUT MCP - For speed testing
Uses only built-in tools (file system)
"""
from langchain_xai import ChatXAI
from deepagents import create_deep_agent


async def agent():
    """Simple agent without MCP - just file system tools"""

    MODEL_NAME = "grok-4-1-fast-reasoning-latest"
    print(f"\n[basic_no_mcp] Creating agent with model: {MODEL_NAME}")
    print(f"No MCP tools - only built-in file system tools\n")

    model = ChatXAI(
        model=MODEL_NAME,
        max_tokens=128000,
        temperature=1.0,
        max_retries=3,
        timeout=300,
    )

    system_prompt = """You are a helpful AI assistant.
You have access to file system tools only (write_file, read_file, edit_file, ls, glob_search, grep_search).
No browser automation or web scraping tools.
Be helpful and complete tasks efficiently."""

    return create_deep_agent(
        model=model,
        tools=[],  # No extra tools - only built-in file system tools
        system_prompt=system_prompt,
    )
