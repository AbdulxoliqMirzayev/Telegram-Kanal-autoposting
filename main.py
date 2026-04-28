from __future__ import annotations

import asyncio
import logging
import signal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    ADMIN_USER_IDS,
    BOT_TOKEN,
    CHANNEL_IDS,
    TELEGRAM_SOURCES,
    WEB_SOURCES,
    TIMEZONE,
    ensure_runtime_dirs,
    validate_required_env,
)
from database.db import (
    add_telegram_source,
    count_posts_today,
    get_telegram_sources,
    init_db,
    set_today_post_override,
    topic_stats,
)
from scheduler import (
    active_post_count,
    apply_today_schedule_override,
    format_schedule_message,
    next_scheduled_post,
    run_post_job,
    setup_scheduler,
)
from scrapers.telegram_scraper import session_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TOPIC_LABELS = {
    "crypto": "🪙 Crypto",
    "aksiya": "📈 Aksiya",
    "trump": "🇺🇸 Trump",
    "dollar": "💵 Dollar/Fed",
    "iqtisodiyot": "🌐 Iqtisodiyot",
    "neft": "🛢 Neft",
    "oltin": "🥇 Oltin",
}

SOURCE_TYPE_LABELS = {
    "web": "🌐 Web",
    "telegram": "📣 Telegram",
}

MENU_CALLBACK = "menu:main"
TEST_MENU_CALLBACK = "menu:test"
STATS_CALLBACK = "menu:stats"
SCHEDULE_CALLBACK = "menu:schedule"
POST_COUNT_CALLBACK = "menu:post_count"
ADD_SOURCE_CALLBACK = "menu:add_source"
BACK_CALLBACK = "menu:back"
TEST_WEB_CALLBACK = "test:web"
TEST_TELEGRAM_CALLBACK = "test:telegram"


def is_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in ADMIN_USER_IDS)


def main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🧪 Test post", callback_data=TEST_MENU_CALLBACK),
                InlineKeyboardButton("📅 Jadval", callback_data=SCHEDULE_CALLBACK),
            ],
            [
                InlineKeyboardButton("📊 Statistika", callback_data=STATS_CALLBACK),
            ],
            [
                InlineKeyboardButton("🔢 Bugungi post soni", callback_data=POST_COUNT_CALLBACK),
                InlineKeyboardButton("➕ Source kanal", callback_data=ADD_SOURCE_CALLBACK),
            ],
        ]
    )


def back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Orqaga", callback_data=BACK_CALLBACK)]]
    )


def test_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 Web post", callback_data=TEST_WEB_CALLBACK),
                InlineKeyboardButton("📣 Telegram post", callback_data=TEST_TELEGRAM_CALLBACK),
            ],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data=BACK_CALLBACK)],
        ]
    )


def panel_message(today_count: int) -> str:
    next_time, post_type = next_scheduled_post()
    planned_count = active_post_count()
    return (
        "🤖 <b>Telegram News Bot Panel</b>\n\n"
        f"📌 Bugungi postlar: <b>{today_count}/{planned_count}</b>\n"
        f"⏭ Keyingi post: <b>{next_time}</b> ({SOURCE_TYPE_LABELS.get(post_type, post_type)})\n\n"
        "Kerakli bo'limni pastdagi tugmalar orqali tanlang."
    )


async def format_stats_message(stats: dict[str, object]) -> str:
    telegram_sources = await get_telegram_sources(TELEGRAM_SOURCES)
    lines = [
        "📊 <b>Post statistikasi</b>",
        "",
        f"Bugun joylangan postlar: <b>{stats['today_posts']}</b>",
        f"Jami joylangan postlar: <b>{stats['total_posts']}</b>",
        "",
        "🗂 <b>Bugungi mavzular:</b>",
    ]
    today_topics = stats["topics_today"]
    total_topics = stats["topics_total"]
    lines.extend(_format_topic_counts(today_topics))
    lines.extend(["", "📚 <b>Umumiy mavzular:</b>"])
    lines.extend(_format_topic_counts(total_topics))
    lines.extend(["", "📡 <b>Yangilik manbalari:</b>", "", "<b>Telegram kanallar:</b>"])
    lines.extend([f"- {source}" for source in telegram_sources] or ["- Hali yo'q"])
    lines.extend(["", "<b>Web sahifalar:</b>"])
    lines.extend([f"- {source['type']}: {source['url']}" for source in WEB_SOURCES])
    lines.extend(["", "<b>Post joylanadigan kanallar:</b>"])
    lines.extend([f"- {channel}" for channel in CHANNEL_IDS] or ["- Hali sozlanmagan"])
    return "\n".join(lines)


