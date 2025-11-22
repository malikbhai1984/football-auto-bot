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

# Environment variables - SportMonks as PRIMARY now
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
SPORTMONKS_API = os.getenv("SPORTMONKS_API", "").strip()  # Primary API

logger.info("🚀 Starting SportMonks Football Prediction Bot...")

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
    39: "Premier League", 140: "La Liga", 78: "Bundesliga", 135: "Serie A", 
    61: "Ligue 1", 94: "Primeira Liga", 88: "Eredivisie", 203: "UEFA Champions League",
    2: "Champions League", 5: "Europa League", 564: "World Cup", 82: "EFL Championship",
    384: "Serie B", 462: "Coupe de France", 539: "UEFA Europa Conference League",
    531: "Asian Cup", 8: "Euro Championship", 1: "World Cup"
}

# Configuration
class Config:
    BOT_CYCLE_INTERVAL = 120  # 2 minutes
    MIN_CONFIDENCE_THRESHOLD = 50  # 50% minimum confidence
    API_TIMEOUT = 15
    MAX_RETRIES = 3

# Global variables
bot_started = False
message_counter = 0

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

def debug_sportmonks_api():
    """Debug function to check SportMonks API response"""
    try:
        logger.info("🔍 DEBUG: Testing SportMonks API...")
        
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        response = requests.get(url, timeout=15)
        
        logger.info(f"📡 DEBUG: API Status Code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"❌ DEBUG: API Error - {response.status_code}")
            return []
        
        data = response.json()
        all_matches = data.get("data", [])
        logger.info(f"📊 DEBUG: Total matches from API: {len(all_matches)}")
        
        # Detailed match info
        for i, match in enumerate(all_matches[:10]):  # First 10 matches only
            league_id = match.get("league_id")
            status = match.get("status", "")
            minute = match.get("minute", "")
            participants = match.get("participants", [])
            
            logger.info(f"🏟️ DEBUG Match {i+1}:")
            logger.info(f"   League ID: {league_id}")
            logger.info(f"   Status: {status}")
            logger.info(f"   Minute: {minute}")
            
            if len(participants) >= 2:
                home_team = participants[0].get("name", "Unknown")
                away_team = participants[1].get("name", "Unknown")
                logger.info(f"   Teams: {home_team} vs {away_team}")
            else:
                logger.info(f"   Teams: Not enough participants")
        
        return all_matches
        
    except Exception as e:
        logger.error(f"❌ DEBUG: API test error: {e}")
        return []

def fetch_sportmonks_live_matches():
    """Fetch live matches from SportMonks with detailed logging"""
    try:
        logger.info("🌐 Fetching live matches from SportMonks...")
        
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        response = requests.get(url, timeout=Config.API_TIMEOUT)
        
        if response.status_code != 200:
            logger.error(f"❌ SportMonks Error: {response.status_code}")
            return []
        
        data = response.json()
        all_matches = data.get("data", [])
        logger.info(f"📊 Raw matches from SportMonks: {len(all_matches)}")
        
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

def filter_live_matches_debug(all_matches):
    """Filter live matches with detailed debugging"""
    live_matches = []
    
    logger.info(f"🔍 Filtering {len(all_matches)} matches...")
    
    for i, match in enumerate(all_matches):
        try:
            league_id = match.get("league_id")
            status = match.get("status", "")
            minute = match.get("minute", "")
            participants = match.get("participants", [])
            
            logger.info(f"🎯 Checking match {i+1}: Status='{status}', Minute='{minute}'")
            
            # Check if match is LIVE
            if status != "LIVE":
                logger.info(f"   ❌ Not LIVE - Status: {status}")
                continue
            
            if not minute or minute in ["FT", "HT", "PEN", "BT", "Canceled"]:
                logger.info(f"   ❌ Invalid minute: {minute}")
                continue
            
            if len(participants) < 2:
                logger.info(f"   ❌ Not enough participants: {len(participants)}")
                continue
            
            # Get match details
            home_team = participants[0].get("name", "Unknown Home")
            away_team = participants[1].get("name", "Unknown Away")
            home_score = match.get("scores", {}).get("home_score", 0)
            away_score = match.get("scores", {}).get("away_score", 0)
            current_minute = parse_minute(minute)
            
            logger.info(f"   ✅ Valid match: {home_team} vs {away_team}")
            logger.info(f"   📊 Score: {home_score}-{away_score}, Minute: {current_minute}")
            
            # EXTENDED minute range for testing
            if current_minute >= 25:  # 25+ minutes now
                league_name = TOP_LEAGUES.get(league_id, f"League {league_id}")
                
                match_data = {
                    "home": home_team, "away": away_team, "league": league_name,
                    "score": f"{home_score}-{away_score}", "minute": minute,
                    "current_minute": current_minute, "home_score": home_score,
                    "away_score": away_score, "status": status, 
                    "match_id": match.get("id"), "is_live": True,
                    "timestamp": get_pakistan_time(), "source": "sportmonks"
                }
                
                live_matches.append(match_data)
                logger.info(f"   🎯 ADDED TO PREDICTION: {home_team} vs {away_team}")
            else:
                logger.info(f"   ❌ Minute too early: {current_minute}")
                
        except Exception as e:
            logger.error(f"❌ Error processing match: {e}")
            continue
    
    logger.info(f"🎯 Final filtered matches for prediction: {len(live_matches)}")
    return live_matches

def analyze_match_prediction_simple(match_data):
    """Simple but effective match prediction"""
    try:
        home_score = match_data['home_score']
        away_score = match_data['away_score']
        current_minute = match_data['current_minute']
        goal_difference = home_score - away_score
        
        logger.info(f"🔮 Analyzing: {match_data['home']} vs {match_data['away']} - {current_minute}min - {home_score}-{away_score}")
        
        # SIMPLIFIED PREDICTION LOGIC
        if current_minute >= 70:  # Late game
            if goal_difference > 0:
                prediction = "Home Win"
                confidence = 70 + min(20, goal_difference * 10)
            elif goal_difference < 0:
                prediction = "Away Win"
                confidence = 70 + min(20, abs(goal_difference) * 10)
            else:
                prediction = "Draw"
                confidence = 55
        elif current_minute >= 45:  # Mid game
            if abs(goal_difference) >= 2:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 65 + min(15, abs(goal_difference) * 7)
            elif abs(goal_difference) == 1:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 58
            else:
                prediction = "Draw"
                confidence = 52
        else:  # Early game (25-44 minutes)
            if abs(goal_difference) >= 2:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 60 + min(10, abs(goal_difference) * 5)
            elif abs(goal_difference) == 1:
                prediction = "Home Win" if goal_difference > 0 else "Away Win"
                confidence = 55
            else:
                prediction = "Draw"
                confidence = 50
        
        # Confidence boost for later minutes
        if current_minute > 60:
            confidence += min(10, (current_minute - 60) / 2)
        
        confidence = min(85, max(45, round(confidence)))
        
        logger.info(f"   📈 Prediction: {prediction}, Confidence: {confidence}%")
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'method': 'enhanced_analysis',
            'goal_difference': goal_difference
        }
        
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
        return {'prediction': 'Unknown', 'confidence': 0, 'method': 'error'}

