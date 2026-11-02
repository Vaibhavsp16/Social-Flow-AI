# BRIM AI — Final production-readiness audit

Date: 24 October 2026 · Scope: Phases 1–7 (foundation, knowledge, RAG, conversation, real estate,
context/language, analytics/admin) · Evidence: `pytest` suite, live API runs, browser passes,
Docker stack.

---

## Implemented

**Platform**
- Auth (bcrypt cost 12, JWT HS256, 24 h expiry), projects, bots, knowledge ingestion, RAG chat with
  citations, conversations, real-estate flow, contextual greeting, four languages, analytics,
  CSV reporting, activity log, admin console.
- Ownership enforced on every route by walking Bot → Project → User (verified by tests).

**Security hardening added in this phase**
- SSRF guard (`app/core/net_guard.py`): http/https only, no credentials in URL, blocks loopback,
  private, link-local (169.254.169.254), multicast and reserved addresses; DNS-resolved addresses
  checked; every redirect hop re-validated; rejected with 400 before a source row is created.
- Rate limiting (`app/core/rate_limit.py`): login 10/min, signup 5/5 min, message turns 60/min,
  bot POSTs 30/min, per IP, toggled by `RATE_LIMIT_ENABLED`.
- JWT/secret: `ENVIRONMENT` setting; startup refuses the development `SECRET_KEY` in production,
  warns otherwise. Unique 256-bit secret in `.env`.
- Prompt injection: retrieved text delimited as `<knowledge_base>` and marked as data; context
  capped at 8,000 characters.
- Upload validation retained: extension whitelist, size cap, empty-file rejection.
- No SQL string interpolation, no `verify=False`, no wildcard CORS with credentials, no secrets in
  logs (grep-verified).

**AI**
- Provider-aware embeddings (OpenAI 1536-d or local projection) with `embedding_provider`
  recorded per chunk; retrieval never compares vectors from different providers.
- Grounded answers with a canonical refusal; refusal carries zero citations.
- Provider failure handling: embedding falls back to local, LLM falls back to deterministic
  synthesis, both logged.

**Database**
- PostgreSQL 16 + pgvector; FKs with `ON DELETE CASCADE` across the ownership chain; indexes on
  every FK plus status/timestamp/event columns; Alembic baseline migration; `_sync_schema()` for
  column drift.

---

## Partially implemented

| Item | State |
|---|---|
| Alembic migrations | Baseline revision only. Tables added after it (properties, leads, activity) exist via `create_all`. A fresh database needs `alembic stamp head` before `alembic upgrade head`; see README. |
| Reporting | CSV complete for six report kinds; the report dict is renderer-neutral but no PDF/email renderer exists. |
| Rate limiting | In-process only — correct for one uvicorn worker, not for multiple workers/instances. |
| Image knowledge | Requires an OCR provider. With no key and no Tesseract, images fail with an actionable message. |
| Puter.js | Client module and persistence endpoint exist (`VITE_USE_PUTER=false` by default); no authenticated Puter session has been exercised. |
| Mobile layout | Dashboard and bot overview now pass at 375 px; the chat header's History button still clips by 20 px in the container build (fix is in `ChatInterface.jsx`, needs a rebuild — the Docker Hub call failed during the last build). |
| Weather context | Logic and greetings verified with a mocked provider; a live Open-Meteo call with a granted location was never exercised end to end. |

---

## Known limitations

1. **Local embeddings are lexical.** Paraphrased questions can miss; the 0.12 threshold is tuned to
   the demo corpus.
2. **"Unique users" = distinct session ids.** Conversations carry no authenticated end user.
3. **Resolution is a definition, not a fact.** Currently "led to a lead, or ended without a
   handoff"; confirm with the business.
4. **Analytics scale.** Aggregation runs in Python per conversation. Fine to roughly 10k
   conversations/month; beyond that, move to SQL aggregate views.
5. **Prompt injection is mitigated, not eliminated.** Instructions inside documents cannot change
   behaviour via the system prompt guard, but a determined document can still bias phrasing.
6. **Admin UI coverage.** Overview verified in a browser; Users/Projects/Bots/Conversations/Leads/
   Activity verified through the API and unit tests, not every tab clicked.
