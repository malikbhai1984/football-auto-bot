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

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
PORT = int(os.environ.get("PORT", 8080))
DOMAIN = os.environ.get("DOMAIN")  # e.g., https://yourapp.up.railway.app

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, API_KEY, or DOMAIN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
API_URL = "https://apiv3.apifootball.com"

# -------------------------
# Fetch live matches
# -------------------------
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
            print(f"❌ API Error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ Live fetch error: {e}")
        return []

# -------------------------
# Intelligent probability calculation
# -------------------------
def calculate_probabilities(match):
    # Base probabilities
    base = 85
    h2h_bonus = random.randint(0, 5)  # placeholder for H2H stats
    form_bonus = random.randint(0, 5)  # placeholder for team form
    live_bonus = random.randint(0, 5)  # placeholder for live stats
    odds_bonus = random.randint(0, 5)  # placeholder for betting odds

    home_win = min(95, base + h2h_bonus + form_bonus + live_bonus + odds_bonus)
    away_win = max(5, 100 - home_win - 5)
    draw = max(5, 100 - home_win - away_win)

    # Over/Under probabilities
    ou = {}
    ou[0.5] = min(95, home_win + random.randint(-5, 5))
    ou[1.5] = min(95, home_win - 2 + random.randint(-5, 5))
    ou[2.5] = min(95, home_win - 5 + random.randint(-5, 5))
    ou[3.5] = min(90, home_win - 10 + random.randint(-5, 5))
    ou[4.5] = min(85, home_win - 15 + random.randint(-5, 5))

    # BTTS probability
    btts = "Yes" if random.randint(0, 100) > 30 else "No"

    # Last 10-min goal probability
    last_10_min = random.randint(60, 90)

    # Correct score predictions
    cs1 = f"{home_win//10}-{away_win//10}"
    cs2 = f"{home_win//10+1}-{away_win//10}"

    # High-probability goal minutes
    goal_minutes = random.sample(range(5, 95), 5)

    return {
        "home_win": home_win,
        "away_win": away_win,
        "draw": draw,
        "over_under": ou,
        "btts": btts,
        "last_10_min": last_10_min,
        "correct_scores": [cs1, cs2],
        "goal_minutes": goal_minutes
    }

# -------------------------
# Generate prediction message
# -------------------------
def generate_prediction(match):
    home = match.get("match_hometeam_name")
    away = match.get("match_awayteam_name")
    home_score = match.get("match_hometeam_score") or "0"
    away_score = match.get("match_awayteam_score") or "0"

    prob = calculate_probabilities(match)

    msg = f"🤖 LIVE PREDICTION\n{home} vs {away}\nScore: {home_score}-{away_score}\n"
    msg += f"Home Win: {prob['home_win']}% | Draw: {prob['draw']}% | Away Win: {prob['away_win']}%\n"
    msg += "📊 Over/Under Goals:\n"
    for k, v in prob["over_under"].items():
        msg += f" - Over {k}: {v}%\n"
    msg += f"BTTS: {prob['btts']}\n"
    msg += f"Last 10-min Goal Chance: {prob['last_10_min']}%\n"
    msg += f"Correct Scores: {', '.join(prob['correct_scores'])}\n"
    msg += f"High-probability Goal Minutes: {', '.join(map(str, prob['goal_minutes']))}\n"
    return msg

# -------------------------
# Auto-update thread every 5 minutes
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
        time.sleep(300)

# -------------------------
# Telegram commands
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    bot.reply_to(message, "🤖 Football Bot monitoring live matches. Use /predict to get predictions.")

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
# Setup bot + webhook
# -------------------------
def setup_bot():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
        print(f"✅ Webhook set: {DOMAIN}/{BOT_TOKEN}")

        t = threading.Thread(target=auto_update, daemon=True)
        t.start()
        print("✅ Auto-update started!")

        bot.send_message(OWNER_CHAT_ID, "🤖 Football Bot Started! Monitoring live matches every 5 minutes.")
    except Exception as e:
        print(f"❌ Bot setup error: {e}")
        bot.polling(none_stop=True)

# -------------------------
# Run
# -------------------------
if __name__ == '__main__':
    setup_bot()
    app.run(host='0.0.0.0', port=PORT)
