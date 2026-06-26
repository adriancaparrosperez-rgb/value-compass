from __future__ import annotations
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from src.decision.enums import DataQualityStatus
from src.decision.service import (
    SERVICE_NAME,
    SERVICE_SCHEMA_VERSION,
    execute_master_decision,
)
from src.models import CompanySnapshot, ScoreCard
from src.services.master_analysis_builder import (
    DEFAULT_MODEL_VERSION,
    build_master_analysis,
)
from src.ui.decision_presenter import (
    PRESENTER_SCHEMA_VERSION,
    DecisionView,
    build_decision_view,
    build_decision_view_dict,
)
NOW = datetime(
    2026,
    6,
    27,
    12,
    0,
    0,
    tzinfo=timezone.utc,
).isoformat()
def _snapshot(
    **overrides: Any,
) -> CompanySnapshot:
    values: dict[str, Any] = {
        "ticker": "TEST",
        "name": "Test Company",
        "currency": "EUR",
        "sector": "Industrials",
        "industry": "Industrial Products",
        "price": 100.0,
        "market_cap": 1_000_000_000.0,
        "enterprise_value": 1_100_000_000.0,
        "revenue": 500_000_000.0,
        "ebitda": 100_000_000.0,
        "ebit": 80_000_000.0,
        "net_income": 50_000_000.0,
        "operating_cash_flow": 90_000_000.0,
        "capex": 30_000_000.0,
        "free_cash_flow": 60_000_000.0,
        "total_cash": 120_000_000.0,
        "total_debt": 220_000_000.0,
        "shares": 10_000_000.0,
        "revenue_growth": 0.12,
        "earnings_growth": 0.15,
        "gross_margin": 0.45,
        "operating_margin": 0.20,
        "net_margin": 0.10,
        "roe": 0.22,
        "roa": 0.10,
        "debt_to_equity": 55.0,
        "current_ratio": 1.5,
        "pe": 18.0,
        "forward_pe": 16.0,
        "price_to_book": 3.0,
        "ev_to_ebitda": 10.0,
        "fcf_yield": 0.06,
        "earnings_yield": 0.05,
        "dividend_yield": 0.025,
        "fifty_two_week_change": 0.15,
        "analyst_target": 115.0,
        "analyst_count": 12,
        "data_quality": 90.0,
        "coverage_score": 90.0,
        "validity_score": 100.0,
        "consistency_score": 100.0,
        "source": "Yahoo Finance",
        "fetched_at": NOW,
        "price_date": NOW,
        "fundamentals_date": NOW,
        "warnings": [],
        "critical_missing_fields": [],
        "provider_metadata": {
            "provider": "Yahoo Finance",
            "provider_role": "preload",
            "is_official_source": False,
        },
        "errors": "",
    }
    values.update(
        overrides
    )
    return CompanySnapshot(
        **values
    )
def _dimension_coverage(
    **overrides: float,
) -> dict[str, float]:
    values = {
        "valuation": 100.0,
        "quality": 100.0,
        "cash": 100.0,
        "balance": 100.0,
        "growth": 100.0,
        "capital_allocation": 100.0,
        "momentum_fundamental": 100.0,
        "risk": 100.0,
    }
    values.update(
        overrides
    )
    return values
def _score_card(
    **overrides: Any,
) -> ScoreCard:
    values: dict[str, Any] = {
        "ticker": "TEST",
        "valuation": 72.0,
        "quality": 80.0,
        "cash": 75.0,
        "balance": 70.0,
        "growth": 68.0,
        "capital_allocation": 60.0,
        "momentum_fundamental": 65.0,
        "risk": 70.0,
        "confidence": 88.0,
        "global_score": 73.0,
        "recommendation": "CANDIDATA",
        "rationale": (
            "Clasificación de radar: CANDIDATA."
        ),
        "calculated_at": NOW,
        "overall_coverage": 90.0,
        "dimension_coverage": (
            _dimension_coverage()
        ),
        "missing_metrics": [],
        "warnings": [],
        "scoring_version": "2.0.0",
    }
    values.update(
        overrides
    )
    return ScoreCard(
        **values
    )
