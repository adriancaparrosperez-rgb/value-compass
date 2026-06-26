from __future__ import annotations
from src.decision.enums import (
    DataQualityStatus,
    GateSeverity,
    MoatStrength,
    MoatTrend,
)
from src.decision.models import (
    GateResult,
    MasterAnalysisInput,
)
def _add_gate(
    gates: list[GateResult],
    code: str,
    passed: bool,
    severity: GateSeverity,
    message: str,
) -> None:
    gates.append(
        GateResult(
            code=code,
            passed=passed,
            severity=severity,
            message=message,
        )
    )
def evaluate_master_gates(
    analysis: MasterAnalysisInput,
) -> list[GateResult]:
    """
    Evalúa controles previos a la decisión de inversión.
    Los gates no calculan la recomendación final. Determinan
    si existen carencias o riesgos que bloquean determinadas
    recomendaciones.
    """
    gates: list[GateResult] = []
    data_quality = analysis.data_quality
    moat = analysis.moat
    accounting = analysis.accounting
    valuation = analysis.valuation
    business = analysis.business
    # =========================================================
    # 1. CALIDAD Y VALIDACIÓN DEL DATO
    # =========================================================
    _add_gate(
        gates=gates,
        code="PRICE_VALIDATED",
        passed=data_quality.price_validated,
        severity=GateSeverity.BLOCKING,
        message=(
            "La cotización debe estar validada y actualizada."
        ),
    )
    _add_gate(
        gates=gates,
        code="CURRENCY_VALIDATED",
        passed=data_quality.currency_validated,
        severity=GateSeverity.BLOCKING,
        message=(
            "La moneda de cotización debe estar validada."
        ),
    )
    _add_gate(
        gates=gates,
        code="TICKER_VALIDATED",
        passed=data_quality.ticker_validated,
        severity=GateSeverity.BLOCKING,
        message=(
            "El ticker debe corresponder a la empresa analizada."
        ),
    )
    _add_gate(
        gates=gates,
        code="FUNDAMENTALS_VALIDATED",
        passed=data_quality.fundamentals_validated,
        severity=GateSeverity.BLOCKING,
        message=(
            "Los fundamentales deben estar actualizados "
            "y contrastados."
        ),
    )
    _add_gate(
        gates=gates,
        code="DATA_NOT_UNRELIABLE",
        passed=(
            data_quality.status
            != DataQualityStatus.UNRELIABLE
        ),
        severity=GateSeverity.BLOCKING,
        message=(
            "La calidad global del dato no puede ser "
            "clasificada como no fiable."
        ),
    )
    _add_gate(
        gates=gates,
        code="DATA_COVERAGE_MINIMUM",
        passed=data_quality.coverage_score >= 55.0,
        severity=GateSeverity.BLOCKING,
        message=(
            "La cobertura de datos críticos debe ser "
            "igual o superior al 55 %."
        ),
    )
    _add_gate(
        gates=gates,
        code="DATA_COVERAGE_STRONG",
        passed=data_quality.coverage_score >= 75.0,
        severity=GateSeverity.WARNING,
        message=(
            "Para una recomendación fuerte se recomienda "
            "una cobertura mínima del 75 %."
        ),
    )
    _add_gate(
        gates=gates,
        code="MULTIPLE_SOURCES",
        passed=data_quality.source_count >= 2,
        severity=GateSeverity.WARNING,
        message=(
            "Los datos principales deberían contrastarse "
            "en al menos dos fuentes."
        ),
    )
    _add_gate(
        gates=gates,
        code="OFFICIAL_SOURCE_AVAILABLE",
        passed=data_quality.official_source_count >= 1,
        severity=GateSeverity.WARNING,
        message=(
            "Debe existir al menos una fuente oficial "
            "para validar los fundamentales."
        ),
    )
    _add_gate(
        gates=gates,
        code="MARKET_CAP_CONSISTENT",
        passed=data_quality.market_cap_validated,
        severity=GateSeverity.WARNING,
        message=(
            "La capitalización debería ser coherente con "
            "el precio y las acciones diluidas."
        ),
    )
    # =========================================================
    # 2. MOAT Y RIESGO DE DISRUPCIÓN
    # =========================================================
    moat_reviewed = (
        moat.strength != MoatStrength.NOT_EVALUATED
        and moat.trend != MoatTrend.NOT_EVALUATED
        and moat.reviewed_score is not None
    )
    _add_gate(
        gates=gates,
        code="MOAT_REVIEWED",
        passed=moat_reviewed,
        severity=GateSeverity.BLOCKING,
        message=(
            "El moat debe haber sido revisado antes de "
            "emitir una recomendación definitiva."
        ),
    )
    moat_not_collapsing = (
        moat.trend
        != MoatTrend.RAPIDLY_DETERIORATING
    )
    _add_gate(
        gates=gates,
        code="MOAT_NOT_COLLAPSING",
        passed=moat_not_collapsing,
        severity=GateSeverity.BLOCKING,
        message=(
            "Un deterioro rápido del moat bloquea las "
            "recomendaciones de compra."
        ),
    )
    disruption_risk = moat.disruption_risk_score
    _add_gate(
        gates=gates,
        code="DISRUPTION_RISK_ACCEPTABLE",
        passed=(
            disruption_risk is not None
            and disruption_risk <= 70.0
        ),
        severity=GateSeverity.WARNING,
        message=(
            "El riesgo de disrupción debe estar evaluado "
            "y mantenerse en niveles asumibles."
        ),
    )
    _add_gate(
        gates=gates,
        code="DISRUPTION_RISK_NOT_CRITICAL",
        passed=(
            disruption_risk is None
            or disruption_risk < 85.0
        ),
        severity=GateSeverity.BLOCKING,
        message=(
            "Un riesgo de disrupción crítico bloquea "
            "las recomendaciones de compra."
        ),
    )
    # =========================================================
    # 3. CALIDAD CONTABLE
    # =========================================================
    accounting_reviewed = (
        accounting.accounting_quality_score
        is not None
    )
    _add_gate(
        gates=gates,
        code="ACCOUNTING_REVIEWED",
        passed=accounting_reviewed,
        severity=GateSeverity.BLOCKING,
        message=(
            "La calidad contable debe estar evaluada."
        ),
    )
    accounting_quality = (
        accounting.accounting_quality_score
    )
    _add_gate(
        gates=gates,
        code="ACCOUNTING_QUALITY_MINIMUM",
        passed=(
            accounting_quality is not None
            and accounting_quality >= 40.0
        ),
        severity=GateSeverity.BLOCKING,
        message=(
            "Una calidad contable inferior a 40 bloquea "
            "las recomendaciones de compra."
        ),
    )
    _add_gate(
        gates=gates,
        code="ACCOUNTING_QUALITY_STRONG",
        passed=(
            accounting_quality is not None
            and accounting_quality >= 60.0
        ),
        severity=GateSeverity.WARNING,
        message=(
            "Para una recomendación fuerte se recomienda "
            "una calidad contable mínima de 60."
        ),
    )
    sbc_ratio = accounting.sbc_to_reported_fcf
    _add_gate(
        gates=gates,
        code="SBC_REVIEWED",
        passed=sbc_ratio is not None,
        severity=GateSeverity.WARNING,
        message=(
            "Debe cuantificarse el peso de la remuneración "
            "en acciones sobre el FCF."
        ),
    )
    _add_gate(
        gates=gates,
        code="SBC_NOT_EXCESSIVE",
        passed=(
            sbc_ratio is None
            or sbc_ratio <= 0.40
        ),
        severity=GateSeverity.WARNING,
        message=(
            "Una SBC superior al 40 % del FCF reportado "
            "requiere una revisión prudente."
        ),
    )
    # =========================================================
    # 4. CREACIÓN DE VALOR POR ACCIÓN
    # =========================================================
    per_share_reviewed = (
        analysis.per_share.per_share_value_score
        is not None
    )
    _add_gate(
        gates=gates,
        code="PER_SHARE_VALUE_REVIEWED",
        passed=per_share_reviewed,
        severity=GateSeverity.WARNING,
        message=(
            "Debe evaluarse la creación de valor por acción."
        ),
    )
    share_count_growth = (
        analysis.per_share.share_count_growth
    )
    _add_gate(
        gates=gates,
        code="DILUTION_NOT_EXCESSIVE",
        passed=(
            share_count_growth is None
            or share_count_growth <= 0.05
        ),
        severity=GateSeverity.WARNING,
        message=(
            "Una dilución anual superior al 5 % requiere "
            "una penalización específica."
        ),
    )
    # =========================================================
    # 5. VALORACIÓN
    # =========================================================
    price_available = (
        valuation.current_price is not None
        and valuation.current_price > 0
    )
    _add_gate(
        gates=gates,
        code="VALUATION_PRICE_AVAILABLE",
        passed=price_available,
        severity=GateSeverity.BLOCKING,
        message=(
            "La valoración necesita un precio actual válido."
        ),
    )
    conservative_value_available = (
        valuation.conservative is not None
        and valuation.conservative.intrinsic_value_per_share
        is not None
        and valuation.conservative.intrinsic_value_per_share
        > 0
    )
    _add_gate(
        gates=gates,
        code="CONSERVATIVE_VALUE_AVAILABLE",
        passed=conservative_value_available,
        severity=GateSeverity.BLOCKING,
        message=(
            "Debe existir un valor intrínseco conservador."
        ),
    )
    base_value_available = (
        valuation.base is not None
        and valuation.base.intrinsic_value_per_share
        is not None
        and valuation.base.intrinsic_value_per_share > 0
    )
    _add_gate(
        gates=gates,
        code="BASE_VALUE_AVAILABLE",
        passed=base_value_available,
        severity=GateSeverity.BLOCKING,
        message=(
            "Debe existir un valor intrínseco base."
        ),
    )
    reverse_dcf_reviewed = (
        valuation.reverse_dcf_status is not None
    )
    _add_gate(
        gates=gates,
        code="REVERSE_DCF_REVIEWED",
        passed=reverse_dcf_reviewed,
        severity=GateSeverity.WARNING,
        message=(
            "Debe analizarse qué expectativas descuenta "
            "el precio actual."
        ),
    )
    conservative_margin = (
        valuation.margin_of_safety_conservative
    )
    _add_gate(
        gates=gates,
        code="CONSERVATIVE_MARGIN_POSITIVE",
        passed=(
            conservative_margin is not None
            and conservative_margin > 0.0
        ),
        severity=GateSeverity.WARNING,
        message=(
            "El precio debería situarse por debajo del "
            "valor conservador para una recomendación fuerte."
        ),
    )
    base_margin = valuation.margin_of_safety_base
    _add_gate(
        gates=gates,
        code="BASE_MARGIN_POSITIVE",
        passed=(
            base_margin is not None
            and base_margin > 0.0
        ),
        severity=GateSeverity.BLOCKING,
        message=(
            "Una recomendación de compra requiere un margen "
            "positivo frente al escenario base."
        ),
    )
    # =========================================================
    # 6. CALIDAD OPERATIVA Y RIESGOS
    # =========================================================
    _add_gate(
        gates=gates,
        code="OPERATING_QUALITY_REVIEWED",
        passed=(
            business.operating_quality_score
            is not None
        ),
        severity=GateSeverity.WARNING,
        message=(
            "Debe evaluarse la calidad operativa del negocio."
        ),
    )
    _add_gate(
        gates=gates,
        code="RISK_REVIEWED",
        passed=business.risk_score is not None,
        severity=GateSeverity.WARNING,
        message=(
            "El riesgo global del negocio debe estar evaluado."
        ),
    )
    platform_dependency = (
        business.platform_dependency_risk
    )
    _add_gate(
        gates=gates,
        code="PLATFORM_DEPENDENCY_NOT_CRITICAL",
        passed=(
            platform_dependency is None
            or platform_dependency < 85.0
        ),
        severity=GateSeverity.BLOCKING,
        message=(
            "Una dependencia crítica de plataformas externas "
            "bloquea una recomendación fuerte."
        ),
    )
    regulatory_risk = business.regulatory_risk
    _add_gate(
        gates=gates,
        code="REGULATORY_RISK_NOT_CRITICAL",
        passed=(
            regulatory_risk is None
            or regulatory_risk < 85.0
        ),
        severity=GateSeverity.BLOCKING,
        message=(
            "Un riesgo regulatorio crítico bloquea "
            "las recomendaciones de compra."
        ),
    )
    return gates
def get_failed_gates(
    gates: list[GateResult],
) -> list[GateResult]:
    return [
        gate
        for gate in gates
        if not gate.passed
    ]
def get_blocking_failures(
    gates: list[GateResult],
) -> list[GateResult]:
    return [
        gate
        for gate in gates
        if (
            not gate.passed
            and gate.severity
            == GateSeverity.BLOCKING
        )
    ]
def get_warning_failures(
    gates: list[GateResult],
) -> list[GateResult]:
    return [
        gate
        for gate in gates
        if (
            not gate.passed
            and gate.severity
            == GateSeverity.WARNING
        )
    ]
def has_blocking_failures(
    gates: list[GateResult],
) -> bool:
    return bool(
        get_blocking_failures(gates)
    )
def blocking_failure_codes(
    gates: list[GateResult],
) -> list[str]:
    return [
        gate.code
        for gate in get_blocking_failures(gates)
    ]
