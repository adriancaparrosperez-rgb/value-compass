from __future__ import annotations

import math
from typing import Any

import pytest

from src.domain import (
    ComparabilityStatus,
    DataIssue,
    DimensionScore,
    EligibilityStatus,
    FieldProvenance,
    IssueCategory,
    IssueSeverity,
    RunStatus,
)
from src.models import (
    MODEL_SCHEMA_VERSION,
    CompanySnapshot,
    ExportArtifact,
    ExportManifest,
    ScoreCard,
    ScoringConfiguration,
    ScreeningResult,
    ScreeningRun,
)


def _score_card(
    **overrides: Any,
) -> ScoreCard:
    values: dict[str, Any] = {
        "ticker": " test ",
        "valuation": 70.0,
        "quality": 80.0,
        "cash": 75.0,
        "balance": 65.0,
        "growth": 60.0,
        "capital_allocation": 55.0,
        "momentum_fundamental": 50.0,
        "risk": 70.0,
        "confidence": 80.0,
        "global_score": 72.5,
        "recommendation": "CANDIDATA",
        "rationale": "Resultado de prueba.",
        "calculated_at": "2026-06-27T12:00:00+00:00",
        "overall_coverage": 85.0,
        "dimension_coverage": {
            "valuation": 100.0,
            "quality": 75.0,
            "cash": 80.0,
            "balance": 70.0,
            "growth": 65.0,
            "capital_allocation": 60.0,
            "momentum_fundamental": 55.0,
            "risk": 50.0,
        },
        "missing_metrics": [
            "interest_coverage",
        ],
        "warnings": [
            "Cobertura parcial.",
        ],
        "scoring_version": "1.0.0",
    }

    values.update(overrides)

    return ScoreCard(**values)


# ============================================================
# COMPANY SNAPSHOT
# ============================================================


def test_company_snapshot_preserves_valid_defaults() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )

    assert snapshot.ticker == "TEST"
    assert snapshot.name == ""
    assert snapshot.currency == ""
    assert snapshot.price is None
    assert snapshot.market_cap is None

    assert snapshot.data_quality == 0.0
    assert snapshot.coverage_score == 0.0
    assert snapshot.validity_score == 0.0
    assert snapshot.freshness_score == 0.0
    assert snapshot.consistency_score == 0.0
    assert snapshot.source_quality_score == 0.0

    assert snapshot.errors == ""
    assert snapshot.missing_fields == []
    assert snapshot.critical_missing_fields == []
    assert snapshot.warnings == []
    assert snapshot.issues == []
    assert snapshot.field_provenance == {}
    assert snapshot.provider_metadata == {}

    assert snapshot.schema_version == (
        MODEL_SCHEMA_VERSION
    )


def test_company_snapshot_normalizes_ticker() -> None:
    snapshot = CompanySnapshot(
        ticker="  itx.mc  "
    )

    assert snapshot.ticker == "ITX.MC"


@pytest.mark.parametrize(
    "ticker",
    [
        "",
        "   ",
        None,
        True,
        123,
        "META US",
    ],
)
def test_company_snapshot_rejects_invalid_ticker(
    ticker: Any,
) -> None:
    with pytest.raises(ValueError):
        CompanySnapshot(
            ticker=ticker,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-10, 0.0),
        (0, 0.0),
        (45.56, 45.6),
        (100, 100.0),
        (150, 100.0),
        (None, 0.0),
        ("75.44", 75.4),
        ("invalid", 0.0),
        (True, 0.0),
        (float("nan"), 0.0),
        (float("inf"), 0.0),
        (float("-inf"), 0.0),
    ],
)
def test_company_snapshot_bounds_quality_scores(
    value: Any,
    expected: float,
) -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        data_quality=value,
        coverage_score=value,
        validity_score=value,
        freshness_score=value,
        consistency_score=value,
        source_quality_score=value,
    )

    assert snapshot.data_quality == expected
    assert snapshot.coverage_score == expected
    assert snapshot.validity_score == expected
    assert snapshot.freshness_score == expected
    assert snapshot.consistency_score == expected
    assert snapshot.source_quality_score == expected


