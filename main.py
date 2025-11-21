import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask, request
import logging
import random
from datetime import datetime, timedelta
import pytz
from threading import Thread
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")

logger.info("🚀 Initializing API-Safe Multi-Source Bot...")

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
    203: "UEFA Champions League"
}

# Global variables
bot_started = False
message_counter = 0
historical_data = {}
api_usage_tracker = {
    'sportmonks': {'count': 0, 'reset_time': datetime.now()},
    'github': {'count': 0, 'reset_time': datetime.now()}
}

def get_pakistan_time():
    """Get current Pakistan time"""
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    """Format datetime in Pakistan time"""
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M %Z')

def check_api_limits(api_name):
    """Check if we're within API limits"""
    try:
        current_time = datetime.now()
        api_data = api_usage_tracker[api_name]
        
        # Reset counter every hour
        if (current_time - api_data['reset_time']).seconds >= 3600:
            api_data['count'] = 0
            api_data['reset_time'] = current_time
            logger.info(f"🔄 {api_name.upper()} API counter reset")
        
        # Check limits
        if api_name == 'sportmonks':
            # 20 requests/hour for free plan
            if api_data['count'] >= 15:  # Safe buffer
                logger.warning(f"⚠️ {api_name.upper()} API near limit: {api_data['count']}/20")
                return False
            if api_data['count'] >= 20:
                logger.error(f"🚫 {api_name.upper()} API limit reached")
                return False
                
        elif api_name == 'github':
            # 60 requests/hour for GitHub
            if api_data['count'] >= 50:  # Safe buffer
                logger.warning(f"⚠️ {api_name.upper()} API near limit: {api_data['count']}/60")
                return False
            if api_data['count'] >= 60:
                logger.error(f"🚫 {api_name.upper()} API limit reached")
                return False
        
        api_data['count'] += 1
        return True
        
    except Exception as e:
        logger.error(f"❌ API limit check error: {e}")
        return True  # Allow by default if check fails

