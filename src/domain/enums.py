from __future__ import annotations

from enum import Enum


class EligibilityStatus(str, Enum):
    """
    Indica si existen datos suficientes y fiables para que
    una empresa pueda clasificarse dentro del radar.

    No expresa atractivo financiero. Solo expresa si la
    clasificación es metodológicamente válida.
    """

    ELIGIBLE = "ELEGIBLE"
    LIMITED = "ELEGIBILIDAD LIMITADA"
    BLOCKED = "BLOQUEADA"
    UNRELIABLE = "DATOS NO FIABLES"
    NOT_EVALUATED = "NO EVALUADA"


class IssueSeverity(str, Enum):
    """
    Severidad técnica o metodológica de una incidencia.
    """

    INFO = "INFORMATIVO"
    WARNING = "ADVERTENCIA"
    ERROR = "ERROR"
    CRITICAL = "CRÍTICO"


class IssueCategory(str, Enum):
    """
    Categoría estable de una incidencia de datos, modelo
    o ejecución.
    """

    TRANSPORT = "TRANSPORTE"
    MISSING_DATA = "DATO AUSENTE"
    INVALID_DATA = "DATO INVÁLIDO"
    STALE_DATA = "DATO DESACTUALIZADO"
    SOURCE_CONFLICT = "CONFLICTO DE FUENTES"
    ACCOUNTING_INCONSISTENCY = "INCONSISTENCIA CONTABLE"
    MODEL_CONTRACT = "CONTRATO DEL MODELO"
    SERIALIZATION = "SERIALIZACIÓN"
    PERSISTENCE = "PERSISTENCIA"
    EXPORT = "EXPORTACIÓN"
    CONFIGURATION = "CONFIGURACIÓN"
    UNKNOWN = "DESCONOCIDO"


class RunStatus(str, Enum):
    """
    Estado de una ejecución de screener, análisis o exportación.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComparabilityStatus(str, Enum):
    """
    Indica si dos resultados históricos pueden compararse
    metodológicamente.
    """

    COMPARABLE = "COMPARABLE"
    PARTIALLY_COMPARABLE = "PARCIALMENTE COMPARABLE"
    NOT_COMPARABLE = "NO COMPARABLE"
    NOT_EVALUATED = "NO EVALUADA"
