"""Extractor interface for pluggable extraction implementations."""

from abc import ABC, abstractmethod

from app.extraction.types import ExtractionResult
from app.models.message import Message


class ExtractorInterface(ABC):
    """Abstract extractor interface."""

    @abstractmethod
    def extract(self, messages: list[Message]) -> ExtractionResult:
        """Extract entities, facts, and relations from messages."""

