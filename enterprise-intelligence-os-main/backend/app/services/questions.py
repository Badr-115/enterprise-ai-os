from __future__ import annotations

import re
import uuid
from collections import defaultdict
from typing import Any


NUMERIC_ALIASES = {
    "revenue": ("revenue", "sales", "إيراد", "الإيرادات", "مبيعات", "المبيعات"),
    "cost": ("cost", "expense", "تكلفة", "التكلفة", "مصروف"),
    "units": ("units", "quantity", "volume", "وحدات", "الوحدات", "كمية"),
}
GROUP_WORDS = ("category", "department", "product", "region", "group", "الفئة", "التصنيف", "القسم", "المنتج", "المنطقة")


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _evidence(row: int | None, field: str, value: Any, explanation: str) -> dict[str, Any]:
    return {"row": row, "field": field, "value": value, "explanation": explanation}


def _metric(question: str, columns: list[str]) -> str:
    lowered = question.casefold()
    numeric_columns = [column for column in columns if column in NUMERIC_ALIASES]
    for column in numeric_columns:
        if column.casefold() in lowered:
            return column
    for column, words in NUMERIC_ALIASES.items():
        if column in columns and any(word in lowered for word in words):
            return column
    return "revenue" if "revenue" in columns else (numeric_columns[0] if numeric_columns else "revenue")


def _group_column(question: str, columns: list[str]) -> str | None:
    candidates = [c for c in columns if c not in {"date", "revenue", "cost", "units"}]
    lowered = question.casefold()
    return next((c for c in candidates if c.casefold() in lowered), candidates[0] if any(w in lowered for w in GROUP_WORDS) and candidates else None)


def _base(dataset: dict[str, Any], question: str, intent: str, answer: str, calculations: list[str], evidence: list[dict[str, Any]], limitations: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex, "dataset_id": dataset["id"], "question": question,
        "status": "completed", "intent": intent, "answer": answer,
        "calculations": calculations, "evidence": evidence[:21],
        "assumptions": ["تم استخدام القيم الرقمية الصالحة فقط، مع إبقاء المصدر الأصلي دون تعديل."],
        "limitations": limitations or ["النتيجة وصفية ولا تثبت السببية أو تتنبأ بالمستقبل."],
    }


