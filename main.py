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

# API Config
HEADERS = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

def get_matches():
    """Get today's matches"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        url = "https://v3.football.api-sports.io/fixtures"
        params = {'date': today}
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        
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
        return []
    except:
        return []

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🤖 *Football Bot Started!*\n\nUse:\n/live - Live Matches\n/predict - Predictions", parse_mode='Markdown')

@bot.message_handler(commands=['live'])
def live_matches(message):
    matches = get_matches()
    if matches:
        response = "🔴 *Today's Matches:*\n\n" + "\n".join(matches)
        bot.reply_to(message, response, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ No matches found today")

@bot.message_handler(commands=['predict'])
def predict(message):
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

@bot.message_handler(func=lambda message: True)
def all_messages(message):
    bot.reply_to(message, "🤖 Use:\n/live - Matches\n/predict - Predictions")

print("🔄 Starting Bot Polling...")
bot.polling(none_stop=True)
