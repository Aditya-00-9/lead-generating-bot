import asyncio
import hashlib
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.classifiers.openai_enricher import OpenAIEnricher
from app.config.settings import Settings
from app.dedupe.engine import DedupeEngine, DedupeDecision
from app.models.lead import IntentLabel, Lead
from app.models.schemas import AIEnrichmentResult, NormalizedMention
from app.ranking.lead_ranker import LeadRanker
from app.prompts.collection_signals import (
    blend_source_quality,
    passes_competitor_context,
    text_has_pain_signal,
)
from app.observability.collector_health import all_collector_health, record_collector_run, set_last_run_snapshot
from app.observability.cost_estimate import estimate_run_cost
from app.services.collector_factory import build_collectors
from app.services.lead_backfill import backfill_platform_and_ranks
from app.services.quality_feedback import aggregate_high_quality_combos, export_quality_feedback_report
from app.services.report_exporter import ReportExporter
from app.slack.digest import RunTelemetry, filter_digest_leads, send_slack_digest, upload_report_to_slack
from app.storage.lead_repository import LeadRepository
from app.storage.report_repository import ReportRepository

logger = structlog.get_logger(__name__)

_TRIAGE_SEM = asyncio.Semaphore(int(os.getenv("TRIAGE_CONCURRENCY", "10")))
_ENRICH_SEM = asyncio.Semaphore(int(os.getenv("ENRICHMENT_CONCURRENCY", "5")))


def _content_hash(source_url: str, text: str) -> str:
    return hashlib.sha256(f"{source_url.strip()}::{text.strip().lower()}".encode()).hexdigest()


def should_persist_gate1_fail(mention: NormalizedMention, min_relevance: float) -> bool:
    """Gate1-fail items lack pain keywords; only persist when collection relevance is high."""
    score = mention.collection_relevance_score
    if score is None:
        return False
    return score >= min_relevance


def should_full_enrich(mention: NormalizedMention) -> bool:
    """Expensive enrichment only for pain-signal mentions that are not stale."""
    if not text_has_pain_signal(mention.cleaned_text):
        return False
    signal = (mention.recency_signal or "").strip().lower()
    return signal != "older"


def _collector_usage_stats(collectors: list) -> tuple[int, int, int]:
    web_searches = 0
    deep_extracts = 0
    extract_chars = 0
    for collector in collectors:
        web_searches += int(getattr(collector, "last_run_web_searches", 0) or 0)
        deep_extracts += int(getattr(collector, "last_run_deep_extracts", 0) or 0)
        extractor = getattr(collector, "_page_extractor", None) or getattr(collector, "_extractor", None)
        if extractor is not None:
            extract_chars += int(getattr(extractor, "last_extract_input_chars", 0) or 0)
    return web_searches, deep_extracts, extract_chars


def _intent_from_score(score: float) -> IntentLabel:
    if score >= 70:
        return IntentLabel.high
    if score >= 50:
        return IntentLabel.medium
    return IntentLabel.low


def _low_enrichment(mention: NormalizedMention) -> AIEnrichmentResult:
    competitor = mention.competitor_mentioned or "Unknown"
    pain = [mention.pain_category] if mention.pain_category and mention.pain_category != "other" else []
    return AIEnrichmentResult(
        competitor=competitor,
        detected_pain_points=pain,
        intent_score=0.0,
        intent_label=IntentLabel.low,
        worth_responding=False,
        ai_summary=mention.cleaned_text[:320],
        suggested_reply=(mention.suggested_hook or "")[:420],
        sentiment="neutral",
        urgency_score=0.0,
        engagement_score=0.0,
        tags=[],
    )


def _enrichment_from_triage(triage: dict, mention: NormalizedMention, min_score: float) -> AIEnrichmentResult:
    score = float(triage["intent_score"])
    return AIEnrichmentResult(
        competitor=triage["competitor"],
        detected_pain_points=triage["pain_points"],
        intent_score=score,
        intent_label=_intent_from_score(score),
        worth_responding=score >= min_score,
        ai_summary=mention.cleaned_text[:320],
        suggested_reply="",
        sentiment="neutral",
        urgency_score=0.0,
        engagement_score=float(triage["source_quality"]),
        tags=[],
    )


def _enrichment_from_lead(lead: Lead) -> AIEnrichmentResult:
    return AIEnrichmentResult(
        competitor=lead.competitor,
        detected_pain_points=list(lead.detected_pain_points or []),
        intent_score=lead.intent_score,
        intent_label=lead.intent_label,
        worth_responding=lead.worth_responding,
        ai_summary=lead.ai_summary,
        suggested_reply=lead.suggested_reply,
        sentiment=lead.sentiment,
        urgency_score=lead.urgency_score,
        engagement_score=lead.engagement_score,
        tags=list(lead.tags or []),
    )


