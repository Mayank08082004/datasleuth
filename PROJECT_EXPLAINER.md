# 🔍 DataSleuth — The Master Project Guide
> **From Zero to Deep Mastery: The Why, What, and How of AI-Powered Dataset Auditing and Exploration**

---

## 🌟 Executive Summary: The Elevator Pitch

Imagine you give an Excel spreadsheet of 100,000 corporate financial transactions to a traditional AI chatbot like ChatGPT or Claude and ask:
> *"What was our total revenue in the North region, and were there any fraudulent duplicate invoices?"*

The standard chatbot might write back with total confidence:
> *"Your total revenue was $4,821,950.00, and no duplicate invoices were found."*

**Here is the terrifying reality:** The chatbot almost certainly **guessed or hallucinated that number**. Large Language Models (LLMs) are text-prediction neural networks, not calculators. They do not run math engines in their heads; they predict what words and numbers *sound plausible*. In high-stakes enterprise accounting, healthcare, or compliance, that hallucination could cost millions of dollars or trigger legal penalties.

**DataSleuth** solves this fundamental crisis.

DataSleuth is an **AI-powered dataset exploration and automated data quality auditing system** built upon one uncompromising principle:
> **Absolute Numerical Determinism: Every number must come from verified Python code (Pandas/NumPy), never from an LLM's imagination.**

In DataSleuth:
- **The Python Engine (Pandas/NumPy)** acts as the **Accountant/Sleuth**: It computes the exact totals, groups, averages, duplicates, and outliers with 100% mathematical precision.
- **The Vector Database (ChromaDB + Google Gemini)** acts as the **Librarian**: It retrieves enterprise domain knowledge, data dictionaries, and business rules.
- **The State Machine (LangGraph)** acts as the **Conductor**: It routes questions, plans safe analytical tools, coordinates RAG, and verifies facts.
- **The Chat Model (Groq / `gpt-oss-120b`)** acts strictly as the **Executive Presenter**: It is fed the pre-calculated numbers in structured JSON and translates them into plain English.
- **The Grounding Verifier** acts as the **Security Guard**: If the LLM invents even a single unverified number, the guard instantly intercepts the message and replaces it with the deterministic Python summary.

---

## 🧭 PART 1: WHY Does DataSleuth Exist? (The Problem)

### 1. The Core Flaws of Generative AI in Tabular Analytics

| Traditional LLM Approach | What Goes Wrong | How DataSleuth Solves It |
|---|---|---|
| **Direct Prompting** (Pasting CSV into ChatGPT) | **Context Limit & Hallucination:** Files larger than a few megabytes exceed prompt tokens. The LLM guesses aggregations, skips rows, or invents totals. | **Decoupled Execution:** The raw data stays in Python memory. Only computed aggregated facts are sent to the LLM. |
| **Unconstrained Code Generation** (Code Interpreter / Auto-Python) | **Syntax Errors & Security Risks:** The LLM generates Python or SQL code on the fly. Code can crash, time out, run infinite loops, or attempt malicious file/system access. | **Pre-Validated Safe Tool Registry:** The LLM never writes free-form code. It only triggers pre-written, audited analytical functions. |
| **Naive RAG (Retrieval-Augmented Generation)** | **Lack of Dataset Context:** Searching documentation without dataset scoping can mix up definitions between different datasets. | **Dataset-Scoped Namespaces:** Vectors in ChromaDB are tagged with `dataset_id`. Dataset A never sees Dataset B's documentation. |
| **Unchecked Output** | **Silent Hallucinations:** Even when instructed to be truthful, models subtly alter decimal places or invent percentages. | **Active Regex Grounding Verifier:** Tokenizes every number in the output and validates it against calculated facts. Zero tolerance for ungrounded numbers. |

