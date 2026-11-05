# 🎬 DataSleuth — Live Demo Presentation Script
> **A Professional Step-by-Step Walkthrough Guide for Project Demos, Evaluators, and Technical Presentations**  
> **Presenter:** Mayank Chauhan  
> **Target Duration:** 7 – 10 Minutes (Includes 3-Minute Elevator Pitch Variant)  
> **Live App:** [https://datasleuth-eight.vercel.app](https://datasleuth-eight.vercel.app)  
> **API Docs:** [https://datasleuth-qa0m.onrender.com/docs](https://datasleuth-qa0m.onrender.com/docs)  

---

## 📋 Pre-Demo Checklist (5 Minutes Before Presenting)

1. **Browser Windows Ready:**
   - [ ] Tab 1: Live Frontend Application (`https://datasleuth-eight.vercel.app` or `http://localhost:5173`)
   - [ ] Tab 2: FastAPI Swagger Docs (`https://datasleuth-qa0m.onrender.com/docs`)
   - [ ] Tab 3: GitHub Repository (`https://github.com/Mayank08082004/datasleuth`)
2. **API Key Setup:**
   - [ ] Ensure your `DATASLEUTH_API_KEY` is pasted in the sidebar and saved.
3. **Demo Files Ready on Desktop / Quick Access:**
   - [ ] `backend/sample_data/transactions.csv` (The 76-row test dataset with deliberate real-world flaws)
   - [ ] `backend/sample_data/data_dictionary.md` (Metadata and column definitions)
   - [ ] `backend/sample_data/business_rules.md` (Plain-English enterprise compliance policies)
4. **Mental Mode:**
   - Speak with calm confidence. Remember: **The system does not hallucinate. Every number is grounded in Python.** If you forget a number, look at the screen—the exact computation is right there.

---

## ⏱️ Live Presentation Flow Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 00:00 - 01:00  │ ACT 1: The Hook & The Problem (Why ChatGPT fails at CSVs) │
├────────────────┼─────────────────────────────────────────────────────────────┤
│ 01:00 - 02:30  │ ACT 2: File Ingestion & The Dual-DataFrame Trick            │
├────────────────┼─────────────────────────────────────────────────────────────┤
│ 02:30 - 04:15  │ ACT 3: The 4-Pillar Automated Quality Audit (Live Anomalies)│
├────────────────┼─────────────────────────────────────────────────────────────┤
│ 04:15 - 05:45  │ ACT 4: Dataset-Scoped RAG & Business Rules Ingestion        │
├────────────────┼─────────────────────────────────────────────────────────────┤
│ 05:45 - 08:30  │ ACT 5: "Ask DataSleuth" — LangGraph, Recharts & Grounding   │
├────────────────┼─────────────────────────────────────────────────────────────┤
│ 08:30 - 09:30  │ ACT 6: Downloadable Reports, Cloud Architecture & Wrap-Up   │
├────────────────┼─────────────────────────────────────────────────────────────┤
│ 09:30 - 12:00  │ ACT 7: Q&A Defense & Evaluator Questions                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎭 ACT 1: The Hook & The Problem (00:00 – 01:00)

### 🖱️ Screen View:
Show the **DataSleuth Dashboard** homepage on your browser.

### 🗣️ What to Say (Word-for-Word):
> *"Good morning/afternoon, professors and evaluators. My name is Mayank Chauhan, and today I am presenting **DataSleuth: An AI-Powered Dataset Exploration and Data Quality Auditor**.*
>
> *To understand why DataSleuth exists, imagine giving a corporate finance spreadsheet with 50,000 transactions to ChatGPT and asking: 'What was our total revenue in the North region, and were there any duplicate invoices?'*
>
> *ChatGPT will answer with absolute confidence—**and almost certainly make up the number**. Large Language Models are text prediction engines, not calculators. In financial auditing, healthcare, or enterprise compliance, a fabricated number is unacceptable.*
>
> *DataSleuth solves this through one foundational rule: **Absolute Numerical Determinism**. Every single aggregation, outlier, and quality check is computed strictly in Python using Pandas and NumPy. The LLM is used only to interpret and explain verified facts, backed by an active Grounding Guardrail that intercepts and suppresses any hallucination.*
>
> *Let me demonstrate this live."*

---

## 📂 ACT 2: File Ingestion & Dual-Frame Profiling (01:00 – 02:30)

### 🖱️ What to Click:
1. On the **Dashboard**, click on the file upload card (`"Choose a file"`).
2. Select `transactions.csv` from your desktop.
3. Watch the app instantly redirect to the **Dataset Overview** (`/datasets/:id`).

### 🖥️ What the Audience Sees:
- Total rows (76), total columns (8), memory footprint.
- A paginated data preview table with columns: `transaction_id`, `customer_id`, `transaction_date`, `region`, `product_category`, `quantity`, `unit_price`, `amount`.
- Column chips showing inferred data types.

### 🗣️ What to Say:
> *"Here, I have just uploaded our real-world transactions dataset. In less than a second, DataSleuth has parsed, typed, and profiled every column.*
>
> *Under the hood, DataSleuth does something unique that standard tools miss. It creates **two simultaneous DataFrames**:*
> 1. *A **Raw DataFrame** that stores every cell as raw text. It preserves leading zeros, and critical dirty values like the text string `'not available'` or the impossible date `'2026-02-30'`.*
> 2. *A **Normalized DataFrame** where clean columns are converted to mathematical numbers and datetimes.*
>
> *Why keep both? Because if you coerce data immediately like standard Pandas does, corrupted text is converted into blank NaNs—and you erase the evidence of bad data. DataSleuth keeps the evidence."*

---

## 🔬 ACT 3: The 4-Pillar Automated Quality Audit (02:30 – 04:15)

### 🖱️ What to Click:
Click on the **"Quality"** tab in the top navigation or sidebar.

### 🖥️ What the Audience Sees:
Cards organized by severity badges (🔴 High, 🟡 Medium, 🔵 Low) across the four pillars:
- **Missing Values:** Blank `customer_id` and blank `quantity`.
- **Duplicates:** Exact duplicate row and duplicate identifier `T0001`.
- **Invalid Values:** Non-numeric entry `"not available"` in `unit_price`, and invalid date `"2026-02-30"`.
- **Outliers:** Transactions `T0021` (\$9,500.00) and `T0060` (\$15,000.00).

### 🗣️ What to Say:
> *"Now, let's open the **Data Quality** audit tab. Without running any prompts, DataSleuth has automatically audited the dataset across four mathematical pillars:*
>
> 1. ***Missing Values (Blanks):** It identifies true empty cells, like row 7 missing customer ID and row 17 missing quantity.*
> 2. ***Corrupted / Invalid Values:** Notice this card: It flags that row `T0063` contains the string `'not available'` in the numeric unit price column. And row `T0075` has a transaction date of `February 30th, 2026`—a date that does not exist in the calendar. Standard tools would crash or silently ignore this; DataSleuth isolates it and names the exact row.*
> 3. ***Duplicate Detection:** Row `T0001` was processed twice. DataSleuth catches both exact duplicate rows and primary-key identity collisions.*
> 4. ***Statistical Outliers via Tukey's IQR Method:** Rather than guessing what is 'large', DataSleuth computes the 25th and 75th percentiles to calculate Inter-Quartile Range fences:*
>    $$[Q_1 - 1.5\text{IQR}, \; Q_3 + 1.5\text{IQR}]$$
>    *It immediately isolates transactions `T0021` at \$9,500 and `T0060` at \$15,000 as statistical anomalies that warrant human investigation.*
>
> *Every single finding includes the exact record ID, row index, and a recommended remediation action."*

---

## 📚 ACT 4: Dataset-Scoped RAG & Business Rules (04:15 – 05:45)

### 🖱️ What to Click:
1. Click on the **"Documentation"** tab.
2. In the upload box, select and upload `data_dictionary.md`.
3. In the upload box, select and upload `business_rules.md`.

### 🖥️ What the Audience Sees:
- Success notifications:
  - *Indexed "data_dictionary.md" as data dictionary (8 chunks).*
  - *Indexed "business_rules.md" as business rules (2 chunks).*
- The indexed chunks list displaying section headers and token counts.

### 🗣️ What to Say:
> *"Real enterprise datasets do not exist in a vacuum; they have documentation and business rules. Here, I am uploading our **Data Dictionary** and **Business Rules**.*
>
> *How does our RAG pipeline work?*
> - *Documents are chunked into 900-character semantic blocks.*
> - *They are embedded using **Google Gemini's `gemini-embedding-2`** model, producing dense **3,072-dimensional vectors**.*
> - *They are stored in **ChromaDB** with a strict metadata tag: `dataset_id`.*
>
> *This means multi-tenant isolation is mathematically enforced: retrieval for this dataset will never leak or confuse rules from another dataset. Furthermore, if the embedding model or dimension is ever updated, our system has self-healing index recovery that avoids service disruptions."*

---

## 💬 ACT 5: "Ask DataSleuth" & The Grounding Verifier (05:45 – 08:30)

### 🖱️ What to Click:
Click on the **"Ask"** tab.

---

### 🔍 Query 1: Aggregation & Instant Recharts Visualization
#### 🖱️ Action:
Click on the suggestion chip: **"What is the average amount by region?"** (or type it in the input box and press Enter).

#### 🖥️ What the Audience Sees:
- Execution completes in $\approx 1$ second.
- A natural-language response citing the exact numbers.
- A responsive, interactive **Bar Chart** rendering `East`, `South`, `North`, and `West`.
- A green **Verified** badge.

#### 🗣️ What to Say:
> *"Watch the speed and structure here. In approximately one second:*
> 1. *Our LangGraph intent classifier routed the question to our deterministic aggregation tool.*
> 2. *Pandas computed the exact mean amount by region: East leads at \$1,031.58, followed by South, North, and West.*
> 3. *The system automatically generated a **Recharts Bar Chart specification** built strictly from the computed rows—not hallucinated by the LLM.*
> 4. *Groq's `gpt-oss-120b` synthesized the executive explanation from those exact figures."*

---

### 🔍 Query 2: Plain-English Business Rules Audit
#### 🖱️ Action:
Click on the suggestion chip: **"Does this dataset violate the uploaded business rules?"**

#### 🖥️ What the Audience Sees:
- The response states that **2 violations** were found.
- It highlights that `amount` has 2 negative values (`T0009` at `-$300.00` and `T0026` at `-$80.00`).
- It highlights that `transaction_id` violated uniqueness (`T0001`).

#### 🗣️ What to Say:
> *"Now we ask a high-level compliance question: 'Does this dataset violate our business rules?'*
>
> *Notice what happened: DataSleuth didn't ask an LLM to read the entire dataset and guess. It retrieved the uploaded rules from ChromaDB, parsed the rules using regex into boolean filters like `amount <= 0`, and evaluated them deterministically in Pandas.*
>
> *It immediately flagged transaction `T0009` with a negative amount of -\$300.00 and duplicate transaction `T0001`."*

---

### 🛡️ Query 3: Demonstrating the "Killer Feature" — Grounding Verifier
#### 🗣️ What to Say (Crucial Technical Highlight for Evaluators):
> *"Now, I want to highlight the most critical architectural innovation in DataSleuth: **The Active Grounding Verifier**.*
>
> *In `backend/app/agents/nodes.py`, we implemented a zero-tolerance grounding check. After the LLM generates its response, a regex tokenizer extracts every single numeric figure and decimal place in the text.*
>
> *It cross-checks those figures against a whitelist of numbers generated by our Python tools, the user's prompt, and retrieved documentation.*
>
> *If the LLM generates even **one ungrounded number**, DataSleuth instantly discards the LLM's text and replaces it with the deterministic Python summary, logging a limitation notice. The user is guaranteed that not a single number on screen was fabricated."*

---

## 📊 ACT 6: Downloadable Audit Reports & Closing (08:30 – 09:30)

### 🖱️ What to Click:
1. Click on the **"Reports"** tab.
2. Click **"Generate report"**.
3. Point out the overview metrics, quality findings, and business rule summaries.
4. Click **"Download JSON"** (show the downloaded JSON file in browser downloads).

### 🗣️ What to Say:
> *"Finally, we navigate to the **Reports** tab. With one click, an auditor or compliance officer can generate a comprehensive audit report and export it as structured JSON for downstream data pipelines or regulatory archiving.*
>
> *To summarize the engineering behind DataSleuth:*
> - *It combines **FastAPI**, **React 18**, **LangGraph**, **Groq**, **Google Gemini**, and **ChromaDB**.*
> - *The entire backend is verified by **82 automated pytest test suites**, covering audit correctness, vector self-healing, and prompt injection security.*
> - *It is fully deployed and accessible live today on Vercel and Render.*
>
> *Thank you, and I am now ready to take any questions."*

---

## 🎯 ACT 7: Q&A Defense — The Top 5 Hard Questions & How to Answer

### Q1: "Why not just ask ChatGPT to write Python code to analyze the data (like Code Interpreter)?"
> **Your Answer:**  
> *"Code Interpreter approaches run arbitrary generated code, which introduces three major risks:  
> 1. Code generation can crash due to syntax errors or unexpected data types.  
> 2. Executing arbitrary generated Python on enterprise servers is a severe security hazard.  
> 3. It is non-deterministic—the model might write different logic on different days.  
> DataSleuth uses a pre-audited, strongly-typed registry of safe tools. The LLM selects the tool, but the code is already verified and secure."*

### Q2: "What happens if a user uploads a dataset with 5 million rows?"
> **Your Answer:**  
> *"DataSleuth is architected for this exact scalability. The dataset is never dumped into an LLM context window. Aggregations, percentiles, and group-bys are computed out-of-core or in-memory via Pandas and NumPy vectorized C-extensions. Only the final aggregated summary table (a few hundred bytes) is sent to Groq. Thus, token cost and latency remain constant regardless of dataset size."*

### Q3: "How does your RAG system prevent data leakage between different datasets?"
> **Your Answer:**  
> *"Every chunk indexed in ChromaDB carries metadata containing the `dataset_id`. During vector retrieval in `rag_service.py`, ChromaDB enforces a strict metadata filter: `where={'dataset_id': current_dataset_id}`. This provides namespace isolation where Dataset A cannot access Dataset B's business rules or data dictionaries."*

### Q4: "Why use Groq instead of standard OpenAI or Anthropic models?"
> **Your Answer:**  
> *"Speed and cost. Because our computational logic is decoupled and handled by Pandas, the LLM is only performing linguistic synthesis. Groq's custom LPU architecture runs `gpt-oss-120b` at 500+ tokens per second, allowing complete end-to-end question answering and chart generation in under 1.5 seconds on a free cloud tier."*

### Q5: "How does the system distinguish between a missing value and an invalid value?"
> **Your Answer:**  
> *"Through our Dual-DataFrame architecture. The `raw` DataFrame keeps the original text, while the `norm` DataFrame coerces types. If a cell was empty in `raw`, it is a **Missing Value**. But if a cell had text in `raw` (like 'not available' or '2026-02-30') and became NaN in `norm`, DataSleuth flags it as an **Invalid Value** and cites the row ID."*

---

## 🆘 Emergency Contingency Plan (What If Something Goes Wrong?)

| Scenario | What to Do / Say |
|---|---|
| **Render Backend Cold Start (First request takes 30s)** | *"Render puts free instances to sleep after inactivity. While the backend wakes up, let me walk you through our architectural design on the slide / Swagger docs."* (Open Tab 2: `/docs` to trigger wakeup). |
| **Wi-Fi Disconnects or Slows Down** | Switch instantly to your local instance: open terminal, run `uvicorn app.main:app` and frontend on `http://localhost:5173`. Everything works identically locally. |
| **Evaluator Asks for an Unsupported Question (e.g. "Predict sales in 2030")** | Type it! Show the system's honest refusal: *"Notice how DataSleuth honestly explains that forecasting is outside its deterministic capabilities, rather than hallucinating an imaginary projection."* This demonstrates high robustness! |

---

### 💡 Final Tip Before You Present:
Keep this document open on your phone or on half your screen. Smile, take a breath, and let DataSleuth's deterministic results do the talking! You've got this! 🚀

