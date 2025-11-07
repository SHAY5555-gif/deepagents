# Automatic Retry/Resume System for Grok Fast Agent

## Overview

The Grok Fast agent now has **two layers** of retry logic:

1. **Built-in Persistence** (System Prompt Level)
   - The agent's system prompt instructs it to NEVER give up
   - Tries multiple approaches when encountering errors
   - Built into `mcp_agent_grok_fast.py`
   - Works automatically in LangGraph Studio

2. **Programmatic Retry Wrapper** (Code Level)
   - `AutoRetryAgent` wrapper in `mcp_agent_grok_fast_with_retry.py`
   - Detects incomplete executions and automatically retries
   - Configurable retry policy (attempts, delays, backoff)
   - Perfect for production deployments

## Layer 1: Built-in Persistence (System Prompt)

The base agent (`mcp_agent_grok_fast.py`) includes extensive instructions in its system prompt:

```python
system_prompt = """You are an UNSTOPPABLE, RELENTLESS web automation agent...

**GOLDEN RULE #1: NEVER STOP UNTIL TASK IS 100% COMPLETE**

When you encounter an error, you MUST:
1. READ the error message word-by-word
2. UNDERSTAND what specifically failed
3. DIAGNOSE the root cause
4. THINK DEEPLY about the best solution
5. TRY A FIX immediately
6. If fix #1 fails → Try fix #2
7. If fix #2 fails → Try fix #3
8. Keep trying until SUCCESS!

**YOU HAVE UNLIMITED RETRIES** - There's NO limit!
"""
```

### How It Works

- Agent **self-retries** within a single execution
- Uses its reasoning capabilities to debug and fix errors
- Tries multiple different approaches automatically
- No external code needed - works in LangGraph Studio UI

### When to Use

✅ **Use built-in persistence for:**
- Interactive development in LangGraph Studio
- Tasks where the agent can self-diagnose and fix errors
- When you want the agent to handle retries intelligently

## Layer 2: Programmatic Retry Wrapper

The `AutoRetryAgent` wrapper adds **external retry logic** that works at the execution level.

### Features

- **Outcome Detection**: Automatically detects if execution completed successfully
- **Checkpoint Resume**: Resumes from last checkpoint if incomplete
- **Exponential Backoff**: Smart delay strategy for transient errors
- **Retry Statistics**: Tracks attempts, outcomes, and execution time
- **Error Classification**: Distinguishes retryable vs. non-retryable errors

### How It Works

```python
from mcp_agent_grok_fast_with_retry import create_agent_with_retry

# Create agent with retry
retry_agent = await create_agent_with_retry(max_attempts=5)

# Execute with automatic retry
success, result, stats = await retry_agent.execute_with_retry(
    initial_input={"messages": [{"role": "user", "content": "Your task"}]},
    config={"configurable": {"thread_id": "unique-id"}},
    verbose=True
)

# Check results
if success:
    print(f"Completed in {stats['total_attempts']} attempts")
else:
    print(f"Failed after {stats['total_attempts']} attempts")
```

### Retry Logic Flow

```
Attempt 1 → Execute → Check Outcome
                      ↓
                    Success? → Return ✅
                      ↓
                    Incomplete/Error?
                      ↓
                    Wait (exponential backoff)
                      ↓
Attempt 2 → Resume from checkpoint → Check Outcome
                                       ↓
                                     Success? → Return ✅
                                       ↓
                                     Continue...
                                       ↓
Attempt 5 (Max) → Execute → Fail ❌
```

### Outcome Detection

The wrapper automatically detects:

1. **Success**: Task completed with no pending operations
2. **Incomplete**: Agent stopped with pending nodes
3. **Interrupted**: User input required (not retryable)
4. **Error**: Exception or explicit error in result

### Error Classification

**Retryable Errors** (will retry):
- Timeout errors
- Connection/network errors
- Rate limits (429, 503, 502, 504)
- Unknown errors (default: retry)