### 2. The Business Reality: The Cost of Bad Data
Dirty data costs global organizations trillions of dollars annually. Common real-world data issues include:
1. **Ghost Duplicates:** The same invoice or transaction processed twice.
2. **Type Poisoning:** A price field containing `"not available"` instead of a number, silently corrupting sums.
3. **Impossible Dates:** Invalid dates like `2026-02-30` (Feb 30th does not exist) crashing downstream ETL pipelines.
4. **Fat-Finger Outliers:** A $15.00 item accidentally entered as $15,000.00, distorting regional profit margins.
5. **Rule Violations:** Negative transaction amounts or unassigned customer IDs.

DataSleuth was created to detect all of these automatically the second a file is uploaded, and allow any business analyst to ask questions in plain English without writing a single line of SQL or Python.

---

## 🏗️ PART 2: WHAT Does DataSleuth Do? (The Features & Architecture)

### 1. High-Level Architecture Diagram

```
                             ┌────────────────────────┐
                             │   User / Web Browser   │
                             │ (React 18 + Vite 5 UI) │
                             └───────────┬────────────┘
                                         │  HTTP / JSON (Protected by X-API-Key)
                                         ▼
                             ┌────────────────────────┐
                             │  FastAPI Backend (API) │
                             │  (Uvicorn on Render)   │
                             └───────────┬────────────┘
                                         │
                 ┌───────────────────────┼────────────────────────┐
                 ▼                       ▼                        ▼
       ┌──────────────────┐    ┌──────────────────┐     ┌──────────────────┐
       │ Ingestion Engine │    │ SQLite Metadata  │     │  Vector RAG Sub- │
       │ (Raw + Normalized│    │ (Dataset record, │     │      system      │
       │    DataFrames)   │    │  Doc references) │     │ (ChromaDB Vector)│
       └─────────┬────────┘    └──────────────────┘     └─────────┬────────┘
                 │                                                │
                 └───────────────────────┬────────────────────────┘
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │    LangGraph Analytical State Graph    │
                     │  (Predictable Deterministic Workflow)  │
                     └───────────────────┬────────────────────┘
                                         │
      ┌────────────────┬─────────────────┼────────────────┬──────────────────┐
      ▼                ▼                 ▼                ▼                  ▼
[1. Classify]   [2. Validate]    [3. Plan & Exec]   [4. RAG Docs]    [5. Rule Engine]
Intent Router   Check dataset      Pandas/NumPy     Gemini Embeds     Regex Matcher &
Regex parser       exists            Analytics      ChromaDB Top-K    Filter Evaluator
      │                │                 │                │                  │
      └────────────────┴─────────────────┼────────────────┴──────────────────┘
                                         │
                                         ▼
                             ┌────────────────────────┐
                             │    Verify Facts &      │
                             │  Generate Chart Spec   │
                             └───────────┬────────────┘
                                         │
                                         ▼
                             ┌────────────────────────┐
                             │   Groq LLM Synthesis   │
                             │ (openai/gpt-oss-120b)  │
                             └───────────┬────────────┘
                                         │
                                         ▼
                             ┌────────────────────────┐
                             │ Active Grounding Check │
                             │ (Regex Number Guard)   │
                             └───────────┬────────────┘
                                         │
                      ┌──────────────────┴──────────────────┐
                      ▼                                     ▼
             [Numbers Match 100%]                 [Hallucination Detected]
                      │                                     │
                      ▼                                     ▼
          Deliver Natural Language             Fallback: Deliver Exact
              Synthesis Answer                  Deterministic Python Summary
```

---

### 2. The Core Application Capabilities

#### A. Comprehensive Data Profiling
When a user uploads a `.csv` or `.xlsx` spreadsheet:
- **Instant Dimension Profiling:** Total row count, column count, memory consumption, null cell count.
- **Column-by-Column Deep Profiling:**
  - **Numeric Columns:** Mean, median, standard deviation, min, max, 25th percentile, 75th percentile, zero counts, negative counts.
  - **Categorical Columns:** Number of unique values (cardinality), top 5 most frequent values with percentage shares.
  - **Datetime Columns:** Earliest date, latest date, chronological span.

