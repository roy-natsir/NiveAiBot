import time
from config import TRADING_PAIRS, TIMEFRAME, CANDLE_LIMIT, SCAN_INTERVAL
from market_data import get_ohlcv
from indicators import calculate_indicators
from niveai_analyst import ask_niveai
from dashboard import print_signal

def analyze_pair(symbol: str):
    print(f"  → Fetching {symbol}...")
    df = get_ohlcv(symbol, TIMEFRAME, CANDLE_LIMIT)
    indicators = calculate_indicators(df)
    analysis = ask_niveai(symbol, TIMEFRAME, indicators)
    print_signal(symbol, TIMEFRAME, indicators, analysis)

def main():
    print("\n🤖 Trading Agent started. Press Ctrl+C to stop.\n")
    while True:
        print(f"⏳ Scanning {len(TRADING_PAIRS)} pairs...")
        for pair in TRADING_PAIRS:
            try:
                analyze_pair(pair)
                time.sleep(2)
            except Exception as e:
                print(f"  ✗ Error pada {pair}: {e}")

        print(f"\n💤 Menunggu {SCAN_INTERVAL // 60} menit...\n")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
