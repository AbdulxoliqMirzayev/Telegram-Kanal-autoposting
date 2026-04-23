# from __future__ import annotations

# import json
# import logging
# from typing import cast

# from pydantic import BaseModel, Field

# from config import Settings
# from models import NewsItem, PostDraft


# class UzbekPostPayload(BaseModel):
#     index: int
#     headline_uz: str = Field(min_length=6, max_length=110)
#     news_uz: str = Field(min_length=20, max_length=360)
#     insight_uz: str = Field(min_length=12, max_length=220)


# class UzbekPostBatch(BaseModel):
#     items: list[UzbekPostPayload]


# class UzbekNewsAnalyzer:
#     def __init__(self, settings: Settings) -> None:
#         self.settings = settings
#         self.logger = logging.getLogger(self.__class__.__name__)

#     def analyze(self, items: list[NewsItem]) -> list[PostDraft]:
#         if not items:
#             return []
#         try:
#             return self._analyze_with_openai(items)
#         except Exception as exc:
#             self.logger.warning(
#                 "OpenAI analysis failed, switching to local Uzbek fallback: %s",
#                 exc,
#                 exc_info=False,
#             )
#             return self._fallback_posts(items)

#     def _analyze_with_openai(self, items: list[NewsItem]) -> list[PostDraft]:
#         from openai import OpenAI

#         client = OpenAI(api_key=self.settings.openai_api_key)
#         payload = [
#             {
#                 "index": index,
#                 "source": item.source,
#                 "title": item.title,
#                 "summary": item.summary,
#                 "company_tags": item.company_tags,
#                 "topic_tags": item.topic_tags,
#                 "importance_score": item.importance_score,
#                 "market_impact_score": item.market_impact_score,
#             }
#             for index, item in enumerate(items, start=1)
#         ]

#         response = client.responses.parse(
#             model=self.settings.openai_model,
#             input=[
#                 {
#                     "role": "system",
#                     "content": (
#                         "You are an Uzbek financial news editor. "
#                         "Write natural, fluent Uzbek for investors, not robotic or literal translation. "
#                         "For each item return: "
#                         "1) a short, punchy Uzbek headline, "
#                         "2) a clear 2-3 sentence Uzbek explanation of the news, "
#                         "3) a short investor takeaway in Uzbek. "
#                         "Stay factual, professional, easy to read, and avoid repetition."
#                     ),
#                 },
#                 {
#                     "role": "user",
#                     "content": json.dumps(payload, ensure_ascii=False),
#                 },
#             ],
#             text_format=UzbekPostBatch,
#         )

#         parsed = cast(UzbekPostBatch | None, response.output_parsed)
#         if parsed is None or len(parsed.items) != len(items):
#             raise RuntimeError("Structured Uzbek output was incomplete.")

#         mapped = {entry.index: entry for entry in parsed.items}
#         posts: list[PostDraft] = []
#         for index, item in enumerate(items, start=1):
#             analyzed = mapped[index]
#             posts.append(
#                 PostDraft(
#                     fingerprint=item.fingerprint,
#                     source=item.source,
#                     source_title=item.title,
#                     source_url=item.url,
#                     importance_score=item.importance_score,
#                     market_impact_score=item.market_impact_score,
#                     headline_uz=analyzed.headline_uz.strip(),
#                     news_uz=analyzed.news_uz.strip(),
#                     insight_uz=analyzed.insight_uz.strip(),
#                     company_tags=item.company_tags,
#                     topic_tags=item.topic_tags,
#                 )
#             )
#         return posts

#     def _fallback_posts(self, items: list[NewsItem]) -> list[PostDraft]:
#         return [
#             PostDraft(
#                 fingerprint=item.fingerprint,
#                 source=item.source,
#                 source_title=item.title,
#                 source_url=item.url,
#                 importance_score=item.importance_score,
#                 market_impact_score=item.market_impact_score,
#                 headline_uz=self._headline(item),
#                 news_uz=self._news(item),
#                 insight_uz=self._insight(item),
#                 company_tags=item.company_tags,
#                 topic_tags=item.topic_tags,
#             )
#             for item in items
#         ]

#     def _headline(self, item: NewsItem) -> str:
#         if item.company_tags:
#             return f"{item.company_tags[0]} bo‘yicha bozor uchun muhim xabar"
#         if "fed" in item.topic_tags:
#             return "Fed bo‘yicha yangi signal paydo bo‘ldi"
#         if "oil_energy" in item.topic_tags:
#             return "Energiya bozorida e’tiborli o‘zgarish"
#         return "Bozor uchun muhim yangilik"

