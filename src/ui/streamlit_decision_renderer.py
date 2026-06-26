from __future__ import annotations
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from src.ui.decision_presenter import (
    DecisionBadge,
    DecisionMetric,
    DecisionSection,
    DecisionView,
    GateView,
    RankingComponentView,
    build_decision_view,
)
RENDERER_VERSION = "1.1.0"
MAX_BADGE_COLUMNS = 3
MAX_METRIC_COLUMNS = 4
TONE_ICONS: dict[str, str] = {
    "positive": "✅",
    "warning": "⚠️",
    "negative": "⛔",
    "neutral": "ℹ️",
}
TONE_LABELS: dict[str, str] = {
    "positive": "Positivo",
    "warning": "Advertencia",
    "negative": "Negativo",
    "neutral": "Neutral",
}
REQUIRED_STREAMLIT_METHODS = frozenset(
    {
        "title",
        "caption",
        "subheader",
        "write",
        "metric",
        "columns",
        "warning",
        "error",
        "expander",
    }
)
class StreamlitDecisionRendererError(RuntimeError):
    """Error controlado durante el renderizado de una decisión."""
@dataclass(frozen=True)
class RenderSummary:
    success: bool
    rendered_badges: int
    rendered_metrics: int
    rendered_sections: int
    rendered_gates: int
    rendered_ranking_components: int
    debug_rendered: bool
def _get_streamlit(
    streamlit_module: Any | None,
) -> Any:
    if streamlit_module is not None:
        return streamlit_module
    try:
        import streamlit as st
    except ImportError as error:
        raise StreamlitDecisionRendererError(
            "Streamlit no está instalado."
        ) from error
    return st
def _validate_streamlit_interface(
    st: Any,
) -> None:
    missing_methods = sorted(
        method_name
        for method_name in REQUIRED_STREAMLIT_METHODS
        if not callable(
            getattr(
                st,
                method_name,
                None,
            )
        )
    )
    if missing_methods:
        joined_methods = ", ".join(
            missing_methods
        )
        raise StreamlitDecisionRendererError(
            "El módulo de Streamlit no contiene la API "
            f"mínima requerida: {joined_methods}."
        )
def _tone_icon(
    tone: str,
) -> str:
    return TONE_ICONS.get(
        tone,
        TONE_ICONS["neutral"],
    )
def _tone_label(
    tone: str,
) -> str:
    return TONE_LABELS.get(
        tone,
        TONE_LABELS["neutral"],
    )
def _call_metric(
    container: Any,
    *,
    label: str,
    value: str,
    help_text: str | None,
) -> None:
    try:
        container.metric(
            label=label,
            value=value,
            help=help_text,
        )
    except TypeError:
        container.metric(
            label=label,
            value=value,
        )
def _render_badge(
    container: Any,
    badge: DecisionBadge,
) -> None:
    icon = _tone_icon(
        badge.tone
    )
    help_text = (
        badge.help_text
        or _tone_label(
            badge.tone
        )
    )
    _call_metric(
        container,
        label=f"{icon} {badge.label}",
        value=badge.value,
        help_text=help_text,
    )
def _visible_badges(
    view: DecisionView,
) -> list[DecisionBadge]:
    badges = [
        view.new_investor_badge,
        view.existing_holder_badge,
        view.confidence_badge,
        view.risk_badge,
        view.valuation_badge,
        view.moat_badge,
    ]
    return [
        badge
        for badge in badges
        if badge is not None
    ]
def _render_in_column_rows(
    st: Any,
    items: Sequence[Any],
    *,
    maximum_columns: int,
    render_item: Any,
) -> int:
    if not items:
        return 0
    if maximum_columns < 1:
        raise StreamlitDecisionRendererError(
            "maximum_columns debe ser mayor que cero."
        )
    rendered_count = 0
    for row_start in range(
        0,
        len(items),
        maximum_columns,
    ):
        row_items = items[
            row_start:
            row_start + maximum_columns
        ]
        columns = st.columns(
            len(row_items)
        )
        if len(columns) != len(row_items):
            raise StreamlitDecisionRendererError(
                "Streamlit no devolvió el número esperado "
                "de columnas."
            )
        for container, item in zip(
            columns,
            row_items,
            strict=True,
        ):
            render_item(
                container,
                item,
            )
            rendered_count += 1
    return rendered_count
