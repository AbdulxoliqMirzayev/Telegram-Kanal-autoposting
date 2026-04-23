from __future__ import annotations

import json
import logging
import random
import re
import time
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import Settings
from models import NewsItem


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def clean_headline(value: str | None) -> str:
    text = clean_text(value)
    return re.sub(
        r"^(?:\d+\s+(?:minute|minutes|hour|hours|day|days)\s+ago|an?\s+(?:hour|day)\s+ago)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )


def build_session(settings: Settings) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    return session


def _iter_json_candidates(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from _iter_json_candidates(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_json_candidates(item)


def parse_json_ld_articles(
    soup: BeautifulSoup,
    source_name: str,
    base_url: str,
) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_urls: set[str] = set()

    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for candidate in _iter_json_candidates(payload):
            item_type = str(candidate.get("@type", "")).lower()
            headline = clean_text(candidate.get("headline") or candidate.get("name"))
            url = clean_text(candidate.get("url"))
            description = clean_text(candidate.get("description"))
            published_at = clean_text(candidate.get("datePublished"))

            if "article" not in item_type and not headline:
                continue
            if not headline or not url:
                continue

            absolute_url = urljoin(base_url, url)
            if absolute_url in seen_urls:
                continue

            items.append(
                NewsItem(
                    source=source_name,
                    title=headline,
                    url=absolute_url,
                    summary=description,
                    published_at=published_at,
                )
            )
            seen_urls.add(absolute_url)

    return items


class BaseScraper:
    source_name = "Base"

    def __init__(self, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or build_session(settings)
        self.logger = logging.getLogger(f"scraper.{self.source_name.lower()}")

    def fetch(self) -> list[NewsItem]:
        raise NotImplementedError

    def get_soup(self, url: str, *, params: dict[str, Any] | None = None) -> BeautifulSoup | None:
        response = self.get_response(url, params=params)
        if response is None:
            return None
        return BeautifulSoup(response.text, "html.parser")

    def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str | None:
        response = self.get_response(url, params=params)
        if response is None:
            return None
        return response.text

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        response = self.get_response(url, params=params)
        if response is None:
            return None
        try:
            return response.json()
        except ValueError as exc:
            self.logger.warning("Failed to fetch JSON from %s: %s", url, exc, exc_info=False)
            return None

    def get_response(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> requests.Response | None:
        max_attempts = max(1, self.settings.http_max_retries + 1)

        for attempt in range(1, max_attempts + 1):
            self._respect_delay()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.settings.http_timeout,
                )
            except requests.RequestException as exc:
                if attempt >= max_attempts:
                    self.logger.warning("Network error for %s: %s", url, exc, exc_info=False)
                    return None
                self.logger.warning(
                    "Network error for %s on attempt %s/%s: %s",
                    url,
                    attempt,
                    max_attempts,
                    exc,
                    exc_info=False,
                )
                time.sleep(min(5.0, attempt * 1.5))
                continue

            if response.status_code == 403:
                self.logger.warning("Access blocked with HTTP 403 for %s. Skipping.", url)
                return None

            if response.status_code == 429:
                if attempt >= max_attempts:
                    self.logger.warning("Rate limit persisted for %s after retries.", url)
                    return None
                retry_after = response.headers.get("Retry-After", "").strip()
                try:
                    wait_seconds = float(retry_after)
                except ValueError:
                    wait_seconds = min(8.0, attempt * 2.0)
                self.logger.warning(
                    "HTTP 429 for %s. Waiting %.1f seconds before retry.",
                    url,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 500:
                if attempt >= max_attempts:
                    self.logger.warning("Server error %s for %s.", response.status_code, url)
                    return None
                time.sleep(min(5.0, attempt * 1.5))
                continue

            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                self.logger.warning("Failed to fetch %s: %s", url, exc, exc_info=False)
                return None

            return response

        return None

    def _respect_delay(self) -> None:
        time.sleep(
            random.uniform(
                self.settings.request_delay_min_seconds,
                self.settings.request_delay_max_seconds,
            )
        )

    def unique(self, items: list[NewsItem]) -> list[NewsItem]:
        seen: set[str] = set()
        unique_items: list[NewsItem] = []
        for item in items:
            key = f"{item.title.lower()}|{item.url.lower()}"
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(item)
        return unique_items
