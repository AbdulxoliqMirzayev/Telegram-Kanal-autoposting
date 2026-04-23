from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import Forbidden

from config import CHANNEL_ID, POST_SCHEDULE, TIMEZONE
from database.db import cleanup_old_records
from processor import dedup, formatter, translator
from scrapers import telegram_scraper, web_scraper

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "web": "🌐 Web sahifalar",
    "telegram": "📣 Telegram kanallar",
}


async def run_post_job(post_type: str, bot: Bot | None = None) -> bool:
    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        logger.info("Post attempt started timestamp=%s source_type=%s", started_at, post_type)
        if post_type == "web":
            news = await web_scraper.fetch_latest()
        else:
            news = await telegram_scraper.fetch_latest()

        if not news:
            logger.warning("Post attempt skipped timestamp=%s source_type=%s reason=no_news", started_at, post_type)
            return False

        if await dedup.is_duplicate(news.content_hash):
            logger.info(
                "Post attempt skipped timestamp=%s source=%s topic=%s reason=duplicate title=%s",
                started_at,
                news.source,
                news.topic,
                news.title_en[:80],
            )
            return False

        translated = await translator.translate(news)
        formatted = formatter.format_post(translated, news)
        if bot is None:
            raise RuntimeError("Telegram bot instance is not available for posting.")

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=formatted,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        await dedup.mark_as_posted(news)
        logger.info(
            "Post attempt succeeded timestamp=%s source=%s topic=%s title=%s",
            started_at,
            news.source,
            ",".join(news.topics) or news.topic,
            news.title_en[:80],
        )
        return True
    except Exception as exc:
        if isinstance(exc, Forbidden):
            logger.error(
                "Post attempt failed timestamp=%s source_type=%s reason=channel_permission error=%s. "
                "Botni %s kanaliga admin qilib qo'shing va Post Messages ruxsatini yoqing.",
                started_at,
                post_type,
                exc,
                CHANNEL_ID,
            )
            return False
        logger.error(
            "Post attempt failed timestamp=%s source_type=%s error=%s",
            started_at,
            post_type,
            exc,
            exc_info=True,
        )
        return False


async def cleanup_job() -> None:
    deleted = await cleanup_old_records(days=30)
    logger.info("Dedup cleanup complete deleted_records=%s", deleted)


def setup_scheduler(bot: Bot | None = None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
    for time_str, post_type in POST_SCHEDULE:
        hour, minute = time_str.split(":", maxsplit=1)
        scheduler.add_job(
            run_post_job,
            CronTrigger(hour=int(hour), minute=int(minute)),
            args=[post_type, bot],
            id=f"post_{time_str}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=900,
        )
    scheduler.add_job(
        cleanup_job,
        CronTrigger(hour=3, minute=0),
        id="cleanup_old_records",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler


def next_scheduled_post(now: datetime | None = None) -> tuple[str, str]:
    tz = pytz.timezone(TIMEZONE)
    current = now.astimezone(tz) if now else datetime.now(tz)
    upcoming: list[tuple[datetime, str, str]] = []
    for time_str, post_type in POST_SCHEDULE:
        hour, minute = [int(part) for part in time_str.split(":", maxsplit=1)]
        run_at = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_at <= current:
            run_at += timedelta(days=1)
        upcoming.append((run_at, time_str, post_type))
    run_at, time_str, post_type = min(upcoming, key=lambda item: item[0])
    day_label = "bugun" if run_at.date() == current.date() else "ertaga"
    return f"{day_label} {time_str}", post_type


def format_schedule_message() -> str:
    lines = [
        "📅 Avtomatik post jadvali",
        f"🕒 Timezone: {TIMEZONE}",
        "",
    ]
    for index, (time_str, post_type) in enumerate(POST_SCHEDULE, start=1):
        lines.append(f"{index}. 🕐 {time_str}  →  {SOURCE_LABELS.get(post_type, post_type)}")
    lines.extend(
        [
            "",
            "✅ Kuniga 8 ta post: 4 ta Web, 4 ta Telegram",
            "🔁 Har slotda eng oxirgi mos yangilik olinadi",
            "🚫 Duplicate va forex/valyuta kursi mavzulari bloklanadi",
        ]
    )
    return "\n".join(lines)
