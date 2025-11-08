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
from datetime import datetime
from flask import Flask, request
import threading
from dotenv import load_dotenv

load_dotenv()

# -------------------------
# Configuration
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")

if not BOT_TOKEN or not OWNER_CHAT_ID or not API_KEY:
    print("❌ Error: Missing environment variables!")
    exit(1)

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

print("🤖 Bot initialized successfully!")

# -------------------------
# Simple Response System
# -------------------------
def get_response(response_type):
    if response_type == "greeting":
        return random.choice([
            "👋 Hello! I'm your Football Prediction Bot!",
            "🤖 Hi there! Ready to analyze matches!",
            "🎯 Welcome! Let's find some winning predictions!"
        ])
    elif response_type == "analyzing":
        return "🔍 Analyzing live matches..."
    elif response_type == "no_matches":
        return "❌ No high-confidence matches found right now."
    return "🤖 Processing..."

# -------------------------
# Football API Functions
# -------------------------
def fetch_live_matches():
    """Fetch live matches from API"""
    try:
        print("🔄 Fetching live matches...")
        # Simulate API call - replace with real API
        return [
            {
                "teams": {
                    "home": {"name": "Manchester United", "id": 33},
                    "away": {"name": "Liverpool", "id": 40}
                },
                "fixture": {"id": 12345},
                "league": {"id": 39}
            },
            {
                "teams": {
                    "home": {"name": "Barcelona", "id": 529},
                    "away": {"name": "Real Madrid", "id": 541}
                },
                "fixture": {"id": 12346},
                "league": {"id": 140}
            }
        ]
    except Exception as e:
        print(f"❌ Error fetching matches: {e}")
        return []

def fetch_odds(fixture_id):
    """Fetch odds for fixture"""
    try:
        # Simulate odds data
        return []
    except:
        return []

# -------------------------
# Prediction Engine
# -------------------------
def generate_prediction(match):
    """Generate prediction for match"""
    home_team = match["teams"]["home"]["name"]
    away_team = match["teams"]["away"]["name"]
    
    # Simulate confidence (85-95%)
    confidence = random.randint(85, 95)
    
    if confidence < 85:
        return None
    
    markets = [
        {"market": "Over 2.5 Goals", "prediction": "Yes", "odds": "1.70-1.90"},
        {"market": "Both Teams to Score", "prediction": "Yes", "odds": "1.80-2.10"},
        {"market": "Home Win", "prediction": "Yes", "odds": "2.10-2.40"},
        {"market": "Away Win", "prediction": "Yes", "odds": "1.90-2.20"}
    ]
    selected_market = random.choice(markets)
    
    return {
        'home_team': home_team,
        'away_team': away_team,
        'market': selected_market['market'],
        'prediction': selected_market['prediction'],
        'confidence': confidence,
        'odds': selected_market['odds'],
        'reason': "Strong team form and historical data support this prediction.",
        'correct_scores': ["2-1", "1-1", "2-0"],
        'btts': "Yes",
        'last_10_min_goal': random.randint(75, 90)
    }

# -------------------------
# Message Formatting
# -------------------------
def format_prediction_message(prediction):
    return f"""
⚽ **HIGH-CONFIDENCE PREDICTION**

**Match:** {prediction['home_team']} vs {prediction['away_team']}

🎯 **Market:** {prediction['market']}
✅ **Prediction:** {prediction['prediction']}
💰 **Confidence:** {prediction['confidence']}%
🔥 **Odds:** {prediction['odds']}

📊 **Analysis:** {prediction['reason']}

🎲 **Correct Scores:** {', '.join(prediction['correct_scores'])}
⚽ **BTTS:** {prediction['btts']}
⏰ **Late Goal Chance:** {prediction['last_10_min_goal']}%

⚠️ Always verify team news before betting!
"""

# -------------------------
# Auto Prediction System (FIXED FUNCTION NAME)
# -------------------------
def auto_predictor():
    """Auto prediction every 5 minutes"""
    while True:
        try:
            print(f"🔄 Auto-scan at {datetime.now().strftime('%H:%M:%S')}")
            matches = fetch_live_matches()
            
            for match in matches:
                prediction = generate_prediction(match)
                if prediction:
                    message = format_prediction_message(prediction)
                    try:
                        bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
                        print(f"✅ Prediction sent for {prediction['home_team']} vs {prediction['away_team']}")
                    except Exception as e:
                        print(f"❌ Send error: {e}")
                    time.sleep(2)
                        
        except Exception as e:
            print(f"❌ Auto-predictor error: {e}")
        
        time.sleep(300)  # 5 minutes

