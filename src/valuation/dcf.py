from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass
class DCFResult:
    enterprise_value: float
    equity_value: float
    value_per_share: float | None
    terminal_value: float
    projected_fcfs: list[float]
    assumptions: dict

    def to_dict(self):
        return asdict(self)

def dcf_value(fcf0: float, growth: float, years: int, wacc: float, terminal_growth: float,
              net_debt: float = 0.0, shares: float | None = None) -> DCFResult:
    if wacc <= terminal_growth:
        raise ValueError("El WACC debe ser superior al crecimiento terminal.")
    if years < 1:
        raise ValueError("El horizonte debe ser al menos de un año.")
    fcfs, pv = [], 0.0
    fcf = fcf0
    for year in range(1, years + 1):
        fcf *= (1 + growth)
        fcfs.append(fcf)
        pv += fcf / ((1 + wacc) ** year)
    terminal = fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal / ((1 + wacc) ** years)
    enterprise = pv + pv_terminal
    equity = enterprise - net_debt
    per_share = equity / shares if shares and shares > 0 else None
    return DCFResult(enterprise, equity, per_share, terminal, fcfs, {
        "fcf0": fcf0, "growth": growth, "years": years, "wacc": wacc,
        "terminal_growth": terminal_growth, "net_debt": net_debt, "shares": shares})
