from __future__ import annotations

import json
import math
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.models import CompanySnapshot
from src.scoring.engine import score_snapshot
from src.services.snapshot_service import SnapshotService
from src.storage.db import Database


DEFAULT_DB_PATH = "data/value_compass.db"
DEFAULT_EXPORT_DIR = "data/exports"
DEFAULT_MAX_WORKERS = 4
DEFAULT_MIN_CONFIDENCE = 55.0
DEFAULT_MIN_COVERAGE = 50.0


class ScreenerService:
    """
    Coordina la descarga, puntuación, persistencia y exportación
    del radar cuantitativo.

    Principios operativos:

    - cada ticker debe dejar trazabilidad, incluso si falla;
    - un error de proveedor no debe detener todo el universo;
    - un error estructural del motor sí debe hacer fallar la ejecución;
    - las ejecuciones incompletas nunca deben quedar como completed;
    - el orden final debe ser determinista y financieramente útil.
    """

    def __init__(
        self,
        settings: dict[str, Any],
        db_path: str = DEFAULT_DB_PATH,
    ) -> None:
        if not isinstance(
            settings,
            dict,
        ):
            raise TypeError(
                "settings debe ser un diccionario."
            )

        if not isinstance(
            db_path,
            str,
        ) or not db_path.strip():
            raise ValueError(
                "db_path debe ser una ruta no vacía."
            )

        self.settings = settings
        self.provider = SnapshotService()
        self.db = Database(
            db_path.strip()
        )

    def run(
        self,
        universe: str,
        tickers: list[str],
    ) -> pd.DataFrame:
        """
        Ejecuta el radar completo para un universo.

        Los fallos individuales del proveedor se transforman en
        snapshots no fiables, de forma que ninguna empresa
        desaparezca silenciosamente del resultado.

        Los fallos de scoring, base de datos o exportación se
        consideran errores estructurales y marcan la ejecución
        como failed.
        """
        normalized_universe = self._normalize_universe(
            universe
        )
        normalized_tickers = self._normalize_tickers(
            tickers
        )

        run_id = self._new_run_id()
        started_at = self._utc_now()

        self._create_run(
            run_id=run_id,
            universe=normalized_universe,
            started_at=started_at,
            company_count=len(
                normalized_tickers
            ),
        )

        try:
            snapshots = self._fetch_snapshots(
                normalized_tickers
            )

            result = self._score_and_persist(
                run_id=run_id,
                snapshots=snapshots,
            )

            result = self._sort_results(
                result
            )

            self._export_results(
                dataframe=result,
                universe=normalized_universe,
                run_id=run_id,
            )

            self._finish_run(
                run_id=run_id,
                status="completed",
            )

            return result

        except Exception:
            self._finish_run_safely(
                run_id=run_id,
                status="failed",
            )
            raise

    def _fetch_snapshots(
        self,
        tickers: list[str],
    ) -> list[CompanySnapshot]:
        """
        Recupera snapshots concurrentemente.

        El resultado conserva el orden original de los tickers,
        aunque las peticiones terminen en un orden diferente.
        """
        if not tickers:
            return []

        max_workers = self._max_workers(
            ticker_count=len(
                tickers
            )
        )

        snapshots_by_ticker: dict[
            str,
            CompanySnapshot,
        ] = {}

        with ThreadPoolExecutor(
            max_workers=max_workers
        ) as pool:
            futures: dict[
                Future[CompanySnapshot],
                str,
            ] = {
                pool.submit(
                    self.provider.get_snapshot,
                    ticker,
                ): ticker
                for ticker in tickers
            }

            for future in as_completed(
                futures
            ):
                ticker = futures[
                    future
                ]

                try:
                    snapshot = future.result()
                except Exception as exc:
                    snapshot = (
                        self._failed_snapshot(
                            ticker=ticker,
                            error=exc,
                        )
                    )

                if not isinstance(
                    snapshot,
                    CompanySnapshot,
                ):
                    snapshot = (
                        self._failed_snapshot(
                            ticker=ticker,
                            error=TypeError(
                                "SnapshotService devolvió "
                                f"{type(snapshot).__name__} "
                                "en lugar de CompanySnapshot."
                            ),
                        )
                    )

                snapshots_by_ticker[
                    ticker
                ] = snapshot

        return [
            snapshots_by_ticker[
                ticker
            ]
            for ticker in tickers
        ]

    def _score_and_persist(
        self,
        *,
        run_id: str,
        snapshots: list[CompanySnapshot],
    ) -> pd.DataFrame:
        """
        Ejecuta el scoring y persiste snapshot y score.

        Toda la escritura se realiza dentro de una misma
        transacción para evitar ejecuciones parcialmente guardadas.
        """
        weights = self._weights()
        thresholds = self._thresholds()
        min_confidence = (
            self._min_confidence()
        )
        min_coverage = (
            self._min_coverage()
        )

        rows: list[
            dict[str, Any]
        ] = []

        with self.db.connect() as con:
            for snapshot in snapshots:
                score = score_snapshot(
                    snapshot=snapshot,
                    weights=weights,
                    thresholds=thresholds,
                    min_confidence=(
                        min_confidence
                    ),
                    min_coverage=(
                        min_coverage
                    ),
                )

                snapshot_payload = (
                    snapshot.to_dict()
                )
                score_payload = (
                    score.to_dict()
                )

                con.execute(
                    """
                    INSERT INTO snapshots(
                        run_id,
                        ticker,
                        fetched_at,
                        payload_json
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        snapshot.ticker,
                        snapshot.fetched_at,
                        self._json_dumps(
                            snapshot_payload
                        ),
                    ),
                )

                con.execute(
                    """
                    INSERT INTO scores(
                        run_id,
                        ticker,
                        calculated_at,
                        payload_json
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        score.ticker,
                        score.calculated_at,
                        self._json_dumps(
                            score_payload
                        ),
                    ),
                )

                rows.append(
                    {
                        **snapshot_payload,
                        **score_payload,
                        "run_id": run_id,
                    }
                )

        return pd.DataFrame(
            rows
        )

    def _sort_results(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Ordena el radar de forma prudente.

        Primero se prioriza la fiabilidad de la recomendación.
        Dentro de cada categoría se ordena por score, confianza
        y cobertura.

        Así se evita que una empresa con datos frágiles aparezca
        por encima de otra con evaluación más robusta.
        """
        if dataframe.empty:
            return dataframe.copy()

        result = dataframe.copy()

        recommendation_priority = {
            "CANDIDATA PRIORITARIA": 4,
            "CANDIDATA": 3,
            "VIGILAR": 2,
            "DESCARTAR EN PRECRIBADO": 1,
            "DATOS NO FIABLES": 0,
        }

        result[
            "_recommendation_priority"
        ] = (
            result[
                "recommendation"
            ]
            .map(
                recommendation_priority
            )
            .fillna(
                -1
            )
        )

        sort_columns = [
            "_recommendation_priority",
            "global_score",
            "confidence",
            "overall_coverage",
            "ticker",
        ]

        ascending = [
            False,
            False,
            False,
            False,
            True,
        ]

        existing_sort_columns = [
            column
            for column
            in sort_columns
            if column in result.columns
        ]

        existing_ascending = [
            ascending[
                sort_columns.index(
                    column
                )
            ]
            for column
            in existing_sort_columns
        ]

        result = (
            result.sort_values(
                by=existing_sort_columns,
                ascending=(
                    existing_ascending
                ),
                kind="stable",
                na_position="last",
            )
            .drop(
                columns=[
                    "_recommendation_priority"
                ],
                errors="ignore",
            )
            .reset_index(
                drop=True
            )
        )

        return result

    def _export_results(
        self,
        *,
        dataframe: pd.DataFrame,
        universe: str,
        run_id: str,
    ) -> None:
        """
        Exporta los resultados a CSV, Excel y JSON.

        La ejecución solo se marca como completed cuando las tres
        exportaciones han terminado correctamente.
        """
        export_dir = self._export_dir()

        export_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_universe = (
            self._safe_filename_component(
                universe
            )
        )

        stem = (
            f"{safe_universe}"
            f"_screening_{run_id}"
        )

        csv_path = (
            export_dir
            / f"{stem}.csv"
        )
        excel_path = (
            export_dir
            / f"{stem}.xlsx"
        )
        json_path = (
            export_dir
            / f"{stem}.json"
        )

        dataframe.to_csv(
            csv_path,
            index=False,
        )

        dataframe.to_excel(
            excel_path,
            index=False,
        )

        json_path.write_text(
            dataframe.to_json(
                orient="records",
                force_ascii=False,
                indent=2,
                date_format="iso",
            ),
            encoding="utf-8",
        )

    def _create_run(
        self,
        *,
        run_id: str,
        universe: str,
        started_at: str,
        company_count: int,
    ) -> None:
        with self.db.connect() as con:
            con.execute(
                """
                INSERT INTO runs(
                    run_id,
                    universe,
                    started_at,
                    status,
                    company_count
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    universe,
                    started_at,
                    "running",
                    company_count,
                ),
            )

    def _finish_run(
        self,
        *,
        run_id: str,
        status: str,
    ) -> None:
        with self.db.connect() as con:
            con.execute(
                """
                UPDATE runs
                SET
                    finished_at = ?,
                    status = ?
                WHERE run_id = ?
                """,
                (
                    self._utc_now(),
                    status,
                    run_id,
                ),
            )

    def _finish_run_safely(
        self,
        *,
        run_id: str,
        status: str,
    ) -> None:
        """
        Intenta actualizar el estado sin ocultar el error original.
        """
        try:
            self._finish_run(
                run_id=run_id,
                status=status,
            )
        except Exception:
            pass

    def _failed_snapshot(
        self,
        *,
        ticker: str,
        error: Exception,
    ) -> CompanySnapshot:
        """
        Crea un snapshot trazable para un fallo individual.

        La empresa permanecerá en el resultado y el motor la
        clasificará como DATOS NO FIABLES.
        """
        error_message = (
            f"{type(error).__name__}: "
            f"{str(error).strip() or 'Error sin detalle'}"
        )

        return CompanySnapshot(
            ticker=ticker,
            source="snapshot_service",
            data_quality=0.0,
            errors=error_message,
            warnings=[
                (
                    "No se pudo recuperar el snapshot. "
                    "La empresa se conserva en el radar "
                    "como dato no fiable."
                )
            ],
        )

    def _weights(
        self,
    ) -> dict[str, Any]:
        weights = self.settings.get(
            "weights",
            {},
        )

        if not isinstance(
            weights,
            dict,
        ):
            raise TypeError(
                "settings['weights'] debe ser un diccionario."
            )

        return weights

    def _thresholds(
        self,
    ) -> dict[str, Any]:
        screening = self._screening_settings()

        thresholds = screening.get(
            "recommendation_thresholds",
            {},
        )

        if not isinstance(
            thresholds,
            dict,
        ):
            raise TypeError(
                "recommendation_thresholds debe ser "
                "un diccionario."
            )

        return thresholds

    def _min_confidence(
        self,
    ) -> float:
        app_settings = self.settings.get(
            "app",
            {},
        )

        if not isinstance(
            app_settings,
            dict,
        ):
            raise TypeError(
                "settings['app'] debe ser un diccionario."
            )

        return self._bounded_setting(
            app_settings.get(
                "min_confidence_for_entry",
                DEFAULT_MIN_CONFIDENCE,
            ),
            default=DEFAULT_MIN_CONFIDENCE,
        )

    def _min_coverage(
        self,
    ) -> float:
        screening = self._screening_settings()

        raw_value = screening.get(
            "min_coverage",
            self.settings.get(
                "app",
                {},
            ).get(
                "min_coverage_for_entry",
                DEFAULT_MIN_COVERAGE,
            )
            if isinstance(
                self.settings.get(
                    "app",
                    {},
                ),
                dict,
            )
            else DEFAULT_MIN_COVERAGE,
        )

        return self._bounded_setting(
            raw_value,
            default=DEFAULT_MIN_COVERAGE,
        )

    def _max_workers(
        self,
        *,
        ticker_count: int,
    ) -> int:
        screening = self._screening_settings()

        raw_workers = screening.get(
            "max_workers",
            DEFAULT_MAX_WORKERS,
        )

        try:
            workers = int(
                raw_workers
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            workers = (
                DEFAULT_MAX_WORKERS
            )

        workers = max(
            1,
            workers,
        )

        if ticker_count > 0:
            workers = min(
                workers,
                ticker_count,
            )

        return workers

    def _export_dir(
        self,
    ) -> Path:
        screening = self._screening_settings()

        configured_path = screening.get(
            "export_dir",
            DEFAULT_EXPORT_DIR,
        )

        if not isinstance(
            configured_path,
            str,
        ) or not configured_path.strip():
            configured_path = (
                DEFAULT_EXPORT_DIR
            )

        return Path(
            configured_path
        )

    def _screening_settings(
        self,
    ) -> dict[str, Any]:
        screening = self.settings.get(
            "screening",
            {},
        )

        if not isinstance(
            screening,
            dict,
        ):
            raise TypeError(
                "settings['screening'] debe ser "
                "un diccionario."
            )

        return screening

    @staticmethod
    def _normalize_universe(
        universe: str,
    ) -> str:
        if not isinstance(
            universe,
            str,
        ):
            raise TypeError(
                "universe debe ser una cadena."
            )

        normalized = universe.strip()

        if not normalized:
            raise ValueError(
                "universe no puede estar vacío."
            )

        return normalized

    @staticmethod
    def _normalize_tickers(
        tickers: list[str],
    ) -> list[str]:
        if not isinstance(
            tickers,
            list,
        ):
            raise TypeError(
                "tickers debe ser una lista."
            )

        normalized: list[str] = []
        seen: set[str] = set()

        for ticker in tickers:
            if not isinstance(
                ticker,
                str,
            ):
                raise TypeError(
                    "Todos los tickers deben ser cadenas."
                )

            clean_ticker = (
                ticker.strip()
            )

            if not clean_ticker:
                continue

            comparison_key = (
                clean_ticker.casefold()
            )

            if comparison_key in seen:
                continue

            seen.add(
                comparison_key
            )
            normalized.append(
                clean_ticker
            )

        return normalized

    @staticmethod
    def _bounded_setting(
        value: Any,
        *,
        default: float,
    ) -> float:
        if (
            value is None
            or isinstance(
                value,
                bool,
            )
        ):
            return default

        try:
            numeric_value = float(
                value
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return default

        if not math.isfinite(
            numeric_value
        ):
            return default

        return max(
            0.0,
            min(
                100.0,
                numeric_value,
            ),
        )

    @staticmethod
    def _safe_filename_component(
        value: str,
    ) -> str:
        safe_value = "".join(
            character
            if (
                character.isalnum()
                or character
                in {
                    "-",
                    "_",
                }
            )
            else "_"
            for character in value
        )

        safe_value = (
            safe_value.strip(
                "_"
            )
        )

        return (
            safe_value
            or "universe"
        )

    @staticmethod
    def _json_dumps(
        payload: dict[str, Any],
    ) -> str:
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            default=str,
        )

    @staticmethod
    def _new_run_id() -> str:
        return datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()
