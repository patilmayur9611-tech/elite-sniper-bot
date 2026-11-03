# ==============================================================================
# DELTA EXCHANGE INDIA - WHALE GOLDEN POCKET OTE & SMART MONEY QUANT ENGINE
# ARCHITECTURE: BOTTOM SWEEP + EMA 10/20 SHIFT + FIB 0.50-0.618 OTE + AI ADVISOR
# ==============================================================================

# MODE: True = Paper Trading (Virtual Safe Simulation), False = Real Trading (Live Money)
PAPER_TRADING = True

# TELEGRAM BOT INTEGRATION (Instant alerts to your phone)
TELEGRAM_BOT_TOKEN = "8796367813:AAEqg1mj4ARxJ1hNS7ESbl0wvtov3Tu6C_s"
TELEGRAM_CHAT_ID = "7271911207"

# DELTA EXCHANGE CREDENTIALS (Required only when PAPER_TRADING = False)
DELTA_API_KEY = "YOUR_DELTA_INDIA_API_KEY"
DELTA_API_SECRET = "YOUR_DELTA_INDIA_API_SECRET"
DELTA_BASE_URL = "https://api.india.delta.exchange"

# CAPITAL & LEVERAGE SETTINGS (Exact User Profile: ₹2,000 INR Wallet)
TOTAL_WALLET_CAPITAL = 2000.0   # Total wallet balance (₹ INR)
POSITION_NOTIONAL_INR = 6000.0  # Contract value per trade (₹6,000 INR budget)
LEVERAGE = 15                   # 15x Leverage
MARGIN_PER_TRADE = 400.0        # ₹6,000 / 15x = ₹400 INR margin per trade
MAX_CONCURRENT_POSITIONS = 3    # Max 3 open positions at a time (Max ₹1,200 margin, ₹800 cash reserve)

# SCANNING & TIMEFRAME SETTINGS
TOP_SYMBOLS_LIMIT = 25          # Scan top 25 high-turnover perpetual pairs on Delta India
MIN_RVOL_THRESHOLD = 1.4        # Minimum 1.4x Relative Volume confirmation
CANDLE_TIMEFRAME = "5"          # 5-minute candles
SCAN_INTERVAL_SECONDS = 10      # Scan loop interval (seconds)
USD_INR_RATE = 86.0             # USD to INR conversion rate

# 🛡️ GATE 1: ANTI-CLIMAX GUARD (STRICTLY BANS BUYING THE TOP!)
ANTI_CLIMAX_MAX_PUMP_PCT = 0.040 # NEVER enter Long if price is > 4.0% above 1-hour low!
ANTI_CLIMAX_MAX_DUMP_PCT = 0.040 # NEVER enter Short if price is > 4.0% below 1-hour high!

# 🎯 FIBONACCI RETRACEMENT ENTRY (0.50 - 0.618 GOLDEN POCKET OTE)
FIB_ENTRY_MIN = 0.50            # 50% Equilibrium boundary
FIB_ENTRY_MAX = 0.618           # 61.8% Golden Pocket sweet spot
FIB_SWEET_SPOT = 0.559          # 55.9% Golden Ratio sniper discount entry
MIN_DISPLACEMENT_LEG_PCT = 0.012 # At least 1.2% 1-hour displacement required (filters flat chop)

# 🛡️ SHELTERED STOP LOSS & ASYMMETRIC LOSS SHIELD
STRUCTURAL_SL_BUFFER_PCT = 0.003 # 0.3% buffer below swing low (Sheltered SL)
MIN_SL_PCT = 0.0050             # Min 0.50% Stop Loss (~₹30 risk on ₹6,000 position)
MAX_SL_PCT = 0.0060             # Max 0.60% Hard Ceiling Stop Loss (Strictly caps loss at -₹36 max!)
MAX_LOSS_PER_TRADE_INR = 36.0   # Hard Rupee loss floor per trade (Never lose more than ₹36 INR)
MAX_DAILY_LOSS_INR = 120.0      # Emergency daily circuit breaker (Pauses trading if ₹120 lost in a day)

# 🚀 MULTI-TIER HARVESTING & BREATHING ROOM TRAILING
MICRO_BE_TRIGGER_PCT = 0.0110   # At +1.10% Gain: Pull SL to +0.50% locked profit (Leaves 0.60% breathing room!)
MICRO_BE_LOCK_PCT = 0.0050      # +0.50% guaranteed win buffer (NO choking normal pullbacks!)
TP1_PCT = 0.0150                # +1.50% Target 1 Golden Harvest
TP1_BOOK_RATIO = 0.60           # Bank 60% Cash immediately at TP1
TP1_SL_LOCK_PCT = 0.0080        # Lock +0.80% on remaining 40% runner
TP2_PCT = 0.0300                # +3.00% Target 2 (Fib 1.272 Extension Runner)
