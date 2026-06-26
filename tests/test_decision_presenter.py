from __future__ import annotations
import json
from copy import deepcopy
from typing import Any
import pytest
from src.ui.decision_presenter import (
    PRESENTER_SCHEMA_VERSION,
    DecisionBadge,
    DecisionPresenterError,
    DecisionView,
    GateView,
    RankingComponentView,
    build_decision_view,
    build_decision_view_dict,
)
def _success_response() -> dict[str, Any]:
    return {
        "success": True,
        "service": "master-decision-service",
        "schema_version": "1.0.0",
        "model_version": "0.1.0",
        "ticker": "TEST",
        "company_name": "Test Company",
        "created_at": "2026-06-26T12:00:00+00:00",
        "decision": {
            "ticker": "TEST",
            "new_investor_action": "COMPRAR",
            "existing_holder_action": "MANTENER",
            "confidence": "ALTA",
            "risk_level": "BAJO",
            "company_quality": "ALTA",
            "valuation_status": "ATRACTIVA",
            "moat_strength": "FUERTE",
            "moat_trend": "ESTABLE",
            "ranking_score": 82.5,
            "gates": [
                {
                    "code": "DATA_QUALITY",
                    "passed": True,
                    "severity": "BLOQUEANTE",
                    "message": (
                        "La calidad de datos es suficiente."
                    ),
                },
                {
                    "code": "VALUATION_WARNING",
                    "passed": False,
                    "severity": "ADVERTENCIA",
                    "message": (
                        "El margen de seguridad es limitado."
                    ),
                },
                {
                    "code": "ACCOUNTING_BLOCK",
                    "passed": False,
                    "severity": "BLOQUEANTE",
                    "message": (
                        "La calidad contable es insuficiente."
                    ),
                },
            ],
            "thesis": [
                "La compañía presenta una calidad elevada.",
                "El moat es fuerte.",
            ],
            "reasons": [
                "La valoración es atractiva.",
            ],
            "warnings": [
                "La cobertura histórica es limitada.",
            ],
            "conditions_to_buy": [
                (
                    "Mantener un margen de seguridad "
                    "suficiente."
                ),
            ],
            "conditions_to_reduce": [
                (
                    "Reducir ante deterioro material "
                    "del moat."
                ),
            ],
            "raw_components": {
                "ranking_coverage": 0.90,
                "ranking_components": [
                    {
                        "name": "Calidad del negocio",
                        "raw_score": 85.0,
                        "weight": 0.25,
                        "weighted_score": 21.25,
                        "available": True,
                        "reason": None,
                    },
                    {
                        "name": "Valoración",
                        "raw_score": 75.0,
                        "weight": 0.20,
                        "weighted_score": 15.0,
                        "available": True,
                        "reason": None,
                    },
                ],
            },
        },
        "metadata": {
            "source_count": 4,
            "data_quality_status": "VALIDADOS",
            "ranking_score": 82.5,
            "confidence": "ALTA",
            "risk_level": "BAJO",
            "new_investor_action": "COMPRAR",
            "existing_holder_action": "MANTENER",
        },
    }
def _error_response() -> dict[str, Any]:
    return {
        "success": False,
        "service": "master-decision-service",
        "schema_version": "1.0.0",
        "error": {
            "type": "INVALID_INPUT",
            "message": "El ticker no puede estar vacío.",
        },
    }
def _metric_value(
    view: DecisionView,
    label: str,
) -> str:
    for metric in view.metrics:
        if metric.label == label:
            return metric.value
    raise AssertionError(
        f"No se encontró la métrica: {label}"
    )
def _assert_badge(
    badge: DecisionBadge | None,
    *,
    value: str,
    tone: str,
) -> None:
    assert badge is not None
    assert badge.value == value
    assert badge.tone == tone
def _gate_by_code(
    view: DecisionView,
    code: str,
) -> GateView:
    for gate in view.gates:
        if gate.code == code:
            return gate
    raise AssertionError(
        f"No se encontró el gate: {code}"
    )
def _ranking_component_by_name(
    view: DecisionView,
    name: str,
) -> RankingComponentView:
    for component in view.ranking_components:
        if component.name == name:
            return component
    raise AssertionError(
        "No se encontró el componente del ranking: "
        f"{name}"
    )
