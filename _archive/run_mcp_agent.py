"""
Runner script for mcp_agent_async.py
"""
import asyncio
import sys
from dotenv import load_dotenv

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

async def main():
    """Run the MCP agent with Chrome DevTools"""

    # Import the agent
    from mcp_agent_async import agent

    print(">> Initializing MCP agent with Chrome DevTools...")
    ag = await agent()

    print(">> Agent initialized successfully!")
    print("\n" + "="*60)
    print(">> Running test query...")
    print("="*60 + "\n")

    # Run a test query
    test_query = "Go to google.com and take a screenshot"
    print(f"Query: {test_query}\n")

    result = await ag.ainvoke({
        "messages": [{"role": "user", "content": test_query}]
    })

    print("\n" + "="*60)
    print(">> RESULT:")
    print("="*60 + "\n")

    # Print the final messages
    for i, msg in enumerate(result.get("messages", []), 1):
        # Messages are LangChain message objects
        role = msg.__class__.__name__.replace("Message", "").lower()
        content = msg.content if hasattr(msg, 'content') else str(msg)

        print(f"[Message {i} - {role.upper()}]")

        if content:
            # Truncate very long content
            if isinstance(content, str) and len(content) > 500:
                print(content[:500] + "...(truncated)")
            else:
                print(content)

        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            print(f"Tool Calls: {len(msg.tool_calls)}")
            for tc in msg.tool_calls:
                print(f"  - {tc.get('name', 'unknown')}")

        print("-"*60)

    print("\n>> Test completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n!! Interrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
