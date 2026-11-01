"""LangGraph node implementations.

Classification and tool selection are deterministic keyword routing, so the workflow is
predictable and testable. The LLM is used only to phrase the final explanation from
tool outputs that are already computed.
"""

import json
import logging
import re
from typing import Any

from app.agents.state import AgentState
from app.services import llm_client
from app.services.dataset_service import get_dataset_row
from app.services.quality_service import run_quality_checks
from app.services.rag_service import get_rules_text, retrieve
from app.services.rules_service import evaluate_rules
from app.tools.data_tools import ToolError, run_tool

logger = logging.getLogger(__name__)
MAX_RETRIES = 1

INTENT_PATTERNS: list[tuple[str, str]] = [
    ("business_rules", r"\b(violat\w*|business rule|rules?|comply|compliance)\b"),
    ("quality", r"\b(missing|null|blank|duplicate\w*|quality|outlier\w*|unusual|invalid|anomal\w*|flag\w*|issue\w*|wrong)\b"),
    ("documentation", r"\b(dictionary|documentation|document|expected format|what does .* (say|mean|represent)|definition|meaning|represent\w*)\b"),
    ("aggregation", r"\b(average|mean|sum|total|count|revenue|highest|lowest|top|by|per|monthly|month|group|maximum|minimum|correlat\w*|relationship|trend)\b"),
]


def classify(state: AgentState) -> AgentState:
    q = state["user_question"].lower()
    intent = "general"
    for name, pattern in INTENT_PATTERNS:
        if re.search(pattern, q):
            intent = name
            break
    # business-rule questions that also mention a documented term still go through rules first
    return {"intent": intent}


def validate_dataset(state: AgentState) -> AgentState:
    row = get_dataset_row(state["dataset_id"])
    if row is None:
        return {"error": "dataset_not_found", "limitations": ["The requested dataset does not exist."]}
    return {"error": None}


def retrieve_documents(state: AgentState) -> AgentState:
    try:
        hits = retrieve(state["dataset_id"], state["user_question"])
    except Exception as exc:  # provider or vector-store failure
        logger.warning("retrieval_failed type=%s", type(exc).__name__)
        return {"retrieved_documents": [],
                "limitations": [f"Document retrieval is unavailable: {type(exc).__name__}. "
                                "Check EMBEDDING_API_KEY and that documents were uploaded."]}
    if not hits:
        return {"retrieved_documents": [],
                "limitations": ["No uploaded documentation for this dataset matched the question. "
                                "Upload a data dictionary or business-rules document to answer it."]}
    return {"retrieved_documents": hits}


def _plan_tools(question: str, columns: list[str], numeric: list[str], categorical: list[str],
                dates: list[str]) -> list[dict[str, Any]]:
    q = question.lower()
    plan: list[dict[str, Any]] = []

    def find(*names):
        for n in names:
            for c in columns:
                if c.lower() == n:
                    return c
        return None

    def mentioned(cols):
        return [c for c in cols if c.lower().replace("_", " ") in q or c.lower() in q]

    if re.search(r"\bmissing|null|blank\b", q):
        plan.append({"name": "missing_values", "args": {}})
    if re.search(r"\bduplicate", q):
        named = [c for c in columns if c.lower().replace("_", " ") in q or c.lower() in q]
        id_named = [c for c in named if c.lower().endswith("id")]
        if id_named:
            plan.append({"name": "duplicate_records", "args": {"column": id_named[0]}})
        else:
            plan.append({"name": "duplicate_records", "args": {}})
    if re.search(r"\boutlier|unusual|unusually|large|anomal", q):
        target = mentioned(numeric) or ([find("amount")] if find("amount") else numeric[:1])
        if target and target[0]:
            plan.append({"name": "outlier_investigation", "args": {"column": target[0]}})
    if re.search(r"correlat|relationship|discount", q) and len(numeric) >= 2:
        m = mentioned(numeric)
        a, b = (m[0], m[1]) if len(m) >= 2 else (numeric[0], numeric[1])
        plan.append({"name": "correlation", "args": {"column_a": a, "column_b": b}})
    if re.search(r"\bmonth|monthly|trend", q) and dates and numeric:
        value = mentioned(numeric) or [find("amount") or numeric[0]]
        plan.append({"name": "monthly_aggregation",
                     "args": {"value_column": value[0], "date_column": dates[0], "agg": "sum"}})
    grouping = re.search(r"\bby\b|\bper\b|\bgroup|\beach\b|\bregion|\bcategor|\bhighest\b|\blowest\b|\btop\b", q)
    wants_total = re.search(r"\btotal\b|\bsum\b|\baverage\b|\bmean\b|\bhow much\b", q)
    if grouping and categorical:
        group = mentioned(categorical) or categorical[:1]
        value = mentioned(numeric) or [find("amount") or (numeric[0] if numeric else None)]
        agg = "mean" if "average" in q or "mean" in q else "sum"
        if group and value and value[0]:
            plan.append({"name": "grouped_aggregation",
                         "args": {"value_column": value[0], "group_by": group[0], "agg": agg, "top_n": 10,
                                  "descending": True}})
    elif wants_total and numeric:
        value = mentioned(numeric) or [find("amount") or numeric[0]]
        plan.append({"name": "column_statistics", "args": {"column": value[0]}})
    if re.search(r"\bhow many\b|\bcount\b|\brows?\b|\brecords?\b|\bcolumns?\b|\bsummar\w*|\bdescribe\b|\bdataset\b|\bsize\b", q):
        plan.append({"name": "dataset_summary", "args": {}})
    return plan


