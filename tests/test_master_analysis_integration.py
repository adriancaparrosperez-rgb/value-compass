from __future__ import annotations
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import pytest
import src.decision.service as decision_service
from src.decision.enums import (
    DataQualityStatus,
    EvidenceConfidence,
    ExistingHolderAction,
    NewInvestorAction,
    RiskLevel,
    ValuationStatus,
)
from src.decision.models import (
    MasterAnalysisInput,
    MasterDecisionResult,
)
from src.decision.service import (
    SERVICE_NAME,
    SERVICE_SCHEMA_VERSION,
    DecisionInputError,
    DecisionServiceError,
    build_decision_response,
    build_error_response,
    execute_master_decision,
    run_master_decision,
)
from src.models import CompanySnapshot, ScoreCard
from src.services.master_analysis_builder import (
    DEFAULT_MODEL_VERSION,
    build_master_analysis,
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
    values.update(overrides)
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
    values.update(overrides)
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
    values.update(overrides)
    return ScoreCard(
        **values
    )
def _analysis(
    *,
    snapshot: CompanySnapshot | None = None,
    score: ScoreCard | None = None,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> MasterAnalysisInput:
    return build_master_analysis(
        snapshot or _snapshot(),
        score or _score_card(),
        model_version=model_version,
    )
def test_builder_output_is_accepted_by_strict_service() -> None:
    analysis = _analysis()
    result = run_master_decision(
        analysis
    )
    assert isinstance(
        analysis,
        MasterAnalysisInput,
    )
    assert isinstance(
        result,
        MasterDecisionResult,
    )
    assert result.ticker == "TEST"
    assert result.model_version == (
        DEFAULT_MODEL_VERSION
    )
def test_preliminary_analysis_produces_controlled_result() -> None:
    result = run_master_decision(
        _analysis()
    )
    assert result.new_investor_action in set(
        NewInvestorAction
    )
    assert result.existing_holder_action in set(
        ExistingHolderAction
    )
    assert result.confidence in set(
        EvidenceConfidence
    )
    assert result.risk_level in set(
        RiskLevel
    )
    assert isinstance(
        result.company_quality,
        str,
    )
    assert result.company_quality
    assert isinstance(
        result.gates,
        list,
    )
    assert isinstance(
        result.thesis,
        list,
    )
    assert isinstance(
        result.reasons,
        list,
    )
    assert isinstance(
        result.warnings,
        list,
    )
    assert isinstance(
        result.conditions_to_buy,
        list,
    )
    assert isinstance(
        result.conditions_to_reduce,
        list,
    )
    assert isinstance(
        result.raw_components,
        dict,
    )
def test_preliminary_analysis_does_not_generate_buy_action() -> None:
    result = run_master_decision(
        _analysis()
    )
    assert result.valuation_status == (
        ValuationStatus.NOT_EVALUATED
    )
    assert result.new_investor_action not in {
        NewInvestorAction.STRONG_BUY,
        NewInvestorAction.BUY,
        NewInvestorAction.PARTIAL_BUY,
    }
    assert any(
        "valoración"
        in condition.casefold()
        for condition
        in result.conditions_to_buy
    )
def test_insufficient_data_crosses_builder_and_service() -> None:
    analysis = _analysis(
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
    assert analysis.data_quality.status == (
        DataQualityStatus.INSUFFICIENT
    )
    result = run_master_decision(
        analysis
    )
    assert result.new_investor_action == (
        NewInvestorAction.MASTER_REVIEW
    )
    assert result.existing_holder_action == (
        ExistingHolderAction.REVIEW_THESIS
    )
    assert result.confidence == (
        EvidenceConfidence.LOW
    )
    assert any(
        "precio"
        in warning.casefold()
        for warning in result.warnings
    )
def test_build_decision_response_returns_stable_contract() -> None:
    response = build_decision_response(
        _analysis()
    )
    assert response["success"] is True
    assert response["service"] == (
        SERVICE_NAME
    )
    assert response["schema_version"] == (
        SERVICE_SCHEMA_VERSION
    )
    assert response["model_version"] == (
        DEFAULT_MODEL_VERSION
    )
    assert response["ticker"] == "TEST"
    assert response["company_name"] == (
        "Test Company"
    )
    assert isinstance(
        response["created_at"],
        str,
    )
    assert isinstance(
        response["decision"],
        dict,
    )
    assert isinstance(
        response["metadata"],
        dict,
    )
def test_success_response_contains_expected_metadata() -> None:
    analysis = _analysis()
    response = build_decision_response(
        analysis
    )
    metadata = response["metadata"]
    assert metadata["source_count"] == (
        len(analysis.sources)
    )
    assert metadata["data_quality_status"] == (
        analysis.data_quality.status.value
    )
    assert metadata["confidence"] in {
        confidence.value
        for confidence in EvidenceConfidence
    }
    assert metadata["risk_level"] in {
        risk.value
        for risk in RiskLevel
    }
    assert metadata[
        "new_investor_action"
    ] in {
        action.value
        for action in NewInvestorAction
    }
    assert metadata[
        "existing_holder_action"
    ] in {
        action.value
        for action in ExistingHolderAction
    }
def test_execute_master_decision_returns_success_response() -> None:
    response = execute_master_decision(
        _analysis()
    )
    assert response["success"] is True
    assert response["service"] == SERVICE_NAME
    assert response["schema_version"] == (
        SERVICE_SCHEMA_VERSION
    )
    assert response["ticker"] == "TEST"
    assert isinstance(
        response["decision"],
        dict,
    )
def test_execute_master_decision_returns_serializable_response() -> None:
    response = execute_master_decision(
        _analysis()
    )
    serialized = json.dumps(
        response,
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert "TEST" in serialized
    assert SERVICE_NAME in serialized
    assert SERVICE_SCHEMA_VERSION in serialized
def test_strict_service_rejects_invalid_analysis_type() -> None:
    with pytest.raises(
        DecisionInputError,
        match="MasterAnalysisInput",
    ):
        run_master_decision(
            {},  # type: ignore[arg-type]
        )
def test_safe_service_converts_invalid_input_into_error_response() -> None:
    response = execute_master_decision(
        {},  # type: ignore[arg-type]
    )
    assert response == {
        "success": False,
        "service": SERVICE_NAME,
        "schema_version": (
            SERVICE_SCHEMA_VERSION
        ),
        "error": {
            "type": "INVALID_INPUT",
            "message": (
                "La entrada debe ser una instancia "
                "de MasterAnalysisInput."
            ),
        },
    }
def test_safe_service_does_not_expose_unexpected_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_unexpected_error(
        analysis: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        raise RuntimeError(
            "Sensitive internal information"
        )
    monkeypatch.setattr(
        decision_service,
        "make_master_decision",
        raise_unexpected_error,
    )
    response = execute_master_decision(
        _analysis()
    )
    assert response["success"] is False
    assert response["error"]["type"] == (
        "ANALYSIS_ERROR"
    )
    assert (
        "Sensitive internal information"
        not in response["error"]["message"]
    )
def test_service_rejects_invalid_engine_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def return_invalid_result(
        analysis: MasterAnalysisInput,
    ) -> Any:
        return {
            "invalid": True,
        }
    monkeypatch.setattr(
        decision_service,
        "make_master_decision",
        return_invalid_result,
    )
    with pytest.raises(
        DecisionServiceError,
        match="MasterDecisionResult",
    ):
        run_master_decision(
            _analysis()
        )
def test_safe_service_converts_invalid_engine_result_into_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def return_invalid_result(
        analysis: MasterAnalysisInput,
    ) -> Any:
        return None
    monkeypatch.setattr(
        decision_service,
        "make_master_decision",
        return_invalid_result,
    )
    response = execute_master_decision(
        _analysis()
    )
    assert response["success"] is False
    assert response["error"] == {
        "type": "SERVICE_ERROR",
        "message": (
            "No se pudo completar correctamente "
            "el análisis."
        ),
    }
def test_build_error_response_handles_input_error() -> None:
    response = build_error_response(
        DecisionInputError(
            "Ticker inválido."
        )
    )
    assert response["success"] is False
    assert response["error"] == {
        "type": "INVALID_INPUT",
        "message": "Ticker inválido.",
    }
def test_build_error_response_handles_service_error_safely() -> None:
    response = build_error_response(
        DecisionServiceError(
            "Sensitive technical detail"
        )
    )
    assert response["error"] == {
        "type": "SERVICE_ERROR",
        "message": (
            "No se pudo completar correctamente "
            "el análisis."
        ),
    }
    assert (
        "Sensitive technical detail"
        not in response["error"]["message"]
    )
def test_build_error_response_handles_unknown_error_safely() -> None:
    response = build_error_response(
        RuntimeError(
            "Sensitive internal detail"
        )
    )
    assert response["error"] == {
        "type": "ANALYSIS_ERROR",
        "message": (
            "Se ha producido un error interno durante "
            "el análisis."
        ),
    }
def test_service_normalizes_ticker_on_defensive_copy() -> None:
    analysis = _analysis()
    analysis.ticker = " test "
    result = run_master_decision(
        analysis
    )
    assert result.ticker == "TEST"
    assert analysis.ticker == " test "
def test_service_does_not_mutate_analysis() -> None:
    analysis = _analysis()
    analysis_before = deepcopy(
        analysis.to_dict()
    )
    run_master_decision(
        analysis
    )
    assert analysis.to_dict() == (
        analysis_before
    )
def test_execute_service_does_not_mutate_analysis() -> None:
    analysis = _analysis()
    analysis_before = deepcopy(
        analysis.to_dict()
    )
    execute_master_decision(
        analysis
    )
    assert analysis.to_dict() == (
        analysis_before
    )
def test_builder_and_service_do_not_mutate_original_inputs() -> None:
    snapshot = _snapshot(
        warnings=[
            "Original snapshot warning",
        ]
    )
    score = _score_card(
        warnings=[
            "Original scoring warning",
        ]
    )
    snapshot_before = deepcopy(
        snapshot.to_dict()
    )
    score_before = deepcopy(
        score.to_dict()
    )
    analysis = build_master_analysis(
        snapshot,
        score,
    )
    execute_master_decision(
        analysis
    )
    assert snapshot.to_dict() == (
        snapshot_before
    )
    assert score.to_dict() == (
        score_before
    )
def test_builder_warnings_reach_service_response() -> None:
    snapshot = _snapshot(
        warnings=[
            "Advertencia específica del proveedor."
        ]
    )
    score = _score_card(
        warnings=[
            "Advertencia específica del scoring."
        ]
    )
    response = execute_master_decision(
        build_master_analysis(
            snapshot,
            score,
        )
    )
    warnings = response[
        "decision"
    ]["warnings"]
    assert (
        "Advertencia específica del proveedor."
        in warnings
    )
    assert (
        "Advertencia específica del scoring."
        in warnings
    )
def test_blocking_issues_reach_service_response() -> None:
    analysis = _analysis(
        snapshot=_snapshot(
            errors=(
                "Error controlado del proveedor."
            ),
        )
    )
    response = execute_master_decision(
        analysis
    )
    assert response["success"] is True
    assert (
        "Error controlado del proveedor."
        in response["decision"]["warnings"]
    )
def test_model_version_crosses_complete_pipeline() -> None:
    analysis = _analysis(
        model_version="3.0.0"
    )
    response = execute_master_decision(
        analysis
    )
    assert analysis.model_version == "3.0.0"
    assert response["model_version"] == (
        "3.0.0"
    )
    assert response[
        "decision"
    ]["model_version"] == "3.0.0"
def test_service_response_contains_ranking_audit_trail() -> None:
    response = execute_master_decision(
        _analysis()
    )
    raw_components = response[
        "decision"
    ]["raw_components"]
    assert "ranking_coverage" in (
        raw_components
    )
    assert "ranking_components" in (
        raw_components
    )
    assert "ranking_penalties" in (
        raw_components
    )
    assert "blocking_gate_codes" in (
        raw_components
    )
    assert "failed_gate_codes" in (
        raw_components
    )
    assert isinstance(
        raw_components[
            "ranking_components"
        ],
        list,
    )
def test_repeated_strict_execution_is_functionally_consistent() -> None:
    analysis = _analysis()
    first = run_master_decision(
        analysis
    )
    second = run_master_decision(
        analysis
    )
    assert first.ticker == second.ticker
    assert (
        first.new_investor_action
        == second.new_investor_action
    )
    assert (
        first.existing_holder_action
        == second.existing_holder_action
    )
    assert first.confidence == second.confidence
    assert first.risk_level == second.risk_level
    assert (
        first.company_quality
        == second.company_quality
    )
    assert (
        first.ranking_score
        == second.ranking_score
    )
    assert first.reasons == second.reasons
    assert first.warnings == second.warnings
    assert (
        first.raw_components
        == second.raw_components
    )
