from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError

from config import CHANNEL_IDS, POST_SCHEDULE, TIMEZONE
from database.db import cleanup_old_records, get_today_post_override
from processor import dedup, formatter, translator
from scrapers import telegram_scraper, web_scraper

logger = logging.getLogger(__name__)
ACTIVE_POST_SCHEDULE = list(POST_SCHEDULE)

SOURCE_LABELS = {
    "web": "🌐 Web sahifalar",
    "telegram": "📣 Telegram kanallar",
}


async def run_post_job(post_type: str, bot: Bot | None = None) -> bool:
    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        logger.info("Post attempt started timestamp=%s source_type=%s", started_at, post_type)
        news = await _select_news_with_fallback(post_type)

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

        sent_channels = await _send_to_channels(bot, formatted, news.image_url)
        if not sent_channels:
            logger.warning(
                "Post attempt failed timestamp=%s source_type=%s reason=no_target_channel_sent",
                started_at,
                post_type,
            )
            return False

        await dedup.mark_as_posted(news)
        logger.info(
            "Post attempt succeeded timestamp=%s channels=%s source=%s topic=%s title=%s",
            started_at,
            ",".join(sent_channels),
            news.source,
            ",".join(news.topics) or news.topic,
            news.title_en[:80],
        )
        return True
    except Exception as exc:
        if isinstance(exc, Forbidden):
            logger.error(
                "Post attempt failed timestamp=%s source_type=%s reason=channel_permission error=%s. "
                "Botni target kanallarga admin qilib qo'shing va Post Messages ruxsatini yoqing.",
                started_at,
                post_type,
                exc,
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


async def _select_news_with_fallback(post_type: str):
    if post_type == "web":
        return await web_scraper.fetch_latest()

    telegram_news = await telegram_scraper.fetch_latest()
    if telegram_news:
        return telegram_news

    logger.warning(
        "Telegram source yielded no usable news. Falling back to web sources for this slot."
    )
    return await web_scraper.fetch_latest()


async def _send_to_channels(bot: Bot, text: str, image_url: str = "") -> list[str]:
    sent_channels: list[str] = []
    for channel_id in CHANNEL_IDS:
        try:
            await _send_single_channel_post(bot, channel_id, text, image_url)
            sent_channels.append(channel_id)
        except Forbidden as exc:
            logger.warning(
                "Target channel skipped channel=%s reason=permission error=%s",
                channel_id,
                exc,
            )
        except TelegramError as exc:
            logger.warning(
                "Target channel skipped channel=%s reason=telegram_error error=%s",
                channel_id,
                exc,
            )
    return sent_channels


async def _send_single_channel_post(
    bot: Bot,
    channel_id: str,
    text: str,
    image_url: str = "",
) -> None:
    if not image_url:
        await bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    try:
        if len(text) <= 1024:
            await bot.send_photo(
                chat_id=channel_id,
                photo=image_url,
                caption=text,
                parse_mode=ParseMode.HTML,
            )
        else:
            await bot.send_photo(chat_id=channel_id, photo=image_url)
            await bot.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
    except TelegramError as exc:
        logger.warning(
            "Image delivery failed channel=%s image_url=%s error=%s. Falling back to text-only post.",
            channel_id,
            image_url,
            exc,
        )
        await bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def cleanup_job() -> None:
    deleted = await cleanup_old_records(days=30)
    logger.info("Dedup cleanup complete deleted_records=%s", deleted)


def setup_scheduler(bot: Bot | None = None) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
    _add_post_jobs(scheduler, bot, ACTIVE_POST_SCHEDULE)
    scheduler.add_job(
        cleanup_job,
        CronTrigger(hour=3, minute=0),
        id="cleanup_old_records",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler


def _add_post_jobs(
    scheduler: AsyncIOScheduler,
    bot: Bot | None,
    schedule: list[tuple[str, str]],
) -> None:
    for time_str, post_type in schedule:
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


async def apply_today_schedule_override(
    scheduler: AsyncIOScheduler,
    bot: Bot | None = None,
    count: int | None = None,
) -> list[tuple[str, str]]:
    global ACTIVE_POST_SCHEDULE
    if count is None:
        count = await get_today_post_override(TIMEZONE)
    ACTIVE_POST_SCHEDULE = generate_post_schedule(count) if count else list(POST_SCHEDULE)

    for job in list(scheduler.get_jobs()):
        if job.id.startswith("post_"):
            scheduler.remove_job(job.id)
    _add_post_jobs(scheduler, bot, ACTIVE_POST_SCHEDULE)
    logger.info("Post schedule updated:\n%s", format_schedule_message())
    return ACTIVE_POST_SCHEDULE


def generate_post_schedule(count: int) -> list[tuple[str, str]]:
    if count < 1 or count > 24:
        raise ValueError("Post count must be between 1 and 24.")
    start_minutes = 8 * 60 + 8
    end_minutes = 21 * 60 + 21
    if count == 1:
        minutes = [start_minutes]
    else:
        step = (end_minutes - start_minutes) / (count - 1)
        minutes = [round(start_minutes + step * index) for index in range(count)]
    schedule: list[tuple[str, str]] = []
    for index, minute_value in enumerate(minutes):
        hour = minute_value // 60
        minute = minute_value % 60
        post_type = "web" if index % 2 == 0 else "telegram"
        schedule.append((f"{hour:02d}:{minute:02d}", post_type))
    return schedule


def next_scheduled_post(now: datetime | None = None) -> tuple[str, str]:
    tz = pytz.timezone(TIMEZONE)
    current = now.astimezone(tz) if now else datetime.now(tz)
    upcoming: list[tuple[datetime, str, str]] = []
    for time_str, post_type in ACTIVE_POST_SCHEDULE:
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
    for index, (time_str, post_type) in enumerate(ACTIVE_POST_SCHEDULE, start=1):
        lines.append(f"{index}. 🕐 {time_str}  →  {SOURCE_LABELS.get(post_type, post_type)}")
    lines.extend(
        [
            "",
            f"✅ Bugungi reja: {len(ACTIVE_POST_SCHEDULE)} ta post",
            "🔁 Har slotda eng oxirgi mos yangilik olinadi",
            "🚫 Duplicate va forex/valyuta kursi mavzulari bloklanadi",
        ]
    )
    return "\n".join(lines)


def active_post_count() -> int:
    return len(ACTIVE_POST_SCHEDULE)
