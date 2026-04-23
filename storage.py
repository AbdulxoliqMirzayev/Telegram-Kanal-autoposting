from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from models import DailyPostingPlan, NewsItem, PostDraft


class SeenNewsStore:
    def __init__(self, storage_path: Path, max_items: int = 4000) -> None:
        self.storage_path = storage_path
        self.max_items = max_items
        self.logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> set[str]:
        payload = self._read_payload()
        return {
            str(item.get("fingerprint", "")).strip()
            for item in payload.get("items", [])
            if item.get("fingerprint")
        }

    def add_post(
        self,
        *,
        fingerprint: str,
        title: str,
        source: str,
        url: str,
    ) -> None:
        if not fingerprint:
            return

        payload = self._read_payload()
        existing = deque(payload.get("items", []), maxlen=self.max_items)
        seen_fingerprints = {
            item.get("fingerprint", "")
            for item in existing
            if item.get("fingerprint")
        }
        if fingerprint in seen_fingerprints:
            return

        existing.append(
            {
                "fingerprint": fingerprint,
                "title": title,
                "source": source,
                "url": url,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._write_payload({"updated_at": datetime.now(timezone.utc).isoformat(), "items": list(existing)})

    def _read_payload(self) -> dict:
        if not self.storage_path.exists():
            return {"items": []}
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("Seen store could not be read: %s", exc, exc_info=False)
            return {"items": []}

    def _write_payload(self, payload: dict) -> None:
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class DailyPlanStore:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> DailyPostingPlan | None:
        if not self.storage_path.exists():
            return None
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("Daily plan could not be read: %s", exc, exc_info=False)
            return None

        posts = [
            PostDraft(**item)
            for item in payload.get("posts", [])
            if isinstance(item, dict)
        ]
        return DailyPostingPlan(
            date=str(payload.get("date", "")),
            generated_at=str(payload.get("generated_at", "")),
            posts=posts,
            posted_indices=[
                int(index)
                for index in payload.get("posted_indices", [])
                if isinstance(index, int)
            ],
        )

    def save(self, plan: DailyPostingPlan) -> None:
        payload = {
            "date": plan.date,
            "generated_at": plan.generated_at,
            "posted_indices": plan.posted_indices,
            "posts": [asdict(post) for post in plan.posts],
        }
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def mark_posted(self, index: int) -> DailyPostingPlan | None:
        plan = self.load()
        if plan is None:
            return None
        if index not in plan.posted_indices:
            plan.posted_indices.append(index)
            plan.posted_indices.sort()
            self.save(plan)
        return plan


class SourceCacheStore:
    def __init__(self, storage_path: Path, max_items: int = 500) -> None:
        self.storage_path = storage_path
        self.max_items = max_items
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_items(self) -> list[NewsItem]:
        if not self.storage_path.exists():
            return []
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("Source cache could not be read: %s", exc, exc_info=False)
            return []

        items: list[NewsItem] = []
        for entry in payload.get("items", []):
            if not isinstance(entry, dict):
                continue
            try:
                items.append(NewsItem(**entry))
            except TypeError:
                continue
        return items

    def save_items(self, items: list[NewsItem]) -> None:
        existing = deque(self.load_items(), maxlen=self.max_items)
        seen = {item.fingerprint or f"{item.title}|{item.url}" for item in existing}

        for item in items:
            key = item.fingerprint or f"{item.title}|{item.url}"
            if key in seen:
                continue
            existing.append(item)
            seen.add(key)

        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": [asdict(item) for item in existing],
        }
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
