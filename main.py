import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask
import logging
import random

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
    logger.error("BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("OWNER_CHAT_ID not found") 
if not SPORTMONKS_API:
    logger.error("API_KEY not found")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except (ValueError, TypeError):
    logger.error("Invalid OWNER_CHAT_ID")

logger.info("Environment variables loaded")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route("/")
def health():
    return "⚽ Football Bot is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

# Simple prediction function (no numpy/scikit-learn dependency)
def predict_goal_chance(stats):
    """Simple goal prediction without external dependencies"""
    last_3_goals = stats["last_3_min_goals"]
    shots_on_target = stats["shots_on_target"]
    possession = stats["possession"]
    
    # Simple formula for goal chance
    base_chance = 50  # Base 50% chance
    chance = base_chance + (last_3_goals * 15) + (shots_on_target * 5) + ((possession - 50) * 0.3)
    
    # Ensure chance is between 0-100
    return max(0, min(100, chance))

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
                        "last_3_min_goals": random.randint(0, 2),
                        "shots_on_target": random.randint(0, 5),
                        "possession": random.randint(40, 60)
                    }
                })
        
        logger.info(f"Found {len(matches)} live matches")
        return matches
    except Exception as e:
        logger.error(f"Error fetching matches: {e}")
        return []

def start_bot():
    logger.info("🤖 Bot service starting...")
    
    # Send startup message
    try:
        bot.send_message(OWNER_CHAT_ID, "🤖 Bot started successfully! Monitoring for goals...")
    except Exception as e:
        logger.error(f"Startup message failed: {e}")
    
    while True:
        try:
            live_matches = fetch_live_matches()
            
            for m in live_matches:
                stats = m["stats"]
                chance = predict_goal_chance(stats)
                
                logger.info(f"Match: {m['home']} vs {m['away']} - Chance: {chance:.2f}%")
                
                if chance >= 70:  # Lowered threshold for testing
                    send_goal_alert(m["home"], m["away"], m["league"], round(chance, 2))
                    
            time.sleep(60)
        except Exception as e:
            logger.error(f"Bot loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    logger.info("🚀 Application starting...")
    
    # Start bot in background thread
    from threading import Thread
    bot_thread = Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask app
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
