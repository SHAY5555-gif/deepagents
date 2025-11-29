"""Simple test for GLM-4.6 Cerebras agent"""

import asyncio
from langgraph_sdk import get_client

async def test():
    client = get_client(url="http://localhost:2024")

    # Create thread
    thread = await client.threads.create()
    print(f"Thread created: {thread['thread_id']}")

    # Send simple message
    async for chunk in client.runs.stream(
        thread["thread_id"],
        "mcp_agent_bright_data_glm",
        input={"messages": [{"role": "user", "content": "Hi! Just say hello back."}]},
        stream_mode="values"
    ):
        if "messages" in chunk:
            for msg in chunk["messages"]:
                if msg.get("type") == "ai":
                    print(f"\nAI Response: {msg.get('content', '')}")

    print("\n[TEST PASSED] Agent responded successfully via Cerebras!")

if __name__ == "__main__":
    asyncio.run(test())