def test_success_response_builds_complete_view() -> None:
    view = build_decision_view(
        _success_response()
    )
    assert isinstance(
        view,
        DecisionView,
    )
    assert view.success is True
    assert (
        view.schema_version
        == PRESENTER_SCHEMA_VERSION
    )
    assert view.service_schema_version == "1.0.0"
    assert (
        view.service_name
        == "master-decision-service"
    )
    assert view.ticker == "TEST"
    assert view.company_name == "Test Company"
    assert (
        view.created_at
        == "2026-06-26T12:00:00+00:00"
    )
    assert view.model_version == "0.1.0"
    assert view.title == "Test Company · TEST"
    assert view.subtitle == (
        "Resultado del análisis maestro · "
        "Calidad empresarial: ALTA"
    )
    assert view.error_type is None
    assert view.error_message is None
def test_success_response_builds_expected_badges() -> None:
    view = build_decision_view(
        _success_response()
    )
    _assert_badge(
        view.new_investor_badge,
        value="COMPRAR",
        tone="positive",
    )
    _assert_badge(
        view.existing_holder_badge,
        value="MANTENER",
        tone="neutral",
    )
    _assert_badge(
        view.confidence_badge,
        value="ALTA",
        tone="positive",
    )
    _assert_badge(
        view.risk_badge,
        value="BAJO",
        tone="positive",
    )
    _assert_badge(
        view.valuation_badge,
        value="ATRACTIVA",
        tone="positive",
    )
    _assert_badge(
        view.moat_badge,
        value="FUERTE · ESTABLE",
        tone="positive",
    )
def test_badges_include_descriptive_labels() -> None:
    view = build_decision_view(
        _success_response()
    )
    assert view.new_investor_badge is not None
    assert (
        view.new_investor_badge.label
        == "Nuevo inversor"
    )
    assert view.existing_holder_badge is not None
    assert (
        view.existing_holder_badge.label
        == "Accionista actual"
    )
    assert view.confidence_badge is not None
    assert view.confidence_badge.label == "Confianza"
    assert view.risk_badge is not None
    assert view.risk_badge.label == "Riesgo"
    assert view.valuation_badge is not None
    assert view.valuation_badge.label == "Valoración"
    assert view.moat_badge is not None
    assert view.moat_badge.label == "Moat"
def test_metrics_are_formatted_correctly() -> None:
    view = build_decision_view(
        _success_response()
    )
    assert (
        _metric_value(
            view,
            "Ranking auxiliar",
        )
        == "82.5 / 100"
    )
    assert (
        _metric_value(
            view,
            "Cobertura del ranking",
        )
        == "90 %"
    )
    assert (
        _metric_value(
            view,
            "Calidad empresarial",
        )
        == "ALTA"
    )
    assert (
        _metric_value(
            view,
            "Fuentes utilizadas",
        )
        == "4"
    )
    assert (
        _metric_value(
            view,
            "Calidad de datos",
        )
        == "VALIDADOS"
    )
    assert (
        _metric_value(
            view,
            "Versión del modelo",
        )
        == "0.1.0"
    )
def test_gate_metrics_count_failures_and_blockers() -> None:
    view = build_decision_view(
        _success_response()
    )
    assert (
        _metric_value(
            view,
            "Gates fallidos",
        )
        == "2"
    )
    assert (
        _metric_value(
            view,
            "Gates bloqueantes",
        )
        == "1"
    )
def test_no_gates_produce_zero_gate_metrics() -> None:
    response = _success_response()
    response["decision"]["gates"] = []
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Gates fallidos",
        )
        == "0"
    )
    assert (
        _metric_value(
            view,
            "Gates bloqueantes",
        )
        == "0"
    )
    assert view.gates == []
def test_failed_gates_are_sorted_before_passed_gates() -> None:
    view = build_decision_view(
        _success_response()
    )
    assert [
        gate.code
        for gate in view.gates
    ] == [
        "ACCOUNTING_BLOCK",
        "VALUATION_WARNING",
        "DATA_QUALITY",
    ]
def test_gate_tones_are_assigned_from_result_and_severity() -> None:
    view = build_decision_view(
        _success_response()
    )
    accounting_gate = _gate_by_code(
        view,
        "ACCOUNTING_BLOCK",
    )
    valuation_gate = _gate_by_code(
        view,
        "VALUATION_WARNING",
    )
    data_gate = _gate_by_code(
        view,
        "DATA_QUALITY",
    )
    assert accounting_gate.tone == "negative"
    assert valuation_gate.tone == "warning"
    assert data_gate.tone == "positive"
