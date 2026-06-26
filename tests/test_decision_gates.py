from __future__ import annotations

from src.decision.enums import (
    DataQualityStatus,
    EvidenceConfidence,
    MoatStrength,
    MoatTrend,
)
from src.decision.gates import (
    blocking_failure_codes,
    evaluate_master_gates,
    get_blocking_failures,
    has_blocking_failures,
)
from src.decision.models import (
    AccountingAssessment,
    BusinessAssessment,
    DataQualityAssessment,
    MasterAnalysisInput,
    MoatAssessment,
    PerShareAssessment,
    ValuationAssessment,
    ValuationScenario,
)


def build_valid_analysis() -> MasterAnalysisInput:
    return MasterAnalysisInput(
        ticker="TEST",
        company_name="Test Company",
        data_quality=DataQualityAssessment(
            status=DataQualityStatus.VALIDATED,
            coverage_score=90.0,
            freshness_score=95.0,
            consistency_score=90.0,
            source_quality_score=85.0,
            price_validated=True,
            currency_validated=True,
            ticker_validated=True,
            market_cap_validated=True,
            fundamentals_validated=True,
            source_count=3,
            official_source_count=1,
        ),
        business=BusinessAssessment(
            operating_quality_score=80.0,
            organic_growth_score=70.0,
            balance_score=75.0,
            cash_score=80.0,
            capital_allocation_score=70.0,
            risk_score=75.0,
            platform_dependency_risk=30.0,
            regulatory_risk=25.0,
        ),
        accounting=AccountingAssessment(
            accounting_quality_score=75.0,
            sbc_to_reported_fcf=0.10,
            reported_fcf=1000.0,
            economic_fcf=900.0,
        ),
        per_share=PerShareAssessment(
            per_share_value_score=75.0,
            share_count_growth=-0.02,
        ),
        moat=MoatAssessment(
            strength=MoatStrength.STRONG,
            trend=MoatTrend.STABLE,
            confidence=EvidenceConfidence.HIGH,
            reviewed_score=80.0,
            disruption_risk_score=25.0,
        ),
        valuation=ValuationAssessment(
            current_price=80.0,
            currency="USD",
            conservative=ValuationScenario(
                name="Conservador",
                intrinsic_value_per_share=90.0,
            ),
            base=ValuationScenario(
                name="Base",
                intrinsic_value_per_share=110.0,
            ),
            optimistic=ValuationScenario(
                name="Optimista",
                intrinsic_value_per_share=130.0,
            ),
            reverse_dcf_status="RAZONABLE",
            margin_of_safety_conservative=0.125,
            margin_of_safety_base=0.375,
            valuation_score=80.0,
        ),
    )


def test_valid_analysis_has_no_blocking_failures() -> None:
    analysis = build_valid_analysis()

    gates = evaluate_master_gates(analysis)

    assert has_blocking_failures(gates) is False
    assert get_blocking_failures(gates) == []


def test_invalid_price_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.data_quality.price_validated = False

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "PRICE_VALIDATED" in codes
    assert has_blocking_failures(gates) is True


def test_invalid_currency_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.data_quality.currency_validated = False

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "CURRENCY_VALIDATED" in codes


def test_unvalidated_ticker_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.data_quality.ticker_validated = False

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "TICKER_VALIDATED" in codes


def test_unreliable_data_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.data_quality.status = (
        DataQualityStatus.UNRELIABLE
    )

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "DATA_NOT_UNRELIABLE" in codes


def test_low_coverage_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.data_quality.coverage_score = 40.0

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "DATA_COVERAGE_MINIMUM" in codes


def test_moat_not_reviewed_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.moat = MoatAssessment()

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "MOAT_REVIEWED" in codes


def test_rapid_moat_deterioration_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.moat.trend = (
        MoatTrend.RAPIDLY_DETERIORATING
    )

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "MOAT_NOT_COLLAPSING" in codes


def test_critical_disruption_risk_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.moat.disruption_risk_score = 90.0

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "DISRUPTION_RISK_NOT_CRITICAL" in codes


def test_low_accounting_quality_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.accounting.accounting_quality_score = 25.0

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "ACCOUNTING_QUALITY_MINIMUM" in codes


def test_missing_accounting_review_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.accounting.accounting_quality_score = None

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "ACCOUNTING_REVIEWED" in codes
    assert "ACCOUNTING_QUALITY_MINIMUM" in codes


def test_missing_conservative_value_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.valuation.conservative = None

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "CONSERVATIVE_VALUE_AVAILABLE" in codes


def test_missing_base_value_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.valuation.base = None

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "BASE_VALUE_AVAILABLE" in codes


def test_negative_base_margin_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.valuation.margin_of_safety_base = -0.10

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "BASE_MARGIN_POSITIVE" in codes


def test_critical_platform_dependency_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.business.platform_dependency_risk = 90.0

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "PLATFORM_DEPENDENCY_NOT_CRITICAL" in codes


def test_critical_regulatory_risk_blocks_recommendation() -> None:
    analysis = build_valid_analysis()
    analysis.business.regulatory_risk = 90.0

    gates = evaluate_master_gates(analysis)
    codes = blocking_failure_codes(gates)

    assert "REGULATORY_RISK_NOT_CRITICAL" in codes
