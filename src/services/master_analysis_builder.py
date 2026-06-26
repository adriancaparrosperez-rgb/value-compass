from __future__ import annotations
import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
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
BUILDER_VERSION = "1.3.0"
DEFAULT_MODEL_VERSION = "0.1.0"
MINIMUM_PRELIMINARY_CONFIDENCE = 55.0
MINIMUM_PRELIMINARY_COVERAGE = 50.0
YAHOO_SOURCE_TYPE = "secondary_market_data"
GENERIC_SOURCE_TYPE = "secondary_data"
FINANCIAL_SOURCE_TYPES = frozenset(
    {
        "official_filing",
        "annual_report",
        "quarterly_report",
        "interim_report",
        "regulatory_filing",
        "earnings_release",
        "official_financial_results",
    }
)
OFFICIAL_CONTEXT_SOURCE_TYPES = frozenset(
    {
        "official_company_page",
        "official_press_release",
        "official_investor_relations",
    }
)
SINGLE_SECONDARY_SOURCE_SCORE = 35.0
MULTIPLE_SECONDARY_SOURCE_SCORE = 50.0
OFFICIAL_CONTEXT_SOURCE_SCORE = 60.0
ONE_OFFICIAL_FINANCIAL_SOURCE_SCORE = 80.0
MULTIPLE_OFFICIAL_FINANCIAL_SOURCE_SCORE = 95.0
class MasterAnalysisBuilderError(ValueError):
    """Error controlado al construir un análisis maestro."""
def _number(
    value: Any,
) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(numeric_value):
        return None
    return numeric_value
def _bounded_score(
    value: Any,
) -> float | None:
    numeric_value = _number(value)
    if numeric_value is None:
        return None
    return round(
        max(
            0.0,
            min(
                100.0,
                numeric_value,
            ),
        ),
        1,
    )
def _normalize_text(
    value: Any,
    *,
    maximum_length: int,
) -> str | None:
    if value is None:
        return None
    if maximum_length < 1:
        raise ValueError(
            "maximum_length debe ser mayor que cero."
        )
    if isinstance(value, str):
        normalized_value = value.strip()
    else:
        normalized_value = str(value).strip()
    if not normalized_value:
        return None
    if len(normalized_value) > maximum_length:
        if maximum_length == 1:
            return "…"
        return (
            normalized_value[: maximum_length - 1]
            + "…"
        )
    return normalized_value