#### B. The Automated 4-Pillar Quality Auditor
DataSleuth deterministically isolates data quality flaws into four rigorous categories:
1. **Missing Values (Blanks):** Pure empty cells (`NaN` or empty strings).
2. **Invalid Values (Parse Failures):** Distinguishes between intentional blanks and *corrupted text* in numeric/date columns (e.g. `"not available"` in a unit price column or `"2026-02-30"` in a date column).
3. **Duplicate Detection:**
   - **Exact Row Duplicates:** Identical records repeated across the dataset.
   - **Identifier Duplicates:** Repeated values in columns that are supposed to be primary keys (e.g., `transaction_id`).
4. **Statistical Outlier Investigation:**
   - Evaluates numeric columns using **Tukey's Inter-Quartile Range (IQR) Fences**:
     $$\text{IQR} = Q_3 - Q_1$$
     $$\text{Fence}_{\text{Low}} = Q_1 - 1.5 \times \text{IQR}, \quad \text{Fence}_{\text{High}} = Q_3 + 1.5 \times \text{IQR}$$
   - Any record where $\text{value} < \text{Fence}_{\text{Low}}$ or $\text{value} > \text{Fence}_{\text{High}}$ is isolated and flagged for human investigation.

#### C. Plain-English Business Rules Compliance Engine
Upload a Markdown file (`business_rules.md`) containing enterprise rules such as:
```markdown
1. Transaction amounts must be positive.
2. Transaction IDs must be unique.
3. Quantity must be greater than zero.
4. Unit price must be positive.
```
DataSleuth parses each rule into a deterministic Boolean filter, scans the dataset, and outputs the exact row index and record ID (e.g., `T0009 has amount = -300.00`) of every violating record.

#### D. Dataset-Scoped Multimodal Document RAG
Upload a Data Dictionary (`data_dictionary.md` or `.pdf`):
- Chunks text into 900-character windows with 150-character overlaps.
- Generates 3,072-dimensional vector embeddings via **Google Gemini (`gemini-embedding-2`)**.
- Stores vectors in **ChromaDB** tagged with the specific `dataset_id`.
- When an analyst asks: *"What does product_category represent?"*, DataSleuth retrieves the exact section and page number, citing the original document chunk.

#### E. Natural-Language Conversational Querying ("Ask")
Users ask questions like:
- *"Which region had the highest total revenue?"*
- *"Show me monthly sales trends for Electronics."*
- *"Are there any duplicate transaction IDs?"*

DataSleuth executes the Python calculation, generates a responsive interactive chart (Bar or Line chart via Recharts), calls Groq's high-speed LLM to formulate an executive summary, and verifies every number before displaying it.

#### F. Audit Reports Generation
Generates a downloadable, compliance-ready JSON audit report consolidating dataset metadata, quality findings, rule violations, and summary statistics.

---

## ⚙️ PART 3: HOW Does DataSleuth Work? (Step-by-Step Technical Deep Dive)

Let us follow a piece of data through the entire system, from the moment a user uploads a file to the moment a chart and verified answer appear on their screen.

---

### Step 1: File Upload & Dual-DataFrame Ingestion
**Source File:** [`backend/app/services/dataset_service.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/services/dataset_service.py)

When a user uploads `transactions.csv`:
1. **Security & Validation:**
   - [`file_validation.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/utils/file_validation.py) checks the extension (`.csv`, `.xlsx`), validates file size (maximum 20MB), sanitizes the filename to prevent directory traversal attacks, and verifies MIME headers.
2. **The Dual-Frame Architecture:**
   - Most data pipelines make the mistake of immediately converting everything to numbers. If a cell has `"not available"`, standard Pandas converts it to `NaN` (blank). **You have now lost the evidence that the user wrote bad text!**
   - DataSleuth creates **TWO** DataFrames:
     - **`raw` DataFrame:** Read with `dtype=str`. Every cell is preserved exactly as written in the file. Leading zeros (`00123`) and invalid strings (`"not available"`, `"2026-02-30"`) remain intact.
     - **`norm` (Normalized) DataFrame:** Processed through `coerce_frame()`. If $\ge 90\%$ of non-empty values in a column parse as numbers or dates, it is coerced to float/int or `datetime64`. The unparseable cells become `NaN`. Columns with ID hints (`id`, `sku`, `code`) are kept as strings to preserve identifier format.
