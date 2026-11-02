"""
Analytics computed from stored rows.

There are no synthetic or extrapolated figures here: every value is a count, ratio or aggregate
over conversations, messages, leads and knowledge sources that exist in the database for the
requested window. When a window holds no conversations the payload says so via ``has_data``.

Definitions (also surfaced in the UI):
  unique_users        distinct conversation session ids in range — the identity a visitor has
  resolved            conversation that produced a lead, or that ended without a handoff
  resolution_rate     resolved / total conversations
  lead_conversion     leads captured / total conversations
  unanswered          a user question whose assistant reply was the canonical refusal, or that
                      never received a reply
"""

import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.messages import is_refusal
from app.models.conversation import Conversation, ConversationStatus, Message, MessageSender
from app.models.knowledge_source import KnowledgeSource, ProcessingStatus
from app.models.lead import Lead


def parse_window(start: Optional[date], end: Optional[date]) -> Tuple[datetime, datetime]:
    """Inclusive date window as UTC datetimes. Defaults to the last 30 days."""
    today = datetime.now(timezone.utc).date()
    end_day = end or today
    start_day = start or (end_day - timedelta(days=29))
    if start_day > end_day:
        start_day, end_day = end_day, start_day
    # Naive UTC: the DateTime columns store naive UTC, and comparing naive values against
    # tz-aware ones raises "can't compare offset-naive and offset-aware datetimes" (500s on
    # every analytics request).
    return (
        datetime.combine(start_day, time.min),
        datetime.combine(end_day, time.max),
    )


def _pct(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 1) if denominator else 0.0


def _sources_of(message: Message) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(message.metadata_json or "{}")
    except (ValueError, TypeError):
        return []
    sources = payload.get("sources") or []
    return sources if isinstance(sources, list) else []


