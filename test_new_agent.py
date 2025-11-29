"""Test the new grok_4_1 agent"""
import asyncio
import httpx


async def test():
    base_url = "http://127.0.0.1:2024"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Create thread
        thread_resp = await client.post(f"{base_url}/threads", json={})
        thread_id = thread_resp.json()["thread_id"]
        print(f"Thread: {thread_id}")
        
        # Run agent
        run_resp = await client.post(
            f"{base_url}/threads/{thread_id}/runs",
            json={
                "assistant_id": "mcp_agent_grok_4_1",  # NEW AGENT!
                "input": {"messages": [{"role": "user", "content": "Say hello"}]}
            }
        )
        run_id = run_resp.json()["run_id"]
        print(f"Run: {run_id}")
        
        # Wait for completion
        for _ in range(30):
            await asyncio.sleep(2)
            status_resp = await client.get(f"{base_url}/threads/{thread_id}/runs/{run_id}")
            status = status_resp.json()["status"]
            if status in ["success", "error"]:
                print(f"\nStatus: {status}")
                print("\n" + "="*80)
                print("CHECK IN LANGSMITH:")
                print(f"https://smith.langchain.com/")
                print(f"Search for thread: {thread_id}")
                print(f"Look for model_name: should be 'grok-4-1-fast-reasoning'")
                print("="*80)
                break


asyncio.run(test())