3. **Persistence:** The file is saved to disk (`./data/uploads/<uuid>_<filename>`), and metadata is recorded in an embedded SQLite database (`./data/datasleuth.db`).

---

### Step 2: The Automated Data Quality Engine
**Source File:** [`backend/app/services/quality_service.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/services/quality_service.py)

The quality engine takes both `raw` and `norm` frames and runs four deterministic passes:

#### 1. Blank Detection (`check_missing`)
Looks at `raw.isna()`. If a cell was actually empty in the original file, it is counted as a missing value.
- Severity is calculated: $\ge 20\%$ missing is `high`, $\ge 5\%$ is `medium`, otherwise `low`.

#### 2. Invalid Value Detection (`check_invalid_numeric` & `check_invalid_dates`)
This is where the dual-frame design shines!
```python
# A cell is INVALID if it was NOT empty in raw, but IS NaN in normalized!
bad_cells = raw[col].notna() & df[col].isna()
```
If row 65 had `"not available"`, it was not empty in `raw`, but became `NaN` in `norm`. DataSleuth catches this instantly and reports:
> *"1 value(s) in numeric column 'unit_price' could not be parsed as numbers. Affected: T0063."*

Similarly, for dates, `"2026-02-30"` is not a valid date. It is caught, flagged, and linked to row identifier `T0075`.

#### 3. Duplicate Detection (`check_duplicate_rows` & `check_duplicate_identifiers`)
- `check_duplicate_rows`: Runs `df.duplicated()` to find entire rows that are carbon copies of earlier rows.
- `check_duplicate_identifiers`: Checks primary-key columns (e.g. `transaction_id`). If an ID repeats, it flags:
  > *"Identifier column 'transaction_id' has 1 repeated value(s) across 2 rows. Affected: T0001."*

#### 4. Outlier Detection (`check_outliers`)
For continuous numeric columns (excluding IDs):
- Computes 25th percentile ($Q_1$) and 75th percentile ($Q_3$).
- $\text{IQR} = Q_3 - Q_1$.
- Calculates lower fence $Q_1 - 1.5 \times \text{IQR}$ and upper fence $Q_3 + 1.5 \times \text{IQR}$.
- Identifies records outside this range. For `transactions.csv`, amounts of $9,500.00 and $15,000.00 are detected as statistical outliers.

---

### Step 3: Plain-Text Business Rules Engine
**Source File:** [`backend/app/services/rules_service.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/services/rules_service.py)

Instead of passing user business rules to an LLM to "figure out", DataSleuth uses strict regex pattern matching to translate plain-English sentences into executable rules:

| English Rule Pattern | Internal Rule Type | Pandas Execution Filter |
|---|---|---|
| `[Column] must be positive` | `"positive"` | `series <= 0` |
| `[Column] must not be negative` | `"non_negative"` | `series < 0` |
| `[Column] must be unique` | `"unique"` | `series.duplicated(keep=False)` |
| `[Column] must be between [A] and [B]` | `"range"` | `(series < A) | (series > B)` |
| `[Col A] must not be later than [Col B]` | `"not_after"` | `df[Col A] > df[Col B]` |

If a sentence does not match a known rule pattern, DataSleuth **does not guess**. It flags the rule as `unsupported_rules` with an honest explanation, ensuring no false sense of security.

---

### Step 4: Multimodal Document RAG Subsystem
**Source File:** [`backend/app/services/rag_service.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/services/rag_service.py) & [`llm_client.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/services/llm_client.py)

When a data dictionary or policy document is uploaded:
1. **Extraction & Chunking:**
   - Markdown and text files are split by markdown headers (`#`, `##`) and windowed into chunks of 900 characters with 150-character overlap.
   - For PDFs, `pypdf` extracts text while preserving page numbers.
