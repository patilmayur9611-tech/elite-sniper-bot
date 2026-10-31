import time
import json
import os
import hmac
import hashlib
import requests
import pandas as pd
import config
import telegram_helper

class DeltaClient:
    def __init__(self):
        self.base_url = config.DELTA_BASE_URL
        self.paper_mode = config.PAPER_TRADING
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        self.paper_file = os.path.join(os.path.dirname(__file__), "paper_trades.json")
        self.products = {}
        self.load_paper_state()
        self.load_products()

    def load_paper_state(self):
        if os.path.exists(self.paper_file):
            try:
                with open(self.paper_file, 'r') as f:
                    self.paper_state = json.load(f)
                    return
            except Exception:
                pass
        self.paper_state = {
            "wallet_balance": config.TOTAL_WALLET_CAPITAL,
            "active_margin": 0.0,
            "open_positions": {},
            "trade_history": []
        }
        self.save_paper_state()

    def save_paper_state(self):
        with open(self.paper_file, 'w') as f:
            json.dump(self.paper_state, f, indent=4)

    def load_products(self, limit=config.TOP_SYMBOLS_LIMIT):
        try:
            r = requests.get(f"{self.base_url}/v2/products", headers=self.headers, timeout=10).json()
            if 'result' in r:
                live_perps = [
                    p for p in r['result'] 
                    if p.get('contract_type') == 'perpetual_futures' 
                    and p.get('trading_status') == 'operational' 
                    and 'USD' in p.get('symbol', '')
                ]
                r_tickers = requests.get(f"{self.base_url}/v2/tickers", headers=self.headers, timeout=10).json()
                vol_map = {}
                if 'result' in r_tickers:
                    for t in r_tickers['result']:
                        vol_map[t.get('symbol')] = float(t.get('turnover_usd') or 0)
                
                sorted_perps = sorted(live_perps, key=lambda x: vol_map.get(x['symbol'], 0), reverse=True)[:limit]
                for p in sorted_perps:
                    sym = p['symbol']
                    tick = float(p.get('tick_size', 0.0001))
                    self.products[sym] = {
                        'id': p['id'],
                        'symbol': sym,
                        'tick_size': tick,
                        'contract_value': float(p.get('contract_value', 1.0)),
                        'precision': self._get_precision(tick)
                    }
                print(f"✅ Loaded {len(self.products)} liquid perpetual products from Delta India.")
        except Exception as e:
            print(f"❌ Error loading Delta products: {e}")

    def _get_precision(self, tick_size: float) -> int:
        if tick_size <= 0:
            return 2
        s = f"{tick_size:.10f}".rstrip('0')
        return len(s.split('.')[1]) if '.' in s else 0

    def round_price(self, symbol: str, price: float) -> float:
        spec = self.products.get(symbol)
        if not spec:
            return round(price, 4)
        tick = spec['tick_size']
        prec = spec['precision']
        return round(round(price / tick) * tick, prec)

    def calculate_contracts(self, symbol: str, price: float) -> int:
        spec = self.products.get(symbol)
        if not spec or price <= 0:
            return 1
        notional_usd = config.POSITION_NOTIONAL_INR / config.USD_INR_RATE
        contract_val_usd = price * spec['contract_value']
        contracts = int(round(notional_usd / contract_val_usd))
        return max(1, contracts)

    def fetch_candles(self, symbol: str, resolution: str = config.CANDLE_TIMEFRAME, count: int = 35) -> pd.DataFrame:
        end_t = int(time.time())
        start_t = end_t - (count * 300)
        url = f"{self.base_url}/v2/chart/history?resolution={resolution}&symbol={symbol}&from={start_t}&to={end_t}"
        try:
            r = requests.get(url, headers=self.headers, timeout=6)
            if r.status_code == 200:
                res = r.json().get('result', {})
                if 'c' in res and len(res['c']) >= 20:
                    df = pd.DataFrame({
                        't': pd.to_datetime(res['t'], unit='s'),
                        'open': pd.to_numeric(res['o']),
                        'high': pd.to_numeric(res['h']),
                        'low': pd.to_numeric(res['l']),
                        'close': pd.to_numeric(res['c']),
                        'volume': pd.to_numeric(res['v'])
                    }).sort_values('t').reset_index(drop=True)
                    return df
        except Exception:
            pass
        return pd.DataFrame()

    def get_mark_price(self, symbol: str) -> float:
        try:
            r = requests.get(f"{self.base_url}/v2/tickers/{symbol}", headers=self.headers, timeout=4).json()
            return float(r['result']['mark_price'])
        except Exception:
            return 0.0

    def generate_signature(self, secret: str, method: str, path: str, timestamp: str, payload: str = "") -> str:
        """HMAC SHA256 Signature for Delta Exchange India Authenticated API"""
        message = method + timestamp + path + payload
        signature = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature
