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

# Environment variables - PRIMARY: API-Football, SECONDARY: SportMonks
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()  # Primary API
SPORTMONKS_API = os.getenv("SPORTMONKS_API", "").strip()      # Secondary API
RAPIDAPI_HOST = "api-football-v1.p.rapidapi.com"  # API-Football host

logger.info("🚀 Starting Dual-API Football Prediction Bot...")

# Validate environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found")

# Check API availability
API_FOOTBALL_AVAILABLE = bool(API_FOOTBALL_KEY)
SPORTMONKS_AVAILABLE = bool(SPORTMONKS_API)

if not API_FOOTBALL_AVAILABLE and not SPORTMONKS_AVAILABLE:
    logger.error("❌ No API keys found - both API-Football and SportMonks missing")
else:
    logger.info(f"📊 API Status - API-Football: {'✅' if API_FOOTBALL_AVAILABLE else '❌'}, SportMonks: {'✅' if SPORTMONKS_AVAILABLE else '❌'}")

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

# League configurations for both APIs
LEAGUE_MAPPINGS = {
    'api_football': {
        39: "Premier League", 140: "La Liga", 78: "Bundesliga", 
        135: "Serie A", 61: "Ligue 1", 94: "Primeira Liga"
    },
    'sportmonks': {
        39: "Premier League", 140: "La Liga", 78: "Bundesliga",
        135: "Serie A", 61: "Ligue 1", 94: "Primeira Liga"
    }
}

# Configuration
class Config:
    BOT_CYCLE_INTERVAL = 180  # 3 minutes
    MIN_CONFIDENCE_THRESHOLD = 58  # 58% minimum confidence
    API_TIMEOUT = 15
    MAX_RETRIES = 3

# Global variables
bot_started = False
message_counter = 0
historical_data = {}
model = None
scaler = StandardScaler()

# API usage tracker
api_usage_tracker = {
    'api_football': {'count': 0, 'reset_time': datetime.now(), 'failures': 0, 'last_success': datetime.now()},
    'sportmonks': {'count': 0, 'reset_time': datetime.now(), 'failures': 0, 'last_success': datetime.now()}
}

def get_pakistan_time():
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M %Z')

def send_telegram_message(message, max_retries=3):
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

def fetch_api_football_live_matches():
    """Fetch live matches from API-Football (Primary)"""
    try:
        if not API_FOOTBALL_AVAILABLE:
            return []
            
        logger.info("🌐 Fetching live matches from API-Football...")
        
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        headers = {
            'x-rapidapi-host': RAPIDAPI_HOST,
            'x-rapidapi-key': API_FOOTBALL_KEY
        }
        params = {'live': 'all'}
        
        response = requests.get(url, headers=headers, params=params, timeout=Config.API_TIMEOUT)
        
        if response.status_code != 200:
            logger.error(f"❌ API-Football Error: {response.status_code}")
            return []
        
        data = response.json()
        all_matches = data.get("response", [])
        logger.info(f"📊 API-Football matches found: {len(all_matches)}")
        
        return all_matches
        
    except Exception as e:
        logger.error(f"❌ API-Football fetch error: {e}")
        return []

def fetch_sportmonks_live_matches():
    """Fetch live matches from SportMonks (Secondary)"""
    try:
        if not SPORTMONKS_AVAILABLE:
            return []
            
        logger.info("🌐 Fetching live matches from SportMonks...")
        
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        response = requests.get(url, timeout=Config.API_TIMEOUT)
        
        if response.status_code != 200:
            logger.error(f"❌ SportMonks Error: {response.status_code}")
            return []
        
        data = response.json()
        all_matches = data.get("data", [])
        logger.info(f"📊 SportMonks matches found: {len(all_matches)}")
        
        return all_matches
        
    except Exception as e:
        logger.error(f"❌ SportMonks fetch error: {e}")
        return []

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

def process_api_football_matches(raw_matches):
    """Process API-Football match data"""
    live_matches = []
    
    for match in raw_matches:
        try:
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            goals = match.get("goals", {})
            league_info = match.get("league", {})
            
            status = fixture.get("status", {}).get("short", "")
            minute = fixture.get("status", {}).get("elapsed", "")
            home_team = teams.get("home", {}).get("name", "Unknown Home")
            away_team = teams.get("away", {}).get("name", "Unknown Away")
            home_score = goals.get("home", 0)
            away_score = goals.get("away", 0)
            league_id = league_info.get("id")
            league_name = league_info.get("name", f"League {league_id}")
            
            current_minute = parse_minute(minute)
            
            if status == "LIVE" and current_minute >= 35:
                match_data = {
                    "home": home_team, "away": away_team, "league": league_name,
                    "score": f"{home_score}-{away_score}", "minute": f"{minute}'",
                    "current_minute": current_minute, "home_score": home_score,
                    "away_score": away_score, "status": status, 
                    "match_id": fixture.get("id"), "is_live": True,
                    "timestamp": get_pakistan_time(), "source": "api_football"
                }
                live_matches.append(match_data)
                logger.info(f"✅ API-Football: {home_team} vs {away_team} - {minute}' - {home_score}-{away_score}")
                
        except Exception as e:
            logger.error(f"❌ Error processing API-Football match: {e}")
            continue
    
    return live_matches

