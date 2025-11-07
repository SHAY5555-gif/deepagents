"""Test the updated agent to verify it now uses Chrome DevTools tools"""
import asyncio
from mcp_agent_async import agent


async def main():
    print("=" * 80)
    print("TESTING UPDATED AGENT WITH NEW SYSTEM PROMPT")
    print("=" * 80)
    print()

    # Create the agent
    print("[1/3] Creating agent with updated system prompt...")
    graph = await agent()
    print("   [OK] Agent created successfully")

    # Test query asking for browser navigation and screenshot
    test_query = "Navigate to google.com and take a screenshot"

    print(f"\n[2/3] Testing with query: '{test_query}'")
    print("   (This should now invoke navigate_page and take_screenshot tools)")
    print()

    # Invoke the agent
    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": test_query}]
    })

    print("\n[3/3] Agent response:")
    print("-" * 80)

    # Print all messages
    for msg in result.get("messages", []):
        if hasattr(msg, "content"):
            print(f"\n{msg.__class__.__name__}: {msg.content}")
        elif hasattr(msg, "name"):
            print(f"\nToolCall: {msg.name}")

    print("\n" + "=" * 80)

    # Check if tools were invoked
    tool_calls = [msg for msg in result.get("messages", []) if hasattr(msg, "name")]
    if tool_calls:
        print(f"[SUCCESS] Agent invoked {len(tool_calls)} tool(s):")
        for tc in tool_calls:
            print(f"   - {tc.name}")
    else:
        print("[FAILED] Agent did not invoke any tools")
        print("   The agent may still be refusing to use browser automation")

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
