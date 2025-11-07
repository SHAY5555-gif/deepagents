"""
Deep Agent with MCP Tools Example
Demonstrates how to integrate MCP tools into a Deep Agent using MultiServerMCPClient
Now includes REAL Chrome DevTools MCP integration!
"""
import asyncio
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from deepagents import create_deep_agent

# Simulated MCP-style tools for demo purposes
@tool
def get_cryptocurrency_price(symbol: str) -> str:
    """Get the current price of a cryptocurrency.

    Args:
        symbol: The cryptocurrency symbol (e.g., BTC, ETH, ADA)
    """
    # Simulated MCP response
    prices = {
        "BTC": "$45,000",
        "ETH": "$2,500",
        "ADA": "$0.50"
    }
    return f"[MCP Tool: CoinCap] {symbol} price: {prices.get(symbol.upper(), 'Unknown')}"

@tool
def search_web(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query
    """
    # Simulated MCP response
    return f"[MCP Tool: WebSearch] Found results for: {query}"

@tool
def get_weather(location: str) -> str:
    """Get weather information for a location.

    Args:
        location: The city or location name
    """
    # Simulated MCP response
    return f"[MCP Tool: Weather] Weather in {location}: Sunny, 72°F"


async def get_chrome_mcp_tools():
    """Get Chrome DevTools MCP tools from Smithery"""
    # Using Chrome DevTools MCP server from Smithery
    # This is a REMOTE HTTP MCP server (not stdio)
    mcp_client = MultiServerMCPClient({
        "chrome_devtools": {
            "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
            "transport": "streamable_http"
        }
    })

    # Get tools (no need for context manager in 0.1.0+)
    tools = await mcp_client.get_tools()
    return tools, mcp_client


def agent():
    """Factory function to create the deep agent for LangGraph Studio.

    NOTE: This is the synchronous version that LangGraph Studio calls.
    It uses simulated tools only because LangGraph Studio doesn't support async factory.
    """
    # Use simulated tools only for LangGraph Studio
    mcp_tools = [
        get_cryptocurrency_price,
        search_web,
        get_weather,
    ]

    # System prompt for the agent
    system_prompt = """You are a helpful research and information assistant with access to MCP tools.

You have access to the following MCP tools:

SIMULATED TOOLS (for demo):
- get_cryptocurrency_price: Get cryptocurrency prices from CoinCap
- search_web: Search the web for information
- get_weather: Get weather information for any location

When answering questions, use these tools to gather accurate information."""

    # Create deep agent with MCP tools
    return create_deep_agent(
        tools=mcp_tools,
        system_prompt=system_prompt,
    )


async def agent_with_chrome_mcp():
    """Async factory function to create the deep agent with REAL Chrome DevTools MCP.

    This is used when running the script directly (python mcp_agent_example.py)
    and provides access to the real Chrome DevTools MCP server from Smithery.
    """
    print("[1/3] Connecting to Chrome DevTools MCP server (Smithery)...")
    chrome_tools, mcp_client = await get_chrome_mcp_tools()
    print(f"  [OK] Connected! Got {len(chrome_tools)} Chrome DevTools tools")
    print()

    # Combine simulated tools with REAL Chrome DevTools MCP tools
    all_tools = [
        get_cryptocurrency_price,
        search_web,
        get_weather,
    ] + chrome_tools

    print(f"[2/3] Creating Deep Agent with {len(all_tools)} MCP tools...")
    print(f"  - 3 simulated demo tools")
    print(f"  - {len(chrome_tools)} real Chrome DevTools MCP tools from Smithery")
    print()

    # System prompt for the agent
    system_prompt = """You are a helpful research and information assistant with access to MCP tools.

You have access to the following MCP tools:

SIMULATED TOOLS (for demo):
- get_cryptocurrency_price: Get cryptocurrency prices from CoinCap
- search_web: Search the web for information
- get_weather: Get weather information for any location

REAL CHROME DEVTOOLS MCP TOOLS (connected via Smithery remote HTTP):
- Browser automation and control via Chrome DevTools Protocol
- Navigate to URLs and interact with web pages
- Take screenshots and capture page content
- Click elements, fill forms, and extract information
- Full browser automation capabilities via Chrome DevTools
- Network monitoring and performance analysis
- Console log inspection

When answering questions, use these tools to gather accurate information and interact with web pages.
The Chrome DevTools tools are REAL and connect via Smithery's remote HTTP MCP server!"""

    # Create deep agent with MCP tools
    agent = create_deep_agent(
        tools=all_tools,
        system_prompt=system_prompt,
    )

    return agent, mcp_client


async def main():
    print("=" * 80)
    print("DEEP AGENT WITH REAL CHROME DEVTOOLS MCP")
    print("=" * 80)
    print()

    # Create agent with real Chrome DevTools MCP
    deep_agent, mcp_client = await agent_with_chrome_mcp()

    try:
        print("[3/3] Running test query...")
        query = "What's the price of BTC and ETH? Also tell me the weather in San Francisco."
        print(f"\nQuery: {query}\n")
        print("-" * 80)
        print()

        # Stream the agent's response
        async for chunk in deep_agent.astream(
            {"messages": [{"role": "user", "content": query}]},
            stream_mode="values"
        ):
            if "messages" in chunk:
                chunk["messages"][-1].pretty_print()

        print()
        print("=" * 80)
        print("[SUCCESS] Deep Agent executed with REAL MCP tools!")
        print("=" * 80)

    finally:
        # Clean up MCP client connection (if needed)
        pass  # MultiServerMCPClient manages its own cleanup in 0.1.0+


if __name__ == "__main__":
    asyncio.run(main())
