# DataSleuth — AI-Powered Dataset Exploration and Data Quality Auditor

DataSleuth uploads CSV or Excel datasets, profiles them, audits data quality, and answers natural-language
questions. **Every number comes from Python.** The chat LLM only explains computed results. Supporting documents
(data dictionaries, business rules) are vectorized with **Google Gemini Embeddings (`gemini-embedding-2`)**, stored in
**ChromaDB**, and retrieved with dataset-scoped RAG. Explanations and conversational answers are synthesized with
**Groq (`openai/gpt-oss-120b`)**.

## Project structure

```
datasleuth/
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI app, lifespan DB init, CORS, /health, request logging
│   │   ├── config.py                  env-based settings (Groq, Gemini, ChromaDB, secrets)
│   │   ├── api/                       datasets.py · analysis.py (chat) · reports.py
│   │   ├── services/
│   │   │   ├── dataset_service.py     validation, raw + normalised loading, SQLite metadata
│   │   │   ├── profiling_service.py   numeric / categorical / date profiles
│   │   │   ├── quality_service.py     deterministic quality checks (never mutates input)
│   │   │   ├── rules_service.py       business-rule parser + evaluator (unsupported → reported)
│   │   │   ├── rag_service.py         extraction, chunking, ChromaDB storage & dataset-scoped retrieval
│   │   │   └── llm_client.py          Groq chat + Google Gemini embeddings (httpx, retries, errors)
│   │   ├── tools/data_tools.py        controlled analytical tools (Pydantic-validated)
│   │   ├── agents/                    LangGraph: state.py · nodes.py · graph.py
│   │   ├── models/schemas.py · database/db.py · utils/ (file checks, API key, rate limit)
│   │   └── requirements.txt · .env.example · render.yaml · Procfile
│   ├── sample_data/                   transactions.csv · business_rules.md · data_dictionary.md
│   └── tests/                         82 tests (mocked integration, correctness, RAG & security)
└── frontend/
    ├── src/pages/                     Dashboard · DatasetOverview · DataQuality · Ask · Documentation · Reports
    ├── src/components/                Layout · ui · ChartView (Recharts)
    ├── src/api.ts · types.ts · hooks.ts · App.tsx · main.tsx · index.css
    ├── e2e/browser-test.mjs           browser test (puppeteer-core driving Chrome)
    └── vercel.json · vite.config.ts · tailwind.config.js · package.json
```

## How answers are produced

```
question ─▶ classify (keywords) ─▶ validate dataset
                                      │
   ┌──────────────────────────────────┼───────────────────────────┐
documentation                  business_rules               quality / aggregation / general
   │                                  │                            │
retrieve docs              retrieve + rule engine        plan tools (deterministic)
(Gemini embeddings)                   │                            │
   │                                  │                  execute tools (pandas, raw + normalised)
   └──▶ verify ◀──────────────────────┘                            │
          │                                              verify ◀──┘   (retry ≤ 1, then respond)
          │                                                │
          ▼                                                ▼
      make chart (from computed rows only) ◀───────────────┘
          │
      respond (Groq explains computed results, or deterministic summary)
          │
      check_grounding (every figure in the text must appear in tool output, question or retrieved text;
                       otherwise the computed summary replaces it)
```

- **Missing vs invalid vs duplicate vs outlier are reported separately.** Missing = blank cells in the file.
  Invalid = text that cannot be parsed (e.g. `"not available"`, `2026-02-30`), reported with transaction IDs.
  Duplicates are checked on the ID column (`transaction_id`) and as exact rows. Outliers are IQR fences and are
  marked "needs investigation", not "error".
- **Tools cannot run arbitrary code.** Tool names come from a fixed registry; arguments are validated with Pydantic and
  checked against real column names; aggregation is limited to `sum/mean/min/max/count/median`.
- **Original files are never modified.** Quality checks read the original text frame (for blanks and invalid values)
  and the normalised frame (for statistics).
- **Honest refusals.** Questions outside the supported analyses get an explicit "outside the analyses DataSleuth
  supports" response, with no tool run and `verified: false`.

## Quick start (local)

### Backend (Python 3.11)

Python 3.13 has no wheels for pinned dependencies, which forces a source build. Use Python 3.11 or 3.12.

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install --only-binary=:all: -r requirements.txt
cp .env.example .env
```

Configure your keys in `backend/.env`:
- `DATASLEUTH_API_KEY`: Generate a random key via `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `LLM_API_KEY`: Your Groq API key
- `EMBEDDING_API_KEY`: Your Google Gemini API key

