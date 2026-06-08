import html
import os
import re
from typing import Optional, Tuple

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from niveai_analyst import analyze_chart_image, ask_chat
from market_data import CoinGeckoRateLimitError, get_price_summary, search_coin

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

DEFAULT_TIMEFRAME = "1h"
SUPPORTED_TIMEFRAMES = ("1h", "4h", "1d", "1w")
TIMEFRAME_ALIASES = {
    "1h": "1h",
    "1 jam": "1h",
    "1j": "1h",
    "jam": "1h",
    "4h": "4h",
    "4 jam": "4h",
    "4j": "4h",
    "1d": "1d",
    "1 day": "1d",
    "daily": "1d",
    "hari ini": "1d",
    "harian": "1d",
    "1w": "1w",
    "1 week": "1w",
    "weekly": "1w",
    "mingguan": "1w",
}

STOP_WORDS = {
    "analisa",
    "analisis",
    "analyze",
    "cek",
    "check",
    "sinyal",
    "signal",
    "coin",
    "token",
    "harga",
    "price",
    "prediksi",
}

ANALYZE_WORDS = {
    "analisa",
    "analisis",
    "analyze",
    "cek",
    "check",
    "sinyal",
    "signal",
    "prediksi",
}

PRICE_WORDS = {"harga", "price"}

MARKET_CONTEXT_WORDS = {
    "sekarang",
    "gimana",
    "bagus",
    "buy",
    "sell",
    "hold",
    "entry",
    "masuk",
    "target",
    "tp",
    "sl",
    "support",
    "resistance",
    "resisten",
    "breakout",
    "dump",
    "pump",
}

COMMON_COINS = {
    "btc": ("bitcoin", "Bitcoin"),
    "bitcoin": ("bitcoin", "Bitcoin"),
    "eth": ("ethereum", "Ethereum"),
    "ethereum": ("ethereum", "Ethereum"),
    "bnb": ("binancecoin", "BNB"),
    "sol": ("solana", "Solana"),
    "solana": ("solana", "Solana"),
    "xrp": ("ripple", "XRP"),
    "doge": ("dogecoin", "Dogecoin"),
    "dogecoin": ("dogecoin", "Dogecoin"),
    "ada": ("cardano", "Cardano"),
    "cardano": ("cardano", "Cardano"),
    "avax": ("avalanche-2", "Avalanche"),
    "avalanche": ("avalanche-2", "Avalanche"),
    "matic": ("matic-network", "Polygon"),
    "polygon": ("matic-network", "Polygon"),
    "pol": ("polygon-ecosystem-token", "Polygon Ecosystem Token"),
    "link": ("chainlink", "Chainlink"),
    "pepe": ("pepe", "Pepe"),
    "shib": ("shiba-inu", "Shiba Inu"),
    "shiba": ("shiba-inu", "Shiba Inu"),
}

COIN_SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "binancecoin": "BNB",
    "solana": "SOL",
    "ripple": "XRP",
    "dogecoin": "DOGE",
    "cardano": "ADA",
    "avalanche-2": "AVAX",
    "matic-network": "MATIC",
    "polygon-ecosystem-token": "POL",
    "chainlink": "LINK",
    "pepe": "PEPE",
    "shiba-inu": "SHIB",
}


def is_allowed(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ALLOWED_USER_ID)


async def reject_if_unauthorized(update: Update) -> bool:
    if is_allowed(update):
        return False
    if update.message:
        await update.message.reply_text("Akses ditolak.")
    return True


def normalize_query(query: str) -> str:
    query = query.lower().strip()
    query = query.replace("$", "")
    query = re.sub(r"\b(usdt|usd|busd|usdc)\b", " ", query)
    query = re.sub(r"[/_-]", " ", query)
    query = re.sub(r"\s+", " ", query)
    return query.strip()


def parse_message(text: str) -> Tuple[str, str]:
    text_lower = normalize_query(text)
    timeframe = DEFAULT_TIMEFRAME

    for alias, value in sorted(TIMEFRAME_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text_lower):
            timeframe = value
            text_lower = re.sub(rf"\b{re.escape(alias)}\b", " ", text_lower)
            break

    words = [word for word in text_lower.split() if word not in STOP_WORDS]
    query = " ".join(words).strip()
    return query, timeframe


