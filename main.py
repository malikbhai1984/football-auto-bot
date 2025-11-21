import os
import time
import requests
import telebot
import pandas as pd
from dotenv import load_dotenv
import numpy as np

load_dotenv()

# Telegram & API keys
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID"))
SPORTMONKS_API = os.getenv("SPORTMONKS_API")
PORT = int(os.getenv("PORT", 8080))

bot = telebot.TeleBot(BOT_TOKEN)

# Historical data CSV (self-learning)
# Columns: league, home_team, away_team, minute, home_score, away_score, goal_last_10
HISTORICAL_CSV = "historical_matches.csv"
if not os.path.exists(HISTORICAL_CSV):
    pd.DataFrame(columns=[
        "league", "home_team", "away_team", "minute",
        "home_score", "away_score", "goal_last_10"
    ]).to_csv(HISTORICAL_CSV, index=False)

df_history = pd.read_csv(HISTORICAL_CSV)

# Top leagues + qualifiers IDs
TOP_LEAGUES = [39, 140, 135, 78, 61, 88, 94, 293, 73, 74]  # e.g., Premier League, La Liga...
QUALIFIERS_IDS = [1001, 1002, 1003]  # Add actual qualifier league IDs

def fetch_live_matches():
    url = f"https://soccer.sportmonks.com/api/v2.0/fixtures/live?api_token={SPORTMONKS_API}&include=localTeam,visitorTeam,league"
    res = requests.get(url).json()
    matches = res.get("data", [])
    filtered = []
    for m in matches:
        league_id = m.get("league", {}).get("data", {}).get("id")
        if league_id in TOP_LEAGUES + QUALIFIERS_IDS:
            filtered.append({
                "match_id": m["id"],
                "home": m.get("localTeam", {}).get("data", {}).get("name", "Home"),
                "away": m.get("visitorTeam", {}).get("data", {}).get("name", "Away"),
                "league": m.get("league", {}).get("data", {}).get("name", "League"),
                "minute": m.get("time", {}).get("minute", 0),
                "home_score": m.get('scores', {}).get('localteam_score', 0),
                "away_score": m.get('scores', {}).get('visitorteam_score', 0)
            })
    return filtered

def predict_goal_chance(match):
    """
    ML/AI-based predictive model:
    - Historical last 10-min goals frequency
    - Adjusts probability based on current score & match minute
    """
    global df_history
    df_filtered = df_history[
        (df_history['league'] == match['league']) &
        ((df_history['home_team'] == match['home']) | (df_history['away_team'] == match['away']))
    ]
    if df_filtered.empty:
        return 60  # conservative default
    goal_rate = df_filtered['goal_last_10'].mean()
    # Adjust for current match score
    goal_rate += 0.5 * (match['home_score'] - match['away_score'])
    goal_rate += 0.2 if match['minute'] >= 80 else 0
    prob = min(max(int(goal_rate * 100), 0), 100)
    return prob

def send_alert(match, prob):
    if prob >= 80:
        message = (
            f"🔥 GOAL ALERT 🔥\n"
            f"League: {match['league']}\n"
            f"Match: {match['home']} vs {match['away']}\n"
            f"Score: {match['home_score']} - {match['away_score']}\n"
            f"Minute: {match['minute']}'\n"
            f"Predicted Goal Chance: {prob}%"
        )
        bot.send_message(OWNER_CHAT_ID, message)

def main_loop():
    print("✅ ML/AI Football Predictive Bot Started")
    while True:
        try:
            live_matches = fetch_live_matches()
            for match in live_matches:
                prob = predict_goal_chance(match)
                send_alert(match, prob)
        except Exception as e:
            print("Error:", e)
        time.sleep(60)  # fetch every 60 sec

if __name__ == "__main__":
    main_loop()
