from __future__ import annotations
import pytest
import src.decision.engine as engine
from src.decision.enums import (
    DataQualityStatus,
    EvidenceConfidence,
    ExistingHolderAction,
    GateSeverity,
    MoatStrength,
    MoatTrend,
    NewInvestorAction,
    RiskLevel,
    ValuationStatus,
)
from src.decision.models import (
    AccountingAssessment,
    BusinessAssessment,
    DataQualityAssessment,
    GateResult,
    MasterAnalysisInput,
    MoatAssessment,
    PerShareAssessment,
    ValuationAssessment,
)
from src.decision.ranking import (
    RankingComponent,
    RankingResult,
)
def _complete_analysis() -> MasterAnalysisInput:
    return MasterAnalysisInput(
        ticker="TEST",
        company_name="Test Company",
        data_quality=DataQualityAssessment(
            status=DataQualityStatus.VALIDATED,
            coverage_score=95.0,
            freshness_score=95.0,
            consistency_score=95.0,
            source_quality_score=95.0,
            price_validated=True,
            currency_validated=True,
            ticker_validated=True,
            market_cap_validated=True,
            fundamentals_validated=True,
        ),
        business=BusinessAssessment(
            operating_quality_score=85.0,
            organic_growth_score=80.0,
            balance_score=85.0,
            cash_score=85.0,
            capital_allocation_score=80.0,
            risk_score=20.0,
        ),
        accounting=AccountingAssessment(
            accounting_quality_score=85.0,
            earnings_quality_score=85.0,
            cash_conversion_score=85.0,
            sbc_to_revenue=0.02,
        ),
        per_share=PerShareAssessment(
            per_share_value_score=85.0,
            share_count_growth=0.01,
        ),
        moat=MoatAssessment(
            strength=MoatStrength.STRONG,
            trend=MoatTrend.STABLE,
            confidence=EvidenceConfidence.HIGH,
            reviewed_score=85.0,
            substitution_risk_score=20.0,
            disruption_risk_score=20.0,
        ),
        valuation=ValuationAssessment(
            valuation_score=85.0,
            status=ValuationStatus.UNDERVALUED,
        ),
        model_version="0.1.0",
    )
def _ranking(
    score: float | None,
    coverage: float = 1.0,
    penalties: list[str] | None = None,
    warnings: list[str] | None = None,
) -> RankingResult:
    return RankingResult(
        score=score,
        coverage=coverage,
        components=[
            RankingComponent(
                name="Valoración",
                raw_score=score,
                weight=0.20,
                weighted_score=(
                    round(score * 0.20, 2)
                    if score is not None
                    else 0.0
                ),
                available=score is not None,
                reason=(
                    ""
                    if score is not None
                    else "No hay datos suficientes."
                ),
            )
        ],
        penalties=list(
            penalties or []
        ),
        warnings=list(
            warnings or []
        ),
    )
def _passed_gates() -> list[GateResult]:
    return [
        GateResult(
            code="TEST_GATE",
            passed=True,
            severity=GateSeverity.BLOCKING,
            message="Gate superado.",
        )
    ]
def _blocking_gate() -> list[GateResult]:
    return [
        GateResult(
            code="BLOCKING_TEST",
            passed=False,
            severity=GateSeverity.BLOCKING,
            message=(
                "Existe un incumplimiento bloqueante."
            ),
        )
    ]
def _warning_gate() -> list[GateResult]:
    return [
        GateResult(
            code="WARNING_TEST",
            passed=False,
            severity=GateSeverity.WARNING,
            message=(
                "Existe una advertencia relevante."
            ),
        )
    ]
def _patch_engine(
    monkeypatch: pytest.MonkeyPatch,
    ranking_result: RankingResult,
    gates: list[GateResult] | None = None,
) -> None:
    selected_gates = (
        gates
        if gates is not None
        else _passed_gates()
    )
    monkeypatch.setattr(
        engine,
        "calculate_ranking",
        lambda analysis: ranking_result,
    )
    monkeypatch.setattr(
        engine,
        "evaluate_master_gates",
        lambda analysis: selected_gates,
    )
