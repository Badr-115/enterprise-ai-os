from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiError(BaseModel):
    code: str
    message: str
    request_id: str


class DatasetSummary(BaseModel):
    numeric_columns: list[str] = Field(default_factory=list)
    date_range: tuple[str | None, str | None] = (None, None)


class DatasetKpis(BaseModel):
    total_revenue: float | None = None
    total_cost: float | None = None
    total_units: float | None = None
    gross_margin: float | None = None
    margin_rate: float | None = None
    daily_revenue: list[dict[str, str | float]] = Field(default_factory=list)


class Anomaly(BaseModel):
    row: int
    metric: str
    value: float
    reason: str
    bounds: list[float] | None = None


class QualityIssue(BaseModel):
    type: Literal["missing_values", "duplicate_records", "invalid_dates", "invalid_numeric", "inconsistent_categories", "outlier", "schema_problem"]
    severity: Literal["info", "warning", "error"]
    message: str
    columns: list[str]
    rows: list[int] = Field(default_factory=list)
    count: int
    details: list[str] = Field(default_factory=list)


class DataQuality(BaseModel):
    issues: list[QualityIssue] = Field(default_factory=list)
    issue_count: int = 0
    rows_affected: int = 0
    has_blocking_issues: bool = False


class DatasetResponse(BaseModel):
    id: str
    name: str
    created_at: str | None = None
    content_hash: str | None = None
    duplicate_of: str | None = None
    rows: int
    columns: list[str]
    summary: DatasetSummary
    warnings: list[str]
    kpis: DatasetKpis
    anomalies: list[Anomaly]
    preview: list[dict[str, Any]]
    quality: DataQuality


class TaskRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=3, max_length=1000)


class QuestionRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=3, max_length=500)


class QuestionEvidence(BaseModel):
    row: int | None = None
    field: str
    value: Any = None
    explanation: str


class QuestionResponse(BaseModel):
    id: str
    dataset_id: str
    question: str
    status: Literal["completed", "unsupported"]
    intent: str
    answer: str
    calculations: list[str] = Field(default_factory=list)
    evidence: list[QuestionEvidence] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AgentExecution(BaseModel):
    agent: str
    status: Literal["completed", "failed", "running"]
    started_at: str
    output: dict[str, Any] | None = None
    error: str | None = None


class ReportFinding(BaseModel):
    text: str
    evidence: list[str]


class Report(BaseModel):
    title: str
    summary: str
    findings: list[ReportFinding]
    limitations: list[str]
    recommendations: list[str] = Field(default_factory=list)
    ai_insight: str | None = None


class Verification(BaseModel):
    approved: bool
    checked_at: str | None = None
    checked_claims: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    dataset_id: str
    prompt: str
    status: Literal["completed", "failed", "running"]
    simulated: bool = True
    executions: list[AgentExecution]
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    workflow_metadata: dict[str, Any] = Field(default_factory=dict)
    report: Report | None = None
    verification: Verification | None = None
