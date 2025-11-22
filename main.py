import os
import requests
import telebot
import time
from datetime import datetime
import pandas as pd
import numpy as np

# -------------------------
# Load environment variables
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
SPORTMONKS_API = os.environ.get("SPORTMONKS_API")
BOT_NAME = os.environ.get("BOT_NAME", "MyBetAlert_Bot")
PREVIOUS_DATA_URL = "https://raw.githubusercontent.com/<your_username>/<repo>/main/matches.csv"

# Initialize Telegram bot
bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------
# Fetch previous matches data
# -------------------------
def load_previous_data():
    try:
        df = pd.read_csv(PREVIOUS_DATA_URL)
        return df
    except Exception as e:
        print(f"❌ Failed to load previous match data: {e}")
        return pd.DataFrame()

previous_data = load_previous_data()

# -------------------------
# Fetch live matches from Sportmonks
# -------------------------
def fetch_live_matches():
    url = f"https://soccer.sportmonks.com/api/v2.0/livescores?api_token={SPORTMONKS_API}"
    try:
        response = requests.get(url)
        data = response.json().get("data", [])
        return data
    except Exception as e:
        print(f"❌ Error fetching live matches: {e}")
        return []

# -------------------------
# Prediction logic
# -------------------------
def predict_match(match):
    # Extract correct structure from Sportmonks
    home = match.get("localTeam", {}).get("data", {}).get("name", "Unknown")
    away = match.get("visitorTeam", {}).get("data", {}).get("name", "Unknown")
    league = match.get("league", {}).get("data", {}).get("name", "Unknown League")
    match_time = match.get("time", "Unknown Time")

    # Example prediction logic (improve using previous_data, H2H, corners)
    home_goals_avg = 1.2
    away_goals_avg = 1.1
    over_prob = min(0.95, max(0.05, (home_goals_avg + away_goals_avg)/5))
    btts_prob = 0.7
    last_10_min_goal_prob = 0.15
    top_scores = [(1,1), (1,0)]

    return {
        "home": home,
        "away": away,
        "league": league,
        "match_time": match_time,
        "over_prob": round(over_prob*100,1),
        "btts_prob": round(btts_prob*100,1),
        "last_10_min_goal_prob": round(last_10_min_goal_prob*100,1),
        "top_scores": top_scores
    }

# -------------------------
# Send predictions to Telegram
# -------------------------
def send_predictions():
    matches = fetch_live_matches()
    if not matches:
        bot.send_message(OWNER_CHAT_ID, "No live matches currently.")
        return

    for match in matches:
        prediction = predict_match(match)
        msg = (
            f"⚽ League: {prediction['league']}\n"
            f"Match: {prediction['home']} vs {prediction['away']}\n"
            f"Time: {prediction['match_time']}\n"
            f"Over 0.5-5.5 Goal Probability: {prediction['over_prob']}%\n"
            f"BTTS Probability: {prediction['btts_prob']}%\n"
            f"Last 10-min Goal Probability: {prediction['last_10_min_goal_prob']}%\n"
            f"Top Correct Scores: {prediction['top_scores']}\n"
        )
        bot.send_message(OWNER_CHAT_ID, msg)

# -------------------------
# Auto-update every 7 minutes
# -------------------------
def start_bot_loop():
    while True:
        try:
            send_predictions()
            print(f"✅ Cycle complete. Waiting 7 minutes... {datetime.now()}")
            time.sleep(7*60)
        except Exception as e:
            print(f"❌ Error in bot loop: {e}")
            time.sleep(60)

# -------------------------
# Start bot
# -------------------------
if __name__ == "__main__":
    start_bot_loop()    
