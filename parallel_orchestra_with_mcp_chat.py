"""
Parallel Orchestra with MCP - Chat Interface Version
====================================================

גרסה עם תמיכה ב-Chat interface של LangGraph Studio
"""

from typing import Annotated, Literal
from typing_extensions import TypedDict
import operator
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import Send
from langchain_xai import ChatXAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


# ============================================================================
# State Definition with Messages Support
# ============================================================================

class OrchestraChatState(TypedDict):
    """State עם תמיכה ב-messages לצ'אט"""

    # Messages for chat interface
    messages: Annotated[list[BaseMessage], operator.add]

    # המשימה המקורית
    original_query: str

    # רשימת נושאים לחקור
    topics: list[dict]

    # תוצאות מ-Perplexity agents (חיפוש)
    search_results: Annotated[list[dict], operator.add]

    # תוצאות מ-Chrome agents (בדיקת דפים)
    web_results: Annotated[list[dict], operator.add]

    # שגיאות
    errors: Annotated[list[str], operator.add]

    # דוח סופי
    final_report: str


# ============================================================================
# Global MCP Clients
# ============================================================================

_perplexity_client = None
_chrome_client = None
_perplexity_tools = None
_chrome_tools = None


async def get_perplexity_tools():
    """קבלת Perplexity MCP tools"""
    global _perplexity_client, _perplexity_tools

    if _perplexity_tools is None:
        _perplexity_client = MultiServerMCPClient({
            "perplexity": {
                "url": "https://server.smithery.ai/@arjunkmrm/perplexity-search/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            }
        })
        _perplexity_tools = await _perplexity_client.get_tools()

    return _perplexity_tools


async def get_chrome_tools():
    """קבלת Chrome DevTools MCP tools"""
    global _chrome_client, _chrome_tools

    if _chrome_tools is None:
        _chrome_client = MultiServerMCPClient({
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http"
            }
        })
        _chrome_tools = await _chrome_client.get_tools()

    return _chrome_tools


# ============================================================================
# Node 0: Extract Query from Messages
# ============================================================================

async def extract_query_from_messages(state: OrchestraChatState) -> dict:
    """מחלץ את השאילתה מההודעות"""
    messages = state.get("messages", [])

    print(f"\n[DEBUG] Total messages received: {len(messages)}")
    print(f"[DEBUG] Messages: {messages}")

    # מצא את ההודעה האחרונה של המשתמש
    user_message = None
    for i, msg in enumerate(reversed(messages)):
        print(f"[DEBUG] Message {i}: type={type(msg)}")

        # Handle both BaseMessage objects and dictionaries
        if isinstance(msg, HumanMessage):
            user_message = msg.content
            print(f"[DEBUG] Found HumanMessage with content: '{user_message}'")
            break
        elif isinstance(msg, dict):
            print(f"[DEBUG] Message is dict: {msg}")
            # Handle dictionary format from LangGraph Studio
            if msg.get("role") == "user" or msg.get("type") == "human":
                user_message = msg.get("content", "")
                print(f"[DEBUG] Found user message (dict) with content: '{user_message}'")
                break
        elif hasattr(msg, 'content'):
            # Fallback: check if it has content attribute
            print(f"[DEBUG] Message has content attribute: '{msg.content}'")
            user_message = msg.content
            break

    # If no message provided, use empty string (will be caught in decompose)
    if not user_message:
        user_message = ""

    print(f"\n[CHAT MODE] User Query: '{user_message}'")

    return {
        "original_query": user_message,
        "topics": [],
        "search_results": [],
        "web_results": [],
        "errors": [],
        "final_report": ""
    }


# ============================================================================
# Node 1: Decompose Task with LLM
# ============================================================================