def process_sportmonks_matches(raw_matches):
    """Process SportMonks match data"""
    live_matches = []
    
    for match in raw_matches:
        try:
            league_id = match.get("league_id")
            status = match.get("status", "")
            minute = match.get("minute", "")
            participants = match.get("participants", [])
            
            if status == "LIVE" and minute and minute not in ["FT", "HT", "PEN", "BT"]:
                if len(participants) >= 2:
                    home_team = participants[0].get("name", "Unknown Home")
                    away_team = participants[1].get("name", "Unknown Away")
                    home_score = match.get("scores", {}).get("home_score", 0)
                    away_score = match.get("scores", {}).get("away_score", 0)
                    current_minute = parse_minute(minute)
                    
                    if current_minute >= 35:
                        league_name = LEAGUE_MAPPINGS['sportmonks'].get(league_id, f"League {league_id}")
                        match_data = {
                            "home": home_team, "away": away_team, "league": league_name,
                            "score": f"{home_score}-{away_score}", "minute": minute,
                            "current_minute": current_minute, "home_score": home_score,
                            "away_score": away_score, "status": status, 
                            "match_id": match.get("id"), "is_live": True,
                            "timestamp": get_pakistan_time(), "source": "sportmonks"
                        }
                        live_matches.append(match_data)
                        logger.info(f"✅ SportMonks: {home_team} vs {away_team} - {minute} - {home_score}-{away_score}")
                        
        except Exception as e:
            logger.error(f"❌ Error processing SportMonks match: {e}")
            continue
    
    return live_matches

def fetch_all_live_matches():
    """Fetch matches from both APIs with primary/secondary fallback"""
    all_matches = []
    
    # Try API-Football first (Primary)
    if API_FOOTBALL_AVAILABLE:
        logger.info("🔍 Trying API-Football (Primary)...")
        api_football_raw = fetch_api_football_live_matches()
        api_football_matches = process_api_football_matches(api_football_raw)
        
        if api_football_matches:
            all_matches.extend(api_football_matches)
            logger.info(f"✅ API-Football provided {len(api_football_matches)} matches")
        else:
            logger.info("❌ API-Football returned no matches")
    
    # Try SportMonks as fallback (Secondary)
    if not all_matches and SPORTMONKS_AVAILABLE:
        logger.info("🔍 Trying SportMonks (Secondary)...")
        sportmonks_raw = fetch_sportmonks_live_matches()
        sportmonks_matches = process_sportmonks_matches(sportmonks_raw)
        
        if sportmonks_matches:
            all_matches.extend(sportmonks_matches)
            logger.info(f"✅ SportMonks provided {len(sportmonks_matches)} matches")
    
    # Remove duplicates
    unique_matches = []
    seen_matches = set()
    
    for match in all_matches:
        match_key = f"{match['home']}_{match['away']}_{match['league']}"
        if match_key not in seen_matches:
            seen_matches.add(match_key)
            unique_matches.append(match)
    
    logger.info(f"🎯 Total unique live matches: {len(unique_matches)}")
    return unique_matches

def analyze_match_prediction(match_data):
    """Analyze match and make prediction"""
    try:
        home_score = match_data['home_score']
        away_score = match_data['away_score']
        current_minute = match_data['current_minute']
        goal_difference = home_score - away_score
        
        # Enhanced prediction logic
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
        minute_bonus = min(10, (current_minute - 35) / 3)
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
    
    if prediction['confidence'] >= 75:
        confidence_emoji = "🎯🔥"
    elif prediction['confidence'] >= 65:
        confidence_emoji = "🎯⭐"
    else:
        confidence_emoji = "🎯"
    
    message = f"""⚽ **DUAL-API LIVE PREDICTION** ⚽

🏆 **League:** {match_data['league']}
🕒 **Minute:** {match_data['minute']}
📊 **Score:** {match_data['score']}
🌐 **Source:** {match_data.get('source', 'API-Football')}

🏠 **{match_data['home']}** vs 🛫 **{match_data['away']}**

🔮 **Prediction:** {prediction['prediction']}
{confidence_emoji} **Confidence:** {prediction['confidence']}%
🛠️ **Method:** {prediction['method']}

⏰ **Analysis Time:** {current_time}

💡 **Analysis:** Based on current score, match timing, and goal difference.

⚠️ *Dual-API system active. For informational purposes only.*"""
    
    return message

