"""HTTP client for the Fuyao gateway (THS / 同花顺 meta ticker-list API)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 1000
MAX_LIMIT = 10_000


class FuyaoApiError(RuntimeError):
    """Raised when Fuyao returns a non-success envelope or HTTP failure."""


def fetch_ticker_list_page(
    *,
    base_url: str,
    api_key: str,
    asset_type: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    timeout_s: float = 60.0,
) -> tuple[list[dict[str, Any]], int | None]:
    """Fetch one page of ``GET /api/meta/tickers/list``.

    Returns ``(items, snapshot_timestamp_ms)``.
    """
    if not api_key.strip():
        raise ValueError("Fuyao API key is empty")
    if limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be in 1..{MAX_LIMIT}, got {limit}")
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")

    query: dict[str, str] = {
        "limit": str(limit),
        "offset": str(offset),
    }
    if asset_type:
        query["asset_type"] = asset_type

    url = (
        f"{base_url.rstrip('/')}/api/meta/tickers/list"
        f"?{urllib.parse.urlencode(query)}"
    )
    request = urllib.request.Request(
        url,
        headers={"X-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise FuyaoApiError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise FuyaoApiError(f"request failed: {exc.reason}") from exc

    if not isinstance(payload, dict):
        raise FuyaoApiError("response is not a JSON object")
    code = payload.get("code")
    if code != 0:
        raise FuyaoApiError(
            f"Fuyao error code={code} message={payload.get('message')!r}"
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise FuyaoApiError("response.data is missing or not an object")
    items = data.get("item")
    if not isinstance(items, list):
        raise FuyaoApiError("response.data.item is missing or not a list")

    timestamp = data.get("timestamp")
    snapshot_ms = timestamp if isinstance(timestamp, int) else None
    return items, snapshot_ms


def fetch_all_tickers(
    *,
    base_url: str,
    api_key: str,
    asset_types: Sequence[str] | None = None,
    limit: int = DEFAULT_LIMIT,
    timeout_s: float = 60.0,
) -> tuple[list[dict[str, Any]], int | None]:
    """Page through ticker list until exhausted.

    When ``asset_types`` is empty/None, omit the filter (vendor returns all types).
    When multiple types are given, they are sent as a comma-separated
    ``asset_type`` query (Fuyao supports multi-value).
    """
    asset_type_param: str | None = None
    if asset_types:
        asset_type_param = ",".join(asset_types)

    all_items: list[dict[str, Any]] = []
    snapshot_ms: int | None = None
    offset = 0

    while True:
        logger.info(
            "fetching Fuyao tickers offset=%s limit=%s asset_type=%s",
            offset,
            limit,
            asset_type_param or "*",
        )
        page, page_ts = fetch_ticker_list_page(
            base_url=base_url,
            api_key=api_key,
            asset_type=asset_type_param,
            limit=limit,
            offset=offset,
            timeout_s=timeout_s,
        )
        if page_ts is not None:
            snapshot_ms = page_ts
        all_items.extend(page)
        if len(page) < limit:
            break
        offset += limit

    logger.info("fetched %s Fuyao tickers", len(all_items))
    return all_items, snapshot_ms
