from __future__ import annotations
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
from src.decision.enums import (
    DataQualityStatus,
    EvidenceConfidence,
    MoatStrength,
    MoatTrend,
    ValuationStatus,
)
from src.decision.models import (
    AccountingAssessment,
    BusinessAssessment,
    DataQualityAssessment,
    MasterAnalysisInput,
    MoatAssessment,
    PerShareAssessment,
    SourceReference,
    ValuationAssessment,
)
from src.models import CompanySnapshot, ScoreCard
from src.services.master_analysis_builder import (
    BUILDER_VERSION,
    DEFAULT_MODEL_VERSION,
    FINANCIAL_SOURCE_TYPES,
    GENERIC_SOURCE_TYPE,
    MINIMUM_PRELIMINARY_CONFIDENCE,
    MINIMUM_PRELIMINARY_COVERAGE,
    MULTIPLE_OFFICIAL_FINANCIAL_SOURCE_SCORE,
    MULTIPLE_SECONDARY_SOURCE_SCORE,
    OFFICIAL_CONTEXT_SOURCE_SCORE,
    OFFICIAL_CONTEXT_SOURCE_TYPES,
    ONE_OFFICIAL_FINANCIAL_SOURCE_SCORE,
    SINGLE_SECONDARY_SOURCE_SCORE,
    YAHOO_SOURCE_TYPE,
    MasterAnalysisBuilderError,
    _bounded_score,
    _build_sources,
    _covered_score,
    _deduplicate_sources,
    _deduplicate_strings,
    _freshness_score,
    _is_official_context_source,
    _is_official_financial_source,
    _is_yahoo_snapshot,
    _latest_datetime_string,
    _latest_financial_source_date,
    _normalize_model_version,
    _normalize_text,
    _number,
    _parse_datetime,
    _source_key,
    _source_quality_score,
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
)
def _iso_days_ago(
    days: int,
) -> str:
    return (
        NOW - timedelta(days=days)
    ).isoformat()
def _snapshot(
    **overrides: Any,
) -> CompanySnapshot:
    values: dict[str, Any] = {
        "ticker": " TEST ",
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
        "capex": None,
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
        "fetched_at": _iso_days_ago(0),
        "price_date": _iso_days_ago(0),
        "fundamentals_date": _iso_days_ago(60),
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
        "calculated_at": _iso_days_ago(0),
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
def _financial_source(
    *,
    name: str = "Annual Report",
    source_type: str = "annual_report",
    url: str = "https://example.com/annual-report",
    published_at: str | None = None,
) -> SourceReference:
    return SourceReference(
        name=name,
        source_type=source_type,
        url=url,
        published_at=(
            published_at
            or _iso_days_ago(30)
        ),
        retrieved_at=_iso_days_ago(0),
        is_official=True,
    )
def _context_source(
    *,
    name: str = "Corporate Press Release",
    source_type: str = "official_press_release",
    url: str = "https://example.com/press-release",
    published_at: str | None = None,
) -> SourceReference:
    return SourceReference(
        name=name,
        source_type=source_type,
        url=url,
        published_at=(
            published_at
            or _iso_days_ago(5)
        ),
        retrieved_at=_iso_days_ago(0),
        is_official=True,
    )
def _secondary_source(
    *,
    name: str = "Secondary Research",
    url: str = "https://secondary.example.com/test",
) -> SourceReference:
    return SourceReference(
        name=name,
        source_type="secondary_research",
        url=url,
        published_at=_iso_days_ago(20),
        retrieved_at=_iso_days_ago(0),
        is_official=False,
    )
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (10, 10.0),
        ("10.5", 10.5),
        (0, 0.0),
        (-5, -5.0),
        (None, None),
        (True, None),
        (False, None),
        ("invalid", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
    ],
)
def test_number_accepts_only_finite_numeric_values(
    value: Any,
    expected: float | None,
) -> None:
    assert _number(value) == expected
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-10, 0.0),
        (0, 0.0),
        (50.55, 50.5),
        (100, 100.0),
        (150, 100.0),
        (None, None),
        ("invalid", None),
        (True, None),
        (float("nan"), None),
    ],
)
def test_bounded_score(
    value: Any,
    expected: float | None,
) -> None:
    assert _bounded_score(value) == expected
