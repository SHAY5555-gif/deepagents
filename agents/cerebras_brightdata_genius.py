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
except ValueError:
    # uvloop (used by Railway/LangGraph) can't be patched - that's OK
    # The async calls will work natively without nest_asyncio
    pass

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


def _run_sync_in_thread(func, *args, **kwargs):
    """Run a sync function in a thread to avoid uvloop conflicts.

    The BrightData SDK internally uses nest_asyncio which doesn't work with uvloop
    (used by Railway/LangGraph). By running in a separate thread, the SDK can
    create its own event loop without uvloop interference.
    """
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=120)  # 2 minute timeout


def _run_search_in_thread(search_type: str, query: str, num_results: int):
    """Run BrightData search in a thread with its own event loop and client.

    Creates a fresh BrightData client and event loop in a separate thread to
    avoid uvloop compatibility issues. This ensures the async search can run
    without interference from the main uvloop.
    """
    import concurrent.futures

    def _run():
        # Create a fresh client in this thread
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            return None

        serp_zone = os.getenv("SERP_ZONE", "serp_api1")

        try:
            from brightdata import BrightDataClient
            client = BrightDataClient(token=api_token, serp_zone=serp_zone)
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Failed to create client in thread: {e}")
            return None

        # Create a new event loop in this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def search():
                async with client.engine:
                    if search_type == "google":
                        return await client.search.google_async(query=query, num_results=num_results)
                    elif search_type == "bing":
                        return await client.search.bing_async(query=query, num_results=num_results)
                    else:
                        raise ValueError(f"Unknown search type: {search_type}")

            return loop.run_until_complete(search())
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


def _run_scrape_in_thread(url: str, response_format: str = "raw"):
    """Run BrightData scrape in a thread with its own event loop and client.

    Creates a fresh BrightData client and event loop in a separate thread to
    avoid uvloop compatibility issues. The SDK's sync methods internally use
    asyncio, so we need our own loop to avoid uvloop conflicts.
    """
    import concurrent.futures

    def _run():
        # Create a fresh client in this thread
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            return None

        web_unlocker_zone = os.getenv("WEB_UNLOCKER_ZONE")

        try:
            from brightdata import BrightDataClient
            client = BrightDataClient(token=api_token, web_unlocker_zone=web_unlocker_zone)
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Failed to create client in thread: {e}")
            return None

        # Create a new event loop in this thread for the SDK's internal async calls
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return client.scrape_url(
                url=url,
                zone=web_unlocker_zone,
                response_format=response_format,
                method="GET"
            )
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


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
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Searching Google for: {query}")
        # Run search in a separate thread to avoid uvloop conflicts
        result = _run_search_in_thread("google", query, num_results)

        if result is None:
            return json.dumps({"success": False, "error": "Failed to execute search"})

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
        logger.error(f"[BRIGHTDATA] Google search error: {type(e).__name__}: {str(e)}")
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
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Searching Bing for: {query}")
        # Run search in a separate thread to avoid uvloop conflicts
        result = _run_search_in_thread("bing", query, num_results)

        if result is None:
            return json.dumps({"success": False, "error": "Failed to execute search"})

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
        logger.error(f"[BRIGHTDATA] Bing search error: {type(e).__name__}: {str(e)}")
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
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Scraping URL: {url}")

        # Run scrape in a separate thread to avoid uvloop conflicts
        result = _run_scrape_in_thread(url, response_format)

        if result is None:
            return json.dumps({"success": False, "url": url, "error": "Failed to execute scrape"})

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
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Crawling website: {url}")

        # Run scrape in a separate thread to avoid uvloop conflicts
        result = _run_scrape_in_thread(url, "raw")

        if result is None:
            return json.dumps({"success": False, "url": url, "error": "Failed to execute crawl"})

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
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Extracting data from: {url}")

        # Run scrape in a separate thread to avoid uvloop conflicts
        result = _run_scrape_in_thread(url, "raw")

        if result is None:
            return json.dumps({"success": False, "url": url, "error": "Failed to execute extraction"})

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


