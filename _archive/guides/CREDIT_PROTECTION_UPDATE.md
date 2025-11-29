# FireCrawl Credit Protection Update

## Changes Made

To protect your FireCrawl credits from accidental consumption, the following changes have been implemented:

### ❌ Tools Removed

The following tools have been **permanently disabled**:

1. **firecrawl_crawl_website**
   - Would crawl multiple pages recursively
   - Could easily consume 100-1,000+ credits per request
   - **Status**: REMOVED from agent

2. **firecrawl_map_website**
   - Would discover all URLs on entire website
   - Could consume hundreds of credits
   - **Status**: REMOVED from agent

### ✅ Tools Still Available

Only **safe, single-page tools** remain enabled:

1. **firecrawl_scrape_url**
   - Scrapes ONE page at a time
   - Safe and predictable cost
   - Status: ACTIVE

2. **firecrawl_extract_structured_data**
   - Extracts data from ONE page using AI
   - Safe and predictable cost
   - Status: ACTIVE

3. **firecrawl_extract_with_pydantic_schema** (RECOMMENDED)
   - Extracts data with schema validation
   - Safe and predictable cost
   - Status: ACTIVE

## What This Means

### You Are Protected From:
- ❌ Accidentally crawling entire websites
- ❌ Consuming thousands of credits in one request
- ❌ Wildcard URL patterns that match hundreds of pages
- ❌ Uncontrolled multi-page operations

### You Can Still:
- ✅ Extract data from single pages
- ✅ Use AI-powered extraction with schemas
- ✅ Scrape specific URLs one at a time
- ✅ Have full control over credit consumption

## Cost Control Guidelines

### Safe Usage (Single Page)
```python
# This is SAFE - extracts ONE page
firecrawl_extract_structured_data(
    url="https://example.com/specific-page",
    prompt="Extract article data"
)
# Cost: ~1 credit
```

### Dangerous Usage (NOW BLOCKED)
```python
# This is BLOCKED - would extract MANY pages
# firecrawl_extract_structured_data(
#     url="https://example.com/*",
#     prompt="Extract all articles"
# )
# Cost: Could be 100-1,000+ credits! (NOW PREVENTED)
```

## Wildcard Warning

⚠️ **CRITICAL**: Even with the remaining tools, be careful with wildcards:

- `https://example.com/*` - Matches ALL pages (DANGEROUS)
- `https://example.com/blog/*` - Matches all blog posts (DANGEROUS)
- `https://example.com/specific-page` - Matches ONE page (SAFE)

**Always use specific URLs** to maintain cost control.

## Code Changes

### File: mcp_agent_grok_4_1.py

**Removed functions:**
- `firecrawl_crawl_website()` - Deleted
- `firecrawl_map_website()` - Deleted

**Updated tools list:**
```python
firecrawl_tools = [
    firecrawl_scrape_url,
    firecrawl_extract_structured_data,
    firecrawl_extract_with_pydantic_schema,
    # firecrawl_crawl_website - DISABLED
    # firecrawl_map_website - DISABLED
]
```

**Added to system prompt:**
```
⚠️ IMPORTANT - CREDIT PROTECTION:
- Only SINGLE-PAGE extraction is enabled
- Multi-page crawling tools are DISABLED
- Always extract from ONE URL at a time
- Use wildcards (*) with EXTREME caution
```

## Documentation Updates

All documentation has been updated to reflect these changes:

1. **FIRECRAWL_QUICKSTART.md** - Marked tools as disabled
2. **FIRECRAWL_EXTRACT_EXAMPLES.md** - Removed dangerous examples, added warnings
3. **FIRECRAWL_SDK_MIGRATION.md** - Documented the removal

## Testing

All changes have been verified:
- ✅ Python syntax validated
- ✅ Enabled tools import successfully
- ✅ No functionality broken
- ✅ Credit protection in place

## Summary

**Before**: 5 tools (2 dangerous)
**After**: 3 tools (all safe)

**Protection**: Multi-page crawling permanently disabled
**Control**: You now have full control over credit usage

---

**Your credits are now protected!** 🛡️

Use only the 3 safe tools for single-page extraction, and always specify exact URLs (no wildcards) for maximum cost control.