**Non-Retryable Errors** (will fail immediately):
- Authentication failures (401, 403)
- Not found errors (404)
- Invalid input errors

### Retry Policy Configuration

```python
retry_agent = await create_agent_with_retry(
    max_attempts=5,        # Maximum retry attempts
    initial_delay=2.0      # Starting delay in seconds
)

# Policy uses exponential backoff:
# Attempt 1: No delay
# Attempt 2: 2.0s delay
# Attempt 3: 4.0s delay
# Attempt 4: 8.0s delay
# Attempt 5: 16.0s delay
# (Max delay capped at 60s)
```

### When to Use

✅ **Use programmatic retry for:**
- Production deployments
- Scheduled/automated tasks
- When you need metrics and monitoring
- Tasks that might hit token limits
- Scenarios requiring graceful degradation

## Usage Examples

### Example 1: Basic Task with Retry

```python
import asyncio
from mcp_agent_grok_fast_with_retry import create_agent_with_retry

async def run_task_with_retry():
    # Create agent
    agent = await create_agent_with_retry(max_attempts=5)

    # Define task
    task = {
        "messages": [{
            "role": "user",
            "content": "Navigate to example.com and extract all links"
        }]
    }

    # Execute with retry
    success, result, stats = await agent.execute_with_retry(
        initial_input=task,
        config={"configurable": {"thread_id": "task-001"}},
        verbose=True
    )

    # Process results
    if success:
        print(f"✅ Completed in {stats['total_attempts']} attempts")
        print(f"⏱️ Total time: {stats['total_time']:.2f}s")
    else:
        print(f"❌ Failed after {stats['total_attempts']} attempts")
        for outcome in stats['outcome_history']:
            print(f"   Attempt {outcome['attempt']}: {outcome['outcome']}")

asyncio.run(run_task_with_retry())
```

### Example 2: Custom Retry Policy

```python
# Aggressive retry for critical tasks
agent = await create_agent_with_retry(
    max_attempts=10,       # More attempts
    initial_delay=0.5      # Faster retries
)

# Conservative retry for expensive operations
agent = await create_agent_with_retry(
    max_attempts=3,        # Fewer attempts
    initial_delay=5.0      # Longer delays
)
```

### Example 3: Manual Resume

```python
# Start task
success, result, stats = await agent.execute_with_retry(
    initial_input=task,
    config=config
)

# Check state
state_snapshot = agent.graph.get_state(config)

if state_snapshot.next:
    # Incomplete - manually resume
    resumed_result = await agent.graph.ainvoke(None, config)
```

## Execution Statistics

The `execute_with_retry` method returns detailed statistics:

```python
{
    "total_attempts": 3,          # How many attempts made
    "retries": 2,                 # How many retries (attempts - 1)
    "total_time": 45.3,           # Total execution time in seconds
    "outcome_history": [           # Detailed history of each attempt
        {
            "attempt": 1,
            "outcome": "incomplete",
            "reason": "Agent stopped with pending operations"
        },
        {
            "attempt": 2,
            "outcome": "error",
            "reason": "Timeout after 30s"
        },
        {
            "attempt": 3,
            "outcome": "success",
            "reason": "Task completed successfully"
        }
    ]
}
```

## Best Practices

### 1. Always Use Checkpointing

```python
# ✅ CORRECT - Includes thread_id for checkpointing
config = {"configurable": {"thread_id": "unique-task-id"}}

# ❌ WRONG - No checkpointing, can't resume
config = {}
```

### 2. Use Unique Thread IDs

```python
import uuid

# Generate unique ID per task
thread_id = f"task-{uuid.uuid4()}"
config = {"configurable": {"thread_id": thread_id}}
```

### 3. Monitor Retry Statistics

