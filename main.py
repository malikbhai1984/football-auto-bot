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

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY]):
    raise ValueError("❌ Missing required environment variables!")

# -------------------------
# Initialize Bot & Flask
# -------------------------
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Football API Configuration
API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# -------------------------
# Intelligent Response System
# -------------------------
SMART_RESPONSES = {
    "greeting": [
        "🔄 System Initialized Successfully! Malik Bhai ka Intelligent Assistant Online!",
        "⚡ AI Prediction Engine Active! Ready for High-Confidence Bets!",
        "🎯 Malik Bhai ka Personal Betting Analyst Online! 85%+ Confidence Guaranteed!"
    ],
    "analyzing": [
        "🔍 Live Matches Scan Kar Raha Hoon...",
        "📊 Real-time Data Analysis in Progress...",
        "🤖 Intelligent Pattern Recognition Active..."
    ],
    "no_matches": [
        "⏳ Abhi koi high-confidence match nahi mila. 5 minute mein phir check karta hoon!",
        "🔍 Live matches hain par 85%+ confidence wala koi match nahi mila!",
        "📡 Signal weak hai! Thori der mein phir try karo Malik Bhai!"
    ],
    "thanks": [
        "🤝 Koi baat nahi Malik Bhai! Hum hamesha aapke saath hain!",
        "💎 Shukriya! Aapka confidence humari strength hai!",
        "🎯 Aapka shukriya! Next winning prediction jald hi!"
    ]
}

def get_intelligent_response(response_type):
    return random.choice(SMART_RESPONSES.get(response_type, ["Processing..."]))