@dataclass
class _WorkItem:
    mention: NormalizedMention
    dedupe: DedupeDecision
    content_hash: str


class LeadPipelineService:
    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        self.settings = settings
        self.session = session
        self.dedupe = DedupeEngine(
            similarity_threshold=settings.duplicate_similarity_threshold,
            window_days=settings.duplicate_window_days,
            candidate_window=settings.dedupe_candidate_window,
        )
        self.enricher = OpenAIEnricher(settings)
        self.ranker = LeadRanker()
        self.collectors = build_collectors(settings)
        self._db_lock = asyncio.Lock()

    def _compute_rank(
        self,
        enrichment: AIEnrichmentResult,
        mention: NormalizedMention,
        source_quality: float,
        ingested_at: datetime,
    ) -> float:
        blended_quality = blend_source_quality(source_quality, mention.collection_relevance_score)
        return self.ranker.score(
            intent=enrichment.intent_score,
            urgency=enrichment.urgency_score,
            engagement=enrichment.engagement_score,
            source_quality=blended_quality,
            source=mention.source,
            competitor=enrichment.competitor,
            ingested_at=ingested_at,
            platform=mention.platform,
            recency_signal=mention.recency_signal,
            source_published_at=mention.source_published_at,
        )

    def _triage_min_relevance(self) -> float:
        return self.settings.triage_min_collection_relevance

    def _should_triage(self, mention: NormalizedMention) -> bool:
        rel = mention.collection_relevance_score
        if rel is None:
            return True
        return rel >= self._triage_min_relevance()

    async def _persist(
        self,
        repo: LeadRepository,
        mention: NormalizedMention,
        enrichment: AIEnrichmentResult,
        dedupe: DedupeDecision,
        content_hash: str,
        rank_score: float,
    ) -> Lead | None:
        async with self._db_lock:
            try:
                return await repo.create(
                    mention,
                    enrichment,
                    dedupe.duplicate_hash,
                    content_hash=content_hash,
                    rank_score=rank_score,
                )
            except IntegrityError:
                await self.session.rollback()
                logger.info("lead.skipped.duplicate_url", url=mention.source_url)
                return None

    async def _process_cached(
        self,
        repo: LeadRepository,
        item: _WorkItem,
        cached: Lead,
        telemetry: RunTelemetry,
    ) -> Lead | None:
        enrichment = _enrichment_from_lead(cached)
        now = datetime.now(timezone.utc)
        rank_score = self._compute_rank(enrichment, item.mention, enrichment.engagement_score, now)
        lead = await self._persist(repo, item.mention, enrichment, item.dedupe, item.content_hash, rank_score)
        if lead:
            telemetry.new_leads += 1
            logger.info("lead.created.cached", lead_id=str(lead.id), url=item.mention.source_url)
        return lead

    async def _process_gate1_fail(
        self, repo: LeadRepository, item: _WorkItem, telemetry: RunTelemetry
    ) -> Lead | None:
        enrichment = _low_enrichment(item.mention)
        now = datetime.now(timezone.utc)
        sq = blend_source_quality(0.0, item.mention.collection_relevance_score)
        rank_score = self._compute_rank(enrichment, item.mention, sq, now)
        lead = await self._persist(repo, item.mention, enrichment, item.dedupe, item.content_hash, rank_score)
        if lead:
            telemetry.new_leads += 1
        return lead

    async def _triage_chunks(self, items: list[_WorkItem]) -> list[dict]:
        chunks: list[list[_WorkItem]] = []
        for i in range(0, len(items), 8):
            chunks.append(items[i : i + 8])

        async def run_chunk(chunk: list[_WorkItem]) -> list[dict]:
            async with _TRIAGE_SEM:
                mentions = [c.mention for c in chunk]
                return await self.enricher.triage_batch(mentions)

        batch_results = await asyncio.gather(*[run_chunk(c) for c in chunks])
        flat: list[dict] = []
        for part in batch_results:
            flat.extend(part)
        return flat

    async def _full_enrich(self, mention: NormalizedMention) -> AIEnrichmentResult:
        async with _ENRICH_SEM:
            return await self.enricher.enrich(mention)

    async def run_daily_ingestion(self) -> list[Lead]:
        started = time.monotonic()
        repo = LeadRepository(self.session)
        report_repo = ReportRepository(self.session)
        report_exporter = ReportExporter(self.settings.report_output_dir)
        telemetry = RunTelemetry()

        if self.settings.lead_backfill_on_ingestion:
            telemetry.backfilled = await backfill_platform_and_ranks(self.session, self.ranker)

        seen_urls = await repo.list_recent_source_urls(self.settings.openai_web_research_seen_url_limit)

        async def run_collector(collector) -> list[NormalizedMention] | Exception:
            started_collector = time.monotonic()
            try:
                if hasattr(collector, "reset_run_stats"):
                    collector.reset_run_stats()
                result = await collector.collect(
                    self.settings.keyword_list,
                    self.settings.max_items_per_query,
                    exclude_urls=seen_urls,
                )
                record_collector_run(
                    collector.name,
                    item_count=len(result),
                    duration_s=time.monotonic() - started_collector,
                )
                return result
            except Exception as exc:
                record_collector_run(
                    collector.name,
                    error=str(exc),
                    duration_s=time.monotonic() - started_collector,
                )
                return exc

        collected_batches = await asyncio.gather(*[run_collector(c) for c in self.collectors])

        mentions: list[NormalizedMention] = []
        for collector, result in zip(self.collectors, collected_batches):
            if isinstance(result, Exception):
                logger.error("collector.failure", collector=collector.name, error=str(result))
                continue
            logger.info("collector.success", collector=collector.name, count=len(result))
            mentions.extend(result)

        context_filtered = 0
        filtered_mentions: list[NormalizedMention] = []
        for mention in mentions:
            if passes_competitor_context(
                mention.cleaned_text, self.settings.competitors, mention.competitor_mentioned
            ):
                filtered_mentions.append(mention)
            else:
                context_filtered += 1
        mentions = filtered_mentions

        batch_unique: list[NormalizedMention] = []
        in_batch_deduped = 0
        for mention in mentions:
            if self.dedupe.is_near_duplicate_in_batch(mention, batch_unique):
                in_batch_deduped += 1
                continue
            batch_unique.append(mention)
        mentions = batch_unique

        telemetry.collected = len(mentions)
        telemetry.context_filtered = context_filtered
        telemetry.deduped += in_batch_deduped
        seen_urls: set[str] = set()
        work: list[_WorkItem] = []
        for mention in mentions:
            if not mention.source_url:
                continue
            url_key = self.dedupe._canonicalize_url(mention.source_url)
            if url_key in seen_urls:
                telemetry.deduped += 1
                continue
            seen_urls.add(url_key)
            dedupe_decision = await self.dedupe.check(self.session, mention)
            if dedupe_decision.is_duplicate:
                telemetry.deduped += 1
                logger.info("dedupe.skipped", url=mention.source_url, reason=dedupe_decision.reason)
                continue
            work.append(
                _WorkItem(
                    mention=mention,
                    dedupe=dedupe_decision,
                    content_hash=_content_hash(mention.source_url, mention.cleaned_text),
                )
            )

        created: list[Lead] = []
        gate1_pass: list[_WorkItem] = []
        gate1_fail: list[_WorkItem] = []

        for item in work:
            cached = await repo.get_by_content_hash(item.content_hash)
            if cached:
                lead = await self._process_cached(repo, item, cached, telemetry)
                if lead:
                    created.append(lead)
                continue
            if text_has_pain_signal(item.mention.cleaned_text):
                gate1_pass.append(item)
                telemetry.gate1_passed += 1
            else:
                gate1_fail.append(item)

        for item in gate1_fail:
            if not should_persist_gate1_fail(item.mention, self.settings.gate1_fail_min_relevance):
                telemetry.gate1_fail_dropped += 1
                continue
            lead = await self._process_gate1_fail(repo, item, telemetry)
            if lead:
                created.append(lead)
                telemetry.gate1_fail_persisted += 1

        triage_eligible: list[_WorkItem] = []
        for item in gate1_pass:
            if not self._should_triage(item.mention):
                telemetry.triage_skipped_low_relevance += 1
                enrichment = _low_enrichment(item.mention)
                now = datetime.now(timezone.utc)
                sq = blend_source_quality(0.0, item.mention.collection_relevance_score)
                rank_score = self._compute_rank(enrichment, item.mention, sq, now)
                lead = await self._persist(
                    repo, item.mention, enrichment, item.dedupe, item.content_hash, rank_score
                )
                if lead:
                    created.append(lead)
                    telemetry.new_leads += 1
                continue
            triage_eligible.append(item)

        triage_results: list[dict] = []
        if triage_eligible:
            triage_results = await self._triage_chunks(triage_eligible)

        gate3_items: list[tuple[_WorkItem, dict, float]] = []
        for item, triage in zip(triage_eligible, triage_results):
            source_quality = blend_source_quality(
                float(triage["source_quality"]), item.mention.collection_relevance_score
            )
            if float(triage["intent_score"]) >= self.settings.min_enrich_score:
                telemetry.gate2_passed += 1
                if should_full_enrich(item.mention):
                    gate3_items.append((item, triage, source_quality))
                else:
                    telemetry.enrich_skipped_stale += 1
                    enrichment = _enrichment_from_triage(triage, item.mention, self.settings.min_enrich_score)
                    now = datetime.now(timezone.utc)
                    rank_score = self._compute_rank(enrichment, item.mention, source_quality, now)
                    lead = await self._persist(
                        repo, item.mention, enrichment, item.dedupe, item.content_hash, rank_score
                    )
                    if lead:
                        created.append(lead)
                        telemetry.new_leads += 1
            else:
                enrichment = _enrichment_from_triage(triage, item.mention, self.settings.min_enrich_score)
                now = datetime.now(timezone.utc)
                rank_score = self._compute_rank(enrichment, item.mention, source_quality, now)
                lead = await self._persist(
                    repo, item.mention, enrichment, item.dedupe, item.content_hash, rank_score
                )
                if lead:
                    created.append(lead)
                    telemetry.new_leads += 1

        async def enrich_one(
            item: _WorkItem, triage: dict, source_quality: float
        ) -> tuple[_WorkItem, AIEnrichmentResult, float] | None:
            try:
                enrichment = await self._full_enrich(item.mention)
                return item, enrichment, source_quality
            except Exception as exc:
                logger.error("enrich.failed", url=item.mention.source_url, error=str(exc))
                return None

        enrich_outcomes = await asyncio.gather(
            *[enrich_one(item, triage, sq) for item, triage, sq in gate3_items]
        )
        for outcome in enrich_outcomes:
            if not outcome:
                continue
            item, enrichment, source_quality = outcome
            telemetry.enriched += 1
            now = datetime.now(timezone.utc)
            rank_score = self._compute_rank(enrichment, item.mention, source_quality, now)
            lead = await self._persist(
                repo, item.mention, enrichment, item.dedupe, item.content_hash, rank_score
            )
            created.append(lead)
            telemetry.new_leads += 1
            logger.info(
                "lead.created",
                lead_id=str(lead.id),
                intent=lead.intent_label.value,
                competitor=lead.competitor,
            )

        telemetry.api_calls = self.enricher.api_call_count
        telemetry.runtime_s = round(time.monotonic() - started, 1)

        web_searches, deep_extracts, extract_chars = _collector_usage_stats(self.collectors)
        cost = estimate_run_cost(
            web_searches=web_searches,
            deep_extract_calls=deep_extracts,
            chat_api_calls=self.enricher.api_call_count,
            triage_chars=self.enricher.est_triage_chars,
            enrich_chars=self.enricher.est_enrich_chars,
            extract_chars=extract_chars,
            responses_model=(self.settings.openai_responses_model or self.settings.openai_model).strip(),
            chat_model=self.settings.openai_triage_model_name,
            extract_model=(self.settings.openai_collection_model or self.settings.openai_model).strip(),
        )
        telemetry.est_cost_usd = cost.est_cost_usd
        telemetry.web_searches = cost.web_searches
        collector_rows = all_collector_health()
        set_last_run_snapshot(
            telemetry=asdict(telemetry),
            collectors=collector_rows,
            cost=cost.to_dict(),
        )

        report_date = datetime.now(ZoneInfo(self.settings.scheduler_timezone)).date()
        new_leads_report_path = report_exporter.export_new_leads_excel(created, report_date)
        all_leads = await repo.list_all_for_export()
        all_leads_report_path = report_exporter.export_all_leads_excel(all_leads, report_date)
        await report_repo.insert_from_leads(created, report_date)

        quality_combos = await aggregate_high_quality_combos(
            self.session,
            min_avg_score=self.settings.quality_feedback_min_avg_score,
            min_samples=self.settings.quality_feedback_min_samples,
        )
        if quality_combos:
            export_quality_feedback_report(quality_combos, self.settings.report_output_dir, report_date=report_date)

        if self.settings.slack_webhook_url:
            try:
                digest_leads = filter_digest_leads(created, self.settings.digest_min_rank_score)
                await send_slack_digest(
                    self.settings.slack_webhook_url,
                    self.settings.slack_channel,
                    digest_leads,
                    report_paths=[new_leads_report_path, all_leads_report_path],
                    telemetry=telemetry,
                    report_date=report_date,
                    collector_health=[asdict(row) for row in collector_rows],
                    cost=cost.to_dict(),
                )
                logger.info("slack.digest.sent", count=len(digest_leads), total_created=len(created))
            except Exception as exc:  # noqa: BLE001
                logger.exception("slack.digest.failed", error=str(exc))
        if self.settings.slack_bot_token and self.settings.slack_channel_id:
            try:
                for report_path in (new_leads_report_path, all_leads_report_path):
                    if report_path.exists():
                        await upload_report_to_slack(
                            self.settings.slack_bot_token, self.settings.slack_channel_id, report_path
                        )
            except Exception as exc:  # noqa: BLE001
                logger.exception("slack.report.upload.failed", error=str(exc))
        return created
