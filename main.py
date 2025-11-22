import os
import time
import threading
import requests
import pandas as pd
import numpy as np
from flask import Flask
from datetime import datetime
import telebot

# ----------------------------
# Environment Variables
# ----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")  # API-Football
SPORTMONKS_API = os.environ.get("SPORTMONKS_API")
BOT_NAME = os.environ.get("BOT_NAME", "MyBetAlert_Bot")

# URLs for live matches / previous data
PREVIOUS_DATA_URL = "https://raw.githubusercontent.com/<your_username>/<repo>/main/matches.csv"

# Telegram Bot
bot = telebot.TeleBot(BOT_TOKEN)

# Flask app
app = Flask(__name__)

# ----------------------------
# Prediction Logic
# ----------------------------
def fetch_previous_data():
    try:
        df = pd.read_csv(PREVIOUS_DATA_URL)
        return df
    except Exception as e:
        print(f"❌ Failed to load previous match data: {e}")
        return pd.DataFrame()

def fetch_live_matches():
    """Fetch live matches from API-Football first, SportMonks fallback"""
    try:
        # API-Football
        headers = {"x-apisports-key": API_KEY}
        resp = requests.get("https://v3.football.api-sports.io/fixtures?live=all", headers=headers, timeout=10)
        data = resp.json()
        matches = data.get("response", [])
        if matches:
            return matches
        else:
            # Fallback SportMonks
            resp = requests.get(f"https://soccer.sportmonks.com/api/v2.0/livescores?api_token={SPORTMONKS_API}", timeout=10)
            data = resp.json()
            matches = data.get("data", [])
            return matches
    except Exception as e:
        print(f"❌ Failed to fetch live matches: {e}")
        return []

def compute_predictions(match, previous_df):
    """Basic prediction logic using Pandas/Numpy"""
    # Example: simple probabilistic model
    over_prob = np.random.uniform(0.4, 0.7) * 100
    btts_prob = np.random.uniform(0.5, 0.8) * 100
    last10_prob = np.random.uniform(0.1, 0.3) * 100
    top_scores = [(1,1),(1,0)]
    return over_prob, btts_prob, last10_prob, top_scores

def format_message(match, over_prob, btts_prob, last10_prob, top_scores):
    team_home = match.get("teams", {}).get("home", {}).get("name") or match.get("match_hometeam_name") or "None"
    team_away = match.get("teams", {}).get("away", {}).get("name") or match.get("match_awayteam_name") or "None"
    league = match.get("league", {}).get("name") or match.get("league_name") or "Unknown League"
    minute = match.get("fixture", {}).get("status", {}).get("elapsed") or match.get("match_minute") or "0"

    msg = (
        f"⚽ League: {league}\n"
        f"Match: {team_home} vs {team_away}\n"
        f"Minute: {minute}'\n"
        f"Over 0.5-5.5 Goal Probability: {over_prob:.1f}%\n"
        f"BTTS Probability: {btts_prob:.1f}%\n"
        f"Last 10-min Goal Probability: {last10_prob:.1f}%\n"
        f"Top Correct Scores: {top_scores}\n"
        "--------------------------------"
    )
    return msg

def send_telegram_message(msg):
    try:
        bot.send_message(OWNER_CHAT_ID, msg)
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

# ----------------------------
# Background Thread for 7-min updates
# ----------------------------
def update_loop():
    previous_df = fetch_previous_data()
    while True:
        live_matches = fetch_live_matches()
        if not live_matches:
            print("⚠️ No live matches right now.")
        for match in live_matches:
            over_prob, btts_prob, last10_prob, top_scores = compute_predictions(match, previous_df)
            msg = format_message(match, over_prob, btts_prob, last10_prob, top_scores)
            send_telegram_message(msg)
        print("✅ Cycle complete. Waiting 7 minutes...")
        time.sleep(7*60)

threading.Thread(target=update_loop, daemon=True).start()

# ----------------------------
# Flask Routes
# ----------------------------
@app.route("/")
def index():
    return "MyBetAlert_Bot Running ✅"

# ----------------------------
# Run Flask
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
