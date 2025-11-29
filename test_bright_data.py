"""Test Bright Data MCP connection"""
import asyncio
import httpx

async def test_http_connection():
    """Test direct HTTP connection to Bright Data MCP"""
    url = "https://mcp.brightdata.com/mcp?token=edebeabb58a1ada040be8c1f67fb707e797a1810bf874285698e03e8771861a5"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"Testing connection to: {url[:60]}...")
            resp = await client.get(url)
            print(f"[OK] Status: {resp.status_code}")
            print(f"Headers: {dict(resp.headers)}")
            print(f"Body preview (first 500 chars): {resp.text[:500]}")
            return True
    except Exception as e:
        print(f"[ERROR] HTTP Connection failed: {type(e).__name__}: {str(e)}")
        return False

async def test_mcp_client():
    """Test MCP client connection"""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        print("\n" + "="*60)
        print("Testing MCP Client Connection...")
        print("="*60)

        client = MultiServerMCPClient({
            "bright_data": {
                "url": "https://mcp.brightdata.com/mcp?token=edebeabb58a1ada040be8c1f67fb707e797a1810bf874285698e03e8771861a5",
                "transport": "streamable_http"
            }
        })

        print("Getting tools...")
        tools = await client.get_tools()
        print(f"[OK] Successfully retrieved {len(tools)} tools!")
        print(f"Tool names: {[t.name for t in tools[:10]]}")
        return True

    except Exception as e:
        print(f"[ERROR] MCP Client failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("="*60)
    print("BRIGHT DATA MCP CONNECTION TEST")
    print("="*60)

    # Test 1: Direct HTTP
    print("\nTest 1: Direct HTTP Connection")
    print("-"*60)
    http_ok = await test_http_connection()

    # Test 2: MCP Client
    print("\nTest 2: MCP Client Connection")
    print("-"*60)
    mcp_ok = await test_mcp_client()

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"HTTP Connection: {'[PASS]' if http_ok else '[FAIL]'}")
    print(f"MCP Client:      {'[PASS]' if mcp_ok else '[FAIL]'}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
