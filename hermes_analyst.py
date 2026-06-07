import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hermes3:8b")

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

    vol_condition = (
        f"INCREASING ({round((vol_now/vol_prev - 1)*100, 1)}% higher than previous)"
        if vol_now > vol_prev
        else f"DECREASING ({round((1 - vol_now/vol_prev)*100, 1)}% lower than previous)"
    )

    return f"""You are a strict crypto trading analyst. You must base your analysis ONLY on the pre-calculated conditions below. Do NOT invent or assume any conditions not listed here.

Symbol: {symbol} | Timeframe: {timeframe}

PRE-CALCULATED CONDITIONS (use these exactly, do not reinterpret):
- RSI ({rsi}): {rsi_condition}
- MACD: {macd_cross}
- EMA Trend: {ema_trend}
- Bollinger Band position: {bb_position}
- Volume: {vol_condition}
- Price change: {indicators['price_change_pct']}%

SIGNAL RULES (follow strictly):
- If RSI OVERBOUGHT + MACD BEARISH → SELL
- If RSI OVERSOLD + MACD BULLISH → BUY
- If RSI OVERBOUGHT + MACD BULLISH → HOLD (momentum vs overbought conflict)
- If RSI NEUTRAL + MACD BULLISH + UPTREND → BUY
- If RSI NEUTRAL + MACD BEARISH + DOWNTREND → SELL
- All other combinations → HOLD

CONFIDENCE RULES:
- High: 4+ conditions align with signal
- Medium: 2-3 conditions align
- Low: conflicting signals

Based strictly on the conditions above, reply in this exact JSON format only:
{{
  "signal": "BUY|SELL|HOLD",
  "confidence": "Low|Medium|High",
  "reason": "Reference the exact conditions listed above. Max 2 sentences.",
  "key_risk": "One specific risk based on the data above. Max 1 sentence."
}}"""


def ask_hermes(symbol: str, timeframe: str, indicators: dict) -> dict:
    prompt = build_prompt(symbol, timeframe, indicators)

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict crypto trading analyst. Always respond with valid JSON only. No markdown, no extra text. Never invent conditions not provided to you."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 300,
            "num_ctx": 4096,
            "seed": 42,
        }
    }

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        return json.loads(content)

    except requests.exceptions.ConnectionError:
        return {"error": "Ollama tidak bisa diakses. Jalankan 'ollama serve' dulu."}
    except json.JSONDecodeError:
        return {"error": f"Response bukan JSON valid: {content[:150]}"}
    except Exception as e:
        return {"error": str(e)}