UNSUPPORTED_MESSAGE = (
    "This question is outside the analyses DataSleuth supports. It can answer questions about missing values, "
    "duplicates, invalid values, outliers, totals and averages (optionally by a column), monthly totals, "
    "correlations, dataset size, and uploaded business rules or documentation.")


def plan_analysis(state: AgentState, frames: dict) -> AgentState:
    df = frames["norm"]
    numeric = [c for c in df.columns if str(df[c].dtype).startswith(("int", "float"))]
    dates = [c for c in df.columns if str(df[c].dtype).startswith("datetime")]
    categorical = [c for c in df.columns if c not in numeric and c not in dates and df[c].nunique() <= 30]
    plan = _plan_tools(state["user_question"], list(df.columns), numeric, categorical, dates)
    if not plan:
        return {"tool_plan": [], "limitations": [UNSUPPORTED_MESSAGE]}
    return {"tool_plan": plan}


def execute_analysis(state: AgentState, frames: dict) -> AgentState:
    """Run only the planned tools. Results are the sole source of numbers in the answer."""
    df = frames["norm"]
    raw = frames["raw"]
    results: list[dict[str, Any]] = []
    limitations: list[str] = []
    for step in state.get("tool_plan", []):
        name, args = step["name"], step.get("args", {})
        try:
            output = run_tool(name, df, args, raw=raw)
            results.append({"tool": name, "args": args, "output": output})
        except ToolError as exc:
            limitations.append(f"Analysis '{name}' could not run: {exc}")
    if state.get("intent") == "quality":
        findings = run_quality_checks(df, raw)
        results.append({"tool": "quality_checks",
                        "args": {},
                        "output": {"findings": [f.model_dump() for f in findings]}})
    # Merge with limitations recorded earlier in the run; LangGraph overwrites keys by default.
    return {"analysis_results": results, "limitations": state.get("limitations", []) + limitations}


def evaluate_business_rules(state: AgentState, frames: dict) -> AgentState:
    rules_text = get_rules_text(state["dataset_id"])
    if not rules_text:
        return {"limitations": ["No business-rules document has been uploaded for this dataset."],
                "analysis_results": []}
    violations, unsupported, evaluated = evaluate_rules(rules_text, frames["norm"])
    return {
        "analysis_results": [{"tool": "business_rule_validation", "args": {},
                              "output": {"evaluated_rules": evaluated,
                                         "violations": [v.model_dump() for v in violations],
                                         "unsupported_rules": [u.model_dump() for u in unsupported]}}],
    }


def verify(state: AgentState, frames: dict) -> AgentState:
    """Checks that every number the answer may use comes from a tool result, and that the dataset matches."""
    problems: list[str] = []
    if state.get("error"):
        problems.append(state["error"])
    row = get_dataset_row(state["dataset_id"])
    if row is None:
        problems.append("dataset_mismatch")
    for result in state.get("analysis_results", []):
        if result.get("output") is None:
            problems.append(f"empty_output:{result.get('tool')}")
    intent = state.get("intent")
    unsupported = UNSUPPORTED_MESSAGE in state.get("limitations", [])
    if intent in ("aggregation", "quality") and not state.get("analysis_results") and not state.get("retrieved_documents"):
        problems.append("no_grounded_result")
    if unsupported:
        problems = [p for p in problems if p != "no_grounded_result"]  # honest refusal, nothing to ground
    ok = not problems
    return {"validation_results": {"ok": ok, "problems": problems},
            "retries": state.get("retries", 0) + (0 if ok else 1)}


