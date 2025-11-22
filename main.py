import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask, request
import logging
from datetime import datetime, timedelta
import pytz
from threading import Thread, Lock
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import io
import re

# ----------------- Logging -----------------
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ----------------- Load environment -----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
SPORTMONKS_API = os.getenv("API_KEY", "").strip()
FOOTBALL_DATA_API = os.getenv("FOOTBALL_DATA_API", "").strip()
BACKUP_API = os.getenv("BACKUP_API", "").strip()

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN missing")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID missing")
try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except:
    OWNER_CHAT_ID = 0
    logger.error("❌ OWNER_CHAT_ID invalid")

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None
app = Flask(__name__)
PAK_TZ = pytz.timezone('Asia/Karachi')

# ----------------- Leagues -----------------
TOP_LEAGUES = {
    39: "Premier League",
    140: "La Liga",
    78: "Bundesliga",
    135: "Serie A",
    61: "Ligue 1",
    94: "Primeira Liga",
    88: "Eredivisie",
    528: "World Cup",
    999: "World Cup Qualifiers"  # Custom ID if needed
}

# ----------------- Config -----------------
class Config:
    BOT_CYCLE_INTERVAL = 60  # seconds
    MIN_CONFIDENCE_THRESHOLD = 85
    DATA_CLEANUP_INTERVAL = 6
    HISTORICAL_DATA_RELOAD = 6
    MARKETS_TO_ANALYZE = [
        'winning_team', 'draw', 'btts',
        'over_0.5','over_1.5','over_2.5','over_3.5','over_4.5','over_5.5',
        'last_10_min_goal'
    ]

# ----------------- Globals -----------------
bot_started = False
message_counter = 0
historical_data = {}
data_lock = Lock()
api_usage_tracker = {
    'sportmonks': {'count':0,'reset_time':datetime.now(),'failures':0,'last_success':datetime.now()},
    'football_data': {'count':0,'reset_time':datetime.now(),'failures':0,'last_success':datetime.now()},
    'github': {'count':0,'reset_time':datetime.now(),'failures':0,'last_success':datetime.now()}
}

# ----------------- Time utils -----------------
def get_pakistan_time():
    return datetime.now(PAK_TZ)
def format_pakistan_time(dt=None):
    if not dt:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M %Z')

# ----------------- API utils -----------------
def check_api_health(api_name):
    api = api_usage_tracker.get(api_name, {})
    if api.get('failures',0) >=3:
        last = api.get('last_success', datetime.now())
        if (datetime.now()-last).seconds < 1800:
            return False
    return True

def update_api_status(api_name, success=True):
    if api_name in api_usage_tracker:
        if success:
            api_usage_tracker[api_name]['failures']=0
            api_usage_tracker[api_name]['last_success']=datetime.now()
        else:
            api_usage_tracker[api_name]['failures']+=1

def check_api_limits(api_name):
    try:
        now = datetime.now()
        api = api_usage_tracker[api_name]
        if (now - api['reset_time']).seconds>=60:
            api['count']=0
            api['reset_time']=now
        limits = {'sportmonks':8,'football_data':8,'github':50}
        if api['count']>=limits.get(api_name,10):
            return False
        api['count']+=1
        return True
    except:
        return True

def safe_api_call(url, api_name, headers=None, timeout=10):
    try:
        if not check_api_limits(api_name) or not check_api_health(api_name):
            return None
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 429:
            time.sleep(30)
            return None
        if resp.status_code==200:
            update_api_status(api_name, True)
            return resp
        update_api_status(api_name, False)
        return None
    except Exception as e:
        logger.error(f"{api_name} call error: {e}")
        update_api_status(api_name, False)
        return None

# ----------------- Flask endpoints -----------------
@app.route("/")
def health(): 
    return json.dumps({
        "status":"healthy",
        "timestamp":format_pakistan_time(),
        "bot_started":bot_started,
        "message_counter":message_counter
    }), 200, {'Content-Type':'application/json'}

@app.route("/health")
def health_check(): return "OK",200

