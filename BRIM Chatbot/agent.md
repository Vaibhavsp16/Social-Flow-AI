# BRIM AI — Complete Project Handoff

> **Purpose.** Everything an agent or developer needs to pick this project up cold.
> **Written:** 8 November 2026. **Supersedes** every earlier handoff, including the 17 October
> version that declared Phase 5 out of scope — Phases 5, 6 and 7 are now implemented, verified
> and deployed.
>
> Read sections 1–3 before touching anything. Section 12 lists the mistakes already made; do not
> repeat them.

---

## 1. What this is

**BRIM AI** is an industry-centric chatbot builder. A user signs up, creates a project, creates a
chatbot inside it, attaches knowledge (documents, websites, social links, images, AutoCAD files),
then chats with the bot. Answers are grounded in attached knowledge and cite their sources.

| Phase | Scope | State |
|---|---|---|
| 1 | Auth, projects, bots, dashboard | Done |
| 2 | Knowledge management: upload, extraction, chunking, status | Done, extended |
| 3 | Embeddings, vector storage, retrieval | Done, now **hybrid** |
| 4 | Conversations, messages, grounding, persistence | Done |
| 5 | Real-estate workflow: intent → requirements → shortlist → lead | Done |
| 6 | Contextual greeting, multilingual (en/hi/gu/mr) | Done |
| 7 | Analytics, reporting (CSV/PDF), admin, activity log | Done |
| — | Deployment (Vercel + Render + Neon) | Done |

Demo accounts exist for every phase. See section 4.

---

## 2. Live deployment

| Piece | URL / value |
|---|---|
| Frontend | https://social-flow-ai-frontend.vercel.app |
| Backend API | https://brim-api-dxgh.onrender.com |
| Health | https://brim-api-dxgh.onrender.com/health |
| API docs | https://brim-api-dxgh.onrender.com/docs |
| Repo | https://github.com/Vaibhavsp16/Social-Flow-AI (**public**) |
| Branch | `main` |
| Database | Neon Postgres + `pgvector` |

Hosting shape:

```
Vercel (React/Vite)  →  Render (FastAPI, Docker)  →  Neon (Postgres + pgvector)
```

**Vercel settings** (already applied): Root Directory `BRIM Chatbot/frontend`, framework Vite,
build `npm run build`, output `dist`, `frontend/vercel.json` provides the SPA rewrite so
`/preview/1380` survives a refresh.

**Vercel env vars:**

```
VITE_API_BASE_URL = https://brim-api-dxgh.onrender.com/api     # must end in /api
VITE_USE_PUTER    = false
```

Vite inlines env vars at **build time**. Changing `VITE_API_BASE_URL` needs a redeploy, not a
restart. A build without it silently embeds `http://localhost:8000/api` — the site loads, every call
fails, and the cause is invisible in the UI.

**Render settings:** `render.yaml` at the repo root declares Docker runtime, rootDir
`BRIM Chatbot/backend`, health check `/health`, and seven env vars. Three are `sync: false` and
prompted at setup: `DATABASE_URL`, `OPENAI_API_KEY`, `BACKEND_CORS_ORIGINS`.

**Render env vars in use:**

```
ENVIRONMENT=production
SECRET_KEY=<generated>            # app refuses to boot with the default when ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST/DB?sslmode=require
BACKEND_CORS_ORIGINS=https://social-flow-ai-frontend.vercel.app,http://localhost:5173,http://127.0.0.1:5173
OPENAI_API_KEY=<key>
EMBEDDING_PROVIDER=openai
ALLOW_SQLITE_FALLBACK=false
RATE_LIMIT_ENABLED=true
```

`BACKEND_CORS_ORIGINS` is tested and confirmed. Starlette returns **400 with no
`Access-Control-Allow-Origin`** for an unlisted origin — that is what a CORS misconfiguration looks
like from curl, and it presents in the browser as "page loads, login fails".

Optional, for automatic social harvesting (see section 9):

