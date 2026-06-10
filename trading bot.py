"""
Telegram Trading Signal Bot
Strategy: RSI + EMA
Exchange: Binance (via ccxt)
Install: pip install python-telegram-bot ccxt pandas ta
"""

import os
import asyncio
import ccxt
import pandas as pd
import ta
from datetime import datetime
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# ==================== CONFIG ====================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"   # ពី @BotFather
CHAT_ID        = "YOUR_CHAT_ID"               # ID របស់ Channel/Group
SYMBOL         = "BTC/USDT"
TIMEFRAME      = "15m"                        # 1m, 5m, 15m, 1h, 4h
CHECK_INTERVAL = 60                           # seconds (ពិនិត្យរៀងរាល់ 60 វិនាទី)

# RSI Settings
RSI_PERIOD     = 14
RSI_OVERSOLD   = 30    # Buy zone
RSI_OVERBOUGHT = 70    # Sell zone

# EMA Settings
EMA_FAST       = 9
EMA_SLOW       = 21

# ==================== WIN RATE TRACKER ====================
signal_history = []

def record_signal(signal_type, price):
    signal_history.append({
        "type": signal_type,
        "price": price,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "result": None  # pending
    })

def get_win_rate():
    completed = [s for s in signal_history if s["result"] is not None]
    if not completed:
        return 0, 0, 0
    wins = sum(1 for s in completed if s["result"] == "WIN")
    total = len(completed)
    return wins, total, round((wins / total) * 100, 1)

# ==================== EXCHANGE ====================
exchange = ccxt.binance({
    "enableRateLimit": True,
})

def fetch_ohlcv(symbol=SYMBOL, timeframe=TIMEFRAME, limit=100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# ==================== INDICATORS ====================
def calculate_indicators(df):
    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=RSI_PERIOD).rsi()

    # EMA
    df["ema_fast"] = ta.trend.EMAIndicator(df["close"], window=EMA_FAST).ema_indicator()
    df["ema_slow"] = ta.trend.EMAIndicator(df["close"], window=EMA_SLOW).ema_indicator()

    return df

# ==================== SIGNAL LOGIC ====================
last_signal = None  # កុំផ្ញើ signal ដដែលៗ

def check_signal(df):
    global last_signal

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    rsi       = latest["rsi"]
    ema_fast  = latest["ema_fast"]
    ema_slow  = latest["ema_slow"]
    price     = latest["close"]

    # BUY: RSI ចេញពី Oversold + EMA Fast កាត់លើ EMA Slow
    buy_condition = (
        rsi < RSI_OVERSOLD and
        prev["ema_fast"] < prev["ema_slow"] and
        ema_fast > ema_slow
    )

    # SELL: RSI ចូល Overbought + EMA Fast ធ្លាក់ក្រោម EMA Slow
    sell_condition = (
        rsi > RSI_OVERBOUGHT and
        prev["ema_fast"] > prev["ema_slow"] and
        ema_fast < ema_slow
    )

    if buy_condition and last_signal != "BUY":
        last_signal = "BUY"
        record_signal("BUY", price)
        return "BUY", price, rsi, ema_fast, ema_slow

    elif sell_condition and last_signal != "SELL":
        last_signal = "SELL"
        record_signal("SELL", price)
        return "SELL", price, rsi, ema_fast, ema_slow

    return None, price, rsi, ema_fast, ema_slow

# ==================== MESSAGE FORMAT ====================
def format_signal_message(signal, price, rsi, ema_fast, ema_slow):
    wins, total, win_rate = get_win_rate()
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if signal == "BUY":
        emoji = "🟢"
        action = "BUY 📈"
    else:
        emoji = "🔴"
        action = "SELL 📉"

    msg = f"""
{emoji} *SIGNAL: {action}*
━━━━━━━━━━━━━━━━━━
💱 Pair   : `{SYMBOL}`
⏱ TF     : `{TIMEFRAME}`
💰 Price  : `{price:,.2f} USDT`
━━━━━━━━━━━━━━━━━━
📊 *Indicators:*
  • RSI     : `{rsi:.1f}`
  • EMA {EMA_FAST}   : `{ema_fast:,.2f}`
  • EMA {EMA_SLOW}   : `{ema_slow:,.2f}`
━━━━━━━━━━━━━━━━━━
🏆 *Win Rate:* `{win_rate}%` ({wins}/{total} signals)
🕐 `{time_now}`
━━━━━━━━━━━━━━━━━━
⚠️ _សូម DYOR មុន Trade!_
    """.strip()
    return msg

# ==================== BOT COMMANDS ====================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Trading Signal Bot Active!*\n\n"
        "Commands:\n"
        "/status - មើល indicator បច្ចុប្បន្ន\n"
        "/winrate - មើល Win Rate\n"
        "/history - ប្រវត្តិ Signal\n"
        "/start - ចាប់ផ្តើម Bot",
        parse_mode="Markdown"
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        df = fetch_ohlcv()
        df = calculate_indicators(df)
        latest = df.iloc[-1]
        price = latest["close"]
        rsi   = latest["rsi"]
        ema_f = latest["ema_fast"]
        ema_s = latest["ema_slow"]
        trend = "📈 Bullish" if ema_f > ema_s else "📉 Bearish"

        msg = f"""
📡 *Market Status*
━━━━━━━━━━━━━━━
💱 `{SYMBOL}` | `{TIMEFRAME}`
💰 Price : `{price:,.2f} USDT`
📊 RSI   : `{rsi:.1f}`
📈 EMA {EMA_FAST} : `{ema_f:,.2f}`
📉 EMA {EMA_SLOW} : `{ema_s:,.2f}`
🔀 Trend : {trend}
        """.strip()
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_winrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wins, total, win_rate = get_win_rate()
    msg = f"""
🏆 *Win Rate Summary*
━━━━━━━━━━━━━━━
✅ Wins   : {wins}
❌ Losses : {total - wins}
📊 Total  : {total}
🎯 Rate   : *{win_rate}%*
    """.strip()
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not signal_history:
        await update.message.reply_text("📭 មិនទាន់មាន Signal ណាមួយទេ។")
        return
    lines = ["📜 *Signal History (last 10)*\n━━━━━━━━━━━━━━━"]
    for s in signal_history[-10:]:
        icon = "🟢" if s["type"] == "BUY" else "🔴"
        result = s["result"] if s["result"] else "⏳"
        lines.append(f"{icon} {s['type']} @ `{s['price']:,.2f}` | {result} | {s['time']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ==================== AUTO SIGNAL LOOP ====================
async def signal_loop(bot: Bot):
    print("✅ Signal loop started...")
    while True:
        try:
            df = fetch_ohlcv()
            df = calculate_indicators(df)
            signal, price, rsi, ema_f, ema_s = check_signal(df)

            if signal:
                msg = format_signal_message(signal, price, rsi, ema_f, ema_s)
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=msg,
                    parse_mode="Markdown"
                )
                print(f"[{datetime.now()}] Signal sent: {signal} @ {price}")
            else:
                print(f"[{datetime.now()}] No signal | RSI={rsi:.1f} | Price={price:,.2f}")

        except Exception as e:
            print(f"[ERROR] {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# ==================== MAIN ====================
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("winrate", cmd_winrate))
    app.add_handler(CommandHandler("history", cmd_history))

    # Start signal loop in background
    asyncio.create_task(signal_loop(app.bot))

    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
