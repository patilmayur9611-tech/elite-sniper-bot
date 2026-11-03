import time
import json
import os
import hmac
import hashlib
import requests
import pandas as pd
import config
import telegram_helper
import ai_advisor

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
                
                # Sort strictly by real 24h turnover so we only trade active institutional coins
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
        if not spec or price <= 0 or spec.get('contract_value', 0) <= 0:
            return 1
        size_mult = ai_advisor.get_position_size_multiplier()
        notional_usd = (config.POSITION_NOTIONAL_INR * size_mult) / config.USD_INR_RATE
        contract_val_usd = price * spec['contract_value']
        contracts = int(round(notional_usd / contract_val_usd))
        return max(1, contracts)

    def fetch_candles(self, symbol: str, resolution: str = config.CANDLE_TIMEFRAME, count: int = 100) -> pd.DataFrame:
        end_t = int(time.time())
        start_t = end_t - (count * 300)
        url = f"{self.base_url}/v2/chart/history?resolution={resolution}&symbol={symbol}&from={start_t}&to={end_t}"
        try:
            r = requests.get(url, headers=self.headers, timeout=8)
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

    def fetch_ticker(self, symbol: str) -> dict:
        """
        Fetches full live ticker data from Delta India:
        Order Book Depth (Quotes), Spread, 24h Turnover, Open Interest, Funding Rate
        """
        try:
            r = requests.get(f"{self.base_url}/v2/tickers/{symbol}", headers=self.headers, timeout=4).json()
            if 'result' in r:
                res = r['result']
                quotes = res.get('quotes', {})
                best_bid = float(quotes.get('best_bid') or 0)
                best_ask = float(quotes.get('best_ask') or 0)
                bid_size = float(quotes.get('bid_size') or 0)
                ask_size = float(quotes.get('ask_size') or 0)
                
                spread_pct = ((best_ask - best_bid) / best_bid * 100) if best_bid > 0 else 999.0
                total_depth = bid_size + ask_size
                bid_imbalance = (bid_size / total_depth) if total_depth > 0 else 0.50
                
                return {
                    'symbol': symbol,
                    'mark_price': float(res.get('mark_price') or 0),
                    'spot_price': float(res.get('spot_price') or 0),
                    'turnover_usd': float(res.get('turnover_usd') or 0),
                    'oi_value_usd': float(res.get('oi_value_usd') or 0),
                    'funding_rate': float(res.get('funding_rate') or 0),
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'bid_size': bid_size,
                    'ask_size': ask_size,
                    'spread_pct': spread_pct,
                    'bid_imbalance': bid_imbalance
                }
        except Exception:
            pass
        return {}

    def get_mark_price(self, symbol: str) -> float:
        t = self.fetch_ticker(symbol)
        return t.get('mark_price', 0.0)

    # ==============================================================================
    # 🔴 REAL MONEY TRADING (DELTA EXCHANGE INDIA AUTHENTICATED API)
    # ==============================================================================

    def _auth_request(self, method: str, path: str, payload_dict: dict = None):
        timestamp = str(int(time.time()))
        body = json.dumps(payload_dict) if payload_dict else ""
        
        signature_data = method + timestamp + path + body
        signature = hmac.new(
            config.DELTA_API_SECRET.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        auth_headers = {
            "api-key": config.DELTA_API_KEY,
            "signature": signature,
            "timestamp": timestamp,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                r = requests.get(url, headers=auth_headers, timeout=10)
            elif method == "POST":
                r = requests.post(url, data=body, headers=auth_headers, timeout=10)
            elif method == "DELETE":
                r = requests.delete(url, data=body, headers=auth_headers, timeout=10)
            return r.json()
        except Exception as e:
            print(f"❌ [AUTH API ERROR] {method} {path}: {e}")
            return None

    def get_real_wallet_balance(self) -> float:
        if config.PAPER_TRADING:
            return self.paper_state.get("wallet_balance", config.TOTAL_WALLET_CAPITAL)
        res = self._auth_request("GET", "/v2/wallet/balances")
        if res and res.get("success"):
            for b in res.get("result", []):
                if b.get("asset_symbol") in ["INR", "USD"]:
                    return float(b.get("available_balance", 0.0))
        return 0.0

    def execute_real_order(self, symbol: str, side: str, size: int, sl_price: float, tp1_price: float):
        spec = self.products.get(symbol)
        if not spec:
            return None

        payload = {
            "product_id": spec['id'],
            "size": size,
            "side": "buy" if side.upper() in ["BUY", "LONG"] else "sell",
            "order_type": "market_order",
            "stop_loss_price": str(self.round_price(symbol, sl_price)),
            "take_profit_price": str(self.round_price(symbol, tp1_price))
        }

        res = self._auth_request("POST", "/v2/orders", payload)
        if res and res.get("success"):
            print(f"🔥 [REAL ORDER SUCCESS] {side} {size} {symbol}: Order ID {res.get('result', {}).get('id')}")
            telegram_helper.send_alert(
                f"🔥 *[REAL ORDER PLACED ON DELTA INDIA]*\n\n"
                f"• *Symbol:* `{symbol}` ({side})\n"
                f"• *Contracts:* `{size}`\n"
                f"• *Stop-Loss:* `{sl_price}`\n"
                f"• *TP1:* `{tp1_price}`\n"
                f"• *Status:* `SUBMITTED TO EXCHANGE`"
            )
            return res.get("result")
        else:
            err = res.get("error", "Unknown error") if res else "Network timeout"
            print(f"❌ [REAL ORDER REJECTED] {symbol}: {err}")
            telegram_helper.send_alert(f"❌ *[REAL ORDER REJECTED]*\n{symbol} order failed: `{err}`")
            return None

    def close_real_position(self, symbol: str, side: str, size: int):
        spec = self.products.get(symbol)
        if not spec:
            return None

        close_side = "sell" if side.upper() in ["BUY", "LONG"] else "buy"
        payload = {
            "product_id": spec['id'],
            "size": size,
            "side": close_side,
            "order_type": "market_order"
        }

        res = self._auth_request("POST", "/v2/orders", payload)
        if res and res.get("success"):
            print(f"✅ [REAL POSITION CLOSED] {symbol} {close_side} {size} contracts")
            return res.get("result")
        return None
