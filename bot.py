"""
========================================================================================
ELITE PRICE ACTION & WICK PSYCHOLOGY SNIPER BOT - MAIN RUNNER
Delta Exchange India Live/Paper Automated Trading System
========================================================================================
"""
import time
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys

import config
from delta_client import DeltaClient
from strategy import StrategyEngine
import telegram_notifier

client = DeltaClient()
strategy = StrategyEngine(client)

class KeepAliveDashboardHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP server for cloud keepalive and web monitoring."""
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "timestamp": time.time()}).encode())
            return

        state = client.state
        history = state.get("trade_history", [])
        wins = len([t for t in history if t.get("total_pnl", 0) > 0])
        losses = len([t for t in history if t.get("total_pnl", 0) <= 0])
        win_rate = (wins / len(history) * 100) if history else 0.0

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Elite Sniper Bot Dashboard</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0b0e14; color: #e6edf3; padding: 25px; margin: 0; }}
                .container {{ max-width: 900px; margin: 0 auto; }}
                .header {{ border-bottom: 1px solid #30363d; padding-bottom: 15px; margin-bottom: 20px; }}
                .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 13px; font-weight: bold; }}
                .badge-green {{ background: #238636; color: white; }}
                .badge-blue {{ background: #1f6feb; color: white; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
                .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; }}
                .card-title {{ font-size: 12px; color: #8b949e; text-transform: uppercase; margin-bottom: 6px; }}
                .card-val {{ font-size: 22px; font-weight: bold; color: #58a6ff; }}
                .pos-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; background: #161b22; border-radius: 8px; overflow: hidden; }}
                .pos-table th, .pos-table td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #21262d; }}
                .pos-table th {{ background: #21262d; color: #8b949e; font-size: 13px; }}
                .green {{ color: #3fb950; font-weight: bold; }}
                .red {{ color: #f85149; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🎯 Elite Price Action & Wick Psychology Sniper Bot</h2>
                    <span class="badge badge-green">STATUS: RUNNING</span>
                    <span class="badge badge-blue">MODE: {'PAPER TRADING' if config.PAPER_TRADING else 'LIVE REAL MONEY'}</span>
                    <span class="badge">EXCHANGE: Delta Exchange India</span>
                </div>
                <div class="grid">
                    <div class="card">
                        <div class="card-title">Active Trading Capital</div>
                        <div class="card-val">${state['active_capital']:.2f}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">Banked Reserve (Cap: ${config.MAX_ACTIVE_CAPITAL:,.0f})</div>
                        <div class="card-val">${state.get('banked_profit', 0):.2f}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">Total Net PnL</div>
                        <div class="card-val" style="color: {'#3fb950' if state.get('total_net_pnl', 0) >= 0 else '#f85149'}">+${state.get('total_net_pnl', 0):.2f}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">Win Rate</div>
                        <div class="card-val">{win_rate:.1f}% ({wins}W / {losses}L)</div>
                    </div>
                </div>

                <h3>Active Positions ({len(state.get('open_positions', {}))})</h3>
                <table class="pos-table">
                    <tr>
                        <th>Asset</th><th>Side</th><th>Entry</th><th>Current SL</th><th>TP1 (1.9R)</th><th>TP2 (4.0R)</th><th>Status</th>
                    </tr>
        """
        positions = state.get("open_positions", {})
        if not positions:
            html += "<tr><td colspan='7' style='text-align: center; color: #8b949e;'>No active positions. Scanning 5M charts...</td></tr>"
        else:
            for sym, p in positions.items():
                side_cls = "green" if p['side'] == 'LONG' else "red"
                status_txt = "✅ TP1 Hit (+0.5R Lock)" if p.get("tp1_hit") else "Running to TP1"
                html += f"""
                    <tr>
                        <td><b>{sym}</b></td>
                        <td class="{side_cls}">{p['side']}</td>
                        <td>${p['entry_price']:.4f}</td>
                        <td>${p['sl_price']:.4f}</td>
                        <td>${p['tp1_price']:.4f}</td>
                        <td>${p['tp2_price']:.4f}</td>
                        <td>{status_txt}</td>
                    </tr>
                """

        html += """
                </table>
            </div>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        # Silence HTTP access logs
        return

def run_http_server():
    try:
        port = int(os.environ.get("PORT", config.SERVER_PORT))
        server = HTTPServer((config.SERVER_HOST, port), KeepAliveDashboardHandler)
        print(f"🌐 [WEB DASHBOARD ACTIVE] Available at port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ [HTTP SERVER WARNING] Could not bind to port: {e}")

def run_telegram_poller():
    while True:
        try:
            telegram_notifier.poll_telegram_commands(client)
        except Exception:
            pass
        time.sleep(2)

def main():
    print("=" * 80)
    print("🎯 ELITE PRICE ACTION & WICK PSYCHOLOGY SNIPER BOT")
    print("   Exchange: Delta Exchange India (api.india.delta.exchange)")
    print(f"   Mode: {'🟢 PAPER TRADING (Virtual Simulation)' if config.PAPER_TRADING else '🔥 REAL TRADING (Live Order Placement)'}")
    print(f"   Initial Capital: ${client.state['active_capital']:.2f} | Compounding Cap: ${config.MAX_ACTIVE_CAPITAL:,.0f}")
    print(f"   Risk Per Trade: {config.RISK_PER_TRADE_PCT*100:.2f}% | Leverage: {config.LEVERAGE}x Isolated")
    print(f"   TP1: {config.TP1_R}R (Close 40%) -> Lock SL at +{config.TRAILING_LOCK_R}R -> TP2: {config.TP2_R}R (Close 60%)")
    print(f"   Monitoring Assets: {', '.join(config.SYMBOLS)}")
    print("=" * 80)

    # Start Keepalive Dashboard in background thread
    dash_thread = threading.Thread(target=run_http_server, daemon=True)
    dash_thread.start()

    # Start Telegram Poller in background thread
    tg_thread = threading.Thread(target=run_telegram_poller, daemon=True)
    tg_thread.start()

    telegram_notifier.send_alert(
        f"🤖 *ELITE SNIPER BOT ONLINE!*\n"
        f"═══════════════════════\n"
        f"🏷️ Mode: *{'🟢 Paper Trading' if config.PAPER_TRADING else '🔥 Live Real Money'}*\n"
        f"💼 Active Capital: *${client.state['active_capital']:.2f}*\n"
        f"🎯 Strategy: *Wick Psychology (48% Rejection + 1.30x Vol)*\n"
        f"📊 Targets: *TP1: 1.9R (40% exit) | TP2: 4.0R (60% exit)*\n"
        f"🔒 Trailing Lock: *+0.50R Profit Guarantee after TP1*\n"
        f"🌐 Assets: `{', '.join(config.SYMBOLS)}`\n"
        f"═══════════════════════\n"
        f"🚀 _Actively scanning 5M candles on Delta Exchange India!_"
    )

    last_banner_time = 0

    while True:
        try:
            now = time.time()
            if now - last_banner_time > 60:
                dt_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                open_cnt = len(client.state["open_positions"])
                print(f"[{dt_str}] Active Capital: ${client.state['active_capital']:.2f} | Banked: ${client.state.get('banked_profit', 0):.2f} | Open Trades: {open_cnt}/{config.MAX_CONCURRENT_TRADES}")
                last_banner_time = now

            for symbol in config.SYMBOLS:
                candles = client.fetch_candles(symbol, resolution=config.CANDLE_RESOLUTION, limit=40)
                if not candles:
                    continue

                curr_candle = candles[-1]
                curr_price = curr_candle["close"]
                high_price = curr_candle["high"]
                low_price = curr_candle["low"]

                # 1. Manage any existing trade on this symbol
                if symbol in client.state["open_positions"]:
                    strategy.manage_open_positions(symbol, curr_price, high_price, low_price)

                # 2. If no trade open, search for new Elite Sniper setup
                elif telegram_notifier.BOT_ACTIVE and len(client.state["open_positions"]) < config.MAX_CONCURRENT_TRADES:
                    setup = strategy.analyze_symbol(symbol, candles)
                    if setup:
                        client.open_trade(
                            symbol=setup["symbol"],
                            side=setup["side"],
                            entry_price=setup["entry_price"],
                            sl_price=setup["sl_price"],
                            tp1_price=setup["tp1_price"],
                            tp2_price=setup["tp2_price"],
                            wick_ratio=setup["wick_ratio"],
                            vol_mult=setup["vol_mult"]
                        )

            # Sleep between scans to avoid API rate-limits
            time.sleep(10)

        except KeyboardInterrupt:
            print("\n🛑 Bot shutdown requested by user. Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"⚠️ [LOOP ERROR] {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
