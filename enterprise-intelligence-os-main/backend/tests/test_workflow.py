from types import SimpleNamespace

from app.agents.workflow import run_workflow, verify_claims


def make_dataset(*, gross_margin=250.0, anomalies=None, quality=None):
    return SimpleNamespace(
        rows=12,
        kpis={
            "total_revenue": 1000.0,
            "total_cost": 750.0,
            "gross_margin": gross_margin,
            "margin_rate": 25.0,
            "total_units": 20.0,
        },
        warnings=["1 missing date"],
        anomalies=anomalies or [],
        quality=quality or {"issues": [], "issue_count": 0, "has_blocking_issues": False},
    )


def test_workflow_returns_bounded_stages_and_evidence_references():
    result = run_workflow(make_dataset(), "Summarize revenue")

    assert result["status"] == "completed"
    assert result["simulated"] is True  # No provider key in test environment.
    assert [event["agent"] for event in result["executions"]][:4] == [
        "Orchestrator", "Business Analyst", "Risk Analyst", "Verification"
    ]
    assert result["verification"]["approved"] is True
    assert all("evidence" in finding for finding in result["report"]["findings"])
    assert "لا تثبت السببية" in result["report"]["limitations"][0]


def test_negative_margin_adds_contextual_risk_finding():
    result = run_workflow(make_dataset(gross_margin=-25.0), "Review profitability")

    assert any("الهامش الإجمالي سالب" in finding["text"] for finding in result["report"]["findings"])
    assert any("تحقق من تسجيل التكاليف" in item for item in result["report"]["recommendations"])


def test_outliers_are_described_as_review_signals_not_proof():
    dataset = make_dataset(anomalies=[{"row": 7, "metric": "revenue", "value": 9000.0}])
    result = run_workflow(dataset, "Find risks")

    assert any("ليست إثباتًا" in finding["text"] for finding in result["report"]["findings"])
    risk = next(event for event in result["executions"] if event["agent"] == "Risk Analyst")
    assert "ليست إثباتًا" in risk["output"]["interpretation"]


def test_verify_claims_checks_all_reported_core_kpis():
    dataset = make_dataset()
    approved, claims = verify_claims(dataset)

    assert approved is True
    assert {claim["metric"] for claim in claims} == {"total_revenue", "total_cost", "gross_margin", "total_units", "margin_rate"}


def test_verification_rejects_missing_core_metric():
    dataset = make_dataset()
    dataset.kpis.pop("total_cost")

    approved, claims = verify_claims(dataset)

    assert approved is False
    assert next(claim for claim in claims if claim["metric"] == "total_cost")["valid"] is False
