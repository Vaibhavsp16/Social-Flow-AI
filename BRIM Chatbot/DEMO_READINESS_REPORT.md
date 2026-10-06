# BRIM AI — Phase 1–4 Integration, Debugging & Demo Readiness Report

**Scope:** audit, debug and verify the existing Phase 1–4 implementation. No Phase 5 work, no
architecture rewrite, no mocked behaviour.

**Status: PHASE 1–4 DEMO READY** (see `D. Remaining issues` for one external account caveat).

---

## A. Problems found

### Blocking — these are why the chatbot said "no knowledge base"

1. **The configured PostgreSQL was never actually used.** On SQLAlchemy 2.1 a bare
   `postgresql://` URL resolves to the **`psycopg` (v3)** dialect. `requirements.txt` installs
   `psycopg2-binary`, not `psycopg`, so every connection attempt raised
   `No module named 'psycopg'` and the app silently degraded to SQLite.

2. **The fallback was silent.** `create_db_engine()` logged the failure at `WARNING` and quietly
   returned a SQLite engine. Nothing surfaced to the UI, which is why the symptom appeared as
   "the chatbot has no knowledge" rather than a database error.

3. **The SQLite fallback database had a stale schema.** `embedding_vector` had been added to the
   `knowledge_chunks` model, but `Base.metadata.create_all()` only creates *new* tables — it never
   alters existing ones. The pre-existing `brim_ai.db` had no such column, so:
   - `INSERT INTO knowledge_chunks (..., embedding_vector, ...)` → `table knowledge_chunks has no
     column named embedding_vector`
   - `SELECT ... embedding_vector ...` on retrieval → `no such column:
     knowledge_chunks.embedding_vector`

   **This is the exact point of failure.** Every knowledge upload failed to store chunks, and every
   retrieval query threw — so the bot always fell through to its "I do not have enough information"
   refusal. Both reported problems had this single root cause.

4. **The pgvector extension was never bootstrapped.** No `CREATE EXTENSION vector` existed anywhere.
   The current database happened to have it already, but a fresh PostgreSQL would fail to create the
   `Vector(1536)` column.

5. **The `openai` package was missing from `requirements.txt`.** `LLMService.get_openai_client()`
   therefore always returned `None`, so the LLM generation path never executed — every answer came
   from the deterministic local grounder. Requirement 11 (retrieved context reaching the LLM) was
   not actually being met, even though the code for it existed.

### Correctness and data-integrity defects

6. **Sources reported as `COMPLETED` with zero chunks.** When extraction produced no text, the
   source was still marked `COMPLETED` with `chunks_count = 0`. Two such rows existed in the
   database. Requirement 6 explicitly forbids this.

7. **Retrieval returned an arbitrary chunk at zero similarity.** A "safety net" returned the top
   chunk whenever the threshold filtered everything out — even at a 0.0 score. This let off-topic
   questions be answered from unrelated content and made grounded refusal unreliable.

8. **Retrieval threshold was never applied from the request.** `ChatQueryRequest.threshold`
   defaulted to `0.20` while the service used `0.02`, and the value was never passed through.

9. **The API never returned `extracted_text`.** `KnowledgeSourceResponse` declared only an unused
   `extracted_text_preview`, so the UI's Inspect modal and the instructions preview always displayed
   "No extracted text available."

10. **Two divergent refusal strings** (`GROUNDED_REFUSAL_MESSAGE` vs a second copy in the local
    grounder), producing inconsistent wording.

### Frontend integration defects

11. **The upload `<input type="file">` sat inside the clickable dropzone `<div>` without
    `stopPropagation`**, so `input.click()` bubbled back into the dropzone handler and re-entered
    itself — a recursive click loop on the main "add knowledge" control.

12. **`ChatInterface` created a duplicate conversation on every open.** Its init effect depended on
    `bot`, so it ran again when the bot finished loading, leaving an extra empty conversation each
    time.

