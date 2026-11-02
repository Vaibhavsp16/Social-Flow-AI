# Phase review — analytics, reporting and administration

Tested 24 October 2026 against the running stack (FastAPI + PostgreSQL/pgvector + React),
real OpenAI-free embeddings, real data only.

## What was verified

### Automated
`pytest tests -q` → **76 passed** (60 existing + 16 new in `tests/test_analytics_admin.py`).

The new tests assert:

- every bot metric equals the matching SQL count (conversations, messages, leads, handoffs)
- intent distribution and resolution maths (1 lead + 2 open/handoff = 33.3% resolved)
- an empty bot returns `has_data: false` and no volume series
- a future-only date range excludes everything
- a business account gets **404** on another tenant's bot analytics
- business reports contain only that tenant's rows
- business accounts get **403** on `/api/admin/*`
- admin sees platform totals, users, bots and masked lead contacts
- activity events exist for signup, project, bot, publish, conversation, lead
- CSV header + row count equal the JSON report for all six kinds
- lead CSV masks phone/email while keeping the name and intent

### Browser (real Chrome)

Business account (`demo@brim.ai`), Analytics page:

| Card | Value |
|---|---|
| Total conversations | 9 |
| Unique users | 9 |
| Messages | 46 |
| Leads | 1 |
| Handoffs | 0 |
| Resolution rate | 11.1% |
| Range | 2026-09-25 → 2026-10-24 |

- Sidebar has no admin link for a business account.
- Direct `/admin` navigation returns 403 from the API and renders no platform data.
- Conversations CSV downloads as `brim_conversations.csv`.

Admin account (`admin@brim.ai`) — verified through the API after the dev server hit its
process limit:

| Metric | Value |
|---|---|
| Users | 424 (415 business, 9 admin) |
| Bots | 504 |
| Conversations | 257 |
| Messages | 1054 |
| Leads | 27 |
| Handoffs | 28 |
| Resolution rate | 10.5% |
| Activity event types | 9 (`bot_published`, `bot_created`, `project_created`, `user_signup`, `knowledge_added`, `conversation_started`, `user_login`, `lead_captured`, `handoff_requested`) |

Lead rows are masked: `Ravi Patel · ******3210 · ****************le.com`. No password hashes are
serialised anywhere.

### Domain regression (documents, websites, RAG)

`python scripts/diagnose_e2e.py` — a fresh bot with:

| Input | Result |
|---|---|
| DOCX (Orion handbook) | COMPLETED, 1 chunk, grounded answer at confidence 0.46 |
| TXT (Northwind policy) | COMPLETED, 1 chunk, answer at 0.35 |
| PDF (W3C test file) | COMPLETED, 1 chunk |
| PNG flyer | **FAILED** — no OCR provider configured (see below) |
| Long TXT manual (~8k chars) | COMPLETED, 17 chunks; mid-document question answered at 0.25 |
| Website `brim.co.in/industry/real-estate/` | COMPLETED, 1 page, 3889 chars, 6 chunks in 2.5 s |
| Off-topic question | Refused, **0 sources** |
| Overview question | Summarises the distinct sources it holds |

## What changed in this phase

1. `activity_events` table + `log_activity()`; nine event types wired at the points that create
   them. Events join the caller's transaction and never break a request.
2. `AnalyticsService` — bot and platform reports with date windows; `has_data` drives the empty
   state.
3. `ReportingService` — renderer-neutral report dict + CSV; six kinds; BOM for Excel.
4. Admin API with `require_admin`; masked customer PII; no password material.
5. UI: real Analytics page, bot Performance panel on the overview and analytics tabs, Admin console
   with tabs, range selector and CSV export. Non-admin `/admin` now shows an explicit
   "Administrator access required" card instead of an empty shell.

## What still needs changing

**1. Image ingestion is disabled** — removing the OpenAI key removed the only OCR path in this
build (Tesseract is not installed). Current behaviour is an explicit failure message. Decide:
install Tesseract locally, or restore a vision provider, or drop image sources from the demo.

**2. Local embeddings are lexical.** They work (relevant 0.19–0.46 vs irrelevant ≤0.08 after the
threshold was raised to 0.12), but they reward vocabulary overlap. Two consequences for the demo:
questions should reuse the document's wording, and paraphrases can miss. A hosted embedding model
(or Puter, once enabled) restores semantic matching; that needs a re-embed of every chunk.

**3. "Unique users" means unique sessions.** Conversations carry `session_id`, not an
authenticated end-user. If the business wants true unique people, capture an identity (phone or
email) at first contact and count by that.

**4. Resolution is a product definition.** It is currently "produced a lead, or ended without a
handoff". Confirm that matches how Prycoons measures a resolved enquiry; alternatives are
lead-only, or "last message not a refusal".

**5. Admin console needs scale features** before real volume: search and filters (role, date,
industry), cursor pagination, and a lead-status workflow. Offset pagination is fine at hundreds of
rows, not at hundreds of thousands.

**6. Analytics are computed in Python per conversation.** Accurate and simple, but the cost grows
linearly. Above roughly 10k conversations per report window, move the totals to SQL aggregates and
keep the Python pass only for citation counts.

**7. PDF and scheduled reports are not implemented.** The report shape supports them; only the CSV
renderer exists. Say the word and PDF (WeasyPrint) plus a weekly email can be added without
touching queries.

**8. The database still carries test data** — 424 users and 504 bots, mostly from the automated
suite. The demo account itself is clean (9 conversations). Before showing the platform to Prycoons,
either run on a fresh volume or keep the demo behind `demo@brim.ai`.

**9. Credentials are demo-grade.** `admin@brim.ai / Admin@12345` and `demo@brim.ai / Demo@12345`
must be rotated before any deployment, and `SECRET_KEY` is still the development default.

**10. Dev servers are not production serving.** The Vite dev server stops after a long idle window
in this environment; use `docker compose up -d --build` (nginx + uvicorn) for the demo so the UI
does not disappear mid-session.
