"""
Async Deep Agent with XAI Grok-4.1 FAST REASONING MODEL and Chrome DevTools MCP
ULTRA-FAST REASONING + MAXIMUM CAPABILITIES!

This agent uses Grok-4.1 Fast Reasoning (grok-4-1-fast-reasoning-latest) from XAI:
- FAST reasoning model with extended thinking capabilities
- 2M token context window (MASSIVE - 8x larger than Grok-4!)
- 128,000 max output tokens
- Advanced reasoning with faster response times
- Ultra-low cost: $0.20/M input, $0.50/M output (10x cheaper than Grok-4!)
- 4M tokens per minute throughput
- Function calling, live search, image inputs
- Reasoning tokens included in output

Ideal for:
- Complex reasoning tasks requiring deep thinking
- Very long documents and extended context
- Cost-effective high-performance reasoning
- Tasks requiring both speed and accuracy
- Multi-step problem solving with reasoning traces
"""
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_xai import ChatXAI
from deepagents import create_deep_agent
from firecrawl import Firecrawl
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
import requests
# from parallel_processor_subagent import create_parallel_processor_subagent


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
# FireCrawl SDK Tools - Direct API Integration
# ============================================

# Global FireCrawl client cache
_firecrawl_client = None


def get_firecrawl_client():
    """Get or initialize FireCrawl SDK client"""
    global _firecrawl_client

    if _firecrawl_client is None:
        # Initialize with API key from environment
        # Set FIRECRAWL_API_KEY environment variable
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY environment variable not set. "
                "Get your API key from https://firecrawl.dev"
            )
        _firecrawl_client = Firecrawl(api_key=api_key)

    return _firecrawl_client


