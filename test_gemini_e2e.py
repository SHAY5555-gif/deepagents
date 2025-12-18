"""End-to-end test of Gemini 3 Flash agent with BrightData tools."""
import sys
import os

# Load .env file first
from dotenv import load_dotenv
load_dotenv()

# Force reload of the module to get fresh code
for mod in list(sys.modules.keys()):
    if 'gemini3_flash' in mod:
        del sys.modules[mod]

# Now import
from agents.gemini3_flash_brightdata_genius import (
    ChatGemini3Flash,
    get_all_tools,
    get_gemini3_flash_model
)
from langchain_core.messages import HumanMessage

def test_agent_with_search():
    print("=" * 60)
    print("Testing Gemini 3 Flash Agent with BrightData Search")
    print("=" * 60)

    # Get tools
    tools = get_all_tools()
    print(f"\n[1] Got {len(tools)} tools:")
    for t in tools:
        print(f"    - {t.name}")

    # Create model
    model = get_gemini3_flash_model(thinking_level="NONE")
    print(f"\n[2] Model created: {model.model_name}")

    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    print(f"\n[3] Tools bound to model")

    # Test query
    query = "What is the current weather in Tel Aviv? Use brightdata_search_google to find out."
    print(f"\n[4] Query: {query}")

    # Invoke
    print(f"\n[5] Invoking model...")
    try:
        response = model_with_tools.invoke([HumanMessage(content=query)])
        print(f"\n[6] Response received!")
        print(f"    Type: {type(response).__name__}")
        print(f"    Content: {response.content[:500] if response.content else 'No content'}")

        # Check for tool calls
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f"\n[7] Tool calls detected: {len(response.tool_calls)}")
            for tc in response.tool_calls:
                print(f"    - Tool: {tc.get('name', 'unknown')}")
                print(f"      Args: {tc.get('args', {})}")
        else:
            print(f"\n[7] No tool calls in response")

        # Check additional_kwargs for tool calls
        if hasattr(response, 'additional_kwargs') and response.additional_kwargs:
            print(f"\n[8] Additional kwargs: {list(response.additional_kwargs.keys())}")
            if 'tool_calls' in response.additional_kwargs:
                print(f"    Tool calls in additional_kwargs: {response.additional_kwargs['tool_calls']}")

        print("\n" + "=" * 60)
        print("TEST PASSED - Agent responded successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 60)
        print("TEST FAILED")
        print("=" * 60)

if __name__ == "__main__":
    test_agent_with_search()
