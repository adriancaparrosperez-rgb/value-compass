from __future__ import annotations

import pytest

from src.domain import (
    DataIssue,
    DimensionScore,
    FieldProvenance,
    IssueCategory,
    IssueSeverity,
    MetricAssessment,
)


def test_data_issue_normalizes_and_serializes() -> None:
    issue = DataIssue(
        code=" missing_price ",
        category=IssueCategory.MISSING_DATA,
        severity=IssueSeverity.CRITICAL,
        message=" Falta el precio. ",
        field_name=" price ",
        provider=" yahoo ",
        recoverable=True,
    )

    assert issue.code == "MISSING_PRICE"
    assert issue.message == "Falta el precio."
    assert issue.field_name == "price"
    assert issue.provider == "yahoo"

    assert issue.to_dict()["category"] == (
        "DATO AUSENTE"
    )


def test_data_issue_rejects_invalid_enums() -> None:
    with pytest.raises(
        ValueError,
        match="IssueCategory",
    ):
        DataIssue(
            code="ERROR",
            category="INVALID",  # type: ignore[arg-type]
            severity=IssueSeverity.ERROR,
            message="Error.",
        )


def test_field_provenance_normalizes_dates_and_score() -> None:
    provenance = FieldProvenance(
        field_name=" free_cash_flow ",
        provider=" annual_report ",
        as_of="2025-12-31T00:00:00Z",
        retrieved_at="2026-02-01T10:00:00+00:00",
        is_official=True,
        is_validated=True,
        quality_score=120,
        notes=[
            " Dato auditado ",
            "dato auditado",
        ],
    )

    assert provenance.field_name == "free_cash_flow"
    assert provenance.provider == "annual_report"
    assert provenance.quality_score == 100.0
    assert provenance.notes == [
        "Dato auditado",
    ]
    assert provenance.as_of == (
        "2025-12-31T00:00:00+00:00"
    )


def test_field_provenance_rejects_invalid_date() -> None:
    with pytest.raises(
        ValueError,
        match="ISO-8601",
    ):
        FieldProvenance(
            field_name="price",
            provider="provider",
            as_of="not-a-date",
        )


def test_metric_assessment_does_not_invent_score() -> None:
    metric = MetricAssessment(
        code="pe_ratio",
        raw_value=None,
        score=75.0,
        coverage=100.0,
        confidence=90.0,
        observed=False,
        valid=True,
    )

    assert metric.observed is False
    assert metric.valid is False
    assert metric.score is None
    assert metric.available is False


def test_metric_assessment_preserves_valid_observation() -> None:
    metric = MetricAssessment(
        code="free_cash_flow_yield",
        raw_value=0.06,
        score=78.0,
        coverage=100.0,
        confidence=80.0,
        observed=True,
        valid=True,
        weight=0.20,
        weighted_contribution=15.6,
    )

    assert metric.available is True
    assert metric.score == 78.0
    assert metric.weight == pytest.approx(0.20)
    assert (
        metric.weighted_contribution
        == pytest.approx(15.6)
    )


def test_metric_assessment_rejects_invalid_issue_list() -> None:
    with pytest.raises(
        ValueError,
        match="DataIssue",
    ):
        MetricAssessment(
            code="metric",
            issues=[
                "invalid",  # type: ignore[list-item]
            ],
        )


def test_dimension_score_combines_score_and_coverage() -> None:
    metric = MetricAssessment(
        code="net_debt_to_ebitda",
        raw_value=1.5,
        score=80.0,
        coverage=100.0,
        confidence=85.0,
        observed=True,
        valid=True,
    )

    dimension = DimensionScore(
        code="financial_resilience",
        score=80.0,
        coverage=75.0,
        confidence=82.0,
        observed=True,
        valid=True,
        nominal_weight=0.15,
        effective_weight=0.1125,
        weighted_contribution=9.0,
        metrics={
            "net_debt_to_ebitda": metric,
        },
        missing_metrics=[
            "interest_coverage",
            "interest_coverage",
        ],
    )

    assert dimension.available is True
    assert dimension.score == 80.0
    assert dimension.coverage == 75.0
    assert dimension.observed_metric_count == 1
    assert dimension.available_metric_count == 1
    assert dimension.missing_metrics == [
        "interest_coverage",
    ]


def test_dimension_score_does_not_convert_missing_to_neutral() -> None:
    dimension = DimensionScore(
        code="valuation",
        score=50.0,
        coverage=0.0,
        observed=False,
        valid=True,
    )

    assert dimension.valid is False
    assert dimension.score is None
    assert dimension.available is False


def test_dimension_score_rejects_invalid_metrics() -> None:
    with pytest.raises(
        ValueError,
        match="MetricAssessment",
    ):
        DimensionScore(
            code="quality",
            metrics={
                "invalid": object(),  # type: ignore[dict-item]
            },
        )


def test_nested_contract_serialization() -> None:
    issue = DataIssue(
        code="STALE_DATA",
        category=IssueCategory.STALE_DATA,
        severity=IssueSeverity.WARNING,
        message="Dato antiguo.",
    )

    metric = MetricAssessment(
        code="revenue_growth",
        raw_value=0.08,
        score=65.0,
        coverage=100.0,
        confidence=70.0,
        observed=True,
        valid=True,
        issues=[
            issue,
        ],
    )

    dimension = DimensionScore(
        code="growth",
        score=65.0,
        coverage=50.0,
        confidence=70.0,
        observed=True,
        valid=True,
        metrics={
            "revenue_growth": metric,
        },
    )

    payload = dimension.to_dict()

    assert payload["code"] == "growth"
    assert payload["score"] == 65.0
    assert (
        payload["metrics"]["revenue_growth"]["issues"][0][
            "severity"
        ]
        == "ADVERTENCIA"
    )
