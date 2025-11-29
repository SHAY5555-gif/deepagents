"""
Example: Using Grok Fast Agent with Automatic Retry/Resume

This script demonstrates how to use the AutoRetryAgent wrapper to automatically
retry incomplete tasks. Perfect for production deployments that need resilience.
"""
import asyncio
from langgraph.checkpoint.memory import MemorySaver
from mcp_agent_grok_fast_with_retry import create_agent_with_retry


async def example_with_retry():
    """Example: Run a task with automatic retry logic"""

    print("=" * 80)
    print("EXAMPLE: Grok Fast Agent with Automatic Retry/Resume")
    print("=" * 80)

    # Create the agent with retry capabilities
    print("\n1️⃣ Creating agent with retry (max 5 attempts)...")
    retry_agent = await create_agent_with_retry(
        max_attempts=5,
        initial_delay=2.0
    )

    print("✅ Agent created!\n")

    # Define the task
    task_message = """
    Navigate to https://news.ycombinator.com and:
    1. Take a screenshot of the front page
    2. Extract the top 3 story titles
    3. Save them to a file called 'top_hn_stories.txt'
    4. Report completion with the story titles
    """

    # Prepare input
    initial_input = {
        "messages": [{"role": "user", "content": task_message}]
    }

    # Configure with thread_id for checkpointing
    config = {
        "configurable": {
            "thread_id": "example-task-001"
        }
    }

    print("2️⃣ Starting task execution with automatic retry...")
    print(f"   Task: {task_message.strip()[:60]}...")
    print(f"   Thread ID: {config['configurable']['thread_id']}\n")

    # Execute with automatic retry
    success, result, stats = await retry_agent.execute_with_retry(
        initial_input=initial_input,
        config=config,
        verbose=True  # Show detailed progress
    )

    # Print results
    print("\n" + "=" * 80)
    print("EXECUTION RESULTS")
    print("=" * 80)
    print(f"Success: {success}")
    print(f"Total attempts: {stats['total_attempts']}")
    print(f"Retries: {stats['retries']}")
    print(f"Total time: {stats['total_time']:.2f}s")
    print(f"\nOutcome history:")
    for i, outcome in enumerate(stats['outcome_history'], 1):
        print(f"  Attempt {outcome['attempt']}: {outcome['outcome']} - {outcome['reason']}")

    if success:
        print("\n✅ Task completed successfully!")
        if result and 'messages' in result:
            print(f"\nFinal message: {result['messages'][-1].get('content', 'No content')[:200]}...")
    else:
        print("\n❌ Task failed after all retry attempts")

    return success, result, stats


async def example_manual_resume():
    """Example: Manually resume from a specific checkpoint"""

    print("\n" + "=" * 80)
    print("EXAMPLE: Manual Resume from Checkpoint")
    print("=" * 80)

    # This example shows how to manually resume if you want more control
    retry_agent = await create_agent_with_retry(max_attempts=3)

    # First, start a task that might fail
    thread_id = "manual-resume-example"
    initial_input = {
        "messages": [{"role": "user", "content": "List the top 5 Python web frameworks"}]
    }
    config = {"configurable": {"thread_id": thread_id}}

    print("\n1️⃣ Starting initial task...")
    success, result, stats = await retry_agent.execute_with_retry(
        initial_input=initial_input,
        config=config,
        verbose=True
    )

    # Check the state after execution
    state_snapshot = retry_agent.graph.get_state(config)

    print(f"\n2️⃣ Checking execution state...")
    print(f"   Has pending nodes: {bool(state_snapshot.next)}")
    print(f"   Current state keys: {list(state_snapshot.values.keys()) if state_snapshot.values else 'None'}")

    # If incomplete, we could manually resume
    if state_snapshot.next:
        print("\n3️⃣ Task incomplete - manually resuming...")

        # Resume by invoking with None (continues from checkpoint)
        resumed_result = await retry_agent.graph.ainvoke(None, config)
        print(f"✅ Resumed execution completed")

    return success, result


async def example_with_custom_retry_policy():
    """Example: Using custom retry settings"""

    print("\n" + "=" * 80)
    print("EXAMPLE: Custom Retry Policy")
    print("=" * 80)

    # Create agent with aggressive retry policy
    retry_agent = await create_agent_with_retry(
        max_attempts=10,      # More attempts
        initial_delay=0.5     # Shorter delays
    )

    task_message = "What is the weather in San Francisco?"
    initial_input = {"messages": [{"role": "user", "content": task_message}]}
    config = {"configurable": {"thread_id": "custom-retry-example"}}

    print("\n🔧 Using custom retry policy:")
    print(f"   Max attempts: 10")
    print(f"   Initial delay: 0.5s")
    print(f"   Exponential backoff: 2x")
    print(f"   Max delay: 60s\n")

    success, result, stats = await retry_agent.execute_with_retry(
        initial_input=initial_input,
        config=config,
        verbose=True
    )

    return success, result, stats


async def main():
    """Run all examples"""
    print("\n" + "🤖" * 40)
    print("Grok Fast Agent - Automatic Retry/Resume Examples")
    print("🤖" * 40)

    # Example 1: Basic usage with retry
    await example_with_retry()

    # Example 2: Manual resume (uncomment to test)
    # await example_manual_resume()

    # Example 3: Custom retry policy (uncomment to test)
    # await example_with_custom_retry_policy()

    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
