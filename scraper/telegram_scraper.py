# from __future__ import annotations

# import asyncio
# from getpass import getpass
# import logging
# import sys
# from urllib.parse import urlparse

# from telethon import TelegramClient
# from telethon.errors import FloodWaitError, PhoneCodeInvalidError, RPCError
# from telethon.sessions import SQLiteSession

# from config import Settings
# from models import NewsItem
# from scraper.base import clean_headline, clean_text


# class TelegramNewsScraper:
#     source_name = "Telegram"

#     def __init__(self, settings: Settings) -> None:
#         self.settings = settings
#         self.logger = logging.getLogger("scraper.telegram")

#     def login(self) -> bool:
#         try:
#             return asyncio.run(self._login_async())
#         except RuntimeError:
#             loop = asyncio.new_event_loop()
#             try:
#                 return loop.run_until_complete(self._login_async())
#             finally:
#                 loop.close()

#     def fetch(self) -> list[NewsItem]:
#         try:
#             return asyncio.run(self._fetch_async())
#         except RuntimeError:
#             loop = asyncio.new_event_loop()
#             try:
#                 return loop.run_until_complete(self._fetch_async())
#             finally:
#                 loop.close()

#     async def _login_async(self) -> bool:
#         client = self._build_client()
#         await client.connect()
#         try:
#             return await self._ensure_authorized(client)
#         finally:
#             await client.disconnect()

#     async def _fetch_async(self) -> list[NewsItem]:
#         if not self.settings.telegram_source_channels:
#             self.logger.info("No Telegram source channels configured. Skipping Telegram source.")
#             return []

#         items: list[NewsItem] = []
#         client = self._build_client()
#         await client.connect()
#         try:
#             if not await self._ensure_authorized(client):
#                 return []

#             for channel in self.settings.telegram_source_channels:
#                 normalized_channel = self._normalize_channel(channel)
#                 try:
#                     async for message in client.iter_messages(
#                         channel,
#                         limit=self.settings.telegram_message_limit,
#                     ):
#                         text = clean_text(message.message or "")
#                         if len(text) < 25:
#                             continue

#                         title, summary = self._split_message(text)
#                         items.append(
#                             NewsItem(
#                                 source=f"Telegram:{normalized_channel}",
#                                 title=title,
#                                 url=self._message_url(normalized_channel, message.id),
#                                 summary=summary,
#                                 published_at=message.date.isoformat() if message.date else "",
#                             )
#                         )
#                 except Exception as exc:
#                     self.logger.warning(
#                         "Failed to read Telegram channel %s: %s",
#                         channel,
#                         exc,
#                         exc_info=False,
#                     )
#         finally:
#             await client.disconnect()

#         return items[: self.settings.max_news_per_source * max(1, len(self.settings.telegram_source_channels))]

#     def _build_client(self) -> TelegramClient:
#         return TelegramClient(
#             SQLiteSession(str(self.settings.telethon_session_path)),
#             self.settings.telegram_api_id,
#             self.settings.telegram_api_hash,
#         )

#     async def _ensure_authorized(self, client: TelegramClient) -> bool:
#         if await client.is_user_authorized():
#             return True

#         if not sys.stdin.isatty():
#             self.logger.warning(
#                 "Telethon session is missing and no interactive terminal is available. "
#                 "Run `python3 main.py --login` once first."
#             )
#             return False

#         phone = input("Telegram phone number (+998...): ").strip()
#         if not phone:
#             self.logger.warning("Telegram login cancelled because phone number was empty.")
#             return False

#         try:
#             await client.start(
#                 phone=lambda: phone,
#                 password=lambda: getpass("Telegram 2FA password (if enabled): "),
#                 code_callback=lambda: input("Telegram login code: ").strip(),
#                 max_attempts=3,
#             )
#         except FloodWaitError as exc:
#             self.logger.warning("Telegram login rate-limited. Wait %s seconds.", exc.seconds)
#             return False
#         except PhoneCodeInvalidError:
#             self.logger.warning("Telegram login code was invalid.")
#             return False
#         except (EOFError, RPCError, ValueError) as exc:
#             self.logger.warning("Telegram login failed: %s", exc, exc_info=False)
#             return False

#         authorized = await client.is_user_authorized()
#         if authorized:
#             self.logger.info(
#                 "Telethon session saved to %s.",
#                 self.settings.telethon_session_path,
#             )
#         return authorized

#     @staticmethod
#     def _split_message(text: str) -> tuple[str, str]:
#         first_line = clean_headline(text.split("\n", maxsplit=1)[0])
#         sentences = [segment.strip() for segment in text.replace("\n", ". ").split(".") if segment.strip()]
#         title = first_line[:140].rstrip(" -:")
#         if len(title) < 18 and sentences:
#             title = sentences[0][:140]
#         summary = ". ".join(sentences[1:4]).strip()
#         if not summary:
#             summary = text[:320]
#         return title, summary

#     @staticmethod
#     def _message_url(channel_name: str, message_id: int) -> str:
#         if channel_name and not urlparse(channel_name).scheme:
#             return f"https://t.me/{channel_name}/{message_id}"
#         return ""