def test_normalize_text_trims_and_converts_values() -> None:
    assert _normalize_text(
        " Test Company ",
        maximum_length=100,
    ) == "Test Company"
    assert _normalize_text(
        123,
        maximum_length=100,
    ) == "123"
    assert _normalize_text(
        "   ",
        maximum_length=100,
    ) is None
    assert _normalize_text(
        None,
        maximum_length=100,
    ) is None
def test_normalize_text_truncates_long_value() -> None:
    result = _normalize_text(
        "A" * 20,
        maximum_length=10,
    )
    assert result == (
        "A" * 9 + "…"
    )
    assert len(result) == 10
def test_normalize_text_handles_one_character_limit() -> None:
    assert _normalize_text(
        "ABCDE",
        maximum_length=1,
    ) == "…"
def test_normalize_text_rejects_invalid_maximum_length() -> None:
    with pytest.raises(
        ValueError,
        match="mayor que cero",
    ):
        _normalize_text(
            "Test",
            maximum_length=0,
        )
def test_deduplicate_strings_is_case_insensitive() -> None:
    result = _deduplicate_strings(
        [
            " First warning ",
            "first warning",
            "",
            None,
            123,
            "Second warning",
        ]
    )
    assert result == [
        "First warning",
        "Second warning",
    ]
@pytest.mark.parametrize(
    "value",
    [
        "2026-06-27T12:00:00+00:00",
        "2026-06-27T12:00:00Z",
        "2026-06-27T12:00:00",
    ],
)
def test_parse_datetime_accepts_iso_values(
    value: str,
) -> None:
    result = _parse_datetime(
        value
    )
    assert result is not None
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)
@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "invalid",
        123,
    ],
)
def test_parse_datetime_rejects_invalid_values(
    value: Any,
) -> None:
    assert _parse_datetime(value) is None
@pytest.mark.parametrize(
    ("days_old", "expected"),
    [
        (0, 100.0),
        (1, 100.0),
        (7, 90.0),
        (30, 80.0),
        (90, 65.0),
        (180, 50.0),
        (365, 30.0),
        (500, 10.0),
    ],
)
def test_freshness_score_age_bands(
    days_old: int,
    expected: float,
) -> None:
    value = (
        NOW - timedelta(days=days_old)
    ).isoformat()
    assert _freshness_score(
        value,
        now=NOW,
    ) == expected
def test_freshness_score_accepts_naive_now() -> None:
    naive_now = NOW.replace(
        tzinfo=None
    )
    assert _freshness_score(
        NOW.isoformat(),
        now=naive_now,
    ) == 100.0
def test_freshness_score_rejects_future_date() -> None:
    future_value = (
        NOW + timedelta(days=2)
    ).isoformat()
    assert _freshness_score(
        future_value,
        now=NOW,
    ) == 0.0
def test_latest_datetime_string_returns_latest_valid_date() -> None:
    result = _latest_datetime_string(
        [
            _iso_days_ago(100),
            None,
            "invalid",
            _iso_days_ago(5),
            _iso_days_ago(20),
        ]
    )
    assert result == _iso_days_ago(5)
def test_latest_datetime_string_returns_none_without_dates() -> None:
    assert _latest_datetime_string(
        [
            None,
            "",
            "invalid",
        ]
    ) is None
def test_model_version_is_normalized() -> None:
    assert _normalize_model_version(
        " 1.3.0 "
    ) == "1.3.0"
