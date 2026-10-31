#!/usr/bin/env python3
"""
Render.com Entry Point for Delta Early Momentum Hunter
Runs the Anti-Sleep Web Server and the 24x7 Delta India Scanner Loop
"""
import threading
from bot import start_http_server, self_ping_worker, MomentumHunterBot

if __name__ == "__main__":
    # Start Keep-Alive Server on PORT (Port 10000 on Render)
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Start Self-Ping Thread to avoid Render Free Tier 15-min idle sleep
    ping_thread = threading.Thread(target=self_ping_worker, daemon=True)
    ping_thread.start()
    
    # Start 24x7 Momentum Hunter Bot
    bot = MomentumHunterBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped cleanly.")