def _format_topic_counts(topic_counts: object) -> list[str]:
    if not isinstance(topic_counts, dict) or not topic_counts:
        return ["- Hali post yo'q"]
    lines: list[str] = []
    for topic, count in topic_counts.items():
        label = TOPIC_LABELS.get(str(topic), str(topic))
        lines.append(f"- {label}: <b>{count}</b> ta")
    return lines


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_count = await count_posts_today(TIMEZONE)
    await update.effective_message.reply_text(
        panel_message(today_count),
        reply_markup=main_menu_markup(),
        parse_mode="HTML",
    )


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        format_schedule_message(),
        reply_markup=back_markup(),
    )


async def session_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.effective_message.reply_text("Bu buyruq faqat admin uchun.")
        return

    status = await session_status()
    await update.effective_message.reply_text(status)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_count = await count_posts_today(TIMEZONE)
    await update.effective_message.reply_text(
        panel_message(today_count),
        reply_markup=main_menu_markup(),
        parse_mode="HTML",
    )


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or user.id not in ADMIN_USER_IDS:
        await update.effective_message.reply_text("Bu buyruq faqat admin uchun.")
        return

    post_type = "web"
    if context.args and context.args[0].lower() in {"web", "telegram"}:
        post_type = context.args[0].lower()

    await update.effective_message.reply_text(f"Test post boshlandi: {post_type}")
    ok = await run_post_job(post_type, context.bot)
    await update.effective_message.reply_text(
        "Test post yuborildi." if ok else "Test post uchun mos yangilik topilmadi yoki xatolik yuz berdi."
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    user_id = query.from_user.id if query.from_user else None
    data = query.data or ""

    if data in {MENU_CALLBACK, BACK_CALLBACK}:
        context.user_data.pop("awaiting", None)
        today_count = await count_posts_today(TIMEZONE)
        await query.edit_message_text(
            panel_message(today_count),
            reply_markup=main_menu_markup(),
            parse_mode="HTML",
        )
        return

    if data == SCHEDULE_CALLBACK:
        await query.edit_message_text(
            format_schedule_message(),
            reply_markup=back_markup(),
        )
        return

    if data == STATS_CALLBACK:
        if not is_admin(user_id):
            await query.answer("Statistika faqat admin uchun.", show_alert=True)
            return
        stats = await topic_stats(TIMEZONE)
        await query.edit_message_text(
            await format_stats_message(stats),
            reply_markup=back_markup(),
            parse_mode="HTML",
        )
        return

    if data == POST_COUNT_CALLBACK:
        if not is_admin(user_id):
            await query.answer("Bu bo'lim faqat admin uchun.", show_alert=True)
            return
        context.user_data["awaiting"] = "post_count"
        await query.edit_message_text(
            "🔢 <b>Bugungi post soni</b>\n\nBugun nechta post joylashni xohlaysiz? 1 dan 24 gacha son yuboring.\n\nMasalan: <code>10</code>\n\nEslatma: bu sozlama faqat bugungi kun uchun amal qiladi, ertaga default jadval qaytadi.",
            reply_markup=back_markup(),
            parse_mode="HTML",
        )
        return

    if data == ADD_SOURCE_CALLBACK:
        if not is_admin(user_id):
            await query.answer("Bu bo'lim faqat admin uchun.", show_alert=True)
            return
        context.user_data["awaiting"] = "telegram_source"
        await query.edit_message_text(
            "➕ <b>Telegram source kanal qo'shish</b>\n\nPublic kanal linki yoki username yuboring.\n\nMasalan:\n<code>https://t.me/example</code>\nyoki\n<code>@example</code>",
            reply_markup=back_markup(),
            parse_mode="HTML",
        )
        return

    if data == TEST_MENU_CALLBACK:
        if not is_admin(user_id):
            await query.answer("Bu bo'lim faqat admin uchun.", show_alert=True)
            return
        await query.edit_message_text(
            "🧪 <b>Test post bo'limi</b>\n\nQaysi manbadan test post yuborilsin?",
            reply_markup=test_menu_markup(),
            parse_mode="HTML",
        )
        return

    if data in {TEST_WEB_CALLBACK, TEST_TELEGRAM_CALLBACK}:
        if not is_admin(user_id):
            await query.answer("Bu amal faqat admin uchun.", show_alert=True)
            return
        post_type = "web" if data == TEST_WEB_CALLBACK else "telegram"
        await query.edit_message_text(
            f"⏳ <b>Test post boshlandi</b>\n\nTanlangan manba: <b>{post_type}</b>",
            parse_mode="HTML",
        )
        try:
            ok = await run_post_job(post_type, context.bot)
        except Exception:
            logger.exception("Test post callback failed post_type=%s", post_type)
            ok = False
        result_text = (
            f"✅ <b>Test post yuborildi</b>\n\nManba: <b>{post_type}</b>"
            if ok
            else f"⚠️ <b>Test post muvaffaqiyatsiz</b>\n\nManba: <b>{post_type}</b>\nMos yangilik topilmadi yoki xatolik yuz berdi. Batafsil log Railway/terminalda ko'rinadi."
        )
        await query.edit_message_text(
            result_text,
            reply_markup=back_markup(),
            parse_mode="HTML",
        )
        return

    logger.warning("Unknown callback data received: %s", data)
    await query.answer("Noma'lum amal. /menu ni qayta oching.", show_alert=True)


async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    if not user or not is_admin(user.id) or not message or not message.text:
        return

    awaiting = context.user_data.get("awaiting")
    if awaiting == "post_count":
        raw_count = message.text.strip()
        try:
            count = int(raw_count)
            await set_today_post_override(count, TIMEZONE)
            scheduler = context.application.bot_data.get("scheduler")
            if scheduler:
                await apply_today_schedule_override(scheduler, context.bot, count)
        except ValueError as exc:
            await message.reply_text(
                f"⚠️ {exc}\n\nIltimos, 1 dan 24 gacha son yuboring.",
                reply_markup=back_markup(),
            )
            return

        context.user_data.pop("awaiting", None)
        await message.reply_text(
            "✅ Bugungi post soni yangilandi.\n\n" + format_schedule_message(),
            reply_markup=main_menu_markup(),
        )
        return

    if awaiting == "telegram_source":
        try:
            sources = await add_telegram_source(message.text.strip(), TELEGRAM_SOURCES)
        except ValueError as exc:
            await message.reply_text(
                f"⚠️ {exc}\n\nPublic kanal linki yoki username yuboring.",
                reply_markup=back_markup(),
            )
            return

        context.user_data.pop("awaiting", None)
        await message.reply_text(
            "✅ Telegram source kanal saqlandi.\n\n"
            f"Jami source kanallar: {len(sources)} ta",
            reply_markup=main_menu_markup(),
        )
        return


def build_application() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("session", session_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(menu:|test:)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))
    return app