2. **Google Gemini Embeddings:**
   - Chunks are vectorized using Google's state-of-the-art `gemini-embedding-2` model via batch API calls (`:batchEmbedContents`).
   - Generates high-density **3,072-dimensional vector embeddings**.
3. **ChromaDB Vector Store:**
   - Chunks and embeddings are saved into an embedded ChromaDB collection using cosine similarity metric (`hnsw:space = "cosine"`).
   - Every chunk is stored with metadata: `{"dataset_id": dataset_id, "filename": filename, "page": page, "section": section}`.
   - Retrieval queries filter by `dataset_id`. Dataset isolation is 100% mathematically enforced.
4. **Resilience & Self-Healing:**
   - If the embedding model or vector dimension ever changes, `_is_dimension_mismatch()` automatically detects the mismatch, drops the outdated collection, and recreates it cleanly without crashing the server.

---

### Step 5: The LangGraph Analytical State Machine
**Source Files:** [`backend/app/agents/graph.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/agents/graph.py) & [`nodes.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/agents/nodes.py)

LangGraph organizes the analysis workflow as a state machine where a typed state dictionary (`AgentState`) flows through discrete nodes.

#### The State Schema (`AgentState`):
```python
class AgentState(TypedDict, total=False):
    dataset_id: str
    user_question: str
    intent: str                      # "aggregation" | "quality" | "business_rules" | "documentation" | "general"
    tool_plan: list[dict]            # [{"name": "grouped_aggregation", "args": {...}}]
    retrieved_documents: list[dict]  # Document chunks from ChromaDB
    analysis_results: list[dict]     # Calculated output from Pandas
    validation_results: dict         # Grounding and safety checks
    final_response: str              # The synthesized English explanation
    chart: Optional[dict]            # Recharts specification (type, x, y, data points)
    citations: list[dict]            # Document chunks cited
    limitations: list[str]           # Honest notices if something could not be done
    retries: int
    error: Optional[str]
```

#### The Graph Nodes & Flow:
1. **`classify` (Intent Router):**
   - Examines the user question using regex pattern grammars:
     - Keywords like *"violate, rule, compliance"* $\to$ `business_rules`
     - Keywords like *"missing, duplicate, outlier, invalid, quality"* $\to$ `quality`
     - Keywords like *"definition, dictionary, mean, represent"* $\to$ `documentation`
     - Keywords like *"sum, average, total, highest, top, monthly"* $\to$ `aggregation`
2. **`validate_dataset`:** Checks whether the dataset exists in SQLite. If missing, branches directly to `handle_error`.
3. **Conditional Branching:**
   - If `documentation` $\to$ Routes to `retrieve` (ChromaDB search) $\to$ `verify`.
   - If `business_rules` $\to$ Routes to `retrieve` $\to$ `rules` (evaluate parsed rules against dataset).
   - If `aggregation` or `quality` $\to$ Routes to `plan` $\to$ `analyse`.
4. **`plan` (`_plan_tools`):**
   - Inspects the dataset column names and data types.
   - Matches the user's intent to a specific tool from [`data_tools.py`](file:///Users/mayankchauhan/Documents/datasleuth/backend/app/tools/data_tools.py):
     - `grouped_aggregation`: e.g. sum of `amount` grouped by `region`.
     - `monthly_aggregation`: resamples datetime to `YYYY-MM` periods.
     - `column_statistics`: computes sum, mean, min, max for a single column.
     - `outlier_investigation`: computes IQR fences for a numeric column.
     - `duplicate_records`: checks whole-row or column-specific duplicates.
     - `correlation`: computes Pearson correlation coefficient between two numeric vectors.
     - `missing_values`: counts blanks per column.
     - `dataset_summary`: counts rows, columns, distinct IDs.
5. **`analyse` (`execute_analysis`):**
   - Executes the planned tool strictly inside Python.
   - Saves the exact numerical dictionary into `analysis_results`.
6. **`verify`:**
   - Ensures that the analysis returned non-empty output and that the dataset matches.
