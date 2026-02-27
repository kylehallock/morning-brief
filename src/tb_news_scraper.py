"""TB tongue swab news scraper — monitors targeted sources for publications
and announcements about tongue swab tuberculosis testing.

Sources:
  - Google News RSS with tongue-swab-specific queries
  - Direct RSS feeds from TB-focused organizations and journals
  - PubMed E-utilities API for research publications
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import feedparser

from src.config import load_tb_sources

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_LINK = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

# Polite identification for NCBI E-utilities (recommended, not required)
PUBMED_TOOL = "morning-brief"
PUBMED_EMAIL = ""  # Set to a real email if you want NCBI to contact you on issues

# Reuse the same dataclass from news_aggregator to keep the pipeline uniform
from src.news_aggregator import NewsItem


def fetch_tb_news(hours_back: int = 72, max_results: int = 20) -> list[NewsItem]:
    """Fetch tongue swab TB news from all configured sources.

    Aggregates Google News, direct RSS feeds, and PubMed results.
    Deduplicates by URL, returns newest first, capped at max_results.
    """
    sources = load_tb_sources()
    all_items: list[NewsItem] = []

    # --- Google News RSS ---
    queries = sources.get("google_news_queries", [])
    if queries:
        try:
            items = _fetch_google_news(queries, hours_back)
            logger.info(f"  Google News: {len(items)} articles")
            all_items.extend(items)
        except Exception as e:
            logger.warning(f"Google News fetch failed: {e}")

    # --- Direct RSS feeds ---
    feeds = sources.get("rss_feeds", [])
    if feeds:
        try:
            items = _fetch_rss_feeds(feeds, hours_back)
            logger.info(f"  RSS feeds: {len(items)} articles")
            all_items.extend(items)
        except Exception as e:
            logger.warning(f"RSS feed fetch failed: {e}")

    # --- PubMed ---
    pubmed_queries = sources.get("pubmed_queries", [])
    if pubmed_queries:
        try:
            items = _fetch_pubmed(pubmed_queries, hours_back)
            logger.info(f"  PubMed: {len(items)} articles")
            all_items.extend(items)
        except Exception as e:
            logger.warning(f"PubMed fetch failed: {e}")

    # Deduplicate by URL, sort newest first
    seen_urls: set[str] = set()
    unique: list[NewsItem] = []
    for item in all_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique.append(item)

    unique.sort(key=lambda x: x.published, reverse=True)
    return unique[:max_results]


# ---------------------------------------------------------------------------
# Google News RSS
# ---------------------------------------------------------------------------

def _fetch_google_news(queries: list[str], hours_back: int) -> list[NewsItem]:
    """Fetch from Google News RSS with tongue-swab-specific queries."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    seen_urls: set[str] = set()
    items: list[NewsItem] = []

    for query in queries:
        url = GOOGLE_NEWS_RSS.format(query=quote(query))
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.warning(f"Google News RSS failed for '{query[:40]}': {e}")
            continue

        for entry in feed.get("entries", []):
            link = entry.get("link", "")
            if link in seen_urls:
                continue
            seen_urls.add(link)

            published = _parse_rss_date(entry)
            if published is None or published < cutoff:
                continue

            title = entry.get("title", "")
            source = ""
            source_tag = entry.get("source", {})
            if isinstance(source_tag, dict):
                source = source_tag.get("title", "")
            if not source and " - " in title:
                source = title.rsplit(" - ", 1)[-1]
                title = title.rsplit(" - ", 1)[0]

            summary = _strip_html(entry.get("summary", entry.get("description", "")))

            items.append(NewsItem(
                title=title,
                source=source,
                url=link,
                published=published,
                summary=summary,
            ))

    return items


# ---------------------------------------------------------------------------
# Direct RSS feeds
# ---------------------------------------------------------------------------

