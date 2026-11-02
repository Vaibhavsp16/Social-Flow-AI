# BRIM AI — Full Project Handoff / Context

> **Purpose of this file:** complete working context for an AI agent (or developer) picking up this
> project cold. It records what the system is, how it works, what was broken, what was fixed, what
> was verified, and which invariants must not be broken. Written 17 October 2026.

---

## 1. What this project is

**BRIM AI** is an industry-centric chatbot builder. A user signs up, creates a project, creates a
chatbot inside it, attaches knowledge (documents, websites, images, raw instructions), and then
chats with the bot. Answers are grounded in the attached knowledge via RAG (retrieval-augmented
generation) and always cite their sources.

Implemented scope is **Phases 1–4**:

| Phase | Contents |
|---|---|
| 1 — Foundation | Auth, projects, bots, dashboard |
| 2 — Knowledge Management | Upload, extraction, chunking, processing status |
| 3 — AI/RAG Foundation | Embeddings, vector storage, retrieval |
| 4 — Conversation Engine | Conversations, messages, intent, persistence, grounded chat |

**Phase 5 was explicitly out of scope and must not be started without a new instruction.**

### Repository layout

```
BRIM_Assessment/                        <- git repo root
├── src/, base44/, ...                  <- UNRELATED project (Base44 "Social Flow AI" app)
└── BRIM Chatbot/                       <- THIS project
    ├── backend/
    │   ├── app/
    │   │   ├── api/            auth, projects, bots, knowledge, chat, conversations, deps
    │   │   ├── core/           config.py, security.py, constants.py
    │   │   ├── database/       base.py, session.py
    │   │   ├── models/         user, project, bot, knowledge_source, knowledge_chunk,
    │   │   │                   conversation, message
    │   │   ├── schemas/        pydantic request/response models
    │   │   └── services/       auth, project, bot, knowledge, document_processor,
    │   │                       embedding, retrieval, llm, conversation
    │   ├── demo_documents/     seed knowledge used by the "pre-packaged" bot option
    │   ├── tests/              test_api, test_knowledge, test_retrieval_rag, test_e2e_demo
    │   ├── migrations/         Alembic (head = da84ee7f07ea)
    │   ├── alembic.ini
    │   ├── requirements.txt
    │   ├── Dockerfile
    │   └── .env                SECRETS — gitignored, never commit
    ├── frontend/
    │   ├── src/{pages,components,services,context,routes,layouts,constants}
    │   ├── nginx.conf          SPA history fallback
    │   ├── Dockerfile
    │   └── package.json
    ├── docker-compose.yml      postgres + backend + frontend
    ├── RUNBOOK.md              how to start and demo
    ├── DEMO_QUESTIONS.md       42 verified questions across the 3 seed knowledge bases
    ├── DEMO_READINESS_REPORT.md  engineering report (problems / fixes / verification)
    └── API_KEYS_AND_COST.md    API key + cost breakdown for management
```

**Git:** remote `https://github.com/Vaibhavsp16/Social-Flow-AI.git`, branch `main`.
HEAD at time of writing: `3706e99 fix(brim-ai): make the Phase 1-4 knowledge pipeline and RAG
work end-to-end`. Note the repo is named Social-Flow-AI but contains both projects.

---

## 2. Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.1.3, Pydantic v2, python-jose (JWT HS256), bcrypt |
| Database | PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16` image) |
| Migrations | Alembic |
| LLM | OpenAI `gpt-4o-mini` (temperature 0.25, max_tokens 512) |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dims) |
| Frontend | React 18, Vite 5, react-router-dom v6, axios, lucide-react |
| Serving | nginx (built SPA) via Docker, or `vite dev` locally |
| Parsing | pypdf, python-docx, Pillow + optional pytesseract (OCR), BeautifulSoup |
| Tests | pytest + FastAPI TestClient (runs against the real database) |

---

## 3. Data model and ownership chain

```
User ──< Project ──< Bot ──< KnowledgeSource ──< KnowledgeChunk
                        └──< Conversation ──< Message