7. **`make_chart` (`build_chart`):**
   - If the tool was `grouped_aggregation` or `monthly_aggregation`, builds a chart spec:
     ```json
     {
       "type": "bar",
       "title": "Sum of amount by region",
       "x_label": "region",
       "y_label": "amount",
       "data": [
         {"name": "East", "value": 19600.0},
         {"name": "South", "value": 14210.0},
         {"name": "North", "value": 8450.0},
         {"name": "West", "value": 4120.0}
       ]
     }
     ```
8. **`respond` (`generate_response`):**
   - Packages the pre-computed facts, tool outputs, and retrieved document snippets into a clean JSON structure.
   - Sends the JSON to **Groq Cloud (`openai/gpt-oss-120b`)** with a strict system instruction:
     > *"You explain analysis results to a data analyst. Use ONLY the numbers in the JSON provided. Never invent figures or sources. If the JSON lacks the answer, say so."*
9. **`check_grounding` (The Active Anti-Hallucination Guard):**
   - **How it works:**
     1. Uses regular expressions `\d+(?:\.\d+)?` to extract every single number in the LLM's response text.
     2. Collects all allowed numbers from the computed tool outputs, the input question, and retrieved document chunks.
     3. Compares each generated number against the allowed set with decimal tolerance checking.
     4. **If any number is not grounded:** The LLM's response is **instantly discarded and replaced** with `_deterministic_summary(facts)` (a summary generated directly by Python string formatting from the raw tool outputs).
     5. The substitution is recorded in `limitations`:
        > *"The generated explanation contained figures that were not in the computed results, so the computed summary is shown instead."*

---

### Step 6: Frontend Experience & Visualization
**Source Directory:** [`frontend/src/`](file:///Users/mayankchauhan/Documents/datasleuth/frontend/src/)

The frontend is a modern single-page application built with **React 18, Vite 5, and Tailwind CSS**:
- **Sidebar & Navigation:** Clean, modern interface with dataset selector and API Key configuration.
- **Pages:**
  - **Dashboard (`/`):** View recent datasets, upload new `.csv` / `.xlsx` files, see immediate file validation badges.
  - **Dataset Overview (`/datasets/:id`):** Interactive paginated preview table of rows, dataset statistics, and column data type chips.
  - **Data Quality (`/datasets/:id/quality`):** Categorized view of missing values, invalid parse failures, duplicate rows, and statistical outliers, with row indices and affected record IDs.
  - **Ask (`/datasets/:id/ask`):** Conversational chat interface. Displays verified answers, dynamic interactive bar/line charts using **Recharts**, collapsible factual evidence JSON, and source document citations.
  - **Documentation (`/datasets/:id/documents`):** Upload data dictionaries and business rule markdown files, inspect indexed vector chunks.
  - **Reports (`/datasets/:id/reports`):** Comprehensive view of audit findings with one-click JSON download.
- **Fast Production Routing:** Reverse-proxy rewrite in `vercel.json` transparently proxies `/api/*` and `/health` requests to the Render cloud backend, avoiding cross-origin issues.

---

## 🔬 Walkthrough Example: A Real Query in Action

Let us trace what happens when you type into the Ask tab:
> **User asks:** *"Which region has the highest total sales?"*

1. **`classify`:** Detects `"highest"`, `"total"`, and `"sales"` $\to$ Intent is classified as `aggregation`.
2. **`validate_dataset`:** Finds dataset `transactions.csv` in SQLite.
3. **`plan`:**
   - Detects column `region` in categorical columns and `amount` in numeric columns.
   - Plans tool: `grouped_aggregation` with `value_column="amount"`, `group_by="region"`, `agg="sum"`, `descending=True`.
4. **`analyse`:**
   - Executes in Pandas:
     ```python
     df.groupby("region")["amount"].sum().sort_values(ascending=False)
     ```
   - Computed Output:
     - East: $19,600.00
     - South: $14,210.00
     - North: $8,450.00
     - West: $4,120.00
5. **`make_chart`:** Builds a Recharts bar chart specification where X is `region` and Y is `amount`.
6. **`respond`:** Groq LLM synthesizes:
   > *"The East region recorded the highest total sales at $19,600.00, followed by South ($14,210.00), North ($8,450.00), and West ($4,120.00)."*
7. **`check_grounding`:**
   - Extracts numbers: `[19600.00, 14210.00, 8450.00, 4120.00]`.
   - Checks against allowed numbers from Pandas tool output: All 4 numbers match exactly.
   - Status: `grounded: True`.
8. **UI Presentation:** The user receives the verified answer, source data table, and an interactive bar chart rendering East, South, North, and West.

---

## 📁 PART 4: Project Directory & File Guide

```
datasleuth/
├── backend/
│   ├── app/
│   │   ├── main.py                    FastAPI app, CORS middleware, API key auth, /health route
│   │   ├── config.py                  Pydantic Settings: API keys, model endpoints, data directories
│   │   ├── database/
│   │   │   └── db.py                  SQLite connection manager (datasets and documents tables)
│   │   ├── models/
│   │   │   └── schemas.py             Pydantic models for request/response validation
│   │   ├── services/
│   │   │   ├── dataset_service.py     File handling, raw vs normalized DataFrames, SQLite sync
│   │   │   ├── profiling_service.py   Statistical column profiling (mean, min, max, frequencies)
│   │   │   ├── quality_service.py     The 4-pillar data auditor (blanks, parse errors, dups, IQR)
│   │   │   ├── rules_service.py       Business rules parser and deterministic evaluator
│   │   │   ├── rag_service.py         Document chunking, Gemini vectorization, ChromaDB isolation
│   │   │   └── llm_client.py          HTTPX clients for Groq Chat and Google Gemini Embeddings
│   │   ├── tools/
│   │   │   └── data_tools.py          Safe Pandas analytical tools (aggregations, IQR, correlations)
│   │   ├── agents/
│   │   │   ├── state.py               AgentState definition for LangGraph
│   │   │   ├── nodes.py               Individual state machine nodes & grounding checker
│   │   │   └── graph.py               LangGraph compilation and conditional routing
│   │   ├── api/
│   │   │   ├── datasets.py            Upload, preview, profile, and document management routes
│   │   │   ├── analysis.py            Natural language query (/chat) route
│   │   │   └── reports.py             Structured audit report generation route
│   │   └── utils/
│   │       └── file_validation.py     Filename sanitization, extension checking, MIME validation
│   ├── sample_data/
│   │   ├── transactions.csv           76-row test dataset with deliberate real-world anomalies
│   │   ├── data_dictionary.md         Field definitions for columns
│   │   └── business_rules.md          Natural language enterprise constraints
│   ├── tests/                         82 automated Pytest suites verifying 100% correctness
│   ├── requirements.txt               Python dependencies
│   ├── render.yaml                    Render cloud deployment configuration
│   └── Procfile                       Production command: uvicorn app.main:app
│
├── frontend/
│   ├── src/
│   │   ├── pages/                     Dashboard, DatasetOverview, DataQuality, Ask, Documentation, Reports
│   │   ├── components/                Layout, UI controls, ChartView (Recharts visualization)
│   │   ├── api.ts                     Type-safe API client with fetch wrapper and X-API-Key injector
│   │   ├── types.ts                   TypeScript interfaces matching backend Pydantic models
│   │   ├── hooks.ts                   Custom React hooks for asynchronous data loading
│   │   ├── App.tsx                    React Router route definitions with lazy-loaded code splitting
│   │   └── main.tsx                   React DOM entrypoint
│   ├── vercel.json                    Vercel deployment config with reverse proxy rewrites to Render
│   └── package.json                   Frontend dependencies (React 18, Vite 5, Tailwind CSS, Recharts)
│
└── README.md                          Project overview and quickstart documentation
```

---

## 🎯 PART 5: Viva / Exam / Technical Interview Defense Prep

### Q1: Why not just use ChatGPT or Claude directly with a CSV file?
> **Answer:** Standard LLMs have three critical flaws when handling tabular data:
> 1. **Numerical Hallucination:** LLMs predict words probabilistically; they cannot perform deterministic multi-row sums, standard deviations, or joins. They frequently make up numbers.
> 2. **Context Window Limits:** A real-world dataset with hundreds of thousands of rows cannot fit into an LLM prompt.
> 3. **Non-Determinism:** If you ask ChatGPT the same aggregation three times, you may get three slightly different figures. In enterprise auditing, results must be reproducible and mathematically verifiable.

### Q2: Why did you choose LangGraph instead of standard LangChain or AutoGen?
> **Answer:** LangGraph provides a **stateful, cyclic state machine** that gives full deterministic control over routing. In standard autonomous agent frameworks (like AutoGen or unconstrained ReAct loops), agents can wander off, call arbitrary tools in unexpected orders, or enter infinite loops. With LangGraph:
> - Intent routing is strictly controlled.
> - The graph explicitly branches based on whether the query needs documentation RAG or numeric aggregation.
> - Facts are verified and grounded before ever returning to the user.

### Q3: Why do you have both a "Raw" and a "Normalized" DataFrame?
> **Answer:** If you immediately convert a column to numeric or datetime in Pandas, unparseable entries (like `"not available"` in a price column or `"2026-02-30"` in a date column) are silently converted to `NaN` (blank). If you do that, you destroy the evidence of user error!
> - The **`raw` frame** preserves every character as text, allowing DataSleuth to report: *"Row T0063 contains 'not available' in a numeric field"*.
> - The **`norm` frame** coerces valid numbers and dates so that aggregations and statistical math can run smoothly.

### Q4: How does the Grounding Verifier prevent hallucinations?
> **Answer:** In `nodes.py`, the `check_grounding` function extracts every single numeric token (and its decimal precision) from the LLM's response using regex. It checks every number against a whitelist of numbers that were directly generated by the Python tool execution, the user's prompt, or retrieved document chunks. If even one ungrounded number is found, the LLM response is discarded and replaced with a deterministic text summary produced directly from the tool's raw data.

### Q5: Why Groq for the LLM and Gemini for Embeddings?
> **Answer:**
> - **Groq (`openai/gpt-oss-120b`):** Groq's custom LPU (Language Processing Unit) hardware provides blazing-fast inference speeds ($\approx 500\text{--}800$ tokens/second). Because our LLM is only phrasing pre-computed facts, Groq delivers near-instantaneous responses ($\approx 1$ second total roundtrip).
> - **Google Gemini (`gemini-embedding-2`):** Generates state-of-the-art 3,072-dimensional vector embeddings with deep semantic understanding of technical terms, acronyms, and enterprise data dictionaries.

### Q6: How is data isolation maintained in ChromaDB?
> **Answer:** Every document chunk ingested into ChromaDB is tagged with metadata containing its `dataset_id`. When retrieval runs for Dataset A, the query contains a strict metadata filter: `{"dataset_id": dataset_id}`. This mathematically guarantees that queries on one dataset can never retrieve or leak confidential business rules or schemas from another dataset.

---

## 🏆 Summary Checklist: Key Highlights of DataSleuth

- ✅ **Zero Hallucination Guarantee:** Strict decoupling of computation (Pandas) from presentation (Groq).
- ✅ **Active Grounding Guardrail:** Automated regex interceptor catches and suppresses fabricated numbers.
- ✅ **Four-Pillar Quality Audit:** Separates blanks, corrupted values, duplicate primary keys, and statistical outliers.
- ✅ **Plain-English Business Rules:** Regex compliance engine tests dataset against user policies.
- ✅ **Multimodal Document RAG:** Gemini 3072d embeddings + ChromaDB with namespace isolation.
- ✅ **82 Automated Tests:** 100% passing test suite verifying audit correctness, vector self-healing, and security.
- ✅ **Production Cloud Deployment:** Live on Vercel (Frontend) and Render (Backend).

