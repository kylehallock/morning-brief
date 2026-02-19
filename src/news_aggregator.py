"""News aggregation from Google News RSS feeds."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser

from src.config import MDX_QUERIES

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published: datetime
    summary: str


def fetch_news(queries: list[str], max_results: int = 10, hours_back: int = 24) -> list[NewsItem]:
    """Fetch news items from Google News RSS for the given queries.

    Deduplicates by URL across queries, filters by pubDate, returns newest first.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    seen_urls = set()
    items = []

    for query in queries:
        url = GOOGLE_NEWS_RSS.format(query=quote(query))
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.warning(f"Failed to fetch RSS for query '{query[:50]}...': {e}")
            continue

        for entry in feed.get("entries", []):
            link = entry.get("link", "")
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Parse publication date
            published = _parse_pub_date(entry)
            if published is None or published < cutoff:
                continue

            # Extract source from title suffix " - SourceName" or source tag
            title = entry.get("title", "")
            source = ""
            source_tag = entry.get("source", {})
            if isinstance(source_tag, dict):
                source = source_tag.get("title", "")
            if not source and " - " in title:
                source = title.rsplit(" - ", 1)[-1]
                title = title.rsplit(" - ", 1)[0]

            summary = entry.get("summary", entry.get("description", ""))
            # Strip HTML tags from summary
            if "<" in summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()

            items.append(NewsItem(
                title=title,
                source=source,
                url=link,
                published=published,
                summary=summary,
            ))

    items.sort(key=lambda x: x.published, reverse=True)
    return items[:max_results]


def _parse_pub_date(entry: dict) -> datetime | None:
    """Parse publication date from RSS entry."""
    pub_date = entry.get("published", "")
    if not pub_date:
        return None
    try:
        return parsedate_to_datetime(pub_date)
    except Exception:
        return None


def fetch_diagnostics_news() -> list[NewsItem]:
    """Fetch molecular diagnostics news (TB-specific + broader MDx)."""
    return fetch_news(MDX_QUERIES, max_results=15)