def test_company_snapshot_uses_legacy_data_quality_as_coverage() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        data_quality=72.0,
        coverage_score=0.0,
    )

    assert snapshot.data_quality == 72.0
    assert snapshot.coverage_score == 72.0


def test_company_snapshot_uses_coverage_as_legacy_data_quality() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        data_quality=0.0,
        coverage_score=64.0,
    )

    assert snapshot.coverage_score == 64.0
    assert snapshot.data_quality == 64.0


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        (100.0, 100.0),
        ("25.5", 25.5),
        (0.0, None),
        (-1.0, None),
        (None, None),
        (True, None),
        (float("nan"), None),
        (float("inf"), None),
    ],
)
def test_company_snapshot_accepts_only_positive_price(
    price: Any,
    expected: float | None,
) -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        price=price,
    )

    assert snapshot.price == expected


def test_company_snapshot_normalizes_financial_numbers() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        revenue="1000.5",
        total_debt=float("nan"),
        revenue_growth="0.12",
        pe=float("inf"),
    )

    assert snapshot.revenue == 1000.5
    assert snapshot.total_debt is None
    assert snapshot.revenue_growth == 0.12
    assert snapshot.pe is None


def test_company_snapshot_normalizes_analyst_count() -> None:
    valid = CompanySnapshot(
        ticker="TEST",
        analyst_count=12,
    )
    numeric_string = CompanySnapshot(
        ticker="TEST",
        analyst_count="8",  # type: ignore[arg-type]
    )
    fractional = CompanySnapshot(
        ticker="TEST",
        analyst_count=2.5,  # type: ignore[arg-type]
    )
    negative = CompanySnapshot(
        ticker="TEST",
        analyst_count=-1,
    )
    boolean = CompanySnapshot(
        ticker="TEST",
        analyst_count=True,  # type: ignore[arg-type]
    )

    assert valid.analyst_count == 12
    assert numeric_string.analyst_count == 8
    assert fractional.analyst_count is None
    assert negative.analyst_count is None
    assert boolean.analyst_count is None


def test_company_snapshot_normalizes_dates_to_utc() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        fetched_at="2026-06-27T12:00:00Z",
        price_date="2026-06-27T12:00:00",
        fundamentals_date=(
            "2026-03-31T00:00:00+00:00"
        ),
    )

    assert snapshot.fetched_at == (
        "2026-06-27T12:00:00+00:00"
    )
    assert snapshot.price_date == (
        "2026-06-27T12:00:00+00:00"
    )
    assert snapshot.fundamentals_date == (
        "2026-03-31T00:00:00+00:00"
    )


def test_company_snapshot_rejects_invalid_dates() -> None:
    with pytest.raises(
        ValueError,
        match="fetched_at",
    ):
        CompanySnapshot(
            ticker="TEST",
            fetched_at="fecha-invalida",
        )


def test_company_snapshot_has_errors_property() -> None:
    clean_snapshot = CompanySnapshot(
        ticker="TEST"
    )
    text_error_snapshot = CompanySnapshot(
        ticker="TEST",
        errors="ProviderError",
    )
    whitespace_snapshot = CompanySnapshot(
        ticker="TEST",
        errors="   ",
    )
    structured_error_snapshot = CompanySnapshot(
        ticker="TEST",
        issues=[
            DataIssue(
                code="INVALID_PRICE",
                category=IssueCategory.INVALID_DATA,
                severity=IssueSeverity.ERROR,
                message="Precio inválido.",
            )
        ],
    )

    assert clean_snapshot.has_errors is False
    assert text_error_snapshot.has_errors is True
    assert whitespace_snapshot.has_errors is False
    assert structured_error_snapshot.has_errors is True


def test_company_snapshot_has_warnings_property() -> None:
    string_warning = CompanySnapshot(
        ticker="TEST",
        warnings=[
            "Advertencia.",
        ],
    )
    structured_warning = CompanySnapshot(
        ticker="TEST",
        issues=[
            DataIssue(
                code="STALE_PRICE",
                category=IssueCategory.STALE_DATA,
                severity=IssueSeverity.WARNING,
                message="Precio antiguo.",
            )
        ],
    )
    clean_snapshot = CompanySnapshot(
        ticker="TEST"
    )

    assert clean_snapshot.has_warnings is False
    assert string_warning.has_warnings is True
    assert structured_warning.has_warnings is True