def test_unknown_failed_gate_severity_is_neutral() -> None:
    response = _success_response()
    response["decision"]["gates"] = [
        {
            "code": "UNKNOWN",
            "passed": False,
            "severity": "DESCONOCIDA",
            "message": "Gate desconocido.",
        }
    ]
    view = build_decision_view(
        response
    )
    assert len(view.gates) == 1
    assert view.gates[0].tone == "neutral"
def test_non_boolean_gate_passed_is_ignored_with_warning() -> None:
    response = _success_response()
    response["decision"]["gates"] = [
        {
            "code": "INVALID_BOOLEAN",
            "passed": "true",
            "severity": "BLOQUEANTE",
            "message": "Valor booleano inválido.",
        }
    ]
    view = build_decision_view(
        response
    )
    assert view.gates == []
    assert any(
        "sin un valor booleano válido"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_ranking_components_are_created() -> None:
    view = build_decision_view(
        _success_response()
    )
    assert len(
        view.ranking_components
    ) == 2
    component = _ranking_component_by_name(
        view,
        "Calidad del negocio",
    )
    assert component.score == 85.0
    assert component.weight == 0.25
    assert component.weighted_score == 21.25
    assert component.available is True
    assert component.reason is None
def test_unavailable_ranking_component_is_preserved() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"] = [
        {
            "name": "Crecimiento",
            "raw_score": None,
            "weight": 0.10,
            "weighted_score": None,
            "available": False,
            "reason": "No existen datos suficientes.",
        }
    ]
    view = build_decision_view(
        response
    )
    component = _ranking_component_by_name(
        view,
        "Crecimiento",
    )
    assert component.available is False
    assert component.score is None
    assert component.weight == 0.10
    assert component.weighted_score is None
    assert (
        component.reason
        == "No existen datos suficientes."
    )
def test_sections_are_created_with_expected_content() -> None:
    view = build_decision_view(
        _success_response()
    )
    assert view.thesis is not None
    assert view.reasons is not None
    assert view.warnings is not None
    assert view.conditions_to_buy is not None
    assert view.conditions_to_reduce is not None
    assert view.thesis.items == [
        "La compañía presenta una calidad elevada.",
        "El moat es fuerte.",
    ]
    assert view.reasons.items == [
        "La valoración es atractiva.",
    ]
    assert view.warnings.items == [
        "La cobertura histórica es limitada.",
    ]
    assert view.conditions_to_buy.items == [
        (
            "Mantener un margen de seguridad "
            "suficiente."
        ),
    ]
    assert view.conditions_to_reduce.items == [
        (
            "Reducir ante deterioro material "
            "del moat."
        ),
    ]
def test_empty_sections_retain_empty_messages() -> None:
    response = _success_response()
    response["decision"]["thesis"] = []
    response["decision"]["reasons"] = None
    response["decision"]["warnings"] = []
    response["decision"]["conditions_to_buy"] = None
    response["decision"]["conditions_to_reduce"] = []
    view = build_decision_view(
        response
    )
    assert view.thesis is not None
    assert view.thesis.items == []
    assert view.thesis.empty_message is not None
    assert view.reasons is not None
    assert view.reasons.items == []
    assert view.reasons.empty_message is not None
    assert view.warnings is not None
    assert view.warnings.items == []
    assert view.warnings.empty_message is not None
    assert view.conditions_to_buy is not None
    assert view.conditions_to_buy.items == []
    assert (
        view.conditions_to_buy.empty_message
        is not None
    )
    assert view.conditions_to_reduce is not None
    assert view.conditions_to_reduce.items == []
    assert (
        view.conditions_to_reduce.empty_message
        is not None
    )
def test_string_section_is_converted_to_single_item() -> None:
    response = _success_response()
    response["decision"]["reasons"] = (
        "Motivo único."
    )
    view = build_decision_view(
        response
    )
    assert view.reasons is not None
    assert view.reasons.items == [
        "Motivo único."
    ]
