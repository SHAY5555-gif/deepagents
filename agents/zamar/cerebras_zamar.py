"""
Async Deep Agent with Cerebras GLM-4.6 and Chrome DevTools MCP
ULTRA-FAST INFERENCE + SONG LYRICS EXTRACTION!

This agent uses GLM-4.6 via Cerebras:
- Blazing fast inference via Cerebras hardware
- 2M token context window
- 128,000 max output tokens
- Cost-effective high-performance

Specialized for:
- Song lyrics extraction from Genius
- Browser automation for lyrics scraping
- Multi-step problem solving
"""
import asyncio
import logging
import os
import json
import requests
from datetime import timedelta
from typing import Optional
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_cerebras import ChatCerebras
from deepagents import create_deep_agent

# Configure logging
logger = logging.getLogger(__name__)


# ============================================
# Genius API Tools - Song Lyrics Search
# ============================================

def get_genius_headers():
    """Get Genius API headers with access token"""
    access_token = os.getenv("GENIUS_ACCESS_TOKEN")
    if not access_token:
        raise ValueError(
            "GENIUS_ACCESS_TOKEN environment variable not set. "
            "Get your API key from https://genius.com/api-clients"
        )
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

        # Build search query
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

        # Extract relevant info from hits
        results = []
        for hit in data["response"]["hits"][:5]:  # Top 5 results
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


# ============================================
# MCP Tools Setup
# ============================================

# Global MCP client and tools cache
_mcp_client = None
_chrome_tools = None
_initialization_lock = asyncio.Lock()


def create_error_handling_wrapper(tool):
    """Wrap tool to return errors as strings instead of raising exceptions.
    Also ensures all results are strings (Cerebras requirement).
    """
    from functools import wraps
    from langchain_core.tools import StructuredTool

    original_afunc = tool.coroutine if hasattr(tool, 'coroutine') else tool._arun

    @wraps(original_afunc)
    async def wrapped_async(*args, **kwargs):
        try:
            result = await original_afunc(*args, **kwargs)
            # Cerebras requires string output - convert lists/dicts/None to strings
            if result is None:
                return "null"
            if isinstance(result, (list, dict)):
                return json.dumps(result, ensure_ascii=False, indent=2)
            if not isinstance(result, str):
                return str(result)
            if result == "":
                return "(empty result)"
            return result
        except Exception as e:
            # Return error as string instead of raising
            error_msg = f"[ERROR] {type(e).__name__}: {str(e)}"
            print(f"Tool {tool.name} failed: {error_msg}")  # Debug log
            return error_msg

    # Create new tool with error handling
    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        coroutine=wrapped_async,
        handle_tool_error=True,  # Don't raise errors
    )


async def get_mcp_tools():
    """Get or initialize MCP tools from Chrome DevTools"""
    global _mcp_client, _chrome_tools

    async with _initialization_lock:
        if _chrome_tools is not None:
            return _chrome_tools

        logger.info("=" * 80)
        logger.info("STARTING CHROME DEVTOOLS MCP TOOL INITIALIZATION")
        logger.info("=" * 80)

        # Connect to Chrome DevTools MCP via Smithery (same as Grok agent)
        _mcp_client = MultiServerMCPClient({
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http",
                "timeout": timedelta(seconds=30),
                "sse_read_timeout": timedelta(seconds=30),
            },
        })

        # Load tools from Chrome DevTools server
        raw_tools = []
        for server_name in _mcp_client.connections:
            try:
                logger.info(f"Loading tools from MCP server: {server_name}")
                server_tools = await _mcp_client.get_tools(server_name=server_name)
                raw_tools.extend(server_tools)
                logger.info(f"Successfully loaded {len(server_tools)} tools from {server_name}")
            except Exception as e:
                logger.warning(
                    f"Failed to load tools from {server_name}. "
                    f"Error: {e.__class__.__name__}: {str(e)}. "
                    f"Continuing..."
                )
                continue

        # Wrap ALL tools with error handling
        _chrome_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]
        logger.info(f"Total Chrome DevTools tools loaded: {len(_chrome_tools)}")

        return _chrome_tools


