import os
import requests
import telebot
import time
import random
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, request
import threading
from dotenv import load_dotenv
import json
import pytz

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_KEY missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ CORRECT API URL FOR API-FOOTBALL.COM
API_URL = "https://apiv3.apifootball.com"

print("🎯 Starting REAL-TIME FOOTBALL PREDICTION BOT...")

# -------------------------
# UPDATED & VERIFIED LEAGUE IDs
# -------------------------
TARGET_LEAGUES = {
    "152": "Premier League",
    "302": "La Liga", 
    "207": "Serie A",
    "168": "Bundesliga",
    "176": "Ligue 1",
    "149": "Champions League",  # ✅ Corrected
    "150": "Europa League"      # ✅ Corrected
}

# -------------------------
# IMPROVED REAL-TIME MATCH DATA FETCHING
# -------------------------
def fetch_real_live_matches():
    """Fetch REAL live matches from API with better error handling"""
    try:
        print("🔴 Fetching REAL live matches from API...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
        
        print(f"📡 API URL: {url.replace(API_KEY, 'API_KEY_HIDDEN')}")
        
        response = requests.get(url, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            
            # Debug output
            print(f"📊 API Response type: {type(data)}")
            if isinstance(data, list):
                print(f"📊 Total matches found: {len(data)}")
            else:
                print(f"📊 API Response: {data}")
            
            if data and isinstance(data, list):
                live_matches = []
                for match in data:
                    try:
                        # Multiple ways to detect live matches
                        match_status = str(match.get("match_status", ""))
                        match_live = str(match.get("match_live", "0"))
                        match_time = match.get("match_time", "")
                        
                        # Check if match is live
                        is_live = (
                            match_live == "1" or 
                            match_status.isdigit() or 
                            match_status in ["1H", "2H", "HT", "IN PROGRESS"]
                        )
                        
                        if is_live:
                            league_id = match.get("league_id", "")
                            # Only include target leagues
                            if str(league_id) in TARGET_LEAGUES:
                                live_matches.append(match)
                                print(f"✅ Live match found: {match.get('match_hometeam_name')} vs {match.get('match_awayteam_name')}")
                    
                    except Exception as e:
                        print(f"⚠️ Match processing warning: {e}")
                        continue
                
                print(f"✅ Found {len(live_matches)} REAL live matches in target leagues")
                return live_matches
            else:
                print("⏳ No live matches data from API or invalid response")
                if isinstance(data, dict) and 'error' in data:
                    print(f"❌ API Error: {data['error']}")
                return []
        else:
            print(f"❌ API Error {response.status_code}: {response.text}")
            return []
            
    except requests.exceptions.Timeout:
        print("❌ API request timeout")
        return []
    except requests.exceptions.ConnectionError:
        print("❌ API connection error")
        return []
    except Exception as e:
        print(f"❌ Live matches fetch error: {str(e)}")
        return []

def process_real_match(match):
    """Process real match data from API"""
    try:
        home_team = match.get("match_hometeam_name", "Unknown")
        away_team = match.get("match_awayteam_name", "Unknown")
        home_score = match.get("match_hometeam_score", "0")
        away_score = match.get("match_awayteam_score", "0")
        minute = match.get("match_status", "0")
        league_id = match.get("league_id", "")
        league_name = TARGET_LEAGUES.get(str(league_id), f"League {league_id}")
        
        # Determine match status
        if minute == "HT":
            match_status = "HALF TIME"
            display_minute = "HT"
        elif minute == "FT":
            match_status = "FULL TIME"
            display_minute = "FT"
        elif minute.isdigit():
            match_status = "LIVE"
            display_minute = f"{minute}'"
        elif minute in ["1H", "2H"]:
            match_status = "LIVE"
            display_minute = minute
        else:
            match_status = "UPCOMING"
            display_minute = minute
        
        return {
            "home_team": home_team,
            "away_team": away_team,
            "score": f"{home_score}-{away_score}",
            "minute": display_minute,
            "status": match_status,
            "league": league_name,
            "league_id": league_id,
            "raw_data": match  # Keep original data for debugging
        }
        
    except Exception as e:
        print(f"❌ Match processing error: {e}")
        return None

def get_real_live_matches():
    """Get real live matches from API with retry logic"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            raw_matches = fetch_real_live_matches()
            
            if not raw_matches:
                if attempt < max_retries - 1:
                    print(f"🔄 Retry {attempt + 1}/{max_retries} in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    print("⏳ No live matches found after retries")
                    return []
            
            processed_matches = []
            for match in raw_matches:
                processed_match = process_real_match(match)
                if processed_match:
                    processed_matches.append(processed_match)
            
            print(f"✅ Successfully processed {len(processed_matches)} real live matches")
            return processed_matches
                
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    
    return []

# -------------------------
# SIMPLIFIED AI CHATBOT (Working Version)
# -------------------------
class SimpleFootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking"},
            "liverpool": {"strength": 92, "style": "high press"},
            "arsenal": {"strength": 90, "style": "possession"},
            "chelsea": {"strength": 85, "style": "balanced"},
            "manchester united": {"strength": 84, "style": "counter attack"},
            "tottenham": {"strength": 87, "style": "attacking"},
            "real madrid": {"strength": 94, "style": "experienced"},
            "barcelona": {"strength": 92, "style": "possession"},
            "bayern munich": {"strength": 93, "style": "dominant"},
            "psg": {"strength": 90, "style": "attacking"}
        }
    
    def get_ai_response(self, user_message, user_id):
        """Simple AI response"""
        user_message_lower = user_message.lower()
        
        if any(word in user_message_lower for word in ['live', 'current', 'now playing']):
            return self.handle_live_matches_query()
        
        elif any(word in user_message_lower for word in ['predict', 'prediction', 'who will win']):
            return self.handle_prediction_query(user_message_lower)
        
        elif any(word in user_message_lower for word in ['hello', 'hi', 'hey']):
            return "👋 Hello! I'm Football Prediction AI! Ask me about live matches or predictions! ⚽"
        
        elif any(word in user_message_lower for word in ['help']):
            return self.get_help_response()
        
        else:
            return "🤖 I can help with:\n• Live match updates\n• Match predictions\n• Team analysis\n\nTry: 'Show me live matches' or 'Predict Man City vs Liverpool'"

    def handle_live_matches_query(self):
        """Handle live matches queries"""
        real_matches = get_real_live_matches()
        
        if real_matches:
            response = "🔴 **LIVE MATCHES RIGHT NOW:**\n\n"
            
            for match in real_matches:
                status_icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                response += f"⚽ **{match['league']}**\n"
                response += f"• {match['home_team']} {match['score']} {match['away_team']}\n"
                response += f"• {status_icon} {match['minute']} - {match['status']}\n\n"
            
            response += "🔄 Updates every 5-7 minutes!"
            
        else:
            response = "⏳ No live matches in major leagues right now.\n\n"
            response += "Try asking for predictions instead!"
        
        return response

    def handle_prediction_query(self, message):
        """Handle prediction queries"""
        teams = []
        for team in self.team_data:
            if team in message:
                teams.append(team)
        
        if len(teams) >= 2:
            return self.generate_prediction(teams[0], teams[1])
        else:
            return "Please specify two teams for prediction. Example: 'Predict Manchester City vs Liverpool'"

    def generate_prediction(self, team1, team2):
        """Generate simple prediction"""
        team1_data = self.team_data.get(team1, {"strength": 80, "style": "balanced"})
        team2_data = self.team_data.get(team2, {"strength": 80, "style": "balanced"})
        
        strength1 = team1_data["strength"]
        strength2 = team2_data["strength"]
        
        # Simple prediction algorithm
        total = strength1 + strength2
        prob1 = (strength1 / total) * 100
        prob2 = (strength2 / total) * 100
        draw_prob = 100 - prob1 - prob2
        
        if prob1 > prob2:
            winner = team1.title()
        elif prob2 > prob1:
            winner = team2.title()
        else:
            winner = "Draw"
        
        return f"""
🎯 **PREDICTION: {team1.upper()} vs {team2.upper()}**

📊 **Probabilities:**
• {team1.title()}: {prob1:.1f}%
• {team2.title()}: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%

🏆 **Most Likely: {winner}**

⚽ **Expected:**
• Both teams to score: YES
• Total goals: OVER 2.5

⚠️ *Football is unpredictable - bet responsibly!*
"""

    def get_help_response(self):
        return """
🤖 **FOOTBALL PREDICTION BOT HELP**

⚡ **COMMANDS:**
/live - Get current live matches
/predict - Get match predictions  
/help - This help message

💬 **CHAT EXAMPLES:**
• "Show me live matches"
• "Predict Manchester City vs Liverpool"
• "Who will win Barcelona vs Real Madrid?"

🎯 **FEATURES:**
• Real-time live scores
• AI match predictions
• 7 major leagues coverage
• Updates every 5-7 minutes
"""

# Initialize AI
football_ai = SimpleFootballAI()

# -------------------------
# TELEGRAM BOT HANDLERS (Simplified)
# -------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
🤖 **WELCOME TO FOOTBALL PREDICTION AI** ⚽

I provide:
• 🔴 Real-time live matches
• 🎯 AI-powered predictions  
• 📊 7 major leagues coverage

⚡ **Quick Commands:**
/live - Current live matches
/predict - Match predictions
/help - Help guide

💬 **Or just chat naturally!**
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['live'])
def get_live_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        live_matches = get_real_live_matches()
        
        if live_matches:
            response = "🔴 **LIVE MATCHES RIGHT NOW:**\n\n"
            
            for match in live_matches:
                status_icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                response += f"⚽ **{match['league']}**\n"
                response += f"• {match['home_team']} {match['score']} {match['away_team']}\n"
                response += f"• {status_icon} {match['minute']} - {match['status']}\n\n"
            
            response += "🔄 Updates every 5-7 minutes!"
            
        else:
            response = "⏳ **No live matches in major leagues right now.**\n\n"
            response += "Try the /predict command for upcoming match predictions!"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def get_predictions(message):
    try:
        response = """
🔮 **MATCH PREDICTIONS**

For specific match predictions, please ask me like:
• "Predict Manchester City vs Liverpool"
• "Who will win Barcelona vs Real Madrid?"
• "Arsenal vs Chelsea prediction"

I cover all major European leagues! 🏆
"""
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['help'])
def get_help(message):
    help_text = football_ai.get_help_response()
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_ai_chat(message):
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        print(f"💬 Chat from user {user_id}: {user_message}")
        
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(1)
        
        ai_response = football_ai.get_ai_response(user_message, user_id)
        
        bot.reply_to(message, ai_response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        bot.reply_to(message, "❌ Sorry, error occurred. Please try again!")

# -------------------------
# AUTO LIVE UPDATER (Fixed)
# -------------------------
def auto_live_updater():
    """Auto-update live matches every 5-7 minutes"""
    update_interval = random.randint(300, 420)  # 5-7 minutes
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Auto-checking live matches...")
            
            live_matches = get_real_live_matches()
            
            if live_matches:
                print(f"✅ {len(live_matches)} live matches found")
                # Here you can add code to send updates to subscribers
            else:
                print("⏳ No live matches currently")
            
            print(f"⏰ Next update in {update_interval//60} minutes...")
            time.sleep(update_interval)
            
            # Randomize next interval between 5-7 minutes
            update_interval = random.randint(300, 420)
            
        except Exception as e:
            print(f"❌ Auto updater error: {e}")
            time.sleep(300)  # Wait 5 minutes on error

# -------------------------
# STARTUP & POLLING (Use this for development)
# -------------------------
def start_bot():
    """Start the bot with polling (better for development)"""
    try:
        print("🚀 Starting Football Prediction Bot with Polling...")
        
        # Start live match updater in background
        updater_thread = threading.Thread(target=auto_live_updater, daemon=True)
        updater_thread.start()
        print("✅ Live Match Auto-Updater Started!")
        
        # Test API connection
        print("🔍 Testing API connection...")
        test_matches = get_real_live_matches()
        print(f"🔍 API Test Result: {len(test_matches)} matches found")
        
        startup_msg = f"""
🤖 **FOOTBALL PREDICTION AI STARTED!**

✅ **Features Active:**
• Real-time match updates
• AI predictions
• 7 major leagues
• 5-7 minute updates

🕒 **Pakistan Time:** {datetime.now(pytz.timezone('Asia/Karachi')).strftime('%Y-%m-%d %H:%M:%S')}

💬 **Bot is ready to receive messages!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
        print("🟢 Bot is now running with polling...")
        bot.infinity_polling()
        
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        print("🔄 Restarting in 10 seconds...")
        time.sleep(10)
        start_bot()

if __name__ == '__main__':
    start_bot()
