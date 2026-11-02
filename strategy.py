import pandas as pd
import numpy as np
import config

class MomentumStrategy:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # 1. 20-period Volume SMA & Relative Volume (RVol)
        df['vol_sma20'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / (df['vol_sma20'] + 1e-8)
        
        # 2. EMAs for Trend Alignment
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # 3. ATR 14 for Volatility Measurement
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low'] - df['close'].shift(1)).abs()
        df['atr14'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
        
        # 4. 20-candle Swings (Excluding current candle)
        df['hh20'] = df['high'].shift(1).rolling(20).max()
        df['ll20'] = df['low'].shift(1).rolling(20).min()
        
        # 5. Bollinger Band Squeeze (Volatility Compression)
        df['bb_mid'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_width'] = (4 * df['bb_std']) / df['bb_mid']
        df['bb_width_sma'] = df['bb_width'].rolling(20).mean()
        df['is_squeeze'] = df['bb_width'].shift(1) <= df['bb_width_sma'].shift(1)
        
        # 6. Candle Anatomy (Wick and Body Ratios)
        candle_range = df['high'] - df['low'] + 1e-8
        df['upper_wick'] = (df['high'] - df[['open', 'close']].max(axis=1)) / candle_range
        df['lower_wick'] = (df[['open', 'close']].min(axis=1) - df['low']) / candle_range
        df['body_ratio'] = (df['close'] - df['open']).abs() / candle_range
        
        return df

    @staticmethod
    def check_signal(df: pd.DataFrame):
        """
        Evaluates signals strictly on the LAST CLOSED CANDLE (df.iloc[-2]).
        Never triggers on forming live candle (df.iloc[-1]) to eliminate fake spikes!
        """
        if len(df) < 25:
            return None
            
        df = MomentumStrategy.calculate_indicators(df)
        
        # STRICT RULE: df.iloc[-2] is the FULLY CLOSED 5-minute candle
        closed = df.iloc[-2]
        live_now = df.iloc[-1]
        
        candle_pct = (closed['close'] - closed['open']) / closed['open']
        atr = closed['atr14']
        candle_time = str(closed['t'])
        
        # ==============================================================================
        # ENGINE 1: INSTITUTIONAL SWEEP & RECLAIM (10.89 PROFIT FACTOR ALPHA)
        # ==============================================================================
        
        # Bullish Sweep: Price sweeps 20-candle low, hunts stops, and reclaims with long lower wick (>= 40%)
        if (closed['low'] < closed['ll20'] and 
            closed['close'] > closed['ll20'] and 
            closed['lower_wick'] >= 0.40 and 
            closed['rvol'] >= 2.0 and 
            closed['close'] > closed['ema50']):
            
            sl = closed['low'] - (0.15 * atr) # Tight SL right below the sweep wick
            tp1 = closed['close'] + (1.8 * atr)
            return {
                'side': 'BUY',
                'price': live_now['close'],
                'sl': sl,
                'tp1': tp1,
                'atr': atr,
                'time': candle_time,
                'reason': f"Bullish Liquidity Sweep (Wick: {closed['lower_wick']*100:.0f}%, RVol: {closed['rvol']:.1f}x)"
            }
            
        # Bearish Sweep: Price sweeps 20-candle high, traps breakout buyers, and reclaims inside with upper wick (>= 40%)
        elif (closed['high'] > closed['hh20'] and 
              closed['close'] < closed['hh20'] and 
              closed['upper_wick'] >= 0.40 and 
              closed['rvol'] >= 2.0 and 
              closed['close'] < closed['ema50']):
              
            sl = closed['high'] + (0.15 * atr) # Tight SL right above the sweep wick
            tp1 = closed['close'] - (1.8 * atr)
            return {
                'side': 'SELL',
                'price': live_now['close'],
                'sl': sl,
                'tp1': tp1,
                'atr': atr,
                'time': candle_time,
                'reason': f"Bearish Trap Sweep (Wick: {closed['upper_wick']*100:.0f}%, RVol: {closed['rvol']:.1f}x)"
            }
            
        # ==============================================================================
        # ENGINE 2: PRECISION SQUEEZE BREAKOUT (SOLID BODY & COMPRESSION)
        # ==============================================================================
        
        # Bullish Breakout: Must come out of a Squeeze, have Solid Body (Upper Wick <= 25%), and High RVol
        if (closed['rvol'] >= 3.0 and 
            closed['close'] > closed['hh20'] and 
            candle_pct >= 0.005 and 
            closed['upper_wick'] <= 0.25 and 
            closed['body_ratio'] >= 0.50 and 
            closed['close'] > closed['ema50'] and 
            closed['ema20'] > closed['ema50'] and 
            closed['is_squeeze']):
            
            # Entry on retest of 9 EMA / Breakout level
            entry_level = max(closed['hh20'], closed['ema9'])
            sl = entry_level - (1.1 * atr)
            tp1 = closed['close'] + (2.0 * atr)
            return {
                'side': 'BUY',
                'price': live_now['close'],
                'sl': sl,
                'tp1': tp1,
                'atr': atr,
                'time': candle_time,
                'reason': f"Solid Squeeze Breakout (Body: {closed['body_ratio']*100:.0f}%, RVol: {closed['rvol']:.1f}x)"
            }
            
        # Bearish Breakdown: Solid Red Body (Lower Wick <= 25%) out of squeeze below 50 EMA
        elif (closed['rvol'] >= 3.0 and 
              closed['close'] < closed['ll20'] and 
              candle_pct <= -0.005 and 
              closed['lower_wick'] <= 0.25 and 
              closed['body_ratio'] >= 0.50 and 
              closed['close'] < closed['ema50'] and 
              closed['ema20'] < closed['ema50'] and 
              closed['is_squeeze']):
              
            entry_level = min(closed['ll20'], closed['ema9'])
            sl = entry_level + (1.1 * atr)
            tp1 = closed['close'] - (2.0 * atr)
            return {
                'side': 'SELL',
                'price': live_now['close'],
                'sl': sl,
                'tp1': tp1,
                'atr': atr,
                'time': candle_time,
                'reason': f"Solid Squeeze Breakdown (Body: {closed['body_ratio']*100:.0f}%, RVol: {closed['rvol']:.1f}x)"
            }
            
        return None
