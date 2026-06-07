import requests
import pandas as pd

BASE_URL = "https://api.coingecko.com/api/v3"

TIMEFRAME_MAP = {
    "1h": 1, "4h": 1, "1d": 7, "1w": 30,
}

def search_coin(query: str) -> tuple:
    """Cari coin ID dari nama/symbol."""
    url = f"{BASE_URL}/search"
    response = requests.get(url, params={"query": query}, timeout=15)
    data = response.json()
    coins = data.get("coins", [])
    if not coins:
        return None, None
    top = coins[0]
    return top["id"], top["name"]

def get_ohlcv(coin_id: str, timeframe: str, limit: int) -> pd.DataFrame:
    days = TIMEFRAME_MAP.get(timeframe, 1)
    url = f"{BASE_URL}/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": days}
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["volume"] = 0.0
    return df

def get_ticker(coin_id: str) -> dict:
    url = f"{BASE_URL}/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"}
    response = requests.get(url, params=params, timeout=15)
    data = response.json()
    return {
        "lastPrice": str(data[coin_id]["usd"]),
        "priceChangePercent": str(data[coin_id].get("usd_24h_change", 0))
    }