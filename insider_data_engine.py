import time
import requests
import pandas as pd
import config

class InsiderDataEngine:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        self.btc_last_check = 0
        self.btc_trend_15m = 0.0

    def get_binance_symbol(self, delta_symbol: str) -> str:
        """
        Maps Delta India perpetual symbols to Binance Futures symbols.
        Example: 1000PEPEUSD -> 1000PEPEUSDT, SOLUSD -> SOLUSDT, BTCUSD -> BTCUSDT
        """
        sym = delta_symbol.upper()
        if sym.endswith('USD'):
            sym = sym[:-3] + 'USDT'
        elif not sym.endswith('USDT'):
            sym = sym + 'USDT'
        return sym

    def check_btc_regime(self) -> float:
        """
        Fetches BTC 15-minute price change from Binance Futures.
        If BTC is in a flash dump (< -0.8%), altcoins must NOT be longed!
        Caches for 60 seconds to prevent rate limit hits.
        """
        now = time.time()
        if now - self.btc_last_check < 60:
            return self.btc_trend_15m

        try:
            url = "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=15m&limit=2"
            r = requests.get(url, headers=self.headers, timeout=4).json()
            if r and len(r) >= 2:
                prev_open = float(r[0][1])
                curr_close = float(r[1][4])
                self.btc_trend_15m = (curr_close - prev_open) / prev_open * 100
                self.btc_last_check = now
        except Exception:
            pass
        return self.btc_trend_15m

    def fetch_binance_insider_metrics(self, delta_symbol: str) -> dict:
        """
        Fetches 100% FREE institutional order-flow data from Binance Futures:
        1. 5-minute Taker Buy/Sell CVD Volume Ratio (Real-time Market Aggression)
        2. Top Trader Accounts Long/Short Ratio (Smart Money Positioning)
        3. 5-minute Open Interest Growth (Contract Capital Inflow/Outflow)
        """
        bin_sym = self.get_binance_symbol(delta_symbol)
        metrics = {
            'taker_cvd_ratio': 1.0,      # >1.05 = Aggressive buyers, <0.95 = Aggressive sellers
            'top_trader_ratio': 1.0,     # >1.10 = Whales Net Long, <0.90 = Whales Net Short
            'oi_change_pct': 0.0,        # >0% = Capital Entering, <0% = Liquidation/Exiting
            'binance_available': False
        }

        try:
            # 1. 5m Taker Buy/Sell Volume Ratio (True CVD)
            url_cvd = f"https://fapi.binance.com/futures/data/takerlongshortRatio?symbol={bin_sym}&period=5m&limit=1"
            r_cvd = requests.get(url_cvd, headers=self.headers, timeout=3).json()
            if r_cvd and isinstance(r_cvd, list) and len(r_cvd) > 0:
                metrics['taker_cvd_ratio'] = float(r_cvd[0].get('buySellRatio', 1.0))
                metrics['binance_available'] = True

            # 2. Top Trader Smart Money Position Ratio
            url_top = f"https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={bin_sym}&period=5m&limit=1"
            r_top = requests.get(url_top, headers=self.headers, timeout=3).json()
            if r_top and isinstance(r_top, list) and len(r_top) > 0:
                metrics['top_trader_ratio'] = float(r_top[0].get('longShortRatio', 1.0))
                metrics['binance_available'] = True

            # 3. 5m Open Interest Growth Trend
            url_oi = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={bin_sym}&period=5m&limit=2"
            r_oi = requests.get(url_oi, headers=self.headers, timeout=3).json()
            if r_oi and isinstance(r_oi, list) and len(r_oi) >= 2:
                oi_0 = float(r_oi[0].get('sumOpenInterestValue', 0))
                oi_1 = float(r_oi[1].get('sumOpenInterestValue', 0))
                if oi_0 > 0:
                    metrics['oi_change_pct'] = ((oi_1 - oi_0) / oi_0) * 100
        except Exception:
            pass

        return metrics

    def compute_confluence(self, delta_symbol: str, side: str, delta_ticker: dict) -> dict:
        """
        Aggregates Delta India Order Book Depth + Binance Institutional Data + BTC Regime.
        Returns a Confluence Score (0 - 100) and Pass/Fail verification.
        """
        binance_data = self.fetch_binance_insider_metrics(delta_symbol)
        btc_15m = self.check_btc_regime()

        # Delta Metrics
        bid_imb = delta_ticker.get('bid_imbalance', 0.50)
        spread = delta_ticker.get('spread_pct', 0.0)
        turnover = delta_ticker.get('turnover_usd', 0.0)
        funding = delta_ticker.get('funding_rate', 0.0)

        # Binance Metrics
        cvd = binance_data['taker_cvd_ratio']
        top_whales = binance_data['top_trader_ratio']
        oi_chg = binance_data['oi_change_pct']

        score = 0
        reasons = []

        # ==============================================================================
        # CRITICAL HARD GUARDS (IMMEDIATE DISQUALIFICATION)
        # ==============================================================================
        if spread > 0.20:
            return {'passed': False, 'score': 0, 'reason': f"REJECTED: Spread too wide ({spread:.3f}% > 0.20%)"}

        if turnover > 0 and turnover < 80000:
            return {'passed': False, 'score': 0, 'reason': f"REJECTED: Low Delta volume (${turnover:,.0f} < $80k)"}

        # BTC Flash Dump Guard (For Longs)
        if side == 'BUY' and btc_15m < -0.80:
            return {'passed': False, 'score': 0, 'reason': f"REJECTED: BTC Flash Dump ({btc_15m:.2f}% in 15m)"}

        # ==============================================================================
        # SCORING ENGINE (0 TO 100 POINTS)
        # ==============================================================================
        if side == 'BUY':
            # 1. Delta India Resting Depth (Bids must dominate or support) [Max 25 pts]
            if bid_imb >= 0.55:
                score += 25
                reasons.append(f"Delta Bids Heavy ({bid_imb*100:.0f}%)")
            elif bid_imb >= 0.40:
                score += 15
                reasons.append(f"Delta Bids Balanced ({bid_imb*100:.0f}%)")
            else:
                reasons.append(f"Delta Asks Heavy ({(1-bid_imb)*100:.0f}%)")

            # 2. Binance Global Taker CVD Aggression [Max 30 pts]
            if cvd >= 1.15:
                score += 30
                reasons.append(f"Aggressive Buyers (CVD {cvd:.2f}x)")
            elif cvd >= 1.00:
                score += 20
                reasons.append(f"Buyers Active (CVD {cvd:.2f}x)")
            elif cvd >= 0.90:
                score += 5
            else:
                score -= 15
                reasons.append(f"Sellers Active (CVD {cvd:.2f}x)")

            # 3. Binance Top Trader Whale Sentiment [Max 25 pts]
            if top_whales >= 1.25:
                score += 25
                reasons.append(f"Whales Net Long ({top_whales:.2f}x)")
            elif top_whales >= 1.05:
                score += 15
                reasons.append(f"Whales Leaning Long ({top_whales:.2f}x)")
            elif top_whales <= 0.85:
                score -= 10
                reasons.append(f"Whales Shorting ({top_whales:.2f}x)")

            # 4. Open Interest Inflow Trend [Max 10 pts]
            if oi_chg > 0.02:
                score += 10
                reasons.append(f"Fresh Money Inflow (OI {oi_chg:+.2f}%)")
            elif oi_chg >= -0.15:
                score += 5

            # 5. Funding Squeeze Fuel Bonus [Max 10 pts]
            if funding < -0.005:
                score += 10
                reasons.append(f"Short Squeeze Fuel (Funding {funding*100:.3f}%)")

        elif side == 'SELL':
            # 1. Delta India Resting Depth (Asks must dominate or support) [Max 25 pts]
            if bid_imb <= 0.45:
                score += 25
                reasons.append(f"Delta Asks Heavy ({(1-bid_imb)*100:.0f}%)")
            elif bid_imb <= 0.60:
                score += 15
                reasons.append(f"Delta Depth Balanced")

            # 2. Binance Global Taker CVD Aggression [Max 30 pts]
            if cvd <= 0.85:
                score += 30
                reasons.append(f"Aggressive Sellers (CVD {cvd:.2f}x)")
            elif cvd <= 1.00:
                score += 20
                reasons.append(f"Sellers Dominating (CVD {cvd:.2f}x)")
            elif cvd <= 1.10:
                score += 5
            else:
                score -= 15
                reasons.append(f"Buyers Absorbing (CVD {cvd:.2f}x)")

            # 3. Binance Top Trader Whale Sentiment [Max 25 pts]
            if top_whales <= 0.85:
                score += 25
                reasons.append(f"Whales Net Short ({top_whales:.2f}x)")
            elif top_whales <= 0.95:
                score += 15
                reasons.append(f"Whales Leaning Short ({top_whales:.2f}x)")

            # 4. Open Interest Inflow Trend [Max 10 pts]
            if oi_chg > 0.02:
                score += 10
                reasons.append(f"Short Accumulation (OI {oi_chg:+.2f}%)")
            elif oi_chg >= -0.15:
                score += 5

            # 5. High Positive Funding [Max 10 pts]
            if funding > 0.03:
                score += 10
                reasons.append(f"Long Squeeze Danger (Funding {funding*100:.3f}%)")

        # Threshold: 45 points provides solid institutional confirmation without paralyzing the bot
        passed = score >= 45
        summary_str = " | ".join(reasons)
        
        return {
            'passed': passed,
            'score': max(0, score),
            'cvd': cvd,
            'top_whales': top_whales,
            'oi_chg': oi_chg,
            'bid_imb': bid_imb,
            'btc_15m': btc_15m,
            'reason': summary_str
        }