13. **`BotOverview` displayed fabricated knowledge data:** hardcoded counts ("Documents (0
    uploaded)", "1 Website linked"), a dead button whose action was
    `'Knowledge ingestion pipeline scheduled for next sprint'`, hardcoded "Conversations: 0", and a
    permanent "No conversations recorded yet" panel even when conversations existed.

14. **Axios timeout was 15 s**, too short for document extraction, chunking and embedding (and for
    website scraping), so slow-but-successful uploads looked like failures.

15. **`tests/test_e2e_demo.py` (left behind, untracked) could never run.** It asserted a response
    shape that does not exist (`msg_data['message']['message']`, `messages[0]['message']`) and
    depended on `requests`, which is not a project dependency. It also required a live server on a
    hardcoded port.

### Environment

16. **No dependencies were installed and there was no virtualenv.** Nothing in the repository had
    actually been executed, which is why these defects were never caught.

17. **The OpenAI account has no credits remaining** (`credit_balance_exhausted` / HTTP 429). This is
    an account/billing limit, not a code defect — but it means LLM answers and real semantic
    embeddings are unavailable until credits are added. See section D.

### Second review round

18. **Mixed embedding spaces could silently corrupt ranking.** Vectors from OpenAI
    (`text-embedding-3-small`) and from the local hashing projection live in unrelated spaces, but
    chunks recorded no provider. The moment a funded API key was added, freshly embedded queries
    would be compared against older locally-embedded chunks, producing meaningless similarities. No
    error would surface — retrieval quality would just quietly degrade.

19. **The local embedding was weaker than it needed to be.** It split on whitespace only, so
    `"Palms?"` and `"Palms"` hashed to different buckets; it carried stop words that dominated the
    signal; and it weighted a repeated word linearly. Measured separability between a relevant and
    an unrelated passage was small, making the relevance threshold hard to tune.

20. **Greetings were answered with a refusal.** `generate_grounded_response()` returned the
    "I do not have enough information" message before any greeting handling ran, so typing "hi" to
    a bot produced a refusal.

21. **The brief's own example question was refused.** *"What information do you have about this
    business?"* shares no specific vocabulary with a document, so retrieval returned nothing and the
    bot refused — despite requirement 9 naming that exact question.

22. **CORS used `allow_origins=["*"]` together with `allow_credentials=True`.** That combination is
    invalid per the CORS spec, and the `BACKEND_CORS_ORIGINS` setting was defined but unused.

23. **`BACKEND_CORS_ORIGINS` could not actually be set from `.env`.** Declared as `List[str]`,
    pydantic-settings requires a JSON array, so a plain comma-separated value crashed startup with
    `SettingsError: error parsing value for field "BACKEND_CORS_ORIGINS"`.

24. **No migration tooling existed.** Schema evolution relied on the `ALTER TABLE` repair added in
    the first round — fine as a safety net, but not a durable history of changes.

25. **No `Dockerfile` for the backend or frontend**, so `docker-compose.yml` could only run
    PostgreSQL, not the application.

26. **The README API table stopped at Phase 2** — every chat and conversation endpoint from
    Phase 4 was undocumented.

---

## B. Fixes implemented

### Backend