def _render_badges(
    st: Any,
    view: DecisionView,
) -> int:
    badges = _visible_badges(
        view
    )
    return _render_in_column_rows(
        st,
        badges,
        maximum_columns=MAX_BADGE_COLUMNS,
        render_item=_render_badge,
    )
def _render_metric(
    container: Any,
    metric: DecisionMetric,
) -> None:
    _call_metric(
        container,
        label=metric.label,
        value=metric.value,
        help_text=metric.help_text,
    )
def _render_metrics(
    st: Any,
    metrics: Sequence[DecisionMetric],
) -> int:
    if not metrics:
        return 0
    st.subheader(
        "Resumen cuantitativo"
    )
    return _render_in_column_rows(
        st,
        metrics,
        maximum_columns=MAX_METRIC_COLUMNS,
        render_item=_render_metric,
    )
def _render_section(
    st: Any,
    section: DecisionSection | None,
) -> bool:
    if section is None:
        return False
    st.subheader(
        section.title
    )
    if section.items:
        for item in section.items:
            st.write(
                f"• {item}"
            )
    elif section.empty_message:
        st.caption(
            section.empty_message
        )
    return True
def _gate_status_text(
    gate: GateView,
) -> str:
    if gate.passed:
        return "Superado"
    return "No superado"
def _gate_title(
    gate: GateView,
) -> str:
    icon = _tone_icon(
        gate.tone
    )
    return (
        f"{icon} {gate.code} · "
        f"{_gate_status_text(gate)} · "
        f"{gate.severity}"
    )
def _render_gate(
    st: Any,
    gate: GateView,
) -> None:
    with st.expander(
        _gate_title(
            gate
        ),
        expanded=not gate.passed,
    ):
        st.write(
            gate.message
        )
def _render_gates(
    st: Any,
    gates: Sequence[GateView],
) -> int:
    st.subheader(
        "Gates de decisión"
    )
    if not gates:
        st.caption(
            "No hay gates disponibles."
        )
        return 0
    for gate in gates:
        _render_gate(
            st,
            gate,
        )
    return len(
        gates
    )
def _format_optional_number(
    value: float | None,
    *,
    decimals: int,
) -> str:
    if value is None:
        return "No disponible"
    return f"{value:.{decimals}f}"
def _format_weight(
    value: float | None,
) -> str:
    if value is None:
        return "No disponible"
    return f"{value * 100.0:.1f} %"
def _ranking_component_row(
    component: RankingComponentView,
) -> dict[str, str]:
    return {
        "Componente": component.name,
        "Disponible": (
            "Sí"
            if component.available
            else "No"
        ),
        "Puntuación": _format_optional_number(
            component.score,
            decimals=1,
        ),
        "Peso": _format_weight(
            component.weight
        ),
        "Contribución": _format_optional_number(
            component.weighted_score,
            decimals=2,
        ),
        "Motivo": (
            component.reason
            or ""
        ),
    }
def _render_dataframe_compatibly(
    st: Any,
    rows: list[dict[str, str]],
) -> None:
    dataframe_method = getattr(
        st,
        "dataframe",
        None,
    )
    if callable(
        dataframe_method
    ):
        try:
            dataframe_method(
                rows,
                width="stretch",
                hide_index=True,
            )
        except TypeError:
            dataframe_method(
                rows,
                use_container_width=True,
                hide_index=True,
            )
        return
    table_method = getattr(
        st,
        "table",
        None,
    )
    if callable(
        table_method
    ):
        table_method(
            rows
        )
        return
    for row in rows:
        st.write(
            row
        )
def _render_ranking_components(
    st: Any,
    components: Sequence[
        RankingComponentView
    ],
) -> int:
    st.subheader(
        "Componentes del ranking"
    )
    if not components:
        st.caption(
            "No hay componentes de ranking disponibles."
        )
        return 0
    rows = [
        _ranking_component_row(
            component
        )
        for component in components
    ]
    _render_dataframe_compatibly(
        st,
        rows,
    )
    return len(
        components
    )