```python
success, result, stats = await agent.execute_with_retry(...)

# Log statistics for monitoring
if stats['retries'] > 2:
    logger.warning(f"Task required {stats['retries']} retries")

if stats['total_time'] > 300:
    logger.warning(f"Task took {stats['total_time']:.1f}s")
```

### 4. Handle Failures Gracefully

```python
success, result, stats = await agent.execute_with_retry(...)

if not success:
    # Check if interrupted (requires user input)
    last_outcome = stats['outcome_history'][-1]

    if last_outcome['outcome'] == 'interrupted':
        # Prompt user for input
        user_input = get_user_input()
        # Resume with input
        result = await agent.graph.ainvoke(
            Command(resume=user_input),
            config
        )
    else:
        # Permanent failure - escalate or log
        notify_failure(task, stats)
```

### 5. Tune Retry Policy for Use Case

```python
# For web scraping (transient failures common)
agent = await create_agent_with_retry(
    max_attempts=10,      # Many retries
    initial_delay=1.0     # Short delays
)

# For expensive API calls
agent = await create_agent_with_retry(
    max_attempts=3,       # Few retries
    initial_delay=10.0    # Long delays
)

# For user-facing tasks (need speed)
agent = await create_agent_with_retry(
    max_attempts=5,
    initial_delay=0.5     # Very short delays
)
```

## Comparison: Built-in vs. Programmatic Retry

| Feature | Built-in (System Prompt) | Programmatic (Wrapper) |
|---------|--------------------------|------------------------|
| **Retry Location** | Inside agent execution | Outside agent execution |
| **How It Works** | Agent self-diagnoses and retries | Detects incomplete and re-invokes |
| **Max Retries** | Unlimited (prompt says so) | Configurable (default: 5) |
| **Retry Logic** | Intelligent (LLM decides) | Rule-based (code decides) |
| **Statistics** | No tracking | Full statistics |
| **Error Handling** | Agent tries multiple approaches | Exponential backoff |
| **Resume Strategy** | Continues in same execution | Resumes from checkpoint |
| **Use Case** | Interactive, complex tasks | Production, monitoring |
| **Works In** | LangGraph Studio | Python code only |

## Combining Both Layers

For **maximum resilience**, use both layers together:

1. **Built-in persistence** handles errors within execution
2. **Programmatic retry** handles entire execution failures

Example scenario:
```
Task: "Scrape data from 10 websites"

Attempt 1:
  - Agent navigates to site 1 → Success
  - Agent navigates to site 2 → Error (timeout)
    ↪ Built-in: Agent retries with higher timeout → Success
  - Agent navigates to site 3 → Error (network)
    ↪ Built-in: Agent retries → Success
  - Agent gets to site 5 → Token limit reached

Attempt 2 (Programmatic Retry):
  - Resumes from checkpoint (already scraped 1-4)
  - Continues with sites 5-10 → Success ✅
```

## Troubleshooting

### Issue: Task never completes even with retries

**Cause**: Task might be too complex or ambiguous

**Solution**:
1. Break down into smaller sub-tasks
2. Add explicit success criteria to the prompt
3. Check if task requires user input (interrupts)

### Issue: Too many retries wasting resources

**Cause**: Non-retryable errors being retried

**Solution**:
1. Check `outcome_history` to identify error patterns
2. Add error patterns to non-retryable list
3. Reduce `max_attempts` for this task type

### Issue: Retries happening too fast/slow

**Cause**: Retry policy doesn't match failure type

**Solution**:
1. For rate limits: Increase `initial_delay`
2. For timeouts: Reduce `max_attempts`, increase delay
3. For transient errors: Reduce `initial_delay`

## Summary

The Grok Fast agent has **two powerful retry mechanisms**:

1. **Built-in Persistence**: Agent's intelligence + unlimited retries within execution
2. **Programmatic Retry**: External logic + configurable retry policy + statistics

Use **built-in** for interactive development.
Use **programmatic** for production deployments.
Use **both together** for maximum resilience!

---

For more examples, see: `example_retry_usage.py`