def _run_linkedin_search_in_thread(query: str, search_type: str):
    """Run LinkedIn search in a thread with its own client.

    Creates a fresh BrightData client in a separate thread to avoid uvloop
    compatibility issues.
    """
    import concurrent.futures

    def _run():
        # Create a fresh client in this thread
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            return None

        try:
            from brightdata import BrightDataClient
            client = BrightDataClient(token=api_token)
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Failed to create client in thread: {e}")
            return None

        if search_type == "jobs":
            return client.search.linkedin.jobs(keyword=query)
        else:
            return client.search.linkedin.profiles(firstName=query)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


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
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Searching LinkedIn for: {query} (type: {search_type})")

        # Run LinkedIn search in a separate thread to avoid uvloop conflicts
        result = _run_linkedin_search_in_thread(query, search_type)

        if result is None:
            return json.dumps({"success": False, "error": "Failed to execute LinkedIn search"})

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
        logger.error(f"[BRIGHTDATA] LinkedIn search error: {type(e).__name__}: {str(e)}")
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
# Combined Tool: Get Lyrics in ONE call (Search + Scrape)
# ============================================================================

def _extract_lyrics_from_html(html: str) -> dict:
    """Extract lyrics from Genius page HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {"success": False, "error": "beautifulsoup4 not installed"}

    soup = BeautifulSoup(html, 'html.parser')
    result = {"success": False, "title": None, "artist": None, "lyrics": None}

    # Extract title and artist from meta tag
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title_content = og_title['content']
        if ' by ' in title_content:
            parts = title_content.split(' by ')
            result["title"] = parts[0].strip()
            result["artist"] = parts[1].strip()

    # Extract lyrics from data-lyrics-container elements
    lyrics_containers = soup.find_all('div', attrs={'data-lyrics-container': 'true'})

    if lyrics_containers:
        lyrics_parts = []
        for container in lyrics_containers:
            for br in container.find_all('br'):
                br.replace_with('\n')
            text = container.get_text(separator='')
            lyrics_parts.append(text.strip())

        raw_lyrics = '\n\n'.join(lyrics_parts)

        # Clean up header noise (Contributors, Translations, etc.)
        import re
        for pattern in [r'\[(?:Intro|Verse|Chorus|Bridge|Pre-Chorus|Outro|Hook)', r'\n[A-Z][a-z]']:
            match = re.search(pattern, raw_lyrics, re.IGNORECASE)
            if match:
                start_pos = match.start()
                if raw_lyrics[start_pos] == '\n':
                    start_pos += 1
                raw_lyrics = raw_lyrics[start_pos:]
                break

        result["lyrics"] = raw_lyrics.strip()
        result["success"] = True

    return result


def _ai_analyze_genius_results(query: str, results: list, artist_hint: Optional[str] = None) -> dict:
    """Use AI to analyze Genius search results and pick the best match.

    Args:
        query: The original search query
        results: List of search result hits from Genius API
        artist_hint: Optional artist name hint from user

    Returns:
        The best matching result dict, or None if no good match
    """
    if not results:
        return None

    # If only one result, return it
    if len(results) == 1:
        return results[0]["result"]

    # Format results for AI analysis
    formatted_results = []
    for i, hit in enumerate(results[:5]):  # Limit to top 5
        song = hit["result"]
        formatted_results.append({
            "index": i,
            "title": song.get("title", "Unknown"),
            "artist": song.get("primary_artist", {}).get("name", "Unknown"),
            "url": song.get("url", ""),
        })

    # Create a simple prompt that works well with Cerebras
    results_text = "\n".join([
        f"{r['index']}: \"{r['title']}\" by {r['artist']}"
        for r in formatted_results
    ])

    prompt = f"""User is searching for: "{query}"{f' by {artist_hint}' if artist_hint else ''}

Search results:
{results_text}

Return ONLY the index number (0-{len(formatted_results)-1}) of the best matching song. Just the number, nothing else.

