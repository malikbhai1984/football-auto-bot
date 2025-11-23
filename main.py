#!/usr/bin/env python3
"""
Railway-ready Telegram Bot with live match prediction updates
"""

import os
import telebot
import logging
from flask import Flask, request
from dotenv import load_dotenv
import threading
import time
import requests
from datetime import datetime

# -------------------- Load ENV --------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 8080))
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")
SPORT_KEY = os.getenv("SPORT_KEY", "soccer")

# -------------------- Telegram Bot Init --------------------
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# -------------------- Flask App Init --------------------
app = Flask(__name__)

# -------------------- Logger --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BOT")

# -------------------- Helpers --------------------
def safe_request(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"HTTP request failed: {e}")
        return None

def get_live_odds():
    """
    Fetch live odds from The Odds API
    """
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
    params = {
        "apiKey": THE_ODDS_API_KEY,
        "regions": "uk",
        "markets": "h2h,totals",
        "oddsFormat": "decimal",
        "dateFormat": "iso"
    }
    return safe_request(url, params=params) or []

def simple_prediction(odds_entry):
    """
    Convert odds to simple probability-based suggestion
    """
    try:
        bookmakers = odds_entry.get("bookmakers", [])
        if not bookmakers:
            return None
        bm = bookmakers[0]
        markets = {m["key"]: m for m in bm.get("markets", [])}
    except Exception:
        return None

    # H2H
    h2h = markets.get("h2h", {}).get("outcomes", [])
    if not h2h:
        return None

    def implied_prob(price): return 1.0 / float(price) if price else 0
    probs = {}
    for o in h2h:
        probs[o["name"]] = implied_prob(o["price"])
    total = sum(probs.values())
    if total > 0:
        for k in probs: probs[k] /= total
    best_pick = max(probs, key=probs.get)
    return {"win_probs": probs, "best_pick": best_pick}

def format_message(match, prediction):
    home = match.get("home_team", "Home")
    away = match.get("away_team", "Away")
    commence = match.get("commence_time", "")
    try:
        commence_dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        commence_str = commence_dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        commence_str = commence
    msg = f"<b>{home} vs {away}</b>\nTime: {commence_str}\n"
    if prediction:
        wp = prediction["win_probs"]
        for team, prob in wp.items():
            msg += f"- {team}: {prob*100:.1f}%\n"
        msg += f"Best Pick: <b>{prediction['best_pick']}</b>\n"
    else:
        msg += "No prediction available.\n"
    msg += "\n---\nThis is for analysis only."
    return msg

# -------------------- Background Auto Thread --------------------
def background_worker():
    logger.info("Background worker started...")
    last_sent = {}
    while True:
        try:
            odds_list = get_live_odds()
            now = time.time()
            for match in odds_list[:3]:  # send top 3 matches only
                match_id = match.get("id") or match.get("key")
                if not match_id: continue
                key = str(match_id)
                if key in last_sent and now - last_sent[key] < 60:
                    continue  # skip recently sent
                pred = simple_prediction(match)
                msg = format_message(match, pred)
                bot.send_message(OWNER_CHAT_ID, msg)
                last_sent[key] = now
        except Exception as e:
            logger.error(f"Worker Error: {e}")
        time.sleep(20)  # every 20 sec

threading.Thread(target=background_worker, daemon=True).start()

# -------------------- Telegram Webhook --------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return "ERROR", 400
    return "OK", 200

# -------------------- Test Route --------------------
@app.route("/")
def home():
    return "Bot Running Successfully!"

# -------------------- Set Webhook --------------------
def set_webhook():
    webhook_url = f"{DOMAIN}/{BOT_TOKEN}"
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook Set: {webhook_url}")
    except Exception as e:
        logger.error(f"Webhook Error: {e}")

# -------------------- Run App --------------------
if __name__ == "__main__":
    try:
        set_webhook()
    except Exception as e:
        logger.error(f"Startup webhook crash: {e}")
    app.run(host="0.0.0.0", port=PORT)
