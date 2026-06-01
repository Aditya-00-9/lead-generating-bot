import json
from typing import Any

import structlog
from openai import APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config.settings import Settings
from app.models.schemas import AIEnrichmentResult, NormalizedMention
from app.prompts.enrichment import USER_TEMPLATE

logger = structlog.get_logger(__name__)

_TRIAGE_BATCH_SIZE = 8


def _gate3_system_prompt(reply_context: str) -> str:
    ctx = reply_context.strip()
    block = f"{ctx}\n" if ctx else ""
    return f"""You are a sales intelligence assistant for KramaAI.
{block}Generate replies that are empathetic and specific. No buzzwords. No exclamation points.
Reference the exact pain point mentioned. Never lead with price.

You MUST return strict JSON and no prose.
Only use facts present in the input text. Do not invent details.
If uncertain, lower confidence with conservative scores.

Return JSON with:
competitor: string
detected_pain_points: string[]
intent_score: float (0-100)
intent_label: "HIGH" | "MEDIUM" | "LOW"
worth_responding: boolean
ai_summary: string (<=320 chars)
suggested_reply: string (human, empathetic, non-salesy, subtle KramaAI mention, <=420 chars)
sentiment: "negative" | "neutral" | "mixed"
urgency_score: float (0-100)
engagement_score: float (0-100)
tags: string[]"""


class OpenAIEnricher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
        self.api_call_count = 0

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        reraise=True,
    )
    async def _call_openai(self, **kwargs: Any) -> Any:
        self.api_call_count += 1
        return await self.client.chat.completions.create(**kwargs)

    async def enrich(self, mention: NormalizedMention) -> AIEnrichmentResult:
        prompt = USER_TEMPLATE.format(
            competitors=", ".join(self.settings.competitors),
            source=mention.source,
            platform=mention.platform,
            title=mention.title,
            cleaned_text=mention.cleaned_text[:6000],
            source_url=mention.source_url,
        )
        resp = await self._call_openai(
            model=self.settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _gate3_system_prompt(self.settings.reply_context)},
                {"role": "user", "content": prompt},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        payload = json.loads(content)
        result = AIEnrichmentResult.model_validate(payload)
        logger.info("ai.enrichment.success", source=mention.source, url=mention.source_url)
        return result

    async def _triage_one(self, mention: NormalizedMention) -> dict[str, Any]:
        user = (
            f"Analyze this competitor mention. Return ONLY JSON with keys: "
            f'competitor, pain_points (array), intent_score (0-100), source_quality (0-100).\n\n'
            f"text: {mention.cleaned_text[:4000]}"
        )
        resp = await self._call_openai(
            model=self.settings.openai_triage_model_name,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Return strict JSON only. Use facts from the text.",
                },
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    async def _triage_batch_chunk(self, mentions: list[NormalizedMention]) -> list[dict[str, Any]]:
        n = len(mentions)
        lines = "\n".join(f"[{i + 1}] {m.cleaned_text[:2000]}" for i, m in enumerate(mentions))
        user = (
            f"Analyze these {n} competitor mentions. Return ONLY a JSON array of {n} objects in the same order.\n"
            f'Each object: {{ "competitor": str, "pain_points": [str], "intent_score": int 0-100, '
            f'"source_quality": int 0-100 }}\n\nMentions:\n{lines}'
        )
        resp = await self._call_openai(
            model=self.settings.openai_triage_model_name,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Return a JSON object with key items: an array of exactly {n} objects in order."
                    ),
                },
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        payload = json.loads(content)
        items = payload if isinstance(payload, list) else payload.get("items", payload.get("results", []))
        if not isinstance(items, list) or len(items) != n:
            raise ValueError("batch triage shape mismatch")
        return items

    def _normalize_triage(self, raw: dict[str, Any]) -> dict[str, Any]:
        pain = raw.get("pain_points") or raw.get("detected_pain_points") or []
        if not isinstance(pain, list):
            pain = [str(pain)] if pain else []
        return {
            "competitor": str(raw.get("competitor") or "Unknown"),
            "pain_points": [str(p) for p in pain],
            "intent_score": int(float(raw.get("intent_score", 0))),
            "source_quality": int(float(raw.get("source_quality", 0))),
        }

    async def triage_batch(self, mentions: list[NormalizedMention]) -> list[dict[str, Any]]:
        if not mentions:
            return []
        results: list[dict[str, Any]] = []
        for start in range(0, len(mentions), _TRIAGE_BATCH_SIZE):
            chunk = mentions[start : start + _TRIAGE_BATCH_SIZE]
            try:
                batch = await self._triage_batch_chunk(chunk)
                results.extend(self._normalize_triage(item) for item in batch)
            except Exception as exc:
                logger.warning("triage.batch.fallback", error=str(exc), size=len(chunk))
                for mention in chunk:
                    try:
                        results.append(self._normalize_triage(await self._triage_one(mention)))
                    except Exception as one_exc:
                        logger.error("triage.one.failed", url=mention.source_url, error=str(one_exc))
                        results.append(
                            {
                                "competitor": "Unknown",
                                "pain_points": [],
                                "intent_score": 0,
                                "source_quality": 0,
                            }
                        )
        return results
