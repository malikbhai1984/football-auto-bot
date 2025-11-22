import os
import time
import requests
import telebot
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta
import pytz
import pandas as pd
import numpy as np
import io
import re
import logging

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# -----------------------------
# Load environment variables
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
SPORTMONKS_API = os.getenv("API_KEY", "").strip()
PORT = int(os.getenv("PORT", 8080))

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except:
    logger.error("OWNER_CHAT_ID invalid or missing!")
    OWNER_CHAT_ID = None

if not BOT_TOKEN or not OWNER_CHAT_ID:
    logger.warning("BOT_TOKEN or OWNER_CHAT_ID missing, bot will not send messages!")

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None
app = Flask(__name__)

PAK_TZ = pytz.timezone("Asia/Karachi")

# -----------------------------
# League Configuration
# -----------------------------
TOP_LEAGUES = {
    39: "Premier League",
    140: "La Liga",
    78: "Bundesliga",
    135: "Serie A",
    61: "Ligue 1",
    94: "Primeira Liga",
    88: "Eredivisie",
    528: "World Cup"
}

# -----------------------------
# Historical Data
# -----------------------------
historical_matches = []

def clean_team_name(name):
    if not name:
        return ""
    name = re.sub(r'FC$|CF$|AFC$|CFC$', '', str(name)).strip()
    name = re.sub(r'\s+', ' ', name)
    return name

def fetch_historical_data():
    """Fetch historical data from GitHub fallback"""
    global historical_matches
    try:
        urls = [
            "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/premier_league.csv",
            "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/la_liga.csv",
            # Add more leagues if needed
        ]
        all_matches = []
        for url in urls:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                for _, row in df.iterrows():
                    all_matches.append({
                        "league": row.get("League", ""),
                        "home_team": clean_team_name(row.get("HomeTeam", "")),
                        "away_team": clean_team_name(row.get("AwayTeam", "")),
                        "home_goals": row.get("FTHG", 0),
                        "away_goals": row.get("FTAG", 0),
                        "result": row.get("FTR", ""),
                        "date": row.get("Date", "")
                    })
        historical_matches = all_matches
        logger.info(f"✅ Loaded {len(historical_matches)} historical matches")
    except Exception as e:
        logger.error(f"❌ Error fetching historical data: {e}")

# -----------------------------
# Telegram message sender
# -----------------------------
def send_telegram(msg):
    if bot and OWNER_CHAT_ID:
        try:
            bot.send_message(OWNER_CHAT_ID, msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"❌ Telegram send failed: {e}")

# -----------------------------
# Utilities
# -----------------------------
def get_time():
    return datetime.now(PAK_TZ).strftime("%H:%M:%S %d-%m-%Y")

def safe_int(value):
    try:
        return int(value)
    except:
        return 0

# -----------------------------
# Live Match Fetch
# -----------------------------
def fetch_live_matches():
    matches = []
    # 1️⃣ Sportmonks API
    try:
        if SPORTMONKS_API:
            url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for match in data:
                    league_id = match.get("league_id")
                    if league_id in TOP_LEAGUES and match.get("status")=="LIVE":
                        participants = match.get("participants", [])
                        if len(participants)>=2:
                            home = participants[0].get("name", "")
                            away = participants[1].get("name", "")
                            score = match.get("scores", {})
                            minute = safe_int(match.get("minute", 0))
                            if 1 <= minute <= 90:
                                matches.append({
                                    "home": home,
                                    "away": away,
                                    "league": TOP_LEAGUES[league_id],
                                    "home_score": score.get("home_score",0),
                                    "away_score": score.get("away_score",0),
                                    "minute": minute
                                })
    except Exception as e:
        logger.error(f"❌ Sportmonks fetch error: {e}")
    return matches

