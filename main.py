import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask
import logging
import random
from datetime import datetime, timedelta
import pytz
from threading import Thread
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import io
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
SPORTMONKS_API = os.getenv("API_KEY", "").strip()

logger.info("🚀 Starting Complete Live Match Prediction Bot...")

# Validate environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found")
if not SPORTMONKS_API:
    logger.error("❌ SPORTMONKS_API not found")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
    logger.info(f"✅ OWNER_CHAT_ID: {OWNER_CHAT_ID}")
except (ValueError, TypeError) as e:
    logger.error(f"❌ Invalid OWNER_CHAT_ID: {e}")
    exit(1)

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Pakistan Time Zone
PAK_TZ = pytz.timezone('Asia/Karachi')

# Top Leagues Configuration
TOP_LEAGUES = {
    39: "Premier League",    # England
    140: "La Liga",          # Spain  
    78: "Bundesliga",        # Germany
    135: "Serie A",          # Italy
    61: "Ligue 1",           # France
    94: "Primeira Liga",     # Portugal
    88: "Eredivisie",        # Netherlands
    203: "UEFA Champions League",
    2: "Champions League",
    5: "Europa League",
    564: "World Cup",
    82: "EFL Championship",
    384: "Serie B",
    94: "Primeira Liga",
    462: "Coupe de France",
    539: "UEFA Europa Conference League"
}

# Configuration
class Config:
    BOT_CYCLE_INTERVAL = 180  # 3 minutes
    MIN_CONFIDENCE_THRESHOLD = 55  # 55% minimum confidence
    API_TIMEOUT = 15
    MAX_RETRIES = 3

# Global variables
bot_started = False
message_counter = 0
historical_data = {}
model = None
scaler = StandardScaler()

def get_pakistan_time():
    """Get current Pakistan time"""
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    """Format datetime in Pakistan time"""
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M %Z')