Start the backend:
```bash
uvicorn app.main:app --reload --port 8000
pytest -q                     # 82 tests, no paid API calls needed
```

### Frontend (Node 18+)

```bash
cd frontend
npm ci
npm run dev                   # http://localhost:5173, proxies /api and /health to :8000
npm run build                 # production build in dist/
```

Open `http://localhost:5173`, paste your `DATASLEUTH_API_KEY` into the sidebar, and click **Save key**. It is stored in that browser's `localStorage` only.

---

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `DATASLEUTH_API_KEY` | Required. Sent as `X-API-Key`. The placeholder `change-me` disables the API (503). | — |
| `LLM_API_KEY` | Groq API Key. Without a key, answers use deterministic summaries. | — |
| `LLM_BASE_URL` | Groq OpenAI-compatible endpoint. | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | Groq Chat Model. | `openai/gpt-oss-120b` |
| `EMBEDDING_API_KEY` | Google Gemini API Key. Without a key, document upload returns 503. | — |
| `EMBEDDING_BASE_URL` | Google Gemini REST endpoint. | `https://generativelanguage.googleapis.com/v1beta` |
| `EMBEDDING_MODEL` | Gemini embedding model. | `gemini-embedding-2` |
| `EMBEDDING_DIMENSIONS` | Optional Matryoshka output dimension downscaling (e.g. 768 or 1536). | `None` (full 3,072 dims) |
| `CORS_ORIGINS` | Comma-separated allowed origins. | `http://localhost:5173,http://localhost:3000` |
| `DATA_DIR` | Storage root for uploads, SQLite database and ChromaDB vectors. | `./data` |
| `MAX_UPLOAD_MB` | Maximum dataset upload size. | `20` |
| `MAX_DOCUMENT_MB` | Maximum markdown/PDF document size. | `10` |
| `RATE_LIMIT_PER_MINUTE` | Requests per minute per client (in-memory, per process). | `60` |
| `TRUST_PROXY_HEADERS` | Use `X-Forwarded-For` for rate limiting. Enable only behind a proxy (e.g. Render). | `false` |
| `LOG_LEVEL` | Logging level. | `INFO` |

---

## API Reference

All `/api/*` routes require `X-API-Key` passed as an HTTP header. `/health` is open.

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Health check & liveness endpoint |
| POST | `/api/datasets/upload` | CSV or XLSX upload → 201; 422 for unsupported or malformed files |
| GET | `/api/datasets` | List all uploaded datasets |
| GET | `/api/datasets/{id}` | Dataset metadata (row count, columns, file type) |
| GET | `/api/datasets/{id}/profile` | Counts, missing cells, duplicates, per-column descriptive statistics |
| GET | `/api/datasets/{id}/preview?page&page_size` | Paginated rows (max 100 per page) |
| GET | `/api/datasets/{id}/quality` | Automated data quality audit findings |
| POST | `/api/datasets/{id}/documents` | Index TXT, MD, or PDF supporting documentation with Gemini & ChromaDB |
| GET | `/api/datasets/{id}/documents` | List documents indexed for this dataset |
| POST | `/api/datasets/{id}/chat` | `{"question": "..."}` → answers, tool results, citations, charts, `verified` status |
| POST | `/api/datasets/{id}/reports` | Generates structured JSON report downloadable in the UI |

Interactive Swagger documentation is available at `/docs` when the backend is running.

---

## Verified Results

- **Backend tests: `82 passed`** (`pytest -q`, Python 3.11).
  - Mocked HTTP provider tests for Groq chat completion and Google Gemini batch embeddings.
  - Dimension mismatch recovery and embedding model transition tests for ChromaDB.
  - 16 audit-correctness tests comparing LangGraph answers with direct Pandas calculations.
  - Security, key masking, bounded retries, and dataset isolation tests.
- **Frontend:**
  - `tsc --noEmit` clean.
  - `vite build` succeeds in under 2 seconds.
  - Main bundle is 175 kB (57 kB gzip); Recharts chart module is in a separate 390 kB lazy chunk.
- **Live Provider Integration: Verified.**
  - **Groq Chat:** Tested live with model `openai/gpt-oss-120b`.
  - **Google Gemini Embeddings:** Tested live with `gemini-embedding-2` generating 3,072-dimensional vectors.
  - **ChromaDB Semantic Search:** Ingested markdown documentation and verified real-time vector indexing and similarity retrieval with citation scoring.