def test_strong_buy_for_high_quality_company(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=88.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.STRONG_BUY
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.INCREASE
    )
    assert (
        result.confidence
        == EvidenceConfidence.HIGH
    )
    assert result.risk_level == RiskLevel.LOW
    assert result.ranking_score == 88.0
    assert result.company_quality in {
        "EXCELENTE",
        "ALTA",
    }
def test_buy_for_attractive_company(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=78.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.BUY
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.HOLD
    )
def test_partial_buy_with_reasonable_valuation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.valuation.status = (
        ValuationStatus.FAIRLY_VALUED
    )
    _patch_engine(
        monkeypatch,
        _ranking(
            score=68.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.PARTIAL_BUY
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.HOLD
    )
def test_wait_when_valuation_is_expensive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.valuation.status = (
        ValuationStatus.EXPENSIVE
    )
    _patch_engine(
        monkeypatch,
        _ranking(
            score=70.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.WAIT
    )
    assert any(
        "valoración más atractiva"
        in condition.lower()
        for condition
        in result.conditions_to_buy
    )
def test_blocking_gate_prevents_new_purchase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=90.0,
            coverage=1.0,
        ),
        gates=_blocking_gate(),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.AVOID
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.REVIEW_THESIS
    )
    assert (
        "BLOCKING_TEST"
        in result.raw_components[
            "blocking_gate_codes"
        ]
    )
    assert any(
        "incumplimiento bloqueante"
        in reason.lower()
        for reason in result.reasons
    )
def test_warning_gate_does_not_block_purchase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=88.0,
            coverage=1.0,
        ),
        gates=_warning_gate(),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        != NewInvestorAction.AVOID
    )
    assert (
        "WARNING_TEST"
        in result.raw_components[
            "failed_gate_codes"
        ]
    )
    assert (
        "WARNING_TEST"
        not in result.raw_components[
            "blocking_gate_codes"
        ]
    )
def test_unreliable_data_blocks_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.data_quality.status = (
        DataQualityStatus.UNRELIABLE
    )
    _patch_engine(
        monkeypatch,
        _ranking(
            score=90.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.UNRELIABLE_DATA
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.UNRELIABLE_DATA
    )
    assert (
        result.confidence
        == EvidenceConfidence.NOT_EVALUABLE
    )
    assert (
        result.risk_level
        == RiskLevel.NOT_EVALUATED
    )
def test_insufficient_data_requires_master_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.data_quality.status = (
        DataQualityStatus.INSUFFICIENT
    )
    _patch_engine(
        monkeypatch,
        _ranking(
            score=80.0,
            coverage=0.80,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.MASTER_REVIEW
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.REVIEW_THESIS
    )
    assert (
        result.confidence
        == EvidenceConfidence.LOW
    )
def test_missing_ranking_requires_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=None,
            coverage=0.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.MASTER_REVIEW
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.REVIEW_THESIS
    )
    assert result.ranking_score is None
def test_low_ranking_coverage_requires_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=80.0,
            coverage=0.40,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.MASTER_REVIEW
    )
