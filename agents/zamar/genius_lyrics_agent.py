"""
Simple Genius Lyrics Agent - Search API + BrightData Scraping in ONE file.

Flow:
1. Search Genius API for the song URL
2. Scrape lyrics using BrightData Web Unlocker
3. Return lyrics with full process visibility
"""
import os
import json
import re
import logging
import requests
import concurrent.futures
from typing import Optional, Dict, Any, List

from bs4 import BeautifulSoup
from langchain_core.tools import tool
from langchain_cerebras import ChatCerebras
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)


# =============================================================================
# Genius Search API
# =============================================================================

def _search_genius_api(query: str) -> List[Dict[str, Any]]:
    """Search Genius API for songs matching the query."""
    api_token = os.getenv("GENIUS_API_TOKEN") or os.getenv("GENIUS_ACCESS_TOKEN")
    if not api_token:
        raise ValueError("GENIUS_API_TOKEN not set in environment")

    headers = {"Authorization": f"Bearer {api_token}"}
    params = {"q": query}

    response = requests.get(
        "https://api.genius.com/search",
        headers=headers,
        params=params,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()
    hits = data.get("response", {}).get("hits", [])

    results = []
    for hit in hits:
        song = hit.get("result", {})
        results.append({
            "title": song.get("title"),
            "artist": song.get("primary_artist", {}).get("name"),
            "url": song.get("url"),
            "id": song.get("id"),
        })

    return results


def _find_best_match(results: List[Dict], song_name: str, artist: Optional[str] = None) -> Optional[Dict]:
    """Find the best matching song from search results."""
    if not results:
        return None

    song_name_lower = song_name.lower()
    artist_lower = artist.lower() if artist else None

    # First pass: exact title match with artist
    for r in results:
        title_match = r["title"] and song_name_lower in r["title"].lower()
        artist_match = not artist_lower or (r["artist"] and artist_lower in r["artist"].lower())
        if title_match and artist_match:
            return r

    # Second pass: just title match
    for r in results:
        if r["title"] and song_name_lower in r["title"].lower():
            return r

    # Fallback: return first result
    return results[0] if results else None


# =============================================================================
# BrightData Scraping
# =============================================================================

def _detect_language(text: str) -> str:
    """Detect the language of text based on character analysis.

    Detects: Hebrew (he), Arabic (ar), Russian (ru), Chinese (zh),
    Korean (ko), and defaults to English (en).

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

    # Determine language by highest count
    counts = {
        "he": hebrew_count,
        "ar": arabic_count,
        "ru": cyrillic_count,
        "zh": cjk_count,
        "ko": hangul_count,
    }

    max_lang = max(counts, key=counts.get)
    if counts[max_lang] > 10:  # Threshold for non-Latin languages
        return max_lang

    # Default to English for Latin-based text
    return "en"


def _clean_lyrics_text(text: str) -> str:
    """Clean up lyrics text by removing header noise from Genius.

    Removes patterns like:
    - "4 ContributorsSong Title Lyrics..."
    - "X ContributorsSong Name - שם השיר Lyrics..."
    """
    # Remove Genius header pattern: "X Contributors...Lyrics"
    # This pattern matches: number + "Contributor(s)" + anything + "Lyrics"
    header_pattern = r'^\d+\s*Contributor[s]?.*?Lyrics'
    text = re.sub(header_pattern, '', text, flags=re.IGNORECASE)

    # Also try to find actual lyrics start markers
    lyrics_start_patterns = [
        r'\[(?:Intro|Verse|Chorus|Bridge|Pre-Chorus|Outro|Hook|Refrain|Instrumental)',
        r'\n[A-Z][a-z]',
    ]

    for pattern in lyrics_start_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start_pos = match.start()
            if text[start_pos] == '\n':
                start_pos += 1
            text = text[start_pos:]
            break

    return text.strip()


def _extract_lyrics_from_html(html: str) -> Dict[str, Any]:
    """Extract lyrics from Genius page HTML."""
    soup = BeautifulSoup(html, 'html.parser')

    result = {
        "success": False,
        "title": None,
        "artist": None,
        "lyrics": None,
        "error": None
    }

    # Extract title and artist from meta tag
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title_content = og_title['content']
        if ' by ' in title_content:
            parts = title_content.split(' by ')
            result["title"] = parts[0].strip()
            result["artist"] = parts[1].strip()

    # Fallback title extraction
    if not result["title"]:
        title_elem = soup.find('h1', class_=re.compile(r'SongHeader.*?Title'))
        if not title_elem:
            title_elem = soup.find('h1')
        if title_elem:
            result["title"] = title_elem.get_text(strip=True)

    # Fallback artist extraction
    if not result["artist"]:
        artist_elem = soup.find('a', class_=re.compile(r'SongHeader.*?Artist'))
        if not artist_elem:
            artist_elem = soup.find('a', href=re.compile(r'/artists/'))
        if artist_elem:
            result["artist"] = artist_elem.get_text(strip=True)

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
        result["lyrics"] = _clean_lyrics_text(raw_lyrics)
        result["success"] = True
    else:
        # Try alternative selector for older Genius page format
        lyrics_div = soup.find('div', class_=re.compile(r'Lyrics__Container'))
        if lyrics_div:
            for br in lyrics_div.find_all('br'):
                br.replace_with('\n')
            raw_lyrics = lyrics_div.get_text(separator='').strip()
            result["lyrics"] = _clean_lyrics_text(raw_lyrics)
            result["success"] = True
        else:
            result["error"] = "Could not find lyrics containers in HTML"

    return result


def _scrape_url_with_brightdata(url: str) -> Dict[str, Any]:
    """Scrape a URL using BrightData Web Unlocker API (direct HTTP call)."""
    import httpx

    api_token = os.getenv("BRIGHTDATA_API_TOKEN")
    if not api_token:
        return {"success": False, "error": "BRIGHTDATA_API_TOKEN not set"}

    logger.info(f"[GENIUS] Scraping URL: {url}")

    try:
        # Get zone from environment or use default
        zone = os.getenv("WEB_UNLOCKER_ZONE", "mcp_unlocker")

        # Direct HTTP call to BrightData Web Unlocker API
        # Using their scraping browser endpoint
        response = httpx.post(
            "https://api.brightdata.com/request",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            },
            json={
                "zone": zone,
                "url": url,
                "format": "raw"
            },
            timeout=60.0
        )

        if response.status_code != 200:
            logger.error(f"[GENIUS] BrightData API error: {response.status_code} - {response.text[:500]}")
            return {"success": False, "error": f"BrightData API returned {response.status_code}", "url": url}

        html = response.text

        if not html:
            return {"success": False, "error": "Empty response from BrightData", "url": url}

        logger.info(f"[GENIUS] Got HTML: {len(html)} chars")

        # Check for block pages
        blocked_indicators = ["access denied", "you have been blocked"]
        html_lower = html.lower()
        if any(ind in html_lower for ind in blocked_indicators) and len(html) < 5000:
            return {"success": False, "error": "Request was blocked", "url": url}

        # Parse lyrics
        lyrics_data = _extract_lyrics_from_html(html)
        lyrics_data["url"] = url
        return lyrics_data

    except httpx.TimeoutException:
        logger.error(f"[GENIUS] Scrape timeout")
        return {"success": False, "error": "Request timed out", "url": url}
    except Exception as e:
        logger.error(f"[GENIUS] Scrape error: {e}")
        return {"success": False, "error": f"{type(e).__name__}: {str(e)}", "url": url}


# =============================================================================
# Main Function: Search + Scrape (with full process visibility)
# =============================================================================

def _search_and_scrape(song_name: str, artist: Optional[str] = None) -> Dict[str, Any]:
    """Search Genius API for the song, then scrape the lyrics."""

    output = {
        "step1_search": {},
        "step2_match": {},
        "step3_scrape": {},
        "final_result": {}
    }

    # Step 1: Build search query and search
    query = f"{artist} {song_name}" if artist else song_name
    logger.info(f"[GENIUS] Searching for: {query}")

    try:
        search_results = _search_genius_api(query)
        logger.info(f"[GENIUS] Found {len(search_results)} results")

        output["step1_search"] = {
            "query": query,
            "results_count": len(search_results),
            "results": search_results[:5]  # Show top 5 results
        }
    except Exception as e:
        output["step1_search"] = {"error": str(e)}
        output["final_result"] = {"success": False, "error": f"Genius API search failed: {e}"}
        return output

    if not search_results:
        output["final_result"] = {"success": False, "error": f"No results found for: {query}"}
        return output

    # Step 2: Find best match
    best_match = _find_best_match(search_results, song_name, artist)
    if not best_match or not best_match.get("url"):
        output["step2_match"] = {"error": "Could not find matching song URL"}
        output["final_result"] = {"success": False, "error": "Could not find matching song URL"}
        return output

    logger.info(f"[GENIUS] Best match: {best_match['title']} by {best_match['artist']}")
    logger.info(f"[GENIUS] URL: {best_match['url']}")

    output["step2_match"] = {
        "selected": best_match,
        "reason": "Best title/artist match from search results"
    }

    # Step 3: Scrape the lyrics page with BrightData
    scrape_result = _scrape_url_with_brightdata(best_match["url"])

    output["step3_scrape"] = {
        "url": best_match["url"],
        "success": scrape_result.get("success", False)
    }

    # Final result
    if scrape_result.get("success"):
        output["final_result"] = {
            "success": True,
            "title": scrape_result.get("title"),
            "artist": scrape_result.get("artist"),
            "lyrics": scrape_result.get("lyrics"),
            "url": best_match["url"],
            "genius_id": best_match.get("id")
        }
    else:
        output["final_result"] = scrape_result
        output["final_result"]["genius_id"] = best_match.get("id")

    return output


# =============================================================================
# LangChain Tool
# =============================================================================

@tool
def get_lyrics(song_name: str, artist: Optional[str] = None) -> str:
    """Get song lyrics from Genius.com.

    This tool:
    1. Searches Genius API for the song
    2. Picks the best match
    3. Scrapes lyrics using BrightData
    4. Detects the language automatically

    Args:
        song_name: Name of the song
        artist: Artist name (optional but recommended)

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
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_search_and_scrape, song_name, artist)
        result = future.result(timeout=120)

    # Convert to structured output format
    final = result.get("final_result", {})

    if final.get("success"):
        lyrics_text = final.get("lyrics") or ""
        language = _detect_language(lyrics_text)

        structured_result = [{
            "title": final.get("title"),
            "artist": final.get("artist"),
            "lyrics": lyrics_text,
            "language": language
        }]
        return json.dumps(structured_result, ensure_ascii=False, indent=2)
    else:
        # Return error in consistent format
        return json.dumps({
            "success": False,
            "error": final.get("error", "Unknown error")
        }, ensure_ascii=False, indent=2)


