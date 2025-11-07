"""
Test Chrome DevTools MCP connection
"""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def test_chrome_mcp():
    """Test Chrome DevTools MCP connection and tool calls"""

    print("Connecting to Chrome DevTools MCP...")

    # Connect to Chrome DevTools MCP
    mcp_client = MultiServerMCPClient({
        "chrome_devtools": {
            "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
            "transport": "streamable_http"
        }
    })

    print("Getting tools...")
    tools = await mcp_client.get_tools()

    print(f"\nLoaded {len(tools)} tools:")
    for tool in tools[:5]:  # Show first 5 tools
        print(f"  - {tool.name}: {tool.description[:80] if tool.description else 'No description'}")

    # Try to call list_pages tool
    print("\n\nTrying to call list_pages tool...")
    list_pages_tool = next((t for t in tools if t.name == "list_pages"), None)

    if list_pages_tool:
        try:
            result = await list_pages_tool.ainvoke({})
            print(f"Success! Result: {result}")
        except Exception as e:
            print(f"Failed! Error: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("list_pages tool not found!")


if __name__ == "__main__":
    asyncio.run(test_chrome_mcp())