def test_section_items_are_deduplicated_case_insensitively() -> None:
    response = _success_response()
    response["decision"]["warnings"] = [
        "Advertencia repetida.",
        "advertencia repetida.",
        "ADVERTENCIA REPETIDA.",
        "Otra advertencia.",
        " ",
    ]
    view = build_decision_view(
        response
    )
    assert view.warnings is not None
    assert view.warnings.items == [
        "Advertencia repetida.",
        "Otra advertencia.",
    ]
def test_error_response_builds_complete_error_view() -> None:
    view = build_decision_view(
        _error_response()
    )
    assert view.success is False
    assert (
        view.schema_version
        == PRESENTER_SCHEMA_VERSION
    )
    assert view.service_schema_version == "1.0.0"
    assert (
        view.service_name
        == "master-decision-service"
    )
    assert view.error_type == "INVALID_INPUT"
    assert (
        view.error_message
        == "El ticker no puede estar vacío."
    )
    assert (
        view.title
        == "No se pudo completar el análisis"
    )
    assert (
        view.subtitle
        == "El ticker no puede estar vacío."
    )
def test_error_response_with_missing_error_fields_is_safe() -> None:
    response: dict[str, Any] = {
        "success": False,
        "error": {},
    }
    view = build_decision_view(
        response
    )
    assert view.success is False
    assert view.error_type == "UNKNOWN_ERROR"
    assert view.error_message == (
        "No se pudo preparar el resultado "
        "del análisis."
    )