async def intelligent_decompose(state: OrchestraChatState) -> dict:
    """פירוק משימה חכם"""
    query = state["original_query"]

    print(f"\nDECOMPOSING TASK: '{query}'")

    # Check if query is empty
    if not query or query.strip() == "":
        print("   ERROR: No query provided!")
        return {
            "topics": [],
            "errors": ["Please provide a research query in the chat input."]
        }

    # לצורך הדוגמה: פירוק פשוט לכמה topics
    # בפועל, כאן אפשר להשתמש ב-LLM לפירוק חכם יותר
    topics = [
        {"id": 1, "topic": f"{query} - Part 1", "type": "search"},
        {"id": 2, "topic": f"{query} - Part 2", "type": "search"},
        {"id": 3, "topic": f"{query} - Part 3", "type": "web"},
    ]

    print(f"   Decomposed into {len(topics)} subtasks")

    return {"topics": topics}


# ============================================================================
# Node 2: Route to Specialized Agents (Fan-Out)
# ============================================================================

def route_to_specialized_agents(state: OrchestraChatState) -> list[Send]:
    """מפנה כל topic לסוכן המתאים"""
    topics = state["topics"]

    sends = []
    for topic in topics:
        if topic["type"] == "search":
            sends.append(Send("perplexity_research_agent", {"id": topic["id"], "topic": topic["topic"]}))
        elif topic["type"] == "web":
            sends.append(Send("chrome_web_agent", {"id": topic["id"], "topic": topic["topic"]}))

    print(f"\nROUTING: Sending {len(sends)} tasks to agents")
    return sends


# ============================================================================
# Node 3: Perplexity Research Agent
# ============================================================================

async def perplexity_research_agent(state: dict) -> dict:
    """סוכן מחקר עם Perplexity"""
    topic_id = state["id"]
    topic = state["topic"]

    print(f"  Perplexity Agent {topic_id}: Researching '{topic}'")

    try:
        perplexity_tools = await get_perplexity_tools()
        search_tool = next((t for t in perplexity_tools if "search" in t.name.lower()), None)

        if search_tool:
            result = await search_tool.ainvoke({"query": topic})
            return {
                "search_results": [{
                    "topic_id": topic_id,
                    "topic": topic,
                    "result": str(result)[:500],
                    "source": "perplexity",
                    "success": True
                }]
            }
        else:
            return {
                "search_results": [{
                    "topic_id": topic_id,
                    "topic": topic,
                    "result": f"[Simulated Perplexity research for: {topic}]",
                    "source": "perplexity",
                    "success": True
                }]
            }

    except Exception as e:
        print(f"  ERROR - Perplexity Agent {topic_id}: {str(e)}")
        return {
            "errors": [f"Perplexity agent {topic_id} failed: {str(e)}"]
        }


# ============================================================================
# Node 4: Chrome Web Agent
# ============================================================================

async def chrome_web_agent(state: dict) -> dict:
    """סוכן Chrome"""
    topic_id = state["id"]
    topic = state["topic"]

    print(f"  Chrome Agent {topic_id}: Checking web for '{topic}'")

    try:
        chrome_tools = await get_chrome_tools()
        navigate_tool = next((t for t in chrome_tools if "navigate" in t.name.lower()), None)

        if navigate_tool:
            url = f"https://www.google.com/search?q={topic.replace(' ', '+')}"
            result = await navigate_tool.ainvoke({"url": url, "timeout": 30000})

            return {
                "web_results": [{
                    "topic_id": topic_id,
                    "topic": topic,
                    "result": str(result)[:500],
                    "source": "chrome",
                    "success": True
                }]
            }
        else:
            return {
                "web_results": [{
                    "topic_id": topic_id,
                    "topic": topic,
                    "result": f"[Simulated Chrome check for: {topic}]",
                    "source": "chrome",
                    "success": True
                }]
            }

    except Exception as e:
        print(f"  ERROR - Chrome Agent {topic_id}: {str(e)}")
        return {
            "errors": [f"Chrome agent {topic_id} failed: {str(e)}"]
        }


# ============================================================================
# Node 5: Aggregate and Send Final Message
# ============================================================================

