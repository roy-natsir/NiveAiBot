from datetime import datetime

COLORS = {
    "BUY":   "\033[92m",
    "SELL":  "\033[91m",
    "HOLD":  "\033[93m",
    "RESET": "\033[0m",
    "BOLD":  "\033[1m",
    "DIM":   "\033[2m",
}

def print_signal(symbol: str, timeframe: str, indicators: dict, analysis: dict):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if "error" in analysis:
        print(f"\n[{now}] ERROR {symbol}: {analysis['error']}")
        return

    signal     = analysis.get("signal", "UNKNOWN")
    confidence = analysis.get("confidence", "-")
    reason     = analysis.get("reason", "-")
    risk       = analysis.get("key_risk", "-")

    color = COLORS.get(signal, "")
    reset = COLORS["RESET"]
    bold  = COLORS["BOLD"]
    dim   = COLORS["DIM"]

    print(f"""
{bold}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{reset}
{bold}  {symbol} | {timeframe} | {now}{reset}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Price  : {indicators['current_price']}  ({'+' if indicators['price_change_pct'] > 0 else ''}{indicators['price_change_pct']}%)
  RSI    : {indicators['rsi']}
  MACD   : {indicators['macd']}  hist: {indicators['macd_histogram']}
  EMA    : 20={indicators['ema_20']}  50={indicators['ema_50']}
  BB     : upper={indicators['bb_upper']}  lower={indicators['bb_lower']}
  Volume : {indicators['volume_latest']}  (prev: {indicators['volume_prev']})

  {bold}SIGNAL     : {color}{signal}{reset}{bold}  [{confidence} confidence]{reset}
  Reason   : {reason}
  Key Risk : {dim}{risk}{reset}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")