Answer:"""

    try:
        # Use Cerebras for fast analysis - use more tokens to ensure response
        model = get_cerebras_model(max_tokens=50, temperature=0.0)
        response = model.invoke(prompt)

        # Parse the response - should be just a number
        response_text = response.content.strip() if response.content else ""
        logger.info(f"[GENIUS AI] Raw response: '{response_text}'")

        # Extract number from response
        import re
        numbers = re.findall(r'\d+', response_text)
        if numbers:
            index = int(numbers[0])
            if 0 <= index < len(results):
                selected = results[index]["result"]
                logger.info(f"[GENIUS AI] Selected index {index}: {selected.get('title')} by {selected.get('primary_artist', {}).get('name')}")
                return selected

        # Fallback to first result if AI response is unclear
        logger.warning(f"[GENIUS AI] Could not parse response '{response_text}', using first result")
        return results[0]["result"]

    except Exception as e:
        logger.warning(f"[GENIUS AI] Analysis failed: {e}, using simple matching")
        # Fallback to simple matching
        if artist_hint:
            for hit in results[:5]:
                song = hit["result"]
                if artist_hint.lower() in song.get("primary_artist", {}).get("name", "").lower():
                    return song
        return results[0]["result"]


def _scrape_genius_url_sync(url: str) -> dict:
    """Scrape lyrics from a Genius URL using BrightData WebUnlocker."""
    import concurrent.futures

    def _run():
        # Get credentials for WebUnlocker
        bearer_token = os.getenv("BRIGHTDATA_API_TOKEN") or os.getenv("BRIGHTDATA_WEBUNLOCKER_BEARER")
        zone_string = os.getenv("WEB_UNLOCKER_ZONE") or os.getenv("BRIGHTDATA_WEBUNLOCKER_APP_ZONE_STRING")

        if not bearer_token:
            return {"success": False, "error": "BRIGHTDATA_API_TOKEN or BRIGHTDATA_WEBUNLOCKER_BEARER not set"}
        if not zone_string:
            return {"success": False, "error": "WEB_UNLOCKER_ZONE or BRIGHTDATA_WEBUNLOCKER_APP_ZONE_STRING not set"}

        try:
            from brightdata import WebUnlocker
            unlocker = WebUnlocker(BRIGHTDATA_WEBUNLOCKER_BEARER=bearer_token, ZONE_STRING=zone_string)
        except Exception as e:
            return {"success": False, "error": f"Failed to create WebUnlocker: {e}"}

        try:
            result = unlocker.get_source(url)

            if not result.success:
                return {"success": False, "error": f"Scrape failed: {result.error}"}

            html = result.data
            if not html or len(html) < 500:
                return {"success": False, "error": "Empty or too short response"}

            if len(html) < 5000:
                html_lower = html.lower()
                if any(x in html_lower for x in ["access denied", "you have been blocked"]):
                    return {"success": False, "error": "Request was blocked"}

            lyrics_data = _extract_lyrics_from_html(html)
            lyrics_data["url"] = url
            lyrics_data["html_size"] = len(html)
            return lyrics_data

        except Exception as e:
            return {"success": False, "error": f"Scrape error: {type(e).__name__}: {str(e)}"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


def _detect_language(text: str) -> str:
    """Detect the language of text based on character analysis.

    Detects: Hebrew (he), Arabic (ar), Russian (ru), Chinese (zh),
    Japanese (ja), Korean (ko), and defaults to English (en).

    Args:
        text: The text to analyze

    Returns:
        ISO 639-1 language code (e.g., 'he', 'en', 'ar')
    """
    if not text:
        return "en"

    # Count character types
    hebrew_count = 0
    arabic_count = 0
    cyrillic_count = 0
    cjk_count = 0
    hangul_count = 0
    latin_count = 0

    for char in text:
        code = ord(char)
        # Hebrew: U+0590 to U+05FF
        if 0x0590 <= code <= 0x05FF:
            hebrew_count += 1
        # Arabic: U+0600 to U+06FF
        elif 0x0600 <= code <= 0x06FF:
            arabic_count += 1
        # Cyrillic: U+0400 to U+04FF
        elif 0x0400 <= code <= 0x04FF:
            cyrillic_count += 1
        # CJK (Chinese/Japanese): U+4E00 to U+9FFF
        elif 0x4E00 <= code <= 0x9FFF:
            cjk_count += 1
        # Hangul (Korean): U+AC00 to U+D7AF
        elif 0xAC00 <= code <= 0xD7AF:
            hangul_count += 1
        # Latin: basic ASCII letters
        elif 0x0041 <= code <= 0x007A:
            latin_count += 1

    # Determine language by highest count (excluding Latin as fallback)
    counts = {
        "he": hebrew_count,
        "ar": arabic_count,
        "ru": cyrillic_count,
        "zh": cjk_count,  # Could be Chinese or Japanese, defaulting to Chinese
        "ko": hangul_count,
    }

    max_lang = max(counts, key=counts.get)
    if counts[max_lang] > 10:  # Threshold for non-Latin languages
        return max_lang

    # Default to English for Latin-based text
    return "en"


@tool
def genius_get_lyrics(song_name: str, artist_name: Optional[str] = None) -> str:
    """Get song lyrics in ONE call - searches Genius and uses AI to pick the best match.

    This is the RECOMMENDED tool for getting lyrics. It:
    1. Searches Genius API for the song
    2. Uses AI (Cerebras) to analyze results and pick the BEST match
    3. Scrapes lyrics from ONLY the AI-verified result
    4. Detects the language automatically
    5. Returns structured JSON array

    The AI analysis ensures:
    - Correct song is selected even with similar titles
    - Artist matching is intelligent (handles variations)
    - Only ONE URL is scraped (no wasted requests)

    Args:
        song_name: The name of the song
        artist_name: Artist name (recommended for accurate matching)

    Returns:
        JSON array with structured song data:
        [
          {
            "title": "Song Title",
            "artist": "Artist Name",
            "lyrics": "Full lyrics text...",
            "language": "he"  // ISO 639-1 code (he, en, ar, ru, zh, ko)
          }
        ]
    """
    try:
        # Step 1: Search Genius API
        headers = get_genius_headers()
        if not headers:
            return json.dumps({"success": False, "error": "GENIUS_ACCESS_TOKEN not set"})

        query = f"{song_name} {artist_name}" if artist_name else song_name
        logger.info(f"[GENIUS] Searching for: {query}")

        response = requests.get(
            "https://api.genius.com/search",
            params={"q": query},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if "response" not in data or not data["response"].get("hits"):
            return json.dumps({"success": False, "error": "No results found", "query": query})

        hits = data["response"]["hits"]
        logger.info(f"[GENIUS] Found {len(hits)} results, analyzing with AI...")

        # Step 2: Use AI to analyze results and pick the best match
        best_match = _ai_analyze_genius_results(
            query=query,
            results=hits,
            artist_hint=artist_name
        )

        if not best_match:
            return json.dumps({"success": False, "error": "AI could not find a matching result", "query": query})

        song_url = best_match["url"]
        song_title = best_match["title"]
        song_artist = best_match["primary_artist"]["name"]

        logger.info(f"[GENIUS] AI selected: {song_title} by {song_artist}")
        logger.info(f"[GENIUS] Scraping URL: {song_url}")

        # Step 3: Scrape lyrics from the verified URL
        lyrics_result = _scrape_genius_url_sync(song_url)

        if not lyrics_result.get("success"):
            return json.dumps({
                "success": False,
                "error": lyrics_result.get("error", "Failed to scrape lyrics"),
                "song_found": {"title": song_title, "artist": song_artist, "url": song_url}
            })

        # Step 4: Detect language from lyrics
        lyrics_text = lyrics_result.get("lyrics") or ""
        language = _detect_language(lyrics_text)

        # Step 5: Return structured result in array format
        structured_result = [{
            "title": lyrics_result.get("title") or song_title,
            "artist": lyrics_result.get("artist") or song_artist,
            "lyrics": lyrics_text,
            "language": language
        }]

        return json.dumps(structured_result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[GENIUS] Error: {type(e).__name__}: {str(e)}")
        return json.dumps({"success": False, "error": f"{type(e).__name__}: {str(e)}"})


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
            genius_get_lyrics,  # RECOMMENDED: One-call solution for lyrics
            genius_search_song,
            genius_get_song_details,
            genius_get_artist,
        ])
        logger.info("Genius API tools enabled (including genius_get_lyrics)")
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
- genius_get_lyrics: RECOMMENDED! Get lyrics in ONE call (search + validate + scrape)
- genius_search_song: Search for songs (use only if you need search results without lyrics)
- genius_get_song_details: Get detailed song info (use only if you need metadata without lyrics)
- genius_get_artist: Get artist information and bio

IMPORTANT: For lyrics requests, ALWAYS use genius_get_lyrics first! It searches, validates, and scrapes in one call. Do NOT use multiple tools for a single lyrics request.

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
