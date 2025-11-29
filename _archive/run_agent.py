"""
Simple runner script to test the simple_parallel_agent
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

async def main():
    """Run the agent with a simple test query"""

    # Import the agent
    from simple_parallel_agent import agent

    print(">> Initializing agent...")
    ag = await agent()

    print(">> Agent initialized successfully!")
    print("\n" + "="*60)
    print(">> Running test query...")
    print("="*60 + "\n")

    # Run a simple test query
    result = await ag.ainvoke({
        "messages": [{"role": "user", "content": "What is LangGraph? Use perplexity to research this."}]
    })

    print("\n" + "="*60)
    print(">> RESULT:")
    print("="*60 + "\n")

    # Print the final messages
    for msg in result.get("messages", []):
        # Messages are LangChain message objects
        role = msg.__class__.__name__.replace("Message", "").lower()
        content = msg.content if hasattr(msg, 'content') else str(msg)
        if content:
            print(f"\n[{role.upper()}]:")
            print(content)
            print("-"*60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n!! Interrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
