from app.collectors.base import BaseCollector
from app.models.schemas import NormalizedMention


class PlaceholderCollector(BaseCollector):
    """Production-safe placeholder for sources requiring bespoke/legal integrations."""

    def __init__(self, source_name: str, platform: str) -> None:
        self.name = source_name.lower().replace(" ", "_")
        self.platform = platform
        self.source_name = source_name

    async def collect(self, keywords: list[str], limit: int) -> list[NormalizedMention]:
        return []