def send_telegram_message(message, max_retries=3):
    """Send message to Telegram with retry logic"""
    global message_counter
    for attempt in range(max_retries):
        try:
            message_counter += 1
            logger.info(f"📤 Sending message #{message_counter}")
            bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
            logger.info(f"✅ Message #{message_counter} sent successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                logger.error(f"🚫 All {max_retries} attempts failed")
    return False

def fetch_all_live_matches():
    """Fetch all live matches from Sportmonks API"""
    try:
        logger.info("🌐 Fetching live matches from Sportmonks...")
        
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        
        response = requests.get(url, timeout=Config.API_TIMEOUT)
        
        if response.status_code != 200:
            logger.error(f"❌ API Error: {response.status_code}")
            if response.status_code == 401:
                logger.error("❌ Invalid API Key")
            elif response.status_code == 429:
                logger.error("❌ Rate Limit Exceeded")
            return []
        
        data = response.json()
        all_matches = data.get("data", [])
        logger.info(f"📊 Total matches from API: {len(all_matches)}")
        
        return all_matches
        
    except Exception as e:
        logger.error(f"❌ API fetch error: {e}")
        return []

def filter_live_matches(all_matches):
    """Filter live matches for analysis"""
    live_matches = []
    
    for match in all_matches:
        try:
            league_id = match.get("league_id")
            status = match.get("status", "")
            minute = match.get("minute", "")
            participants = match.get("participants", [])
            
            # Check if match is LIVE and has valid minute
            if status == "LIVE" and minute and minute not in ["FT", "HT", "PEN", "BT", "Canceled"]:
                if len(participants) >= 2:
                    home_team = participants[0].get("name", "Unknown Home")
                    away_team = participants[1].get("name", "Unknown Away")
                    
                    home_score = match.get("scores", {}).get("home_score", 0)
                    away_score = match.get("scores", {}).get("away_score", 0)
                    
                    # Parse minute
                    current_minute = parse_minute(minute)
                    
                    if current_minute >= 35:  # 35+ minutes only
                        league_name = TOP_LEAGUES.get(league_id, f"League {league_id}")
                        
                        match_data = {
                            "home": home_team,
                            "away": away_team,
                            "league": league_name,
                            "score": f"{home_score}-{away_score}",
                            "minute": minute,
                            "current_minute": current_minute,
                            "home_score": home_score,
                            "away_score": away_score,
                            "status": status,
                            "match_id": match.get("id"),
                            "is_live": True,
                            "timestamp": get_pakistan_time()
                        }
                        
                        live_matches.append(match_data)
                        logger.info(f"✅ Added: {home_team} vs {away_team} - {minute} - {home_score}-{away_score}")
                        
        except Exception as e:
            logger.error(f"❌ Error processing match: {e}")
            continue
    
    return live_matches

def parse_minute(minute_str):
    """Parse minute string to integer"""
    try:
        if isinstance(minute_str, str):
            if "'" in minute_str:
                return int(minute_str.replace("'", ""))
            elif minute_str.isdigit():
                return int(minute_str)
            elif '+' in minute_str:
                return int(minute_str.split('+')[0])
        elif isinstance(minute_str, int):
            return minute_str
    except:
        pass
    return 0

def analyze_match_prediction(match_data):
    """Analyze match and make prediction"""
    try:
        home_score = match_data['home_score']
        away_score = match_data['away_score']
        current_minute = match_data['current_minute']
        goal_difference = home_score - away_score
        
        # Base prediction logic
        if current_minute >= 75:  # Late game
            if goal_difference > 0:
                prediction = "Home Win"
                confidence = 75 + min(15, goal_difference * 8)
            elif goal_difference < 0:
                prediction = "Away Win"
                confidence = 75 + min(15, abs(goal_difference) * 8)
            else:
                prediction = "Draw"
                confidence = 60
        elif current_minute >= 60:  # Mid-late game
            if abs(goal_difference) >= 2:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 70 + min(10, abs(goal_difference) * 5)
            elif abs(goal_difference) == 1:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 60
            else:
                prediction = "Draw"
                confidence = 55
        else:  # Early-mid game (35-59 minutes)
            if abs(goal_difference) >= 2:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 65 + min(10, abs(goal_difference) * 4)
            elif abs(goal_difference) == 1:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 58
            else:
                prediction = "Draw"
                confidence = 52
        
        # Adjust confidence based on minute
        minute_bonus = min(10, (current_minute - 35) / 3)  # Bonus for later minutes
        confidence += minute_bonus
        
        # Cap confidence
        confidence = min(90, max(50, round(confidence)))
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'method': 'score_time_analysis',
            'goal_difference': goal_difference
        }
        
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
        return {'prediction': 'Unknown', 'confidence': 0, 'method': 'error'}

def format_prediction_message(match_data, prediction):
    """Format prediction message for Telegram"""
    current_time = format_pakistan_time()
    
    # Emoji based on confidence
    if prediction['confidence'] >= 75:
        confidence_emoji = "🎯🔥"
    elif prediction['confidence'] >= 65:
        confidence_emoji = "🎯⭐"
    else:
        confidence_emoji = "🎯"
    
    message = f"""⚽ **LIVE MATCH PREDICTION** ⚽

🏆 **League:** {match_data['league']}
🕒 **Minute:** {match_data['minute']}
📊 **Score:** {match_data['score']}

🏠 **{match_data['home']}** vs 🛫 **{match_data['away']}**

🔮 **Prediction:** {prediction['prediction']}
{confidence_emoji} **Confidence:** {prediction['confidence']}%
🛠️ **Method:** {prediction['method']}

⏰ **Analysis Time:** {current_time}
🔍 **Match State:** {get_match_state(match_data['current_minute'], prediction['goal_difference'])}

💡 **Analysis:** Based on current score, match timing, and goal difference.

⚠️ *For informational purposes only. Bet responsibly.*"""
    
    return message

def get_match_state(minute, goal_difference):
    """Get match state description"""
    if minute >= 80:
        if abs(goal_difference) >= 2:
            return "Late Game - Strong Lead"
        elif abs(goal_difference) == 1:
            return "Late Game - Close Match"
        else:
            return "Late Game - Draw"
    elif minute >= 60:
        return "Mid-Late Game"
    else:
        return "First Half - Developing"
