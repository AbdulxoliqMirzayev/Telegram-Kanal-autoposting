# from __future__ import annotations

# from html import escape
# import logging
# import time

# import requests

# from config import Settings
# from models import PostDraft


# class TelegramChannelSender:
#     def __init__(self, settings: Settings) -> None:
#         self.settings = settings
#         self.logger = logging.getLogger(self.__class__.__name__)
#         self.session = requests.Session()
#         self.session.headers.update({"User-Agent": "Mozilla/5.0"})

#     def build_message(self, post: PostDraft) -> str:
#         parts = [
#             "<b>📰 Sarlavha:</b>",
#             escape(post.headline_uz),
#             "",
#             "<b>📊 Yangilik:</b>",
#             escape(post.news_uz),
#             "",
#             "<b>📈 Xulosa:</b>",
#             escape(post.insight_uz),
#             "",
#             (
#                 f"<b>Baholar:</b> Ahamiyat {post.importance_score}/10 | "
#                 f"Bozor ta'siri {post.market_impact_score}/10"
#             ),
#         ]

#         if post.source_url:
#             safe_url = escape(post.source_url, quote=True)
#             parts.extend(["", f'<a href="{safe_url}">Manba</a>'])

#         return "\n".join(parts)

#     def send(self, post: PostDraft) -> None:
#         message = self.build_message(post)
#         endpoint = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
#         payload = {
#             "chat_id": self.settings.telegram_channel_id,
#             "text": message,
#             "parse_mode": "HTML",
#             "disable_web_page_preview": True,
#         }

#         max_attempts = max(1, self.settings.http_max_retries + 1)
#         for attempt in range(1, max_attempts + 1):
#             try:
#                 response = self.session.post(
#                     endpoint,
#                     data=payload,
#                     timeout=self.settings.http_timeout,
#                 )
#             except requests.RequestException as exc:
#                 if attempt >= max_attempts:
#                     raise RuntimeError(f"Telegram send failed: {exc}") from exc
#                 self.logger.warning(
#                     "Telegram send network error on attempt %s/%s: %s",
#                     attempt,
#                     max_attempts,
#                     exc,
#                     exc_info=False,
#                 )
#                 time.sleep(min(5.0, attempt * 1.5))
#                 continue

#             if response.status_code == 429:
#                 try:
#                     response_json = response.json()
#                     retry_after = float(
#                         response_json.get("parameters", {}).get("retry_after", 2)
#                     )
#                 except ValueError:
#                     retry_after = 2.0
#                 if attempt >= max_attempts:
#                     raise RuntimeError("Telegram Bot API rate limited the request.")
#                 self.logger.warning(
#                     "Telegram Bot API rate limit hit. Waiting %.1f seconds.",
#                     retry_after,
#                 )
#                 time.sleep(retry_after)
#                 continue

#             if response.status_code >= 500:
#                 if attempt >= max_attempts:
#                     raise RuntimeError(
#                         f"Telegram Bot API server error: {response.status_code}"
#                     )
#                 time.sleep(min(5.0, attempt * 1.5))
#                 continue

#             if response.status_code >= 400:
#                 raise RuntimeError(
#                     f"Telegram Bot API returned {response.status_code}: {response.text}"
#                 )

#             return


from __future__ import annotations

from html import escape
import logging
import time

import requests

from config import Settings
from models import PostDraft


class TelegramChannelSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": settings.user_agent})

    def build_message(self, post: PostDraft) -> str:
        parts: list[str] = []

        if post.headline_uz.strip():
            parts.append(f"📊 <b>{escape(post.headline_uz.strip())}</b>")
            parts.append("")

        if post.news_uz.strip():
            parts.append(escape(post.news_uz.strip()))
            parts.append("")

        if post.insight_uz.strip():
            parts.append(f"📈 <b>Qisqa xulosa:</b> {escape(post.insight_uz.strip())}")

        return "\n".join(parts).strip()

    def send(self, post: PostDraft) -> None:
        message = self.build_message(post)

        if post.image_url:
            endpoint = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendPhoto"
            payload = {
                "chat_id": self.settings.telegram_channel_id,
                "photo": post.image_url,
                "caption": message,
                "parse_mode": "HTML",
            }
        else:
            endpoint = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.settings.telegram_channel_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }

        max_attempts = max(1, self.settings.http_max_retries + 1)

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.post(
                    endpoint,
                    data=payload,
                    timeout=self.settings.http_timeout,
                )
            except requests.RequestException as exc:
                if attempt >= max_attempts:
                    raise RuntimeError(f"Telegram send failed: {exc}") from exc
                self.logger.warning(
                    "Telegram send network error on attempt %s/%s: %s",
                    attempt,
                    max_attempts,
                    exc,
                    exc_info=False,
                )
                time.sleep(min(5.0, attempt * 1.5))
                continue

            if response.status_code == 429:
                try:
                    response_json = response.json()
                    retry_after = float(
                        response_json.get("parameters", {}).get("retry_after", 2)
                    )
                except ValueError:
                    retry_after = 2.0

                if attempt >= max_attempts:
                    raise RuntimeError("Telegram Bot API rate limited the request.")

                self.logger.warning(
                    "Telegram Bot API rate limit hit. Waiting %.1f seconds.",
                    retry_after,
                )
                time.sleep(retry_after)
                continue

            if response.status_code >= 500:
                if attempt >= max_attempts:
                    raise RuntimeError(
                        f"Telegram Bot API server error: {response.status_code}"
                    )
                time.sleep(min(5.0, attempt * 1.5))
                continue

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Telegram Bot API returned {response.status_code}: {response.text}"
                )

            return