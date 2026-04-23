from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from config import HTTP_TIMEOUT, HTTP_USER_AGENT, WEB_SOURCES
from models import NewsArticle
from processor.dedup import create_content_hash, is_duplicate
from processor.formatter import detect_topics

logger = logging.getLogger(__name__)


async def fetch_latest() -> NewsArticle | None:
    candidates: list[NewsArticle] = []
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": HTTP_USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    ) as client:
        for source in WEB_SOURCES:
            source_candidates = await _fetch_source_candidates(client, source)
            candidates.extend(source_candidates)

    candidates.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    for candidate in candidates:
        if not await is_duplicate(candidate.content_hash):
            return candidate
    return None


async def _fetch_source_candidates(
    client: httpx.AsyncClient, source: dict[str, str]
) -> list[NewsArticle]:
    url = source["url"]
    source_name = source["type"].title()
    for attempt in range(3):
        try:
            response = await client.get(url)
            response.raise_for_status()
            feed_articles = _articles_from_feed(response.text, url, source_name)
            if feed_articles:
                return feed_articles

            soup = BeautifulSoup(response.text, "lxml")
            urls = _extract_article_urls(soup, url)
            articles: list[NewsArticle] = []
            for article_url in urls[:10]:
                article = await _fetch_article(client, article_url, source_name)
                if article:
                    articles.append(article)
            if not articles:
                fallback = _article_from_soup(soup, url, source_name)
                if fallback:
                    articles.append(fallback)
            return articles
        except Exception as exc:
            logger.warning(
                "Web source failed source=%s attempt=%s error=%s",
                source_name,
                attempt + 1,
                exc,
            )
            await asyncio.sleep(2**attempt)
    return []


async def _fetch_article(
    client: httpx.AsyncClient, url: str, source_name: str
) -> NewsArticle | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception as exc:
        logger.debug("Article fetch skipped url=%s error=%s", url, exc)
        return None
    soup = BeautifulSoup(response.text, "lxml")
    return _article_from_soup(soup, url, source_name)


def _article_from_soup(soup: BeautifulSoup, url: str, source_name: str) -> NewsArticle | None:
    title = _first_meta(
        soup,
        ["og:title", "twitter:title"],
        ["headline"],
    ) or _first_text(soup, ["h1", "title"])
    description = _first_meta(
        soup,
        ["og:description", "twitter:description", "description"],
        [],
    ) or _paragraph_summary(soup)
    published = _parse_datetime(
        _first_meta(
            soup,
            ["article:published_time", "datePublished", "pubdate"],
            ["datePublished"],
        )
    )

    title = _clean_title(title, source_name)
    description = " ".join((description or "").split())
    if len(title) < 12:
        return None

    topics = detect_topics(f"{title} {description}")
    if not topics:
        return None

    content_hash = create_content_hash(title)
    return NewsArticle(
        title_en=title,
        description=description or title,
        source_name=source_name,
        source_type="web",
        source_url=url,
        published_at=published,
        topic=topics[0],
        topics=topics,
        content_hash=content_hash,
    )


def _articles_from_feed(text: str, base_url: str, source_name: str) -> list[NewsArticle]:
    if "<rss" not in text[:500].lower() and "<feed" not in text[:500].lower():
        return []

    soup = BeautifulSoup(text, "xml")
    entries = soup.find_all("item") or soup.find_all("entry")
    articles: list[NewsArticle] = []
    for entry in entries[:30]:
        title = _tag_text(entry, "title")
        link = _feed_link(entry, base_url)
        description = (
            _tag_text(entry, "description")
            or _tag_text(entry, "summary")
            or _tag_text(entry, "content")
            or title
        )
        published = _parse_datetime(
            _tag_text(entry, "pubDate")
            or _tag_text(entry, "published")
            or _tag_text(entry, "updated")
        )
        article = _article_from_values(
            title=title,
            description=_strip_html(description),
            url=link,
            source_name=source_name,
            published=published,
        )
        if article:
            articles.append(article)
    return articles


def _article_from_values(
    *,
    title: str,
    description: str,
    url: str,
    source_name: str,
    published: datetime | None,
) -> NewsArticle | None:
    title = _clean_title(title, source_name)
    description = " ".join((description or "").split())
    if len(title) < 12:
        return None

    topics = detect_topics(f"{title} {description}")
    if not topics:
        return None

    return NewsArticle(
        title_en=title,
        description=description or title,
        source_name=source_name,
        source_type="web",
        source_url=url,
        published_at=published,
        topic=topics[0],
        topics=topics,
        content_hash=create_content_hash(title),
    )


def _tag_text(entry: BeautifulSoup, tag_name: str) -> str:
    tag = entry.find(tag_name)
    return tag.get_text(" ", strip=True) if tag else ""


def _strip_html(value: str) -> str:
    if "<" not in value or ">" not in value:
        return value.strip()
    return BeautifulSoup(value, "lxml").get_text(" ", strip=True)


def _feed_link(entry: BeautifulSoup, base_url: str) -> str:
    link = entry.find("link")
    if not link:
        return base_url
    href = link.get("href")
    if href:
        return urljoin(base_url, str(href))
    return urljoin(base_url, link.get_text(" ", strip=True))


def _extract_article_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    base_host = urlparse(base_url).netloc.replace("www.", "")
    urls: list[str] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = str(link.get("href", "")).strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        absolute = urljoin(base_url, href).split("#", maxsplit=1)[0]
        parsed = urlparse(absolute)
        host = parsed.netloc.replace("www.", "")
        if base_host not in host and host not in base_host:
            continue
        if absolute in seen or not _looks_like_article(parsed.path):
            continue
        urls.append(absolute)
        seen.add(absolute)
    return urls


def _looks_like_article(path: str) -> bool:
    lowered = path.lower()
    if any(skip in lowered for skip in ("/video/", "/live-tv/", "/quotes/")):
        return False
    return any(
        part in lowered
        for part in (
            "/news/",
            "/news-detail/",
            "/article/",
            "/business/",
            "/finance/",
            "/stock-market-news/",
            "/economy/",
        )
    )


def _first_meta(soup: BeautifulSoup, properties: list[str], itemprops: list[str]) -> str:
    for prop in properties:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
    for prop in itemprops:
        tag = soup.find(attrs={"itemprop": prop})
        if tag:
            if tag.get("content"):
                return str(tag["content"]).strip()
            return tag.get_text(" ", strip=True)
    return ""


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            return tag.get_text(" ", strip=True)
    return ""


def _paragraph_summary(soup: BeautifulSoup) -> str:
    paragraphs = [
        paragraph.get_text(" ", strip=True)
        for paragraph in soup.find_all("p")
        if len(paragraph.get_text(" ", strip=True)) > 40
    ]
    return " ".join(paragraphs[:3])


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clean_title(title: str, source_name: str) -> str:
    cleaned = " ".join((title or "").split())
    for separator in (" | ", " - "):
        suffix = f"{separator}{source_name}"
        if cleaned.lower().endswith(suffix.lower()):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned
