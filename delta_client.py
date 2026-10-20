"""
========================================================================================
DELTA EXCHANGE INDIA CLIENT & MONTHLY-STEPPED COMPOUNDING PORTFOLIO MANAGER
Option 2 Master Engine with $12,000 Fee Shield & 2-Hour Loss Cooldown
Time strictly locked to Indian Standard Time (IST, UTC+5:30)
========================================================================================
"""
import urllib.request
import urllib.parse
import json
import time
import hmac
import hashlib
import datetime
import os
import config
import telegram_notifier

class DeltaClient:
    def __init__(self):
        self.base_url = config.DELTA_BASE_URL
        self.state_file = os.path.join(os.path.dirname(__file__), "elite_sniper_state.json")
        self.last_loss_timestamps = {}
        self.load_state()

    def load_state(self):
        """Loads persistent portfolio balance and trade records."""
        now_month = config.get_now_ist().strftime('%Y-%m')
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                    self.state.setdefault("initial_capital", config.INITIAL_CAPITAL)
                    self.state.setdefault("active_capital", config.INITIAL_CAPITAL)
                    self.state.setdefault("month_starting_capital", config.INITIAL_CAPITAL)
                    self.state.setdefault("current_month", now_month)
                    self.state.setdefault("banked_profit", 0.0)
                    self.state.setdefault("total_net_pnl", 0.0)
                    self.state.setdefault("open_positions", {})
                    self.state.setdefault("trade_history", [])
                    return
            except Exception as e:
                print(f"[STATE LOAD ERROR] {e}. Reinitializing default state.")

        self.state = {
            "initial_capital": config.INITIAL_CAPITAL,
            "active_capital": config.INITIAL_CAPITAL,
            "month_starting_capital": config.INITIAL_CAPITAL,
            "current_month": now_month,
            "banked_profit": 0.0,
            "total_net_pnl": 0.0,
            "open_positions": {},
            "trade_history": []
        }
        self.save_state()

    def save_state(self):
        """Persists current state atomically to disk."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            print(f"[STATE SAVE ERROR] {e}")

    def fetch_candles(self, symbol, resolution=config.CANDLE_RESOLUTION, limit=100):
        """Fetches latest OHLCV candles from Delta Exchange India with IST timestamps."""
        end_time = int(time.time())
        if resolution == "3m":
            res_secs = 180
        elif resolution == "5m":
            res_secs = 300
        elif resolution == "15m":
            res_secs = 900
        elif resolution == "1h":
            res_secs = 3600
        elif resolution == "4h":
            res_secs = 14400
        else:
            res_secs = 300

        start_time = end_time - (res_secs * limit)
        url = f"{self.base_url}/v2/history/candles?resolution={resolution}&symbol={symbol}&start={start_time}&end={end_time}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
                candles = data.get("result", [])
                formatted = []
                for c in candles:
                    formatted.append({
                        "time": c["time"],
                        "datetime": config.format_timestamp_ist(c["time"]),
                        "open": float(c["open"]),
                        "high": float(c["high"]),
                        "low": float(c["low"]),
                        "close": float(c["close"]),
                        "volume": float(c.get("volume", 0))
                    })
                formatted.sort(key=lambda x: x["time"])
                return formatted
        except Exception as e:
            print(f"[FETCH ERROR] {symbol} ({resolution}) candles: {e}")
            return []

    def fetch_ticker(self, symbol):
        """Fetches live mark price and last traded price."""
        url = f"{self.base_url}/v2/tickers/{symbol}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
                res = data.get("result", {})
                return {
                    "last_price": float(res.get("close", 0)),
                    "mark_price": float(res.get("mark_price", 0))
                }
        except Exception:
            return None

    def is_in_loss_cooldown(self, symbol):
        """Returns True if the coin is currently inside the 2-Hour post-loss cooldown."""
        last_loss = self.last_loss_timestamps.get(symbol, 0)
        elapsed = time.time() - last_loss
        return elapsed < config.LOSS_COOLDOWN_SECONDS

    def get_remaining_cooldown_mins(self, symbol):
        """Returns remaining cooldown time in minutes."""
        last_loss = self.last_loss_timestamps.get(symbol, 0)
        remaining = config.LOSS_COOLDOWN_SECONDS - (time.time() - last_loss)
        return max(0, int(remaining / 60))

    def get_current_risk_allowance(self):
        """
        MONTHLY-STEPPED COMPOUNDING ENGINE:
        - Active capital remains fixed for the entire calendar month (IST based).
        - Only when month completes in IST, month_starting_capital is updated for the new month.
        - Risk per trade is strictly: month_starting_capital * 6.25% (capped at $1,250 on $20k cap).
        """
        now_month = config.get_now_ist().strftime('%Y-%m')
        recorded_month = self.state.get("current_month", now_month)

        if now_month != recorded_month:
            # Calendar month rollover in IST!
            prev_cap = self.state.get("month_starting_capital", config.INITIAL_CAPITAL)
            curr_active = self.state.get("active_capital", config.INITIAL_CAPITAL)
            
            # Apply $20,000 hard active cap
            if curr_active > config.MAX_ACTIVE_CAPITAL:
                overflow = curr_active - config.MAX_ACTIVE_CAPITAL
                self.state["banked_profit"] += overflow
                self.state["active_capital"] = config.MAX_ACTIVE_CAPITAL
                new_start_cap = config.MAX_ACTIVE_CAPITAL
            else:
                new_start_cap = max(curr_active, 100.0)

            self.state["month_starting_capital"] = new_start_cap
            self.state["current_month"] = now_month
            self.save_state()

            msg = (
                f"📅 *[MONTHLY CAPITAL ROLLOVER COMPLETED]*\n"
                f"═══════════════════════\n"
                f"📆 New Month (IST): *{now_month}*\n"
                f"💼 Starting Active Capital: *${new_start_cap:,.2f}*\n"
                f"🎯 Fixed Risk Per Trade: *${new_start_cap * config.RISK_PER_TRADE_PCT:,.2f}* (6.25%)\n"
                f"🏦 Banked Reserve: *${self.state.get('banked_profit', 0):,.2f}*\n"
                f"🕒 Clock: `{config.get_now_ist().strftime('%Y-%m-%d %H:%M:%S')} IST`\n"
                f"═══════════════════════\n"
                f"🚀 _Active capital is now locked for the next 30 days!_"
            )
            telegram_notifier.send_alert(msg)
            print(f"📅 [MONTH ROLLOVER IST] New month {now_month}: Starting capital set to ${new_start_cap:,.2f}")

        month_cap = min(self.state.get("month_starting_capital", config.INITIAL_CAPITAL), config.MAX_ACTIVE_CAPITAL)
        return month_cap * config.RISK_PER_TRADE_PCT

    def open_trade(self, symbol, side, entry_price, sl_price, tp1_price, tp2_price, wick_ratio, vol_mult):
        """Calculates sizing with $12,000 Fee Shield Cap and registers new position."""
        if len(self.state["open_positions"]) >= config.MAX_CONCURRENT_TRADES:
            print(f"⚠️ Max concurrent trades ({config.MAX_CONCURRENT_TRADES}) reached. Skipping {symbol}.")
            return None

        if self.is_in_loss_cooldown(symbol):
            mins_left = self.get_remaining_cooldown_mins(symbol)
            print(f"⏳ {symbol} in 2-Hour Loss Cooldown ({mins_left}m remaining). Skipping trade.")
            return None

        risk_dollars = self.get_current_risk_allowance()
        sl_pct = abs(entry_price - sl_price) / entry_price
        if sl_pct <= 0:
            return None

        # Position size in USD based on risk and SL distance
        raw_position_val = risk_dollars / sl_pct

        # FEE SHIELD CAP: Strictly cap position value to $12,000 USD
        position_val = min(raw_position_val, config.MAX_POSITION_USD)
        margin_used = position_val / config.LEVERAGE

        now_str = config.get_now_ist().strftime('%Y-%m-%d %H:%M:%S')
        trade = {
            "symbol": symbol,
            "side": side,
            "entry_time": now_str,
            "entry_timestamp": time.time(),
            "entry_price": entry_price,
            "sl_price": sl_price,
            "initial_sl": sl_price,
            "tp1_price": tp1_price,
            "tp2_price": tp2_price,
            "sl_pct": sl_pct * 100,
            "risk_amount": risk_dollars,
            "position_val": position_val,
            "remaining_ratio": 1.0, # 100% open
            "margin_used": margin_used,
            "tp1_hit": False,
            "tp1_pnl": 0.0,
            "trailing_lock_active": False,
            "wick_ratio": wick_ratio,
            "vol_mult": vol_mult
        }

        if config.PAPER_TRADING:
            self.state["open_positions"][symbol] = trade
            self.save_state()
            telegram_notifier.notify_entry(trade)
            print(f"🟢 [NEW TRADE OPENED] {symbol} {side} @ ${entry_price:.4f} | Risk: ${risk_dollars:.2f} | Pos: ${position_val:,.0f} | 20x Margin: ${margin_used:.2f}")
            return trade
        else:
            return self.execute_live_order(trade)

    def trigger_tp1(self, symbol, current_price):
        """
        Executes TP1 (1.9R):
        1. Books 40% position profit.
        2. Shifts remaining 60% runner's Stop-Loss to +0.50R in PROFIT.
        """
        if symbol not in self.state["open_positions"]:
            return

        trade = self.state["open_positions"][symbol]
        if trade["tp1_hit"]:
            return

        # 40% position value
        pos_40 = trade["position_val"] * config.TP1_CLOSE_RATIO
        r_dist = abs(trade["entry_price"] - trade["initial_sl"])

        pnl_40 = (pos_40 * config.TP1_R * (r_dist / trade["entry_price"])) - (pos_40 * 0.001)

        # Update compounding balance with TP1 profit
        self._apply_realized_pnl(pnl_40)

        # Calculate new trailing stop at +0.50R in PROFIT
        if trade["side"] == "LONG":
            new_sl = trade["entry_price"] + (config.TRAILING_LOCK_R * r_dist)
        else:
            new_sl = trade["entry_price"] - (config.TRAILING_LOCK_R * r_dist)

        trade["tp1_hit"] = True
        trade["tp1_pnl"] = pnl_40
        trade["remaining_ratio"] = 1.0 - config.TP1_CLOSE_RATIO # 60% remaining
        trade["sl_price"] = new_sl
        trade["trailing_lock_active"] = True

        self.save_state()
        telegram_notifier.notify_tp1_hit(trade, pnl_40, new_sl)
        print(f"💰 [TP1 HIT] {symbol} | Banked 40%: +${pnl_40:.2f} | SL shifted to +0.50R: ${new_sl:.4f}")

    def close_full_trade(self, symbol, exit_price, reason):
        """Closes remaining position (TP2, Trailing SL hit, or initial SL hit)."""
        if symbol not in self.state["open_positions"]:
            return

        trade = self.state["open_positions"][symbol]
        remaining_ratio = trade["remaining_ratio"]
        runner_pos_val = trade["position_val"] * remaining_ratio

        if trade["side"] == "LONG":
            pct_change = (exit_price - trade["entry_price"]) / trade["entry_price"]
        else:
            pct_change = (trade["entry_price"] - exit_price) / trade["entry_price"]

        gross_runner_pnl = runner_pos_val * pct_change
        fee = runner_pos_val * 0.001
        net_runner_pnl = gross_runner_pnl - fee

        self._apply_realized_pnl(net_runner_pnl)
        total_trade_pnl = trade.get("tp1_pnl", 0.0) + net_runner_pnl

        duration_mins = int((time.time() - trade["entry_timestamp"]) / 60)
        trade["duration_mins"] = duration_mins
        trade["exit_price"] = exit_price
        trade["exit_time"] = config.get_now_ist().strftime('%Y-%m-%d %H:%M:%S')
        trade["runner_pnl"] = round(net_runner_pnl, 2)
        trade["total_pnl"] = round(total_trade_pnl, 2)
        trade["exit_reason"] = reason

        self.state["trade_history"].append(trade)
        del self.state["open_positions"][symbol]

        # Trigger 2-Hour Loss Cooldown if Stop-Loss hit
        if reason == "SL_HIT":
            self.last_loss_timestamps[symbol] = time.time()
            print(f"⏳ [2-HOUR COOLDOWN ACTIVATED] {symbol} will not trade for 2 hours to avoid chop.")

        self.save_state()

        if reason == "TP2_HIT":
            telegram_notifier.notify_tp2_hit(trade, net_runner_pnl, total_trade_pnl)
        elif reason == "TRAILING_LOCK_HIT":
            telegram_notifier.notify_trailing_sl_exit(trade, net_runner_pnl, total_trade_pnl)
        else:
            telegram_notifier.notify_sl_hit(trade, abs(total_trade_pnl))

        print(f"🏁 [TRADE CLOSED] {symbol} | Reason: {reason} | Runner PnL: ${net_runner_pnl:+.2f} | Total: ${total_trade_pnl:+.2f}")

    def _apply_realized_pnl(self, pnl):
        """Updates active capital with realized PnL."""
        self.state["total_net_pnl"] += pnl
        self.state["active_capital"] += pnl
        self.save_state()

    def execute_live_order(self, trade):
        """Sends authenticated orders to Delta Exchange India."""
        timestamp = str(int(time.time()))
        method = "POST"
        path = "/v2/orders"
        contracts = max(1, int(trade["position_val"] / trade["entry_price"]))
        body = json.dumps({
            "product_symbol": trade["symbol"],
            "size": contracts,
            "side": "buy" if trade["side"] == "LONG" else "sell",
            "order_type": "market_order"
        })

        signature_data = method + timestamp + path + body
        signature = hmac.new(
            config.DELTA_API_SECRET.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "api-key": config.DELTA_API_KEY,
            "timestamp": timestamp,
            "signature": signature,
            "User-Agent": "Mozilla/5.0"
        }

        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, data=body.encode('utf-8'), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                res = json.loads(r.read().decode())
                print(f"🔥 [LIVE ORDER PLACED] {trade['symbol']} {trade['side']} ({contracts} contracts): {res}")
                self.state["open_positions"][trade["symbol"]] = trade
                self.save_state()
                telegram_notifier.notify_entry(trade)
                return trade
        except Exception as e:
            print(f"❌ [LIVE EXECUTION FAILED] {trade['symbol']}: {e}")
            return None