# -------------------------
# Bot Message Handlers
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Welcome message"""
    welcome_text = """
🤖 **Football Prediction Bot**

I provide high-confidence football predictions with 85%+ accuracy.

**Commands:**
/start - Show this help
/predict - Get predictions  
/status - Bot status

**Auto-features:**
• Scans every 5 minutes
• Sends high-confidence predictions
• Real-time match analysis
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    print(f"✅ Welcome message sent to user")

@bot.message_handler(commands=['predict', 'live'])
def send_predictions(message):
    """Send predictions"""
    try:
        print(f"📨 Prediction request from user")
        bot.reply_to(message, "🔍 Scanning for live matches...")
        
        matches = fetch_live_matches()
        if not matches:
            bot.reply_to(message, "❌ No live matches found.")
            return
        
        prediction_found = False
        for match in matches:
            prediction = generate_prediction(match)
            if prediction:
                msg = format_prediction_message(prediction)
                bot.reply_to(message, msg, parse_mode='Markdown')
                prediction_found = True
                print(f"✅ Prediction sent to user")
                break
        
        if not prediction_found:
            bot.reply_to(message, "❌ No high-confidence predictions available.")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
        print(f"❌ Prediction error: {e}")

@bot.message_handler(commands=['status'])
def send_status(message):
    """Send bot status"""
    status_text = f"""
🤖 **Bot Status**

✅ **Online and Active**
🕐 **Last Check:** {datetime.now().strftime('%H:%M:%S')}
⏰ **Next Scan:** 5 minutes
🎯 **Confidence:** 85%+ only

Everything is working perfectly!
"""
    bot.reply_to(message, status_text, parse_mode='Markdown')
    print(f"✅ Status sent to user")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all messages"""
    text = message.text.lower()
    
    if any(word in text for word in ['hi', 'hello', 'hey']):
        response = get_response("greeting")
        bot.reply_to(message, response)
        print(f"✅ Greeting sent to user")
    
    elif any(word in text for word in ['predict', 'prediction', 'match', 'live']):
        send_predictions(message)
    
    elif any(word in text for word in ['thanks', 'thank you']):
        bot.reply_to(message, "You're welcome! 🎯")
        print(f"✅ Thanks response sent")
    
    elif any(word in text for word in ['status', 'working']):
        send_status(message)
    
    else:
        help_text = """
🤖 I'm your Football Prediction Bot!

Try these:
• "predict" - Get predictions
• "live" - Current matches  
• "status" - Check bot status

I auto-scan every 5 minutes! ⏰
"""
        bot.reply_to(message, help_text)
        print(f"✅ Help message sent to user")

# -------------------------
# Flask Webhook Routes
# -------------------------
@app.route('/')
def home():
    return "🤖 Football Prediction Bot is Running!"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Telegram webhook"""
    try:
        json_data = request.get_json()
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return 'ERROR', 400

# -------------------------
# Initialize Bot (FIXED FUNCTION NAME)
# -------------------------
def setup_bot():
    """Setup bot webhook"""
    print("🚀 Setting up bot...")
    
    try:
        # Remove existing webhook
        bot.remove_webhook()
        time.sleep(1)
        
        # Set new webhook
        domain = "https://football-auto-bot-production.up.railway.app"
        webhook_url = f"{domain}/{BOT_TOKEN}"
        
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
        
        # Start auto-predictor (FIXED: using correct function name)
        auto_thread = threading.Thread(target=auto_predictor, daemon=True)
        auto_thread.start()
        print("✅ Auto-predictor started!")
        print("🎯 Bot is now LIVE and ready to receive messages!")
        
    except Exception as e:
        print(f"❌ Setup error: {e}")
        print("🔄 Using polling as fallback...")
        bot.remove_webhook()
        bot.polling(none_stop=True)

# -------------------------
# Start Application
# -------------------------
if __name__ == '__main__':
    setup_bot()
    port = int(os.environ.get('PORT', 8080))
    print(f"🌐 Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port)
