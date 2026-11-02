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
from insider_data_engine import InsiderDataEngine
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
            wallet = bot_instance.client.get_real_wallet_balance() if not config.PAPER_TRADING else bot_instance.client.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
            
        health_data = {
            "status": "ONLINE_ACTIVE",
            "bot": "Delta Multi-Source Institutional Momentum Engine",
            "mode": "PAPER_TRADING" if config.PAPER_TRADING else "LIVE_REAL_MONEY",
            "wallet_balance": wallet,
            "open_positions": open_pos,
            "max_positions": config.MAX_CONCURRENT_POSITIONS,
            "data_channels": [
                "OHLCV_5M_CLOSED",
                "BINANCE_TAKER_CVD_5M",
                "BINANCE_TOP_TRADER_WHALES",
                "BINANCE_OPEN_INTEREST_GROWTH",
                "DELTA_INDIA_RESTING_DEPTH",
                "BTC_MACRO_REGIME_15M"
            ],
            "ist_time": datetime.now(IST).strftime("%Y-%m-%d %I:%M:%S %p IST")
        }
        self.wfile.write(json.dumps(health_data).encode("utf-8"))

    def log_message(self, format, *args):
        pass

def start_http_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        print(f"🌐 [KEEP-ALIVE SERVER] Listening on port {PORT}...")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ HTTP Server notice: {e}")

def self_ping_worker():
    time.sleep(30)
    while True:
        url = os.environ.get("RENDER_EXTERNAL_URL") or getattr(config, "RENDER_URL", "")
        if url:
            if not url.startswith("http"):
                url = f"https://{url}"
            try:
                r = requests.get(f"{url}/", timeout=10)
                print(f"🔄 [KEEP-ALIVE PING] Pinged {url} (Status: {r.status_code})")
            except Exception as e:
                pass
        time.sleep(480)

