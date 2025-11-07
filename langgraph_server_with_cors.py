"""
LangGraph Server with CORS Support
===================================

Custom server that runs LangGraph with CORS enabled for browser access.
This wrapper adds CORS middleware to the LangGraph API.
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import httpx
import asyncio
from typing import Any, Dict
import os

# Create FastAPI app with CORS
app = FastAPI(title="LangGraph API with CORS", version="1.0.0")

# Add CORS middleware - allows access from anywhere
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all headers to the browser
)

# LangGraph backend server URL
LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://localhost:8123")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy(path: str, request: Request):
    """
    Proxy all requests to the LangGraph server with CORS headers.
    This acts as a middleware between the browser and LangGraph.
    """

    # Build the target URL
    target_url = f"{LANGGRAPH_URL}/{path}"

    # Get query parameters
    query_params = dict(request.query_params)

    # Get request body if exists
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
        except:
            body = None

    # Get headers (filter out host header)
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in ["host", "content-length"]
    }

    # Make request to LangGraph server
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                params=query_params,
                headers=headers,
                content=body
            )

            # Return response with proper headers
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/json")
            )

        except httpx.TimeoutException:
            return JSONResponse(
                status_code=504,
                content={"error": "Gateway timeout - LangGraph server took too long to respond"}
            )
        except httpx.ConnectError:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Cannot connect to LangGraph server",
                    "details": f"Make sure LangGraph is running on {LANGGRAPH_URL}",
                    "hint": "Run 'langgraph up' in a separate terminal first"
                }
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Proxy error: {str(e)}"}
            )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check if LangGraph is running
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{LANGGRAPH_URL}/health")
            langgraph_status = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            langgraph_status = "disconnected"

    return {
        "status": "ok",
        "message": "CORS proxy is running",
        "langgraph_backend": langgraph_status,
        "langgraph_url": LANGGRAPH_URL
    }


@app.get("/")
async def root():
    """Root endpoint with information"""
    return {
        "title": "LangGraph API with CORS Support",
        "description": "This proxy server adds CORS headers to LangGraph API",
        "cors_enabled": True,
        "allowed_origins": "*",
        "backend_url": LANGGRAPH_URL,
        "endpoints": {
            "/health": "Health check",
            "/threads": "LangGraph threads API",
            "/runs": "LangGraph runs API",
            "/assistants": "LangGraph assistants API"
        },
        "note": "All LangGraph endpoints are available through this proxy with CORS enabled"
    }


if __name__ == "__main__":
    print("=" * 70)
    print("Starting LangGraph Server with CORS Support")
    print("=" * 70)
    print("\nConfiguration:")
    print(f"  - Proxy Port: 2024")
    print(f"  - LangGraph Backend: {LANGGRAPH_URL}")
    print(f"  - CORS: Enabled for all origins")
    print("\nEndpoints:")
    print(f"  - API with CORS: http://localhost:2024")
    print(f"  - Health Check: http://localhost:2024/health")
    print("\nImportant:")
    print(f"  1. Make sure LangGraph is running on {LANGGRAPH_URL}")
    print(f"     Run: langgraph up")
    print(f"  2. Then run this proxy server")
    print(f"     Run: python langgraph_server_with_cors.py")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 70)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=2024,
        log_level="info"
    )