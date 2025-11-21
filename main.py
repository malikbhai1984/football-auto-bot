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

# Configuration Constants
class Config:
    SPORTMONKS_LIMIT_PER_MINUTE = 8
    GITHUB_LIMIT_PER_MINUTE = 10
    BOT_CYCLE_INTERVAL = 600  # 10 minutes
    DATA_CLEANUP_INTERVAL = 24  # cycles
    HISTORICAL_DATA_RELOAD = 24  # cycles

# Global variables
bot_started = False
message_counter = 0
historical_data = {}
model = None
scaler = StandardScaler()
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
            if api_data['count'] >= 15:  # Safe buffer
                logger.warning(f"⚠️ {api_name.upper()} API near limit: {api_data['count']}/20")
                return False
            if api_data['count'] >= 20:
                logger.error(f"🚫 {api_name.upper()} API limit reached")
                return False
                
        elif api_name == 'github':
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

def send_telegram_message(message, max_retries=3):
    """Send message to Telegram with retry logic"""
    global message_counter
    for attempt in range(max_retries):
        try:
            message_counter += 1
            logger.info(f"📤 Sending message #{message_counter} (Attempt {attempt + 1})")
            bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
            logger.info(f"✅ Message #{message_counter} sent successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Attempt {attempt + 1} failed for message #{message_counter}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # Wait before retry
            else:
                logger.error(f"🚫 All {max_retries} attempts failed for message #{message_counter}")
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
                            'source': 'petermclagan',
                            'timestamp': get_pakistan_time()
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
                                'source': 'openfootball',
                                'timestamp': get_pakistan_time()
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
                                "is_live": True,
                                "timestamp": get_pakistan_time()
                            }
                            
                            current_matches.append(match_data)
        
        logger.info(f"📊 Live matches found: {len(current_matches)}")
        return current_matches
        
    except Exception as e:
        logger.error(f"❌ Live matches error: {e}")
        return []

def load_historical_data():
    """Load historical data from multiple sources"""
    global historical_data
    try:
        logger.info("📥 Loading historical data from multiple sources...")
        
        # Fetch from both sources
        petermclagan_data = fetch_petermclagan_data()
        openfootball_data = fetch_openfootball_data()
        
        # Combine all data
        all_data = petermclagan_data + openfootball_data
        
        # Store in global variable with timestamp
        historical_data = {
            'matches': all_data,
            'last_updated': get_pakistan_time(),
            'total_matches': len(all_data),
            'sources': {
                'petermclagan': len(petermclagan_data),
                'openfootball': len(openfootball_data)
            }
        }
        
        logger.info(f"✅ Historical data loaded: {len(all_data)} total matches")
        logger.info(f"📊 Sources - PeterMcLagan: {len(petermclagan_data)}, OpenFootball: {len(openfootball_data)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Historical data loading error: {e}")
        return False

def train_ml_model():
    """Train ML model on historical data"""
    global model, scaler
    
    try:
        if not historical_data or 'matches' not in historical_data:
            logger.warning("⚠️ No historical data available for ML training")
            return False
        
        matches = historical_data['matches']
        if len(matches) < 50:  # Minimum matches required
            logger.warning(f"⚠️ Insufficient data for ML training: {len(matches)} matches")
            return False
        
        # Prepare features and labels
        features = []
        labels = []
        
        for match in matches:
            try:
                # Basic features
                home_goals = match.get('home_goals', 0)
                away_goals = match.get('away_goals', 0)
                
                # Determine result (H=Home Win, A=Away Win, D=Draw)
                result = match.get('result', '')
                if result == 'H':
                    label = 0  # Home win
                elif result == 'A':
                    label = 1  # Away win
                else:
                    label = 2  # Draw
                
                # Simple features for now
                feature = [home_goals, away_goals, random.random()]  # Add some randomness
                features.append(feature)
                labels.append(label)
                
            except Exception as e:
                continue
        
        if len(features) < 30:
            logger.warning("⚠️ Not enough valid matches for ML training")
            return False
        
        # Scale features
        features_scaled = scaler.fit_transform(features)
        
        # Train model
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(features_scaled, labels)
        
        logger.info(f"✅ ML Model trained on {len(features)} matches")
        return True
        
    except Exception as e:
        logger.error(f"❌ ML Model training error: {e}")
        return False

def predict_match_outcome(match_data, historical_matches):
    """Predict match outcome using ML and historical data"""
    try:
        if model is None:
            # Fallback to simple prediction based on historical data
            return simple_prediction(match_data, historical_matches)
        
        # Prepare features for prediction
        home_team = match_data['home']
        away_team = match_data['away']
        
        # Get team historical performance
        home_stats = get_team_stats(home_team, historical_matches)
        away_stats = get_team_stats(away_team, historical_matches)
        
        # Create feature vector
        features = [
            home_stats['avg_goals_for'],
            away_stats['avg_goals_for'],
            (home_stats['win_rate'] - away_stats['win_rate'])
        ]
        
        # Scale features and predict
        features_scaled = scaler.transform([features])
        prediction = model.predict(features_scaled)[0]
        probability = model.predict_proba(features_scaled)[0]
        
        outcomes = ['Home Win', 'Away Win', 'Draw']
        confidence = max(probability) * 100
        
        return {
            'prediction': outcomes[prediction],
            'confidence': round(confidence, 1),
            'method': 'ml_model'
        }
        
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
        # Fallback to simple prediction
        return simple_prediction(match_data, historical_matches)

