#!/usr/bin/env python3
"""
Render.com Entry Point for Delta Institutional Momentum Hunter v2
Runs:
1. Anti-Sleep Web Server (Port 10000)
2. Self-Ping Keep-Alive Worker
3. Interactive Telegram Command Listener (/status, /positions, /balance)
4. 24x7 Delta India Multi-Pair Scanner Loop (Closed Bar Execution + Sweep Alpha)
"""
import threading
from bot import start_http_server, self_ping_worker, MomentumHunterBot
import telegram_helper

if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    ping_thread.start()
    
    tg_thread = threading.Thread(target=telegram_helper.handle_telegram_commands, daemon=True)
    tg_thread.start()
    
    bot = MomentumHunterBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped cleanly.")