def _fetch_rss_feeds(feeds: list[dict], hours_back: int) -> list[NewsItem]:
    """Fetch from direct RSS feed URLs with optional keyword filtering."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    items: list[NewsItem] = []

    for feed_cfg in feeds:
        name = feed_cfg.get("name", "Unknown")
        url = feed_cfg.get("url", "")
        keywords = [k.lower() for k in feed_cfg.get("filter_keywords", [])]

        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.warning(f"RSS feed '{name}' failed: {e}")
            continue

        if feed.get("bozo") and not feed.get("entries"):
            logger.warning(f"RSS feed '{name}' returned no entries (bozo={feed.get('bozo_exception', 'unknown')})")
            continue

        for entry in feed.get("entries", []):
            published = _parse_rss_date(entry)
            if published is None or published < cutoff:
                continue

            title = entry.get("title", "")
            summary = _strip_html(entry.get("summary", entry.get("description", "")))

            # Keyword filtering: if keywords specified, at least one must appear
            if keywords:
                text = f"{title} {summary}".lower()
                if not any(kw in text for kw in keywords):
                    continue

            link = entry.get("link", "")

            items.append(NewsItem(
                title=title,
                source=name,
                url=link,
                published=published,
                summary=summary,
            ))

    return items


# ---------------------------------------------------------------------------
# PubMed E-utilities
# ---------------------------------------------------------------------------

def _fetch_pubmed(queries: list[str], hours_back: int) -> list[NewsItem]:
    """Fetch recent publications from PubMed using E-utilities (esearch + efetch).

    Uses only stdlib (urllib + xml.etree) — no extra dependencies needed.
    Docs: https://www.ncbi.nlm.nih.gov/books/NBK25499/
    """
    days_back = max(1, hours_back // 24)
    all_pmids: set[str] = set()

    # Step 1: Search for article IDs across all queries
    for query in queries:
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": "20",
            "datetype": "edat",
            "reldate": str(days_back),
            "retmode": "xml",
            "sort": "date",
            "tool": PUBMED_TOOL,
        }
        if PUBMED_EMAIL:
            params["email"] = PUBMED_EMAIL

        url = f"{PUBMED_SEARCH_URL}?{urlencode(params)}"
        try:
            req = Request(url, headers={"User-Agent": "morning-brief/1.0"})
            with urlopen(req, timeout=15) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for id_elem in root.iter("Id"):
                if id_elem.text:
                    all_pmids.add(id_elem.text.strip())
        except Exception as e:
            logger.warning(f"PubMed search failed for '{query[:40]}': {e}")
            continue

    if not all_pmids:
        return []

    # Step 2: Fetch article details
    pmid_list = ",".join(sorted(all_pmids))
    params = {
        "db": "pubmed",
        "id": pmid_list,
        "retmode": "xml",
        "tool": PUBMED_TOOL,
    }
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL

    url = f"{PUBMED_FETCH_URL}?{urlencode(params)}"
    try:
        req = Request(url, headers={"User-Agent": "morning-brief/1.0"})
        with urlopen(req, timeout=30) as resp:
            xml_data = resp.read()
    except Exception as e:
        logger.warning(f"PubMed fetch failed: {e}")
        return []

    return _parse_pubmed_xml(xml_data)


def _parse_pubmed_xml(xml_data: bytes) -> list[NewsItem]:
    """Parse PubMed efetch XML into NewsItem objects."""
    items: list[NewsItem] = []

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        logger.warning(f"PubMed XML parse error: {e}")
        return []

    for article in root.iter("PubmedArticle"):
        try:
            # Extract PMID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text.strip() if pmid_elem is not None and pmid_elem.text else ""
            if not pmid:
                continue

            # Extract title
            title_elem = article.find(".//ArticleTitle")
            title = _text_content(title_elem) if title_elem is not None else ""
            if not title:
                continue

            # Extract journal name
            journal_elem = article.find(".//Journal/Title")
            journal = journal_elem.text.strip() if journal_elem is not None and journal_elem.text else "PubMed"

            # Extract publication date
            pub_date = _parse_pubmed_date(article)

            # Extract abstract (first 300 chars)
            abstract_parts = []
            for abs_text in article.iter("AbstractText"):
                if abs_text.text:
                    abstract_parts.append(abs_text.text.strip())
            abstract = " ".join(abstract_parts)[:300]

            items.append(NewsItem(
                title=title,
                source=journal,
                url=PUBMED_LINK.format(pmid=pmid),
                published=pub_date,
                summary=abstract,
            ))
        except Exception as e:
            logger.warning(f"Failed to parse PubMed article: {e}")
            continue

    return items


def _parse_pubmed_date(article: ET.Element) -> datetime:
    """Extract publication date from a PubmedArticle element."""
    # Try PubMedPubDate with pubstatus="pubmed" first, then ArticleDate
    for date_elem in article.iter("PubMedPubDate"):
        if date_elem.get("PubStatus") == "pubmed":
            return _extract_date_parts(date_elem)

    date_elem = article.find(".//ArticleDate")
    if date_elem is not None:
        return _extract_date_parts(date_elem)

    # Fallback to epoch if no date found
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _extract_date_parts(elem: ET.Element) -> datetime:
    """Extract year/month/day from an XML element with Year/Month/Day children."""
    year = int(elem.findtext("Year", "1970"))
    month = int(elem.findtext("Month", "1"))
    day = int(elem.findtext("Day", "1"))
    return datetime(year, month, day, tzinfo=timezone.utc)


def _text_content(elem: ET.Element) -> str:
    """Get all text content from an element, including tail text of children."""
    return "".join(elem.itertext()).strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_rss_date(entry: dict) -> datetime | None:
    """Parse publication date from an RSS entry."""
    pub_date = entry.get("published", "")
    if not pub_date:
        pub_date = entry.get("updated", "")
    if not pub_date:
        return None
    try:
        return parsedate_to_datetime(pub_date)
    except Exception:
        # Try ISO format as fallback (some Atom feeds use it)
        try:
            return datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
        except Exception:
            return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    if "<" in text:
        return re.sub(r"<[^>]+>", "", text).strip()
    return text
