"""Test the agent's resilience with error handling wrapper"""
import asyncio
from mcp_agent_async import agent


async def main():
    print("=" * 80)
    print("TESTING AGENT RESILIENCE WITH ERROR HANDLING")
    print("=" * 80)
    print()
    print("This test verifies that the agent:")
    print("  1. Receives error messages instead of crashing")
    print("  2. Can retry after errors")
    print("  3. Continues working through multiple errors")
    print()

    # Create the agent
    print("[1/3] Creating agent with error handling wrapper...")
    graph = await agent()
    print("   ✓ Agent created successfully")

    # Test with a query that will likely encounter errors but should keep trying
    test_query = """Navigate to google.com and take a screenshot.

IMPORTANT: If you encounter ANY errors (timeout, no page, etc.):
- READ the error message carefully
- UNDERSTAND what went wrong
- FIX the problem (e.g., create a page if needed, increase timeout)
- RETRY the operation
- NEVER give up until you succeed!"""

    print(f"\n[2/3] Testing with query:")
    print(f"   '{test_query[:50]}...'")
    print()
    print("   Watching for resilient behavior (retries after errors)...")
    print()

    try:
        result = await graph.ainvoke({
            "messages": [{"role": "user", "content": test_query}]
        })

        print("\n[3/3] Results:")
        print("-" * 80)

        # Extract messages
        messages = result.get("messages", [])

        # Count errors and retries
        error_count = 0
        tool_calls = []
        retries = []

        for i, msg in enumerate(messages):
            msg_type = msg.__class__.__name__

            if msg_type == "AIMessage":
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc["name"]
                        tool_calls.append(tool_name)

                        # Check if this is a retry (same tool called again)
                        if tool_calls.count(tool_name) > 1:
                            retries.append(tool_name)

            elif msg_type == "ToolMessage":
                if hasattr(msg, "content") and "[ERROR]" in str(msg.content):
                    error_count += 1
                    print(f"\n   [ERROR DETECTED] {msg.content[:100]}...")

        print("\n" + "=" * 80)
        print("RESILIENCE ANALYSIS:")
        print("=" * 80)

        print(f"\n✓ Total tool calls: {len(tool_calls)}")
        print(f"✓ Errors encountered: {error_count}")
        print(f"✓ Retries detected: {len(retries)}")

        if error_count > 0 and len(tool_calls) > error_count:
            print("\n🎉 SUCCESS! Agent is RESILIENT:")
            print(f"   - Encountered {error_count} error(s)")
            print(f"   - Continued working ({len(tool_calls)} total tool calls)")
            print(f"   - Performed {len(retries)} retry/retries")
            print("\n   The error handling wrapper is working perfectly!")
        elif error_count > 0:
            print("\n⚠️  PARTIAL SUCCESS:")
            print(f"   - Encountered {error_count} error(s)")
            print(f"   - Made {len(tool_calls)} tool call(s)")
            print("   - Agent may need more explicit retry instructions")
        else:
            print("\n✓ NO ERRORS encountered (task completed smoothly)")

        print("=" * 80)

    except Exception as e:
        print(f"\n[FAILED] Agent crashed with exception: {e}")
        print("\nThis should NOT happen with the error handling wrapper!")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
