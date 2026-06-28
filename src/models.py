from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, ClassVar

from src.domain import (
    ComparabilityStatus,
    DataIssue,
    DimensionScore,
    EligibilityStatus,
    FieldProvenance,
    IssueSeverity,
    RunStatus,
    bounded_score,
    deduplicate_strings,
    finite_number,
    iso_datetime_utc,
    normalize_text,
    normalize_ticker,
    to_primitive,
    utc_now_iso,
)


MODEL_SCHEMA_VERSION = 2
LEGACY_MODEL_SCHEMA_VERSION = 1

DEFAULT_MINIMUM_CONFIDENCE = 55.0
DEFAULT_MINIMUM_COVERAGE = 50.0

DIMENSION_CODES = (
    "valuation",
    "quality",
    "cash",
    "balance",
    "growth",
    "capital_allocation",
    "momentum_fundamental",
    "financial_resilience",
)

LEGACY_TO_DIMENSION = {
    "valuation": "valuation",
    "quality": "quality",
    "cash": "cash",
    "balance": "balance",
    "growth": "growth",
    "capital_allocation": "capital_allocation",
    "momentum_fundamental": "momentum_fundamental",
    "risk": "financial_resilience",
}

DIMENSION_TO_LEGACY = {
    dimension_code: legacy_code
    for legacy_code, dimension_code
    in LEGACY_TO_DIMENSION.items()
}


def _normalize_optional_text(
    value: Any,
    *,
    maximum_length: int,
) -> str:
    return (
        normalize_text(
            value,
            maximum_length=maximum_length,
            allow_non_string=False,
        )
        or ""
    )


def _normalize_optional_number(
    value: Any,
) -> float | None:
    return finite_number(value)


def _normalize_non_negative_number(
    value: Any,
) -> float | None:
    normalized_value = finite_number(value)

    if normalized_value is None:
        return None

    if normalized_value < 0:
        return None

    return normalized_value


def _normalize_positive_number(
    value: Any,
) -> float | None:
    normalized_value = finite_number(value)

    if normalized_value is None:
        return None

    if normalized_value <= 0:
        return None

    return normalized_value


def _normalize_optional_date(
    value: Any,
    *,
    field_name: str,
) -> str:
    if value in (
        None,
        "",
    ):
        return ""

    normalized_date = iso_datetime_utc(value)

    if normalized_date is None:
        raise ValueError(
            f"{field_name} debe ser una fecha "
            "ISO-8601 válida."
        )

    return normalized_date


def _normalize_string_list(
    values: Any,
    *,
    field_name: str,
) -> list[str]:
    if values is None:
        return []

    if not isinstance(
        values,
        (
            list,
            tuple,
            set,
        ),
    ):
        raise ValueError(
            f"{field_name} debe ser una colección."
        )

    return deduplicate_strings(values)


def _normalize_dimension_coverage(
    value: Any,
) -> dict[str, float]:
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise ValueError(
            "dimension_coverage debe ser un diccionario."
        )

    result: dict[str, float] = {}

    for dimension_code, coverage in value.items():
        normalized_code = normalize_text(
            dimension_code,
            maximum_length=100,
            allow_non_string=True,
        )

        if normalized_code is None:
            continue

        normalized_coverage = bounded_score(
            coverage,
            default=0.0,
        )

        result[normalized_code] = (
            normalized_coverage
            if normalized_coverage is not None
            else 0.0
        )

    return result


def _issue_from_dict(
    payload: dict[str, Any],
) -> DataIssue:
    from src.domain import (
        IssueCategory,
        IssueSeverity,
    )

    category_value = payload.get(
        "category",
        IssueCategory.UNKNOWN,
    )
    severity_value = payload.get(
        "severity",
        IssueSeverity.WARNING,
    )

    if not isinstance(
        category_value,
        IssueCategory,
    ):
        category_value = IssueCategory(
            category_value
        )

    if not isinstance(
        severity_value,
        IssueSeverity,
    ):
        severity_value = IssueSeverity(
            severity_value
        )

    return DataIssue(
        code=payload.get(
            "code",
            "UNKNOWN_ISSUE",
        ),
        category=category_value,
        severity=severity_value,
        message=payload.get(
            "message",
            "Incidencia sin descripción.",
        ),
        field_name=payload.get(
            "field_name"
        ),
        provider=payload.get(
            "provider"
        ),
        actual_value=payload.get(
            "actual_value"
        ),
        expected_value=payload.get(
            "expected_value"
        ),
        recoverable=payload.get(
            "recoverable",
            True,
        ),
        created_at=payload.get(
            "created_at"
        ),
        metadata=payload.get(
            "metadata",
            {},
        ),
    )


def _provenance_from_dict(
    payload: dict[str, Any],
) -> FieldProvenance:
    return FieldProvenance(
        field_name=payload.get(
            "field_name",
            "unknown",
        ),
        provider=payload.get(
            "provider",
            "unknown",
        ),
        source_name=payload.get(
            "source_name"
        ),
        source_type=payload.get(
            "source_type"
        ),
        source_url=payload.get(
            "source_url"
        ),
        as_of=payload.get(
            "as_of"
        ),
        retrieved_at=payload.get(
            "retrieved_at"
        ),
        is_official=payload.get(
            "is_official",
            False,
        ),
        is_validated=payload.get(
            "is_validated",
            False,
        ),
        is_estimated=payload.get(
            "is_estimated",
            False,
        ),
        quality_score=payload.get(
            "quality_score"
        ),
        notes=payload.get(
            "notes",
            [],
        ),
        metadata=payload.get(
            "metadata",
            {},
        ),
    )