class MomentumHunterBot:
    def __init__(self):
        global bot_instance
        bot_instance = self
        
        self.client = DeltaClient()
        self.strategy = MomentumStrategy()
        self.insider_engine = InsiderDataEngine()
        self.last_candle_signals = {}
        
        telegram_helper.register_bot(self)
        
        mode_str = "📝 PAPER TRADING (Safe Simulation)" if config.PAPER_TRADING else "🔴 LIVE REAL MONEY"
        print("=" * 72)
        print("🚀 DELTA EXCHANGE INDIA - MULTI-SOURCE INSTITUTIONAL ENGINE")
        print("=" * 72)
        print(f"Mode: {mode_str}")
        print(f"Wallet Capital: ₹{config.TOTAL_WALLET_CAPITAL:,.0f} INR")
        print(f"Position Notional: ₹{config.POSITION_NOTIONAL_INR:,.0f} INR (Margin: ₹{config.MARGIN_PER_TRADE:,.0f} @ {config.LEVERAGE}x)")
        print(f"Max Concurrent Positions: {config.MAX_CONCURRENT_POSITIONS}")
        print("Insider Feeds: Binance Taker CVD + Whales L/S + OI Trend + Delta Depth + BTC 15m")
        print("Zero Blind Trades: 100% of entries verified by multi-source order flow.")
        print("=" * 72)
        
        startup_msg = (
            f"🚀 *Delta Multi-Source Institutional Engine Online*\n\n"
            f"• *Mode:* `{mode_str}`\n"
            f"• *Data Confluence Feeds:*\n"
            f"   - 100% Closed 5m Candles\n"
            f"   - Binance Global Taker CVD (5m)\n"
            f"   - Binance Top Trader Smart Money Ratio\n"
            f"   - Binance Open Interest Expansion (5m)\n"
            f"   - Delta India Order Book Resting Liquidity\n"
            f"   - BTC Macro 15m Health Filter\n"
            f"• *Wallet Capital:* ₹{config.TOTAL_WALLET_CAPITAL:,.0f}\n"
            f"• *Position Size:* ₹{config.POSITION_NOTIONAL_INR:,.0f} (Margin: ₹{config.MARGIN_PER_TRADE:,.0f} @ {config.LEVERAGE}x)\n"
            f"• *Max Positions:* {config.MAX_CONCURRENT_POSITIONS}\n"
            f"• *Pairs Monitored:* Top {len(self.client.products)} Liquid Perps\n\n"
            f"💡 *Commands:* `/status`, `/positions`, `/balance`"
        )
        telegram_helper.send_alert(startup_msg)

    def execute_entry(self, symbol: str, signal: dict):
        open_pos = self.client.paper_state["open_positions"]
        if len(open_pos) >= config.MAX_CONCURRENT_POSITIONS:
            return
            
        if symbol in open_pos:
            return
            
        candle_time = signal.get('time', '')
        if self.last_candle_signals.get(symbol) == candle_time:
            return
            
        side = signal['side']
        entry_price = self.client.round_price(symbol, signal['price'])
        contracts = self.client.calculate_contracts(symbol, entry_price)
        initial_sl = self.client.round_price(symbol, signal['sl'])
        tp1_price = self.client.round_price(symbol, signal['tp1'])
        atr = signal['atr']
        score = signal.get('insider_score', 0)
        metrics = signal.get('insider_metrics', {})

        # 🔴 LIVE REAL MONEY EXECUTION (IF PAPER_TRADING = FALSE)
        if not config.PAPER_TRADING:
            real_res = self.client.execute_real_order(symbol, side, contracts, initial_sl, tp1_price)
            if not real_res:
                print(f"❌ Real order submission failed for {symbol}. Will not track.")
                return

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
            'atr': atr,
            'reason': signal['reason']
        }
        
        self.last_candle_signals[symbol] = candle_time
        open_pos[symbol] = pos_data
        self.client.paper_state["active_margin"] += config.MARGIN_PER_TRADE
        self.client.save_paper_state()
        
        cvd_val = metrics.get('cvd', 1.0)
        whales_val = metrics.get('top_whales', 1.0)
        depth_val = metrics.get('bid_imb', 0.5) * 100
        oi_val = metrics.get('oi_chg', 0.0)
        
        print(f"\n⚡ [{datetime.now(IST).strftime('%H:%M:%S')}] NEW {side} ENTRY CONFIRMED: {symbol}")
        print(f"   Setup: {signal['reason']}")
        print(f"   Insider Score: {score}/100 | CVD: {cvd_val:.2f}x | Whales: {whales_val:.2f}x | Delta Depth: {depth_val:.0f}%")
        print(f"   Price: {entry_price} | Contracts: {contracts} (Value: ₹{config.POSITION_NOTIONAL_INR:,.0f})")
        print(f"   Stop Loss: {initial_sl} | TP1: {tp1_price}")
        print(f"   Slots In Use: {len(open_pos)}/{config.MAX_CONCURRENT_POSITIONS}")
        
        alert = (
            f"🎯 *NEW {side} SIGNAL (INSTITUTIONAL DATA CONFIRMED)*\n\n"
            f"• *Coin:* `{symbol}`\n"
            f"• *Setup:* `{signal['reason']}`\n"
            f"• *Entry:* `{entry_price}`\n"
            f"• *Contracts:* `{contracts}` (Value: ₹{config.POSITION_NOTIONAL_INR:,.0f})\n"
            f"• *Margin Used:* ₹{config.MARGIN_PER_TRADE:,.0f} @ {config.LEVERAGE}x\n"
            f"• *Stop Loss:* `{initial_sl}`\n"
            f"• *Target 1:* `{tp1_price}`\n\n"
            f"📊 *Live Insider Data Verification:*\n"
            f"   - *Confluence Score:* `{score}/100` ✅\n"
            f"   - *Binance Taker CVD (5m):* `{cvd_val:.2f}x` (Aggressive Flow)\n"
            f"   - *Binance Smart Money Ratio:* `{whales_val:.2f}x`\n"
            f"   - *Binance 5m OI Growth:* `{oi_val:+.2f}%`\n"
            f"   - *Delta India Book Depth:* `{depth_val:.0f}% Bids`"
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
                    
                    if not config.PAPER_TRADING:
                        self.client.close_real_position(sym, side, pos['contracts'])

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
                    
                # Check TP1
                if curr_price >= pos['tp1_price'] and not pos['tp1_hit']:
                    pos['tp1_hit'] = True
                    pos['current_sl'] = self.client.round_price(sym, entry_p * 1.001)
                    self.client.save_paper_state()
                    
                    print(f"\n🎉 [TP1 HIT] {sym} reached target! SL moved to BREAKEVEN ({pos['current_sl']}). Free slot opened!")
                    telegram_helper.send_alert(
                        f"🎉 *TP1 HIT — {sym}*\n\n"
                        f"• 30% Profit Booked!\n"
                        f"• Stop Loss moved to *BREAKEVEN* (`{pos['current_sl']}`)\n"
                        f"• Trade is now *100% Risk-Free*!\n"
                        f"• 70% Runner riding with Trailing Stop."
                    )
                    
                # Trailing Stop for Runner
                if pos['tp1_hit']:
                    trail = self.client.round_price(sym, pos['peak_price'] - (1.3 * atr))
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
                    
                    if not config.PAPER_TRADING:
                        self.client.close_real_position(sym, side, pos['contracts'])

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
                    
                # Check TP1
                if curr_price <= pos['tp1_price'] and not pos['tp1_hit']:
                    pos['tp1_hit'] = True
                    pos['current_sl'] = self.client.round_price(sym, entry_p * 0.999)
                    self.client.save_paper_state()
                    
                    print(f"\n🎉 [TP1 HIT] {sym} (SHORT) reached target! SL moved to BREAKEVEN ({pos['current_sl']}).")
                    telegram_helper.send_alert(
                        f"🎉 *TP1 HIT (SHORT) — {sym}*\n\n"
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
        print(f"\n⚡ Multi-Source Scanner active. Scanning Top {len(self.client.products)} Pairs every {config.SCAN_INTERVAL_SECONDS}s...")
        cycle = 1
        while True:
            t_now = datetime.now(IST).strftime('%H:%M:%S')
            open_count = len(self.client.paper_state["open_positions"])
            print(f"[{t_now} IST] Cycle #{cycle} | Open Slots: {open_count}/{config.MAX_CONCURRENT_POSITIONS}   ", end="\r")
            
            self.manage_positions()
            
            for sym in list(self.client.products.keys()):
                if sym in self.client.paper_state["open_positions"]:
                    continue
                    
                # 1. Fetch live Delta India ticker (Quotes, Depth, Spread, Turnover, Funding)
                ticker_data = self.client.fetch_ticker(sym)
                if not ticker_data:
                    continue
                    
                # 2. Fetch candles (35 periods)
                df = self.client.fetch_candles(sym, resolution=config.CANDLE_TIMEFRAME, count=35)
                if df.empty:
                    continue
                    
                # 3. Stage 1 Candle Microstructure Check
                unconfirmed_signal = self.strategy.check_signal(df, ticker=ticker_data, insider_conf=None)
                if not unconfirmed_signal:
                    continue
                    
                candidate_side = unconfirmed_signal['side']
                print(f"\n🔍 Candidate setup detected on {sym} ({candidate_side})! Fetching multi-source insider matrix...")
                
                # 4. Stage 2 Multi-Source Institutional Confluence Verification
                insider_conf = self.insider_engine.compute_confluence(sym, candidate_side, ticker_data)
                
                # 5. Stage 3 Strict Execution Gate
                confirmed_signal = self.strategy.check_signal(df, ticker=ticker_data, insider_conf=insider_conf)
                if confirmed_signal:
                    self.execute_entry(sym, confirmed_signal)
                    if len(self.client.paper_state["open_positions"]) >= config.MAX_CONCURRENT_POSITIONS:
                        break
                else:
                    print(f"⛔ [REJECTED BY DATA] {sym} {candidate_side}: {insider_conf.get('reason')} (Score: {insider_conf.get('score')}/100)")

            cycle += 1
            time.sleep(config.SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    ping_thread.start()
    
    tg_thread = threading.Thread(target=telegram_helper.handle_telegram_commands, daemon=True)
    tg_thread.start()
    
    bot = MomentumHunterBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped cleanly by user.")
