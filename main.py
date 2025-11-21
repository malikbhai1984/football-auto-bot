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

BOT_NAME = os.getenv("BOT_NAME", "MyBetAlert_Bot")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", 0))
API_KEY = os.getenv("API_KEY")
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.environ.get("PORT", 8080))

# -------- FIXED INDENTATION ----------
if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, API_KEY, or DOMAIN missing!")

# Bot + Flask initialization
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)     # ❌ FIXED: name → __name__

API_URL = "https://apiv3.apifootball.com"

# -------------------------
# Fetch live matches
# -------------------------
def fetch_live_matches():
    try:
        url = (
            f"{API_URL}/?action=get_events&APIkey={API_KEY}"
            f"&from={datetime.now().strftime('%Y-%m-%d')}"
            f"&to={datetime.now().strftime('%Y-%m-%d')}"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [m for m in data if m.get("match_live") == "1"]
        else:
            print(f"❌ API Error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ Live fetch error: {e}")
        return []

# -------------------------
# Prediction engine
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
        0.5: min(95, home_win + random.randint(-5, 5)),
        1.5: min(95, home_win + random.randint(-5, 5)),
        2.5: min(90, home_win + random.randint(-5, 5)),
        3.5: min(85, home_win + random.randint(-5, 5)),
        4.5: min(80, home_win + random.randint(-5, 5)),
    }

    btts = "Yes" if random.randint(0, 100) > 30 else "No"
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
        "goal_minutes": goal_minutes,
    }

def generate_prediction(match):
    home = match.get("match_hometeam_name")
    away = match.get("match_awayteam_name")
    home_score = match.get("match_hometeam_score") or "0"
    away_score = match.get("match_awayteam_score") or "0"

    prob = calculate_probabilities(match)

    msg = (
        f"🤖 {BOT_NAME} LIVE PREDICTION\n"
        f"{home} vs {away}\n"
        f"Score: {home_score}-{away_score}\n"
        f"Home Win: {prob['home_win']}% | Draw: {prob['draw']}% | Away Win: {prob['away_win']}%\n"
        "📊 Over/Under Goals:\n"
    )
    for k, v in prob["over_under"].items():
        msg += f" - Over {k}: {v}%\n"

    msg += (
        f"BTTS: {prob['btts']}\n"
        f"Last 10-min Goal Chance: {prob['last_10_min']}%\n"
        f"Correct Scores: {', '.join(prob['correct_scores'])}\n"
        f"High-probability Goal Minutes: {', '.join(map(str, prob['goal_minutes']))}\n"
    )

    return msg

# -------------------------
# Auto-update thread
# -------------------------
def auto_update():
    while True:
        try:
            matches = fetch_live_matches()
            if matches:
                for match in matches:
                    msg = generate_prediction(match)
                    try:
                        bot.send_message(OWNER_CHAT_ID, msg)
                        time.sleep(2)
                    except Exception as e:
                        print(f"❌ Send message error: {e}")
            else:
                print("⏳ No live matches currently.")

        except Exception as e:
            print(f"❌ Auto-update error: {e}")

        time.sleep(300)  # every 5 minutes

# -------------------------
# Telegram commands
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    bot.reply_to(message, f"🤖 {BOT_NAME} monitoring live matches. Use /predict to get predictions.")

@bot.message_handler(commands=['predict'])
def send_predictions(message):
    matches = fetch_live_matches()
    if matches:
        msg = generate_prediction(matches[0])
        bot.reply_to(message, msg)
    else:
        bot.reply_to(message, "⏳ No live matches currently.")

# -------------------------
# Flask webhook
# -------------------------
@app.route('/')
def home():
    return "Football Bot Running!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return 'ERROR', 400

# -------------------------
# Bot setup
# -------------------------
def setup_bot():
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
    print(f"✅ Webhook set: {DOMAIN}/{BOT_TOKEN}")

    threading.Thread(target=auto_update, daemon=True).start()
    print("✅ Auto-update started!")

    bot.send_message(OWNER_CHAT_ID, f"🤖 {BOT_NAME} Started! Monitoring live matches every 5 minutes.")
    print("✅ Test message sent successfully!")

# -------------------------
# Run
# -------------------------
setup_bot()

# ❌ FIXED — name → __name__
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
