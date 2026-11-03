import os
import sys
import time
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta
import requests
import config
import ai_advisor
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
            "bot": "Whale Golden Pocket OTE & Smart Money Quant Engine",
            "mode": "PAPER_TRADING" if config.PAPER_TRADING else "LIVE_REAL_MONEY",
            "discipline_state": ai_advisor.get_psychology_state(),
            "wallet_balance": wallet,
            "open_positions": open_pos,
            "max_positions": config.MAX_CONCURRENT_POSITIONS,
            "architecture": [
                "ANTI_CLIMAX_PEAK_GUARD_4PCT",
                "BOTTOM_LIQUIDITY_SWEEP_RECLAIM",
                "EMA_10_20_GOLDEN_SHIFT",
                "FIB_0.50_0.618_OTE_DISCOUNT",
                "SHELTERED_SWING_SL_0.60PCT_MAX",
                "60PCT_TP1_CASH_HARVEST",
                "BREATHING_ROOM_TRAILING_SL",
                "AI_PSYCHOLOGY_DISCIPLINE_STATE_MACHINE"
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
            try:
                requests.get(url, timeout=10)
                print("⚡ [SELF-PING] Render keep-alive ping successful.")
            except Exception as e:
                print(f"⚠️ [SELF-PING ERROR] {e}")
        time.sleep(300)

class ScalperBot:
    def __init__(self):
        print("\n" + "="*80)
        print("   WHALE GOLDEN POCKET OTE & SMART MONEY QUANT ENGINE (DELTA INDIA)")
        print(f"   Architecture: Bottom Sweep + Fib 0.50-0.618 OTE + Sheltered SL + AI Advisor")
        print(f"   Mode: {'VIRTUAL PAPER TRADING' if config.PAPER_TRADING else 'LIVE REAL MONEY TRADING'}")
        print("="*80 + "\n")
        
        self.client = DeltaClient()
        self.insider_engine = InsiderDataEngine()
        self.symbols = list(self.client.products.keys())
        self.last_candle_signals = {}
        
        # Load AI Overrides and register telegram reference
        ai_advisor.load_ai_overrides(config)
        telegram_helper.register_bot(self)
        
        print(f"✅ Loaded {len(self.symbols)} active high-turnover perpetual coins.")
        wallet_bal = self.client.get_real_wallet_balance() if not config.PAPER_TRADING else self.client.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
        print(f"💼 Available Capital: ₹{wallet_bal:,.2f} INR")
        print(f"🛡️ Hard Loss Limit per Trade: ₹{getattr(config, 'MAX_LOSS_PER_TRADE_INR', 36.0):.2f} INR")
        print(f"🎯 Dynamic TP1 Cash Harvest: {ai_advisor.get_dynamic_tp1_book_ratio()*100:.0f}% Position")
        print(f"🧠 AI Psychology Discipline: {ai_advisor.get_psychology_state()} MODE\n")
        
        mode_str = "VIRTUAL PAPER TRADING (SAFE)" if config.PAPER_TRADING else "LIVE REAL MONEY TRADING (REAL INR)"
        p_state = ai_advisor.get_psychology_state()
        state_icon = "🟢" if p_state == "NORMAL" else ("🛡️" if p_state == "DEFENSIVE" else "🔥")
        
        startup_msg = (
            f"🚀 *[BOT ONLINE — WHALE OTE & AI ADVISOR ACTIVE]*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Mode: *{mode_str}*\n"
            f"• Capital: *₹{wallet_bal:,.2f} INR*\n"
            f"• Architecture: *Whale Bottom Sweep + Fib 0.50-0.618 OTE*\n"
            f"• AI State: *{state_icon} {p_state} MODE*\n"
            f"• Max Loss Cap: *₹{getattr(config, 'MAX_LOSS_PER_TRADE_INR', 36.0):.2f} INR* per trade\n"
            f"• TP1 Cash Harvest: *{ai_advisor.get_dynamic_tp1_book_ratio()*100:.0f}% Position*\n"
            f"• Scanned Coins: *{len(self.symbols)} Pairs*\n"
            f"• Time: *{datetime.now(IST).strftime('%d-%b-%Y %I:%M:%S %p IST')}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Commands: `/ai` | `/status` | `/positions` | `/pnl` | `/balance`"
        )
        telegram_helper.send_alert(startup_msg)

    def execute_entry(self, symbol: str, signal: dict):
        open_pos = self.client.paper_state["open_positions"]
        if len(open_pos) >= config.MAX_CONCURRENT_POSITIONS:
            return
            
        if symbol in open_pos:
            return

        # Check AI coin suspension
        is_susp, susp_msg = ai_advisor.is_coin_suspended(symbol)
        if is_susp:
            print(f"⏸️ [AI FILTER] {symbol} rejected: {susp_msg}")
            return
            
        candle_time = signal.get('time', '')
        if self.last_candle_signals.get(symbol) == candle_time:
            return
            
        side = signal['side']
        entry_price = self.client.round_price(symbol, signal['price'])
        
        # Dynamic position size scaled by AI discipline state machine
        size_mult = ai_advisor.get_position_size_multiplier()
        notional_budget = config.POSITION_NOTIONAL_INR * size_mult
        margin_used = config.MARGIN_PER_TRADE * size_mult
        
        # Calculate contracts based on dynamic notional budget
        spec = self.client.products.get(symbol)
        if not spec or spec.get('contract_value', 0) <= 0:
            return
        notional_usd = notional_budget / config.USD_INR_RATE
        contract_val_usd = entry_price * spec['contract_value']
        contracts = max(1, int(round(notional_usd / contract_val_usd)))

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
            'micro_be_hit': False,
            'tp1_booked_inr': 0.0,
            'peak_price': entry_price,
            'notional_inr': notional_budget,
            'margin_inr': margin_used,
            'entry_timestamp': time.time(),
            'entry_time': datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p IST'),
            'atr': atr,
            'reason': signal['reason']
        }
        
        self.last_candle_signals[symbol] = candle_time
        open_pos[symbol] = pos_data
        self.client.paper_state["active_margin"] += margin_used
        self.client.save_paper_state()
        
        cvd_val = metrics.get('cvd', 1.0)
        whales_val = metrics.get('top_whales', 1.0)
        depth_val = metrics.get('bid_imb', 0.5) * 100
        sl_diff_pct = abs(initial_sl - entry_price) / entry_price * 100
        tp_diff_pct = abs(tp1_price - entry_price) / entry_price * 100
        
        print(f"\n⚡ [{datetime.now(IST).strftime('%H:%M:%S')}] NEW {side} ENTRY SNIPED: {symbol}")
        print(f"   Setup: {signal['reason']}")
        print(f"   Price: {entry_price} | Contracts: {contracts} (Value: ₹{notional_budget:,.0f} INR)")
        print(f"   Sheltered SL: {initial_sl} (-{sl_diff_pct:.2f}%) | TP1: {tp1_price} (+{tp_diff_pct:.2f}%)")
        print(f"   Slots In Use: {len(open_pos)}/{config.MAX_CONCURRENT_POSITIONS}")
        
        alert = (
            f"🎯 *[NEW WHALE OTE SNIPER ENTRY]* 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 *Coin:* `{symbol}` (*{side}*)\n"
            f"📥 *Discount Entry:* `${entry_price}`\n"
            f"📦 *Position Size:* `{contracts} Contracts` (*₹{notional_budget:,.0f} INR*)\n"
            f"🛡️ *Margin Used:* `₹{margin_used:,.0f} INR` ({config.LEVERAGE}x Leverage)\n"
            f"🛑 *Sheltered SL:* `${initial_sl}` (*-{sl_diff_pct:.2f}%*)\n"
            f"🎯 *TP1 Target:* `${tp1_price}` (*+{tp_diff_pct:.2f}%*)\n\n"
            f"📊 *Confluence & Quality:* `{score}/100` ✅\n"
            f"• Setup: _{signal['reason']}_\n"
            f"• AI State: *{ai_advisor.get_psychology_state()} MODE*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━"
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
            pos_notional = pos.get('notional_inr', config.POSITION_NOTIONAL_INR)
            pos_margin = pos.get('margin_inr', config.MARGIN_PER_TRADE)
            
            # Dynamic TP1 Book ratio from AI Advisor
            tp1_ratio = ai_advisor.get_dynamic_tp1_book_ratio()
            runner_ratio = 1.0 - tp1_ratio
            
            # ==================================================================
            # 🟢 BUY / LONG POSITION MANAGEMENT
            # ==================================================================
            if side == 'BUY':
                pos['peak_price'] = max(pos['peak_price'], curr_price)
                peak_gain_pct = (pos['peak_price'] - entry_p) / entry_p
                cur_gain_pct = (curr_price - entry_p) / entry_p
                
                # 1. BREATHING ROOM MICRO-BE (+1.10% peak move -> lock +0.50% profit)
                if not pos.get('micro_be_hit') and peak_gain_pct >= getattr(config, 'MICRO_BE_TRIGGER_PCT', 0.0110):
                    pos['micro_be_hit'] = True
                    lock_p = entry_p * (1.0 + getattr(config, 'MICRO_BE_LOCK_PCT', 0.0050))
                    pos['current_sl'] = self.client.round_price(sym, lock_p)
                    self.client.save_paper_state()
                    print(f"🛡️ [MICRO-BE ACTIVATED] {sym} peaked +{peak_gain_pct*100:.2f}%. SL shifted to +0.50% lock ({pos['current_sl']}), leaving 0.60% breathing room.")

                # 2. CHECK TP1 HIT (+1.50% Target 1: Book 60% Cash)
                if curr_price >= pos['tp1_price'] and not pos['tp1_hit']:
                    pos['tp1_hit'] = True
                    tp1_pnl_pct = (curr_price - entry_p) / entry_p
                    tp1_booked_inr = (pos_notional * tp1_ratio) * tp1_pnl_pct
                    pos['tp1_booked_inr'] = tp1_booked_inr
                    
                    self.client.paper_state["wallet_balance"] += tp1_booked_inr
                    
                    # Move SL to lock +0.80% on remaining runner
                    lock_sl = self.client.round_price(sym, entry_p * (1.0 + getattr(config, 'TP1_SL_LOCK_PCT', 0.0080)))
                    pos['current_sl'] = lock_sl
                    self.client.save_paper_state()
                    
                    print(f"\n🎉 [TP1 HIT] {sym} reached target! Booked +₹{tp1_booked_inr:.2f} INR ({tp1_ratio*100:.0f}% Size)! SL moved to {pos['current_sl']}.")
                    
                    telegram_helper.send_alert(
                        f"🎯 *[TARGET 1 REACHED — {tp1_ratio*100:.0f}% CASH BOOKED]* ✅\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🪙 *Coin:* `{sym}` (*LONG*)\n"
                        f"📥 *Entry Price:* `${entry_p}`\n"
                        f"🎯 *TP1 Target Price:* `${curr_price}`\n"
                        f"📈 *Move Captured:* `+{tp1_pnl_pct*100:.2f}%`\n"
                        f"💰 *CASH IN WALLET:* `+₹{tp1_booked_inr:.2f} INR`\n\n"
                        f"🛡️ *Risk-Free Runner Active:*\n"
                        f"• Stop Loss locked in profit at *+0.80%* (`${pos['current_sl']}`)\n"
                        f"• Remaining {runner_ratio*100:.0f}% Position riding risk-free towards TP2 (+3.0%)!\n"
                        f"💼 *Wallet Balance:* `₹{self.client.paper_state['wallet_balance']:,.2f} INR`\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━"
                    )

                # 3. CHECK STOP LOSS / EMERGENCY LOSS / TRAIL EXIT
                live_pnl_pct = (curr_price - entry_p) / entry_p
                live_pnl_inr = pos_notional * live_pnl_pct
                hard_cap = getattr(config, 'MAX_LOSS_PER_TRADE_INR', 36.0)
                
                is_sl_hit = curr_price <= pos['current_sl']
                is_emergency_loss = (live_pnl_inr <= -hard_cap) and not pos.get('tp1_hit')

                if is_sl_hit or is_emergency_loss:
                    exit_p = curr_price if is_emergency_loss else pos['current_sl']
                    pnl_pct = (exit_p - entry_p) / entry_p
                    
                    weight = runner_ratio if pos.get('tp1_hit') else 1.00
                    runner_inr = (pos_notional * weight) * pnl_pct
                    total_pnl_inr = pos.get('tp1_booked_inr', 0.0) + runner_inr
                    
                    if not config.PAPER_TRADING:
                        self.client.close_real_position(sym, side, pos['contracts'])

                    self.client.paper_state["wallet_balance"] += runner_inr
                    self.client.paper_state["active_margin"] = max(0.0, self.client.paper_state["active_margin"] - pos_margin)
                    
                    exit_reason = "Protected Profit / Trailing Stop" if total_pnl_inr > 0 else ("Sheltered Swing Stop Hit" if is_sl_hit else "Emergency Loss Floor (-₹36)")
                    
                    trade_record = {
                        "symbol": sym, "side": side, "entry": entry_p, "exit": exit_p, 
                        "pnl_pct": pnl_pct, "pnl_inr": total_pnl_inr, 
                        "entry_time": pos.get('entry_timestamp', time.time()),
                        "exit_time": time.time(),
                        "time": datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p'),
                        "reason": exit_reason
                    }
                    self.client.paper_state["trade_history"].append(trade_record)
                    del open_pos[sym]
                    self.client.save_paper_state()
                    
                    # 🧠 AI ADVISOR POST-MORTEM & DISCIPLINE UPDATE
                    ai_advisor.record_trade_exit(trade_record, self.client, config)
                    
                    wallet_now = self.client.paper_state['wallet_balance']
                    if total_pnl_inr >= 0:
                        print(f"\n💰 [PROFIT EXIT] {sym} (LONG) at {exit_p} | Net Profit: +₹{total_pnl_inr:.2f} INR")
                        telegram_helper.send_alert(
                            f"💰 *[TRADE COMPLETED — NET PROFIT BOOKED]* 🟢\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🪙 *Coin:* `{sym}` (*LONG*)\n"
                            f"📥 *Entry Price:* `${entry_p}`\n"
                            f"📤 *Exit Price:* `${exit_p}`\n"
                            f"📈 *Move Realized:* `{pnl_pct*100:+.2f}%`\n\n"
                            f"💵 *NET PROFIT ON TRADE:* `+₹{total_pnl_inr:.2f} INR` 🚀\n"
                            f"💼 *Updated Wallet Balance:* `₹{wallet_now:,.2f} INR`\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━"
                        )
                    else:
                        print(f"\n🛑 [STOP LOSS HIT] {sym} (LONG) at {exit_p} | Capped Loss: -₹{abs(total_pnl_inr):.2f} INR")
                        telegram_helper.send_alert(
                            f"🛑 *[STOP LOSS TRIGGERED — LOSS PROTECTED]* 🔴\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🪙 *Coin:* `{sym}` (*LONG*)\n"
                            f"📥 *Entry Price:* `${entry_p}`\n"
                            f"📤 *Exit Price:* `${exit_p}`\n"
                            f"📉 *Move:* `{pnl_pct*100:+.2f}%`\n\n"
                            f"🛡️ *CAPPED LOSS:* `-₹{abs(total_pnl_inr):.2f} INR` (Strict Risk Shield)\n"
                            f"💼 *Remaining Wallet Capital:* `₹{wallet_now:,.2f} INR`\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━"
                        )
                    continue

                # Trailing Stop for Runner
                if pos['tp1_hit']:
                    trail = self.client.round_price(sym, pos['peak_price'] - (0.007 * pos['peak_price']))
                    if trail > pos['current_sl']:
                        pos['current_sl'] = trail
                        self.client.save_paper_state()

            # ==================================================================
            # 🔴 SELL / SHORT POSITION MANAGEMENT
            # ==================================================================
            elif side == 'SELL':
                pos['peak_price'] = min(pos['peak_price'], curr_price)
                peak_gain_pct = (entry_p - pos['peak_price']) / entry_p
                cur_gain_pct = (entry_p - curr_price) / entry_p
                
                # 1. BREATHING ROOM MICRO-BE (+1.10% peak gain -> lock +0.50% profit)
                if not pos.get('micro_be_hit') and peak_gain_pct >= getattr(config, 'MICRO_BE_TRIGGER_PCT', 0.0110):
                    pos['micro_be_hit'] = True
                    lock_p = entry_p * (1.0 - getattr(config, 'MICRO_BE_LOCK_PCT', 0.0050))
                    pos['current_sl'] = self.client.round_price(sym, lock_p)
                    self.client.save_paper_state()
                    print(f"🛡️ [MICRO-BE ACTIVATED] {sym} peaked +{peak_gain_pct*100:.2f}%. SL shifted to +0.50% lock ({pos['current_sl']}), leaving 0.60% breathing room.")

                # 2. CHECK TP1 HIT (+1.50% Target 1: Book 60% Cash)
                if curr_price <= pos['tp1_price'] and not pos['tp1_hit']:
                    pos['tp1_hit'] = True
                    tp1_pnl_pct = (entry_p - curr_price) / entry_p
                    tp1_booked_inr = (pos_notional * tp1_ratio) * tp1_pnl_pct
                    pos['tp1_booked_inr'] = tp1_booked_inr
                    
                    self.client.paper_state["wallet_balance"] += tp1_booked_inr
                    lock_sl = self.client.round_price(sym, entry_p * (1.0 - getattr(config, 'TP1_SL_LOCK_PCT', 0.0080)))
                    pos['current_sl'] = lock_sl
                    self.client.save_paper_state()
                    
                    print(f"\n🎉 [TP1 HIT] {sym} (SHORT) reached target! Booked +₹{tp1_booked_inr:.2f} INR ({tp1_ratio*100:.0f}% Size)! SL moved to {pos['current_sl']}.")
                    
                    telegram_helper.send_alert(
                        f"🎯 *[TARGET 1 REACHED — {tp1_ratio*100:.0f}% CASH BOOKED]* ✅\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🪙 *Coin:* `{sym}` (*SHORT*)\n"
                        f"📥 *Entry Price:* `${entry_p}`\n"
                        f"🎯 *TP1 Target Price:* `${curr_price}`\n"
                        f"📈 *Move Captured:* `+{tp1_pnl_pct*100:.2f}%`\n"
                        f"💰 *CASH IN WALLET:* `+₹{tp1_booked_inr:.2f} INR`\n\n"
                        f"🛡️ *Risk-Free Runner Active:*\n"
                        f"• Stop Loss locked in profit at *+0.80%* (`${pos['current_sl']}`)\n"
                        f"• Remaining {runner_ratio*100:.0f}% Position riding risk-free towards TP2 (+3.0%)!\n"
                        f"💼 *Wallet Balance:* `₹{self.client.paper_state['wallet_balance']:,.2f} INR`\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━"
                    )

                # 3. CHECK STOP LOSS / EMERGENCY LOSS / TRAIL EXIT
                live_pnl_pct = (entry_p - curr_price) / entry_p
                live_pnl_inr = pos_notional * live_pnl_pct
                hard_cap = getattr(config, 'MAX_LOSS_PER_TRADE_INR', 36.0)
                
                is_sl_hit = curr_price >= pos['current_sl']
                is_emergency_loss = (live_pnl_inr <= -hard_cap) and not pos.get('tp1_hit')

                if is_sl_hit or is_emergency_loss:
                    exit_p = curr_price if is_emergency_loss else pos['current_sl']
                    pnl_pct = (entry_p - exit_p) / entry_p
                    
                    weight = runner_ratio if pos.get('tp1_hit') else 1.00
                    runner_inr = (pos_notional * weight) * pnl_pct
                    total_pnl_inr = pos.get('tp1_booked_inr', 0.0) + runner_inr
                    
                    if not config.PAPER_TRADING:
                        self.client.close_real_position(sym, side, pos['contracts'])

                    self.client.paper_state["wallet_balance"] += runner_inr
                    self.client.paper_state["active_margin"] = max(0.0, self.client.paper_state["active_margin"] - pos_margin)
                    
                    exit_reason = "Protected Profit / Trailing Stop" if total_pnl_inr > 0 else ("Sheltered Swing Stop Hit" if is_sl_hit else "Emergency Loss Floor (-₹36)")
                    
                    trade_record = {
                        "symbol": sym, "side": side, "entry": entry_p, "exit": exit_p, 
                        "pnl_pct": pnl_pct, "pnl_inr": total_pnl_inr, 
                        "entry_time": pos.get('entry_timestamp', time.time()),
                        "exit_time": time.time(),
                        "time": datetime.now(IST).strftime('%Y-%m-%d %I:%M:%S %p'),
                        "reason": exit_reason
                    }
                    self.client.paper_state["trade_history"].append(trade_record)
                    del open_pos[sym]
                    self.client.save_paper_state()
                    
                    # 🧠 AI ADVISOR POST-MORTEM & DISCIPLINE UPDATE
                    ai_advisor.record_trade_exit(trade_record, self.client, config)
                    
                    wallet_now = self.client.paper_state['wallet_balance']
                    if total_pnl_inr >= 0:
                        print(f"\n💰 [PROFIT EXIT] {sym} (SHORT) at {exit_p} | Net Profit: +₹{total_pnl_inr:.2f} INR")
                        telegram_helper.send_alert(
                            f"💰 *[TRADE COMPLETED — NET PROFIT BOOKED]* 🟢\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🪙 *Coin:* `{sym}` (*SHORT*)\n"
                            f"📥 *Entry Price:* `${entry_p}`\n"
                            f"📤 *Exit Price:* `${exit_p}`\n"
                            f"📈 *Move Realized:* `{pnl_pct*100:+.2f}%`\n\n"
                            f"💵 *NET PROFIT ON TRADE:* `+₹{total_pnl_inr:.2f} INR` 🚀\n"
                            f"💼 *Updated Wallet Balance:* `₹{wallet_now:,.2f} INR`\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━"
                        )
                    else:
                        print(f"\n🛑 [STOP LOSS HIT] {sym} (SHORT) at {exit_p} | Capped Loss: -₹{abs(total_pnl_inr):.2f} INR")
                        telegram_helper.send_alert(
                            f"🛑 *[STOP LOSS TRIGGERED — LOSS PROTECTED]* 🔴\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"🪙 *Coin:* `{sym}` (*SHORT*)\n"
                            f"📥 *Entry Price:* `${entry_p}`\n"
                            f"📤 *Exit Price:* `${exit_p}`\n"
                            f"📉 *Move:* `{pnl_pct*100:+.2f}%`\n\n"
                            f"🛡️ *CAPPED LOSS:* `-₹{abs(total_pnl_inr):.2f} INR` (Strict Risk Shield)\n"
                            f"💼 *Remaining Wallet Capital:* `₹{wallet_now:,.2f} INR`\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━"
                        )
                    continue

                if pos['tp1_hit']:
                    trail = self.client.round_price(sym, pos['peak_price'] + (0.007 * pos['peak_price']))
                    if trail < pos['current_sl']:
                        pos['current_sl'] = trail
                        self.client.save_paper_state()

    def run_scan_loop(self):
        print("🔄 [SCAN LOOP] Continuous Whale Golden Pocket OTE Market Scanner Started...\n")
        
        while True:
            try:
                # 1. Manage Active Positions
                self.manage_positions()
                
                open_count = len(self.client.paper_state["open_positions"])
                if open_count >= config.MAX_CONCURRENT_POSITIONS:
                    time.sleep(config.SCAN_INTERVAL_SECONDS)
                    continue
                    
                # 2. Fetch Multi-Source Institutional Confluence
                btc_safe = self.insider_engine.is_btc_safe()
                if not btc_safe:
                    time.sleep(config.SCAN_INTERVAL_SECONDS)
                    continue

                # 3. Scan High-Turnover Coins for Whale OTE Setups
                for sym in self.symbols:
                    if sym in self.client.paper_state["open_positions"]:
                        continue

                    df = self.client.fetch_candles(sym, count=60)
                    if df.empty or len(df) < 30:
                        continue
                        
                    ticker = self.client.fetch_ticker(sym)
                    if not ticker:
                        continue
                        
                    # Calculate Technical Golden Pocket Signal with AI Filter
                    signal = MomentumStrategy.check_signal(df, ticker=ticker, symbol=sym)
                    if not signal:
                        continue
                        
                    # 4. Mandatory Institutional Confluence Check
                    confirmed_signal = self.insider_engine.evaluate_confluence(sym, signal, ticker)
                    if not confirmed_signal:
                        continue
                        
                    # Execute Entry
                    self.execute_entry(sym, confirmed_signal)
                    if len(self.client.paper_state["open_positions"]) >= config.MAX_CONCURRENT_POSITIONS:
                        break
                        
            except Exception as e:
                print(f"⚠️ [SCAN LOOP EXCEPTION] {e}")
                
            time.sleep(config.SCAN_INTERVAL_SECONDS)

if __name__ == "__main__":
    t_http = threading.Thread(target=start_http_server, daemon=True)
    t_http.start()
    
    t_ping = threading.Thread(target=self_ping_worker, daemon=True)
    t_ping.start()
    
    t_tg = threading.Thread(target=telegram_helper.handle_telegram_commands, daemon=True)
    t_tg.start()

    bot_instance = ScalperBot()
    bot_instance.run_scan_loop()