# -----------------------------
# Prediction Functions
# -----------------------------
def compute_team_stats(team, historical):
    team_matches = [m for m in historical if m['home_team']==team or m['away_team']==team]
    if not team_matches:
        return {
            "win_rate":0.35,"draw_rate":0.3,"loss_rate":0.35,
            "avg_goals_for":1.3,"avg_goals_against":1.3,"form_strength":0.5
        }
    wins=draws=losses=0
    goals_for=goals_against=0
    form=[]
    for m in team_matches[-10:]:
        is_home = m['home_team']==team
        gf = m['home_goals'] if is_home else m['away_goals']
        ga = m['away_goals'] if is_home else m['home_goals']
        goals_for+=gf
        goals_against+=ga
        r = m['result']
        if (is_home and r=='H') or (not is_home and r=='A'):
            wins+=1; form.append(1)
        elif r=='D': draws+=1; form.append(0.5)
        else: losses+=1; form.append(0)
    n=len(team_matches)
    return {
        "win_rate":wins/n,
        "draw_rate":draws/n,
        "loss_rate":losses/n,
        "avg_goals_for":goals_for/n,
        "avg_goals_against":goals_against/n,
        "form_strength":np.mean(form)
    }

def predict_goals(home_stats, away_stats, current_score, line):
    total_goals = sum(current_score)
    minutes_left = 90-current_score[2]
    expected_goals = (home_stats['avg_goals_for'] + away_stats['avg_goals_for']) * minutes_left/90
    total_expected = total_goals + expected_goals
    if total_expected>line+0.5:
        return f"Over {line}"
    return f"Under {line}"

def predict_btts(home_stats, away_stats, current_score):
    gf = home_stats['avg_goals_for']*0.5 + away_stats['avg_goals_for']*0.5
    if gf>1.2:
        return "Yes"
    return "No"

def predict_winner(home_stats, away_stats, current_score):
    home = home_stats['win_rate'] + home_stats['form_strength']*0.3 + current_score[0]*0.1
    away = away_stats['win_rate'] + away_stats['form_strength']*0.3 + current_score[1]*0.1
    if home-away>0.25: return "Home Win"
    elif away-home>0.25: return "Away Win"
    return "Draw"

# -----------------------------
# Main Prediction Loop
# -----------------------------
def analyze_and_send():
    fetch_historical_data()
    while True:
        try:
            matches = fetch_live_matches()
            for m in matches:
                home_stats = compute_team_stats(m['home'], historical_matches)
                away_stats = compute_team_stats(m['away'], historical_matches)
                cs = (m['home_score'], m['away_score'], m['minute'])
                msg = f"""🏆 {m['league']}
⏰ Minute: {m['minute']} | Score: {m['home_score']}-{m['away_score']}
📝 {m['home']} vs {m['away']}

🔥 Predictions:
• Winner: {predict_winner(home_stats, away_stats, cs)}
• BTTS: {predict_btts(home_stats, away_stats, cs)}
"""
                for line in [0.5,1.5,2.5,3.5,4.5,5.5]:
                    msg+=f"• Goals {line}: {predict_goals(home_stats, away_stats, cs, line)}\n"
                msg+=f"⏰ Last 10 min goal chance: {'High' if m['minute']>=80 else 'Low'}\n"
                msg+=f"🕐 Time: {get_time()}"
                send_telegram(msg)
                time.sleep(1)
            logger.info("✅ Cycle complete. Waiting 7 minutes...")
            time.sleep(420)  # 7 minutes
        except Exception as e:
            logger.error(f"❌ Main loop error: {e}")
            time.sleep(60)

# -----------------------------
# Flask Routes for Railway
# -----------------------------
@app.route("/")
def index():
    return "ULTRA 85%+ Bot Running", 200

# -----------------------------
# Start background thread
# -----------------------------
Thread(target=analyze_and_send, daemon=True).start()

# -----------------------------
# Run Flask
# -----------------------------
if __name__=="__main__":
    logger.info("🚀 Starting Flask server...")
    app.run(host="0.0.0.0", port=PORT)
