import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask
import logging
from datetime import datetime, timedelta
import pytz
from threading import Thread, Lock
import json
import pandas as pd
import numpy as np
import schedule
import io
import re

# ------------------ Logging ------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ------------------ Env ------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
SPORTMONKS_API = os.getenv("API_KEY", "").strip()
BACKUP_GITHUB = "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/"

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except:
    OWNER_CHAT_ID = 0

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None
PAK_TZ = pytz.timezone('Asia/Karachi')

# ------------------ Config ------------------
TOP_LEAGUES = {
    39: "Premier League", 140: "La Liga", 78: "Bundesliga",
    135: "Serie A", 61: "Ligue 1", 94: "Primeira Liga",
    88: "Eredivisie", 528: "World Cup Qualifiers"
}

MARKETS = ['winning_team', 'draw', 'btts', 'over_0.5','over_1.5','over_2.5','over_3.5','over_4.5','over_5.5','last_10_min_goal']

DATA_LOCK = Lock()
historical_matches = []
last_sent = {}

# ------------------ Utils ------------------
def get_pakistan_time():
    return datetime.now(PAK_TZ)

def format_pakistan_time():
    return get_pakistan_time().strftime('%Y-%m-%d %H:%M:%S %Z')

def clean_team_name(team):
    if not team: return ""
    team = str(team).strip()
    team = re.sub(r'FC$|CF$|AFC$|CFC$', '', team).strip()
    team = re.sub(r'\s+', ' ', team)
    return team

# ------------------ Telegram ------------------
def send_telegram(message):
    if not bot or not OWNER_CHAT_ID: return False
    try:
        bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

# ------------------ Historical ------------------
def load_historical_data():
    global historical_matches
    datasets = ['premier_league.csv','la_liga.csv','bundesliga.csv','serie_a.csv','ligue_1.csv','primeira_liga.csv','eredivisie.csv']
    all_matches = []
    for file in datasets:
        try:
            url = BACKUP_GITHUB + file
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                for _, row in df.iterrows():
                    all_matches.append({
                        'league': file.replace('.csv','').replace('_',' ').title(),
                        'home_team': clean_team_name(row.get('HomeTeam','')),
                        'away_team': clean_team_name(row.get('AwayTeam','')),
                        'home_goals': row.get('FTHG',0),
                        'away_goals': row.get('FTAG',0),
                        'result': row.get('FTR',''),
                        'date': row.get('Date',''),
                        'source':'github'
                    })
            logger.info(f"Loaded {len(df)} matches from {file}")
        except Exception as e:
            logger.error(f"Historical load error {file}: {e}")
            continue
    historical_matches = all_matches
    logger.info(f"Total historical matches loaded: {len(historical_matches)}")

# ------------------ Live Matches ------------------
def fetch_live_matches():
    matches = []
    if not SPORTMONKS_API: return matches
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for m in data.get("data",[]):
                league_id = m.get("league_id")
                if league_id not in TOP_LEAGUES: continue
                status = m.get("status","")
                minute = m.get("minute")
                if status!="LIVE" or not minute: continue
                participants = m.get("participants",[])
                if len(participants)<2: continue
                home = participants[0].get("name","")
                away = participants[1].get("name","")
                home_score = m.get("scores",{}).get("home_score",0)
                away_score = m.get("scores",{}).get("away_score",0)
                matches.append({
                    'match_id': m.get("id"),
                    'league': TOP_LEAGUES[league_id],
                    'home': clean_team_name(home),
                    'away': clean_team_name(away),
                    'home_score': home_score,
                    'away_score': away_score,
                    'minute': int(minute.replace("'","")) if isinstance(minute,str) else int(minute)
                })
    except Exception as e:
        logger.error(f"Live fetch error: {e}")
    return matches

# ------------------ Team Stats ------------------
def get_team_stats(team, hist):
    team_matches = [x for x in hist if x['home_team']==team or x['away_team']==team]
    if not team_matches: return {'win_rate':0.35,'draw_rate':0.3,'avg_goals_for':1.3,'avg_goals_against':1.3,'form_strength':0.5}
    wins=draws=goals_for=goals_against=0
    form=[]
    for m in team_matches[-10:]:
        is_home = m['home_team']==team
        goals_for += m['home_goals'] if is_home else m['away_goals']
        goals_against += m['away_goals'] if is_home else m['home_goals']
        if (is_home and m['result']=='H') or (not is_home and m['result']=='A'):
            wins+=1
            form.append(1)
        elif m['result']=='D':
            draws+=1
            form.append(0.5)
        else:
            form.append(0)
    total = len(team_matches)
    return {
        'win_rate': wins/total,
        'draw_rate': draws/total,
        'avg_goals_for': goals_for/total,
        'avg_goals_against': goals_against/total,
        'form_strength': sum(form)/len(form) if form else 0.5
    }

