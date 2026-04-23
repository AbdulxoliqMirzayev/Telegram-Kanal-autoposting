from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.sessions import SQLiteSession

from config import (
    HTTP_TIMEOUT,
    HTTP_USER_AGENT,
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_SOURCES,
    TELETHON_SESSION_PATH,
    USE_TELETHON,
)
from models import NewsArticle
from processor.dedup import create_content_hash, is_duplicate
from processor.formatter import detect_topics

logger = logging.getLogger(__name__)


async def fetch_latest() -> NewsArticle | None:
    if USE_TELETHON and TELEGRAM_API_ID and TELEGRAM_API_HASH:
        telethon_article = await _fetch_latest_telethon()
        if telethon_article:
            return telethon_article

    logger.info("Using public Telegram web scraping fallback for source channels.")
    return await _fetch_latest_public()


async def _fetch_latest_telethon() -> NewsArticle | None:
    session_path = await _resolve_authorized_session_path()
    if session_path is None:
        logger.warning(
            "Telethon is not authorized. Falling back to public t.me/s scraping. Expected session path: %s",
            TELETHON_SESSION_PATH,
        )
        return None

    candidates: list[NewsArticle] = []
    client = TelegramClient(
        SQLiteSession(str(session_path)),
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )
    await client.connect()
    try:
        if not await client.is_user_authorized():
            logger.warning(
                "Telethon session at %s is not authorized. Run `python setup_session.py` once.",
                session_path,
            )
            return None

        for source in TELEGRAM_SOURCES:
            channel = _normalize_channel(source)
            try:
                async for message in client.iter_messages(channel, limit=20):
                    text = _clean_text(message.message or message.text or "")
                    if len(text) < 25:
                        continue
                    article = _message_to_article(text, channel, message.id, message.date)
                    if article and not await is_duplicate(article.content_hash):
                        candidates.append(article)
                await asyncio.sleep(random.uniform(2.0, 3.0))
            except RPCError as exc:
                logger.warning("Telegram source failed channel=%s error=%s", channel, exc)
            except Exception as exc:
                logger.warning("Telegram source failed channel=%s error=%s", channel, exc)
    finally:
        await client.disconnect()

    candidates.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return candidates[0] if candidates else None


async def _fetch_latest_public() -> NewsArticle | None:
    candidates: list[NewsArticle] = []
    headers = {"User-Agent": HTTP_USER_AGENT}
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers=headers,
    ) as client:
        for source in TELEGRAM_SOURCES:
            channel = _normalize_channel(source)
            try:
                articles = await _fetch_public_channel(client, channel)
                candidates.extend(articles)
                await asyncio.sleep(random.uniform(1.0, 1.8))
            except Exception as exc:
                logger.warning("Public Telegram source failed channel=%s error=%s", channel, exc)

    candidates.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    for candidate in candidates:
        if not await is_duplicate(candidate.content_hash):
            return candidate
    return None


async def _fetch_public_channel(
    client: httpx.AsyncClient,
    channel: str,
) -> list[NewsArticle]:
    url = f"https://t.me/s/{channel}"
    response = await client.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    message_blocks = soup.select(".tgme_widget_message_wrap")[-20:]
    articles: list[NewsArticle] = []

    for block in message_blocks:
        message = block.select_one(".tgme_widget_message")
        text_node = block.select_one(".tgme_widget_message_text")
        if not message or not text_node:
            continue

        text = _clean_text(text_node.get_text("\n", strip=True))
        if len(text) < 25:
            continue

        post_url = str(message.get("data-post") or "")
        message_id = _message_id_from_data_post(post_url)
        published_at = _public_message_datetime(block)
        article = _message_to_article(text, channel, message_id, published_at)
        if article and not await is_duplicate(article.content_hash):
            articles.append(article)

    logger.info("Public Telegram channel=%s returned %s candidate(s).", channel, len(articles))
    return articles


