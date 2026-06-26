from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  ticker TEXT NOT NULL,
  fetched_at TEXT,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ticker ON snapshots(ticker);
CREATE TABLE IF NOT EXISTS scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  ticker TEXT NOT NULL,
  calculated_at TEXT,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scores_ticker ON scores(ticker);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  universe TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT,
  company_count INTEGER,
  notes TEXT
);
"""

class Database:
    def __init__(self, path: str = "data/value_compass.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)

    def connect(self):
        return sqlite3.connect(self.path)

    def latest_scores(self) -> pd.DataFrame:
        query = """
        SELECT s.run_id, s.ticker, s.calculated_at, s.payload_json
        FROM scores s JOIN (SELECT ticker, MAX(id) max_id FROM scores GROUP BY ticker) x ON s.id=x.max_id
        """
        with self.connect() as con:
            return pd.read_sql_query(query, con)