def _service_response(
    *,
    snapshot: CompanySnapshot | None = None,
    score: ScoreCard | None = None,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> dict[str, Any]:
    analysis = build_master_analysis(
        snapshot or _snapshot(),
        score or _score_card(),
        model_version=model_version,
    )
    return execute_master_decision(
        analysis
    )
def _metric_values(
    view: DecisionView,
) -> dict[str, str]:
    return {
        metric.label: metric.value
        for metric in view.metrics
    }
def test_complete_pipeline_builds_successful_view() -> None:
    response = _service_response()
    assert response["success"] is True
    view = build_decision_view(
        response
    )
    assert isinstance(
        view,
        DecisionView,
    )
    assert view.success is True
    assert view.ticker == "TEST"
    assert view.company_name == "Test Company"
    assert view.title == "Test Company · TEST"
    assert (
        view.schema_version
        == PRESENTER_SCHEMA_VERSION
    )
    assert (
        view.service_schema_version
        == SERVICE_SCHEMA_VERSION
    )
    assert view.service_name == SERVICE_NAME
    assert (
        view.model_version
        == DEFAULT_MODEL_VERSION
    )
def test_complete_pipeline_builds_primary_badges() -> None:
    view = build_decision_view(
        _service_response()
    )
    assert view.new_investor_badge is not None
    assert view.existing_holder_badge is not None
    assert view.confidence_badge is not None
    assert view.risk_badge is not None
    assert view.valuation_badge is not None
    assert view.moat_badge is not None
    assert (
        view.new_investor_badge.value
        != "No disponible"
    )
    assert (
        view.existing_holder_badge.value
        != "No disponible"
    )
    assert (
        view.confidence_badge.value
        != "No evaluable"
    )
    assert view.risk_badge.value
def test_complete_pipeline_builds_expected_metrics() -> None:
    view = build_decision_view(
        _service_response()
    )
    metrics = _metric_values(
        view
    )
    assert set(
        metrics
    ) == {
        "Ranking auxiliar",
        "Cobertura del ranking",
        "Calidad empresarial",
        "Gates fallidos",
        "Gates bloqueantes",
        "Fuentes utilizadas",
        "Calidad de datos",
        "Versión del modelo",
    }
    assert (
        metrics["Fuentes utilizadas"]
        == "1"
    )
    assert (
        metrics["Versión del modelo"]
        == DEFAULT_MODEL_VERSION
    )
    assert (
        metrics["Ranking auxiliar"]
        != ""
    )
    assert (
        metrics["Cobertura del ranking"]
        != ""
    )
def test_complete_pipeline_builds_sections() -> None:
    view = build_decision_view(
        _service_response()
    )
    assert view.thesis is not None
    assert view.reasons is not None
    assert view.warnings is not None
    assert view.conditions_to_buy is not None
    assert view.conditions_to_reduce is not None
    assert view.thesis.title == (
        "Tesis de inversión"
    )
    assert view.reasons.title == (
        "Motivos de la decisión"
    )
    assert view.warnings.title == (
        "Advertencias"
    )
    assert (
        view.conditions_to_buy.title
        == "Condiciones para comprar o aumentar"
    )
    assert (
        view.conditions_to_reduce.title
        == "Condiciones para reducir o salir"
    )
def test_complete_pipeline_transforms_gates() -> None:
    response = _service_response()
    service_gates = response[
        "decision"
    ]["gates"]
    view = build_decision_view(
        response
    )
    assert len(
        view.gates
    ) == len(
        service_gates
    )
    assert all(
        gate.code
        for gate in view.gates
    )
    assert all(
        isinstance(
            gate.passed,
            bool,
        )
        for gate in view.gates
    )
    assert all(
        gate.tone
        in {
            "positive",
            "warning",
            "negative",
            "neutral",
        }
        for gate in view.gates
    )
def test_complete_pipeline_transforms_ranking_components() -> None:
    response = _service_response()
    service_components = response[
        "decision"
    ]["raw_components"][
        "ranking_components"
    ]
    view = build_decision_view(
        response
    )
    assert len(
        view.ranking_components
    ) == len(
        service_components
    )
    assert all(
        component.name
        for component in view.ranking_components
    )
    assert all(
        isinstance(
            component.available,
            bool,
        )
        for component
        in view.ranking_components
    )
def test_preliminary_analysis_remains_prudent_in_view() -> None:
    response = _service_response()
    view = build_decision_view(
        response
    )
    assert view.valuation_badge is not None
    assert (
        view.valuation_badge.value
        == "NO EVALUADA"
    )
    assert view.new_investor_badge is not None
    assert (
        view.new_investor_badge.value
        not in {
            "COMPRA CLARA",
            "COMPRAR",
            "COMPRA PARCIAL",
        }
    )
    assert view.conditions_to_buy is not None
    assert any(
        "valoración"
        in condition.casefold()
        for condition
        in view.conditions_to_buy.items
    )
def test_insufficient_data_crosses_entire_pipeline() -> None:
    response = _service_response(
        snapshot=_snapshot(
            price=None,
            critical_missing_fields=[
                "price",
            ],
        ),
        score=_score_card(
            confidence=30.0,
            overall_coverage=35.0,
        ),
    )
    assert response["success"] is True
    assert (
        response["metadata"][
            "data_quality_status"
        ]
        == DataQualityStatus.INSUFFICIENT.value
    )
    view = build_decision_view(
        response
    )
    assert view.success is True
    assert view.new_investor_badge is not None
    assert view.existing_holder_badge is not None
    assert (
        view.new_investor_badge.value
        == "REQUIERE ANÁLISIS MAESTRO"
    )
    assert (
        view.existing_holder_badge.value
        == "REVISAR TESIS"
    )
    assert view.warnings is not None
    assert any(
        "precio"
        in warning.casefold()
        for warning in view.warnings.items
    )
def test_service_error_crosses_presenter_safely() -> None:
    response = execute_master_decision(
        {},  # type: ignore[arg-type]
    )
    assert response["success"] is False
    view = build_decision_view(
        response
    )
    assert view.success is False
    assert (
        view.schema_version
        == PRESENTER_SCHEMA_VERSION
    )
    assert (
        view.service_schema_version
        == SERVICE_SCHEMA_VERSION
    )
    assert view.service_name == SERVICE_NAME
    assert view.error_type == (
        "INVALID_INPUT"
    )
    assert view.error_message
    assert (
        view.title
        == "No se pudo completar el análisis"
    )
def test_success_view_dict_is_json_serializable() -> None:
    response = _service_response()
    result = build_decision_view_dict(
        response
    )
    serialized = json.dumps(
        result,
        ensure_ascii=False,
    )
    assert isinstance(
        result,
        dict,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert result["success"] is True
    assert (
        result["schema_version"]
        == PRESENTER_SCHEMA_VERSION
    )
    assert "TEST" in serialized
    assert "Test Company" in serialized
def test_error_view_dict_is_json_serializable() -> None:
    response = execute_master_decision(
        {},  # type: ignore[arg-type]
    )
    result = build_decision_view_dict(
        response
    )
    serialized = json.dumps(
        result,
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert result["success"] is False
    assert result["error_type"] == (
        "INVALID_INPUT"
    )
def test_presenter_does_not_mutate_service_response() -> None:
    response = _service_response()
    response_before = deepcopy(
        response
    )
    build_decision_view(
        response
    )
    assert response == response_before
def test_view_raw_response_is_defensively_copied() -> None:
    response = _service_response()
    view = build_decision_view(
        response
    )
    original_ticker = view.raw_response[
        "ticker"
    ]
    response["ticker"] = "CHANGED"
    response[
        "decision"
    ]["warnings"].append(
        "Changed warning"
    )
    assert (
        view.raw_response["ticker"]
        == original_ticker
    )
    assert (
        "Changed warning"
        not in view.raw_response[
            "decision"
        ]["warnings"]
    )
def test_builder_warning_reaches_presented_warning_section() -> None:
    response = _service_response(
        snapshot=_snapshot(
            warnings=[
                (
                    "Advertencia específica "
                    "del proveedor."
                ),
            ]
        ),
        score=_score_card(
            warnings=[
                (
                    "Advertencia específica "
                    "del scoring."
                ),
            ]
        ),
    )
    view = build_decision_view(
        response
    )
    assert view.warnings is not None
    assert (
        "Advertencia específica del proveedor."
        in view.warnings.items
    )
    assert (
        "Advertencia específica del scoring."
        in view.warnings.items
    )
def test_model_version_crosses_entire_pipeline() -> None:
    response = _service_response(
        model_version="3.0.0"
    )
    view = build_decision_view(
        response
    )
    assert (
        response["model_version"]
        == "3.0.0"
    )
    assert (
        response["decision"][
            "model_version"
        ]
        == "3.0.0"
    )
    assert view.model_version == "3.0.0"
    metrics = _metric_values(
        view
    )
    assert (
        metrics["Versión del modelo"]
        == "3.0.0"
    )
def test_real_service_contract_generates_no_schema_warning() -> None:
    view = build_decision_view(
        _service_response()
    )
    assert not any(
        "esquema del servicio"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_repeated_presentation_is_deterministic() -> None:
    response = _service_response()
    first = build_decision_view_dict(
        response
    )
    second = build_decision_view_dict(
        response
    )
    assert first == second
