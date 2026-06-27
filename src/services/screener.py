from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import pandas as pd
from src.services.snapshot_service import SnapshotService
from src.scoring.engine import score_snapshot
from src.storage.db import Database

class ScreenerService:
    def __init__(self, settings: dict, db_path: str = "data/value_compass.db"):
        self.settings = settings
        self.provider = SnapshotService()
        self.db = Database(db_path)

    def run(self, universe: str, tickers: list[str]) -> pd.DataFrame:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        started = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as con:
            con.execute("INSERT INTO runs(run_id, universe, started_at, status, company_count) VALUES(?,?,?,?,?)",
                        (run_id, universe, started, "running", len(tickers)))
        snapshots = []
        workers = int(self.settings.get("screening", {}).get("max_workers", 4))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.provider.get_snapshot, t): t for t in tickers}
            for future in as_completed(futures):
                snapshots.append(future.result())
        rows = []
        weights = self.settings.get("weights", {})
        thresholds = self.settings.get("screening", {}).get("recommendation_thresholds", {})
        min_conf = self.settings.get("app", {}).get("min_confidence_for_entry", 55)
        with self.db.connect() as con:
            for snap in snapshots:
                score = score_snapshot(snap, weights, thresholds, min_conf)
                con.execute("INSERT INTO snapshots(run_id,ticker,fetched_at,payload_json) VALUES(?,?,?,?)",
                            (run_id, snap.ticker, snap.fetched_at, json.dumps(snap.to_dict(), ensure_ascii=False)))
                con.execute("INSERT INTO scores(run_id,ticker,calculated_at,payload_json) VALUES(?,?,?,?)",
                            (run_id, score.ticker, score.calculated_at, json.dumps(score.to_dict(), ensure_ascii=False)))
                rows.append({**snap.to_dict(), **score.to_dict(), "run_id": run_id})
            con.execute("UPDATE runs SET finished_at=?, status=? WHERE run_id=?",
                        (datetime.now(timezone.utc).isoformat(), "completed", run_id))
        df = pd.DataFrame(rows).sort_values(["global_score", "confidence"], ascending=False)
        out_dir = Path("data/exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{universe}_screening_{run_id}"
        df.to_csv(out_dir / f"{stem}.csv", index=False)
        df.to_excel(out_dir / f"{stem}.xlsx", index=False)
        (out_dir / f"{stem}.json").write_text(df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
        return df