def simple_prediction(match_data, historical_matches):
    """Simple prediction based on historical data"""
    home_team = match_data['home']
    away_team = match_data['away']
    current_score = match_data.get('home_score', 0), match_data.get('away_score', 0)
    
    home_stats = get_team_stats(home_team, historical_matches)
    away_stats = get_team_stats(away_team, historical_matches)
    
    # Simple logic based on current score and historical performance
    if current_score[0] > current_score[1]:
        prediction = "Home Win"
        confidence = 60 + home_stats['win_rate'] * 20
    elif current_score[0] < current_score[1]:
        prediction = "Away Win"
        confidence = 60 + away_stats['win_rate'] * 20
    else:
        prediction = "Draw"
        confidence = 40 + (home_stats['draw_rate'] + away_stats['draw_rate']) * 15
    
    return {
        'prediction': prediction,
        'confidence': min(95, max(30, confidence)),  # Cap between 30-95%
        'method': 'historical_analysis'
    }

def get_team_stats(team_name, historical_matches):
    """Get team statistics from historical matches"""
    team_matches = [m for m in historical_matches 
                   if m['home_team'] == team_name or m['away_team'] == team_name]
    
    if not team_matches:
        return {'win_rate': 0.3, 'draw_rate': 0.3, 'avg_goals_for': 1.2, 'total_matches': 0}
    
    wins = 0
    draws = 0
    goals_for = 0
    total_matches = len(team_matches)
    
    for match in team_matches:
        if match['home_team'] == team_name:
            goals_for += match.get('home_goals', 0)
            if match.get('result') == 'H':
                wins += 1
            elif match.get('result') == 'D':
                draws += 1
        else:
            goals_for += match.get('away_goals', 0)
            if match.get('result') == 'A':
                wins += 1
            elif match.get('result') == 'D':
                draws += 1
    
    return {
        'win_rate': wins / total_matches,
        'draw_rate': draws / total_matches,
        'avg_goals_for': goals_for / total_matches,
        'total_matches': total_matches
    }

def analyze_with_multiple_sources():
    """Main analysis function using multiple data sources"""
    try:
        logger.info("🔍 Starting multi-source analysis...")
        
        # Fetch current live matches
        live_matches = fetch_current_live_matches()
        
        if not live_matches:
            logger.info("😴 No live matches found for analysis")
            return 0
        
        predictions_sent = 0
        
        for match in live_matches:
            try:
                # Find relevant historical data
                historical_for_match = find_relevant_historical_data(match)
                
                if len(historical_for_match) >= 3:  # Minimum historical data
                    # Make prediction
                    prediction = predict_match_outcome(match, historical_for_match)
                    
                    # Format and send message
                    message = format_prediction_message(match, prediction, len(historical_for_match))
                    
                    if send_telegram_message(message):
                        predictions_sent += 1
                        logger.info(f"✅ Prediction sent for {match['home']} vs {match['away']}")
                    
                    # Wait between messages to avoid rate limiting
                    time.sleep(2)
                    
                else:
                    logger.info(f"📊 Insufficient historical data for {match['home']} vs {match['away']}")
                    
            except Exception as e:
                logger.error(f"❌ Error analyzing match {match.get('home', 'Unknown')}: {e}")
                continue
        
        logger.info(f"📈 Analysis complete: {predictions_sent} predictions sent")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Multi-source analysis error: {e}")
        return 0

def find_relevant_historical_data(match):
    """Find relevant historical data for a match"""
    if not historical_data or 'matches' not in historical_data:
        return []
    
    home_team = match['home']
    away_team = match['away']
    league = match['league']
    
    relevant_matches = []
    
    for historical_match in historical_data['matches']:
        # Check if teams match (either home-home or home-away)
        teams_match = (
            (historical_match['home_team'] == home_team and historical_match['away_team'] == away_team) or
            (historical_match['home_team'] == away_team and historical_match['away_team'] == home_team)
        )
        
        # Check if league is similar
        league_similar = (
            league.lower() in historical_match['league'].lower() or
            historical_match['league'].lower() in league.lower()
        )
        
        if teams_match or league_similar:
            relevant_matches.append(historical_match)
    
    return relevant_matches

def format_prediction_message(match, prediction, historical_count):
    """Format prediction message for Telegram"""
    current_time = format_pakistan_time()
    
    message = f"""⚽ **MATCH PREDICTION** ⚽

🏆 **League:** {match['league']}
🕒 **Minute:** {match['minute']}
📊 **Score:** {match['score']}

🏠 **{match['home']}** vs 🛫 **{match['away']}**

🔮 **Prediction:** {prediction['prediction']}
🎯 **Confidence:** {prediction['confidence']}%
🛠️ **Method:** {prediction['method']}

📈 **Historical Data:** {historical_count} matches analyzed
🕐 **Analysis Time:** {current_time}

⚠️ *Disclaimer: For entertainment purposes only. Bet responsibly.*"""
    
    return message

