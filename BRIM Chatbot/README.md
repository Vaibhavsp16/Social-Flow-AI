# BRIM AI — Industry Chatbot Platform

BRIM AI lets a business create a chatbot per industry, attach knowledge (documents, websites,
instructions), and hold grounded conversations that cite their sources. The Real Estate build adds
a guided Prycoons flow — buying, renting, browsing, lead capture and human handoff — with a
contextual greeting and four languages.

---

## Architecture

```
React 18 + Vite  ──HTTP/JWT──▶  FastAPI  ──SQLAlchemy──▶  PostgreSQL 16 + pgvector
   (nginx)                       (uvicorn)                    (Docker volume)
                                     │
                                     ├─ RetrievalService  (cosine search, provider-aware)
                                     ├─ LLMService        (OpenAI or local grounded synthesis)
                                     ├─ RealEstateFlow    (deterministic dialogue manager)
                                     ├─ AnalyticsService  (metrics from stored rows)
                                     └─ ActivityService   (platform event log)
```

| Layer | Contents |
|---|---|
| `backend/app/api` | auth, projects, bots, knowledge, chat, conversations, properties, context, analytics, admin |
| `backend/app/services` | auth, bot, project, knowledge, document processor, embedding, retrieval, llm, conversation, real-estate flow, property, greeting, language, weather, holiday, analytics, reporting, activity |
| `backend/app/models` | user, project, bot, knowledge source/chunk, conversation/message, property, lead, activity |
| `frontend/src` | pages (dashboard, bots, create, overview, chat, analytics, admin), components, services, contexts |

Ownership chain: `User → Project → Bot → KnowledgeSource → KnowledgeChunk`, and
`Bot → Conversation → Message`, `Bot → Lead`. Every route walks Bot → Project → User.

---

## Setup

### Prerequisites

- Docker Desktop (recommended path), or Python 3.11+ and Node 18+
- An OpenAI key is optional: without it the platform uses local embeddings and deterministic
  grounded answers. Puter.js can supply the LLM from the browser instead.

### Docker (whole stack)

```bash
cd "BRIM Chatbot"
cp backend/.env.example backend/.env      # then edit values
docker compose up -d --build
```

- Frontend: <http://localhost:8080>
- API: <http://localhost:8000/api> · docs: <http://localhost:8000/docs>
- Postgres: `localhost:5433` (container `postgres:5432`)

### Local development

```bash
# 1. database only
docker compose up -d postgres

# 2. backend
cd backend
python -m venv venv
venv\Scripts\activate            # Windows; source venv/bin/activate elsewhere
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 3. frontend
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Create a demo account and an admin:

```bash
cd backend
python scripts/seed_demo_account.py     # demo@brim.ai / Demo@12345
python scripts/seed_admin.py            # admin@brim.ai / Admin@12345
```

> Change both passwords before any deployment.

---

## Environment variables

Backend (`backend/.env`; see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | dev placeholder | JWT signing. Startup refuses the default when `ENVIRONMENT=production`. |
| `ENVIRONMENT` | `development` | `production` enforces the secret check. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime. |
| `POSTGRES_SERVER` / `PORT` / `DB` / `USER` / `PASSWORD` | localhost / 5433 / brim_ai_db / brim_user | Database connection (compose overrides host to `postgres`). |
| `DATABASE_URL` | unset | Full URL override; must keep `postgresql+psycopg2://`. |
| `BACKEND_CORS_ORIGINS` | localhost:5173/3000/5174 | Comma list or JSON array. |
| `OPENAI_API_KEY` | empty | Enables OpenAI embeddings and gpt-4o-mini answers. |
| `EMBEDDING_PROVIDER` | `auto` | `auto` \| `openai` \| `local`. |
| `ALLOW_SQLITE_FALLBACK` | `false` | Opt-in only; a stopped database should fail loudly. |
| `RATE_LIMIT_ENABLED` | `true` | Per-IP limits on auth, chat and ingestion. |
| `WEATHER_ENABLED` / `WEATHER_PROVIDER` | `true` / `open-meteo` | Greeting weather context. |
| `WEATHER_MENTION_PROBABILITY` | `0.35` | How often pleasant weather is mentioned. |
| `ENGAGEMENT_ENABLED` / `ENGAGEMENT_PROBABILITY` | `true` / `0.5` | Optional light question in the greeting. |
| `HOLIDAY_FILE` | `demo_documents/holidays.json` | Festival calendar. |

Frontend (`frontend/.env`):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | API base. |
| `VITE_USE_PUTER` | `false` | Route grounded answers through Puter.js in the browser. |

---

## Database

PostgreSQL 16 with pgvector. `init_db()` runs on startup: it creates the extension, `create_all()`
for new tables and `_sync_schema()` to add columns that `create_all` cannot alter.

