import pandas as pd
import numpy as np
import config

class MomentumStrategy:
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # 20-period Volume SMA & Relative Volume
        df['vol_sma20'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / (df['vol_sma20'] + 1e-8)
        
        # ATR 14
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low'] - df['close'].shift(1)).abs()
        df['atr14'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()
        
        # Trend Filter (50 EMA)
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        
        # 20-candle Highest High & Lowest Low
        df['hh20'] = df['high'].shift(1).rolling(20).max()
        df['ll20'] = df['low'].shift(1).rolling(20).min()
        return df

    @staticmethod
    def check_signal(df: pd.DataFrame):
        if len(df) < 20:
            return None
            
        df = MomentumStrategy.calculate_indicators(df)
        curr = df.iloc[-1]
        candle_pct = (curr['close'] - curr['open']) / curr['open']
        
        # 🟢 PUMP HUNTER (LONG)
        # RVol >= 3.8x + Breakout 20-candle High + Green Candle >= 0.6% + Price > 50 EMA
        if (curr['rvol'] >= config.MIN_RVOL_THRESHOLD and 
            curr['close'] > curr['hh20'] and 
            candle_pct >= 0.006 and 
            curr['close'] > curr['ema50']):
            
            return {
                'side': 'BUY',
                'price': curr['close'],
                'atr': curr['atr14'],
                'rvol': curr['rvol'],
                'reason': f"Pump Breakout (RVol: {curr['rvol']:.1f}x, +{candle_pct*100:.2f}%)"
            }
            
        # 🔴 DUMP HUNTER (SHORT)
        # RVol >= 3.8x + Breakdown 20-candle Low + Red Candle <= -0.6% + Price < 50 EMA
        elif (curr['rvol'] >= config.MIN_RVOL_THRESHOLD and 
              curr['close'] < curr['ll20'] and 
              candle_pct <= -0.006 and 
              curr['close'] < curr['ema50']):
            
            return {
                'side': 'SELL',
                'price': curr['close'],
                'atr': curr['atr14'],
                'rvol': curr['rvol'],
                'reason': f"Dump Breakdown (RVol: {curr['rvol']:.1f}x, {candle_pct*100:.2f}%)"
            }
            
        return None
