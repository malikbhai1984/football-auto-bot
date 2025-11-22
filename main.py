import os
import requests
import time
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
import telebot

# -----------------------
# Load environment
# -----------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_FOOTBALL_KEY = os.environ.get("API_KEY")         # API-Football
SPORTMONKS_KEY = os.environ.get("SPORTMONKS_API")    # SportMonks fallback
BOT_NAME = os.environ.get("BOT_NAME", "MyBetAlert_Bot")

bot = telebot.TeleBot(BOT_TOKEN)

# -----------------------
# Prediction placeholders
# Replace with your Pandas/Numpy logic
# -----------------------
def predict_match(match_data):
    """
    Input: match_data dict with H2H, corners, score, minute
    Output: dict with predictions
    """
    # Dummy logic, replace with your real model
    return {
        "over_prob": round(np.random.uniform(40, 90), 1),
        "btts_prob": round(np.random.uniform(50, 90), 1),
        "last10_prob": round(np.random.uniform(5, 25), 1),
        "top_scores": [(1,1), (2,1)]
    }

# -----------------------
# Fetch live matches from API-Football
# -----------------------
def fetch_live_matches_apifootball():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        matches = []
        for f in data['response']:
            fixture = f['fixture']
            league = f['league']
            teams = f['teams']
            goals = f['goals']
            minute = fixture['status']['elapsed']
            matches.append({
                "league": league['name'],
                "home": teams['home']['name'],
                "away": teams['away']['name'],
                "minute": minute,
                "home_goals": goals['home'],
                "away_goals": goals['away'],
                "h2h": {},       # Add H2H/corners if available
            })
        return matches
    except Exception as e:
        print("API-Football fetch failed:", e)
        return []

# -----------------------
# Fetch live matches from SportMonks (fallback)
# -----------------------
def fetch_live_matches_sportmonks():
    url = f"https://soccer.sportmonks.com/api/v2.0/livescores?api_token={SPORTMONKS_KEY}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        matches = []
        for f in data.get('data', []):
            matches.append({
                "league": f['league']['data']['name'] if 'league' in f else "Unknown League",
                "home": f['localTeam']['data']['name'] if 'localTeam' in f else "Home",
                "away": f['visitorTeam']['data']['name'] if 'visitorTeam' in f else "Away",
                "minute": f.get('time', {}).get('minute', 0),
                "home_goals": f.get('scores', {}).get('localteam_score', 0),
                "away_goals": f.get('scores', {}).get('visitorteam_score', 0),
                "h2h": {},   # Add H2H/corners if available
            })
        return matches
    except Exception as e:
        print("SportMonks fetch failed:", e)
        return []

# -----------------------
# Send message to Telegram
# -----------------------
def send_match_prediction(match):
    preds = predict_match(match)
    message = f"""
⚽ League: {match['league']}
Match: {match['home']} vs {match['away']}
Minute: {match['minute']}'  
Over 0.5-5.5 Goal Probability: {preds['over_prob']}%
BTTS Probability: {preds['btts_prob']}%
Last 10-min Goal Probability: {preds['last10_prob']}%
Top Correct Scores: {preds['top_scores']}
"""
    bot.send_message(OWNER_CHAT_ID, message)

# -----------------------
# Main loop
# -----------------------
def main_loop():
    while True:
        print(f"[{datetime.now()}] Fetching live matches...")
        matches = fetch_live_matches_apifootball()
        if not matches:
            matches = fetch_live_matches_sportmonks()
        
        if not matches:
            print("⚠️ No live matches right now.")
            bot.send_message(OWNER_CHAT_ID, "⚠️ No live matches right now.")
        else:
            for match in matches:
                send_match_prediction(match)
        
        print("✅ Cycle complete. Waiting 7 minutes...")
        time.sleep(420)  # 7 minutes

# -----------------------
# Start bot
# -----------------------
if __name__ == "__main__":
    print(f"{BOT_NAME} started...")
    main_loop()