class AnalyticsService:

    # ── shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _conversations(db: Session, bot_ids: Iterable[int], start: datetime, end: datetime) -> List[Conversation]:
        ids = [bot_id for bot_id in bot_ids]
        if not ids:
            return []
        return (
            db.query(Conversation)
            .filter(
                Conversation.bot_id.in_(ids),
                Conversation.started_at >= start,
                Conversation.started_at <= end,
            )
            .order_by(Conversation.started_at.asc())
            .all()
        )

    @staticmethod
    def _messages(db: Session, convo_ids: List[int]) -> List[Message]:
        if not convo_ids:
            return []
        return (
            db.query(Message)
            .filter(Message.conversation_id.in_(convo_ids))
            .order_by(Message.conversation_id.asc(), Message.timestamp.asc(), Message.id.asc())
            .all()
        )

    @staticmethod
    def _unanswered(messages: List[Message], convos: List[Conversation]) -> List[Dict[str, Any]]:
        """Questions that received a refusal, or never received an answer."""
        by_convo: Dict[int, List[Message]] = defaultdict(list)
        for message in messages:
            by_convo[message.conversation_id].append(message)

        found: List[Dict[str, Any]] = []
        for convo in convos:
            thread = by_convo.get(convo.id, [])
            for index, message in enumerate(thread):
                if message.sender != MessageSender.USER.value:
                    continue
                reply = next(
                    (m for m in thread[index + 1:] if m.sender == MessageSender.ASSISTANT.value),
                    None,
                )
                if reply is None:
                    found.append({
                        "conversation_id": convo.id,
                        "question": message.content,
                        "asked_at": message.timestamp,
                        "reason": "no_reply",
                    })
                elif is_refusal(reply.content):
                    found.append({
                        "conversation_id": convo.id,
                        "question": message.content,
                        "asked_at": message.timestamp,
                        "reason": "refused",
                    })
        return found

    @staticmethod
    def _volume(convos: List[Conversation], messages: List[Message]) -> List[Dict[str, Any]]:
        per_day: Dict[str, Dict[str, int]] = defaultdict(lambda: {"conversations": 0, "messages": 0})
        for convo in convos:
            per_day[convo.started_at.date().isoformat()]["conversations"] += 1
        convo_by_id = {c.id: c for c in convos}
        for message in messages:
            convo = convo_by_id.get(message.conversation_id)
            if convo:
                per_day[message.timestamp.date().isoformat()]["messages"] += 1
        return [
            {"date": day, **counts}
            for day, counts in sorted(per_day.items())
        ]

    # ── bot-level ─────────────────────────────────────────────────────────────

    @classmethod
    def bot_report(
        cls,
        db: Session,
        bot_id: int,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> Dict[str, Any]:
        window_start, window_end = parse_window(start, end)

        convos = cls._conversations(db, [bot_id], window_start, window_end)
        convo_ids = [c.id for c in convos]
        messages = cls._messages(db, convo_ids)

        leads = (
            db.query(Lead)
            .filter(
                Lead.bot_id == bot_id,
                Lead.created_at >= window_start,
                Lead.created_at <= window_end,
            )
            .all()
        )
        lead_convo_ids = {lead.conversation_id for lead in leads if lead.conversation_id}

        handoffs = [
            c for c in convos
            if c.status in (ConversationStatus.HANDOFF_REQUESTED.value, ConversationStatus.HANDED_OFF.value)
        ]
        handoff_ids = {c.id for c in handoffs}

        resolved = [
            c for c in convos
            if c.id in lead_convo_ids
            or (c.status == ConversationStatus.ENDED.value and c.id not in handoff_ids)
        ]

        unanswered = cls._unanswered(messages, convos)

        source_counter: Counter = Counter()
        for message in messages:
            if message.sender != MessageSender.ASSISTANT.value:
                continue
            for source in _sources_of(message):
                name = source.get("source_name") or source.get("name")
                if name:
                    source_counter[name] += 1

        knowledge_sources = (
            db.query(KnowledgeSource)
            .filter(KnowledgeSource.bot_id == bot_id)
            .order_by(KnowledgeSource.created_at.desc())
            .all()
        )
        knowledge_in_range = [
            source for source in knowledge_sources
            if window_start <= (source.created_at or window_start) <= window_end
        ]

        intent_counts = Counter((c.intent or "unknown").lower() for c in convos)
        total = len(convos)

        return {
            "range": {"start": window_start.date().isoformat(), "end": window_end.date().isoformat()},
            "has_data": total > 0,
            "totals": {
                "conversations": total,
                "unique_users": len({c.session_id for c in convos}),
                "messages": len(messages),
                "leads": len(leads),
                "handoffs": len(handoffs),
                "resolved": len(resolved),
                "unresolved": total - len(resolved),
                "resolution_rate": _pct(len(resolved), total),
                "avg_messages_per_conversation": round(len(messages) / total, 1) if total else 0.0,
                "lead_conversion_rate": _pct(len(leads), total),
            },
            "intents": {
                "buying": intent_counts.get("buying", 0),
                "renting": intent_counts.get("renting", 0),
                "browsing": intent_counts.get("browsing", 0),
                "other": total - sum(
                    intent_counts.get(key, 0) for key in ("buying", "renting", "browsing")
                ),
            },
            "volume": cls._volume(convos, messages),
            "knowledge": {
                "sources": len(knowledge_sources),
                "sources_in_range": len(knowledge_in_range),
                "processed": sum(
                    1 for s in knowledge_sources
                    if s.processing_status == ProcessingStatus.COMPLETED.value
                ),
                "failed": sum(
                    1 for s in knowledge_sources
                    if s.processing_status == ProcessingStatus.FAILED.value
                ),
                "failed_sources": [
                    {"name": s.name, "error": s.error_message}
                    for s in knowledge_sources
                    if s.processing_status == ProcessingStatus.FAILED.value
                ],
                "top_sources": [
                    {"source": name, "citations": count}
                    for name, count in source_counter.most_common(5)
                ],
                "unanswered_count": len(unanswered),
            },
            "unanswered": [
                {
                    "conversation_id": row["conversation_id"],
                    "question": row["question"],
                    "asked_at": row["asked_at"].isoformat(),
                    "reason": row["reason"],
                }
                for row in unanswered[:50]
            ],
        }

    # ── platform-level (admin) ────────────────────────────────────────────────

    @classmethod
    def platform_report(
        cls,
        db: Session,
        start: Optional[date] = None,
        end: Optional[date] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate across every bot, or across one owner's bots when ``user_id`` is given.

        The same code serves the admin console and a business user's own overview; the only
        difference is the bot scope, so the two can never drift.
        """
        from app.models.bot import Bot
        from app.models.project import Project

        window_start, window_end = parse_window(start, end)

        bot_query = db.query(Bot)
        if user_id is not None:
            bot_query = bot_query.join(Project, Project.id == Bot.project_id).filter(
                Project.user_id == user_id
            )
        bots = bot_query.all()
        bot_ids = [b.id for b in bots]

        convos = cls._conversations(db, bot_ids, window_start, window_end)
        convo_ids = [c.id for c in convos]
        messages = cls._messages(db, convo_ids)

        leads_query = db.query(Lead).filter(
            Lead.created_at >= window_start, Lead.created_at <= window_end
        )
        if user_id is not None:
            leads_query = leads_query.filter(Lead.bot_id.in_(bot_ids or [-1]))
        leads = leads_query.all()

        handoffs = [
            c for c in convos
            if c.status in (ConversationStatus.HANDOFF_REQUESTED.value, ConversationStatus.HANDED_OFF.value)
        ]
        lead_convo_ids = {lead.conversation_id for lead in leads if lead.conversation_id}
        handoff_ids = {c.id for c in handoffs}
        resolved = [
            c for c in convos
            if c.id in lead_convo_ids
            or (c.status == ConversationStatus.ENDED.value and c.id not in handoff_ids)
        ]

        intent_counts = Counter((c.intent or "unknown").lower() for c in convos)
        total = len(convos)

        per_bot = []
        for bot in bots:
            bot_convos = [c for c in convos if c.bot_id == bot.id]
            per_bot.append({
                "bot_id": bot.id,
                "bot_name": bot.name,
                "status": bot.status,
                "conversations": len(bot_convos),
                "messages": sum(1 for m in messages if m.conversation_id in {c.id for c in bot_convos}),
                "leads": sum(1 for lead in leads if lead.bot_id == bot.id),
                "handoffs": sum(
                    1 for c in bot_convos
                    if c.status in (
                        ConversationStatus.HANDOFF_REQUESTED.value,
                        ConversationStatus.HANDED_OFF.value,
                    )
                ),
            })

        return {
            "range": {"start": window_start.date().isoformat(), "end": window_end.date().isoformat()},
            "has_data": total > 0,
            "totals": {
                "bots": len(bots),
                "conversations": total,
                "unique_users": len({c.session_id for c in convos}),
                "messages": len(messages),
                "leads": len(leads),
                "handoffs": len(handoffs),
                "resolved": len(resolved),
                "unresolved": total - len(resolved),
                "resolution_rate": _pct(len(resolved), total),
                "avg_messages_per_conversation": round(len(messages) / total, 1) if total else 0.0,
                "lead_conversion_rate": _pct(len(leads), total),
            },
            "intents": {
                "buying": intent_counts.get("buying", 0),
                "renting": intent_counts.get("renting", 0),
                "browsing": intent_counts.get("browsing", 0),
                "other": total - sum(
                    intent_counts.get(key, 0) for key in ("buying", "renting", "browsing")
                ),
            },
            "volume": cls._volume(convos, messages),
            "per_bot": sorted(per_bot, key=lambda row: row["conversations"], reverse=True),
            "unanswered": [
                {
                    "conversation_id": row["conversation_id"],
                    "question": row["question"],
                    "asked_at": row["asked_at"].isoformat(),
                    "reason": row["reason"],
                }
                for row in cls._unanswered(messages, convos)[:50]
            ],
        }