@dataclass
class CompanySnapshot:
    """
    Contrato central de datos financieros de una empresa.

    Los campos financieros representan datos observados o
    precargados. La procedencia, validación e incidencias se
    registran separadamente y nunca deben inferirse solo porque
    exista un valor numérico.
    """

    ticker: str

    name: str = ""
    currency: str = ""
    sector: str = ""
    industry: str = ""

    price: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None

    revenue: float | None = None
    ebitda: float | None = None
    ebit: float | None = None
    net_income: float | None = None

    operating_cash_flow: float | None = None
    capex: float | None = None
    free_cash_flow: float | None = None

    total_cash: float | None = None
    total_debt: float | None = None
    shares: float | None = None

    revenue_growth: float | None = None
    earnings_growth: float | None = None

    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None

    roe: float | None = None
    roa: float | None = None

    debt_to_equity: float | None = None
    current_ratio: float | None = None
    interest_coverage: float | None = None

    pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    ev_to_ebitda: float | None = None

    fcf_yield: float | None = None
    earnings_yield: float | None = None
    dividend_yield: float | None = None

    fifty_two_week_change: float | None = None

    analyst_target: float | None = None
    analyst_count: int | None = None

    source: str = ""
    fetched_at: str = ""
    price_date: str = ""
    fundamentals_date: str = ""

    data_quality: float = 0.0
    coverage_score: float = 0.0
    validity_score: float = 0.0
    freshness_score: float = 0.0
    consistency_score: float = 0.0
    source_quality_score: float = 0.0

    missing_fields: list[str] = field(
        default_factory=list
    )
    critical_missing_fields: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )

    issues: list[DataIssue] = field(
        default_factory=list
    )

    field_provenance: dict[
        str,
        FieldProvenance,
    ] = field(
        default_factory=dict
    )

    provider_metadata: dict[str, Any] = field(
        default_factory=dict
    )

    errors: str = ""

    schema_version: int = MODEL_SCHEMA_VERSION

    _NUMERIC_FIELDS: ClassVar[tuple[str, ...]] = (
        "market_cap",
        "enterprise_value",
        "revenue",
        "ebitda",
        "ebit",
        "net_income",
        "operating_cash_flow",
        "capex",
        "free_cash_flow",
        "total_cash",
        "total_debt",
        "shares",
        "revenue_growth",
        "earnings_growth",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "roe",
        "roa",
        "debt_to_equity",
        "current_ratio",
        "interest_coverage",
        "pe",
        "forward_pe",
        "price_to_book",
        "ev_to_ebitda",
        "fcf_yield",
        "earnings_yield",
        "dividend_yield",
        "fifty_two_week_change",
    )

    def __post_init__(self) -> None:
        self.ticker = normalize_ticker(
            self.ticker,
            strict=True,
        )

        self.name = _normalize_optional_text(
            self.name,
            maximum_length=250,
        )
        self.currency = _normalize_optional_text(
            self.currency,
            maximum_length=20,
        ).upper()
        self.sector = _normalize_optional_text(
            self.sector,
            maximum_length=150,
        )
        self.industry = _normalize_optional_text(
            self.industry,
            maximum_length=200,
        )
        self.source = _normalize_optional_text(
            self.source,
            maximum_length=250,
        )
        self.errors = _normalize_optional_text(
            self.errors,
            maximum_length=4_000,
        )

        self.price = _normalize_positive_number(
            self.price
        )

        for field_name in self._NUMERIC_FIELDS:
            setattr(
                self,
                field_name,
                _normalize_optional_number(
                    getattr(
                        self,
                        field_name,
                    )
                ),
            )

        self.analyst_target = (
            _normalize_positive_number(
                self.analyst_target
            )
        )

        analyst_count = finite_number(
            self.analyst_count
        )

        if (
            analyst_count is None
            or analyst_count < 0
            or not analyst_count.is_integer()
        ):
            self.analyst_count = None
        else:
            self.analyst_count = int(
                analyst_count
            )

        self.fetched_at = _normalize_optional_date(
            self.fetched_at,
            field_name="fetched_at",
        )
        self.price_date = _normalize_optional_date(
            self.price_date,
            field_name="price_date",
        )
        self.fundamentals_date = (
            _normalize_optional_date(
                self.fundamentals_date,
                field_name="fundamentals_date",
            )
        )

        self.data_quality = (
            bounded_score(
                self.data_quality,
                default=0.0,
            )
            or 0.0
        )
        self.coverage_score = (
            bounded_score(
                self.coverage_score,
                default=0.0,
            )
            or 0.0
        )
        self.validity_score = (
            bounded_score(
                self.validity_score,
                default=0.0,
            )
            or 0.0
        )
        self.freshness_score = (
            bounded_score(
                self.freshness_score,
                default=0.0,
            )
            or 0.0
        )
        self.consistency_score = (
            bounded_score(
                self.consistency_score,
                default=0.0,
            )
            or 0.0
        )
        self.source_quality_score = (
            bounded_score(
                self.source_quality_score,
                default=0.0,
            )
            or 0.0
        )

        if (
            self.coverage_score == 0.0
            and self.data_quality > 0.0
        ):
            self.coverage_score = (
                self.data_quality
            )

        if (
            self.data_quality == 0.0
            and self.coverage_score > 0.0
        ):
            self.data_quality = (
                self.coverage_score
            )

        self.missing_fields = (
            _normalize_string_list(
                self.missing_fields,
                field_name="missing_fields",
            )
        )
        self.critical_missing_fields = (
            _normalize_string_list(
                self.critical_missing_fields,
                field_name=(
                    "critical_missing_fields"
                ),
            )
        )
        self.warnings = _normalize_string_list(
            self.warnings,
            field_name="warnings",
        )

        if not isinstance(
            self.issues,
            list,
        ) or any(
            not isinstance(
                issue,
                DataIssue,
            )
            for issue in self.issues
        ):
            raise ValueError(
                "issues debe contener únicamente "
                "instancias de DataIssue."
            )

        if not isinstance(
            self.field_provenance,
            dict,
        ):
            raise ValueError(
                "field_provenance debe ser "
                "un diccionario."
            )

        normalized_provenance: dict[
            str,
            FieldProvenance,
        ] = {}

        for field_name, provenance in (
            self.field_provenance.items()
        ):
            normalized_field_name = (
                normalize_text(
                    field_name,
                    maximum_length=150,
                    allow_non_string=False,
                )
            )

            if normalized_field_name is None:
                raise ValueError(
                    "Cada clave de field_provenance "
                    "debe ser texto válido."
                )

            if not isinstance(
                provenance,
                FieldProvenance,
            ):
                raise ValueError(
                    "field_provenance debe contener "
                    "instancias de FieldProvenance."
                )

            if (
                provenance.field_name
                != normalized_field_name
            ):
                raise ValueError(
                    "La clave de procedencia no coincide "
                    "con provenance.field_name."
                )

            normalized_provenance[
                normalized_field_name
            ] = provenance

        self.field_provenance = (
            normalized_provenance
        )

        if not isinstance(
            self.provider_metadata,
            dict,
        ):
            raise ValueError(
                "provider_metadata debe ser "
                "un diccionario."
            )

        if self.schema_version != MODEL_SCHEMA_VERSION:
            raise ValueError(
                "CompanySnapshot debe utilizar "
                f"schema_version={MODEL_SCHEMA_VERSION}."
            )

    @property
    def has_errors(self) -> bool:
        if bool(self.errors):
            return True

        return any(
            issue.severity
            in {
                IssueSeverity.ERROR,
                IssueSeverity.CRITICAL,
            }
            for issue in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        if bool(self.warnings):
            return True

        return any(
            issue.severity
            == IssueSeverity.WARNING
            for issue in self.issues
        )

    @property
    def has_critical_issues(self) -> bool:
        return any(
            issue.severity
            == IssueSeverity.CRITICAL
            for issue in self.issues
        )

    @property
    def is_usable(self) -> bool:
        return (
            bool(self.ticker)
            and self.price is not None
            and self.price > 0.0
            and not self.critical_missing_fields
            and not self.has_errors
            and not self.has_critical_issues
        )

    def add_warning(
        self,
        message: Any,
    ) -> None:
        normalized_message = normalize_text(
            message,
            maximum_length=2_000,
        )

        if normalized_message is None:
            return

        self.warnings = deduplicate_strings(
            [
                *self.warnings,
                normalized_message,
            ]
        )

    def add_issue(
        self,
        issue: DataIssue,
    ) -> None:
        if not isinstance(
            issue,
            DataIssue,
        ):
            raise ValueError(
                "issue debe ser DataIssue."
            )

        self.issues.append(issue)

    def provenance_for(
        self,
        field_name: str,
    ) -> FieldProvenance | None:
        normalized_field_name = (
            normalize_text(
                field_name,
                maximum_length=150,
            )
        )

        if normalized_field_name is None:
            return None

        return self.field_provenance.get(
            normalized_field_name
        )

    def to_dict(self) -> dict[str, Any]:
        payload = to_primitive(self)

        if not isinstance(payload, dict):
            raise TypeError(
                "CompanySnapshot no pudo "
                "serializarse como diccionario."
            )

        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> CompanySnapshot:
        if not isinstance(payload, dict):
            raise ValueError(
                "payload debe ser un diccionario."
            )

        normalized_payload = dict(payload)

        raw_issues = normalized_payload.get(
            "issues",
            [],
        )

        normalized_payload["issues"] = [
            (
                issue
                if isinstance(
                    issue,
                    DataIssue,
                )
                else _issue_from_dict(issue)
            )
            for issue in raw_issues
            if isinstance(
                issue,
                (
                    DataIssue,
                    dict,
                ),
            )
        ]

        raw_provenance = (
            normalized_payload.get(
                "field_provenance",
                {},
            )
        )

        if not isinstance(
            raw_provenance,
            dict,
        ):
            raise ValueError(
                "field_provenance debe ser "
                "un diccionario."
            )

        normalized_payload[
            "field_provenance"
        ] = {
            field_name: (
                provenance
                if isinstance(
                    provenance,
                    FieldProvenance,
                )
                else _provenance_from_dict(
                    provenance
                )
            )
            for field_name, provenance
            in raw_provenance.items()
            if isinstance(
                provenance,
                (
                    FieldProvenance,
                    dict,
                ),
            )
        }

        normalized_payload[
            "schema_version"
        ] = MODEL_SCHEMA_VERSION

        return cls(**normalized_payload)

    @classmethod
    def from_legacy_dict(
        cls,
        payload: dict[str, Any],
    ) -> CompanySnapshot:
        if not isinstance(payload, dict):
            raise ValueError(
                "payload debe ser un diccionario."
            )

        normalized_payload = dict(payload)

        normalized_payload.setdefault(
            "coverage_score",
            normalized_payload.get(
                "data_quality",
                0.0,
            ),
        )
        normalized_payload.setdefault(
            "schema_version",
            MODEL_SCHEMA_VERSION,
        )

        return cls.from_dict(
            normalized_payload
        )


@dataclass
class ScoreCard:
    """
    Resultado del scoring preliminar.

    Los campos escalares heredados se conservan temporalmente
    para los consumidores actuales. La representación v2
    principal está en `dimensions`.
    """

    ticker: str

    valuation: float | None
    quality: float | None
    cash: float | None
    balance: float | None
    growth: float | None
    capital_allocation: float | None
    momentum_fundamental: float | None
    risk: float | None

    confidence: float
    global_score: float
    recommendation: str
    rationale: str

    calculated_at: str = ""

    overall_coverage: float = 0.0
    dimension_coverage: dict[str, float] = field(
        default_factory=dict
    )

    missing_metrics: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )

    scoring_version: str = "unknown"

    dimensions: dict[
        str,
        DimensionScore,
    ] = field(
        default_factory=dict
    )

    eligibility_status: EligibilityStatus = (
        EligibilityStatus.NOT_EVALUATED
    )
    radar_signal: str | None = None

    configuration_hash: str = ""
    schema_version: int = MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.ticker = normalize_ticker(
            self.ticker,
            strict=True,
        )

        for legacy_field_name in (
            "valuation",
            "quality",
            "cash",
            "balance",
            "growth",
            "capital_allocation",
            "momentum_fundamental",
            "risk",
        ):
            setattr(
                self,
                legacy_field_name,
                bounded_score(
                    getattr(
                        self,
                        legacy_field_name,
                    )
                ),
            )

        self.confidence = (
            bounded_score(
                self.confidence,
                default=0.0,
            )
            or 0.0
        )
        self.global_score = (
            bounded_score(
                self.global_score,
                default=0.0,
            )
            or 0.0
        )
        self.overall_coverage = (
            bounded_score(
                self.overall_coverage,
                default=0.0,
            )
            or 0.0
        )

        self.recommendation = (
            normalize_text(
                self.recommendation,
                maximum_length=150,
            )
            or ""
        )
        self.rationale = (
            normalize_text(
                self.rationale,
                maximum_length=4_000,
            )
            or ""
        )
        self.scoring_version = (
            normalize_text(
                self.scoring_version,
                maximum_length=100,
            )
            or "unknown"
        )
        self.configuration_hash = (
            normalize_text(
                self.configuration_hash,
                maximum_length=128,
            )
            or ""
        )

        self.calculated_at = (
            _normalize_optional_date(
                self.calculated_at,
                field_name="calculated_at",
            )
        )

        self.dimension_coverage = (
            _normalize_dimension_coverage(
                self.dimension_coverage
            )
        )
        self.missing_metrics = (
            _normalize_string_list(
                self.missing_metrics,
                field_name="missing_metrics",
            )
        )
        self.warnings = _normalize_string_list(
            self.warnings,
            field_name="warnings",
        )

        if not isinstance(
            self.eligibility_status,
            EligibilityStatus,
        ):
            self.eligibility_status = (
                EligibilityStatus(
                    self.eligibility_status
                )
            )

        self.radar_signal = normalize_text(
            self.radar_signal,
            maximum_length=150,
        )

        if not isinstance(
            self.dimensions,
            dict,
        ):
            raise ValueError(
                "dimensions debe ser un diccionario."
            )

        if self.dimensions:
            self._validate_dimensions()
            self._synchronize_legacy_from_dimensions()
        else:
            self._build_dimensions_from_legacy()

        self._derive_classification_from_legacy()

        if self.schema_version != MODEL_SCHEMA_VERSION:
            raise ValueError(
                "ScoreCard debe utilizar "
                f"schema_version={MODEL_SCHEMA_VERSION}."
            )

    def _validate_dimensions(self) -> None:
        normalized_dimensions: dict[
            str,
            DimensionScore,
        ] = {}

        for dimension_code, dimension in (
            self.dimensions.items()
        ):
            normalized_code = normalize_text(
                dimension_code,
                maximum_length=100,
            )

            if normalized_code is None:
                raise ValueError(
                    "Cada código de dimensión debe "
                    "ser texto válido."
                )

            if normalized_code not in DIMENSION_CODES:
                raise ValueError(
                    "Dimensión desconocida: "
                    f"{normalized_code}."
                )

            if not isinstance(
                dimension,
                DimensionScore,
            ):
                raise ValueError(
                    "dimensions debe contener "
                    "instancias de DimensionScore."
                )

            if dimension.code != normalized_code:
                raise ValueError(
                    "La clave de la dimensión no coincide "
                    "con DimensionScore.code."
                )

            normalized_dimensions[
                normalized_code
            ] = dimension

        self.dimensions = normalized_dimensions

    def _build_dimensions_from_legacy(self) -> None:
        inferred_coverage = False
        dimensions: dict[str, DimensionScore] = {}

        for legacy_name, dimension_code in (
            LEGACY_TO_DIMENSION.items()
        ):
            score_value = getattr(
                self,
                legacy_name,
            )

            coverage_value = (
                self.dimension_coverage.get(
                    legacy_name
                )
            )

            if coverage_value is None:
                coverage_value = (
                    self.dimension_coverage.get(
                        dimension_code
                    )
                )

            if (
                coverage_value is None
                and score_value is not None
            ):
                coverage_value = 100.0
                inferred_coverage = True

            if coverage_value is None:
                coverage_value = 0.0

            observed = score_value is not None
            valid = (
                observed
                and coverage_value > 0.0
            )

            dimensions[dimension_code] = (
                DimensionScore(
                    code=dimension_code,
                    score=score_value,
                    coverage=coverage_value,
                    confidence=(
                        self.confidence
                        if observed
                        else 0.0
                    ),
                    observed=observed,
                    valid=valid,
                )
            )

        self.dimensions = dimensions

        self.dimension_coverage = {
            dimension_code: (
                dimension.coverage
            )
            for dimension_code, dimension
            in self.dimensions.items()
        }

        if inferred_coverage:
            self.warnings = deduplicate_strings(
                [
                    *self.warnings,
                    (
                        "La cobertura de algunas dimensiones "
                        "se ha inferido temporalmente desde "
                        "el contrato heredado."
                    ),
                ]
            )

        if self.overall_coverage == 0.0:
            available_coverages = [
                dimension.coverage
                for dimension
                in self.dimensions.values()
                if dimension.observed
            ]

            if available_coverages:
                self.overall_coverage = round(
                    sum(available_coverages)
                    / len(available_coverages),
                    1,
                )

    def _synchronize_legacy_from_dimensions(
        self,
    ) -> None:
        for dimension_code, legacy_name in (
            DIMENSION_TO_LEGACY.items()
        ):
            dimension = self.dimensions.get(
                dimension_code
            )

            setattr(
                self,
                legacy_name,
                (
                    dimension.score
                    if (
                        dimension is not None
                        and dimension.available
                    )
                    else None
                ),
            )

        self.dimension_coverage = {
            dimension_code: (
                dimension.coverage
            )
            for dimension_code, dimension
            in self.dimensions.items()
        }

    def _derive_classification_from_legacy(
        self,
    ) -> None:
        normalized_recommendation = (
            self.recommendation.casefold()
        )

        if (
            normalized_recommendation
            == "datos no fiables".casefold()
        ):
            self.eligibility_status = (
                EligibilityStatus.UNRELIABLE
            )
            self.radar_signal = None
            return

        if (
            self.eligibility_status
            == EligibilityStatus.NOT_EVALUATED
        ):
            if (
                self.confidence
                >= DEFAULT_MINIMUM_CONFIDENCE
                and self.overall_coverage
                >= DEFAULT_MINIMUM_COVERAGE
            ):
                self.eligibility_status = (
                    EligibilityStatus.ELIGIBLE
                )
            else:
                self.eligibility_status = (
                    EligibilityStatus.LIMITED
                )

        if (
            self.radar_signal is None
            and self.recommendation
            and self.eligibility_status
            not in {
                EligibilityStatus.UNRELIABLE,
                EligibilityStatus.BLOCKED,
            }
        ):
            self.radar_signal = (
                self.recommendation
            )

    @property
    def financial_resilience(
        self,
    ) -> float | None:
        return self.dimension_score(
            "financial_resilience"
        )

    @property
    def ranking_score(self) -> float:
        return self.global_score

    @property
    def is_reliable(self) -> bool:
        """
        Alias heredado.

        La lógica nueva debe utilizar meets_reliability()
        indicando umbrales explícitos.
        """
        return self.meets_reliability(
            minimum_confidence=(
                DEFAULT_MINIMUM_CONFIDENCE
            ),
            minimum_coverage=(
                DEFAULT_MINIMUM_COVERAGE
            ),
        )

    def meets_reliability(
        self,
        *,
        minimum_confidence: float,
        minimum_coverage: float,
    ) -> bool:
        normalized_confidence = bounded_score(
            minimum_confidence
        )
        normalized_coverage = bounded_score(
            minimum_coverage
        )

        if (
            normalized_confidence is None
            or normalized_coverage is None
        ):
            raise ValueError(
                "Los umbrales de fiabilidad deben "
                "ser puntuaciones válidas."
            )

        return (
            self.eligibility_status
            not in {
                EligibilityStatus.BLOCKED,
                EligibilityStatus.UNRELIABLE,
            }
            and self.confidence
            >= normalized_confidence
            and self.overall_coverage
            >= normalized_coverage
        )

    def dimension(
        self,
        code: str,
    ) -> DimensionScore | None:
        normalized_code = normalize_text(
            code,
            maximum_length=100,
        )

        if normalized_code is None:
            return None

        normalized_code = (
            LEGACY_TO_DIMENSION.get(
                normalized_code,
                normalized_code,
            )
        )

        return self.dimensions.get(
            normalized_code
        )

    def dimension_score(
        self,
        code: str,
    ) -> float | None:
        dimension = self.dimension(code)

        if (
            dimension is None
            or not dimension.available
        ):
            return None

        return dimension.score

    def add_warning(
        self,
        message: Any,
    ) -> None:
        normalized_message = normalize_text(
            message,
            maximum_length=2_000,
        )

        if normalized_message is None:
            return

        self.warnings = deduplicate_strings(
            [
                *self.warnings,
                normalized_message,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        payload = to_primitive(self)

        if not isinstance(payload, dict):
            raise TypeError(
                "ScoreCard no pudo serializarse "
                "como diccionario."
            )

        return payload

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> ScoreCard:
        if not isinstance(payload, dict):
            raise ValueError(
                "payload debe ser un diccionario."
            )

        normalized_payload = dict(payload)

        raw_dimensions = (
            normalized_payload.get(
                "dimensions",
                {},
            )
        )

        if raw_dimensions:
            if not isinstance(
                raw_dimensions,
                dict,
            ):
                raise ValueError(
                    "dimensions debe ser "
                    "un diccionario."
                )

            normalized_dimensions: dict[
                str,
                DimensionScore,
            ] = {}

            for code, dimension_payload in (
                raw_dimensions.items()
            ):
                if isinstance(
                    dimension_payload,
                    DimensionScore,
                ):
                    normalized_dimensions[
                        code
                    ] = dimension_payload
                    continue

                if not isinstance(
                    dimension_payload,
                    dict,
                ):
                    raise ValueError(
                        "Cada dimensión debe ser "
                        "un diccionario."
                    )

                normalized_dimensions[
                    code
                ] = DimensionScore(
                    code=dimension_payload.get(
                        "code",
                        code,
                    ),
                    score=dimension_payload.get(
                        "score"
                    ),
                    coverage=dimension_payload.get(
                        "coverage",
                        0.0,
                    ),
                    confidence=dimension_payload.get(
                        "confidence",
                        0.0,
                    ),
                    observed=dimension_payload.get(
                        "observed",
                        False,
                    ),
                    valid=dimension_payload.get(
                        "valid",
                        False,
                    ),
                    nominal_weight=(
                        dimension_payload.get(
                            "nominal_weight",
                            0.0,
                        )
                    ),
                    effective_weight=(
                        dimension_payload.get(
                            "effective_weight",
                            0.0,
                        )
                    ),
                    weighted_contribution=(
                        dimension_payload.get(
                            "weighted_contribution"
                        )
                    ),
                    missing_metrics=(
                        dimension_payload.get(
                            "missing_metrics",
                            [],
                        )
                    ),
                    warnings=(
                        dimension_payload.get(
                            "warnings",
                            [],
                        )
                    ),
                    rationale=(
                        dimension_payload.get(
                            "rationale",
                            "",
                        )
                    ),
                )

            normalized_payload[
                "dimensions"
            ] = normalized_dimensions

        eligibility_value = (
            normalized_payload.get(
                "eligibility_status",
                EligibilityStatus.NOT_EVALUATED,
            )
        )

        if not isinstance(
            eligibility_value,
            EligibilityStatus,
        ):
            normalized_payload[
                "eligibility_status"
            ] = EligibilityStatus(
                eligibility_value
            )

        normalized_payload[
            "schema_version"
        ] = MODEL_SCHEMA_VERSION

        return cls(**normalized_payload)

    @classmethod
    def from_legacy_dict(
        cls,
        payload: dict[str, Any],
    ) -> ScoreCard:
        if not isinstance(payload, dict):
            raise ValueError(
                "payload debe ser un diccionario."
            )

        normalized_payload = dict(payload)

        normalized_payload.setdefault(
            "overall_coverage",
            normalized_payload.get(
                "confidence",
                0.0,
            ),
        )
        normalized_payload.setdefault(
            "dimension_coverage",
            {},
        )
        normalized_payload.setdefault(
            "missing_metrics",
            [],
        )
        normalized_payload.setdefault(
            "warnings",
            [],
        )
        normalized_payload.setdefault(
            "scoring_version",
            "legacy",
        )
        normalized_payload.setdefault(
            "dimensions",
            {},
        )
        normalized_payload.setdefault(
            "eligibility_status",
            EligibilityStatus.NOT_EVALUATED,
        )
        normalized_payload.setdefault(
            "schema_version",
            MODEL_SCHEMA_VERSION,
        )

        return cls.from_dict(
            normalized_payload
        )

    def comparability_with(
        self,
        other: ScoreCard,
    ) -> ComparabilityAssessment:
        if not isinstance(
            other,
            ScoreCard,
        ):
            raise ValueError(
                "other debe ser ScoreCard."
            )

        reasons: list[str] = []

        if (
            self.schema_version
            != other.schema_version
        ):
            reasons.append(
                "Los esquemas del modelo son distintos."
            )

        if (
            self.scoring_version
            != other.scoring_version
        ):
            reasons.append(
                "Las versiones del scoring son distintas."
            )

        if (
            self.configuration_hash
            and other.configuration_hash
            and self.configuration_hash
            != other.configuration_hash
        ):
            reasons.append(
                "Las configuraciones del scoring "
                "son distintas."
            )

        if not reasons:
            status = (
                ComparabilityStatus.COMPARABLE
            )
        elif (
            self.schema_version
            == other.schema_version
            and self.scoring_version
            == other.scoring_version
        ):
            status = (
                ComparabilityStatus.PARTIALLY_COMPARABLE
            )
        else:
            status = (
                ComparabilityStatus.NOT_COMPARABLE
            )

        return ComparabilityAssessment(
            status=status,
            reasons=reasons,
            left_schema_version=(
                self.schema_version
            ),
            right_schema_version=(
                other.schema_version
            ),
            left_model_version=(
                self.scoring_version
            ),
            right_model_version=(
                other.scoring_version
            ),
            left_configuration_hash=(
                self.configuration_hash
            ),
            right_configuration_hash=(
                other.configuration_hash
            ),
        )


@dataclass(frozen=True)
class ScoringConfiguration:
    """
    Configuración versionada del scoring preliminar.
    """

    scoring_version: str

    dimension_weights: dict[str, float]

    priority_threshold: float = 80.0
    candidate_threshold: float = 70.0
    watch_threshold: float = 58.0

    minimum_confidence: float = (
        DEFAULT_MINIMUM_CONFIDENCE
    )
    minimum_coverage: float = (
        DEFAULT_MINIMUM_COVERAGE
    )

    schema_version: int = MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        normalized_version = normalize_text(
            self.scoring_version,
            maximum_length=100,
        )

        if normalized_version is None:
            raise ValueError(
                "scoring_version no puede estar vacío."
            )

        object.__setattr__(
            self,
            "scoring_version",
            normalized_version,
        )

        if not isinstance(
            self.dimension_weights,
            dict,
        ):
            raise ValueError(
                "dimension_weights debe ser "
                "un diccionario."
            )

        normalized_weights: dict[
            str,
            float,
        ] = {}

        for dimension_code, weight in (
            self.dimension_weights.items()
        ):
            if dimension_code not in DIMENSION_CODES:
                raise ValueError(
                    "Dimensión desconocida en configuración: "
                    f"{dimension_code}."
                )

            normalized_weight = finite_number(
                weight
            )

            if (
                normalized_weight is None
                or normalized_weight < 0
            ):
                raise ValueError(
                    "Los pesos deben ser números "
                    "no negativos."
                )

            normalized_weights[
                dimension_code
            ] = normalized_weight

        if sum(normalized_weights.values()) <= 0:
            raise ValueError(
                "La suma de pesos debe ser positiva."
            )

        object.__setattr__(
            self,
            "dimension_weights",
            normalized_weights,
        )

        for field_name in (
            "priority_threshold",
            "candidate_threshold",
            "watch_threshold",
            "minimum_confidence",
            "minimum_coverage",
        ):
            normalized_value = bounded_score(
                getattr(
                    self,
                    field_name,
                )
            )

            if normalized_value is None:
                raise ValueError(
                    f"{field_name} debe ser válido."
                )

            object.__setattr__(
                self,
                field_name,
                normalized_value,
            )

        if not (
            self.priority_threshold
            >= self.candidate_threshold
            >= self.watch_threshold
        ):
            raise ValueError(
                "Los umbrales deben cumplir: "
                "priority >= candidate >= watch."
            )

    @property
    def configuration_hash(self) -> str:
        payload = self.to_dict()

        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

        return hashlib.sha256(
            canonical_payload.encode(
                "utf-8"
            )
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = to_primitive(self)

        if not isinstance(payload, dict):
            raise TypeError(
                "ScoringConfiguration no pudo "
                "serializarse."
            )

        return payload


@dataclass
class ComparabilityAssessment:
    status: ComparabilityStatus

    reasons: list[str] = field(
        default_factory=list
    )

    left_schema_version: int | None = None
    right_schema_version: int | None = None

    left_model_version: str | None = None
    right_model_version: str | None = None

    left_configuration_hash: str | None = None
    right_configuration_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.status,
            ComparabilityStatus,
        ):
            self.status = ComparabilityStatus(
                self.status
            )

        self.reasons = deduplicate_strings(
            self.reasons
        )

    @property
    def comparable(self) -> bool:
        return (
            self.status
            == ComparabilityStatus.COMPARABLE
        )

    def to_dict(self) -> dict[str, Any]:
        payload = to_primitive(self)

        if not isinstance(payload, dict):
            raise TypeError(
                "ComparabilityAssessment no pudo "
                "serializarse."
            )

        return payload


@dataclass
class ScreeningResult:
    run_id: str
    ticker: str
    snapshot: CompanySnapshot
    score: ScoreCard | None = None

    status: RunStatus = RunStatus.COMPLETED

    error_code: str | None = None
    error_message: str | None = None

    created_at: str = field(
        default_factory=utc_now_iso
    )

    schema_version: int = MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.run_id = (
            normalize_text(
                self.run_id,
                maximum_length=150,
            )
            or ""
        )

        if not self.run_id:
            raise ValueError(
                "run_id no puede estar vacío."
            )

        self.ticker = normalize_ticker(
            self.ticker
        )

        if not isinstance(
            self.snapshot,
            CompanySnapshot,
        ):
            raise ValueError(
                "snapshot debe ser CompanySnapshot."
            )

        if (
            self.snapshot.ticker
            != self.ticker
        ):
            raise ValueError(
                "El ticker del resultado no coincide "
                "con el snapshot."
            )

        if (
            self.score is not None
            and not isinstance(
                self.score,
                ScoreCard,
            )
        ):
            raise ValueError(
                "score debe ser ScoreCard o None."
            )

        if (
            self.score is not None
            and self.score.ticker
            != self.ticker
        ):
            raise ValueError(
                "El ticker del score no coincide "
                "con el resultado."
            )

        if not isinstance(
            self.status,
            RunStatus,
        ):
            self.status = RunStatus(
                self.status
            )

        self.created_at = (
            _normalize_optional_date(
                self.created_at,
                field_name="created_at",
            )
        )

    def to_dict(self) -> dict[str, Any]:
        payload = to_primitive(self)

        if not isinstance(payload, dict):
            raise TypeError(
                "ScreeningResult no pudo serializarse."
            )

        return payload


@dataclass
class ScreeningRun:
    run_id: str
    universe: str

    status: RunStatus = RunStatus.PENDING

    started_at: str = field(
        default_factory=utc_now_iso
    )
    finished_at: str = ""

    requested_company_count: int = 0
    completed_company_count: int = 0
    failed_company_count: int = 0

    scoring_version: str = ""
    configuration_hash: str = ""

    notes: list[str] = field(
        default_factory=list
    )

    schema_version: int = MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.run_id = (
            normalize_text(
                self.run_id,
                maximum_length=150,
            )
            or ""
        )
        self.universe = (
            normalize_text(
                self.universe,
                maximum_length=150,
            )
            or ""
        )

        if not self.run_id:
            raise ValueError(
                "run_id no puede estar vacío."
            )

        if not self.universe:
            raise ValueError(
                "universe no puede estar vacío."
            )

        if not isinstance(
            self.status,
            RunStatus,
        ):
            self.status = RunStatus(
                self.status
            )

        self.started_at = (
            _normalize_optional_date(
                self.started_at,
                field_name="started_at",
            )
        )
        self.finished_at = (
            _normalize_optional_date(
                self.finished_at,
                field_name="finished_at",
            )
        )

        for field_name in (
            "requested_company_count",
            "completed_company_count",
            "failed_company_count",
        ):
            value = getattr(
                self,
                field_name,
            )

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(
                    f"{field_name} debe ser "
                    "un entero no negativo."
                )

        if (
            self.completed_company_count
            + self.failed_company_count
            > self.requested_company_count
            and self.requested_company_count > 0
        ):
            raise ValueError(
                "Los resultados procesados no pueden "
                "superar el total solicitado."
            )

        self.notes = deduplicate_strings(
            self.notes
        )

    @property
    def processed_company_count(self) -> int:
        return (
            self.completed_company_count
            + self.failed_company_count
        )

    @property
    def progress_percentage(self) -> float:
        if self.requested_company_count <= 0:
            return 0.0

        return round(
            min(
                100.0,
                (
                    self.processed_company_count
                    / self.requested_company_count
                    * 100.0
                ),
            ),
            1,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = to_primitive(self)

        if not isinstance(payload, dict):
            raise TypeError(
                "ScreeningRun no pudo serializarse."
            )

        return payload


@dataclass
class ExportArtifact:
    artifact_type: str
    filename: str

    content_type: str = ""
    checksum: str = ""
    row_count: int | None = None
    created_at: str = field(
        default_factory=utc_now_iso
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.artifact_type = (
            normalize_text(
                self.artifact_type,
                maximum_length=100,
            )
            or ""
        )
        self.filename = (
            normalize_text(
                self.filename,
                maximum_length=500,
            )
            or ""
        )
        self.content_type = (
            normalize_text(
                self.content_type,
                maximum_length=150,
            )
            or ""
        )
        self.checksum = (
            normalize_text(
                self.checksum,
                maximum_length=256,
            )
            or ""
        )

        if not self.artifact_type:
            raise ValueError(
                "artifact_type no puede estar vacío."
            )

        if not self.filename:
            raise ValueError(
                "filename no puede estar vacío."
            )

        if (
            self.row_count is not None
            and (
                not isinstance(
                    self.row_count,
                    int,
                )
                or isinstance(
                    self.row_count,
                    bool,
                )
                or self.row_count < 0
            )
        ):
            raise ValueError(
                "row_count debe ser un entero "
                "no negativo o None."
            )

        self.created_at = (
            _normalize_optional_date(
                self.created_at,
                field_name="created_at",
            )
        )

        if not isinstance(
            self.metadata,
            dict,
        ):
            raise ValueError(
                "metadata debe ser un diccionario."
            )


@dataclass
class ExportManifest:
    run_id: str
    artifacts: list[ExportArtifact] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=utc_now_iso
    )

    schema_version: int = MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.run_id = (
            normalize_text(
                self.run_id,
                maximum_length=150,
            )
            or ""
        )

        if not self.run_id:
            raise ValueError(
                "run_id no puede estar vacío."
            )

        if not isinstance(
            self.artifacts,
            list,
        ) or any(
            not isinstance(
                artifact,
                ExportArtifact,
            )
            for artifact in self.artifacts
        ):
            raise ValueError(
                "artifacts debe contener únicamente "
                "instancias de ExportArtifact."
            )

        self.created_at = (
            _normalize_optional_date(
                self.created_at,
                field_name="created_at",
            )
        )

    def to_dict(self) -> dict[str, Any]:
        payload = to_primitive(self)

        if not isinstance(payload, dict):
            raise TypeError(
                "ExportManifest no pudo serializarse."
            )

        return payload
