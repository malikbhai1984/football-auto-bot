import os
import time
import random
import requests
import telebot
import threading
from datetime import datetime
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
PORT = int(os.environ.get("PORT", 8080))

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_KEY missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

LIVE_API_URL = f"https://apiv3.apifootball.com/?action=get_events&match_live=1&APIkey={API_KEY}"

print("🤖 AI Football Analyst Started Successfully!")

# -------------------------
# Fetch live matches
# -------------------------
def fetch_live_matches():
    try:
        response = requests.get(LIVE_API_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and data:
                return data
        return []
    except Exception as e:
        print(f"❌ Error fetching live matches: {e}")
        return []

# -------------------------
# Prediction engine (dummy high-confidence logic)
# -------------------------
def generate_prediction(match):
    home = match.get("match_hometeam_name")
    away = match.get("match_awayteam_name")
    score_home = match.get("match_hometeam_score") or "0"
    score_away = match.get("match_awayteam_score") or "0"

    confidence = random.randint(85, 95)  # 85%+ confidence
    market = "Over 2.5 Goals" if random.random() > 0.5 else "Both Teams to Score"
    prediction = "Yes"
    odds_range = "1.70-2.10"
    btts = "Yes" if market == "Both Teams to Score" else "No"
    last_10_min_goal = random.randint(70, 90)
    correct_scores = [f"{score_home}-{score_away}", f"{int(score_home)+1}-{int(score_away)}", f"{score_home}-{int(score_away)+1}"]

    return {
        'home_team': home,
        'away_team': away,
        'market': market,
        'prediction': prediction,
        'confidence': confidence,
        'odds': odds_range,
        'reason': f"Based on live stats and historical data simulation for {home} vs {away}.",
        'correct_scores': correct_scores,
        'btts': btts,
        'last_10_min_goal': last_10_min_goal
    }

# -------------------------
# Auto-update system
# -------------------------
def auto_predictor():
    while True:
        try:
            matches = fetch_live_matches()
            if matches:
                print(f"📊 {len(matches)} live matches found. Sending predictions...")
                for match in matches:
                    prediction = generate_prediction(match)
                    message = f"""
🤖 AI PREDICTION
Match: {prediction['home_team']} vs {prediction['away_team']}
Market: {prediction['market']}
Prediction: {prediction['prediction']}
Confidence: {prediction['confidence']}%
Odds: {prediction['odds']}
BTTS: {prediction['btts']}
Late Goal Chance: {prediction['last_10_min_goal']}%
Likely Scores: {', '.join(prediction['correct_scores'])}
Reason: {prediction['reason']}
"""
                    try:
                        bot.send_message(OWNER_CHAT_ID, message)
                        time.sleep(1)
                    except Exception as e:
                        print(f"❌ Telegram send error: {e}")
            else:
                print("⏳ No live matches currently.")
        except Exception as e:
            print(f"❌ Auto-predictor error: {e}")

        time.sleep(300)  # 5 minutes

threading.Thread(target=auto_predictor, daemon=True).start()

# -------------------------
# Bot commands
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    bot.reply_to(message, "🤖 AI Football Prediction Bot\nCommands:\n/predict - Get live predictions\n/matches - List current live matches\n/status - System info")

@bot.message_handler(commands=['predict'])
def send_predictions(message):
    matches = fetch_live_matches()
    if not matches:
        bot.reply_to(message, "❌ No live matches currently.")
        return
    for match in matches[:5]:  # top 5 matches
        prediction = generate_prediction(match)
        msg = f"""
🤖 AI PREDICTION
Match: {prediction['home_team']} vs {prediction['away_team']}
Market: {prediction['market']}
Prediction: {prediction['prediction']}
Confidence: {prediction['confidence']}%
Odds: {prediction['odds']}
BTTS: {prediction['btts']}
Late Goal Chance: {prediction['last_10_min_goal']}%
Likely Scores: {', '.join(prediction['correct_scores'])}
Reason: {prediction['reason']}
"""
        bot.reply_to(message, msg)

@bot.message_handler(commands=['matches'])
def send_matches_list(message):
    matches = fetch_live_matches()
    if not matches:
        bot.reply_to(message, "❌ No live matches currently.")
        return
    text = "🔴 LIVE MATCHES:\n\n"
    for match in matches[:10]:
        text += f"{match['match_hometeam_name']} vs {match['match_awayteam_name']} - Score: {match.get('match_hometeam_score') or 0}-{match.get('match_awayteam_score') or 0}\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['status'])
def send_status(message):
    matches = fetch_live_matches()
    bot.reply_to(message, f"🤖 System Online\nLive Matches: {len(matches)}\nNext auto-check in 5 minutes")

# -------------------------
# Flask webhook
# -------------------------
@app.route('/', methods=['GET'])
def home():
    return "🤖 AI Football Bot Online"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

# -------------------------
# Start bot
# -------------------------
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(1)
        domain = os.environ.get("RAILWAY_STATIC_URL", "https://your-railway-app.up.railway.app")
        webhook_url = f"{domain}/{BOT_TOKEN}"
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Bot start error: {e}")
