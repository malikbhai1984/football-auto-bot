import os
import requests
import numpy as np
import telebot
from dotenv import load_dotenv
from sklearn.linear_model import LogisticRegression
import time
from flask import Flask
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")

# Validate environment variables
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found in environment variables")
if not OWNER_CHAT_ID:
    logger.error("OWNER_CHAT_ID not found in environment variables")
if not SPORTMONKS_API:
    logger.error("API_KEY not found in environment variables")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except (ValueError, TypeError):
    logger.error("Invalid OWNER_CHAT_ID. Must be a valid integer.")

logger.info("Environment variables loaded successfully")

bot = telebot.TeleBot(BOT_TOKEN)

# Flask app
app = Flask(__name__)

@app.route("/")
def health():
    return "Bot is running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

# ML Model
try:
    logger.info("Training ML model...")
    ml_model = LogisticRegression(random_state=42)
    X_dummy = np.random.rand(50, 3)
    y_dummy = np.random.randint(0, 2, 50)
    ml_model.fit(X_dummy, y_dummy)
    logger.info("ML model trained successfully")
except Exception as e:
    logger.error(f"ML model training failed: {e}")
    ml_model = None

# Leagues IDs
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 2, 3, 8]
WC_QUALIFIERS_IDS = [159, 160, 161]
LEAGUES_IDS = TOP_LEAGUES_IDS + WC_QUALIFIERS_IDS

def send_goal_alert(home, away, league, chance):
    message = f"🔥 GOAL ALERT 🔥\nLeague: {league}\nMatch: {home} vs {away}\nChance: {chance}%"
    try:
        bot.send_message(OWNER_CHAT_ID, message)
        logger.info(f"Alert sent: {home} vs {away}")
    except Exception as e:
        logger.error(f"Telegram error: {e}")

def fetch_live_matches():
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("Fetching live matches...")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        matches = []

        for match in data.get("data", []):
            league_id = match.get("league_id")
            if league_id in LEAGUES_IDS:
                participants = match.get("participants", [])
                home_team = "Unknown Home"
                away_team = "Unknown Away"
                
                if len(participants) >= 2:
                    home_team = participants[0].get("name", "Unknown Home")
                    away_team = participants[1].get("name", "Unknown Away")
                
                league_data = match.get("league", {})
                league_name = league_data.get("name", "Unknown League")

                matches.append({
                    "home": home_team,
                    "away": away_team,
                    "league": league_name,
                    "stats": {
                        "last_3_min_goals": np.random.randint(0, 2),
                        "shots_on_target": np.random.randint(0, 5),
                        "possession": np.random.randint(40, 60)
                    }
                })
        
        logger.info(f"Found {len(matches)} live matches")
        return matches
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching matches: {e}")
        return []

def start_bot():
    logger.info("Bot service starting...")
    
    # Send startup message
    try:
        bot.send_message(OWNER_CHAT_ID, "🤖 Bot started successfully! Monitoring for goals...")
    except Exception as e:
        logger.error(f"Startup message failed: {e}")
    
    while True:
        try:
            live_matches = fetch_live_matches()
            
            for m in live_matches:
                if ml_model is None:
                    continue
                    
                stats = m["stats"]
                X = np.array([[stats["last_3_min_goals"], stats["shots_on_target"], stats["possession"]]])
                
                try:
                    chance = ml_model.predict_proba(X)[0][1] * 100
                    logger.info(f"Match: {m['home']} vs {m['away']} - Chance: {chance:.2f}%")
                    
                    if chance >= 80:
                        send_goal_alert(m["home"], m["away"], m["league"], round(chance, 2))
                except Exception as e:
                    logger.error(f"Prediction error: {e}")
                    
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Bot loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    logger.info("Application starting...")
    
    # Start bot in background thread
    from threading import Thread
    bot_thread = Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask app
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
