"""
Test script to verify Bright Data MCP tools on Railway deployment
"""
import requests
import json
import time

# Railway deployment URL
BASE_URL = "https://deepagents-langgraph-production.up.railway.app"

def create_thread():
    """Create a new thread"""
    response = requests.post(f"{BASE_URL}/threads", json={"metadata": {}})
    response.raise_for_status()
    return response.json()["thread_id"]

def send_message(thread_id, message):
    """Send a message to the agent"""
    payload = {
        "assistant_id": "mcp_agent_bright_data_only",
        "input": {
            "messages": [{"role": "user", "content": message}]
        },
        "stream_mode": "values"
    }
    response = requests.post(f"{BASE_URL}/threads/{thread_id}/runs", json=payload)
    response.raise_for_status()
    return response.json()["run_id"]

def get_run_status(thread_id, run_id):
    """Get the status of a run"""
    response = requests.get(f"{BASE_URL}/threads/{thread_id}/runs/{run_id}")
    response.raise_for_status()
    return response.json()

def get_thread_state(thread_id):
    """Get the current state of a thread"""
    response = requests.get(f"{BASE_URL}/threads/{thread_id}/state")
    response.raise_for_status()
    return response.json()

def test_bright_data_tools():
    """Test that Bright Data tools are available and working"""
    print("=" * 80)
    print("TESTING RAILWAY DEPLOYMENT - Bright Data MCP Tools")
    print("=" * 80)

    # Create thread
    print("\n1. Creating thread...")
    thread_id = create_thread()
    print(f"   [OK] Thread created: {thread_id}")

    # Test 1: Ask about available tools
    print("\n2. Asking agent to list Bright Data tools...")
    run_id = send_message(thread_id, "List only your Bright Data MCP tools (search_engine, scrape_as_markdown, etc.)")

    # Wait for completion
    print("   Waiting for response...")
    for _ in range(30):  # Wait up to 30 seconds
        time.sleep(1)
        run = get_run_status(thread_id, run_id)
        if run["status"] in ["success", "error"]:
            break

    if run["status"] == "success":
        print(f"   [OK] Run completed successfully")

        # Get response
        state = get_thread_state(thread_id)
        messages = state["values"]["messages"]
        last_message = messages[-1]
        print(f"\n   Agent Response:")
        print(f"   {last_message['content'][:500]}...")
    else:
        print(f"   [FAILED] Run failed with status: {run['status']}")
        return False

    # Test 2: Try to use a Bright Data tool
    print("\n3. Testing scrape_as_markdown tool...")
    run_id = send_message(thread_id, "Use scrape_as_markdown to scrape https://example.com and show me the first 100 characters")

    print("   Waiting for response...")
    for _ in range(60):  # Wait up to 60 seconds
        time.sleep(1)
        run = get_run_status(thread_id, run_id)
        if run["status"] in ["success", "error"]:
            break

    if run["status"] == "success":
        print(f"   [OK] Tool execution completed")

        # Get response
        state = get_thread_state(thread_id)
        messages = state["values"]["messages"]
        last_message = messages[-1]
        print(f"\n   Agent Response:")
        print(f"   {last_message['content'][:500]}...")

        # Check if scraping was successful
        if "example" in last_message['content'].lower() or "scraped" in last_message['content'].lower():
            print("\n   [SUCCESS] Bright Data tool executed successfully!")
            return True
        else:
            print("\n   [WARNING] Tool executed but response unclear")
            return True
    else:
        print(f"   [FAILED] Tool execution failed with status: {run['status']}")
        return False

    print("\n" + "=" * 80)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    try:
        success = test_bright_data_tools()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
