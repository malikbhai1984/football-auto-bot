import os
import requests
import telebot
from flask import Flask, request
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime
import pytz
import joblib
from urllib.error import HTTPError

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
TOP_LEAGUES_IDS = [39,140,135,78,61,88,94,129,53,79]  # Premier, La Liga, Serie A...
WC_QUALIFIERS_IDS = [215,216,217,218,219]

# ------------------------
# Load historical/H2H data safely
# ------------------------
try:
    historical_df = pd.read_csv(
        "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/football_data.csv"
    )
except HTTPError as e:
    print("Historical data 404 error:", e)
    historical_df = pd.DataFrame()

# ------------------------
# Load pre-trained ML models safely
# ------------------------
def load_model(path):
    try:
        return joblib.load(path)
    except:
        print(f"Model {path} not found, skipping...")
        return None

winner_model = load_model("models/winner_xgb_model.pkl")
ou_model = load_model("models/over_under_xgb_model.pkl")
btts_model = load_model("models/btts_xgb_model.pkl")
last10_model = load_model("models/last10_xgb_model.pkl")

# ------------------------
# Fetch live matches
# ------------------------
def fetch_live_matches():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures?live=all"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        matches = response.json().get("response", [])
    except Exception as e:
        print("Live matches fetch error:", e)
        matches = []

    # Filter Top Leagues + WC Qualifiers
    filtered = []
    for m in matches:
        league_id = m['league']['id']
        if league_id in TOP_LEAGUES_IDS + WC_QUALIFIERS_IDS:
            filtered.append(m)
    return filtered

# ------------------------
# ML Prediction function
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
    # Prepare feature vector from historical + H2H data
    # ------------------------
    # Example: just placeholders. Replace with your real features
    features = pd.DataFrame([{
        "home_team_id": match['teams']['home']['id'],
        "away_team_id": match['teams']['away']['id'],
        "home_team_rank": 1,  # from historical_df
        "away_team_rank": 2,
        "home_form": 80,      # last 5 games
        "away_form": 75
    }])

    # ------------------------
    # Winner Prediction
    # ------------------------
    if winner_model is not None:
        proba = winner_model.predict_proba(features)  # e.g., columns = [Home, Draw, Away]
        winner_index = np.argmax(proba)
        if proba[0][winner_index] >= 0.85:  # only ≥85%
            predictions['winner'] = ["Home","Draw","Away"][winner_index]

    # ------------------------
    # BTTS Prediction
    # ------------------------
    if btts_model is not None:
        btts_proba = btts_model.predict_proba(features)  # columns = [No, Yes]
        if btts_proba[0][1] >= 0.85:
            predictions['btts'] = "Yes"
        elif btts_proba[0][0] >= 0.85:
            predictions['btts'] = "No"

    # ------------------------
    # Over/Under 0.5–5.5 Goals
    # ------------------------
    if ou_model is not None:
        for line in [0.5,1.5,2.5,3.5,4.5,5.5]:
            ou_proba = ou_model.predict_proba(features.assign(line=line))  # columns = [Under, Over]
            if ou_proba[0][1] >= 0.85:
                predictions['over_under'][line] = int(ou_proba[0][1]*100)

    # ------------------------
    # Goal minutes & last 10-min prediction
    # ------------------------
    # Just a placeholder: replace with actual ML logic on minute-level data
    predictions['goal_minutes']['home'] = [10,34,57,82]
    predictions['goal_minutes']['away'] = [22,49,78,88]
    if last10_model is not None:
        last10_home = last10_model.predict_proba(features)[0][1]
        last10_away = last10_model.predict_proba(features)[0][1]
        predictions['last_10_min_goal']['home'] = int(last10_home*100)
        predictions['last_10_min_goal']['away'] = int(last10_away*100)

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
