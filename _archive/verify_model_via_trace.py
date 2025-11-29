"""Verify model by checking LangSmith traces after agent run"""
import asyncio
import httpx
import time


async def run_and_check():
    """Run agent and provide trace link for verification"""
    base_url = "http://127.0.0.1:2025"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Create thread
        thread_response = await client.post(
            f"{base_url}/threads",
            json={"metadata": {"test": "model_verification", "timestamp": str(time.time())}}
        )
        thread_data = thread_response.json()
        thread_id = thread_data["thread_id"]
        print(f"Thread ID: {thread_id}")

        # Send simple request
        run_response = await client.post(
            f"{base_url}/threads/{thread_id}/runs",
            json={
                "assistant_id": "mcp_agent_grok_4_1",  # NEW AGENT WITH UPDATED MODEL!
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": "Say hello"
                    }]
                }
            }
        )
        run_data = run_response.json()
        run_id = run_data["run_id"]
        print(f"Run ID: {run_id}")

        # Wait for completion
        for i in range(30):
            await asyncio.sleep(2)
            status_response = await client.get(
                f"{base_url}/threads/{thread_id}/runs/{run_id}"
            )
            status_data = status_response.json()
            status = status_data["status"]

            if status in ["success", "error", "timeout"]:
                print(f"\nRun completed with status: {status}")

                # Provide LangSmith trace URL
                print("\n" + "="*80)
                print("TO VERIFY THE MODEL:")
                print("="*80)
                print("1. Open LangSmith: https://smith.langchain.com/")
                print("2. Go to Projects > deepagents")
                print("3. Find the most recent trace (search for 'Say hello')")
                print("4. Click on the trace to expand")
                print("5. Look for the LLM call details")
                print("6. Check the 'Model' field - it should show: grok-4-1-fast-reasoning-latest")
                print("="*80)

                # Try to get trace info from metadata if available
                if "metadata" in status_data:
                    print(f"\nTrace metadata: {status_data.get('metadata', {})}")

                break
        else:
            print("Timeout waiting for run to complete")


if __name__ == "__main__":
    print("Running agent to generate LangSmith trace...")
    print("This will help verify the exact model being used.\n")
    asyncio.run(run_and_check())