def test_company_snapshot_is_usable_with_minimum_valid_data() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        price=100.0,
    )

    assert snapshot.is_usable is True


@pytest.mark.parametrize(
    "snapshot",
    [
        CompanySnapshot(
            ticker="TEST",
            price=None,
        ),
        CompanySnapshot(
            ticker="TEST",
            price=100.0,
            critical_missing_fields=[
                "market_cap",
            ],
        ),
        CompanySnapshot(
            ticker="TEST",
            price=100.0,
            errors="Error de proveedor.",
        ),
        CompanySnapshot(
            ticker="TEST",
            price=100.0,
            issues=[
                DataIssue(
                    code="CRITICAL_CONFLICT",
                    category=(
                        IssueCategory.SOURCE_CONFLICT
                    ),
                    severity=IssueSeverity.CRITICAL,
                    message=(
                        "Conflicto crítico entre fuentes."
                    ),
                )
            ],
        ),
    ],
)
def test_company_snapshot_is_not_usable_when_blocked(
    snapshot: CompanySnapshot,
) -> None:
    assert snapshot.is_usable is False


def test_company_snapshot_add_warning() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )

    snapshot.add_warning(
        "Primera advertencia."
    )

    assert snapshot.warnings == [
        "Primera advertencia.",
    ]


def test_company_snapshot_add_warning_normalizes_and_deduplicates() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )

    snapshot.add_warning(
        "  Dato no validado.  "
    )
    snapshot.add_warning(
        "dato no validado."
    )
    snapshot.add_warning(
        "DATO NO VALIDADO."
    )
    snapshot.add_warning("")
    snapshot.add_warning("   ")
    snapshot.add_warning(
        None  # type: ignore[arg-type]
    )

    assert snapshot.warnings == [
        "Dato no validado.",
    ]


def test_company_snapshot_add_issue() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )

    issue = DataIssue(
        code="MISSING_FCF",
        category=IssueCategory.MISSING_DATA,
        severity=IssueSeverity.WARNING,
        message="Falta el flujo de caja libre.",
    )

    snapshot.add_issue(issue)

    assert snapshot.issues == [
        issue,
    ]


def test_company_snapshot_rejects_invalid_issue() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )

    with pytest.raises(
        ValueError,
        match="DataIssue",
    ):
        snapshot.add_issue(
            "invalid",  # type: ignore[arg-type]
        )


def test_company_snapshot_validates_field_provenance() -> None:
    provenance = FieldProvenance(
        field_name="free_cash_flow",
        provider="annual_report",
        is_official=True,
        is_validated=True,
        quality_score=95.0,
    )

    snapshot = CompanySnapshot(
        ticker="TEST",
        field_provenance={
            "free_cash_flow": provenance,
        },
    )

    assert snapshot.provenance_for(
        "free_cash_flow"
    ) == provenance


def test_company_snapshot_rejects_mismatched_provenance_key() -> None:
    provenance = FieldProvenance(
        field_name="revenue",
        provider="annual_report",
    )

    with pytest.raises(
        ValueError,
        match="no coincide",
    ):
        CompanySnapshot(
            ticker="TEST",
            field_provenance={
                "free_cash_flow": provenance,
            },
        )


def test_company_snapshot_to_dict_returns_v2_contract() -> None:
    provenance = FieldProvenance(
        field_name="price",
        provider="market_provider",
        quality_score=90.0,
    )

    snapshot = CompanySnapshot(
        ticker="TEST",
        name="Test Company",
        price=100.0,
        warnings=[
            "Advertencia.",
        ],
        field_provenance={
            "price": provenance,
        },
        provider_metadata={
            "used_fast_info": True,
        },
    )

    result = snapshot.to_dict()

    assert isinstance(result, dict)
    assert result["ticker"] == "TEST"
    assert result["name"] == "Test Company"
    assert result["price"] == 100.0
    assert result["schema_version"] == (
        MODEL_SCHEMA_VERSION
    )
    assert result["warnings"] == [
        "Advertencia.",
    ]
    assert result["field_provenance"]["price"][
        "provider"
    ] == "market_provider"
    assert result["provider_metadata"] == {
        "used_fast_info": True,
    }


