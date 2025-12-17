"""Test parallel sub-agents for stock price search."""
import os
import asyncio
from langgraph_sdk import get_client

# Railway backend URL
LANGGRAPH_URL = "https://deepagents-langgraph-production.up.railway.app"

async def test_parallel_subagents():
    """Test parallel sub-agents for stock price searches."""
    print("=" * 80)
    print("Testing Parallel Sub-Agents for Stock Prices")
    print("=" * 80)

    client = get_client(url=LANGGRAPH_URL)

    # List available assistants
    print("\n1. Listing available assistants...")
    try:
        assistants = await client.assistants.search()
        print(f"   Found {len(assistants)} assistants:")
        for a in assistants:
            print(f"   - {a['assistant_id']}: {a.get('name', 'N/A')}")
    except Exception as e:
        print(f"   Error listing assistants: {e}")
        return

    # Find the cerebras_brightdata_genius assistant
    assistant_id = "cerebras_brightdata_genius"

    # Create a new thread
    print(f"\n2. Creating a new thread for {assistant_id}...")
    try:
        thread = await client.threads.create()
        thread_id = thread["thread_id"]
        print(f"   Thread created: {thread_id}")
    except Exception as e:
        print(f"   Error creating thread: {e}")
        return

    # Send a message to test parallel sub-agents
    print("\n3. Sending message to test parallel sub-agents...")
    message = """Use 3 sub-agents in parallel to search for current stock prices:
1) Google (GOOGL) - search for latest Google stock price
2) Microsoft (MSFT) - search for latest Microsoft stock price
3) Apple (AAPL) - search for latest Apple stock price

Each sub-agent should use web search to find the current price."""

    print(f"   Message: {message[:100]}...")

    try:
        # Stream the response
        print("\n4. Waiting for response (streaming)...")
        print("-" * 40)

        async for chunk in client.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            input={"messages": [{"role": "user", "content": message}]},
            stream_mode="values",
        ):
            if chunk.event == "values":
                messages = chunk.data.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    if last_msg.get("type") == "ai" or last_msg.get("role") == "assistant":
                        content = last_msg.get("content", "")
                        if content and isinstance(content, str):
                            print(f"\nAssistant: {content[:500]}...")
                        elif content and isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    print(f"\nAssistant: {item.get('text', '')[:500]}...")
            elif chunk.event == "error":
                print(f"\nERROR: {chunk.data}")

        print("\n" + "-" * 40)
        print("Stream completed!")

    except Exception as e:
        print(f"   Error during run: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_parallel_subagents())
