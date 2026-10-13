"""Deterministic, read-only tools available to the bounded analysis workflow.

Tools return JSON-serializable evidence. They never mutate source data and never
accept arbitrary code, SQL, shell commands, or file paths from the language model.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable
import math
from time import perf_counter


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    summary: str
    data: dict[str, Any]
    duration_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {"tool": self.name, "ok": self.ok, "summary": self.summary,
                "duration_ms": round(self.duration_ms, 3), "data": self.data}


def _get(dataset: Any, key: str, default: Any = None) -> Any:
    if isinstance(dataset, dict):
        return dataset.get(key, default)
    return getattr(dataset, key, default)


def dataset_profile(dataset: Any) -> ToolResult:
    summary = _get(dataset, "summary", {}) or {}
    quality = _get(dataset, "quality", {}) or {}
    return ToolResult(
        name="dataset_profile", ok=True,
        summary="Created a deterministic profile from stored dataset metadata.",
        data={
            "dataset_id": _get(dataset, "id"),
            "name": _get(dataset, "name"),
            "rows": int(_get(dataset, "rows", 0) or 0),
            "columns": list(_get(dataset, "columns", []) or []),
            "date_range": summary.get("date_range") if isinstance(summary, dict) else None,
            "warning_count": len(_get(dataset, "warnings", []) or []),
            "quality_issue_count": quality.get("issue_count", 0) if isinstance(quality, dict) else 0,
        },
    )


def profitability_check(dataset: Any) -> ToolResult:
    kpis = _get(dataset, "kpis", {}) or {}
    revenue, cost = kpis.get("total_revenue"), kpis.get("total_cost")
    margin = kpis.get("gross_margin")
    valid = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (revenue, cost, margin))
    if not valid:
        return ToolResult("profitability_check", False, "Required financial metrics are missing or invalid.",
                          {"required": ["total_revenue", "total_cost", "gross_margin"]})
    return ToolResult(
        "profitability_check", True,
        "Checked revenue, cost, gross margin, and margin rate using deterministic calculations.",
        {
            "total_revenue": revenue, "total_cost": cost, "gross_margin": margin,
            "margin_rate": kpis.get("margin_rate"),
            "cost_exceeds_revenue": cost > revenue,
            "negative_margin": margin < 0,
            "evidence": ["kpis.total_revenue", "kpis.total_cost", "kpis.gross_margin", "kpis.margin_rate"],
        },
    )


def quality_audit(dataset: Any) -> ToolResult:
    quality = _get(dataset, "quality", {}) or {}
    issues = quality.get("issues", []) if isinstance(quality, dict) else []
    counts: dict[str, int] = defaultdict(int)
    severities: dict[str, int] = defaultdict(int)
    for issue in issues:
        if isinstance(issue, dict):
            counts[str(issue.get("type", "unknown"))] += int(issue.get("count", 0) or 0)
            severities[str(issue.get("severity", "unknown"))] += 1
    return ToolResult(
        "quality_audit", True, "Summarized existing data-quality findings; no source rows were modified.",
        {"issue_count": len(issues), "counts_by_type": dict(counts), "issues_by_severity": dict(severities),
         "has_blocking_issues": bool(quality.get("has_blocking_issues", False)) if isinstance(quality, dict) else False,
         "issues": issues[:20]},
    )


def anomaly_review(dataset: Any) -> ToolResult:
    anomalies = _get(dataset, "anomalies", []) or []
    return ToolResult(
        "anomaly_review", True,
        "Returned detected outliers as review candidates, not as proof of fraud or error.",
        {"count": len(anomalies), "items": anomalies[:50], "interpretation": "review_signal_not_proof"},
    )


def category_breakdown(dataset: Any, prompt: str = "") -> ToolResult:
    records = _get(dataset, "records", []) or []
    columns = list(_get(dataset, "columns", []) or [])
    numeric_names = {"date", "revenue", "cost", "units"}
    candidates = [c for c in columns if str(c).casefold() not in numeric_names]
    chosen = next((c for c in candidates if str(c).casefold() in prompt.casefold()), None)
    if chosen is None and candidates:
        chosen = candidates[0]
    if not chosen:
        return ToolResult("category_breakdown", False, "No categorical column is available for grouping.",
                          {"available_columns": columns})
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for row in records:
        if not isinstance(row, dict):
            continue
        label = str(row.get(chosen) or "غير مصنف")
        value = row.get("revenue")
        if isinstance(value, (int, float)) and math.isfinite(value):
            totals[label] += float(value)
            counts[label] += 1
    ranked = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    return ToolResult(
        "category_breakdown", True, f"Aggregated valid revenue by {chosen} without changing source data.",
        {"group_by": chosen, "groups": [{"name": name, "revenue": round(value, 2), "valid_rows": counts[name]}
                                          for name, value in ranked[:20]],
         "evidence": ["records[*].revenue", f"records[*].{chosen}"]},
    )


TOOLS: dict[str, Callable[..., ToolResult]] = {
    "dataset_profile": dataset_profile,
    "profitability_check": profitability_check,
    "quality_audit": quality_audit,
    "anomaly_review": anomaly_review,
    "category_breakdown": category_breakdown,
}


def select_tools(prompt: str, dataset: Any) -> list[ToolResult]:
    """Choose a bounded set of read-only tools using transparent intent rules."""
    text = (prompt or "").casefold()
    selected: list[ToolResult] = []

    def execute(name: str) -> None:
        started = perf_counter()
        if name == "category_breakdown":
            result = category_breakdown(dataset, prompt)
        else:
            result = TOOLS[name](dataset)
        selected.append(ToolResult(result.name, result.ok, result.summary, result.data,
                                   (perf_counter() - started) * 1000))

    execute("dataset_profile")
    execute("profitability_check")
    if any(term in text for term in ("quality", "missing", "duplicate", "جودة", "مفقود", "تكرار", "بيانات")):
        execute("quality_audit")
    if any(term in text for term in ("anomal", "outlier", "fraud", "risk", "شاذ", "مخاطر", "احتيال", "غريب")):
        execute("anomaly_review")
    if any(term in text for term in ("group", "category", "compare", "segment", "حسب", "تصنيف", "قارن", "مقارنة", "فئة")):
        execute("category_breakdown")
    return selected
