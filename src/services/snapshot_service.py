from __future__ import annotations

import json
import logging
import threading
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.models import CompanySnapshot
from src.providers.base import MarketDataProvider
from src.providers.yahoo import YahooProvider


logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIRECTORY = "data/snapshot_cache"
DEFAULT_CACHE_TTL_SECONDS = 900
DEFAULT_STALE_TTL_SECONDS = 86400
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 1800

_RATE_LIMIT_EXCEPTION_TYPES = {
    "YFRateLimitError",
}

_RATE_LIMIT_MESSAGE_FRAGMENTS = (
    "too many requests",
    "rate limited",
    "rate limit",
)


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _normalize_ticker(
    ticker: Any,
) -> str:
    if not isinstance(
        ticker,
        str,
    ):
        raise ValueError(
            "El ticker debe ser una cadena de texto."
        )

    normalized_ticker = (
        ticker.strip().upper()
    )

    if not normalized_ticker:
        raise ValueError(
            "El ticker no puede estar vacío."
        )

    return normalized_ticker


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    normalized_value = value.strip()

    if not normalized_value:
        return None

    try:
        parsed_value = datetime.fromisoformat(
            normalized_value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    if parsed_value.tzinfo is None:
        parsed_value = parsed_value.replace(
            tzinfo=timezone.utc
        )

    return parsed_value.astimezone(
        timezone.utc
    )


def _snapshot_from_dict(
    payload: Any,
) -> CompanySnapshot | None:
    if not isinstance(
        payload,
        dict,
    ):
        return None

    try:
        return CompanySnapshot(
            **payload
        )
    except (
        TypeError,
        ValueError,
    ):
        logger.exception(
            "No se pudo reconstruir un snapshot almacenado."
        )
        return None


def _is_rate_limit_snapshot(
    snapshot: CompanySnapshot,
) -> bool:
    metadata = snapshot.provider_metadata

    if not isinstance(
        metadata,
        dict,
    ):
        return False

    components = (
        metadata.get(
            "initialization"
        ),
        metadata.get(
            "fast_info"
        ),
        metadata.get(
            "info"
        ),
        metadata.get(
            "normalization"
        ),
    )

    for component in components:
        if not isinstance(
            component,
            dict,
        ):
            continue

        exception_type = str(
            component.get(
                "exception_type",
                "",
            )
        ).strip()

        message = str(
            component.get(
                "message",
                "",
            )
        ).strip().casefold()

        if (
            exception_type
            in _RATE_LIMIT_EXCEPTION_TYPES
        ):
            return True

        if any(
            fragment in message
            for fragment
            in _RATE_LIMIT_MESSAGE_FRAGMENTS
        ):
            return True

    return False


def _is_valid_snapshot(
    snapshot: CompanySnapshot,
) -> bool:
    return (
        snapshot.price is not None
        and snapshot.market_cap is not None
        and not snapshot.has_errors
    )


class SnapshotService:
    """
    Coordina la adquisición de snapshots.

    Responsabilidades:

    - evitar consultas repetidas para el mismo ticker;
    - almacenar el último resultado válido;
    - impedir nuevos intentos durante un rate limit;
    - devolver datos anteriores cuando Yahoo no está disponible;
    - mantener YahooProvider separado de la interfaz.
    """

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        *,
        cache_directory: str | Path = (
            DEFAULT_CACHE_DIRECTORY
        ),
        cache_ttl_seconds: int = (
            DEFAULT_CACHE_TTL_SECONDS
        ),
        stale_ttl_seconds: int = (
            DEFAULT_STALE_TTL_SECONDS
        ),
        rate_limit_cooldown_seconds: int = (
            DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
        ),
    ) -> None:
        self.provider = (
            provider
            if provider is not None
            else YahooProvider()
        )

        self.cache_directory = Path(
            cache_directory
        )
        self.cache_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.cache_ttl = timedelta(
            seconds=max(
                0,
                int(
                    cache_ttl_seconds
                ),
            )
        )
        self.stale_ttl = timedelta(
            seconds=max(
                0,
                int(
                    stale_ttl_seconds
                ),
            )
        )
        self.rate_limit_cooldown = timedelta(
            seconds=max(
                0,
                int(
                    rate_limit_cooldown_seconds
                ),
            )
        )

        self._memory_cache: dict[
            str,
            CompanySnapshot,
        ] = {}

        self._memory_cache_times: dict[
            str,
            datetime,
        ] = {}

        self._cooldown_until: (
            datetime | None
        ) = None

        self._lock = threading.RLock()

    def get_snapshot(
        self,
        ticker: str,
        *,
        force_refresh: bool = False,
    ) -> CompanySnapshot:
        normalized_ticker = (
            _normalize_ticker(
                ticker
            )
        )

        with self._lock:
            if not force_refresh:
                fresh_snapshot = (
                    self._get_fresh_snapshot(
                        normalized_ticker
                    )
                )

                if fresh_snapshot is not None:
                    return fresh_snapshot

            if self._cooldown_is_active():
                stale_snapshot = (
                    self._get_stale_snapshot(
                        normalized_ticker
                    )
                )

                if stale_snapshot is not None:
                    return self._prepare_cached_snapshot(
                        stale_snapshot,
                        cache_status=(
                            "stale_rate_limit"
                        ),
                        warning=(
                            "Yahoo se encuentra temporalmente "
                            "limitado. Se utiliza el último "
                            "snapshot válido almacenado."
                        ),
                    )

                return self._build_cooldown_snapshot(
                    normalized_ticker
                )

        provider_snapshot = (
            self.provider.get_snapshot(
                normalized_ticker
            )
        )

        with self._lock:
            if _is_rate_limit_snapshot(
                provider_snapshot
            ):
                self._activate_cooldown()

                stale_snapshot = (
                    self._get_stale_snapshot(
                        normalized_ticker
                    )
                )

                if stale_snapshot is not None:
                    return self._prepare_cached_snapshot(
                        stale_snapshot,
                        cache_status=(
                            "stale_after_rate_limit"
                        ),
                        warning=(
                            "Yahoo ha limitado temporalmente "
                            "las solicitudes. Se utiliza el "
                            "último snapshot válido almacenado."
                        ),
                    )

                self._mark_rate_limited_snapshot(
                    provider_snapshot
                )
                return provider_snapshot

            if _is_valid_snapshot(
                provider_snapshot
            ):
                self._store_snapshot(
                    provider_snapshot
                )
                self._clear_cooldown()

            return provider_snapshot

    def _get_fresh_snapshot(
        self,
        ticker: str,
    ) -> CompanySnapshot | None:
        memory_snapshot = (
            self._memory_cache.get(
                ticker
            )
        )
        memory_time = (
            self._memory_cache_times.get(
                ticker
            )
        )

        if (
            memory_snapshot is not None
            and memory_time is not None
            and _utc_now() - memory_time
            <= self.cache_ttl
        ):
            return self._prepare_cached_snapshot(
                memory_snapshot,
                cache_status="memory_fresh",
                warning=(
                    "Se reutiliza un snapshot reciente "
                    "para evitar consultas repetidas."
                ),
            )

        disk_record = (
            self._read_disk_record(
                ticker
            )
        )

        if disk_record is None:
            return None

        stored_at = disk_record.get(
            "stored_at"
        )
        snapshot = disk_record.get(
            "snapshot"
        )

        if (
            not isinstance(
                stored_at,
                datetime,
            )
            or not isinstance(
                snapshot,
                CompanySnapshot,
            )
        ):
            return None

        if (
            _utc_now() - stored_at
            > self.cache_ttl
        ):
            return None

        self._memory_cache[
            ticker
        ] = deepcopy(
            snapshot
        )
        self._memory_cache_times[
            ticker
        ] = stored_at

        return self._prepare_cached_snapshot(
            snapshot,
            cache_status="disk_fresh",
            warning=(
                "Se reutiliza un snapshot reciente "
                "almacenado localmente."
            ),
        )

    def _get_stale_snapshot(
        self,
        ticker: str,
    ) -> CompanySnapshot | None:
        memory_snapshot = (
            self._memory_cache.get(
                ticker
            )
        )
        memory_time = (
            self._memory_cache_times.get(
                ticker
            )
        )

        if (
            memory_snapshot is not None
            and memory_time is not None
            and _utc_now() - memory_time
            <= self.stale_ttl
            and _is_valid_snapshot(
                memory_snapshot
            )
        ):
            return deepcopy(
                memory_snapshot
            )

        disk_record = (
            self._read_disk_record(
                ticker
            )
        )

        if disk_record is None:
            return None

        stored_at = disk_record.get(
            "stored_at"
        )
        snapshot = disk_record.get(
            "snapshot"
        )

        if (
            not isinstance(
                stored_at,
                datetime,
            )
            or not isinstance(
                snapshot,
                CompanySnapshot,
            )
            or not _is_valid_snapshot(
                snapshot
            )
        ):
            return None

        if (
            _utc_now() - stored_at
            > self.stale_ttl
        ):
            return None

        return deepcopy(
            snapshot
        )

    def _store_snapshot(
        self,
        snapshot: CompanySnapshot,
    ) -> None:
        stored_at = _utc_now()
        ticker = _normalize_ticker(
            snapshot.ticker
        )

        stored_snapshot = deepcopy(
            snapshot
        )

        stored_snapshot.provider_metadata[
            "cache"
        ] = {
            "status": "stored",
            "stored_at": (
                stored_at.isoformat()
            ),
        }

        self._memory_cache[
            ticker
        ] = deepcopy(
            stored_snapshot
        )
        self._memory_cache_times[
            ticker
        ] = stored_at

        payload = {
            "schema_version": "1.0.0",
            "ticker": ticker,
            "stored_at": (
                stored_at.isoformat()
            ),
            "snapshot": (
                stored_snapshot.to_dict()
            ),
        }

        target_path = (
            self._snapshot_path(
                ticker
            )
        )
        temporary_path = (
            target_path.with_suffix(
                ".tmp"
            )
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
            temporary_path.replace(
                target_path
            )
        except OSError:
            logger.exception(
                "No se pudo persistir el snapshot de %s.",
                ticker,
            )

            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

    def _read_disk_record(
        self,
        ticker: str,
    ) -> dict[str, Any] | None:
        path = self._snapshot_path(
            ticker
        )

        if not path.exists():
            return None

        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            logger.exception(
                "No se pudo leer la caché de %s.",
                ticker,
            )
            return None

        if not isinstance(
            payload,
            dict,
        ):
            return None

        stored_at = _parse_datetime(
            payload.get(
                "stored_at"
            )
        )
        snapshot = _snapshot_from_dict(
            payload.get(
                "snapshot"
            )
        )

        if (
            stored_at is None
            or snapshot is None
        ):
            return None

        return {
            "stored_at": stored_at,
            "snapshot": snapshot,
        }

    def _snapshot_path(
        self,
        ticker: str,
    ) -> Path:
        safe_ticker = "".join(
            character
            if character.isalnum()
            or character in {
                ".",
                "-",
                "_",
            }
            else "_"
            for character in ticker
        )

        return self.cache_directory / (
            f"{safe_ticker}.json"
        )

    def _prepare_cached_snapshot(
        self,
        snapshot: CompanySnapshot,
        *,
        cache_status: str,
        warning: str,
    ) -> CompanySnapshot:
        cached_snapshot = deepcopy(
            snapshot
        )

        cached_snapshot.provider_metadata[
            "cache"
        ] = {
            "status": cache_status,
            "served_at": (
                _utc_now().isoformat()
            ),
            "is_cached": True,
        }

        cached_snapshot.add_warning(
            warning
        )

        return cached_snapshot

    def _cooldown_is_active(
        self,
    ) -> bool:
        return (
            self._cooldown_until is not None
            and _utc_now()
            < self._cooldown_until
        )

    def _activate_cooldown(
        self,
    ) -> None:
        self._cooldown_until = (
            _utc_now()
            + self.rate_limit_cooldown
        )

        logger.warning(
            "Yahoo ha activado el cooldown hasta %s.",
            self._cooldown_until.isoformat(),
        )

    def _clear_cooldown(
        self,
    ) -> None:
        self._cooldown_until = None

    def _mark_rate_limited_snapshot(
        self,
        snapshot: CompanySnapshot,
    ) -> None:
        snapshot.provider_metadata[
            "rate_limit"
        ] = {
            "active": True,
            "detected_at": (
                _utc_now().isoformat()
            ),
            "cooldown_until": (
                self._cooldown_until.isoformat()
                if self._cooldown_until
                is not None
                else None
            ),
        }

        snapshot.add_warning(
            "Yahoo ha limitado temporalmente "
            "las solicitudes. No se realizarán "
            "nuevos intentos durante el periodo "
            "de enfriamiento."
        )

    def _build_cooldown_snapshot(
        self,
        ticker: str,
    ) -> CompanySnapshot:
        snapshot = CompanySnapshot(
            ticker=ticker,
            source=(
                "Yahoo Finance "
                "(consulta omitida por rate limit)"
            ),
        )

        snapshot.fetched_at = (
            _utc_now().isoformat()
        )
        snapshot.errors = (
            "Yahoo se encuentra temporalmente limitado "
            "y no existe un snapshot válido almacenado."
        )
        snapshot.critical_missing_fields = [
            "price",
            "market_cap",
        ]
        snapshot.missing_fields = [
            "price",
            "market_cap",
        ]
        snapshot.provider_metadata = {
            "provider": "Yahoo Finance",
            "provider_role": "preload",
            "provider_status": "rate_limited",
            "rate_limit": {
                "active": True,
                "cooldown_until": (
                    self._cooldown_until.isoformat()
                    if self._cooldown_until
                    is not None
                    else None
                ),
            },
            "cache": {
                "status": "miss",
                "is_cached": False,
            },
        }

        snapshot.add_warning(
            "No se ha consultado Yahoo porque continúa "
            "activo el periodo de enfriamiento."
        )

        return snapshot
