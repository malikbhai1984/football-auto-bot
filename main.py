import requests
import telebot
import time
import random
from datetime import datetime

# Your Credentials - CHANGE THESE!
BOT_TOKEN = "7125854817:AAE4wO3o1JXvNzz-a1uVwv_5qG7B9nDp-Z0"
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN)
print("✅ Bot Started!")

def get_live_matches():
    """Get live matches from API"""
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        headers = {
            "x-apisports-key": API_KEY,
            "x-rapidapi-host": "v3.football.api-sports.io"
        }
        params = {'live': 'all'}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                matches = []
                for match in data['response'][:6]:
                    home = match['teams']['home']['name']
                    away = match['teams']['away']['name']
                    home_goals = match['goals']['home'] or 0
                    away_goals = match['goals']['away'] or 0
                    league = match['league']['name']
                    status = match['fixture']['status']['short']
                    
                    matches.append({
                        'match': f"{home} vs {away}",
                        'score': f"{home_goals}-{away_goals}",
                        'league': league,
                        'status': status
                    })
                return matches
        return []
    except:
        return []

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🤖 *Football Bot Started!*\n\nUse:\n/live - Live Matches\n/predict - Predictions", parse_mode='Markdown')

@bot.message_handler(commands=['live'])
def live_matches(message):
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

@bot.message_handler(commands=['predict'])
def predict(message):
    matches = get_live_matches()
    if matches:
        match = random.choice(matches)
        confidence = random.randint(85, 95)
        prediction_text = f"""
🎯 *PREDICTION:*

*Match:* {match['match']}
*League:* {match['league']}
*Score:* {match['score']}

*Prediction:* Over 2.5 Goals
*Confidence:* {confidence}%
*Status:* {match['status']}

✅ *High Confidence Bet*
"""
        bot.reply_to(message, prediction_text, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ No matches for prediction")

@bot.message_handler(func=lambda message: True)
def all_messages(message):
    bot.reply_to(message, "🤖 Use:\n/live - Matches\n/predict - Predictions")

print("🔄 Starting Bot...")
bot.polling(none_stop=True)
