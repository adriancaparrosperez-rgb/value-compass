from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.enums import (
    IssueCategory,
    IssueSeverity,
)
from src.domain.normalization import (
    bounded_score,
    deduplicate_strings,
    finite_number,
    iso_datetime_utc,
    normalize_text,
)
from src.domain.serialization import to_primitive


DOMAIN_CONTRACT_SCHEMA_VERSION = 2


def _required_text(
    value: Any,
    *,
    field_name: str,
    maximum_length: int,
) -> str:
    normalized_value = normalize_text(
        value,
        maximum_length=maximum_length,
    )

    if normalized_value is None:
        raise ValueError(
            f"{field_name} debe contener texto válido."
        )

    return normalized_value


@dataclass
class DataIssue:
    """
    Incidencia estructurada relacionada con un dato, modelo
    o proceso.

    Sustituirá gradualmente listas de warnings y cadenas de
    error sin estructura.
    """

    code: str
    category: IssueCategory
    severity: IssueSeverity
    message: str

    field_name: str | None = None
    provider: str | None = None
    actual_value: Any = None
    expected_value: Any = None
    recoverable: bool = True
    created_at: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    schema_version: int = (
        DOMAIN_CONTRACT_SCHEMA_VERSION
    )

    def __post_init__(self) -> None:
        self.code = _required_text(
            self.code,
            field_name="code",
            maximum_length=100,
        ).upper()

        self.message = _required_text(
            self.message,
            field_name="message",
            maximum_length=2_000,
        )

        if not isinstance(
            self.category,
            IssueCategory,
        ):
            raise ValueError(
                "category debe ser un IssueCategory."
            )

        if not isinstance(
            self.severity,
            IssueSeverity,
        ):
            raise ValueError(
                "severity debe ser un IssueSeverity."
            )

        self.field_name = normalize_text(
            self.field_name,
            maximum_length=150,
        )

        self.provider = normalize_text(
            self.provider,
            maximum_length=150,
        )

        if not isinstance(
            self.recoverable,
            bool,
        ):
            raise ValueError(
                "recoverable debe ser booleano."
            )

        if self.created_at is not None:
            normalized_date = iso_datetime_utc(
                self.created_at
            )

            if normalized_date is None:
                raise ValueError(
                    "created_at debe ser una fecha "
                    "ISO-8601 válida."
                )

            self.created_at = normalized_date

        if not isinstance(
            self.metadata,
            dict,
        ):
            raise ValueError(
                "metadata debe ser un diccionario."
            )

    def to_dict(self) -> dict[str, Any]:
        result = to_primitive(self)

        if not isinstance(result, dict):
            raise TypeError(
                "DataIssue no pudo serializarse "
                "como diccionario."
            )

        return result


