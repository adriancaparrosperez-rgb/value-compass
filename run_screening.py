from __future__ import annotations
import argparse
from src.config import settings, universes
from src.services.screener import ScreenerService

p = argparse.ArgumentParser()
p.add_argument("--universe", default="IBEX35")
args = p.parse_args()
u = universes()
if args.universe not in u:
    raise SystemExit(f"Universo desconocido: {args.universe}")
tickers = u[args.universe].get("tickers", [])
if not tickers:
    raise SystemExit("El universo no contiene tickers")
df = ScreenerService(settings()).run(args.universe, tickers)
print(df[["ticker","global_score","confidence","recommendation"]].to_string(index=False))