@pytest.mark.parametrize(
    ("value", "message"),
    [
        (
            None,
            "debe ser texto",
        ),
        (
            "",
            "no puede estar vacía",
        ),
        (
            "A" * 51,
            "no puede superar",
        ),
    ],
)
def test_invalid_model_version_raises_controlled_error(
    value: Any,
    message: str,
) -> None:
    with pytest.raises(
        MasterAnalysisBuilderError,
        match=message,
    ):
        _normalize_model_version(
            value
        )
def test_financial_source_types_are_declared() -> None:
    assert "annual_report" in (
        FINANCIAL_SOURCE_TYPES
    )
    assert "quarterly_report" in (
        FINANCIAL_SOURCE_TYPES
    )
    assert "regulatory_filing" in (
        FINANCIAL_SOURCE_TYPES
    )
def test_context_source_types_are_declared() -> None:
    assert "official_press_release" in (
        OFFICIAL_CONTEXT_SOURCE_TYPES
    )
    assert "official_company_page" in (
        OFFICIAL_CONTEXT_SOURCE_TYPES
    )
def test_financial_source_is_classified_correctly() -> None:
    source = _financial_source()
    assert _is_official_financial_source(
        source
    ) is True
    assert _is_official_context_source(
        source
    ) is False
def test_context_source_is_classified_correctly() -> None:
    source = _context_source()
    assert _is_official_context_source(
        source
    ) is True
    assert _is_official_financial_source(
        source
    ) is False
def test_non_official_source_is_not_financially_official() -> None:
    source = SourceReference(
        name="Unofficial Annual Report Copy",
        source_type="annual_report",
        url="https://secondary.example.com/report",
        published_at=_iso_days_ago(30),
        retrieved_at=_iso_days_ago(0),
        is_official=False,
    )
    assert _is_official_financial_source(
        source
    ) is False
def test_yahoo_snapshot_is_detected_from_metadata() -> None:
    assert _is_yahoo_snapshot(
        _snapshot()
    ) is True
def test_yahoo_snapshot_is_detected_from_source_name() -> None:
    snapshot = _snapshot(
        source="Yahoo market data",
        provider_metadata={},
    )
    assert _is_yahoo_snapshot(
        snapshot
    ) is True
def test_non_yahoo_snapshot_is_not_misclassified() -> None:
    snapshot = _snapshot(
        source="Alternative Data Provider",
        provider_metadata={
            "provider": "Alternative Data",
        },
    )
    assert _is_yahoo_snapshot(
        snapshot
    ) is False
def test_build_sources_creates_yahoo_reference() -> None:
    sources = _build_sources(
        _snapshot(),
        None,
    )
    assert len(sources) == 1
    source = sources[0]
    assert source.source_type == (
        YAHOO_SOURCE_TYPE
    )
    assert source.is_official is False
    assert source.url is not None
    assert "/quote/TEST" in source.url
def test_build_sources_creates_generic_reference() -> None:
    snapshot = _snapshot(
        source="Alternative Data Provider",
        provider_metadata={
            "provider": "Alternative Data",
        },
    )
    sources = _build_sources(
        snapshot,
        None,
    )
    assert len(sources) == 1
    assert sources[0].source_type == (
        GENERIC_SOURCE_TYPE
    )
    assert sources[0].url is None
    assert sources[0].is_official is False
def test_source_key_uses_normalized_url_when_available() -> None:
    source = _financial_source(
        url="HTTPS://EXAMPLE.COM/REPORT/",
    )
    assert _source_key(
        source
    ) == (
        "url",
        "https://example.com/report",
    )
def test_source_key_uses_name_and_type_without_url() -> None:
    source = SourceReference(
        name=" Annual Report ",
        source_type=" annual_report ",
        url=None,
        published_at=None,
        retrieved_at=None,
        is_official=True,
    )
    assert _source_key(
        source
    ) == (
        "annual report",
        "annual_report",
    )