```

Ownership is enforced at every route by walking `Bot → Project → User`. A knowledge chunk is
retrievable **only** through its own `bot_id`.

Key columns on `knowledge_chunks`: `bot_id`, `knowledge_source_id`, `chunk_index`, `content`,
`embedding_json` (Text), `embedding_vector` (`Vector(1536)`), `embedding_provider`
(`'openai' | 'local' | NULL`), `page_number`.

`knowledge_sources`: `source_type` (DOCUMENT | IMAGE | WEBSITE | SOCIAL_LINK | INSTRUCTION),
`processing_status` (UPLOADED | PROCESSING | COMPLETED | FAILED), `chunks_count`, `error_message`,
`extracted_text`, `file_path`, `file_size`.

Conversation statuses: ACTIVE / CLOSED / HANDOFF. Messages carry `sender` (USER | ASSISTANT |
SYSTEM), `intent`, `metadata_json`.

---

## 4. The knowledge pipeline (end to end)

```
Upload (multipart)  POST /api/bots/{bot_id}/knowledge/upload
  └─ KnowledgeService.upload_file
       ├─ validate extension + size
       ├─ DocumentProcessor.extract_text_from_file        (pdf / docx / txt / image OCR)
       ├─ DocumentProcessor.clean_text
       ├─ DocumentProcessor.chunk_text                     (800 chars, 100 overlap)
       ├─ KnowledgeService._finalize_source                (status COMPLETED only if chunks > 0)
       └─ KnowledgeService._generate_and_save_chunks
            ├─ EmbeddingService.get_embedding_with_provider(chunk)  -> (vector, provider)
            └─ INSERT KnowledgeChunk(embedding_vector=vector, embedding_provider=provider)

Question  POST /api/bots/{bot_id}/chat   (or /api/conversations/{id}/messages)
  └─ RetrievalService.search_relevant_chunks(bot_id, query, top_k=4, threshold=0.02)
       ├─ embed the query -> (vector, provider)
       ├─ PostgreSQL path: ORDER BY embedding_vector <=> :query  (cosine distance)
       │  filtered by bot_id AND embedding_provider (NULL counts as 'local')
       ├─ non-PostgreSQL path: in-memory cosine over that bot's chunks
       └─ _apply_relevance_gate: keep score >= threshold;
          if none, return the single best chunk only when score > 0;
          else [] -> (overview fallback if the question is broad) -> else refusal
  └─ LLMService.generate_grounded_response
       ├─ greeting short-circuit
       ├─ no chunks -> GROUNDED_REFUSAL_MESSAGE
       ├─ OpenAI client available -> strict grounded system prompt + retrieved context
       └─ unavailable -> _local_grounded_synthesis (deterministic, quotes retrieved text)
  └─ citations built from the retrieved chunks
```

---

## 5. Critical invariants — do not break these

These are the exact things that were wrong before. Reverting any of them re-introduces the original
outage.

1. **The database URL must stay pinned to `postgresql+psycopg2://`.**
   SQLAlchemy 2.1 resolves a bare `postgresql://` to the **psycopg (v3)** dialect. `requirements.txt`
   installs `psycopg2-binary`, not `psycopg`. With the bare scheme every connection fails.
   See `app/core/config.py::get_database_url`.

2. **`create_all()` does not ALTER existing tables.** `init_db()` must keep calling
   `_ensure_pgvector_extension()` and `_sync_schema()` (in `app/database/session.py`), which add
   missing columns. Without this, a pre-existing database silently lacks `embedding_vector` and
   every chunk INSERT and retrieval SELECT throws `no such column`.

3. **Never compare embeddings from different providers.** `embedding_provider` records who produced
   each vector; retrieval filters on it. OpenAI vectors and local hashing vectors occupy unrelated
   spaces — mixing them produces meaningless scores. NULL means 'local' (legacy rows).

4. **A knowledge source is COMPLETED only if it produced chunks.** Otherwise FAILED with a real
   `error_message`. Do not mark success on empty extraction.

5. **Do not make retrieval "always return something".** If nothing clears the threshold the correct
   behaviour is a refusal. The only exception is the deliberate *overview* fallback for broad
   questions like "what information do you have about this business?", gated by `OVERVIEW_TERMS`.

6. **`.env` is gitignored and contains a live API key.** Never commit it, never print its value.

