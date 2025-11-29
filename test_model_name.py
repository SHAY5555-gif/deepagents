"""Test to get exact model name from agent configuration"""
import asyncio
import httpx


async def test_model():
    """Test to verify exact model name"""
    base_url = "http://127.0.0.1:2024"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Create thread
        thread_response = await client.post(
            f"{base_url}/threads",
            json={"metadata": {"test": "model_verification"}}
        )
        thread_data = thread_response.json()
        thread_id = thread_data["thread_id"]
        print(f"Thread created: {thread_id}")

        # Send message asking for exact model string
        run_response = await client.post(
            f"{base_url}/threads/{thread_id}/runs",
            json={
                "assistant_id": "mcp_agent_grok_fast",
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": "Please tell me the EXACT model identifier string you are using (the string that was passed to ChatXAI model parameter). Include the full version name like grok-4-X-fast-reasoning-latest."
                    }]
                }
            }
        )
        run_data = run_response.json()
        run_id = run_data["run_id"]
        print(f"Run started: {run_id}")

        # Poll for completion
        for attempt in range(30):
            await asyncio.sleep(2)
            status_response = await client.get(
                f"{base_url}/threads/{thread_id}/runs/{run_id}"
            )
            status_data = status_response.json()
            status = status_data["status"]
            print(f"Status check {attempt + 1}: {status}")

            if status in ["success", "error", "timeout"]:
                # Get state
                state_response = await client.get(
                    f"{base_url}/threads/{thread_id}/state"
                )
                state_data = state_response.json()
                messages = state_data.get("values", {}).get("messages", [])

                print("\n" + "="*80)
                print("AGENT RESPONSE:")
                print("="*80)

                # Show only the AI response
                for msg in messages:
                    if msg.get("type") == "ai" or msg.get("role") == "assistant":
                        print(msg.get("content", ""))

                print("="*80 + "\n")

                # Check for model string
                response_text = str(messages).lower()
                if "grok-4-1-fast-reasoning-latest" in response_text:
                    print("[SUCCESS] Confirmed: Agent is using grok-4-1-fast-reasoning-latest")
                elif "grok-4-0-fast-reasoning-latest" in response_text or "grok-4-fast-reasoning-latest" in response_text:
                    print("[WARNING] Agent appears to be using OLD model version")
                else:
                    print("[INFO] Could not definitively determine model version from response")
                    print(f"[INFO] Response text contains: {response_text[:200]}")

                break
        else:
            print("Timeout waiting for response")


if __name__ == "__main__":
    asyncio.run(test_model())
