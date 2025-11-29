"""
Test Chrome DevTools MCP connection - Detailed error inspection
"""
import asyncio
import json
from langchain_mcp_adapters.client import MultiServerMCPClient


async def test_chrome_mcp_detailed():
    """Test Chrome DevTools MCP connection and inspect actual errors"""

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

    print(f"\nLoaded {len(tools)} tools")

    # Try to call list_pages tool and inspect the raw error
    print("\n\nTrying to call list_pages tool...")
    list_pages_tool = next((t for t in tools if t.name == "list_pages"), None)

    if list_pages_tool:
        try:
            # Try calling the tool through the MCP client directly
            print("Calling tool via MCP client...")

            # Access the underlying MCP client
            client_session = list(mcp_client._clients.values())[0]

            # Call the tool directly
            from mcp.types import CallToolRequest
            result = await client_session.call_tool("list_pages", {})

            print(f"Raw result: {result}")
            print(f"Result type: {type(result)}")
            print(f"Result dict: {result.model_dump() if hasattr(result, 'model_dump') else result}")

        except Exception as e:
            print(f"\nException caught!")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception message: {str(e)}")
            print(f"Exception args: {e.args}")

            # Try to get more details
            if hasattr(e, '__dict__'):
                print(f"Exception attributes: {e.__dict__}")

            import traceback
            print("\nFull traceback:")
            traceback.print_exc()
    else:
        print("list_pages tool not found!")


if __name__ == "__main__":
    asyncio.run(test_chrome_mcp_detailed())
