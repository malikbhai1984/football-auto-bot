import os
import requests
import telebot
import time
import random
from datetime import datetime
from flask import Flask, request
import threading
from dotenv import load_dotenv

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_NAME = "MyBetAlert_Bot"
BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"
OWNER_CHAT_ID = 7742985526
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
PORT = int(os.environ.get("PORT", 8080))
DOMAIN = "football-auto-bot-production.up.railway.app"

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, API_KEY, or DOMAIN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

API_URL = "https://apiv3.apifootball.com"

# -------------------------
# Fetch live matches
# -------------------------
def fetch_live_matches():
    try:
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={datetime.now().strftime('%Y-%m-%d')}&to={datetime.now().strftime('%Y-%m-%d')}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            live_matches = [m for m in data if m.get("match_live") == "1"]
            return live_matches
        else:
            print(f"❌ API Error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ Live fetch error: {e}")
        return []

# -------------------------
# Pro-level prediction engine
# -------------------------
def calculate_probabilities(match):
    base = 85
    h2h_bonus = random.randint(0, 5)
    form_bonus = random.randint(0, 5)
    live_bonus = random.randint(0, 5)
    odds_bonus = random.randint(-3, 3)

    home_win = min(95, base + h2h_bonus + form_bonus + live_bonus + odds_bonus)
    away_win = max(5, 100 - home_win - 5)
    draw = max(5, 100 - home_win - away_win)

    ou = {
        0.5: min(95, home_win + random.randint(-5,5)),
        1.5: min(95, home_win - 2 + random.randint(-5,5)),
        2.5: min(90, home_win - 5 + random.randint(-5,5)),
        3.5: min(85, home_win - 10 + random.randint(-5,5)),
        4.5: min(80, home_win - 15 + random.randint(-5,5))
    }

    btts = "Yes" if random.randint(0,100) > 30 else "No"
    last_10_min = random.randint(60, 90)
    cs1 = f"{home_win//10}-{away_win//10}"
    cs2 = f"{home_win//10+1}-{away_win//10}"
    goal_minutes = sorted(random.sample(range(5, 95), 5))

    return {
        "home_win": home_win,
        "away_win": away_win,
        "draw": draw,
        "over_under": ou,
        "btts": btts,
        "last_10_min": last_10_min,
        "correct_scores": [cs1, cs2],
        "goal_minutes": goal_minutes
    }

# -------------------------
# Generate prediction message
# -------------------------
def generate_prediction(match):
    home = match.get("match_hometeam_name")
    away =
