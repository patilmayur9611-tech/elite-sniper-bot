# ==============================================================================
# DELTA EXCHANGE INDIA - EARLY MOMENTUM HUNTER (CONFIG)
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

# CAPITAL & LEVERAGE SETTINGS (Exact User Profile)
TOTAL_WALLET_CAPITAL = 2000.0   # Total wallet balance (₹ INR)
POSITION_NOTIONAL_INR = 6000.0  # Contract value per trade (₹5,000 - ₹7,000 range)
LEVERAGE = 15                   # 15x Leverage
MARGIN_PER_TRADE = 400.0        # ₹6,000 / 15x = ₹400 INR margin per trade
MAX_CONCURRENT_POSITIONS = 3    # Max 3 open positions at a time (Max ₹1,200 margin, ₹800 cash reserve)

# SCANNING & STRATEGY SETTINGS
TOP_SYMBOLS_LIMIT = 25          # Scan top 25 high-volume perpetual pairs on Delta India
MIN_RVOL_THRESHOLD = 3.8        # Minimum 3.8x Relative Volume spike
CANDLE_TIMEFRAME = "5"          # 5-minute candles
SCAN_INTERVAL_SECONDS = 10      # Scan loop interval (seconds)
USD_INR_RATE = 86.0             # USD to INR conversion rate
