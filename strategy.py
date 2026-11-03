import pandas as pd
import numpy as np
import config
import ai_advisor

class MomentumStrategy:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 1. 20-period Volume SMA & Relative Volume (RVol)
        df['vol_sma20'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / (df['vol_sma20'] + 1e-8)
        
        # 2. EMAs for Trend Alignment & Golden Shift (10, 20, 50)
        df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # 3. RSI 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-8)
        df['rsi14'] = 100 - (100 / (1 + rs))

        # 4. ATR 14 for Volatility Measurement
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low'] - df['close'].shift(1)).abs()
        df['atr14'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
        
        # 5. 1-Hour Swings (12 candles lookback on 5m)
        df['hh12'] = df['high'].shift(1).rolling(12).max()
        df['ll12'] = df['low'].shift(1).rolling(12).min()
        
        # 6. 20-candle Swings
        df['hh20'] = df['high'].shift(1).rolling(20).max()
        df['ll20'] = df['low'].shift(1).rolling(20).min()

        # 7. Candle Anatomy (Wick and Body Ratios)
        candle_range = df['high'] - df['low'] + 1e-8
        df['upper_wick'] = (df['high'] - df[['open', 'close']].max(axis=1)) / candle_range
        df['lower_wick'] = (df[['open', 'close']].min(axis=1) - df['low']) / candle_range
        df['body_ratio'] = (df['close'] - df['open']).abs() / candle_range
        
        return df

    @staticmethod
    def check_signal(df: pd.DataFrame, ticker: dict = None, insider_conf: dict = None, symbol: str = ""):
        """
        WHALE GOLDEN POCKET OTE (OPTIMAL TRADE ENTRY) QUANT ENGINE:
        1. AI Coin Reputation Check: Rejects choppy coins suspended by AI Advisor.
        2. Anti-Climax Guard: Strictly bans buying Long if price > 4% above 1h low!
        3. Bottom Sweep & EMA 10/20 Golden Cross Shift.
        4. Fibonacci 0.50 - 0.618 Golden Pocket Retracement Entry (0.559 Sweet Spot).
        5. Sheltered Swing Low SL: Clamped between 0.50% and 0.60% (Strictly ₹36 INR loss cap).
        6. Insider Confluence: Multi-source order flow validation.
        """
        if len(df) < 30:
            return None
            
        # ==============================================================================
        # 1. HARD EXCHANGE GUARDS (SPREAD & LIQUIDITY)
        # ==============================================================================
        if ticker:
            spread = ticker.get('spread_pct', 0.0)
            if spread > 0.20:
                return None
                
            turnover = ticker.get('turnover_usd', 0.0)
            if turnover > 0 and turnover < 100000:
                return None

        # ==============================================================================
        # 2. AI PSYCHOLOGY & COIN SUSPENSION CHECK
        # ==============================================================================
        if symbol:
            is_susp, susp_reason = ai_advisor.is_coin_suspended(symbol)
            if is_susp:
                return None

        df = MomentumStrategy.calculate_indicators(df)
        
        # Closed candle and live candle
        closed = df.iloc[-2]
        prev_closed = df.iloc[-3]
        live_now = df.iloc[-1]
        
        live_price = float(live_now['close'])
        atr = float(closed['atr14']) if not np.isnan(closed['atr14']) else float(closed['high'] - closed['low'])
        candle_time = str(closed['t'])
        
        lowest_1h = float(closed['ll12']) if not np.isnan(closed['ll12']) else float(df['low'].iloc[-12:].min())
        highest_1h = float(closed['hh12']) if not np.isnan(closed['hh12']) else float(df['high'].iloc[-12:].max())
        
        ema10 = float(closed['ema10'])
        ema20 = float(closed['ema20'])
        ema50 = float(closed['ema50'])
        prev_ema10 = float(prev_closed['ema10'])
        prev_ema20 = float(prev_closed['ema20'])
        rsi = float(closed['rsi14'])
        
        bid_imbalance = ticker.get('bid_imbalance', 0.50) if ticker else 0.50
        
        candidate_signal = None
        
        # ----------------------------------------------------
        # 🟢 ENGINE 1: WHALE GOLDEN POCKET OTE (LONG SETUP)
        # ----------------------------------------------------
        pump_from_1h_low = (live_price - lowest_1h) / lowest_1h if lowest_1h > 0 else 0
        anti_climax_pump_cap = getattr(config, 'ANTI_CLIMAX_MAX_PUMP_PCT', 0.040)
        
        # Anti-Climax Guard: NEVER buy if price > 4% above 1h low!
        if pump_from_1h_low <= anti_climax_pump_cap:
            ema_bullish_shift = (ema10 >= ema20) and (prev_ema10 <= prev_ema20 or ema10 > ema50)
            
            # Bottom Sweep: Lower wick rejection on swing low
            has_lower_rejection = (closed['lower_wick'] >= 0.20) or (closed['low'] <= lowest_1h * 1.005)
            
            if ema_bullish_shift and has_lower_rejection and rsi <= 65.0:
                swing_low = lowest_1h
                impulse_high = max(float(closed['high']), float(prev_closed['high']))
                leg_range = impulse_high - swing_low
                min_disp = getattr(config, 'MIN_DISPLACEMENT_LEG_PCT', 0.012)
                
                # Displacement leg must be at least 1.2%
                if leg_range > 0 and (leg_range / swing_low) >= min_disp:
                    fib_500 = impulse_high - config.FIB_ENTRY_MIN * leg_range
                    fib_618 = impulse_high - config.FIB_ENTRY_MAX * leg_range
                    ote_entry = impulse_high - config.FIB_SWEET_SPOT * leg_range
                    
                    # Check if live price is in or near Golden Pocket discount
                    if abs(live_price - ote_entry) / ote_entry <= 0.008 or live_price <= fib_500:
                        entry_p = min(live_price, ote_entry)
                        
                        # Sheltered Stop Loss 0.3% below swing low
                        raw_sl = swing_low * (1.0 - config.STRUCTURAL_SL_BUFFER_PCT)
                        sl_dist = (entry_p - raw_sl) / entry_p
                        
                        # Hard clamped between MIN_SL_PCT (0.50%) and MAX_SL_PCT (0.60% / ₹36 max loss)
                        min_sl = getattr(config, 'MIN_SL_PCT', 0.0050)
                        max_sl = getattr(config, 'MAX_SL_PCT', 0.0060)
                        sl_dist = max(min_sl, min(max_sl, sl_dist))
                        sl_p = entry_p * (1.0 - sl_dist)
                        
                        tp1_p = entry_p * (1.0 + getattr(config, 'TP1_PCT', 0.0150))
                        
                        candidate_signal = {
                            'side': 'BUY',
                            'price': entry_p,
                            'sl': sl_p,
                            'tp1': tp1_p,
                            'atr': atr,
                            'time': candle_time,
                            'setup': 'Whale Golden Pocket OTE Long',
                            'fib_level': '0.559 Sweet Spot',
                            'sl_dist_pct': sl_dist
                        }

        # ----------------------------------------------------
        # 🔴 ENGINE 2: WHALE GOLDEN POCKET OTE (SHORT SETUP)
        # ----------------------------------------------------
        if not candidate_signal:
            dump_from_1h_high = (highest_1h - live_price) / highest_1h if highest_1h > 0 else 0
            anti_climax_dump_cap = getattr(config, 'ANTI_CLIMAX_MAX_DUMP_PCT', 0.040)
            
            if dump_from_1h_high <= anti_climax_dump_cap:
                ema_bearish_shift = (ema10 <= ema20) and (prev_ema10 >= prev_ema20 or ema10 < ema50)
                has_upper_rejection = (closed['upper_wick'] >= 0.20) or (closed['high'] >= highest_1h * 0.995)
                
                if ema_bearish_shift and has_upper_rejection and rsi >= 35.0:
                    swing_high = highest_1h
                    impulse_low = min(float(closed['low']), float(prev_closed['low']))
                    leg_range = swing_high - impulse_low
                    min_disp = getattr(config, 'MIN_DISPLACEMENT_LEG_PCT', 0.012)
                    
                    if leg_range > 0 and (leg_range / swing_high) >= min_disp:
                        fib_500 = impulse_low + config.FIB_ENTRY_MIN * leg_range
                        fib_618 = impulse_low + config.FIB_ENTRY_MAX * leg_range
                        ote_entry = impulse_low + config.FIB_SWEET_SPOT * leg_range
                        
                        if abs(live_price - ote_entry) / ote_entry <= 0.008 or live_price >= fib_500:
                            entry_p = max(live_price, ote_entry)
                            raw_sl = swing_high * (1.0 + config.STRUCTURAL_SL_BUFFER_PCT)
                            sl_dist = (raw_sl - entry_p) / entry_p
                            
                            min_sl = getattr(config, 'MIN_SL_PCT', 0.0050)
                            max_sl = getattr(config, 'MAX_SL_PCT', 0.0060)
                            sl_dist = max(min_sl, min(max_sl, sl_dist))
                            sl_p = entry_p * (1.0 + sl_dist)
                            
                            tp1_p = entry_p * (1.0 - getattr(config, 'TP1_PCT', 0.0150))
                            
                            candidate_signal = {
                                'side': 'SELL',
                                'price': entry_p,
                                'sl': sl_p,
                                'tp1': tp1_p,
                                'atr': atr,
                                'time': candle_time,
                                'setup': 'Whale Golden Pocket OTE Short',
                                'fib_level': '0.559 Sweet Spot',
                                'sl_dist_pct': sl_dist
                            }

        if not candidate_signal:
            return None

        # ==============================================================================
        # 3. ENFORCE INSTITUTIONAL INSIDER CONFLUENCE & AI QUALITY GATE
        # ==============================================================================
        req_score = ai_advisor.get_required_entry_score()
        
        if insider_conf:
            score = insider_conf.get('score', 0)
            if score < req_score:
                return None
                
            cvd = insider_conf.get('cvd', 1.0)
            whales = insider_conf.get('top_whales', 1.0)
            insider_notes = insider_conf.get('reason', '')
            
            candidate_signal['reason'] = (
                f"{candidate_signal['setup']} [{candidate_signal['fib_level']} | Score: {score}/100 | "
                f"CVD: {cvd:.2f}x | Whales: {whales:.2f}x | SL: {candidate_signal['sl_dist_pct']*100:.2f}%]"
            )
            candidate_signal['insider_score'] = score
            candidate_signal['insider_metrics'] = insider_conf
        else:
            candidate_signal['reason'] = (
                f"{candidate_signal['setup']} [{candidate_signal['fib_level']} | Depth: {bid_imbalance*100:.0f}% | "
                f"SL: {candidate_signal['sl_dist_pct']*100:.2f}%]"
            )

        return candidate_signal
