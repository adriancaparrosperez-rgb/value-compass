from __future__ import annotations

from enum import Enum

from src.domain import (
    ComparabilityStatus,
    EligibilityStatus,
    IssueCategory,
    IssueSeverity,
    RunStatus,
)


def test_domain_enums_are_string_enums() -> None:
    enum_values = [
        EligibilityStatus.ELIGIBLE,
        IssueSeverity.WARNING,
        IssueCategory.MISSING_DATA,
        RunStatus.RUNNING,
        ComparabilityStatus.COMPARABLE,
    ]

    assert all(
        isinstance(value, str)
        for value in enum_values
    )

    assert all(
        isinstance(value, Enum)
        for value in enum_values
    )


def test_eligibility_status_separates_data_quality_from_radar_signal() -> None:
    assert EligibilityStatus.ELIGIBLE.value == "ELEGIBLE"
    assert (
        EligibilityStatus.UNRELIABLE.value
        == "DATOS NO FIABLES"
    )
    assert (
        EligibilityStatus.NOT_EVALUATED.value
        == "NO EVALUADA"
    )


def test_issue_categories_cover_data_and_operational_failures() -> None:
    assert (
        IssueCategory.MISSING_DATA.value
        == "DATO AUSENTE"
    )
    assert (
        IssueCategory.SOURCE_CONFLICT.value
        == "CONFLICTO DE FUENTES"
    )
    assert (
        IssueCategory.PERSISTENCE.value
        == "PERSISTENCIA"
    )
    assert (
        IssueCategory.EXPORT.value
        == "EXPORTACIÓN"
    )


def test_run_status_values_match_operational_persistence_values() -> None:
    assert RunStatus.PENDING.value == "pending"
    assert RunStatus.RUNNING.value == "running"
    assert RunStatus.COMPLETED.value == "completed"
    assert RunStatus.PARTIAL.value == "partial"
    assert RunStatus.FAILED.value == "failed"
    assert RunStatus.CANCELLED.value == "cancelled"


def test_comparability_status_distinguishes_partial_compatibility() -> None:
    assert (
        ComparabilityStatus.COMPARABLE.value
        == "COMPARABLE"
    )
    assert (
        ComparabilityStatus.PARTIALLY_COMPARABLE.value
        == "PARCIALMENTE COMPARABLE"
    )
    assert (
        ComparabilityStatus.NOT_COMPARABLE.value
        == "NO COMPARABLE"
    )


def test_enum_values_are_stable_for_serialization() -> None:
    payload = {
        "eligibility": EligibilityStatus.BLOCKED.value,
        "severity": IssueSeverity.CRITICAL.value,
        "category": IssueCategory.MODEL_CONTRACT.value,
        "status": RunStatus.FAILED.value,
        "comparability": (
            ComparabilityStatus.NOT_COMPARABLE.value
        ),
    }

    assert payload == {
        "eligibility": "BLOQUEADA",
        "severity": "CRÍTICO",
        "category": "CONTRATO DEL MODELO",
        "status": "failed",
        "comparability": "NO COMPARABLE",
    }
