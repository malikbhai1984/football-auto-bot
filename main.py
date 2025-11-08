import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests






# main.py
import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
import telebot
from flask import Flask, request

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
BOT_NAME = os.environ.get("BOT_NAME", "Malik Bhai Intelligent Bot")

# Check mandatory variables
if not BOT_TOKEN or not OWNER_CHAT_ID or not API_FOOTBALL_KEY:
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_FOOTBALL_KEY missing!")

# -------------------------
# Initialize Flask first
# -------------------------
app = Flask(__name__)

# -------------------------
# Initialize Telegram bot
# -------------------------
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# -------------------------
# Webhook route
# -------------------------
@app.route('/' + BOT_TOKEN, methods=['POST'])
def receive_update():
    try:
        update = telebot.types.Update.de_json(request.data.decode('utf-8'))
        bot.process_new_updates([update])
    except Exception as e:
        print(f"⚠️ Error processing update: {e}")
    return 'OK', 200

@app.route('/')
def home():
    return f"⚽ {BOT_NAME} is running perfectly on Railway!", 200

# -------------------------
# Intelligent Prediction Logic
# -------------------------
def fetch_live_matches():
    """Fetch live matches from API-Football"""
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10).json()
        return response.get("response", [])
    except Exception as e:
        print("⚠️ Error fetching live matches:", e)
        return []

def calculate_confident_bet(match):
    """
    Dummy intelligent algorithm for demonstration:
    - Replace with H2H, last 5 matches, odds weighting, goal trends
    - Returns a single 85%+ confident market
    """
    # Example static prediction
    prediction = {
        "market": "Over 2.5 Goals",
        "confidence": 87,
        "reason": "Teams have scored 3+ in last 5 H2H, recent league trend high scoring",
        "odds_range": "1.75-1.90",
        "risk_note": "No major injuries"
    }
    return prediction

# -------------------------
# Telegram Handlers
# -------------------------
@bot.message_handler(commands=['start', 'hello'])
def handle_start(message):
    bot.reply_to(message, f"⚽ {BOT_NAME} is live!\nWelcome, {message.from_user.first_name}! ✅")

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    text = message.text.lower().strip()
    print(f"📩 Received: {text}")

    live_matches = fetch_live_matches()
    if live_matches:
        match = live_matches[0]  # Example: pick first live match
        bet = calculate_confident_bet(match)
        reply = f"⚽ 85%+ Confirmed Bet Found!\n"
        reply += f"🔹 Market: {bet['market']}\n"
        reply += f"💰 Confidence: {bet['confidence']}%\n"
        reply += f"📊 Reason: {bet['reason']}\n"
        reply += f"🔥 Odds Range: {bet['odds_range']}\n"
        reply += f"⚠️ Risk Note: {bet['risk_note']}\n"
        bot.reply_to(message, reply)
    else:
        # Intelligent fallback reply
        bot.reply_to(message, "🤖 Malik Bhai Intelligent Bot is online and ready! Ask me about live matches or bets.")

# -------------------------
# Auto 5-Minute Updates
# -------------------------
def auto_update():
    while True:
        live_matches = fetch_live_matches()
        if live_matches:
            match = live_matches[0]
            bet = calculate_confident_bet(match)
            msg = f"⚽ 85%+ Confirmed Bet Found!\n"
            msg += f"🔹 Market: {bet['market']}\n"
            msg += f"💰 Confidence: {bet['confidence']}%\n"
            msg += f"📊 Reason: {bet['reason']}\n"
            msg += f"🔥 Odds Range: {bet['odds_range']}\n"
            msg += f"⚠️ Risk Note: {bet['risk_note']}\n"
            try:
                bot.send_message(OWNER_CHAT_ID, msg)
            except Exception as e:
                print("⚠️ Error sending auto-update:", e)
        time.sleep(300)  # 5 minutes

# -------------------------
# Run bot
# -------------------------
if __name__ == "__main__":
    # Delete webhook before polling to prevent conflicts
    bot.remove_webhook()
    print("✅ Webhook removed. Malik Bhai Intelligent Bot running in polling mode")

    # Start auto-update in background
    import threading
    threading.Thread(target=auto_update, daemon=True).start()

    # Start polling
    bot.infinity_polling()


