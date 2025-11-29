"""Test GLM-4.6 agent with disabled_params fix"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from langgraph_sdk import get_client

async def test_glm_agent():
    """Test the GLM-4.6 agent with a simple query"""

    # Connect to LangGraph server
    client = get_client(url="http://localhost:2024")

    # Get the mcp_agent_bright_data_glm assistant
    assistant_id = "mcp_agent_bright_data_glm"

    print(f"Testing {assistant_id}...")
    print("=" * 80)

    try:
        # Create a thread
        thread = await client.threads.create()
        print(f"Created thread: {thread['thread_id']}")

        # Simple test query that should trigger the model
        test_message = "Say hi! Just respond with a simple greeting."

        print(f"\nSending message: {test_message}")
        print("-" * 80)

        # Stream the response
        async for chunk in client.runs.stream(
            thread["thread_id"],
            assistant_id,
            input={"messages": [{"role": "user", "content": test_message}]},
            stream_mode="updates",
        ):
            print(f"Chunk: {chunk}")

        print("\n" + "=" * 80)
        print("✓ SUCCESS! Agent responded without 404 errors!")
        return True

    except Exception as e:
        print(f"\n" + "=" * 80)
        print(f"✗ FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_glm_agent())
    exit(0 if success else 1)
