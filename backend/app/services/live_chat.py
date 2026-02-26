"""Live chat testing service for GPT-assisted conversation turns."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.config import get_settings
from app.extraction.extractor_interface import ExtractorInterface
from app.schemas.chat import LiveChatTurnResult
from app.schemas.message import MessageCreate, MessageRead
from app.services.extraction import run_extraction_for_conversation
from app.services.messages import create_messages, list_messages


class LiveChatError(RuntimeError):
    """Raised when live chat generation fails."""


class ChatCompletionClient(Protocol):
    """Protocol for chat completion providers."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return assistant text for the provided conversation."""


@dataclass(slots=True)
class OpenAIChatClient:
    """Minimal OpenAI chat completions client for live testing."""

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": messages,
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        req = urllib_request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LiveChatError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except urllib_error.URLError as exc:
            raise LiveChatError(f"OpenAI request failed: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
            content = decoded["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise TypeError("assistant message content missing")
            return content.strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LiveChatError("OpenAI returned an unexpected chat response") from exc


def get_default_chat_client() -> ChatCompletionClient:
    """Return configured chat client for live testing."""

    settings = get_settings()
    if not settings.openai_api_key:
        raise LiveChatError(
            "OPENAI_API_KEY is not configured. Set it in backend/.env before using live chat."
        )
    return OpenAIChatClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def run_live_chat_turn(
    db: Session,
    conversation_id: str,
    *,
    user_content: str,
    auto_extract: bool = True,
    system_prompt: str | None = None,
    extractor: ExtractorInterface | None = None,
    chat_client: ChatCompletionClient | None = None,
) -> LiveChatTurnResult:
    """Persist a user turn, generate assistant reply, and optionally extract."""

    trimmed_content = user_content.strip()
    if not trimmed_content:
        raise LiveChatError("Message content cannot be empty.")

    created_user = create_messages(
        db,
        conversation_id,
        [MessageCreate(role="user", content=trimmed_content)],
    )[0]

    messages_for_model = _build_chat_messages(
        list_messages(db, conversation_id),
        system_prompt=system_prompt,
    )
    assistant_content = (chat_client or get_default_chat_client()).complete(messages_for_model)
    created_assistant = create_messages(
        db,
        conversation_id,
        [MessageCreate(role="assistant", content=assistant_content)],
    )[0]

    extraction = None
    if auto_extract:
        extraction = run_extraction_for_conversation(db, conversation_id, extractor=extractor)

    return LiveChatTurnResult(
        conversation_id=conversation_id,
        user_message=MessageRead.model_validate(created_user),
        assistant_message=MessageRead.model_validate(created_assistant),
        extraction=extraction,
    )


def _build_chat_messages(
    conversation_messages: list[Any],
    *,
    system_prompt: str | None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    else:
        messages.append(
            {
                "role": "system",
                "content": (
                    "You are assisting with live testing of a stock-research conversation. "
                    "Respond clearly and factually, and keep responses concise."
                ),
            }
        )

    for message in conversation_messages:
        role = str(getattr(message, "role", "")).strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(getattr(message, "content", "")).strip()
        if not content:
            continue
        messages.append({"role": role, "content": content})
    return messages
