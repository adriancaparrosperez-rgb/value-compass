from __future__ import annotations

from pathlib import Path
from typing import Any

from src.models import CompanySnapshot
from src.services.snapshot_service import (
    SnapshotService,
)


class FakeProvider:
    def __init__(
        self,
        snapshots: list[CompanySnapshot],
    ) -> None:
        self.snapshots = snapshots
        self.call_count = 0

    def get_snapshot(
        self,
        ticker: str,
    ) -> CompanySnapshot:
        self.call_count += 1

        index = min(
            self.call_count - 1,
            len(self.snapshots) - 1,
        )

        return self.snapshots[
            index
        ]


def _valid_snapshot(
    ticker: str = "META",
) -> CompanySnapshot:
    snapshot = CompanySnapshot(
        ticker=ticker,
        name="Meta Platforms",
        currency="USD",
        price=500.0,
        market_cap=1_200_000_000_000.0,
        source="Fake provider",
    )
    snapshot.fetched_at = (
        "2026-06-27T12:00:00+00:00"
    )
    snapshot.provider_metadata = {
        "provider": "Fake provider",
        "provider_status": "success",
    }

    return snapshot


def _rate_limited_snapshot(
    ticker: str = "META",
) -> CompanySnapshot:
    snapshot = CompanySnapshot(
        ticker=ticker,
        source="Yahoo Finance",
    )
    snapshot.fetched_at = (
        "2026-06-27T12:05:00+00:00"
    )
    snapshot.errors = (
        "Yahoo no devolvió información utilizable "
        "para el ticker solicitado."
    )
    snapshot.critical_missing_fields = [
        "price",
        "market_cap",
    ]
    snapshot.provider_metadata = {
        "provider": "Yahoo Finance",
        "provider_status": "failed",
        "info": {
            "status": "error",
            "exception_type": (
                "YFRateLimitError"
            ),
            "message": (
                "Too Many Requests. "
                "Rate limited."
            ),
        },
    }

    return snapshot


def test_repeated_request_uses_cache(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(
        [
            _valid_snapshot(),
        ]
    )

    service = SnapshotService(
        provider=provider,
        cache_directory=tmp_path,
        cache_ttl_seconds=900,
    )

    first = service.get_snapshot(
        "META"
    )
    second = service.get_snapshot(
        "meta"
    )

    assert first.price == 500.0
    assert second.price == 500.0
    assert provider.call_count == 1
    assert second.provider_metadata[
        "cache"
    ][
        "is_cached"
    ] is True


def test_different_ticker_calls_provider(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(
        [
            _valid_snapshot(
                "META"
            ),
            _valid_snapshot(
                "AAPL"
            ),
        ]
    )

    service = SnapshotService(
        provider=provider,
        cache_directory=tmp_path,
    )

    service.get_snapshot(
        "META"
    )
    service.get_snapshot(
        "AAPL"
    )

    assert provider.call_count == 2


def test_rate_limit_returns_last_valid_snapshot(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(
        [
            _valid_snapshot(),
            _rate_limited_snapshot(),
        ]
    )

    service = SnapshotService(
        provider=provider,
        cache_directory=tmp_path,
        cache_ttl_seconds=0,
        stale_ttl_seconds=86400,
        rate_limit_cooldown_seconds=1800,
    )

    first = service.get_snapshot(
        "META"
    )
    second = service.get_snapshot(
        "META",
        force_refresh=True,
    )

    assert first.price == 500.0
    assert second.price == 500.0
    assert second.errors == ""
    assert provider.call_count == 2
    assert second.provider_metadata[
        "cache"
    ][
        "status"
    ] == "stale_after_rate_limit"


def test_cooldown_avoids_additional_provider_calls(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(
        [
            _rate_limited_snapshot(),
        ]
    )

    service = SnapshotService(
        provider=provider,
        cache_directory=tmp_path,
        cache_ttl_seconds=0,
        rate_limit_cooldown_seconds=1800,
    )

    first = service.get_snapshot(
        "META"
    )
    second = service.get_snapshot(
        "AAPL"
    )

    assert first.errors
    assert second.errors
    assert provider.call_count == 1
    assert second.provider_metadata[
        "provider_status"
    ] == "rate_limited"


def test_disk_cache_survives_new_service_instance(
    tmp_path: Path,
) -> None:
    first_provider = FakeProvider(
        [
            _valid_snapshot(),
        ]
    )

    first_service = SnapshotService(
        provider=first_provider,
        cache_directory=tmp_path,
        cache_ttl_seconds=900,
    )

    first_service.get_snapshot(
        "META"
    )

    second_provider = FakeProvider(
        [
            _rate_limited_snapshot(),
        ]
    )

    second_service = SnapshotService(
        provider=second_provider,
        cache_directory=tmp_path,
        cache_ttl_seconds=900,
    )

    snapshot = second_service.get_snapshot(
        "META"
    )

    assert snapshot.price == 500.0
    assert second_provider.call_count == 0
    assert snapshot.provider_metadata[
        "cache"
    ][
        "status"
    ] == "disk_fresh"


def test_invalid_ticker_does_not_call_provider(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(
        [
            _valid_snapshot(),
        ]
    )

    service = SnapshotService(
        provider=provider,
        cache_directory=tmp_path,
    )

    try:
        service.get_snapshot(
            "   "
        )
    except ValueError as error:
        assert (
            "no puede estar vacío"
            in str(error)
        )
    else:
        raise AssertionError(
            "Se esperaba ValueError."
        )

    assert provider.call_count == 0
