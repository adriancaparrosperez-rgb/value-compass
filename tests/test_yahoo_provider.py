def test_successful_components_record_useful_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    fast_metadata = snapshot.provider_metadata[
        "fast_info"
    ]
    info_metadata = snapshot.provider_metadata[
        "info"
    ]

    assert fast_metadata[
        "status"
    ] == "success"
    assert fast_metadata[
        "usable"
    ] is True
    assert fast_metadata[
        "useful_fields"
    ] == [
        "last_price",
        "market_cap",
        "last_price_time",
    ]
    assert fast_metadata[
        "useful_field_count"
    ] == len(
        fast_metadata[
            "useful_fields"
        ]
    )
    assert "last_price" in fast_metadata[
        "available_keys"
    ]
    assert "market_cap" in fast_metadata[
        "available_keys"
    ]

    assert info_metadata[
        "status"
    ] == "success"
    assert info_metadata[
        "usable"
    ] is True
    assert "currentPrice" in info_metadata[
        "useful_fields"
    ]
    assert "marketCap" in info_metadata[
        "useful_fields"
    ]
    assert "totalRevenue" in info_metadata[
        "useful_fields"
    ]
    assert info_metadata[
        "useful_field_count"
    ] == len(
        info_metadata[
            "useful_fields"
        ]
    )


def test_info_with_invalid_format_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=[
            "invalid",
        ],
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    info_metadata = snapshot.provider_metadata[
        "info"
    ]

    assert info_metadata[
        "loaded"
    ] is True
    assert info_metadata[
        "status"
    ] == "invalid_format"
    assert info_metadata[
        "returned_type"
    ] == "list"
    assert snapshot.provider_metadata[
        "info_available"
    ] is False
    assert snapshot.provider_metadata[
        "info_usable"
    ] is False
    assert snapshot.provider_metadata[
        "fast_info_usable"
    ] is True
    assert snapshot.provider_metadata[
        "provider_status"
    ] == "partial"
    assert snapshot.price == 101.0
    assert snapshot.errors == ""

    assert any(
        "formato no válido"
        in warning.casefold()
        for warning in snapshot.warnings
    )


def test_none_fast_info_is_recorded_as_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info=None,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    fast_metadata = snapshot.provider_metadata[
        "fast_info"
    ]

    assert fast_metadata[
        "loaded"
    ] is True
    assert fast_metadata[
        "status"
    ] == "empty"
    assert fast_metadata[
        "usable"
    ] is False
    assert snapshot.provider_metadata[
        "fast_info_available"
    ] is False
    assert snapshot.provider_metadata[
        "fast_info_usable"
    ] is False
    assert snapshot.provider_metadata[
        "info_usable"
    ] is True
    assert snapshot.provider_metadata[
        "provider_status"
    ] == "partial"
    assert snapshot.price == 100.0
    assert snapshot.market_cap == 1_000_000_000.0


def test_none_info_is_recorded_as_invalid_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ticker = FakeYahooTicker(
        info=None,
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    info_metadata = snapshot.provider_metadata[
        "info"
    ]

    assert info_metadata[
        "loaded"
    ] is True
    assert info_metadata[
        "status"
    ] == "invalid_format"
    assert info_metadata[
        "returned_type"
    ] == "NoneType"
    assert snapshot.provider_metadata[
        "info_usable"
    ] is False
    assert snapshot.provider_metadata[
        "fast_info_usable"
    ] is True
    assert snapshot.provider_metadata[
        "provider_status"
    ] == "partial"
    assert snapshot.name == "TEST"
    assert snapshot.price == 101.0
    assert snapshot.errors == ""


def test_fast_info_price_date_has_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    fast_info = _valid_fast_info()

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.price_date == (
        _unix_timestamp_to_iso(
            fast_info[
                "last_price_time"
            ]
        )
    )
    assert snapshot.price_date != (
        _unix_timestamp_to_iso(
            info[
                "regularMarketTime"
            ]
        )
    )
    assert snapshot.provider_metadata[
        "price_observation_complete"
    ] is True


def test_info_price_date_is_used_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    fast_info = _valid_fast_info()
    fast_info[
        "last_price_time"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.price == 101.0
    assert snapshot.price_date == (
        _unix_timestamp_to_iso(
            info[
                "regularMarketTime"
            ]
        )
    )
    assert snapshot.provider_metadata[
        "price_observation_complete"
    ] is True


def test_price_observation_is_incomplete_without_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "regularMarketTime"
    ] = None

    fast_info = _valid_fast_info()
    fast_info[
        "last_price_time"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.price == 101.0
    assert snapshot.price_date is None
    assert snapshot.provider_metadata[
        "price_observation_complete"
    ] is False


def test_exception_message_is_sanitized_and_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_message = (
        "first line\n"
        "second line\r"
        + "x" * 1_000
    )

    fake_ticker = FakeYahooTicker(
        info_error=RuntimeError(
            long_message
        ),
        fast_info=_valid_fast_info(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    stored_message = snapshot.provider_metadata[
        "info"
    ][
        "message"
    ]

    assert "\n" not in stored_message
    assert "\r" not in stored_message
    assert len(
        stored_message
    ) <= 500
    assert snapshot.provider_metadata[
        "info"
    ][
        "exception_type"
    ] == "RuntimeError"


def test_fast_info_object_with_get_method_is_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FastInfoObject:
        def __init__(
            self,
        ) -> None:
            self._values = {
                "last_price": 205.0,
                "market_cap": 2_050_000_000.0,
                "last_price_time": 1_750_200_000,
            }

        def get(
            self,
            key: str,
        ) -> Any:
            return self._values.get(
                key
            )

        def keys(
            self,
        ) -> Any:
            return self._values.keys()

    fake_ticker = FakeYahooTicker(
        info=_valid_info(),
        fast_info=FastInfoObject(),
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.price == 205.0
    assert snapshot.market_cap == 2_050_000_000.0
    assert snapshot.provider_metadata[
        "fast_info_usable"
    ] is True
    assert snapshot.provider_metadata[
        "fast_info"
    ][
        "status"
    ] == "success"
    assert snapshot.provider_metadata[
        "fast_info"
    ][
        "useful_field_count"
    ] == 3
    assert "last_price" in snapshot.provider_metadata[
        "fast_info"
    ][
        "available_keys"
    ]


def test_fetch_timestamp_is_not_used_as_price_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info = _valid_info()
    info[
        "regularMarketTime"
    ] = None

    fast_info = _valid_fast_info()
    fast_info[
        "last_price_time"
    ] = None

    fake_ticker = FakeYahooTicker(
        info=info,
        fast_info=fast_info,
    )

    _patch_ticker(
        monkeypatch,
        fake_ticker,
    )

    snapshot = YahooProvider().get_snapshot(
        "TEST"
    )

    assert snapshot.fetched_at is not None
    assert snapshot.price_date is None
    assert snapshot.price_date != snapshot.fetched_at