def test_company_snapshot_to_dict_does_not_share_mutable_references() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        warnings=[
            "Advertencia.",
        ],
        provider_metadata={
            "nested": {
                "value": 1,
            },
        },
    )

    result = snapshot.to_dict()

    result["warnings"].append(
        "Nueva advertencia."
    )
    result["provider_metadata"][
        "nested"
    ]["value"] = 99

    assert snapshot.warnings == [
        "Advertencia.",
    ]
    assert snapshot.provider_metadata == {
        "nested": {
            "value": 1,
        },
    }


def test_company_snapshot_round_trip_from_dict() -> None:
    original = CompanySnapshot(
        ticker="TEST",
        price=100.0,
        coverage_score=80.0,
        issues=[
            DataIssue(
                code="STALE_FUNDAMENTALS",
                category=IssueCategory.STALE_DATA,
                severity=IssueSeverity.WARNING,
                message="Fundamentales antiguos.",
            )
        ],
        field_provenance={
            "price": FieldProvenance(
                field_name="price",
                provider="provider",
                is_validated=True,
            )
        },
    )

    reconstructed = CompanySnapshot.from_dict(
        original.to_dict()
    )

    assert reconstructed.to_dict() == (
        original.to_dict()
    )


def test_company_snapshot_from_legacy_dict() -> None:
    snapshot = CompanySnapshot.from_legacy_dict(
        {
            "ticker": "test",
            "price": 100.0,
            "data_quality": 65.0,
        }
    )

    assert snapshot.ticker == "TEST"
    assert snapshot.coverage_score == 65.0
    assert snapshot.schema_version == (
        MODEL_SCHEMA_VERSION
    )


# ============================================================
# SCORE CARD
# ============================================================


def test_score_card_normalizes_ticker() -> None:
    score = _score_card()

    assert score.ticker == "TEST"


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("valuation", -1, 0.0),
        ("quality", 150, 100.0),
        ("cash", "75.55", 75.5),
        ("balance", None, None),
        ("growth", float("nan"), None),
        (
            "capital_allocation",
            float("inf"),
            None,
        ),
        (
            "momentum_fundamental",
            True,
            None,
        ),
        ("risk", "invalid", None),
    ],
)
def test_score_card_normalizes_dimension_scores_without_inventing_neutral_values(
    field_name: str,
    value: Any,
    expected: float | None,
) -> None:
    score = _score_card(
        **{
            field_name: value,
        }
    )

    assert getattr(
        score,
        field_name,
    ) == expected


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("confidence", -10, 0.0),
        ("confidence", 150, 100.0),
        ("confidence", None, 0.0),
        ("global_score", "88.84", 88.8),
        ("global_score", float("nan"), 0.0),
        ("overall_coverage", 105, 100.0),
        ("overall_coverage", "invalid", 0.0),
    ],
)
def test_score_card_bounds_summary_scores(
    field_name: str,
    value: Any,
    expected: float,
) -> None:
    score = _score_card(
        **{
            field_name: value,
        }
    )

    assert getattr(
        score,
        field_name,
    ) == expected


def test_score_card_builds_v2_dimensions_from_legacy_fields() -> None:
    score = _score_card()

    assert set(score.dimensions) == {
        "valuation",
        "quality",
        "cash",
        "balance",
        "growth",
        "capital_allocation",
        "momentum_fundamental",
        "financial_resilience",
    }

    assert score.dimension_score(
        "valuation"
    ) == 70.0
    assert score.dimension_score(
        "risk"
    ) == 70.0
    assert score.financial_resilience == 70.0


def test_score_card_maps_legacy_risk_to_financial_resilience() -> None:
    score = _score_card(
        risk=82.0,
        dimension_coverage={
            "risk": 90.0,
        },
    )

    dimension = score.dimension(
        "financial_resilience"
    )

    assert dimension is not None
    assert dimension.score == 82.0
    assert dimension.coverage == 90.0
    assert score.risk == 82.0
    assert score.financial_resilience == 82.0


