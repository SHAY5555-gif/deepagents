"""Properly test the agent with environment variables loaded"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from mcp_agent_async import agent


async def main():
    # Load .env file
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    print("=" * 80)
    print("TESTING AGENT WITH SMITHERY CHROME DEVTOOLS MCP")
    print("=" * 80)
    print()

    # Verify environment variables
    print("[1/4] Checking environment variables...")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        print(f"   Anthropic API Key: {api_key[:20]}...")
    else:
        print("   ERROR: ANTHROPIC_API_KEY not found!")
        return

    # Create the agent
    print("\n[2/4] Creating agent with Smithery MCP tools...")
    graph = await agent()
    print("   Agent created successfully")

    # Test with browser automation query
    test_query = "Navigate to google.com and take a screenshot"

    print(f"\n[3/4] Sending query: '{test_query}'")
    print("   Expected: Agent should invoke navigate_page and take_screenshot")
    print()

    try:
        result = await graph.ainvoke({
            "messages": [{"role": "user", "content": test_query}]
        })

        print("\n[4/4] Results:")
        print("-" * 80)

        # Extract messages
        messages = result.get("messages", [])

        # Look for tool calls
        tool_calls = []
        ai_responses = []

        for msg in messages:
            msg_type = msg.__class__.__name__

            if msg_type == "AIMessage":
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(tc["name"])
                        print(f"\n   [TOOL CALL] {tc['name']}")
                        print(f"      Args: {tc.get('args', {})}")

                if hasattr(msg, "content") and msg.content:
                    ai_responses.append(msg.content)
                    print(f"\n   [AI] {msg.content[:200]}...")

            elif msg_type == "ToolMessage":
                if hasattr(msg, "content"):
                    print(f"\n   [TOOL RESULT] {msg.content[:200]}...")

        print("\n" + "=" * 80)
        print("ANALYSIS:")
        print("=" * 80)

        if tool_calls:
            print(f"\n[SUCCESS] Agent invoked {len(tool_calls)} tool(s):")
            for tc in tool_calls:
                print(f"   - {tc}")

            # Check if it used the right tools
            has_navigate = any("navigate" in tc.lower() for tc in tool_calls)
            has_screenshot = any("screenshot" in tc.lower() for tc in tool_calls)

            if has_navigate and has_screenshot:
                print("\n[PERFECT] Agent used BOTH navigate_page AND take_screenshot!")
                print("The Smithery Chrome DevTools MCP is FULLY WORKING!")
            elif has_navigate:
                print("\n[PARTIAL] Agent used navigate but not screenshot yet")
            else:
                print("\n[PARTIAL] Agent used tools but not the expected ones")
        else:
            print("\n[FAILED] Agent did NOT invoke any tools")
            print("\nAgent's response:")
            for resp in ai_responses:
                print(f"   {resp}")
            print("\nThe agent still refuses to use browser automation tools!")
            print("This means the system prompt update may not have taken effect.")

        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
