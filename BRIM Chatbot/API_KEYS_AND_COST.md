# BRIM AI — API Keys & Running Cost

**Prepared:** 9 October 2026
**Scope:** Phases 1–4 as built (authentication, projects, bots, knowledge base, RAG, chat)
**Pricing source:** OpenAI official documentation and pricepertoken.com, verified October 2026

---

## 1. Executive summary

**The platform needs exactly one paid API key: OpenAI.**

Everything else in the stack — the database, the document processing, the website scraping, the
OCR, the authentication — runs on our own infrastructure at **no per-use cost**.

| Item | Answer |
|---|---|
| Paid API keys required | **1** (OpenAI) |
| Cost of the demo | **under $0.05** (5 cents) |
| Cost of a 5,000-conversation pilot | **≈ $1.80 / month** |
| Cost of a 100,000-conversation production load | **≈ $35 / month** |
| Cost if no key is configured | **$0** — the platform degrades to its built-in offline engine |

The dominant cost driver is chat volume, not document storage or database size.

---

## 2. Required API key

| # | Key | Purpose | Where it is used |
|---|---|---|---|
| 1 | **`OPENAI_API_KEY`** | Answer generation **and** semantic search (embeddings) | `llm_service.py`, `embedding_service.py` |

This single key powers two distinct operations:

- **Answer generation** — the model reads the retrieved knowledge and writes the reply.
- **Embeddings** — converts documents and questions into vectors so the right content can be found.

### Models currently configured

| Role | Model | Output size | Set in |
|---|---|---|---|
| Answer generation | `gpt-4o-mini` | max 512 tokens per reply | `llm_service.py:119` |
| Embeddings | `text-embedding-3-small` | 1,536 dimensions | `embedding_service.py:82` |

Both are OpenAI's lowest-cost tier for their function, and both are already wired up. No code
change is needed to start using them — adding credit to the account is sufficient.

### Where to add it

`BRIM Chatbot/backend/.env`

```
OPENAI_API_KEY=<your-openai-key>
```

The file is excluded from version control (`.gitignore`), so the key is never committed.

---

## 3. Configuration secrets (no cost)

These are required but are **self-generated** and free — they are not purchased API keys and should
not be requested from any vendor.

| Setting | Purpose | Who provides it |
|---|---|---|
| `SECRET_KEY` | Signs the login tokens (JWT) | We generate it. Must be replaced with a random value before production. |
| `POSTGRES_PASSWORD` | Database password | We set it. |
| `POSTGRES_USER` / `POSTGRES_DB` / `POSTGRES_SERVER` / `POSTGRES_PORT` | Database connection | Our own PostgreSQL container. |

**Current status:** `SECRET_KEY` still holds the default development placeholder. This must be
rotated to a random value before any public deployment — it is a security item, not a cost item.

---

## 4. Current pricing (October 2026)

### Chat / answer generation — `gpt-4o-mini`

| | Price per 1M tokens |
|---|---|
| Input | **$0.15** |
| Output | **$0.60** |

### Embeddings — `text-embedding-3-small`

| | Price per 1M tokens |
|---|---|
| Input | **$0.02** |

---

## 5. Unit costs (calculated from the actual code)

These figures are derived from the configured settings, not estimates:

- Document chunks are 800 characters with 100 characters of overlap
- Each chat turn retrieves the top **4** chunks
- Conversation history is capped at the last **6** messages
- Replies are capped at **512** tokens

### Per chat message

| Component | Tokens | Cost |
|---|---|---|
| Input (system prompt + 4 retrieved chunks + history + question) | ~1,500 | $0.000225 |
| Output (reply) | ~200 | $0.000120 |
| Question embedding | ~20 | $0.0000004 |
| **Total per message** | | **≈ $0.00035** |

> **≈ 2,900 chat messages per $1**

### Per document ingested

Embedding a document is a **one-time** cost. Re-asking questions does not re-embed the document.

| Document size | Chunks | Tokens | One-time cost |
|---|---|---|---|
| 5-page PDF | ~18 | ~3,600 | $0.00007 |
| 50-page PDF | ~180 | ~36,000 | $0.0007 |
| 100-page PDF | ~360 | ~72,000 | **$0.0014** |

> **≈ 690 hundred-page documents per $1**

---

## 6. Cost scenarios