def test_score_card_does_not_make_missing_dimension_available() -> None:
    score = _score_card(
        growth=None,
        dimension_coverage={
            "growth": 100.0,
        },
    )

    dimension = score.dimension(
        "growth"
    )

    assert dimension is not None
    assert dimension.observed is False
    assert dimension.valid is False
    assert dimension.score is None
    assert dimension.available is False
    assert score.growth is None


def test_score_card_normalizes_dimension_coverage_to_canonical_codes() -> None:
    score = _score_card(
        dimension_coverage={
            "valuation": 125,
            "quality": -20,
            "cash": "66.66",
            "growth": float("nan"),
            "risk": True,
        }
    )

    assert score.dimension_coverage[
        "valuation"
    ] == 100.0
    assert score.dimension_coverage[
        "quality"
    ] == 0.0
    assert score.dimension_coverage[
        "cash"
    ] == 66.7
    assert score.dimension_coverage[
        "growth"
    ] == 0.0
    assert score.dimension_coverage[
        "financial_resilience"
    ] == 0.0


def test_score_card_rejects_unknown_explicit_dimension() -> None:
    with pytest.raises(
        ValueError,
        match="Dimensión desconocida",
    ):
        _score_card(
            dimensions={
                "unknown": DimensionScore(
                    code="unknown",
                    score=50.0,
                    coverage=100.0,
                    observed=True,
                    valid=True,
                )
            },
        )


def test_score_card_uses_explicit_dimensions_as_source_of_truth() -> None:
    dimensions = {
        "valuation": DimensionScore(
            code="valuation",
            score=91.0,
            coverage=80.0,
            confidence=85.0,
            observed=True,
            valid=True,
        ),
        "financial_resilience": DimensionScore(
            code="financial_resilience",
            score=77.0,
            coverage=70.0,
            confidence=80.0,
            observed=True,
            valid=True,
        ),
    }

    score = _score_card(
        valuation=10.0,
        risk=10.0,
        dimensions=dimensions,
    )

    assert score.valuation == 91.0
    assert score.risk == 77.0
    assert score.financial_resilience == 77.0


def test_score_card_derives_eligibility_and_signal() -> None:
    score = _score_card(
        confidence=80.0,
        overall_coverage=85.0,
        recommendation="CANDIDATA",
    )

    assert score.eligibility_status == (
        EligibilityStatus.ELIGIBLE
    )
    assert score.radar_signal == "CANDIDATA"


def test_score_card_separates_unreliable_data_from_radar_signal() -> None:
    score = _score_card(
        recommendation="DATOS NO FIABLES",
    )

    assert score.eligibility_status == (
        EligibilityStatus.UNRELIABLE
    )
    assert score.radar_signal is None
    assert score.is_reliable is False


@pytest.mark.parametrize(
    (
        "confidence",
        "coverage",
        "expected",
    ),
    [
        (55.0, 50.0, True),
        (80.0, 85.0, True),
        (54.9, 100.0, False),
        (100.0, 49.9, False),
        (0.0, 0.0, False),
    ],
)
def test_score_card_is_reliable_legacy_property(
    confidence: float,
    coverage: float,
    expected: bool,
) -> None:
    score = _score_card(
        confidence=confidence,
        overall_coverage=coverage,
    )

    assert score.is_reliable is expected


def test_score_card_meets_explicit_reliability_thresholds() -> None:
    score = _score_card(
        confidence=70.0,
        overall_coverage=75.0,
    )

    assert score.meets_reliability(
        minimum_confidence=65.0,
        minimum_coverage=70.0,
    ) is True

    assert score.meets_reliability(
        minimum_confidence=75.0,
        minimum_coverage=70.0,
    ) is False


def test_score_card_add_warning_normalizes_and_deduplicates() -> None:
    score = _score_card(
        warnings=[]
    )

    score.add_warning(
        "  Dato incompleto.  "
    )
    score.add_warning(
        "dato incompleto."
    )
    score.add_warning("")
    score.add_warning(
        123  # type: ignore[arg-type]
    )

    assert score.warnings == [
        "Dato incompleto.",
    ]


