import os
import requests
import pandas as pd
import numpy as np
import telebot
from datetime import datetime
import time
from flask import Flask
from threading import Thread

# --------------------
# Environment Variables
# --------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")            # API-Football
SPORTMONKS_API = os.environ.get("SPORTMONKS_API")
PORT = int(os.environ.get("PORT", 8080))
BOT_NAME = os.environ.get("BOT_NAME", "MyBetAlert_Bot")

# --------------------
# Initialize Telegram Bot
# --------------------
bot = telebot.TeleBot(BOT_TOKEN)

# --------------------
# URLs and Config
# --------------------
PREVIOUS_DATA_URL = "https://raw.githubusercontent.com/<your_username>/<repo>/main/matches.csv"

TOP_LEAGUES_IDS = [
    39, 140, 78, 61, 135, 64, 71, 2  # EPL, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira, Russian League
]

UPDATE_INTERVAL = 420  # 7 minutes

# --------------------
# Helper Functions
# --------------------
def fetch_previous_matches():
    try:
        df = pd.read_csv(PREVIOUS_DATA_URL)
        return df
    except Exception as e:
        print(f"❌ Failed to load previous match data: {e}")
        return pd.DataFrame()

def fetch_live_matches():
    """
    First try API-Football. If fails, fallback to SportMonks.
    """
    # --------- API-Football ----------
    try:
        headers = {"x-rapidapi-key": API_KEY}
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures?live=all"
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json().get('response', [])
        live_matches = []
        for match in data:
            league_id = match['league']['id']
            if league_id in TOP_LEAGUES_IDS or match['league']['type'] == 'WCQ':
                live_matches.append({
                    'home_team': match['teams']['home'],
                    'away_team': match['teams']['away'],
                    'league': match['league'],
                    'time': {'minute': match['fixture']['status']['elapsed'] or 0}
                })
        if live_matches:
            return live_matches
    except Exception as e:
        print(f"⚠️ API-Football failed: {e}")

    # --------- SportMonks Fallback ----------
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}"
        r = requests.get(url, timeout=10)
        data = r.json()
        live_matches = []
        for match in data.get('data', []):
            league_id = match.get('league_id')
            if league_id in TOP_LEAGUES_IDS or match.get('competition', {}).get('type') == 'WCQ':
                live_matches.append(match)
        return live_matches
    except Exception as e:
        print(f"⚠️ SportMonks failed: {e}")
        return []

def calculate_predictions(match):
    """
    Dummy prediction logic for now.
    Replace with advanced AI/ML logic using H2H, corners, previous stats.
    """
    over_prob = np.random.uniform(40, 70)
    btts_prob = np.random.uniform(50, 85)
    last10_prob = np.random.uniform(10, 30)
    top_scores = [(1, 1), (1, 0)]
    return over_prob, btts_prob, last10_prob, top_scores

def format_message(match, over_prob, btts_prob, last10_prob, top_scores):
    home = match.get('home_team', {}).get('name', "None")
    away = match.get('away_team', {}).get('name', "None")
    league = match.get('league', {}).get('name', "Unknown League")
    minute = match.get('time', {}).get('minute', 0)
    return (f"⚽ League: {league}\n"
            f"Match: {home} vs {away} ({minute}')\n"
            f"Over 0.5-5.5 Goal Probability: {over_prob:.1f}%\n"
            f"BTTS Probability: {btts_prob:.1f}%\n"
            f"Last 10-min Goal Probability: {last10_prob:.1f}%\n"
            f"Top Correct Scores: {top_scores}\n")

def send_predictions():
    live_matches = fetch_live_matches()
    if not live_matches:
        print("⚠️ No live matches right now.")
        return

    for match in live_matches:
        over_prob, btts_prob, last10_prob, top_scores = calculate_predictions(match)
        message = format_message(match, over_prob, btts_prob, last10_prob, top_scores)
        try:
            bot.send_message(OWNER_CHAT_ID, message)
        except Exception as e:
            print(f"❌ Failed to send message: {e}")

# --------------------
# Background Thread
# --------------------
def start_bot_loop():
    while True:
        try:
            send_predictions()
        except Exception as e:
            print(f"❌ Error in prediction loop: {e}")
        print(f"✅ Cycle complete. Waiting {UPDATE_INTERVAL // 60} minutes...")
        time.sleep(UPDATE_INTERVAL)

# --------------------
# Flask App for Railway
# --------------------
app = Flask(__name__)

@app.route("/")
def home():
    return f"{BOT_NAME} is running 🚀"

# --------------------
# Run Bot in Thread
# --------------------
thread = Thread(target=start_bot_loop)
thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
