import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests








import os
from dotenv import load_dotenv
import telebot
from flask import Flask, request
import requests
import threading
import time
from datetime import datetime
import math

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
BOT_NAME = os.environ.get("BOT_NAME", "Malik Bhai Intelligent Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID or not API_KEY:
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_KEY missing!")

# -------------------------
# Initialize Flask & Bot
# -------------------------
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
API_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# -------------------------
# Fetch live matches
# -------------------------
def fetch_live_matches():
    try:
        resp = requests.get(f"{API_URL}/fixtures?live=all", headers=HEADERS).json()
        return resp.get("response", [])
    except:
        return []

# -------------------------
# Fetch odds for a fixture
# -------------------------
def fetch_odds(fixture_id):
    try:
        resp = requests.get(f"{API_URL}/odds?fixture={fixture_id}", headers=HEADERS).json()
        return resp.get("response", [])
    except:
        return []

# -------------------------
# Fetch team form (last 5 matches)
# -------------------------
def fetch_team_form(team_id):
    try:
        resp = requests.get(f"{API_URL}/fixtures?team={team_id}&last=5", headers=HEADERS).json()
        matches = resp.get("response", [])
        wins = draws = losses = goals_scored = goals_conceded = 0
        for m in matches:
            home_goals = m["goals"]["home"]
            away_goals = m["goals"]["away"]
            if m["teams"]["home"]["id"] == team_id:
                goals_scored += home_goals
                goals_conceded += away_goals
                if home_goals > away_goals: wins+=1
                elif home_goals==away_goals: draws+=1
                else: losses+=1
            else:
                goals_scored += away_goals
                goals_conceded += home_goals
                if away_goals > home_goals: wins+=1
                elif home_goals==away_goals: draws+=1
                else: losses+=1
        form_score = ((wins*3 + draws)/15)*100
        avg_goals = goals_scored/5
        return form_score, avg_goals
    except:
        return 70, 1.2

# -------------------------
# Fetch H2H stats
# -------------------------
def fetch_h2h(home_id, away_id):
    try:
        resp = requests.get(f"{API_URL}/fixtures/headtohead?h2h={home_id}-{away_id}", headers=HEADERS).json()
        matches = resp.get("response", [])
        h2h_weight = 0
        count = 0
        for m in matches[:5]:
            home_goals = m["goals"]["home"]
            away_goals = m["goals"]["away"]
            if home_goals>away_goals: h2h_weight += 90
            elif home_goals==away_goals: h2h_weight += 80
            else: h2h_weight += 70
            count+=1
        return h2h_weight/count if count>0 else 75
    except:
        return 75

# -------------------------
# Calculate confidence
# -------------------------
def calculate_confidence(odds, home_form, away_form, h2h, avg_goal):
    try:
        # Odds weight
        odds_weight = max(100/odds["Home"],100/odds["Draw"],100/odds["Away"])
        # Form weight
        form_weight = (home_form+away_form)/2
        # Goal trend weight
        goal_weight = avg_goal*15
        # Combined confidence
        combined = (0.4*odds_weight) + (0.25*form_weight) + (0.2*h2h) + (0.15*goal_weight)
        return round(combined,1)
    except:
        return 0

# -------------------------
# Poisson-based Correct Score
# -------------------------
def poisson_scores(avg_home, avg_away):
    max_goals = 3
    scores = {}
    for h in range(0,max_goals+1):
        for a in range(0,max_goals+1):
            prob = (math.exp(-avg_home)*avg_home**h/math.factorial(h)) * (math.exp(-avg_away)*avg_away**a/math.factorial(a))
            scores[f"{h}-{a}"]=round(prob*100,1)
    sorted_scores = sorted(scores.items(), key=lambda x:x[1], reverse=True)[:2]
    return [s[0] for s in sorted_scores]

# -------------------------
# Intelligent Analysis
# -------------------------
def intelligent_analysis(match):
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    home_id = match["teams"]["home"]["id"]
    away_id = match["teams"]["away"]["id"]
    fixture_id = match["fixture"]["id"]

    # Odds
    odds_raw = fetch_odds(fixture_id)
    odds_list = {"Home":2.0,"Draw":3.0,"Away":4.0}
    if odds_raw:
        try:
            for book in odds_raw:
                if book["bookmaker"]["name"].lower()=="bet365":
                    mw = book["bets"][0]["values"]
                    odds_list = {"Home":float(mw[0]["odd"]),"Draw":float(mw[1]["odd"]),"Away":float(mw[2]["odd"])}
                    break
        except: pass

    # Team form
    home_form, avg_home_goals = fetch_team_form(home_id)
    away_form, avg_away_goals = fetch_team_form(away_id)

    # H2H
    h2h_weight = fetch_h2h(home_id, away_id)

    # Confidence
    confidence = calculate_confidence(odds_list, home_form, away_form, h2h_weight, (avg_home_goals+avg_away_goals)/2)
    if confidence<85: return None

    # Correct Score
    top_scores = poisson_scores(avg_home_goals, avg_away_goals)

    # BTTS
    btts = "Yes" if avg_home_goals>0.8 and avg_away_goals>0.8 else "No"

    # Last 10-min goal chance
    last_10_prob = round((0.2*(avg_home_goals+avg_away_goals))*100,1)
    if last_10_prob>100: last_10_prob=100

    return {
        "market":"Over 2.5 Goals",
        "prediction":"Yes",
        "confidence":confidence,
        "odds":"1.70-1.85",
        "reason":f"Real-time Odds + Team Form + H2H + Goal Trend analyzed for {home} vs {away}",
        "correct_scores":top_scores,
        "btts":btts,
        "last_10_min_goal":last_10_prob
    }

# -------------------------
# Telegram Message
# -------------------------
def format_bet_msg(match, analysis):
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    return (
        f"⚽ 85%+ Confirmed Bet Found!\n"
        f"Match: {home} vs {away}\n"
        f"🔹 Market – Prediction: {analysis['market']} – {analysis['prediction']}\n"
        f"💰 Confidence Level: {analysis['confidence']}%\n"
        f"📊 Reasoning: {analysis['reason']}\n"
        f"🔥 Odds Range: {analysis['odds']}\n"
        f"⚠️ Risk Note: Check injuries/cards\n"
        f"✅ Top Correct Scores: {', '.join(analysis['correct_scores'])}\n"
        f"✅ BTTS: {analysis['btts']}\n"
        f"✅ Last 10-Min Goal Chance: {analysis['last_10_min_goal']}%"
    )

# -------------------------
# Auto-update every 5 minutes
# -------------------------
def auto_update_job():
    while True:
        matches = fetch_live_matches()
        for match in matches:
            analysis = intelligent_analysis(match)
            if analysis:
                msg = format_bet_msg(match, analysis)
                try: bot.send_message(OWNER_CHAT_ID, msg)
                except: pass
        time.sleep(300)

threading.Thread(target=auto_update_job, daemon=True).start()

# -------------------------
# Webhook
# -------------------------
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.data.decode('utf-8'))
        bot.process_new_updates([update])
    except Exception as e:
        print(f"⚠️ Error: {e}")
    return 'OK', 200

