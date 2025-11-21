import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask
import logging
import random
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")

logger.info(f"BOT_TOKEN: {BOT_TOKEN}")
logger.info(f"OWNER_CHAT_ID: {OWNER_CHAT_ID}")
logger.info(f"SPORTMONKS_API: {SPORTMONKS_API}")

# Validate environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found") 
if not SPORTMONKS_API:
    logger.error("❌ API_KEY not found")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
    logger.info(f"✅ OWNER_CHAT_ID converted to int: {OWNER_CHAT_ID}")
except (ValueError, TypeError) as e:
    logger.error(f"❌ Invalid OWNER_CHAT_ID: {e}")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route("/")
def health():
    return "⚽ Advanced Betting Bot is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

# Simple function to send test message
def send_test_message():
    try:
        message = f"🤖 **Bot Test Message**\n\n✅ Bot successfully started!\n🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n📡 Status: Running and monitoring matches\n\n🔜 First analysis in 30 seconds..."
        bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
        logger.info("✅ Test message sent successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send test message: {e}")
        return False

# Simple match analysis
def analyze_matches():
    try:
        # Simulate some matches for testing
        test_matches = [
            {
                "home": "Manchester City",
                "away": "Liverpool", 
                "league": "Premier League",
                "current_score": "1-0",
                "minute": "65"
            },
            {
                "home": "Real Madrid",
                "away": "Barcelona",
                "league": "La Liga", 
                "current_score": "2-1",
                "minute": "70"
            }
        ]
        
        for match in test_matches:
            chance = random.randint(75, 95)
            if chance >= 80:
                message = f"🎯 **GOAL PREDICTION**\n\n⚽ {match['home']} vs {match['away']}\n🏆 {match['league']}\n📊 {match['current_score']} ({match['minute']}')\n✅ Chance: {chance}%\n💰 Bet: YES - Goal in last 10 min"
                bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
                logger.info(f"✅ Prediction sent: {match['home']} vs {match['away']}")
        
        return len(test_matches)
    except Exception as e:
        logger.error(f"❌ Error in analyze_matches: {e}")
        return 0

def start_bot():
    logger.info("🚀 Starting bot service...")
    
    # Wait a bit for everything to initialize
    time.sleep(10)
    
    # Send startup message
    logger.info("📤 Sending startup message...")
    if send_test_message():
        logger.info("✅ Startup message sent successfully")
    else:
        logger.error("❌ Failed to send startup message")
    
    # Main loop
    counter = 0
    while True:
        try:
            counter += 1
            logger.info(f"🔄 Bot loop iteration {counter}")
            
            # Analyze matches every 2 minutes for testing
            matches_analyzed = analyze_matches()
            logger.info(f"📊 Analyzed {matches_analyzed} matches")
            
            # Send status update every 5 iterations
            if counter % 5 == 0:
                status_msg = f"📊 **Bot Status Update**\n\n🔄 Iterations: {counter}\n🕒 Last check: {datetime.now().strftime('%H:%M:%S')}\n✅ Bot is running smoothly\n\nNext update in 2 minutes..."
                bot.send_message(OWNER_CHAT_ID, status_msg, parse_mode='Markdown')
            
            # Wait 2 minutes
            logger.info("⏰ Waiting 2 minutes...")
            time.sleep(120)
            
        except Exception as e:
            logger.error(f"❌ Bot loop error: {e}")
            time.sleep(120)

if __name__ == "__main__":
    logger.info("🎯 Starting Advanced Betting Bot Application...")
    
    # Start bot in background thread
    from threading import Thread
    bot_thread = Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logger.info("✅ Bot thread started")
    
    # Start Flask app
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
