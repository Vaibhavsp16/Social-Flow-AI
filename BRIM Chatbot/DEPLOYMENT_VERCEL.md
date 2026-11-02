# Deploying BRIM AI — Vercel frontend + hosted backend

Vercel runs the React frontend. It cannot run this backend: BRIM AI needs a long-lived
FastAPI process, a PostgreSQL database with the `pgvector` extension, and local disk for
uploaded files. Serverless functions give you none of those. So the deployment has three
parts:

```
Vercel (frontend)  ──HTTPS──▶  Render (FastAPI + Docker)  ──▶  Neon (Postgres + pgvector)
```

Do them in this order: database → backend → frontend. The frontend needs the backend URL,
and the backend needs the database URL.

---

## Part 0 — Before you start

You need accounts on [vercel.com](https://vercel.com), [render.com](https://render.com) and
[neon.tech](https://neon.tech). All three have free tiers that are enough for a demo.

Two values you will reuse:

| Name | What it is |
|---|---|
| `API_URL` | Your backend's public URL, e.g. `https://brim-api.onrender.com` |
| `APP_URL` | Your frontend's public URL, e.g. `https://brim-ai.vercel.app` |

Generate a JWT secret now and keep it — the app refuses to start in production with the
default:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Part 1 — Database (Neon)

1. Create a Neon project. Pick the region closest to your Render region (Frankfurt or Oregon
   are common).
2. Open **Connection Details** and copy the connection string. It looks like:

   ```
   postgresql://neondb_owner:PASSWORD@ep-cool-name-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

3. Turn it into the SQLAlchemy form the app expects — change the scheme and keep `sslmode`:

   ```
   postgresql+psycopg2://neondb_owner:PASSWORD@ep-cool-name-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

   The `postgresql+psycopg2://` prefix is required. `config.py` pins it, and a plain
   `postgresql://` string will fail.

4. Enable pgvector. On Neon it is preinstalled; the app runs `CREATE EXTENSION IF NOT EXISTS
   vector` on startup, so you normally do not need to do anything. If you use Supabase
   instead, open **Database → Extensions** and enable `vector` manually before the first
   boot.

Leave this connection string open — you need it in Part 2.

---

## Part 2 — Backend (Render)

### 2.1 Create the web service

1. In Render: **New → Web Service → Build and deploy from a Git repository**.
2. Connect `Vaibhavsp16/Social-Flow-AI`.
3. Settings:

   | Field | Value |
   |---|---|
   | Name | `brim-api` |
   | Root Directory | `BRIM Chatbot/backend` |
   | Runtime | **Docker** |
   | Instance type | Starter (free tier sleeps after inactivity) |

   The repo contains the project in a subfolder, so **Root Directory must be set**. If you
   leave it blank, Render will not find a Dockerfile.

4. Do not deploy yet — add the environment variables first.

### 2.2 Environment variables

Add these under **Environment → Environment Variables**:

| Key | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | the value you generated in Part 0 |
| `DATABASE_URL` | the `postgresql+psycopg2://…?sslmode=require` string |
| `ALLOW_SQLITE_FALLBACK` | `false` |
| `BACKEND_CORS_ORIGINS` | `https://your-app.vercel.app` (comma-separate more if needed) |
| `OPENAI_API_KEY` | your key |
| `EMBEDDING_PROVIDER` | `openai` |
| `RATE_LIMIT_ENABLED` | `true` |

Notes that matter:

- `ENVIRONMENT=production` with the stock `SECRET_KEY` makes the app exit on purpose. That is
  a safety check, not a bug.
- `ALLOW_SQLITE_FALLBACK=false` means a database problem fails loudly instead of silently
  creating a local SQLite file that holds your knowledge base hostage.
- `EMBEDDING_PROVIDER=openai` keeps embeddings consistent. If you leave it on `auto` and the
  key is ever missing, some chunks get local hashing vectors, and a query embedded with OpenAI
  will not match them.
- `BACKEND_CORS_ORIGINS` must be the exact frontend origin, with `https://` and no trailing
  slash. A mismatch shows up in the browser as a CORS error on every request.

### 2.3 Persistent disk for uploads

Uploaded files are written to `uploads/` inside the container, which is wiped on every
deploy. The extracted text and vectors live in Postgres, so **answers keep working**; only the
original file (used by the *Inspect* view) is lost.

To keep the originals, add a **Disk** under the service: mount path `/app/uploads`, 1 GB.
That path matches the app's working directory in the Dockerfile.

### 2.4 Deploy and verify

Click **Create Web Service**. First boot takes a few minutes (image build, then schema
creation). Then check:

```
https://brim-api.onrender.com/health     → {"status":"healthy"}
```

If `/health` is 502 or the logs show `could not connect`, the `DATABASE_URL` is wrong —
usually the missing `+psycopg2` or a dropped `?sslmode=require`.

---

## Part 3 — Frontend (Vercel)

### 3.1 Import the project

1. Vercel → **Add New → Project** → import `Vaibhavsp16/Social-Flow-AI`.
2. **Root Directory**: click *Edit* and select `BRIM Chatbot/frontend`.

   This is the single most common mistake. The repo root is `BRIM_Assessment`; the app is one
   level down. If you skip this, the build fails with "No package.json found".

3. Vercel auto-detects Vite. Confirm:

   | Field | Value |
   |---|---|
   | Framework Preset | Vite |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |
   | Install Command | `npm install` |

   The repository has a `frontend/vercel.json` that declares the same values, plus the
   rewrite described below.

### 3.2 Environment variables

| Key | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://brim-api.onrender.com/api` |
| `VITE_USE_PUTER` | `false` |

Two things to get right:

- The variable is **`VITE_API_BASE_URL`**, not `VITE_API_URL`. `src/services/api.js` reads
  `import.meta.env.VITE_API_BASE_URL`. With a different name the build silently falls back to
  `http://localhost:8000/api` and every request fails in production.
- It must end in **`/api`**. All service files call paths like `/auth/login` relative to this
  base, so leaving off `/api` produces 404s.
- Vite inlines env vars **at build time**. Changing a value later requires a redeploy, not
  just a restart.

### 3.3 Deploy

Click **Deploy**. When it finishes, open the URL. The login page should appear.

### 3.4 Close the CORS loop

Go back to Render → Environment and set:

```
BACKEND_CORS_ORIGINS=https://your-actual-vercel-domain.vercel.app
```

Save; Render redeploys automatically. Without this, the frontend loads but login fails with a
CORS error in the console.

If you attach a custom domain later, add it to the same comma-separated list and redeploy.

---

## Part 4 — Verify the deployment end to end

Run these in order; stop at the first failure.

1. **Backend health**
   `https://brim-api.onrender.com/health` → `{"status":"healthy"}`

2. **API docs reachable**
   `https://brim-api.onrender.com/docs` → Swagger UI. Confirms routing, not just the health
   route.

3. **Login from the browser**
   Open the Vercel URL, sign up a new account (the Neon database starts empty). Watch the
   browser console — no CORS errors.

4. **Create a bot and upload a PDF**
   Dashboard → create project → create bot → Knowledge → upload a brochure. Status should move
   to `COMPLETED` with a chunk count. A `FAILED` status shows the extraction error inline.

5. **Ask a document question**
   Open the chat preview, ask something answerable from the file. You should get an answer
   with citation chips, not a refusal.

6. **Ask something absent**
   Confirm it refuses with zero citations. That proves the relevance gate still works in the
   hosted environment.

---

## Known limits of this setup

- **Free-tier cold starts.** Render's free instance sleeps after ~15 minutes idle. The first
  request afterwards takes 30–60 seconds. For a demo or a VP walkthrough, either open the app
  a few minutes early to wake it, or use a paid instance.
- **Uploads without a disk are ephemeral.** Covered in 2.3. Knowledge answers survive, raw
  files do not.
- **This backend cannot run on Vercel.** If someone asks why the API is not on the same
  platform: serverless functions have no persistent process, no local disk and a request
  timeout that a 25 MB PDF with OCR would exceed.
- **The rate limiter is per-process.** With one instance that is correct. Scaling to multiple
  instances would need a shared store (Redis); the code is structured so that change is local
  to `app/core/rate_limit.py`.
- **Embedding cost.** Each upload embeds every chunk once. Keep `EMBEDDING_PROVIDER` fixed once
  data exists — switching providers later requires re-embedding
  (`backend/scripts/reembed_chunks.py`).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Vercel build: "No package.json found" | Root Directory not set | Set it to `BRIM Chatbot/frontend` |
| Login fails, console shows CORS | Origin not allowlisted | Add exact Vercel URL to `BACKEND_CORS_ORIGINS`, redeploy |
| Every request hits `localhost:8000` | Env var misnamed or missing at build time | Use `VITE_API_BASE_URL`, then redeploy |
| 404 on `/auth/login` | `VITE_API_BASE_URL` missing the `/api` suffix | Correct the value, redeploy |
| Backend exits on boot, logs mention `SECRET_KEY` | Production with the default secret | Set a real `SECRET_KEY` |
| Backend 502, logs show connection refused | Bad `DATABASE_URL` | Ensure `postgresql+psycopg2://` and `?sslmode=require` |
| `type "vector" does not exist` | pgvector not enabled | Neon: usually automatic; Supabase: enable the extension |
| Deep link like `/preview/1380` 404s on refresh | Missing SPA rewrite | `frontend/vercel.json` handles it — confirm it is committed |
| Knowledge answers refuse in production but work locally | Chunks embedded with a different provider | Set `EMBEDDING_PROVIDER=openai`, re-upload, or run `reembed_chunks.py` |

---

## Redeploying after a code change

```bash
git add -A
git commit -m "your message"
git push origin main
```

Vercel and Render both watch `main` and rebuild automatically. There is no separate deploy
step.
