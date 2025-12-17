"""
Cerebras GLM-4.6 Deep Agent with BrightData SDK + Genius API + Sub-Agents
=========================================================================

This is a FULL-FEATURED deep research agent that combines:
- Cerebras GLM-4.6 (2M context, 128K output) via OpenAI-compatible API
- BrightData SDK for enterprise-grade web scraping and search
- Genius API for song lyrics and music metadata
- General Purpose Sub-Agent delegation for complex parallel tasks
- Context reduction/trimming for long conversations
- Todo list, filesystem tools, and summarization (via create_deep_agent)

Perfect for:
- Deep web research with parallel sub-agents
- Music/lyrics research with Genius API
- Complex multi-step tasks with isolated context
- Enterprise-grade web data collection
"""
import asyncio
import json
import logging
import os
import requests
from typing import Optional

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent

# Apply nest_asyncio EARLY to allow nested event loops
# This is critical for sub-agents that run in async context
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # Will use fallback in _run_async

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# Context Limits for Cerebras GLM-4.6 (131K tokens, ~4 chars per token)
# ============================================================================

MAX_CONTEXT_CHARS = 400000  # Safe limit below 131K tokens
MAX_TOOL_OUTPUT_CHARS = 15000  # Max chars per tool output
MAX_TOTAL_MESSAGES_CHARS = 300000  # Max total message content