def test_sources_with_same_url_are_deduplicated() -> None:
    first = _financial_source(
        name="Annual Report",
        url="https://example.com/report",
    )
    second = _financial_source(
        name="Audited Financial Statements",
        url="https://example.com/report/",
    )
    result = _deduplicate_sources(
        [
            first,
            second,
        ]
    )
    assert len(result) == 1
def test_sources_without_url_are_deduplicated_by_name_and_type() -> None:
    first = SourceReference(
        name="Annual Report",
        source_type="annual_report",
        url=None,
        published_at=None,
        retrieved_at=None,
        is_official=True,
    )
    second = SourceReference(
        name="annual report",
        source_type="ANNUAL_REPORT",
        url=None,
        published_at=None,
        retrieved_at=None,
        is_official=True,
    )
    result = _deduplicate_sources(
        [
            first,
            second,
        ]
    )
    assert len(result) == 1
def test_build_sources_adds_and_deduplicates_sources() -> None:
    official = _financial_source()
    sources = _build_sources(
        _snapshot(),
        [
            official,
            deepcopy(official),
        ],
    )
    assert len(sources) == 2
    assert sum(
        source.is_official
        for source in sources
    ) == 1
def test_build_sources_rejects_non_list_input() -> None:
    with pytest.raises(
        MasterAnalysisBuilderError,
        match="debe ser una lista",
    ):
        _build_sources(
            _snapshot(),
            "invalid",
        )
def test_build_sources_rejects_invalid_source_element() -> None:
    with pytest.raises(
        MasterAnalysisBuilderError,
        match="SourceReference",
    ):
        _build_sources(
            _snapshot(),
            [
                {
                    "name": "Invalid",
                }
            ],
        )
def test_source_quality_single_secondary_source() -> None:
    sources = _build_sources(
        _snapshot(),
        None,
    )
    assert _source_quality_score(
        sources
    ) == SINGLE_SECONDARY_SOURCE_SCORE
def test_source_quality_multiple_secondary_sources() -> None:
    sources = _build_sources(
        _snapshot(),
        [
            _secondary_source(),
        ],
    )
    assert _source_quality_score(
        sources
    ) == MULTIPLE_SECONDARY_SOURCE_SCORE
def test_source_quality_official_context_source() -> None:
    sources = _build_sources(
        _snapshot(),
        [
            _context_source(),
        ],
    )
    assert _source_quality_score(
        sources
    ) == OFFICIAL_CONTEXT_SOURCE_SCORE
def test_source_quality_one_official_financial_source() -> None:
    sources = _build_sources(
        _snapshot(),
        [
            _financial_source(),
        ],
    )
    assert _source_quality_score(
        sources
    ) == (
        ONE_OFFICIAL_FINANCIAL_SOURCE_SCORE
    )
def test_source_quality_multiple_official_financial_sources() -> None:
    sources = _build_sources(
        _snapshot(),
        [
            _financial_source(
                name="Annual Report",
                url="https://example.com/annual",
            ),
            _financial_source(
                name="Quarterly Report",
                source_type="quarterly_report",
                url="https://example.com/quarterly",
            ),
        ],
    )
    assert _source_quality_score(
        sources
    ) == (
        MULTIPLE_OFFICIAL_FINANCIAL_SOURCE_SCORE
    )
def test_context_source_does_not_outrank_financial_source() -> None:
    context_sources = _build_sources(
        _snapshot(),
        [
            _context_source(),
        ],
    )
    financial_sources = _build_sources(
        _snapshot(),
        [
            _financial_source(),
        ],
    )
    assert _source_quality_score(
        context_sources
    ) < _source_quality_score(
        financial_sources
    )
def test_latest_financial_source_date_ignores_context_sources() -> None:
    result = _latest_financial_source_date(
        [
            _context_source(
                published_at=_iso_days_ago(2)
            ),
            _financial_source(
                published_at=_iso_days_ago(30)
            ),
        ]
    )
    assert result == _iso_days_ago(30)
