# from __future__ import annotations

# import logging
# from dataclasses import replace
# from datetime import date, datetime

# from ai import UzbekNewsAnalyzer
# from bot import TelegramChannelSender
# from config import Settings
# from models import DailyPostingPlan, NewsItem
# from scraper import TelegramNewsScraper, TradingViewNewsScraper
# from storage import DailyPlanStore, SeenNewsStore, SourceCacheStore
# from utils import NewsDeduplicator, NewsFilter


# class FinancialNewsService:
#     def __init__(self, settings: Settings) -> None:
#         self.settings = settings
#         self.logger = logging.getLogger(self.__class__.__name__)
#         self.filter = NewsFilter()
#         self.deduplicator = NewsDeduplicator()
#         self.seen_store = SeenNewsStore(settings.seen_store_path)
#         self.plan_store = DailyPlanStore(settings.daily_plan_path)
#         self.source_cache_store = SourceCacheStore(settings.source_cache_path)
#         self.analyzer = UzbekNewsAnalyzer(settings)
#         self.sender = TelegramChannelSender(settings)
#         self.scrapers = [
#             TelegramNewsScraper(settings),
#             TradingViewNewsScraper(settings),
#         ]

#     def prepare_daily_posts(
#         self,
#         *,
#         target_date: date | None = None,
#         force: bool = False,
#     ) -> DailyPostingPlan:
#         today = target_date or datetime.now(self.settings.timezone).date()
#         existing_plan = self.plan_store.load()
#         if (
#             existing_plan
#             and existing_plan.date == today.isoformat()
#             and len(existing_plan.posts) >= self.settings.daily_post_count
#             and not force
#         ):
#             self.logger.info(
#                 "Reusing existing daily plan for %s with %s post(s).",
#                 existing_plan.date,
#                 len(existing_plan.posts),
#             )
#             return existing_plan

#         self.logger.info("Preparing daily posting plan for %s.", today.isoformat())
#         raw_news = self._collect_live_news()
#         self.logger.info("Collected %s raw items from live sources.", len(raw_news))

#         live_candidates = self.filter.filter_and_score_items(raw_news)
#         if live_candidates:
#             self.source_cache_store.save_items(live_candidates)

#         seen_fingerprints = self.seen_store.load()
#         selected = self._select_daily_candidates(live_candidates, seen_fingerprints)

#         if len(selected) < self.settings.daily_post_count:
#             cached_candidates = self.source_cache_store.load_items()
#             if cached_candidates:
#                 self.logger.info(
#                     "Supplementing with %s cached source item(s).",
#                     len(cached_candidates),
#                 )
#             selected = self._supplement_with_cache(
#                 selected,
#                 cached_candidates,
#                 seen_fingerprints,
#             )

#         if not selected:
#             raise RuntimeError("No relevant financial news could be prepared for today.")

#         analyzed_posts = self.analyzer.analyze(selected)
#         if len(analyzed_posts) < self.settings.daily_post_count:
#             self.logger.warning(
#                 "Prepared only %s post(s) for %s; target is %s.",
#                 len(analyzed_posts),
#                 today.isoformat(),
#                 self.settings.daily_post_count,
#             )
#         plan = DailyPostingPlan(
#             date=today.isoformat(),
#             generated_at=datetime.now(self.settings.timezone).isoformat(),
#             posts=analyzed_posts,
#             posted_indices=[],
#         )
#         self.plan_store.save(plan)
#         self.logger.info("Daily plan prepared with %s post(s).", len(plan.posts))
#         return plan

#     def publish_next_post(self, *, target_date: date | None = None) -> bool:
#         today = target_date or datetime.now(self.settings.timezone).date()
#         plan = self.plan_store.load()

#         if plan is None or plan.date != today.isoformat() or not plan.posts:
#             self.logger.info("No valid plan found for %s. Preparing a new one.", today.isoformat())
#             plan = self.prepare_daily_posts(target_date=today, force=True)

#         next_index = self._next_unposted_index(plan)
#         if next_index is None:
#             self.logger.info("All scheduled posts for %s have already been sent.", plan.date)
#             return False

#         post = plan.posts[next_index]
#         self.sender.send(post)
#         self.plan_store.mark_posted(next_index)
#         self.seen_store.add_post(
#             fingerprint=post.fingerprint,
#             title=post.source_title,
#             source=post.source,
#             url=post.source_url,
#         )
#         self.logger.info("Published post %s/%s for %s.", next_index + 1, len(plan.posts), plan.date)
#         return True

#     def login_telethon(self) -> bool:
#         telegram_scraper = self.scrapers[0]
#         return telegram_scraper.login()

#     def _collect_live_news(self) -> list[NewsItem]:
#         collected: list[NewsItem] = []
#         for scraper in self.scrapers:
#             try:
#                 items = scraper.fetch()
#             except Exception:
#                 self.logger.exception("Scraper %s failed unexpectedly.", scraper.source_name)
#                 continue

