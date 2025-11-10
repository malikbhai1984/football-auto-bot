import os
import requests
import telebot
import time
import random
from datetime import datetime
from flask import Flask, request
import threading
from dotenv import load_dotenv

load_dotenv()

# -------------------------
# Config
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_KEY missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

API_URL = "https://apiv3.apifootball.com"

HEADERS = {
    "Accept": "application/json"
}

print("🤖 AI Football Analyst Ready!")

# -------------------------
# Live Matches Fetch
# -------------------------
def fetch_live_matches():
    try:
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&live=1"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                live_matches = []
                for fixture in data:
                    match_data = {
                        "match_id": fixture.get("match_id"),
                        "home_team": fixture.get("match_hometeam_name"),
                        "away_team": fixture.get("match_awayteam_name"),
                        "home_score": fixture.get("match_hometeam_score"),
                        "away_score": fixture.get("match_awayteam_score"),
                        "status": fixture.get("match_status"),
                        "league": fixture.get("league_name"),
                        "live": fixture.get("match_live")
                    }
                    live_matches.append(match_data)
                return live_matches
        return []
    except Exception as e:
        print(f"❌ Live matches fetch error: {e}")
        return []

# -------------------------
# Auto-predictor
# -------------------------
def auto_predictor():
    while True:
        try:
            matches = fetch_live_matches()
            if matches:
                for match in matches:
                    home = match["home_team"]
                    away = match["away_team"]
                    home_score = match["home_score"] or "0"
                    away_score = match["away_score"] or "0"

                    # Example simple prediction logic
                    prediction = f"📊 Live: {home} {home_score} - {away_score} {away}\n"
                    prediction += "Market: Over 2.5 Goals | Prediction: Yes | Confidence: 90%\n"
                    prediction += "BTTS: Yes | Last 10 Min Goal Chance: 80%\n"
                    prediction += "Likely Correct Scores: 2-1, 1-1\n"

                    try:
                        bot.send_message(OWNER_CHAT_ID, prediction)
                    except Exception as e:
                        print(f"❌ Telegram send error: {e}")
            else:
                print("⏳ No live matches currently")

        except Exception as e:
            print(f"❌ Auto predictor error: {e}")

        time.sleep(300)  # 5 minutes

# Start auto predictor in background
threading.Thread(target=auto_predictor, daemon=True).start()

# -------------------------
# Webhook endpoint
# -------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        json_data = request.get_json()
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "ERROR", 400

@app.route("/")
def home():
    return "🤖 AI Football Bot - Online"

# -------------------------
# Bot Commands
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🤖 Welcome! Bot is live and auto-scanning matches every 5 minutes.")

@bot.message_handler(commands=['live', 'predict'])
def send_live(message):
    matches = fetch_live_matches()
    if not matches:
        bot.reply_to(message, "⏳ No live matches currently.")
        return
    msg = "🔴 Live Matches:\n\n"
    for m in matches:
        msg += f"{m['home_team']} {m['home_score'] or 0}-{m['away_score'] or 0} {m['away_team']} | League: {m['league']}\n"
    bot.reply_to(message, msg)

# -------------------------
# Setup webhook for Railway
# -------------------------
def setup_webhook():
    bot.remove_webhook()
    time.sleep(1)
    domain = os.environ.get("DOMAIN")  # Railway live URL
    webhook_url = f"{domain}/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set: {webhook_url}")

if __name__ == "__main__":
    setup_webhook()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
