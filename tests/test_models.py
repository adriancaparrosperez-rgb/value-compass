from __future__ import annotations
import math
from typing import Any
import pytest
from src.models import (
    CompanySnapshot,
    ScoreCard,
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
        },
        "missing_metrics": [
            "interest_coverage",
        ],
        "warnings": [
            "Cobertura parcial.",
        ],
        "scoring_version": "1.0.0",
    }
    values.update(
        overrides
    )
    return ScoreCard(
        **values
    )
def test_company_snapshot_preserves_legacy_defaults() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )
    assert snapshot.ticker == "TEST"
    assert snapshot.name == ""
    assert snapshot.currency == ""
    assert snapshot.price is None
    assert snapshot.market_cap is None
    assert snapshot.data_quality == 0.0
    assert snapshot.errors == ""
    assert snapshot.missing_fields == []
    assert snapshot.critical_missing_fields == []
    assert snapshot.warnings == []
    assert snapshot.provider_metadata == {}
def test_company_snapshot_normalizes_ticker() -> None:
    snapshot = CompanySnapshot(
        ticker="  itx.mc  "
    )
    assert snapshot.ticker == "ITX.MC"
@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        (
            123,
            "123",
        ),
        (
            None,
            "None",
        ),
        (
            True,
            "True",
        ),
    ],
)
def test_company_snapshot_converts_non_string_ticker(
    ticker: Any,
    expected: str,
) -> None:
    snapshot = CompanySnapshot(
        ticker=ticker  # type: ignore[arg-type]
    )
    assert snapshot.ticker == expected
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            -10,
            0.0,
        ),
        (
            0,
            0.0,
        ),
        (
            45.56,
            45.6,
        ),
        (
            100,
            100.0,
        ),
        (
            150,
            100.0,
        ),
        (
            None,
            0.0,
        ),
        (
            "75.44",
            75.4,
        ),
        (
            "invalid",
            0.0,
        ),
        (
            True,
            0.0,
        ),
        (
            float("nan"),
            0.0,
        ),
        (
            float("inf"),
            0.0,
        ),
        (
            float("-inf"),
            0.0,
        ),
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
        consistency_score=value,
    )
    assert snapshot.data_quality == expected
    assert snapshot.coverage_score == expected
    assert snapshot.validity_score == expected
    assert snapshot.consistency_score == expected
def test_company_snapshot_has_errors_property() -> None:
    clean_snapshot = CompanySnapshot(
        ticker="TEST"
    )
    error_snapshot = CompanySnapshot(
        ticker="TEST",
        errors="ProviderError",
    )
    whitespace_snapshot = CompanySnapshot(
        ticker="TEST",
        errors="   ",
    )
    assert clean_snapshot.has_errors is False
    assert error_snapshot.has_errors is True
    assert whitespace_snapshot.has_errors is False
def test_company_snapshot_has_warnings_property() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )
    assert snapshot.has_warnings is False
    snapshot.warnings.append(
        "Advertencia."
    )
    assert snapshot.has_warnings is True
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
            ticker="",
            price=100.0,
        ),
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
        "Primera advertencia."
    ]
def test_company_snapshot_add_warning_trims_text() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )
    snapshot.add_warning(
        "  Advertencia con espacios.  "
    )
    assert snapshot.warnings == [
        "Advertencia con espacios."
    ]
def test_company_snapshot_add_warning_ignores_empty_values() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )
    snapshot.add_warning("")
    snapshot.add_warning("   ")
    snapshot.add_warning(
        None  # type: ignore[arg-type]
    )
    assert snapshot.warnings == []
def test_company_snapshot_add_warning_deduplicates_case_insensitively() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST"
    )
    snapshot.add_warning(
        "Dato no validado."
    )
    snapshot.add_warning(
        "dato no validado."
    )
    snapshot.add_warning(
        "DATO NO VALIDADO."
    )
    assert snapshot.warnings == [
        "Dato no validado."
    ]
def test_company_snapshot_to_dict_returns_complete_mapping() -> None:
    snapshot = CompanySnapshot(
        ticker="TEST",
        name="Test Company",
        price=100.0,
        warnings=[
            "Advertencia.",
        ],
        provider_metadata={
            "used_fast_info": True,
        },
    )
    result = snapshot.to_dict()
    assert isinstance(
        result,
        dict,
    )
    assert result["ticker"] == "TEST"
    assert result["name"] == "Test Company"
    assert result["price"] == 100.0
    assert result["warnings"] == [
        "Advertencia.",
    ]
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
def test_score_card_normalizes_ticker() -> None:
    score = _score_card()
    assert score.ticker == "TEST"