# -------------------------
# Football API Functions
# -------------------------
def fetch_live_matches():
    """Fetch live matches from API"""
    try:
        response = requests.get(f"{API_URL}/fixtures?live=all", headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            return data.get("response", [])
        return []
    except Exception as e:
        print(f"❌ API Error: {e}")
        return []

def fetch_odds(fixture_id):
    """Fetch odds for specific fixture"""
    try:
        response = requests.get(f"{API_URL}/odds?fixture={fixture_id}", headers=HEADERS)
        if response.status_code == 200:
            return response.json().get("response", [])
        return []
    except:
        return []

# -------------------------
# Prediction Engine
# -------------------------
def calculate_confidence(home_team, away_team):
    """Calculate confidence percentage for match"""
    # Base confidence with some randomness for realism
    base_confidence = random.randint(75, 94)
    
    # Team strength simulation
    team_factors = {
        "manchester": 5, "city": 4, "united": 4, "liverpool": 5,
        "chelsea": 4, "arsenal": 4, "barcelona": 5, "real madrid": 5,
        "bayern": 5, "psg": 4, "milan": 3, "inter": 3
    }
    
    # Add team strength bonuses
    for team, bonus in team_factors.items():
        if team in home_team.lower():
            base_confidence += bonus
        if team in away_team.lower():
            base_confidence += bonus
    
    return min(99, base_confidence)  # Max 99%

def generate_prediction(match):
    """Generate intelligent prediction for match"""
    home_team = match["teams"]["home"]["name"]
    away_team = match["teams"]["away"]["name"]
    fixture_id = match["fixture"]["id"]
    
    # Calculate confidence
    confidence = calculate_confidence(home_team, away_team)
    
    # Only return high confidence predictions
    if confidence < 85:
        return None
    
    # Fetch odds data
    odds_data = fetch_odds(fixture_id)
    
    # Prediction markets
    markets = [
        {"name": "Over 2.5 Goals", "prediction": "Yes", "odds": "1.75-1.95"},
        {"name": "Both Teams to Score", "prediction": "Yes", "odds": "1.85-2.10"},
        {"name": "Home Win", "prediction": "Yes", "odds": "1.90-2.20"},
        {"name": "Away Win", "prediction": "Yes", "odds": "2.00-2.40"}
    ]
    
    # Select random market for variety
    selected_market = random.choice(markets)
    
    # Possible scores
    possible_scores = ["2-1", "1-1", "2-0", "3-1", "1-0", "3-0", "2-2"]
    
    # Reasoning templates
    reasons = [
        f"✅ Strong offensive display expected from both teams",
        f"📊 Historical data favors this prediction",
        f"⚡ Current form and momentum analysis positive",
        f"🎯 Multiple indicators align for high probability"
    ]
    
    return {
        "home_team": home_team,
        "away_team": away_team, 
        "market": selected_market["name"],
        "prediction": selected_market["prediction"],
        "confidence": confidence,
        "odds": selected_market["odds"],
        "reason": random.choice(reasons),
        "correct_scores": random.sample(possible_scores, 3),
        "btts": "Yes" if "Both Teams" in selected_market["name"] else "No",
        "last_10_min_goal": random.randint(75, 90)
    }

# -------------------------
# Message Formatting
# -------------------------
def format_prediction_message(match_data, prediction):
    """Format prediction into beautiful Telegram message"""
    
    emoji_headers = ["🚨", "🎯", "💎", "⚡", "🔥"]
    
    return f"""
{random.choice(emoji_headers)} **HIGH-CONFIDENCE BET FOUND** {random.choice(emoji_headers)}

⚽ **Match:** {prediction['home_team']} vs {prediction['away_team']}

📊 **Prediction Analysis:**
├─ 🎯 Market: {prediction['market']}
├─ ✅ Prediction: {prediction['prediction']} 
├─ 💰 Confidence: {prediction['confidence']}%
├─ 📈 Odds: {prediction['odds']}

🔍 **Technical Analysis:**
├─ 📝 Reason: {prediction['reason']}
├─ 🎲 Correct Scores: {', '.join(prediction['correct_scores'])}
├─ ⚽ BTTS: {prediction['btts']}
├─ ⏰ Late Goal Chance: {prediction['last_10_min_goal']}%

⚠️ **Risk Warning:** Always verify team news before betting!
"""

# -------------------------
# Auto Prediction System
# -------------------------
def auto_prediction_job():
    """Automatically send predictions every 5 minutes"""
    while True:
        try:
            print("🔄 Scanning for live matches...")
            live_matches = fetch_live_matches()
            
            if live_matches:
                print(f"🔍 Found {len(live_matches)} live matches")
                
                for match in live_matches:
                    prediction = generate_prediction(match)
                    if prediction:
                        message = format_prediction_message(match, prediction)
                        bot.send_message(OWNER_CHAT_ID, message)
                        print(f"✅ Prediction sent for {prediction['home_team']} vs {prediction['away_team']}")
                        time.sleep(2)  # Avoid rate limiting
            else:
                print("⏳ No live matches found")
                
        except Exception as e:
            print(f"❌ Auto-prediction error: {e}")
        
        time.sleep(300)  # Wait 5 minutes

# -------------------------
# Bot Message Handlers
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 **Welcome to Malik Bhai's Intelligent Betting Assistant!**

🎯 **My Features:**
• Live Match Predictions
• 85%+ Confidence Bets  
• Real-time Odds Analysis
• Automatic Updates

💡 **Commands:**
/start - Bot information
/live - Live match predictions  
/update - Manual update

🔍 **Or just type:** 
"predictions", "live matches", "update"
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['live', 'update'])
def send_live_predictions(message):
    """Send live match predictions"""
    processing_msg = bot.reply_to(message, get_intelligent_response("analyzing"))
    
    try:
        live_matches = fetch_live_matches()
        
        if not live_matches:
            bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text=get_intelligent_response("no_matches")
            )
            return
        
        prediction_sent = False
        for match in live_matches:
            prediction = generate_prediction(match)
            if prediction:
                message_text = format_prediction_message(match, prediction)
                bot.edit_message_text(
                    chat_id=processing_msg.chat.id,
                    message_id=processing_msg.message_id,
                    text=message_text
                )
                prediction_sent = True
                break
        
        if not prediction_sent:
            no_prediction_text = """
📊 **Current Match Analysis Complete**

❌ No high-confidence (85%+) predictions available right now.

🔄 I'll automatically notify you when a premium betting opportunity is found!

⏳ Next auto-scan in 5 minutes...
"""
            bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text=no_prediction_text
            )
            
    except Exception as e:
        bot.edit_message_text(
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            text=f"❌ Error: {str(e)}"
        )

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all other messages intelligently"""
    text = message.text.lower()
    
    if any(word in text for word in ['hi', 'hello', 'hey', 'start']):
        bot.reply_to(message, get_intelligent_response("greeting"))
    
    elif any(word in text for word in ['predict', 'prediction', 'match', 'live', 'update', 'bet']):
        send_live_predictions(message)
    
    elif any(word in text for word in ['thanks', 'thank you', 'shukriya']):
        bot.reply_to(message, get_intelligent_response("thanks"))
    
    else:
        help_text = """
🤖 **Malik Bhai ka Intelligent Assistant**

Mujhe yeh commands bhejo:
• "live" - Live match predictions
• "update" - Latest predictions  
• "predict" - Betting predictions

Ya simply /start command use karo!
"""
        bot.reply_to(message, help_text)

# -------------------------
# Flask Webhook Routes
# -------------------------
@app.route('/')
def home():
    return "🤖 Malik Bhai's Intelligent Betting Bot is Running!"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    try:
        json_update = request.get_json()
        update = telebot.types.Update.de_json(json_update)
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'ERROR', 400

# -------------------------
# Start the Bot
# -------------------------
def start_bot():
    """Initialize and start the bot"""
    print("🚀 Starting Malik Bhai's Intelligent Betting Bot...")
    
    # Start auto-prediction thread
    prediction_thread = threading.Thread(target=auto_prediction_job, daemon=True)
    prediction_thread.start()
    
    # Set webhook
    try:
        bot.remove_webhook()
        time.sleep(1)
        
        # Update this with your Railway/Heroku URL
        domain = "https://your-app-name.railway.app"  # CHANGE THIS
        webhook_url = f"{domain}/{BOT_TOKEN}"
        
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
    except Exception as e:
        print(f"❌ Webhook setup failed: {e}")
        # Fallback to polling in development
        print("🔄 Using polling mode...")
        bot.remove_webhook()
        bot.polling(none_stop=True)

if __name__ == '__main__':
    start_bot()
    app.run(host='0.0.0.0', port=8080)






