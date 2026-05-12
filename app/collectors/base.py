from abc import ABC, abstractmethod

from app.models.schemas import NormalizedMention


class BaseCollector(ABC):
    """Abstract collector contract for all sources."""

    name: str
    platform: str

    @abstractmethod
    async def collect(self, keywords: list[str], limit: int) -> list[NormalizedMention]:
        raise NotImplementedError