def test_score_card_to_dict_contains_versioned_contract() -> None:
    score = _score_card()

    result = score.to_dict()

    assert isinstance(result, dict)
    assert result["ticker"] == "TEST"
    assert result["global_score"] == 72.5
    assert result["overall_coverage"] == 85.0
    assert result["missing_metrics"] == [
        "interest_coverage",
    ]
    assert result["warnings"] == [
        "Cobertura parcial.",
    ]
    assert result["scoring_version"] == "1.0.0"
    assert result["schema_version"] == (
        MODEL_SCHEMA_VERSION
    )
    assert (
        result["dimensions"]["valuation"]["score"]
        == 70.0
    )
    assert (
        result["dimensions"][
            "financial_resilience"
        ]["score"]
        == 70.0
    )


def test_score_card_to_dict_does_not_share_mutable_references() -> None:
    score = _score_card()

    result = score.to_dict()

    result["warnings"].append(
        "Nueva advertencia."
    )
    result["dimension_coverage"][
        "valuation"
    ] = 0.0
    result["missing_metrics"].append(
        "new_metric"
    )
    result["dimensions"]["valuation"][
        "score"
    ] = 0.0

    assert score.warnings == [
        "Cobertura parcial.",
    ]
    assert score.dimension_coverage[
        "valuation"
    ] == 100.0
    assert score.missing_metrics == [
        "interest_coverage",
    ]
    assert score.dimension_score(
        "valuation"
    ) == 70.0


def test_score_card_preserves_textual_fields() -> None:
    score = _score_card(
        recommendation="VIGILAR",
        rationale="La cobertura es parcial.",
        scoring_version="2.0.0",
    )

    assert score.recommendation == "VIGILAR"
    assert score.rationale == (
        "La cobertura es parcial."
    )
    assert score.scoring_version == "2.0.0"


def test_score_card_round_trip_from_dict() -> None:
    original = _score_card(
        configuration_hash="abc123",
    )

    reconstructed = ScoreCard.from_dict(
        original.to_dict()
    )

    assert reconstructed.to_dict() == (
        original.to_dict()
    )


def test_score_card_from_legacy_dict() -> None:
    score = ScoreCard.from_legacy_dict(
        {
            "ticker": "test",
            "valuation": 70.0,
            "quality": 80.0,
            "cash": 75.0,
            "balance": 65.0,
            "growth": 60.0,
            "capital_allocation": 55.0,
            "momentum_fundamental": 50.0,
            "risk": 70.0,
            "confidence": 80.0,
            "global_score": 72.5,
            "recommendation": "CANDIDATA",
            "rationale": "Legacy.",
        }
    )

    assert score.ticker == "TEST"
    assert score.scoring_version == "legacy"
    assert score.schema_version == (
        MODEL_SCHEMA_VERSION
    )
    assert score.dimension_score(
        "valuation"
    ) == 70.0
    assert score.financial_resilience == 70.0


def test_score_card_comparability() -> None:
    left = _score_card(
        scoring_version="2.0.0",
        configuration_hash="same",
    )
    right = _score_card(
        scoring_version="2.0.0",
        configuration_hash="same",
    )

    result = left.comparability_with(
        right
    )

    assert result.status == (
        ComparabilityStatus.COMPARABLE
    )
    assert result.comparable is True
    assert result.reasons == []


def test_score_card_detects_incompatible_scoring_versions() -> None:
    left = _score_card(
        scoring_version="1.0.0",
    )
    right = _score_card(
        scoring_version="2.0.0",
    )

    result = left.comparability_with(
        right
    )

    assert result.status == (
        ComparabilityStatus.NOT_COMPARABLE
    )
    assert result.comparable is False
    assert (
        "Las versiones del scoring son distintas."
        in result.reasons
    )


def test_model_values_are_finite_or_missing_after_normalization() -> None:
    score = _score_card(
        valuation=float("nan"),
        quality=float("inf"),
        confidence=float("-inf"),
        global_score=float("nan"),
        overall_coverage=float("inf"),
    )

    normalized_values = [
        score.valuation,
        score.quality,
        score.confidence,
        score.global_score,
        score.overall_coverage,
    ]

    assert all(
        value is None
        or math.isfinite(value)
        for value in normalized_values
    )