def cleanup_old_data():
    """Clean up old data to prevent memory issues"""
    global historical_data, message_counter
    
    try:
        current_time = get_pakistan_time()
        cutoff_time = current_time - timedelta(hours=24)
        
        # Clean historical data
        if historical_data and 'matches' in historical_data:
            original_count = len(historical_data['matches'])
            historical_data['matches'] = [
                m for m in historical_data['matches'] 
                if m.get('timestamp', current_time) > cutoff_time
            ]
            new_count = len(historical_data['matches'])
            
            if new_count < original_count:
                logger.info(f"🧹 Cleaned {original_count - new_count} old historical records")
        
        # Reset message counter if it gets too large
        if message_counter > 10000:
            message_counter = 0
            logger.info("🔄 Message counter reset")
            
        logger.info("✅ Data cleanup completed")
        
    except Exception as e:
        logger.error(f"❌ Data cleanup error: {e}")

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
    
    # Add historical data stats
    if historical_data:
        status_msg += f"📈 **Historical Data:** {historical_data.get('total_matches', 0)} matches\n"
        status_msg += f"🕒 **Last Updated:** {historical_data.get('last_updated', 'Never').strftime('%H:%M') if isinstance(historical_data.get('last_updated'), datetime) else 'Never'}\n\n"
    
    status_msg += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
    status_msg += f"📨 **Messages Sent:** {message_counter}\n"
    status_msg += "🔄 Next check in 2 hours"
    
    return status_msg

def send_startup_message():
    """Send startup message to owner"""
    startup_msg = f"""🚀 *API-Safe Multi-Source Bot Started Successfully!*

⏰ **Startup Time:** {format_pakistan_time()}
📊 **Data Sources:**
   • Sportmonks (Live Matches)
   • Peter McLagan (Historical)
   • OpenFootball (Historical)

🛡️ **Features:**
   • Rate Limiting Protection
   • Multi-source Analysis
   • ML Model Predictions
   • Automatic Data Cleaning

📈 **Initial Stats:**
   • Historical Matches: {historical_data.get('total_matches', 0) if historical_data else 0}
   • Top Leagues: {len(TOP_LEAGUES)}
   • Cycle Interval: {Config.BOT_CYCLE_INTERVAL} seconds

Bot is now running and will send predictions automatically!"""
    
    send_telegram_message(startup_msg)

def start_bot_thread():
    """Start the bot worker in a separate thread"""
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 Bot worker thread started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot thread: {e}")
        return False

def bot_worker():
    """Main bot worker with API protection"""
    global bot_started
    logger.info("🔄 Starting API-Safe Bot Worker...")
    
    bot_started = True
    
    # Initial data loading
    logger.info("📥 Loading initial historical data...")
    if load_historical_data():
        logger.info("✅ Historical data loaded successfully")
        
        # Train ML model
        logger.info("🤖 Training ML model...")
        if train_ml_model():
            logger.info("✅ ML model trained successfully")
        else:
            logger.warning("⚠️ ML model training failed, using fallback methods")
    else:
        logger.error("❌ Initial historical data loading failed")
    
    time.sleep(5)
    
    # Send startup message
    logger.info("📤 Sending startup message...")
    send_startup_message()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            logger.info(f"🔄 API-Safe Cycle #{cycle} at {format_pakistan_time()}")
            
            # Reload historical data periodically
            if cycle % Config.HISTORICAL_DATA_RELOAD == 0:
                logger.info("🔄 Reloading historical data...")
                load_historical_data()
                train_ml_model()  # Retrain model with new data
            
            # Clean up old data
            if cycle % Config.DATA_CLEANUP_INTERVAL == 0:
                logger.info("🧹 Cleaning up old data...")
                cleanup_old_data()
            
            # Analyze matches
            predictions_sent = analyze_with_multiple_sources()
            logger.info(f"📈 Cycle #{cycle}: {predictions_sent} analyses sent")
            
            # Send API status periodically
            if cycle % 12 == 0:  # Every 2 hours
                api_status_msg = get_api_status_message()
                send_telegram_message(api_status_msg)
            
            # Wait for next cycle
            logger.info(f"⏰ Waiting {Config.BOT_CYCLE_INTERVAL} seconds for next cycle...")
            time.sleep(Config.BOT_CYCLE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Bot worker error in cycle #{cycle}: {e}")
            time.sleep(Config.BOT_CYCLE_INTERVAL)  # Wait before retry

# Auto-start bot when module loads
logger.info("🎯 Auto-starting API-Safe Multi-Source Bot...")
if start_bot_thread():
    logger.info("✅ Bot auto-started successfully")
else:
    logger.error("❌ Bot auto-start failed")

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
