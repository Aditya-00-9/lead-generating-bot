import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.classifiers.openai_enricher import OpenAIEnricher
from app.collectors.google_alerts import GoogleAlertsCollector
from app.collectors.placeholders import PlaceholderCollector
from app.collectors.reddit import RedditCollector
from app.config.settings import Settings
from app.dedupe.engine import DedupeEngine
from app.models.lead import Lead
from app.ranking.lead_ranker import LeadRanker
from app.services.report_exporter import ReportExporter
from app.slack.digest import send_slack_digest, upload_report_to_slack
from app.storage.lead_repository import LeadRepository
from app.storage.report_repository import ReportRepository

logger = structlog.get_logger(__name__)


class LeadPipelineService:
    def __init__(self, settings: Settings, session: AsyncSession) -> None:
        self.settings = settings
        self.session = session
        self.dedupe = DedupeEngine(
            similarity_threshold=settings.duplicate_similarity_threshold,
            window_days=settings.duplicate_window_days,
        )
        self.enricher = OpenAIEnricher(settings)
        self.ranker = LeadRanker()

        self.collectors = [RedditCollector(settings), GoogleAlertsCollector(settings)]
        if settings.enable_placeholder_sources:
            self.collectors.extend(
                [
                    PlaceholderCollector("G2", "review-site"),
                    PlaceholderCollector("Capterra", "review-site"),
                    PlaceholderCollector("App Store", "app-store"),
                    PlaceholderCollector("Play Store", "play-store"),
                ]
            )

    async def run_daily_ingestion(self) -> list[Lead]:
        repo = LeadRepository(self.session)
        report_repo = ReportRepository(self.session)
        report_exporter = ReportExporter(self.settings.report_output_dir)
        tasks = [collector.collect(self.settings.keyword_list, self.settings.max_items_per_query) for collector in self.collectors]
        collected_batches = await asyncio.gather(*tasks, return_exceptions=True)

        mentions = []
        for collector, result in zip(self.collectors, collected_batches):
            if isinstance(result, Exception):
                logger.error("collector.failure", collector=collector.name, error=str(result))
                continue
            logger.info("collector.success", collector=collector.name, count=len(result))
            mentions.extend(result)

        created: list[Lead] = []
        for mention in mentions:
            if not mention.source_url:
                continue
            dedupe_decision = await self.dedupe.check(self.session, mention)
            if dedupe_decision.is_duplicate:
                logger.info("dedupe.skipped", url=mention.source_url, reason=dedupe_decision.reason)
                continue

            enrichment = await self.enricher.enrich(mention)
            rank_score = self.ranker.score(enrichment)
            enrichment.tags = list(set(enrichment.tags + [f"rank:{rank_score}"]))
            lead = await repo.create(mention, enrichment, dedupe_decision.duplicate_hash)
            created.append(lead)
            logger.info("lead.created", lead_id=str(lead.id), intent=lead.intent_label.value, competitor=lead.competitor)

        report_date = datetime.now(ZoneInfo(self.settings.scheduler_timezone)).date()
        report_path = report_exporter.export_daily_excel(created, report_date)
        await report_repo.insert_from_leads(created, report_date)

        if self.settings.slack_webhook_url:
            await send_slack_digest(self.settings.slack_webhook_url, self.settings.slack_channel, created, report_path=report_path)
            logger.info("slack.digest.sent", count=len(created))
        if self.settings.slack_bot_token and self.settings.slack_channel_id and report_path.exists():
            await upload_report_to_slack(self.settings.slack_bot_token, self.settings.slack_channel_id, report_path)
            logger.info("slack.report.uploaded", report_path=str(report_path))
        return created
