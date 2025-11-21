import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Bot
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import time

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("SPORTMONKS_API")
APIFOOTBALL_API = os.getenv("API_KEY")  # API-Football
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 8080))

if not all([BOT_TOKEN, OWNER_CHAT_ID, SPORTMONKS_API, APIFOOTBALL_API, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, SPORTMONKS_API, APIFOOTBALL_API, or DOMAIN missing!")

bot = Bot(token=BOT_TOKEN)

# -------------------------
# Load ML model
# -------------------------
MODEL_FILE = "goal_predictor.pkl"

if os.path.exists(MODEL_FILE):
    model = joblib.load(MODEL_FILE)
    scaler = joblib.load("scaler.pkl")
else:
    # Dummy model if not exists (replace with real training)
    model = RandomForestClassifier()
    scaler = StandardScaler()

# -------------------------
# Top leagues + qualifiers IDs
# -------------------------
TOP_LEAGUES = [39, 140, 78, 61, 71, 135, 109, 102]  # Example: EPL, La Liga, Serie A...
QUALIFIERS = [999, 1000, 1001]  # Example IDs, replace with actual qualifiers

# -------------------------
# Helper Functions
# -------------------------
def fetch_live_matches():
    """Fetch live matches from SportMonks API filtered by leagues"""
    url = f"https://soccer.sportmonks.com/api/v2.0/livescores?api_token={SPORTMONKS_API}"
    response = requests.get(url)
    data = response.json()
    live_matches = []

    for match in data.get("data", []):
        league_id = match["league_id"]
        if league_id in TOP_LEAGUES + QUALIFIERS:
            live_matches.append({
                "match_id": match["id"],
                "league": match["league"]["name"],
                "home_team": match["localTeam"]["name"],
                "away_team": match["visitorTeam"]["name"],
                "score": f"{match['scores']['localteam_score']} - {match['scores']['visitorteam_score']}",
                "minute": match["time"]["minute"]
            })
    return live_matches

def predict_goal(match_features):
    """Predict goal probability using ML model"""
    features_scaled = scaler.transform([match_features])
    prob = model.predict_proba(features_scaled)[0][1] * 100
    return prob

def send_telegram_alert(match, probability):
    """Send Telegram message"""
    message = (
        f"🔥 GOAL ALERT 🔥\n"
        f"League: {match['league']}\n"
        f"{match['home_team']} vs {match['away_team']}\n"
        f"Score: {match['score']} | Minute: {match['minute']}\n"
        f"Probability next 10 min: {probability:.1f}%"
    )
    bot.send_message(chat_id=OWNER_CHAT_ID, text=message)

# -------------------------
# Main Loop
# -------------------------
def main():
    print("✅ Live match alert bot started!")
    while True:
        try:
            live_matches = fetch_live_matches()
            for match in live_matches:
                # Example: match features for ML model (replace with actual live stats)
                match_features = [
                    np.random.randint(0,3),  # home_score
                    np.random.randint(0,3),  # away_score
                    np.random.rand(),        # home_xG
                    np.random.rand(),        # away_xG
                    np.random.rand(),        # shots_diff
                    np.random.rand(),        # possession_diff
                    np.random.rand(),        # h2h_avg_goals
                    match["minute"]
                ]

                prob = predict_goal(match_features)
                if prob >= 80:
                    send_telegram_alert(match, prob)
        except Exception as e:
            print("Error:", e)
        time.sleep(60)  # 1 minute delay

if __name__ == "__main__":
    main()