---

## Deployment Guide

DataSleuth is designed for simple, modern deployment: **FastAPI backend on Render** and **Vite/React frontend on Vercel**.

### What to do about ChromaDB in Deployment

DataSleuth uses ChromaDB's embedded `PersistentClient`, storing vector indices and SQLite metadata under `$DATA_DIR/chroma`.

1. **Deploying on the Free Tier (No Paid Disks Needed):**
   - You **do not need a persistent disk**. Leave `DATA_DIR=./data` (the default).
   - ChromaDB, SQLite, and file uploads work inside the local `./data` folder of the container.
   - When Render's free tier spins down after 15 minutes of inactivity or restarts, the container restarts fresh. Users simply upload their CSV when testing or demoing.
   - **Do NOT add any disk in the "Disks" section** of the Render dashboard. Leaving "Disks" empty allows you to select Render's **Free Instance Type ($0/month)**.
2. **Worker Concurrency:**
   - Always run the backend with **`--workers 1`** (as configured in `render.yaml` and `Procfile`). Embedded ChromaDB uses local SQLite and HNSW file structures; a single worker avoids cross-process file-lock contention.
3. **Model Change Safety:**
   - DataSleuth automatically tags ChromaDB collections with the active `embedding_model`. If you change the model in the future, the backend detects the dimension/model mismatch, safely resets the incompatible collection, and synchronizes SQLite cleanly without throwing 500 errors.

---

### Step-by-Step Deployment

#### 1. Pre-Deployment Checklist
- [x] Backend tests pass: `pytest backend/tests`
- [x] Frontend builds cleanly: `npm --prefix frontend run build`
- [x] Make sure `.env` files are **not** committed to Git (verified in `.gitignore`)
- [x] Generate a secure API key for production:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

#### 2. Deploy Backend on Render
1. Push your code to a GitHub/GitLab repository.
2. In the [Render Dashboard](https://dashboard.render.com/), click **New** → **Web Service** and connect your repository.
3. Choose **Blueprint** (it will auto-detect `backend/render.yaml`) OR configure manually:
   - **Root Directory:** `backend`
   - **Environment:** `Python 3.11.9`
   - **Build Command:** `pip install --only-binary=:all: -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
   - **Health Check Path:** `/health`
4. Set Environment Variables in Render:
   - `DATASLEUTH_API_KEY` = `<your generated production key>`
   - `LLM_API_KEY` = `<your Groq API key>`
   - `LLM_BASE_URL` = `https://api.groq.com/openai/v1`
   - `LLM_MODEL` = `openai/gpt-oss-120b`
   - `EMBEDDING_API_KEY` = `<your Google Gemini API key>`
   - `EMBEDDING_BASE_URL` = `https://generativelanguage.googleapis.com/v1beta`
   - `EMBEDDING_MODEL` = `gemini-embedding-2`
   - `DATA_DIR` = `./data`
   - `TRUST_PROXY_HEADERS` = `true`
   - `CORS_ORIGINS` = `https://<your-app>.vercel.app`
5. **Leave the "Disks" section completely empty** (do not add any disk). This keeps your deployment on Render's 100% Free plan.
6. Deploy the service and copy your public backend URL (e.g., `https://datasleuth-api.onrender.com`).

#### 3. Deploy Frontend on Vercel
1. Open [`frontend/vercel.json`](file:///Users/mayankchauhan/Documents/datasleuth/frontend/vercel.json) and replace `YOUR-BACKEND.onrender.com` with your real Render URL:
   ```json
   {
     "rewrites": [
       { "source": "/api/:path*", "destination": "https://datasleuth-api.onrender.com/api/:path*" },
       { "source": "/health", "destination": "https://datasleuth-api.onrender.com/health" },
       { "source": "/((?!api/|health).*)", "destination": "/index.html" }
     ]
   }
   ```
2. Commit and push the updated `vercel.json` to your repository.
3. In [Vercel Dashboard](https://vercel.com/), click **Add New** → **Project** and select your repository.
4. Set **Root Directory** to `frontend`.
5. Keep Framework Preset as **Vite** (Build command: `npm run build`, Output directory: `dist`).
6. Click **Deploy**.
7. Once deployed, open your Vercel URL, paste your `DATASLEUTH_API_KEY` in the sidebar, and save it!
