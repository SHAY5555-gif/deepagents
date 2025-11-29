"""Test script to verify Grok Fast agent is using the updated model"""
import asyncio
import httpx
import json


async def test_agent():
    """Test the mcp_agent_grok_fast agent"""
    base_url = "http://127.0.0.1:2024"

    # Create a thread
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Create thread
        thread_response = await client.post(
            f"{base_url}/threads",
            json={"metadata": {"test": "grok_model_check"}}
        )
        thread_data = thread_response.json()
        thread_id = thread_data["thread_id"]
        print(f"Created thread: {thread_id}")

        # Send a simple test message
        run_response = await client.post(
            f"{base_url}/threads/{thread_id}/runs",
            json={
                "assistant_id": "mcp_agent_grok_fast",
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": "What model are you using? Just tell me the exact model name."
                    }]
                }
            }
        )
        run_data = run_response.json()
        run_id = run_data["run_id"]
        print(f"Started run: {run_id}")

        # Poll for completion
        max_attempts = 30
        for attempt in range(max_attempts):
            await asyncio.sleep(2)
            status_response = await client.get(
                f"{base_url}/threads/{thread_id}/runs/{run_id}"
            )
            status_data = status_response.json()
            status = status_data["status"]
            print(f"Attempt {attempt + 1}/{max_attempts}: Status = {status}")

            if status in ["success", "error", "timeout"]:
                # Get the thread state to see messages
                state_response = await client.get(
                    f"{base_url}/threads/{thread_id}/state"
                )
                state_data = state_response.json()

                print("\n" + "="*80)
                print("AGENT RESPONSE:")
                print("="*80)

                # Print the latest messages
                messages = state_data.get("values", {}).get("messages", [])
                for msg in messages[-3:]:  # Show last 3 messages
                    role = msg.get("type", msg.get("role", "unknown"))
                    content = msg.get("content", "")
                    print(f"\n[{role.upper()}]:")
                    print(content)

                print("\n" + "="*80)

                if status == "success":
                    print("\nTest completed successfully!")

                    # Check if model name appears in response
                    response_text = str(messages)
                    if "grok-4-1-fast-reasoning-latest" in response_text.lower() or "grok-4.1" in response_text.lower():
                        print("[SUCCESS] Agent is using the updated model: grok-4-1-fast-reasoning-latest")
                    else:
                        print("[WARNING] Could not confirm model name in response")
                else:
                    print(f"\nTest ended with status: {status}")

                break
        else:
            print("\nTest timed out waiting for response")


if __name__ == "__main__":
    asyncio.run(test_agent())