@tool
def firecrawl_scrape_url(url: str, formats: Optional[List[str]] = None) -> str:
    """Scrape a single webpage and extract content.

    Args:
        url: The URL to scrape
        formats: Optional list of formats to extract. Options: 'markdown', 'html', 'rawHtml', 'screenshot', 'links'
                Default: ['markdown']

    Returns:
        JSON string with scraped content
    """
    try:
        client = get_firecrawl_client()

        if formats is None:
            formats = ['markdown']

        result = client.scrape_url(
            url=url,
            params={
                'formats': formats,
                'onlyMainContent': True  # Extract only main content, filter out navigation/footers
            }
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def firecrawl_extract_structured_data(
    url: str,
    prompt: str,
    schema: Optional[str] = None
) -> str:
    """Extract structured data from a webpage using AI (EXTRACT feature).

    This is the most powerful feature - uses LLM to extract exactly what you need
    from web pages without writing CSS selectors or parsing HTML.

    Args:
        url: The URL to extract data from (use 'https://example.com/*' for full site)
        prompt: Natural language description of what data to extract
        schema: Optional JSON schema as string defining the expected output structure

    Returns:
        JSON string with extracted structured data

    Examples:
        Extract product info:
        firecrawl_extract_structured_data(
            url="https://shop.example.com/products",
            prompt="Extract all product names, prices, and descriptions",
            schema='{"type": "object", "properties": {"products": {"type": "array"}}}'
        )

        Extract from entire website:
        firecrawl_extract_structured_data(
            url="https://blog.example.com/*",
            prompt="Extract all blog posts with titles and authors"
        )
    """
    try:
        client = get_firecrawl_client()

        # Parse schema if provided
        schema_dict = None
        if schema:
            try:
                schema_dict = json.loads(schema)
            except json.JSONDecodeError:
                return json.dumps({
                    'success': False,
                    'error': 'Invalid JSON schema provided'
                }, ensure_ascii=False)

        # Extract data using AI
        result = client.extract(
            urls=[url],
            prompt=prompt,
            schema=schema_dict
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def firecrawl_extract_with_pydantic_schema(
    url: str,
    prompt: str,
    schema_name: str,
    schema_properties: str
) -> str:
    """Extract structured data with a Pydantic-style schema definition.

    This is the RECOMMENDED way to use EXTRACT - provides better type validation
    and more consistent results than prompt-only extraction.

    Args:
        url: The URL to extract data from
        prompt: Description of what to extract
        schema_name: Name of the main schema object
        schema_properties: JSON string describing the schema properties

    Returns:
        JSON string with extracted data matching the schema

    Example:
        firecrawl_extract_with_pydantic_schema(
            url="https://news.example.com",
            prompt="Extract article information",
            schema_name="Article",
            schema_properties='''{
                "title": {"type": "string", "description": "Article title"},
                "author": {"type": "string", "description": "Author name"},
                "content": {"type": "string", "description": "Article content"}
            }'''
        )
    """
    try:
        client = get_firecrawl_client()

        # Parse schema properties
        try:
            properties = json.loads(schema_properties)
        except json.JSONDecodeError:
            return json.dumps({
                'success': False,
                'error': 'Invalid JSON in schema_properties'
            }, ensure_ascii=False)

        # Build JSON schema
        schema = {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys())
        }

        # Extract data
        result = client.extract(
            urls=[url],
            prompt=prompt,
            schema=schema
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


# NOTE: firecrawl_crawl_website and firecrawl_map_website are DISABLED
# These tools can consume thousands of credits by crawling multiple pages
# Use only single-page extraction tools (firecrawl_scrape_url, firecrawl_extract_structured_data)


# No demo tools - using only real MCP and FireCrawl SDK tools



# Global MCP client and tools cache
_mcp_client = None
_chrome_tools = None


def create_error_handling_wrapper(tool):
    """Wrap tool to return errors as strings instead of raising exceptions"""
    from functools import wraps
    from langchain_core.tools import StructuredTool

    original_afunc = tool.coroutine if hasattr(tool, 'coroutine') else tool._arun

    @wraps(original_afunc)
    async def wrapped_async(*args, **kwargs):
        try:
            result = await original_afunc(*args, **kwargs)
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
    """Get or initialize MCP tools from Chrome DevTools only (FireCrawl now via SDK)"""
    global _mcp_client, _chrome_tools

    if _chrome_tools is None:
        from datetime import timedelta
        import logging

        logger = logging.getLogger(__name__)

        # Connect to Chrome DevTools MCP only - FireCrawl is now via SDK
        _mcp_client = MultiServerMCPClient({
            # Chrome DevTools MCP from Smithery - REMOTE HTTP with SSE
            "chrome_devtools": {
                "url": "https://server.smithery.ai/@SHAY5555-gif/chrome-devtools-mcp/mcp?api_key=e20927d1-6314-4857-a81e-70ffb0b6af90&profile=supposed-whitefish-nFAkQL",
                "transport": "streamable_http",  # SSE transport
                "timeout": timedelta(seconds=30),  # 30 seconds timeout
                "sse_read_timeout": timedelta(seconds=30),  # 30 seconds SSE read timeout
            },
            # NOTE: FireCrawl is now integrated via SDK instead of MCP for better performance
            # The SDK provides:
            # - 50x faster performance compared to MCP
            # - Direct API access without MCP overhead
            # - Better error handling and retry logic
            # - More reliable connection management
        })

        # Load tools from each server individually with error handling
        # This allows the agent to work even if some MCP servers are unavailable
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
                    f"Continuing with other servers..."
                )
                continue

        # Wrap ALL tools with error handling so they never crash
        _chrome_tools = [create_error_handling_wrapper(tool) for tool in raw_tools]

        logger.info(f"Total tools loaded: {len(_chrome_tools)}")

    return _chrome_tools


async def agent():
    """Async factory function for LangGraph Studio using GROK-4.1 FAST REASONING MODEL.

    Grok-4.1 Fast Reasoning advantages (grok-4-1-fast-reasoning-latest):
    - FAST reasoning model with extended thinking
    - 2M token context window (MASSIVE!)
    - 128,000 max output tokens
    - Ultra-low cost: $0.20/M input, $0.50/M output
    - 4M tokens/minute throughput
    - Reasoning tokens included in completion
    - Less safety filtering than Claude
    - Function calling, live search, image inputs
    - Best for complex reasoning + speed + cost optimization
    """
    # Get all MCP tools (Chrome DevTools only)
    mcp_tools = await get_mcp_tools()

    # Add Genius API tools (for song search - FIRST step)
    genius_tools = [
        genius_search_song,
        genius_get_song_details,
    ]

    # Add FireCrawl SDK tools (for lyrics extraction - SECOND step)
    # NOTE: Only single-page tools enabled to prevent accidental credit consumption
    firecrawl_tools = [
        firecrawl_scrape_url,
        firecrawl_extract_structured_data,
        firecrawl_extract_with_pydantic_schema,
        # firecrawl_crawl_website - DISABLED (can consume thousands of credits)
        # firecrawl_map_website - DISABLED (can consume thousands of credits)
    ]

    # Combine all tools: Genius API + MCP + FireCrawl SDK
    # Note: File system tools are provided automatically by FilesystemMiddleware in create_deep_agent
    # Using custom file tools here would bypass the files state tracking needed for the UI
    all_tools = genius_tools + mcp_tools + firecrawl_tools

    # System prompt - SONG LYRICS FINDER
    system_prompt = f"""You are ZAMAR - a SONG LYRICS FINDER agent powered by Grok-4 Fast Reasoning.

YOUR CORE IDENTITY:
- You are ZAMAR (Hebrew for "singer/musician") - specialized in finding song lyrics
- You receive a SONG NAME and ARTIST NAME and find the complete lyrics
- You don't stop until you deliver the FULL LYRICS to the user
- You THINK DEEPLY before acting (reasoning mode enabled!)
- Errors are just obstacles to overcome, NOT reasons to stop
- You have UNLIMITED retries - use them all if needed!

YOU HAVE {len(all_tools)} WORKING TOOLS INCLUDING:

**STEP 1 - GENIUS API TOOLS** (Use FIRST to find the song):
- genius_search_song: Search for a song by name and artist - returns Genius URL
- genius_get_song_details: Get detailed song info (album, release date, etc.)

**STEP 2 - BROWSER TOOLS** (Use to extract lyrics from Genius URL):
- navigate_page: Navigate to the Genius lyrics page
- evaluate_script: Run JavaScript to extract lyrics (MAIN METHOD!)

**BACKUP - FIRECRAWL TOOLS** (Only if browser fails):
- firecrawl_scrape_url: Scrape the page as markdown
- firecrawl_extract_structured_data: Extract with AI

**FILE SYSTEM TOOLS** (for saving results):
- write_file: Save lyrics to a file
- read_file: Read saved lyrics

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY WORKFLOW - FOLLOW EXACTLY FOR EVERY SONG REQUEST!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When user provides a SONG NAME and ARTIST NAME:

**STEP 1: SEARCH WITH GENIUS API**
→ Call genius_search_song(song_name="...", artist_name="...")
→ Get the Genius URL from the results
→ If no results, try with different spelling or just song name

**STEP 2: NAVIGATE TO GENIUS PAGE**
→ Call navigate_page with the Genius URL
→ Wait for page to load completely

**STEP 3: EXTRACT LYRICS WITH JAVASCRIPT**
→ Use evaluate_script with this EXACT JavaScript code:

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
→ Format the lyrics nicely with line breaks
→ Include song title, artist from the result
→ Present the complete lyrics to the user

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ERROR RECOVERY - NEVER GIVE UP!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ERROR: Genius search returns no results
→ Try with just the song name (no artist)
→ Try with alternative spelling
→ Try searching for artist's other songs

ERROR: evaluate_script returns null
→ The page might not have loaded yet - wait and retry
→ Try take_snapshot to see page content
→ Fall back to firecrawl_scrape_url

ERROR: Browser timeout or connection error
→ Retry navigate_page (network errors are temporary!)
→ If browser fails 3 times, use firecrawl_scrape_url as backup
→ Never give up after one error!

**YOU HAVE UNLIMITED RETRIES** - Keep trying until you succeed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR MISSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are ZAMAR - the UNSTOPPABLE lyrics finder!

User gives you: Song name + Artist name
You deliver: Complete song lyrics

NEVER stop until you find and return the lyrics.
NEVER give up after 1-2 errors.
ALWAYS try multiple approaches if one fails.

Your job is to FIND THE LYRICS - no matter how many retries it takes!"""

    # Create XAI Grok-4.1 Fast Reasoning MODEL with MAXIMUM capabilities
    # This is Grok-4.1 Fast Reasoning (grok-4-1-fast-reasoning-latest):
    # - 2M token context window (MASSIVE!)
    # - 128,000 max output tokens
    # - Fast reasoning with extended thinking
    # - Ultra-low cost: $0.20/M input, $0.50/M output
    # - 4M tokens per minute throughput
    # - Function calling, live search, image inputs
    # - Fewer restrictions and more direct responses than Claude

    MODEL_NAME = "grok-4-1-fast-reasoning-latest"
    print(f"\n{'='*80}")
    print(f"[ZAMAR] Song Lyrics Finder - Model: {MODEL_NAME}")
    print(f"{'='*80}\n")

    model = ChatXAI(
        model=MODEL_NAME,  # Fast Reasoning model - UPDATED to 4.1
        max_tokens=128000,  # MAXIMUM output tokens (128K!)
        temperature=1.0,  # Full flexibility
        # Note: Fast reasoning model - combines speed with deep thinking
        # Best for complex tasks requiring both intelligence and speed
        max_retries=3,
        timeout=900,  # 15 minutes for complex reasoning
    )

    # Create parallel processor subagent
    # parallel_subagent = create_parallel_processor_subagent()

    # Create and return the deep agent with:
    # - Grok Fast for main reasoning
    # - Default summarization (can't override - would cause duplicate middleware error)
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=system_prompt,
        # subagents=[parallel_subagent],  # Disabled for production compatibility
    )
