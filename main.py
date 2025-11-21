import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
import telebot
import numpy as np
from sklearn.linear_model import LogisticRegression
from datetime import datetime, timedelta

# ---------------------------
# Load Environment Variables
# ---------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID"))
SPORTMONKS_API = os.getenv("SPORTMONKS_API")
DOMAIN = os.getenv("DOMAIN")

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------------------
# Top 8 leagues + WC Qualifiers IDs
# Replace these IDs with actual Sportmonks league IDs
# ---------------------------
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 61, 2, 3]  # Example: Premier, La Liga, Serie A etc
WC_QUALIFIERS_ID = [999]  # Example World Cup Qualifier league ID
ALL_LEAGUES = TOP_LEAGUES_IDS + WC_QUALIFIERS_ID

# ---------------------------
# ML/AI Model Stub
# ---------------------------
# Logistic Regression example model
ml_model = LogisticRegression()
X_train = np.array([[0,1,50],[1,3,60],[0,0,40],[1,2,55]])  # Example features
y_train = np.array([0,1,0,1])
ml_model.fit(X_train, y_train)

# ---------------------------
# Fetch live matches
# ---------------------------
def fetch_live_matches():
    matches = []
    for league_id in ALL_LEAGUES:
        url = f"https://soccer.sportmonks.com/api/v2.0/fixtures/league/{league_id}?api_token={SPORTMONKS_API}&include=localTeam,visitorTeam&statuses=1,2,3"  # live/status=1,2,3
        try:
            res = requests.get(url)
            data = res.json()
            for m in data.get('data', []):
                match = {
                    "home": m["localTeam"]["data"]["name"],
                    "away": m["visitorTeam"]["data"]["name"],
                    "league": m.get("league", {}).get("data", {}).get("name", "Unknown League"),
                    "last_10_stats": [0,1,50]  # Replace with real last-10-min features
                }
                matches.append(match)
        except Exception as e:
            print(f"[{datetime.now()}] Error fetching league {league_id}: {e}")
    return matches

# ---------------------------
# Goal Alert Checker
# ---------------------------
def check_goal_alerts():
    matches = fetch_live_matches()
    for m in matches:
        try:
            goal_prob = ml_model.predict_proba([m["last_10_stats"]])[0][1] * 100
            if goal_prob >= 80:
                message = f"🔥 GOAL ALERT 🔥\n{m['home']} vs {m['away']}\nLeague: {m['league']}\nChance: {goal_prob:.1f}%"
                bot.send_message(OWNER_CHAT_ID, message)
                print(f"[{datetime.now()}] {message}")
        except Exception as e:
            print(f"[{datetime.now()}] Error in alert calculation: {e}")

# ---------------------------
# Main Loop
# ---------------------------
if __name__ == "__main__":
    print(f"[{datetime.now()}] Bot started... ✅")
    while True:
        try:
            check_goal_alerts()
        except Exception as e:
            print(f"[{datetime.now()}] Error in main loop: {e}")
        time.sleep(60)  # Har minute check kare
