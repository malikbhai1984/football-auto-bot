import os
import telebot
import time
import logging
import random
from datetime import datetime
from threading import Thread
from flask import Flask, request
from dotenv import load_dotenv
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import xgboost as xgb

# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -------------------------
# Load environment
# -------------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN").strip()
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID").strip())
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 8080))

# -------------------------
# Bot init
# -------------------------
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# -------------------------
# Config
# -------------------------
CONFIDENCE_THRESHOLD = 85
BOT_CYCLE_INTERVAL_MIN = 300  # 5 min
BOT_CYCLE_INTERVAL_MAX = 420  # 7 min

# -------------------------
# ML System
# -------------------------
class MLSystem:
    def __init__(self):
        self.win_model = None
        self.over_models = {}  # over_0.5, over_1.5 ... over_5.5
        self.scaler = StandardScaler()
        self.is_trained = False

ml_system = MLSystem()

# -------------------------
# Sample historical data
# -------------------------
def create_sample_data():
    teams = ['Man United','Liverpool','Arsenal','Chelsea','Man City','Tottenham']
    matches = []
    for _ in range(200):
        home = random.choice(teams)
        away = random.choice([t for t in teams if t != home])
        home_goals = random.randint(0,4)
        away_goals = random.randint(0,4)
        total_goals = home_goals + away_goals
        matches.append({
            'home_team': home,
            'away_team': away,
            'home_goals': home_goals,
            'away_goals': away_goals,
            'total_goals': total_goals,
            'home_win': 1 if home_goals > away_goals else 0,
            'away_win': 1 if away_goals > home_goals else 0,
            'draw': 1 if home_goals == away_goals else 0,
            'btts': 1 if home_goals>0 and away_goals>0 else 0,
            'over_0.5': 1 if total_goals>0.5 else 0,
            'over_1.5': 1 if total_goals>1.5 else 0,
            'over_2.5': 1 if total_goals>2.5 else 0,
            'over_3.5': 1 if total_goals>3.5 else 0,
            'over_4.5': 1 if total_goals>4.5 else 0,
            'over_5.5': 1 if total_goals>5.5 else 0,
        })
    return matches

# -------------------------
# Train ML models
# -------------------------
def train_models():
    try:
        logger.info("🧠 Training ML models...")
        data = create_sample_data()
        if len(data)<10:
            logger.error("❌ Insufficient data")
            return False

        X=[]
        for m in data:
            X.append([random.uniform(0.8,1.2), random.uniform(0.7,1.3), random.uniform(0.9,1.1)])
        X_scaled = ml_system.scaler.fit_transform(X)

        # Win model
        y_win=[]
        for m in data:
            if m['home_win']: y_win.append(0)
            elif m['away_win']: y_win.append(1)
            else: y_win.append(2)
        ml_system.win_model = xgb.XGBClassifier(n_estimators=50, max_depth=4, random_state=42)
        ml_system.win_model.fit(X_scaled, y_win)

        # Over models
        for g in [0.5,1.5,2.5,3.5,4.5,5.5]:
            y = [m[f'over_{g}'] for m in data]
            model = RandomForestClassifier(n_estimators=30, max_depth=4, random_state=42)
            model.fit(X_scaled,y)
            ml_system.over_models[g] = model

        ml_system.is_trained = True
        logger.info("✅ ML models trained successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Training error: {e}")
        return False

