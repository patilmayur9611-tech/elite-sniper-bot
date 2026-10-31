import os
import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta
import requests
import config
from delta_client import DeltaClient
from strategy import MomentumStrategy
import telegram_helper

# Indian Standard Time (IST = UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))
PORT = int(os.environ.get("PORT", 10000))
bot_instance = None

class HealthHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        
        open_pos = 0
        wallet = config.TOTAL_WALLET_CAPITAL
        if bot_instance and hasattr(bot_instance, 'client'):
            open_pos = len(bot_instance.client.paper_state.get("open_positions", {}))
            wallet = bot_instance.client.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
            
        health_data = {
            "status": "ONLINE_ACTIVE",
            "bot": "Delta Early Momentum Hunter",
            "mode": "PAPER_TRADING" if config.PAPER_TRADING else "LIVE_REAL_MONEY",
            "wallet_balance": wallet,
            "open_positions": open_pos,
            "max_positions": config.MAX_CONCURRENT_POSITIONS,
            "ist_time": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
        }
        self.wfile.write(json.dumps(health_data).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress health check spam in console/Render logs

def start_http_server():
    """Runs lightweight HTTP server in background so Render never sleeps or crashes on port check"""
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        print(f"🌐 [ANTI-SLEEP SERVER] Listening on port {PORT} for 24/7 Keep-Alive...")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ HTTP Server notice: {e}")

def self_ping_worker():
    """Pings own Render URL every 8 minutes to prevent Render Free Tier from sleeping (15-min idle timeout)"""
    time.sleep(30) # Initial wait
    while True:
        url = os.environ.get("RENDER_EXTERNAL_URL") or getattr(config, "RENDER_URL", "")
        if url:
            if not url.startswith("http"):
                url = f"https://{url}"
            try:
                r = requests.get(f"{url}/", timeout=10)
                print(f"🔄 [ANTI-SLEEP PING] Successfully pinged {url} (Status: {r.status_code})")
            except Exception as e:
                print(f"⚠️ [ANTI-SLEEP PING] Ping error: {e}")
        time.sleep(480) # Ping every 8 minutes (Render sleeps at 15 mins)

class MomentumHunterBot:
    def __init__(self):
        global bot_instance
        bot_instance = self
        
        self.client = DeltaClient()
        self.strategy = MomentumStrategy()
        
        mode_str = "📝 PAPER TRADING (Safe Simulation)" if config.PAPER_TRADING else "🔴 LIVE REAL MONEY"
        print("=" * 68)
        print("🚀 DELTA EXCHANGE INDIA - EARLY MOMENTUM HUNTER")
        print("=" * 68)
        print(f"Mode: {mode_str}")
        print(f"Wallet Capital: ₹{config.TOTAL_WALLET_CAPITAL:,.0f} INR")
        print(f"Position Notional: ₹{config.POSITION_NOTIONAL_INR:,.0f} INR (Margin: ₹{config.MARGIN_PER_TRADE:,.0f} @ {config.LEVERAGE}x)")
        print(f"Max Concurrent Positions: {config.MAX_CONCURRENT_POSITIONS}")
        print("=" * 68)
        
        # Send Telegram Bot Online Notification
        startup_msg = (
            f"🚀 *Delta Early Momentum Hunter Online*\n\n"
            f"• *Mode:* `{mode_str}`\n"
            f"• *Wallet Capital:* ₹{config.TOTAL_WALLET_CAPITAL:,.0f}\n"
            f"• *Position Size:* ₹{config.POSITION_NOTIONAL_INR:,.0f} (Margin: ₹{config.MARGIN_PER_TRADE:,.0f} @ {config.LEVERAGE}x)\n"
            f"• *Max Positions:* {config.MAX_CONCURRENT_POSITIONS}\n"
            f"• *Anti-Sleep Shield:* Active 24/7 (Port {PORT})\n"
            f"• *Pairs Monitored:* Top {len(self.client.products)} Volume Perps"
        )
        telegram_helper.send_alert(startup_msg)

    def execute_entry(self, symbol: str, signal: dict):
        open_pos = self.client.paper_state["open_positions"]
        if len(open_pos) >= config.MAX_CONCURRENT_POSITIONS:
            return
            
        if symbol in open_pos:
            return
            
        side = signal['side']
        entry_price = self.client.round_price(symbol, signal['price'])
        contracts = self.client.calculate_contracts(symbol, entry_price)
        atr = signal['atr']
        
        if side == 'BUY':
            initial_sl = self.client.round_price(symbol, entry_price - (1.3 * atr))
            tp1_price = self.client.round_price(symbol, entry_price * 1.035) # +3.5%
        else: # SHORT
            initial_sl = self.client.round_price(symbol, entry_price + (1.1 * atr))
            tp1_price = self.client.round_price(symbol, entry_price * 0.965) # -3.5%
            
        pos_data = {
            'symbol': symbol,
            'side': side,
            'contracts': contracts,
            'entry_price': entry_price,
            'current_sl': initial_sl,
            'initial_sl': initial_sl,
            'tp1_price': tp1_price,
            'tp1_hit': False,
            'peak_price': entry_price,
            'entry_time': datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p IST'),
            'atr': atr
        }
        
        open_pos[symbol] = pos_data
        self.client.paper_state["active_margin"] += config.MARGIN_PER_TRADE
        self.client.save_paper_state()
        
        print(f"\n⚡ [{datetime.now(IST).strftime('%H:%M:%S')}] NEW {side} ENTRY: {symbol}")
        print(f"   Price: {entry_price} | Contracts: {contracts} (Value: ₹{config.POSITION_NOTIONAL_INR:,.0f})")
        print(f"   Stop Loss: {initial_sl} | TP1 (+3.5%): {tp1_price}")
        print(f"   Slots In Use: {len(open_pos)}/{config.MAX_CONCURRENT_POSITIONS}")
        
        alert = (
            f"🎯 *NEW {side} SIGNAL*\n\n"
            f"• *Coin:* `{symbol}`\n"
            f"• *Entry:* `{entry_price}`\n"
            f"• *Contracts:* `{contracts}` (Value: ₹{config.POSITION_NOTIONAL_INR:,.0f})\n"
            f"• *Margin Used:* ₹{config.MARGIN_PER_TRADE:,.0f} @ {config.LEVERAGE}x\n"
            f"• *Stop Loss:* `{initial_sl}` (~-1.0%)\n"
            f"• *Target 1:* `{tp1_price}` (+3.5%)\n"
            f"• *Signal:* {signal['reason']}"
        )
        telegram_helper.send_alert(alert)

    def manage_positions(self):
        open_pos = self.client.paper_state["open_positions"]
        if not open_pos:
            return
            
        symbols = list(open_pos.keys())
        for sym in symbols:
            pos = open_pos[sym]
            side = pos['side']
            curr_price = self.client.get_mark_price(sym)
            if curr_price <= 0:
                continue
                
            entry_p = pos['entry_price']
            atr = pos['atr']
            
            if side == 'BUY':
                pos['peak_price'] = max(pos['peak_price'], curr_price)
                
                # Check Stop Loss
                if curr_price <= pos['current_sl']:
                    exit_p = pos['current_sl']
                    pnl_pct = (exit_p - entry_p) / entry_p
                    pnl_inr = config.POSITION_NOTIONAL_INR * pnl_pct
                    
                    print(f"\n🛑 [STOP LOSS HIT] {sym} (LONG) at {exit_p} | PnL: {pnl_pct*100:+.2f}% (₹{pnl_inr:+.1f} INR)")
                    
                    self.client.paper_state["wallet_balance"] += pnl_inr
                    self.client.paper_state["active_margin"] = max(0.0, self.client.paper_state["active_margin"] - config.MARGIN_PER_TRADE)
                    self.client.paper_state["trade_history"].append({
                        "symbol": sym, "side": side, "entry": entry_p, "exit": exit_p, "pnl_pct": pnl_pct, "pnl_inr": pnl_inr, "time": datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p')
                    })
                    del open_pos[sym]
                    self.client.save_paper_state()
                    
                    telegram_helper.send_alert(
                        f"🛑 *POSITION CLOSED (LONG)*\n\n"
                        f"• *Coin:* `{sym}`\n"
                        f"• *Exit Price:* `{exit_p}`\n"
                        f"• *PnL:* `{pnl_pct*100:+.2f}%` (*₹{pnl_inr:+.1f} INR*)\n"
                        f"• *Wallet Balance:* ₹{self.client.paper_state['wallet_balance']:,.1f}"
                    )
                    continue
                    
                # Check TP1 (+3.5%)
                if curr_price >= pos['tp1_price'] and not pos['tp1_hit']:
                    pos['tp1_hit'] = True
                    pos['current_sl'] = self.client.round_price(sym, entry_p * 1.001)
                    self.client.save_paper_state()
                    
                    print(f"\n🎉 [TP1 HIT] {sym} reached +3.5%! SL moved to BREAKEVEN ({pos['current_sl']}). Free slot opened!")
                    telegram_helper.send_alert(
                        f"🎉 *TP1 HIT (+3.5%) — {sym}*\n\n"
                        f"• 30% Profit Booked!\n"
                        f"• Stop Loss moved to *BREAKEVEN* (`{pos['current_sl']}`)\n"
                        f"• Trade is now *100% Risk-Free*!\n"
                        f"• 70% Runner riding with Trailing Stop."
                    )
                    
                # Trailing Stop for Runner
                if pos['tp1_hit']:
                    trail = self.client.round_price(sym, pos['peak_price'] - (1.4 * atr))
                    if trail > pos['current_sl']:
                        pos['current_sl'] = trail
                        self.client.save_paper_state()
                        
            elif side == 'SELL':
                pos['peak_price'] = min(pos['peak_price'], curr_price)
                
                # Check Stop Loss
                if curr_price >= pos['current_sl']:
                    exit_p = pos['current_sl']
                    pnl_pct = (entry_p - exit_p) / entry_p
                    pnl_inr = config.POSITION_NOTIONAL_INR * pnl_pct
                    
                    print(f"\n🛑 [STOP LOSS HIT] {sym} (SHORT) at {exit_p} | PnL: {pnl_pct*100:+.2f}% (₹{pnl_inr:+.1f} INR)")
                    
                    self.client.paper_state["wallet_balance"] += pnl_inr
                    self.client.paper_state["active_margin"] = max(0.0, self.client.paper_state["active_margin"] - config.MARGIN_PER_TRADE)
                    self.client.paper_state["trade_history"].append({
                        "symbol": sym, "side": side, "entry": entry_p, "exit": exit_p, "pnl_pct": pnl_pct, "pnl_inr": pnl_inr, "time": datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p')
                    })
                    del open_pos[sym]
                    self.client.save_paper_state()
                    
                    telegram_helper.send_alert(
                        f"🛑 *POSITION CLOSED (SHORT)*\n\n"
                        f"• *Coin:* `{sym}`\n"
                        f"• *Exit Price:* `{exit_p}`\n"
                        f"• *PnL:* `{pnl_pct*100:+.2f}%` (*₹{pnl_inr:+.1f} INR*)\n"
                        f"• *Wallet Balance:* ₹{self.client.paper_state['wallet_balance']:,.1f}"
                    )
                    continue
                    
                # Check TP1 (-3.5%)
                if curr_price <= pos['tp1_price'] and not pos['tp1_hit']:
                    pos['tp1_hit'] = True
                    pos['current_sl'] = self.client.round_price(sym, entry_p * 0.999)
                    self.client.save_paper_state()
                    
                    print(f"\n🎉 [TP1 HIT] {sym} (SHORT) reached +3.5%! SL moved to BREAKEVEN ({pos['current_sl']}).")
                    telegram_helper.send_alert(
                        f"🎉 *TP1 HIT (SHORT +3.5%) — {sym}*\n\n"
                        f"• Stop Loss moved to *BREAKEVEN* (`{pos['current_sl']}`)\n"
                        f"• Trade is now *100% Risk-Free*!\n"
                        f"• 70% Runner riding with Trailing Stop."
                    )
                    
                # Trailing Runner
                if pos['tp1_hit']:
                    trail = self.client.round_price(sym, pos['peak_price'] + (1.1 * atr))
                    if trail < pos['current_sl']:
                        pos['current_sl'] = trail
                        self.client.save_paper_state()

    def run(self):
        print(f"\n⚡ Live Scanner active. Scanning Top {len(self.client.products)} Pairs every {config.SCAN_INTERVAL_SECONDS}s...")
        cycle = 1
        while True:
            t_now = datetime.now(IST).strftime('%H:%M:%S')
            open_count = len(self.client.paper_state["open_positions"])
            print(f"[{t_now} IST] Cycle #{cycle} | Open Slots: {open_count}/{config.MAX_CONCURRENT_POSITIONS}   ", end="\r")
            
            self.manage_positions()
            
            for sym in list(self.client.products.keys()):
                if sym in self.client.paper_state["open_positions"]:
                    continue
                df = self.client.fetch_candles(sym, resolution=config.CANDLE_TIMEFRAME, count=30)
                if df.empty:
                    continue
                signal = self.strategy.check_signal(df)
                if signal:
                    self.execute_entry(sym, signal)
                    if len(self.client.paper_state["open_positions"]) >= config.MAX_CONCURRENT_POSITIONS:
                        break
            cycle += 1
            time.sleep(config.SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    # Start Embedded HTTP Server for Render Keep-Alive
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Start Self-Ping Thread to prevent Render Free Tier Sleep
    ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    ping_thread.start()
    
    bot = MomentumHunterBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped cleanly by user.")
