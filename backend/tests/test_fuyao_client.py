import io
import json
from datetime import date
from urllib.error import HTTPError

import pytest

from tick.market.fuyao_client import (
    FuyaoApiError,
    fetch_all_tickers,
    fetch_ticker_list_page,
    fetch_trading_day_range,
    trading_day_windows,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_fetch_ticker_list_page_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=60.0):  # noqa: ARG001
        assert request.get_header("X-api-key") == "test-key"
        assert "asset_type=a-share" in request.full_url
        assert "limit=2" in request.full_url
        assert "offset=0" in request.full_url
        return _FakeResponse(
            {
                "code": 0,
                "message": "success",
                "data": {
                    "timestamp": 123,
                    "item": [{"thscode": "600519.SH"}],
                },
            }
        )

    monkeypatch.setattr(
        "tick.market.fuyao_client.urllib.request.urlopen",
        fake_urlopen,
    )
    items, snapshot_ms = fetch_ticker_list_page(
        base_url="https://fuyao.example",
        api_key="test-key",
        asset_type="a-share",
        limit=2,
        offset=0,
    )
    assert items == [{"thscode": "600519.SH"}]
    assert snapshot_ms == 123


def test_fetch_ticker_list_page_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=60.0):  # noqa: ARG001
        return _FakeResponse({"code": 2001, "message": "invalid key", "data": None})

    monkeypatch.setattr(
        "tick.market.fuyao_client.urllib.request.urlopen",
        fake_urlopen,
    )
    with pytest.raises(FuyaoApiError, match="code=2001"):
        fetch_ticker_list_page(
            base_url="https://fuyao.example",
            api_key="bad",
        )


def test_fetch_all_tickers_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_urlopen(request, timeout=60.0):  # noqa: ARG001
        offset = int(request.full_url.split("offset=")[1].split("&")[0])
        calls.append(offset)
        if offset == 0:
            items = [{"thscode": "A"}, {"thscode": "B"}]
        else:
            items = [{"thscode": "C"}]
        return _FakeResponse(
            {
                "code": 0,
                "message": "success",
                "data": {"timestamp": 9, "item": items},
            }
        )

    monkeypatch.setattr(
        "tick.market.fuyao_client.urllib.request.urlopen",
        fake_urlopen,
    )
    items, snapshot_ms = fetch_all_tickers(
        base_url="https://fuyao.example",
        api_key="k",
        asset_types=["a-share"],
        limit=2,
    )
    assert calls == [0, 2]
    assert [row["thscode"] for row in items] == ["A", "B", "C"]
    assert snapshot_ms == 9


def test_fetch_ticker_list_page_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=60.0):  # noqa: ARG001
        raise HTTPError(
            request.full_url,
            500,
            "server error",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b"boom"),
        )

    monkeypatch.setattr(
        "tick.market.fuyao_client.urllib.request.urlopen",
        fake_urlopen,
    )
    with pytest.raises(FuyaoApiError, match="HTTP 500"):
        fetch_ticker_list_page(base_url="https://fuyao.example", api_key="k")


def test_ten_year_window_stops_on_the_anniversary() -> None:
    assert trading_day_windows(date(2020, 2, 29), date(2030, 2, 28)) == [
        (date(2020, 2, 29), date(2030, 2, 28))
    ]
    assert trading_day_windows(date(2016, 11, 17), date(2026, 11, 23)) == [
        (date(2016, 11, 17), date(2026, 11, 17)),
        (date(2026, 11, 18), date(2026, 11, 23)),
    ]


def test_fetch_trading_day_range_splits_ten_year_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []

    def fake_urlopen(request, timeout=60.0):  # noqa: ARG001
        urls.append(request.full_url)
        return _FakeResponse(
            {
                "code": 0,
                "message": "success",
                "data": {"timestamp": 5, "item": []},
            }
        )

    monkeypatch.setattr(
        "tick.market.fuyao_client.urllib.request.urlopen",
        fake_urlopen,
    )
    items, snapshot_ms = fetch_trading_day_range(
        base_url="https://fuyao.example",
        api_key="test-key",
        start=date(2016, 11, 17),
        end=date(2026, 11, 23),
    )
    assert items == []
    assert snapshot_ms == 5
    assert urls == [
        "https://fuyao.example/api/a-share/calendar/trading-days"
        "?start_date=20161117&end_date=20261117",
        "https://fuyao.example/api/a-share/calendar/trading-days"
        "?start_date=20261118&end_date=20261123",
    ]
