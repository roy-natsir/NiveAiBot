import time
from typing import Optional

import pandas as pd
import requests

BASE_URL = "https://api.coingecko.com/api/v3"
USER_AGENT = "trading-bot/1.0"

TIMEFRAME_MAP = {
    "1h": 1, "4h": 1, "1d": 7, "1w": 30,
}

SEARCH_CACHE_TTL = 60 * 60 * 24
OHLCV_CACHE_TTL = 60 * 5
TICKER_CACHE_TTL = 5
MARKET_CHART_1D_CACHE_TTL = 60
MARKET_CHART_7D_CACHE_TTL = 60 * 5
MAX_RETRIES = 3

_session = requests.Session()
_cache = {}


class CoinGeckoRateLimitError(RuntimeError):
    """Raised when CoinGecko refuses requests because the rate limit is hit."""


def _copy_cached(value):
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, dict):
        return value.copy()
    return value


def _get_cached(key, ttl: int, allow_stale: bool = False):
    cached = _cache.get(key)
    if not cached:
        return None

    saved_at, value = cached
    is_fresh = time.time() - saved_at < ttl
    if is_fresh or allow_stale:
        return _copy_cached(value)
    return None


def _set_cached(key, value):
    _cache[key] = (time.time(), _copy_cached(value))


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


def _request_json(path: str, params: dict, cache_key: tuple, cache_ttl: int, force_refresh: bool = False):
    if not force_refresh:
        cached = _get_cached(cache_key, cache_ttl)
        if cached is not None:
            return cached

    url = f"{BASE_URL}{path}"
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = _session.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )

            if response.status_code == 429:
                stale = _get_cached(cache_key, cache_ttl, allow_stale=True)
                if stale is not None:
                    return stale

                retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                wait_seconds = retry_after if retry_after is not None else 2 ** attempt
                if attempt < MAX_RETRIES - 1:
                    time.sleep(min(wait_seconds, 10))
                    continue

                raise CoinGeckoRateLimitError(
                    "CoinGecko sedang membatasi request. Coba lagi beberapa menit lagi."
                )

            response.raise_for_status()
            data = response.json()
            _set_cached(cache_key, data)
            return data

        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue

    if last_error:
        raise last_error
    raise RuntimeError("Gagal mengambil data CoinGecko.")


def search_coin(query: str) -> tuple:
    """Cari coin ID dari nama/symbol."""
    query = query.strip().lower()
    data = _request_json(
        "/search",
        {"query": query},
        ("search", query),
        SEARCH_CACHE_TTL,
    )
    coins = data.get("coins", [])
    if not coins:
        return None, None
    top = coins[0]
    return top["id"], top["name"]

def get_ohlcv(coin_id: str, timeframe: str, limit: int) -> pd.DataFrame:
    days = TIMEFRAME_MAP.get(timeframe, 1)
    params = {"vs_currency": "usd", "days": days}
    data = _request_json(
        f"/coins/{coin_id}/ohlc",
        params,
        ("ohlcv", coin_id, timeframe, days),
        OHLCV_CACHE_TTL,
    )
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["volume"] = 0.0
    if limit:
        df = df.tail(limit)
    return df

def get_ticker(coin_id: str, force_refresh: bool = False) -> dict:
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_last_updated_at": "true",
    }
    data = _request_json(
        "/simple/price",
        params,
        ("ticker", coin_id),
        TICKER_CACHE_TTL,
        force_refresh=force_refresh,
    )
    
    if coin_id not in data:
        return {"lastPrice": "0", "priceChangePercent": "0", "lastUpdatedAt": None}
    
    return {
        "lastPrice": str(data[coin_id].get("usd", 0)),
        "priceChangePercent": str(data[coin_id].get("usd_24h_change", 0)),
        "lastUpdatedAt": data[coin_id].get("last_updated_at"),
    }


def _price_before(prices: list, target_ms: int):
    if not prices:
        return None

    for timestamp, price in reversed(prices):
        if int(timestamp) <= target_ms:
            return float(price)

    return float(prices[0][1])


def _percent_change(current_price: float, past_price) -> float:
    if past_price is None or past_price <= 0:
        return 0.0
    return round((current_price - past_price) / past_price * 100, 3)


def get_market_chart_prices(coin_id: str, days: int) -> list:
    ttl = MARKET_CHART_1D_CACHE_TTL if days <= 1 else MARKET_CHART_7D_CACHE_TTL
    data = _request_json(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": days},
        ("market_chart", coin_id, days),
        ttl,
    )
    return data.get("prices", [])


def get_price_summary(coin_id: str, force_live: bool = False) -> dict:
    ticker = get_ticker(coin_id, force_refresh=force_live)
    current_price = float(ticker.get("lastPrice", 0) or 0)

    prices_1d = get_market_chart_prices(coin_id, 1)
    prices_7d = get_market_chart_prices(coin_id, 7)
    latest_timestamp = int(prices_1d[-1][0]) if prices_1d else int(time.time() * 1000)

    changes = {
        "24H": round(float(ticker.get("priceChangePercent", 0) or 0), 3),
        "15m": _percent_change(
            current_price,
            _price_before(prices_1d, latest_timestamp - 15 * 60 * 1000),
        ),
        "1h": _percent_change(
            current_price,
            _price_before(prices_1d, latest_timestamp - 60 * 60 * 1000),
        ),
        "4h": _percent_change(
            current_price,
            _price_before(prices_1d, latest_timestamp - 4 * 60 * 60 * 1000),
        ),
        "1D": _percent_change(
            current_price,
            _price_before(prices_1d, latest_timestamp - 24 * 60 * 60 * 1000),
        ),
        "7D": _percent_change(
            current_price,
            _price_before(prices_7d, latest_timestamp - 7 * 24 * 60 * 60 * 1000),
        ),
    }

    return {
        "lastPrice": current_price,
        "lastUpdatedAt": ticker.get("lastUpdatedAt"),
        "changes": changes,
    }