@app.route("/")
def home():
    return f"""
    <html>
        <head><title>Dual-API Football Prediction Bot</title></head>
        <body>
            <h1>⚽ Dual-API Football Prediction Bot</h1>
            <p><strong>Status:</strong> 🟢 Running</p>
            <p><strong>Started:</strong> {format_pakistan_time()}</p>
            <p><strong>Messages Sent:</strong> {message_counter}</p>
            <p><strong>API Status:</strong> API-Football: {'✅' if API_FOOTBALL_AVAILABLE else '❌'}, SportMonks: {'✅' if SPORTMONKS_AVAILABLE else '❌'}</p>
            <p><a href="/health">Health Check</a> | <a href="/live-matches">Live Matches</a></p>
        </body>
    </html>
    """

@app.route("/health")
def health():
    status = {
        "status": "healthy",
        "timestamp": format_pakistan_time(),
        "bot_started": bot_started,
        "messages_sent": message_counter,
        "api_football": "available" if API_FOOTBALL_AVAILABLE else "missing",
        "sportmonks": "available" if SPORTMONKS_AVAILABLE else "missing"
    }
    return json.dumps(status, indent=2)

@app.route("/live-matches")
def live_matches():
    try:
        all_matches = fetch_all_live_matches()
        result = {
            "timestamp": format_pakistan_time(),
            "live_matches": len(all_matches),
            "matches": all_matches
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def send_startup_message():
    startup_msg = f"""🚀 **Dual-API Football Prediction Bot Started!**

⏰ **Startup Time:** {format_pakistan_time()}
📊 **API Status:**
   • API-Football (Primary): {'✅ Connected' if API_FOOTBALL_AVAILABLE else '❌ Missing'}
   • SportMonks (Secondary): {'✅ Connected' if SPORTMONKS_AVAILABLE else '❌ Missing'}

🎯 **Settings:**
   • Check Interval: {Config.BOT_CYCLE_INTERVAL} seconds
   • Min Confidence: {Config.MIN_CONFIDENCE_THRESHOLD}%
   • Minute Range: 35+ minutes

🤖 **Dual-API System:** 
   • Primary: API-Football
   • Fallback: SportMonks
   • Automatic failover

Bot is now actively scanning for live matches with dual-API reliability!"""
    send_telegram_message(startup_msg)

def bot_worker():
    global bot_started
    logger.info("🔄 Starting Dual-API Bot Worker...")
    bot_started = True
    
    time.sleep(2)
    send_startup_message()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            current_time = format_pakistan_time()
            logger.info(f"🔄 Cycle #{cycle} at {current_time}")
            
            all_matches = fetch_all_live_matches()
            logger.info(f"📊 Found {len(all_matches)} live matches")
            
            predictions_sent = 0
            for match in all_matches:
                try:
                    prediction = analyze_match_prediction(match)
                    if prediction['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
                        message = format_prediction_message(match, prediction)
                        if send_telegram_message(message):
                            predictions_sent += 1
                            logger.info(f"✅ Prediction sent: {match['home']} vs {match['away']} - {prediction['confidence']}%")
                        time.sleep(2)
                    else:
                        logger.info(f"📊 Low confidence: {match['home']} vs {match['away']} - {prediction['confidence']}%")
                except Exception as e:
                    logger.error(f"❌ Match analysis error: {e}")
                    continue
            
            if predictions_sent > 0:
                logger.info(f"🎯 Cycle #{cycle}: {predictions_sent} predictions sent")
            else:
                logger.info(f"😴 Cycle #{cycle}: No high-confidence predictions")
            
            logger.info(f"⏰ Waiting {Config.BOT_CYCLE_INTERVAL} seconds...")
            time.sleep(Config.BOT_CYCLE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Bot worker error: {e}")
            time.sleep(Config.BOT_CYCLE_INTERVAL)

def start_bot():
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 Dual-API Bot started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return False

# Auto-start bot
logger.info("🎯 Auto-starting Dual-API Football Prediction Bot...")
if start_bot():
    logger.info("✅ Bot auto-started successfully")
else:
    logger.error("❌ Bot auto-start failed")

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
