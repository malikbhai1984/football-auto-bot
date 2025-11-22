import os
import requests
import telebot
import pandas as pd
import numpy as np
import time
from datetime import datetime
from dotenv import load_dotenv

# --------------------------
# Load Environment Variables
# --------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API_KEY = os.getenv("API_KEY")
SPORTMONKS_API = os.getenv("SPORTMONKS_API")
PREVIOUS_DATA_URL = "https://raw.githubusercontent.com/<your_username>/<repo>/main/matches.csv"

bot = telebot.TeleBot(BOT_TOKEN)

# --------------------------
# Fetch Previous Matches Data
# --------------------------
def load_previous_data():
    try:
        df = pd.read_csv(PREVIOUS_DATA_URL)
        print("✅ Previous data loaded successfully")
        return df
    except Exception as e:
        print(f"⚠️ Failed to load previous match data: {e}")
        return pd.DataFrame()  # empty fallback

previous_matches = load_previous_data()

# --------------------------
# Fetch Live Matches
# --------------------------
def get_live_matches():
    url = f"https://soccer.sportmonks.com/api/v2.0/livescores?api_token={SPORTMONKS_API}"
    try:
        response = requests.get(url)
        data = response.json()
        return data.get("data", [])
    except:
        return []

# --------------------------
# Prediction Logic
# --------------------------
def predict_match(match):
    home = match.get("home_team", {}).get("name")
    away = match.get("away_team", {}).get("name")
    
    # Basic stats fallback
    home_goals_avg = 1.2
    away_goals_avg = 1.1
    over_prob = min(0.95, max(0.05, (home_goals_avg + away_goals_avg)/5))
    
    # BTTS probability (using corners/h2h if available)
    btts_prob = 0.7  # fallback
    last_10_min_goal_prob = 0.15
    
    # Correct score predictions (simplified)
    top_scores = [(1,1), (1,0)]
    
    return {
        "home": home,
        "away": away,
        "over_prob": round(over_prob*100,1),
        "btts_prob": round(btts_prob*100,1),
        "last_10_min_goal_prob": round(last_10_min_goal_prob*100,1),
        "top_scores": top_scores
    }

# --------------------------
# Send Predictions to Telegram
# --------------------------
def send_predictions():
    matches = get_live_matches()
    if not matches:
        print("⚠️ No live matches found")
        return

    for match in matches:
        prediction = predict_match(match)
        msg = (
            f"⚽ Match: {prediction['home']} vs {prediction['away']}\n"
            f"Over 0.5-5.5 Goal Probability: {prediction['over_prob']}%\n"
            f"BTTS Probability: {prediction['btts_prob']}%\n"
            f"Last 10-min Goal Probability: {prediction['last_10_min_goal_prob']}%\n"
            f"Top Correct Scores: {prediction['top_scores']}\n"
        )
        bot.send_message(OWNER_CHAT_ID, msg)
        time.sleep(1)

# --------------------------
# Main Loop: Update Every 7-8 Minutes
# --------------------------
while True:
    try:
        print(f"🔄 Running cycle at {datetime.now()}")
        send_predictions()
        print("✅ Cycle complete. Waiting 7 minutes...")
        time.sleep(7*60)  # 7 minutes
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(60)
