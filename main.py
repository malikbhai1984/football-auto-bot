import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
import telebot
import numpy as np
from sklearn.linear_model import LogisticRegression  # ML example

# ---------------------------
# Load Environment Variables
# ---------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID"))
SPORTMONKS_API = os.getenv("SPORTMONKS_API")
APIFOOTBALL_API = os.getenv("API_KEY")
DOMAIN = os.getenv("DOMAIN")

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------------------
# Top 8 leagues + WC Qualifiers IDs (example IDs, replace with real)
# ---------------------------
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 61, 2, 3]  # Premier, La Liga, Serie A etc
WC_QUALIFIERS_ID = [999]  # Replace with real competition ID

ALL_LEAGUES = TOP_LEAGUES_IDS + WC_QUALIFIERS_ID

# ---------------------------
# ML Model Stub
# ---------------------------
# Example: LogisticRegression model to predict goal chance (replace with real data & training)
ml_model = LogisticRegression()
# Dummy training data (features: last_goals, shots_on_target, possession, etc.)
X_train = np.array([[0,1,50],[1,3,60],[0,0,40],[1,2,55]])
y_train = np.array([0,1,0,1])  # 0 = no goal, 1 = goal
ml_model.fit(X_train, y_train)

# ---------------------------
# Fetch Matches
# ---------------------------
def fetch_matches():
    matches = []
    for league_id in ALL_LEAGUES:
        url = f"https://soccer.sportmonks.com/api/v2.0/fixtures/league/{league_id}?api_token={SPORTMONKS_API}&include=localTeam,visitorTeam"
        try:
            res = requests.get(url)
            data = res.json()
            for m in data.get('data', []):
                match = {
                    "home": m["localTeam"]["data"]["name"],
                    "away": m["visitorTeam"]["data"]["name"],
                    "league": m.get("league", {}).get("data", {}).get("name", "Unknown League"),
                    "last_10_stats": [0,1,50]  # Example feature vector
                }
                matches.append(match)
        except Exception as e:
            print(f"Error fetching league {league_id}: {e}")
    return matches

# ---------------------------
# Check Goal Alerts
# ---------------------------
def check_goal_alerts():
    matches = fetch_matches()
    for m in matches:
        # Predict goal probability with ML model
        goal_prob = ml_model.predict_proba([m["last_10_stats"]])[0][1] * 100
        if goal_prob >= 80:
            message = f"🔥 GOAL ALERT 🔥\n{m['home']} vs {m['away']}\nLeague: {m['league']}\nChance: {goal_prob:.1f}%"
            bot.send_message(OWNER_CHAT_ID, message)
            print(message)

# ---------------------------
# Main Loop
# ---------------------------
if __name__ == "__main__":
    print("Bot started... ✅")
    while True:
        try:
            check_goal_alerts()
        except Exception as e:
            print(f"Error in main loop: {e}")
        time.sleep(60)  # Har minute check kare