def test_deteriorating_moat_with_high_risk_leads_to_reduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.moat.trend = (
        MoatTrend.DETERIORATING
    )
    analysis.business.risk_score = 70.0
    _patch_engine(
        monkeypatch,
        _ranking(
            score=70.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.AVOID
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.REDUCE
    )
    assert result.risk_level == RiskLevel.HIGH
def test_deteriorating_moat_with_medium_risk_does_not_force_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.moat.trend = (
        MoatTrend.DETERIORATING
    )
    analysis.business.risk_score = 40.0
    _patch_engine(
        monkeypatch,
        _ranking(
            score=70.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert result.risk_level == RiskLevel.MEDIUM
    assert (
        result.existing_holder_action
        == ExistingHolderAction.REDUCE
    )
    assert (
        result.existing_holder_action
        != ExistingHolderAction.EXIT
    )
def test_rapid_deterioration_can_trigger_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.moat.trend = (
        MoatTrend.RAPIDLY_DETERIORATING
    )
    analysis.business.risk_score = 80.0
    analysis.moat.disruption_risk_score = 90.0
    _patch_engine(
        monkeypatch,
        _ranking(
            score=50.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert (
        result.new_investor_action
        == NewInvestorAction.AVOID
    )
    assert (
        result.existing_holder_action
        == ExistingHolderAction.EXIT
    )
    assert (
        result.risk_level
        == RiskLevel.CRITICAL
    )
def test_company_quality_does_not_depend_on_valuation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attractive_analysis = _complete_analysis()
    expensive_analysis = _complete_analysis()
    attractive_analysis.valuation.status = (
        ValuationStatus.UNDERVALUED
    )
    expensive_analysis.valuation.status = (
        ValuationStatus.VERY_EXPENSIVE
    )
    _patch_engine(
        monkeypatch,
        _ranking(
            score=80.0,
            coverage=1.0,
        ),
    )
    attractive_result = (
        engine.make_master_decision(
            attractive_analysis
        )
    )
    expensive_result = (
        engine.make_master_decision(
            expensive_analysis
        )
    )
    assert (
        attractive_result.company_quality
        == expensive_result.company_quality
    )
def test_high_dilution_increases_risk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    analysis.per_share.share_count_growth = 0.12
    _patch_engine(
        monkeypatch,
        _ranking(
            score=75.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert result.risk_level == RiskLevel.MEDIUM
    assert any(
        "dilución"
        in condition.lower()
        for condition
        in result.conditions_to_buy
    )
def test_warnings_and_reasons_are_deduplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    repeated_warning = (
        "Advertencia repetida."
    )
    repeated_penalty = (
        "Penalización repetida."
    )
    analysis.data_quality.warnings = [
        repeated_warning
    ]
    analysis.accounting.warnings = [
        repeated_warning
    ]
    _patch_engine(
        monkeypatch,
        _ranking(
            score=75.0,
            coverage=1.0,
            penalties=[
                repeated_penalty,
                repeated_penalty,
            ],
            warnings=[
                repeated_warning
            ],
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert result.warnings.count(
        repeated_warning
    ) == 1
    assert result.reasons.count(
        repeated_penalty
    ) == 1
def test_result_contains_explainable_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=85.0,
            coverage=0.90,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    assert result.thesis
    assert result.conditions_to_buy
    assert result.conditions_to_reduce
    assert (
        result.raw_components[
            "ranking_coverage"
        ]
        == 0.90
    )
    assert (
        "ranking_components"
        in result.raw_components
    )
    assert (
        "failed_gate_codes"
        in result.raw_components
    )
    assert (
        "blocking_gate_codes"
        in result.raw_components
    )
def test_decision_result_serializes_enums(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _complete_analysis()
    _patch_engine(
        monkeypatch,
        _ranking(
            score=88.0,
            coverage=1.0,
        ),
    )
    result = engine.make_master_decision(
        analysis
    )
    serialized = result.to_dict()
    assert serialized["ticker"] == "TEST"
    assert (
        serialized["new_investor_action"]
        == NewInvestorAction.STRONG_BUY.value
    )
    assert (
        serialized["existing_holder_action"]
        == ExistingHolderAction.INCREASE.value
    )
    assert (
        serialized["confidence"]
        == EvidenceConfidence.HIGH.value
    )
    assert (
        serialized["risk_level"]
        == RiskLevel.LOW.value
    )
    assert (
        serialized["valuation_status"]
        == ValuationStatus.UNDERVALUED.value
    )
    assert isinstance(
        serialized["gates"],
        list,
    )
    assert isinstance(
        serialized["raw_components"],
        dict,
    )