def format_prediction_message(match_data, prediction):
    """Format prediction message for Telegram"""
    current_time = format_pakistan_time()
    
    if prediction['confidence'] >= 70:
        confidence_emoji = "🎯🔥"
    elif prediction['confidence'] >= 60:
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

💡 **Analysis:** Based on current score and match timing.

⚠️ *For informational purposes only.*"""
    
    return message

@app.route("/")
def home():
    return f"""
    <html>
        <head><title>SportMonks Prediction Bot</title></head>
        <body>
            <h1>⚽ SportMonks Prediction Bot</h1>
            <p><strong>Status:</strong> 🟢 Running</p>
            <p><strong>Started:</strong> {format_pakistan_time()}</p>
            <p><strong>Messages Sent:</strong> {message_counter}</p>
            <p><a href="/health">Health Check</a> | <a href="/debug">Debug</a> | <a href="/live-matches">Live Matches</a></p>
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
        "sportmonks_api": "available" if SPORTMONKS_API else "missing"
    }
    return json.dumps(status, indent=2)

@app.route("/debug")
def debug():
    """Debug endpoint to see what's happening"""
    try:
        all_matches = debug_sportmonks_api()
        filtered_matches = filter_live_matches_debug(all_matches)
        
        result = {
            "timestamp": format_pakistan_time(),
            "total_matches": len(all_matches),
            "live_matches": len(filtered_matches),
            "matches": filtered_matches
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

@app.route("/live-matches")
def live_matches():
    try:
        all_matches = fetch_sportmonks_live_matches()
        filtered_matches = filter_live_matches_debug(all_matches)
        result = {
            "timestamp": format_pakistan_time(),
            "total_matches": len(all_matches),
            "live_matches": len(filtered_matches),
            "matches": filtered_matches
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def send_startup_message():
    startup_msg = f"""🚀 **SportMonks Prediction Bot Started!**

⏰ **Startup Time:** {format_pakistan_time()}
📊 **API Status:** ✅ Connected
🎯 **Settings:**
   • Check Interval: {Config.BOT_CYCLE_INTERVAL} seconds
   • Min Confidence: {Config.MIN_CONFIDENCE_THRESHOLD}%
   • Minute Range: 25+ minutes

🤖 **Enhanced Features:**
   • Detailed debugging
   • Lower confidence threshold
   • Extended minute range
   • Better logging

Bot is now actively scanning for live matches!"""
    send_telegram_message(startup_msg)

def bot_worker():
    global bot_started
    logger.info("🔄 Starting Enhanced Bot Worker...")
    bot_started = True
    
    # Run debug first to see what's happening
    logger.info("🔍 Running initial debug...")
    debug()
    
    time.sleep(2)
    send_startup_message()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            current_time = format_pakistan_time()
            logger.info(f"🔄 Cycle #{cycle} at {current_time}")
            
            # Fetch and filter matches
            all_matches = fetch_sportmonks_live_matches()
            live_matches = filter_live_matches_debug(all_matches)
            
            logger.info(f"📊 Found {len(live_matches)} live matches for analysis")
            
            predictions_sent = 0
            for match in live_matches:
                try:
                    # Make prediction
                    prediction = analyze_match_prediction_simple(match)
                    
                    # Send message if confidence is high enough
                    if prediction['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
                        message = format_prediction_message(match, prediction)
                        
                        if send_telegram_message(message):
                            predictions_sent += 1
                            logger.info(f"✅ PREDICTION SENT: {match['home']} vs {match['away']} - {prediction['confidence']}%")
                        
                        # Wait between messages
                        time.sleep(1)
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
        logger.info("🤖 Enhanced Bot started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return False

# Auto-start bot
logger.info("🎯 Auto-starting Enhanced SportMonks Prediction Bot...")
if start_bot():
    logger.info("✅ Bot auto-started successfully")
else:
    logger.error("❌ Bot auto-start failed")

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
