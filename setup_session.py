from __future__ import annotations

import asyncio
import logging
from getpass import getpass
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PhoneCodeInvalidError, RPCError
from telethon.sessions import SQLiteSession

from config import (
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_PHONE,
    TELETHON_SESSION_PATH,
    ensure_runtime_dirs,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _is_authorized_session(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        client = TelegramClient(
            SQLiteSession(str(path)),
            TELEGRAM_API_ID,
            TELEGRAM_API_HASH,
        )
        await client.connect()
    except Exception as exc:
        logger.warning("Telethon session %s could not be opened: %s", path, exc)
        return False
    try:
        return await client.is_user_authorized()
    finally:
        await client.disconnect()


async def main() -> int:
    ensure_runtime_dirs()
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH are required.")
        return 1

    legacy_path = TELETHON_SESSION_PATH.with_name("telethon.session")
    if legacy_path != TELETHON_SESSION_PATH and await _is_authorized_session(legacy_path):
        TELETHON_SESSION_PATH.write_bytes(legacy_path.read_bytes())
        logger.info(
            "Authorized legacy Telethon session migrated: %s -> %s",
            legacy_path,
            TELETHON_SESSION_PATH,
        )
        return 0

    logger.info("Telethon session path: %s", TELETHON_SESSION_PATH)

    client = TelegramClient(
        SQLiteSession(str(TELETHON_SESSION_PATH)),
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )
    try:
        await client.connect()
    except (ConnectionError, OSError) as exc:
        logger.error(
            "Could not connect to Telegram: %s. Internet/VPN/firewallni tekshiring va qayta urinib ko'ring.",
            exc,
        )
        return 1
    try:
        if await client.is_user_authorized():
            logger.info("Telethon session already authorized at %s.", TELETHON_SESSION_PATH)
            return 0

        phone = TELEGRAM_PHONE or input("Telegram phone number (+998...): ").strip()
        if not phone:
            logger.error("Telegram phone number is required.")
            return 1

        await client.start(
            phone=lambda: phone,
            password=lambda: getpass("Telegram 2FA password (if enabled): "),
            code_callback=lambda: input("Telegram login code: ").strip(),
            max_attempts=3,
        )
        if await client.is_user_authorized():
            logger.info("Telethon session authorized and saved to %s.", TELETHON_SESSION_PATH)
            return 0
        logger.error("Telethon login finished, but session is still not authorized.")
        return 1
    except FloodWaitError as exc:
        logger.error("Telegram login rate-limited. Wait %s seconds.", exc.seconds)
        return 1
    except PhoneCodeInvalidError:
        logger.error("Telegram login code was invalid.")
        return 1
    except (EOFError, RPCError, ValueError) as exc:
        logger.error("Telegram login failed: %s", exc)
        return 1
    finally:
        await client.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
