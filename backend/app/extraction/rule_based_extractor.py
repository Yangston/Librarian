"""Deterministic MVP extractor using simple regex rules."""

from __future__ import annotations

import re

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractedRelation, ExtractionResult
from app.models.message import Message

TICKER_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")
PERCENT_PATTERN = re.compile(r"(?P<value>-?\d+(?:\.\d+)?)%")
REPORTED_PATTERN = re.compile(
    r"(?P<company>[A-Z][A-Za-z0-9&.\- ]{1,80}?) reported (?P<metric>[^.!?\n]+)",
    re.MULTILINE,
)
IMPACTED_PATTERN = re.compile(
    r"(?P<event>[A-Z][A-Za-z0-9&.\- ]{1,80}?) impacted (?P<company>[A-Z][A-Za-z0-9&.\- ]{1,80})(?:[.!?\n]|$)",
    re.MULTILINE,
)

UPPERCASE_STOPWORDS = {
    "I",
    "A",
    "AN",
    "THE",
    "AND",
    "OR",
    "OF",
    "IN",
    "ON",
    "TO",
    "FOR",
    "CEO",
    "CFO",
    "EPS",
    "AI",
    "MVP",
}


class RuleBasedExtractor(ExtractorInterface):
    """Simple deterministic extractor for the Phase 1 MVP."""

    def extract(self, messages: list[Message]) -> ExtractionResult:
        """Extract entities, facts, and relations from messages."""

        entity_map: dict[tuple[str, str], ExtractedEntity] = {}
        facts: list[ExtractedFact] = []
        relations: list[ExtractedRelation] = []
        seen_fact_keys: set[tuple[object, ...]] = set()
        seen_relation_keys: set[tuple[object, ...]] = set()

        for message in messages:
            content = message.content.strip()
            if not content:
                continue

            tickers = self._extract_ticker_entities(entity_map, content, message.id)
            self._extract_percentage_facts(
                content=content,
                message_id=message.id,
                tickers=tickers,
                facts=facts,
                seen_fact_keys=seen_fact_keys,
            )
            self._extract_reported_pattern(
                content=content,
                message_id=message.id,
                entity_map=entity_map,
                facts=facts,
                seen_fact_keys=seen_fact_keys,
            )
            self._extract_impacted_pattern(
                content=content,
                message_id=message.id,
                entity_map=entity_map,
                relations=relations,
                seen_relation_keys=seen_relation_keys,
            )

        entities = sorted(entity_map.values(), key=lambda e: (e.entity_type, e.name.lower()))
        facts.sort(key=lambda f: (f.subject_name.lower(), f.predicate, f.object_value))
        relations.sort(key=lambda r: (r.from_name.lower(), r.relation_type, r.to_name.lower()))
        return ExtractionResult(entities=entities, facts=facts, relations=relations)

    def _extract_ticker_entities(
        self,
        entity_map: dict[tuple[str, str], ExtractedEntity],
        content: str,
        message_id: int,
    ) -> list[str]:
        """Extract ticker-like entities."""

        tickers: set[str] = set()
        for match in TICKER_PATTERN.finditer(content):
            ticker = match.group(0).strip()
            if ticker in UPPERCASE_STOPWORDS or ticker.isdigit():
                continue
            tickers.add(ticker)
            self._ensure_entity(
                entity_map=entity_map,
                name=ticker,
                entity_type="Company",
                message_id=message_id,
                aliases=[ticker],
                tags=["ticker"],
            )
        return sorted(tickers)

    def _extract_percentage_facts(
        self,
        *,
        content: str,
        message_id: int,
        tickers: list[str],
        facts: list[ExtractedFact],
        seen_fact_keys: set[tuple[object, ...]],
    ) -> None:
        """Link percentage mentions to detected ticker entities."""

        if not tickers:
            return
        for percent_match in PERCENT_PATTERN.finditer(content):
            percent_text = f"{percent_match.group('value')}%"
            snippet = self._sentence_snippet(content, percent_match.start(), percent_match.end())
            for ticker in tickers:
                key = (ticker.lower(), "mentioned_percentage_change", percent_text, message_id)
                if key in seen_fact_keys:
                    continue
                seen_fact_keys.add(key)
                facts.append(
                    ExtractedFact(
                        subject_name=ticker,
                        subject_type="Company",
                        predicate="mentioned_percentage_change",
                        object_value=percent_text,
                        confidence=0.8,
                        source_message_ids=[message_id],
                        snippet=snippet,
                    )
                )

    def _extract_reported_pattern(
        self,
        *,
        content: str,
        message_id: int,
        entity_map: dict[tuple[str, str], ExtractedEntity],
        facts: list[ExtractedFact],
        seen_fact_keys: set[tuple[object, ...]],
    ) -> None:
        """Extract facts from '[Company] reported [metric]' pattern."""

        for match in REPORTED_PATTERN.finditer(content):
            company = self._clean_phrase(match.group("company"))
            metric = self._clean_phrase(match.group("metric"))
            if not company or not metric:
                continue
            self._ensure_entity(entity_map, company, "Company", message_id)
            key = (company.lower(), "reported", metric.lower(), message_id)
            if key in seen_fact_keys:
                continue
            seen_fact_keys.add(key)
            facts.append(
                ExtractedFact(
                    subject_name=company,
                    subject_type="Company",
                    predicate="reported",
                    object_value=metric,
                    confidence=0.95,
                    source_message_ids=[message_id],
                    snippet=match.group(0).strip(),
                )
            )

    def _extract_impacted_pattern(
        self,
        *,
        content: str,
        message_id: int,
        entity_map: dict[tuple[str, str], ExtractedEntity],
        relations: list[ExtractedRelation],
        seen_relation_keys: set[tuple[object, ...]],
    ) -> None:
        """Extract relations from '[Event] impacted [Company]' pattern."""

        for match in IMPACTED_PATTERN.finditer(content):
            event_name = self._clean_phrase(match.group("event"))
            company_name = self._clean_phrase(match.group("company"))
            if not event_name or not company_name:
                continue
            self._ensure_entity(entity_map, event_name, "Event", message_id)
            self._ensure_entity(entity_map, company_name, "Company", message_id)
            key = (event_name.lower(), "impacted", company_name.lower(), message_id)
            if key in seen_relation_keys:
                continue
            seen_relation_keys.add(key)
            snippet = match.group(0).strip()
            relations.append(
                ExtractedRelation(
                    from_name=event_name,
                    from_type="Event",
                    relation_type="impacted",
                    to_name=company_name,
                    to_type="Company",
                    qualifiers={"snippet": snippet},
                    source_message_ids=[message_id],
                    snippet=snippet,
                )
            )

    def _ensure_entity(
        self,
        entity_map: dict[tuple[str, str], ExtractedEntity],
        name: str,
        entity_type: str,
        message_id: int,
        aliases: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        cleaned = self._clean_phrase(name)
        if not cleaned:
            return
        key = (cleaned.lower(), entity_type)
        existing = entity_map.get(key)
        if existing is None:
            existing = ExtractedEntity(name=cleaned, entity_type=entity_type)
            entity_map[key] = existing
        if message_id not in existing.source_message_ids:
            existing.source_message_ids.append(message_id)
        for alias in aliases or []:
            if alias not in existing.aliases:
                existing.aliases.append(alias)
        for tag in tags or []:
            if tag not in existing.tags:
                existing.tags.append(tag)

    @staticmethod
    def _clean_phrase(value: str) -> str:
        """Normalize extracted phrase whitespace and punctuation."""

        return re.sub(r"\s+", " ", value).strip(" .,:;\"'")

    @staticmethod
    def _sentence_snippet(content: str, start: int, end: int) -> str:
        """Return a sentence-like snippet around the match indexes."""

        left = max(content.rfind(".", 0, start), content.rfind("!", 0, start), content.rfind("?", 0, start))
        right_candidates = [idx for idx in (content.find(".", end), content.find("!", end), content.find("?", end)) if idx != -1]
        right = min(right_candidates) if right_candidates else len(content)
        snippet = content[(left + 1 if left != -1 else 0) : (right + 1 if right < len(content) else right)]
        return snippet.strip()