#             self.logger.info("%s returned %s item(s).", scraper.source_name, len(items))
#             collected.extend(items)
#         return collected

#     def _select_daily_candidates(
#         self,
#         candidate_items: list[NewsItem],
#         seen_fingerprints: set[str],
#     ) -> list[NewsItem]:
#         if not candidate_items:
#             return []

#         ranked_items = self.deduplicator.rank_unique(candidate_items, seen_fingerprints)
#         selected: list[NewsItem] = []
#         strict = [
#             item
#             for item in ranked_items
#             if item.importance_score >= 6 and item.market_impact_score >= 6
#         ]
#         relaxed = [
#             item
#             for item in ranked_items
#             if item not in strict and item.importance_score >= 5 and item.market_impact_score >= 4
#         ]
#         fallback = [item for item in ranked_items if item not in strict and item not in relaxed]

#         for bucket in (strict, relaxed, fallback):
#             for item in bucket:
#                 if len(selected) >= self.settings.daily_post_count:
#                     return selected
#                 selected.append(replace(item))

#         return selected[: self.settings.daily_post_count]

#     def _supplement_with_cache(
#         self,
#         selected: list[NewsItem],
#         cached_items: list[NewsItem],
#         seen_fingerprints: set[str],
#     ) -> list[NewsItem]:
#         if len(selected) >= self.settings.daily_post_count:
#             return selected

#         selected_fingerprints = {item.fingerprint for item in selected}
#         combined_seen = set(seen_fingerprints) | selected_fingerprints
#         filtered_cache = self.filter.filter_and_score_items(cached_items)
#         ranked_cache = self.deduplicator.rank_unique(filtered_cache, combined_seen)

#         for item in ranked_cache:
#             if len(selected) >= self.settings.daily_post_count:
#                 break
#             if item.fingerprint in selected_fingerprints:
#                 continue
#             selected.append(replace(item))
#             selected_fingerprints.add(item.fingerprint)

#         return selected

#     @staticmethod
#     def _next_unposted_index(plan: DailyPostingPlan) -> int | None:
#         for index, _post in enumerate(plan.posts):
#             if index not in plan.posted_indices:
#                 return index
#         return None

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime

from ai import UzbekNewsAnalyzer
from bot import TelegramChannelSender
from config import Settings
from models import DailyPostingPlan, NewsItem
from scraper import TelegramNewsScraper, TradingViewNewsScraper
from storage import DailyPlanStore, SeenNewsStore, SourceCacheStore
from utils import NewsDeduplicator, NewsFilter