#     @staticmethod
#     def _normalize_channel(channel: str) -> str:
#         normalized = channel.strip()
#         if normalized.startswith("https://t.me/"):
#             normalized = normalized.removeprefix("https://t.me/")
#         normalized = normalized.removeprefix("@").strip("/")
#         return normalized


from __future__ import annotations

import asyncio
from getpass import getpass
import logging
import sys
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.errors import FloodWaitError, PhoneCodeInvalidError, RPCError
from telethon.sessions import SQLiteSession

from config import Settings
from models import NewsItem
from scraper.base import clean_headline, clean_text


class TelegramNewsScraper:
    source_name = "Telegram"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger("scraper.telegram")

    def login(self) -> bool:
        try:
            return asyncio.run(self._login_async())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._login_async())
            finally:
                loop.close()

    def fetch(self) -> list[NewsItem]:
        try:
            return asyncio.run(self._fetch_async())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._fetch_async())
            finally:
                loop.close()

    async def _login_async(self) -> bool:
        client = self._build_client()
        await client.connect()
        try:
            return await self._ensure_authorized(client)
        finally:
            await client.disconnect()

    async def _fetch_async(self) -> list[NewsItem]:
        if not self.settings.telegram_source_channels:
            self.logger.info("No Telegram source channels configured. Skipping Telegram source.")
            return []

        items: list[NewsItem] = []
        client = self._build_client()
        await client.connect()

        try:
            if not await self._ensure_authorized(client):
                return []

            for channel in self.settings.telegram_source_channels:
                normalized_channel = self._normalize_channel(channel)

                try:
                    async for message in client.iter_messages(
                        channel,
                        limit=self.settings.telegram_message_limit,
                    ):
                        text = clean_text(message.message or message.text or "")
                        if len(text) < 25:
                            continue

                        title, summary = self._split_message(text)
                        image_url = ""

                        if normalized_channel and message.id:
                            # Telegram public post image preview URL via message link itself
                            # Direct file URL yo‘q, lekin post link saqlanadi.
                            image_url = ""

                        items.append(
                            NewsItem(
                                source=f"Telegram:{normalized_channel}",
                                title=title,
                                url=self._message_url(normalized_channel, message.id),
                                summary=summary,
                                published_at=message.date.isoformat() if message.date else "",
                                image_url=image_url,
                            )
                        )
                except Exception as exc:
                    self.logger.warning(
                        "Failed to read Telegram channel %s: %s",
                        channel,
                        exc,
                        exc_info=False,
                    )
        finally:
            await client.disconnect()

        limit = self.settings.max_news_per_source * max(
            1, len(self.settings.telegram_source_channels)
        )
        return items[:limit]

    def _build_client(self) -> TelegramClient:
        return TelegramClient(
            SQLiteSession(str(self.settings.telethon_session_path)),
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
        )

    async def _ensure_authorized(self, client: TelegramClient) -> bool:
        if await client.is_user_authorized():
            return True

        if not sys.stdin.isatty():
            self.logger.warning(
                "Telethon session is missing and no interactive terminal is available. "
                "Run `python3 main.py --login` once first."
            )
            return False

        phone = input("Telegram phone number (+998...): ").strip()
        if not phone:
            self.logger.warning("Telegram login cancelled because phone number was empty.")
            return False

        try:
            await client.start(
                phone=lambda: phone,
                password=lambda: getpass("Telegram 2FA password (if enabled): "),
                code_callback=lambda: input("Telegram login code: ").strip(),
                max_attempts=3,
            )
        except FloodWaitError as exc:
            self.logger.warning("Telegram login rate-limited. Wait %s seconds.", exc.seconds)
            return False
        except PhoneCodeInvalidError:
            self.logger.warning("Telegram login code was invalid.")
            return False
        except (EOFError, RPCError, ValueError) as exc:
            self.logger.warning("Telegram login failed: %s", exc, exc_info=False)
            return False

        authorized = await client.is_user_authorized()
        if authorized:
            self.logger.info(
                "Telethon session saved to %s.",
                self.settings.telethon_session_path,
            )
        return authorized

    @staticmethod
    def _split_message(text: str) -> tuple[str, str]:
        first_line = clean_headline(text.split("\n", maxsplit=1)[0])
        sentences = [
            segment.strip()
            for segment in text.replace("\n", ". ").split(".")
            if segment.strip()
        ]
        title = first_line[:140].rstrip(" -:")
        if len(title) < 18 and sentences:
            title = sentences[0][:140]
        summary = ". ".join(sentences[1:4]).strip()
        if not summary:
            summary = text[:320]
        return title, summary

    @staticmethod
    def _message_url(channel_name: str, message_id: int) -> str:
        if channel_name and not urlparse(channel_name).scheme:
            return f"https://t.me/{channel_name}/{message_id}"
        return ""

    @staticmethod
    def _normalize_channel(channel: str) -> str:
        normalized = channel.strip()
        if normalized.startswith("https://t.me/"):
            normalized = normalized.removeprefix("https://t.me/")
        normalized = normalized.removeprefix("@").strip("/")
        return normalized