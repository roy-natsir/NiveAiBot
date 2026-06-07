import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from market_data import get_ohlcv, get_ticker
from indicators import calculate_indicators
from hermes_analyst import ask_hermes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "4h", "1d": "1d",
    "hari ini": "1d", "harian": "1d",
    "1 jam": "1h", "4 jam": "4h",
}

COIN_MAP = {
    "btc": "BTC/USDT", "bitcoin": "BTC/USDT",
    "eth": "ETH/USDT", "ethereum": "ETH/USDT",
    "bnb": "BNB/USDT",
    "sol": "SOL/USDT", "solana": "SOL/USDT",
    "xrp": "XRP/USDT",
    "doge": "DOGE/USDT", "dogecoin": "DOGE/USDT",
    "ada": "ADA/USDT", "cardano": "ADA/USDT",
    "avax": "AVAX/USDT",
    "matic": "MATIC/USDT", "polygon": "MATIC/USDT",
    "link": "LINK/USDT",
}

def parse_message(text: str):
    text = text.lower()

    # Deteksi symbol
    symbol = None
    for key, val in COIN_MAP.items():
        if key in text:
            symbol = val
            break

    # Deteksi timeframe
    timeframe = "1h"  # default
    for key, val in TIMEFRAME_MAP.items():
        if key in text:
            timeframe = val
            break

    return symbol, timeframe

def format_signal(symbol: str, timeframe: str, indicators: dict, analysis: dict) -> str:
    if "error" in analysis:
        return f"❌ Error analisa: {analysis['error']}"

    signal = analysis.get("signal", "?")
    confidence = analysis.get("confidence", "?")
    reason = analysis.get("reason", "-")
    risk = analysis.get("key_risk", "-")

    signal_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(signal, "⚪")
    conf_emoji = {"High": "🔥", "Medium": "✅", "Low": "⚠️"}.get(confidence, "")

    price_change = indicators['price_change_pct']
    change_emoji = "📈" if price_change > 0 else "📉"

    return f"""
📊 *Analisa {symbol}* | `{timeframe}`
━━━━━━━━━━━━━━━━━━━━

💰 *Harga*: `{indicators['current_price']}` {change_emoji} `{'+' if price_change > 0 else ''}{price_change}%`

📉 *Indikator Teknikal*
- RSI (14): `{indicators['rsi']}`
- MACD: `{indicators['macd']}`
- MACD Signal: `{indicators['macd_signal']}`
- MACD Histogram: `{indicators['macd_histogram']}`
- EMA 20: `{indicators['ema_20']}`
- EMA 50: `{indicators['ema_50']}`
- BB Upper: `{indicators['bb_upper']}`
- BB Lower: `{indicators['bb_lower']}`
- Volume: `{indicators['volume_latest']}` (prev: `{indicators['volume_prev']}`)

🤖 *Sinyal AI*
- Signal: {signal_emoji} *{signal}*
- Confidence: {conf_emoji} `{confidence}`
- Alasan: _{reason}_
- Key Risk: _{risk}_
━━━━━━━━━━━━━━━━━━━━
_Bukan financial advice. DYOR._
"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Cek apakah user diizinkan
    if user_id != ALLOWED_USER_ID:
        await update.message.reply_text("⛔ Akses ditolak.")
        return

    text = update.message.text
    symbol, timeframe = parse_message(text)

    if not symbol:
        await update.message.reply_text(
            "❓ Coin tidak dikenali.\n\n"
            "Contoh perintah:\n"
            "• analisa btc\n"
            "• analisa eth 4h\n"
            "• sinyal solana hari ini\n"
            "• cek bnb 1h"
        )
        return

    # Kirim pesan loading
    loading_msg = await update.message.reply_text(
        f"⏳ Menganalisa {symbol} ({timeframe})..."
    )

    try:
        df = get_ohlcv(symbol, timeframe, 100)
        indicators = calculate_indicators(df)
        analysis = ask_hermes(symbol, timeframe, indicators)
        result = format_signal(symbol, timeframe, indicators, analysis)

        await loading_msg.delete()
        await update.message.reply_text(result, parse_mode="Markdown")

    except Exception as e:
        await loading_msg.delete()
        await update.message.reply_text(f"❌ Error: {str(e)}")

def main():
    print("🤖 Trading Signal Bot started...")
    print("Kirim pesan ke bot Telegram kamu untuk mulai analisa.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot berjalan. Tekan Ctrl+C untuk stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()