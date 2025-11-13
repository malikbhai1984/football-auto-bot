import os
from flask import Flask, request
import telebot
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
DOMAIN = os.environ.get("DOMAIN")
PORT = int(os.environ.get("PORT", 5000))

if not all([BOT_TOKEN, OWNER_CHAT_ID, DOMAIN]):
    raise ValueError("BOT_TOKEN, OWNER_CHAT_ID, DOMAIN must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

API_URL = "https://apiv3.apifootball.com"
API_KEY = os.environ.get("API_KEY") or "YOUR_API_KEY"

TARGET_LEAGUES = {
    "5": "World Cup Qualifiers",
    "152": "Premier League",
    "302": "La Liga",
    "207": "Serie A",
    "168": "Bundesliga",
    "176": "Ligue 1"
    # Add more leagues as needed
}

def safe_api_call(url):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, list) else []
        else:
            print(f"API error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"API call exception: {e}")
        return []

def get_matches_by_status(statuses):
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
    matches = safe_api_call(url)
    filtered = []
    for m in matches:
        if str(m.get("league_id")) in TARGET_LEAGUES and m.get("match_status") in statuses:
            filtered.append(m)
    return filtered

def format_match(match):
    home = match.get("match_hometeam_name", "Home")
    away = match.get("match_awayteam_name", "Away")
    score = f"{match.get('match_hometeam_score', 0)}-{match.get('match_awayteam_score', 0)}"
    status = match.get("match_status", "")
    league = TARGET_LEAGUES.get(str(match.get("league_id")), "Unknown League")
    time = match.get("match_time") or ""
    return f"{home} {score} {away} | {status} | {league} | {time}"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running!"

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(
        message,
        "Welcome to Football Bot!
"
        "Commands:
"
        "/live - Live matches
"
        "/upcoming - Upcoming matches
"
        "/predict - Simple predictions
"
        "/stats - Bot status"
    )

@bot.message_handler(commands=["live"])
def live_matches(message):
    live = get_matches_by_status(["1", "2", "3", "4", "HT"])  # Add statuses representing live matches
    if not live:
        bot.reply_to(message, "No live matches currently.")
    else:
        texts = [format_match(m) for m in live[:10]]
        reply = "Live Matches:
" + "
".join(texts)
        bot.reply_to(message, reply)

@bot.message_handler(commands=["upcoming"])
def upcoming_matches(message):
    upcoming = get_matches_by_status([""])  # Empty string means not started
    if not upcoming:
        bot.reply_to(message, "No upcoming matches today.")
    else:
        texts = [format_match(m) for m in upcoming[:10]]
        reply = "Upcoming Matches:
" + "
".join(texts)
        bot.reply_to(message, reply)

@bot.message_handler(commands=["predict"])
def predict(message):
    # Simple dummy prediction logic for demo
    upcoming = get_matches_by_status([""])
    if not upcoming:
        bot.reply_to(message, "No matches to predict.")
    else:
        preds = []
        for m in upcoming[:5]:
            home = m.get("match_hometeam_name", "Home")
            away = m.get("match_awayteam_name", "Away")
            pred = f"{home} to win"
            preds.append(f"{home} vs {away}
Prediction: {pred}")
        bot.reply_to(message, "

".join(preds))

@bot.message_handler(commands=["stats"])
def stats(message):
    bot.reply_to(
        message,
        f"Bot is running.
Target Leagues: {', '.join(TARGET_LEAGUES.values())}
"
        f"API URL: {API_URL}"
    )

def set_webhook():
    webhook_url = f"{DOMAIN}/{BOT_TOKEN}"
    bot.remove_webhook()
    if bot.set_webhook(url=webhook_url):
        print(f"Webhook set successfully to {webhook_url}")
    else:
        print("Failed to set webhook")

if __name__ == "__main__":
    print("Starting bot...")
    set_webhook()
    app.run(host="0.0.0.0", port=PORT)
