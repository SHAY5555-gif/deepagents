# Genius Lyrics Scraping Guide

## Using Chrome DevTools MCP

This guide explains how to extract song lyrics from Genius.com using the Chrome DevTools MCP server.

---

## URL Format

```
https://genius.com/{ARTIST}-{SONG-TITLE}-lyrics
```

**Examples:**
- `https://genius.com/The-beatles-hey-jude-lyrics`
- `https://genius.com/Queen-bohemian-rhapsody-lyrics`
- `https://genius.com/Adele-hello-lyrics`

---

## Step 1: Navigate to Page

```json
{
  "tool": "mcp__chrome-devtools-local__navigate_page",
  "parameters": {
    "url": "https://genius.com/{ARTIST}-{SONG}-lyrics"
  }
}
```

---

## Step 2: Extract Lyrics

```json
{
  "tool": "mcp__chrome-devtools-local__evaluate_script",
  "parameters": {
    "function": "() => { const container = document.querySelector('[data-lyrics-container=\"true\"]'); if (!container) return null; const header = container.querySelector('[data-exclude-from-selection=\"true\"]'); if (header) header.remove(); return container.innerText.trim(); }"
  }
}
```

### Formatted JavaScript:

```javascript
() => {
  // Find lyrics container
  const container = document.querySelector('[data-lyrics-container="true"]');
  if (!container) return null;

  // Remove header (contributors, translations, etc.)
  const header = container.querySelector('[data-exclude-from-selection="true"]');
  if (header) header.remove();

  // Return clean lyrics text
  return container.innerText.trim();
}
```

---

## Key Selectors

| Element | Selector |
|---------|----------|
| Lyrics Container | `[data-lyrics-container="true"]` |
| Header to Remove | `[data-exclude-from-selection="true"]` |

---

## Response Format

The script returns a clean string with the lyrics:

```
[Verse 1]
First line of lyrics...
Second line of lyrics...

[Chorus]
Chorus lyrics...
```

---

## Error Handling

If the page structure changes, the script returns `null`. Check for:
- Page loaded correctly
- Lyrics container exists
- Not a "lyrics pending" page

---

## Alternative: Get Metadata Too

```javascript
() => {
  const container = document.querySelector('[data-lyrics-container="true"]');
  if (!container) return null;

  const header = container.querySelector('[data-exclude-from-selection="true"]');
  if (header) header.remove();

  // Get song title
  const title = document.querySelector('h1')?.innerText || '';

  // Get artist
  const artist = document.querySelector('a[href*="/artists/"]')?.innerText || '';

  return {
    title: title,
    artist: artist,
    lyrics: container.innerText.trim()
  };
}
```

---

## Notes

- This method returns **only** the lyrics text
- No metadata, no extra fields
- No API credits required
- Works as long as page structure remains the same
- Genius may update their HTML structure - update selectors if needed

---

## Comparison with Other Methods

| Method | Pros | Cons |
|--------|------|------|
| **Chrome DevTools MCP** | Clean output, free, full control | Requires browser |
| Firecrawl JSON | Structured data | Returns metadata, costs credits |
| Firecrawl Markdown | Fast | Includes links, needs cleanup |
| Genius API | Official | Doesn't include full lyrics |
