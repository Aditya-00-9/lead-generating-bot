import json

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config.settings import Settings
from app.models.schemas import AIEnrichmentResult, NormalizedMention
from app.prompts.enrichment import SYSTEM_PROMPT, USER_TEMPLATE

logger = structlog.get_logger(__name__)


class OpenAIEnricher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)

    @retry(wait=wait_exponential(min=1, max=20), stop=stop_after_attempt(3), reraise=True)
    async def enrich(self, mention: NormalizedMention) -> AIEnrichmentResult:
        prompt = USER_TEMPLATE.format(
            competitors=", ".join(self.settings.competitors),
            source=mention.source,
            platform=mention.platform,
            title=mention.title,
            cleaned_text=mention.cleaned_text[:6000],
            source_url=mention.source_url,
        )
        resp = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content or "{}"
        payload = json.loads(content)
        result = AIEnrichmentResult.model_validate(payload)
        logger.info("ai.enrichment.success", source=mention.source, url=mention.source_url)
        return result