7. **Test data in the database.** The suite creates accounts with `@example.com`; the demo account
   itself is clean. Clean before a customer-facing demo if the admin console will be shown.
8. **JWT is stateless.** Logout is client-side only; a token remains valid until expiry.

---

## Required external services

| Service | Required? | Notes |
|---|---|---|
| PostgreSQL 16 + pgvector | Yes | Docker image `pgvector/pgvector:pg16`. |
| OpenAI | Optional | `OPENAI_API_KEY`; enables semantic embeddings and gpt-4o-mini answers. |
| Open-Meteo | Optional | No key; weather context. Failure is ignored. |
| BigDataCloud reverse geocode | Optional | Browser-only; converts granted coordinates to a city label. |
| Puter.js | Optional | Browser LLM; `VITE_USE_PUTER=true`. |

---

## Environment variables

Backend: `ENVIRONMENT`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM`,
`POSTGRES_SERVER/PORT/DB/USER/PASSWORD`, `DATABASE_URL`, `ALLOW_SQLITE_FALLBACK`,
`BACKEND_CORS_ORIGINS`, `OPENAI_API_KEY`, `EMBEDDING_PROVIDER`, `RATE_LIMIT_ENABLED`,
`WEATHER_ENABLED`, `WEATHER_PROVIDER`, `WEATHER_MENTION_PROBABILITY`, `ENGAGEMENT_ENABLED`,
`ENGAGEMENT_PROBABILITY`, `HOLIDAY_FILE`.

Frontend: `VITE_API_BASE_URL`, `VITE_USE_PUTER`.

Full descriptions in `README.md`; a template ships as `backend/.env.example`.

---

## Future improvements

1. Move rate limiting to Redis when running more than one worker.
2. Add PDF/scheduled report renderers over the existing report dict.
3. Authenticate end users (phone/email consent) to make "unique users" a person, not a session.
4. Replace local embeddings with a hosted model and re-embed (script already exists).
5. Add OCR (Tesseract or a vision provider) so image knowledge works without a key.
6. Token revocation list or short-lived access tokens with refresh.
7. SQL aggregate views for analytics at scale.
8. Admin pagination/search in the UI (API already supports limit/offset).
9. Structured logging with request ids and redaction.
10. Backup/restore runbook for the database volume.

---

## Demo checklist

**Before you start**
1. `docker compose up -d --build` from `BRIM Chatbot/`; wait for `backend healthy`.
2. Confirm `http://localhost:8000/health` → `{"status":"healthy"}` and `http://localhost:8080` loads.
3. Log in as `demo@brim.ai / Demo@12345` (business) and `admin@brim.ai / Admin@12345` (admin).
4. Change both passwords if the demo is customer-facing.

**Show, in this order**
1. Dashboard → 3 bots, real counts.
2. Create Bot → Real Estate → the BRIM knowledge pack is pre-selected → create.
3. Chat: "I'm looking to buy a 3 BHK in Ambli under 2 crore" → shortlist card → "can someone call me?"
   → name → phone → email → WhatsApp → confirmation.
4. Ask a document question from the Knowledge tab (e.g. "What services does BRIM offer for real
   estate brands?") → answer with citations.
5. Ask the off-topic question ("warranty on interstellar starships to Pluto") → refusal, zero
   citations. This proves grounding.
6. Language switch (हिन्दी) → "मुझे 3 बीएचके फ्लैट चाहिए अंबली में" → property card in Hindi.
7. Knowledge tab → add a website (`https://brim.co.in/industry/healthcare/`, 3 pages) → "Crawled 3
   pages and indexed N chunks".
8. Analytics → real numbers, intents, export a CSV.
9. Admin console as `admin@brim.ai` → users/leads/activity; then open `/admin` as the business
   account → "Administrator access required".

**Do not show**
- Image upload (no OCR configured).
- Weather small talk unless the location prompt is accepted (unverified live).
- PDF export (not implemented).

**If something fails**
- Backend logs: `docker compose logs -f backend`.
- "No conversation data yet." is correct for a fresh bot — hold one real conversation first.
- 429 responses mean the rate limiter is working; wait a minute.
