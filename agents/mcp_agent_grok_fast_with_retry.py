"""
Grok-4 Fast Reasoning Agent with AUTOMATIC RETRY/RESUME Logic

This is a STANDALONE SCRIPT that wraps the Grok Fast agent and adds automatic retry.
It's designed to be used OUTSIDE of LangGraph Studio for production deployments.

For LangGraph Studio usage, the base agent (mcp_agent_grok_fast.py) already has
unlimited retries built into its system prompt. This script provides programmatic
control over retries for custom deployments.

Usage:
    from mcp_agent_grok_fast_with_retry import create_agent_with_retry

    agent = await create_agent_with_retry(max_attempts=5)
    success, result, stats = await agent.execute_with_retry(
        initial_input={"messages": [{"role": "user", "content": "Your task"}]},
        config={"configurable": {"thread_id": "unique-thread-id"}}
    )
"""
import asyncio
import time
from typing import Any
from langgraph.types import Command
from langgraph.graph.state import CompiledStateGraph

# Import the base agent
from mcp_agent_grok_fast import agent as create_base_agent


class RetryPolicy:
    """Defines retry behavior"""
    def __init__(
        self,
        max_attempts: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff"""
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay)


class AutoRetryAgent:
    """
    Wrapper that adds automatic retry/resume logic to a LangGraph agent.

    Features:
    - Detects incomplete executions (errors, token limits, interruptions)
    - Automatically resumes from last checkpoint
    - Implements exponential backoff for transient errors
    - Tracks retry attempts and execution status
    """

    def __init__(self, graph: CompiledStateGraph, policy: RetryPolicy | None = None):
        self.graph = graph
        self.policy = policy or RetryPolicy()

    def _detect_outcome(self, result: Any, config: dict) -> tuple[str, str]:
        """
        Detect execution outcome.

        Returns:
            tuple of (outcome_type, reason)
            - outcome_type: "success" | "incomplete" | "interrupted" | "error"
            - reason: human-readable explanation
        """
        try:
            # Get the state snapshot to check execution status
            state_snapshot = self.graph.get_state(config)

            # Check if there are pending nodes (incomplete execution)
            if state_snapshot.next:
                # There are still nodes to execute
                if state_snapshot.tasks:
                    # Check for interrupts
                    for task in state_snapshot.tasks:
                        if task.interrupts:
                            return "interrupted", f"Agent was interrupted: {task.interrupts}"

                return "incomplete", "Agent stopped with pending operations"

            # No pending nodes - check if result indicates success
            if isinstance(result, dict):
                # Check for error indicators in result
                if result.get("error"):
                    return "error", f"Agent returned error: {result.get('error')}"

                # Check for explicit completion markers
                if result.get("completed") is False:
                    return "incomplete", "Task marked as incomplete"

            # If we got here, execution completed successfully
            return "success", "Task completed successfully"

        except Exception as e:
            return "error", f"Failed to detect outcome: {str(e)}"

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable"""
        error_str = str(error).lower()

        # Retryable errors (transient issues)
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "429",
            "503",
            "502",
            "504",
        ]

        # Non-retryable errors (permanent issues)
        non_retryable_patterns = [
            "authentication",
            "unauthorized",
            "401",
            "403",
            "invalid",
            "not found",
            "404",
        ]

        # Check non-retryable first
        for pattern in non_retryable_patterns:
            if pattern in error_str:
                return False

        # Check retryable
        for pattern in retryable_patterns:
            if pattern in error_str:
                return True

        # Default: retry unknown errors
        return True

    async def execute_with_retry(
        self,
        initial_input: dict | Command,
        config: dict,
        verbose: bool = True
    ) -> tuple[bool, Any, dict]:
        """
        Execute the agent with automatic retry/resume logic.

        Args:
            initial_input: The initial input to the agent
            config: LangGraph config (must include thread_id for checkpointing)
            verbose: Whether to print status messages

        Returns:
            tuple of (success, final_result, execution_stats)
        """
        stats = {
            "total_attempts": 0,
            "retries": 0,
            "outcome_history": [],
            "total_time": 0.0
        }

        start_time = time.time()
        attempt = 0
        last_result = None

        while attempt < self.policy.max_attempts:
            attempt += 1
            stats["total_attempts"] = attempt

            if verbose:
                if attempt == 1:
                    print(f"\n🚀 Starting task execution (attempt {attempt}/{self.policy.max_attempts})")
                else:
                    print(f"\n🔄 Retrying task execution (attempt {attempt}/{self.policy.max_attempts})")

            try:
                # For first attempt, use initial input
                # For retries, resume from checkpoint with None (continue from last state)
                input_data = initial_input if attempt == 1 else None

                # Execute the agent
                result = await self.graph.ainvoke(input_data, config)
                last_result = result

                # Detect outcome
                outcome_type, reason = self._detect_outcome(result, config)
                stats["outcome_history"].append({
                    "attempt": attempt,
                    "outcome": outcome_type,
                    "reason": reason
                })

                if verbose:
                    print(f"📊 Execution outcome: {outcome_type} - {reason}")

                # Handle different outcomes
                if outcome_type == "success":
                    stats["total_time"] = time.time() - start_time
                    if verbose:
                        print(f"✅ Task completed successfully in {stats['total_attempts']} attempt(s)")
                        print(f"⏱️ Total execution time: {stats['total_time']:.2f}s")
                    return True, result, stats

                elif outcome_type == "interrupted":
                    # Interrupts require user input - can't auto-retry
                    stats["total_time"] = time.time() - start_time
                    if verbose:
                        print(f"⏸️ Task interrupted (requires user input): {reason}")
                    return False, result, stats

                elif outcome_type in ["incomplete", "error"]:
                    # Retry if we haven't exceeded max attempts
                    if attempt < self.policy.max_attempts:
                        stats["retries"] += 1
                        delay = self.policy.get_delay(attempt)

                        if verbose:
                            print(f"⚠️ {outcome_type.capitalize()}: {reason}")
                            print(f"⏳ Waiting {delay:.1f}s before retry {attempt + 1}/{self.policy.max_attempts}...")

                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Max attempts reached
                        stats["total_time"] = time.time() - start_time
                        if verbose:
                            print(f"❌ Task failed after {self.policy.max_attempts} attempts")
                            print(f"⏱️ Total execution time: {stats['total_time']:.2f}s")
                        return False, result, stats

            except Exception as e:
                # Handle execution errors
                error_msg = str(e)
                stats["outcome_history"].append({
                    "attempt": attempt,
                    "outcome": "exception",
                    "reason": error_msg
                })

                if verbose:
                    print(f"💥 Exception during execution: {error_msg}")

                # Check if error is retryable
                if self._is_retryable_error(e) and attempt < self.policy.max_attempts:
                    stats["retries"] += 1
                    delay = self.policy.get_delay(attempt)

                    if verbose:
                        print(f"🔧 Error appears retryable, waiting {delay:.1f}s before retry...")

                    await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable error or max attempts reached
                    stats["total_time"] = time.time() - start_time
                    if verbose:
                        print(f"❌ Non-retryable error or max attempts reached")
                    return False, None, stats

        # Should never reach here, but just in case
        stats["total_time"] = time.time() - start_time
        return False, last_result, stats


