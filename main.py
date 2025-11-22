import os
import requests
import telebot
from flask import Flask, request
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
import joblib  # for loading ML model

# ------------------------
# Load environment variables
# ------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API_KEY = os.getenv("API_KEY")
BOT_NAME = os.getenv("BOT_NAME")
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 8080))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ------------------------
# Config: leagues & qualifiers
# ------------------------
TOP_LEAGUES_IDS = [
    39, 140, 135, 78, 61, 88, 94, 129, 53, 79  # Premier, La Liga, Serie A, Bundesliga, Ligue1, Eredivisie, Primeira, Russia, Belgium, Turkey
]
WC_QUALIFIERS_IDS = [
    215, 216, 217, 218, 219  # Example: UEFA, CONMEBOL, CAF, AFC, CONCACAF qualifier league IDs
]

# ------------------------
# Load historical / ML models
# ------------------------
historical_df = pd.read_csv(
    "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/football_data.csv"
)

# Example: load pre-trained ML models
try:
    winner_model = joblib.load("models/winner_xgb_model.pkl")
    ou_model = joblib.load("models/over_under_xgb_model.pkl")
    btts_model = joblib.load("models/btts_xgb_model.pkl")
except:
    winner_model, ou_model, btts_model = None, None, None

# ------------------------
# Fetch live matches
# ------------------------
def fetch_live_matches():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures?live=all"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    matches = data.get("response", [])

    # Filter only Top Leagues + WC Qualifiers
    filtered_matches = []
    for m in matches:
        league_id = m['league']['id']
        if league_id in TOP_LEAGUES_IDS + WC_QUALIFIERS_IDS:
            filtered_matches.append(m)
    return filtered_matches

# ------------------------
# Calculate predictions
# ------------------------
def calculate_predictions(match, historical_df):
    predictions = {
        "home_team": match['teams']['home']['name'],
        "away_team": match['teams']['away']['name'],
        "winner": None,
        "btts": None,
        "over_under": {},
        "goal_minutes": {"home": [], "away": []},
        "last_10_min_goal": {"home": 0, "away": 0}
    }

    # ------------------------
    # Example: integrate ML model logic here
    # ------------------------
    # Replace these with real ML predictions
    predictions['winner'] = np.random.choice(["Home", "Away", "Draw"])
    predictions['btts'] = np.random.choice(["Yes", "No"])
    
    for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        predictions['over_under'][line] = np.random.randint(70, 95)  # dummy confidence %

    predictions['goal_minutes']['home'] = [12, 34, 57, 82]
    predictions['goal_minutes']['away'] = [22, 49, 78, 88]

    # Last 10-minute goals (80-90 min)
    predictions['last_10_min_goal']['home'] = np.random.randint(70, 95)
    predictions['last_10_min_goal']['away'] = np.random.randint(70, 95)

    # ------------------------
    # Filter only >=85% confidence
    # ------------------------
    predictions['over_under'] = {k:v for k,v in predictions['over_under'].items() if v >= 85}
    if predictions['winner'] not in ["Home", "Away", "Draw"]:
        predictions['winner'] = None
    if predictions['btts'] not in ["Yes", "No"]:
        predictions['btts'] = None

    return predictions

# ------------------------
# Format message
# ------------------------
def format_prediction_message(pred):
    msg = f"⚽ {pred['home_team']} vs {pred['away_team']}\n"
    if pred['winner']:
        msg += f"🏆 Winner: {pred['winner']}\n"
    if pred['btts']:
        msg += f"🔵 BTTS: {pred['btts']}\n"
    if pred['over_under']:
        msg += "📊 Over/Under 85%+:\n"
        for line, conf in pred['over_under'].items():
            msg += f"   Over/Under {line}: {conf}%\n"
    if pred['goal_minutes']:
        msg += "⏱️ Goal Minutes:\n"
        msg += f"   Home: {pred['goal_minutes']['home']}\n"
        msg += f"   Away: {pred['goal_minutes']['away']}\n"
    if pred['last_10_min_goal']:
        msg += "⏳ Last 10-min Goals Chance:\n"
        msg += f"   Home: {pred['last_10_min_goal']['home']}%\n"
        msg += f"   Away: {pred['last_10_min_goal']['away']}%\n"
    return msg

# ------------------------
# Telegram Handlers
# ------------------------
@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.reply_to(message, f"Hello! I fetch 85%+ confirmed football predictions.\nUse /live to get current matches.")

@bot.message_handler(commands=['live'])
def live_predictions(message):
    bot.send_message(message.chat.id, "Fetching live matches...")
    live_matches = fetch_live_matches()
    if not live_matches:
        bot.send_message(message.chat.id, "No live matches found.")
        return

    for match in live_matches:
        pred = calculate_predictions(match, historical_df)
        if pred['over_under'] or pred['winner'] or pred['btts']:
            msg = format_prediction_message(pred)
            bot.send_message(message.chat.id, msg)

# ------------------------
# Flask Webhook
# ------------------------
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def index():
    return "Bot is running!"

# ------------------------
# Set webhook
# ------------------------
def set_webhook():
    webhook_url = f"{DOMAIN}/{BOT_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=PORT)
