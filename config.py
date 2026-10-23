"""
========================================================================================
ICT ASIAN JUDAS SWING & OTE MASTER BOT - CONFIGURATION (INR EDITION)
Exchange: Delta Exchange India (api.india.delta.exchange)
Currency: Indian Rupee (INR - ₹)
Clock: Strictly Locked to Indian Standard Time (IST, UTC+5:30)
========================================================================================
"""
import os
import datetime

# ========================================================================================
# 1. EXPLICIT INDIAN STANDARD TIME (IST) TIMEZONE LOCK (UTC+5:30)
# Guarantees identical clock on Local Windows, Cloud VPS, Docker, and Render (which defaults to UTC)
# ========================================================================================
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_now_ist():
    """Returns current datetime strictly locked to Indian Standard Time (IST, UTC+5:30)."""
    return datetime.datetime.now(IST)

def format_timestamp_ist(ts):
    """Converts a unix timestamp (seconds) into formatted IST string."""
    return datetime.datetime.fromtimestamp(ts, tz=IST).strftime('%Y-%m-%d %H:%M:%S')

# ========================================================================================
# 2. TRADING MODE
# True  = Simulated execution with realistic fills and slippage (100% safe paper trading)
# False = Real order execution on Delta Exchange India via authenticated REST API
# ========================================================================================
PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"

# ========================================================================================
# 3. TELEGRAM BOT ALERTS & REMOTE CONTROL (AUTHENTICATED)
# ========================================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8796367813:AAEqg1mj4ARxJ1hNS7ESbl0wvtov3Tu6C_s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7271911207")

# ========================================================================================
# 4. DELTA EXCHANGE INDIA API CREDENTIALS (Required if PAPER_TRADING = False)
# ========================================================================================
DELTA_API_KEY = os.getenv("DELTA_INDIA_API_KEY", "YOUR_DELTA_INDIA_API_KEY")
DELTA_API_SECRET = os.getenv("DELTA_INDIA_API_SECRET", "YOUR_DELTA_INDIA_API_SECRET")
DELTA_BASE_URL = "https://api.india.delta.exchange"
DELTA_WS_URL = "wss://socket.india.delta.exchange"

# ========================================================================================
# 5. INDIAN RUPEE (INR - ₹) CAPITAL MANAGEMENT & 20X LEVERAGE
# Delta Exchange India runs deposits, withdrawals, margin, and balances in INR (₹)
# ========================================================================================
USD_INR_RATE = float(os.getenv("USD_INR_RATE", "90.0"))        # Conversion peg (~₹90 / USD)
INITIAL_CAPITAL_INR = float(os.getenv("INITIAL_CAPITAL_INR", "2000.0"))    # ₹2,000 Starting Capital
MAX_ACTIVE_CAPITAL_INR = float(os.getenv("MAX_ACTIVE_CAPITAL_INR", "50000.0"))  # ₹50,000 Active Capital Hard Cap
RISK_PER_TRADE_PCT = 0.040        # 4.0% Golden Risk per trade (₹80 on ₹2,000 capital)
LEVERAGE = 20                    # 20x Leverage (Isolated Margin)
MAX_CONCURRENT_TRADES = 3        # Maximum simultaneous open trades
MAX_MARGIN_PER_TRADE_PCT = 0.50  # 50% Margin cap (50% free cash reserve guaranteed)
MAX_POSITION_INR = 500000.0      # Position cap dynamic up to ₹50k capital

def format_inr(amount):
    """Formats currency into Indian Rupee format."""
    return f"₹{amount:,.2f}"

# ========================================================================================
# 6. ASSET UNIVERSE: TOP 7 LEADERBOARD COINS (OPTIMIZED MODEL C)
# ========================================================================================
SYMBOLS = [
    'BTCUSD',    # Bitcoin (Highest Liquidity & Volume)
    'XRPUSD',    # Ripple (Cleanest Range Sweeps)
    'SOLUSD',    # Solana (Fastest Momentum)
    'DOGEUSD',   # Dogecoin
    'AVAXUSD',   # Avalanche
    'BNBUSD',    # BNB
    'ADAUSD'     # Cardano
]

# ========================================================================================
# 7. ELITE SNIPER TIMEFRAMES & SESSIONS (LOCKED STRICTLY TO IST UTC+5:30)
# ========================================================================================
CANDLE_RESOLUTION = "3m"         # 3-Minute Precision Entry Candles (Sniper Execution)
TREND_RESOLUTION = "1h"          # 1-Hour Trend Bias (20-EMA Alignment - Highest Profit Anchor)

WEAK_HOURS_IST = [1, 9]          # Skip 1-2 AM and 9-10 AM IST low-volume chop hours
LOOKBACK_SWING_BARS = 16         # 16 bars lookback for liquidity swing high/low
VOLUME_MULT_MIN = 1.25           # Minimum 1.25x volume expansion (Model C Optimized)
WICK_RATIO_MIN = 0.45            # Minimum 45% absorption wick ratio (Model C Optimized)
DOUBLE_SWEEP_BUFFER_PCT = 0.0008 # Protective buffer beyond sweep wick tip
FVG_MAX_WAIT_BARS = 4            # Wait up to 4 bars for pullback into FVG limit zone
MIN_SL_PCT = 0.0018              # Minimum 0.18% SL
MAX_SL_PCT = 0.0050              # Maximum 0.50% SL
BREAKEVEN_TRIGGER_R = 1.0        # Trigger BE shield at +1.0R
BREAKEVEN_LOCK_R = 0.10          # Lock at +0.10R

# Asian Session: 05:30 AM to 12:30 PM IST
ASIAN_START_MINUTES = 5 * 60 + 30   # 330 mins (05:30 IST)
ASIAN_END_MINUTES = 12 * 60 + 30    # 750 mins (12:30 IST)

# London Killzone: 12:30 PM to 04:30 PM IST (Judas Sweep Execution)
LONDON_KZ_START_MINUTES = 12 * 60 + 30  # 750 mins (12:30 IST)
LONDON_KZ_END_MINUTES = 16 * 60 + 30    # 990 mins (16:30 IST)

# NY Killzone: 05:30 PM to 10:30 PM IST (Displacement & Expansion)
NY_KZ_START_MINUTES = 17 * 60 + 30      # 1050 mins (17:30 IST)
NY_KZ_END_MINUTES = 22 * 60 + 30        # 1350 mins (22:30 IST)

# ========================================================================================
# 8. ICT OTE & DISPLACEMENT RULES
# ========================================================================================
MIN_DISPLACEMENT_BODY_ATR = 0.70 # Minimum 0.70 ATR displacement candle
MIN_SWEEP_DEPTH_ATR = 0.40       # Minimum 0.40 ATR sweep depth beyond Asian boundary
OTE_FIB_ENTRY = 0.618            # 0.618 Fibonacci OTE entry
OTE_FIB_DEEP = 0.705             # 0.705 Fibonacci sweet spot
SL_ATR_BUFFER = 0.25             # 0.25 ATR protective buffer beyond sweep wick tip

# ========================================================================================
# 9. RESCUED RISK MANAGEMENT RULES (30% / 30% / 40% Open Runner + Ratchet Trail Lock)
# ========================================================================================
# Level 1: +1.0R -> Book 30% profit immediately & move SL to Elevated Breakeven (+0.18% Fee Shield)
RESCUE_PROFIT_R = 1.0
RESCUE_CLOSE_RATIO = 0.30
ELEVATED_BREAKEVEN_PCT = 0.0018  # +0.18% fee shield covers 100% exchange fees & GST on reversal!

# Level 2: +1.9R -> Book 30% profit & Lock SL at +1.2R Guaranteed Profit Floor!
TP1_R = 1.9
TP1_CLOSE_RATIO = 0.30
TP1_LOCK_SL_R = 1.2              # Lock SL at +1.2R guaranteed profit floor

# Level 3: Open 40% Runner -> No fixed cap, dynamically trails peak with ATR breathing room
TP2_R = 3.0                      # Reference target
RUNNER_RATIO = 0.40
TRAIL_DISTANCE_R = 0.50          # Base distance behind peak price to trail 40% runner
TRAIL_ATR_MULT = 1.25            # Multiplier for 3M ATR buffer
MIN_TRAIL_DISTANCE_R = 0.50      # Minimum trailing distance floor
MAX_TRAIL_DISTANCE_R = 0.85      # Maximum trailing distance ceiling

# ========================================================================================
# 10. CLOUD KEEPALIVE & HEALTHCHECK SERVER (RENDER DEPLOYMENT)
# Render dynamically passes $PORT environment variable (defaults to 10000)
# ========================================================================================
SERVER_HOST = "0.0.0.0"
SERVER_PORT = int(os.getenv("PORT", "10000"))
