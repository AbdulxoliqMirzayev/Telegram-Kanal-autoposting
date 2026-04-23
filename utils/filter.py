# from __future__ import annotations

# import hashlib
# import re
# from urllib.parse import urlparse

# from models import NewsItem

# FOCUS_COMPANIES = {
#     "Apple": {"apple", "aapl", "iphone"},
#     "Nvidia": {"nvidia", "nvda", "h100", "blackwell"},
#     "Microsoft": {"microsoft", "msft", "azure"},
#     "Tesla": {"tesla", "tsla", "elon musk"},
#     "Amazon": {"amazon", "amzn", "aws"},
#     "Google": {"alphabet", "google", "googl", "goog"},
#     "Meta": {"meta", "facebook", "instagram", "whatsapp"},
# }

# MACRO_TOPICS = {
#     "usd": {"usd", "us dollar", "dollar index", "greenback"},
#     "fed": {"federal reserve", "fed", "powell", "fomc", "rate cut", "rate hike"},
#     "inflation": {"inflation", "cpi", "pce", "consumer prices"},
#     "oil_energy": {"oil", "crude", "wti", "brent", "energy", "opec", "natural gas"},
#     "trump_economy": {
#         "donald trump",
#         "trump",
#         "tariff",
#         "tariffs",
#         "trade war",
#         "trade policy",
#     },
# }

# ECONOMY_CONTEXT = {
#     "economy",
#     "economic",
#     "markets",
#     "market",
#     "stocks",
#     "shares",
#     "earnings",
#     "inflation",
#     "rate",
#     "rates",
#     "dollar",
#     "fed",
#     "oil",
#     "tariff",
#     "investor",
#     "guidance",
# }

# LOW_QUALITY_PATTERNS = {
#     "photo",
#     "photos",
#     "video",
#     "watch:",
#     "opinion",
#     "podcast",
#     "quiz",
#     "live blog",
#     "live updates",
#     "celebrity",
#     "sports",
#     "fashion",
#     "crypto meme",
# }


# def normalize_text(value: str) -> str:
#     text = value.lower().strip()
#     text = re.sub(r"https?://\S+", " ", text)
#     text = re.sub(r"[^a-z0-9\s]+", " ", text)
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# class NewsFilter:
#     def annotate(self, item: NewsItem) -> NewsItem:
#         combined_text = normalize_text(f"{item.title} {item.summary}")

#         company_tags = [
#             company
#             for company, keywords in FOCUS_COMPANIES.items()
#             if any(keyword in combined_text for keyword in keywords)
#         ]
#         topic_tags = [
#             topic
#             for topic, keywords in MACRO_TOPICS.items()
#             if any(keyword in combined_text for keyword in keywords)
#         ]

#         item.company_tags = company_tags
#         item.topic_tags = topic_tags
#         item.fingerprint = self.build_fingerprint(item)
#         return item

#     def keep(self, item: NewsItem) -> bool:
#         if not item.title or len(item.title.strip()) < 18:
#             return False

#         self.annotate(item)
#         if not item.company_tags and not item.topic_tags:
#             return False

#         combined_text = normalize_text(f"{item.title} {item.summary}")
#         if any(pattern in combined_text for pattern in LOW_QUALITY_PATTERNS):
#             return False

#         if "trump_economy" in item.topic_tags and not any(
#             term in combined_text for term in ECONOMY_CONTEXT
#         ):
#             return False

#         return True

#     def score(self, item: NewsItem) -> NewsItem:
#         combined_text = normalize_text(f"{item.title} {item.summary}")

#         importance = 2
#         if item.company_tags:
#             importance += 4
#         if len(item.company_tags) > 1:
#             importance += 1
#         if {"fed", "inflation", "oil_energy", "usd"} & set(item.topic_tags):
#             importance += 2
#         if "trump_economy" in item.topic_tags:
#             importance += 1
#         if any(
#             term in combined_text
#             for term in {
#                 "earnings",
#                 "guidance",
#                 "forecast",
#                 "revenue",
#                 "profit",
#                 "beats",
#                 "misses",
#                 "rises",
#                 "falls",
#                 "surges",
#                 "plunges",
#                 "tariff",
#                 "opec",
#                 "inflation",
#             }
#         ):
#             importance += 2

#         market_impact = 2
#         if item.company_tags:
#             market_impact += 3
#         if {"fed", "usd", "inflation"} & set(item.topic_tags):
#             market_impact += 3
#         if "oil_energy" in item.topic_tags:
#             market_impact += 2
#         if any(
#             term in combined_text
#             for term in {"earnings", "guidance", "forecast", "tariff", "opec", "fed"}
#         ):
#             market_impact += 2