@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        (
            "valuation",
            -1,
            0.0,
        ),
        (
            "quality",
            150,
            100.0,
        ),
        (
            "cash",
            "75.55",
            75.5,
        ),
        (
            "balance",
            None,
            50.0,
        ),
        (
            "growth",
            float("nan"),
            50.0,
        ),
        (
            "capital_allocation",
            float("inf"),
            50.0,
        ),
        (
            "momentum_fundamental",
            True,
            50.0,
        ),
        (
            "risk",
            "invalid",
            50.0,
        ),
    ],
)
def test_score_card_bounds_dimension_scores(
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
@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        (
            "confidence",
            -10,
            0.0,
        ),
        (
            "confidence",
            150,
            100.0,
        ),
        (
            "confidence",
            None,
            0.0,
        ),
        (
            "global_score",
            "88.84",
            88.8,
        ),
        (
            "global_score",
            float("nan"),
            0.0,
        ),
        (
            "overall_coverage",
            105,
            100.0,
        ),
        (
            "overall_coverage",
            "invalid",
            0.0,
        ),
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
def test_score_card_normalizes_dimension_coverage() -> None:
    score = _score_card(
        dimension_coverage={
            "valuation": 125,
            "quality": -20,
            "cash": "66.66",
            "growth": float("nan"),
            "risk": True,
        }
    )
    assert score.dimension_coverage == {
        "valuation": 100.0,
        "quality": 0.0,
        "cash": 66.7,
        "growth": 0.0,
        "risk": 0.0,
    }
def test_score_card_converts_dimension_names_to_strings() -> None:
    score = _score_card(
        dimension_coverage={
            123: 50.0,
        }
    )
    assert score.dimension_coverage == {
        "123": 50.0,
    }
@pytest.mark.parametrize(
    (
        "confidence",
        "coverage",
        "expected",
    ),
    [
        (
            55.0,
            50.0,
            True,
        ),
        (
            80.0,
            85.0,
            True,
        ),
        (
            54.9,
            100.0,
            False,
        ),
        (
            100.0,
            49.9,
            False,
        ),
        (
            0.0,
            0.0,
            False,
        ),
    ],
)
def test_score_card_is_reliable_property(
    confidence: float,
    coverage: float,
    expected: bool,
) -> None:
    score = _score_card(
        confidence=confidence,
        overall_coverage=coverage,
    )
    assert score.is_reliable is expected
def test_score_card_add_warning() -> None:
    score = _score_card(
        warnings=[]
    )
    score.add_warning(
        "Cobertura insuficiente."
    )
    assert score.warnings == [
        "Cobertura insuficiente."
    ]
def test_score_card_add_warning_deduplicates_and_trims() -> None:
    score = _score_card(
        warnings=[]
    )
    score.add_warning(
        "  Dato incompleto.  "
    )
    score.add_warning(
        "dato incompleto."
    )
    assert score.warnings == [
        "Dato incompleto."
    ]
def test_score_card_add_warning_ignores_invalid_messages() -> None:
    score = _score_card(
        warnings=[]
    )
    score.add_warning("")
    score.add_warning("   ")
    score.add_warning(
        123  # type: ignore[arg-type]
    )
    assert score.warnings == []
def test_score_card_to_dict_contains_extended_contract() -> None:
    score = _score_card()
    result = score.to_dict()
    assert isinstance(
        result,
        dict,
    )
    assert result["ticker"] == "TEST"
    assert result["global_score"] == 72.5
    assert result["overall_coverage"] == 85.0
    assert result["dimension_coverage"] == {
        "valuation": 100.0,
        "quality": 75.0,
    }
    assert result["missing_metrics"] == [
        "interest_coverage",
    ]
    assert result["warnings"] == [
        "Cobertura parcial.",
    ]
    assert result["scoring_version"] == "1.0.0"
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
    assert score.warnings == [
        "Cobertura parcial.",
    ]
    assert score.dimension_coverage[
        "valuation"
    ] == 100.0
    assert score.missing_metrics == [
        "interest_coverage",
    ]
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
def test_model_values_are_finite_after_normalization() -> None:
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
        math.isfinite(value)
        for value in normalized_values
    )