@app.route('/')
def home():
    return f"⚽ {BOT_NAME} is running perfectly!", 200

# -------------------------
# Telegram Handlers
# -------------------------
@bot.message_handler(commands=['start', 'hello'])
def start(message):
    bot.reply_to(message, f"⚽ {BOT_NAME} is live!\nWelcome, {message.from_user.first_name}! ✅")

@bot.message_handler(func=lambda msg: True)
def smart_reply(message):
    text = message.text.lower().strip()
    if "hi" in text or "hello" in text:
        bot.reply_to(message, "👋 Hello Malik Bhai! Intelligent Bot is online ✅")
    elif any(x in text for x in ["update","live","who will win","over 2.5","btts","correct score"]):
        matches = fetch_live_matches()
        if not matches:
            bot.reply_to(message, "📊 No live matches now. Auto-update will notify you soon!")
        else:
            for match in matches:
                analysis = intelligent_analysis(match)
                if analysis:
                    msg = format_bet_msg(match, analysis)
                    bot.reply_to(message, msg)
                    break
    else:
        bot.reply_to(message, "🤖 Malik Bhai Intelligent Bot is online and ready! Ask me for match predictions like I do.")

# -------------------------
# Start Flask + webhook
# -------------------------
if __name__ == "__main__":
    domain = "https://your-railway-domain.up.railway.app"  # Update with your Railway domain
    webhook_url = f"{domain}/{BOT_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set: {webhook_url}")
    app.run(host='0.0.0.0', port=8080)