# ------------------ Predictions ------------------
def predict_match(home_stats, away_stats, home_score, away_score, minute):
    predictions = {}
    total_goals = home_score+away_score

    # Winning Team
    h = home_stats['win_rate']*1.1+home_stats['form_strength']*0.3+(home_score-away_score)*0.1
    a = away_stats['win_rate']+away_stats['form_strength']*0.3-(home_score-away_score)*0.1
    if h>a+0.25: predictions['winning_team']={'prediction':'Home Win','confidence':min(95,70+(h-a)*80)}
    elif a>h+0.25: predictions['winning_team']={'prediction':'Away Win','confidence':min(95,70+(a-h)*80)}

    # Draw
    if home_score==away_score and minute>=75: predictions['draw']={'prediction':'Draw','confidence':85}
    # BTTS
    btts_prob = (home_stats['avg_goals_for']*away_stats['avg_goals_against'] + away_stats['avg_goals_for']*home_stats['avg_goals_against'])/2
    if btts_prob>1.2 and minute<=75: predictions['btts']={'prediction':'Yes','confidence':min(88,60+btts_prob*20)}
    # Over/Under 0.5-5.5
    rem = 90-minute
    h_rate = home_stats['avg_goals_for']/90
    a_rate = away_stats['avg_goals_for']/90
    expected_add = (h_rate+a_rate)*rem
    expected_total = total_goals+expected_add
    for line in [0.5,1.5,2.5,3.5,4.5,5.5]:
        if expected_total>line+0.5: predictions[f'over_{line}']={'prediction':f'Over {line}','confidence':min(95,70+(expected_total-line)*40)}
        else: predictions[f'over_{line}']={'prediction':f'Under {line}','confidence':40}
    # Last 10 min goal
    goal_prob = (h_rate+a_rate)*10
    predictions['last_10_min_goal']={'prediction':'High Chance' if goal_prob>0.8 else 'Low Chance','confidence':min(90,60+goal_prob*40) if goal_prob>0.8 else 35}
    return predictions

# ------------------ Format Message ------------------
def format_message(match, pred):
    msg = f"🎯 *Predictions {format_pakistan_time()}*\n🏆 {match['league']}\n🏠 {match['home']} vs 🛫 {match['away']}\nScore: {match['home_score']}-{match['away_score']} Min: {match['minute']}\n\n"
    for k,v in pred.items():
        if 'over' in k: label = f"⚽ {v['prediction']} Goals"
        elif k=='btts': label = f"🎯 Both Teams To Score: {v['prediction']}"
        elif k=='last_10_min_goal': label=f"⏰ Last 10 Min Goal: {v['prediction']}"
        elif k=='winning_team': label=f"🏆 Winning Team: {v['prediction']}"
        elif k=='draw': label=f"🤝 Match Draw: {v['prediction']}"
        else: label=f"{k}: {v['prediction']}"
        msg += f"• {label} - {v['confidence']}% ✅\n"
    msg += "\n⚠️ *Professional betting analysis - gamble responsibly*"
    return msg

# ------------------ Job ------------------
def job():
    global last_sent
    live_matches = fetch_live_matches()
    if not live_matches: 
        logger.info("No live matches found")
        return
    for match in live_matches:
        mid = match['match_id']
        if mid in last_sent and time.time()-last_sent[mid]<420: continue  # 7 min
        home_stats = get_team_stats(match['home'], historical_matches)
        away_stats = get_team_stats(match['away'], historical_matches)
        pred = predict_match(home_stats, away_stats, match['home_score'], match['away_score'], match['minute'])
        if pred:
            msg = format_message(match, pred)
            send_telegram(msg)
            last_sent[mid]=time.time()

# ------------------ Scheduler ------------------
schedule.every(7).minutes.do(job)

# ------------------ Flask for keepalive ------------------
app = Flask(__name__)
@app.route("/")
def ping(): return "Bot alive"

# ------------------ Start Bot ------------------
if __name__=="__main__":
    logger.info("Loading historical data...")
    load_historical_data()
    logger.info("Starting scheduler and Flask server...")
    # Scheduler in thread
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)
    Thread(target=run_schedule,daemon=True).start()
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",8080)))
