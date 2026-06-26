from __future__ import annotations
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
PRESENTER_SCHEMA_VERSION = "1.2.0"
SUPPORTED_SERVICE_SCHEMA_MAJOR = 1
DEFAULT_TEXT_MAXIMUM_LENGTH = 2_000
MAXIMUM_TICKER_LENGTH = 30
MAXIMUM_COMPANY_NAME_LENGTH = 250
MAXIMUM_MODEL_VERSION_LENGTH = 50
MAXIMUM_SCHEMA_VERSION_LENGTH = 50
MAXIMUM_SERVICE_NAME_LENGTH = 100
MAXIMUM_GATE_CODE_LENGTH = 100
MAXIMUM_GATE_SEVERITY_LENGTH = 50
MAXIMUM_COMPONENT_NAME_LENGTH = 150
Tone = Literal[
    "positive",
    "warning",
    "negative",
    "neutral",
]
VALID_TONES = frozenset(
    {
        "positive",
        "warning",
        "negative",
        "neutral",
    }
)
NEW_INVESTOR_TONES: dict[str, Tone] = {
    "compra clara": "positive",
    "comprar": "positive",
    "compra parcial": "warning",
    "esperar": "warning",
    "requiere análisis maestro": "warning",
    "descartar": "negative",
    "datos no fiables": "negative",
}
HOLDER_TONES: dict[str, Tone] = {
    "aumentar": "positive",
    "mantener": "neutral",
    "revisar tesis": "warning",
    "reducir": "warning",
    "salir": "negative",
    "datos no fiables": "negative",
}
CONFIDENCE_TONES: dict[str, Tone] = {
    "alta": "positive",
    "media": "neutral",
    "baja": "warning",
    "no evaluable": "negative",
}
RISK_TONES: dict[str, Tone] = {
    "bajo": "positive",
    "medio": "warning",
    "alto": "negative",
    "crítico": "negative",
    "no evaluado": "neutral",
}
VALUATION_TONES: dict[str, Tone] = {
    "infravalorada": "positive",
    "muy atractiva": "positive",
    "atractiva": "positive",
    "valoración razonable": "neutral",
    "razonable": "neutral",
    "exigente": "warning",
    "sobrevalorada": "warning",
    "muy exigente": "warning",
    "no evaluada": "neutral",
}
MOAT_TONES: dict[str, Tone] = {
    "fuerte": "positive",
    "moderado": "neutral",
    "débil": "negative",
    "no evaluado": "neutral",
}
GATE_SEVERITY_ORDER = {
    "bloqueante": 0,
    "advertencia": 1,
    "informativo": 2,
}
class DecisionPresenterError(ValueError):
    """Error controlado al preparar datos para la interfaz."""
@dataclass(frozen=True)
class DecisionBadge:
    label: str
    value: str
    tone: Tone
    help_text: str | None = None
@dataclass(frozen=True)
class DecisionMetric:
    label: str
    value: str
    help_text: str | None = None
@dataclass(frozen=True)
class DecisionSection:
    title: str
    items: list[str] = field(
        default_factory=list
    )
    empty_message: str | None = None
@dataclass(frozen=True)
class GateView:
    code: str
    message: str
    severity: str
    passed: bool
    tone: Tone
@dataclass(frozen=True)
class RankingComponentView:
    name: str
    score: float | None
    weight: float | None
    weighted_score: float | None
    available: bool
    reason: str | None = None
