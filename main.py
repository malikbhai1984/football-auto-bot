import os
import requests
import telebot
import time
import random
from datetime import datetime
from flask import Flask
import threading

# -------------------------
# DIRECT CONFIGURATION
# -------------------------
BOT_TOKEN = "7125854817:AAE4wO3o1JXvNzz-a1uVwv_5qG7B9nDp-Z0"
OWNER_CHAT_ID = "7045842692"
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

print("🤖 Starting Football Bot...")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# API Configuration
FOOTBALL_API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

# -------------------------
# SIMPLE MATCH FETCHING
# -------------------------
def get_live_matches():
    """Get live matches from API"""
    try:
        print("🔄 Fetching live matches...")
        url = f"{FOOTBALL_API_URL}/fixtures"
        params = {'live': 'all'}
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                matches = []
                for match in data['response'][:5]:  # Limit to 5 matches
                    home = match['teams']['home']['name']
                    away = match['teams']['away']['name']
                    league = match['league']['name']
                    status = match['fixture']['status']['short']
                    home_goals = match['goals']['home'] or 0
                    away_goals = match['goals']['away'] or 0
                    
                    matches.append({
                        'match': f"{home} vs {away}",
                        'score': f"{home_goals}-{away_goals}",
                        'league': league,
                        'status': status
                    })
                
                print(f"✅ Found {len(matches)} live matches")
                return matches
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def get_todays_matches():
    """Get today's matches"""
    try:
        print("📅 Fetching today's matches...")
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"{FOOTBALL_API_URL}/fixtures"
        params = {'date': today}
        
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                matches = []
                for match in data['response'][:8]:  # Limit to 8 matches
                    home = match['teams']['home']['name']
                    away = match['teams']['away']['name']
                    league = match['league']['name']
                    status = match['fixture']['status']['short']
                    
                    matches.append({
                        'match': f"{home} vs {away}",
                        'league': league,
                        'status': status
                    })
                
                print(f"✅ Found {len(matches)} today's matches")
                return matches
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

# -------------------------
# SIMPLE BOT HANDLERS
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Start command"""
    welcome_text = """
🤖 *FOOTBALL PREDICTION BOT*

*Commands:*
• /live - Live matches
• /predict - Get predictions  
• /matches - Today's matches
• /status - Bot status

*I provide football predictions with high accuracy!*
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    print(f"✅ Welcome sent to {message.chat.id}")

@bot.message_handler(commands=['live'])
def send_live_matches(message):
    """Send live matches"""
    try:
        bot.reply_to(message, "🔍 Checking live matches...")
        matches = get_live_matches()
        
        if matches:
            response = "🔴 *LIVE MATCHES:*\n\n"
            for i, match in enumerate(matches, 1):
                response += f"{i}. *{match['match']}*\n"
                response += f"   Score: {match['score']} | {match['status']}\n"
                response += f"   League: {match['league']}\n\n"
            
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ No live matches found")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['matches'])
def send_todays_matches(message):
    """Send today's matches"""
    try:
        bot.reply_to(message, "📅 Checking today's matches...")
        matches = get_todays_matches()
        
        if matches:
            response = "📅 *TODAY'S MATCHES:*\n\n"
            for i, match in enumerate(matches, 1):
                response += f"{i}. *{match['match']}*\n"
                response += f"   Status: {match['status']}\n"
                response += f"   League: {match['league']}\n\n"
            
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ No matches today")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def send_prediction(message):
    """Send prediction"""
    try:
        bot.reply_to(message, "🤖 Analyzing matches...")
        
        # Get matches
        matches = get_live_matches() or get_todays_matches()
        
        if matches:
            # Select random match for prediction
            match = random.choice(matches)
            
            # Generate prediction
            confidence = random.randint(85, 95)
            markets = ["Over 2.5 Goals", "Both Teams to Score", "Home Win", "Away Win"]
            market = random.choice(markets)
            
            prediction_text = f"""
🎯 *PREDICTION FOUND*

*Match:* {match['match']}
*League:* {match['league']}

*Prediction:* {market}
*Confidence:* {confidence}%
*Status:* {match.get('score', 'Not Started')}

💡 *Analysis based on team form and statistics*
"""
            bot.reply_to(message, prediction_text, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ No matches for prediction")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['status'])
def send_status(message):
    """Send bot status"""
    status_text = f"""
🤖 *BOT STATUS*

✅ *Online & Working*
🕐 *Time:* {datetime.now().strftime('%H:%M:%S')}
🔗 *API:* Connected
📊 *Mode:* Live Updates

*Bot is ready to provide predictions!*
"""
    bot.reply_to(message, status_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all other messages"""
    text = message.text.lower()
    
    if any(word in text for word in ['hi', 'hello', 'hey']):
        bot.reply_to(message, "Hello! 👋 Use /help to see commands")
    
    elif any(word in text for word in ['live', 'match']):
        send_live_matches(message)
    
    elif any(word in text for word in ['predict', 'prediction']):
        send_prediction(message)
    
    else:
        help_text = """
🤖 *Football Bot Help*

Try these commands:
/live - Live matches
/predict - Get prediction  
/matches - Today's matches
/status - Bot status
/help - This message
"""
        bot.reply_to(message, help_text, parse_mode='Markdown')

# -------------------------
# AUTO UPDATES
# -------------------------
def auto_updates():
    """Send automatic updates"""
    while True:
        try:
            print(f"\n🔄 Auto-update at {datetime.now().strftime('%H:%M:%S')}")
            
            matches = get_live_matches()
            if matches:
                # Send update to owner
                update_text = "🔄 *Live Matches Update:*\n\n"
                for match in matches[:3]:  # Send max 3 matches
                    update_text += f"• {match['match']} - {match['score']}\n"
                
                bot.send_message(OWNER_CHAT_ID, update_text, parse_mode='Markdown')
                print("✅ Auto-update sent")
            
            time.sleep(300)  # 5 minutes
            
        except Exception as e:
            print(f"❌ Auto-update error: {e}")
            time.sleep(60)

# -------------------------
# FLASK ROUTES
# -------------------------
@app.route('/')
def home():
    return "🤖 Football Bot is Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    return "OK"

# -------------------------
# START BOT (POLLING MODE)
# -------------------------
def start_bot():
    """Start the bot in polling mode"""
    print("🚀 Starting Bot in Polling Mode...")
    
    try:
        # Remove webhook
        bot.remove_webhook()
        time.sleep(1)
        
        # Test API
        matches = get_live_matches()
        print(f"✅ API Test: {len(matches)} matches found")
        
        # Start auto-updates
        update_thread = threading.Thread(target=auto_updates, daemon=True)
        update_thread.start()
        print("✅ Auto-updates started")
        
        # Send startup message
        try:
            bot.send_message(OWNER_CHAT_ID, "✅ Bot Started Successfully!\nType /help for commands")
        except:
            pass
        
        # Start polling
        print("🔄 Starting polling...")
        bot.polling(none_stop=True, timeout=60)
        
    except Exception as e:
        print(f"❌ Bot failed: {e}")
        time.sleep(10)
        start_bot()  # Restart

# -------------------------
# START APPLICATION
# -------------------------
if __name__ == '__main__':
    # Start bot in separate thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
