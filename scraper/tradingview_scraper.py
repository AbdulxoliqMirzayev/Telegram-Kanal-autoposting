# from __future__ import annotations

# import logging
# import xml.etree.ElementTree as ET
# from urllib.parse import urljoin

# from config import Settings
# from models import NewsItem
# from scraper.base import BaseScraper, clean_headline, clean_text, parse_json_ld_articles


# class TradingViewNewsScraper(BaseScraper):
#     source_name = "TradingView"

#     def __init__(self, settings: Settings) -> None:
#         super().__init__(settings)
#         self.logger = logging.getLogger("scraper.tradingview")
#         self.tradingview_url = "https://www.tradingview.com/news/"
#         self.yahoo_global_rss_url = "https://finance.yahoo.com/news/rssindex"

#     def fetch(self) -> list[NewsItem]:
#         collected: list[NewsItem] = []
#         collected.extend(self._fetch_tradingview())
#         collected.extend(self._fetch_yahoo_global_feed())
#         return self.unique(collected)[: self.settings.max_news_per_source]

#     def _fetch_tradingview(self) -> list[NewsItem]:
#         soup = self.get_soup(self.tradingview_url)
#         if soup is None:
#             return []

#         items = parse_json_ld_articles(soup, "TradingView", self.tradingview_url)
#         if items:
#             return items

#         parsed: list[NewsItem] = []
#         seen_urls: set[str] = set()
#         for anchor in soup.select("a[href^='/news/'], article a[href^='/news/']"):
#             title = clean_headline(anchor.get_text(" ", strip=True))
#             href = clean_text(anchor.get("href"))
#             if len(title) < 25 or not href:
#                 continue

#             absolute_url = urljoin(self.tradingview_url, href)
#             if absolute_url in seen_urls:
#                 continue

#             summary = ""
#             article = anchor.find_parent("article")
#             if article is not None:
#                 paragraph = article.find("p")
#                 if paragraph is not None:
#                     summary = clean_text(paragraph.get_text(" ", strip=True))

#             parsed.append(
#                 NewsItem(
#                     source="TradingView",
#                     title=title,
#                     url=absolute_url,
#                     summary=summary,
#                 )
#             )
#             seen_urls.add(absolute_url)
#         return parsed

#     def _fetch_yahoo_global_feed(self) -> list[NewsItem]:
#         xml_text = self.get_text(self.yahoo_global_rss_url)
#         if not xml_text or "<rss" not in xml_text.lower():
#             return []

#         try:
#             root = ET.fromstring(xml_text)
#         except ET.ParseError as exc:
#             self.logger.warning("Yahoo Finance RSS parse failed: %s", exc, exc_info=False)
#             return []

#         items: list[NewsItem] = []
#         for node in root.findall("./channel/item"):
#             title = clean_headline(node.findtext("title", default=""))
#             link = clean_text(node.findtext("link", default=""))
#             description = clean_text(node.findtext("description", default=""))
#             published_at = clean_text(node.findtext("pubDate", default=""))
#             if len(title) < 25 or not link:
#                 continue
#             items.append(
#                 NewsItem(
#                     source="Yahoo Finance RSS",
#                     title=title,
#                     url=link,
#                     summary=description,
#                     published_at=published_at,
#                 )
#             )
#         return items


from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from config import Settings
from models import NewsItem
from scraper.base import BaseScraper, clean_headline, clean_text, parse_json_ld_articles


class TradingViewNewsScraper(BaseScraper):
    source_name = "TradingView"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.logger = logging.getLogger("scraper.tradingview")
        self.tradingview_url = "https://www.tradingview.com/news/"
        self.yahoo_global_rss_url = "https://finance.yahoo.com/news/rssindex"

    def fetch(self) -> list[NewsItem]:
        collected: list[NewsItem] = []
        collected.extend(self._fetch_tradingview())
        collected.extend(self._fetch_yahoo_global_feed())
        return self.unique(collected)[: self.settings.max_news_per_source]

    def _fetch_tradingview(self) -> list[NewsItem]:
        soup = self.get_soup(self.tradingview_url)
        if soup is None:
            return []

        items = parse_json_ld_articles(soup, "TradingView", self.tradingview_url)
        if items:
            enriched: list[NewsItem] = []
            for item in items:
                image_url = self._extract_image_for_url(soup, item.url)
                item.image_url = image_url
                enriched.append(item)
            return enriched

        parsed: list[NewsItem] = []
        seen_urls: set[str] = set()

        for anchor in soup.select("a[href^='/news/'], article a[href^='/news/']"):
            title = clean_headline(anchor.get_text(" ", strip=True))
            href = clean_text(anchor.get("href"))
            if len(title) < 25 or not href:
                continue

            absolute_url = urljoin(self.tradingview_url, href)
            if absolute_url in seen_urls:
                continue

            summary = ""
            image_url = ""
            article = anchor.find_parent("article")

            if article is not None:
                paragraph = article.find("p")
                if paragraph is not None:
                    summary = clean_text(paragraph.get_text(" ", strip=True))

                image = article.find("img")
                if image is not None:
                    image_url = clean_text(
                        image.get("src")
                        or image.get("data-src")
                        or image.get("srcset", "").split(" ")[0]
                    )
                    if image_url.startswith("/"):
                        image_url = urljoin(self.tradingview_url, image_url)

            parsed.append(
                NewsItem(
                    source="TradingView",
                    title=title,
                    url=absolute_url,
                    summary=summary,
                    image_url=image_url,
                )
            )
            seen_urls.add(absolute_url)

        return parsed

    def _fetch_yahoo_global_feed(self) -> list[NewsItem]:
        xml_text = self.get_text(self.yahoo_global_rss_url)
        if not xml_text or "<rss" not in xml_text.lower():
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            self.logger.warning("Yahoo Finance RSS parse failed: %s", exc, exc_info=False)
            return []

        items: list[NewsItem] = []
        for node in root.findall("./channel/item"):
            title = clean_headline(node.findtext("title", default=""))
            link = clean_text(node.findtext("link", default=""))
            description = clean_text(node.findtext("description", default=""))
            published_at = clean_text(node.findtext("pubDate", default=""))

            if len(title) < 25 or not link:
                continue

            items.append(
                NewsItem(
                    source="Yahoo Finance RSS",
                    title=title,
                    url=link,
                    summary=description,
                    published_at=published_at,
                    image_url="",
                )
            )

        return items

    @staticmethod
    def _extract_image_for_url(soup, absolute_url: str) -> str:
        for anchor in soup.select("a[href^='/news/'], article a[href^='/news/']"):
            href = clean_text(anchor.get("href"))
            candidate_url = urljoin("https://www.tradingview.com/news/", href)
            if candidate_url != absolute_url:
                continue

            article = anchor.find_parent("article")
            if article is None:
                return ""

            image = article.find("img")
            if image is None:
                return ""

            image_url = clean_text(
                image.get("src")
                or image.get("data-src")
                or image.get("srcset", "").split(" ")[0]
            )
            if image_url.startswith("/"):
                return urljoin("https://www.tradingview.com/news/", image_url)
            return image_url

        return ""
    


    