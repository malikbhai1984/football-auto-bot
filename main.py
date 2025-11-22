import os
import time
import requests
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from threading import Thread, Lock
from dotenv import load_dotenv
import telebot

# -------------------------
# Load Environment Variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID"))
API_KEY = os.environ.get("API_KEY")
SPORTMONKS_API = os.environ.get("SPORTMONKS_API")
BOT_NAME = os.environ.get("BOT_NAME")
PORT = int(os.environ.get("PORT", 8080))

# -------------------------
# Logger Setup
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------
# Telegram Bot
# -------------------------
bot = telebot.TeleBot(BOT_TOKEN)
message_counter = 0

def send_telegram_message(message, max_retries=3):
    global message_counter
    if not bot or not OWNER_CHAT_ID:
        logger.error("❌ Cannot send message - bot or chat ID not configured")
        return False
    for attempt in range(max_retries):
        try:
            message_counter += 1
            logger.info(f"📤 Sending message #{message_counter} (Attempt {attempt+1})")
            bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
            logger.info(f"✅ Message #{message_counter} sent successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"🚫 All {max_retries} attempts failed")
    return False

# -------------------------
# Fetch Top Leagues + WC Qualifiers
# -------------------------
TOP_LEAGUES = [39, 140, 78, 61, 135, 94, 88, 82]  # Example IDs: EPL, La Liga, Serie A, Bundesliga, Ligue 1...
WC_QUALIFIERS = [100]  # Replace with actual league ID for qualifiers

def fetch_live_matches():
    leagues = TOP_LEAGUES + WC_QUALIFIERS
    live_matches = []
    for league_id in leagues:
        url = f"https://api.sportmonks.com/v3/football/livescores/now?api_token={SPORTMONKS_API}&include=stats,localTeam,visitorTeam"
        try:
            resp = requests.get(url)
            data = resp.json()
            if "data" in data:
                for match in data['data']:
                    live_matches.append(match)
        except Exception as e:
            logger.error(f"Error fetching live matches for league {league_id}: {e}")
    logger.info(f"Fetched {len(live_matches)} live matches")
    return live_matches

# -------------------------
# Historical Data (GitHub)
# -------------------------
HISTORICAL_DATA_URL = "https://raw.githubusercontent.com/petermclagan/footballAPI/main/matches.csv"

def load_historical_data():
    try:
        df = pd.read_csv(HISTORICAL_DATA_URL)
        logger.info(f"✅ Historical data loaded: {df.shape[0]} rows")
        return df
    except Exception as e:
        logger.error(f"❌ Error loading historical data: {e}")
        return pd.DataFrame()

# -------------------------
# Prediction Logic
# -------------------------
CONFIDENCE_THRESHOLD = 0.85

def predict_match(match, historical_df):
    """Return dictionary of predictions with confidence"""
    try:
        home = match['localTeam']['data']['name']
        away = match['visitorTeam']['data']['name']

        # Filter H2H + recent form
        h2h = historical_df[
            ((historical_df['home_team'] == home) & (historical_df['away_team'] == away)) |
            ((historical_df['home_team'] == away) & (historical_df['away_team'] == home))
        ]

        if h2h.empty:
            return None

        # Example simple stats
        avg_goals = h2h['home_score'].mean() + h2h['away_score'].mean()
        over_05_conf = min(1, avg_goals / 2)  # rough approximation
        over_15_conf = min(1, avg_goals / 1.5)
        over_25_conf = min(1, avg_goals / 2.5)

        # Only send predictions with high confidence
        predictions = {}
        if over_05_conf >= CONFIDENCE_THRESHOLD:
            predictions['Over 0.5 Goals'] = round(over_05_conf, 2)
        if over_15_conf >= CONFIDENCE_THRESHOLD:
            predictions['Over 1.5 Goals'] = round(over_15_conf, 2)
        if over_25_conf >= CONFIDENCE_THRESHOLD:
            predictions['Over 2.5 Goals'] = round(over_25_conf, 2)

        if predictions:
            return {
                'match': f"{home} vs {away}",
                'predictions': predictions
            }
        return None
    except Exception as e:
        logger.error(f"❌ Prediction error for match {match}: {e}")
        return None

def format_prediction_message(pred):
    msg = f"⚽ *{pred['match']}*\n"
    for market, conf in pred['predictions'].items():
        msg += f"{market}: {conf*100:.0f}%\n"
    msg += f"🕒 Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    return msg

# -------------------------
# Main Cycle
# -------------------------
def run_bot_cycle():
    historical_df = load_historical_data()
    while True:
        live_matches = fetch_live_matches()
        for match in live_matches:
            pred = predict_match(match, historical_df)
            if pred:
                msg = format_prediction_message(pred)
                send_telegram_message(msg)
            else:
                logger.info(f"No high-confidence predictions for {match['localTeam']['data']['name']} vs {match['visitorTeam']['data']['name']}")
        logger.info("✅ Cycle complete. Waiting 7 minutes...")
        time.sleep(420)  # 7 minutes

# -------------------------
# Start Bot
# -------------------------
if __name__ == "__main__":
    logger.info("🚀 Starting MyBetAlert Bot")
    t = Thread(target=run_bot_cycle)
    t.start()
    bot.infinity_polling()
