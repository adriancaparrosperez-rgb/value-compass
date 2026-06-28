app:
  name: Value Compass
  base_currency: EUR
  default_index: IBEX35
  timezone: Europe/Madrid
  min_confidence_for_entry: 55
screening:
  max_workers: 4
  stale_price_hours: 36
  recommendation_thresholds:
    strong_entry: 80
    entry: 70
    watch: 58
valuation:
  default_wacc: 0.09
  default_terminal_growth: 0.025
  default_margin_of_safety: 0.25
weights:
  valuation: 0.25
  quality: 0.20
  cash: 0.15
  balance: 0.15
  growth: 0.10
  capital_allocation: 0.05
  momentum_fundamental: 0.05
  risk: 0.05