```
META_ACCESS_TOKEN / INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_USER_ID
FACEBOOK_PAGE_ID
SOCIAL_POST_LIMIT=12
```

---

## 3. Local development

```
UI (Docker)       http://localhost:8080
UI (dev server)   http://localhost:5173
API               http://localhost:8000/api
API docs          http://localhost:8000/docs
Postgres (host)   127.0.0.1:5433   (container: postgres:5432)
```

**Start (full stack):**

```powershell
cd "C:\Users\Vaibhav.S.P\Downloads\BRIM_Assessment\BRIM Chatbot"
docker compose up -d
```

**After code changes** — `up -d` alone reuses the old image and is the most common source of
"I fixed it but nothing changed":

```powershell
docker compose up -d --build backend
docker compose up -d --build frontend
```

**Stop:**

```powershell
docker compose stop        # keep containers, resume with `start`
docker compose down        # remove containers, KEEP the postgres_data volume
docker compose down -v     # DESTROYS the database volume
```

**Dev mode with hot reload:**

```powershell
docker compose up -d postgres
cd backend; .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
cd frontend; npm run dev
```

**Tests:**

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -q      # 95 pass; ~3 min
```

Postgres must be up. `ALLOW_SQLITE_FALLBACK=false` means the backend fails loudly instead of
quietly switching to SQLite — that is deliberate.

---

## 4. Accounts and identifiers

Local database (seeded):

```
demo@brim.ai   / Demo@12345    BUSINESS  — projects, bots, bot 1380
admin@brim.ai  / Admin@12345   ADMIN     — Analytics, Admin, activity log
```

Deployed database (created by the deployment smoke test):

```
deploy.check.542221e6@brimtest.com / Deploy@2026    BUSINESS
project "Deploy Project" (Real Estate), bot #2 "Deploy Bot"
```

The two databases are **completely separate**. Local demo accounts do not exist on the deployed
instance, and bot 1380 with its documents exists only locally. Anything needed for a hosted demo
must be created or uploaded on the hosted instance.

New signups get role `BUSINESS`, which is 403 on `/api/admin/*`. To create an admin on the
deployed database:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://...?sslmode=require"
.\venv\Scripts\python.exe scripts\seed_admin.py you@email.com "Password"
```

Unset `DATABASE_URL` afterwards or local runs will point at Neon.

Known bot ids (local): `1380` Signature Brochure Assistant (the main test bot), `310` FMCG,
`283` Jewellery, `282` Property Advisor (custom welcome message), `1582` BRIM Industry Assistant.

---

## 5. Architecture

```
BRIM_Assessment/                       <- git repo root
  docker-compose.yml                   <- postgres + backend + frontend
  render.yaml                          <- Render blueprint for the API
  DEPLOYMENT_VERCEL.md                 <- step-by-step deployment guide
  agent.md                             <- this file
  BRIM Chatbot/
    backend/
      app/
        api/                           auth, projects, bots, knowledge, chat, analytics, admin,
                                       properties, context
        core/                          config, constants, messages (i18n catalogue), net_guard,
                                       rate_limit, industry_packs
        database/session.py            engine, pgvector extension, schema drift repair
        models/                        user, project, bot, conversation, knowledge_source,
                                       knowledge_chunk, property, lead, activity
        schemas/                       pydantic request/response models
        services/                      the substance — see below
      scripts/                         verification and seeding tools
      tests/                           95 tests
    frontend/
      src/pages/                       Dashboard, Projects, Bots, BotOverview, Knowledge,
                                       ChatInterface, Analytics, Admin
      src/components/                  KnowledgeManager, UI kit
      src/services/                    api.js (axios + token), knowledgeService, chatbotService
      vercel.json
```

### Services that matter

| File | Responsibility |
|---|---|
| `document_processor.py` | Every extractor. Crawling, PDF, DOCX, images, DXF/DWG, chunking, text repair. |
| `knowledge_service.py` | Upload pipeline, source lifecycle, website + social ingestion, industry packs. |
| `embedding_service.py` | OpenAI or local hashing embeddings; records `embedding_provider` per chunk. |
| `retrieval_service.py` | **Hybrid** retrieval, relevance gate, lexical fallback, citation shaping. |
| `llm_service.py` | System prompt, grounding, refusal, markdown stripping, local synthesis. |
| `conversation_service.py` | Message pipeline, greeting creation, flow dispatch, citations, persistence. |
| `real_estate_flow.py` | Deterministic slot filling, shortlist, lead capture, handoff. |
| `property_service.py` | Property search, ranking, shortlist prose. |
| `greeting_service.py` | `build()` for the chat, `preview()` for the editor. Must stay identical. |
| `social_service.py` | Social profiles/posts: Graph API, YouTube, pasted captions, hashtags. |
| `weather_service.py`, `holiday_service.py`, `language_service.py` | Context signals. |
| `analytics_service.py`, `reporting_service.py` | Metrics from SQL; CSV and PDF renderers. |

---

## 6. Data model invariants

Do not violate these without reading the code that depends on them.

- **`DATABASE_URL` must be `postgresql+psycopg2://`.** A plain `postgresql://` fails with
  SQLAlchemy 2.x.
- **`create_all()` cannot ALTER.** `init_db()` runs `_ensure_pgvector_extension()` then
  `_sync_schema()`, which repairs drift idempotently on every boot. `knowledge_chunks.page_number`
  is `VARCHAR(500)`; it was 50, and multi-page crawl URLs overflowed it with
  `StringDataTruncation`.
- **Vector column is fixed at 1536 dimensions** (both providers). Never compare an OpenAI vector
  with a local hashing vector — `embedding_provider` filters every retrieval. `NULL` means local.
- **Provider must be consistent per chunk and per query.** When a transient OpenAI failure leaves
  the two mismatched, retrieval falls back to `_lexical_search` keyed on the bot's stored providers.
- **Activity log is append-only** and joins the caller's transaction (`add` + `flush`) so an event
  exists only if the action committed.
- **Coordinates are never stored or sent.** Only a city/region label leaves the browser.
- **Refusal is one canonical sentence per language** (`GROUNDED_REFUSAL_MESSAGE`), detected
  case-insensitively via `messages.is_refusal`, and citations are stripped when it fires.

---

## 7. Knowledge ingestion — every supported shape

`DocumentProcessor` is the single entry point. Allowed extensions live in `core/constants.py`:
`.pdf .doc .docx .txt .dxf .dwg .png .jpg .jpeg .webp`, 25 MB cap.

**PDF — per page, not per file.** For each page: extract the text layer; if it yields fewer than
`PAGE_TEXT_MIN_CHARS` (400) characters, render that page at `OCR_RENDER_DPI` (200) and transcribe
it with the vision model (`gpt-4o-mini`, `detail: high`), capped at `MAX_OCR_PAGES` (20) calls.
Every page is prefixed `Page N` so citations name a page a reader can open. This is what makes
plan-layout PDFs and mixed documents work — the earlier whole-file decision lost every drawing page.

`_merge_page_text` drops transcript lines whose words already appear in the text layer
(≥60% overlap), because a drawing page repeats its title block and OCR spacing differs.

**Word documents.** Body order is preserved by walking `document.element.body`, so tables stay
next to their headings instead of being appended at the end. Headers and footers are included.
Embedded images above `DOCX_IMAGE_MIN_PIXELS` (120k) are OCR'd — byte size is a poor test because
a mostly-white PNG compresses to a few KB.

**AutoCAD.** `.dxf` via `ezdxf`: TEXT, MTEXT, ATTRIB, DIMENSION, layers and block names.
`.dwg` is a closed binary: `_convert_dwg_to_dxf` uses an ODA File Converter or `dwg2dxf` when one
is installed; otherwise UTF-16LE **and** ASCII printable runs are salvaged (modern DWG stores text
as UTF-16, so ASCII-only salvage found nothing).

**Website crawl.** Bounded same-site crawl (`max_pages`, ceiling 12) with `/cdn-cgi/` blocked,
chrome removed by class token and ARIA role, and noise lines filtered.

**Text repair.** `clean_text` calls `_repair_line_wraps`, which detects the "one word per line"
pattern produced by printing a web page to PDF and rejoins it. Without this, a website-export PDF
produced one-word lines and retrieval could not match anything.

**Re-uploading the same file replaces it** (same bot + filename + size), deleting *all* previous
copies. It used to delete only the first, so duplicates accumulated and every citation appeared
twice.

---

## 8. Retrieval and answering

**Hybrid retrieval** in `retrieval_service.search_relevant_chunks`:

1. Vector search (`_search_vector`) over the bot's chunks, provider-filtered.
2. IDF-weighted lexical search (`_lexical_search`) over the same chunks.
3. Merge by `chunk.id`, keeping the higher score; sort; `top_k=8`.

Why hybrid: embeddings are strong on paraphrase and weak on entity names, numbers and project
names; keyword matching is the reverse. The developer question ("Who is the developer and when was
the company started?") returned a refusal before this change and answers "SN Built Pvt. Ltd., 1996"
after it.

Parameters:

```
DEFAULT_THRESHOLD_OPENAI = 0.18     measured relevant 0.31–0.75, unrelated <= 0.11
DEFAULT_THRESHOLD_LOCAL  = 0.12     local hashing scores cluster near 0.02
MAX_CONTEXT_CHARS        = 8000     retrieved text wrapped in <knowledge_base>
MAX_DISPLAY_CITATIONS    = 4        one per document, strongest passage
MIN_DISPLAY_SCORE        = 0.20
```

**Lowering the threshold is not the fix for missed answers** — it attaches unrelated documents and
produces confident wrong answers. Add lexical coverage or improve extraction instead.

Lexical tokenisation is unicode-aware (`_TOKENS`) so Hindi and Gujarati queries match at all; it
used to tokenise with `[a-z0-9]`, which returned nothing for non-Latin scripts.

**Citations collapse to one per document.** Two passages from one brochure rendered as two pills
with the same name at different percentages and read as a duplication bug.

**Prompt rules** (`llm_service.build_system_prompt`) that carry real weight: answer the question
asked; combine sources; quote names, numbers and dates exactly; reply warmly to small talk without
launching the requirement script; quote real captions and never invent a post or hashtag.
`strip_markdown` unwraps `[label](url)` to `label (url)` because the chat bubble is plain text.

**Answers drift when the flow hijacks the message.** `RealEstateFlow.should_handle` must only claim
property language (buy/rent/BHK/crore/lakh/available/options) or a reply to a question it already
asked. Every conversation starts as `intent=browsing`, so gating on intent alone made even "Hi"
open a shortlist. A bare "budget" is not property intent ("which channel gets the largest budget
share" is a document question) — it requires a number or a property word.

---

## 9. Social media

Posts are **first-class records**, not one profile blob. Each post keeps its own caption, hashtags,
date and permalink, and a frequency-ranked hashtag summary is generated across posts.

Three ingestion paths, tried in this order:

1. **Meta Graph API** — when `META_ACCESS_TOKEN` is set. Instagram `/{user}/media` with
   `caption,permalink,timestamp,like_count,comments_count`; Facebook `/{page}/posts`. Requires a
   Business or Creator account **linked to a Facebook Page**.
2. **YouTube** — recent uploads with descriptions and hashtags. The public RSS feed
   (`feeds/videos.xml`) returns **404 on this network**, so the fallback reads the channel page for
   video ids and each watch page's `shortDescription`. Channel id must come from the canonical link
   or `externalId`; the first `"channelId"` in the HTML often belongs to a recommended channel.
3. **Pasted captions** — one or more, separated by a line of `---`. Each becomes its own post.
   This is the only path that works for Instagram today.

**Hard limitation, verified — do not re-litigate it:** Instagram and TikTok captions cannot be
scraped anonymously. Tested and closed: mobile profile JSON API (401), public profile endpoint
(401), post embed endpoint (no caption), three third-party mirrors (403/Cloudflare). A token is the
only automatic route. For a demo, paste captions.

Profile metadata still works: followers, posts, and the **bio**, which lives in the plain
`description` tag while `og:description` carries the follower line — take the richer of the two.
The profile's own handle must be excluded from "accounts tagged".

Verified end to end on bot 1380: handle, hashtags, post themes and verbatim sample captions all
answer with sources.

---

## 10. Greeting, language and conversation flow

`GreetingService.build()` produces the chat's first message; `preview()` produces the same text for
the bot editor, and the API exposes it as `greeting_preview`. **They must stay identical** — the
editor previously showed `welcome_message` while the chat served a generated greeting, so the two
pages disagreed on every bot using the platform default. Verified 8/8 bots.

Shape: one welcome line plus one open question. No time-of-day, holiday, weather or engagement
question in the opening — those are resolved into the `context` payload and shown as chips.

A custom `welcome_message` is used verbatim, but the open question is still appended. The platform
default (`"Hi! How can I help you today?"`) is deliberately not treated as custom; honouring it
would greet and then ask the same question twice.

Languages: `en`, `hi`, `gu`, `mr` with script detection (Devanagari split by function words),
romanised normalisation (`mujhe chahiye`, `mane joiye`) and localised slot tokens (अंबली, બોપલ,
करोड़). Greeting parity is checked in English only; other languages go through the same functions.

---

## 11. Security posture

Implemented: JWT HS256 with bcrypt cost 12; `ENVIRONMENT=production` refuses the default
`SECRET_KEY`; SSRF guard (`net_guard.assert_safe_url`) blocking loopback, private, link-local and
`169.254.169.254`, re-validated on every redirect hop; in-process per-IP rate limiting (login
10/min, signup 5/5min, messages 60/min); ownership checks on every bot/source route; admin gate
returning 403; lead phone/email masked in admin responses; retrieved text wrapped in
`<knowledge_base>` with an 8,000-character budget as a prompt-injection barrier.

**Known weakness:** the rate limiter is per-process. Behind more than one Render instance it
multiplies. Call sites are funnelled so a Redis swap is local.

**Open security item — see section 13.** A live Neon password was committed and pushed to a public
repository. Rotation is the fix; git history still contains it.

---

## 12. Mistakes already made — do not repeat

1. **`.env.example` contained a real Neon connection string.** It is a tracked file. Never put a
   working credential in a tracked file; placeholders only.
2. **`docker compose up -d` without `--build`** served a stale image three separate times and made
   correct fixes look broken.
3. **`create_all()` was assumed to migrate.** It does not ALTER; a widening column needed an
   idempotent startup statement.
4. **The relevance gate returned the best chunk at score 0** — the forbidden "always return
   something". It is a pure filter now.
5. **Lowering the threshold** to fix a miss attached a policy document to an unrelated question.
6. **Gating the real-estate flow on intent** rather than on explicit property language made "Hi"
   open a shortlist.
7. **Deduplicating with `.first()`** left older duplicates in place; delete every match.
8. **`Select-Object -First N` on a pipeline** terminates the producer early — it can make a long
   verification look truncated.
9. **PowerShell rejects multi-path `Remove-Item`** in this sandbox. Move files into one folder, then
   delete that folder by a single literal path.
10. **Do not build fixtures and call it verification of a user's file.** When a referenced local file
    is missing from disk, say so and ask for an upload. Fixtures reproducing a document's *shape*
    are acceptable for pipeline tests only if clearly labelled as such.

---

## 13. Open items

| Item | Why it matters | Action |
|---|---|---|
| **Neon password was leaked** in commit `6cb8d4b`, repo is public | Full read/write to production DB | Rotate in Neon → update `DATABASE_URL` on Render → confirm `/health`. Optionally purge history (force-push) with owner approval. |
| Graph API token | Automatic Instagram captions | Optional. Needs Business account + linked FB Page. |
| Real customer documents never run | `prycoons (1).pdf`, `Signature Brochure_1 (1).pdf`, the positioning `.docx` were never present on disk | Upload to the hosted instance and ask the questions in section 14. |
| Uploads are ephemeral on Render free tier | No persistent disk; original files vanish on redeploy | Extracted text and vectors live in Postgres, so **answers survive**. Only the *Inspect* original-file view breaks. Add a 1 GB disk at `/app/uploads` if that matters. |
| Deployed UI not clicked through by an agent | API verified 15/15; browser verified locally | Browser pass on the deployed site when convenient. |

---

## 14. Verification and demo

**Verification scripts** (`backend/scripts/`):

| Script | Purpose |
|---|---|
| `check_deployment.py` | 15-step smoke test against a deployed instance: health, signup, login, project, bot, OCR upload, DOCX upload, greeting, grounded answer, refusal, analytics, CORS. |
| `verify_documents_api.py` | Uploads every document shape and asserts the expected fact appears in the answer. |
| `verify_social_posts.py` | Handle, hashtags, post themes and sample captions. |
| `verify_greeting_parity.py` | Bot-detail greeting must equal the chat's first message, across all bots. |
| `check_citations.py` | One citation per source, capped. |
| `make_test_fixtures.py` | Regenerates `_fixtures/` (gitignored): website-export PDF, image-only brochure, mixed plan PDF, DOCX with an embedded diagram. |
| `seed_admin.py`, `seed_demo_account.py`, `reembed_chunks.py` | Data operations. |

**Demo script that scores well** — knowledge first, workflow second:

1. Opening message: one welcome line, one question.
2. "Who is the developer and when was the company started?" → document answer + 1 citation.
3. "What carpet area is given in the area statement?" → exact figure.
4. "Warranty on interstellar starships to Pluto?" → refusal, **zero** citations.
5. Social: handle → hashtags → post themes → sample captions.
6. "I want to buy a 3 BHK in Ambli under 2 crore" → shortlist → "can someone call me?" → lead.

Notes for presenting: the free Render instance sleeps after ~15 minutes idle (first request takes
30–60s), so open the app a few minutes early. Ask for "the area statement" rather than "the carpet
area of the units" — the plan drawing legitimately contains unit-wise areas too, and either answer
is correct.

---

## 15. Test state

```
pytest tests -q          → 95 passed (~3 min)
```

Coverage: `test_api`, `test_knowledge`, `test_retrieval_rag`, `test_e2e_demo`,
`test_industry_packs`, `test_real_estate_flow`, `test_context_language`, `test_analytics_admin`,
`test_security`.

Live checks, last recorded 3 November 2026: deployment smoke test 15/15; documents 13/13; social 4/4;
greeting parity 8/8.

---

## 16. Configuration reference

`backend/.env` (local, never committed):

```
DATABASE_URL / POSTGRES_HOST=localhost POSTGRES_PORT=5433
SECRET_KEY=<long random>
OPENAI_API_KEY=<key>
EMBEDDING_PROVIDER=openai|local
ALLOW_SQLITE_FALLBACK=false
ENVIRONMENT=development|production
BACKEND_CORS_ORIGINS=<comma separated>
RATE_LIMIT_ENABLED=true
ENGAGEMENT_ENABLED=true
HOLIDAY_FILE=demo_documents/holidays.json
```

Costs: embeddings and vision OCR are the only per-use spend. OCR is approximately 1,700 tokens per
page at 200 DPI, so a 7-page brochure is negligible; `MAX_OCR_PAGES=20` caps a large catalogue.

---

## 17. How to continue this work

1. `docker compose up -d --build` and wait for `/health`.
2. `pytest tests -q` — establish the baseline before changing anything.
3. Read the service you are touching; each has a comment explaining the failure it prevents. Those
   comments are load-bearing, not decoration.
4. Change one thing, verify with the specific script in section 14, then the full suite.
5. Rebuild the affected image before claiming anything works. `up -d` alone does nothing.
6. Report what was actually verified, with the output. If something could not be tested — a missing
   file, a blocked platform, an unrotated credential — say so explicitly rather than describing it
   as done.
