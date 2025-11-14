import os
import requests
import telebot
from flask import Flask, request
from datetime import datetime
from dotenv import load_dotenv
import threading

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
DOMAIN = os.environ.get("DOMAIN")
PORT = int(os.environ.get("PORT", 5000))
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
API_URL = f"https://apiv3.apifootball.com/?action=get_events&match_live=1&APIkey={API_KEY}"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Top 7 Leagues + World Cup Qualifiers league IDs
TARGET_LEAGUES = {
    "152": "Premier League",
    "302": "La Liga",
    "207": "Serie A",
    "168": "Bundesliga",
    "176": "Ligue 1",
    "262": "Champions League",
    "263": "Europa League",
    "5": "World Cup Qualifiers"
}

def fetch_live_top_leagues_matches():
    try:
        resp = requests.get(API_URL, timeout=10)
        data = resp.json()
        # Filter matches to those in target leagues
        matches = [m for m in data if str(m.get("league_id")) in TARGET_LEAGUES]
        return matches
    except Exception as e:
        print(f"API fetch error: {e}")
        return []

def simple_prediction(home_goals, away_goals, home_team, away_team):
    home_goals = int(home_goals) if home_goals else 0
    away_goals = int(away_goals) if away_goals else 0
    if home_goals > away_goals:
        return f"Prediction: {home_team} to win"
    elif away_goals > home_goals:
        return f"Prediction: {away_team} to win"
    else:
        return "Prediction: Draw"

def format_match_info(match):
    home = match.get("match_hometeam_name", "Home")
    away = match.get("match_awayteam_name", "Away")
    home_score = match.get("match_hometeam_score", "0")
    away_score = match.get("match_awayteam_score", "0")
    league_name = TARGET_LEAGUES.get(str(match.get("league_id")), "Unknown League")
    pred = simple_prediction(home_score, away_score, home, away)
    return f"{home} vs {away}
Score: {home_score}-{away_score}
League: {league_name}
{pred}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = ("👋 Welcome to Football Bot ⚽

"
                    "Commands:
"
                    "/live - Show live matches and predictions
"
                    "/help - This help message")
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['live'])
def send_live_matches(message):
    matches = fetch_live_top_leagues_matches()
    if not matches:
        bot.reply_to(message, "No live matches right now in target leagues.")
        return
    messages = [format_match_info(m) for m in matches[:10]]
    reply = "🔴 Live Matches:

" + "

".join(messages)
    bot.reply_to(message, reply)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Football Telegram Bot running"

def set_webhook():
    webhook_url = f"{DOMAIN}/{BOT_TOKEN}"
    bot.remove_webhook()
    if bot.set_webhook(webhook_url):
        print(f"Webhook set to {webhook_url}")
    else:
        print("Webhook setup failed")

if __name__ == "__main__":
    set_webhook()
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