def test_error_response_with_non_mapping_error_is_safe() -> None:
    response: dict[str, Any] = {
        "success": False,
        "error": "error inválido",
    }
    view = build_decision_view(
        response
    )
    assert view.success is False
    assert view.error_type == "UNKNOWN_ERROR"
    assert view.error_message == (
        "No se pudo preparar el resultado "
        "del análisis."
    )
    assert any(
        "campo error válido"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_missing_success_field_raises_error() -> None:
    with pytest.raises(
        DecisionPresenterError,
        match="campo booleano success",
    ):
        build_decision_view(
            {
                "decision": {},
            }
        )
@pytest.mark.parametrize(
    "invalid_success",
    [
        "true",
        1,
        0,
        None,
        [],
        {},
    ],
)
def test_non_boolean_success_field_raises_error(
    invalid_success: Any,
) -> None:
    with pytest.raises(
        DecisionPresenterError,
        match="campo booleano success",
    ):
        build_decision_view(
            {
                "success": invalid_success,
                "decision": {},
            }
        )
@pytest.mark.parametrize(
    "invalid_response",
    [
        [],
        "invalid",
        123,
        None,
    ],
)
def test_non_mapping_response_raises_error(
    invalid_response: Any,
) -> None:
    with pytest.raises(
        DecisionPresenterError,
        match="debe ser un diccionario",
    ):
        build_decision_view(
            invalid_response
        )
@pytest.mark.parametrize(
    "invalid_decision",
    [
        None,
        [],
        "invalid",
        123,
    ],
)
def test_success_without_valid_decision_mapping_raises_error(
    invalid_decision: Any,
) -> None:
    with pytest.raises(
        DecisionPresenterError,
        match="decision debe ser un diccionario",
    ):
        build_decision_view(
            {
                "success": True,
                "decision": invalid_decision,
            }
        )
def test_response_ticker_has_priority_over_decision_ticker() -> None:
    response = _success_response()
    response["ticker"] = "PRIMARY"
    response["decision"]["ticker"] = "SECONDARY"
    view = build_decision_view(
        response
    )
    assert view.ticker == "PRIMARY"
def test_decision_ticker_is_used_when_response_ticker_is_missing() -> None:
    response = _success_response()
    response.pop(
        "ticker"
    )
    response["decision"]["ticker"] = "FALLBACK"
    view = build_decision_view(
        response
    )
    assert view.ticker == "FALLBACK"
    assert view.title == "Test Company · FALLBACK"
def test_missing_all_tickers_uses_safe_fallback() -> None:
    response = _success_response()
    response.pop(
        "ticker"
    )
    response["decision"].pop(
        "ticker"
    )
    view = build_decision_view(
        response
    )
    assert view.ticker == "SIN TICKER"
def test_missing_company_name_uses_ticker_as_title() -> None:
    response = _success_response()
    response["company_name"] = None
    view = build_decision_view(
        response
    )
    assert view.company_name is None
    assert view.title == "TEST"
def test_ticker_mismatch_generates_integrity_warning() -> None:
    response = _success_response()
    response["decision"]["ticker"] = "OTHER"
    view = build_decision_view(
        response
    )
    assert any(
        "ticker de la respuesta no coincide"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_ticker_comparison_is_case_insensitive() -> None:
    response = _success_response()
    response["ticker"] = "test"
    response["decision"]["ticker"] = "TEST"
    view = build_decision_view(
        response
    )
    assert not any(
        "ticker de la respuesta no coincide"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
@pytest.mark.parametrize(
    ("field_name", "expected_text"),
    [
        (
            "new_investor_action",
            "nuevo inversor",
        ),
        (
            "existing_holder_action",
            "accionista actual",
        ),
        (
            "confidence",
            "nivel de confianza",
        ),
        (
            "risk_level",
            "nivel de riesgo",
        ),
        (
            "valuation_status",
            "estado de valoración",
        ),
        (
            "moat_strength",
            "fortaleza del moat",
        ),
        (
            "moat_trend",
            "tendencia del moat",
        ),
    ],
)
def test_missing_required_decision_field_generates_warning(
    field_name: str,
    expected_text: str,
) -> None:
    response = _success_response()
    response["decision"].pop(
        field_name
    )
    view = build_decision_view(
        response
    )
    assert any(
        expected_text in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_invalid_gate_collection_generates_warning() -> None:
    response = _success_response()
    response["decision"]["gates"] = {}
    view = build_decision_view(
        response
    )
    assert view.gates == []
    assert any(
        "campo gates no tiene un formato válido"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_invalid_gate_item_is_ignored_with_warning() -> None:
    response = _success_response()
    response["decision"]["gates"].append(
        "gate inválido"
    )
    view = build_decision_view(
        response
    )
    assert len(view.gates) == 3
    assert any(
        "gate con formato inválido"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_duplicate_gate_is_ignored_case_insensitively() -> None:
    response = _success_response()
    response["decision"]["gates"].append(
        {
            "code": "data_quality",
            "passed": False,
            "severity": "BLOQUEANTE",
            "message": "Duplicado.",
        }
    )
    view = build_decision_view(
        response
    )
    assert sum(
        gate.code.casefold()
        == "data_quality"
        for gate in view.gates
    ) == 1
    assert any(
        "gate duplicado"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_missing_gate_code_is_ignored_with_warning() -> None:
    response = _success_response()
    response["decision"]["gates"] = [
        {
            "passed": False,
            "severity": "ADVERTENCIA",
            "message": "Sin código.",
        }
    ]
    view = build_decision_view(
        response
    )
    assert view.gates == []
    assert any(
        "sin código válido"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_invalid_ranking_collection_generates_warning() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"] = {}
    view = build_decision_view(
        response
    )
    assert view.ranking_components == []
    assert any(
        "componentes del ranking no tienen"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_invalid_ranking_component_is_ignored() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"].append(
        "componente inválido"
    )
    view = build_decision_view(
        response
    )
    assert len(
        view.ranking_components
    ) == 2
    assert any(
        "componente del ranking"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_duplicate_ranking_component_is_ignored_case_insensitively() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"].append(
        {
            "name": "valoración",
            "raw_score": 50.0,
            "weight": 0.20,
            "weighted_score": 10.0,
            "available": True,
        }
    )
    view = build_decision_view(
        response
    )
    assert sum(
        component.name.casefold()
        == "valoración"
        for component in view.ranking_components
    ) == 1
    assert any(
        "componente duplicado"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_available_component_without_score_generates_warning() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"][0][
        "raw_score"
    ] = None
    view = build_decision_view(
        response
    )
    assert any(
        "figura disponible"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_ranking_component_score_out_of_range_is_rejected() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"][0][
        "raw_score"
    ] = 150.0
    view = build_decision_view(
        response
    )
    component = _ranking_component_by_name(
        view,
        "Calidad del negocio",
    )
    assert component.score is None
    assert any(
        "raw_score"
        in warning.casefold()
        and "fuera del rango"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_ranking_component_weight_out_of_range_is_rejected() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"][0][
        "weight"
    ] = 1.5
    view = build_decision_view(
        response
    )
    component = _ranking_component_by_name(
        view,
        "Calidad del negocio",
    )
    assert component.weight is None
    assert any(
        "weight"
        in warning.casefold()
        and "fuera del rango"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_incoherent_weighted_score_generates_warning() -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_components"][0][
        "weighted_score"
    ] = 80.0
    view = build_decision_view(
        response
    )
    assert any(
        "no es coherente"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
@pytest.mark.parametrize(
    "invalid_number",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
        True,
        None,
    ],
)
def test_invalid_ranking_score_is_rendered_safely(
    invalid_number: Any,
) -> None:
    response = _success_response()
    response["decision"]["ranking_score"] = (
        invalid_number
    )
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Ranking auxiliar",
        )
        == "No disponible"
    )
@pytest.mark.parametrize(
    "invalid_number",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        "invalid",
        True,
        None,
    ],
)
def test_invalid_ranking_coverage_is_rendered_safely(
    invalid_number: Any,
) -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_coverage"] = invalid_number
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Cobertura del ranking",
        )
        == "No disponible"
    )
@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (
            0,
            "0.0 / 100",
        ),
        (
            55.25,
            "55.2 / 100",
        ),
        (
            100,
            "100.0 / 100",
        ),
    ],
)
def test_valid_ranking_score_is_presented(
    score: float,
    expected: str,
) -> None:
    response = _success_response()
    response["decision"]["ranking_score"] = score
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Ranking auxiliar",
        )
        == expected
    )