def safe_api_call(url, api_name, timeout=10):
    """Make safe API call with rate limiting"""
    try:
        if not check_api_limits(api_name):
            logger.warning(f"⏸️ Skipping {api_name} call due to limits")
            return None
        
        response = requests.get(url, timeout=timeout)
        
        # Check for rate limit headers
        if response.status_code == 429:
            logger.warning(f"⏰ {api_name.upper()} rate limited, waiting...")
            time.sleep(60)  # Wait 1 minute
            return None
        
        if response.status_code == 200:
            return response
        else:
            logger.warning(f"❌ {api_name.upper()} API error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        logger.warning(f"⏰ {api_name.upper()} API timeout")
        return None
    except Exception as e:
        logger.error(f"❌ {api_name.upper()} API call error: {e}")
        return None

@app.route("/")
def health():
    return "⚽ API-Safe Multi-Source Bot is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

@app.route("/api-status")
def api_status():
    """Check API usage status"""
    status_msg = "📊 **API USAGE STATUS**\n\n"
    
    for api_name, data in api_usage_tracker.items():
        remaining_time = 3600 - (datetime.now() - data['reset_time']).seconds
        status_msg += f"**{api_name.upper()}:**\n"
        status_msg += f"• Requests: {data['count']}/"
        status_msg += f"{'20' if api_name == 'sportmonks' else '60'}\n"
        status_msg += f"• Reset in: {remaining_time//60} minutes\n"
        status_msg += f"• Status: {'✅ OK' if data['count'] < 15 else '⚠️ WARNING'}\n\n"
    
    return status_msg

def send_telegram_message(message):
    """Send message to Telegram with retry logic"""
    global message_counter
    try:
        message_counter += 1
        logger.info(f"📤 Sending message #{message_counter}")
        bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
        logger.info(f"✅ Message #{message_counter} sent successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send message #{message_counter}: {e}")
        return False

def fetch_petermclagan_data():
    """Fetch historical data from Peter McLagan FootballAPI"""
    try:
        if not check_api_limits('github'):
            return []
            
        logger.info("📊 Fetching Peter McLagan historical data...")
        
        base_url = "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/"
        
        datasets = {
            'premier_league': 'premier_league.csv',
            'la_liga': 'la_liga.csv', 
        }
        
        historical_matches = []
        
        for league, filename in datasets.items():
            try:
                url = base_url + filename
                response = safe_api_call(url, 'github', timeout=15)
                
                if response:
                    csv_data = io.StringIO(response.text)
                    df = pd.read_csv(csv_data)
                    
                    for _, row in df.iterrows():
                        match_data = {
                            'league': league.replace('_', ' ').title(),
                            'home_team': row.get('HomeTeam', ''),
                            'away_team': row.get('AwayTeam', ''),
                            'home_goals': row.get('FTHG', 0),
                            'away_goals': row.get('FTAG', 0),
                            'date': row.get('Date', ''),
                            'result': row.get('FTR', ''),
                            'source': 'petermclagan'
                        }
                        historical_matches.append(match_data)
                    
                    logger.info(f"✅ Loaded {len(df)} matches from {league}")
                else:
                    logger.warning(f"⚠️ Skipped {league} due to API limits")
                    
            except Exception as e:
                logger.error(f"❌ Error loading {league}: {e}")
                continue
        
        logger.info(f"📈 Peter McLagan matches: {len(historical_matches)}")
        return historical_matches
        
    except Exception as e:
        logger.error(f"❌ Peter McLagan API error: {e}")
        return []

def fetch_openfootball_data():
    """Fetch data from OpenFootball CSV auto-updates"""
    try:
        if not check_api_limits('github'):
            return []
            
        logger.info("📊 Fetching OpenFootball auto-update data...")
        
        base_url = "https://raw.githubusercontent.com/openfootball/"
        
        datasets = {
            'england': 'england/master/2023-24/eng.1.csv',
            'spain': 'spain/master/2023-24/es.1.csv',
        }
        
        openfootball_matches = []
        
        for country, path in datasets.items():
            try:
                url = base_url + path
                response = safe_api_call(url, 'github', timeout=15)
                
                if response:
                    lines = response.text.strip().split('\n')
                    
                    for line in lines[1:6]:  # Only first 5 matches to save API calls
                        parts = line.split(',')
                        if len(parts) >= 7:
                            match_data = {
                                'league': f"{country.title()} League",
                                'home_team': parts[1].strip(),
                                'away_team': parts[2].strip(),
                                'home_goals': int(parts[3]) if parts[3].isdigit() else 0,
                                'away_goals': int(parts[4]) if parts[4].isdigit() else 0,
                                'date': parts[0],
                                'result': 'H' if int(parts[3]) > int(parts[4]) else 'A' if int(parts[3]) < int(parts[4]) else 'D',
                                'source': 'openfootball'
                            }
                            openfootball_matches.append(match_data)
                    
                    logger.info(f"✅ Loaded {min(5, len(lines)-1)} matches from {country}")
                else:
                    logger.warning(f"⚠️ Skipped {country} due to API limits")
                    
            except Exception as e:
                logger.error(f"❌ Error loading {country}: {e}")
                continue
        
        logger.info(f"📈 OpenFootball matches: {len(openfootball_matches)}")
        return openfootball_matches
        
    except Exception as e:
        logger.error(f"❌ OpenFootball API error: {e}")
        return []

def fetch_current_live_matches():
    """Fetch current live matches from Sportmonks with API protection"""
    try:
        if not check_api_limits('sportmonks'):
            logger.warning("⏸️ Sportmonks API limit reached, skipping live matches")
            return []
            
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("🌐 Fetching live matches from Sportmonks...")
        
        response = safe_api_call(url, 'sportmonks', timeout=15)
        
        if not response:
            return []
        
        data = response.json()
        current_matches = []
        
        for match in data.get("data", []):
            league_id = match.get("league_id")
            
            if league_id in TOP_LEAGUES:
                status = match.get("status", "")
                minute = match.get("minute", "")
                
                if status == "LIVE" and minute and minute != "FT" and minute != "HT":
                    participants = match.get("participants", [])
                    
                    if len(participants) >= 2:
                        home_team = participants[0].get("name", "Unknown Home")
                        away_team = participants[1].get("name", "Unknown Away")
                        
                        home_score = match.get("scores", {}).get("home_score", 0)
                        away_score = match.get("scores", {}).get("away_score", 0)
                        
                        try:
                            if isinstance(minute, str) and "'" in minute:
                                current_minute = int(minute.replace("'", ""))
                            else:
                                current_minute = int(minute)
                        except:
                            current_minute = 0
                        
                        if 60 <= current_minute <= 89:
                            match_data = {
                                "home": home_team,
                                "away": away_team,
                                "league": TOP_LEAGUES[league_id],
                                "score": f"{home_score}-{away_score}",
                                "minute": minute,
                                "current_minute": current_minute,
                                "home_score": home_score,
                                "away_score": away_score,
                                "status": status,
                                "match_id": match.get("id"),
                                "is_live": True
                            }
                            
                            current_matches.append(match_data)
        
        logger.info(f"📊 Live matches found: {len(current_matches)}")
        return current_matches
        
    except Exception as e:
        logger.error(f"❌ Live matches error: {e}")
        return []

# ... [Rest of the code remains similar but with API protection]

def bot_worker():
    """Main bot worker with API protection"""
    global bot_started
    logger.info("🔄 Starting API-Safe Bot...")
    
    # Load historical data first
    logger.info("📥 Loading historical databases...")
    if load_historical_data():
        logger.info("✅ Historical data loaded successfully")
    
    time.sleep(10)
    
    logger.info("📤 Sending startup message...")
    send_startup_message()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            logger.info(f"🔄 API-Safe Cycle #{cycle} at {format_pakistan_time()}")
            
            # Reload historical data every 24 cycles (approx 3 hours) to save API calls
            if cycle % 24 == 0:
                logger.info("🔄 Reloading historical data...")
                load_historical_data()
            
            # Analyze matches
            predictions = analyze_with_multiple_sources()
            logger.info(f"📈 Cycle #{cycle}: {predictions} analyses sent")
            
            # Send API status every 12 cycles
            if cycle % 12 == 0:
                api_status = get_api_status_message()
                send_telegram_message(api_status)
            
            # Wait 10 minutes instead of 7 to reduce API calls
            logger.info("⏰ Waiting 10 minutes for next cycle...")
            time.sleep(600)  # 10 minutes
            
        except Exception as e:
            logger.error(f"❌ API-safe bot error: {e}")
            time.sleep(600)

def get_api_status_message():
    """Get API status message"""
    status_msg = "📊 **API USAGE STATUS**\n\n"
    
    for api_name, data in api_usage_tracker.items():
        remaining_time = 3600 - (datetime.now() - data['reset_time']).seconds
        used = data['count']
        limit = 20 if api_name == 'sportmonks' else 60
        
        status_msg += f"**{api_name.upper()}:** {used}/{limit} requests\n"
        status_msg += f"Reset in: {remaining_time//60}m {remaining_time%60}s\n"
        
        if used >= limit * 0.8:
            status_msg += "Status: ⚠️ **NEAR LIMIT**\n"
        elif used >= limit * 0.5:
            status_msg += "Status: 🟡 **MODERATE**\n"
        else:
            status_msg += "Status: ✅ **SAFE**\n"
        
        status_msg += "\n"
    
    status_msg += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
    status_msg += "🔄 Next check in 2 hours"
    
    return status_msg

# ... [Rest of the functions remain similar]

# Auto-start bot
logger.info("🎯 Auto-starting API-Safe Multi-Source Bot...")
start_bot_thread()

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