def format_number(value: float, decimals: int = 6) -> str:
    value = float(value)
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:,.4f}"
    return f"{value:,.{decimals}f}".rstrip("0").rstrip(".")


def format_percent(value: float) -> str:
    value = float(value)
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def change_emoji(value: float) -> str:
    value = float(value)
    if value <= -8:
        return "😭"
    if value <= -5:
        return "😰"
    if value <= -3:
        return "😨"
    if value <= -1:
        return "😟"
    if value < 0:
        return "😢"
    if value >= 8:
        return "😍"
    if value >= 5:
        return "🥰"
    if value >= 2:
        return "😏"
    if value > 0:
        return "🤨"
    return "😮‍💨"


def resolve_common_coin(query: str) -> Tuple[Optional[str], Optional[str]]:
    key = normalize_query(query)
    if key in COMMON_COINS:
        return COMMON_COINS[key]
    return None, None


def resolve_coin(query: str) -> Tuple[Optional[str], Optional[str]]:
    coin_id, coin_name = resolve_common_coin(query)
    if coin_id:
        return coin_id, coin_name
    return search_coin(query)


def display_symbol(query: str, coin_id: str, coin_name: str) -> str:
    normalized = normalize_query(query)
    for token in normalized.split():
        if token in COMMON_COINS:
            common_coin_id, _ = COMMON_COINS[token]
            return COIN_SYMBOLS.get(common_coin_id, token.upper())

    if coin_id in COIN_SYMBOLS:
        return COIN_SYMBOLS[coin_id]

    words = normalize_query(coin_name).split()
    return words[0].upper() if words else coin_id.upper()


def text_tokens(text: str) -> set:
    return set(normalize_query(text).split())


def has_common_coin(text: str) -> bool:
    tokens = text_tokens(text)
    return any(token in COMMON_COINS for token in tokens)


def first_common_coin(text: str) -> Optional[str]:
    for token in normalize_query(text).split():
        if token in COMMON_COINS:
            return token
    return None


def coin_query_from_text(text: str, fallback: str) -> str:
    return first_common_coin(text) or fallback


def is_price_request(text: str) -> bool:
    tokens = text_tokens(text)
    return bool(tokens & PRICE_WORDS) and has_common_coin(text)


def should_run_market_analysis(text: str, query: str, timeframe: str) -> bool:
    if not query:
        return False

    tokens = text_tokens(text)
    query_tokens = query.split()

    if tokens & ANALYZE_WORDS:
        return True
    if timeframe != DEFAULT_TIMEFRAME:
        return True
    if len(query_tokens) == 1 and query_tokens[0] in COMMON_COINS:
        return True
    if has_common_coin(text) and tokens & MARKET_CONTEXT_WORDS:
        return True
    if re.search(r"\$[A-Za-z0-9]{2,12}", text):
        return True

    return False


def remember_chat(context: ContextTypes.DEFAULT_TYPE, user_text: str, ai_text: str) -> None:
    history = context.user_data.setdefault("chat_history", [])
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": ai_text})
    del history[:-8]


async def send_ai_text(message, text: str) -> None:
    max_len = 3900
    for start in range(0, len(text), max_len):
        await message.reply_text(html.escape(text[start:start + max_len]), parse_mode=ParseMode.HTML)


def format_price_snapshot(coin_name: str, symbol: str, summary: dict) -> str:
    price = float(summary.get("lastPrice", 0) or 0)
    changes = summary.get("changes", {})

    lines = [
        f"<b>{html.escape(coin_name)} ${html.escape(symbol)}</b>",
        f"Harga <code>${format_number(price)}</code>",
    ]

    for label in ("24H", "15m", "1h", "4h", "1D", "7D"):
        value = float(changes.get(label, 0) or 0)
        lines.append(f"{label} {change_emoji(value)} <code>{format_percent(value)}</code>")

    return "\n".join(lines)