| File | Fix |
|---|---|
| `app/core/config.py` | `get_database_url()` now returns `postgresql+**psycopg2**://…`, pinning the driver that is actually installed instead of letting SQLAlchemy 2.1 pick the missing `psycopg` dialect. |
| `app/database/session.py` | Rewritten: explicit connection logging; **loud `ERROR` log** (naming the URL and cause) when falling back to SQLite; `ALLOW_SQLITE_FALLBACK` env switch to fail fast instead; `_ensure_pgvector_extension()` runs `CREATE EXTENSION IF NOT EXISTS vector`; `_sync_schema()` detects model columns missing from existing tables and adds them via `ALTER TABLE`, so a stale database self-repairs instead of breaking every query. |
| `app/schemas/knowledge_source.py` | Exposes `extracted_text` so the UI can show real extracted content and processing detail. |
| `app/services/knowledge_service.py` | New `_finalize_source()` helper: a source is `COMPLETED` **only** when chunks were produced; otherwise `FAILED` with an actionable `error_message`. Applied to upload, website, instructions and sample seeding. |
| `app/services/retrieval_service.py` | Shared `_apply_relevance_gate()` for both the pgvector and in-memory paths; a chunk is only returned when it clears the threshold **or** has a genuinely positive score — otherwise nothing is returned and the assistant refuses. Chunk vector loading now prefers `embedding_vector` and falls back to `embedding_json`. |
| `app/api/chat.py` | Passes the request `threshold` through to retrieval on both the authenticated and public endpoints. |
| `app/schemas/chat.py` | Default threshold aligned to the service value (`0.02`). |
| `app/services/llm_service.py` | Single canonical refusal message (removes the divergent copy); new `_humanize()` strips markdown headings/bold/bullet syntax so grounded answers read as prose rather than a raw chunk dump. |
| `requirements.txt` | Added `openai>=1.30.0` with a comment explaining why it is required. |

### Frontend

| File | Fix |
|---|---|
| `src/components/KnowledgeManager.jsx` | `stopPropagation` on the file input (fixes the recursive click); real `✓ Ready` marker and full chunk count on completed sources; surfaces `error_message` inline in the list **and** in the Inspect modal. |
| `src/pages/ChatInterface.jsx` | Init effect guarded by a ref so exactly one conversation is created per bot; bot welcome message is applied to the placeholder bubble without opening another conversation. |
| `src/pages/BotOverview.jsx` | Real knowledge counts from the API; "Manage sources" now opens the Knowledge tab; real conversation count; Chat History tab renders the actual persisted conversations with working Open links; removed the hardcoded/fake values. |
| `src/services/api.js` | Default timeout raised to 60 s. |
| `src/services/knowledgeService.js` | Upload 180 s, website ingestion 120 s. |

### Tests

| File | Fix |
|---|---|
| `tests/test_e2e_demo.py` | Rewritten as a runnable Phase 1–4 acceptance suite over the real FastAPI app + database, including direct DB assertions that chunk rows and stored embeddings exist. Also runnable as a script that prints an auditable PASS/FAIL report. |

### Second round

| File | Fix |
|---|---|
| `app/services/embedding_service.py` | `get_embedding_with_provider()` reports which provider produced each vector. Rewritten local projection: punctuation-insensitive tokenisation, stop-word removal, sublinear term weighting, word bigrams and character 4-grams, all hash-projected and unit-normalised. Measured separability improved from a weak/noisy signal to **related ≈0.40–0.46 vs unrelated ≈0.005–0.064**. The 429 short-circuit is now time-bounded rather than permanent. |
| `app/models/knowledge_chunk.py` | New `embedding_provider` column (indexed). |
| `app/services/knowledge_service.py` | Records the provider used for every chunk. |
| `app/services/retrieval_service.py` | Filters to chunks whose provider matches the query's, so vectors from different providers are never compared. `NULL` is treated as `local` for pre-existing rows. Added a bot-scoped overview fallback for broad "what do you know" questions, and a greeting-safe path. |
| `app/services/llm_service.py` | New `_greeting_reply()` runs before the knowledge check, so greetings are never refused. Broad exploratory questions are answered from retrieved content instead of refused. |
| `app/core/config.py` | `BACKEND_CORS_ORIGINS` is now a string accepting either comma-separated values or a JSON array, with a `cors_origins` list property. Added `EMBEDDING_PROVIDER`. |
| `app/main.py` | CORS uses the configured explicit origin list instead of `["*"]` with credentials. |
| `migrations/` + `alembic.ini` | Alembic configured against the application settings (no duplicated DB config). Initial revision creates every table, the `vector` extension and `embedding_provider`. Verified to build the full schema from an empty database. |
| `backend/Dockerfile`, `.dockerignore` | Non-root Python 3.12 image for the API. |
| `frontend/Dockerfile`, `nginx.conf`, `.dockerignore` | Multi-stage Node build served by nginx, with SPA history fallback and asset caching. |
| `docker-compose.yml` | Now runs the **full stack**: `postgres` + `backend` + `frontend`, with health-gated startup, service-name networking, and `ALLOW_SQLITE_FALLBACK=false` so the container fails loudly rather than degrading. Removed the obsolete `version` key. |
| `README.md` | API table completed with all chat and conversation endpoints. |
| `RUNBOOK.md` | New: complete start-up, verification, demo-script and troubleshooting guide. |
| `backend/.env` | Rotated `OPENAI_API_KEY`, added `EMBEDDING_PROVIDER` and `BACKEND_CORS_ORIGINS`. |

