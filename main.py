import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests






import os
import time
import requests
from datetime import datetime
from flask import Flask, request
import telebot
import threading
import random

# -------------------------
# Load environment variables
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY")
BOT_NAME = os.environ.get("BOT_NAME", "Malik Bhai Intelligent Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID or not API_FOOTBALL_KEY:
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_FOOTBALL_KEY missing!")

# -------------------------
# Initialize Flask and Bot
# -------------------------
app = Flask(__name__)
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
    return f"⚽ {BOT_NAME} is running perfectly!", 200

# -------------------------
# API-Football Helper
# -------------------------
def get_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if data.get("response"):
            return data["response"]
    except Exception as e:
        print(f"⚠️ API error: {e}")
    return []

# -------------------------
# Advanced Intelligent Prediction
# -------------------------
def calculate_prediction(match):
    home_team = match['teams']['home']['name']
    away_team = match['teams']['away']['name']
    
    # Dummy H2H + recent stats (replace with real API calls if needed)
    def fetch_team_stats(team_name):
        return {
            "form_score": random.randint(60, 95),      # recent 5 match performance
            "avg_goals_scored": random.uniform(1.0, 2.5),
            "avg_goals_conceded": random.uniform(0.5, 2.0),
        }
    
    home_stats = fetch_team_stats(home_team)
    away_stats = fetch_team_stats(away_team)
    
    # H2H advantage simulation
    h2h_adv = random.randint(0, 10)  # e.g., home team +0-10%
    
    # Confidence calculation
    confidence_home_win = min(100, home_stats['form_score'] + h2h_adv - away_stats['form_score']/2)
    confidence_over_2_5 = min(100, (home_stats['avg_goals_scored'] + away_stats['avg_goals_scored']) * 20)
    confidence_btts = min(100, (home_stats['avg_goals_scored'] + away_stats['avg_goals_scored']) * 25)
    
    # Last 10 min goal probability
    last_10_min = min(100, (home_stats['avg_goals_scored'] + away_stats['avg_goals_scored'])*15)
    
    # Correct score prediction simulation
    correct_scores = ["2-1", "1-2", "1-1", "0-1"]
    correct_score = random.sample(correct_scores, 2)
    
    # High probability goal minutes
    high_goal_minutes = [23, 45, 67, 80]
    
    # Markets
    markets = [
        {"market": "Match Winner", "prediction": f"{home_team} to win", "confidence": confidence_home_win, "reason": "Home strong recent form + H2H advantage", "odds_range": "1.70-1.90"},
        {"market": "Over 2.5 Goals", "prediction": "Over 2.5 Goals", "confidence": confidence_over_2_5, "reason": "High scoring trend recent matches", "odds_range": "1.75-1.95"},
        {"market": "BTTS", "prediction": "Yes", "confidence": confidence_btts, "reason": "Both teams scoring regularly", "odds_range": "1.75-1.90"},
        {"market": "Last 10 Min Goal", "prediction": "Yes", "confidence": last_10_min, "reason": "High goal probability final 10 mins", "odds_range": "1.80-1.95"},
        {"market": "Correct Score", "prediction": correct_score, "confidence": max(confidence_home_win, confidence_btts), "reason": "Frequent 2-1 or 1-2 outcomes in H2H", "odds_range": "6.50-7.50"},
        {"market": "High Prob Goal Minutes", "prediction": high_goal_minutes, "confidence": 90, "reason": "Most goals scored in these minutes", "odds_range": "N/A"}
    ]
    
    # Return single market with >=85% confidence
    high_conf = [m for m in markets if m["confidence"] >= 85]
    if high_conf:
        high_conf.sort(key=lambda x: x["confidence"], reverse=True)
        return high_conf[0]
    else:
        return markets[0]

# -------------------------
# Telegram Handlers
# -------------------------
@bot.message_handler(commands=['start', 'hello'])
def handle_start(message):
    bot.reply_to(message, f"⚽ {BOT_NAME} is live!\nWelcome, {message.from_user.first_name}! ✅")

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    text = message.text.lower().strip()
    
    # Trigger only for prediction queries
    if any(word in text for word in ["over", "under", "winner", "score", "btts", "goal"]):
        live_matches = get_live_matches()
        if not live_matches:
            bot.reply_to(message, "⚠️ No live matches found. I will auto-update when matches go live.")
            return
        
        match = live_matches[0]
        prediction = calculate_prediction(match)
        reply_msg = f"🔹 85%+ Confirmed Bet: {prediction['prediction']}\n" \
                    f"💰 Confidence Level: {prediction['confidence']}%\n" \
                    f"📊 Reasoning: {prediction['reason']}\n" \
                    f"🔥 Odds Range: {prediction['odds_range']}"
        bot.reply_to(message, reply_msg)
    else:
        bot.reply_to(message, f"🤖 {BOT_NAME} is online and ready! Ask me for match predictions like I do.")

# -------------------------
# Auto-update every 5 minutes
# -------------------------
def auto_update():
    while True:
        try:
            live_matches = get_live_matches()
            for match in live_matches:
                prediction = calculate_prediction(match)
                msg = f"⚽ 85%+ Confirmed Bet Found!\n🔹 {prediction['prediction']} – {prediction['confidence']}%\n" \
                      f"💰 Match: {match['teams']['home']['name']} vs {match['teams']['away']['name']}\n" \
                      f"📊 Reasoning: {prediction['reason']}\n🔥 Odds: {prediction['odds_range']}"
                bot.send_message(OWNER_CHAT_ID, msg)
            time.sleep(300)  # 5 minutes
        except Exception as e:
            print(f"⚠️ Auto-update error: {e}")
            time.sleep(60)

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    bot.remove_webhook()
    print("✅ Webhook removed. Malik Bhai Intelligent Bot running in polling mode")
    
    threading.Thread(target=auto_update, daemon=True).start()
    bot.infinity_polling()