def test_latest_financial_source_date_uses_latest_financial_document() -> None:
    result = _latest_financial_source_date(
        [
            _financial_source(
                name="Annual Report",
                url="https://example.com/annual",
                published_at=_iso_days_ago(120),
            ),
            _financial_source(
                name="Quarterly Report",
                source_type="quarterly_report",
                url="https://example.com/quarterly",
                published_at=_iso_days_ago(20),
            ),
        ]
    )
    assert result == _iso_days_ago(20)
def test_build_master_analysis_returns_complete_contract() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    assert isinstance(
        result,
        MasterAnalysisInput,
    )
    assert result.ticker == "TEST"
    assert result.company_name == "Test Company"
    assert result.model_version == (
        DEFAULT_MODEL_VERSION
    )
    assert isinstance(
        result.data_quality,
        DataQualityAssessment,
    )
    assert isinstance(
        result.business,
        BusinessAssessment,
    )
    assert isinstance(
        result.accounting,
        AccountingAssessment,
    )
    assert isinstance(
        result.per_share,
        PerShareAssessment,
    )
    assert isinstance(
        result.moat,
        MoatAssessment,
    )
    assert isinstance(
        result.valuation,
        ValuationAssessment,
    )
    assert len(result.sources) == 1
def test_builder_never_claims_field_validation_automatically() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        additional_sources=[
            _financial_source(),
        ],
    )
    quality = result.data_quality
    assert quality.price_validated is False
    assert quality.currency_validated is False
    assert quality.ticker_validated is False
    assert quality.market_cap_validated is False
    assert quality.fundamentals_validated is False
def test_ticker_consistency_is_not_external_validation() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    assert result.data_quality.ticker_validated is False
    assert any(
        "no ha sido validado externamente"
        in warning.casefold()
        for warning
        in result.data_quality.warnings
    )
def test_yahoo_only_does_not_produce_validated_status() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    assert result.data_quality.status != (
        DataQualityStatus.VALIDATED
    )
def test_official_financial_source_does_not_validate_fields_by_itself() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        additional_sources=[
            _financial_source(),
        ],
    )
    quality = result.data_quality
    assert quality.official_source_count == 1
    assert quality.source_count == 2
    assert quality.price_validated is False
    assert quality.currency_validated is False
    assert quality.ticker_validated is False
    assert quality.market_cap_validated is False
    assert quality.fundamentals_validated is False
    assert any(
        "campo por campo"
        in warning.casefold()
        for warning in quality.warnings
    )
def test_context_source_does_not_replace_fundamentals_date() -> None:
    snapshot = _snapshot(
        fundamentals_date=_iso_days_ago(90)
    )
    result = build_master_analysis(
        snapshot,
        _score_card(),
        additional_sources=[
            _context_source(
                published_at=_iso_days_ago(2)
            ),
        ],
    )
    assert (
        result.data_quality.fundamentals_date
        == _iso_days_ago(90)
    )
def test_financial_source_can_update_fundamentals_reference_date() -> None:
    snapshot = _snapshot(
        fundamentals_date=_iso_days_ago(90)
    )
    result = build_master_analysis(
        snapshot,
        _score_card(),
        additional_sources=[
            _financial_source(
                published_at=_iso_days_ago(10)
            ),
        ],
    )
    assert (
        result.data_quality.fundamentals_date
        == _iso_days_ago(10)
    )
def test_context_source_does_not_remove_missing_financial_source_warning() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        additional_sources=[
            _context_source(),
        ],
    )
    assert any(
        "ninguna fuente financiera oficial"
        in warning.casefold()
        for warning
        in result.data_quality.warnings
    )
def test_financial_source_changes_financial_source_warning() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        additional_sources=[
            _financial_source(),
        ],
    )
    assert not any(
        "ninguna fuente financiera oficial"
        in warning.casefold()
        for warning
        in result.data_quality.warnings
    )
    assert any(
        "documentación financiera oficial"
        in warning.casefold()
        for warning
        in result.data_quality.warnings
    )