---

## C. Verification

### Automated test suite

```
python -m pytest tests -q
```

| | Before | After |
|---|---|---|
| Result | **7 passed, 7 failed, 4 errors** | **27 passed, 0 failed** |

The pre-fix failures were all `sqlite3.OperationalError: table knowledge_chunks has no column named
embedding_vector` and the resulting `PendingRollbackError`s.

### Live end-to-end verification (real HTTP, uvicorn on 127.0.0.1:8000, PostgreSQL 16 + pgvector)

```
Authentication:                 PASS
Project creation:               PASS
Bot creation:                   PASS
Knowledge upload (multipart):   PASS
Document processing:            PASS
Chunking:                       PASS  (4 chunks from the Prycoons demo guide)
Embedding generation + storage: PASS  (returned to the UI: 2050 chars extracted)
Vector retrieval:               PASS  (4 source citations)
LLM / grounded generation:      PASS
Unknown-question refusal:       PASS
Bot isolation:                  PASS
Conversation + message persist: PASS
Chat persistence (refresh):     PASS
End-to-end chatbot:             PASS
```

23/23 live checks passed.

Additional specific verifications:

- **pgvector is real:** `knowledge_chunks.embedding_vector` is a `vector` column with
  `vector_dims = 1536`; embeddings are physically present in PostgreSQL (`count(embedding_vector)`
  matches the chunk count).
- **Bot isolation:** a query about another bot's knowledge returns **zero** citations and a refusal;
  each bot answers correctly from its own sources.
- **Refusal:** *"What is the warranty policy on interstellar starships to Pluto?"* →
  *"I do not have enough information in my knowledge base to answer this question accurately…"* with
  no citations.
- **Grounded answer (from the real uploaded document):**
  > Here is what I found in our knowledge base:
  > 1. Sunset Palms Luxury Residencies (Ambli, Ahmedabad)
  > • Configuration: Premium 3 BHK and 4 BHK air-conditioned apartments.
  > • Carpet Area: • 3 BHK: 2,150 sq ft to 2,400 sq ft. …
- **Schema self-repair proved:** starting against the old stale SQLite file now logs
  `Schema drift repaired: added missing column knowledge_chunks.embedding_vector (VECTOR(1536))`
  and retrieval works, instead of failing every query.
- **Frontend:** production build succeeds (`127 modules transformed`, no errors).
- **CORS:** preflight from `http://localhost:5173` returns `200` with
  `access-control-allow-origin: http://localhost:5173` and `authorization` permitted.
- **Greeting:** `"hi"` returns the bot welcome message, never a refusal.
- **Overview question:** *"What information do you have about this business?"* returns real
  content from the uploaded guide instead of refusing.
- **Embedding separability:** related `0.3975` / `0.4646` vs unrelated `0.0051` / `0.0639` —
  a wide, threshold-friendly margin.
- **Alembic:** `alembic upgrade head` against an empty database created all 7 tables, the `vector`
  extension, a `vector(1536)` column and `embedding_provider`; the existing database is stamped at
  head so future migrations apply cleanly.