@dataclass(frozen=True)
class DecisionView:
    success: bool
    schema_version: str
    service_schema_version: str | None = None
    service_name: str | None = None
    ticker: str | None = None
    company_name: str | None = None
    created_at: str | None = None
    model_version: str | None = None
    title: str = ""
    subtitle: str = ""
    new_investor_badge: DecisionBadge | None = None
    existing_holder_badge: DecisionBadge | None = None
    confidence_badge: DecisionBadge | None = None
    risk_badge: DecisionBadge | None = None
    valuation_badge: DecisionBadge | None = None
    moat_badge: DecisionBadge | None = None
    metrics: list[DecisionMetric] = field(
        default_factory=list
    )
    thesis: DecisionSection | None = None
    reasons: DecisionSection | None = None
    warnings: DecisionSection | None = None
    conditions_to_buy: DecisionSection | None = None
    conditions_to_reduce: DecisionSection | None = None
    gates: list[GateView] = field(
        default_factory=list
    )
    ranking_components: list[
        RankingComponentView
    ] = field(
        default_factory=list
    )
    presentation_warnings: list[str] = field(
        default_factory=list
    )
    error_type: str | None = None
    error_message: str | None = None
    raw_response: dict[str, Any] = field(
        default_factory=dict
    )
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
def _ensure_mapping(
    value: Any,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(
        value,
        Mapping,
    ):
        raise DecisionPresenterError(
            f"{field_name} debe ser un diccionario."
        )
    return value
def _optional_mapping(
    value: Any,
) -> Mapping[str, Any]:
    if isinstance(
        value,
        Mapping,
    ):
        return value
    return {}
def _mapping_with_warning(
    value: Any,
    *,
    field_name: str,
    presentation_warnings: list[str],
) -> Mapping[str, Any]:
    if isinstance(
        value,
        Mapping,
    ):
        return value
    if value is not None:
        presentation_warnings.append(
            f"El campo {field_name} no tiene "
            "un formato válido."
        )
    return {}
def _safe_copy_mapping(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        copied_value = deepcopy(
            dict(value)
        )
    except Exception as error:
        raise DecisionPresenterError(
            "No se pudo crear una copia segura "
            "de la respuesta."
        ) from error
    return copied_value
def _validate_maximum_length(
    maximum_length: int,
) -> None:
    if (
        isinstance(
            maximum_length,
            bool,
        )
        or not isinstance(
            maximum_length,
            int,
        )
        or maximum_length < 1
    ):
        raise DecisionPresenterError(
            "maximum_length debe ser un entero "
            "mayor que cero."
        )
def _normalize_whitespace(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()
def _text(
    value: Any,
    default: str = "",
    maximum_length: int = (
        DEFAULT_TEXT_MAXIMUM_LENGTH
    ),
) -> str:
    _validate_maximum_length(
        maximum_length
    )
    if value is None:
        return default
    if isinstance(
        value,
        bytes,
    ):
        return default
    if isinstance(
        value,
        str,
    ):
        normalized = _normalize_whitespace(
            value
        )
    else:
        normalized = _normalize_whitespace(
            str(value)
        )
    if not normalized:
        return default
    if len(normalized) > maximum_length:
        if maximum_length == 1:
            return "…"
        return (
            normalized[: maximum_length - 1]
            + "…"
        )
    return normalized
def _optional_text(
    value: Any,
    maximum_length: int = (
        DEFAULT_TEXT_MAXIMUM_LENGTH
    ),
) -> str | None:
    normalized = _text(
        value,
        maximum_length=maximum_length,
    )
    return normalized or None
def _boolean(
    value: Any,
    default: bool = False,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value
    return default
def _number(
    value: Any,
) -> float | None:
    if (
        value is None
        or isinstance(
            value,
            bool,
        )
    ):
        return None
    try:
        result = float(
            value
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None
    if not math.isfinite(
        result
    ):
        return None
    return result
def _number_in_range(
    value: Any,
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    numeric_value = _number(
        value
    )
    if numeric_value is None:
        return None
    if not (
        minimum
        <= numeric_value
        <= maximum
    ):
        return None
    return numeric_value
def _integer(
    value: Any,
) -> int | None:
    numeric_value = _number(
        value
    )
    if numeric_value is None:
        return None
    if not numeric_value.is_integer():
        return None
    return int(
        numeric_value
    )
def _deduplicate_strings(
    values: Sequence[Any],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if isinstance(
            item,
            bytes,
        ):
            continue
        normalized = _text(
            item
        )
        if not normalized:
            continue
        comparison_key = (
            normalized.casefold()
        )
        if comparison_key in seen:
            continue
        seen.add(
            comparison_key
        )
        result.append(
            normalized
        )
    return result
def _string_list(
    value: Any,
) -> list[str]:
    if value is None:
        return []
    if isinstance(
        value,
        bytes,
    ):
        return []
    if isinstance(
        value,
        str,
    ):
        normalized = _text(
            value
        )
        return (
            [normalized]
            if normalized
            else []
        )
    if not isinstance(
        value,
        Sequence,
    ):
        return []
    return _deduplicate_strings(
        value
    )
def _format_ratio_as_percentage(
    value: Any,
    decimals: int = 0,
) -> str:
    numeric_value = _number_in_range(
        value,
        minimum=0.0,
        maximum=1.0,
    )
    if numeric_value is None:
        return "No disponible"
    return (
        f"{numeric_value * 100.0:.{decimals}f} %"
    )
def _format_percentage_value(
    value: Any,
    decimals: int = 0,
) -> str:
    numeric_value = _number(
        value
    )
    if numeric_value is None:
        return "No disponible"
    return (
        f"{numeric_value:.{decimals}f} %"
    )
def _format_score(
    value: Any,
    decimals: int = 1,
) -> str:
    numeric_value = _number_in_range(
        value,
        minimum=0.0,
        maximum=100.0,
    )
    if numeric_value is None:
        return "No disponible"
    return (
        f"{numeric_value:.{decimals}f} / 100"
    )
def _normalize_status(
    value: Any,
) -> str:
    return _text(
        value
    ).casefold()
def _tone_from_mapping(
    value: Any,
    mapping: Mapping[str, Tone],
) -> Tone:
    normalized = _normalize_status(
        value
    )
    return mapping.get(
        normalized,
        "neutral",
    )
def _tone_for_new_investor_action(
    action: str,
) -> Tone:
    return _tone_from_mapping(
        action,
        NEW_INVESTOR_TONES,
    )
def _tone_for_holder_action(
    action: str,
) -> Tone:
    return _tone_from_mapping(
        action,
        HOLDER_TONES,
    )
def _tone_for_confidence(
    confidence: str,
) -> Tone:
    return _tone_from_mapping(
        confidence,
        CONFIDENCE_TONES,
    )
def _tone_for_risk(
    risk: str,
) -> Tone:
    return _tone_from_mapping(
        risk,
        RISK_TONES,
    )
def _tone_for_valuation(
    valuation: str,
) -> Tone:
    return _tone_from_mapping(
        valuation,
        VALUATION_TONES,
    )
def _tone_for_moat(
    moat: str,
) -> Tone:
    return _tone_from_mapping(
        moat,
        MOAT_TONES,
    )
def _tone_for_gate(
    passed: bool,
    severity: str,
) -> Tone:
    if passed:
        return "positive"
    normalized_severity = (
        _normalize_status(
            severity
        )
    )
    if (
        normalized_severity
        == "bloqueante"
    ):
        return "negative"
    if (
        normalized_severity
        == "advertencia"
    ):
        return "warning"
    return "neutral"
def _badge(
    label: str,
    value: Any,
    tone: Tone,
    help_text: str | None = None,
) -> DecisionBadge:
    normalized_tone: Tone = (
        tone
        if tone in VALID_TONES
        else "neutral"
    )
    return DecisionBadge(
        label=_text(
            label,
            "Sin etiqueta",
            maximum_length=100,
        ),
        value=_text(
            value,
            "No disponible",
        ),
        tone=normalized_tone,
        help_text=_optional_text(
            help_text
        ),
    )
def _section(
    title: str,
    value: Any,
    empty_message: str,
) -> DecisionSection:
    return DecisionSection(
        title=_text(
            title,
            "Sección",
            maximum_length=150,
        ),
        items=_string_list(
            value
        ),
        empty_message=_optional_text(
            empty_message
        ),
    )
def _normalize_ticker_for_comparison(
    value: Any,
) -> str | None:
    ticker = _optional_text(
        value,
        maximum_length=(
            MAXIMUM_TICKER_LENGTH
        ),
    )
    if ticker is None:
        return None
    return ticker.upper()
def _parse_schema_major(
    value: Any,
) -> int | None:
    normalized_version = (
        _optional_text(
            value,
            maximum_length=(
                MAXIMUM_SCHEMA_VERSION_LENGTH
            ),
        )
    )
    if normalized_version is None:
        return None
    major_part = (
        normalized_version
        .split(
            ".",
            maxsplit=1,
        )[0]
        .strip()
    )
    if not major_part.isdigit():
        return None
    return int(
        major_part
    )
def _collect_schema_warnings(
    response: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    schema_value = response.get(
        "schema_version"
    )
    schema_version = _optional_text(
        schema_value,
        maximum_length=(
            MAXIMUM_SCHEMA_VERSION_LENGTH
        ),
    )
    if schema_version is None:
        warnings.append(
            "La respuesta no informa de la versión "
            "del esquema del servicio."
        )
        return warnings
    schema_major = _parse_schema_major(
        schema_version
    )
    if schema_major is None:
        warnings.append(
            "La versión del esquema del servicio "
            "no tiene un formato reconocible."
        )
    elif (
        schema_major
        != SUPPORTED_SERVICE_SCHEMA_MAJOR
    ):
        warnings.append(
            "La versión principal del esquema del servicio "
            "puede no ser compatible con el presenter."
        )
    return warnings
def _gate_sort_key(
    gate: GateView,
) -> tuple[int, int, str]:
    failure_order = (
        1
        if gate.passed
        else 0
    )
    severity_order = (
        GATE_SEVERITY_ORDER.get(
            gate.severity.casefold(),
            3,
        )
    )
    return (
        failure_order,
        severity_order,
        gate.code.casefold(),
    )
def _build_gate_views(
    value: Any,
    presentation_warnings: list[str],
) -> list[GateView]:
    if (
        not isinstance(
            value,
            Sequence,
        )
        or isinstance(
            value,
            (
                str,
                bytes,
            ),
        )
    ):
        if value is not None:
            presentation_warnings.append(
                "El campo gates no tiene un formato válido."
            )
        return []
    gates: list[GateView] = []
    seen_codes: set[str] = set()
    for index, item in enumerate(
        value
    ):
        if not isinstance(
            item,
            Mapping,
        ):
            presentation_warnings.append(
                "Se ignoró un gate con formato inválido "
                f"en la posición {index}."
            )
            continue
        passed_value = item.get(
            "passed"
        )
        if not isinstance(
            passed_value,
            bool,
        ):
            presentation_warnings.append(
                "Se ignoró un gate sin un valor booleano "
                f"válido en passed en la posición {index}."
            )
            continue
        code = _optional_text(
            item.get(
                "code"
            ),
            maximum_length=(
                MAXIMUM_GATE_CODE_LENGTH
            ),
        )
        if code is None:
            presentation_warnings.append(
                "Se ignoró un gate sin código válido "
                f"en la posición {index}."
            )
            continue
        comparison_key = (
            code.casefold()
        )
        if comparison_key in seen_codes:
            presentation_warnings.append(
                f"Se ignoró el gate duplicado {code}."
            )
            continue
        seen_codes.add(
            comparison_key
        )
        message = _text(
            item.get(
                "message"
            ),
            "Sin detalle.",
        )
        severity = _text(
            item.get(
                "severity"
            ),
            "INFORMATIVO",
            maximum_length=(
                MAXIMUM_GATE_SEVERITY_LENGTH
            ),
        )
        gates.append(
            GateView(
                code=code,
                message=message,
                severity=severity,
                passed=passed_value,
                tone=_tone_for_gate(
                    passed=passed_value,
                    severity=severity,
                ),
            )
        )
    return sorted(
        gates,
        key=_gate_sort_key,
    )
def _validate_ranking_component_number(
    value: Any,
    *,
    minimum: float,
    maximum: float,
    field_label: str,
    component_name: str,
    presentation_warnings: list[str],
) -> float | None:
    if value is None:
        return None
    numeric_value = _number(
        value
    )
    if numeric_value is None:
        presentation_warnings.append(
            f"El campo {field_label} del componente "
            f"{component_name} no contiene un número válido."
        )
        return None
    if not (
        minimum
        <= numeric_value
        <= maximum
    ):
        presentation_warnings.append(
            f"El campo {field_label} del componente "
            f"{component_name} está fuera del rango permitido."
        )
        return None
    return numeric_value
def _build_ranking_component_views(
    raw_components: Mapping[str, Any],
    presentation_warnings: list[str],
) -> list[RankingComponentView]:
    value = raw_components.get(
        "ranking_components"
    )
    if (
        not isinstance(
            value,
            Sequence,
        )
        or isinstance(
            value,
            (
                str,
                bytes,
            ),
        )
    ):
        if value is not None:
            presentation_warnings.append(
                "Los componentes del ranking no tienen "
                "un formato válido."
            )
        return []
    components: list[
        RankingComponentView
    ] = []
    seen_names: set[str] = set()
    for index, item in enumerate(
        value
    ):
        if not isinstance(
            item,
            Mapping,
        ):
            presentation_warnings.append(
                "Se ignoró un componente del ranking "
                f"con formato inválido en la posición {index}."
            )
            continue
        name = _text(
            item.get(
                "name"
            ),
            f"Componente {index + 1}",
            maximum_length=(
                MAXIMUM_COMPONENT_NAME_LENGTH
            ),
        )
        comparison_key = (
            name.casefold()
        )
        if comparison_key in seen_names:
            presentation_warnings.append(
                "Se ignoró el componente duplicado "
                f"{name}."
            )
            continue
        seen_names.add(
            comparison_key
        )
        available_value = item.get(
            "available"
        )
        if not isinstance(
            available_value,
            bool,
        ):
            presentation_warnings.append(
                "El componente "
                f"{name} no contiene un indicador available "
                "booleano válido; se considera no disponible."
            )
            available = False
        else:
            available = (
                available_value
            )
        score = (
            _validate_ranking_component_number(
                item.get(
                    "raw_score"
                ),
                minimum=0.0,
                maximum=100.0,
                field_label="raw_score",
                component_name=name,
                presentation_warnings=(
                    presentation_warnings
                ),
            )
        )
        weight = (
            _validate_ranking_component_number(
                item.get(
                    "weight"
                ),
                minimum=0.0,
                maximum=1.0,
                field_label="weight",
                component_name=name,
                presentation_warnings=(
                    presentation_warnings
                ),
            )
        )
        weighted_score = (
            _validate_ranking_component_number(
                item.get(
                    "weighted_score"
                ),
                minimum=0.0,
                maximum=100.0,
                field_label="weighted_score",
                component_name=name,
                presentation_warnings=(
                    presentation_warnings
                ),
            )
        )
        if (
            available
            and score is None
        ):
            presentation_warnings.append(
                f"El componente {name} figura disponible "
                "pero no contiene una puntuación válida."
            )
        if (
            not available
            and any(
                candidate is not None
                for candidate in (
                    score,
                    weight,
                    weighted_score,
                )
            )
        ):
            presentation_warnings.append(
                f"El componente {name} figura como no "
                "disponible pero contiene valores numéricos."
            )
        if (
            score is not None
            and weight is not None
            and weighted_score is not None
        ):
            expected_weighted_score = (
                score * weight
            )
            tolerance = max(
                0.1,
                abs(
                    expected_weighted_score
                )
                * 0.01,
            )
            if (
                abs(
                    weighted_score
                    - expected_weighted_score
                )
                > tolerance
            ):
                presentation_warnings.append(
                    f"El weighted_score del componente {name} "
                    "no es coherente con raw_score y weight."
                )
        components.append(
            RankingComponentView(
                name=name,
                score=score,
                weight=weight,
                weighted_score=weighted_score,
                available=available,
                reason=_optional_text(
                    item.get(
                        "reason"
                    )
                ),
            )
        )
    return components
def _build_title(
    ticker: str,
    company_name: str | None,
) -> str:
    if company_name:
        return (
            f"{company_name} · {ticker}"
        )
    return ticker
def _build_subtitle(
    decision: Mapping[str, Any],
) -> str:
    quality = _text(
        decision.get(
            "company_quality"
        ),
        "NO EVALUABLE",
        maximum_length=50,
    )
    return (
        "Resultado del análisis maestro · "
        f"Calidad empresarial: {quality}"
    )
def _validated_ranking_coverage(
    raw_components: Mapping[str, Any],
    presentation_warnings: list[str],
) -> float | None:
    raw_value = raw_components.get(
        "ranking_coverage"
    )
    if raw_value is None:
        return None
    numeric_value = _number(
        raw_value
    )
    if numeric_value is None:
        presentation_warnings.append(
            "La cobertura del ranking no contiene "
            "un valor numérico válido."
        )
        return None
    if not (
        0.0
        <= numeric_value
        <= 1.0
    ):
        presentation_warnings.append(
            "La cobertura del ranking está fuera "
            "del rango permitido de 0 a 1."
        )
        return None
    return numeric_value
def _build_metrics(
    response: Mapping[str, Any],
    decision: Mapping[str, Any],
    raw_components: Mapping[str, Any],
    gates: list[GateView],
    presentation_warnings: list[str],
) -> list[DecisionMetric]:
    metadata = _mapping_with_warning(
        response.get(
            "metadata"
        ),
        field_name="metadata",
        presentation_warnings=(
            presentation_warnings
        ),
    )
    source_count_raw = metadata.get(
        "source_count"
    )
    source_count = _integer(
        source_count_raw
    )
    if (
        source_count_raw is not None
        and (
            source_count is None
            or source_count < 0
        )
    ):
        presentation_warnings.append(
            "El número de fuentes no contiene "
            "un entero no negativo válido."
        )
    source_count_text = (
        str(
            source_count
        )
        if (
            source_count is not None
            and source_count >= 0
        )
        else "No disponible"
    )
    ranking_score_raw = decision.get(
        "ranking_score"
    )
    ranking_score = _number_in_range(
        ranking_score_raw,
        minimum=0.0,
        maximum=100.0,
    )
    if (
        ranking_score_raw is not None
        and ranking_score is None
    ):
        presentation_warnings.append(
            "El ranking auxiliar no contiene una "
            "puntuación válida entre 0 y 100."
        )
    ranking_coverage = (
        _validated_ranking_coverage(
            raw_components,
            presentation_warnings,
        )
    )
    failed_gates = sum(
        not gate.passed
        for gate in gates
    )
    blocking_gates = sum(
        (
            not gate.passed
            and gate.severity.casefold()
            == "bloqueante"
        )
        for gate in gates
    )
    return [
        DecisionMetric(
            label="Ranking auxiliar",
            value=_format_score(
                ranking_score
            ),
            help_text=(
                "Ordena oportunidades, pero no sustituye "
                "los gates ni la decisión cualitativa."
            ),
        ),
        DecisionMetric(
            label="Cobertura del ranking",
            value=_format_ratio_as_percentage(
                ranking_coverage
            ),
            help_text=(
                "Proporción de dimensiones disponibles "
                "para calcular el ranking."
            ),
        ),
        DecisionMetric(
            label="Calidad empresarial",
            value=_text(
                decision.get(
                    "company_quality"
                ),
                "No evaluable",
                maximum_length=50,
            ),
        ),
        DecisionMetric(
            label="Gates fallidos",
            value=str(
                failed_gates
            ),
        ),
        DecisionMetric(
            label="Gates bloqueantes",
            value=str(
                blocking_gates
            ),
        ),
        DecisionMetric(
            label="Fuentes utilizadas",
            value=source_count_text,
        ),
        DecisionMetric(
            label="Calidad de datos",
            value=_text(
                metadata.get(
                    "data_quality_status"
                ),
                "No disponible",
                maximum_length=80,
            ),
        ),
        DecisionMetric(
            label="Versión del modelo",
            value=_text(
                response.get(
                    "model_version"
                ),
                "No disponible",
                maximum_length=(
                    MAXIMUM_MODEL_VERSION_LENGTH
                ),
            ),
        ),
    ]
def _collect_integrity_warnings(
    response: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(
        _collect_schema_warnings(
            response
        )
    )
    response_ticker = (
        _normalize_ticker_for_comparison(
            response.get(
                "ticker"
            )
        )
    )
    decision_ticker = (
        _normalize_ticker_for_comparison(
            decision.get(
                "ticker"
            )
        )
    )
    if (
        response_ticker
        and decision_ticker
        and response_ticker
        != decision_ticker
    ):
        warnings.append(
            "El ticker de la respuesta no coincide con "
            "el ticker de la decisión."
        )
    required_decision_fields = {
        "new_investor_action": (
            "Falta la recomendación para el nuevo inversor."
        ),
        "existing_holder_action": (
            "Falta la recomendación para el accionista actual."
        ),
        "confidence": (
            "Falta el nivel de confianza."
        ),
        "risk_level": (
            "Falta el nivel de riesgo."
        ),
        "valuation_status": (
            "Falta el estado de valoración."
        ),
        "moat_strength": (
            "Falta la fortaleza del moat."
        ),
        "moat_trend": (
            "Falta la tendencia del moat."
        ),
    }
    for field_name, warning in (
        required_decision_fields.items()
    ):
        if not _optional_text(
            decision.get(
                field_name
            )
        ):
            warnings.append(
                warning
            )
    return _deduplicate_strings(
        warnings
    )
def _build_error_view(
    response: Mapping[str, Any],
) -> DecisionView:
    error = _optional_mapping(
        response.get(
            "error"
        )
    )
    error_type = _text(
        error.get(
            "type"
        ),
        "UNKNOWN_ERROR",
        maximum_length=100,
    )
    error_message = _text(
        error.get(
            "message"
        ),
        (
            "No se pudo preparar el resultado "
            "del análisis."
        ),
    )
    presentation_warnings = (
        _collect_schema_warnings(
            response
        )
    )
    if not isinstance(
        response.get(
            "error"
        ),
        Mapping,
    ):
        presentation_warnings.append(
            "La respuesta de error no contiene "
            "un campo error válido."
        )
    return DecisionView(
        success=False,
        schema_version=PRESENTER_SCHEMA_VERSION,
        service_schema_version=(
            _optional_text(
                response.get(
                    "schema_version"
                ),
                maximum_length=(
                    MAXIMUM_SCHEMA_VERSION_LENGTH
                ),
            )
        ),
        service_name=_optional_text(
            response.get(
                "service"
            ),
            maximum_length=(
                MAXIMUM_SERVICE_NAME_LENGTH
            ),
        ),
        title=(
            "No se pudo completar el análisis"
        ),
        subtitle=error_message,
        presentation_warnings=(
            _deduplicate_strings(
                presentation_warnings
            )
        ),
        error_type=error_type,
        error_message=error_message,
        raw_response=_safe_copy_mapping(
            response
        ),
    )
def build_decision_view(
    response: Mapping[str, Any],
) -> DecisionView:
    """
    Convierte la respuesta del servicio en un modelo estable
    de presentación.
    No depende de Streamlit y no contiene lógica financiera.
    Tolera campos opcionales dañados, pero registra las
    anomalías en presentation_warnings.
    """
    validated_response = (
        _ensure_mapping(
            response,
            "La respuesta del servicio",
        )
    )
    success = validated_response.get(
        "success"
    )
    if not isinstance(
        success,
        bool,
    ):
        raise DecisionPresenterError(
            "La respuesta debe incluir un campo "
            "booleano success."
        )
    if not success:
        return _build_error_view(
            validated_response
        )
    decision = _ensure_mapping(
        validated_response.get(
            "decision"
        ),
        "decision",
    )
    presentation_warnings = (
        _collect_integrity_warnings(
            validated_response,
            decision,
        )
    )
    response_ticker = _optional_text(
        validated_response.get(
            "ticker"
        ),
        maximum_length=(
            MAXIMUM_TICKER_LENGTH
        ),
    )
    decision_ticker = _optional_text(
        decision.get(
            "ticker"
        ),
        maximum_length=(
            MAXIMUM_TICKER_LENGTH
        ),
    )
    ticker = (
        response_ticker
        or decision_ticker
        or "SIN TICKER"
    )
    company_name = _optional_text(
        validated_response.get(
            "company_name"
        ),
        maximum_length=(
            MAXIMUM_COMPANY_NAME_LENGTH
        ),
    )
    new_investor_action = _text(
        decision.get(
            "new_investor_action"
        ),
        "No disponible",
        maximum_length=100,
    )
    existing_holder_action = _text(
        decision.get(
            "existing_holder_action"
        ),
        "No disponible",
        maximum_length=100,
    )
    confidence = _text(
        decision.get(
            "confidence"
        ),
        "No evaluable",
        maximum_length=50,
    )
    risk_level = _text(
        decision.get(
            "risk_level"
        ),
        "No evaluado",
        maximum_length=50,
    )
    valuation_status = _text(
        decision.get(
            "valuation_status"
        ),
        "No evaluada",
        maximum_length=100,
    )
    moat_strength = _text(
        decision.get(
            "moat_strength"
        ),
        "No evaluado",
        maximum_length=50,
    )
    moat_trend = _text(
        decision.get(
            "moat_trend"
        ),
        "No evaluado",
        maximum_length=100,
    )
    raw_components_value = (
        decision.get(
            "raw_components"
        )
    )
    raw_components = (
        _mapping_with_warning(
            raw_components_value,
            field_name="raw_components",
            presentation_warnings=(
                presentation_warnings
            ),
        )
    )
    gates = _build_gate_views(
        decision.get(
            "gates"
        ),
        presentation_warnings,
    )
    ranking_components = (
        _build_ranking_component_views(
            raw_components,
            presentation_warnings,
        )
    )
    metrics = _build_metrics(
        response=validated_response,
        decision=decision,
        raw_components=raw_components,
        gates=gates,
        presentation_warnings=(
            presentation_warnings
        ),
    )
    moat_value = (
        f"{moat_strength} · {moat_trend}"
    )
    return DecisionView(
        success=True,
        schema_version=PRESENTER_SCHEMA_VERSION,
        service_schema_version=(
            _optional_text(
                validated_response.get(
                    "schema_version"
                ),
                maximum_length=(
                    MAXIMUM_SCHEMA_VERSION_LENGTH
                ),
            )
        ),
        service_name=_optional_text(
            validated_response.get(
                "service"
            ),
            maximum_length=(
                MAXIMUM_SERVICE_NAME_LENGTH
            ),
        ),
        ticker=ticker,
        company_name=company_name,
        created_at=_optional_text(
            validated_response.get(
                "created_at"
            ),
            maximum_length=100,
        ),
        model_version=_optional_text(
            validated_response.get(
                "model_version"
            ),
            maximum_length=(
                MAXIMUM_MODEL_VERSION_LENGTH
            ),
        ),
        title=_build_title(
            ticker=ticker,
            company_name=company_name,
        ),
        subtitle=_build_subtitle(
            decision
        ),
        new_investor_badge=_badge(
            label="Nuevo inversor",
            value=new_investor_action,
            tone=(
                _tone_for_new_investor_action(
                    new_investor_action
                )
            ),
            help_text=(
                "Acción recomendada para quien todavía "
                "no mantiene una posición."
            ),
        ),
        existing_holder_badge=_badge(
            label="Accionista actual",
            value=existing_holder_action,
            tone=_tone_for_holder_action(
                existing_holder_action
            ),
            help_text=(
                "Acción recomendada para quien ya mantiene "
                "una posición en la compañía."
            ),
        ),
        confidence_badge=_badge(
            label="Confianza",
            value=confidence,
            tone=_tone_for_confidence(
                confidence
            ),
        ),
        risk_badge=_badge(
            label="Riesgo",
            value=risk_level,
            tone=_tone_for_risk(
                risk_level
            ),
        ),
        valuation_badge=_badge(
            label="Valoración",
            value=valuation_status,
            tone=_tone_for_valuation(
                valuation_status
            ),
        ),
        moat_badge=_badge(
            label="Moat",
            value=moat_value,
            tone=_tone_for_moat(
                moat_strength
            ),
        ),
        metrics=metrics,
        thesis=_section(
            title="Tesis de inversión",
            value=decision.get(
                "thesis"
            ),
            empty_message=(
                "No hay elementos suficientes para "
                "formular una tesis."
            ),
        ),
        reasons=_section(
            title="Motivos de la decisión",
            value=decision.get(
                "reasons"
            ),
            empty_message=(
                "No se han identificado motivos "
                "adicionales."
            ),
        ),
        warnings=_section(
            title="Advertencias",
            value=decision.get(
                "warnings"
            ),
            empty_message=(
                "No se han identificado advertencias."
            ),
        ),
        conditions_to_buy=_section(
            title=(
                "Condiciones para comprar o aumentar"
            ),
            value=decision.get(
                "conditions_to_buy"
            ),
            empty_message=(
                "No se han definido condiciones "
                "adicionales de compra."
            ),
        ),
        conditions_to_reduce=_section(
            title=(
                "Condiciones para reducir o salir"
            ),
            value=decision.get(
                "conditions_to_reduce"
            ),
            empty_message=(
                "No se han definido condiciones "
                "adicionales de reducción."
            ),
        ),
        gates=gates,
        ranking_components=(
            ranking_components
        ),
        presentation_warnings=(
            _deduplicate_strings(
                presentation_warnings
            )
        ),
        raw_response=_safe_copy_mapping(
            validated_response
        ),
    )
def build_decision_view_dict(
    response: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Devuelve una representación serializable del modelo
    de presentación.
    """
    return build_decision_view(
        response
    ).to_dict()
