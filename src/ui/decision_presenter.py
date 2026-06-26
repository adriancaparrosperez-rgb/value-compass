from __future__ import annotations
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
PRESENTER_SCHEMA_VERSION = "1.1.0"
Tone = Literal[
    "positive",
    "warning",
    "negative",
    "neutral",
]
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
    if not isinstance(value, Mapping):
        raise DecisionPresenterError(
            f"{field_name} debe ser un diccionario."
        )
    return value
def _optional_mapping(
    value: Any,
) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
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
def _text(
    value: Any,
    default: str = "",
    maximum_length: int = 2_000,
) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip()
    else:
        normalized = str(value).strip()
    if not normalized:
        return default
    if len(normalized) > maximum_length:
        return (
            normalized[: maximum_length - 1]
            + "…"
        )
    return normalized
def _optional_text(
    value: Any,
    maximum_length: int = 2_000,
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
    if isinstance(value, bool):
        return value
    return default
def _number(
    value: Any,
) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result
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
def _string_list(
    value: Any,
) -> list[str]:
    if value is None:
        return []
    if isinstance(
        value,
        (str, bytes),
    ):
        normalized = _text(
            value
        )
        return [
            normalized
        ] if normalized else []
    if not isinstance(
        value,
        Sequence,
    ):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _text(
            item
        )
        if not normalized:
            continue
        comparison_key = normalized.casefold()
        if comparison_key in seen:
            continue
        seen.add(
            comparison_key
        )
        result.append(
            normalized
        )
    return result
def _format_ratio_as_percentage(
    value: Any,
    decimals: int = 0,
) -> str:
    numeric_value = _number(
        value
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
    numeric_value = _number(
        value
    )
    if numeric_value is None:
        return "No disponible"
    bounded_value = max(
        0.0,
        min(
            100.0,
            numeric_value,
        ),
    )
    return (
        f"{bounded_value:.{decimals}f} / 100"
    )
def _normalize_status(
    value: Any,
) -> str:
    return _text(
        value
    ).casefold()
def _tone_for_new_investor_action(
    action: str,
) -> Tone:
    normalized = _normalize_status(
        action
    )
    if normalized in {
        "compra clara",
        "comprar",
    }:
        return "positive"
    if normalized in {
        "compra parcial",
        "esperar",
        "requiere análisis maestro",
    }:
        return "warning"
    if normalized in {
        "descartar",
        "datos no fiables",
    }:
        return "negative"
    return "neutral"
def _tone_for_holder_action(
    action: str,
) -> Tone:
    normalized = _normalize_status(
        action
    )
    if normalized == "aumentar":
        return "positive"
    if normalized == "mantener":
        return "neutral"
    if normalized in {
        "revisar tesis",
        "reducir",
    }:
        return "warning"
    if normalized in {
        "salir",
        "datos no fiables",
    }:
        return "negative"
    return "neutral"
def _tone_for_confidence(
    confidence: str,
) -> Tone:
    normalized = _normalize_status(
        confidence
    )
    if normalized == "alta":
        return "positive"
    if normalized == "media":
        return "neutral"
    if normalized == "baja":
        return "warning"
    if normalized == "no evaluable":
        return "negative"
    return "neutral"
def _tone_for_risk(
    risk: str,
) -> Tone:
    normalized = _normalize_status(
        risk
    )
    if normalized == "bajo":
        return "positive"
    if normalized == "medio":
        return "warning"
    if normalized in {
        "alto",
        "crítico",
    }:
        return "negative"
    return "neutral"
def _tone_for_valuation(
    valuation: str,
) -> Tone:
    normalized = _normalize_status(
        valuation
    )
    if normalized in {
        "infravalorada",
        "muy atractiva",
        "atractiva",
    }:
        return "positive"
    if normalized in {
        "valoración razonable",
        "razonable",
    }:
        return "neutral"
    if normalized in {
        "exigente",
        "sobrevalorada",
        "muy exigente",
    }:
        return "warning"
    return "neutral"
def _tone_for_moat(
    moat: str,
) -> Tone:
    normalized = _normalize_status(
        moat
    )
    if normalized == "fuerte":
        return "positive"
    if normalized == "moderado":
        return "neutral"
    if normalized == "débil":
        return "negative"
    return "neutral"
def _tone_for_gate(
    passed: bool,
    severity: str,
) -> Tone:
    if passed:
        return "positive"
    normalized_severity = _normalize_status(
        severity
    )
    if normalized_severity == "bloqueante":
        return "negative"
    if normalized_severity == "advertencia":
        return "warning"
    return "neutral"
def _badge(
    label: str,
    value: Any,
    tone: Tone,
    help_text: str | None = None,
) -> DecisionBadge:
    return DecisionBadge(
        label=label,
        value=_text(
            value,
            "No disponible",
        ),
        tone=tone,
        help_text=help_text,
    )
def _section(
    title: str,
    value: Any,
    empty_message: str,
) -> DecisionSection:
    return DecisionSection(
        title=title,
        items=_string_list(
            value
        ),
        empty_message=empty_message,
    )
def _gate_sort_key(
    gate: GateView,
) -> tuple[int, int, str]:
    if gate.passed:
        failure_order = 1
    else:
        failure_order = 0
    severity_order = {
        "bloqueante": 0,
        "advertencia": 1,
        "informativo": 2,
    }.get(
        gate.severity.casefold(),
        3,
    )
    return (
        failure_order,
        severity_order,
        gate.code,
    )
def _build_gate_views(
    value: Any,
    presentation_warnings: list[str],
) -> list[GateView]:
    if not isinstance(
        value,
        Sequence,
    ) or isinstance(
        value,
        (str, bytes),
    ):
        if value is not None:
            presentation_warnings.append(
                "El campo gates no tiene un formato válido."
            )
        return []
    gates: list[GateView] = []
    seen_codes: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(
            item,
            Mapping,
        ):
            presentation_warnings.append(
                "Se ignoró un gate con formato inválido "
                f"en la posición {index}."
            )
            continue
        code = _text(
            item.get("code"),
            f"UNKNOWN_GATE_{index}",
            maximum_length=100,
        )
        comparison_key = code.casefold()
        if comparison_key in seen_codes:
            presentation_warnings.append(
                f"Se ignoró el gate duplicado {code}."
            )
            continue
        seen_codes.add(
            comparison_key
        )
        message = _text(
            item.get("message"),
            "Sin detalle.",
        )
        severity = _text(
            item.get("severity"),
            "INFORMATIVO",
            maximum_length=50,
        )
        passed = _boolean(
            item.get("passed")
        )
        gates.append(
            GateView(
                code=code,
                message=message,
                severity=severity,
                passed=passed,
                tone=_tone_for_gate(
                    passed=passed,
                    severity=severity,
                ),
            )
        )
    return sorted(
        gates,
        key=_gate_sort_key,
    )
def _build_ranking_component_views(
    raw_components: Mapping[str, Any],
    presentation_warnings: list[str],
) -> list[RankingComponentView]:
    value = raw_components.get(
        "ranking_components"
    )
    if not isinstance(
        value,
        Sequence,
    ) or isinstance(
        value,
        (str, bytes),
    ):
        if value is not None:
            presentation_warnings.append(
                "Los componentes del ranking no tienen "
                "un formato válido."
            )
        return []
    components: list[RankingComponentView] = []
    seen_names: set[str] = set()
    for index, item in enumerate(value):
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
            item.get("name"),
            f"Componente {index + 1}",
            maximum_length=150,
        )
        comparison_key = name.casefold()
        if comparison_key in seen_names:
            presentation_warnings.append(
                "Se ignoró el componente duplicado "
                f"{name}."
            )
            continue
        seen_names.add(
            comparison_key
        )
        score = _number(
            item.get("raw_score")
        )
        weight = _number(
            item.get("weight")
        )
        weighted_score = _number(
            item.get("weighted_score")
        )
        available = _boolean(
            item.get("available")
        )
        if available and score is None:
            presentation_warnings.append(
                f"El componente {name} figura disponible "
                "pero no contiene una puntuación válida."
            )
        components.append(
            RankingComponentView(
                name=name,
                score=score,
                weight=weight,
                weighted_score=weighted_score,
                available=available,
                reason=_optional_text(
                    item.get("reason")
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
        decision.get("company_quality"),
        "NO EVALUABLE",
        maximum_length=50,
    )
    return (
        "Resultado del análisis maestro · "
        f"Calidad empresarial: {quality}"
    )
def _build_metrics(
    response: Mapping[str, Any],
    decision: Mapping[str, Any],
    raw_components: Mapping[str, Any],
    gates: list[GateView],
) -> list[DecisionMetric]:
    metadata = _optional_mapping(
        response.get("metadata")
    )
    source_count = _integer(
        metadata.get("source_count")
    )
    source_count_text = (
        str(source_count)
        if source_count is not None
        and source_count >= 0
        else "No disponible"
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
                decision.get(
                    "ranking_score"
                )
            ),
            help_text=(
                "Ordena oportunidades, pero no sustituye "
                "los gates ni la decisión cualitativa."
            ),
        ),
        DecisionMetric(
            label="Cobertura del ranking",
            value=_format_ratio_as_percentage(
                raw_components.get(
                    "ranking_coverage"
                )
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
                maximum_length=50,
            ),
        ),
    ]
def _collect_integrity_warnings(
    response: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    response_ticker = _optional_text(
        response.get("ticker"),
        maximum_length=30,
    )
    decision_ticker = _optional_text(
        decision.get("ticker"),
        maximum_length=30,
    )
    if (
        response_ticker
        and decision_ticker
        and response_ticker != decision_ticker
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
            decision.get(field_name)
        ):
            warnings.append(
                warning
            )
    return warnings
def _build_error_view(
    response: Mapping[str, Any],
) -> DecisionView:
    error = _optional_mapping(
        response.get("error")
    )
    error_type = _text(
        error.get("type"),
        "UNKNOWN_ERROR",
        maximum_length=100,
    )
    error_message = _text(
        error.get("message"),
        (
            "No se pudo preparar el resultado "
            "del análisis."
        ),
    )
    return DecisionView(
        success=False,
        schema_version=PRESENTER_SCHEMA_VERSION,
        service_schema_version=_optional_text(
            response.get("schema_version"),
            maximum_length=50,
        ),
        service_name=_optional_text(
            response.get("service"),
            maximum_length=100,
        ),
        title="No se pudo completar el análisis",
        subtitle=error_message,
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
    """
    validated_response = _ensure_mapping(
        response,
        "La respuesta del servicio",
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
        validated_response.get("ticker"),
        maximum_length=30,
    )
    decision_ticker = _optional_text(
        decision.get("ticker"),
        maximum_length=30,
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
        maximum_length=250,
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
        decision.get("confidence"),
        "No evaluable",
        maximum_length=50,
    )
    risk_level = _text(
        decision.get("risk_level"),
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
    raw_components = _optional_mapping(
        decision.get(
            "raw_components"
        )
    )
    gates = _build_gate_views(
        decision.get("gates"),
        presentation_warnings,
    )
    ranking_components = (
        _build_ranking_component_views(
            raw_components,
            presentation_warnings,
        )
    )
    moat_value = (
        f"{moat_strength} · {moat_trend}"
    )
    return DecisionView(
        success=True,
        schema_version=PRESENTER_SCHEMA_VERSION,
        service_schema_version=_optional_text(
            validated_response.get(
                "schema_version"
            ),
            maximum_length=50,
        ),
        service_name=_optional_text(
            validated_response.get(
                "service"
            ),
            maximum_length=100,
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
            maximum_length=50,
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
            tone=_tone_for_new_investor_action(
                new_investor_action
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
        metrics=_build_metrics(
            response=validated_response,
            decision=decision,
            raw_components=raw_components,
            gates=gates,
        ),
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
            title="Condiciones para comprar o aumentar",
            value=decision.get(
                "conditions_to_buy"
            ),
            empty_message=(
                "No se han definido condiciones "
                "adicionales de compra."
            ),
        ),
        conditions_to_reduce=_section(
            title="Condiciones para reducir o salir",
            value=decision.get(
                "conditions_to_reduce"
            ),
            empty_message=(
                "No se han definido condiciones "
                "adicionales de reducción."
            ),
        ),
        gates=gates,
        ranking_components=ranking_components,
        presentation_warnings=_string_list(
            presentation_warnings
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