def _render_presentation_warnings(
    st: Any,
    warnings: Sequence[str],
) -> None:
    if not warnings:
        return
    st.warning(
        "Se han detectado advertencias técnicas "
        "al preparar la presentación."
    )
    for warning in warnings:
        st.write(
            f"• {warning}"
        )
def _render_header(
    st: Any,
    view: DecisionView,
) -> None:
    st.title(
        view.title
        or "Resultado del análisis"
    )
    if view.subtitle:
        st.caption(
            view.subtitle
        )
    metadata_parts: list[str] = []
    if view.created_at:
        metadata_parts.append(
            f"Generado: {view.created_at}"
        )
    if view.model_version:
        metadata_parts.append(
            f"Modelo: {view.model_version}"
        )
    if metadata_parts:
        st.caption(
            " · ".join(
                metadata_parts
            )
        )
def _render_error_view(
    st: Any,
    view: DecisionView,
) -> RenderSummary:
    st.error(
        view.error_message
        or "No se pudo completar el análisis."
    )
    if view.error_type:
        st.caption(
            f"Tipo de error: {view.error_type}"
        )
    _render_presentation_warnings(
        st,
        view.presentation_warnings,
    )
    return RenderSummary(
        success=False,
        rendered_badges=0,
        rendered_metrics=0,
        rendered_sections=0,
        rendered_gates=0,
        rendered_ranking_components=0,
        debug_rendered=False,
    )
def _render_debug_information(
    st: Any,
    view: DecisionView,
) -> bool:
    json_method = getattr(
        st,
        "json",
        None,
    )
    if not callable(
        json_method
    ):
        raise StreamlitDecisionRendererError(
            "El modo debug requiere el método st.json."
        )
    with st.expander(
        "Información técnica",
        expanded=False,
    ):
        json_method(
            view.raw_response
        )
    return True
def render_decision_view(
    view: DecisionView,
    *,
    streamlit_module: Any | None = None,
    show_debug: bool = False,
) -> RenderSummary:
    """
    Renderiza un DecisionView sin ejecutar lógica financiera.
    Devuelve un resumen estructurado para auditoría y pruebas.
    """
    if not isinstance(
        view,
        DecisionView,
    ):
        raise StreamlitDecisionRendererError(
            "view debe ser una instancia de DecisionView."
        )
    if not isinstance(
        show_debug,
        bool,
    ):
        raise StreamlitDecisionRendererError(
            "show_debug debe ser booleano."
        )
    st = _get_streamlit(
        streamlit_module
    )
    _validate_streamlit_interface(
        st
    )
    _render_header(
        st,
        view,
    )
    if not view.success:
        return _render_error_view(
            st,
            view,
        )
    _render_presentation_warnings(
        st,
        view.presentation_warnings,
    )
    rendered_badges = _render_badges(
        st,
        view,
    )
    rendered_metrics = _render_metrics(
        st,
        view.metrics,
    )
    rendered_sections = sum(
        _render_section(
            st,
            section,
        )
        for section in (
            view.thesis,
            view.reasons,
            view.warnings,
            view.conditions_to_buy,
            view.conditions_to_reduce,
        )
    )
    rendered_gates = _render_gates(
        st,
        view.gates,
    )
    rendered_ranking_components = (
        _render_ranking_components(
            st,
            view.ranking_components,
        )
    )
    debug_rendered = False
    if show_debug:
        debug_rendered = (
            _render_debug_information(
                st,
                view,
            )
        )
    return RenderSummary(
        success=True,
        rendered_badges=rendered_badges,
        rendered_metrics=rendered_metrics,
        rendered_sections=rendered_sections,
        rendered_gates=rendered_gates,
        rendered_ranking_components=(
            rendered_ranking_components
        ),
        debug_rendered=debug_rendered,
    )
def render_decision_response(
    response: Mapping[str, Any],
    *,
    streamlit_module: Any | None = None,
    show_debug: bool = False,
) -> DecisionView:
    """
    Convierte una respuesta del servicio, la renderiza y
    devuelve el DecisionView resultante.
    """
    if not isinstance(
        response,
        Mapping,
    ):
        raise StreamlitDecisionRendererError(
            "response debe ser un diccionario."
        )
    view = build_decision_view(
        response
    )
    render_decision_view(
        view,
        streamlit_module=streamlit_module,
        show_debug=show_debug,
    )
    return view