def generate_response(state: AgentState) -> AgentState:
    """Writes the explanation. The prompt contains only computed results and retrieved text."""
    facts = {
        "question": state["user_question"],
        "intent": state.get("intent"),
        "analysis_results": state.get("analysis_results", []),
        "documents": [{"text": d["text"], "filename": d["filename"], "page": d.get("page"),
                       "section": d.get("section")} for d in state.get("retrieved_documents", [])],
        "limitations": state.get("limitations", []),
    }
    answer = _deterministic_summary(facts)
    try:
        if facts["analysis_results"] or facts["documents"]:
            system = ("You explain analysis results to a data analyst. Use ONLY the numbers in the JSON "
                      "provided. Never invent figures or sources. If the JSON lacks the answer, say so.")
            answer = llm_client.chat(system, json.dumps(facts, default=str)[:12000])
    except llm_client.ProviderNotConfigured:
        answer = answer + "\n\n(LLM explanation unavailable: LLM_API_KEY is not configured.)"
    except llm_client.ProviderError:
        answer = answer + "\n\n(LLM explanation unavailable: the provider request failed.)"
    return {"final_response": answer, "citations": _citations(state.get("retrieved_documents", []))}


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _figures(text: str) -> list[tuple[float, int]]:
    """Every number in the text as (absolute value, decimal places). Thousands separators are ignored."""
    out = []
    for token in _NUMBER.findall(text.replace(",", "")):
        decimals = len(token.split(".")[1]) if "." in token else 0
        out.append((abs(float(token)), decimals))
    return out


def check_grounding(state: AgentState) -> AgentState:
    """Every figure in the final text must appear in tool output, the question, or retrieved text.

    If the LLM wrote a figure that is not supported, the deterministic summary (built only from
    tool output) replaces it, and the replacement is recorded as a limitation.
    """
    answer = state.get("final_response", "")
    evidence = " ".join([
        json.dumps(state.get("analysis_results", []), default=str),
        state.get("user_question", ""),
        " ".join(d["text"] for d in state.get("retrieved_documents", [])),
    ])
    allowed: list[float] = []
    for value, _ in _figures(evidence):
        allowed.append(value)
        if value < 1:  # percentages shown as e.g. 1.3% come from shares like 0.013
            allowed.append(round(value * 100, 6))
    unsupported = []
    for value, decimals in _figures(answer):
        tolerance = 0.5 * 10 ** -decimals
        if not any(abs(value - a) <= tolerance for a in allowed):
            unsupported.append(value)
    if not unsupported:
        return {"validation_results": {**state.get("validation_results", {}), "grounded": True}}
    facts = {"analysis_results": state.get("analysis_results", []), "documents": [],
             "limitations": state.get("limitations", [])}
    return {
        "final_response": _deterministic_summary(facts),
        "limitations": state.get("limitations", []) + [
            "The generated explanation contained figures that were not in the computed results, "
            "so the computed summary is shown instead."],
        "validation_results": {**state.get("validation_results", {}), "grounded": False},
    }