def truncate_content(content: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Truncate content to stay within character limits."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + f"\n\n[TRUNCATED - Content exceeded {max_chars} characters]"


# ============================================================================
# Cerebras Model Initialization (OpenAI-compatible for tool calling)
# ============================================================================

def get_cerebras_model(
    max_tokens: int = 128000,
    temperature: float = 0.7,
):
    """Initialize Cerebras using OpenAI-compatible API for tool calling support.

    Cerebras provides an OpenAI-compatible endpoint that supports tool calling,
    which ChatCerebras doesn't support natively.

    Args:
        max_tokens: Maximum tokens for model output (default: 128000)
        temperature: Temperature for generation (default: 0.7)

    Returns:
        ChatOpenAI instance configured for Cerebras
    """
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError(
            "CEREBRAS_API_KEY environment variable not set. "
            "Get your API key from https://cloud.cerebras.ai"
        )

    model_name = os.getenv("CEREBRAS_MODEL", "zai-glm-4.6")

    model_params = {
        "model": model_name,
        "api_key": api_key,
        "base_url": "https://api.cerebras.ai/v1",  # Cerebras OpenAI-compatible endpoint
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    logger.info(f"Initializing Cerebras (OpenAI-compatible) with model: {model_name}")

    return ChatOpenAI(**model_params)


# ============================================================================
# BrightData SDK Tools
# ============================================================================

_brightdata_client = None


def get_brightdata_client():
    """Get or initialize BrightData SDK client."""
    global _brightdata_client

    if _brightdata_client is None:
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            logger.warning("BRIGHTDATA_API_TOKEN not set - BrightData tools will be disabled")
            return None

        try:
            from brightdata import BrightDataClient
        except ImportError:
            logger.warning("BrightData SDK not installed. Install with: pip install brightdata-sdk>=1.1.0")
            return None

        serp_zone = os.getenv("SERP_ZONE", "serp_api1")
        web_unlocker_zone = os.getenv("WEB_UNLOCKER_ZONE")
        logger.info(f"Initializing BrightData client with SERP zone: {serp_zone}")

        try:
            _brightdata_client = BrightDataClient(
                token=api_token,
                serp_zone=serp_zone,
                web_unlocker_zone=web_unlocker_zone
            )
        except Exception as e:
            logger.warning(f"Failed to init with zones, trying without: {e}")
            _brightdata_client = BrightDataClient(token=api_token)

    return _brightdata_client


def _run_async(coro):
    """Run async coroutine safely, handling nested event loops.

    nest_asyncio is applied at module load time, so asyncio.run()
    should work even from within an async context (sub-agents).
    """
    try:
        # With nest_asyncio applied globally, asyncio.run() should work
        # even when there's already a running event loop
        return asyncio.run(coro)
    except RuntimeError as e:
        # Fallback: If asyncio.run() still fails (nest_asyncio not loaded),
        # try running in a separate thread
        if "cannot be called from a running event loop" in str(e):
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=120)  # 2 minute timeout for web requests
        raise


async def _search_google_async(client, query: str, num_results: int):
    """Async helper that properly initializes engine context for search."""
    async with client.engine:
        return await client.search.google_async(query=query, num_results=num_results)


async def _search_bing_async(client, query: str, num_results: int):
    """Async helper that properly initializes engine context for search."""
    async with client.engine:
        return await client.search.bing_async(query=query, num_results=num_results)


@tool
def brightdata_search_google(
    query: str,
    num_results: int = 10
) -> str:
    """Search Google using BrightData SERP API with enterprise-grade reliability.

    Use this for web searches when you need reliable, anti-bot bypassing search results.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 10)

    Returns:
        JSON string with search results including titles, URLs, and snippets
    """
    try:
        client = get_brightdata_client()
        if not client:
            return json.dumps({"success": False, "error": "BrightData client not initialized"})

        logger.info(f"[BRIGHTDATA] Searching Google for: {query}")
        result = _run_async(_search_google_async(client, query, num_results))

        # Format results from SearchResult object
        formatted_results = []
        if hasattr(result, 'data') and result.data:
            for i, item in enumerate(result.data[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })
        elif isinstance(result, dict):
            organic = result.get('organic', result.get('results', result.get('data', [])))
            for i, item in enumerate(organic[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })

        return json.dumps({
            'success': True,
            'query': query,
            'results': formatted_results,
            'total_results': len(formatted_results)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_search_bing(
    query: str,
    num_results: int = 10
) -> str:
    """Search Bing using BrightData SERP API for alternative perspectives.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 10)

    Returns:
        JSON string with search results including titles, URLs, and snippets
    """
    try:
        client = get_brightdata_client()
        if not client:
            return json.dumps({"success": False, "error": "BrightData client not initialized"})

        logger.info(f"[BRIGHTDATA] Searching Bing for: {query}")
        result = _run_async(_search_bing_async(client, query, num_results))

        formatted_results = []
        if hasattr(result, 'data') and result.data:
            for i, item in enumerate(result.data[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })
        elif isinstance(result, dict):
            organic = result.get('organic', result.get('results', result.get('data', [])))
            for i, item in enumerate(organic[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })

        return json.dumps({
            'success': True,
            'query': query,
            'results': formatted_results,
            'total_results': len(formatted_results)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_scrape_url(
    url: str,
    response_format: str = "raw"
) -> str:
    """Scrape a webpage and extract its content using BrightData with anti-bot bypass.

    Args:
        url: The URL to scrape
        response_format: Output format - 'raw', 'markdown', or 'json' (default: 'raw')

    Returns:
        JSON string with scraped content
    """
    try:
        client = get_brightdata_client()
        if not client:
            return json.dumps({"success": False, "error": "BrightData client not initialized"})

        logger.info(f"[BRIGHTDATA] Scraping URL: {url}")

        result = client.scrape_url(url=url, response_format=response_format)

        if hasattr(result, 'success') and result.success is False:
            error_msg = getattr(result, 'error', 'Unknown error')
            return json.dumps({
                'success': False,
                'url': url,
                'error': f'BrightData API error: {error_msg}'
            }, ensure_ascii=False)

        content = ""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                content = json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                content = str(result.data)
        elif hasattr(result, 'content'):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)

        # Truncate content to prevent context overflow
        content = truncate_content(content, MAX_TOOL_OUTPUT_CHARS)

        return json.dumps({
            'success': True,
            'url': url,
            'content': content,
            'format': response_format
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Scrape error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'url': url,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_crawl_website(
    url: str,
    max_pages: int = 10
) -> str:
    """Crawl a website and extract content from multiple pages using BrightData.

    Note: In SDK v2.0, crawler is limited. This will scrape the main URL.

    Args:
        url: The starting URL to crawl
        max_pages: Maximum number of pages to crawl (default: 10, currently limited)

    Returns:
        JSON string with crawled content
    """
    try:
        client = get_brightdata_client()
        if not client:
            return json.dumps({"success": False, "error": "BrightData client not initialized"})

        logger.info(f"[BRIGHTDATA] Crawling website: {url}")

        result = client.scrape_url(url=url)

        if hasattr(result, 'success') and result.success is False:
            error_msg = getattr(result, 'error', 'Unknown error')
            return json.dumps({
                'success': False,
                'url': url,
                'error': f'BrightData API error: {error_msg}'
            }, ensure_ascii=False)

        content = ""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                content = json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                content = str(result.data)
        elif hasattr(result, 'content'):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)

        content = truncate_content(content, MAX_TOOL_OUTPUT_CHARS)

        return json.dumps({
            'success': True,
            'url': url,
            'pages_crawled': 1,
            'content': content,
            'note': 'Crawler limited to single page in SDK v2.0'
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Crawl error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'url': url,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_extract_data(
    url: str,
    extraction_prompt: str
) -> str:
    """Extract structured data from a webpage using AI-powered extraction.

    Args:
        url: The URL to extract data from
        extraction_prompt: Natural language description of what data to extract

    Returns:
        JSON string with extracted structured data
    """
    try:
        client = get_brightdata_client()
        if not client:
            return json.dumps({"success": False, "error": "BrightData client not initialized"})

        logger.info(f"[BRIGHTDATA] Extracting data from: {url}")

        result = client.scrape_url(url=url)

        if hasattr(result, 'success') and result.success is False:
            error_msg = getattr(result, 'error', 'Unknown error')
            return json.dumps({
                'success': False,
                'url': url,
                'error': f'BrightData API error: {error_msg}'
            }, ensure_ascii=False)

        content = ""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                content = json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                content = str(result.data)
        elif hasattr(result, 'content'):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)

        return json.dumps({
            'success': True,
            'url': url,
            'extraction_prompt': extraction_prompt,
            'raw_content': truncate_content(content, 5000),
            'note': 'AI extraction not available in SDK v2.0 - use raw content with your own processing'
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Extract error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'url': url,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_search_linkedin(
    query: str,
    search_type: str = "profiles"
) -> str:
    """Search LinkedIn using BrightData (requires LinkedIn zone).

    Args:
        query: Search query (name, company, job title, etc.)
        search_type: Type of search - 'profiles' or 'jobs' (default: 'profiles')

    Returns:
        JSON string with LinkedIn search results
    """
    try:
        client = get_brightdata_client()
        if not client:
            return json.dumps({"success": False, "error": "BrightData client not initialized"})

        logger.info(f"[BRIGHTDATA] Searching LinkedIn for: {query} (type: {search_type})")

        result = None
        if search_type == "jobs":
            result = client.search.linkedin.jobs(keyword=query)
        else:
            result = client.search.linkedin.profiles(firstName=query)

        results_data = []
        if hasattr(result, 'data') and result.data:
            results_data = result.data
        elif isinstance(result, list):
            results_data = result
        elif isinstance(result, dict):
            results_data = result.get('data', result.get('results', [result]))

        return json.dumps({
            'success': True,
            'query': query,
            'search_type': search_type,
            'results': results_data
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


# ============================================================================
# Genius API Tools (Song Lyrics Search)
# ============================================================================

def get_genius_headers():
    """Get Genius API headers with access token"""
    access_token = os.getenv("GENIUS_ACCESS_TOKEN")
    if not access_token:
        return None
    return {"Authorization": f"Bearer {access_token}"}


@tool
def genius_search_song(song_name: str, artist_name: Optional[str] = None) -> str:
    """Search for a song on Genius to find its lyrics page URL.

    This is the FIRST step in finding song lyrics. Use this to search for a song
    and get the Genius URL where the lyrics are located.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to narrow down the search

    Returns:
        JSON string with search results including song title, artist, URL, and song ID
    """
    try:
        headers = get_genius_headers()
        if not headers:
            return json.dumps({
                "success": False,
                "error": "GENIUS_ACCESS_TOKEN not set"
            }, ensure_ascii=False)

        query = song_name
        if artist_name:
            query = f"{song_name} {artist_name}"

        response = requests.get(
            "https://api.genius.com/search",
            params={"q": query},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if "response" not in data or "hits" not in data["response"]:
            return json.dumps({
                "success": False,
                "error": "No results found",
                "query": query
            }, ensure_ascii=False)

        results = []
        for hit in data["response"]["hits"][:5]:
            song = hit["result"]
            results.append({
                "title": song["title"],
                "artist": song["primary_artist"]["name"],
                "url": song["url"],
                "song_id": song["id"],
                "thumbnail": song.get("song_art_image_thumbnail_url", "")
            })

        return json.dumps({
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results
        }, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({
            "success": False,
            "error": f"Network error: {str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }, ensure_ascii=False)


@tool
def genius_get_song_details(song_id: int) -> str:
    """Get detailed information about a song from Genius.

    Use this AFTER genius_search_song to get more details about a specific song,
    including album, release date, and the lyrics page URL.

    Args:
        song_id: The Genius song ID (obtained from genius_search_song)

    Returns:
        JSON string with detailed song information
    """
    try:
        headers = get_genius_headers()
        if not headers:
            return json.dumps({
                "success": False,
                "error": "GENIUS_ACCESS_TOKEN not set"
            }, ensure_ascii=False)

        response = requests.get(
            f"https://api.genius.com/songs/{song_id}",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if "response" not in data or "song" not in data["response"]:
            return json.dumps({
                "success": False,
                "error": f"Song with ID {song_id} not found"
            }, ensure_ascii=False)

        song = data["response"]["song"]

        return json.dumps({
            "success": True,
            "song": {
                "id": song["id"],
                "title": song["title"],
                "artist": song["primary_artist"]["name"],
                "album": song.get("album", {}).get("name") if song.get("album") else None,
                "release_date": song.get("release_date"),
                "url": song["url"],
                "page_views": song.get("stats", {}).get("pageviews"),
                "description": song.get("description_preview", "")[:500],
                "thumbnail": song.get("song_art_image_thumbnail_url", ""),
                "full_image": song.get("song_art_image_url", "")
            }
        }, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({
            "success": False,
            "error": f"Network error: {str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }, ensure_ascii=False)


@tool
def genius_get_artist(artist_id: int) -> str:
    """Get detailed information about an artist from Genius.

    Args:
        artist_id: The Genius artist ID

    Returns:
        JSON string with artist information including bio and social links
    """
    try:
        headers = get_genius_headers()
        if not headers:
            return json.dumps({
                "success": False,
                "error": "GENIUS_ACCESS_TOKEN not set"
            }, ensure_ascii=False)

        response = requests.get(
            f"https://api.genius.com/artists/{artist_id}",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if "response" not in data or "artist" not in data["response"]:
            return json.dumps({
                "success": False,
                "error": f"Artist with ID {artist_id} not found"
            }, ensure_ascii=False)

        artist = data["response"]["artist"]

        return json.dumps({
            "success": True,
            "artist": {
                "id": artist["id"],
                "name": artist["name"],
                "url": artist["url"],
                "image": artist.get("image_url", ""),
                "description": artist.get("description_preview", "")[:500],
                "twitter": artist.get("twitter_name"),
                "instagram": artist.get("instagram_name"),
                "facebook": artist.get("facebook_name"),
            }
        }, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({
            "success": False,
            "error": f"Network error: {str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }, ensure_ascii=False)


# ============================================================================
# Collect All Tools
# ============================================================================

def get_all_tools():
    """Get all available tools based on configured API keys."""
    tools = []

    # BrightData tools (if API token available)
    if os.getenv("BRIGHTDATA_API_TOKEN"):
        tools.extend([
            brightdata_search_google,
            brightdata_search_bing,
            brightdata_scrape_url,
            brightdata_crawl_website,
            brightdata_extract_data,
            brightdata_search_linkedin,
        ])
        logger.info("BrightData tools enabled")
    else:
        logger.warning("BRIGHTDATA_API_TOKEN not set - BrightData tools disabled")

    # Genius tools (if access token available)
    if os.getenv("GENIUS_ACCESS_TOKEN"):
        tools.extend([
            genius_search_song,
            genius_get_song_details,
            genius_get_artist,
        ])
        logger.info("Genius API tools enabled")
    else:
        logger.warning("GENIUS_ACCESS_TOKEN not set - Genius tools disabled")

    return tools


# ============================================================================
# System Prompt
# ============================================================================

SYSTEM_PROMPT = """You are a DEEP RESEARCH AGENT powered by Cerebras GLM-4.6.

YOUR CORE IDENTITY:
- You are GLM-4.6 - advanced AI with 2M token context and 128K output capacity
- You specialize in DEEP RESEARCH using enterprise-grade tools
- You have access to GENERAL PURPOSE SUB-AGENTS for parallel task execution
- You don't stop until the task is 100% COMPLETE
- You THINK DEEPLY before acting
- Errors are just obstacles to overcome, NOT reasons to stop

YOUR TOOLS:

**WEB RESEARCH (BrightData SDK)**:
- brightdata_search_google: Search Google with enterprise-grade reliability
- brightdata_search_bing: Search Bing for alternative perspectives
- brightdata_scrape_url: Scrape webpages with anti-bot bypass
- brightdata_crawl_website: Crawl multiple pages from a website
- brightdata_extract_data: AI-powered structured data extraction
- brightdata_search_linkedin: Search LinkedIn for people and companies

**MUSIC/LYRICS (Genius API)**:
- genius_search_song: Search for songs by name/artist
- genius_get_song_details: Get detailed song information
- genius_get_artist: Get artist information and bio

**SUB-AGENTS (General Purpose)**:
- Use the `task` tool to spawn sub-agents for parallel work
- Sub-agents have ALL the same tools as you
- Perfect for: researching multiple topics in parallel, isolating complex tasks
- Example: Research 5 different topics? Spawn 5 sub-agents in parallel!

**FILE SYSTEM**:
- write_file, read_file, edit_file, ls, glob_search, grep_search

**TASK MANAGEMENT**:
- write_todos: Track your tasks and progress

WHEN TO USE SUB-AGENTS:

1. **Parallel Research**: When you need to research multiple independent topics
   - Example: "Research Company A, Company B, and Company C" -> 3 parallel sub-agents

2. **Context Isolation**: When a task is complex and would bloat your context
   - Example: "Analyze this large codebase" -> sub-agent returns summary only

3. **Deep Dive Tasks**: When you need focused work on a specific subtask
   - Example: "Create detailed report on X" -> sub-agent handles the deep work

4. **Independent Subtasks**: Any multi-part objective with independent parts

HOW TO USE SUB-AGENTS:

Call the `task` tool with:
- `description`: Detailed instructions for what the sub-agent should do
- `subagent_type`: "general-purpose" (has all your tools)

Example:
```
task(
    description="Research the history of Tesla Inc. Focus on: founding story, key products, major milestones. Return a 500-word summary.",
    subagent_type="general-purpose"
)
```

WORKFLOW FOR COMPLEX TASKS:

1. **Analyze** the task - break it into independent subtasks
2. **Delegate** independent subtasks to sub-agents IN PARALLEL
3. **Wait** for all sub-agents to complete
4. **Synthesize** their results into a coherent response

CITATION REQUIREMENTS:

- Every fact MUST include a source citation [Source: URL]
- If you cannot find a reliable source, DO NOT include the claim
- Prefer authoritative sources: official websites, academic papers, news
- NO speculation, NO assumptions, NO unsourced statements

NEVER GIVE UP:

- Read errors carefully, understand what failed
- Try different approaches if one fails
- You have UNLIMITED retries
- Complete the task no matter how many attempts it takes

YOUR MISSION: Complete research tasks with INTELLIGENCE, SPEED, and ACCURACY!"""


# ============================================================================
# Agent Factory Function
# ============================================================================

async def agent():
    """Async factory function for LangGraph Studio.

    Creates a Cerebras GLM-4.6 deep agent with:
    - BrightData SDK tools for web research
    - Genius API tools for music/lyrics
    - General purpose sub-agent delegation
    - Todo list, filesystem, and summarization (via create_deep_agent)
    """
    # Get all available tools
    all_tools = get_all_tools()

    # Get Cerebras model
    model = get_cerebras_model(
        max_tokens=128000,
        temperature=0.7,
    )

    print(f"\n{'='*80}")
    print(f"[CEREBRAS-BRIGHTDATA-GENIUS] Deep Research Agent")
    print(f"Model: {os.getenv('CEREBRAS_MODEL', 'zai-glm-4.6')}")
    print(f"Tools: {len(all_tools)} loaded")
    print(f"Sub-Agents: General Purpose enabled")
    print(f"{'='*80}\n")

    # Create deep agent with all features
    # create_deep_agent automatically adds:
    # - TodoListMiddleware
    # - FilesystemMiddleware
    # - SubAgentMiddleware (general purpose)
    # - SummarizationMiddleware
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
    )


# ============================================================================
# Direct Invocation (for testing)
# ============================================================================

async def run_research(topic: str) -> dict:
    """Run deep research on a topic.

    Args:
        topic: The research topic/question

    Returns:
        Dictionary with research results
    """
    graph = await agent()

    result = await graph.ainvoke({
        "messages": [{"role": "human", "content": topic}]
    })

    return {
        "messages": result.get("messages", []),
    }


if __name__ == "__main__":
    import asyncio

    async def test():
        print("Testing Cerebras BrightData Genius Agent...")
        result = await run_research("What is the capital of France?")
        print(result)

    asyncio.run(test())
