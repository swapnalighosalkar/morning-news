"""
News MCP Server - Fetches and summarizes top world news using Claude Code CLI.
No API key needed - uses your existing Claude subscription via Claude Code.
"""

import asyncio
import httpx
import os
import subprocess
import sys
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Initialize MCP server
app = Server("news-summarizer")

# --- News fetching helpers ---

GNEWS_API_URL = "https://gnews.io/api/v4/top-headlines"
NEWSAPI_URL = "https://newsapi.org/v2/top-headlines"


async def fetch_news_gnews(category: str = "world", max_articles: int = 10) -> list[dict]:
    """Fetch news from GNews API (free tier available)."""
    api_key = os.environ.get("GNEWS_API_KEY")
    if not api_key:
        raise ValueError("GNEWS_API_KEY environment variable not set")

    params = {
        "category": category,
        "lang": "en",
        "max": max_articles,
        "apikey": api_key,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(GNEWS_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "content": item.get("content", ""),
            "url": item.get("url", ""),
            "source": item.get("source", {}).get("name", "Unknown"),
            "publishedAt": item.get("publishedAt", ""),
        })
    return articles


async def fetch_news_newsapi(category: str = "general", max_articles: int = 10) -> list[dict]:
    """Fetch news from NewsAPI.org (free tier available)."""
    api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        raise ValueError("NEWSAPI_KEY environment variable not set")

    params = {
        "category": category,
        "language": "en",
        "pageSize": max_articles,
        "apiKey": api_key,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(NEWSAPI_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "content": item.get("content", ""),
            "url": item.get("url", ""),
            "source": item.get("source", {}).get("name", "Unknown"),
            "publishedAt": item.get("publishedAt", ""),
        })
    return articles


def build_news_prompt(articles: list[dict], style: str = "concise") -> str:
    """Build prompt for Claude to summarize articles."""
    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"""
Article {i}:
Title: {a['title']}
Source: {a['source']}
Published: {a['publishedAt']}
Description: {a['description']}
Content: {a['content'][:500] if a['content'] else 'N/A'}
URL: {a['url']}
---"""

    style_instructions = {
        "concise": "Write a concise 1-2 sentence summary per article. Keep the overall response brief.",
        "detailed": "Write a detailed 3-5 sentence summary per article, explaining context and significance.",
        "bullets": "Summarize all articles as a single bullet-point briefing, grouped by topic.",
        "executive": "Write an executive briefing — an overall summary paragraph followed by the top 5 key headlines.",
    }

    instruction = style_instructions.get(style, style_instructions["concise"])

    return f"""You are a professional news analyst. Below are the top world news articles fetched at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.

{instruction}

NEWS ARTICLES:
{articles_text}

Provide your summary now:"""


async def summarize_with_claude_code(articles: list[dict], style: str = "concise") -> str:
    """
    Summarize articles using Claude Code CLI.
    Uses your existing Claude subscription - no API key needed.
    """
    prompt = build_news_prompt(articles, style)

    # Run claude CLI as a subprocess with -p flag (print mode, non-interactive)
    result = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await result.communicate()

    if result.returncode != 0:
        err = stderr.decode().strip()
        raise RuntimeError(f"Claude Code CLI error: {err}")

    return stdout.decode().strip()


# --- MCP Tool Definitions ---

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_top_news",
            description=(
                "Fetches the top world news headlines and returns raw article data. "
                "Use this to get current headlines without summarization."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "News category: world, business, technology, sports, health, science, entertainment",
                        "default": "world",
                    },
                    "max_articles": {
                        "type": "integer",
                        "description": "Number of articles to fetch (1-20)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "provider": {
                        "type": "string",
                        "description": "News provider to use: gnews or newsapi",
                        "default": "gnews",
                        "enum": ["gnews", "newsapi"],
                    },
                },
            },
        ),
        types.Tool(
            name="summarize_news",
            description=(
                "Fetches top world news AND summarizes it using Claude AI. "
                "Returns an AI-generated briefing of current headlines. "
                "Uses your Claude subscription via Claude Code - no API key needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "News category: world, business, technology, sports, health, science, entertainment",
                        "default": "world",
                    },
                    "max_articles": {
                        "type": "integer",
                        "description": "Number of articles to fetch and summarize (1-20)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "summary_style": {
                        "type": "string",
                        "description": "Style of summary: concise, detailed, bullets, executive",
                        "default": "concise",
                        "enum": ["concise", "detailed", "bullets", "executive"],
                    },
                    "provider": {
                        "type": "string",
                        "description": "News provider: gnews or newsapi",
                        "default": "gnews",
                        "enum": ["gnews", "newsapi"],
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "get_top_news":
        category = arguments.get("category", "world")
        max_articles = arguments.get("max_articles", 10)
        provider = arguments.get("provider", "gnews")

        try:
            if provider == "newsapi":
                articles = await fetch_news_newsapi(category, max_articles)
            else:
                articles = await fetch_news_gnews(category, max_articles)

            lines = [f"Top {len(articles)} {category.title()} News Headlines\n"]
            for i, a in enumerate(articles, 1):
                lines.append(
                    f"{i}. {a['title']}\n"
                    f"   Source: {a['source']} | {a['publishedAt']}\n"
                    f"   {a['description']}\n"
                    f"   {a['url']}\n"
                )

            return [types.TextContent(type="text", text="\n".join(lines))]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error fetching news: {str(e)}")]

    elif name == "summarize_news":
        category = arguments.get("category", "world")
        max_articles = arguments.get("max_articles", 10)
        style = arguments.get("summary_style", "concise")
        provider = arguments.get("provider", "gnews")

        try:
            # Fetch articles
            if provider == "newsapi":
                articles = await fetch_news_newsapi(category, max_articles)
            else:
                articles = await fetch_news_gnews(category, max_articles)

            if not articles:
                return [types.TextContent(type="text", text="No articles found.")]

            # Summarize using Claude Code CLI (your existing subscription)
            summary = await summarize_with_claude_code(articles, style)

            sources = "\n".join(
                f"  - {a['title'][:60]} ({a['url']})" for a in articles
            )

            result = (
                f"World News Summary ({datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})\n"
                f"Category: {category.title()} | Style: {style} | Articles: {len(articles)}\n\n"
                f"{summary}\n\n"
                f"---\nSources:\n{sources}"
            )

            return [types.TextContent(type="text", text=result)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# --- Entry point ---

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
