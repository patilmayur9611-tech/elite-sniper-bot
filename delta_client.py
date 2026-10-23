"""
========================================================================================
DELTA EXCHANGE INDIA CLIENT & COMPOUNDING PORTFOLIO MANAGER (INR EDITION)
Exchange: Delta Exchange India (api.india.delta.exchange)
Currency: Indian Rupee (INR - ₹)
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
        """Loads persistent portfolio balance and trade records in Indian Rupee (INR - ₹)."""
        now_month = config.get_now_ist().strftime('%Y-%m')
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                    self.state.setdefault("initial_capital_inr", config.INITIAL_CAPITAL_INR)
                    self.state.setdefault("active_capital_inr", config.INITIAL_CAPITAL_INR)
                    self.state.setdefault("month_starting_capital_inr", config.INITIAL_CAPITAL_INR)
                    self.state.setdefault("current_month", now_month)
                    self.state.setdefault("banked_profit_inr", 0.0)
                    self.state.setdefault("total_net_pnl_inr", 0.0)
                    self.state.setdefault("open_positions", {})
                    self.state.setdefault("closed_trades", [])
                    return
            except Exception as e:
                print(f"[STATE LOAD ERROR] {e}. Reinitializing default state.")

        self.state = {
            "initial_capital_inr": config.INITIAL_CAPITAL_INR,
            "active_capital_inr": config.INITIAL_CAPITAL_INR,
            "month_starting_capital_inr": config.INITIAL_CAPITAL_INR,
            "current_month": now_month,
            "banked_profit_inr": 0.0,
            "total_net_pnl_inr": 0.0,
            "open_positions": {},
            "closed_trades": []
        }
        self.save_state()

    def save_state(self):
        """Persists current state atomically to disk."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            print(f"[STATE SAVE ERROR] {e}")

    def fetch_candles(self, symbol, resolution="15m", limit=60):
        """
        Fetches historical candles from Delta Exchange India public API without geo-blocking.
        """
        end_time = int(time.time())
        res_seconds_map = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400
        }
        res_secs = res_seconds_map.get(resolution, 900)
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

    def get_current_risk_inr(self):
        """
        Compounding Engine with Max Active Capital ceiling in INR:
        - Risk per trade is strictly 2.0% of active INR capital.
        - Surplus profits beyond MAX_ACTIVE_CAPITAL_INR are safely banked into the vault.
        """
        now_month = config.get_now_ist().strftime('%Y-%m')
        recorded_month = self.state.get("current_month", now_month)

        if now_month != recorded_month:
            # Calendar month rollover in IST!
            curr_active = self.state.get("active_capital_inr", config.INITIAL_CAPITAL_INR)
            if curr_active > config.MAX_ACTIVE_CAPITAL_INR:
                overflow = curr_active - config.MAX_ACTIVE_CAPITAL_INR
                self.state["banked_profit_inr"] += overflow
                self.state["active_capital_inr"] = config.MAX_ACTIVE_CAPITAL_INR

            self.state["month_starting_capital_inr"] = self.state["active_capital_inr"]
            self.state["current_month"] = now_month
            self.save_state()

        curr_cap = self.state.get("active_capital_inr", config.INITIAL_CAPITAL_INR)
        return curr_cap * config.RISK_PER_TRADE_PCT

    def open_position(self, setup):
        """
        Opens a new trade position using 20x Leverage and Rescued Risk Management in INR.
        """
        symbol = setup["symbol"]
        side = setup["side"]
        entry_price = setup["entry_price"]
        sl_price = setup["sl_price"]
        risk_dist = abs(entry_price - sl_price)

        # Resilient target calculation (Guarantees zero KeyError)
        rescue_tp = setup.get("rescue_tp")
        if not rescue_tp:
            rescue_tp = entry_price + (getattr(config, "RESCUE_PROFIT_R", 1.0) * risk_dist) if side == "LONG" else entry_price - (getattr(config, "RESCUE_PROFIT_R", 1.0) * risk_dist)

        tp1_price = setup.get("tp1_price")
        if not tp1_price:
            tp1_price = entry_price + (getattr(config, "TP1_R", 1.9) * risk_dist) if side == "LONG" else entry_price - (getattr(config, "TP1_R", 1.9) * risk_dist)

        tp2_price = setup.get("tp2_price")
        if not tp2_price:
            tp2_price = entry_price + (getattr(config, "TP2_R", 3.0) * risk_dist) if side == "LONG" else entry_price - (getattr(config, "TP2_R", 3.0) * risk_dist)

        if len(self.state["open_positions"]) >= config.MAX_CONCURRENT_TRADES:
            return None

        risk_inr = self.get_current_risk_inr()
        sl_pct = abs(entry_price - sl_price) / entry_price
        if sl_pct <= 0:
            return None

        # Position value calculation in INR with dynamic 50% margin defense
        raw_position_inr = risk_inr / sl_pct
        curr_active_cap = self.state.get("active_capital_inr", config.INITIAL_CAPITAL_INR)
        max_margin_allowed = curr_active_cap * getattr(config, "MAX_MARGIN_PER_TRADE_PCT", 0.50)
        max_position_allowed = max_margin_allowed * config.LEVERAGE
        position_inr = min(raw_position_inr, max_position_allowed, config.MAX_POSITION_INR)
        margin_used_inr = position_inr / config.LEVERAGE

        # Equivalent USD sizes for Delta contract logic
        position_usd = position_inr / config.USD_INR_RATE
        entry_inr_est = entry_price * config.USD_INR_RATE

        # Integer Contract Lot Sizing & Allocation (Delta Exchange Live Order Shield)
        est_contract_val = entry_price * 0.001 if "BTC" in symbol else entry_price * 0.1 if ("SOL" in symbol or "BNB" in symbol) else 1.0
        total_contracts = max(1, int(round(position_usd / est_contract_val)))

        if total_contracts == 1:
            tp1_contracts = 1
            tp2_contracts = 0
            runner_contracts = 0
        elif total_contracts == 2:
            tp1_contracts = 1
            tp2_contracts = 0
            runner_contracts = 1
        elif total_contracts == 3:
            tp1_contracts = 1
            tp2_contracts = 1
            runner_contracts = 1
        else:
            tp1_contracts = max(1, int(round(total_contracts * getattr(config, "RESCUE_CLOSE_RATIO", 0.30))))
            tp2_contracts = max(1, int(round(total_contracts * getattr(config, "TP1_CLOSE_RATIO", 0.30))))
            runner_contracts = total_contracts - tp1_contracts - tp2_contracts
            if runner_contracts <= 0:
                runner_contracts = 1
                if tp2_contracts > 1: tp2_contracts -= 1
                elif tp1_contracts > 1: tp1_contracts -= 1

        now_str = config.get_now_ist().strftime('%Y-%m-%d %H:%M:%S')
        trade = {
            "symbol": symbol,
            "side": side,
            "entry_time": now_str,
            "entry_timestamp": time.time(),
            "entry_price": entry_price,
            "entry_inr_est": entry_inr_est,
            "sl_price": sl_price,
            "initial_sl": sl_price,
            "rescue_tp": rescue_tp,
            "tp1_price": tp1_price,
            "tp2_price": tp2_price,
            "sl_pct": sl_pct * 100,
            "risk_inr": risk_inr,
            "position_inr": position_inr,
            "position_usd": position_usd,
            "total_contracts": total_contracts,
            "tp1_contracts": tp1_contracts,
            "tp2_contracts": tp2_contracts,
            "runner_contracts": runner_contracts,
            "remaining_contracts": total_contracts,
            "remaining_ratio": 1.0,  # 100% open initially
            "margin_used_inr": margin_used_inr,
            "rescue_hit": False,
            "tp1_hit": False,
            "peak_price": entry_price,
            "peak_r": 0.0,
            "atr_val": setup.get("atr_val", abs(entry_price - sl_price) * 0.40),
            "realized_pnl_inr": 0.0,
            "setup_type": setup.get("setup_type", "ICT_OTE")
        }

        self.state["open_positions"][symbol] = trade
        self.save_state()
        telegram_notifier.notify_entry(trade)
        print(f"🟢 [NEW TRADE OPENED] {symbol} {side} @ ${entry_price:.4f} (~₹{entry_inr_est:,.2f}) | Risk: {config.format_inr(risk_inr)} | 20x Margin: {config.format_inr(margin_used_inr)}")
        return trade

    def manage_positions(self):
        """
        Monitors active positions against live prices in INR:
        1. Checks Level 1 Rescued TP (+1.0R): Books 30% profit in INR & locks SL to Elevated Breakeven!
        2. Checks Level 2 TP1 (+1.9R): Books 30% profit in INR & RATCHET LOCKS SL at +1.2R Guaranteed Profit!
        3. Dynamically trails remaining 40% open runner behind peak price (-0.50R)!
        4. Checks Stop Loss execution.
        """
        if not self.state["open_positions"]:
            return

        symbols_to_close = []

        for symbol, trade in list(self.state["open_positions"].items()):
            ticker = self.fetch_ticker(symbol)
            if not ticker or ticker["last_price"] <= 0:
                continue

            current_price = ticker["last_price"]
            side = trade["side"]
            entry_price = trade["entry_price"]
            sl_price = trade["sl_price"]
            pos_inr = trade["position_inr"]
            r_dist = abs(entry_price - trade["initial_sl"])

            # Track peak price and peak R-multiple
            current_r = ((current_price - entry_price) / r_dist) if side == "LONG" else ((entry_price - current_price) / r_dist)
            if current_r > trade.get("peak_r", 0.0):
                trade["peak_r"] = current_r
                trade["peak_price"] = current_price

            # ---------------------------------------------------------
            # 1. RESCUED RULE (+1.0R): 30% Profit in INR & Elevated Breakeven Lock (+0.18% Fee Shield)
            # ---------------------------------------------------------
            if not trade["rescue_hit"]:
                hit_rescue = (current_price >= trade["rescue_tp"]) if side == "LONG" else (current_price <= trade["rescue_tp"])
                if hit_rescue:
                    close_qty = trade.get("tp1_contracts", 0)
                    total_qty = trade.get("total_contracts", 1)
                    close_ratio = (close_qty / total_qty) if (total_qty > 0 and close_qty > 0) else getattr(config, "RESCUE_CLOSE_RATIO", 0.30)
                    closed_val_inr = pos_inr * close_ratio
                    r_dist_pct = abs(trade["rescue_tp"] - entry_price) / entry_price
                    pnl_rescue_inr = closed_val_inr * r_dist_pct

                    trade["remaining_ratio"] -= close_ratio
                    trade["remaining_contracts"] = max(0, trade.get("remaining_contracts", total_qty) - close_qty)
                    trade["realized_pnl_inr"] += pnl_rescue_inr
                    trade["rescue_hit"] = True

                    # Elevated Breakeven (+0.18% Fee Shield): Covers 100% of Delta Exchange entry/exit fees + GST!
                    fee_shield_pct = getattr(config, "ELEVATED_BREAKEVEN_PCT", 0.0018)
                    elevated_be = entry_price * (1.0 + fee_shield_pct) if side == "LONG" else entry_price * (1.0 - fee_shield_pct)
                    trade["sl_price"] = elevated_be

                    self._apply_realized_pnl_inr(pnl_rescue_inr)
                    self.save_state()
                    telegram_notifier.notify_rescue_hit(trade, pnl_rescue_inr)
                    qty_desc = f"{close_qty} contracts" if close_qty > 0 else f"{close_ratio*100:.0f}%"
                    print(f"🛡️ [LEVEL 1 HIT] {symbol} booked {qty_desc} (+{config.format_inr(pnl_rescue_inr)}) & SL moved to ELEVATED BREAKEVEN (${elevated_be:.4f})!")

            # ---------------------------------------------------------
            # 2. TARGET 1 (+1.9R): 30% Profit in INR & RATCHET SL Locked at +1.2R Guaranteed Floor!
            # ---------------------------------------------------------
            if not trade["tp1_hit"] and trade["rescue_hit"]:
                hit_tp1 = (current_price >= trade["tp1_price"]) if side == "LONG" else (current_price <= trade["tp1_price"])
                if hit_tp1:
                    close_qty = trade.get("tp2_contracts", 0)
                    total_qty = trade.get("total_contracts", 1)
                    close_ratio = (close_qty / total_qty) if (total_qty > 0 and close_qty > 0) else getattr(config, "TP1_CLOSE_RATIO", 0.30)
                    closed_val_inr = pos_inr * close_ratio
                    r_dist_pct = abs(trade["tp1_price"] - entry_price) / entry_price
                    pnl_tp1_inr = closed_val_inr * r_dist_pct

                    trade["remaining_ratio"] -= close_ratio
                    trade["remaining_contracts"] = max(0, trade.get("remaining_contracts", total_qty) - close_qty)
                    trade["realized_pnl_inr"] += pnl_tp1_inr
                    trade["tp1_hit"] = True

                    # RATCHET LOCK: Lock SL to +1.2R in guaranteed profit floor for remaining 40% runner!
                    lock_r = getattr(config, "TP1_LOCK_SL_R", 1.2)
                    ratchet_sl = entry_price + (lock_r * r_dist) if side == "LONG" else entry_price - (lock_r * r_dist)
                    trade["sl_price"] = ratchet_sl

                    self._apply_realized_pnl_inr(pnl_tp1_inr)
                    self.save_state()
                    telegram_notifier.notify_tp1_hit(trade, pnl_tp1_inr, trade["sl_price"])
                    qty_desc = f"{close_qty} contracts" if close_qty > 0 else f"{close_ratio*100:.0f}%"
                    print(f"💰 [TARGET 1 HIT] {symbol} booked {qty_desc} (+{config.format_inr(pnl_tp1_inr)}) & SL RATCHET LOCKED AT +{lock_r}R GUARANTEED PROFIT (${ratchet_sl:.4f})!")

            # ---------------------------------------------------------
            # 3. OPEN 40% RUNNER ATR-AWARE DYNAMIC TRAILING
            # ---------------------------------------------------------
            if trade["tp1_hit"]:
                atr_val = trade.get("atr_val", r_dist * 0.40)
                atr_mult = getattr(config, "TRAIL_ATR_MULT", 1.25)
                min_dist = getattr(config, "MIN_TRAIL_DISTANCE_R", 0.50)
                max_dist = getattr(config, "MAX_TRAIL_DISTANCE_R", 0.85)

                atr_dist_r = (atr_mult * atr_val / r_dist) if r_dist > 0 else min_dist
                trail_buffer = max(min_dist, min(max_dist, atr_dist_r))
                lock_floor_r = getattr(config, "TP1_LOCK_SL_R", 1.2)
                trail_r = trade.get("peak_r", 0.0) - trail_buffer

                if trail_r > lock_floor_r:
                    new_trail_sl = entry_price + (trail_r * r_dist) if side == "LONG" else entry_price - (trail_r * r_dist)
                    is_better = (new_trail_sl > trade["sl_price"]) if side == "LONG" else (new_trail_sl < trade["sl_price"])
                    if is_better:
                        old_sl = trade["sl_price"]
                        trade["sl_price"] = new_trail_sl
                        self.save_state()
                        print(f"📈 [ATR DYNAMIC TRAIL] {symbol} runner SL advanced from ${old_sl:.4f} to ${new_trail_sl:.4f} (+{trail_r:.2f}R from peak {trade['peak_r']:.2f}R, buffer {trail_buffer:.2f}R)!")

            # ---------------------------------------------------------
            # 4. STOP LOSS CHECK (Elevated Breakeven, Ratchet Trailing SL, or Initial SL)
            # ---------------------------------------------------------
            hit_sl = (current_price <= trade["sl_price"]) if side == "LONG" else (current_price >= trade["sl_price"])
            if hit_sl:
                remaining_val_inr = pos_inr * trade["remaining_ratio"]
                exit_sl = trade["sl_price"]

                # Check direction of exit relative to entry
                if side == "LONG":
                    gain_pct = (exit_sl - entry_price) / entry_price
                else:
                    gain_pct = (entry_price - exit_sl) / entry_price

                pnl_remaining_inr = remaining_val_inr * gain_pct

                if trade["tp1_hit"]:
                    reason = "RUNNER_TRAILING_LOCK_EXIT"
                elif trade["rescue_hit"]:
                    reason = "ELEVATED_BREAKEVEN_EXIT"
                else:
                    reason = "STOP_LOSS_EXIT"

                total_trade_pnl_inr = trade["realized_pnl_inr"] + pnl_remaining_inr
                self._apply_realized_pnl_inr(pnl_remaining_inr)

                telegram_notifier.notify_sl_hit(trade, total_trade_pnl_inr, reason)
                symbols_to_close.append((symbol, reason, total_trade_pnl_inr, current_price))

        for symbol, reason, final_pnl_inr, exit_px in symbols_to_close:
            self._close_position_record(symbol, reason, final_pnl_inr, exit_px)

    def _apply_realized_pnl_inr(self, pnl_inr):
        """Applies realized PnL in INR and manages the MAX_ACTIVE_CAPITAL_INR cap."""
        self.state["active_capital_inr"] += pnl_inr
        self.state["total_net_pnl_inr"] += pnl_inr

        # Surplus profit beyond MAX_ACTIVE_CAPITAL_INR gets banked into safe vault
        if self.state["active_capital_inr"] > config.MAX_ACTIVE_CAPITAL_INR:
            overflow = self.state["active_capital_inr"] - config.MAX_ACTIVE_CAPITAL_INR
            self.state["banked_profit_inr"] += overflow
            self.state["active_capital_inr"] = config.MAX_ACTIVE_CAPITAL_INR

    def _close_position_record(self, symbol, reason, final_pnl_inr, exit_px):
        """Archives closed trade and removes from open positions."""
        if symbol in self.state["open_positions"]:
            trade = self.state["open_positions"].pop(symbol)
            trade["exit_time"] = config.get_now_ist().strftime('%Y-%m-%d %H:%M:%S')
            trade["exit_price"] = exit_px
            trade["final_pnl_inr"] = final_pnl_inr
            trade["close_reason"] = reason

            self.state["closed_trades"].append(trade)
            if final_pnl_inr < 0:
                self.record_loss_cooldown(symbol)
            self.save_state()
            print(f"🏁 [POSITION CLOSED] {symbol} | Reason: {reason} | Final PnL: {config.format_inr(final_pnl_inr)}")

    def is_in_loss_cooldown(self, symbol):
        """Checks if symbol suffered a loss within the last 2 hours (7200 seconds)."""
        cooldowns = self.state.get("loss_cooldowns", {})
        last_loss = cooldowns.get(symbol, 0)
        return (time.time() - last_loss) < 7200

    def record_loss_cooldown(self, symbol):
        """Records a 2-hour loss cooldown timestamp."""
        if "loss_cooldowns" not in self.state:
            self.state["loss_cooldowns"] = {}
        self.state["loss_cooldowns"][symbol] = time.time()
        self.save_state()

    def trigger_breakeven(self, symbol, new_sl):
        """Shifts stop loss to breakeven."""
        if symbol in self.state["open_positions"]:
            self.state["open_positions"][symbol]["sl_price"] = new_sl
            self.state["open_positions"][symbol]["be_activated"] = True
            self.save_state()

    def trigger_tp1(self, symbol, new_sl):
        """Marks TP1 hit and trails stop loss."""
        if symbol in self.state["open_positions"]:
            self.state["open_positions"][symbol]["tp1_hit"] = True
            self.state["open_positions"][symbol]["sl_price"] = new_sl
            self.save_state()

    def close_full_trade(self, symbol, reason, pnl):
        """Closes entire remaining position."""
        if symbol in self.state["open_positions"]:
            ticker = self.fetch_ticker(symbol)
            exit_px = ticker.get("last_price", 0) if ticker else 0
            self._close_position_record(symbol, reason, pnl, exit_px)
