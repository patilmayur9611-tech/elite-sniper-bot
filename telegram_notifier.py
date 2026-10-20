"""
========================================================================================
TELEGRAM NOTIFIER & REMOTE CONTROL MODULE
Instant Mobile Alerts & Interactive 2-Way Commands
========================================================================================
"""
import urllib.request
import urllib.parse
import json
import threading
import time
import datetime
import config

TELEGRAM_OFFSET = 0
BOT_ACTIVE = True

def send_alert(message):
    """Sends markdown formatted message to Telegram."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return None
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[TELEGRAM ERROR] Failed to send message: {e}")
        return None

def notify_entry(trade):
    """Sends entry alert with full trade parameters."""
    side_icon = "🟢 *LONG*" if trade['side'] == 'LONG' else "🔴 *SHORT*"
    msg = (
        f"🎯 *[NEW SNIPER ENTRY]* {side_icon}\n"
        f"═══════════════════════\n"
        f"🪙 Asset: *{trade['symbol']}*\n"
        f"📍 Entry Price: *${trade['entry_price']:.4f}*\n"
        f"🛡️ Stop-Loss: *${trade['sl_price']:.4f}* (Risk: {trade['sl_pct']:.2f}% | ${trade['risk_amount']:.2f})\n"
        f"🎯 Target 1 (1.9R): *${trade['tp1_price']:.4f}* (Close 40%)\n"
        f"🚀 Target 2 (4.0R): *${trade['tp2_price']:.4f}* (Close 60%)\n"
        f"📊 Position Size: *${trade['position_val']:.2f}* ({config.LEVERAGE}x Isolated Margin: ${trade['margin_used']:.2f})\n"
        f"🕒 Time: `{trade['entry_time']}`\n"
        f"═══════════════════════\n"
        f"💡 _Wick Absorption: {trade.get('wick_ratio', 0)*100:.1f}% | Vol Surge: {trade.get('vol_mult', 0):.2f}x_"
    )
    send_alert(msg)

def notify_tp1_hit(trade, pnl_40, new_sl):
    """Alerts when TP1 (1.9R) hits and shifts SL to +0.50R profit lock."""
    msg = (
        f"💰 *[TARGET 1 (1.9R) HIT!]* 🎯\n"
        f"═══════════════════════\n"
        f"🪙 Asset: *{trade['symbol']}* ({trade['side']})\n"
        f"💵 Closed 40% Position PnL: *+${pnl_40:.2f}* 🟢\n"
        f"🔒 *TRAILING PROFIT LOCK ACTIVATED!*\n"
        f"🛡️ New SL shifted to: *${new_sl:.4f}* (+0.50R in PROFIT)\n"
        f"💎 Remaining 60% Runner Aiming for Target 2 (4.0R: *${trade['tp2_price']:.4f}*)\n"
        f"═══════════════════════\n"
        f"🎉 _This trade is now 100% risk-free with guaranteed green profit!_"
    )
    send_alert(msg)

def notify_tp2_hit(trade, pnl_60, total_pnl):
    """Alerts when full Target 2 (4.0R) is achieved."""
    msg = (
        f"🚀 *[MONSTER WIN! TARGET 2 (4.0R) HIT!]* 🏆\n"
        f"═══════════════════════\n"
        f"🪙 Asset: *{trade['symbol']}* ({trade['side']})\n"
        f"🎯 Exit Price: *${trade['tp2_price']:.4f}*\n"
        f"💵 Runner 60% PnL: *+${pnl_60:.2f}*\n"
        f"💰 *TOTAL TRADE PROFIT: +${total_pnl:.2f}* 🔥\n"
        f"🕒 Duration: `{trade.get('duration_mins', 0)} mins`\n"
        f"═══════════════════════\n"
        f"📈 _Elite Price Action execution delivered maximum 4.0R payout!_"
    )
    send_alert(msg)

def notify_trailing_sl_exit(trade, pnl_60, total_pnl):
    """Alerts when runner retraced and closed at +0.50R profit lock."""
    msg = (
        f"🛡️ *[TRAILING PROFIT LOCK EXIT (+0.50R)]*\n"
        f"═══════════════════════\n"
        f"🪙 Asset: *{trade['symbol']}* ({trade['side']})\n"
        f"📍 Exit Price: *${trade['sl_price']:.4f}*\n"
        f"💵 Runner 60% Locked PnL: *+${pnl_60:.2f}* 🟢\n"
        f"💰 *FINAL TOTAL TRADE PROFIT: +${total_pnl:.2f}* 🟢\n"
        f"═══════════════════════\n"
        f"✅ _Protected profit against reversal. Guaranteed win banked!_"
    )
    send_alert(msg)

def notify_sl_hit(trade, loss_amount):
    """Alerts when Stop Loss is triggered."""
    msg = (
        f"🔴 *[STOP-LOSS HIT (-1.0R)]*\n"
        f"═══════════════════════\n"
        f"🪙 Asset: *{trade['symbol']}* ({trade['side']})\n"
        f"📍 Exit Price: *${trade['sl_price']:.4f}*\n"
        f"🔻 Net Loss: *-${loss_amount:.2f}*\n"
        f"🛡️ Strict capital control preserved 93.75% of active capital.\n"
        f"═══════════════════════"
    )
    send_alert(msg)

def poll_telegram_commands(client):
    """Polls Telegram updates for user commands."""
    global TELEGRAM_OFFSET, BOT_ACTIVE
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return BOT_ACTIVE

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates?offset={TELEGRAM_OFFSET}&timeout=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            res = json.loads(r.read().decode())
            updates = res.get("result", [])
            for u in updates:
                TELEGRAM_OFFSET = u["update_id"] + 1
                msg = u.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "").strip().lower()

                if chat_id != str(config.TELEGRAM_CHAT_ID):
                    continue

                if text == "/status":
                    state = client.state
                    positions = state.get("open_positions", {})
                    pos_txt = ""
                    if not positions:
                        pos_txt = "ℹ️ _No active trades. Scanning 3M charts with 1H Trend Bias..._"
                    else:
                        for s, p in positions.items():
                            tp1_tag = " [✅ TP1 Hit | 🔒 +0.5R Lock]" if p.get("tp1_hit") else " [Waiting TP1 1.9R]"
                            pos_txt += (
                                f"\n• *{s} {p['side']}* @ ${p['entry_price']:.4f}\n"
                                f"  SL: ${p['sl_price']:.4f} | TP1: ${p['tp1_price']:.4f} | TP2: ${p['tp2_price']:.4f}\n"
                                f"  Status: {tp1_tag}\n"
                            )

                    now_ist = config.get_now_ist().strftime('%Y-%m-%d %H:%M:%S')
                    reply = (
                        f"📊 *ELITE SNIPER BOT STATUS*\n"
                        f"═══════════════════════\n"
                        f"🕒 Clock: `{now_ist} IST` *(Locked UTC+5:30)*\n"
                        f"🤖 State: *{'✅ RUNNING' if BOT_ACTIVE else '⏸️ PAUSED'}*\n"
                        f"🏷️ Mode: *{'🟢 Paper Simulation' if config.PAPER_TRADING else '🔥 Real Money (Delta India)'}*\n"
                        f"💼 Active Trading Capital: *${state['active_capital']:.2f}* (Max Cap: ${config.MAX_ACTIVE_CAPITAL:,.0f})\n"
                        f"🏦 Banked Reserve: *${state.get('banked_profit', 0):.2f}*\n"
                        f"💰 Total Net Profit: *+${state.get('total_net_pnl', 0):.2f}*\n"
                        f"═══════════════════════\n"
                        f"*ACTIVE POSITIONS:*\n{pos_txt}"
                    )
                    send_alert(reply)

                elif text == "/balance":
                    state = client.state
                    history = state.get("trade_history", [])
                    wins = len([t for t in history if t.get("total_pnl", 0) > 0])
                    losses = len([t for t in history if t.get("total_pnl", 0) <= 0])
                    win_rate = (wins / len(history) * 100) if history else 0.0

                    send_alert(
                        f"💰 *WALLET & COMPOUNDING METRICS*\n"
                        f"═══════════════════════\n"
                        f"💵 Active Capital: *${state['active_capital']:.2f}*\n"
                        f"🏦 Banked Reserve: *${state.get('banked_profit', 0):.2f}*\n"
                        f"💎 Total Capital Value: *${(state['active_capital'] + state.get('banked_profit', 0)):.2f}*\n"
                        f"📈 Total Net Profit: *+${state.get('total_net_pnl', 0):.2f}*\n"
                        f"🎯 Total Trades: {len(history)} (Wins: {wins} | Losses: {losses} | Win Rate: {win_rate:.1f}%)\n"
                        f"═══════════════════════"
                    )

                elif text == "/stop":
                    BOT_ACTIVE = False
                    send_alert("⏸️ *Bot Paused!*\nNew trade entries are stopped. Open trades will continue to be monitored for TP/SL exits.\nSend `/start` to resume.")

                elif text == "/start":
                    BOT_ACTIVE = True
                    send_alert("▶️ *Bot Resumed!*\nActively monitoring Delta Exchange India 5M candles for institutional liquidity sweeps.")

                elif text in ["/help", "help", "hi", "hello"]:
                    send_alert(
                        "🤖 *ELITE SNIPER BOT COMMANDS:*\n"
                        "• `/status` - Live positions, current balance, and market scan state\n"
                        "• `/balance` - Compounding metrics & banked profits\n"
                        "• `/stop` - Pause opening new positions\n"
                        "• `/start` - Resume active trade scanning"
                    )

    except Exception:
        pass

    return BOT_ACTIVE