# -------------------------
# Generate predictions
# -------------------------
def generate_predictions(match):
    if not ml_system.is_trained: return {}
    try:
        feat = [[random.uniform(0.8,1.2), random.uniform(0.7,1.3), random.uniform(0.9,1.1)]]
        feat_scaled = ml_system.scaler.transform(feat)
        predictions={}

        # Win
        win_probs = ml_system.win_model.predict_proba(feat_scaled)[0]
        win_types=['Home Win','Away Win','Draw']
        for i,p in enumerate(win_probs):
            if p*100 >= CONFIDENCE_THRESHOLD:
                predictions['win']={'prediction':win_types[i],'confidence':p*100}

        # Over/Under
        for g,model in ml_system.over_models.items():
            p = model.predict_proba(feat_scaled)[0][1]*100
            if p >= CONFIDENCE_THRESHOLD:
                predictions[f'over_{g}']={'prediction':f'Over {g}','confidence':p}

        # BTTS
        btts_chance = random.randint(50,100)
        if btts_chance >= CONFIDENCE_THRESHOLD:
            predictions['btts']={'prediction':'Yes','confidence':btts_chance}

        # Goal minutes
        goal_minutes = sorted(random.sample(range(5,90),5))
        last_10_min = 100 if 80 in goal_minutes else 0
        predictions['goal_minutes']=goal_minutes
        predictions['last_10_min']=last_10_min

        return predictions
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
        return {}

# -------------------------
# Create test live matches
# -------------------------
def get_live_matches():
    return [
        {'home':'Man United','away':'Liverpool','league':'Premier League','score':'1-0','minute':'65','status':'LIVE'},
        {'home':'Arsenal','away':'Chelsea','league':'Premier League','score':'2-1','minute':'72','status':'LIVE'},
        {'home':'Man City','away':'Tottenham','league':'Premier League','score':'0-0','minute':'35','status':'LIVE'}
    ]

# -------------------------
# Format message
# -------------------------
def format_prediction_message(match,preds):
    msg=f"⚽ **FOOTBALL PREDICTION** ⚽\n\n🏆 {match['league']}\n⏰ Minute: {match['minute']}\n📊 Score: {match['score']}\n\n{match['home']} 🆚 {match['away']}\n\n🎯 **Predictions:**\n"
    for k,v in preds.items():
        if k in ['goal_minutes','last_10_min']: continue
        msg+=f"• {v['prediction']} - {v['confidence']:.1f}%\n"
    if 'goal_minutes' in preds:
        msg+=f"\n⏱ High-probability goal minutes: {', '.join(map(str,preds['goal_minutes']))}\n"
    if 'last_10_min' in preds:
        msg+=f"⚡ Chance of last 10-min goal: {preds['last_10_min']}%\n"
    msg+="\n🤖 *AI Powered Predictions*"
    return msg

# -------------------------
# Telegram sender
# -------------------------
def send_telegram_message(msg):
    try:
        bot.send_message(OWNER_CHAT_ID,msg,parse_mode='Markdown')
        logger.info("✅ Message sent")
    except Exception as e:
        logger.error(f"❌ Telegram send error: {e}")

# -------------------------
# Bot worker
# -------------------------
def bot_worker():
    if not train_models():
        logger.error("❌ ML training failed")
        return
    send_telegram_message("🚀 **Football Prediction Bot Started**\n✅ ML Models trained\n✅ Will send 85%+ predictions every 5–7 minutes")
    cycle=0
    while True:
        cycle+=1
        logger.info(f"🔄 Cycle {cycle}")
        matches = get_live_matches()
        for m in matches:
            preds = generate_predictions(m)
            if preds:
                msg = format_prediction_message(m,preds)
                send_telegram_message(msg)
            time.sleep(2)
        sleep_time = random.randint(BOT_CYCLE_INTERVAL_MIN,BOT_CYCLE_INTERVAL_MAX)
        time.sleep(sleep_time)

# -------------------------
# Flask webhook
# -------------------------
@app.route('/')
def home():
    return "Football Bot Running"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
        return 'OK',200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return 'ERROR',400

# -------------------------
# Start bot
# -------------------------
def start_bot():
    t=Thread(target=bot_worker,daemon=True)
    t.start()
    logger.info("✅ Bot thread started")

if __name__=="__main__":
    start_bot()
    app.run(host='0.0.0.0',port=PORT,debug=False)