class FinancialNewsService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        self.filter = NewsFilter()
        self.deduplicator = NewsDeduplicator()
        self.seen_store = SeenNewsStore(settings.seen_store_path)
        self.plan_store = DailyPlanStore(settings.daily_plan_path)
        self.source_cache_store = SourceCacheStore(settings.source_cache_path)
        self.analyzer = UzbekNewsAnalyzer(settings)
        self.sender = TelegramChannelSender(settings)
        self.scrapers = [
            TelegramNewsScraper(settings),
            TradingViewNewsScraper(settings),
        ]

    def prepare_daily_posts(
        self,
        *,
        target_date: date | None = None,
        force: bool = False,
    ) -> DailyPostingPlan:
        """
        Legacy compatibility:
        Hozir oldindan 8 ta post tayyorlamaymiz.
        Faqat bo'sh daily plan yaratib qo'yamiz, posted_indices tracking uchun.
        """
        today = target_date or datetime.now(self.settings.timezone).date()
        existing_plan = self.plan_store.load()

        if existing_plan and existing_plan.date == today.isoformat() and not force:
            return existing_plan

        plan = DailyPostingPlan(
            date=today.isoformat(),
            generated_at=datetime.now(self.settings.timezone).isoformat(),
            posts=[],
            posted_indices=[],
        )
        self.plan_store.save(plan)
        self.logger.info(
            "Initialized live posting plan for %s. Posts will be generated at slot time.",
            today.isoformat(),
        )
        return plan

    def publish_next_post(self, *, target_date: date | None = None) -> bool:
        today = target_date or datetime.now(self.settings.timezone).date()
        plan = self.plan_store.load()

        if plan is None or plan.date != today.isoformat():
            self.logger.info("No valid plan found for %s. Creating live plan.", today.isoformat())
            plan = self.prepare_daily_posts(target_date=today, force=True)

        next_index = self._next_unposted_slot_index(plan)
        if next_index is None:
            self.logger.info("All scheduled posts for %s have already been sent.", today.isoformat())
            return False

        source_preference = "web" if next_index % 2 == 0 else "telegram"
        self.logger.info(
            "Generating live post for slot %s/%s with source preference: %s",
            next_index + 1,
            self.settings.daily_post_count,
            source_preference,
        )

        post_item = self._build_live_post_candidate(source_preference=source_preference)
        if post_item is None:
            self.logger.warning("Could not find a suitable live news item for slot %s.", next_index + 1)
            return False

        analyzed_posts = self.analyzer.analyze([post_item])
        if not analyzed_posts:
            self.logger.warning("Analyzer returned no draft for live item: %s", post_item.title)
            return False

        post = analyzed_posts[0]
        self.sender.send(post)

        self.plan_store.mark_posted(next_index)
        self.seen_store.add_post(
            fingerprint=post.fingerprint,
            title=post.source_title,
            source=post.source,
            url=post.source_url,
        )
        self.logger.info(
            "Published live post for slot %s/%s on %s.",
            next_index + 1,
            self.settings.daily_post_count,
            today.isoformat(),
        )
        return True

    def login_telethon(self) -> bool:
        telegram_scraper = self.scrapers[0]
        return telegram_scraper.login()

    def _build_live_post_candidate(self, *, source_preference: str) -> NewsItem | None:
        raw_news = self._collect_live_news()
        self.logger.info("Collected %s raw live item(s).", len(raw_news))

        if not raw_news:
            return None

        candidates = self.filter.filter_and_score_items(raw_news)
        if candidates:
            self.source_cache_store.save_items(candidates)

        seen_fingerprints = self.seen_store.load()
        ranked_items = self.deduplicator.rank_unique(candidates, seen_fingerprints)

        preferred_items = self._filter_by_source_preference(ranked_items, source_preference)
        fallback_items = [item for item in ranked_items if item not in preferred_items]

        ordered_candidates = preferred_items + fallback_items

        selected = self._select_daily_candidates(ordered_candidates, seen_fingerprints)
        if selected:
            return selected[0]

        cached_items = self.source_cache_store.load_items()
        if cached_items:
            filtered_cache = self.filter.filter_and_score_items(cached_items)
            ranked_cache = self.deduplicator.rank_unique(filtered_cache, seen_fingerprints)
            preferred_cache = self._filter_by_source_preference(ranked_cache, source_preference)
            fallback_cache = [item for item in ranked_cache if item not in preferred_cache]
            combined_cache = preferred_cache + fallback_cache

            selected_cache = self._select_daily_candidates(combined_cache, seen_fingerprints)
            if selected_cache:
                self.logger.info("Using cached fallback item for live posting.")
                return selected_cache[0]

        return None

    def _filter_by_source_preference(
        self,
        items: list[NewsItem],
        source_preference: str,
    ) -> list[NewsItem]:
        if source_preference == "web":
            return [
                item for item in items
                if item.source == "TradingView" or item.source == "Yahoo Finance RSS"
            ]
        if source_preference == "telegram":
            return [item for item in items if item.source.startswith("Telegram:")]
        return items

    def _collect_live_news(self) -> list[NewsItem]:
        collected: list[NewsItem] = []
        for scraper in self.scrapers:
            try:
                items = scraper.fetch()
            except Exception:
                self.logger.exception("Scraper %s failed unexpectedly.", scraper.source_name)
                continue

            self.logger.info("%s returned %s item(s).", scraper.source_name, len(items))
            collected.extend(items)
        return collected

    def _select_daily_candidates(
        self,
        candidate_items: list[NewsItem],
        seen_fingerprints: set[str],
    ) -> list[NewsItem]:
        if not candidate_items:
            return []

        ranked_items = self.deduplicator.rank_unique(candidate_items, seen_fingerprints)

        company_items = [item for item in ranked_items if item.company_tags]

        trump_items = [
            item
            for item in ranked_items
            if "trump_economy" in item.topic_tags and item not in company_items
        ]

        macro_stock_items = [
            item
            for item in ranked_items
            if (
                {"fed", "inflation", "oil_energy", "stocks"} & set(item.topic_tags)
                and item not in company_items
                and item not in trump_items
            )
        ]

        fallback_items = [
            item
            for item in ranked_items
            if item not in company_items
            and item not in trump_items
            and item not in macro_stock_items
        ]

        selected: list[NewsItem] = []
        selected_fingerprints: set[str] = set()
        target_count = max(1, self.settings.daily_post_count * 2)

        for bucket in (company_items, trump_items, macro_stock_items, fallback_items):
            for item in bucket:
                if len(selected) >= target_count:
                    return selected
                if item.fingerprint in selected_fingerprints:
                    continue
                selected.append(replace(item))
                selected_fingerprints.add(item.fingerprint)

        return selected[:target_count]

    def _next_unposted_slot_index(self, plan: DailyPostingPlan) -> int | None:
        for index in range(self.settings.daily_post_count):
            if index not in plan.posted_indices:
                return index
        return None