# Public API for creating retry-enabled agents
async def create_agent_with_retry(
    max_attempts: int = 5,
    initial_delay: float = 2.0
) -> AutoRetryAgent:
    """
    Create a Grok Fast agent with automatic retry capabilities.

    This is the recommended way to create an agent with retry logic for
    production deployments outside of LangGraph Studio.

    Args:
        max_attempts: Maximum number of retry attempts (default: 5)
        initial_delay: Initial retry delay in seconds (default: 2.0)

    Returns:
        AutoRetryAgent instance with custom configuration

    Example:
        ```python
        agent = await create_agent_with_retry(max_attempts=5)

        success, result, stats = await agent.execute_with_retry(
            initial_input={"messages": [{"role": "user", "content": "Your task"}]},
            config={"configurable": {"thread_id": "my-thread"}}
        )

        if success:
            print(f"Task completed in {stats['total_attempts']} attempts")
        else:
            print(f"Task failed after {stats['total_attempts']} attempts")
        ```
    """
    base_agent = await create_base_agent()

    retry_policy = RetryPolicy(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=60.0,
        exponential_base=2.0
    )

    return AutoRetryAgent(graph=base_agent, policy=retry_policy)


# For LangGraph Studio compatibility - export the base agent directly
# The base agent already has built-in retry logic through the system prompt
agent = create_base_agent