- Embeddings are stored in `knowledge_chunks.embedding_vector` (`vector(1536)`) plus
  `embedding_json` for the local provider. `embedding_provider` keeps the two spaces apart —
  retrieval only compares vectors from the same provider.
- Migrations live in `migrations/` (Alembic). Existing databases that were created by
  `create_all()` need a one-time `alembic stamp head` before `alembic upgrade head`; a fresh
  database can run `alembic upgrade head` directly.
- Deleting a user/project/bot cascades to its bots, knowledge sources, chunks, conversations,
  messages, leads and properties.

Useful commands:

```bash
alembic current
alembic upgrade head
alembic revision --autogenerate -m "describe change"
```

---

## API

Base path `/api`. All routes except `/auth/signup`, `/auth/login`, `/industries`,
`/context/languages`, `/bots/{id}/chat` and `/knowledge/*` static lists require
`Authorization: Bearer <token>`.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/signup`, `POST /auth/login`, `GET /auth/me` |
| Projects | `GET/POST /projects`, `GET/PUT/DELETE /projects/{id}` |
| Bots | `GET/POST /bots`, `GET/PUT/DELETE /bots/{id}` |
| Knowledge | `GET /bots/{id}/knowledge`, `POST .../upload`, `.../website`, `.../instruction`, `.../social`, `.../seed-sample`, `.../seed-industry`, `DELETE /knowledge/{id}` |
| Chat | `POST /bots/{id}/chat` (stateless), conversations below |
| Conversations | `POST /conversations`, `GET /conversations/{id}`, `GET /bots/{id}/conversations`, `POST /conversations/{id}/messages`, `POST /conversations/{id}/handoff`, `PATCH /messages/{id}` |
| Real estate | `GET /bots/{id}/properties`, `POST .../properties/seed`, `GET /bots/{id}/leads` |
| Context | `POST /context/greeting`, `GET /context/languages` |
| Analytics | `GET /analytics/overview`, `GET /analytics/bots/{id}`, `GET /reports/{kind}` (`csv` or `json`) |
| Admin | `GET /admin/overview`, `/admin/users`, `/projects`, `/bots`, `/conversations`, `/leads`, `/activity` |

Report kinds: `conversations`, `leads`, `bot_usage`, `intents`, `handoffs`, `unanswered`.

---

## AI services

| Concern | Implementation |
|---|---|
| Embeddings | OpenAI `text-embedding-3-small` (1536d) when a key is configured, otherwise a deterministic local projection. Provider is recorded per chunk. |
| Answers | OpenAI `gpt-4o-mini` (temperature 0.25, max 512 tokens) with a strict grounded prompt; without a key, `_local_grounded_synthesis` quotes retrieved text. |
| Optional Puter | `@heyputer/puter.js` can rephrase a grounded answer in the browser; the server persists the final text. |
| Weather / holidays | Open-Meteo (no key) and a JSON calendar, both optional and failure-tolerant. |
| Prompt injection | Retrieved text is delimited as `<knowledge_base>` and explicitly marked as data, never instructions. |
| Context budget | Retrieved context is capped at 8,000 characters per prompt. |

External services: OpenAI (optional), Open-Meteo (optional), BigDataCloud reverse geocoding
(browser, optional). Nothing else leaves the deployment.

---

## Development commands

```bash
cd backend
pytest tests -q                      # full suite
pytest tests/test_security.py -q     # security regressions
python scripts/demo_real_estate.py   # scripted five-scenario walkthrough
python scripts/diagnose_e2e.py       # upload + crawl + RAG against a live server
python scripts/reembed_chunks.py     # rewrite vectors for the active provider
python scripts/build_industry_packs.py  # refresh the 8 BRIM industry packs

cd frontend
npm run dev
npm run build
```

---

## Testing

The suite runs against the real PostgreSQL database and creates its own users with an
`@example.com` suffix. It covers auth, projects, bots, knowledge ingestion, retrieval, RAG,
conversations, the real-estate flow, multilingual greeting, analytics, reporting, admin
authorisation and security regressions (SSRF, rate limiting, JWT tampering, upload validation,
cross-tenant isolation, prompt-injection guard).

Rate limiting is disabled for the suite in `tests/conftest.py` and exercised explicitly in
`tests/test_security.py`.

---

## Deployment notes

- Put the API behind a TLS-terminating proxy; keep `BACKEND_CORS_ORIGINS` to the exact frontend
  origins.
- Set a unique `SECRET_KEY` and `ENVIRONMENT=production`; startup refuses the default key.
- `RATE_LIMIT_ENABLED` is in-process only. With more than one uvicorn worker, move the limiter to
  Redis before exposing the API publicly.
- `.env` is gitignored. Never commit keys; rotate any key that has been shared.
- The database is the single stateful component — back it up before upgrades.
- Uploaded files are parsed in memory; nothing is written to disk for knowledge sources.