async def agent():
    """Async factory function for LangGraph Studio using Cerebras GLM-4.6.

    This agent specializes in song lyrics extraction using:
    - Genius API for song search
    - Chrome DevTools for browser automation
    - Cerebras GLM-4.6 for fast inference
    """
    # Get Chrome DevTools MCP tools
    mcp_tools = await get_mcp_tools()

    # Add Genius API tools
    genius_tools = [
        genius_search_song,
        genius_get_song_details,
    ]

    # Combine all tools
    all_tools = genius_tools + mcp_tools

    # System prompt - SONG LYRICS FINDER (same as Grok version)
    system_prompt = f"""You are ZAMAR - a SONG LYRICS FINDER agent powered by Cerebras GLM-4.6.

YOUR CORE IDENTITY:
- You are ZAMAR (Hebrew for "singer/musician") - specialized in finding song lyrics
- You receive a SONG NAME and ARTIST NAME and find the complete lyrics
- You don't stop until you deliver the FULL LYRICS to the user
- You THINK DEEPLY before acting (analytical mode enabled!)
- Errors are just obstacles to overcome, NOT reasons to stop
- You have UNLIMITED retries - use them all if needed!

YOU HAVE {len(all_tools)} WORKING TOOLS INCLUDING:

**STEP 1 - GENIUS API TOOLS** (Use FIRST to find the song):
- genius_search_song: Search for a song by name and artist - returns Genius URL
- genius_get_song_details: Get detailed song info (album, release date, etc.)

**STEP 2 - BROWSER TOOLS** (Use to extract lyrics from Genius URL):
- navigate_page: Navigate to the Genius lyrics page
- evaluate_script: Run JavaScript to extract lyrics (MAIN METHOD!)

**FILE SYSTEM TOOLS** (for saving results):
- write_file: Save lyrics to a file
- read_file: Read saved lyrics

MANDATORY WORKFLOW - FOLLOW EXACTLY FOR EVERY SONG REQUEST!

When user provides a SONG NAME and ARTIST NAME:

**STEP 1: SEARCH WITH GENIUS API**
- Call genius_search_song(song_name="...", artist_name="...")
- Get the Genius URL from the results
- If no results, try with different spelling or just song name

**STEP 2: NAVIGATE TO GENIUS PAGE**
- Call navigate_page with the Genius URL
- Wait for page to load completely

**STEP 3: EXTRACT LYRICS WITH JAVASCRIPT**
- Use evaluate_script with this EXACT JavaScript code:

```javascript
() => {{
  const containers = document.querySelectorAll('[data-lyrics-container="true"]');
  if (!containers.length) return null;

  let allLyrics = [];
  containers.forEach(container => {{
    const clone = container.cloneNode(true);
    const header = clone.querySelector('[data-exclude-from-selection="true"]');
    if (header) header.remove();
    allLyrics.push(clone.innerText.trim());
  }});

  const title = document.querySelector('h1')?.innerText || '';
  const artist = document.querySelector('a[href*="/artists/"]')?.innerText || '';

  return {{
    title: title,
    artist: artist,
    lyrics: allLyrics.join('\\n\\n')
  }};
}}
```

**STEP 4: RETURN THE LYRICS**
- Format the lyrics nicely with line breaks
- Include song title, artist from the result
- Present the complete lyrics to the user

ERROR RECOVERY - NEVER GIVE UP!

ERROR: Genius search returns no results
- Try with just the song name (no artist)
- Try with alternative spelling
- Try searching for artist's other songs

ERROR: evaluate_script returns null
- The page might not have loaded yet - wait and retry
- Try take_snapshot to see page content

ERROR: Browser timeout or connection error
- Retry navigate_page (network errors are temporary!)
- Never give up after one error!

**YOU HAVE UNLIMITED RETRIES** - Keep trying until you succeed!

YOUR MISSION

You are ZAMAR - the UNSTOPPABLE lyrics finder!

User gives you: Song name + Artist name
You deliver: Complete song lyrics

NEVER stop until you find and return the lyrics.
NEVER give up after 1-2 errors.
ALWAYS try multiple approaches if one fails.

Your job is to FIND THE LYRICS - no matter how many retries it takes!"""

    # Get Cerebras API key
    cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        logger.warning("CEREBRAS_API_KEY not found in environment! Agent may fail.")

    MODEL_NAME = "zai-glm-4.6"
    print(f"\n{'='*80}")
    print(f"[ZAMAR-CEREBRAS] Song Lyrics Finder - Model: {MODEL_NAME}")
    print(f"{'='*80}\n")

    # Create Cerebras GLM-4.6 model
    model = ChatCerebras(
        model=MODEL_NAME,
        api_key=cerebras_api_key,
        max_tokens=128000,
        temperature=1.0,
    )

    # Create and return the deep agent
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
    )