async def aggregate_and_respond(state: OrchestraChatState) -> dict:
    """מאחד תוצאות ושולח תשובה"""
    search_results = state.get("search_results", [])
    web_results = state.get("web_results", [])
    errors = state.get("errors", [])

    print(f"\nAGGREGATING RESULTS:")
    print(f"   - Search results: {len(search_results)}")
    print(f"   - Web results: {len(web_results)}")
    print(f"   - Errors: {len(errors)}")

    # יצירת דוח מאוחד
    report_lines = [
        "=" * 70,
        "ORCHESTRA RESEARCH REPORT",
        "=" * 70,
        f"Total search results: {len(search_results)}",
        f"Total web results: {len(web_results)}",
        f"Errors: {len(errors)}",
        "",
        "SEARCH RESULTS (Perplexity):",
        "-" * 70,
    ]

    for result in search_results:
        report_lines.append(f"  [{result['topic_id']}] {result['topic']}")
        report_lines.append(f"      Result: {result['result'][:200]}...")
        report_lines.append("")

    report_lines.append("")
    report_lines.append("WEB RESULTS (Chrome):")
    report_lines.append("-" * 70)

    for result in web_results:
        report_lines.append(f"  [{result['topic_id']}] {result['topic']}")
        report_lines.append(f"      Result: {result['result'][:200]}...")
        report_lines.append("")

    if errors:
        report_lines.append("")
        report_lines.append("ERRORS:")
        report_lines.append("-" * 70)
        for error in errors:
            report_lines.append(f"  - {error}")

    report_lines.append("")
    report_lines.append("=" * 70)

    final_report = "\n".join(report_lines)

    print(f"\nFinal report generated ({len(final_report)} chars)")

    # שליחת תשובה כ-AIMessage
    return {
        "final_report": final_report,
        "messages": [AIMessage(content=final_report)]
    }


# ============================================================================
# Graph Construction
# ============================================================================

def create_parallel_orchestra_chat():
    """בונה את ה-graph עם תמיכה בצ'אט"""

    builder = StateGraph(OrchestraChatState)

    # Nodes
    builder.add_node("extract_query", extract_query_from_messages)
    builder.add_node("intelligent_decompose", intelligent_decompose)
    builder.add_node("perplexity_research_agent", perplexity_research_agent)
    builder.add_node("chrome_web_agent", chrome_web_agent)
    builder.add_node("aggregate_and_respond", aggregate_and_respond)

    # Edges
    builder.add_edge(START, "extract_query")
    builder.add_edge("extract_query", "intelligent_decompose")

    # Fan-out
    builder.add_conditional_edges(
        "intelligent_decompose",
        route_to_specialized_agents,
        ["perplexity_research_agent", "chrome_web_agent"]
    )

    # Fan-in
    builder.add_edge("perplexity_research_agent", "aggregate_and_respond")
    builder.add_edge("chrome_web_agent", "aggregate_and_respond")

    builder.add_edge("aggregate_and_respond", END)

    return builder.compile()


# ============================================================================
# Entry Point for LangGraph Studio
# ============================================================================

async def agent():
    """
    נקודת כניסה ל-LangGraph Studio עם תמיכה בצ'אט

    הוסף ל-langgraph.json:
    {
      "graphs": {
        "parallel_orchestra_chat": "./parallel_orchestra_with_mcp_chat.py:agent"
      }
    }
    """
    return create_parallel_orchestra_chat()


# ============================================================================
# Main Demo
# ============================================================================

async def main():
    """הדגמה"""

    print("\n" + "=" * 70)
    print("PARALLEL ORCHESTRA WITH MCP - CHAT MODE")
    print("=" * 70)

    graph = create_parallel_orchestra_chat()

    result = await graph.ainvoke({
        "messages": [HumanMessage(content="Research the top 5 AI tools of 2024")],
        "original_query": "",
        "topics": [],
        "search_results": [],
        "web_results": [],
        "errors": [],
        "final_report": ""
    })

    print("\n" + result["final_report"])


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
