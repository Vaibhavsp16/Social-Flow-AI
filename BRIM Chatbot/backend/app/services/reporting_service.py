"""
Reporting.

A report is a plain dict — title, columns, rows, summary, metadata — and CSV is one renderer over
it. A PDF (or scheduled email) renderer can consume the same structure without touching queries,
so the report definitions stay in one place.
"""

import csv
import io
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.bot import Bot
from app.models.conversation import Conversation, ConversationStatus, Message, MessageSender
from app.models.lead import Lead
from app.models.project import Project
from app.services.analytics_service import AnalyticsService, parse_window


def _mask(value: Optional[str], keep: int = 3) -> str:
    """Show only the tail of a phone/email so exports stay useful without exposing full PII."""
    if not value:
        return ""
    text = str(value)
    return f"{'*' * max(len(text) - keep, 0)}{text[-keep:]}"


def _scope_bots(db: Session, bot_id: Optional[int], user_id: Optional[int]) -> List[Bot]:
    query = db.query(Bot)
    if bot_id is not None:
        query = query.filter(Bot.id == bot_id)
    if user_id is not None:
        query = query.join(Project, Project.id == Bot.project_id).filter(Project.user_id == user_id)
    return query.all()


class ReportingService:

    KINDS = ("conversations", "leads", "bot_usage", "intents", "handoffs", "unanswered")

    @classmethod
    def build(
        cls,
        db: Session,
        kind: str,
        start: Optional[date] = None,
        end: Optional[date] = None,
        bot_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if kind not in cls.KINDS:
            raise ValueError(f"Unknown report kind: {kind}")

        window_start, window_end = parse_window(start, end)
        bots = _scope_bots(db, bot_id, user_id)
        bot_ids = [b.id for b in bots]
        bot_names = {b.id: b.name for b in bots}

        convos = AnalyticsService._conversations(db, bot_ids, window_start, window_end)
        convo_ids = [c.id for c in convos]
        messages = AnalyticsService._messages(db, convo_ids)
        message_counts = Counter(m.conversation_id for m in messages)

        leads_query = db.query(Lead).filter(
            Lead.created_at >= window_start, Lead.created_at <= window_end
        )
        if bot_id is not None:
            leads_query = leads_query.filter(Lead.bot_id == bot_id)
        elif user_id is not None:
            leads_query = leads_query.filter(Lead.bot_id.in_(bot_ids or [-1]))
        leads = leads_query.order_by(Lead.created_at.asc()).all()

        lead_convo_ids = {lead.conversation_id for lead in leads if lead.conversation_id}

        def handoff(convo: Conversation) -> bool:
            return convo.status in (
                ConversationStatus.HANDOFF_REQUESTED.value,
                ConversationStatus.HANDED_OFF.value,
            )

        def resolved(convo: Conversation) -> bool:
            return convo.id in lead_convo_ids or (
                convo.status == ConversationStatus.ENDED.value and not handoff(convo)
            )

        if kind == "conversations":
            columns = [
                "conversation_id", "bot", "started_at", "intent", "status",
                "messages", "lead_captured", "handoff", "resolved",
            ]
            rows = [
                [
                    c.id, bot_names.get(c.bot_id, ""), c.started_at.isoformat(), c.intent or "",
                    c.status, message_counts.get(c.id, 0),
                    "yes" if c.id in lead_convo_ids else "no",
                    "yes" if handoff(c) else "no",
                    "yes" if resolved(c) else "no",
                ]
                for c in convos
            ]
            summary = {"conversations": len(convos)}

        elif kind == "leads":
            columns = [
                "lead_id", "created_at", "bot", "name", "phone_masked", "email_masked",
                "preferred_contact", "intent", "location", "budget_max", "status",
            ]
            rows = [
                [
                    lead.id, lead.created_at.isoformat(), bot_names.get(lead.bot_id, ""), lead.name,
                    _mask(lead.phone, 4), _mask(lead.email, 6), lead.preferred_contact,
                    lead.intent or "", lead.location or "", lead.budget_max or "", lead.status,
                ]
                for lead in leads
            ]
            summary = {"leads": len(leads)}

        elif kind == "bot_usage":
            columns = [
                "bot_id", "bot", "status", "conversations", "unique_users", "messages",
                "leads", "handoffs", "resolution_rate",
            ]
            rows = []
            for bot in bots:
                bot_convos = [c for c in convos if c.bot_id == bot.id]
                bot_messages = [m for m in messages if m.conversation_id in {c.id for c in bot_convos}]
                bot_resolved = [c for c in bot_convos if resolved(c)]
                rows.append([
                    bot.id, bot.name, bot.status, len(bot_convos),
                    len({c.session_id for c in bot_convos}), len(bot_messages),
                    sum(1 for lead in leads if lead.bot_id == bot.id),
                    sum(1 for c in bot_convos if handoff(c)),
                    round(len(bot_resolved) / len(bot_convos) * 100, 1) if bot_convos else 0.0,
                ])
            summary = {"bots": len(bots), "conversations": len(convos)}

        elif kind == "intents":
            columns = ["intent", "conversations", "share_pct"]
            counts = Counter((c.intent or "unknown").lower() for c in convos)
            total = len(convos)
            rows = [
                [intent, count, round(count / total * 100, 1) if total else 0.0]
                for intent, count in counts.most_common()
            ]
            summary = {"conversations": total}

        elif kind == "handoffs":
            columns = ["conversation_id", "bot", "started_at", "status", "last_message_at", "messages"]
            rows = []
            for convo in convos:
                if not handoff(convo):
                    continue
                thread = [m for m in messages if m.conversation_id == convo.id]
                last = thread[-1].timestamp.isoformat() if thread else ""
                rows.append([
                    convo.id, bot_names.get(convo.bot_id, ""), convo.started_at.isoformat(),
                    convo.status, last, len(thread),
                ])
            summary = {"handoffs": len(rows)}

        else:  # unanswered
            columns = ["conversation_id", "bot", "asked_at", "reason", "question"]
            unanswered = AnalyticsService._unanswered(messages, convos)
            convo_by_id = {c.id: c for c in convos}
            rows = [
                [
                    row["conversation_id"],
                    bot_names.get(convo_by_id[row["conversation_id"]].bot_id, ""),
                    row["asked_at"].isoformat(),
                    row["reason"],
                    row["question"],
                ]
                for row in unanswered
            ]
            summary = {"unanswered": len(rows)}

        return {
            "kind": kind,
            "title": {
                "conversations": "Conversations",
                "leads": "Leads",
                "bot_usage": "Bot usage",
                "intents": "Intent distribution",
                "handoffs": "Handoffs",
                "unanswered": "Unanswered questions",
            }[kind],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "range": {
                "start": window_start.date().isoformat(),
                "end": window_end.date().isoformat(),
            },
            "filters": {
                "bot_id": bot_id,
                "scope": "platform" if user_id is None else "business",
            },
            "columns": columns,
            "rows": rows,
            "summary": summary,
        }

    # ── renderers ─────────────────────────────────────────────────────────────

    @staticmethod
    def to_csv(report: Dict[str, Any]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(report["columns"])
        writer.writerows(report["rows"])
        return buffer.getvalue()

    @staticmethod
    def filename(report: Dict[str, Any]) -> str:
        return (
            f"brim_{report['kind']}_{report['range']['start']}_to_{report['range']['end']}.csv"
        )

    # ── PDF renderer ─────────────────────────────────────────────────────────
    @staticmethod
    def to_pdf(report: Dict[str, Any]) -> bytes:
        """
        Render a report dict as a PDF.

        The report structure is renderer-neutral, so this is a second presentation of the same
        rows the CSV and JSON endpoints return. Helvetica is limited to Latin-1, so text is
        transliterated with a replacement character rather than raising mid-generation.
        """
        from fpdf import FPDF

        def safe(value: Any) -> str:
            text = "" if value is None else str(value)
            return text.encode("latin-1", "replace").decode("latin-1")

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=12)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 15)
        pdf.cell(0, 9, safe(report["title"]), ln=1)
        pdf.set_font("Helvetica", "", 9)
        window = report.get("range") or {}
        pdf.cell(
            0, 6,
            safe(
                f"Generated {report.get('generated_at')}  |  Range {window.get('start')} to "
                f"{window.get('end')}  |  {len(report.get('rows') or [])} rows"
            ),
            ln=1,
        )
        for key, value in (report.get("summary") or {}).items():
            pdf.cell(0, 5, safe(f"{key}: {value}"), ln=1)
        pdf.ln(3)

        columns = report["columns"]
        rows = report["rows"]
        usable = pdf.w - 2 * pdf.l_margin
        width = usable / max(len(columns), 1)

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(238, 236, 248)
        for column in columns:
            label = str(column).replace("_", " ").title()
            pdf.cell(width, 7, safe(label)[:34], border=1, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        for row in rows:
            # Keep the table on one line per record; truncate rather than wrap so page breaks
            # remain predictable.
            # Rows are positional lists (the same shape the CSV writer consumes).
            for index in range(len(columns)):
                value = row[index] if index < len(row) else ""
                pdf.cell(width, 6, safe(value)[:46], border=1)
            pdf.ln()

        if not rows:
            pdf.set_font("Helvetica", "I", 9)
            pdf.cell(0, 8, "No records in this range.", ln=1)

        return bytes(pdf.output())
