import os
import requests
import telebot
from flask import Flask, request
from dotenv import load_dotenv
from datetime import datetime, timedelta
import threading
import time
import schedule

# Load environment variables
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
DOMAIN = os.environ.get("DOMAIN")
PORT = int(os.environ.get("PORT", 5000))

if not all([BOT_TOKEN, OWNER_CHAT_ID, DOMAIN]):
    raise ValueError("BOT_TOKEN, OWNER_CHAT_ID, and DOMAIN must be set in environment")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

API_URL = "https://apiv3.apifootball.com"
API_KEY = os.environ.get("API_KEY") or "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

TARGET_LEAGUES = {
    "152": "🏴 Premier League",
    "302": "🇪🇸 La Liga",
    "207": "🇮🇹 Serie A",
    "168": "🇩🇪 Bundesliga",
    "176": "🇫🇷 Ligue 1",
    "262": "⭐ Champions League",
    "263": "🌍 Europa League",
    "5": "🌎 World Cup Qualifiers",
}

api_hits = 0

def safe_api_call(url):
    global api_hits
    try:
        api_hits += 1
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []
        print(f"API error: Status {response.status_code}")
        return []
    except Exception as e:
        print(f"API call error: {e}")
        return []

def get_matches(statuses):
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
    data = safe_api_call(url)
    return [
        m for m in data
        if str(m.get("league_id")) in TARGET_LEAGUES and m.get("match_status") in statuses
    ]

def format_match(m):
    home = m.get("match_hometeam_name", "Home")
    away = m.get("match_awayteam_name", "Away")
    score = f"{m.get('match_hometeam_score', 0)}-{m.get('match_awayteam_score', 0)}"
    status = m.get("match_status", "NS")
    league = TARGET_LEAGUES.get(str(m.get("league_id")), "Unknown League")
    time_str = m.get("match_time") or ""
    return f"{home} {score} {away} | {status} | {league} | {time_str}"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_data = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Football Telegram Bot is running."

@bot.message_handler(commands=["start", "help"])
def welcome(message):
    txt = (
        "👋 Welcome to Football Bot!

"
        "Available commands:
"
        "/today - Today's matches
"
        "/live - Live matches
"
        "/upcoming - Upcoming matches
"
        "/predict - Simple match predictions
"
        "/stats - Bot stats

"
        "Type a command to get started!"
    )
    bot.reply_to(message, txt)

@bot.message_handler(commands=["today"])
def today_handler(message):
    matches = get_matches(["", "HT", "1H", "2H", "FT"])
    if not matches:
        bot.reply_to(message, "No matches today.")
        return
    res = "📅 Today's Matches:

" + "
".join(format_match(m) for m in matches[:15])
    bot.reply_to(message, res)

@bot.message_handler(commands=["live"])
def live_handler(message):
    matches = get_matches(["1", "2", "3", "4", "HT"])
    if not matches:
        bot.reply_to(message, "No live matches currently.")
        return
    res = "🔴 Live Matches:

" + "
".join(format_match(m) for m in matches[:15])
    bot.reply_to(message, res)

@bot.message_handler(commands=["upcoming"])
def upcoming_handler(message):
    matches = get_matches([""])
    if not matches:
        bot.reply_to(message, "No upcoming matches today.")
        return
    res = "🕒 Upcoming Matches:

" + "
".join(format_match(m) for m in matches[:15])
    bot.reply_to(message, res)

@bot.message_handler(commands=["predict"])
def predict_handler(message):
    matches = get_matches([""])
    if not matches:
        bot.reply_to(message, "No matches to predict.")
        return
    results = []
    for m in matches[:5]:
        home = m.get("match_hometeam_name", "Home")
        away = m.get("match_awayteam_name", "Away")
        pred = f"{home} likely to win"  # placeholder simple prediction
        results.append(f"{home} vs {away}
Prediction: {pred}")
    bot.reply_to(message, "

".join(results))

@bot.message_handler(commands=["stats"])
def stats_handler(message):
    txt = (
        f"📊 Bot Stats:
"
        f"API Calls: {api_hits}
"
        f"Leagues Tracked: {', '.join(TARGET_LEAGUES.values())}
"
        f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"
        f"Status: Online"
    )
    bot.reply_to(message, txt)

def setup_webhook():
    url = f"{DOMAIN}/{BOT_TOKEN}"
    bot.remove_webhook()
    if bot.set_webhook(url):
        print(f"Webhook set to {url}")
    else:
        print("Failed to set webhook")

def run_scheduler():
    def send_predictions():
        try:
            matches = get_matches([""])
            if matches:
                text = "Scheduled Predictions:

"
                text += "

".join(
                    f"{m.get('match_hometeam_name')} vs {m.get('match_awayteam_name')}
Prediction: Home win"
                    for m in matches[:5]
                )
                bot.send_message(OWNER_CHAT_ID, text)
                print("Sent scheduled predictions")
        except Exception as e:
            print(f"Error sending scheduled predictions: {e}")

    schedule.every(10).minutes.do(send_predictions)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    setup_webhook()
    thread = threading.Thread(target=run_scheduler)
    thread.daemon = True
    thread.start()
    app.run(host="0.0.0.0", port=PORT)
