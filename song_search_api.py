"""
Simple REST API for song lyrics search using LangGraph deployed on Render

This API acts as a proxy to the LangGraph endpoint, similar to Next.js rewrites.
It sends requests to the LangGraph agent and returns structured JSON responses.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import json
import uuid

app = FastAPI(title="Song Search API", version="2.0.0")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LangGraph Configuration
LANGGRAPH_ENDPOINT = "https://deepagents-langgraph-production.up.railway.app"
AGENT_ID = "mcp_agent_bright_data_glm"  # Changed from mcp_agent_grok_fast
API_KEY = "demo-token"

# Request/Response models
class SongSearchRequest(BaseModel):
    query: str
    trustedDomains: Optional[List[str]] = ["shironet.mako.co.il", "tab4u.com", "nagnu.co.il"]

class SongSearchResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    tokensUsed: Optional[dict] = None
    cost: Optional[float] = None


async def call_langgraph_agent(query: str, trusted_domains: List[str]) -> dict:
    """
    Call LangGraph agent endpoint directly (like Next.js proxy)

    Steps:
    1. Create a new thread
    2. Send message to thread with streaming
    3. Parse SSE stream response
    4. Extract and return results
    """
    # Use 3-minute timeout for LangGraph agent operations
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Step 1: Create thread
        thread_response = await client.post(
            f"{LANGGRAPH_ENDPOINT}/threads",
            headers={
                "x-api-key": API_KEY,
                "x-auth-scheme": "langsmith",
                "content-type": "application/json",
            },
            json={}
        )

        if thread_response.status_code != 200:
            raise HTTPException(
                status_code=thread_response.status_code,
                detail=f"Failed to create thread: {thread_response.text}"
            )

        thread_data = thread_response.json()
        thread_id = thread_data.get("thread_id")

        if not thread_id:
            raise HTTPException(status_code=500, detail="No thread_id in response")

        # Step 2: Send message with streaming
        prompt = f"""Find the complete lyrics for this song: "{query}"

Return the result in this EXACT JSON format:

{{
  "songs": [
    {{
      "title": "exact song title",
      "artist": "artist name",
      "language": "עברית or ערבית or ארמית",
      "lyrics": "complete lyrics with line breaks preserved"
    }}
  ]
}}

IMPORTANT: Return ONLY valid JSON with the complete lyrics."""

        message_id = str(uuid.uuid4())

        stream_response = await client.post(
            f"{LANGGRAPH_ENDPOINT}/threads/{thread_id}/runs/stream",
            headers={
                "x-api-key": API_KEY,
                "x-auth-scheme": "langsmith",
                "content-type": "application/json",
            },
            json={
                "input": {
                    "messages": [{
                        "id": message_id,
                        "type": "human",
                        "content": prompt
                    }]
                },
                "config": {
                    "recursion_limit": 100
                },
                "stream_mode": ["messages-tuple", "values", "updates"],
                "stream_resumable": True,
                "assistant_id": AGENT_ID,
                "on_disconnect": "continue"
            }
        )

        if stream_response.status_code != 200:
            raise HTTPException(
                status_code=stream_response.status_code,
                detail=f"Failed to stream: {stream_response.text}"
            )

        # Step 3: Parse SSE stream
        full_response = ""
        print(f"[DEBUG] Starting SSE stream parsing for query: {query}", flush=True)
        print(f"[DEBUG] Stream response status: {stream_response.status_code}", flush=True)
        print(f"[DEBUG] Stream headers: {dict(stream_response.headers)}", flush=True)

        event_type = None
        event_count = 0
        values_events_seen = 0
        lines_received = 0

        async for line in stream_response.aiter_lines():
            lines_received += 1
            if not line or line.strip() == "":
                continue

            # Parse event type
            if line.startswith("event: "):
                event_type = line[7:].strip()  # Remove "event: " prefix
                continue

            # Parse data
            if line.startswith("data: "):
                try:
                    data_str = line[6:]  # Remove "data: " prefix

                    # Check for end event
                    if data_str.strip() == "[DONE]":
                        print(f"[DEBUG] Received [DONE] event, stream complete", flush=True)
                        break

                    data = json.loads(data_str)
                    event_count += 1

                    # Look for "values" events with messages containing final AI response
                    if event_type == "values":
                        values_events_seen += 1

                        if isinstance(data, dict) and "messages" in data:
                            messages = data["messages"]

                            if isinstance(messages, list):
                                for msg in messages:
                                    if isinstance(msg, dict) and msg.get("type") == "ai" and "content" in msg:
                                        content = msg["content"]

                                        if isinstance(content, str) and content:
                                            full_response = content
                                            print(f"[DEBUG] Found AI response: {len(content)} chars", flush=True)

                    # Reset event type after processing
                    event_type = None

                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON decode error: {e}, line: {line[:100]}", flush=True)
                    continue

        print(f"[DEBUG] Stream complete. Lines received: {lines_received}, Events: {event_count}, VALUES events: {values_events_seen}, Response length: {len(full_response)} chars", flush=True)
        return {"response": full_response, "thread_id": thread_id}


@app.post("/search-song", response_model=SongSearchResponse)
async def search_song(request: SongSearchRequest):
    """
    Search for a song and extract lyrics using LangGraph agent on Render

    This endpoint acts as a proxy to the LangGraph deployment,
    similar to how Next.js rewrites work.
    """
    try:
        # Call LangGraph agent
        result = await call_langgraph_agent(request.query, request.trustedDomains)
        response_text = result.get("response", "")

        if not response_text:
            return SongSearchResponse(
                success=False,
                error="No response from agent"
            )

        # Try to extract JSON from response
        import re

        # Find JSON in the response
        json_match = re.search(r'\{[\s\S]*"songs"[\s\S]*\}', response_text)
        if json_match:
            song_data = json.loads(json_match.group())

            # Calculate approximate cost
            estimated_tokens = len(request.query) / 4 + len(response_text) / 4
            estimated_cost = (estimated_tokens / 1_000_000) * 0.35

            return SongSearchResponse(
                success=True,
                data=song_data,
                tokensUsed={
                    "input": int(len(request.query) / 4),
                    "output": int(len(response_text) / 4),
                },
                cost=estimated_cost
            )
        else:
            # No JSON found, return error with response
            return SongSearchResponse(
                success=False,
                error=f"Could not extract song data. Agent response: {response_text[:500]}"
            )

    except Exception as e:
        return SongSearchResponse(
            success=False,
            error=f"Error searching for song: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "song-search-api"}


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "service": "Song Search API",
        "version": "2.0.0",
        "description": "Proxy to LangGraph agent on Render",
        "endpoints": {
            "/search-song": "POST - Search for a song and extract lyrics",
            "/health": "GET - Health check",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
