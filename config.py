from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _as_int(value: str | None, default: int = 0) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _admin_ids(value: str | None) -> set[int]:
    ids: set[int] = set()
    for raw_id in _split_csv(value):
        try:
            ids.add(int(raw_id))
        except ValueError:
            continue
    return ids


def _source_name_from_url(url: str) -> str:
    lowered = url.lower()
    if "tradingview" in lowered:
        return "TradingView"
    if "webull" in lowered:
        return "Webull"
    if "yahoo" in lowered:
        return "Yahoo Finance"
    if "investing" in lowered:
        return "Investing.com"
    host = lowered.split("//", maxsplit=1)[-1].split("/", maxsplit=1)[0]
    return host.replace("www.", "").split(".", maxsplit=1)[0].title()


def _web_sources_from_env(value: str | None) -> list[dict[str, str]]:
    urls = _split_csv(value)
    return [{"url": url, "type": _source_name_from_url(url)} for url in urls]


def _post_schedule_from_env(value: str | None) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in _split_csv(value):
        try:
            time_text, source_type = item.rsplit(":", maxsplit=1)
        except ValueError:
            continue
        source_type = source_type.strip().lower()
        if source_type not in {"web", "telegram"}:
            continue
        hour, minute = time_text.split(":", maxsplit=1)
        if not (hour.isdigit() and minute.isdigit()):
            continue
        pairs.append((f"{int(hour):02d}:{int(minute):02d}", source_type))
    return pairs


DATA_DIR = Path(os.getenv("DATA_DIR") or os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or "data")
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "posted_news.sqlite3")))
TELETHON_SESSION_PATH = Path(
    os.getenv("TELETHON_SESSION_PATH", str(DATA_DIR / "session.session"))
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
CHANNEL_IDS = _split_csv(os.getenv("TELEGRAM_CHANNEL_IDS")) or ([CHANNEL_ID] if CHANNEL_ID else [])
TELEGRAM_API_ID = _as_int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent").strip() or "Asia/Tashkent"
ADMIN_USER_IDS = _admin_ids(os.getenv("ADMIN_USER_IDS"))
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "20"))
USE_TELETHON = os.getenv("USE_TELETHON", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
HTTP_USER_AGENT = os.getenv(
    "HTTP_USER_AGENT",
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
)

DEFAULT_POST_SCHEDULE = [
    ("08:08", "web"),
    ("10:10", "telegram"),
    ("12:12", "telegram"),
    ("13:13", "web"),
    ("15:15", "web"),
    ("17:17", "telegram"),
    ("19:19", "web"),
    ("21:21", "telegram"),
]

DEFAULT_TELEGRAM_SOURCES = [
    "ReutersBusiness",
    "Bloomberg",
    "coindesk",
    "investing_com",
    "cointelegraph",
    "FT_Markets",
]

DEFAULT_WEB_SOURCES = [
    {"url": "https://www.tradingview.com/news/", "type": "TradingView"},
    {"url": "https://www.webullapp.com/news", "type": "Webull"},
    {"url": "https://finance.yahoo.com/news/rssindex", "type": "Yahoo Finance"},
    {"url": "https://www.investing.com/rss/news_25.rss", "type": "Investing.com"},
    {"url": "https://www.investing.com/rss/news_95.rss", "type": "Investing.com"},
    {"url": "https://www.investing.com/rss/news_14.rss", "type": "Investing.com"},
]

TELEGRAM_SOURCES = _split_csv(os.getenv("TELEGRAM_SOURCE_CHANNELS")) or DEFAULT_TELEGRAM_SOURCES
WEB_SOURCES = _web_sources_from_env(os.getenv("WEB_SOURCE_URLS")) or DEFAULT_WEB_SOURCES
POST_SCHEDULE = _post_schedule_from_env(os.getenv("POST_SCHEDULE")) or DEFAULT_POST_SCHEDULE
SCHEDULE = [time_text for time_text, _source_type in POST_SCHEDULE]


def timezone() -> ZoneInfo:
    return ZoneInfo(TIMEZONE)


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    TELETHON_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)


def validate_required_env() -> None:
    missing: list[str] = []
    if not BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not CHANNEL_IDS:
        missing.append("TELEGRAM_CHANNEL_ID or TELEGRAM_CHANNEL_IDS")
    if USE_TELETHON and not TELEGRAM_API_ID:
        missing.append("TELEGRAM_API_ID")
    if USE_TELETHON and not TELEGRAM_API_HASH:
        missing.append("TELEGRAM_API_HASH")
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
