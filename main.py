#!/usr/bin/env python3
"""
Telegram Bot: Live Football High-Confidence Predictions (85%+)
Sources: SofaScore & FlashScore
Auto-update every 5–7 minutes
"""

import os
import time
import logging
import threading
import random
from flask import Flask, request
from dotenv import load_dotenv
import telebot

# Optional: SofaScore & FlashScore scrapers (pip install sofascore-api flashscore-scraper)
from sofascore import SofaScore
from flashscore_scraper import FlashScore

# -------------------- Load ENV --------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID"))
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 8080))
BOT_NAME = os.getenv("BOT_NAME", "MyBetAlert_Bot")

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("BOT")

# -------------------- Telegram Bot --------------------
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# -------------------- Flask App --------------------
app = Flask(__name__)

# -------------------- In-memory state --------------------
active_chats = set()
last_sent_for_match = {}

# -------------------- Helpers --------------------

def safe_request(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log.warning("Request failed: %s", e)
        return None

# -------------------- Live Match Fetchers --------------------

def get_live_matches():
    """
    Fetch live matches from SofaScore & FlashScore
    Returns a list of dicts:
    {
        "home_team": str,
        "away_team": str,
        "score": str,
        "start_time": str,
        "source": str
    }
    """
    matches = []

    # --- SofaScore ---
    sofascore = safe_request(SofaScore)  # init
    if sofascore:
        live_soccer = safe_request(sofascore.get_live_matches, sport="football") or []
        for m in live_soccer:
            matches.append({
                "home_team": m.get("homeTeam", "Home"),
                "away_team": m.get("awayTeam", "Away"),
                "score": m.get("score", "-"),
                "start_time": m.get("startTime", "-"),
                "source": "SofaScore"
            })

    # --- FlashScore ---
    flashscore = safe_request(FlashScore)
    if flashscore:
        live_flash = safe_request(flashscore.get_live_matches, sport="soccer") or []
        for m in live_flash:
            matches.append({
                "home_team": m.get("home_team", "Home"),
                "away_team": m.get("away_team", "Away"),
                "score": m.get("score", "-"),
                "start_time": m.get("time", "-"),
                "source": "FlashScore"
            })

    return matches

# -------------------- Prediction Logic --------------------

def simple_prediction_from_match(match):
    """
    Dummy prediction: assign win probabilities based on random + source trend
    Replace with your real algorithm if desired
    """
    base = random.uniform(0.3, 0.7)
    home_prob = base
    away_prob = 1 - base
    draw_prob = random.uniform(0.05, 0.15)

    # normalize
    total = home_prob + away_prob + draw_prob
    probs = {
        "home": home_prob / total,
        "draw": draw_prob / total,
        "away": away_prob / total
    }

    best_pick = max(probs, key=probs.get)
    return {"win_probs": probs, "best_pick": best_pick}

def high_conf_prediction(match):
    """
    Returns prediction only if max probability >= 85%
    """
    pred = simple_prediction_from_match(match)
    max_prob = max(pred["win_probs"].values(), 0)
    if max_prob >= 0.85:
        return pred
    return None

# -------------------- Message Formatter --------------------

def format_match_message(match, prediction):
    home = match.get("home_team", "Home")
    away = match.get("away_team", "Away")
    score = match.get("score", "-")
    start_time = match.get("start_time", "-")
    source = match.get("source", "Unknown")

    msg = f"<b>{home} vs {away}</b>\nSource: {source}\nTime: {start_time}\nScore: {score}\n"

    if prediction:
        wp = prediction.get("win_probs", {})
        best = prediction.get("best_pick", "N/A").upper()
        msg += "✅ <b>High-Confidence Prediction (85%+)</b>\n"
        msg += f"Win probabilities:\n - {home}: {wp.get('home',0)*100:.1f}%\n - Draw: {wp.get('draw',0)*100:.1f}%\n - {away}: {wp.get('away',0)*100:.1f}%\n"
        msg += f"Best pick: <b>{best}</b>\n"
    else:
        msg += "No high-confidence prediction available.\n"

    msg += "\n---\nThis is probability-based suggestion only."
    return msg

# -------------------- Background Worker --------------------

def background_worker():
    log.info("Background worker started (5–7 min updates)...")
    while True:
        try:
            matches = get_live_matches()
            now = time.time()
            for match in matches:
                match_id = f"{match['home_team']}_{match['away_team']}_{match.get('source')}"
                last = last_sent_for_match.get(match_id, 0)
                if now - last < 300:  # 5 min cooldown
                    continue

                pred = high_conf_prediction(match)
                if not pred:
                    continue  # skip low confidence

                msg = format_match_message(match, pred)
                for chat_id in active_chats or [OWNER_CHAT_ID]:
                    try:
                        bot.send_message(chat_id, msg)
                    except Exception as e:
                        log.warning("Send failed: %s", e)

                last_sent_for_match[match_id] = now

            # sleep random 5–7 min
            time.sleep(random.randint(300, 420))
        except Exception as e:
            log.error("Worker error: %s", e)
            time.sleep(60)

# Start background thread
threading.Thread(target=background_worker, daemon=True).start()

# -------------------- Telegram Commands --------------------

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    bot.reply_to(message, "Salaam! Use /live to enable live updates.")

@bot.message_handler(commands=["live"])
def cmd_live(message):
    chat_id = message.chat.id
    if chat_id in active_chats:
        bot.reply_to(message, "Live updates already active.")
    else:
        active_chats.add(chat_id)
        bot.reply_to(message, "✅ Live updates enabled for this chat.")

@bot.message_handler(commands=["stop"])
def cmd_stop(message):
    chat_id = message.chat.id
    if chat_id in active_chats:
        active_chats.remove(chat_id)
        bot.reply_to(message, "Live updates stopped.")
    else:
        bot.reply_to(message, "No live updates were active.")

# -------------------- Webhook Endpoint --------------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        update = request.get_data().decode("utf-8")
        bot.process_new_updates([telebot.types.Update.de_json(update)])
    except Exception as e:
        log.error("Webhook error: %s", e)
        return "ERROR", 400
    return "OK", 200

@app.route("/")
def home():
    return "Bot Running Successfully!"

# -------------------- Webhook Setup --------------------

def set_webhook():
    webhook_url = f"{DOMAIN}/{BOT_TOKEN}"
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        log.info(f"Webhook Set: {webhook_url}")
    except Exception as e:
        log.error("Webhook failed: %s", e)

# -------------------- Main --------------------

if __name__ == "__main__":
    set_webhook()
    log.info(f"Starting Flask app on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