def help_text() -> str:
    return """
<b>NiveAI Crypto Bot</b>

Kirim nama coin untuk cek harga:
<code>/p BTC</code>
<code>cek solana 4h</code>
<code>harga pepe</code>

Command:
<code>/p btc</code> - harga live + perubahan multi-timeframe
<code>/price btc</code> - sama seperti /p
<code>/analyze btc</code> - ringkasan harga market
<code>/chat apa itu RSI?</code> - tanya jawab dengan AI analyst
<code>/timeframes</code> - timeframe yang tersedia
<code>/help</code> - bantuan

Kirim foto chart dengan caption untuk analisa gambar.
Contoh caption: <code>analisa chart BTC, cari support resistance</code>

Timeframe: <code>1h</code>, <code>4h</code>, <code>1d</code>, <code>1w</code>
""".strip()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return
    await update.message.reply_text(help_text(), parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return
    await update.message.reply_text(help_text(), parse_mode=ParseMode.HTML)


async def timeframes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return
    await update.message.reply_text(
        "Timeframe tersedia: 1h, 4h, 1d, 1w\nDefault: 1h",
    )


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return

    query = normalize_query(" ".join(context.args))
    if not query:
        await update.message.reply_text("Contoh: /p BTC")
        return

    await send_price_snapshot(update, query)


async def send_price_snapshot(update: Update, query: str):
    loading_msg = await update.message.reply_text(f"Mencari harga {query}...")

    try:
        coin_id, coin_name = resolve_coin(query)
        if not coin_id:
            await loading_msg.edit_text(f"Coin '{query}' tidak ditemukan di CoinGecko.")
            return

        summary = get_price_summary(coin_id)
        symbol = display_symbol(query, coin_id, coin_name)
        await loading_msg.edit_text(
            format_price_snapshot(coin_name, symbol, summary),
            parse_mode=ParseMode.HTML,
        )
    except CoinGeckoRateLimitError as exc:
        await loading_msg.edit_text(str(exc))
    except Exception as exc:
        await loading_msg.edit_text(f"Error: {exc}")


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return

    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("Contoh: /chat apa itu RSI dan MACD?")
        return

    loading_msg = await update.message.reply_text("NiveAI sedang berpikir...")
    history = context.user_data.get("chat_history", [])
    answer = ask_chat(question, history=history)
    remember_chat(context, question, answer)

    await loading_msg.delete()
    await send_ai_text(update.message, answer)


async def analyze_query(update: Update, query: str, timeframe: str):
    await send_price_snapshot(update, query)


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return

    query, timeframe = parse_message(" ".join(context.args))
    if not query:
        await update.message.reply_text("Contoh: /analyze btc 4h")
        return

    await analyze_query(update, query, timeframe)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return

    if not update.message.photo:
        await update.message.reply_text("Kirim gambar chart yang jelas.")
        return

    caption = update.message.caption or ""
    loading_msg = await update.message.reply_text("Menganalisa chart dari gambar...")

    try:
        photo = update.message.photo[-1]
        telegram_file = await photo.get_file()
        image_bytes = bytes(await telegram_file.download_as_bytearray())
        result = analyze_chart_image(image_bytes, caption)

        await loading_msg.delete()
        await send_ai_text(update.message, result)
    except Exception as exc:
        await loading_msg.edit_text(f"Error analisa chart: {exc}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await reject_if_unauthorized(update):
        return

    text = update.message.text or ""
    query, timeframe = parse_message(text)

    if not query:
        await update.message.reply_text(help_text(), parse_mode=ParseMode.HTML)
        return

    if is_price_request(text):
        coin_query = coin_query_from_text(text, query)
        await send_price_snapshot(update, coin_query)
        return

    if should_run_market_analysis(text, query, timeframe):
        await analyze_query(update, coin_query_from_text(text, query), timeframe)
        return

    loading_msg = await update.message.reply_text("NiveAI sedang berpikir...")
    history = context.user_data.get("chat_history", [])
    answer = ask_chat(text, history=history)
    remember_chat(context, text, answer)

    await loading_msg.delete()
    await send_ai_text(update.message, answer)


def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN belum diisi di .env")
    if not ALLOWED_USER_ID:
        raise RuntimeError("ALLOWED_USER_ID belum diisi di .env")

    print("Trading Signal Bot started...")
    print("Kirim pesan ke bot Telegram kamu untuk mulai analisa.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("timeframes", timeframes_command))
    app.add_handler(CommandHandler("p", price_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("chat", chat_command))
    app.add_handler(CommandHandler("ask", chat_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot berjalan. Tekan Ctrl+C untuk stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
