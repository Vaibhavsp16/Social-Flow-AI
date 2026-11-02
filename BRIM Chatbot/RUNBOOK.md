# BRIM AI — Runbook

Everything needed to start the project and demonstrate Phase 1–4. Pick **Option A** (Docker) or
**Option B** (local dev). Option B is faster to start; Option A is the closer match to a
production deployment.

Run all commands from the `BRIM Chatbot` folder unless a step says otherwise.

```
BRIM Chatbot/
├── docker-compose.yml      postgres + backend + frontend
├── backend/                FastAPI + SQLAlchemy
├── frontend/               React + Vite
├── RUNBOOK.md              this file
└── DEMO_READINESS_REPORT.md
```

---

## Demo account (ready to use)

The workspace is pre-seeded so the demo starts on real content, not an empty dashboard.

| Item | Value |
|---|---|
| Login | `demo@brim.ai` / `Demo@12345` |
| Project | BRIM Branding Studio (Real Estate) |
| Bot | BRIM Property Advisor — Real Estate knowledge pack indexed (6 chunks) |

Rebuild it at any time (idempotent — it logs in and refreshes instead of duplicating):

```bash
cd backend
python scripts/seed_demo_account.py
```

`scripts/clean_test_data.sql` removes the `*@example.com` accounts created by the test suite
without touching real accounts. Take a `pg_dump` first.

---

## BRIM industry knowledge packs

The eight industries from https://brim.co.in/industry/ each have a committed text snapshot in
`backend/demo_documents/brim/`. Seeding one indexes the agency's positioning, service catalogue and
FAQs for that industry. Rebuild the snapshots from the live site when the content changes:

```bash
cd backend
python scripts/build_industry_packs.py
```

`GET /api/knowledge/industry-packs` lists them; `POST /api/bots/{id}/knowledge/seed-industry` with
`{"industry_key": "jewellery"}` attaches one (re-seeding refreshes, never duplicates).

---

## Prerequisites

| Tool | Notes |
|---|---|
| Docker Desktop | Must be **running** (whale icon steady). Needed for PostgreSQL in both options. |
| Python 3.12 | Option B only. The virtualenv already exists at `backend/venv`. |
| Node.js 18+ | Option B only. |

---

## Option A — Docker (whole stack)

```bash
cd "BRIM Chatbot"
docker compose up -d --build
docker compose ps
```

Wait until `brim_ai_postgres` and `brim_ai_backend` both show `healthy`.

| Service | URL |
|---|---|
| Frontend | http://localhost:8080 |
| Backend API | http://localhost:8000/api |
| API docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5433 (user `brim_user`, db `brim_ai_db`) |

To confirm the right database is being used:

```bash
docker compose logs backend | grep "Database connected"
# expect: Database connected: postgresql (postgresql+psycopg2://***@postgres:5432/brim_ai_db)
```

To stop (data is kept):

```bash
docker compose down
```

To wipe everything and start clean:

```bash
docker compose down -v
docker compose up -d --build
```

---

## Option B — Local development (3 terminals)

### Terminal 1 — Database

```bash
cd "BRIM Chatbot"
docker compose up -d postgres
docker compose ps            # wait for "healthy"
```

### Terminal 2 — Backend

