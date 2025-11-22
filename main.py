import os
import requests
import time
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, request

# -------------------
# Environment Variables
# -------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
SPORTMONKS_API = os.environ.get("SPORTMONKS_API")
BOT_NAME = os.environ.get("BOT_NAME", "MyBetAlert_Bot")
PORT = int(os.environ.get("PORT", 8080))

# -------------------
# Logging Setup
# -------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# -------------------
# Telegram Function
# -------------------
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": OWNER_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        logger.error(f"Telegram message failed: {e}")

# -------------------
# Utilities
# -------------------
def format_pakistan_time():
    return (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")

# -------------------
# Fetch Previous Data for Predictions
# -------------------
PREVIOUS_DATA_URL = "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/matches.csv"

def load_previous_data():
    try:
        df = pd.read_csv(PREVIOUS_DATA_URL)
        logger.info(f"Previous match data loaded: {df.shape[0]} rows")
        return df
    except Exception as e:
        logger.error(f"Failed to load previous match data: {e}")
        return pd.DataFrame()

previous_df = load_previous_data()

# -------------------
# Fetch Live Matches
# -------------------
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 94, 49, 88]  # EPL, La Liga, Serie A, Bundesliga, Ligue1, etc.

def fetch_sportmonks_live():
    url = f"https://soccer.sportmonks.com/api/v2.0/livescores?api_token={SPORTMONKS_API}"
    try:
        r = requests.get(url, timeout=10).json()
        matches = []
        for m in r.get("data", []):
            if m.get("league_id") in TOP_LEAGUES_IDS or m.get("competition_id") == 2:  # World Cup qualifiers id=2
                matches.append({
                    "home": m.get("localTeam", {}).get("data", {}).get("name", ""),
                    "away": m.get("visitorTeam", {}).get("data", {}).get("name", ""),
                    "league": m.get("league", {}).get("data", {}).get("name", ""),
                    "score": f"{m.get('scores', {}).get('localteam_score', 0)}-{m.get('scores', {}).get('visitorteam_score', 0)}",
                    "minute": m.get("time", {}).get("minute", 0),
                    "corners": np.random.randint(0, 10)  # placeholder, replace with real API if needed
                })
        logger.info(f"Fetched {len(matches)} live matches from SportMonks")
        return matches
    except Exception as e:
        logger.error(f"Error fetching SportMonks live: {e}")
        return []

# -------------------
# Simple AI/ML Prediction Logic
# -------------------
def predict_over_goals(match):
    """
    Use previous match data to predict goals 0.5–5.5
    This is a simple statistical approach using rolling averages.
    """
    home = match["home"]
    away = match["away"]

    home_df = previous_df[previous_df["home_team"] == home]
    away_df = previous_df[previous_df["away_team"] == away]

    if home_df.empty or away_df.empty:
        return "Over 1.5", 0.6  # fallback prediction

    avg_goals = (home_df["home_score"].mean() + away_df["away_score"].mean()) / 2
    prob = min(max(avg_goals / 3, 0.5), 0.95)  # normalize to 0.5–0.95 confidence

    # Map to Over 0.5–5.5
    if avg_goals < 1:
        prediction = "Over 0.5"
    elif avg_goals < 2:
        prediction = "Over 1.5"
    elif avg_goals < 3:
        prediction = "Over 2.5"
    elif avg_goals < 4:
        prediction = "Over 3.5"
    else:
        prediction = "Over 4.5"

    return prediction, prob

# -------------------
# Main Bot Loop
# -------------------
def run_bot_cycle():
    while True:
        live_matches = fetch_sportmonks_live()
        if not live_matches:
            logger.info("No live matches found. Retrying in 7 minutes...")
            time.sleep(420)
            continue

        for match in live_matches:
            pred, confidence = predict_over_goals(match)
            msg = (
                f"⚽ Live Match Update:\n"
                f"🏠 {match['home']} vs 🛫 {match['away']}\n"
                f"League: {match['league']}\n"
                f"Score: {match['score']} | Minute: {match['minute']}\n"
                f"Predicted: *{pred}* (Confidence: {confidence*100:.1f}%)\n"
                f"Corners: {match['corners']}"
            )
            logger.info(f"Sending Telegram for {match['home']} vs {match['away']}")
            send_telegram_message(msg)

        logger.info("✅ Cycle complete. Waiting 7 minutes...")
        time.sleep(420)  # 7 minutes

# -------------------
# Flask App for Railway
# -------------------
app = Flask(__name__)

@app.route("/")
def index():
    return "Football Auto Prediction Bot is running 🚀"

# -------------------
# Start Bot Thread
# -------------------
def start_bot_thread():
    bot_thread = Thread(target=run_bot_cycle, daemon=True)
    bot_thread.start()
    return True

if __name__ == "__main__":
    logger.info("🚀 Starting Football Auto Prediction Bot...")
    start_bot_thread()
    send_telegram_message("🤖 ULTRA BOT STARTED: Telegram messages working ✅")
    app.run(host="0.0.0.0", port=PORT)
