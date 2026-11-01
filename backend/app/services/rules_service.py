"""Business-rule extraction and deterministic evaluation.

Rules are matched against a fixed set of supported patterns. Anything that does not match
is reported as unsupported instead of being guessed at. The LLM never evaluates rules.
"""

import re
from dataclasses import dataclass

import pandas as pd

from app.models.schemas import Finding, UnsupportedRule


@dataclass
class ParsedRule:
    statement: str
    kind: str
    column: str | None = None
    column2: str | None = None
    low: float | None = None
    high: float | None = None


_COL = r"([A-Za-z_][A-Za-z0-9_ ]*?)"


def _norm_col(raw: str, columns: list[str]) -> str | None:
    """Map a phrase from the rule text to an actual dataset column."""
    key = re.sub(r"[\s\-]+", "_", raw.strip().lower())
    lookup = {c.lower(): c for c in columns}
    if key in lookup:
        return lookup[key]
    # allow plural forms, e.g. "customer ids" -> customer_id
    key_singular = key[:-1] if key.endswith("s") else key
    if key_singular in lookup:
        return lookup[key_singular]
    # allow a qualifier prefix, e.g. "transaction amount" -> amount
    for col_key, col in lookup.items():
        if key_singular.endswith("_" + col_key) or key_singular.endswith(col_key):
            return col
    return None


def parse_rules(text: str, columns: list[str]) -> tuple[list[ParsedRule], list[UnsupportedRule]]:
    parsed: list[ParsedRule] = []
    unsupported: list[UnsupportedRule] = []
    for raw_line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", raw_line).strip()
        if not line or line.startswith("#"):
            continue
        rule = _match(line, columns)
        if rule is None:
            unsupported.append(UnsupportedRule(rule=line, reason="No supported rule pattern matched, or column not found in dataset."))
        else:
            parsed.append(rule)
    return parsed, unsupported


def _match(line: str, columns: list[str]) -> ParsedRule | None:
    l = line.rstrip(".").strip()

    m = re.fullmatch(rf"{_COL} must be positive", l, re.I) or re.fullmatch(rf"{_COL} must be greater than zero", l, re.I)
    if m:
        col = _norm_col(m.group(1), columns)
        return ParsedRule(line, "positive", column=col) if col else None

    m = re.fullmatch(rf"{_COL} must not be negative", l, re.I)
    if m:
        col = _norm_col(m.group(1), columns)
        return ParsedRule(line, "non_negative", column=col) if col else None

    m = re.fullmatch(rf"{_COL} must be unique", l, re.I) or re.fullmatch(rf"{_COL} must be unique values?", l, re.I)
    if m:
        col = _norm_col(m.group(1), columns)
        return ParsedRule(line, "unique", column=col) if col else None

    m = re.fullmatch(rf"{_COL} must be between (-?\d+(?:\.\d+)?) and (-?\d+(?:\.\d+)?)", l, re.I)
    if m:
        col = _norm_col(m.group(1), columns)
        return ParsedRule(line, "range", column=col, low=float(m.group(2)), high=float(m.group(3))) if col else None

    m = re.fullmatch(rf"{_COL} must not be later than {_COL}", l, re.I)
    if m:
        c1, c2 = _norm_col(m.group(1), columns), _norm_col(m.group(2), columns)
        return ParsedRule(line, "not_after", column=c1, column2=c2) if c1 and c2 else None

    return None


def evaluate_rule(rule: ParsedRule, df: pd.DataFrame, ids_start: int) -> Finding | None:
    """Returns a Finding for each violation, or None when the rule holds."""
    failing: pd.Series | None = None
    desc = ""
    action = "Correct the records that violate this business rule at the source."
    if rule.kind in ("positive", "non_negative", "range", "unique") and rule.column is None:
        return None
    if rule.kind == "positive":
        s = pd.to_numeric(df[rule.column], errors="coerce")
        failing = s.notna() & (s <= 0)
        desc = f"Rule '{rule.statement}': {int(failing.sum())} value(s) in '{rule.column}' are not positive."
    elif rule.kind == "non_negative":
        s = pd.to_numeric(df[rule.column], errors="coerce")
        failing = s.notna() & (s < 0)
        desc = f"Rule '{rule.statement}': {int(failing.sum())} value(s) in '{rule.column}' are negative."
    elif rule.kind == "range":
        s = pd.to_numeric(df[rule.column], errors="coerce")
        failing = s.notna() & ((s < rule.low) | (s > rule.high))
        desc = f"Rule '{rule.statement}': {int(failing.sum())} value(s) in '{rule.column}' fall outside [{rule.low}, {rule.high}]."
    elif rule.kind == "unique":
        s = df[rule.column].dropna()
        failing = pd.Series(False, index=df.index)
        failing.loc[s[s.duplicated(keep=False)].index] = True
        desc = f"Rule '{rule.statement}': {int(failing.sum())} row(s) share a duplicated value in '{rule.column}'."
    elif rule.kind == "not_after":
        a, b = df[rule.column], df[rule.column2]
        if not (pd.api.types.is_datetime64_any_dtype(a) and pd.api.types.is_datetime64_any_dtype(b)):
            return None  # cannot evaluate reliably without date columns
        failing = a.notna() & b.notna() & (a > b)
        desc = f"Rule '{rule.statement}': {int(failing.sum())} row(s) where '{rule.column}' is later than '{rule.column2}'."
    else:
        return None

    n = int(failing.sum())
    if n == 0:
        return None
    return Finding(
        finding_id=f"R{ids_start:04d}",
        category="business_rule_violation",
        severity="high",
        column=rule.column,
        description=desc,
        affected_records=n,
        evidence={"rule": rule.statement, "row_indices": [int(i) for i in df.index[failing][:20]]},
        recommended_action=action,
    )


def evaluate_rules(text: str, df: pd.DataFrame) -> tuple[list[Finding], list[UnsupportedRule], list[str]]:
    """Returns (violations, unsupported rules, evaluated rule statements)."""
    parsed, unsupported = parse_rules(text, list(df.columns))
    violations: list[Finding] = []
    evaluated: list[str] = []
    counter = 1
    for rule in parsed:
        finding = evaluate_rule(rule, df, counter)
        evaluated.append(rule.statement)
        if finding:
            violations.append(finding)
            counter += 1
    return violations, unsupported, evaluated
