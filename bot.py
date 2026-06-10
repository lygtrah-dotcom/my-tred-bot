import os
import asyncio
import ccxt
import pandas as pd
import ta
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT  = os.environ.get("CHAT_ID", "")

SYMBOL   = "BTC/USDT"
TF       = "15m"
INTERVAL = 60

exchange = ccxt.binance({"enableRateLimit": True})
history  = []
last_sig = None

def get_data():
    bars = exchange.fetch_ohlcv(SYMBOL, TF, limit=100)
    df = pd.DataFrame(bars, columns=["ts","o","h","l","c","v"])
    df["rsi"] = ta.momentum.RSIIndicator(df["c"], 14).rsi()
    df["ema9"]  = ta.trend.EMAIndicator(df["c"], 9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(df["c"], 21).ema_indicator()
    return df

def check(df):
    global last_sig
    r = df.iloc[-1]
    p = df.iloc[-2]
    buy  = r["rsi"] < 30 and p["ema9"] < p["ema21"] and r["ema9"] > r["ema21"]
    sell = r["rsi"] > 70 and p["ema9"] > p["ema21"] and r["ema9"] < r["ema21"]
    if buy and last_sig != "BUY":
        last_sig = "BUY"
        history.append({"t":"BUY","p":r["c"],"time":datetime.now().strftime("%H:%M")})
        return "BUY", r["c"], r["rsi"]
    if sell and last_sig != "SELL":
        last_sig = "SELL"
        history.append({"t":"SELL","p":r["c"],"time":datetime.now().strftime("%H:%M")})
        return "SELL", r["c"], r["rsi"]
    return None, r["c"], r["rsi"]

def msg(sig, price, rsi):
    e = "🟢" if sig=="BUY" else "🔴"
    return f"""{e} *{sig}*
💱 {SYMBOL} | {TF}
💰 `{price:,.2f}` USDT
📊 RSI: `{rsi:.1f}`
🕐 {datetime.now().strftime("%Y-%m-%d %H:%M")}
⚠️ _DYOR មុន Trade!_"""

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("🤖 *Bot Active!*\n/status /winrate /history", parse_mode="Markdown")

async def status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    df = get_data()
    r = df.iloc[-1]
    t = "📈 Bullish" if r["ema9"]>r["ema21"] else "📉 Bearish"
    await u.message.reply_text(
        f"📡 *Status*\n💰 `{r['c']:,.2f}`\n📊 RSI: `{r['rsi']:.1f}`\n{t}",
        parse_mode="Markdown")

async def winrate(u: Update, c: ContextTypes.DEFAULT_TYPE):
    t = len(history)
    await u.message.reply_text(f"📊 Signals: {t}", parse_mode="Markdown")

async def hist(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not history:
        await u.message.reply_text("📭 មិនទាន់មាន Signal")
        return
    lines = ["📜 *History*"]
    for s in history[-10:]:
        e = "🟢" if s["t"]=="BUY" else "🔴"
        lines.append(f"{e} {s['t']} @ `{s['p']:,.2f}` | {s['time']}")
    await u.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def loop(bot: Bot):
    while True:
        try:
            df = get_data()
            sig, price, rsi = check(df)
            if sig:
                await bot.send_message(chat_id=CHAT, text=msg(sig,price,rsi), parse_mode="Markdown")
                print(f"Signal: {sig} @ {price}")
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(INTERVAL)

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("status",  status))
    app.add_handler(CommandHandler("winrate", winrate))
    app.add_handler(CommandHandler("history", hist))
    asyncio.create_task(loop(app.bot))
    print("Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
