"""
========================================================================================
ELITE PRICE ACTION & WICK PSYCHOLOGY SNIPER BOT - CONFIGURATION
Exchange: Delta Exchange India (api.india.delta.exchange)
========================================================================================
"""
import os

# TRADING MODE
# True  = Simulated execution with realistic fills and slippage (100% safe)
# False = Real order execution on Delta Exchange India via authenticated REST API
PAPER_TRADING = True

# TELEGRAM BOT ALERTS & REMOTE CONTROL
TELEGRAM_BOT_TOKEN = "8944428241:AAHdy7BTfOHNtiJtuGgn08-V6QZTiptjhGE"
TELEGRAM_CHAT_ID = "7271911207"

# DELTA EXCHANGE INDIA API CREDENTIALS (Required if PAPER_TRADING = False)
DELTA_API_KEY = os.getenv("DELTA_INDIA_API_KEY", "YOUR_DELTA_INDIA_API_KEY")
DELTA_API_SECRET = os.getenv("DELTA_INDIA_API_SECRET", "YOUR_DELTA_INDIA_API_SECRET")
DELTA_BASE_URL = "https://api.india.delta.exchange"
DELTA_WS_URL = "wss://socket.india.delta.exchange"

# CAPITAL MANAGEMENT & COMPOUNDING ENGINE
INITIAL_CAPITAL = 2000.0         # Starting capital ($2,000.00)
MAX_ACTIVE_CAPITAL = 20000.0     # Capped active trading capital ($20,000.00)
RISK_PER_TRADE_PCT = 0.0625      # 6.25% risk per trade ($125 on $2k -> $1,250 max on $20k)
LEVERAGE = 20                    # 20x Isolated Margin
MAX_CONCURRENT_TRADES = 3        # Maximum simultaneous open trades across universe

# ASSET UNIVERSE (Available on Delta Exchange India)
SYMBOLS = [
    'SOLUSD',
    'AVAXUSD',
    'BTCUSD',
    'XRPUSD',
    'DOGEUSD',
    'SUIUSD',
    'KAITOUSD'
]

# ELITE PRICE ACTION & WICK PSYCHOLOGY STRATEGY PARAMETERS
CANDLE_RESOLUTION = "5m"         # 5-minute timeframe
WICK_RATIO_MIN = 0.48            # Minimum 48% wick rejection to confirm institutional absorption
VOLUME_MULT_MIN = 1.30           # Minimum 1.30x volume surge vs 20-period moving average
DOUBLE_SWEEP_BUFFER_PCT = 0.0012 # 0.12% double-sweep safety buffer beyond wick tip
LOOKBACK_SWING_BARS = 20         # Bars to identify local swing high / swing low liquidity pools

# PROFIT TARGETS & TRAILING LOCK RULES
TP1_R = 1.9                      # Target 1: 1.9R (Closes 40% position)
TP1_CLOSE_RATIO = 0.40           # 40% cash profit secured at TP1
TRAILING_LOCK_R = 0.50           # Shift Stop-Loss of remaining 60% runner to +0.50R in PROFIT
TP2_R = 4.0                      # Target 2: 4.0R (Closes remaining 60% runner for full home run)
MAX_HOLD_CANDLES = 72            # 6 hours max hold time

# LOCAL DASHBOARD & CLOUD KEEPALIVE SERVER
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8085
