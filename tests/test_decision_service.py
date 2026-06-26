from __future__ import annotations
import json
from copy import deepcopy
import pytest
import src.decision.service as service
from src.decision.enums import (
    DataQualityStatus,
    EvidenceConfidence,
    ExistingHolderAction,
    MoatStrength,
    MoatTrend,
    NewInvestorAction,
    RiskLevel,
    ValuationStatus,
)
from src.decision.models import (
    DataQualityAssessment,
    MasterAnalysisInput,
    MasterDecisionResult,
    SourceReference,
)
from src.decision.service import (
    DecisionInputError,
    DecisionServiceError,
    build_decision_response,
    build_error_response,
    execute_master_decision,
    run_master_decision,
)
def _analysis() -> MasterAnalysisInput:
    return MasterAnalysisInput(
        ticker=" test ",
        company_name=" Test Company ",
        data_quality=DataQualityAssessment(
            status=DataQualityStatus.VALIDATED,
            coverage_score=90.0,
            freshness_score=90.0,
            consistency_score=90.0,
            source_quality_score=90.0,
        ),
        sources=[
            SourceReference(
                name="Informe anual",
                source_type="official_filing",
                url="https://example.com/report",
                published_at="2026-01-01",
                retrieved_at="2026-06-26",
                is_official=True,
            )
        ],
        model_version=" 0.1.0 ",
    )
def _decision(
    ticker: str = "TEST",
) -> MasterDecisionResult:
    return MasterDecisionResult(
        ticker=ticker,
        new_investor_action=NewInvestorAction.BUY,
        existing_holder_action=ExistingHolderAction.HOLD,
        confidence=EvidenceConfidence.HIGH,
        risk_level=RiskLevel.LOW,
        company_quality="ALTA",
        valuation_status=ValuationStatus.ATTRACTIVE,
        moat_strength=MoatStrength.STRONG,
        moat_trend=MoatTrend.STABLE,
        ranking_score=82.5,
        model_version="0.1.0",
    )
