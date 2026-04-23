from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class NewsArticle:
    title_en: str
    description: str
    source_name: str
    source_type: str
    source_url: str = ""
    source_channel: str = ""
    published_at: datetime | None = None
    topic: str = ""
    topics: list[str] = field(default_factory=list)
    content_hash: str = ""

    @property
    def source(self) -> str:
        return self.source_channel or self.source_name

    @property
    def raw_text(self) -> str:
        return f"{self.title_en}\n\n{self.description}".strip()


@dataclass(slots=True)
class TranslatedNews:
    title: str
    body: str
    summary: str