@dataclass
class FieldProvenance:
    """
    Procedencia y estado de validación de un campo concreto.

    Una fuente general pertenece al análisis. Esta estructura
    indica de dónde procede exactamente una magnitud.
    """

    field_name: str
    provider: str

    source_name: str | None = None
    source_type: str | None = None
    source_url: str | None = None

    as_of: str | None = None
    retrieved_at: str | None = None

    is_official: bool = False
    is_validated: bool = False
    is_estimated: bool = False

    quality_score: float | None = None
    notes: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    schema_version: int = (
        DOMAIN_CONTRACT_SCHEMA_VERSION
    )

    def __post_init__(self) -> None:
        self.field_name = _required_text(
            self.field_name,
            field_name="field_name",
            maximum_length=150,
        )

        self.provider = _required_text(
            self.provider,
            field_name="provider",
            maximum_length=150,
        )

        self.source_name = normalize_text(
            self.source_name,
            maximum_length=250,
        )
        self.source_type = normalize_text(
            self.source_type,
            maximum_length=100,
        )
        self.source_url = normalize_text(
            self.source_url,
            maximum_length=2_000,
        )

        for attribute_name in (
            "as_of",
            "retrieved_at",
        ):
            current_value = getattr(
                self,
                attribute_name,
            )

            if current_value is None:
                continue

            normalized_date = iso_datetime_utc(
                current_value
            )

            if normalized_date is None:
                raise ValueError(
                    f"{attribute_name} debe ser una "
                    "fecha ISO-8601 válida."
                )

            setattr(
                self,
                attribute_name,
                normalized_date,
            )

        for attribute_name in (
            "is_official",
            "is_validated",
            "is_estimated",
        ):
            if not isinstance(
                getattr(self, attribute_name),
                bool,
            ):
                raise ValueError(
                    f"{attribute_name} debe ser booleano."
                )

        self.quality_score = bounded_score(
            self.quality_score
        )

        self.notes = deduplicate_strings(
            self.notes
        )

        if not isinstance(
            self.metadata,
            dict,
        ):
            raise ValueError(
                "metadata debe ser un diccionario."
            )

    def to_dict(self) -> dict[str, Any]:
        result = to_primitive(self)

        if not isinstance(result, dict):
            raise TypeError(
                "FieldProvenance no pudo serializarse "
                "como diccionario."
            )

        return result


@dataclass
class MetricAssessment:
    """
    Evaluación de una métrica individual utilizada en scoring.

    Distingue entre valor observado, puntuación derivada,
    cobertura y confianza.
    """

    code: str

    raw_value: float | None = None
    score: float | None = None
    coverage: float = 0.0
    confidence: float = 0.0

    observed: bool = False
    valid: bool = False
    estimated: bool = False

    weight: float = 0.0
    weighted_contribution: float | None = None

    reason: str | None = None
    provenance: FieldProvenance | None = None
    issues: list[DataIssue] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    schema_version: int = (
        DOMAIN_CONTRACT_SCHEMA_VERSION
    )

    def __post_init__(self) -> None:
        self.code = _required_text(
            self.code,
            field_name="code",
            maximum_length=100,
        )

        self.raw_value = finite_number(
            self.raw_value
        )
        self.score = bounded_score(
            self.score
        )
        self.coverage = (
            bounded_score(
                self.coverage,
                default=0.0,
            )
            or 0.0
        )
        self.confidence = (
            bounded_score(
                self.confidence,
                default=0.0,
            )
            or 0.0
        )

        normalized_weight = finite_number(
            self.weight
        )
        self.weight = (
            max(
                0.0,
                normalized_weight,
            )
            if normalized_weight is not None
            else 0.0
        )

        self.weighted_contribution = (
            finite_number(
                self.weighted_contribution
            )
        )

        for attribute_name in (
            "observed",
            "valid",
            "estimated",
        ):
            if not isinstance(
                getattr(self, attribute_name),
                bool,
            ):
                raise ValueError(
                    f"{attribute_name} debe ser booleano."
                )

        self.reason = normalize_text(
            self.reason,
            maximum_length=1_000,
        )

        if (
            self.provenance is not None
            and not isinstance(
                self.provenance,
                FieldProvenance,
            )
        ):
            raise ValueError(
                "provenance debe ser FieldProvenance "
                "o None."
            )

        if not isinstance(
            self.issues,
            list,
        ) or any(
            not isinstance(issue, DataIssue)
            for issue in self.issues
        ):
            raise ValueError(
                "issues debe contener únicamente "
                "instancias de DataIssue."
            )

        if not isinstance(
            self.metadata,
            dict,
        ):
            raise ValueError(
                "metadata debe ser un diccionario."
            )

        if not self.observed:
            self.valid = False

        if not self.valid:
            self.score = None
            self.weighted_contribution = None

    @property
    def available(self) -> bool:
        return (
            self.observed
            and self.valid
            and self.score is not None
        )

    def to_dict(self) -> dict[str, Any]:
        result = to_primitive(self)

        if not isinstance(result, dict):
            raise TypeError(
                "MetricAssessment no pudo serializarse "
                "como diccionario."
            )

        return result


