from __future__ import annotations

from src.analysis.accounting import (
    AccountingInput,
    assess_accounting_quality,
    calculate_economic_fcf,
    calculate_reported_fcf,
)


def test_reported_fcf_is_cfo_minus_capex() -> None:
    result = calculate_reported_fcf(
        operating_cash_flow=1_000.0,
        capital_expenditure=200.0,
    )

    assert result == 800.0


def test_reported_fcf_accepts_negative_capex_sign() -> None:
    result = calculate_reported_fcf(
        operating_cash_flow=1_000.0,
        capital_expenditure=-200.0,
    )

    assert result == 800.0


def test_reported_fcf_returns_none_without_required_data() -> None:
    assert calculate_reported_fcf(
        operating_cash_flow=None,
        capital_expenditure=200.0,
    ) is None

    assert calculate_reported_fcf(
        operating_cash_flow=1_000.0,
        capital_expenditure=None,
    ) is None


def test_economic_fcf_subtracts_sbc_when_enabled() -> None:
    result = calculate_economic_fcf(
        reported_fcf=800.0,
        stock_based_compensation=150.0,
        use_sbc_adjusted_fcf=True,
    )

    assert result == 650.0


def test_economic_fcf_keeps_reported_fcf_when_disabled() -> None:
    result = calculate_economic_fcf(
        reported_fcf=800.0,
        stock_based_compensation=150.0,
        use_sbc_adjusted_fcf=False,
    )

    assert result == 800.0


def test_clean_company_gets_high_accounting_score() -> None:
    assessment = assess_accounting_quality(
        AccountingInput(
            revenue=10_000.0,
            gaap_earnings=1_000.0,
            adjusted_earnings=1_050.0,
            operating_cash_flow=1_300.0,
            capital_expenditure=200.0,
            stock_based_compensation=100.0,
            diluted_shares=100.0,
            diluted_shares_previous=101.0,
        )
    )

    assert assessment.reported_fcf == 1_100.0
    assert assessment.economic_fcf == 1_000.0
    assert assessment.accounting_quality_score is not None
    assert assessment.accounting_quality_score >= 70.0


def test_large_gaap_non_gaap_gap_reduces_score() -> None:
    assessment = assess_accounting_quality(
        AccountingInput(
            revenue=10_000.0,
            gaap_earnings=500.0,
            adjusted_earnings=1_200.0,
            operating_cash_flow=900.0,
            capital_expenditure=100.0,
            stock_based_compensation=100.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
        )
    )

    assert assessment.accounting_quality_score is not None
    assert assessment.earnings_quality_score is not None
    assert assessment.earnings_quality_score < 70.0
    assert any(
        "GAAP" in warning
        for warning in assessment.warnings
    )


def test_high_sbc_reduces_accounting_score() -> None:
    low_sbc = assess_accounting_quality(
        AccountingInput(
            revenue=10_000.0,
            gaap_earnings=1_000.0,
            adjusted_earnings=1_050.0,
            operating_cash_flow=1_300.0,
            capital_expenditure=200.0,
            stock_based_compensation=100.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
        )
    )

    high_sbc = assess_accounting_quality(
        AccountingInput(
            revenue=10_000.0,
            gaap_earnings=1_000.0,
            adjusted_earnings=1_050.0,
            operating_cash_flow=1_300.0,
            capital_expenditure=200.0,
            stock_based_compensation=800.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
        )
    )

    assert low_sbc.accounting_quality_score is not None
    assert high_sbc.accounting_quality_score is not None
    assert (
        high_sbc.accounting_quality_score
        < low_sbc.accounting_quality_score
    )


def test_material_dilution_reduces_score() -> None:
    no_dilution = assess_accounting_quality(
        AccountingInput(
            revenue=10_000.0,
            gaap_earnings=1_000.0,
            adjusted_earnings=1_050.0,
            operating_cash_flow=1_300.0,
            capital_expenditure=200.0,
            stock_based_compensation=100.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
        )
    )

    high_dilution = assess_accounting_quality(
        AccountingInput(
            revenue=10_000.0,
            gaap_earnings=1_000.0,
            adjusted_earnings=1_050.0,
            operating_cash_flow=1_300.0,
            capital_expenditure=200.0,
            stock_based_compensation=100.0,
            diluted_shares=110.0,
            diluted_shares_previous=100.0,
        )
    )

    assert no_dilution.accounting_quality_score is not None
    assert high_dilution.accounting_quality_score is not None
    assert (
        high_dilution.accounting_quality_score
        < no_dilution.accounting_quality_score
    )


def test_negative_reported_fcf_generates_warning() -> None:
    assessment = assess_accounting_quality(
        AccountingInput(
            revenue=1_000.0,
            gaap_earnings=100.0,
            adjusted_earnings=110.0,
            operating_cash_flow=100.0,
            capital_expenditure=200.0,
            stock_based_compensation=20.0,
        )
    )

    assert assessment.reported_fcf == -100.0
    assert any(
        "negativo o nulo" in warning
        for warning in assessment.warnings
    )


def test_missing_data_does_not_create_false_score() -> None:
    assessment = assess_accounting_quality(
        AccountingInput()
    )

    assert assessment.reported_fcf is None
    assert assessment.economic_fcf is None
    assert assessment.accounting_quality_score is None