async def _resolve_authorized_session_path() -> Path | None:
    candidates = [
        TELETHON_SESSION_PATH,
        TELETHON_SESSION_PATH.with_name("telethon.session"),
    ]
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        try:
            client = TelegramClient(
                SQLiteSession(str(path)),
                TELEGRAM_API_ID,
                TELEGRAM_API_HASH,
            )
            await client.connect()
        except Exception as exc:
            logger.warning("Telethon session %s could not be opened: %s", path, exc)
            continue
        try:
            if await client.is_user_authorized():
                if path != TELETHON_SESSION_PATH:
                    TELETHON_SESSION_PATH.write_bytes(path.read_bytes())
                    logger.info(
                        "Authorized legacy Telethon session migrated: %s -> %s",
                        path,
                        TELETHON_SESSION_PATH,
                    )
                return TELETHON_SESSION_PATH
        finally:
            await client.disconnect()
    return None


async def session_status() -> str:
    if not USE_TELETHON:
        return (
            "ℹ️ Telethon o'chirilgan.\n\n"
            "Hozir bot Telegram kanallarni login kodsiz public t.me/s sahifalari orqali o'qiydi.\n"
            "Agar user-session kerak bo'lsa .env ichida USE_TELETHON=true qiling va python setup_session.py ishlating."
        )

    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        return "❌ TELEGRAM_API_ID yoki TELEGRAM_API_HASH sozlanmagan."

    lines = ["🔐 Telethon session holati", ""]
    candidates = [
        TELETHON_SESSION_PATH,
        TELETHON_SESSION_PATH.with_name("telethon.session"),
    ]
    seen: set[Path] = set()
    any_authorized = False
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if not path.exists():
            lines.append(f"⚪ {path}: fayl yo'q")
            continue

        try:
            client = TelegramClient(
                SQLiteSession(str(path)),
                TELEGRAM_API_ID,
                TELEGRAM_API_HASH,
            )
            await client.connect()
            try:
                authorized = await client.is_user_authorized()
            finally:
                await client.disconnect()
        except Exception as exc:
            lines.append(f"⚠️ {path}: ochib bo'lmadi ({exc})")
            continue

        if authorized:
            any_authorized = True
            lines.append(f"✅ {path}: authorized")
        else:
            lines.append(f"❌ {path}: authorized emas")

    if not any_authorized:
        lines.extend(
            [
                "",
                "Yechim:",
                "1. Botni terminalda CTRL+C bilan to'xtating",
                "2. python setup_session.py ni ishga tushiring",
                "3. Telegramdan kelgan kodni kiriting",
                "4. python main.py ni qayta ishga tushiring",
            ]
        )
    return "\n".join(lines)


def _message_to_article(
    text: str,
    channel: str,
    message_id: int | str,
    published_at: datetime | None,
) -> NewsArticle | None:
    title, description = _split_message(text)
    topics = detect_topics(f"{title} {description}")
    if not topics:
        return None
    return NewsArticle(
        title_en=title,
        description=description or text[:500],
        source_name=f"Telegram:{channel}",
        source_type="telegram",
        source_url=f"https://t.me/{channel}/{message_id}" if channel and message_id else "",
        source_channel=channel,
        published_at=published_at,
        topic=topics[0],
        topics=topics,
        content_hash=create_content_hash(title),
    )


def _split_message(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else text[:140]
    if len(title) > 160:
        title = title[:160].rsplit(" ", maxsplit=1)[0]
    body = " ".join(lines[1:]) or text
    return title.strip(" -:"), body.strip()


def _clean_text(value: str) -> str:
    lines = [
        " ".join(line.split())
        for line in value.replace("\r", "\n").split("\n")
    ]
    return "\n".join(line for line in lines if line)


def _normalize_channel(channel: str) -> str:
    normalized = channel.strip()
    normalized = normalized.removeprefix("https://t.me/")
    normalized = normalized.removeprefix("http://t.me/")
    normalized = normalized.removeprefix("@")
    return normalized.strip("/")


def _message_id_from_data_post(value: str) -> str:
    if not value:
        return ""
    if "/" in value:
        return value.rsplit("/", maxsplit=1)[-1].strip()
    return ""


def _public_message_datetime(block: BeautifulSoup) -> datetime | None:
    time_tag = block.select_one("time")
    if not time_tag:
        return None
    raw_datetime = str(time_tag.get("datetime") or "")
    if not raw_datetime:
        return None
    try:
        parsed = datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
