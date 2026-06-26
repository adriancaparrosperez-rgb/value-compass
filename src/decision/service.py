from __future__ import annotations
import logging
from copy import deepcopy
from typing import Any
from src.decision.engine import make_master_decision
from src.decision.models import (
    MasterAnalysisInput,
    MasterDecisionResult,
    SourceReference,
)
SERVICE_SCHEMA_VERSION = "1.0.0"
SERVICE_NAME = "master-decision-service"
logger = logging.getLogger(__name__)
class DecisionInputError(ValueError):
    """Error controlado de validación de la entrada."""
class DecisionServiceError(RuntimeError):
    """Error interno controlado de la capa de servicio."""
def _normalize_ticker(
    ticker: Any,
) -> str:
    if not isinstance(ticker, str):
        raise DecisionInputError(
            "El ticker debe ser una cadena de texto."
        )
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise DecisionInputError(
            "El ticker no puede estar vacío."
        )
    if len(normalized_ticker) > 30:
        raise DecisionInputError(
            "El ticker no puede superar 30 caracteres."
        )
    if any(
        character.isspace()
        for character in normalized_ticker
    ):
        raise DecisionInputError(
            "El ticker no puede contener espacios."
        )
    return normalized_ticker
def _normalize_company_name(
    company_name: Any,
) -> str | None:
    if company_name is None:
        return None
    if not isinstance(company_name, str):
        raise DecisionInputError(
            "El nombre de la empresa debe ser texto."
        )
    normalized_name = company_name.strip()
    if not normalized_name:
        return None
    if len(normalized_name) > 250:
        raise DecisionInputError(
            "El nombre de la empresa no puede superar "
            "250 caracteres."
        )
    return normalized_name
def _normalize_model_version(
    model_version: Any,
) -> str:
    if not isinstance(model_version, str):
        raise DecisionInputError(
            "La versión del modelo debe ser texto."
        )
    normalized_version = model_version.strip()
    if not normalized_version:
        raise DecisionInputError(
            "La versión del modelo no puede estar vacía."
        )
    if len(normalized_version) > 50:
        raise DecisionInputError(
            "La versión del modelo no puede superar "
            "50 caracteres."
        )
    return normalized_version
def _validate_sources(
    sources: Any,
) -> None:
    if not isinstance(sources, list):
        raise DecisionInputError(
            "Las fuentes deben proporcionarse como una lista."
        )
    for index, source in enumerate(sources):
        if not isinstance(
            source,
            SourceReference,
        ):
            raise DecisionInputError(
                "Cada fuente debe ser una instancia "
                f"de SourceReference. Elemento inválido: {index}."
            )
        if not isinstance(source.name, str):
            raise DecisionInputError(
                "El nombre de cada fuente debe ser texto."
            )
        if not source.name.strip():
            raise DecisionInputError(
                "El nombre de cada fuente no puede estar vacío."
            )
        if not isinstance(
            source.source_type,
            str,
        ):
            raise DecisionInputError(
                "El tipo de cada fuente debe ser texto."
            )
        if not source.source_type.strip():
            raise DecisionInputError(
                "El tipo de cada fuente no puede estar vacío."
            )
        if (
            source.url is not None
            and not isinstance(source.url, str)
        ):
            raise DecisionInputError(
                "La URL de cada fuente debe ser texto "
                "o un valor nulo."
            )
        if (
            source.published_at is not None
            and not isinstance(
                source.published_at,
                str,
            )
        ):
            raise DecisionInputError(
                "La fecha de publicación de cada fuente "
                "debe ser texto o un valor nulo."
            )
        if (
            source.retrieved_at is not None
            and not isinstance(
                source.retrieved_at,
                str,
            )
        ):
            raise DecisionInputError(
                "La fecha de consulta de cada fuente "
                "debe ser texto o un valor nulo."
            )
        if not isinstance(
            source.is_official,
            bool,
        ):
            raise DecisionInputError(
                "El indicador de fuente oficial "
                "debe ser booleano."
            )
def _validate_analysis(
    analysis: Any,
) -> MasterAnalysisInput:
    if not isinstance(
        analysis,
        MasterAnalysisInput,
    ):
        raise DecisionInputError(
            "La entrada debe ser una instancia "
            "de MasterAnalysisInput."
        )
    _normalize_ticker(
        analysis.ticker
    )
    _normalize_company_name(
        analysis.company_name
    )
    _normalize_model_version(
        analysis.model_version
    )
    _validate_sources(
        analysis.sources
    )
    return analysis
