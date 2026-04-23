from __future__ import annotations

import hashlib

from database import db
from models import NewsArticle


def create_content_hash(title: str) -> str:
    normalized = title.lower().strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def is_duplicate(content_hash: str) -> bool:
    row = await db.fetchone(
        "SELECT id FROM posted_news WHERE content_hash = ? LIMIT 1",
        (content_hash,),
    )
    return row is not None


async def mark_as_posted(news: NewsArticle) -> None:
    await db.execute(
        """
        INSERT OR IGNORE INTO posted_news
            (content_hash, source_url, source_channel, topic, title_en)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            news.content_hash,
            news.source_url,
            news.source_channel,
            ",".join(news.topics) or news.topic,
            news.title_en,
        ),
    )