def test_low_confidence_marks_data_as_insufficient() -> None:
    score = _score_card(
        confidence=(
            MINIMUM_PRELIMINARY_CONFIDENCE
            - 0.1
        )
    )
    result = build_master_analysis(
        _snapshot(),
        score,
    )
    assert result.data_quality.status == (
        DataQualityStatus.INSUFFICIENT
    )
    assert any(
        "confianza"
        in issue.casefold()
        for issue
        in result.data_quality.blocking_issues
    )
def test_low_coverage_marks_data_as_insufficient() -> None:
    score = _score_card(
        overall_coverage=(
            MINIMUM_PRELIMINARY_COVERAGE
            - 0.1
        )
    )
    result = build_master_analysis(
        _snapshot(),
        score,
    )
    assert result.data_quality.status == (
        DataQualityStatus.INSUFFICIENT
    )
    assert any(
        "cobertura"
        in issue.casefold()
        for issue
        in result.data_quality.blocking_issues
    )
def test_provider_error_marks_data_as_insufficient() -> None:
    result = build_master_analysis(
        _snapshot(
            errors="Provider error",
        ),
        _score_card(),
    )
    assert result.data_quality.status == (
        DataQualityStatus.INSUFFICIENT
    )
    assert "Provider error" in (
        result.data_quality.blocking_issues
    )
def test_missing_price_marks_data_as_insufficient() -> None:
    result = build_master_analysis(
        _snapshot(
            price=None,
            critical_missing_fields=[
                "price",
            ],
        ),
        _score_card(),
    )
    assert result.data_quality.status == (
        DataQualityStatus.INSUFFICIENT
    )
    assert any(
        "precio válido"
        in issue.casefold()
        for issue
        in result.data_quality.blocking_issues
    )
def test_coverage_score_combines_snapshot_and_radar_coverage() -> None:
    result = build_master_analysis(
        _snapshot(
            coverage_score=80.0
        ),
        _score_card(
            overall_coverage=60.0
        ),
    )
    assert (
        result.data_quality.coverage_score
        == 70.0
    )
def test_business_maps_only_supported_preliminary_scores() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    business = result.business
    assert business.sector == "Industrials"
    assert business.industry == (
        "Industrial Products"
    )
    assert business.business_model is None
    assert (
        business.operating_quality_score
        == 80.0
    )
    assert business.balance_score == 70.0
    assert business.cash_score == 75.0
    assert (
        business.capital_allocation_score
        == 60.0
    )
    assert business.risk_score is None
    assert business.organic_growth_score is None
    assert business.organic_revenue_growth is None
    assert (
        business.return_on_invested_capital
        is None
    )
    assert any(
        BUILDER_VERSION in note
        for note in business.notes
    )
def test_uncovered_business_dimension_is_not_transferred() -> None:
    score = _score_card(
        quality=50.0,
        capital_allocation=50.0,
        dimension_coverage=(
            _dimension_coverage(
                quality=0.0,
                capital_allocation=0.0,
            )
        ),
    )
    result = build_master_analysis(
        _snapshot(),
        score,
    )
    assert (
        result.business.operating_quality_score
        is None
    )
    assert (
        result.business.capital_allocation_score
        is None
    )
def test_uncovered_valuation_is_not_transferred_as_neutral_score() -> None:
    score = _score_card(
        valuation=50.0,
        dimension_coverage=(
            _dimension_coverage(
                valuation=0.0
            )
        ),
    )
    result = build_master_analysis(
        _snapshot(),
        score,
    )
    assert (
        result.valuation.multiples_score
        is None
    )
def test_partial_dimension_coverage_allows_preliminary_score() -> None:
    score = _score_card(
        quality=80.0,
        dimension_coverage=(
            _dimension_coverage(
                quality=50.0
            )
        ),
    )
    assert _covered_score(
        score,
        "quality",
        score.quality,
    ) == 80.0