@dataclass
class DimensionScore:
    """
    Resultado completo de una dimensión del scoring.

    Evita mantener el score y su cobertura en dos estructuras
    independientes.
    """

    code: str

    score: float | None = None
    coverage: float = 0.0
    confidence: float = 0.0

    observed: bool = False
    valid: bool = False

    nominal_weight: float = 0.0
    effective_weight: float = 0.0
    weighted_contribution: float | None = None

    metrics: dict[str, MetricAssessment] = field(
        default_factory=dict
    )
    missing_metrics: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    issues: list[DataIssue] = field(
        default_factory=list
    )
    rationale: str = ""

    schema_version: int = (
        DOMAIN_CONTRACT_SCHEMA_VERSION
    )

    def __post_init__(self) -> None:
        self.code = _required_text(
            self.code,
            field_name="code",
            maximum_length=100,
        )

        self.score = bounded_score(
            self.score
        )
        self.coverage = (
            bounded_score(
                self.coverage,
                default=0.0,
            )
            or 0.0
        )
        self.confidence = (
            bounded_score(
                self.confidence,
                default=0.0,
            )
            or 0.0
        )

        for attribute_name in (
            "nominal_weight",
            "effective_weight",
        ):
            normalized_value = finite_number(
                getattr(self, attribute_name)
            )

            setattr(
                self,
                attribute_name,
                (
                    max(
                        0.0,
                        normalized_value,
                    )
                    if normalized_value is not None
                    else 0.0
                ),
            )

        self.weighted_contribution = (
            finite_number(
                self.weighted_contribution
            )
        )

        if not isinstance(
            self.observed,
            bool,
        ):
            raise ValueError(
                "observed debe ser booleano."
            )

        if not isinstance(
            self.valid,
            bool,
        ):
            raise ValueError(
                "valid debe ser booleano."
            )

        if not isinstance(
            self.metrics,
            dict,
        ):
            raise ValueError(
                "metrics debe ser un diccionario."
            )

        normalized_metrics: dict[
            str,
            MetricAssessment,
        ] = {}

        for metric_code, metric in self.metrics.items():
            if not isinstance(
                metric,
                MetricAssessment,
            ):
                raise ValueError(
                    "metrics debe contener únicamente "
                    "instancias de MetricAssessment."
                )

            normalized_code = _required_text(
                metric_code,
                field_name="metric_code",
                maximum_length=100,
            )

            normalized_metrics[
                normalized_code
            ] = metric

        self.metrics = normalized_metrics

        self.missing_metrics = (
            deduplicate_strings(
                self.missing_metrics
            )
        )
        self.warnings = deduplicate_strings(
            self.warnings
        )

        if not isinstance(
            self.issues,
            list,
        ) or any(
            not isinstance(issue, DataIssue)
            for issue in self.issues
        ):
            raise ValueError(
                "issues debe contener únicamente "
                "instancias de DataIssue."
            )

        self.rationale = (
            normalize_text(
                self.rationale,
                maximum_length=2_000,
            )
            or ""
        )

        if not self.observed:
            self.valid = False

        if not self.valid:
            self.score = None
            self.weighted_contribution = None

    @property
    def available(self) -> bool:
        return (
            self.observed
            and self.valid
            and self.score is not None
            and self.coverage > 0.0
        )

    @property
    def observed_metric_count(self) -> int:
        return sum(
            metric.observed
            for metric in self.metrics.values()
        )

    @property
    def available_metric_count(self) -> int:
        return sum(
            metric.available
            for metric in self.metrics.values()
        )

    def to_dict(self) -> dict[str, Any]:
        result = to_primitive(self)

        if not isinstance(result, dict):
            raise TypeError(
                "DimensionScore no pudo serializarse "
                "como diccionario."
            )

        return result
