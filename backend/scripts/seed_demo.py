"""Seed a demo stock conversation and run extraction.

Usage (from repository root):
    python backend/scripts/seed_demo.py

Usage (from backend directory):
    python scripts/seed_demo.py
    # or
    python -m scripts.seed_demo
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete

# Make `app` imports work whether the script is run from repo root or backend/.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.schemas.message import MessageCreate
from app.services.extraction import run_extraction_for_conversation
from app.services.messages import create_messages


DEFAULT_CONVERSATION_ID = "stocks-demo-001"


def build_demo_messages() -> list[MessageCreate]:
    """Return a deterministic 3-5 stock demo conversation."""

    base = datetime(2026, 2, 24, 14, 0, 0, tzinfo=timezone.utc)
    payloads = [
        ("user", "AAPL reported iPhone revenue strength and the stock rose 3.2% after the call."),
        ("assistant", "TSLA reported vehicle deliveries and shares moved -1.4% in late trading."),
        ("user", "Fed rate decision impacted NVDA as traders reassessed AI valuations."),
        ("assistant", "Supply chain disruption impacted AAPL and management flagged margin pressure."),
        ("user", "MSFT reported cloud revenue acceleration while AMZN gained 2.1%."),
    ]
    return [
        MessageCreate(role=role, content=content, timestamp=base.replace(minute=base.minute + idx))
        for idx, (role, content) in enumerate(payloads)
    ]


def reset_conversation(db, conversation_id: str) -> None:
    """Remove existing records for the demo conversation."""

    db.execute(delete(Relation).where(Relation.conversation_id == conversation_id))
    db.execute(delete(Fact).where(Fact.conversation_id == conversation_id))
    db.execute(delete(Entity).where(Entity.conversation_id == conversation_id))
    db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    db.commit()


def parse_args() -> argparse.Namespace:
    """Parse script CLI arguments."""

    parser = argparse.ArgumentParser(description="Seed a demo stock conversation and run extraction.")
    parser.add_argument(
        "--conversation-id",
        default=DEFAULT_CONVERSATION_ID,
        help=f"Conversation ID to seed (default: {DEFAULT_CONVERSATION_ID})",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not delete existing records for the conversation before seeding.",
    )
    return parser.parse_args()


def main() -> None:
    """Seed demo data and print a short summary."""

    args = parse_args()
    conversation_id: str = args.conversation_id
    messages = build_demo_messages()

    with SessionLocal() as db:
        if not args.no_reset:
            reset_conversation(db, conversation_id)

        created_messages = create_messages(db, conversation_id, messages)
        extraction_result = run_extraction_for_conversation(db, conversation_id)

    print("Seed complete")
    print(f"conversation_id={conversation_id}")
    print(f"messages_created={len(created_messages)}")
    print(f"entities_created={extraction_result.entities_created}")
    print(f"facts_created={extraction_result.facts_created}")
    print(f"relations_created={extraction_result.relations_created}")
    print()
    print("Inspect:")
    print(f"  GET /conversations/{conversation_id}/messages")
    print(f"  GET /conversations/{conversation_id}/entities")
    print(f"  GET /conversations/{conversation_id}/facts")
    print(f"  GET /conversations/{conversation_id}/relations")


if __name__ == "__main__":
    main()
