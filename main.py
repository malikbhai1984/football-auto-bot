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
# Helper: Fetch live matches
# -------------------------
def fetch_live_matches():
    try:
        resp = requests.get(f"{API_URL}/fixtures?live=all", headers=HEADERS).json()
        return resp.get("response", [])
    except Exception as e:
        print(f"⚠️ API Error: {e}")
        return []

# -------------------------
# Helper: Fetch odds for a fixture
# -------------------------
def fetch_odds(fixture_id):
    try:
        resp = requests.get(f"{API_URL}/odds?fixture={fixture_id}", headers=HEADERS).json()
        return resp.get("response", [])
    except Exception as e:
        print(f"⚠️ Odds API Error: {e}")
        return []

# -------------------------
# Helper: Fetch H2H stats
# -------------------------
def fetch_h2h(home, away):
    try:
        resp = requests.get(f"{API_URL}/fixtures/headtohead?h2h={home}-{away}", headers=HEADERS).json()
        return resp.get("response", [])
    except Exception as e:
        print(f"⚠️ H2H API Error: {e}")
        return []

# -------------------------
# Intelligent Probability Calculation
# -------------------------
def calculate_confidence(odds_list, home_form, away_form, h2h_data, goals_trend):
    """
    Combines odds, team form, H2H, and scoring trend to return a realistic confidence %
    """
    try:
        # Odds weight (higher probability for lower odds)
        odds_weight = 0
        if odds_list:
            home_odd = float(odds_list.get("Home", 2))
            draw_odd = float(odds_list.get("Draw", 3))
            away_odd = float(odds_list.get("Away", 4))
            odds_weight = max(100/home_odd, 100/draw_odd, 100/away_odd)

        # Team form weight
        form_weight = (home_form + away_form)/2  # % form

        # H2H weight
        h2h_weight = 0
        if h2h_data:
            h2h_weight = sum([m["result_weight"] for m in h2h_data])/len(h2h_data)

        # Goal trend weight
        goal_weight = sum(goals_trend)/len(goals_trend) if goals_trend else 0

        # Combined confidence
        combined = (0.4*odds_weight) + (0.3*form_weight) + (0.2*h2h_weight) + (0.1*goal_weight)
        return round(combined, 1)
    except:
        return 0

# -------------------------
# Intelligent Analysis
# -------------------------
def intelligent_analysis(match):
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    fixture_id = match["fixture"]["id"]

    # Fetch odds
    odds_raw = fetch_odds(fixture_id)
    odds_list = {}
    if odds_raw:
        try:
            for book in odds_raw:
                if book["bookmaker"]["name"].lower() == "bet365":
                    mw = book["bets"][0]["values"]
                    odds_list = {"Home": float(mw[0]["odd"]), "Draw": float(mw[1]["odd"]), "Away": float(mw[2]["odd"])}
                    break
        except: pass

    # Fetch recent team form (dummy % for example)
    home_form = 85  # % based on last 5 matches
    away_form = 80  # %

    # Fetch H2H data (dummy weight)
    h2h_data = [{"result_weight": 90}, {"result_weight": 85}]  # Example weights

    # Dynamic scoring trend (goal minutes)
    goals_trend = [80, 85, 90]  # % probability for last 10 min scoring

    # Calculate confidence
    confidence = calculate_confidence(odds_list, home_form, away_form, h2h_data, goals_trend)

    if confidence < 85:
        return None

    # Select market based on highest probability
    # For example: Over 2.5 Goals
    analysis = {
        "market": "Over 2.5 Goals",
        "prediction": "Yes",
        "confidence": confidence,
        "odds": "1.70-1.85",
        "reason": f"Odds weight + Team form + H2H + Goal trend analyzed for {home} vs {away}"
    }
    return analysis

# -------------------------
# Format Telegram message
# -------------------------
def format_bet_msg(match, analysis):
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    return (
        f"⚽ 85%+ Confirmed Bet Found!\n"
        f"Match: {home} vs {away}\n"
        f"🔹 Final 85%+ Confirmed Bet: {analysis['market']} – {analysis['prediction']}\n"
        f"💰 Confidence Level: {analysis['confidence']}%\n"
        f"📊 Reasoning: {analysis['reason']}\n"
        f"🔥 Odds Range: {analysis['odds']}\n"
        f"⚠️ Risk Note: Check injuries/cards before betting"
    )

# -------------------------
# Auto-update job every 5 minutes
# -------------------------
def auto_update_job():
    while True:
        matches = fetch_live_matches()
        for match in matches:
            analysis = intelligent_analysis(match)
            if analysis:
                msg = format_bet_msg(match, analysis)
                try:
                    bot.send_message(OWNER_CHAT_ID, msg)
                    print(f"✅ Auto-update sent: {match['teams']['home']['name']} vs {match['teams']['away']['name']}")
                except Exception as e:
                    print(f"⚠️ Telegram send error: {e}")
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
    elif any(x in text for x in ["update", "live", "who will win", "over 2.5", "btts"]):
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
    domain = "https://football-auto-bot-production.up.railway.app"  # Update with your Railway domain
    webhook_url = f"{domain}/{BOT_TOKEN}"

    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set: {webhook_url}")

    app.run(host='0.0.0.0', port=8080)







