"""Full cycle test - Gemini 3 Flash agent with actual tool execution."""
import sys
import os
import json

# Load .env file first
from dotenv import load_dotenv
load_dotenv()

# Force reload of the module to get fresh code
for mod in list(sys.modules.keys()):
    if 'gemini3_flash' in mod or 'brightdata' in mod:
        del sys.modules[mod]

# Now import
from agents.gemini3_flash_brightdata_genius import (
    ChatGemini3Flash,
    get_all_tools,
    get_gemini3_flash_model
)
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

def test_full_agent_cycle():
    print("=" * 60)
    print("FULL CYCLE TEST: Gemini 3 Flash + BrightData Execution")
    print("=" * 60)

    # Get tools
    tools = get_all_tools()
    tools_dict = {t.name: t for t in tools}
    print(f"\n[1] Loaded {len(tools)} tools")

    # Create model
    model = get_gemini3_flash_model(thinking_level="NONE")
    model_with_tools = model.bind_tools(tools)
    print(f"[2] Model created and tools bound")

    # Initial query
    messages = [
        HumanMessage(content="Search for 'LangChain agents 2024' using BrightData Google search and summarize what you find.")
    ]
    print(f"\n[3] Query: {messages[0].content}")

    # First invocation - should get tool call
    print(f"\n[4] Invoking model (expecting tool call)...")
    response = model_with_tools.invoke(messages)

    if not response.tool_calls:
        print(f"[ERROR] No tool calls generated!")
        print(f"Response content: {response.content}")
        return False

    print(f"[5] Got tool call: {response.tool_calls[0]['name']}")
    print(f"    Args: {response.tool_calls[0]['args']}")

    # Execute the tool
    tool_call = response.tool_calls[0]
    tool_name = tool_call['name']
    tool_args = tool_call['args']
    tool_id = tool_call.get('id', 'call_1')

    print(f"\n[6] Executing tool: {tool_name}...")
    tool = tools_dict.get(tool_name)
    if not tool:
        print(f"[ERROR] Tool {tool_name} not found!")
        return False

    try:
        # Execute the tool
        result = tool.invoke(tool_args)
        result_str = str(result)
        print(f"[7] Tool result (first 500 chars): {result_str[:500]}...")
    except Exception as e:
        print(f"[ERROR] Tool execution failed: {type(e).__name__}: {e}")
        result_str = f"Error: {e}"

    # Add messages for second invocation
    messages.append(response)
    messages.append(ToolMessage(content=result_str, tool_call_id=tool_id, name=tool_name))

    # Second invocation - should get summary
    print(f"\n[8] Invoking model with tool results...")
    try:
        final_response = model_with_tools.invoke(messages)
        print(f"\n[9] Final response:")
        print("-" * 40)
        if final_response.content:
            print(final_response.content[:1000])
            if len(final_response.content) > 1000:
                print(f"\n... (truncated, total {len(final_response.content)} chars)")
        else:
            print("(No content)")

        # Check if model wants another tool call
        if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
            print(f"\n[!] Model wants more tool calls: {len(final_response.tool_calls)}")
            for tc in final_response.tool_calls:
                print(f"    - {tc.get('name')}: {tc.get('args')}")

        print("-" * 40)
    except Exception as e:
        print(f"[ERROR] Final invocation failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("FULL CYCLE TEST PASSED!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_full_agent_cycle()
    sys.exit(0 if success else 1)
