import os
import requests
import telebot
import time
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from threading import Thread
from datetime import datetime, timedelta
import pytz
import io
import re
import logging

# ----------------- Logging -----------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# ----------------- Environment -----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", 0))
SPORTMONKS_API = os.getenv("API_KEY")  # primary API key
FALLBACK_API = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

bot = telebot.TeleBot(BOT_TOKEN)

PAK_TZ = pytz.timezone('Asia/Karachi')

# ----------------- Leagues -----------------
TOP_8_LEAGUES = [
    "Premier League", "La Liga", "Serie A", "Bundesliga",
    "Ligue 1", "Primeira Liga", "Eredivisie", "Russian Premier League"
]
WC_QUALIFIERS = ["World Cup Qualification"]

# ----------------- Helper Functions -----------------
def get_pak_time():
    return datetime.now(PAK_TZ)

def format_time(dt=None):
    if not dt:
        dt = get_pak_time()
    return dt.strftime("%Y-%m-%d %H:%M %Z")

def clean_name(name):
    if not name:
        return ""
    name = str(name).strip()
    name = re.sub(r'FC$|CF$|AFC$|CFC$', '', name).strip()
    return re.sub(r'\s+', ' ', name)

# ----------------- Historical Data -----------------
def fetch_historical_data():
    logger.info("📥 Fetching historical data from GitHub...")
    urls = [
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/premier_league.csv",
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/la_liga.csv",
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/serie_a.csv",
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/bundesliga.csv",
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/ligue_1.csv",
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/primeira_liga.csv",
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/eredivisie.csv"
    ]
    matches = []
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                for _, row in df.iterrows():
                    matches.append({
                        'home_team': clean_name(row.get('HomeTeam')),
                        'away_team': clean_name(row.get('AwayTeam')),
                        'home_goals': row.get('FTHG', 0),
                        'away_goals': row.get('FTAG', 0),
                        'home_corners': row.get('HC', 0),
                        'away_corners': row.get('AC', 0),
                        'result': row.get('FTR'),
                        'league': url.split("/")[-1].replace(".csv", "").replace("_", " ").title(),
                        'date': row.get('Date')
                    })
        except Exception as e:
            logger.error(f"❌ Error fetching {url}: {e}")
    logger.info(f"✅ Historical matches loaded: {len(matches)}")
    return matches

historical_matches = fetch_historical_data()

# ----------------- Live Matches -----------------
def fetch_live_matches():
    matches = []
    api_key = SPORTMONKS_API if SPORTMONKS_API else FALLBACK_API
    url = f"https://api.sportmonks.com/v3/football/livescores?api_token={api_key}&include=league,participants"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            for m in data:
                league_name = m.get("league", {}).get("data", {}).get("name", "")
                if league_name not in TOP_8_LEAGUES + WC_QUALIFIERS:
                    continue
                participants = m.get("participants", [])
                if len(participants) < 2:
                    continue
                home = clean_name(participants[0].get("name"))
                away = clean_name(participants[1].get("name"))
                home_score = m.get("scores", {}).get("home_score", 0)
                away_score = m.get("scores", {}).get("away_score", 0)
                minute = m.get("minute", 0)
                matches.append({
                    "home": home,
                    "away": away,
                    "home_score": home_score,
                    "away_score": away_score,
                    "minute": int(minute),
                    "league": league_name,
                    "match_id": m.get("id")
                })
    except Exception as e:
        logger.error(f"❌ Live matches fetch error: {e}")
    return matches

# ----------------- ML / AI Prediction -----------------
def get_team_stats(team, hist_matches):
    team_matches = [m for m in hist_matches if m['home_team'] == team or m['away_team'] == team]
    if not team_matches:
        return {'win_rate':0.35,'draw_rate':0.3,'loss_rate':0.35,
                'avg_goals_for':1.3,'avg_goals_against':1.3,'form':0.5,
                'avg_corners':4.5}
    
    wins = draws = losses = 0
    goals_for = goals_against = corners = 0
    recent_form = []
    for match in team_matches[-10:]:
        is_home = match['home_team']==team
        gf = match['home_goals'] if is_home else match['away_goals']
        ga = match['away_goals'] if is_home else match['home_goals']
        cor = match['home_corners'] if is_home else match['away_corners']
        goals_for += gf
        goals_against += ga
        corners += cor
        result = match['result']
        if (is_home and result=='H') or (not is_home and result=='A'):
            wins += 1
            recent_form.append(1)
        elif result=='D':
            draws +=1
            recent_form.append(0.5)
        else:
            losses +=1
            recent_form.append(0)
    total = len(team_matches)
    return {
        'win_rate': wins/total,
        'draw_rate': draws/total,
        'loss_rate': losses/total,
        'avg_goals_for': goals_for/total,
        'avg_goals_against': goals_against/total,
        'form': np.mean(recent_form),
        'avg_corners': corners/total
    }