```bash
cd "BRIM Chatbot/backend"
.\venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> First run only — if `venv` is missing:
> ```bash
> python -m venv venv
> .\venv\Scripts\activate
> pip install -r requirements.txt
> ```

**Critical check — the very first log lines must read:**

```
INFO:  Database connected: postgresql (postgresql+psycopg2://***@127.0.0.1:5433/brim_ai_db)
```

If instead you see `Falling back to local SQLite`, PostgreSQL is not reachable and the app is
using a throwaway SQLite file. Fix that before demoing — see Troubleshooting.

### Terminal 3 — Frontend

```bash
cd "BRIM Chatbot/frontend"
npm install          # first run only
npm run dev
```

Open **http://localhost:5173**.

---

## Demo script (the flow to walk through)

1. **Sign up / Log in** at http://localhost:5173 (any email + 6-char password).
2. **Dashboard** → click **+ Create New Bot**.
3. **Step 1** → enter a bot name, pick any language/personality.
4. **Step 2 (Knowledge)** → keep the **🏢 Real Estate Guide** pre-packaged option selected
   (you can also upload your own PDF/DOCX/TXT/PNG/JPG here).
5. **Steps 3–4** → continue, then **Create Bot**.
6. **Open Bot Overview** → open the **Knowledge Base** tab.
   The source shows **COMPLETED** with a chunk count and a `✓ Ready` marker. Click **Inspect**
   to see the extracted text.
7. Click **💬 Open Interactive Chat**.
8. Ask: **"What are the 3 BHK prices and amenities at Sunset Palms?"**
   → Answer quotes real facts from the document (1.85 Crore, 3 BHK, rooftop pool) with source
   citation chips.
9. Ask something off-topic: **"What is the warranty policy on interstellar starships to Pluto?"**
   → The bot refuses politely and cites nothing.
10. Refresh the browser → the conversation history is still there.

Optional isolation proof: create a second bot in a **Healthcare** project, give it a different
document, and confirm each bot only answers from its own knowledge.

---

## Verify the whole pipeline automatically

```bash
cd "BRIM Chatbot/backend"
.\venv\Scripts\activate
python -m pytest tests -q
```

Expected: **27 passed**. This drives the real FastAPI app and database through authentication,
project/bot creation, knowledge upload → extraction → chunking → embeddings → `COMPLETED`,
retrieval, grounded answering, refusal, bot isolation and conversation persistence.

For a readable report with per-area PASS/FAIL output:

```bash
python tests/test_e2e_demo.py
```

---

## Verifying the database directly

```bash
docker exec -e PGPASSWORD=brim_password_2026 brim_ai_postgres \
  psql -U brim_user -d brim_ai_db -c "
    SELECT (SELECT count(*) FROM users)             AS users,
           (SELECT count(*) FROM projects)          AS projects,
           (SELECT count(*) FROM bots)              AS bots,
           (SELECT count(*) FROM knowledge_sources) AS sources,
           (SELECT count(*) FROM knowledge_chunks)  AS chunks,
           (SELECT count(*) FROM conversations)     AS conversations,
           (SELECT count(*) FROM messages)          AS messages;"

# Confirm embeddings are physically stored as vectors, not just JSON
docker exec -e PGPASSWORD=brim_password_2026 brim_ai_postgres \
  psql -U brim_user -d brim_ai_db -c "
    SELECT count(*) AS chunks,
           count(embedding_vector) AS with_vector,
           min(vector_dims(embedding_vector)) AS dims
    FROM knowledge_chunks;"
```

---

## Configuration

`backend/.env` is the single source of truth:

| Variable | Purpose |
|---|---|
| `POSTGRES_*` | Database connection |
| `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT auth |
| `OPENAI_API_KEY` | Enables GPT-4o-mini answers and OpenAI embeddings |
| `EMBEDDING_PROVIDER` | `auto` (default), `openai`, or `local` |
| `BACKEND_CORS_ORIGINS` | Allowed frontend origins, comma separated |
| `ALLOW_SQLITE_FALLBACK` | Set `false` to fail fast instead of degrading to SQLite |

**About `OPENAI_API_KEY`:** the app works fully without it. Answers then come from a
deterministic grounded synthesizer that quotes the retrieved document text, and embeddings use a
local projection. With a funded key, answers become natural-language and embeddings become
semantic. No code change is needed — it switches automatically. `openai` is already in
`requirements.txt`.

---

## Troubleshooting

**"Falling back to local SQLite" in the backend log**
PostgreSQL is unreachable. Check `docker compose ps` shows `brim_ai_postgres` as `healthy`, and
that `POSTGRES_PORT` in `backend/.env` matches the host port (`5433`). Data written while in
fallback mode is not in PostgreSQL.

**`ModuleNotFoundError: No module named 'psycopg'`**
You are running a bare `postgresql://` URL. The app pins `postgresql+psycopg2://` in
`app/core/config.py`; make sure `DATABASE_URL` is not set to a bare URL in your environment.

**Upload succeeds but status is `FAILED` or chunks are 0**
The file yielded no extractable text (a scanned/image-only PDF needs OCR). The UI now shows the
real error message under the file name. Use a text-based PDF/DOCX/TXT.

**Answers say "I do not have enough information…"**
Either the bot genuinely has no completed knowledge source, or the question shares no vocabulary
with the document. Check the Knowledge Base tab shows `COMPLETED` with chunks > 0, then ask a
question using words that appear in the document.

**Port already in use**
Postgres host port is configurable: `POSTGRES_HOST_PORT=5434 docker compose up -d` and update
`POSTGRES_PORT` in `backend/.env` to match.

**Reset the database completely**
```bash
docker compose down -v && docker compose up -d postgres
```
Then restart the backend — it recreates the schema, the pgvector extension and the seed documents.

---

## Real-estate demo (Phase 5)

The Real Estate bot runs a guided flow: greeting → buy/rent/browse → requirements → shortlist →
lead capture → confirmation, with human handoff available at any point.

**Scripted end-to-end check (no server needed, database only):**

```bash
cd backend
python scripts/demo_real_estate.py
```

It prints the buying, renting, browsing, handoff and "no invented listing" transcripts, and the lead
row that was captured.

**Live demo lines** (use the demo account, open the Real Estate bot's chat):

1. `I'm looking to buy a 3 BHK apartment in Ambli, budget around 2 crore` → shortlist card
2. `can someone call me?` → lead capture starts
3. `Ravi Patel` → `98765 43210` → `ravi.patel@example.com` → `WhatsApp` → confirmation
4. `What services does BRIM offer for real estate brands?` → grounded answer with citations
5. Fresh chat: `I want a 2 BHK on rent in Bopal under 40k` → rental shortlist (or an honest
   "no exact match, here are closest")
6. Fresh chat: `I'd rather speak to a human advisor` → conversation status HANDOFF_REQUESTED
7. Fresh chat: `Do you have a 5 BHK penthouse in Gandhinagar?` → no invented listing

**Inventory:** `backend/demo_documents/prycoons_properties.json` is development data (13 records,
all `is_mock=true`). Seed per bot with `POST /api/bots/{id}/properties/seed` or automatically on the
first chat turn. Leads: `GET /api/bots/{id}/leads`.

**LLM:** no API key is configured. Answers use the local deterministic synthesiser and local
embeddings. To enable Puter.js in the browser, set `VITE_USE_PUTER=true` in `frontend/.env` and sign
in to a Puter account in that browser.

---

## Contextual greeting + multilingual demo

Open a Real Estate bot's chat. The opening message is generated server-side and stored, so it
respects the visitor's time of day, language and (if permitted) city.

1. **Late-night / morning greeting** — open a new chat; the greeting matches the current hour.
2. **Deny location** — when Chrome asks, block it. The chat still opens (time-only greeting).
   Allow it instead and the greeting may add a one-line weather note for the city.
3. **Hindi** — select "हिन्दी" in the header dropdown, then send
   `मुझे 3 बीएचके फ्लैट चाहिए अंबली में` → Hindi reply with an Orion Heights card.
   Follow with `बजट 2 करोड़ है` → Hindi shortlist.
4. **Switch back** — set the dropdown to Auto and send `can someone call me?` → English reply,
   with Ambli / 3 BHK / ₹2.0 Cr still on the state chips (language changed, state did not).
5. **Refusal** — ask something outside the knowledge base → the refusal is in the visitor's
   language and carries no citations.

Environment switches and the external API list are in `CONTEXT_AND_LANGUAGE.md`.
