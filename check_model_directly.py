"""Direct verification of the model being instantiated"""
import asyncio
import sys


async def check_model():
    """Import and check the model configuration directly"""
    # Import the agent function
    from mcp_agent_grok_fast import agent

    # Create the agent
    print("Creating agent...")
    agent_instance = await agent()

    # Access the model from the agent's state
    # The agent is a CompiledGraph, we need to inspect it
    print(f"\nAgent type: {type(agent_instance)}")
    print(f"Agent: {agent_instance}")

    # Try to access the model through the agent
    if hasattr(agent_instance, 'nodes'):
        print(f"\nAgent nodes: {agent_instance.nodes}")

    if hasattr(agent_instance, 'get_state'):
        print(f"\nAgent has get_state method")

    # Check if we can access builder info
    if hasattr(agent_instance, 'builder'):
        print(f"\nBuilder: {agent_instance.builder}")

    # The best way is to inspect the source code that was loaded
    import inspect
    source = inspect.getsource(agent)

    print("\n" + "="*80)
    print("MODEL CONFIGURATION IN SOURCE CODE:")
    print("="*80)

    for line in source.split('\n'):
        if 'ChatXAI' in line or ('model=' in line and 'grok' in line.lower()):
            print(line.strip())

    print("="*80)


if __name__ == "__main__":
    asyncio.run(check_model())
