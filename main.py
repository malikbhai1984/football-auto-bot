import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests





import os
import requests
import telebot
import time
import random
import logging
from datetime import datetime
from flask import Flask, request
import threading
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# -------------------------
# Configuration
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_KEY missing!")

# -------------------------
# Initialize Bot & Flask
# -------------------------
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# ... [rest of the code, including IntelligentAnalyst, API functions, AdvancedPredictor, etc.] ...

# -------------------------
# Initialize Advanced System
# -------------------------
def initialize_advanced_system():
    """Initialize the enhanced prediction system"""
    logger.info("🚀 Starting Advanced AI Football Prediction System...")
    logger.info("📊 Loading real-time data processors...")
    logger.info("🤖 Initializing predictive algorithms...")
    logger.info("🔍 Activating comprehensive monitoring...")
    
    # Start enhanced auto-prediction thread
    prediction_thread = threading.Thread(target=intelligent_auto_predictor, daemon=True)
    prediction_thread.start()
    
    # Configure webhook with YOUR DOMAIN
    try:
        bot.remove_webhook()
        time.sleep(1)
        
        # ✅ YOUR ACTUAL RAILWAY DOMAIN
        railway_domain = "https://football-auto-bot-production.up.railway.app"
        webhook_url = f"{railway_domain}/{BOT_TOKEN}"
        
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook configured: {webhook_url}")
        logger.info("🔧 System running in PRODUCTION mode")
        logger.info("🎯 Bot is now LIVE and ready!")
        
    except Exception as e:
        logger.error(f"❌ Webhook configuration failed: {e}")
        logger.info("🔄 Activating fallback polling mode...")
        bot.remove_webhook()
        bot.polling(none_stop=True)

# ... [rest of the code] ...

# -------------------------
# Flask Webhook Routes
# -------------------------
@app.route('/')
def home():
    return "🤖 Advanced AI Football Prediction System - Operational"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Enhanced webhook handler"""
    try:
        json_update = request.get_json()
        logger.info(f"Update received: {json_update}")
        update = telebot.types.Update.de_json(json_update)
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return 'ERROR', 400

# Initialize the system when the app is run
initialize_advanced_system()

# Run the app if this is the main module
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
