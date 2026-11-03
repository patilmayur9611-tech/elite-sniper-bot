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
        df['bb_width'] = (4 * df['bb_std']) / (df['bb_mid'] + 1e-8)
        df['bb_width_sma'] = df['bb_width'].rolling(20).mean()
        # Fallback if bb_width_sma has any NaN: compare to expanding mean
        fallback_sma = df['bb_width'].expanding().mean()
        effective_sma = df['bb_width_sma'].fillna(fallback_sma)
        df['is_squeeze'] = df['bb_width'].shift(1) <= effective_sma.shift(1)
        
        # 6. Candle Anatomy (Wick and Body Ratios)
        candle_range = df['high'] - df['low'] + 1e-8
        df['upper_wick'] = (df['high'] - df[['open', 'close']].max(axis=1)) / candle_range
        df['lower_wick'] = (df[['open', 'close']].min(axis=1) - df['low']) / candle_range
        df['body_ratio'] = (df['close'] - df['open']).abs() / candle_range
        
        return df

    @staticmethod
    def check_signal(df: pd.DataFrame, ticker: dict = None, insider_conf: dict = None):
        """
        Multi-Dimensional Institutional Decision Engine:
        Requires BOTH Candlestick Microstructure AND Multi-Source Insider Order-Flow Confluence.
        Zero Blind Trades: If insider data does not confirm, the trade is rejected!
        """
        if len(df) < 40:
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

        df = MomentumStrategy.calculate_indicators(df)
        
        # STRICT RULE: df.iloc[-2] is the FULLY CLOSED 5-minute candle
        closed = df.iloc[-2]
        live_now = df.iloc[-1]
        
        candle_pct = (closed['close'] - closed['open']) / closed['open']
        atr = closed['atr14'] if not np.isnan(closed['atr14']) else (closed['high'] - closed['low'])
        candle_time = str(closed['t'])
        
        # Microstructure Depth from Ticker
        bid_imbalance = ticker.get('bid_imbalance', 0.50) if ticker else 0.50
        
        candidate_signal = None
        
        # ==============================================================================
        # ENGINE 1: INSTITUTIONAL SWEEP & RECLAIM
        # ==============================================================================
        # Bullish Sweep: Price sweeps 20-candle low, hunts stops, reclaims with lower wick >= 35%
        if (closed['low'] < closed['ll20'] and 
            closed['close'] > closed['ll20'] and 
            closed['close'] > closed['open'] and 
            closed['lower_wick'] >= 0.35 and 
            closed['rvol'] >= 1.4 and 
            bid_imbalance >= 0.38):
            
            sl = closed['low'] - (0.15 * atr)
            tp1 = closed['close'] + (1.8 * atr)
            candidate_signal = {
                'side': 'BUY',
                'price': live_now['close'],
                'sl': sl,
                'tp1': tp1,
                'atr': atr,
                'time': candle_time,
                'setup': 'Bullish Sweep Reclaim'
            }
            
        # Bearish Sweep: Price sweeps 20-candle high, traps breakout buyers, reclaims with upper wick >= 35%
        elif (closed['high'] > closed['hh20'] and 
              closed['close'] < closed['hh20'] and 
              closed['close'] < closed['open'] and 
              closed['upper_wick'] >= 0.35 and 
              closed['rvol'] >= 1.4 and 
              bid_imbalance <= 0.62):
              
            sl = closed['high'] + (0.15 * atr)
            tp1 = closed['close'] - (1.8 * atr)
            candidate_signal = {
                'side': 'SELL',
                'price': live_now['close'],
                'sl': sl,
                'tp1': tp1,
                'atr': atr,
                'time': candle_time,
                'setup': 'Bearish Trap Reclaim'
            }

        # ==============================================================================
        # ENGINE 2: PRECISION SQUEEZE BREAKOUT (SOLID BODY & COMPRESSION)
        # ==============================================================================
        if not candidate_signal:
            # Bullish Breakout: Squeeze + Solid Green Body + Healthy Volume + Bid Depth >= 40%
            if (closed['rvol'] >= 1.8 and 
                closed['close'] > closed['hh20'] and 
                candle_pct >= 0.004 and 
                closed['upper_wick'] <= 0.35 and 
                closed['body_ratio'] >= 0.45 and 
                closed['close'] > closed['ema20'] and 
                closed['is_squeeze'] and 
                bid_imbalance >= 0.40):
                
                entry_level = max(closed['hh20'], closed['ema9'])
                sl = entry_level - (1.1 * atr)
                tp1 = closed['close'] + (2.0 * atr)
                candidate_signal = {
                    'side': 'BUY',
                    'price': live_now['close'],
                    'sl': sl,
                    'tp1': tp1,
                    'atr': atr,
                    'time': candle_time,
                    'setup': 'Solid Squeeze Breakout'
                }
                
            # Bearish Breakdown: Squeeze + Solid Red Body + Healthy Sell Volume + Ask Depth >= 40%
            elif (closed['rvol'] >= 1.8 and 
                  closed['close'] < closed['ll20'] and 
                  candle_pct <= -0.004 and 
                  closed['lower_wick'] <= 0.35 and 
                  closed['body_ratio'] >= 0.45 and 
                  closed['close'] < closed['ema20'] and 
                  closed['is_squeeze'] and 
                  bid_imbalance <= 0.60):
                  
                entry_level = min(closed['ll20'], closed['ema9'])
                sl = entry_level + (1.1 * atr)
                tp1 = closed['close'] - (2.0 * atr)
                candidate_signal = {
                    'side': 'SELL',
                    'price': live_now['close'],
                    'sl': sl,
                    'tp1': tp1,
                    'atr': atr,
                    'time': candle_time,
                    'setup': 'Solid Squeeze Breakdown'
                }

        if not candidate_signal:
            return None

        # ==============================================================================
        # 3. ENFORCE INSTITUTIONAL INSIDER CONFLUENCE (MANDATORY)
        # ==============================================================================
        if insider_conf:
            if not insider_conf.get('passed', False):
                return None
            
            score = insider_conf.get('score', 0)
            cvd = insider_conf.get('cvd', 1.0)
            whales = insider_conf.get('top_whales', 1.0)
            insider_notes = insider_conf.get('reason', '')
            
            candidate_signal['reason'] = (
                f"{candidate_signal['setup']} [Score: {score}/100 | CVD: {cvd:.2f}x | "
                f"Whales: {whales:.2f}x | {insider_notes}]"
            )
            candidate_signal['insider_score'] = score
            candidate_signal['insider_metrics'] = insider_conf
        else:
            candidate_signal['reason'] = f"{candidate_signal['setup']} (Depth: {bid_imbalance*100:.0f}%)"

        return candidate_signal
