"""
Quick Test for Parallel Agents
===============================

בדיקה מהירה של תזמור סוכנים במקביל
הרץ: python test_parallel_quick.py
"""

import asyncio
from typing import Annotated
from typing_extensions import TypedDict
import operator
import time
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send


# ============================================================================
# State
# ============================================================================

class QuickTestState(TypedDict):
    """State פשוט לבדיקה"""
    num_agents: int
    results: Annotated[list[dict], operator.add]


# ============================================================================
# Nodes
# ============================================================================

def create_tasks(state: QuickTestState) -> dict:
    """יוצר את מספר המשימות"""
    num = state["num_agents"]
    print(f"\n[*] Creating {num} parallel tasks...")
    return {}


def route_to_workers(state: QuickTestState) -> list[Send]:
    """יוצר Send objects לכל worker"""
    num = state["num_agents"]
    print(f"[>] Routing to {num} parallel workers...\n")

    return [
        Send("worker", {"worker_id": i})
        for i in range(num)
    ]


async def worker(state: dict) -> dict:
    """Worker שעובד על משימה אחת"""
    worker_id = state["worker_id"]

    start_time = time.time()
    print(f"  [W{worker_id:2d}] Worker {worker_id:2d} started")

    # סימולציה של עבודה (2 שניות)
    await asyncio.sleep(2)

    elapsed = time.time() - start_time
    print(f"  [OK] Worker {worker_id:2d} finished in {elapsed:.2f}s")

    return {
        "results": [{
            "worker_id": worker_id,
            "duration": elapsed,
            "status": "success"
        }]
    }


def summarize(state: QuickTestState) -> dict:
    """מסכם את התוצאות"""
    results = state.get("results", [])

    print(f"\n[SUMMARY]")
    print(f"   Total workers: {len(results)}")
    print(f"   All succeeded: {all(r['status'] == 'success' for r in results)}")

    if results:
        avg_duration = sum(r["duration"] for r in results) / len(results)
        max_duration = max(r["duration"] for r in results)
        print(f"   Average duration: {avg_duration:.2f}s")
        print(f"   Max duration: {max_duration:.2f}s")
        print(f"\n   [!] If running in parallel, total time = {max_duration:.2f}s")
        print(f"   [!] If running sequentially, would take = {avg_duration * len(results):.2f}s")

    return {}


# ============================================================================
# Graph
# ============================================================================

def create_test_graph():
    """יוצר את הגרף"""

    builder = StateGraph(QuickTestState)

    builder.add_node("create_tasks", create_tasks)
    builder.add_node("worker", worker)
    builder.add_node("summarize", summarize)

    builder.add_edge(START, "create_tasks")
    builder.add_conditional_edges(
        "create_tasks",
        route_to_workers,
        ["worker"]
    )
    builder.add_edge("worker", "summarize")
    builder.add_edge("summarize", END)

    return builder.compile()


# ============================================================================
# Main
# ============================================================================

async def main():
    """הרצת הבדיקה"""

    print("=" * 70)
    print("PARALLEL AGENTS QUICK TEST")
    print("=" * 70)

    # בדיקה עם 10 סוכנים
    graph = create_test_graph()

    print("\nTest: Running 10 workers in parallel")
    print("   Each worker takes 2 seconds")
    print("   Expected total time: ~2 seconds (not 20!)")
    print("-" * 70)

    start = time.time()

    result = await graph.ainvoke({
        "num_agents": 10,
        "results": []
    })

    total_time = time.time() - start

    print("\n" + "=" * 70)
    print(f"[DONE] TEST COMPLETED in {total_time:.2f} seconds")

    if total_time < 5:
        print("[SUCCESS] Agents ran in parallel!")
    else:
        print("[WARNING] Agents might have run sequentially")

    print("=" * 70)

    return result


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# Expected Output:
# ============================================================================
"""
======================================================================
🧪 PARALLEL AGENTS QUICK TEST
======================================================================

📝 Test: Running 10 workers in parallel
   Each worker takes 2 seconds
   Expected total time: ~2 seconds (not 20!)
----------------------------------------------------------------------

🎯 Creating 10 parallel tasks...
🚀 Routing to 10 parallel workers...

  ⚙️  Worker  0 started
  ⚙️  Worker  1 started
  ⚙️  Worker  2 started
  ⚙️  Worker  3 started
  ⚙️  Worker  4 started
  ⚙️  Worker  5 started
  ⚙️  Worker  6 started
  ⚙️  Worker  7 started
  ⚙️  Worker  8 started
  ⚙️  Worker  9 started
  ✅ Worker  0 finished in 2.00s
  ✅ Worker  1 finished in 2.00s
  ✅ Worker  2 finished in 2.00s
  ✅ Worker  3 finished in 2.00s
  ✅ Worker  4 finished in 2.00s
  ✅ Worker  5 finished in 2.00s
  ✅ Worker  6 finished in 2.00s
  ✅ Worker  7 finished in 2.00s
  ✅ Worker  8 finished in 2.00s
  ✅ Worker  9 finished in 2.00s

📊 SUMMARY:
   Total workers: 10
   All succeeded: True
   Average duration: 2.00s
   Max duration: 2.00s

   🎉 If running in parallel, total time ≈ 2.00s
   💡 If running sequentially, would take ≈ 20.00s

======================================================================
✅ TEST COMPLETED in 2.05 seconds
✅ SUCCESS: Agents ran in parallel! ✅
======================================================================
"""
