import pandas as pd
import ta

def calculate_indicators(df: pd.DataFrame) -> dict:
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

    macd = ta.trend.MACD(df["close"], window_fast=12, window_slow=26, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    bb = ta.volatility.BollingerBands(df["close"], window=20)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()

    df["ema_20"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema_50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()

   latest = df.iloc[-1]
    prev = df.iloc[-2]

    vol_latest = float(latest["volume"])
    vol_prev = float(prev["volume"])
    
    # Hindari division by zero
    price_change = 0.0
    if float(prev["close"]) != 0:
        price_change = round(
            (float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100, 3
        )

    return {
        "current_price": round(float(latest["close"]), 4),
        "rsi": round(float(latest["rsi"]), 2),
        "macd": round(float(latest["macd"]), 6),
        "macd_signal": round(float(latest["macd_signal"]), 6),
        "macd_histogram": round(float(latest["macd_hist"]), 6),
        "bb_upper": round(float(latest["bb_upper"]), 4),
        "bb_lower": round(float(latest["bb_lower"]), 4),
        "ema_20": round(float(latest["ema_20"]), 4),
        "ema_50": round(float(latest["ema_50"]), 4),
        "volume_latest": vol_latest,
        "volume_prev": vol_prev,
        "price_change_pct": price_change,
    }