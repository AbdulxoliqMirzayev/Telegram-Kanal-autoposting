from __future__ import annotations

import asyncio
import json
import logging

from deep_translator import GoogleTranslator
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from models import NewsArticle, TranslatedNews

logger = logging.getLogger(__name__)

TRANSLATION_PROMPT = """
Sen moliyaviy yangiliklar tarjimonisan. Quyidagi inglizcha yangilikni O'zbek tiliga tarjima qil.
Qoidalar:
- Rasmiy O'zbek tilida yoz (lotin alifbosida)
- Moliyaviy atamalarni to'g'ri tarjima qil
- Sarlavha: qisqa va diqqat tortuvchi
- Tana: 3-5 gap, aniq va tushunarli
- Xulosa: 1-2 gap, asosiy ma'noni aks ettir
- JSON formatida qaytargin: {{"title": "...", "body": "...", "summary": "..."}}

Yangilik:
{news_text}
"""


async def translate(news: NewsArticle) -> TranslatedNews:
    if OPENAI_API_KEY:
        try:
            return await _translate_openai(news)
        except Exception:
            logger.exception("OpenAI translation failed; falling back to GoogleTranslator.")
    return await _translate_google(news)


async def _translate_openai(news: NewsArticle) -> TranslatedNews:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": TRANSLATION_PROMPT.format(news_text=news.raw_text[:5000]),
            }
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    payload = json.loads(content)
    return TranslatedNews(
        title=str(payload.get("title") or news.title_en).strip(),
        body=str(payload.get("body") or news.description).strip(),
        summary=str(payload.get("summary") or news.description[:300]).strip(),
    )


async def _translate_google(news: NewsArticle) -> TranslatedNews:
    def do_translate() -> TranslatedNews:
        translator = GoogleTranslator(source="auto", target="uzbek")
        title = translator.translate(news.title_en[:1000]) or news.title_en
        body_source = news.description or news.title_en
        body = translator.translate(body_source[:4500]) or body_source
        summary_source = body_source[:900]
        summary = translator.translate(summary_source) or summary_source
        return TranslatedNews(title=title, body=body, summary=summary)

    try:
        return await asyncio.to_thread(do_translate)
    except Exception:
        logger.exception("GoogleTranslator failed.")
        raise
