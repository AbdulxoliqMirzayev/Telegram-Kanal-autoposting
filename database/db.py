from __future__ import annotations

import sqlite3
import json
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

CREATE_APP_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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


async def get_setting(key: str, default: str = "") -> str:
    row = await fetchone("SELECT value FROM app_settings WHERE key = ?", (key,))
    return str(row["value"]) if row else default


async def set_setting(key: str, value: str) -> None:
    await execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )


async def get_json_setting(key: str, default: Any) -> Any:
    raw = await get_setting(key, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


async def set_json_setting(key: str, value: Any) -> None:
    await set_setting(key, json.dumps(value, ensure_ascii=False))


async def get_telegram_sources(default_sources: list[str]) -> list[str]:
    sources = await get_json_setting("telegram_sources", default_sources)
    if not isinstance(sources, list):
        return default_sources
    cleaned = [str(item).strip() for item in sources if str(item).strip()]
    return cleaned or default_sources


async def add_telegram_source(source: str, default_sources: list[str]) -> list[str]:
    normalized = normalize_telegram_source(source)
    if not normalized:
        raise ValueError("Telegram kanal username yoki link noto'g'ri.")
    sources = await get_telegram_sources(default_sources)
    if normalized not in sources:
        sources.append(normalized)
        await set_json_setting("telegram_sources", sources)
    return sources


async def get_today_post_override(tz_name: str) -> int | None:
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(tz_name)).date().isoformat()
    payload = await get_json_setting("today_post_override", {})
    if not isinstance(payload, dict) or payload.get("date") != today:
        return None
    try:
        count = int(payload.get("count"))
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


async def set_today_post_override(count: int, tz_name: str) -> None:
    from zoneinfo import ZoneInfo

    if count < 1 or count > 24:
        raise ValueError("Post soni 1 dan 24 gacha bo'lishi kerak.")
    today = datetime.now(ZoneInfo(tz_name)).date().isoformat()
    await set_json_setting("today_post_override", {"date": today, "count": count})


def normalize_telegram_source(source: str) -> str:
    value = source.strip()
    value = value.removeprefix("https://t.me/")
    value = value.removeprefix("http://t.me/")
    value = value.removeprefix("@")
    value = value.strip("/")
    if not value or " " in value:
        return ""
    return f"https://t.me/{value}"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _init_db_sync() -> None:
    with _connect() as connection:
        connection.execute(CREATE_POSTED_NEWS_TABLE)
        connection.execute(CREATE_APP_SETTINGS_TABLE)
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