@pytest.mark.parametrize(
    "score",
    [
        -10,
        130,
    ],
)
def test_out_of_range_ranking_score_is_rejected(
    score: float,
) -> None:
    response = _success_response()
    response["decision"]["ranking_score"] = score
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Ranking auxiliar",
        )
        == "No disponible"
    )
    assert any(
        "entre 0 y 100"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
@pytest.mark.parametrize(
    "coverage",
    [
        -0.01,
        1.01,
        2.5,
    ],
)
def test_out_of_range_ranking_coverage_is_rejected(
    coverage: float,
) -> None:
    response = _success_response()
    response["decision"][
        "raw_components"
    ]["ranking_coverage"] = coverage
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Cobertura del ranking",
        )
        == "No disponible"
    )
    assert any(
        "rango permitido de 0 a 1"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
@pytest.mark.parametrize(
    ("source_count", "expected"),
    [
        (
            0,
            "0",
        ),
        (
            4,
            "4",
        ),
        (
            4.0,
            "4",
        ),
        (
            -1,
            "No disponible",
        ),
        (
            4.5,
            "No disponible",
        ),
        (
            True,
            "No disponible",
        ),
        (
            "4",
            "4",
        ),
        (
            "invalid",
            "No disponible",
        ),
    ],
)
def test_source_count_is_formatted_safely(
    source_count: Any,
    expected: str,
) -> None:
    response = _success_response()
    response["metadata"][
        "source_count"
    ] = source_count
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Fuentes utilizadas",
        )
        == expected
    )
def test_missing_metadata_uses_safe_defaults() -> None:
    response = _success_response()
    response.pop(
        "metadata"
    )
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Fuentes utilizadas",
        )
        == "No disponible"
    )
    assert (
        _metric_value(
            view,
            "Calidad de datos",
        )
        == "No disponible"
    )
