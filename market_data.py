import requests
import pandas as pd

BASE_URL = "https://api.binance.us/api/v3"

SYMBOL_MAP = {
    "BTC/USDT": "BTCUSDT",
    "ETH/USDT": "ETHUSDT",
    "BNB/USDT": "BNBUSDT",
    "SOL/USDT": "SOLUSDT",
    "XRP/USDT": "XRPUSDT",
    "DOGE/USDT": "DOGEUSDT",
    "ADA/USDT": "ADAUSDT",
    "AVAX/USDT": "AVAXUSDT",
    "MATIC/USDT": "MATICUSDT",
    "LINK/USDT": "LINKUSDT",
}

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "4h", "1d": "1d",
}

def get_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    binance_symbol = SYMBOL_MAP.get(symbol, "BTCUSDT")
    interval = TIMEFRAME_MAP.get(timeframe, "1h")

    url = f"{BASE_URL}/klines"
    params = {
        "symbol": binance_symbol,
        "interval": interval,
        "limit": limit,
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["open"]   = df["open"].astype(float)
    df["high"]   = df["high"].astype(float)
    df["low"]    = df["low"].astype(float)
    df["close"]  = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)

    return df[["timestamp", "open", "high", "low", "close", "volume"]]

def get_ticker(symbol: str) -> dict:
    binance_symbol = SYMBOL_MAP.get(symbol, "BTCUSDT")
    url = f"{BASE_URL}/ticker/24hr"
    response = requests.get(url, params={"symbol": binance_symbol}, timeout=15)
    return response.json()