import urllib.request
import urllib.parse
import json
import threading
import time
from datetime import datetime, timezone, timedelta
import config

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
    """Polls Telegram for incoming user commands like /status, /positions, /balance"""
    global TELEGRAM_OFFSET
    time.sleep(5)
    print("🤖 [TELEGRAM LISTENER] Listening for /status, /positions, /balance commands...")
    
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
                        
                    cmd = text.lower().split()[0] if text else ""
                    now_ist = datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p IST')
                    
                    if cmd in ["/status", "/help", "status", "/start"]:
                        wallet = config.TOTAL_WALLET_CAPITAL
                        open_count = 0
                        history_count = 0
                        if bot_ref and hasattr(bot_ref, 'client'):
                            wallet = bot_ref.client.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
                            open_count = len(bot_ref.client.paper_state.get("open_positions", {}))
                            history_count = len(bot_ref.client.paper_state.get("trade_history", []))
                            
                        resp = (
                            f"⚡ *[DELTA EARLY MOMENTUM HUNTER STATUS]* ⚡\n"
                            f"═══════════════════════════\n"
                            f"🟢 *Bot State:* `RUNNING 24/7 (ONLINE)`\n"
                            f"🕒 *Current Time:* `{now_ist}`\n"
                            f"💰 *Wallet Capital:* `₹{wallet:,.2f} INR`\n"
                            f"💼 *Position Size:* `₹{config.POSITION_NOTIONAL_INR:,.0f} @ {config.LEVERAGE}x`\n"
                            f"🛡️ *Margin Per Trade:* `₹{config.MARGIN_PER_TRADE:,.0f} INR`\n"
                            f"📊 *Open Positions:* `{open_count} / {config.MAX_CONCURRENT_POSITIONS}`\n"
                            f"📈 *Completed Trades:* `{history_count}`\n"
                            f"📡 *Delta Live Feed:* `Connected (Top 25 Pairs)`\n"
                            f"═══════════════════════════\n"
                            f"📌 *Commands Available:*\n"
                            f"• `/status` - Bot live status & wallet check\n"
                            f"• `/positions` - View all active open trades\n"
                            f"• `/balance` - Check capital & free margin"
                        )
                        send_alert(resp)
                        
                    elif cmd in ["/positions", "/trades", "positions"]:
                        if not bot_ref or not hasattr(bot_ref, 'client'):
                            send_alert("⚠️ Bot engine initializing, please wait...")
                            continue
                            
                        open_pos = bot_ref.client.paper_state.get("open_positions", {})
                        if not open_pos:
                            send_alert(f"ℹ️ *No Open Positions Right Now*\n\nBot is actively scanning Delta India for RVol >= 3.8x breakouts. All {config.MAX_CONCURRENT_POSITIONS} slots are free.")
                        else:
                            pos_text = f"📊 *[ACTIVE OPEN POSITIONS ({len(open_pos)}/{config.MAX_CONCURRENT_POSITIONS})]*\n═══════════════════════════\n"
                            for sym, p in open_pos.items():
                                curr_p = bot_ref.client.get_mark_price(sym)
                                if p['side'] == 'BUY':
                                    pnl_pct = (curr_p - p['entry_price']) / p['entry_price'] if curr_p > 0 else 0
                                else:
                                    pnl_pct = (p['entry_price'] - curr_p) / p['entry_price'] if curr_p > 0 else 0
                                pnl_inr = config.POSITION_NOTIONAL_INR * pnl_pct
                                
                                pos_text += (
                                    f"🪙 *{sym}* ({p['side']})\n"
                                    f"• Entry: `${p['entry_price']}` | Current: `${curr_p}`\n"
                                    f"• PnL: `{pnl_pct*100:+.2f}%` (*₹{pnl_inr:+.1f} INR*)\n"
                                    f"• SL: `${p['current_sl']}` | TP1: `${p['tp1_price']}`\n"
                                    f"───────────────────────────\n"
                                )
                            send_alert(pos_text)
                            
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
                            f"• Margin Per Slot: *₹{config.MARGIN_PER_TRADE:,.0f} INR*"
                        )
                        send_alert(resp)
                        
        except Exception as e:
            # Silence timeout errors during normal long polling
            pass
        time.sleep(2)