def _citations(docs: list[dict]) -> list[dict]:
    return [{"document_id": d["document_id"], "filename": d["filename"], "chunk_id": d["chunk_id"],
             "page": d.get("page"), "section": d.get("section")} for d in docs]


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _summarise_tool(r: dict[str, Any]) -> str:
    out, tool = r["output"], r["tool"]
    if tool == "missing_values":
        missing = [c for c in out["columns"] if c["missing"] > 0]
        if not missing:
            return "No missing values were found in any column."
        parts = ", ".join(f"{c['column']} ({c['missing']} missing, {c['share']:.1%})" for c in missing)
        return f"Columns with missing values: {parts}."
    if tool == "duplicate_records":
        if "column" in out:
            examples = ", ".join(f"{e['value']} (×{e['count']})" for e in out["examples"][:5])
            return (f"{out['repeated_values']} value(s) in '{out['column']}' repeat, affecting "
                    f"{out['affected_rows']} row(s): {examples}.")
        return f"{out['extra_duplicate_rows']} exact duplicate row(s) found."
    if tool == "grouped_aggregation":
        rows = out["rows"]
        head = "; ".join(f"{row[out['group_by']]}: {_fmt(row[out['agg']])}" for row in rows[:10])
        text = f"{out['agg']} of {out['value_column']} by {out['group_by']} — {head}."
        if rows and out["agg"] in ("sum", "mean") and out.get("descending", True):
            top = rows[0]
            text += f" Highest: {top[out['group_by']]} ({_fmt(top[out['agg']])})."
        return text
    if tool == "column_statistics":
        if out.get("type") == "numeric":
            return (f"'{out['column']}': total {_fmt(out['sum'])} across {out['count']} non-missing value(s); "
                    f"mean {_fmt(out['mean'])}, median {_fmt(out['median'])}, "
                    f"min {_fmt(out['min'])}, max {_fmt(out['max'])}.")
        return f"'{out['column']}': {out}"
    if tool == "monthly_aggregation":
        rows = out["rows"]
        head = "; ".join(f"{row['period']}: {_fmt(row[out['agg']])}" for row in rows)
        return f"{out['agg']} of {out['value_column']} by month — {head}."
    if tool == "correlation":
        c = out["coefficient"]
        strength = "weak" if c is None or abs(c) < 0.3 else "moderate" if abs(c) < 0.7 else "strong"
        return (f"Pearson correlation between {out['column_a']} and {out['column_b']} is "
                f"{_fmt(c)} ({strength}, {out['pairs_used']} complete pairs).")
    if tool == "outlier_investigation":
        def _name(r_):
            label = f"{out['identifier_column']} {r_['row_id']}" if r_.get("row_id") is not None else f"row {r_['row_index']}"
            return f"{label} = {_fmt(r_['value'])}"
        rows = ", ".join(_name(r_) for r_ in out["rows"][:5])
        return (f"{out['outlier_count']} value(s) in '{out['column']}' fall outside the IQR fences "
                f"[{_fmt(out['fence_low'])}, {_fmt(out['fence_high'])}]: {rows or 'none'}. "
                "These may be legitimate and need investigation.")
    if tool == "quality_checks":
        if not out["findings"]:
            return "Quality checks found no issues."
        return "Quality findings:\n" + "\n".join(f"- [{f['severity']}] {f['description']}" for f in out["findings"])
    if tool == "business_rule_validation":
        return (f"{len(out['violations'])} violation(s) across {len(out['evaluated_rules'])} evaluated rule(s)"
                f"; {len(out['unsupported_rules'])} rule(s) could not be evaluated.")
    if tool == "dataset_summary":
        distinct = ""
        if out.get("distinct_identifiers") is not None:
            distinct = f" ({out['distinct_identifiers']} distinct {out['identifier_column']} value(s))"
        return (f"The dataset has {out['row_count']} row(s){distinct} and {out['column_count']} column(s), "
                f"{out['missing_cells']} missing cell(s) and {out['duplicate_rows']} exact duplicate row(s).")
    return f"{tool}: {out}"


def _deterministic_summary(facts: dict) -> str:
    lines = [_summarise_tool(r) for r in facts["analysis_results"]]
    for d in facts["documents"]:
        where = d["filename"] + (f", page {d['page']}" if d.get("page") else "") + \
                (f", section '{d['section']}'" if d.get("section") else "")
        lines.append(f"From {where}: {d['text'][:300]}")
    lines.extend(facts["limitations"])
    return "\n".join(lines) or "No supported analysis or documentation was found for this question."


def build_chart(state: AgentState, frames: dict) -> AgentState:
    """Chart specs are built only from computed rows."""
    for r in state.get("analysis_results", []):
        if r["tool"] == "grouped_aggregation" and r["output"]["rows"]:
            out = r["output"]
            agg_key = out["agg"]
            return {"chart": {"type": "bar", "title": f"{out['agg'].title()} of {out['value_column']} by {out['group_by']}",
                              "x_label": out["group_by"], "y_label": out["value_column"],
                              "data": [{"name": row[out["group_by"]], "value": row[agg_key]} for row in out["rows"]]}}
        if r["tool"] == "monthly_aggregation" and r["output"]["rows"]:
            out = r["output"]
            agg_key = out["agg"]
            return {"chart": {"type": "line", "title": f"{out['agg'].title()} of {out['value_column']} by month",
                              "x_label": "period", "y_label": out["value_column"],
                              "data": [{"name": row["period"], "value": row[agg_key]} for row in out["rows"]]}}
    return {"chart": None}