#         item.importance_score = min(10, importance)
#         item.market_impact_score = min(10, market_impact)
#         item.total_score = (item.importance_score * 2) + item.market_impact_score
#         return item

#     def filter_and_score_items(self, items: list[NewsItem]) -> list[NewsItem]:
#         filtered: list[NewsItem] = []
#         for item in items:
#             if self.keep(item):
#                 filtered.append(self.score(item))
#         return filtered

#     @staticmethod
#     def build_fingerprint(item: NewsItem) -> str:
#         normalized_title = normalize_text(item.title)
#         host = urlparse(item.url).netloc.lower()
#         raw = f"{host}|{normalized_title}"
#         return hashlib.sha1(raw.encode("utf-8")).hexdigest()


from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from models import NewsItem

FOCUS_COMPANIES = {
    "Apple": {"apple", "aapl", "iphone", "ipad", "mac"},
    "Nvidia": {"nvidia", "nvda", "blackwell", "h100", "gpu"},
    "Microsoft": {"microsoft", "msft", "azure", "openai partnership"},
    "Tesla": {"tesla", "tsla", "elon musk", "model y", "model 3"},
    "Amazon": {"amazon", "amzn", "aws", "prime"},
    "Google": {"alphabet", "google", "googl", "goog", "gemini"},
    "Meta": {"meta", "facebook", "instagram", "whatsapp", "threads"},
    "Netflix": {"netflix", "nflx"},
    "AMD": {"amd", "advanced micro devices"},
    "Intel": {"intel", "intc"},
    "Oracle": {"oracle", "orcl"},
    "Broadcom": {"broadcom", "avgo"},
    "Palantir": {"palantir", "pltr"},
    "Salesforce": {"salesforce", "crm"},
    "JPMorgan": {"jpmorgan", "jpm", "jamie dimon"},
    "Goldman Sachs": {"goldman sachs", "gs"},
    "Bank of America": {"bank of america", "bac"},
    "Morgan Stanley": {"morgan stanley", "ms"},
    "Visa": {"visa", "v"},
    "Mastercard": {"mastercard", "ma"},
    "Berkshire Hathaway": {"berkshire", "brk", "warren buffett"},
    "ExxonMobil": {"exxon", "xom", "exxonmobil"},
    "Chevron": {"chevron", "cvx"},
    "Saudi Aramco": {"aramco"},
    "Coca-Cola": {"coca cola", "ko"},
    "PepsiCo": {"pepsico", "pep"},
    "Walmart": {"walmart", "wmt"},
    "Costco": {"costco", "cost"},
    "Alibaba": {"alibaba", "baba"},
    "Tencent": {"tencent"},
    "Toyota": {"toyota", "tm"},
    "Samsung": {"samsung"},
    "Sony": {"sony"},
    "Adobe": {"adobe", "adbe"},
    "Uber": {"uber"},
    "Airbnb": {"airbnb", "abnb"},
    "Qualcomm": {"qualcomm", "qcom"},
    "Boeing": {"boeing", "ba"},
    "Caterpillar": {"caterpillar", "cat"},
    "Pfizer": {"pfizer", "pfe"},
    "Johnson & Johnson": {"johnson johnson", "jnj"},
    "Eli Lilly": {"eli lilly", "lly"},
}

MACRO_TOPICS = {
    "fed": {"federal reserve", "fed", "fomc", "powell", "rate cut", "rate hike"},
    "inflation": {"inflation", "cpi", "pce", "consumer prices"},
    "oil_energy": {"oil", "crude", "wti", "brent", "opec", "energy"},
    "trump_economy": {
        "donald trump",
        "trump",
        "tariff",
        "tariffs",
        "trade policy",
        "trade war",
    },
    "stocks": {
        "stock",
        "stocks",
        "shares",
        "equity",
        "equities",
        "earnings",
        "guidance",
        "revenue",
        "profit",
        "forecast",
        "wall street",
        "nasdaq",
        "s&p 500",
        "dow jones",
        "investor",
        "market cap",
    },
}

# Bular chiqmasin
FOREX_PATTERNS = {
    "eur/usd",
    "usd/jpy",
    "gbp/usd",
    "aud/usd",
    "usd/cad",
    "usd/chf",
    "nzd/usd",
    "xau/usd",
    "dxy:",
    "forex",
    "fx market",
    "currency pair",
    "yen",
    "euro",
    "sterling",
}