def predict_match(home_stats, away_stats, home_score, away_score, minute):
    predictions = {}

    # ---------- Winning Team ----------
    home_strength = home_stats['win_rate']*1.1 + home_stats['form']*0.3 + (home_score-away_score)*0.1
    away_strength = away_stats['win_rate'] + away_stats['form']*0.3 + (away_score-home_score)*0.1
    if home_strength>away_strength+0.25:
        predictions['winning_team'] = {'prediction':'Home Win','confidence':min(95,70+(home_strength-away_strength)*80)}
    elif away_strength>home_strength+0.25:
        predictions['winning_team'] = {'prediction':'Away Win','confidence':min(95,70+(away_strength-home_strength)*80)}

    # ---------- Draw ----------
    if home_score==away_score and minute>=75:
        predictions['draw'] = {'prediction':'Draw','confidence':85}

    # ---------- BTTS ----------
    btts_prob = (home_stats['avg_goals_for']*away_stats['avg_goals_against'] +
                 away_stats['avg_goals_for']*home_stats['avg_goals_against'])/2
    if btts_prob>1.2 and minute<=75:
        predictions['btts'] = {'prediction':'Yes','confidence':min(88,60+btts_prob*20)}

    # ---------- Over/Under 0.5 to 5.5 ----------
    total_goals = home_score+away_score
    minutes_left = 90-minute
    expected_goals = (home_stats['avg_goals_for']+away_stats['avg_goals_for'])*minutes_left/90
    total_expected = total_goals + expected_goals
    for val in np.arange(0.5, 6.0, 0.5):
        conf = min(95,70 + (total_expected - val)*30)
        if conf>=85:
            if total_expected>val:
                predictions[f'over_{val}'] = {'prediction':f'Over {val}','confidence':conf}
            else:
                predictions[f'under_{val}'] = {'prediction':f'Under {val}','confidence':conf}

    # ---------- Last 10-minute goal chance ----------
    if minute>=80:
        prob = (home_stats['avg_goals_for']+away_stats['avg_goals_for'])/90*10
        if prob>=1:
            predictions['last_10_min_goal'] = {'prediction':'Likely Goal','confidence':min(95, 75+prob*10)}
    return predictions

# ----------------- Telegram Messaging -----------------
def send_telegram(msg):
    try:
        bot.send_message(OWNER_CHAT_ID, msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Telegram send error: {e}")

def format_message(match, pred):
    msg = f"🎯 *85%+ CONFIDENCE PREDICTIONS*\n"
    msg+=f"🏆 League: {match['league']}\n"
    msg+=f"🕒 Minute: {match['minute']}\n"
    msg+=f"📊 Score: {match['home_score']}-{match['away_score']}\n"
    msg+=f"🏠 {match['home']} vs 🛫 {match['away']}\n\n"
    msg+="🔥 *Predictions:* \n"
    for k,v in pred.items():
        msg+=f"• {k.replace('_',' ').title()}: {v['prediction']} - {v['confidence']}% ✅\n"
    msg+=f"\n🕐 Time: {format_time()}"
    return msg

# ----------------- Bot Worker -----------------
def bot_worker():
    while True:
        live_matches = fetch_live_matches()
        if live_matches:
            for match in live_matches:
                home_stats = get_team_stats(match['home'], historical_matches)
                away_stats = get_team_stats(match['away'], historical_matches)
                pred = predict_match(home_stats, away_stats, match['home_score'], match['away_score'], match['minute'])
                if pred:
                    msg = format_message(match, pred)
                    send_telegram(msg)
                time.sleep(1)
        time.sleep(60)  # 1-minute interval

# ----------------- Start Bot -----------------
if __name__ == "__main__":
    logger.info("🤖 Starting Top 8 Leagues + WC Qualifiers Prediction Bot with 0.5-5.5 & Last 10-min goal")
    Thread(target=bot_worker, daemon=True).start()
