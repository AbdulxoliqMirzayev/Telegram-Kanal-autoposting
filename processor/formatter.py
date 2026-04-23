from __future__ import annotations

import html
from models import NewsArticle, TranslatedNews

ALLOWED_TOPICS = {
    "crypto": [
        "bitcoin",
        "ethereum",
        "crypto",
        "btc",
        "eth",
        "blockchain",
        "binance",
        "coinbase",
        "defi",
        "nft",
        "altcoin",
        "usdt",
        "solana",
    ],
    "aksiya": [
        "company",
        "companies",
        "corporate",
        "stock",
        "stocks",
        "shares",
        "share price",
        "equity",
        "nasdaq",
        "s&p",
        "dow jones",
        "ipo",
        "dividend",
        "earnings",
        "revenue",
        "profit",
        "quarterly results",
        "guidance",
        "buyback",
        "shareholder",
        "market value",
        "market cap",
        "tesla",
        "apple",
        "nvidia",
        "microsoft",
        "amazon",
        "google",
        "alphabet",
        "meta",
        "netflix",
        "berkshire",
        "jpmorgan",
        "goldman sachs",
        "morgan stanley",
        "exxon",
        "chevron",
    ],
    "trump": [
        "trump",
        "donald trump",
        "white house",
        "tariff",
        "trade war",
        "executive order",
        "maga",
    ],
    "dollar": [
        "dollar",
        "usd",
        "fed",
        "federal reserve",
        "interest rate",
        "inflation",
        "cpi",
        "monetary policy",
        "jerome powell",
    ],
    "iqtisodiyot": [
        "economy",
        "gdp",
        "recession",
        "economic",
        "trade",
        "unemployment",
        "jobs report",
        "growth",
        "imf",
        "world bank",
    ],
    "neft": ["oil", "opec", "crude", "brent", "energy", "gas price"],
    "oltin": ["gold", "silver", "commodity", "xau"],
}

BANNED_KEYWORDS = [
    "forex",
    "foreign exchange",
    "fx trading",
    "currency trading",
    "currency market",
    "currency pair",
    "eur/usd",
    "gbp/usd",
    "exchange rate",
    "currency exchange",
    "valyuta",
    "valyuta kursi",
    "валюта курси",
    "обменный курс",
    "usd/uzs",
    "usd/rub",
    "usd/eur",
    "pip",
    "spread",
    "metatrader",
    "mt4",
    "mt5",
    "leverage",
    "broker",
]

HASHTAG_MAP = {
    "crypto": "#crypto #bitcoin #kripto",
    "aksiya": "#aksiya #stocks #birja",
    "trump": "#trump #siyosat #iqtisodiyot",
    "dollar": "#dollar #fed",
    "iqtisodiyot": "#iqtisodiyot #economy #moliya",
    "neft": "#neft #opec #energetika",
    "oltin": "#oltin #gold #tovarlar",
}

FLAG_MAP = {
    "crypto": "🪙",
    "aksiya": "📈",
    "trump": "🇺🇸",
    "dollar": "💵",
    "iqtisodiyot": "🌐",
    "neft": "🛢",
    "oltin": "🥇",
}

LABEL_MAP = {
    "crypto": "Kripto yangilik",
    "aksiya": "Aksiya bozori",
    "trump": "Tramp yangiligi",
    "dollar": "Dollar &amp; Fed",
    "iqtisodiyot": "Iqtisodiy yangilik",
    "neft": "Neft &amp; Energetika",
    "oltin": "Oltin &amp; Tovarlar",
}


def detect_topics(text: str) -> list[str]:
    haystack = text.lower()
    if any(keyword in haystack for keyword in BANNED_KEYWORDS):
        return []

    matched: list[str] = []
    for topic, keywords in ALLOWED_TOPICS.items():
        if any(keyword in haystack for keyword in keywords):
            matched.append(topic)
    return matched


def primary_topic(topics: list[str]) -> str:
    return topics[0] if topics else "iqtisodiyot"


def format_post(translated: TranslatedNews, news: NewsArticle) -> str:
    topic = primary_topic(news.topics or [news.topic])
    flag = FLAG_MAP.get(topic, "🌐")
    label = LABEL_MAP.get(topic, "Iqtisodiy yangilik")
    hashtags = _hashtags(news.topics or [topic])

    title = html.escape(_single_line(translated.title))
    body = html.escape(_limit_sentences(translated.body, max_sentences=5))
    summary = html.escape(_limit_sentences(translated.summary, max_sentences=2))

    post = (
        f"{flag} <b>{label}</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"{body}\n\n"
        f"📌 <b>Xulosa:</b> {summary}\n\n"
        f"{hashtags}"
    )
    return _truncate_post(post)


def _hashtags(topics: list[str]) -> str:
    tags: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        for tag in HASHTAG_MAP.get(topic, "").split():
            if tag not in seen:
                tags.append(tag)
                seen.add(tag)
    return " ".join(tags) or "#iqtisodiyot #moliya"


def _single_line(value: str) -> str:
    return " ".join(value.split()).strip()


def _limit_sentences(value: str, max_sentences: int) -> str:
    text = " ".join(value.split()).strip()
    if not text:
        return ""
    sentences = [part.strip() for part in text.replace("!", ".").replace("?", ".").split(".")]
    compact = [sentence for sentence in sentences if sentence]
    if len(compact) <= max_sentences:
        return text
    return ". ".join(compact[:max_sentences]) + "."


def _truncate_post(post: str, max_length: int = 4096) -> str:
    if len(post) <= max_length:
        return post
    suffix = "\n\n..."
    return post[: max_length - len(suffix)].rstrip() + suffix