def _deduplicate_strings(
    values: list[Any],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        normalized_value = value.strip()
        if not normalized_value:
            continue
        comparison_key = normalized_value.casefold()
        if comparison_key in seen:
            continue
        seen.add(comparison_key)
        result.append(normalized_value)
    return result
def _parse_datetime(
    value: Any,
) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized_value = value.strip()
    if not normalized_value:
        return None
    try:
        parsed_value = datetime.fromisoformat(
            normalized_value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None
    if parsed_value.tzinfo is None:
        parsed_value = parsed_value.replace(
            tzinfo=timezone.utc
        )
    return parsed_value.astimezone(
        timezone.utc
    )
def _freshness_score(
    value: Any,
    *,
    now: datetime | None = None,
) -> float:
    parsed_value = _parse_datetime(value)
    if parsed_value is None:
        return 0.0
    if now is None:
        current_time = datetime.now(
            timezone.utc
        )
    elif now.tzinfo is None:
        current_time = now.replace(
            tzinfo=timezone.utc
        )
    else:
        current_time = now.astimezone(
            timezone.utc
        )
    age_days = (
        current_time - parsed_value
    ).total_seconds() / 86_400.0
    if age_days < -1.0:
        return 0.0
    age_days = max(
        0.0,
        age_days,
    )
    if age_days <= 1.0:
        return 100.0
    if age_days <= 7.0:
        return 90.0
    if age_days <= 30.0:
        return 80.0
    if age_days <= 90.0:
        return 65.0
    if age_days <= 180.0:
        return 50.0
    if age_days <= 365.0:
        return 30.0
    return 10.0
def _latest_datetime_string(
    values: list[Any],
) -> str | None:
    valid_dates = [
        parsed_value
        for value in values
        if (
            parsed_value := _parse_datetime(value)
        )
        is not None
    ]
    if not valid_dates:
        return None
    return max(
        valid_dates
    ).isoformat()
def _normalize_model_version(
    model_version: Any,
) -> str:
    if not isinstance(
        model_version,
        str,
    ):
        raise MasterAnalysisBuilderError(
            "La versión del modelo debe ser texto."
        )
    normalized_version = model_version.strip()
    if not normalized_version:
        raise MasterAnalysisBuilderError(
            "La versión del modelo no puede estar vacía."
        )
    if len(normalized_version) > 50:
        raise MasterAnalysisBuilderError(
            "La versión del modelo no puede superar "
            "50 caracteres."
        )
    return normalized_version
def _validate_inputs(
    snapshot: Any,
    score: Any,
) -> tuple[
    CompanySnapshot,
    ScoreCard,
]:
    if not isinstance(
        snapshot,
        CompanySnapshot,
    ):
        raise MasterAnalysisBuilderError(
            "snapshot debe ser una instancia "
            "de CompanySnapshot."
        )
    if not isinstance(
        score,
        ScoreCard,
    ):
        raise MasterAnalysisBuilderError(
            "score debe ser una instancia de ScoreCard."
        )
    snapshot_ticker = _normalize_text(
        snapshot.ticker,
        maximum_length=30,
    )
    score_ticker = _normalize_text(
        score.ticker,
        maximum_length=30,
    )
    if not snapshot_ticker:
        raise MasterAnalysisBuilderError(
            "El snapshot no contiene un ticker válido."
        )
    if not score_ticker:
        raise MasterAnalysisBuilderError(
            "El score no contiene un ticker válido."
        )
    if (
        snapshot_ticker.upper()
        != score_ticker.upper()
    ):
        raise MasterAnalysisBuilderError(
            "El ticker del snapshot no coincide "
            "con el ticker del score."
        )
    return snapshot, score
def _copy_assessment(
    value: Any,
    *,
    expected_type: type,
    field_name: str,
) -> Any:
    if not isinstance(
        value,
        expected_type,
    ):
        raise MasterAnalysisBuilderError(
            f"{field_name} debe ser una instancia "
            f"de {expected_type.__name__}."
        )
    try:
        return deepcopy(value)
    except Exception as error:
        raise MasterAnalysisBuilderError(
            f"No se pudo copiar de forma segura {field_name}."
        ) from error
def _validate_source(
    source: Any,
    *,
    field_name: str,
) -> SourceReference:
    if not isinstance(
        source,
        SourceReference,
    ):
        raise MasterAnalysisBuilderError(
            f"{field_name} debe contener únicamente "
            "instancias de SourceReference."
        )
    name = _normalize_text(
        source.name,
        maximum_length=250,
    )
    source_type = _normalize_text(
        source.source_type,
        maximum_length=100,
    )
    if not name:
        raise MasterAnalysisBuilderError(
            "Cada fuente debe contener un nombre."
        )
    if not source_type:
        raise MasterAnalysisBuilderError(
            "Cada fuente debe contener un tipo."
        )
    if not isinstance(
        source.is_official,
        bool,
    ):
        raise MasterAnalysisBuilderError(
            "El indicador is_official debe ser booleano."
        )
    return SourceReference(
        name=name,
        source_type=source_type,
        url=_normalize_text(
            source.url,
            maximum_length=2_000,
        ),
        published_at=_normalize_text(
            source.published_at,
            maximum_length=100,
        ),
        retrieved_at=_normalize_text(
            source.retrieved_at,
            maximum_length=100,
        ),
        is_official=source.is_official,
    )
def _normalized_source_type(
    source: SourceReference,
) -> str:
    return source.source_type.strip().casefold()
def _is_official_financial_source(
    source: SourceReference,
) -> bool:
    return (
        source.is_official
        and _normalized_source_type(
            source
        )
        in FINANCIAL_SOURCE_TYPES
    )
def _is_official_context_source(
    source: SourceReference,
) -> bool:
    return (
        source.is_official
        and _normalized_source_type(
            source
        )
        in OFFICIAL_CONTEXT_SOURCE_TYPES
    )
def _source_key(
    source: SourceReference,
) -> tuple[str, str]:
    normalized_url = (
        source.url.strip().casefold().rstrip("/")
        if source.url
        else ""
    )
    if normalized_url:
        return (
            "url",
            normalized_url,
        )
    return (
        source.name.strip().casefold(),
        source.source_type.strip().casefold(),
    )
def _deduplicate_sources(
    sources: list[SourceReference],
) -> list[SourceReference]:
    result: list[SourceReference] = []
    seen: set[
        tuple[str, str]
    ] = set()
    for source in sources:
        source_key = _source_key(
            source
        )
        if source_key in seen:
            continue
        seen.add(source_key)
        result.append(source)
    return result
def _provider_metadata(
    snapshot: CompanySnapshot,
) -> dict[str, Any]:
    metadata = snapshot.provider_metadata
    if isinstance(
        metadata,
        dict,
    ):
        return metadata
    return {}
def _is_yahoo_snapshot(
    snapshot: CompanySnapshot,
) -> bool:
    metadata = _provider_metadata(
        snapshot
    )
    provider_name = _normalize_text(
        metadata.get(
            "provider"
        ),
        maximum_length=100,
    )
    source_name = _normalize_text(
        snapshot.source,
        maximum_length=250,
    )
    combined_text = " ".join(
        value
        for value in (
            provider_name,
            source_name,
        )
        if value
    ).casefold()
    return "yahoo" in combined_text
def _build_snapshot_source(
    snapshot: CompanySnapshot,
) -> SourceReference:
    metadata = _provider_metadata(
        snapshot
    )
    source_name = (
        _normalize_text(
            snapshot.source,
            maximum_length=250,
        )
        or _normalize_text(
            metadata.get(
                "provider"
            ),
            maximum_length=250,
        )
        or "Proveedor de precarga"
    )
    if _is_yahoo_snapshot(
        snapshot
    ):
        normalized_ticker = (
            _normalize_text(
                snapshot.ticker,
                maximum_length=30,
            )
            or snapshot.ticker
        )
        encoded_ticker = quote(
            normalized_ticker,
            safe=".-^=",
        )
        source_url = (
            "https://finance.yahoo.com/quote/"
            f"{encoded_ticker}"
        )
        source_type = YAHOO_SOURCE_TYPE
    else:
        source_url = None
        source_type = GENERIC_SOURCE_TYPE
    return SourceReference(
        name=source_name,
        source_type=source_type,
        url=source_url,
        published_at=(
            snapshot.fundamentals_date
        ),
        retrieved_at=(
            snapshot.fetched_at
            or None
        ),
        is_official=False,
    )
def _build_sources(
    snapshot: CompanySnapshot,
    additional_sources: Any,
) -> list[SourceReference]:
    sources = [
        _build_snapshot_source(
            snapshot
        )
    ]
    if additional_sources is None:
        return sources
    if not isinstance(
        additional_sources,
        list,
    ):
        raise MasterAnalysisBuilderError(
            "additional_sources debe ser una lista."
        )
    for index, source in enumerate(
        additional_sources
    ):
        sources.append(
            _validate_source(
                source,
                field_name=(
                    f"additional_sources[{index}]"
                ),
            )
        )
    return _deduplicate_sources(
        sources
    )
def _source_quality_score(
    sources: list[SourceReference],
) -> float:
    official_financial_count = sum(
        _is_official_financial_source(
            source
        )
        for source in sources
    )
    official_context_count = sum(
        _is_official_context_source(
            source
        )
        for source in sources
    )
    secondary_count = sum(
        not source.is_official
        for source in sources
    )
    if official_financial_count >= 2:
        return (
            MULTIPLE_OFFICIAL_FINANCIAL_SOURCE_SCORE
        )
    if official_financial_count == 1:
        return (
            ONE_OFFICIAL_FINANCIAL_SOURCE_SCORE
        )
    if official_context_count >= 1:
        return OFFICIAL_CONTEXT_SOURCE_SCORE
    if secondary_count >= 2:
        return MULTIPLE_SECONDARY_SOURCE_SCORE
    if secondary_count == 1:
        return SINGLE_SECONDARY_SOURCE_SCORE
    return 0.0
def _latest_financial_source_date(
    sources: list[SourceReference],
) -> str | None:
    return _latest_datetime_string(
        [
            source.published_at
            for source in sources
            if _is_official_financial_source(
                source
            )
        ]
    )
def _partial_data_status() -> DataQualityStatus:
    for attribute_name in (
        "PARTIAL",
        "LIMITED",
        "PARTIALLY_VALIDATED",
    ):
        candidate = getattr(
            DataQualityStatus,
            attribute_name,
            None,
        )
        if candidate is not None:
            return candidate
    return DataQualityStatus.INSUFFICIENT
def _preliminary_data_status(
    snapshot: CompanySnapshot,
    score: ScoreCard,
) -> DataQualityStatus:
    has_blocking_problem = (
        bool(snapshot.errors)
        or bool(
            snapshot.critical_missing_fields
        )
        or snapshot.price is None
        or (
            score.confidence
            < MINIMUM_PRELIMINARY_CONFIDENCE
        )
        or (
            score.overall_coverage
            < MINIMUM_PRELIMINARY_COVERAGE
        )
    )
    if has_blocking_problem:
        return DataQualityStatus.INSUFFICIENT
    return _partial_data_status()
def _build_data_quality(
    snapshot: CompanySnapshot,
    score: ScoreCard,
    sources: list[SourceReference],
) -> DataQualityAssessment:
    snapshot_coverage = (
        _bounded_score(
            snapshot.coverage_score
        )
        or 0.0
    )
    score_coverage = (
        _bounded_score(
            score.overall_coverage
        )
        or 0.0
    )
    coverage_score = round(
        (
            snapshot_coverage
            + score_coverage
        )
        / 2.0,
        1,
    )
    latest_price_date = (
        _latest_datetime_string(
            [
                snapshot.price_date,
                snapshot.fetched_at,
            ]
        )
    )
    latest_fundamentals_date = (
        _latest_datetime_string(
            [
                snapshot.fundamentals_date,
                _latest_financial_source_date(
                    sources
                ),
            ]
        )
    )
    price_freshness = _freshness_score(
        latest_price_date
    )
    fundamentals_freshness = (
        _freshness_score(
            latest_fundamentals_date
        )
    )
    freshness_score = round(
        (
            0.40 * price_freshness
            + 0.60 * fundamentals_freshness
        ),
        1,
    )
    consistency_score = (
        _bounded_score(
            snapshot.consistency_score
        )
        or 0.0
    )
    official_source_count = sum(
        source.is_official
        for source in sources
    )
    official_financial_source_count = sum(
        _is_official_financial_source(
            source
        )
        for source in sources
    )
    warnings: list[Any] = [
        *snapshot.warnings,
        *score.warnings,
    ]
    warnings.append(
        "El ticker es internamente consistente entre snapshot "
        "y scoring, pero no ha sido validado externamente."
    )
    if official_financial_source_count == 0:
        warnings.append(
            "No se ha incorporado ninguna fuente financiera "
            "oficial que permita contrastar los fundamentales."
        )
    else:
        warnings.append(
            "La presencia de documentación financiera oficial "
            "no implica que cada magnitud haya sido reconciliada "
            "campo por campo."
        )
    if fundamentals_freshness < 50.0:
        warnings.append(
            "La fecha de los fundamentales es antigua "
            "o no ha podido validarse."
        )
    if score_coverage < 75.0:
        warnings.append(
            "La cobertura del precribado es parcial."
        )
    blocking_issues: list[Any] = []
    if snapshot.errors:
        blocking_issues.append(
            snapshot.errors
        )
    for field_name in (
        snapshot.critical_missing_fields
    ):
        blocking_issues.append(
            "Falta un campo crítico del proveedor: "
            f"{field_name}."
        )
    if snapshot.price is None:
        blocking_issues.append(
            "No se dispone de un precio válido."
        )
    if (
        score.confidence
        < MINIMUM_PRELIMINARY_CONFIDENCE
    ):
        blocking_issues.append(
            "La confianza del precribado es insuficiente."
        )
    if (
        score.overall_coverage
        < MINIMUM_PRELIMINARY_COVERAGE
    ):
        blocking_issues.append(
            "La cobertura del precribado es insuficiente."
        )
    return DataQualityAssessment(
        status=_preliminary_data_status(
            snapshot,
            score,
        ),
        coverage_score=coverage_score,
        freshness_score=freshness_score,
        consistency_score=consistency_score,
        source_quality_score=(
            _source_quality_score(
                sources
            )
        ),
        price_validated=False,
        currency_validated=False,
        ticker_validated=False,
        market_cap_validated=False,
        fundamentals_validated=False,
        price_date=latest_price_date,
        fundamentals_date=(
            latest_fundamentals_date
        ),
        source_count=len(sources),
        official_source_count=(
            official_source_count
        ),
        warnings=_deduplicate_strings(
            warnings
        ),
        blocking_issues=(
            _deduplicate_strings(
                blocking_issues
            )
        ),
    )
def _dimension_is_covered(
    score: ScoreCard,
    dimension: str,
) -> bool:
    coverage = _number(
        score.dimension_coverage.get(
            dimension
        )
    )
    return (
        coverage is not None
        and coverage > 0.0
    )
def _covered_score(
    score: ScoreCard,
    dimension: str,
    value: Any,
) -> float | None:
    if not _dimension_is_covered(
        score,
        dimension,
    ):
        return None
    return _bounded_score(
        value
    )
def _build_business(
    snapshot: CompanySnapshot,
    score: ScoreCard,
) -> BusinessAssessment:
    warnings: list[Any] = [
        (
            "La evaluación del negocio es preliminar "
            "y se basa en datos cuantitativos de precarga."
        ),
        (
            "El crecimiento de ingresos no ha sido "
            "validado como crecimiento orgánico."
        ),
        (
            "La asignación de capital no incluye una revisión "
            "de adquisiciones, recompras, emisiones ni retorno "
            "incremental."
        ),
        (
            "El riesgo empresarial no puede evaluarse "
            "adecuadamente con el score del radar."
        ),
    ]
    notes: list[Any] = [
        score.rationale,
        (
            "Resultado del radar: "
            f"{score.recommendation}."
        ),
        (
            "Versión del scoring preliminar: "
            f"{score.scoring_version}."
        ),
        (
            "Versión del builder: "
            f"{BUILDER_VERSION}."
        ),
    ]
    return BusinessAssessment(
        sector=_normalize_text(
            snapshot.sector,
            maximum_length=150,
        ),
        industry=_normalize_text(
            snapshot.industry,
            maximum_length=200,
        ),
        business_model=None,
        operating_quality_score=(
            _covered_score(
                score,
                "quality",
                score.quality,
            )
        ),
        organic_growth_score=None,
        balance_score=_covered_score(
            score,
            "balance",
            score.balance,
        ),
        cash_score=_covered_score(
            score,
            "cash",
            score.cash,
        ),
        capital_allocation_score=(
            _covered_score(
                score,
                "capital_allocation",
                score.capital_allocation,
            )
        ),
        risk_score=None,
        revenue_growth=_number(
            snapshot.revenue_growth
        ),
        organic_revenue_growth=None,
        operating_margin=_number(
            snapshot.operating_margin
        ),
        return_on_invested_capital=None,
        customer_concentration_risk=None,
        supplier_concentration_risk=None,
        platform_dependency_risk=None,
        regulatory_risk=None,
        warnings=_deduplicate_strings(
            warnings
        ),
        notes=_deduplicate_strings(
            notes
        ),
    )
def _build_accounting(
    snapshot: CompanySnapshot,
) -> AccountingAssessment:
    warnings: list[Any] = [
        (
            "No se dispone de una conciliación completa "
            "entre resultados GAAP y resultados ajustados."
        ),
        (
            "No se ha validado la compensación basada "
            "en acciones ni los ajustes no recurrentes."
        ),
        (
            "No se calcula una puntuación de calidad contable "
            "sin revisar estados financieros oficiales."
        ),
    ]
    if snapshot.capex is None:
        warnings.append(
            "El CAPEX no está disponible y no puede "
            "reconciliarse el FCF reportado."
        )
    return AccountingAssessment(
        gaap_earnings=_number(
            snapshot.net_income
        ),
        adjusted_earnings=None,
        gaap_eps=None,
        adjusted_eps=None,
        operating_cash_flow=_number(
            snapshot.operating_cash_flow
        ),
        capital_expenditure=_number(
            snapshot.capex
        ),
        reported_fcf=_number(
            snapshot.free_cash_flow
        ),
        economic_fcf=None,
        stock_based_compensation=None,
        sbc_to_revenue=None,
        sbc_to_reported_fcf=None,
        recurring_adjustments=None,
        acquisition_related_adjustments=None,
        restructuring_adjustments=None,
        impairment_adjustments=None,
        cash_conversion_score=None,
        earnings_quality_score=None,
        accounting_quality_score=None,
        uses_sbc_adjusted_fcf=False,
        warnings=_deduplicate_strings(
            warnings
        ),
        notes=[
            (
                "Los datos contables de precarga no sustituyen "
                "los estados financieros oficiales."
            )
        ],
    )
def _build_per_share(
    snapshot: CompanySnapshot,
) -> PerShareAssessment:
    notes: list[str] = []
    if snapshot.shares is not None:
        notes.append(
            "Las acciones en circulación del snapshot no se "
            "trasladan a diluted_shares porque no equivalen "
            "necesariamente al promedio diluido oficial."
        )
    return PerShareAssessment(
        diluted_shares=None,
        diluted_shares_previous=None,
        share_count_growth=None,
        revenue_per_share=None,
        revenue_per_share_growth=None,
        gaap_eps_growth=None,
        adjusted_eps_growth=None,
        reported_fcf_per_share=None,
        economic_fcf_per_share=None,
        fcf_per_share_growth=None,
        buybacks=None,
        net_buybacks_after_sbc=None,
        net_debt_per_share=None,
        per_share_value_score=None,
        warnings=[
            (
                "No se dispone de una serie histórica "
                "de acciones diluidas."
            ),
            (
                "No puede evaluarse la dilución, las recompras "
                "netas ni el crecimiento económico por acción."
            ),
        ],
        notes=notes,
    )
def _build_moat() -> MoatAssessment:
    return MoatAssessment(
        strength=MoatStrength.NOT_EVALUATED,
        trend=MoatTrend.NOT_EVALUATED,
        confidence=(
            EvidenceConfidence.NOT_EVALUABLE
        ),
        warnings=[
            (
                "El moat no puede evaluarse de forma fiable "
                "a partir de un snapshot cuantitativo."
            )
        ],
        notes=[
            (
                "Se requiere evidencia cualitativa sobre "
                "ventajas competitivas, clientes, competencia, "
                "precios, sustitución y disrupción."
            )
        ],
    )
def _build_valuation(
    snapshot: CompanySnapshot,
    score: ScoreCard,
) -> ValuationAssessment:
    multiples_score = _covered_score(
        score,
        "valuation",
        score.valuation,
    )
    return ValuationAssessment(
        current_price=_number(
            snapshot.price
        ),
        currency=_normalize_text(
            snapshot.currency,
            maximum_length=20,
        ),
        conservative=None,
        base=None,
        optimistic=None,
        reverse_dcf_growth=None,
        reverse_dcf_margin=None,
        reverse_dcf_status=None,
        multiples_score=multiples_score,
        valuation_score=None,
        margin_of_safety_conservative=None,
        margin_of_safety_base=None,
        status=ValuationStatus.NOT_EVALUATED,
        warnings=[
            (
                "La valoración disponible es únicamente "
                "un scoring preliminar de múltiplos."
            ),
            (
                "No se han calculado escenarios conservador, "
                "base y optimista."
            ),
            (
                "No se ha ejecutado un reverse DCF."
            ),
        ],
        notes=[
            (
                "El score de múltiplos procede del radar "
                "y no constituye una estimación de valor "
                "intrínseco."
            )
        ],
    )
def build_master_analysis(
    snapshot: CompanySnapshot,
    score: ScoreCard,
    *,
    model_version: str = DEFAULT_MODEL_VERSION,
    data_quality: DataQualityAssessment | None = None,
    business: BusinessAssessment | None = None,
    accounting: AccountingAssessment | None = None,
    per_share: PerShareAssessment | None = None,
    moat: MoatAssessment | None = None,
    valuation: ValuationAssessment | None = None,
    additional_sources: list[
        SourceReference
    ] | None = None,
) -> MasterAnalysisInput:
    """
    Construye un MasterAnalysisInput prudente y extensible.
    El builder provisional nunca declara como validados datos
    concretos únicamente por haber recibido una fuente oficial.
    Las fuentes financieras oficiales se distinguen de las
    fuentes corporativas meramente contextuales.
    Los bloques enriquecidos opcionales sustituyen por completo
    el bloque provisional correspondiente.
    """
    validated_snapshot, validated_score = (
        _validate_inputs(
            snapshot,
            score,
        )
    )
    normalized_model_version = (
        _normalize_model_version(
            model_version
        )
    )
    try:
        snapshot_copy = deepcopy(
            validated_snapshot
        )
        score_copy = deepcopy(
            validated_score
        )
    except Exception as error:
        raise MasterAnalysisBuilderError(
            "No se pudo crear una copia segura "
            "de los datos de entrada."
        ) from error
    sources = _build_sources(
        snapshot_copy,
        additional_sources,
    )
    data_quality_result = (
        _copy_assessment(
            data_quality,
            expected_type=DataQualityAssessment,
            field_name="data_quality",
        )
        if data_quality is not None
        else _build_data_quality(
            snapshot_copy,
            score_copy,
            sources,
        )
    )
    business_result = (
        _copy_assessment(
            business,
            expected_type=BusinessAssessment,
            field_name="business",
        )
        if business is not None
        else _build_business(
            snapshot_copy,
            score_copy,
        )
    )
    accounting_result = (
        _copy_assessment(
            accounting,
            expected_type=AccountingAssessment,
            field_name="accounting",
        )
        if accounting is not None
        else _build_accounting(
            snapshot_copy
        )
    )
    per_share_result = (
        _copy_assessment(
            per_share,
            expected_type=PerShareAssessment,
            field_name="per_share",
        )
        if per_share is not None
        else _build_per_share(
            snapshot_copy
        )
    )
    moat_result = (
        _copy_assessment(
            moat,
            expected_type=MoatAssessment,
            field_name="moat",
        )
        if moat is not None
        else _build_moat()
    )
    valuation_result = (
        _copy_assessment(
            valuation,
            expected_type=ValuationAssessment,
            field_name="valuation",
        )
        if valuation is not None
        else _build_valuation(
            snapshot_copy,
            score_copy,
        )
    )
    return MasterAnalysisInput(
        ticker=snapshot_copy.ticker,
        company_name=_normalize_text(
            snapshot_copy.name,
            maximum_length=250,
        ),
        data_quality=data_quality_result,
        business=business_result,
        accounting=accounting_result,
        per_share=per_share_result,
        moat=moat_result,
        valuation=valuation_result,
        sources=sources,
        model_version=(
            normalized_model_version
        ),
    )