def test_invalid_metadata_mapping_generates_warning() -> None:
    response = _success_response()
    response["metadata"] = "invalid"
    view = build_decision_view(
        response
    )
    assert (
        _metric_value(
            view,
            "Fuentes utilizadas",
        )
        == "No disponible"
    )
    assert any(
        "campo metadata"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_invalid_raw_components_mapping_generates_warning() -> None:
    response = _success_response()
    response["decision"]["raw_components"] = (
        "invalid"
    )
    view = build_decision_view(
        response
    )
    assert view.ranking_components == []
    assert any(
        "campo raw_components"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_missing_schema_version_generates_warning() -> None:
    response = _success_response()
    response.pop(
        "schema_version"
    )
    view = build_decision_view(
        response
    )
    assert any(
        "no informa de la versión"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_incompatible_schema_major_generates_warning() -> None:
    response = _success_response()
    response["schema_version"] = "2.0.0"
    view = build_decision_view(
        response
    )
    assert any(
        "puede no ser compatible"
        in warning.casefold()
        for warning in view.presentation_warnings
    )
def test_presenter_does_not_share_success_raw_response_reference() -> None:
    response = _success_response()
    original = deepcopy(
        response
    )
    view = build_decision_view(
        response
    )
    response["ticker"] = "CHANGED"
    response["decision"]["thesis"].clear()
    response["metadata"]["source_count"] = 999
    assert view.raw_response == original
    assert view.raw_response is not response
    assert (
        view.raw_response["decision"]
        is not response["decision"]
    )
def test_presenter_does_not_share_error_raw_response_reference() -> None:
    response = _error_response()
    original = deepcopy(
        response
    )
    view = build_decision_view(
        response
    )
    response["error"]["message"] = "MODIFICADO"
    assert view.raw_response == original
    assert view.raw_response is not response
def test_view_dictionary_is_json_serializable() -> None:
    result = build_decision_view_dict(
        _success_response()
    )
    serialized = json.dumps(
        result,
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert result["success"] is True
    assert result["ticker"] == "TEST"
    assert (
        result["schema_version"]
        == PRESENTER_SCHEMA_VERSION
    )
def test_error_view_dictionary_is_json_serializable() -> None:
    result = build_decision_view_dict(
        _error_response()
    )
    serialized = json.dumps(
        result,
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert result["success"] is False
    assert result["error_type"] == (
        "INVALID_INPUT"
    )
def test_view_dictionary_is_independent_from_view_dataclass() -> None:
    response = _success_response()
    view = build_decision_view(
        response
    )
    result = view.to_dict()
    result["raw_response"]["ticker"] = (
        "CHANGED"
    )
    assert view.raw_response["ticker"] == "TEST"
@pytest.mark.parametrize(
    ("action", "expected_tone"),
    [
        (
            "COMPRA CLARA",
            "positive",
        ),
        (
            "COMPRAR",
            "positive",
        ),
        (
            "COMPRA PARCIAL",
            "warning",
        ),
        (
            "ESPERAR",
            "warning",
        ),
        (
            "REQUIERE ANÁLISIS MAESTRO",
            "warning",
        ),
        (
            "DESCARTAR",
            "negative",
        ),
        (
            "DATOS NO FIABLES",
            "negative",
        ),
        (
            "DESCONOCIDO",
            "neutral",
        ),
    ],
)
def test_new_investor_action_tones(
    action: str,
    expected_tone: str,
) -> None:
    response = _success_response()
    response["decision"][
        "new_investor_action"
    ] = action
    view = build_decision_view(
        response
    )
    assert view.new_investor_badge is not None
    assert (
        view.new_investor_badge.tone
        == expected_tone
    )
@pytest.mark.parametrize(
    ("action", "expected_tone"),
    [
        (
            "AUMENTAR",
            "positive",
        ),
        (
            "MANTENER",
            "neutral",
        ),
        (
            "REVISAR TESIS",
            "warning",
        ),
        (
            "REDUCIR",
            "warning",
        ),
        (
            "SALIR",
            "negative",
        ),
        (
            "DATOS NO FIABLES",
            "negative",
        ),
        (
            "DESCONOCIDO",
            "neutral",
        ),
    ],
)
def test_existing_holder_action_tones(
    action: str,
    expected_tone: str,
) -> None:
    response = _success_response()
    response["decision"][
        "existing_holder_action"
    ] = action
    view = build_decision_view(
        response
    )
    assert view.existing_holder_badge is not None
    assert (
        view.existing_holder_badge.tone
        == expected_tone
    )
@pytest.mark.parametrize(
    ("confidence", "expected_tone"),
    [
        (
            "ALTA",
            "positive",
        ),
        (
            "MEDIA",
            "neutral",
        ),
        (
            "BAJA",
            "warning",
        ),
        (
            "NO EVALUABLE",
            "negative",
        ),
        (
            "DESCONOCIDA",
            "neutral",
        ),
    ],
)
def test_confidence_tones(
    confidence: str,
    expected_tone: str,
) -> None:
    response = _success_response()
    response["decision"]["confidence"] = (
        confidence
    )
    view = build_decision_view(
        response
    )
    assert view.confidence_badge is not None
    assert (
        view.confidence_badge.tone
        == expected_tone
    )
@pytest.mark.parametrize(
    ("risk", "expected_tone"),
    [
        (
            "BAJO",
            "positive",
        ),
        (
            "MEDIO",
            "warning",
        ),
        (
            "ALTO",
            "negative",
        ),
        (
            "CRÍTICO",
            "negative",
        ),
        (
            "NO EVALUADO",
            "neutral",
        ),
    ],
)
def test_risk_tones(
    risk: str,
    expected_tone: str,
) -> None:
    response = _success_response()
    response["decision"]["risk_level"] = risk
    view = build_decision_view(
        response
    )
    assert view.risk_badge is not None
    assert view.risk_badge.tone == expected_tone
@pytest.mark.parametrize(
    ("valuation", "expected_tone"),
    [
        (
            "INFRAVALORADA",
            "positive",
        ),
        (
            "MUY ATRACTIVA",
            "positive",
        ),
        (
            "ATRACTIVA",
            "positive",
        ),
        (
            "VALORACIÓN RAZONABLE",
            "neutral",
        ),
        (
            "RAZONABLE",
            "neutral",
        ),
        (
            "EXIGENTE",
            "warning",
        ),
        (
            "SOBREVALORADA",
            "warning",
        ),
        (
            "MUY EXIGENTE",
            "warning",
        ),
        (
            "NO EVALUADA",
            "neutral",
        ),
    ],
)
def test_valuation_tones(
    valuation: str,
    expected_tone: str,
) -> None:
    response = _success_response()
    response["decision"][
        "valuation_status"
    ] = valuation
    view = build_decision_view(
        response
    )
    assert view.valuation_badge is not None
    assert (
        view.valuation_badge.tone
        == expected_tone
    )
@pytest.mark.parametrize(
    ("moat", "expected_tone"),
    [
        (
            "FUERTE",
            "positive",
        ),
        (
            "MODERADO",
            "neutral",
        ),
        (
            "DÉBIL",
            "negative",
        ),
        (
            "NO EVALUADO",
            "neutral",
        ),
    ],
)
def test_moat_tones(
    moat: str,
    expected_tone: str,
) -> None:
    response = _success_response()
    response["decision"][
        "moat_strength"
    ] = moat
    view = build_decision_view(
        response
    )
    assert view.moat_badge is not None
    assert view.moat_badge.tone == expected_tone
def test_text_fields_are_trimmed() -> None:
    response = _success_response()
    response["ticker"] = "  TEST  "
    response["company_name"] = "  Test Company  "
    response["decision"][
        "new_investor_action"
    ] = "  COMPRAR  "
    view = build_decision_view(
        response
    )
    assert view.ticker == "TEST"
    assert view.company_name == "Test Company"
    assert view.new_investor_badge is not None
    assert (
        view.new_investor_badge.value
        == "COMPRAR"
    )
def test_internal_whitespace_is_normalized() -> None:
    response = _success_response()
    response["company_name"] = (
        "Test   Company\nInternational"
    )
    view = build_decision_view(
        response
    )
    assert (
        view.company_name
        == "Test Company International"
    )
def test_bytes_are_not_presented_as_text() -> None:
    response = _success_response()
    response["decision"]["warnings"] = [
        b"contenido binario",
        "Advertencia válida.",
    ]
    view = build_decision_view(
        response
    )
    assert view.warnings is not None
    assert view.warnings.items == [
        "Advertencia válida.",
    ]
def test_excessively_long_company_name_is_truncated() -> None:
    response = _success_response()
    response["company_name"] = "A" * 300
    view = build_decision_view(
        response
    )
    assert view.company_name is not None
    assert len(view.company_name) == 250
    assert view.company_name.endswith("…")
def test_excessively_long_section_item_is_truncated() -> None:
    response = _success_response()
    response["decision"]["warnings"] = [
        "A" * 3_000
    ]
    view = build_decision_view(
        response
    )
    assert view.warnings is not None
    assert len(view.warnings.items) == 1
    assert len(view.warnings.items[0]) == 2_000
    assert view.warnings.items[0].endswith("…")
class _UncopyableValue:
    def __deepcopy__(
        self,
        memo: dict[int, Any],
    ) -> Any:
        raise RuntimeError(
            "No se puede copiar."
        )
def test_uncopyable_response_content_raises_presenter_error() -> None:
    response = _success_response()
    response["uncopyable"] = (
        _UncopyableValue()
    )
    with pytest.raises(
        DecisionPresenterError,
        match="copia segura",
    ):
        build_decision_view(
            response
        )
