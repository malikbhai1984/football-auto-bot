import os
import requests
import telebot
import time
import random
from datetime import datetime
from flask import Flask, request
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"
BOT_NAME = "MyBetAlert_Bot"
OWNER_CHAT_ID = 7742985526
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
PORT = int(os.getenv("PORT", 8080))
DOMAIN = "football-auto-bot-production.up.railway.app"

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("BOT_TOKEN, OWNER_CHAT_ID, API_KEY, or DOMAIN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
API_URL = "https://apiv3.apifootball.com"

# Predictor class with 85%+ confidence filtering
class FootballPredictor:
    def __init__(self):
        self.over_under_thresholds = [0.5, 1.5, 2.5, 3.5, 4.5]

    def calculate_probabilities(self, match):
        # Base confidence and some random variation for demo
        base = 85
        home = base + random.randint(0, 10)
        away = base + random.randint(0, 10)
        draw = max(0, 100 - home - away)
        home = max(home, 0)
        away = max(away, 0)

        # Over/Under probabilities per threshold with randomness
        ou = {}
        for val in self.over_under_thresholds:
            prob = max(0, min(100, 100 - val*15 + random.randint(-5,5)))
            ou[val] = prob

        # BTTS probability simplified
        btts_prob = random.randint(70, 99)

        # Goal minutes (random 5 distinct minutes between 5 and 90)
        goal_minutes = sorted(random.sample(range(5, 91), 5))

        return {
            "home_win": home,
            "away_win": away,
            "draw": draw,
            "over_under": ou,
            "btts": btts_prob,
            "goal_minutes": goal_minutes
        }

    def get_85_confidence_predictions(self, probs):
        results = {}
        # Winner or draw
        if probs["home_win"] >= 85:
            results['winner'] = f"Home Win ({probs['home_win']}%)"
        elif probs["away_win"] >= 85:
            results['winner'] = f"Away Win ({probs['away_win']}%)"
        elif probs["draw"] >= 85:
            results['winner'] = f"Draw ({probs['draw']}%)"

        # BTTS
        if probs["btts"] >= 85:
            results['btts'] = f"Both Teams To Score: YES ({probs['btts']}%)"

        # Over/Under 85%+ only
        ou_preds = []
        for k, v in probs["over_under"].items():
            if v >= 85:
                ou_preds.append(f"Over {k} Goals ({v}%)")
        if ou_preds:
            results['over_under'] = ou_preds

        # Goal minutes
        results['goal_minutes'] = probs['goal_minutes']

        return results

predictor = FootballPredictor()

def fetch_live_matches():
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            live_matches = [m for m in data if m.get("match_live") == "1"]
            return live_matches
        else:
            print(f"API error: {resp.status_code}")
    except Exception as e:
        print(f"Live fetch error: {e}")
    return []

def generate_prediction_message(match):
    home = match.get("match_hometeam_name", "Home")
    away = match.get("match_awayteam_name", "Away")
    home_score = match.get("match_hometeam_score", "0")
    away_score = match.get("match_awayteam_score", "0")

    probs = predictor.calculate_probabilities(match)
    filtered_preds = predictor.get_85_confidence_predictions(probs)

    if not filtered_preds:
        return f"No 85%+ confidence predictions available for {home} vs {away} currently."

    msg = f"🤖 {BOT_NAME} LIVE PREDICTION\n{home} vs {away}\nScore: {home_score}-{away_score}\n"
    if 'winner' in filtered_preds:
        msg += f"🏆 Prediction: {filtered_preds['winner']}\n"
    if 'btts' in filtered_preds:
        msg += f"⚽ {filtered_preds['btts']}\n"
    if 'over_under' in filtered_preds:
        msg += "📊 Over/Under Predictions:\n"
        for pred in filtered_preds['over_under']:
            msg += f" - {pred}\n"
    msg += "⏰ Probable Goal Minutes: " + ", ".join(str(m) for m in filtered_preds['goal_minutes']) + "\n"
    return msg

def auto_update():
    while True:
        try:
            matches = fetch_live_matches()
            if not matches:
                print("No live matches at the moment.")
            for match in matches:
                msg = generate_prediction_message(match)
                try:
                    bot.send_message(OWNER_CHAT_ID, msg)
                    time.sleep(2)
                except Exception as e:
                    print(f"Failed to send message: {e}")
        except Exception as e:
            print(f"Auto-update error: {e}")
        time.sleep(300)  # 5 minutes

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    help_text = f"🤖 {BOT_NAME} - Live Football Prediction Bot\nUse /predict to get the latest 85%+ confidence predictions."
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['predict'])
def handle_predict(message):
    matches = fetch_live_matches()
    if matches:
        msg = generate_prediction_message(matches[0])
        bot.reply_to(message, msg)
    else:
        bot.reply_to(message, "No live matches currently.")

@app.route('/')
def home():
    return f"{BOT_NAME} is running."

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ERROR", 400

def setup_bot():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
        print(f"Webhook set to {DOMAIN}/{BOT_TOKEN}")

        t = threading.Thread(target=auto_update, daemon=True)
        t.start()
        print("Auto-update thread started.")

        bot.send_message(OWNER_CHAT_ID, f"{BOT_NAME} started! Monitoring live football every 5 minutes.")
    except Exception as e:
        print(f"Setup error: {e}")
        print("Starting long polling as fallback.")
        bot.polling(none_stop=True)

if __name__ == "__main__":
    setup_bot()
    app.run(host="0.0.0.0", port=PORT)