def _patch_valid_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_make_master_decision(
        analysis: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        return _decision(
            ticker=analysis.ticker
        )
    monkeypatch.setattr(
        service,
        "make_master_decision",
        fake_make_master_decision,
    )
def test_run_master_decision_normalizes_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    received_analysis: (
        MasterAnalysisInput | None
    ) = None
    def fake_make_master_decision(
        prepared: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        nonlocal received_analysis
        received_analysis = prepared
        return _decision(
            ticker=prepared.ticker
        )
    monkeypatch.setattr(
        service,
        "make_master_decision",
        fake_make_master_decision,
    )
    result = run_master_decision(
        analysis
    )
    assert result.ticker == "TEST"
    assert received_analysis is not None
    assert received_analysis.ticker == "TEST"
    assert (
        received_analysis.company_name
        == "Test Company"
    )
    assert (
        received_analysis.model_version
        == "0.1.0"
    )
def test_service_does_not_modify_original_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    original = deepcopy(
        analysis
    )
    _patch_valid_decision(
        monkeypatch
    )
    run_master_decision(
        analysis
    )
    assert analysis.ticker == original.ticker
    assert (
        analysis.company_name
        == original.company_name
    )
    assert (
        analysis.model_version
        == original.model_version
    )
    assert analysis.sources == original.sources
def test_build_decision_response_returns_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    _patch_valid_decision(
        monkeypatch
    )
    response = build_decision_response(
        analysis
    )
    assert response["success"] is True
    assert (
        response["service"]
        == service.SERVICE_NAME
    )
    assert (
        response["schema_version"]
        == service.SERVICE_SCHEMA_VERSION
    )
    assert response["ticker"] == "TEST"
    assert (
        response["company_name"]
        == "Test Company"
    )
    assert response["model_version"] == "0.1.0"
    assert isinstance(
        response["decision"],
        dict,
    )
    assert isinstance(
        response["metadata"],
        dict,
    )
    assert (
        response["metadata"]["source_count"]
        == 1
    )
    assert (
        response["metadata"][
            "data_quality_status"
        ]
        == DataQualityStatus.VALIDATED.value
    )
    assert (
        response["metadata"]["ranking_score"]
        == 82.5
    )
    assert (
        response["metadata"]["confidence"]
        == EvidenceConfidence.HIGH.value
    )
    assert (
        response["metadata"]["risk_level"]
        == RiskLevel.LOW.value
    )
    assert (
        response["metadata"][
            "new_investor_action"
        ]
        == NewInvestorAction.BUY.value
    )
    assert (
        response["metadata"][
            "existing_holder_action"
        ]
        == ExistingHolderAction.HOLD.value
    )
def test_decision_response_is_json_serializable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    _patch_valid_decision(
        monkeypatch
    )
    response = build_decision_response(
        analysis
    )
    serialized = json.dumps(
        response,
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
    assert "TEST" in serialized
@pytest.mark.parametrize(
    ("ticker", "message"),
    [
        (
            "",
            "ticker no puede estar vacío",
        ),
        (
            "   ",
            "ticker no puede estar vacío",
        ),
        (
            "BRK B",
            "ticker no puede contener espacios",
        ),
        (
            "A" * 31,
            "ticker no puede superar 30",
        ),
    ],
)
def test_invalid_ticker_raises_input_error(
    ticker: str,
    message: str,
) -> None:
    analysis = _analysis()
    analysis.ticker = ticker
    with pytest.raises(
        DecisionInputError,
        match=message,
    ):
        run_master_decision(
            analysis
        )
def test_non_string_ticker_raises_input_error() -> None:
    analysis = _analysis()
    analysis.ticker = 123  # type: ignore[assignment]
    with pytest.raises(
        DecisionInputError,
        match="ticker debe ser una cadena",
    ):
        run_master_decision(
            analysis
        )
def test_empty_company_name_becomes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    analysis.company_name = "   "
    received_name: str | None = "initial"
    def fake_make_master_decision(
        prepared: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        nonlocal received_name
        received_name = prepared.company_name
        return _decision(
            ticker=prepared.ticker
        )
    monkeypatch.setattr(
        service,
        "make_master_decision",
        fake_make_master_decision,
    )
    run_master_decision(
        analysis
    )
    assert received_name is None
def test_invalid_company_name_type_raises_error() -> None:
    analysis = _analysis()
    analysis.company_name = 123  # type: ignore[assignment]
    with pytest.raises(
        DecisionInputError,
        match="nombre de la empresa debe ser texto",
    ):
        run_master_decision(
            analysis
        )
def test_company_name_length_is_limited() -> None:
    analysis = _analysis()
    analysis.company_name = "A" * 251
    with pytest.raises(
        DecisionInputError,
        match="no puede superar 250",
    ):
        run_master_decision(
            analysis
        )
def test_empty_model_version_raises_error() -> None:
    analysis = _analysis()
    analysis.model_version = "   "
    with pytest.raises(
        DecisionInputError,
        match="versión del modelo no puede estar vacía",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_model_version_type_raises_error() -> None:
    analysis = _analysis()
    analysis.model_version = 1  # type: ignore[assignment]
    with pytest.raises(
        DecisionInputError,
        match="versión del modelo debe ser texto",
    ):
        run_master_decision(
            analysis
        )
def test_model_version_length_is_limited() -> None:
    analysis = _analysis()
    analysis.model_version = "1" * 51
    with pytest.raises(
        DecisionInputError,
        match="no puede superar 50",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_sources_type_raises_error() -> None:
    analysis = _analysis()
    analysis.sources = {}  # type: ignore[assignment]
    with pytest.raises(
        DecisionInputError,
        match="fuentes deben proporcionarse como una lista",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_source_item_raises_error() -> None:
    analysis = _analysis()
    analysis.sources = [
        "fuente inválida"
    ]  # type: ignore[list-item]
    with pytest.raises(
        DecisionInputError,
        match="SourceReference",
    ):
        run_master_decision(
            analysis
        )
def test_empty_source_name_raises_error() -> None:
    analysis = _analysis()
    analysis.sources = [
        SourceReference(
            name="   ",
            source_type="official_filing",
        )
    ]
    with pytest.raises(
        DecisionInputError,
        match="nombre de cada fuente no puede estar vacío",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_source_name_type_raises_error() -> None:
    analysis = _analysis()
    source = SourceReference(
        name="Informe anual",
        source_type="official_filing",
    )
    source.name = 123  # type: ignore[assignment]
    analysis.sources = [source]
    with pytest.raises(
        DecisionInputError,
        match="nombre de cada fuente debe ser texto",
    ):
        run_master_decision(
            analysis
        )
def test_empty_source_type_raises_error() -> None:
    analysis = _analysis()
    analysis.sources = [
        SourceReference(
            name="Informe anual",
            source_type="   ",
        )
    ]
    with pytest.raises(
        DecisionInputError,
        match="tipo de cada fuente no puede estar vacío",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_source_type_type_raises_error() -> None:
    analysis = _analysis()
    source = SourceReference(
        name="Informe anual",
        source_type="official_filing",
    )
    source.source_type = 123  # type: ignore[assignment]
    analysis.sources = [source]
    with pytest.raises(
        DecisionInputError,
        match="tipo de cada fuente debe ser texto",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_source_url_type_raises_error() -> None:
    analysis = _analysis()
    source = SourceReference(
        name="Informe anual",
        source_type="official_filing",
    )
    source.url = 123  # type: ignore[assignment]
    analysis.sources = [source]
    with pytest.raises(
        DecisionInputError,
        match="URL de cada fuente debe ser texto",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_source_published_at_type_raises_error() -> None:
    analysis = _analysis()
    source = SourceReference(
        name="Informe anual",
        source_type="official_filing",
    )
    source.published_at = 123  # type: ignore[assignment]
    analysis.sources = [source]
    with pytest.raises(
        DecisionInputError,
        match="fecha de publicación",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_source_retrieved_at_type_raises_error() -> None:
    analysis = _analysis()
    source = SourceReference(
        name="Informe anual",
        source_type="official_filing",
    )
    source.retrieved_at = 123  # type: ignore[assignment]
    analysis.sources = [source]
    with pytest.raises(
        DecisionInputError,
        match="fecha de consulta",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_source_official_flag_raises_error() -> None:
    analysis = _analysis()
    source = SourceReference(
        name="Informe anual",
        source_type="official_filing",
    )
    source.is_official = 1  # type: ignore[assignment]
    analysis.sources = [source]
    with pytest.raises(
        DecisionInputError,
        match="fuente oficial",
    ):
        run_master_decision(
            analysis
        )
def test_invalid_analysis_type_raises_error() -> None:
    with pytest.raises(
        DecisionInputError,
        match="MasterAnalysisInput",
    ):
        run_master_decision(
            {"ticker": "TEST"}  # type: ignore[arg-type]
        )
def test_invalid_input_does_not_call_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    analysis.ticker = ""
    engine_called = False
    def fake_make_master_decision(
        prepared: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        nonlocal engine_called
        engine_called = True
        return _decision(
            ticker=prepared.ticker
        )
    monkeypatch.setattr(
        service,
        "make_master_decision",
        fake_make_master_decision,
    )
    response = execute_master_decision(
        analysis
    )
    assert response["success"] is False
    assert engine_called is False
def test_engine_must_return_decision_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    monkeypatch.setattr(
        service,
        "make_master_decision",
        lambda prepared: {
            "ticker": prepared.ticker
        },
    )
    with pytest.raises(
        DecisionServiceError,
        match="MasterDecisionResult válido",
    ):
        run_master_decision(
            analysis
        )
def test_execute_returns_invalid_input_response() -> None:
    analysis = _analysis()
    analysis.ticker = ""
    response = execute_master_decision(
        analysis
    )
    assert response["success"] is False
    assert (
        response["error"]["type"]
        == "INVALID_INPUT"
    )
    assert "ticker" in (
        response["error"]["message"].lower()
    )
def test_execute_hides_internal_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    def raise_internal_error(
        prepared: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        raise RuntimeError(
            "SECRETO_INTERNO"
        )
    monkeypatch.setattr(
        service,
        "make_master_decision",
        raise_internal_error,
    )
    response = execute_master_decision(
        analysis
    )
    assert response["success"] is False
    assert (
        response["error"]["type"]
        == "ANALYSIS_ERROR"
    )
    assert "SECRETO_INTERNO" not in (
        response["error"]["message"]
    )
def test_execute_handles_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    monkeypatch.setattr(
        service,
        "make_master_decision",
        lambda prepared: None,
    )
    response = execute_master_decision(
        analysis
    )
    assert response["success"] is False
    assert (
        response["error"]["type"]
        == "SERVICE_ERROR"
    )
    assert (
        response["error"]["message"]
        == (
            "No se pudo completar correctamente "
            "el análisis."
        )
    )
def test_build_error_response_for_input_error() -> None:
    response = build_error_response(
        DecisionInputError(
            "Entrada incorrecta."
        )
    )
    assert response["success"] is False
    assert (
        response["error"]["type"]
        == "INVALID_INPUT"
    )
    assert (
        response["error"]["message"]
        == "Entrada incorrecta."
    )
def test_build_error_response_for_service_error() -> None:
    response = build_error_response(
        DecisionServiceError(
            "Detalle técnico."
        )
    )
    assert response["success"] is False
    assert (
        response["error"]["type"]
        == "SERVICE_ERROR"
    )
    assert "Detalle técnico" not in (
        response["error"]["message"]
    )
def test_build_error_response_for_unknown_error() -> None:
    response = build_error_response(
        RuntimeError(
            "Información interna."
        )
    )
    assert response["success"] is False
    assert (
        response["error"]["type"]
        == "ANALYSIS_ERROR"
    )
    assert "Información interna" not in (
        response["error"]["message"]
    )
def test_error_response_is_json_serializable() -> None:
    response = build_error_response(
        DecisionInputError(
            "Entrada incorrecta."
        )
    )
    serialized = json.dumps(
        response,
        ensure_ascii=False,
    )
    assert isinstance(
        serialized,
        str,
    )
def test_run_master_decision_propagates_engine_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    def raise_engine_error(
        prepared: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        raise RuntimeError(
            "Fallo controlado de prueba."
        )
    monkeypatch.setattr(
        service,
        "make_master_decision",
        raise_engine_error,
    )
    with pytest.raises(
        RuntimeError,
        match="Fallo controlado de prueba",
    ):
        run_master_decision(
            analysis
        )
def test_success_response_uses_normalized_ticker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    analysis.ticker = "  brk.b  "
    _patch_valid_decision(
        monkeypatch
    )
    response = execute_master_decision(
        analysis
    )
    assert response["success"] is True
    assert response["ticker"] == "BRK.B"
    assert (
        response["decision"]["ticker"]
        == "BRK.B"
    )
def test_original_sources_are_not_modified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis = _analysis()
    original_sources = deepcopy(
        analysis.sources
    )
    def mutate_prepared_analysis(
        prepared: MasterAnalysisInput,
    ) -> MasterDecisionResult:
        prepared.sources.clear()
        return _decision(
            ticker=prepared.ticker
        )
    monkeypatch.setattr(
        service,
        "make_master_decision",
        mutate_prepared_analysis,
    )
    run_master_decision(
        analysis
    )
    assert analysis.sources == original_sources
    assert len(analysis.sources) == 1