| Scenario | Bots | Documents | Chat messages / month | Monthly cost |
|---|---|---|---|---|
| **Demo / evaluation** | 1–3 | 5 | 100 | **≈ $0.04** |
| **Pilot** | 10 | 50 | 5,000 | **≈ $1.80** |
| **Production (moderate)** | 50 | 500 | 100,000 | **≈ $35** |
| **Production (high volume)** | 200 | 2,000 | 1,000,000 | **≈ $345** |

Notes:
- Document ingestion is a one-time cost reflected once, not monthly.
- Costs scale almost linearly with chat volume; the number of bots or stored documents is
  negligible by comparison.
- These assume average-length questions and replies. Unusually long conversations cost more
  because more history is sent per turn, though the 6-message cap limits this.

---

## 7. What costs nothing extra

The following components were verified in the codebase as running locally. They require **no API
key, subscription or per-use fee**, and no vendor needs to be contacted for them:

| Capability | How it is implemented |
|---|---|
| PostgreSQL database with vector search (pgvector) | Self-hosted Docker container |
| PDF text extraction | Local (`pypdf`) |
| Word document extraction | Local (`python-docx`) |
| Plain text files | Local |
| Image text extraction (OCR) | Local (`pytesseract`), optional — degrades gracefully if absent |
| Website content extraction | Local (`httpx` + `BeautifulSoup`) |
| Login / authentication | Local JWT, keys we generate |
| Application server, web frontend | Self-hosted Docker |

The only outbound network calls the application makes are to `api.openai.com`.

---

## 8. Optional upgrades (not required)

The platform is functional today at the costs above. If higher quality is later requested, these
are the levers, in order of value:

| Upgrade | Effect | Cost impact | Extra work |
|---|---|---|---|
| **Add credit to the existing key** | Replies become natural, conversational answers instead of extracted passages | None beyond the figures above | None — it starts working immediately |
| **Upgrade the answer model** to a mid-tier model (~$2.00 in / $10.00 out per 1M) | Noticeably better reasoning and phrasing | Chat cost rises roughly **13×** (≈ $450/month at 100k messages) | One-line change, plus an embedding-model change to keep vectors consistent |
| **Upgrade embeddings** to `text-embedding-3-large` ($0.13/1M, 3,072 dimensions) | Better recall on paraphrased questions | Embedding cost rises ~6.5× (still under $5/month at production scale) | **Requires a database migration** — the vector column is fixed at 1,536 dimensions. All documents would need re-embedding. |

**Recommendation:** start with the current models. They are appropriate for the workload, and
because answers are grounded in retrieved documents rather than open-ended generation, a
low-cost model performs well. Upgrade only if answer quality is measured as insufficient.

---

## 9. Important account note

The OpenAI key currently in use **authenticates correctly but the account has no credit balance**.
The API returns:

```
429 — "You have no credits remaining. Add credits to continue using the API."
```

Until credit is added, the platform automatically falls back to its built-in offline engine. This
is fully functional — retrieval, grounding, source citations and refusal on unknown questions all
work — but replies are quoted from documents rather than phrased conversationally.

**Action required:** add credit at https://platform.openai.com/settings/organization/billing/
A small amount (e.g. $10–$20) covers the demo and a substantial pilot period.

To keep spend controlled, a monthly usage limit can be set on the same page.

---

## 10. Summary for approval

| Request | Amount |
|---|---|
| OpenAI API access (one key) | **$0 upfront** — pay-as-you-go |
| Recommended initial credit | **$20** (covers ~57,000 chat messages, or the demo plus months of pilot use) |
| Other API vendors | **None required** |
| Recurring infrastructure cost | None beyond existing hosting |

**Total to proceed: $20 of prepaid credit on a single OpenAI account.**

---

## Update — 23 October 2026

The OpenAI key was removed at the client's request (`OPENAI_API_KEY=` in `backend/.env`).
The system now runs entirely on:
- **Local embeddings** (deterministic hashing projection, 1536 dims) — no per-document cost.
- **Local grounded synthesis** — answers are composed from retrieved text with citations.
- **Puter.js (optional, frontend)** — browser-side LLM used only when `VITE_USE_PUTER=true`.

Current cost of a demo: **zero** API spend. If a hosted LLM is added later, the Phase 1–4 pricing
model in the sections above applies unchanged; the only switch is the provider configuration.