#     def _news(self, item: NewsItem) -> str:
#         seed = (item.summary or item.title).strip().rstrip(".")
#         if item.company_tags:
#             company = item.company_tags[0]
#             return (
#                 f"{company} atrofidagi ushbu xabar bozorda yangi baholashlarni keltirib chiqarmoqda. "
#                 f"Investorlar endi yangilikning daromad, o‘sish sur’ati va aksiyalar kayfiyatiga ta’sirini kuzatadi."
#             )
#         if "fed" in item.topic_tags or "inflation" in item.topic_tags:
#             return (
#                 f"{seed}. Bu mavzu stavkalar, dollar va aksiyalar bahosiga tez ta’sir qilishi mumkin. "
#                 f"Shu sabab investorlar bu yo‘nalishni diqqat bilan kuzatmoqda."
#             )
#         return (
#             f"{seed}. Bu xabar global bozor kayfiyati uchun muhim fon yaratmoqda. "
#             f"Ayniqsa yirik kompaniyalar va sektor indekslari bu signalga tez javob berishi mumkin."
#         )

#     def _insight(self, item: NewsItem) -> str:
#         if item.company_tags:
#             return (
#                 "Kompaniya bo‘yicha bunday signal aksiyalar narxi, analitik kutishlari va sektor sentimentiga bevosita ta’sir qiladi."
#             )
#         if "fed" in item.topic_tags or "usd" in item.topic_tags:
#             return "Dollar va Fed bo‘yicha har qanday o‘zgarish aksiyalar, obligatsiyalar va risk ishtahasini qayta narxlaydi."
#         if "oil_energy" in item.topic_tags:
#             return "Energiya bozori harakati inflyatsiya foniga va ko‘plab sektorlarning marjasiga ta’sir qiladi."
#         return "Yangilik investor qarorlari va qisqa muddatli bozor kayfiyatiga ta’sir ko‘rsatishi mumkin."

from __future__ import annotations

import json
import logging

from openai import OpenAI

from config import Settings
from models import NewsItem, PostDraft


class UzbekNewsAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client = OpenAI(api_key=settings.openai_api_key)

    def analyze(self, items: list[NewsItem]) -> list[PostDraft]:
        drafts: list[PostDraft] = []
        for item in items:
            try:
                draft = self._analyze_one(item)
                drafts.append(draft)
            except Exception:
                self.logger.exception("Failed to analyze news item: %s", item.title)
        return drafts

    def _analyze_one(self, item: NewsItem) -> PostDraft:
        prompt = f"""
Sen professional o'zbek moliyaviy kontent muharririsan.

Vazifa:
Berilgan yangilikni tabiiy, silliq, qisqa va Telegram uchun qulay o'zbekcha formatda yoz.

Muhim qoidalar:
- "Sarlavha", "Yangilik", "Xulosa" degan label so'zlarni yozma.
- Juda sun'iy yoki robotcha tarjima qilma.
- Qisqa mavzu nomi yoz.
- Asosiy matn 2-4 gap bo'lsin.
- Oxirida 1 gaplik juda qisqa xulosa yoz.
- Matn investorlar uchun tushunarli bo'lsin.
- Company nomlarini noto'g'ri tarjima qilma.
- Agar xabar kompaniya haqida bo'lsa, aynan shu kompaniyaga urg'u ber.
- Agar xabar dollar/Fed/inflatsiya/neft haqida bo'lsa, bozor ta'sirini sodda tushuntir.
- Ortiqcha bezak, bo'lim, baho, manba yozma.

Quyidagi JSON formatda qaytar:
{{
  "headline_uz": "qisqa mavzu nomi",
  "news_uz": "asosiy 2-4 gaplik matn",
  "insight_uz": "1 gaplik qisqa xulosa"
}}

Manba: {item.source}
Sarlavha: {item.title}
Qisqa mazmun: {item.summary}
URL: {item.url}
Company tags: {", ".join(item.company_tags)}
Topic tags: {", ".join(item.topic_tags)}
"""

        response = self.client.chat.completions.create(
    model=self.settings.openai_model,
    messages=[
        {
            "role": "system",
            "content": "Siz professional o'zbek moliyaviy muharrirsiz.",
        },
        {"role": "user", "content": prompt},
    ],
)

        content = response.choices[0].message.content.strip()
        parsed = self._parse_json(content)

        return PostDraft(
            fingerprint=item.fingerprint,
            source=item.source,
            source_title=item.title,
            source_url=item.url,
            importance_score=item.importance_score,
            market_impact_score=item.market_impact_score,
            headline_uz=parsed["headline_uz"].strip(),
            news_uz=parsed["news_uz"].strip(),
            insight_uz=parsed["insight_uz"].strip(),
            company_tags=item.company_tags,
            topic_tags=item.topic_tags,
            image_url=item.image_url,
        )

    def _parse_json(self, content: str) -> dict[str, str]:
        try:
            data = json.loads(content)
            return {
                "headline_uz": str(data.get("headline_uz", "")).strip(),
                "news_uz": str(data.get("news_uz", "")).strip(),
                "insight_uz": str(data.get("insight_uz", "")).strip(),
            }
        except Exception:
            cleaned = content.strip().strip("`")
            return {
                "headline_uz": "Bozor uchun muhim yangilik",
                "news_uz": cleaned[:700],
                "insight_uz": "Bu xabar investorlar kayfiyatiga ta'sir qilishi mumkin.",
            }
        