async def check_channel_access(app: Application) -> None:
    bot_user = await app.bot.get_me()
    for channel_id in CHANNEL_IDS:
        try:
            member = await app.bot.get_chat_member(channel_id, bot_user.id)
            if member.status not in {"administrator", "creator"}:
                logger.warning(
                    "Kanal tekshiruvi: bot %s kanalida admin emas. Bu kanal skip qilinadi.",
                    channel_id,
                )
                continue
            logger.info("Kanal tekshiruvi OK: bot %s kanalida admin.", channel_id)
        except TelegramError as exc:
            logger.warning(
                "Kanal tekshiruvi xatosi channel=%s error=%s. Bu kanal skip qilinadi.",
                channel_id,
                exc,
            )


async def notify_admins_startup(app: Application) -> None:
    if not ADMIN_USER_IDS:
        return
    today_count = await count_posts_today(TIMEZONE)
    message = "🚀 Bot ishga tushdi\n\n" + panel_message(today_count)
    for admin_id in ADMIN_USER_IDS:
        try:
            await app.bot.send_message(
                chat_id=admin_id,
                text=message,
                reply_markup=main_menu_markup(),
                parse_mode="HTML",
            )
        except TelegramError as exc:
            logger.warning(
                "Admin startup xabarini yuborib bo'lmadi admin_id=%s error=%s",
                admin_id,
                exc,
            )


async def main() -> None:
    validate_required_env()
    ensure_runtime_dirs()
    await init_db()

    app = build_application()
    scheduler = setup_scheduler(app.bot)
    app.bot_data["scheduler"] = scheduler

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await app.initialize()
    await check_channel_access(app)
    await apply_today_schedule_override(scheduler, app.bot)
    await app.start()
    if app.updater is None:
        raise RuntimeError("Telegram polling updater is not available.")
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    scheduler.start()
    logger.info("Bot started. Scheduler running in timezone=%s.\n%s", TIMEZONE, format_schedule_message())
    await notify_admins_startup(app)

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down bot.")
        scheduler.shutdown(wait=False)
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