# =============================================================================
# Agent Definition
# =============================================================================

SYSTEM_PROMPT = """You are a Lyrics Finder agent. Your ONLY job is to find song lyrics.

RULES:
1. When the user gives you a song name - IMMEDIATELY use the get_lyrics tool
2. DO NOT ask clarifying questions - just search
3. If the user provides an artist name, use it. If not, search without it.

Examples:
- User: "Hello by Adele" -> Use get_lyrics(song_name="Hello", artist="Adele")
- User: "Bohemian Rhapsody" -> Use get_lyrics(song_name="Bohemian Rhapsody")
- User: "Queen - We Will Rock You" -> Use get_lyrics(song_name="We Will Rock You", artist="Queen")

CRITICAL - OUTPUT FORMAT:
Your FINAL response MUST be ONLY the structured JSON array, nothing else.
Do NOT add any text, explanation, or markdown formatting.
Just return the raw JSON exactly as received from the tool:

[
  {
    "title": "Song Title",
    "artist": "Artist Name",
    "lyrics": "Full lyrics...",
    "language": "he"
  }
]

If the tool returns an error, return the error JSON as-is.
"""


async def agent():
    """Create the Genius Lyrics agent."""

    cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        raise ValueError("CEREBRAS_API_KEY not set")

    MODEL_NAME = "zai-glm-4.6"

    model = ChatCerebras(
        model=MODEL_NAME,
        api_key=cerebras_api_key,
        temperature=1.0,
        max_tokens=128000,
    )

    print("\n" + "="*60)
    print("[GENIUS-LYRICS-AGENT] Ready to find lyrics")
    print(f"Model: {MODEL_NAME} (Cerebras)")
    print("Tools: [get_lyrics]")
    print("="*60 + "\n")

    return create_react_agent(
        model=model,
        tools=[get_lyrics],
        prompt=SYSTEM_PROMPT,
    )