7. **The vector column is fixed at 1536 dimensions.** Switching to `text-embedding-3-large`
   (3072 dims) requires a migration **and** re-embedding every existing chunk.

8. **Inside Docker the database host is `postgres:5432`.** `backend/.env` says
   `POSTGRES_PORT=5433` because that is the *host* mapping. `docker-compose.yml` overrides both
   host and port, and sets `ALLOW_SQLITE_FALLBACK=false` so a broken connection fails loudly
   instead of silently degrading.

9. **The application writes no uploaded files to disk.** Text is extracted and stored in the
   database; there is no uploads volume to persist.

---

## 6. What was broken, and what was fixed

### Root cause of the original bug

Two reported symptoms — *"the chatbot says it has no knowledge base"* and *"adding knowledge while
creating a bot does not work"* — had a single cause chain:

1. `postgresql://` resolved to the uninstalled `psycopg` v3 driver → connection failed.
2. `create_db_engine()` swallowed the exception and silently fell back to SQLite.
3. That SQLite file predated the `embedding_vector` column, and `create_all()` does not ALTER.
4. Every chunk INSERT and every retrieval SELECT therefore threw, so uploads stored nothing and the
   bot always produced its refusal message.

### Backend fixes

| File | Fix |
|---|---|
| `app/core/config.py` | Pin `postgresql+psycopg2://`; make `BACKEND_CORS_ORIGINS` accept a comma-separated string or JSON (a `List[str]` field cannot be set from `.env`); add `OPENAI_API_KEY`, `EMBEDDING_PROVIDER` |
| `app/database/session.py` | Loud logging on fallback; `ALLOW_SQLITE_FALLBACK`; `CREATE EXTENSION IF NOT EXISTS vector`; `_sync_schema()` ALTER-based drift repair |
| `app/main.py` | CORS uses configured origins instead of `["*"]` with credentials |
| `app/services/knowledge_service.py` | `_finalize_source()` sets COMPLETED only when chunks exist; stores `embedding_provider` |
| `app/services/embedding_service.py` | `get_embedding_with_provider()`; rewritten local projection (punctuation-insensitive tokenising, stop-word removal, sublinear term weighting, word bigrams, char 4-grams) |
| `app/services/retrieval_service.py` | `_chunk_vector()`, `_chunk_provider()`, `_apply_relevance_gate()`, `_is_overview_query()`, `_overview_fallback()`; provider filtering |
| `app/services/llm_service.py` | `_greeting_reply()` before the knowledge check; overview-question handling; `_humanize()` for readable fallback output; one canonical refusal string |
| `app/models/knowledge_chunk.py` | Added `embedding_provider` |
| `app/schemas/knowledge_source.py` | Exposed `extracted_text` |
| `app/schemas/chat.py` | Threshold default aligned to `0.02` (was `0.20`, stricter than the service) |
| `app/api/chat.py` | Passes `threshold` through on both chat endpoints |
| `requirements.txt` | Added `openai` (its absence meant the LLM path never ran) and `alembic` |

### Frontend fixes

| File | Fix |
|---|---|
| `components/KnowledgeManager.jsx` | `stopPropagation` on the file input (the input sat inside a clickable dropzone, causing a recursive `click()` loop); renders `error_message` on FAILED; shows "✓ Ready" |
| `pages/ChatInterface.jsx` | Initialise once per bot via a ref — the effect depended on `bot`, creating a second empty conversation on every open; personalised welcome updates in place instead |
| `pages/BotOverview.jsx` | Replaced fabricated knowledge counts and a dead "Manage sources" toast with real data; real conversation history list; real stat cards |
| `services/api.js` | Timeout 15s → 60s |
| `services/knowledgeService.js` | 180s upload / 120s website timeouts |

### Infrastructure and docs added

`backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `.dockerignore` ×2, full-stack
`docker-compose.yml`, Alembic (`alembic.ini`, `migrations/`, initial revision verified against an
empty database), `RUNBOOK.md`, `DEMO_QUESTIONS.md`, `DEMO_READINESS_REPORT.md`,
`API_KEYS_AND_COST.md`, and a rewritten `tests/test_e2e_demo.py`.

---

## 7. Verified state

| Check | Result |
|---|---|
| `pytest tests -q` | **27 passed** (was 7 passed / 7 failed / 4 errors) |
| Live HTTP flow (uvicorn + PostgreSQL) | 23/23 checks passed |
| Docker full stack | postgres healthy, backend healthy, frontend running |
| Backend startup log | `Database connected: postgresql (postgresql+psycopg2://***@postgres:5432/brim_ai_db)` |
| Embeddings physically stored | confirmed 1536-dim vectors in pgvector |
| Bot isolation | a bot never retrieves another bot's chunks |
| Refusal on unknown knowledge | confirmed |
| Conversation persistence | confirmed across refresh |
| Frontend production build | succeeds |

Tests cover: auth, project/bot persistence, upload → extract → chunk → embed → COMPLETED,
retrieval scoping, grounded answer, unknown-question refusal, bot isolation, conversation
persistence with RAG, greeting/overview handling, embedding separability.

> The suite runs against the **real database** and creates data each run (no transaction rollback).
> That is why the database accumulates many `stack_*` / `e2e_*` users and bots. Harmless, but it
> makes raw table counts meaningless.

---

## 8. Configuration

`backend/.env` (gitignored) holds:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | JWT signing. **Still the development placeholder — randomise before any public deployment.** |
| `POSTGRES_SERVER` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Local values. Docker overrides host/port. |
| `OPENAI_API_KEY` | Present. See limitation #1 below. |
| `EMBEDDING_PROVIDER` | `auto` — prefers OpenAI, falls back to local |
| `ALLOW_SQLITE_FALLBACK` | Dev convenience; compose sets `false` |
| `BACKEND_CORS_ORIGINS` | Comma-separated or JSON array |

Do not invent a second configuration system — `app/core/config.py` is the single source of truth and
`migrations/env.py` reads it too.

---

## 9. How to run

Full detail in `RUNBOOK.md`. Short version:

**Docker (whole stack)**
```bash
cd "BRIM Chatbot"
docker compose up -d --build
```
Frontend http://localhost:8080 · API http://localhost:8000/api · docs http://localhost:8000/docs

**Local development**
```bash
# 1 database
cd "BRIM Chatbot" && docker compose up -d postgres

# 2 backend
cd "BRIM Chatbot/backend"
python -m venv venv                      # first time only
.\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 3 frontend
cd "BRIM Chatbot/frontend" && npm install && npm run dev   # http://localhost:5173
```

**Stop**
```bash
docker compose stop        # pause, keeps data
docker compose down        # remove containers, keeps volume
docker compose down -v     # DESTROYS the database volume
```

**Migrations**
```bash
cd backend
alembic current
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

---

## 10. Known limitations / open items

1. **The OpenAI account has no credits** (`429 credit_balance_exhausted`, last confirmed on both a
   previous key and its replacement). Consequences:
   - Answers come from `_local_grounded_synthesis` — deterministic, quoted from the retrieved
     document, **not** natural conversation.
   - Embeddings use the local hashing projection, so retrieval is **lexical**: questions should use
     vocabulary that appears in the document.
   - Everything above still passes in this mode. Adding credits activates the LLM path with no code
     change.
   - The API key was also pasted into a chat, so it should be rotated as a hygiene measure.

2. **The UI has never been click-tested in a real browser.** The browser automation bridge was
   unavailable, so the frontend is verified only by a production build, API-contract matching, and
   CORS preflight. A manual pass through the demo flow is still advisable.

3. **Prompt injection is not addressed.** Retrieved chunk text and user-supplied "instructions"
   sources go into the system prompt. Acceptable for a trusted-admin demo; needs hardening before
   untrusted users can add knowledge.

4. **No response streaming** — chat replies arrive as a single response.

5. **No rate limiting, no per-tenant quotas** on chat endpoints.

6. **The demo documents are small** (3–4 chunks each). Cost and quality figures scale with document
   size and are not representative of large corpora.

7. **`SECRET_KEY` is the development default** (see §8).

8. The repo root also contains an **unrelated Base44 project**; ignore `src/` and `base44/` when
   working on BRIM AI.

---

## 11. Demo material

Three pre-packaged knowledge bases ship in `backend/demo_documents/`:
`Prycoons_Real_Estate_Guide.txt`, `Apex_Healthcare_Clinic_Guide.txt`,
`CloudScale_SaaS_Platform_Docs.txt`.

**42 questions were verified** against the live pipeline (all return grounded answers with
citations) and are listed with their expected answers in `DEMO_QUESTIONS.md`. A good live
demonstration is asking something absent from the document — e.g. *"What is the warranty policy on
interstellar starships to Pluto?"* — and showing the bot refuse with zero citations.

---

## 12. Cost

**One paid API key is required: OpenAI.** Everything else (PostgreSQL, OCR, scraping, JWT) is
self-hosted and free. Estimated usage: ≈$0.00035 per chat message, ≈$0.0014 per 100-page document
ingested; roughly ≈$0.04 for a demo and ≈$1.80/month for 5,000 messages. Full breakdown with
assumptions in `API_KEYS_AND_COST.md`.

---

## 13. How to continue safely

- **Run the tests before and after any change:** `pytest tests -q` from `backend/`.
- **Never rewrite the architecture.** Fixes were deliberately minimal and targeted. The stack
  (React + FastAPI + PostgreSQL + pgvector + Docker) is fixed.
- **Do not start Phase 5.**
- **Do not swap the embedding model** without a migration and a full re-embed.
- **Do not add a second DB configuration path**; `app/core/config.py` is authoritative.
- **Commit style:** conventional commits, imperative subject, body explains *why*.
- **When a bug looks like "the bot has no knowledge",** check in this order: (1) which database is
  actually connected, (2) whether chunks exist for that `bot_id`, (3) whether
  `embedding_provider` matches the query's provider, (4) the retrieval score versus threshold.

---

## 14. Update — 17 October 2026 (demo hardening)

**Live OpenAI path is now active.** The supplied key was verified against `/v1/models`,
`/v1/embeddings` (1536 dims) and `/v1/chat/completions`. Root cause of it "not working" before:
`EmbeddingService`/`LLMService` read `os.getenv("OPENAI_API_KEY")` while the key only existed inside
the Settings object, and `EMBEDDING_PROVIDER` was never read at all. `app/core/config.py` now
mirrors the resolved values into `os.environ`, and the provider override is honoured. All 41 legacy
chunks were re-embedded with `scripts/reembed_chunks.py`.

**Eight BRIM industries are first-class.**
`app/core/industry_packs.py` + `demo_documents/brim/*.txt` (built by `scripts/build_industry_packs.py`)
carry the brim.co.in industry pages. `PREDEFINED_INDUSTRIES` is now the eight BRIM industries plus
"Other". New endpoints: `GET /api/knowledge/industry-packs`,
`POST /api/bots/{id}/knowledge/seed-industry` (idempotent). CreateBot auto-selects the pack for the
chosen industry; KnowledgeManager defaults the picker to the bot's own industry.

**Website ingestion is a real crawler.** `DocumentProcessor.crawl_website(url, max_pages)` follows
same-site links from the seed page (depth 1, max 12), prefers `<main>`/`<article>`, strips theme
chrome by class token, drops publish timestamps and click labels, and records the URL of each chunk
so citations point at the exact page. `max_pages` is exposed on the API and in the UI.

**Additional defects fixed during verification:**
- Native pgvector search threw on every request (`EmbeddingService.PROVIDER_LOCAL` did not exist),
  silently forcing the in-memory path.
- `/knowledge/samples` and `/knowledge/industry-packs` were shadowed by `/knowledge/{source_id}`.
- `ProjectResponse` re-validated industry on read, so legacy values 500'd the whole project list.
- The LLM refusal text diverged from `GROUNDED_REFUSAL_MESSAGE`, so refusals carried citations.
- `_apply_relevance_gate` returned the best chunk even when it scored 0 ("always return something").
- Threshold is now provider-aware (0.25 OpenAI / 0.02 local), measured: relevant 0.31–0.75,
  unrelated ≤0.11.
- Overview detection is pattern-based; the old keyword set swallowed real questions containing
  "services"/"offer".
- Conversation creation reuses an existing empty ACTIVE conversation, so a refresh no longer
  litters history with blank chats.

**Verified:** `pytest tests -q` → 35 passed. Browser click-through (real Chrome) → login, create bot
with an industry pack, grounded answer with 4 citations, refusal with zero citations, website crawl
("Crawled 3 pages and indexed 6 chunks"), history rendering after reload. Screenshots and reports in
`artifacts/`.

**Demo login:** `demo@brim.ai` / `Demo@12345` (rebuild with `scripts/seed_demo_account.py`).

---

## 15. Update — 23 October 2026 (Phase 5: Prycoons real estate + Puter)

**Phase 5 is now in scope and implemented for Real Estate.** A bot whose project industry is
"Real Estate" runs a dialogue flow instead of plain RAG; every other industry is unchanged.

    greeting → intent (buy / rent / browse) → requirements → shortlist
             → lead capture → confirmation → human handoff

**New tables** (created by `create_all`; no Alembic revision added):
`properties` (bot-scoped inventory) and `leads` (captured contacts).

**New modules**
- `app/services/property_service.py` — filter → rank → shortlist. Hard filters: listing type,
  availability, type, BHK; location is substring-matched; budget is soft so an over-budget answer
  is still possible. `describe_shortlist` builds the reply text from rows, never from a model.
- `app/services/real_estate_flow.py` — the state machine. Slots: location, property_type, bhk,
  budget, amenities, timeline, purpose. One question per turn, with a personal question mixed in;
  knowledge questions are delegated to RAG mid-flow and then the flow resumes.
- `app/api/properties.py` — `GET /bots/{id}/properties`, `POST /bots/{id}/properties/seed`,
  `GET /bots/{id}/leads`.
- `POST /conversations/{id}/handoff`, `PATCH /messages/{id}`.

**Property data is clearly mock.** `demo_documents/prycoons_properties.json` holds 13 illustrative
records (8 sale, 4 rent, 1 sold) marked `is_mock=True`; the UI card shows a "DEVELOPMENT DATA"
badge. Replace the JSON (or load real rows into `properties`) when Prycoons supplies inventory.

**Intent detection note.** The flow does not use `detect_intent` for buy/rent/browse: that counter
scores "bhk" and "available" as buying, which mislabels rentals and browsing. The flow matches
explicit verbs (rent/lease vs buy/purchase), treats "call me"/"callback" as lead acceptance rather
than handoff, and answers a message ending in "?" only when it is a genuine knowledge question.

**OpenAI key removed.** `backend/.env` now has `OPENAI_API_KEY=` (empty). Embeddings fall back to
the local deterministic engine; all chunks were re-embedded with `scripts/reembed_chunks.py` so
retrieval still works. Answers come from `_local_grounded_synthesis` (deterministic, quoted).

**Puter.js integration (optional).** `@heyputer/puter.js` is installed in the frontend and wrapped
by `src/services/puterService.js` (dynamic import, so it is not in the default bundle). When the
server has no LLM it returns a `llm_prompt`; if `VITE_USE_PUTER=true` in `frontend/.env`,
`ChatInterface` sends that prompt to Puter and persists the polished answer with `PATCH /messages/{id}`.
Default is off — everything works without it. Note Puter's SDK expects a browser session with a
signed-in Puter account; enable it only for demos where that is acceptable.

**Verified**
- `pytest tests -q` → **43 passed** (35 existing + 8 new real-estate scenarios) with no API key.
- `python scripts/demo_real_estate.py` → buying (shortlist → lead saved), renting (honest
  no-match + alternatives), browsing (no lead push), handoff (`HANDOFF_REQUESTED`), and
  no-invented-listing refusal.
- Browser (real Chrome): property card renders with price/amenities/DEVELOPMENT DATA badge;
  "can someone call me?" starts lead capture; full lead confirmation; knowledge question still
  answers with 4 citations on the local embedding engine.

---

## 16. Update — 23 October 2026 (contextual greeting + multilingual)

**Greeting pipeline.** `GreetingService.build()` → holiday (highest) → notable weather → time of
day, with wording from `app/core/messages.py`. A greeting is created once per conversation in
`POST /api/conversations` and stored as the first assistant message, so a reload does not
regenerate it. `POST /api/context/greeting` exposes the same engine for the pre-login widget.

**Languages.** en · hi · gu · mr. Detection order: explicit picker → script/word detection →
`navigator.language` → English. Devanagari is split Hindi/Marathi with function words; romanised
Hindi/Gujarati is detected from common words. Localised tokens (अंबली, બોપલ, बीएचके, करोड़ …) are
normalised before slot extraction, so requirements work in any language. Language changes wording
only — slots and stage persist, asserted in both directions by tests.

**Location.** Browser geolocation is optional, capped at 6 s, and reverse-geocoded in the browser;
only city/region is sent. Coordinates are never stored or transmitted to our API. Denial sets a
local flag and the greeting falls back to time of day.

**Weather + holidays.** `WeatherService` (Open-Meteo, no key, 15-minute per-city cache) and
`HolidayService` (JSON calendar, `HOLIDAY_FILE`) are both abstractions that degrade to "unavailable"
without raising. A holiday always outranks weather and time.

**Engagement.** One optional light question per opening greeting, gated by `ENGAGEMENT_ENABLED`
and a deterministic hash so the same conversation always gets the same greeting.

**Endpoints added:** `GET /api/context/languages`, `POST /api/context/greeting`.

**Tests:** `tests/test_context_language.py` (16) cover detection, all four time bands, holiday
priority, weather available/unavailable, location absent, stored greeting, privacy of state,
Hindi shortlist, English switch-back, explicit selection and localised refusal. Full suite: 59 passed.

**Browser verification:** contextual late-night greeting with location denied, glossary-free Hindi
reply with a property card (₹1.85 Cr), Hindi budget follow-up, then English switch-back with Ambli
/ 3 BHK / ₹2.0 Cr preserved, zero application console errors.

**Also fixed:** greeting timestamps rendered 5:30 hours early (server UTC serialised without a zone
suffix, parsed as local); `formatTime` now treats a bare timestamp as UTC.

**Known limitation:** knowledge-base answers quote the source document, so those passages stay in
the document's language even when the surrounding replies are localised. The refusal message is
translated. Full answer translation needs the LLM path (Puter or a hosted model).

---

## 17. Update — 24 October 2026 (analytics, reporting, admin)

**Metrics are SQL-derived.** `AnalyticsService.bot_report()` and `platform_report()` count real
conversations, messages, leads, handoffs and knowledge sources for a date window. `has_data` is
false when the window holds no conversations, and the UI then shows "No conversation data yet."
instead of zeros dressed up as performance. Definitions (resolved, unique users, lead conversion)
are documented in `ANALYTICS_AND_ADMIN.md`.

**Reports.** `ReportingService.build()` returns a renderer-neutral dict (columns/rows/summary/range);
CSV is one renderer over it, so PDF can be added without touching queries. Six kinds:
conversations, leads, bot_usage, intents, handoffs, unanswered. CSV is UTF-8 BOM and is asserted to
carry exactly the same rows as the JSON response.

**Admin.** `users.role == 'ADMIN'`; every `/api/admin/*` route depends on `require_admin` and returns
403 to business accounts. Lists cover users, projects, bots, conversations, leads and activity.
Lead phone/email are masked; password hashes are never serialised.

**Activity.** `activity_events` records signup, login, project/bot creation, publishing, knowledge
additions, conversation starts, lead captures and handoff requests. Events join the caller's
transaction; logging failures never break the request.

**Also changed this phase:**
- Local-embedding relevance gate raised from 0.02 to 0.12. At 0.02 an unrelated "starship warranty"
  question scored 0.078 and was answered from a policy document; genuine questions score 0.19-0.46.
- Retrieval's overview heuristic now calls the pattern-based detector instead of a keyword set, so
  "what amenities are available…" refuses rather than dumping arbitrary chunks.
- The grounded synthesiser can no longer emit its header with an empty body.
- Image ingestion now fails with an actionable message (OCR provider required) after the API key was
  removed; previously it produced a metadata placeholder.

**Tests:** `tests/test_analytics_admin.py` (16) plus the existing 60 → 76 passed.
