"""
Simple test of deepagents without external MCP dependencies
"""
import asyncio
import sys
import os
from dotenv import load_dotenv
from deepagents import create_deep_agent
from langchain_core.tools import tool

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()


@tool
def calculate_sum(a: float, b: float) -> float:
    """Add two numbers together"""
    return a + b


@tool
def calculate_product(a: float, b: float) -> float:
    """Multiply two numbers together"""
    return a * b


async def main():
    """Run a simple agent with basic tools"""

    print(">> Creating simple deep agent...")
    print("   Model: claude-sonnet-4-5-20250929")
    print("   Tools: calculate_sum, calculate_product")
    print()

    # Create agent with simple tools
    agent = create_deep_agent(
        tools=[calculate_sum, calculate_product],
        system_prompt="""You are a helpful math assistant.
        You have access to tools to add and multiply numbers.
        Use these tools to help answer questions."""
    )

    print(">> Agent created successfully!\n")
    print("="*60)
    print(">> Running test query...")
    print("="*60 + "\n")

    # Test query
    test_query = "What is (5 + 3) * 7? Please use the tools to calculate this step by step."
    print(f"Query: {test_query}\n")

    try:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": test_query}]
        })

        print("\n" + "="*60)
        print(">> RESULT:")
        print("="*60 + "\n")

        # Print messages
        for i, msg in enumerate(result.get("messages", []), 1):
            msg_type = msg.__class__.__name__.replace("Message", "")

            print(f"[Message {i} - {msg_type}]")

            if hasattr(msg, 'content') and msg.content:
                print(f"Content: {msg.content}")

            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"Tool Calls: {len(msg.tool_calls)}")
                for tc in msg.tool_calls:
                    print(f"  - {tc.get('name', 'unknown')}: {tc.get('args', {})}")

            print("-"*60)

        print("\n>> Test completed successfully!")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n!! Interrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
