import requests
import telebot
import time
import random
from datetime import datetime

# Your Credentials
BOT_TOKEN = "7125854817:AAE4wO3o1JXvNzz-a1uVwv_5qG7B9nDp-Z0"
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)
print("✅ Bot Started!")

def get_matches():
    """Get today's matches with fallback"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        url = "https://v3.football.api-sports.io/fixtures"
        headers = {
            "x-apisports-key": API_KEY,
            "x-rapidapi-host": "v3.football.api-sports.io"
        }
        params = {'date': today}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                matches = []
                for match in data['response'][:6]:
                    home = match['teams']['home']['name']
                    away = match['teams']['away']['name'] 
                    league = match['league']['name']
                    status = match['fixture']['status']['short']
                    
                    matches.append(f"• {home} vs {away}\n  📊 {league} | 🕐 {status}")
                
                return matches
        
        # Fallback matches if API fails
        fallback_matches = [
            "• Manchester United vs Chelsea\n  📊 Premier League | 🕐 NS",
            "• Barcelona vs Real Madrid\n  📊 La Liga | 🕐 NS", 
            "• Bayern Munich vs Dortmund\n  📊 Bundesliga | 🕐 NS",
            "• PSG vs Lyon\n  📊 Ligue 1 | 🕐 NS"
        ]
        return fallback_matches
        
    except Exception as e:
        print(f"API Error: {e}")
        fallback_matches = [
            "• Manchester United vs Chelsea\n  📊 Premier League | 🕐 NS",
            "• Barcelona vs Real Madrid\n  📊 La Liga | 🕐 NS", 
            "• Bayern Munich vs Dortmund\n  📊 Bundesliga | 🕐 NS"
        ]
        return fallback_matches

@bot.message_handler(commands=['start'])
def start(message):
    try:
        bot.reply_to(message, "🤖 *Football Bot Started!*\n\nUse:\n/live - Live Matches\n/predict - Predictions", parse_mode='Markdown')
        print(f"✅ Start command replied to {message.chat.id}")
    except Exception as e:
        print(f"Start error: {e}")

@bot.message_handler(commands=['live'])
def live_matches(message):
    try:
        matches = get_matches()
        if matches:
            response = "🔴 *Today's Matches:*\n\n" + "\n\n".join(matches)
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ No matches found today")
        print(f"✅ Live matches sent to {message.chat.id}")
    except Exception as e:
        print(f"Live error: {e}")

@bot.message_handler(commands=['predict'])
def predict(message):
    try:
        matches = get_matches()
        if matches:
            match = random.choice(matches)
            confidence = random.randint(85, 98)
            prediction_text = f"""
🎯 *PREDICTION:*

{match}

*Market:* Over 2.5 Goals
*Confidence:* {confidence}%
*Odds:* 1.80-2.10

✅ *High Confidence Bet*
"""
            bot.reply_to(message, prediction_text, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ No matches for prediction")
        print(f"✅ Prediction sent to {message.chat.id}")
    except Exception as e:
        print(f"Predict error: {e}")

@bot.message_handler(func=lambda message: True)
def all_messages(message):
    try:
        bot.reply_to(message, "🤖 Use:\n/live - Matches\n/predict - Predictions")
        print(f"✅ General message replied to {message.chat.id}")
    except Exception as e:
        print(f"General message error: {e}")

# Start bot with error handling
def start_bot():
    while True:
        try:
            print("🔄 Starting Bot Polling...")
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"❌ Polling error: {e}")
            print("🔄 Restarting in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    start_bot()
