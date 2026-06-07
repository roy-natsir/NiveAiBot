import requests
import pandas as pd
import time

TIMEFRAME_MAP = {
    "1m": "1", "5m": "5", "15m": "15",
    "1h": "60", "4h": "240", "1d": "D",
}

SYMBOL_MAP = {
    "BTC/USDT": "btcidr",
    "ETH/USDT": "ethidr",
    "BNB/USDT": "bnbidr",
    "SOL/USDT": "solidr",
    "XRP/USDT": "xrpidr",
    "DOGE/USDT": "dogeidr",
    "ADA/USDT": "adaidr",
    "AVAX/USDT": "avaxidr",
    "MATIC/USDT": "maticidr",
    "LINK/USDT": "linkidr",
}

SECONDS_MAP = {
    "1m": 60, "5m": 300, "15m": 900,
    "1h": 3600, "4h": 14400, "1d": 86400,
}

def get_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    pair = SYMBOL_MAP.get(symbol, "btcidr")
    resolution = TIMEFRAME_MAP.get(timeframe, "60")
    seconds = SECONDS_MAP.get(timeframe, 3600)

    to_time = int(time.time())
    from_time = to_time - (limit * seconds)

    url = "https://indodax.com/tradingview/history"
    params = {
        "symbol": pair.upper(),
        "resolution": resolution,
        "from": from_time,
        "to": to_time,
    }

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    if data.get("s") != "ok":
        raise ValueError(f"Indodax API error: {data.get('s')} — {data}")

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(data["t"], unit="s"),
        "open": [float(x) for x in data["o"]],
        "high": [float(x) for x in data["h"]],
        "low":  [float(x) for x in data["l"]],
        "close": [float(x) for x in data["c"]],
        "volume": [float(x) for x in data["v"]],
    })
    return df

def get_ticker(symbol: str) -> dict:
    pair = SYMBOL_MAP.get(symbol, "btcidr")
    url = f"https://indodax.com/api/ticker/{pair}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    return response.json()