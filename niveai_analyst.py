import base64
import json
import os
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", GROQ_MODEL)
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }


def _extract_content(response: requests.Response) -> str:
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _post_chat_completion(payload: dict, timeout: int = 30) -> str:
    response = requests.post(
        GROQ_URL,
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    return _extract_content(response)

def build_prompt(symbol: str, timeframe: str, indicators: dict) -> str:
    rsi = indicators["rsi"]
    macd = indicators["macd"]
    macd_signal = indicators["macd_signal"]
    macd_hist = indicators["macd_histogram"]
    price = indicators["current_price"]
    ema20 = indicators["ema_20"]
    ema50 = indicators["ema_50"]
    bb_upper = indicators["bb_upper"]
    bb_lower = indicators["bb_lower"]
    vol_now = indicators["volume_latest"]
    vol_prev = indicators["volume_prev"]

    rsi_condition = (
        "OVERBOUGHT (>70)" if rsi > 70
        else "OVERSOLD (<30)" if rsi < 30
        else "NEUTRAL (30-70)"
    )

    macd_cross = (
        "BULLISH (MACD above signal, histogram positive)" if macd > macd_signal and macd_hist > 0
        else "BEARISH (MACD below signal, histogram negative)" if macd < macd_signal and macd_hist < 0
        else "MIXED (crossover zone)"
    )

    ema_trend = (
        "UPTREND (price > EMA20 > EMA50)" if price > ema20 > ema50
        else "DOWNTREND (price < EMA20 < EMA50)" if price < ema20 < ema50
        else "SIDEWAYS"
    )

    bb_position = (
        "ABOVE UPPER BAND (overbought zone)" if price > bb_upper
        else "BELOW LOWER BAND (oversold zone)" if price < bb_lower
        else "WITHIN BANDS"
    )

    if vol_prev <= 0:
        vol_condition = "UNAVAILABLE (CoinGecko OHLC endpoint does not provide volume)"
    else:
        vol_condition = (
            f"INCREASING ({round((vol_now/vol_prev - 1)*100, 1)}% higher than previous)"
            if vol_now > vol_prev
            else f"DECREASING ({round((1 - vol_now/vol_prev)*100, 1)}% lower than previous)"
        )

    return f"""You are a strict crypto trading analyst. Base your analysis ONLY on the pre-calculated conditions below. Do NOT invent or assume any conditions not listed here.

Symbol: {symbol} | Timeframe: {timeframe}

PRE-CALCULATED CONDITIONS:
- RSI ({rsi}): {rsi_condition}
- MACD: {macd_cross}
- EMA Trend: {ema_trend}
- Bollinger Band position: {bb_position}
- Volume: {vol_condition}
- Price change: {indicators['price_change_pct']}%

SIGNAL RULES (follow strictly):
- RSI OVERBOUGHT + MACD BEARISH → SELL
- RSI OVERSOLD + MACD BULLISH → BUY
- RSI OVERBOUGHT + MACD BULLISH → HOLD
- RSI NEUTRAL + MACD BULLISH + UPTREND → BUY
- RSI NEUTRAL + MACD BEARISH + DOWNTREND → SELL
- All other combinations → HOLD

CONFIDENCE RULES:
- High: 4+ conditions align
- Medium: 2-3 conditions align
- Low: conflicting signals

Reply in this exact JSON format only, no other text:
{{
  "signal": "BUY|SELL|HOLD",
  "confidence": "Low|Medium|High",
  "reason": "Max 2 sentences referencing exact conditions above.",
  "key_risk": "Max 1 sentence."
}}"""


def ask_niveai(symbol: str, timeframe: str, indicators: dict) -> dict:
    prompt = build_prompt(symbol, timeframe, indicators)

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict crypto trading analyst. Always respond with valid JSON only. No markdown, no extra text."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.0,
        "max_tokens": 300,
    }

    try:
        content = _post_chat_completion(payload, timeout=30)

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        return json.loads(content)

    except requests.exceptions.ConnectionError:
        return {"error": "Groq API tidak bisa diakses. Cek koneksi internet."}
    except json.JSONDecodeError:
        return {"error": f"Response bukan JSON valid: {content[:150]}"}
    except Exception as e:
        return {"error": str(e)}


def ask_chat(question: str, history: Optional[List[dict]] = None) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are NiveAI, an Indonesian crypto trading analyst inside a Telegram bot. "
                "Answer conversationally, clearly, and practically. You may explain technical analysis, "
                "risk management, market structure, indicators, trading plans, and crypto concepts. "
                "Do not promise profit. When giving trade ideas, include invalidation/risk and remind the user "
                "that it is not financial advice. Keep answers concise unless the user asks for depth."
            ),
        }
    ]

    if history:
        messages.extend(history[-8:])

    messages.append({"role": "user", "content": question})

    payload = {
        "model": GROQ_CHAT_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 700,
    }

    try:
        return _post_chat_completion(payload, timeout=30)
    except requests.exceptions.ConnectionError:
        return "Groq API tidak bisa diakses. Cek koneksi internet."
    except Exception as e:
        return f"Error AI chat: {e}"


def analyze_chart_image(image_bytes: bytes, question: str = "") -> str:
    if not GROQ_VISION_MODEL:
        return (
            "Mode analisa chart gambar belum aktif. Isi GROQ_VISION_MODEL di .env "
            "dengan model vision Groq yang tersedia, lalu restart bot."
        )

    prompt = question.strip() or (
        "Analisa chart/candle ini. Baca timeframe, pair, struktur trend, candle penting, "
        "support/resistance, volume, dan indikator yang terlihat seperti RSI, MACD, EMA/MA, "
        "Bollinger Bands, VWAP, Fibonacci, atau indikator lain di chart. Jelaskan skenario "
        "bullish/bearish, area invalidation, dan risk management. Jangan mengarang angka "
        "yang tidak terlihat jelas dari gambar."
    )

    encoded = base64.b64encode(image_bytes).decode("ascii")
    if len(encoded) > 4 * 1024 * 1024:
        return "Gambar terlalu besar untuk Groq Vision. Kirim screenshot chart yang lebih kecil/terkompres."

    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are NiveAI, an Indonesian crypto chart analyst. Analyze visible chart images carefully. "
                    "Read candlestick structure, trend, support/resistance, volume, and any visible indicators "
                    "such as RSI, MACD, EMA/MA, Bollinger Bands, VWAP, Fibonacci, order blocks, or divergence. "
                    "If price labels, timeframe, indicator values, or candle details are unclear, say so instead "
                    "of guessing. Give practical scenarios, invalidation levels, and risk notes. This is not "
                    "financial advice."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded}",
                        },
                    },
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 900,
    }

    try:
        return _post_chat_completion(payload, timeout=45)
    except requests.exceptions.ConnectionError:
        return "Groq API tidak bisa diakses. Cek koneksi internet."
    except Exception as e:
        return f"Error analisa chart: {e}"