def test_missing_dimension_coverage_returns_none() -> None:
    score = _score_card(
        dimension_coverage={
            "valuation": 100.0,
        }
    )
    assert _covered_score(
        score,
        "quality",
        score.quality,
    ) is None
def test_accounting_does_not_invent_quality_metrics() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    accounting = result.accounting
    assert accounting.gaap_earnings == (
        50_000_000.0
    )
    assert accounting.operating_cash_flow == (
        90_000_000.0
    )
    assert accounting.reported_fcf == (
        60_000_000.0
    )
    assert accounting.adjusted_earnings is None
    assert accounting.economic_fcf is None
    assert accounting.cash_conversion_score is None
    assert accounting.earnings_quality_score is None
    assert accounting.accounting_quality_score is None
    assert (
        accounting.uses_sbc_adjusted_fcf
        is False
    )
def test_accounting_warns_when_capex_is_missing() -> None:
    result = build_master_analysis(
        _snapshot(
            capex=None,
        ),
        _score_card(),
    )
    assert any(
        "capex"
        in warning.casefold()
        for warning
        in result.accounting.warnings
    )
def test_per_share_does_not_treat_outstanding_shares_as_diluted() -> None:
    result = build_master_analysis(
        _snapshot(
            shares=10_000_000.0,
        ),
        _score_card(),
    )
    per_share = result.per_share
    assert per_share.diluted_shares is None
    assert per_share.diluted_shares_previous is None
    assert per_share.revenue_per_share is None
    assert per_share.reported_fcf_per_share is None
    assert per_share.gaap_eps_growth is None
    assert any(
        "no equivalen"
        in note.casefold()
        for note in per_share.notes
    )
def test_default_moat_is_not_evaluated() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    assert result.moat.strength == (
        MoatStrength.NOT_EVALUATED
    )
    assert result.moat.trend == (
        MoatTrend.NOT_EVALUATED
    )
    assert result.moat.confidence == (
        EvidenceConfidence.NOT_EVALUABLE
    )
def test_default_valuation_is_not_intrinsic_valuation() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    valuation = result.valuation
    assert valuation.current_price == 100.0
    assert valuation.currency == "EUR"
    assert valuation.multiples_score == 72.0
    assert valuation.valuation_score is None
    assert valuation.status == (
        ValuationStatus.NOT_EVALUATED
    )
    assert valuation.conservative is None
    assert valuation.base is None
    assert valuation.optimistic is None
    assert valuation.reverse_dcf_growth is None
    assert valuation.reverse_dcf_margin is None
    assert valuation.reverse_dcf_status is None
@pytest.mark.parametrize(
    ("field_name", "expected_type"),
    [
        (
            "data_quality",
            "DataQualityAssessment",
        ),
        (
            "business",
            "BusinessAssessment",
        ),
        (
            "accounting",
            "AccountingAssessment",
        ),
        (
            "per_share",
            "PerShareAssessment",
        ),
        (
            "moat",
            "MoatAssessment",
        ),
        (
            "valuation",
            "ValuationAssessment",
        ),
    ],
)
def test_invalid_optional_assessment_type_is_rejected(
    field_name: str,
    expected_type: str,
) -> None:
    kwargs = {
        field_name: object(),
    }
    with pytest.raises(
        MasterAnalysisBuilderError,
        match=expected_type,
    ):
        build_master_analysis(
            _snapshot(),
            _score_card(),
            **kwargs,
        )
def test_custom_data_quality_is_defensively_copied() -> None:
    baseline = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    custom_quality = deepcopy(
        baseline.data_quality
    )
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        data_quality=custom_quality,
    )
    assert result.data_quality == (
        custom_quality
    )
    assert result.data_quality is not (
        custom_quality
    )