# ----------------- Telegram -----------------
def send_telegram_message(msg, max_retries=3):
    global message_counter
    if not bot or not OWNER_CHAT_ID: return False
    for attempt in range(max_retries):
        try:
            message_counter+=1
            bot.send_message(OWNER_CHAT_ID, msg, parse_mode='Markdown')
            return True
        except Exception as e:
            if attempt<max_retries-1: time.sleep(2**attempt)
    return False

# ----------------- Historical data -----------------
def clean_team_name(team_name):
    if not team_name: return ""
    n=str(team_name).strip()
    n=re.sub(r'FC$|CF$|AFC$|CFC$','',n).strip()
    n=re.sub(r'\s+',' ',n)
    return n

def fetch_petermclagan_data():
    try:
        url_base="https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/"
        datasets={'premier_league':'premier_league.csv','la_liga':'la_liga.csv'}
        matches=[]
        for league,fn in datasets.items():
            resp = safe_api_call(url_base+fn,'github')
            if resp:
                df=pd.read_csv(io.StringIO(resp.text))
                for _,r in df.iterrows():
                    matches.append({
                        'league': league.replace('_',' ').title(),
                        'home_team': clean_team_name(r.get('HomeTeam','')),
                        'away_team': clean_team_name(r.get('AwayTeam','')),
                        'home_goals': r.get('FTHG',0),
                        'away_goals': r.get('FTAG',0),
                        'date': r.get('Date',''),
                        'result': r.get('FTR',''),
                        'source':'petermclagan',
                        'timestamp': get_pakistan_time()
                    })
        return matches
    except: return []

def load_historical_data():
    global historical_data
    petermclagan_data=fetch_petermclagan_data()
    historical_data={'matches':petermclagan_data,'last_updated':get_pakistan_time(),'total_matches':len(petermclagan_data)}
    return True

def find_relevant_historical_data(match):
    if not historical_data or 'matches' not in historical_data: return []
    home=match['home']; away=match['away']; league=match['league']
    relevant=[]
    for m in historical_data['matches']:
        if (m['home_team']==home and m['away_team']==away) or (m['home_team']==away and m['away_team']==home) or (league.lower() in m['league'].lower() or m['league'].lower() in league.lower()):
            relevant.append(m)
    return relevant

# ----------------- Live match fetching -----------------
def fetch_live_matches():
    all_matches=[]
    # SPORTMONKS
    if SPORTMONKS_API and check_api_health('sportmonks'):
        url=f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        resp=safe_api_call(url,'sportmonks')
        if resp:
            data=resp.json()
            for m in data.get('data',[]):
                league_id=m.get('league_id')
                if league_id not in TOP_LEAGUES: continue
                minute=m.get('minute')
                if not minute or m.get('status') not in ['LIVE','HT']: continue
                participants=m.get('participants',[])
                if len(participants)<2: continue
                home=participants[0].get('name')
                away=participants[1].get('name')
                home_score=m.get('scores',{}).get('home_score',0)
                away_score=m.get('scores',{}).get('away_score',0)
                try: current_minute=int(str(minute).replace("'",""))
                except: current_minute=0
                all_matches.append({
                    "home":home,"away":away,"league":TOP_LEAGUES[league_id],
                    "score":f"{home_score}-{away_score}",
                    "home_score":home_score,"away_score":away_score,
                    "minute":f"{minute}'","current_minute":current_minute,
                    "match_id":m.get('id'),"status":m.get('status'),"source":"sportmonks"
                })
    # FOOTBALL-DATA fallback
    if FOOTBALL_DATA_API and check_api_health('football_data') and not all_matches:
        url="https://api.football-data.org/v4/matches"
        headers={'X-Auth-Token':FOOTBALL_DATA_API}
        resp=safe_api_call(url,'football_data',headers=headers)
        if resp:
            data=resp.json()
            for m in data.get("matches",[]):
                status=m.get("status"); minute=m.get("minute",0)
                if status!="LIVE" or not minute: continue
                home=m.get("homeTeam",{}).get("name")
                away=m.get("awayTeam",{}).get("name")
                score=m.get("score",{}).get("fullTime",{})
                all_matches.append({
                    "home":home,"away":away,"league":m.get("competition",{}).get("name"),
                    "score":f"{score.get('home',0)}-{score.get('away',0)}",
                    "home_score":score.get('home',0),"away_score":score.get('away',0),
                    "minute":f"{minute}'","current_minute":minute,
                    "match_id":m.get("id"),"status":status,"source":"football_data"
                })
    logger.info(f"📊 Live matches fetched: {len(all_matches)}")
    return all_matches

