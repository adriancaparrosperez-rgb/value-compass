from __future__ import annotations

from src.analysis.per_share import (
    PerShareInput,
    assess_per_share_value,
)


def test_per_share_metrics_are_calculated() -> None:
    assessment = assess_per_share_value(
        PerShareInput(
            revenue=1_200.0,
            revenue_previous=1_000.0,
            gaap_earnings=120.0,
            gaap_earnings_previous=100.0,
            reported_fcf=150.0,
            reported_fcf_previous=120.0,
            economic_fcf=130.0,
            economic_fcf_previous=100.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
            buybacks=50.0,
            stock_based_compensation=20.0,
            net_debt=200.0,
        )
    )

    assert assessment.revenue_per_share == 12.0
    assert assessment.reported_fcf_per_share == 1.5
    assert assessment.economic_fcf_per_share == 1.3
    assert assessment.net_debt_per_share == 2.0
    assert assessment.net_buybacks_after_sbc == 30.0
    assert assessment.per_share_value_score is not None


def test_reducing_share_count_improves_per_share_metrics() -> None:
    assessment = assess_per_share_value(
        PerShareInput(
            revenue=1_000.0,
            revenue_previous=1_000.0,
            gaap_earnings=100.0,
            gaap_earnings_previous=100.0,
            reported_fcf=120.0,
            reported_fcf_previous=120.0,
            economic_fcf=100.0,
            economic_fcf_previous=100.0,
            diluted_shares=90.0,
            diluted_shares_previous=100.0,
        )
    )

    assert assessment.share_count_growth == -0.1
    assert assessment.revenue_per_share_growth is not None
    assert assessment.revenue_per_share_growth > 0
    assert assessment.fcf_per_share_growth is not None
    assert assessment.fcf_per_share_growth > 0
    assert assessment.per_share_value_score is not None
    assert assessment.per_share_value_score >= 70.0


def test_dilution_reduces_per_share_value_score() -> None:
    stable = assess_per_share_value(
        PerShareInput(
            revenue=1_100.0,
            revenue_previous=1_000.0,
            gaap_earnings=110.0,
            gaap_earnings_previous=100.0,
            reported_fcf=132.0,
            reported_fcf_previous=120.0,
            economic_fcf=110.0,
            economic_fcf_previous=100.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
        )
    )

    diluted = assess_per_share_value(
        PerShareInput(
            revenue=1_100.0,
            revenue_previous=1_000.0,
            gaap_earnings=110.0,
            gaap_earnings_previous=100.0,
            reported_fcf=132.0,
            reported_fcf_previous=120.0,
            economic_fcf=110.0,
            economic_fcf_previous=100.0,
            diluted_shares=110.0,
            diluted_shares_previous=100.0,
        )
    )

    assert stable.per_share_value_score is not None
    assert diluted.per_share_value_score is not None
    assert (
        diluted.per_share_value_score
        < stable.per_share_value_score
    )


def test_high_dilution_generates_warning() -> None:
    assessment = assess_per_share_value(
        PerShareInput(
            revenue=1_000.0,
            revenue_previous=1_000.0,
            gaap_earnings=100.0,
            gaap_earnings_previous=100.0,
            reported_fcf=100.0,
            reported_fcf_previous=100.0,
            economic_fcf=90.0,
            economic_fcf_previous=90.0,
            diluted_shares=108.0,
            diluted_shares_previous=100.0,
        )
    )

    assert assessment.share_count_growth == 0.08
    assert any(
        "dilución" in warning.lower()
        for warning in assessment.warnings
    )


def test_buybacks_that_do_not_cover_sbc_generate_warning() -> None:
    assessment = assess_per_share_value(
        PerShareInput(
            revenue=1_000.0,
            revenue_previous=900.0,
            gaap_earnings=100.0,
            gaap_earnings_previous=90.0,
            reported_fcf=120.0,
            reported_fcf_previous=100.0,
            economic_fcf=80.0,
            economic_fcf_previous=75.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
            buybacks=50.0,
            stock_based_compensation=80.0,
        )
    )

    assert assessment.net_buybacks_after_sbc == -30.0
    assert any(
        "no compensan" in warning.lower()
        for warning in assessment.warnings
    )


def test_economic_fcf_growth_is_preferred() -> None:
    assessment = assess_per_share_value(
        PerShareInput(
            revenue=1_100.0,
            revenue_previous=1_000.0,
            gaap_earnings=110.0,
            gaap_earnings_previous=100.0,
            reported_fcf=150.0,
            reported_fcf_previous=100.0,
            economic_fcf=105.0,
            economic_fcf_previous=100.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
        )
    )

    assert assessment.fcf_per_share_growth == 0.05


def test_missing_data_does_not_create_false_score() -> None:
    assessment = assess_per_share_value(
        PerShareInput()
    )

    assert assessment.revenue_per_share is None
    assert assessment.reported_fcf_per_share is None
    assert assessment.economic_fcf_per_share is None
    assert assessment.per_share_value_score is None


def test_zero_shares_are_rejected() -> None:
    assessment = assess_per_share_value(
        PerShareInput(
            revenue=1_000.0,
            diluted_shares=0.0,
            diluted_shares_previous=100.0,
        )
    )

    assert assessment.revenue_per_share is None
    assert any(
        "acciones diluidas actuales" in warning.lower()
        for warning in assessment.warnings
    )


def test_negative_net_debt_is_allowed() -> None:
    assessment = assess_per_share_value(
        PerShareInput(
            revenue=1_000.0,
            revenue_previous=900.0,
            gaap_earnings=100.0,
            gaap_earnings_previous=90.0,
            reported_fcf=120.0,
            reported_fcf_previous=100.0,
            economic_fcf=110.0,
            economic_fcf_previous=95.0,
            diluted_shares=100.0,
            diluted_shares_previous=100.0,
            net_debt=-200.0,
        )
    )

    assert assessment.net_debt_per_share == -2.0
