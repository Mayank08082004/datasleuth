# 🔍 DataSleuth — AI-Powered Dataset Exploration & Data Quality Auditor

[![Live Frontend](https://img.shields.io/badge/Live%20App-Vercel-black?style=for-the-badge&logo=vercel)](https://datasleuth-eight.vercel.app)
[![Live Backend](https://img.shields.io/badge/API%20Backend-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://datasleuth-qa0m.onrender.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%200.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite%205-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://vitejs.dev)
[![Groq](https://img.shields.io/badge/Chat%20LLM-Groq%20(gpt--oss--120b)-F55036?style=for-the-badge)](https://groq.com)
[![Gemini](https://img.shields.io/badge/Embeddings-Google%20Gemini%20(embedding--2)-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB%200.5-orange?style=for-the-badge)](https://www.trychroma.com)

> **Live Deployment:**  
> 🌐 **Web Application:** [https://datasleuth-eight.vercel.app](https://datasleuth-eight.vercel.app)  
> ⚡ **API & Interactive Docs:** [https://datasleuth-qa0m.onrender.com/docs](https://datasleuth-qa0m.onrender.com/docs)  
> 🩺 **Health Check:** [https://datasleuth-qa0m.onrender.com/health](https://datasleuth-qa0m.onrender.com/health)

---

## 💡 Overview

**DataSleuth** is a production data exploration and audit platform. It ingests CSV or Excel datasets, profiles columns, detects quality anomalies, and answers natural-language business and statistical questions with verifiable evidence.

### 🛡️ Core Philosophy: Zero Hallucinations
- **Every number comes from Python:** Aggregations, statistics, and audits are computed deterministically with **Pandas** and **NumPy**. The LLM never writes or executes code in the dark and never invents metrics.
- **Strict Grounding Verifier:** Every figure in the final answer is cross-checked against computed results. If the LLM generates an unverified figure, DataSleuth automatically replaces it with the deterministic summary.
- **Dataset-Scoped Multimodal RAG:** Supporting documents (data dictionaries, business rules) are chunked and vectorized using **Google Gemini `gemini-embedding-2`** and indexed in **ChromaDB** with strict dataset isolation.
- **High-Speed Conversational Synthesis:** **Groq (`openai/gpt-oss-120b`)** transforms verified tool outputs into concise, executive-ready insights.

---

## 🏗️ Architecture & Query Flow

```
                      User Question
                            │
                            ▼
                    ┌──────────────┐
                    │   Classify   │ (Keyword & Intent Router)
                    └───────┬──────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Validate Dataset│
                   └────────┬────────┘
                            │
      ┌─────────────────────┼─────────────────────────┐
      ▼                     ▼                         ▼
 [Documentation]     [Business Rules]     [Quality / Aggregation / General]
      │                     │                         │
  Gemini Embeddings     Gemini Embeddings         Deterministic Tool Plan
      │                     │                         │
  ChromaDB Search       Evaluate Rule Engine      Execute Pandas / NumPy
      │                     │                         │
      └──────────────┬──────┴─────────────────────────┘
                     │
                     ▼
             ┌───────────────┐
             │    Verify     │ (Check tool results & dataset consistency)
             └───────┬───────┘
                     │
                     ▼
             ┌───────────────┐
             │  Build Chart  │ (Generated strictly from computed rows)
             └───────┬───────┘
                     │
                     ▼
             ┌───────────────┐
             │ Groq Response │ (Synthesize explanation from facts only)
             └───────┬───────┘
                     │
                     ▼
             ┌───────────────┐
             │Check Grounding│ (Verify every number; fallback if ungrounded)
             └───────┬───────┘
                     │
                     ▼
        Verified Answer + Interactive Chart + Source Citations
```

---

## ✨ Features

- **📊 Comprehensive Data Profiling:** Instant row/column counts, blanks, distinct identifiers, min/max/mean/median, and categorical distribution breakdowns.
- **🔬 Automated Data Quality Auditor:** Distinguishes between blank values, parse failures (e.g. `2026-02-30`), duplicated primary keys, and statistical outliers (IQR fences).
- **📑 Rule-Engine & Policy Compliance:** Audits datasets against plain-text business rules (e.g. *"Transaction amounts must be positive"* or *"Transaction IDs must be unique"*), highlighting offending row indices.
- **📚 Dataset-Isolated Document RAG:** Vectorizes data dictionaries and business rule documents using Google Gemini embeddings with cosine similarity retrieval.
- **📈 Rich Visualizations:** Interactive responsive charts powered by Recharts built strictly from verified query data.
- **📄 Downloadable Audit Reports:** Generates structured JSON reports containing overview metrics, quality findings, and audit summaries.

---

## 📂 Repository Structure

```
datasleuth/
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI application, CORS, /health, request logger
│   │   ├── config.py                  Pydantic settings (Groq, Gemini, ChromaDB, secrets)
│   │   ├── api/                       API routes: datasets.py · analysis.py · reports.py
│   │   ├── services/
│   │   │   ├── dataset_service.py     File validation, raw + normalized frames, SQLite metadata
│   │   │   ├── profiling_service.py   Numeric, categorical, and datetime profiles
│   │   │   ├── quality_service.py     Deterministic data quality checks (read-only)
│   │   │   ├── rules_service.py       Business-rule parser and violation evaluator
│   │   │   ├── rag_service.py         Document chunking, ChromaDB storage & recovery, RAG
│   │   │   └── llm_client.py          Groq chat & Google Gemini embedding clients
│   │   ├── tools/data_tools.py        Registered, safe analysis tools (grouped agg, IQR fences, etc.)
│   │   ├── agents/                    LangGraph state graph: state.py · nodes.py · graph.py
│   │   └── models/schemas.py          Pydantic request & response schemas
│   ├── sample_data/                   transactions.csv · business_rules.md · data_dictionary.md
│   ├── tests/                         82 tests (mocked providers, Chroma recovery, audit correctness)
│   ├── requirements.txt · .env.example · render.yaml · Procfile
│   └── .python-version                Pins Python 3.11.9 for cloud deployments
└── frontend/
    ├── src/
    │   ├── pages/                     Dashboard · DatasetOverview · DataQuality · Ask · Documentation · Reports
    │   ├── components/                Layout · UI · ChartView (Recharts)
    │   ├── api.ts                     Type-safe API client (relative proxy routing)
    │   ├── types.ts · hooks.ts · App.tsx · main.tsx
    ├── vercel.json                    Reverse proxy rewrite rules to Render backend
    └── package.json · vite.config.ts · tailwind.config.js
```

---

## 🚀 Live Production Deployment

DataSleuth is deployed on a free-tier cloud architecture:

| Component | Platform | Live URL | Details |
|---|---|---|---|
| **Frontend** | **Vercel** | [datasleuth-eight.vercel.app](https://datasleuth-eight.vercel.app) | React 18, Vite 5, Tailwind CSS, automatic reverse proxy to API |
| **Backend** | **Render** | [datasleuth-qa0m.onrender.com](https://datasleuth-qa0m.onrender.com) | FastAPI, Python 3.11.9, Uvicorn (1 worker) |
| **Chat LLM** | **Groq Cloud** | Endpoint: `api.groq.com/openai/v1` | Model: `openai/gpt-oss-120b` |
| **Embeddings** | **Google AI** | Endpoint: `generativelanguage.googleapis.com` | Model: `gemini-embedding-2` (3,072 dims) |
| **Vector DB** | **ChromaDB** | Embedded `PersistentClient` | Storage: `$DATA_DIR/chroma` |

---

## 🛠️ Local Setup & Quick Start

### 1. Prerequisites
- **Python:** 3.11 or 3.12 (Python 3.11.9 recommended)
- **Node.js:** 18+ and npm

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --only-binary=:all: -r requirements.txt

# Configure environment variables
cp .env.example .env
```

Generate your secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Configure `backend/.env`:
```dotenv
DATASLEUTH_API_KEY=<your-generated-key>
LLM_API_KEY=<your-groq-api-key>
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b

EMBEDDING_API_KEY=<your-google-gemini-api-key>
EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta
EMBEDDING_MODEL=gemini-embedding-2
DATA_DIR=./data
```

Start the API:
```bash
uvicorn app.main:app --reload --port 8000
```

Run tests:
```bash
pytest backend/tests -q
# 82 passed in ~4s
```

### 3. Frontend Setup

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. In the left sidebar, paste your `DATASLEUTH_API_KEY` and click **Save key**.

---

## ⚙️ Environment Variables Reference

| Variable | Description | Default |
|---|---|---|
| `DATASLEUTH_API_KEY` | Required header key (`X-API-Key`) protecting all `/api/*` routes. | `change-me` |
| `LLM_API_KEY` | Groq API Key. | — |
| `LLM_BASE_URL` | Groq OpenAI-compatible endpoint. | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | Chat model. | `openai/gpt-oss-120b` |
| `EMBEDDING_API_KEY` | Google Gemini API Key. | — |
| `EMBEDDING_BASE_URL` | Google Gemini API endpoint. | `https://generativelanguage.googleapis.com/v1beta` |
| `EMBEDDING_MODEL` | Gemini embedding model. | `gemini-embedding-2` |
| `EMBEDDING_DIMENSIONS` | Optional Matryoshka dimension reduction (e.g. 768 or 1536). | `None` (full 3,072) |
| `DATA_DIR` | Storage root for uploaded files, SQLite DB, and ChromaDB vectors. | `./data` |
| `CORS_ORIGINS` | Allowed origins (comma-separated). | `http://localhost:5173,http://localhost:3000` |
| `MAX_UPLOAD_MB` | Maximum allowed dataset file size (MB). | `20` |
| `MAX_DOCUMENT_MB` | Maximum allowed markdown/PDF documentation file size (MB). | `10` |
| `RATE_LIMIT_PER_MINUTE`| Maximum requests per minute per IP address. | `60` |
| `TRUST_PROXY_HEADERS` | Set to `true` when behind a reverse proxy (Render, Cloudflare, etc.). | `false` |

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service liveness and version check (public) |
| `POST` | `/api/datasets/upload` | Upload and validate `.csv` or `.xlsx` dataset file |
| `GET` | `/api/datasets` | List all uploaded datasets and their metadata |
| `GET` | `/api/datasets/{id}` | Retrieve metadata for a specific dataset |
| `GET` | `/api/datasets/{id}/profile` | Get comprehensive column profiling & statistics |
| `GET` | `/api/datasets/{id}/preview` | Paginated row preview (`page`, `page_size`) |
| `GET` | `/api/datasets/{id}/quality` | Automated data quality audit findings |
| `POST` | `/api/datasets/{id}/documents` | Ingest and vectorize `.md`, `.txt`, or `.pdf` documentation |
| `GET` | `/api/datasets/{id}/documents` | List indexed documentation chunks for a dataset |
| `POST` | `/api/datasets/{id}/chat` | Natural-language query execution & synthesis |
| `POST` | `/api/datasets/{id}/reports` | Generate structured audit report (JSON download) |

---

## 🧪 Verification & Testing

Every commit and feature is thoroughly tested with automated test suites:

- **Backend Test Suite:** `82 passed` (`pytest`, Python 3.11)
  - Unit tests for Groq chat & Google Gemini batch embedding API payloads.
  - Safe ChromaDB dimension mismatch recovery and automatic model change handling.
  - 16 audit correctness tests verified against raw Pandas operations.
  - Security tests verifying zero key leaks in error traces or URLs.
- **Frontend Build:** `npm run build` cleanly compiles in under 2 seconds with zero TypeScript warnings.
- **Production Integration:** Live uploads of `transactions.csv`, `data_dictionary.md`, and `business_rules.md` verified on Render & Vercel.

---

## 📄 License

Distributed under the MIT License.
