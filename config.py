"""
========================================================================================
ELITE PRICE ACTION & WICK PSYCHOLOGY SNIPER BOT - CONFIGURATION (OPTION 2 MASTER ENGINE)
Exchange: Delta Exchange India (api.india.delta.exchange)
========================================================================================
"""
import os

# TRADING MODE
# True  = Simulated execution with realistic fills and slippage (100% safe)
# False = Real order execution on Delta Exchange India via authenticated REST API
PAPER_TRADING = True

# TELEGRAM BOT ALERTS & REMOTE CONTROL
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8796367813:AAEqg1mj4ARxJ1hNS7ESbl0wvtov3Tu6C_s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7271911207")

# DELTA EXCHANGE INDIA API CREDENTIALS (Required if PAPER_TRADING = False)
DELTA_API_KEY = os.getenv("DELTA_INDIA_API_KEY", "YOUR_DELTA_INDIA_API_KEY")
DELTA_API_SECRET = os.getenv("DELTA_INDIA_API_SECRET", "YOUR_DELTA_INDIA_API_SECRET")
DELTA_BASE_URL = "https://api.india.delta.exchange"
DELTA_WS_URL = "wss://socket.india.delta.exchange"

# CAPITAL MANAGEMENT (MONTHLY-STEPPED COMPOUNDING ENGINE)
# Active capital is fixed for the entire calendar month and only steps up at month-end!
INITIAL_CAPITAL = 2000.0         # Starting capital ($2,000.00)
MAX_ACTIVE_CAPITAL = 20000.0     # Maximum active risk cap ($20,000.00)
RISK_PER_TRADE_PCT = 0.0625      # 6.25% risk per trade based on month-starting active capital
LEVERAGE = 20                    # 20x Isolated Margin
MAX_CONCURRENT_TRADES = 3        # Maximum simultaneous open trades across universe
MAX_POSITION_USD = 12000.0       # $12,000 Fee Shield Cap: strictly caps Delta taker fees to ~$12/trade!

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

# OPTION 2: TIMEFRAMES & FILTER ENGINE
CANDLE_RESOLUTION = "3m"         # 3-Minute Entry Candles (Faster trigger, smaller SL, bigger R-multiple)
TREND_RESOLUTION = "1h"          # 1-Hour Trend Bias
LOOKBACK_SWING_BARS = 16         # 16-bar swing high / swing low lookback
WICK_RATIO_MIN = 0.48            # Minimum 48% wick rejection to confirm institutional absorption
VOLUME_MULT_MIN = 1.30           # Minimum 1.30x volume surge vs 16-period moving average
DOUBLE_SWEEP_BUFFER_PCT = 0.0012 # 0.12% double-sweep safety buffer beyond wick tip
FVG_MAX_WAIT_BARS = 4            # Wait up to 4 bars for pullback into Fair Value Gap limit zone
MIN_SL_PCT = 0.0018              # Minimum SL distance (0.18%)
MAX_SL_PCT = 0.0050              # Maximum SL distance (0.50%)

# ADVANCED INSTITUTIONAL FILTERS
LOSS_COOLDOWN_SECONDS = 7200     # 2-Hour Loss Cooldown per coin after SL hit
WEAK_HOURS_IST = [1, 9]          # Skip low-liquidity chop sessions: 01:00-02:00 AM & 09:00-10:00 AM IST

# PROFIT TARGETS & TRAILING LOCK RULES
TP1_R = 1.9                      # Target 1: 1.9R (Closes 40% position)
TP1_CLOSE_RATIO = 0.40           # 40% cash profit secured at TP1
TRAILING_LOCK_R = 0.50           # Shift Stop-Loss of remaining 60% runner to +0.50R in PROFIT
TP2_R = 4.0                      # Target 2: 4.0R (Closes remaining 60% runner for full home run)
MAX_HOLD_CANDLES = 120           # 6 hours max hold time (120 x 3m)

# LOCAL DASHBOARD & CLOUD KEEPALIVE SERVER
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8085