def answer_question(dataset: dict[str, Any], question: str) -> dict[str, Any]:
    records = dataset.get("records") or []
    columns = dataset.get("columns") or []
    normalized = question.casefold()
    if any(word in normalized for word in ("unsupported", "forecast", "predict", "تنبؤ", "توقع")):
        return _unsupported(dataset, question, "هذا النوع من التنبؤ غير مدعوم؛ اختر عملية وصفية موثقة من القائمة المتاحة.")
    if any(word in normalized for word in ("missing", "null", "quality", "duplicate", "جودة", "مفقود", "مفقودة", "مكررة")):
        quality = dataset.get("quality") or {}
        return _base(dataset, question, "data_quality", f"تم رصد {quality.get('issue_count', 0)} ملاحظات جودة تؤثر في {quality.get('rows_affected', 0)} صفًا.",
                     ["تم الاعتماد على فحص الجودة المحفوظ عند الاستيراد."],
                     [_evidence(None, "dataset.quality", quality, "ملخص فحص الجودة")],
                     ["لا يتم تصحيح المصدر تلقائيًا."])

    metric = _metric(normalized, columns)
    values = [(i + 2, _number(row.get(metric)), row) for i, row in enumerate(records)]
    valid = [(row_no, value, row) for row_no, value, row in values if value is not None]
    if not valid:
        return _unsupported(dataset, question, f"لا توجد قيم رقمية صالحة في العمود {metric}.")

    group = _group_column(normalized, columns)
    if group and any(w in normalized for w in GROUP_WORDS + (" by ", "حسب")) and not any(word in normalized for word in ("compare", "comparison", "مقارنة", " مقابل ", " vs ")):
        totals: dict[str, float] = defaultdict(float)
        rows_by_group: dict[str, list[int]] = defaultdict(list)
        for row_no, value, row in valid:
            key = str(row.get(group) or "غير مصنف")
            totals[key] += value
            rows_by_group[key].append(row_no)
        ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        return _base(dataset, question, "grouping", f"إجمالي {metric} حسب {group}: " + "، ".join(f"{key}={value:,.2f}" for key, value in ranked),
                     [f"تم تجميع {metric} حسب {group}.", f"تم استخدام {len(valid)} صفًا رقميًا صالحًا."],
                     [_evidence(None, "dataset.content_hash", dataset.get("content_hash"), "بصمة المصدر"),
                      *[_evidence(row, group, ranked[0][0], "صف ضمن المجموعة الأعلى") for row in rows_by_group[ranked[0][0]][:20]]])

    if any(word in normalized for word in ("trend", "over time", "daily", "اتجاه", "زمني", "يومي", "تغير", "change")):
        dated = [(str(row.get("date")), value, row_no) for row_no, value, row in valid if row.get("date")]
        if len(dated) < 2:
            return _unsupported(dataset, question, "لا يمكن حساب الاتجاه دون سجلين مؤرخين بقيم صالحة.")
        dated.sort(key=lambda item: item[0])
        first, last = dated[0], dated[-1]
        change = last[1] - first[1]
        return _base(dataset, question, "trend", f"تغير {metric} من {first[1]:,.2f} في {first[0]} إلى {last[1]:,.2f} في {last[0]} ({change:+,.2f}).",
                     ["تم ترتيب السجلات حسب التاريخ ثم مقارنة أول وآخر قيمة صالحة."],
                     [_evidence(first[2], metric, first[1], f"بداية الاتجاه: {first[0]}"), _evidence(last[2], metric, last[1], f"نهاية الاتجاه: {last[0]}")])

    if any(word in normalized for word in ("compare", "comparison", "مقارنة", " مقابل ", " vs ")):
        group_candidates = [c for c in columns if c not in {"date", "revenue", "cost", "units"}]
        compare_group = next((c for c in group_candidates if c.casefold() in normalized), None)
        if compare_group is None:
            compare_group = next(
                (c for c in group_candidates
                 if sum(1 for row in records if str(row.get(c) or "").casefold() in normalized) >= 2),
                None,
            )
        if compare_group:
            groups: dict[str, float] = defaultdict(float)
            rows_by_group: dict[str, int] = {}
            for row_no, value, row in valid:
                key = str(row.get(compare_group) or "غير مصنف")
                if key.casefold() in normalized:
                    groups[key] += value
                    rows_by_group[key] = row_no
            if len(groups) >= 2:
                return _base(dataset, question, "comparison",
                             "، ".join(f"{key}={value:,.2f}" for key, value in groups.items()),
                             [f"تمت مقارنة {metric} حسب {compare_group} للقيم المذكورة في السؤال."],
                             [_evidence(rows_by_group[key], compare_group, key, "مجموعة المقارنة") for key in groups])
        return _base(dataset, question, "comparison", f"الفرق بين أعلى وأدنى قيمة في {metric} هو {max(v for _, v, _ in valid)-min(v for _, v, _ in valid):,.2f}.",
                     ["تمت مقارنة القيم الرقمية الصالحة في المصدر."],
                     [_evidence(max(valid, key=lambda item: item[1])[0], metric, max(v for _, v, _ in valid), "أعلى قيمة"),
                      _evidence(min(valid, key=lambda item: item[1])[0], metric, min(v for _, v, _ in valid), "أدنى قيمة")])

    if any(word in normalized for word in ("average", "avg", "mean", "متوسط", "معدل")):
        result, intent = sum(v for _, v, _ in valid) / len(valid), "average"
        label = "المتوسط"
    elif any(word in normalized for word in ("minimum", "min", "lowest", "أدنى", "أقل", "أصغر")):
        result, intent = min(v for _, v, _ in valid), "minimum"
        label = "الحد الأدنى"
    elif any(word in normalized for word in ("maximum", "max", "highest", "أعلى", "أكبر")):
        result, intent = max(v for _, v, _ in valid), "maximum"
        label = "الحد الأقصى"
    else:
        result, intent = sum(v for _, v, _ in valid), "total"
        label = "الإجمالي"
    selected = valid[0] if intent == "total" else (min(valid, key=lambda item: item[1]) if intent == "minimum" else max(valid, key=lambda item: item[1]))
    return _base(dataset, question, intent, f"{label} لـ {metric}: {result:,.2f}.",
                 [f"تم حساب {label.lower()} من {len(valid)} قيمة رقمية صالحة في {metric}."] ,
                 [_evidence(None, "dataset.content_hash", dataset.get("content_hash"), "بصمة المصدر"),
                  _evidence(selected[0], metric, selected[1], f"قيمة ممثلة لعملية {intent}")])


def _unsupported(dataset: dict[str, Any], question: str, answer: str) -> dict[str, Any]:
    return {"id": uuid.uuid4().hex, "dataset_id": dataset["id"], "question": question, "status": "unsupported",
            "intent": "unsupported", "answer": answer,
            "calculations": [], "evidence": [], "assumptions": [],
            "limitations": ["لم يتم تنفيذ عملية غير موجودة في قائمة التحليلات المدعومة."]}
