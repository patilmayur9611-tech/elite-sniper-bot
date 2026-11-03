import urllib.request
import urllib.parse
import json
import threading
import time
from datetime import datetime, timezone, timedelta
import config
import ai_advisor

IST = timezone(timedelta(hours=5, minutes=30))
TELEGRAM_OFFSET = 0
bot_ref = None

def register_bot(b):
    global bot_ref
    bot_ref = b

def send_alert(message: str):
    """Sends formatted Telegram message to user's phone"""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")
        return None

def handle_telegram_commands():
    """Polls Telegram for incoming user commands like /ai, /status, /positions, /balance, /pnl, /history"""
    global TELEGRAM_OFFSET
    time.sleep(5)
    print("🤖 [TELEGRAM LISTENER] Listening for /ai, /status, /positions, /balance, /pnl, /history commands...")
    
    while True:
        if not config.TELEGRAM_BOT_TOKEN:
            time.sleep(10)
            continue
            
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates?offset={TELEGRAM_OFFSET}&timeout=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
                updates = data.get("result", [])
                for u in updates:
                    TELEGRAM_OFFSET = u["update_id"] + 1
                    msg = u.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip()
                    
                    if chat_id != str(config.TELEGRAM_CHAT_ID):
                        continue
                        
                    cmd = text.lower()
                    print(f"📩 [TELEGRAM USER COMMAND] Received: {text}")
                    
                    if cmd in ["/ai", "/ai_status", "ai", "ai_status"]:
                        report = ai_advisor.get_ai_status_report()
                        send_alert(report)
                        
                    elif cmd in ["/status", "status", "/start", "start"]:
                        p_state = ai_advisor.get_psychology_state()
                        state_icon = "🟢" if p_state == "NORMAL" else ("🛡️" if p_state == "DEFENSIVE" else "🔥")
                        open_count = 0
                        wallet = config.TOTAL_WALLET_CAPITAL
                        if bot_ref and hasattr(bot_ref, 'client'):
                            open_count = len(bot_ref.client.paper_state.get("open_positions", {}))
                            wallet = bot_ref.client.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
                            
                        status_msg = (
                            f"🤖 *[WHALE OTE & AI BOT SYSTEM STATUS]*\n"
                            f"═══════════════════════════\n"
                            f"• Engine: *Whale Golden Pocket OTE*\n"
                            f"• AI State: *{state_icon} {p_state} MODE*\n"
                            f"• Mode: *{'Paper Virtual' if config.PAPER_TRADING else 'LIVE REAL'}*\n"
                            f"• Open Positions: *{open_count}/{config.MAX_CONCURRENT_POSITIONS}*\n"
                            f"• Wallet Balance: *₹{wallet:,.2f} INR*\n"
                            f"• Max Loss Cap: *₹{getattr(config, 'MAX_LOSS_PER_TRADE_INR', 36.0):.2f} INR*\n"
                            f"• Position Budget: *₹{config.POSITION_NOTIONAL_INR * ai_advisor.get_position_size_multiplier():,.0f} INR*\n"
                            f"• Time: *{datetime.now(IST).strftime('%I:%M:%S %p IST')}*\n"
                            f"═══════════════════════════\n"
                            f"Commands: `/ai` | `/positions` | `/pnl` | `/balance`"
                        )
                        send_alert(status_msg)
                        
                    elif cmd in ["/positions", "/pos", "positions", "pos"]:
                        if not bot_ref or not hasattr(bot_ref, 'client'):
                            send_alert("⚠️ Bot engine initializing...")
                            continue
                            
                        open_pos = bot_ref.client.paper_state.get("open_positions", {})
                        if not open_pos:
                            send_alert("ℹ️ *No active positions open right now.* Scanner actively looking for Bottom Sweep setups.")
                        else:
                            pos_text = f"📊 *[CURRENT OPEN POSITIONS ({len(open_pos)})]*\n═══════════════════════════\n"
                            for sym, p in open_pos.items():
                                curr_p = bot_ref.client.get_mark_price(sym)
                                entry_p = p['entry_price']
                                side = p['side']
                                pnl_pct = ((curr_p - entry_p)/entry_p)*100 if side == 'BUY' else ((entry_p - curr_p)/entry_p)*100
                                pnl_inr = (config.POSITION_NOTIONAL_INR) * (pnl_pct / 100)
                                icon = "🟢" if pnl_inr >= 0 else "🔴"
                                pos_text += (
                                    f"🪙 *{sym}* ({side})\n"
                                    f"• Entry: `${entry_p}` | Mark: `${curr_p}`\n"
                                    f"• PnL: {icon} *{pnl_pct:+.2f}%* (`₹{pnl_inr:+.2f} INR`)\n"
                                    f"• Peak Move: `+{abs(p.get('peak_price', entry_p) - entry_p)/entry_p*100:.2f}%`\n"
                                    f"• TP1 Target: `${p['tp1_price']}`\n"
                                    f"• Current SL: `${p['current_sl']}`\n"
                                    f"───────────────────────────\n"
                                )
                            send_alert(pos_text)
                            
                    elif cmd in ["/pnl", "/history", "pnl", "history"]:
                        if not bot_ref or not hasattr(bot_ref, 'client'):
                            send_alert("⚠️ Bot engine initializing...")
                            continue
                            
                        history = bot_ref.client.paper_state.get("trade_history", [])
                        wallet = bot_ref.client.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
                        starting_cap = config.TOTAL_WALLET_CAPITAL
                        total_pnl = wallet - starting_cap
                        total_return_pct = (total_pnl / starting_cap) * 100
                        
                        if not history:
                            resp = (
                                f"📊 *[REALIZED PNL & TRADE HISTORY]*\n"
                                f"═══════════════════════════\n"
                                f"ℹ️ No closed trades yet today.\n\n"
                                f"💰 *Current Wallet Balance:* `₹{wallet:,.2f} INR`\n"
                                f"💼 *Starting Balance:* `₹{starting_cap:,.2f} INR`\n"
                                f"📈 *Net Return:* `{total_return_pct:+.2f}%` (*₹{total_pnl:+.2f} INR*)"
                            )
                        else:
                            wins = [t for t in history if t.get('pnl_inr', 0) > 0]
                            losses = [t for t in history if t.get('pnl_inr', 0) <= 0]
                            win_rate = (len(wins) / len(history)) * 100 if history else 0
                            
                            resp = (
                                f"📊 *[REALIZED PNL & TRADE PERFORMANCE]*\n"
                                f"═══════════════════════════\n"
                                f"💰 *Net Realized PnL:* `₹{total_pnl:+.2f} INR` ({total_return_pct:+.2f}%)\n"
                                f"💼 *Current Wallet Balance:* `₹{wallet:,.2f} INR`\n"
                                f"🎯 *Total Closed Trades:* `{len(history)}`\n"
                                f"🏆 *Wins:* `{len(wins)}` | 🛑 *Losses:* `{len(losses)}`\n"
                                f"📈 *Win Rate:* `{win_rate:.1f}%`\n"
                                f"═══════════════════════════\n"
                                f"📋 *Recent Completed Trades:*\n"
                            )
                            for t in history[-5:]:
                                p_inr = t.get('pnl_inr', 0)
                                p_pct = t.get('pnl_pct', 0) * 100
                                icon = "🟢" if p_inr > 0 else "🔴"
                                resp += (
                                    f"{icon} *{t.get('symbol')}* ({t.get('side')}): "
                                    f"`{p_inr:+.1f} INR` (*{p_pct:+.2f}%*) | {t.get('time', '')}\n"
                                )
                        send_alert(resp)

                    elif cmd in ["/balance", "balance"]:
                        wallet = config.TOTAL_WALLET_CAPITAL
                        active_margin = 0.0
                        if bot_ref and hasattr(bot_ref, 'client'):
                            wallet = bot_ref.client.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
                            active_margin = bot_ref.client.paper_state.get("active_margin", 0.0)
                        free_cash = max(0.0, wallet - active_margin)
                        
                        resp = (
                            f"💰 *[WALLET & MARGIN DETAILS]*\n"
                            f"═══════════════════════════\n"
                            f"• Total Wallet Balance: *₹{wallet:,.2f} INR*\n"
                            f"• Active Locked Margin: *₹{active_margin:,.2f} INR*\n"
                            f"• Free Available Reserve: *₹{free_cash:,.2f} INR*\n"
                            f"• Leverage: *{config.LEVERAGE}x Isolated*\n"
                            f"• Dynamic Size Multiplier: *{ai_advisor.get_position_size_multiplier()*100:.0f}%*\n"
                            f"• Position Size per Slot: *₹{config.POSITION_NOTIONAL_INR*ai_advisor.get_position_size_multiplier():,.0f} INR*\n"
                            f"• Margin per Slot: *₹{config.MARGIN_PER_TRADE*ai_advisor.get_position_size_multiplier():,.0f} INR*"
                        )
                        send_alert(resp)
                        
        except Exception as e:
            pass
        time.sleep(2)