- **Docker (full stack, verified running):** `docker compose build` produced both images
  (backend 548 MB, frontend 94 MB). `docker compose up -d` brought all three services up —
  `postgres healthy (5433→5432)`, `backend healthy (8000)`, `frontend running (8080)`. The backend
  logged `Database connected: postgresql (postgresql+psycopg2://***@postgres:5432/brim_ai_db)`,
  which is definitive proof it used PostgreSQL and not the SQLite fallback (the compose file also
  sets `ALLOW_SQLITE_FALLBACK=false`, so a container that could not reach PostgreSQL would have
  failed its healthcheck instead of starting). A full flow through the published port —
  signup → project → bot → upload → **COMPLETED / 4 chunks** → chat → **200 with 3 citations** and a
  grounded answer — returned PASS. The nginx SPA history fallback was confirmed (`/dashboard`
  returns 200, not 404). Direct database inspection showed every table populated and
  **222 chunks carrying real 1536-dim vectors**.

### Pre-demo checklist to run yourself

```bash
# 1. Database
cd "BRIM Chatbot" && docker compose up -d && docker compose ps

# 2. Backend  (must be the venv python)
cd backend && .\venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# expect: "Database connected: postgresql (...)"  <- must NOT say "Falling back to local SQLite"

# 3. Frontend
cd frontend && npm run dev     # http://localhost:5173

# 4. Full acceptance suite (optional but recommended before the demo)
cd backend && python -m pytest tests -q
```

Then click through: **Login → Dashboard → Create Bot → (Step 2) Real Estate demo guide →
Create → Open Bot Overview → Knowledge Base (COMPLETED, 4 chunks) → Open Interactive Chat → ask
"What are the 3 BHK prices and amenities at Sunset Palms?"**

---

## D. Remaining issues

1. **Neither API key has credits — this is an external billing blocker, not a code defect.**
   The replacement key was tested and returns the same `429 – credit_balance_exhausted`
   (`"You have no credits remaining. Add credits to continue using the API"`). Until credits are
   added, answers come from the deterministic local grounder and embeddings use the local
   projection. Everything verified above passes in that mode, so the demo works as-is — but if you
   want natural-language answers, add credits at
   https://platform.openai.com/settings/organization/billing/ . The `openai` package is installed
   and the LLM path is correctly wired, so it activates automatically with no code change.
2. **Browser click-through of the UI could not be completed** — the browser bridge timed out at the
   first tool call, and you have confirmed browser access cannot be granted. The UI is verified by a
   clean production build, exact API-contract matching for every call the UI makes, and CORS
   validation. Follow `RUNBOOK.md` → *Demo script* for the manual pass.
3. **Rotate the old API key.** The previous key was superseded in `backend/.env`, but it is still
   valid at OpenAI until revoked. Delete it from the OpenAI dashboard. `.env` is gitignored and was
   never committed, and old migration/verification scripts that contained it have been removed.
4. **`_sync_schema()` remains alongside Alembic.** `create_all()` + schema repair still runs on
   startup so a stale database self-heals; Alembic provides versioned history for deliberate
   changes. Both are intentional, but new schema changes should go through Alembic
   (`alembic revision --autogenerate`).
5. **The pipeline still degrades rather than failing hard on a missing vector database.** If
   pgvector is unavailable the retriever falls back to in-memory cosine scoring over the bot's
   chunks. Correct, but O(n) — fine at this scale, not at high volume.
6. **Local embeddings remain lexical, not semantic.** Materially improved (measured above), but a
   learned model will always handle paraphrase better than a hashing projection.
7. **`ALLOW_SQLITE_FALLBACK` defaults to `true` for local dev.** Docker Compose sets it to `false`
   so containers fail loudly; a bare local run still degrades to SQLite with a loud `ERROR` log.

---

**PHASE 1–4 DEMO READY**

The reported symptoms are resolved at their root: the app now uses PostgreSQL + pgvector, knowledge
uploads genuinely extract → chunk → embed → store, retrieval is scoped per bot, and retrieved
context reaches the answer generator with a verified grounded refusal when nothing relevant exists.