# ----------------- ML prediction -----------------
def ml_predict_winner(match,historical_matches):
    try:
        df=pd.DataFrame(historical_matches)
        if df.empty: return {'prediction':'None','confidence':0}
        df['home_avg']=df['home_goals']/1.0
        df['away_avg']=df['away_goals']/1.0
        df['label']=df['result'].map({'H':0,'D':1,'A':2})
        X=df[['home_avg','away_avg']]
        y=df['label']
        model=GradientBoostingClassifier()
        model.fit(X,y)
        home=match['home_score']; away=match['away_score']
        pred=model.predict([[home,away]])[0]
        prob=model.predict_proba([[home,away]])[0]
        labels=['Home Win','Draw','Away Win']
        return {'prediction':labels[pred],'confidence':round(max(prob)*100,2)}
    except: return {'prediction':'None','confidence':0}

# ----------------- Simple heuristic for other markets -----------------
def predict_btts(match,historical_matches):
    home=match['home_score']; away=match['away_score']
    if home>0 and away>0: return {'prediction':'Yes','confidence':90}
    return {'prediction':'No','confidence':40}

def predict_over(match, line):
    home=match['home_score']; away=match['away_score']
    total=home+away
    if total>=line: return {'prediction':f'Over {line}','confidence':90}
    return {'prediction':f'Under {line}','confidence':40}

def predict_last_10(match):
    return {'prediction':'High Chance','confidence':45} if match['current_minute']>=80 else {'prediction':'Low Chance','confidence':35}

# ----------------- Message formatting -----------------
def format_message(match,preds,historical_count):
    msg=f"""🎯 **ULTRA 85%+ PREDICTIONS** 🎯

🏆 League: {match['league']}
🕒 Minute: {match['minute']}
📊 Score: {match['score']}

🏠 {match['home']} vs 🛫 {match['away']}

🔥 HIGH-CONFIDENCE BETS (85%+):
"""
    for k,v in preds.items():
        if v['confidence']>=Config.MIN_CONFIDENCE_THRESHOLD:
            msg+=f"• {k.replace('_',' ').title()}: {v['prediction']} - {v['confidence']}% ✅\n"
    msg+=f"\n📈 Analysis: {historical_count} historical matches\n🕐 Time: {format_pakistan_time()}\n⚠️ Gamble responsibly"
    return msg

# ----------------- Bot Worker -----------------
def bot_worker():
    global bot_started
    bot_started=True
    load_historical_data()
    send_telegram_message(f"🚀 ULTRA Bot Started at {format_pakistan_time()}")
    cycle=0
    while True:
        try:
            cycle+=1
            live=fetch_live_matches()
            for match in live:
                hist=find_relevant_historical_data(match)
                if len(hist)<3: continue
                preds={}
                preds['Winning Team']=ml_predict_winner(match,hist)
                preds['BTTS']=predict_btts(match,hist)
                for g in [0.5,1.5,2.5,3.5,4.5,5.5]:
                    preds[f'Over {g}']=predict_over(match,g)
                preds['Last 10 Min Goal']=predict_last_10(match)
                message=format_message(match,preds,len(hist))
                send_telegram_message(message)
                time.sleep(1)
            time.sleep(Config.BOT_CYCLE_INTERVAL)
        except Exception as e:
            logger.error(f"Bot cycle error: {e}")
            time.sleep(10)

def start_bot_thread():
    try:
        Thread(target=bot_worker,daemon=True).start()
        return True
    except:
        return False

# ----------------- Auto start -----------------
if BOT_TOKEN and OWNER_CHAT_ID:
    start_bot_thread()

if __name__=="__main__":
    port=int(os.environ.get("PORT",8080))
    app.run(host="0.0.0.0",port=port,debug=False)
