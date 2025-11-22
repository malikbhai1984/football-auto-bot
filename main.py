import os
import requests
import telebot
import time
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from threading import Thread

# ---------------- ENV VARIABLES ----------------
load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID"))
API_KEY = os.environ.get("API_KEY")
SPORTMONKS_API = os.environ.get("SPORTMONKS_API")
BOT_NAME = os.environ.get("BOT_NAME", "MyBetAlert_Bot")

# ----------- Top Leagues & WCQ IDs -------------
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 2, 3, 8]  # EPL, LaLiga, Serie A, Bundesliga, Ligue 1, etc.

# -------- TELEGRAM BOT INIT -------------------
bot = telebot.TeleBot(BOT_TOKEN)

# -------- FETCH LIVE MATCHES ------------------
def fetch_live_matches():
    # ---------- API-Football ----------
    try:
        headers = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": "api-football-v1.p.rapidapi.com"}
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures?live=all"
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json().get('response', [])
        live_matches = []
        for match in data:
            league_id = match['league']['id']
            if league_id in TOP_LEAGUES_IDS or match['league']['type'] == 'WCQ':
                live_matches.append({
                    'home_team': match['teams']['home']['name'],
                    'away_team': match['teams']['away']['name'],
                    'league': match['league']['name'],
                    'minute': match['fixture']['status'].get('elapsed', 0)
                })
        if live_matches:
            print(f"✅ API-Football live matches fetched: {len(live_matches)}")
            return live_matches
    except Exception as e:
        print(f"⚠️ API-Football failed: {e}")

    # ---------- SportMonks Fallback ----------
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}"
        r = requests.get(url, timeout=10)
        data = r.json()
        live_matches = []
        for match in data.get('data', []):
            league_id = match.get('league_id')
            if league_id in TOP_LEAGUES_IDS or match.get('competition', {}).get('type') == 'WCQ':
                live_matches.append({
                    'home_team': match.get('localTeam', {}).get('data', {}).get('name', 'None'),
                    'away_team': match.get('visitorTeam', {}).get('data', {}).get('name', 'None'),
                    'league': match.get('league', {}).get('data', {}).get('name', 'Unknown League'),
                    'minute': match.get('time', {}).get('minute', 0)
                })
        if live_matches:
            print(f"✅ SportMonks live matches fetched: {len(live_matches)}")
            return live_matches
    except Exception as e:
        print(f"⚠️ SportMonks failed: {e}")

    return []

# -------- PREDICTION LOGIC -------------------
def predict_match(match):
    """
    Dummy ML/AI prediction using random probabilities.
    Replace with your own ML model or statistical formulas.
    """
    over_prob = np.random.uniform(0.4, 0.9)
    btts_prob = np.random.uniform(0.3, 0.8)
    last10_prob = np.random.uniform(0.1, 0.3)
    correct_scores = [(1,1),(1,0)]
    return {
        'home_team': match['home_team'],
        'away_team': match['away_team'],
        'league': match['league'],
        'minute': match['minute'],
        'over_prob': round(over_prob*100,1),
        'btts_prob': round(btts_prob*100,1),
        'last10_prob': round(last10_prob*100,1),
        'top_scores': correct_scores
    }

# -------- SEND TELEGRAM MESSAGE ---------------
def send_prediction(pred):
    message = (f"⚽ Match: {pred['home_team']} vs {pred['away_team']}\n"
               f"League: {pred['league']}\n"
               f"Time: {pred['minute']}'\n"
               f"Over 0.5-5.5 Goal Probability: {pred['over_prob']}%\n"
               f"BTTS Probability: {pred['btts_prob']}%\n"
               f"Last 10-min Goal Probability: {pred['last10_prob']}%\n"
               f"Top Correct Scores: {pred['top_scores']}\n")
    bot.send_message(OWNER_CHAT_ID, message)

# -------- MAIN LOOP --------------------------
def main_loop():
    while True:
        try:
            matches = fetch_live_matches()
            if not matches:
                print("⚠️ No live matches right now.")
            for match in matches:
                pred = predict_match(match)
                send_prediction(pred)
            print("✅ Cycle complete. Waiting 7 minutes...")
            time.sleep(420)  # 7 minutes
        except Exception as e:
            print(f"⚠️ Error in main loop: {e}")
            time.sleep(60)

# -------- RUN IN THREAD ----------------------
if __name__ == "__main__":
    print("🚀 Bot started...")
    Thread(target=main_loop).start()
    bot.polling(none_stop=True)