LOW_QUALITY_PATTERNS = {
    "photo",
    "photos",
    "video",
    "watch:",
    "opinion",
    "podcast",
    "quiz",
    "live blog",
    "live updates",
    "celebrity",
    "sports",
    "fashion",
    "crypto meme",
    "bitcoin",
    "btc/usd",
    "eth/usd",
    "stablecoin",
    "token",
    "altcoin",
    "crypto market recap",
}

TRUMP_MARKET_CONTEXT = {
    "tariff",
    "trade",
    "market",
    "stocks",
    "shares",
    "economy",
    "economic",
    "company",
    "companies",
    "earnings",
    "inflation",
    "fed",
    "oil",
    "manufacturing",
    "policy",
    "wall street",
    "nasdaq",
    "s&p",
}

MACRO_STOCK_CONTEXT = {
    "stocks",
    "shares",
    "equities",
    "earnings",
    "company",
    "companies",
    "investor",
    "investors",
    "wall street",
    "nasdaq",
    "s&p 500",
    "dow jones",
    "tech stocks",
    "market cap",
    "guidance",
    "revenue",
    "profit",
}


def normalize_text(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9/\s&.+-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class NewsFilter:
    def annotate(self, item: NewsItem) -> NewsItem:
        combined_text = normalize_text(f"{item.title} {item.summary}")

        company_tags = [
            company
            for company, keywords in FOCUS_COMPANIES.items()
            if any(keyword in combined_text for keyword in keywords)
        ]
        topic_tags = [
            topic
            for topic, keywords in MACRO_TOPICS.items()
            if any(keyword in combined_text for keyword in keywords)
        ]

        item.company_tags = company_tags
        item.topic_tags = topic_tags
        item.fingerprint = self.build_fingerprint(item)
        return item

    def keep(self, item: NewsItem) -> bool:
        if not item.title or len(item.title.strip()) < 18:
            return False

        self.annotate(item)
        combined_text = normalize_text(f"{item.title} {item.summary}")

        if any(pattern in combined_text for pattern in LOW_QUALITY_PATTERNS):
            return False

        # Sof forex/currency postlarni kesib tashlaymiz
        if any(pattern in combined_text for pattern in FOREX_PATTERNS):
            # faqat kompaniya bo'lsa qoldiramiz
            if not item.company_tags:
                return False

        # Kompaniya bo'lsa doim prioritet
        if item.company_tags:
            return True

        # Trump faqat bozor/kompaniya/economy context bo'lsa
        if "trump_economy" in item.topic_tags:
            return any(term in combined_text for term in TRUMP_MARKET_CONTEXT)

        # Fed / inflation / oil faqat stock-market context bilan bo'lsa
        if {"fed", "inflation", "oil_energy"} & set(item.topic_tags):
            return any(term in combined_text for term in MACRO_STOCK_CONTEXT)

        # Stocks topic bo'lsa qoldiramiz
        if "stocks" in item.topic_tags:
            return True

        return False

    def score(self, item: NewsItem) -> NewsItem:
        combined_text = normalize_text(f"{item.title} {item.summary}")

        importance = 2
        market_impact = 2

        if item.company_tags:
            importance += 5
            market_impact += 4

        if len(item.company_tags) > 1:
            importance += 1
            market_impact += 1

        if "stocks" in item.topic_tags:
            importance += 2
            market_impact += 2

        if {"fed", "inflation", "oil_energy"} & set(item.topic_tags):
            importance += 1
            market_impact += 2

        if "trump_economy" in item.topic_tags:
            importance += 1
            market_impact += 2

        if any(
            term in combined_text
            for term in {
                "earnings",
                "guidance",
                "forecast",
                "revenue",
                "profit",
                "beats",
                "misses",
                "surges",
                "plunges",
                "tariff",
                "opec",
                "deal",
                "acquisition",
                "partnership",
                "buyback",
            }
        ):
            importance += 2
            market_impact += 2

        item.importance_score = min(10, importance)
        item.market_impact_score = min(10, market_impact)
        item.total_score = (item.importance_score * 2) + item.market_impact_score
        return item

    def filter_and_score_items(self, items: list[NewsItem]) -> list[NewsItem]:
        filtered: list[NewsItem] = []
        for item in items:
            if self.keep(item):
                filtered.append(self.score(item))
        return filtered

    @staticmethod
    def build_fingerprint(item: NewsItem) -> str:
        normalized_title = normalize_text(item.title)
        host = urlparse(item.url).netloc.lower()
        raw = f"{host}|{normalized_title}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()