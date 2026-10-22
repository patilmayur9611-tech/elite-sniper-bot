"""
========================================================================================
ELITE PRICE ACTION & WICK PSYCHOLOGY STRATEGY ENGINE (OPTION 2 MASTER ENGINE)
Features:
- 1H 20-EMA Macro Trend Filter (100% Counter-Trend Trade Elimination)
- 3M Candlestick Liquidity Sweep & Wick Absorption
- Fair Value Gap (FVG) Pullback Limit Entry Retest (Waits up to 4 bars)
- +1.0R Breakeven Shield (Shifts SL to Entry + 0.10R to eliminate risk)
- 2-Hour Loss Cooldown per Coin
- Weak Hours Session Filter (Skip 1-2 AM & 9-10 AM IST strictly locked to UTC+5:30)
- Trailing Profit Lock at +0.50R Guaranteed Green after TP1
========================================================================================
"""
import numpy as np
import datetime
import time
import config

class StrategyEngine:
    def __init__(self, client):
        self.client = client
        self.pending_fvg = {}  # symbol -> dict of pending FVG limit setups

    def is_weak_hour(self):
        """Checks if current time falls in low-volume chop hours strictly in IST (+5:30)."""
        now_ist = config.get_now_ist()
        return now_ist.hour in config.WEAK_HOURS_IST

    def get_1h_trend_bias(self, symbol):
        """
        Determines 1H Macro Trend Bias from Delta Exchange using 1H 20-EMA:
        - BULLISH: 1H candle close > 1H 20-EMA and close >= prev open (Shorts 100% BLOCKED)
        - BEARISH: 1H candle close < 1H 20-EMA and close <= prev open (Longs 100% BLOCKED)
        - NEUTRAL: Chop / conflict (ALL trades BLOCKED)
        """
        candles_1h = self.client.fetch_candles(symbol, resolution=config.TREND_RESOLUTION, limit=30)
        if len(candles_1h) < 20:
            return "NEUTRAL"

        closes = np.array([c["close"] for c in candles_1h])
        # Calculate true 1H 20-EMA
        alpha = 2.0 / (20.0 + 1.0)
        ema = closes[0]
        for p in closes[1:]:
            ema = alpha * p + (1.0 - alpha) * ema

        c_curr = candles_1h[-1]
        c_prev = candles_1h[-2]

        curr_close = c_curr["close"]
        prev_open = c_prev["open"]

        if curr_close > ema and curr_close >= prev_open:
            return "BULLISH"
        elif curr_close < ema and curr_close <= prev_open:
            return "BEARISH"
        return "NEUTRAL"

    def analyze_symbol(self, symbol, candles):
        """
        Scans 3M candles for Option 2 Elite Sniper Setups:
        1. Checks 2-Hour Loss Cooldown
        2. Checks Weak Hours Filter (Strict IST)
        3. Monitors & fills pending FVG pullback limit orders
        4. Detects new 1H-aligned wick sweeps and creates pending FVG limit zones
        """
        if len(candles) < 25:
            return None

        # 1. 2-Hour Loss Cooldown Defense
        if self.client.is_in_loss_cooldown(symbol):
            return None

        # 2. Weak Hours Filter Defense (Explicit IST)
        if self.is_weak_hour():
            return None

        curr_candle = candles[-1]

        # 3. Check Pending FVG Pullback Limit Entry
        if symbol in self.pending_fvg:
            pending = self.pending_fvg[symbol]
            pending["bars_waited"] += 1

            if pending["bars_waited"] > config.FVG_MAX_WAIT_BARS:
                print(f"⏱️ [FVG EXPIRED] {symbol} {pending['side']} pullback did not fill within {config.FVG_MAX_WAIT_BARS} candles. Setup cancelled.")
                del self.pending_fvg[symbol]
            else:
                side = pending["side"]
                entered = False
                entry_price = 0.0

                if side == "LONG":
                    # Price dips into the FVG imbalance zone
                    if curr_candle["low"] <= pending["fvg_high"] and curr_candle["high"] >= pending["fvg_low"]:
                        entered = True
                        entry_price = min(curr_candle["open"], pending["fvg_high"])
                elif side == "SHORT":
                    # Price rallies into the FVG imbalance zone
                    if curr_candle["high"] >= pending["fvg_low"] and curr_candle["low"] <= pending["fvg_high"]:
                        entered = True
                        entry_price = max(curr_candle["open"], pending["fvg_low"])

                if entered:
                    sl_price = pending["sl"]
                    risk_dist = abs(entry_price - sl_price)
                    sl_pct = risk_dist / entry_price

                    del self.pending_fvg[symbol]

                    # Validate SL percentage range (0.18% to 0.50%)
                    if config.MIN_SL_PCT <= sl_pct <= config.MAX_SL_PCT:
                        if side == "LONG":
                            rescue_tp = entry_price + (config.RESCUE_PROFIT_R * risk_dist)
                            tp1_price = entry_price + (config.TP1_R * risk_dist)
                            tp2_price = entry_price + (config.TP2_R * risk_dist)
                        else:
                            rescue_tp = entry_price - (config.RESCUE_PROFIT_R * risk_dist)
                            tp1_price = entry_price - (config.TP1_R * risk_dist)
                            tp2_price = entry_price - (config.TP2_R * risk_dist)

                        print(f"🎯 [FVG PULLBACK FILLED] {symbol} {side} limit filled @ ${entry_price:.4f}! SL: ${sl_price:.4f} ({sl_pct*100:.2f}%)")
                        return {
                            "symbol": symbol,
                            "side": side,
                            "entry_price": entry_price,
                            "sl_price": sl_price,
                            "rescue_tp": rescue_tp,
                            "tp1_price": tp1_price,
                            "tp2_price": tp2_price,
                            "wick_ratio": pending.get("wick_ratio", 0.50),
                            "vol_mult": pending.get("vol_mult", 1.50)
                        }

        # 4. Check for NEW Wick Absorption Setup on 3M Candles
        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])

        lookback = config.LOOKBACK_SWING_BARS
        pre_highs = highs[-lookback-2:-2]
        pre_lows = lows[-lookback-2:-2]
        pre_vols = volumes[-lookback-2:-2]

        if len(pre_highs) < lookback or len(pre_lows) < lookback:
            return None

        swing_high = np.max(pre_highs)
        swing_low = np.min(pre_lows)
        vol_avg = np.mean(pre_vols) if len(pre_vols) > 0 else 1.0

        c_prev = candles[-2] # Last closed 3m candle
        c_open = c_prev["open"]
        c_high = c_prev["high"]
        c_low = c_prev["low"]
        c_close = c_prev["close"]
        c_vol = c_prev["volume"]

        c_range = c_high - c_low
        if c_range <= 0:
            return None

        vol_mult = (c_vol / vol_avg) if vol_avg > 0 else 1.0
        if vol_mult < config.VOLUME_MULT_MIN:
            return None

        # Check 1H 20-EMA Macro Trend Bias (Strict: NEUTRAL is rejected!)
        bias = self.get_1h_trend_bias(symbol)

        # 1. BULLISH ABSORPTION (Long Setup - Only allowed if 1H Trend is firmly BULLISH)
        if bias == "BULLISH":
            lower_wick = min(c_open, c_close) - c_low
            lower_wick_ratio = lower_wick / c_range

            if (lower_wick_ratio >= config.WICK_RATIO_MIN and
                c_low < swing_low and c_close > swing_low and
                c_close > c_open):
                
                fvg_high = c_close
                fvg_low = max(c_open, swing_low)
                sl_price = c_low * (1.0 - config.DOUBLE_SWEEP_BUFFER_PCT)

                self.pending_fvg[symbol] = {
                    "side": "LONG",
                    "fvg_high": fvg_high,
                    "fvg_low": fvg_low,
                    "sl": sl_price,
                    "bars_waited": 0,
                    "wick_ratio": lower_wick_ratio,
                    "vol_mult": vol_mult
                }
                print(f"👀 [FVG LONG ZONE DETECTED] {symbol} | Trend: 1H BULLISH (>20-EMA) | Waiting pullback into ${fvg_low:.4f} - ${fvg_high:.4f} | SL: ${sl_price:.4f}")

        # 2. BEARISH ABSORPTION (Short Setup - Only allowed if 1H Trend is firmly BEARISH)
        elif bias == "BEARISH":
            upper_wick = c_high - max(c_open, c_close)
            upper_wick_ratio = upper_wick / c_range

            if (upper_wick_ratio >= config.WICK_RATIO_MIN and
                c_high > swing_high and c_close < swing_high and
                c_close < c_open):
                
                fvg_high = min(c_open, swing_high)
                fvg_low = c_close
                sl_price = c_high * (1.0 + config.DOUBLE_SWEEP_BUFFER_PCT)

                self.pending_fvg[symbol] = {
                    "side": "SHORT",
                    "fvg_high": fvg_high,
                    "fvg_low": fvg_low,
                    "sl": sl_price,
                    "bars_waited": 0,
                    "wick_ratio": upper_wick_ratio,
                    "vol_mult": vol_mult
                }
                print(f"👀 [FVG SHORT ZONE DETECTED] {symbol} | Trend: 1H BEARISH (<20-EMA) | Waiting pullback into ${fvg_low:.4f} - ${fvg_high:.4f} | SL: ${sl_price:.4f}")

        return None

    def manage_open_positions(self, symbol, current_price, candle_high, candle_low):
        """
        Manages ongoing positions:
        - Detects Breakeven Shield (+1.0R) -> Shifts SL to Entry + 0.10R (100% Risk-Free!)
        - Detects Target 1 (1.9R) -> Locks 40% profit & shifts SL to +0.50R
        - Detects Target 2 (4.0R) -> Closes remaining 60% runner
        - Detects Trailing Stop hit -> Exits guaranteed in green (+0.50R)
        - Detects Breakeven Exit -> Exits guaranteed in green (+0.10R, no cooldown)
        - Detects Initial Stop Loss hit -> Strict capital defense (-1.0R) & activates 2H Cooldown
        """
        if symbol not in self.client.state["open_positions"]:
            return

        trade = self.client.state["open_positions"][symbol]
        side = trade["side"]
        sl = trade["sl_price"]
        tp1 = trade["tp1_price"]
        tp2 = trade["tp2_price"]
        tp1_hit = trade["tp1_hit"]
        entry = trade["entry_price"]
        r_dist = abs(entry - trade["initial_sl"])

        if side == "LONG":
            # 1. Check Breakeven Shield at +1.0R (before TP1)
            if getattr(config, "USE_BREAKEVEN_SHIELD", True) and not tp1_hit and not trade.get("be_activated", False):
                be_trigger_p = entry + (config.BREAKEVEN_TRIGGER_R * r_dist)
                if candle_high >= be_trigger_p or current_price >= be_trigger_p:
                    new_sl = entry + (config.BREAKEVEN_LOCK_R * r_dist)
                    self.client.trigger_breakeven(symbol, new_sl)
                    sl = new_sl

            # 2. Check TP1 hit (1.9R)
            if not tp1_hit and (candle_high >= tp1 or current_price >= tp1):
                self.client.trigger_tp1(symbol, tp1)
                return

            # 3. Check TP2 hit (4.0R home run runner)
            if tp1_hit and (candle_high >= tp2 or current_price >= tp2):
                self.client.close_full_trade(symbol, tp2, "TP2_HIT")
                return

            # 4. Check Trailing SL (+0.50R) exit after TP1
            if tp1_hit and (candle_low <= sl or current_price <= sl):
                self.client.close_full_trade(symbol, sl, "TRAILING_LOCK_HIT")
                return

            # 5. Check Breakeven SL (+0.10R) exit (Zero risk, no loss cooldown)
            if not tp1_hit and trade.get("be_activated", False) and (candle_low <= sl or current_price <= sl):
                self.client.close_full_trade(symbol, sl, "BREAKEVEN_EXIT")
                return

            # 6. Check Initial SL exit (-1.0R loss, triggers 2H cooldown)
            if not tp1_hit and not trade.get("be_activated", False) and (candle_low <= sl or current_price <= sl):
                self.client.close_full_trade(symbol, sl, "SL_HIT")
                return

        elif side == "SHORT":
            # 1. Check Breakeven Shield at +1.0R (before TP1)
            if getattr(config, "USE_BREAKEVEN_SHIELD", True) and not tp1_hit and not trade.get("be_activated", False):
                be_trigger_p = entry - (config.BREAKEVEN_TRIGGER_R * r_dist)
                if candle_low <= be_trigger_p or current_price <= be_trigger_p:
                    new_sl = entry - (config.BREAKEVEN_LOCK_R * r_dist)
                    self.client.trigger_breakeven(symbol, new_sl)
                    sl = new_sl

            # 2. Check TP1 hit (1.9R)
            if not tp1_hit and (candle_low <= tp1 or current_price <= tp1):
                self.client.trigger_tp1(symbol, tp1)
                return

            # 3. Check TP2 hit (4.0R home run runner)
            if tp1_hit and (candle_low <= tp2 or current_price <= tp2):
                self.client.close_full_trade(symbol, tp2, "TP2_HIT")
                return

            # 4. Check Trailing SL (+0.50R) exit after TP1
            if tp1_hit and (candle_high >= sl or current_price >= sl):
                self.client.close_full_trade(symbol, sl, "TRAILING_LOCK_HIT")
                return

            # 5. Check Breakeven SL (+0.10R) exit (Zero risk, no loss cooldown)
            if not tp1_hit and trade.get("be_activated", False) and (candle_high >= sl or current_price >= sl):
                self.client.close_full_trade(symbol, sl, "BREAKEVEN_EXIT")
                return

            # 6. Check Initial SL exit (-1.0R loss, triggers 2H cooldown)
            if not tp1_hit and not trade.get("be_activated", False) and (candle_high >= sl or current_price >= sl):
                self.client.close_full_trade(symbol, sl, "SL_HIT")
                return