def test_all_optional_assessments_are_defensively_copied() -> None:
    baseline = build_master_analysis(
        _snapshot(),
        _score_card(),
    )
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        business=baseline.business,
        accounting=baseline.accounting,
        per_share=baseline.per_share,
        moat=baseline.moat,
        valuation=baseline.valuation,
    )
    assert result.business == baseline.business
    assert result.accounting == baseline.accounting
    assert result.per_share == baseline.per_share
    assert result.moat == baseline.moat
    assert result.valuation == baseline.valuation
    assert result.business is not baseline.business
    assert result.accounting is not baseline.accounting
    assert result.per_share is not baseline.per_share
    assert result.moat is not baseline.moat
    assert result.valuation is not baseline.valuation
def test_builder_rejects_snapshot_score_ticker_mismatch() -> None:
    with pytest.raises(
        MasterAnalysisBuilderError,
        match="no coincide",
    ):
        build_master_analysis(
            _snapshot(
                ticker="AAA",
            ),
            _score_card(
                ticker="BBB",
            ),
        )
def test_builder_rejects_invalid_snapshot_type() -> None:
    with pytest.raises(
        MasterAnalysisBuilderError,
        match="CompanySnapshot",
    ):
        build_master_analysis(
            {},  # type: ignore[arg-type]
            _score_card(),
        )
def test_builder_rejects_invalid_score_type() -> None:
    with pytest.raises(
        MasterAnalysisBuilderError,
        match="ScoreCard",
    ):
        build_master_analysis(
            _snapshot(),
            {},  # type: ignore[arg-type]
        )
def test_builder_normalizes_model_version() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        model_version=" 2.5.0 ",
    )
    assert result.model_version == "2.5.0"
def test_builder_does_not_mutate_snapshot_or_score() -> None:
    snapshot = _snapshot(
        warnings=[
            "Original warning",
        ],
    )
    score = _score_card(
        warnings=[
            "Score warning",
        ],
    )
    snapshot_before = snapshot.to_dict()
    score_before = score.to_dict()
    build_master_analysis(
        snapshot,
        score,
        additional_sources=[
            _financial_source(),
        ],
    )
    assert snapshot.to_dict() == (
        snapshot_before
    )
    assert score.to_dict() == (
        score_before
    )
def test_builder_output_is_independent_from_input_mutations() -> None:
    snapshot = _snapshot()
    score = _score_card()
    result = build_master_analysis(
        snapshot,
        score,
    )
    snapshot.name = "Changed Company"
    snapshot.warnings.append(
        "Changed warning"
    )
    score.rationale = (
        "Changed rationale"
    )
    score.dimension_coverage[
        "valuation"
    ] = 0.0
    assert result.company_name == (
        "Test Company"
    )
    assert not any(
        warning == "Changed warning"
        for warning
        in result.data_quality.warnings
    )
    assert (
        result.valuation.multiples_score
        == 72.0
    )
def test_additional_sources_are_defensively_copied() -> None:
    source = _financial_source()
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        additional_sources=[
            source,
        ],
    )
    source.name = "Changed source"
    assert result.sources[1].name != (
        "Changed source"
    )
def test_warnings_are_deduplicated_across_snapshot_and_score() -> None:
    snapshot = _snapshot(
        warnings=[
            "Shared warning",
        ],
    )
    score = _score_card(
        warnings=[
            "shared warning",
        ],
    )
    result = build_master_analysis(
        snapshot,
        score,
    )
    assert sum(
        warning.casefold()
        == "shared warning"
        for warning
        in result.data_quality.warnings
    ) == 1
def test_master_analysis_is_json_serializable() -> None:
    result = build_master_analysis(
        _snapshot(),
        _score_card(),
        additional_sources=[
            _financial_source(),
        ],
    )
    serialized = json.dumps(
        result.to_dict(),
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert "TEST" in serialized
    assert "Test Company" in serialized
    assert DEFAULT_MODEL_VERSION in serialized