def _prepare_analysis(
    analysis: MasterAnalysisInput,
) -> MasterAnalysisInput:
    """
    Valida, copia y normaliza el análisis.
    La copia defensiva evita modificar el objeto recibido
    desde la interfaz, una tarea automática o un proceso batch.
    """
    validated_analysis = _validate_analysis(
        analysis
    )
    try:
        prepared_analysis = deepcopy(
            validated_analysis
        )
    except Exception as error:
        raise DecisionServiceError(
            "No se pudo preparar una copia segura "
            "del análisis."
        ) from error
    prepared_analysis.ticker = _normalize_ticker(
        prepared_analysis.ticker
    )
    prepared_analysis.company_name = (
        _normalize_company_name(
            prepared_analysis.company_name
        )
    )
    prepared_analysis.model_version = (
        _normalize_model_version(
            prepared_analysis.model_version
        )
    )
    return prepared_analysis
def _run_prepared_analysis(
    prepared_analysis: MasterAnalysisInput,
) -> MasterDecisionResult:
    decision = make_master_decision(
        prepared_analysis
    )
    if not isinstance(
        decision,
        MasterDecisionResult,
    ):
        raise DecisionServiceError(
            "El motor no devolvió un "
            "MasterDecisionResult válido."
        )
    return decision
def run_master_decision(
    analysis: MasterAnalysisInput,
) -> MasterDecisionResult:
    """
    Entrada estricta para procesos internos y tests.
    Devuelve el resultado tipado y propaga los errores para
    que puedan diagnosticarse correctamente.
    """
    prepared_analysis = _prepare_analysis(
        analysis
    )
    return _run_prepared_analysis(
        prepared_analysis
    )
def build_decision_response(
    analysis: MasterAnalysisInput,
) -> dict[str, Any]:
    """
    Ejecuta el motor y construye una respuesta estable
    y serializable para la interfaz o procesos externos.
    """
    prepared_analysis = _prepare_analysis(
        analysis
    )
    decision = _run_prepared_analysis(
        prepared_analysis
    )
    serialized_decision = decision.to_dict()
    if not isinstance(
        serialized_decision,
        dict,
    ):
        raise DecisionServiceError(
            "El resultado serializado del motor "
            "no es un diccionario."
        )
    return {
        "success": True,
        "service": SERVICE_NAME,
        "schema_version": SERVICE_SCHEMA_VERSION,
        "model_version": prepared_analysis.model_version,
        "ticker": prepared_analysis.ticker,
        "company_name": prepared_analysis.company_name,
        "created_at": decision.created_at,
        "decision": serialized_decision,
        "metadata": {
            "source_count": len(
                prepared_analysis.sources
            ),
            "data_quality_status": (
                prepared_analysis
                .data_quality
                .status
                .value
            ),
            "ranking_score": decision.ranking_score,
            "confidence": decision.confidence.value,
            "risk_level": decision.risk_level.value,
            "new_investor_action": (
                decision.new_investor_action.value
            ),
            "existing_holder_action": (
                decision.existing_holder_action.value
            ),
        },
    }
def build_error_response(
    error: Exception,
) -> dict[str, Any]:
    """
    Construye una respuesta de error segura y serializable.
    Los errores de entrada muestran un mensaje concreto.
    Los errores internos no exponen detalles técnicos.
    """
    if isinstance(
        error,
        DecisionInputError,
    ):
        error_type = "INVALID_INPUT"
        message = str(error).strip()
        if not message:
            message = (
                "La entrada proporcionada no es válida."
            )
    elif isinstance(
        error,
        DecisionServiceError,
    ):
        error_type = "SERVICE_ERROR"
        message = (
            "No se pudo completar correctamente "
            "el análisis."
        )
    else:
        error_type = "ANALYSIS_ERROR"
        message = (
            "Se ha producido un error interno durante "
            "el análisis."
        )
    return {
        "success": False,
        "service": SERVICE_NAME,
        "schema_version": SERVICE_SCHEMA_VERSION,
        "error": {
            "type": error_type,
            "message": message,
        },
    }
def execute_master_decision(
    analysis: MasterAnalysisInput,
) -> dict[str, Any]:
    """
    Entrada segura para Streamlit y procesos automatizados.
    Siempre devuelve una estructura serializable con
    success=True o success=False.
    """
    try:
        return build_decision_response(
            analysis
        )
    except DecisionInputError as error:
        return build_error_response(
            error
        )
    except DecisionServiceError as error:
        logger.exception(
            "Error en la capa de servicio de decisión."
        )
        return build_error_response(
            error
        )
    except Exception as error:
        logger.exception(
            "Error inesperado al ejecutar el motor "
            "maestro de decisión."
        )
        return build_error_response(
            error
        )
