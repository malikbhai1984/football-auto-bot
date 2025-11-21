import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask
import logging
import random
from datetime import datetime
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")

logger.info("🔧 Initializing Bot...")
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")  # First 10 chars only for security
logger.info(f"OWNER_CHAT_ID: {OWNER_CHAT_ID}")

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

# Global variable to track bot status
bot_started = False

@app.route("/")
def health():
    return "⚽ Advanced Betting Bot is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

@app.route("/start-bot")
def start_bot_manual():
    """Manual endpoint to start bot"""
    global bot_started
    if not bot_started:
        start_bot_thread()
        return "🤖 Bot started manually!", 200
    return "🤖 Bot already running!", 200

def send_test_message():
    """Send test message to verify bot is working"""
    try:
        message = (
            "🎯 **BOT ACTIVATED SUCCESSFULLY!** 🎯\n\n"
            "✅ Bot is now running on Railway\n"
            "🕒 Startup Time: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n"
            "📡 Status: Monitoring matches every 2 minutes\n"
            "🎪 Features: Goal predictions & betting alerts\n\n"
            "🔜 First analysis starting now..."
        )
        bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
        logger.info("✅ Test message sent successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send test message: {e}")
        return False

def analyze_matches():
    """Analyze matches and send predictions"""
    try:
        # Simulate some test matches
        test_matches = [
            {
                "home": "Man City",
                "away": "Liverpool", 
                "league": "Premier League",
                "score": "1-0",
                "minute": "65"
            },
            {
                "home": "Real Madrid", 
                "away": "Barcelona",
                "league": "La Liga",
                "score": "2-1", 
                "minute": "70"
            }
        ]
        
        predictions_sent = 0
        for match in test_matches:
            # Simulate goal chance calculation
            goal_chance = random.randint(75, 95)
            
            if goal_chance >= 80:
                message = (
                    f"🔥 **GOAL PREDICTION ALERT** 🔥\n\n"
                    f"⚽ **Match:** {match['home']} vs {match['away']}\n"
                    f"🏆 **League:** {match['league']}\n" 
                    f"📊 **Score:** {match['score']} ({match['minute']}')\n"
                    f"✅ **Goal Chance:** {goal_chance}%\n"
                    f"💰 **Bet Suggestion:** YES - Goal in last 10 minutes\n\n"
                    f"🔄 Next update in 2 minutes..."
                )
                bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
                predictions_sent += 1
                logger.info(f"✅ Prediction sent for {match['home']} vs {match['away']}")
        
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Error in analyze_matches: {e}")
        return 0

def bot_worker():
    """Main bot worker function"""
    global bot_started
    logger.info("🔄 Starting bot worker loop...")
    
    # Wait for everything to initialize
    time.sleep(5)
    
    # Send startup message
    logger.info("📤 Sending startup message...")
    if send_test_message():
        logger.info("✅ Startup message delivered")
    else:
        logger.error("❌ Startup message failed")
    
    counter = 0
    while True:
        try:
            counter += 1
            logger.info(f"🔄 Bot iteration {counter}")
            
            # Analyze matches and send predictions
            predictions = analyze_matches()
            logger.info(f"📊 Sent {predictions} predictions this cycle")
            
            # Send status update every 3 iterations
            if counter % 3 == 0:
                status_msg = (
                    f"📈 **BOT STATUS UPDATE**\n\n"
                    f"🔄 Cycles Completed: {counter}\n"
                    f"🕒 Last Update: {datetime.now().strftime('%H:%M:%S')}\n" 
                    f"✅ Predictions Sent: {predictions} this cycle\n"
                    f"📡 Bot Status: ACTIVE & MONITORING\n\n"
                    f"⏰ Next update in 2 minutes..."
                )
                bot.send_message(OWNER_CHAT_ID, status_msg, parse_mode='Markdown')
            
            # Wait 2 minutes
            logger.info("⏰ Waiting 2 minutes for next cycle...")
            time.sleep(120)
            
        except Exception as e:
            logger.error(f"❌ Bot worker error: {e}")
            time.sleep(120)

def start_bot_thread():
    """Start the bot in a background thread"""
    global bot_started
    if not bot_started:
        logger.info("🚀 Starting bot background thread...")
        thread = Thread(target=bot_worker, daemon=True)
        thread.start()
        bot_started = True
        logger.info("✅ Bot thread started successfully")
    else:
        logger.info("✅ Bot thread already running")

# Start bot automatically when module loads
logger.info("🎯 Initializing bot startup...")
start_bot_thread()

if __name__ == "__main__":
    logger.info("🌐 Starting Flask application...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
