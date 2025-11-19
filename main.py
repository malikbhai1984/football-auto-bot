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

BOT_TOKEN = os.environ.get("8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as")           # From Railway
OWNER_CHAT_ID = os.environ.get("7742985526")   # From Railway
API_KEY = os.environ.get("839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325")               # From Railway
DOMAIN = os.environ.get("DOMAIN")                 # From Railway
BOT_NAME = os.environ.get("BOT_NAME")             # Optional – Not required

PORT = int(os.environ.get("PORT", 8080))

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ Missing required environment variables!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

API_URL = "https://apiv3.apifootball.com"


# Fetch live matches
def fetch_live_matches():
    try:
        url = (
            f"{API_URL}/?action=get_events&APIkey={API_KEY}&"
            f"from={datetime.now().strftime('%Y-%m-%d')}&"
            f"to={datetime.now().strftime('%Y-%m-%d')}"
        )
        resp = requests.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            return [m for m in data if m.get("match_live") == "1"]

        print("❌ API Error:", resp.status_code)
        return []

    except Exception as e:
        print(f"❌ Live fetch error: {e}")
        return []


# Make probability predictions
def calculate_probabilities(match):
    base = 85
    home_win = min(95, base + random.randint(0, 15))
    away_win = max(5, 100 - home_win - 5)
    draw = 100 - home_win - away_win

    ou = {
        0.5: min(95, home_win + random.randint(-5, 5)),
        1.5: min(95, home_win - 3 + random.randint(-5, 5)),
        2.5: min(90, home_win - 10 + random.randint(-5, 5)),
        3.5: min(85, home_win - 15 + random.randint(-5, 5)),
        4.5: min(80, home_win - 20 + random.randint(-5, 5)),
    }

    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "over_under": ou,
        "btts": "Yes" if random.randint(0, 100) > 30 else "No",
        "last_10_min": random.randint(60, 90),
        "correct_scores": [
            f"{home_win//10}-{away_win//10}",
            f"{home_win//10 + 1}-{away_win//10}"
        ],
        "goal_minutes": random.sample(range(5, 95), 5)
    }


# Build prediction message
def generate_prediction(match):
    home = match.get("match_hometeam_name")
    away = match.get("match_awayteam_name")
    hs = match.get("match_hometeam_score") or "0"
    ascore = match.get("match_awayteam_score") or "0"

    p = calculate_probabilities(match)

    msg = (
        f"🤖 LIVE PREDICTION\n"
        f"{home} vs {away}\n"
        f"Score: {hs}-{ascore}\n"
        f"Home Win: {p['home_win']}% | Draw: {p['draw']}% | Away Win: {p['away_win']}%\n"
        f"📊 Over/Under:\n"
    )

    for k, v in p["over_under"].items():
        msg += f" - Over {k}: {v}%\n"

    msg += (
        f"BTTS: {p['btts']}\n"
        f"Last 10-min Goal Chance: {p['last_10_min']}%\n"
        f"Correct Scores: {', '.join(p['correct_scores'])}\n"
        f"Goal Minutes: {', '.join(map(str, p['goal_minutes']))}\n"
    )

    return msg


# Auto-update loop
def auto_update():
    while True:
        try:
            matches = fetch_live_matches()
            if matches:
                for m in matches:
                    bot.send_message(OWNER_CHAT_ID, generate_prediction(m))
                    time.sleep(2)
            else:
                print("⏳ No live matches.")
        except Exception as e:
            print("❌ Auto-update error:", e)

        time.sleep(300)


# Telegram commands
@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.reply_to(message, "🤖 Bot is active! Use /predict to get live predictions.")

@bot.message_handler(commands=['predict'])
def predict(message):
    matches = fetch_live_matches()
    if matches:
        bot.reply_to(message, generate_prediction(matches[0]))
    else:
        bot.reply_to(message, "⏳ No live matches right now.")


# Flask webhook
@app.route('/')
def home():
    return "Football Bot Running!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
    except Exception as e:
        print("❌ Webhook error:", e)
    return "OK", 200


# Setup bot
def setup_bot():
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
    print("✅ Webhook set:", f"{DOMAIN}/{BOT_TOKEN}")

    threading.Thread(target=auto_update, daemon=True).start()
    bot.send_message(OWNER_CHAT_ID, "🤖 Football Bot Started & Monitoring Live Matches.")


# Run
if __name__ == '__main__':
    setup_bot()
    app.run(host='0.0.0.0', port=PORT)
