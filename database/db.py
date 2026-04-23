from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from config import DB_PATH


CREATE_POSTED_NEWS_TABLE = """
CREATE TABLE IF NOT EXISTS posted_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT UNIQUE NOT NULL,
    source_url TEXT,
    source_channel TEXT,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    topic TEXT,
    title_en TEXT
);
"""


async def init_db() -> None:
    _init_db_sync()


async def execute(query: str, params: tuple = ()) -> None:
    _execute_sync(query, params)


async def fetchone(query: str, params: tuple = ()) -> dict[str, Any] | None:
    return _fetchone_sync(query, params)


async def fetchall(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    return _fetchall_sync(query, params)


async def count_posts_today(tz_name: str) -> int:
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo(tz_name))
    start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    row = await fetchone(
        """
        SELECT COUNT(*) AS count
        FROM posted_news
        WHERE posted_at >= ? AND posted_at < ?
        """,
        (start_utc.isoformat(sep=" "), end_utc.isoformat(sep=" ")),
    )
    return int(row["count"]) if row else 0


async def cleanup_old_records(days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return _cleanup_old_records_sync(cutoff)


async def topic_stats(tz_name: str) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo(tz_name))
    start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)

    all_rows = await fetchall("SELECT topic FROM posted_news")
    today_rows = await fetchall(
        """
        SELECT topic
        FROM posted_news
        WHERE posted_at >= ? AND posted_at < ?
        """,
        (start_utc.isoformat(sep=" "), end_utc.isoformat(sep=" ")),
    )

    return {
        "total_posts": len(all_rows),
        "today_posts": len(today_rows),
        "topics_total": _count_topics(all_rows),
        "topics_today": _count_topics(today_rows),
    }


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _init_db_sync() -> None:
    with _connect() as connection:
        connection.execute(CREATE_POSTED_NEWS_TABLE)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_posted_news_posted_at ON posted_news(posted_at)"
        )
        connection.commit()


def _execute_sync(query: str, params: tuple = ()) -> None:
    with _connect() as connection:
        connection.execute(query, params)
        connection.commit()


def _fetchone_sync(query: str, params: tuple = ()) -> dict[str, Any] | None:
    with _connect() as connection:
        cursor = connection.execute(query, params)
        row = cursor.fetchone()
    return dict(row) if row else None


def _fetchall_sync(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with _connect() as connection:
        cursor = connection.execute(query, params)
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def _cleanup_old_records_sync(cutoff: datetime) -> int:
    with _connect() as connection:
        cursor = connection.execute(
            "DELETE FROM posted_news WHERE posted_at < ?",
            (cutoff.replace(tzinfo=None).isoformat(sep=" "),),
        )
        connection.commit()
        return int(cursor.rowcount or 0)


def _count_topics(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        raw_topic = str(row.get("topic") or "").strip()
        if not raw_topic:
            continue
        for topic in [part.strip() for part in raw_topic.split(",") if part.strip()]:
            counts[topic] = counts.get(topic, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
