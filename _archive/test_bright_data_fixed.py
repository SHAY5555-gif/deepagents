"""Test Bright Data MCP connection with SSE transport"""
import asyncio

async def test_mcp_client_sse():
    """Test MCP client connection with SSE transport"""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        print("="*60)
        print("Testing Bright Data MCP with SSE Transport")
        print("="*60)

        client = MultiServerMCPClient({
            "bright_data": {
                "url": "https://mcp.brightdata.com/sse?token=edebeabb58a1ada040be8c1f67fb707e797a1810bf874285698e03e8771861a5",
                "transport": "sse"
            }
        })

        print("\n1. Getting tools from Bright Data MCP...")
        tools = await client.get_tools()

        print(f"\n[SUCCESS] Retrieved {len(tools)} tools!")
        print(f"\nFirst 10 tools:")
        for i, tool in enumerate(tools[:10], 1):
            print(f"  {i}. {tool.name}: {tool.description[:80]}...")

        return True

    except Exception as e:
        print(f"\n[ERROR] MCP Client failed:")
        print(f"  Error type: {type(e).__name__}")
        print(f"  Error message: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False

async def main():
    success = await test_mcp_client_sse()

    print("\n" + "="*60)
    if success:
        print("[PASS] Bright Data MCP is working correctly!")
    else:
        print("[FAIL] Bright Data MCP connection failed")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
