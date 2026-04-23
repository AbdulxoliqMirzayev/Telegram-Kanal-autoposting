from __future__ import annotations

from utils.filter import normalize_text
from models import NewsItem


class NewsDeduplicator:
    def rank_unique(
        self,
        items: list[NewsItem],
        seen_fingerprints: set[str],
    ) -> list[NewsItem]:
        unique_items: dict[str, NewsItem] = {}

        for item in items:
            if not item.fingerprint or item.fingerprint in seen_fingerprints:
                continue

            normalized_title = normalize_text(item.title)
            existing = unique_items.get(normalized_title)
            if existing is None or self._is_better(item, existing):
                unique_items[normalized_title] = item

        ranked = sorted(
            unique_items.values(),
            key=lambda item: (
                item.total_score,
                item.importance_score,
                item.market_impact_score,
                len(item.company_tags),
                item.published_at,
            ),
            reverse=True,
        )
        return ranked

    @staticmethod
    def _is_better(candidate: NewsItem, current: NewsItem) -> bool:
        return (
            candidate.total_score,
            candidate.importance_score,
            candidate.market_impact_score,
        ) > (
            current.total_score,
            current.importance_score,
            current.market_impact_score,
        )
