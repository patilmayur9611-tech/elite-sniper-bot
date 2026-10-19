"""
========================================================================================
ELITE PRICE ACTION & WICK PSYCHOLOGY STRATEGY ENGINE
Analyzes 5M Institutional Absorption, Imbalance Fills, and Manages Trailing Profit Locks
========================================================================================
"""
import numpy as np
import config

class StrategyEngine:
    def __init__(self, client):
        self.client = client

    def analyze_symbol(self, symbol, candles):
        """
        Scans 5M candles for Elite Wick Psychology signals.
        Returns trade parameters dict if a valid setup triggers, else None.
        """
        if len(candles) < 30:
            return None

        # Lookback arrays
        closes = np.array([c["close"] for c in candles])
        highs = np.array([c["high"] for c in candles])
        lows = np.array([c["low"] for c in candles])
        opens = np.array([c["open"] for c in candles])
        volumes = np.array([c["volume"] for c in candles])

        # 20-period volume moving average
        vol_ma = np.mean(volumes[-21:-1]) if len(volumes) > 21 else np.mean(volumes)

        # Trigger candle is the last closed candle (index -2) or current forming (index -1)
        # Using completed candle index -2 for zero repaint signal confirmation
        c_prev = candles[-2]
        c_open = c_prev["open"]
        c_high = c_prev["high"]
        c_low = c_prev["low"]
        c_close = c_prev["close"]
        c_vol = c_prev["volume"]

        c_range = c_high - c_low
        if c_range <= 0:
            return None

        vol_mult = (c_vol / vol_ma) if vol_ma > 0 else 1.0

        # Swing high & low over the preceding lookback period (excluding trigger candle)
        lookback = config.LOOKBACK_SWING_BARS
        pre_highs = highs[-lookback-2:-2]
        pre_lows = lows[-lookback-2:-2]
        if len(pre_highs) == 0 or len(pre_lows) == 0:
            return None

        swing_high = np.max(pre_highs)
        swing_low = np.min(pre_lows)

        # 1. BULLISH ABSORPTION SETUP (Institutional Long)
        # Lower wick absorption >= 48%, swept swing low, volume >= 1.30x
        lower_wick = min(c_open, c_close) - c_low
        lower_wick_ratio = lower_wick / c_range

        if (lower_wick_ratio >= config.WICK_RATIO_MIN and
            vol_mult >= config.VOLUME_MULT_MIN and
            c_low < swing_low and c_close > swing_low):
            
            entry_price = float(candles[-1]["close"]) # Current market price
            sl_buffer = c_low * config.DOUBLE_SWEEP_BUFFER_PCT
            sl_price = c_low - sl_buffer
            risk_dist = entry_price - sl_price
            
            if risk_dist > 0:
                tp1_price = entry_price + (config.TP1_R * risk_dist)
                tp2_price = entry_price + (config.TP2_R * risk_dist)
                return {
                    "symbol": symbol,
                    "side": "LONG",
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "tp1_price": tp1_price,
                    "tp2_price": tp2_price,
                    "wick_ratio": lower_wick_ratio,
                    "vol_mult": vol_mult
                }

        # 2. BEARISH ABSORPTION SETUP (Institutional Short)
        # Upper wick absorption >= 48%, swept swing high, volume >= 1.30x
        upper_wick = c_high - max(c_open, c_close)
        upper_wick_ratio = upper_wick / c_range

        if (upper_wick_ratio >= config.WICK_RATIO_MIN and
            vol_mult >= config.VOLUME_MULT_MIN and
            c_high > swing_high and c_close < swing_high):
            
            entry_price = float(candles[-1]["close"]) # Current market price
            sl_buffer = c_high * config.DOUBLE_SWEEP_BUFFER_PCT
            sl_price = c_high + sl_buffer
            risk_dist = sl_price - entry_price
            
            if risk_dist > 0:
                tp1_price = entry_price - (config.TP1_R * risk_dist)
                tp2_price = entry_price - (config.TP2_R * risk_dist)
                return {
                    "symbol": symbol,
                    "side": "SHORT",
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "tp1_price": tp1_price,
                    "tp2_price": tp2_price,
                    "wick_ratio": upper_wick_ratio,
                    "vol_mult": vol_mult
                }

        return None

    def manage_open_positions(self, symbol, current_price, candle_high, candle_low):
        """
        Manages ongoing positions:
        - Detects Target 1 (1.9R) -> Locks 40% profit & shifts SL to +0.50R
        - Detects Target 2 (4.0R) -> Closes remaining 60% runner
        - Detects Trailing Stop hit -> Exits guaranteed in green (+0.50R)
        - Detects Initial Stop Loss hit -> Strict capital defense (-1.0R)
        """
        if symbol not in self.client.state["open_positions"]:
            return

        trade = self.client.state["open_positions"][symbol]
        side = trade["side"]
        sl = trade["sl_price"]
        tp1 = trade["tp1_price"]
        tp2 = trade["tp2_price"]
        tp1_hit = trade["tp1_hit"]

        if side == "LONG":
            # Check TP1 hit
            if not tp1_hit and (candle_high >= tp1 or current_price >= tp1):
                self.client.trigger_tp1(symbol, tp1)
                return

            # Check TP2 hit (after TP1 is achieved)
            if tp1_hit and (candle_high >= tp2 or current_price >= tp2):
                self.client.close_full_trade(symbol, tp2, "TP2_HIT")
                return

            # Check Trailing SL (+0.50R) exit
            if tp1_hit and (candle_low <= sl or current_price <= sl):
                self.client.close_full_trade(symbol, sl, "TRAILING_LOCK_HIT")
                return

            # Check initial SL exit (before TP1)
            if not tp1_hit and (candle_low <= sl or current_price <= sl):
                self.client.close_full_trade(symbol, sl, "SL_HIT")
                return

        elif side == "SHORT":
            # Check TP1 hit
            if not tp1_hit and (candle_low <= tp1 or current_price <= tp1):
                self.client.trigger_tp1(symbol, tp1)
                return

            # Check TP2 hit (after TP1 is achieved)
            if tp1_hit and (candle_low <= tp2 or current_price <= tp2):
                self.client.close_full_trade(symbol, tp2, "TP2_HIT")
                return

            # Check Trailing SL (+0.50R) exit
            if tp1_hit and (candle_high >= sl or current_price >= sl):
                self.client.close_full_trade(symbol, sl, "TRAILING_LOCK_HIT")
                return

            # Check initial SL exit (before TP1)
            if not tp1_hit and (candle_high >= sl or current_price >= sl):
                self.client.close_full_trade(symbol, sl, "SL_HIT")
                return
