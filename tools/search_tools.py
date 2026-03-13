"""
tools/search_tools.py
─────────────────────
LangChain-compatible tools that the Trend Agent uses to discover
what's currently viral/trending in the food & cooking space.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool          # @tool decorator turns a plain function into a LangChain Tool object
from tavily import TavilyClient                # Tavily: search engine built for LLM agents (returns clean text, not raw HTML)


# ─────────────────────────────────────────────
#  Helper: build a Tavily client on first use
# ─────────────────────────────────────────────
def _tavily_client() -> TavilyClient:
    """Construct a Tavily client."""

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "TAVILY_API_KEY is not set. "
            "Get a free key at https://tavily.com and add it to your .env file."
        )
    return TavilyClient(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
#  TOOL 1 - search_trending_food_topics
#  The workhorse: broad search for what's viral RIGHT NOW on social/food media.
# ─────────────────────────────────────────────────────────────────────────────
@tool
def search_trending_food_topics(query: str = "trending food recipes right now") -> str:
    """
    Search the web for currently trending food topics, viral recipes,
    and popular cooking content.

    Args:
        query: A search string. Defaults to a broad food-trend query but
               the LLM will override this with something more targeted
               (e.g. "viral Instagram recipes this week").

    Returns:
        A JSON string with a list of result dicts:
            [{"title": ..., "url": ..., "content": ..., "relevance_to_query": ...}, ...]
        The LLM reads this to extract concrete trend names.
    """
    client = _tavily_client()

    results = client.search(
        query=query,
        search_depth="advanced",
        max_results=8,
        include_answer=True,
        topic="news",              # Bias toward recent articles (last ~7 days)
    )

    cleaned = [
        {
            "title":   r.get("title", ""),
            "url":     r.get("url", ""),
            "content": r.get("content", "")[:600],   # Truncate to ~600 chars to save tokens
            "relevance_to_query":   round(r.get("score", 0), 3),  # Relevance score to query (0-1)
        }
        for r in results.get("results", [])
    ]

    # Pre-summarised answer Tavily generates (handy context)
    answer = results.get("answer", "")

    return json.dumps({"answer": answer, "results": cleaned}, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  TOOL 2 - search_social_media_food_trends
#  Focused query for the platforms our content will be published on (e.g. Instagram).
# ─────────────────────────────────────────────────────────────────────────────
@tool
def search_social_media_food_trends(platform: str = "Instagram") -> str:
    """
    Search for food content that is currently trending specifically on
    social media platforms (e.g. Instagram Posts).

    Args:
        platform: Which platform(s) to focus on. The LLM passes this in
                  based on the publishing targets defined in ContentState.

    Returns:
        JSON string - same shape as search_trending_food_topics.
    """
    client = _tavily_client()

    query = f"viral food recipe trend {platform} {datetime.now().strftime('%B %Y')}"

    results = client.search(
        query=query,
        search_depth="advanced",
        max_results=8,
        include_answer=True,
        topic="news",
    )

    cleaned = [
        {
            "title":   r.get("title", ""),
            "url":     r.get("url", ""),
            "content": r.get("content", "")[:600],
            "relevance_to_query":   round(r.get("score", 0), 3),
        }
        for r in results.get("results", [])
    ]

    return json.dumps({
        "platform": platform,
        "answer":   results.get("answer", ""),
        "results":  cleaned,
    }, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  TOOL 3 - search_seasonal_ingredients
#  Seasonality is a major driver of food content popularity.
# ─────────────────────────────────────────────────────────────────────────────
@tool
def search_seasonal_ingredients() -> str:
    """
    Find which ingredients are in season right now and what recipes
    are popular around them.

    Returns:
        JSON string with seasonal ingredient info and related recipe ideas.
    """
    month = datetime.now().strftime("%B")

    client = _tavily_client()

    query = f"seasonal ingredients {month} cooking recipes trending"

    results = client.search(
        query=query,
        search_depth="basic",
        max_results=5,
        include_answer=True,
    )

    cleaned = [
        {
            "title":   r.get("title", ""),
            "content": r.get("content", "")[:400],
        }
        for r in results.get("results", [])
    ]

    return json.dumps({
        "month":       month,
        "answer":      results.get("answer", ""),
        "results":     cleaned,
    }, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  TOOL 4 - search_competitor_content
#  Check what top food creators are posting
# ─────────────────────────────────────────────────────────────────────────────
@tool
def search_competitor_content(niche: str = "quick easy home cooking") -> str:
    """
    Search for recent content from popular food creators and food accounts
    to understand what's already saturated and where there are gaps.

    Args:
        niche: The cooking niche to analyse. The LLM fills this from context.

    Returns:
        JSON string with recent creator content and engagement signals.
    """
    client = _tavily_client()

    # We look at the last 7 days explicitly
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"food creator recipe content {niche} site:instagram.com OR site:tiktok.com OR site:youtube.com"

    results = client.search(
        query=query,
        search_depth="basic",
        max_results=6,
        include_answer=False,
    )

    cleaned = [
        {
            "title":   r.get("title", ""),
            "url":     r.get("url", ""),
            "content": r.get("content", "")[:400],
        }
        for r in results.get("results", [])
    ]

    return json.dumps({"niche": niche, "results": cleaned}, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
#  Exported list:
#      from tools.search_tools import TREND_TOOLS
# ─────────────────────────────────────────────────────────────────────────────
TREND_TOOLS = [
    search_trending_food_topics,
    search_social_media_food_trends,
    search_seasonal_ingredients,
    search_competitor_content,
]