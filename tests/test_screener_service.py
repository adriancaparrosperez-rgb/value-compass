from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.models import CompanySnapshot, ScoreCard
from src.scoring.engine import (
    RADAR_CANDIDATE,
    RADAR_PRIORITY,
    RADAR_UNRELIABLE,
    RADAR_WATCH,
)
from src.services import screener as screener_module
from src.services.screener import ScreenerService


DEFAULT_WEIGHTS: dict[str, float] = {
    "valuation": 0.25,
    "quality": 0.20,
    "cash": 0.15,
    "balance": 0.15,
    "growth": 0.10,
    "capital_allocation": 0.05,
    "momentum_fundamental": 0.05,
    "risk": 0.05,
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "priority": 80.0,
    "candidate": 70.0,
    "watch": 58.0,
}


class TemporaryDatabase:
    """
    Base SQLite mínima para probar ScreenerService.

    Replica únicamente las tablas y columnas utilizadas por el
    servicio, sin depender del archivo de producción.
    """

    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = path

        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    universe TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    company_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    fetched_at TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def connect(
        self,
    ) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.path
        )

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class FakeProvider:
    def __init__(
        self,
        responses: dict[
            str,
            CompanySnapshot | Exception | Any,
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get_snapshot(
        self,
        ticker: str,
    ) -> CompanySnapshot:
        self.calls.append(
            ticker
        )

        response = self.responses[
            ticker
        ]

        if isinstance(
            response,
            Exception,
        ):
            raise response

        return response


def build_snapshot(
    ticker: str,
    **overrides: Any,
) -> CompanySnapshot:
    values: dict[str, Any] = {
        "ticker": ticker,
        "name": f"{ticker} Company",
        "currency": "USD",
        "sector": "Technology",
        "industry": "Software",
        "price": 100.0,
        "market_cap": 100_000.0,
        "enterprise_value": 90_000.0,
        "revenue": 20_000.0,
        "ebitda": 5_000.0,
        "ebit": 4_000.0,
        "net_income": 3_000.0,
        "operating_cash_flow": 4_000.0,
        "capex": 1_000.0,
        "free_cash_flow": 3_000.0,
        "total_cash": 20_000.0,
        "total_debt": 10_000.0,
        "shares": 1_000.0,
        "revenue_growth": 0.15,
        "earnings_growth": 0.18,
        "gross_margin": 0.60,
        "operating_margin": 0.20,
        "net_margin": 0.15,
        "roe": 0.22,
        "roa": 0.10,
        "debt_to_equity": 0.50,
        "current_ratio": 1.50,
        "interest_coverage": 10.0,
        "pe": 20.0,
        "forward_pe": 15.0,
        "price_to_book": 4.0,
        "ev_to_ebitda": 10.0,
        "fcf_yield": 0.07,
        "earnings_yield": 0.06,
        "dividend_yield": 0.02,
        "fifty_two_week_change": 0.10,
        "analyst_target": 120.0,
        "analyst_count": 20,
        "source": "test",
        "data_quality": 90.0,
        "coverage_score": 90.0,
        "validity_score": 90.0,
        "consistency_score": 90.0,
    }

    values.update(
        overrides
    )

    return CompanySnapshot(
        **values
    )


def build_score(
    ticker: str,
    *,
    global_score: float = 75.0,
    confidence: float = 90.0,
    coverage: float = 100.0,
    recommendation: str = RADAR_CANDIDATE,
) -> ScoreCard:
    return ScoreCard(
        ticker=ticker,
        valuation=75.0,
        quality=75.0,
        cash=75.0,
        balance=75.0,
        growth=75.0,
        capital_allocation=75.0,
        momentum_fundamental=75.0,
        risk=75.0,
        confidence=confidence,
        global_score=global_score,
        recommendation=recommendation,
        rationale="Resultado de prueba.",
        calculated_at="2026-06-28T12:00:00+00:00",
        overall_coverage=coverage,
        dimension_coverage={
            "valuation": coverage,
            "quality": coverage,
            "cash": coverage,
            "balance": coverage,
            "growth": coverage,
            "capital_allocation": coverage,
            "momentum_fundamental": coverage,
            "risk": coverage,
        },
        missing_metrics=[],
        warnings=[],
        scoring_version="test",
    )


def build_settings(
    export_dir: Path,
    **screening_overrides: Any,
) -> dict[str, Any]:
    screening: dict[str, Any] = {
        "max_workers": 2,
        "export_dir": str(
            export_dir
        ),
        "min_coverage": 60.0,
        "recommendation_thresholds": dict(
            DEFAULT_THRESHOLDS
        ),
    }

    screening.update(
        screening_overrides
    )

    return {
        "weights": dict(
            DEFAULT_WEIGHTS
        ),
        "screening": screening,
        "app": {
            "min_confidence_for_entry": 65.0,
            "min_coverage_for_entry": 60.0,
        },
    }


def build_service(
    tmp_path: Path,
    *,
    responses: dict[
        str,
        CompanySnapshot | Exception | Any,
    ]
    | None = None,
    settings: dict[str, Any] | None = None,
) -> ScreenerService:
    export_dir = (
        tmp_path
        / "exports"
    )

    service = ScreenerService(
        settings=(
            settings
            or build_settings(
                export_dir
            )
        ),
        db_path=str(
            tmp_path
            / "unused.db"
        ),
    )

    service.db = TemporaryDatabase(
        tmp_path
        / "test_screener.db"
    )

    service.provider = FakeProvider(
        responses
        or {}
    )

    return service


def read_run_rows(
    service: ScreenerService,
) -> list[sqlite3.Row]:
    with service.db.connect() as connection:
        connection.row_factory = (
            sqlite3.Row
        )

        return list(
            connection.execute(
                """
                SELECT
                    run_id,
                    universe,
                    started_at,
                    finished_at,
                    status,
                    company_count
                FROM runs
                ORDER BY started_at
                """
            )
        )


def read_payloads(
    service: ScreenerService,
    table: str,
) -> list[dict[str, Any]]:
    if table not in {
        "snapshots",
        "scores",
    }:
        raise ValueError(
            "Tabla no permitida."
        )

    with service.db.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT payload_json
            FROM {table}
            ORDER BY id
            """
        ).fetchall()

    return [
        json.loads(
            row[0]
        )
        for row in rows
    ]


# ============================================================
# NORMALIZACIÓN Y CONFIGURACIÓN
# ============================================================


def test_normalize_tickers_strips_blanks_and_duplicates() -> None:
    result = (
        ScreenerService._normalize_tickers(
            [
                " META ",
                "",
                "meta",
                "AAPL",
                "  ",
                "aapl",
                "MSFT",
            ]
        )
    )

    assert result == [
        "META",
        "AAPL",
        "MSFT",
    ]


@pytest.mark.parametrize(
    "invalid_tickers",
    [
        None,
        (),
        "META",
        {
            "META",
        },
    ],
)
def test_normalize_tickers_requires_list(
    invalid_tickers: Any,
) -> None:
    with pytest.raises(
        TypeError,
        match="lista",
    ):
        ScreenerService._normalize_tickers(
            invalid_tickers
        )


def test_normalize_tickers_rejects_non_string_items() -> None:
    with pytest.raises(
        TypeError,
        match="cadenas",
    ):
        ScreenerService._normalize_tickers(
            [
                "META",
                123,
            ]
        )


@pytest.mark.parametrize(
    "universe",
    [
        "",
        " ",
        "\n",
    ],
)
def test_empty_universe_is_rejected(
    universe: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="vacío",
    ):
        ScreenerService._normalize_universe(
            universe
        )


def test_max_workers_is_bounded_by_ticker_count(
    tmp_path: Path,
) -> None:
    settings = build_settings(
        tmp_path
        / "exports",
        max_workers=100,
    )

    service = build_service(
        tmp_path,
        settings=settings,
    )

    assert (
        service._max_workers(
            ticker_count=3
        )
        == 3
    )


@pytest.mark.parametrize(
    "configured_value",
    [
        None,
        "invalid",
        math.inf,
        True,
    ],
)
def test_invalid_max_workers_falls_back_safely(
    tmp_path: Path,
    configured_value: Any,
) -> None:
    settings = build_settings(
        tmp_path
        / "exports",
        max_workers=configured_value,
    )

    service = build_service(
        tmp_path,
        settings=settings,
    )

    assert (
        service._max_workers(
            ticker_count=10
        )
        >= 1
    )


# ============================================================
# DESCARGA CONCURRENTE Y AISLAMIENTO DE FALLOS
# ============================================================


def test_fetch_snapshots_preserves_input_order(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path,
        responses={
            "META": build_snapshot(
                "META"
            ),
            "AAPL": build_snapshot(
                "AAPL"
            ),
            "MSFT": build_snapshot(
                "MSFT"
            ),
        },
    )

    snapshots = service._fetch_snapshots(
        [
            "META",
            "AAPL",
            "MSFT",
        ]
    )

    assert [
        snapshot.ticker
        for snapshot
        in snapshots
    ] == [
        "META",
        "AAPL",
        "MSFT",
    ]


def test_provider_failure_becomes_traceable_snapshot(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path,
        responses={
            "META": RuntimeError(
                "Provider unavailable"
            ),
        },
    )

    snapshots = service._fetch_snapshots(
        [
            "META",
        ]
    )

    assert len(
        snapshots
    ) == 1

    snapshot = snapshots[0]

    assert snapshot.ticker == "META"
    assert snapshot.data_quality == 0.0
    assert snapshot.errors
    assert "Provider unavailable" in str(
        snapshot.errors
    )


def test_invalid_provider_result_becomes_failed_snapshot(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path,
        responses={
            "META": {
                "ticker": "META",
            },
        },
    )

    snapshots = service._fetch_snapshots(
        [
            "META",
        ]
    )

    assert snapshots[0].ticker == "META"
    assert snapshots[0].errors
    assert "CompanySnapshot" in str(
        snapshots[0].errors
    )


# ============================================================
# SCORING, PERSISTENCIA Y PARÁMETROS
# ============================================================


def test_score_and_persist_passes_confidence_and_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path,
        responses={},
    )

    captured: dict[str, Any] = {}

    def fake_score_snapshot(
        *,
        snapshot: CompanySnapshot,
        weights: dict[str, Any],
        thresholds: dict[str, Any],
        min_confidence: float,
        min_coverage: float,
    ) -> ScoreCard:
        captured.update(
            {
                "snapshot": snapshot,
                "weights": weights,
                "thresholds": thresholds,
                "min_confidence": (
                    min_confidence
                ),
                "min_coverage": (
                    min_coverage
                ),
            }
        )

        return build_score(
            snapshot.ticker
        )

    monkeypatch.setattr(
        screener_module,
        "score_snapshot",
        fake_score_snapshot,
    )

    dataframe = (
        service._score_and_persist(
            run_id="RUN-1",
            snapshots=[
                build_snapshot(
                    "META"
                )
            ],
        )
    )

    assert captured[
        "min_confidence"
    ] == 65.0

    assert captured[
        "min_coverage"
    ] == 60.0

    assert captured[
        "weights"
    ] == DEFAULT_WEIGHTS

    assert captured[
        "thresholds"
    ] == DEFAULT_THRESHOLDS

    assert dataframe.loc[
        0,
        "ticker",
    ] == "META"

    assert len(
        read_payloads(
            service,
            "snapshots",
        )
    ) == 1

    assert len(
        read_payloads(
            service,
            "scores",
        )
    ) == 1


def test_snapshot_and_score_payloads_are_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path,
    )

    monkeypatch.setattr(
        screener_module,
        "score_snapshot",
        lambda **kwargs: build_score(
            kwargs[
                "snapshot"
            ].ticker
        ),
    )

    service._score_and_persist(
        run_id="RUN-2",
        snapshots=[
            build_snapshot(
                "META"
            ),
            build_snapshot(
                "AAPL"
            ),
        ],
    )

    snapshot_payloads = read_payloads(
        service,
        "snapshots",
    )
    score_payloads = read_payloads(
        service,
        "scores",
    )

    assert {
        payload[
            "ticker"
        ]
        for payload
        in snapshot_payloads
    } == {
        "META",
        "AAPL",
    }

    assert {
        payload[
            "ticker"
        ]
        for payload
        in score_payloads
    } == {
        "META",
        "AAPL",
    }


# ============================================================
# ORDENACIÓN FINANCIERA DEL RADAR
# ============================================================


def test_sort_results_prioritizes_recommendation_before_score(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path
    )

    dataframe = pd.DataFrame(
        [
            {
                "ticker": "UNRELIABLE",
                "recommendation": (
                    RADAR_UNRELIABLE
                ),
                "global_score": 99.0,
                "confidence": 10.0,
                "overall_coverage": 20.0,
            },
            {
                "ticker": "WATCH",
                "recommendation": (
                    RADAR_WATCH
                ),
                "global_score": 60.0,
                "confidence": 90.0,
                "overall_coverage": 95.0,
            },
            {
                "ticker": "CANDIDATE",
                "recommendation": (
                    RADAR_CANDIDATE
                ),
                "global_score": 70.0,
                "confidence": 80.0,
                "overall_coverage": 80.0,
            },
            {
                "ticker": "PRIORITY",
                "recommendation": (
                    RADAR_PRIORITY
                ),
                "global_score": 82.0,
                "confidence": 75.0,
                "overall_coverage": 75.0,
            },
        ]
    )

    result = service._sort_results(
        dataframe
    )

    assert result[
        "ticker"
    ].tolist() == [
        "PRIORITY",
        "CANDIDATE",
        "WATCH",
        "UNRELIABLE",
    ]


def test_sort_results_uses_score_confidence_and_coverage_as_tiebreakers(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path
    )

    dataframe = pd.DataFrame(
        [
            {
                "ticker": "LOW-SCORE",
                "recommendation": (
                    RADAR_CANDIDATE
                ),
                "global_score": 71.0,
                "confidence": 99.0,
                "overall_coverage": 99.0,
            },
            {
                "ticker": "HIGH-SCORE",
                "recommendation": (
                    RADAR_CANDIDATE
                ),
                "global_score": 75.0,
                "confidence": 70.0,
                "overall_coverage": 70.0,
            },
            {
                "ticker": "HIGH-CONFIDENCE",
                "recommendation": (
                    RADAR_CANDIDATE
                ),
                "global_score": 75.0,
                "confidence": 90.0,
                "overall_coverage": 80.0,
            },
            {
                "ticker": "HIGH-COVERAGE",
                "recommendation": (
                    RADAR_CANDIDATE
                ),
                "global_score": 75.0,
                "confidence": 90.0,
                "overall_coverage": 95.0,
            },
        ]
    )

    result = service._sort_results(
        dataframe
    )

    assert result[
        "ticker"
    ].tolist() == [
        "HIGH-COVERAGE",
        "HIGH-CONFIDENCE",
        "HIGH-SCORE",
        "LOW-SCORE",
    ]


def test_sort_results_handles_empty_dataframe(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path
    )

    dataframe = pd.DataFrame()

    result = service._sort_results(
        dataframe
    )

    assert result.empty


# ============================================================
# EXPORTACIONES
# ============================================================


def test_export_results_creates_csv_excel_and_json(
    tmp_path: Path,
) -> None:
    export_dir = (
        tmp_path
        / "custom_exports"
    )

    service = build_service(
        tmp_path,
        settings=build_settings(
            export_dir
        ),
    )

    dataframe = pd.DataFrame(
        [
            {
                "ticker": "META",
                "global_score": 75.0,
                "recommendation": (
                    RADAR_CANDIDATE
                ),
            }
        ]
    )

    service._export_results(
        dataframe=dataframe,
        universe="S&P 500 / Test",
        run_id="RUN123",
    )

    files = {
        path.suffix
        for path
        in export_dir.iterdir()
    }

    assert files == {
        ".csv",
        ".xlsx",
        ".json",
    }

    json_file = next(
        export_dir.glob(
            "*.json"
        )
    )

    payload = json.loads(
        json_file.read_text(
            encoding="utf-8"
        )
    )

    assert payload[
        0
    ][
        "ticker"
    ] == "META"


def test_export_filename_is_sanitized(
    tmp_path: Path,
) -> None:
    export_dir = (
        tmp_path
        / "exports"
    )

    service = build_service(
        tmp_path,
        settings=build_settings(
            export_dir
        ),
    )

    service._export_results(
        dataframe=pd.DataFrame(),
        universe="../../IBEX 35",
        run_id="RUN123",
    )

    generated_names = [
        path.name
        for path
        in export_dir.iterdir()
    ]

    assert all(
        ".." not in name
        for name
        in generated_names
    )

    assert all(
        "/" not in name
        for name
        in generated_names
    )


# ============================================================
# EJECUCIÓN COMPLETA
# ============================================================


def test_run_completes_persists_and_exports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "META": build_snapshot(
            "META"
        ),
        "AAPL": build_snapshot(
            "AAPL"
        ),
    }

    service = build_service(
        tmp_path,
        responses=responses,
    )

    score_by_ticker = {
        "META": build_score(
            "META",
            global_score=82.0,
            recommendation=(
                RADAR_PRIORITY
            ),
        ),
        "AAPL": build_score(
            "AAPL",
            global_score=72.0,
            recommendation=(
                RADAR_CANDIDATE
            ),
        ),
    }

    monkeypatch.setattr(
        screener_module,
        "score_snapshot",
        lambda **kwargs: (
            score_by_ticker[
                kwargs[
                    "snapshot"
                ].ticker
            ]
        ),
    )

    result = service.run(
        universe="TEST INDEX",
        tickers=[
            " META ",
            "AAPL",
            "meta",
            "",
        ],
    )

    assert result[
        "ticker"
    ].tolist() == [
        "META",
        "AAPL",
    ]

    assert service.provider.calls.count(
        "META"
    ) == 1

    assert service.provider.calls.count(
        "AAPL"
    ) == 1

    runs = read_run_rows(
        service
    )

    assert len(
        runs
    ) == 1

    assert runs[
        0
    ][
        "status"
    ] == "completed"

    assert runs[
        0
    ][
        "company_count"
    ] == 2

    assert runs[
        0
    ][
        "finished_at"
    ] is not None

    export_dir = Path(
        service.settings[
            "screening"
        ][
            "export_dir"
        ]
    )

    assert len(
        list(
            export_dir.glob(
                "*.csv"
            )
        )
    ) == 1

    assert len(
        list(
            export_dir.glob(
                "*.xlsx"
            )
        )
    ) == 1

    assert len(
        list(
            export_dir.glob(
                "*.json"
            )
        )
    ) == 1


def test_partial_provider_failure_does_not_abort_universe(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path,
        responses={
            "GOOD": build_snapshot(
                "GOOD"
            ),
            "FAIL": RuntimeError(
                "Temporary provider failure"
            ),
        },
    )

    result = service.run(
        universe="PARTIAL",
        tickers=[
            "GOOD",
            "FAIL",
        ],
    )

    assert set(
        result[
            "ticker"
        ]
    ) == {
        "GOOD",
        "FAIL",
    }

    failed_row = result.loc[
        result[
            "ticker"
        ]
        == "FAIL"
    ].iloc[
        0
    ]

    assert (
        failed_row[
            "recommendation"
        ]
        == RADAR_UNRELIABLE
    )

    assert failed_row[
        "errors"
    ]

    runs = read_run_rows(
        service
    )

    assert runs[
        0
    ][
        "status"
    ] == "completed"


def test_empty_ticker_list_completes_with_empty_result(
    tmp_path: Path,
) -> None:
    service = build_service(
        tmp_path,
        responses={},
    )

    result = service.run(
        universe="EMPTY",
        tickers=[],
    )

    assert result.empty

    runs = read_run_rows(
        service
    )

    assert runs[
        0
    ][
        "status"
    ] == "completed"

    assert runs[
        0
    ][
        "company_count"
    ] == 0


def test_scoring_failure_marks_run_as_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path,
        responses={
            "META": build_snapshot(
                "META"
            ),
        },
    )

    def fail_scoring(
        **_: Any,
    ) -> ScoreCard:
        raise RuntimeError(
            "Scoring contract failure"
        )

    monkeypatch.setattr(
        screener_module,
        "score_snapshot",
        fail_scoring,
    )

    with pytest.raises(
        RuntimeError,
        match="Scoring contract failure",
    ):
        service.run(
            universe="TEST",
            tickers=[
                "META",
            ],
        )

    runs = read_run_rows(
        service
    )

    assert runs[
        0
    ][
        "status"
    ] == "failed"

    assert runs[
        0
    ][
        "finished_at"
    ] is not None


def test_export_failure_marks_run_as_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_service(
        tmp_path,
        responses={
            "META": build_snapshot(
                "META"
            ),
        },
    )

    monkeypatch.setattr(
        screener_module,
        "score_snapshot",
        lambda **kwargs: build_score(
            kwargs[
                "snapshot"
            ].ticker
        ),
    )

    def fail_export(
        **_: Any,
    ) -> None:
        raise OSError(
            "Export unavailable"
        )

    monkeypatch.setattr(
        service,
        "_export_results",
        fail_export,
    )

    with pytest.raises(
        OSError,
        match="Export unavailable",
    ):
        service.run(
            universe="TEST",
            tickers=[
                "META",
            ],
        )

    runs = read_run_rows(
        service
    )

    assert runs[
        0
    ][
        "status"
    ] == "failed"


def test_run_ids_are_unique() -> None:
    first = (
        ScreenerService._new_run_id()
    )
    second = (
        ScreenerService._new_run_id()
    )

    assert first != second