# ============================================================
# SCORING CONFIGURATION
# ============================================================


def test_scoring_configuration_is_versioned_and_hashable() -> None:
    configuration = ScoringConfiguration(
        scoring_version="2.0.0",
        dimension_weights={
            "valuation": 0.20,
            "quality": 0.20,
            "cash": 0.15,
            "balance": 0.15,
            "growth": 0.10,
            "capital_allocation": 0.10,
            "momentum_fundamental": 0.05,
            "financial_resilience": 0.05,
        },
    )

    assert configuration.scoring_version == "2.0.0"
    assert len(
        configuration.configuration_hash
    ) == 64
    assert configuration.to_dict()[
        "schema_version"
    ] == MODEL_SCHEMA_VERSION


def test_scoring_configuration_hash_is_deterministic() -> None:
    first = ScoringConfiguration(
        scoring_version="2.0.0",
        dimension_weights={
            "valuation": 0.6,
            "quality": 0.4,
        },
    )
    second = ScoringConfiguration(
        scoring_version="2.0.0",
        dimension_weights={
            "quality": 0.4,
            "valuation": 0.6,
        },
    )

    assert (
        first.configuration_hash
        == second.configuration_hash
    )


def test_scoring_configuration_rejects_unknown_dimension() -> None:
    with pytest.raises(
        ValueError,
        match="Dimensión desconocida",
    ):
        ScoringConfiguration(
            scoring_version="2.0.0",
            dimension_weights={
                "unknown": 1.0,
            },
        )


def test_scoring_configuration_rejects_incoherent_thresholds() -> None:
    with pytest.raises(
        ValueError,
        match="priority",
    ):
        ScoringConfiguration(
            scoring_version="2.0.0",
            dimension_weights={
                "valuation": 1.0,
            },
            priority_threshold=60.0,
            candidate_threshold=70.0,
            watch_threshold=50.0,
        )


# ============================================================
# EXECUTION AND EXPORT CONTRACTS
# ============================================================


def test_screening_result_validates_ticker_coherence() -> None:
    snapshot = CompanySnapshot(
        ticker="META",
        price=500.0,
    )
    score = _score_card(
        ticker="META",
    )

    result = ScreeningResult(
        run_id="run-1",
        ticker="META",
        snapshot=snapshot,
        score=score,
    )

    assert result.ticker == "META"
    assert result.status == RunStatus.COMPLETED


def test_screening_result_rejects_mismatched_snapshot() -> None:
    with pytest.raises(
        ValueError,
        match="snapshot",
    ):
        ScreeningResult(
            run_id="run-1",
            ticker="META",
            snapshot=CompanySnapshot(
                ticker="AAPL",
                price=100.0,
            ),
        )


def test_screening_run_calculates_progress() -> None:
    run = ScreeningRun(
        run_id="run-1",
        universe="IBEX35",
        status=RunStatus.RUNNING,
        requested_company_count=35,
        completed_company_count=20,
        failed_company_count=5,
    )

    assert run.processed_company_count == 25
    assert run.progress_percentage == 71.4


def test_screening_run_rejects_impossible_counts() -> None:
    with pytest.raises(
        ValueError,
        match="superar",
    ):
        ScreeningRun(
            run_id="run-1",
            universe="IBEX35",
            requested_company_count=10,
            completed_company_count=9,
            failed_company_count=2,
        )


def test_export_manifest_serializes_artifacts() -> None:
    artifact = ExportArtifact(
        artifact_type="csv",
        filename="ibex35_scores.csv",
        content_type="text/csv",
        checksum="abc123",
        row_count=35,
    )

    manifest = ExportManifest(
        run_id="run-1",
        artifacts=[
            artifact,
        ],
    )

    payload = manifest.to_dict()

    assert payload["run_id"] == "run-1"
    assert payload["artifacts"][0][
        "filename"
    ] == "ibex35_scores.csv"
    assert payload["artifacts"][0][
        "row_count"
    ] == 35
