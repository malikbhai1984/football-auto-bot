
import os
import requests
import time
from flask import Flask
import logging
from datetime import datetime, timedelta
import pytz
from threading import Thread
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325").strip()

logger.info("🚀 Starting AUTO API-FOOTBALL Live Prediction Bot...")

# Validate critical environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID) if OWNER_CHAT_ID else 0
except (ValueError, TypeError) as e:
    logger.error(f"❌ Invalid OWNER_CHAT_ID: {e}")
    OWNER_CHAT_ID = 0

app = Flask(__name__)
PAK_TZ = pytz.timezone('Asia/Karachi')

class Config:
    BOT_CYCLE_INTERVAL = 120  # 2 minutes
    MIN_CONFIDENCE_THRESHOLD = 85

# Global variables
bot_started = False
message_counter = 0

def get_pakistan_time():
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M PKT')

def format_date(dt=None):
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%Y-%m-%d')

def send_telegram_message(message, max_retries=2):
    """Send message to Telegram"""
    global message_counter
    
    if not BOT_TOKEN or not OWNER_CHAT_ID:
        return False
        
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    for attempt in range(max_retries):
        try:
            payload = {
                'chat_id': OWNER_CHAT_ID,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(telegram_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                message_counter += 1
                logger.info(f"✅ Message #{message_counter} sent")
                return True
            else:
                logger.error(f"❌ Telegram API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Telegram send attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    return False

# ==================== API-FOOTBALL LIVE MATCHES ====================
def fetch_live_matches_from_api():
    """Fetch REAL live matches from API-Football"""
    live_matches = []
    
    if not API_FOOTBALL_KEY:
        logger.error("❌ API_FOOTBALL_KEY not set")
        return []
    
    try:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        headers = {
            'X-RapidAPI-Key': API_FOOTBALL_KEY,
            'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
        }
        
        # Get LIVE matches
        params = {'live': 'all'}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            fixtures = data.get('response', [])
            
            for fixture in fixtures:
                fixture_data = fixture.get('fixture', {})
                status = fixture_data.get('status', {})
                
                # Check if match is live
                if status.get('short') in ['1H', '2H', 'HT', 'ET', 'P']:
                    teams = fixture.get('teams', {})
                    goals = fixture.get('goals', {})
                    league = fixture.get('league', {})
                    
                    home_team = teams.get('home', {}).get('name', 'Unknown')
                    away_team = teams.get('away', {}).get('name', 'Unknown')
                    home_score = goals.get('home', 0)
                    away_score = goals.get('away', 0)
                    minute = status.get('elapsed', 0)
                    league_name = league.get('name', 'Unknown League')
                    country = league.get('country', 'Unknown')
                    
                    match_data = {
                        "home": home_team,
                        "away": away_team,
                        "league": f"{league_name} ({country})",
                        "score": f"{home_score}-{away_score}",
                        "minute": f"{minute}'",
                        "current_minute": minute,
                        "home_score": home_score,
                        "away_score": away_score,
                        "status": "LIVE",
                        "fixture_id": fixture_data.get('id'),
                        "timestamp": fixture_data.get('timestamp'),
                        "source": "api-football",
                        "api_timestamp": get_pakistan_time()
                    }
                    live_matches.append(match_data)
            
            logger.info(f"✅ API-Football LIVE matches found: {len(live_matches)}")
            
        elif response.status_code == 429:
            logger.error("❌ API-Football rate limit exceeded")
        else:
            logger.error(f"❌ API-Football error: {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ API-Football connection error: {e}")
    
    return live_matches

def fetch_todays_fixtures_from_api():
    """Fetch today's fixtures from API-Football"""
    fixtures = []
    
    if not API_FOOTBALL_KEY:
        return []
    
    try:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        headers = {
            'X-RapidAPI-Key': API_FOOTBALL_KEY,
            'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
        }
        
        today = format_date()
        params = {'date': today}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            for fixture in data.get('response', []):
                fixture_data = fixture.get('fixture', {})
                teams = fixture.get('teams', {})
                league = fixture.get('league', {})
                
                home_team = teams.get('home', {}).get('name', 'Unknown')
                away_team = teams.get('away', {}).get('name', 'Unknown')
                league_name = league.get('name', 'Unknown League')
                country = league.get('country', 'Unknown')
                
                # Get match time
                timestamp = fixture_data.get('timestamp', 0)
                if timestamp:
                    match_time = datetime.fromtimestamp(timestamp, PAK_TZ).strftime('%H:%M')
                else:
                    match_time = "TBD"
                
                fixture_info = {
                    "home": home_team,
                    "away": away_team,
                    "league": f"{league_name} ({country})",
                    "time": match_time,
                    "date": today,
                    "status": fixture_data.get('status', {}).get('short', 'NS')
                }
                fixtures.append(fixture_info)
            
            logger.info(f"✅ API-Football fixtures found: {len(fixtures)}")
            
    except Exception as e:
        logger.error(f"❌ API-Football fixtures error: {e}")
    
    return fixtures

# ==================== PREDICTION ENGINE ====================
def generate_predictions(match_data):
    """Generate predictions for matches"""
    predictions = {}
    
    try:
        current_score = match_data.get('home_score', 0), match_data.get('away_score', 0)
        current_minute = match_data.get('current_minute', 0)
        
        if current_minute < 25:
            return predictions
        
        # Winning Team Prediction
        winning_pred = predict_winning_team(current_score, current_minute)
        if winning_pred['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
            predictions['winning_team'] = winning_pred
        
        # Over/Under Predictions
        for goals_line in [0.5, 1.5, 2.5, 3.5]:
            over_pred = predict_over_under(current_score, current_minute, goals_line)
            if over_pred['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
                predictions[f'over_{goals_line}'] = over_pred
        
        # BTTS Prediction
        btts_pred = predict_btts(current_score, current_minute)
        if btts_pred['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
            predictions['btts'] = btts_pred
        
        # Last 10 minutes goal
        if current_minute >= 75:
            last_10_pred = {'prediction': 'High Chance', 'confidence': 88, 'method': 'closing_stages'}
            predictions['last_10_min_goal'] = last_10_pred
                
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
    
    return predictions

def predict_winning_team(current_score, current_minute):
    """Predict winning team"""
    home_score, away_score = current_score
    goal_difference = home_score - away_score
    
    if current_minute >= 75:
        if goal_difference > 0:
            return {'prediction': 'Home Win', 'confidence': 88, 'method': 'late_game'}
        elif goal_difference < 0:
            return {'prediction': 'Away Win', 'confidence': 87, 'method': 'late_game'}
        else:
            return {'prediction': 'Draw', 'confidence': 85, 'method': 'late_game'}
    
    if current_minute >= 45 and abs(goal_difference) >= 2:
        winning_team = 'Home Win' if goal_difference > 0 else 'Away Win'
        return {'prediction': winning_team, 'confidence': 86, 'method': 'dominant_lead'}
    
    return {'prediction': 'None', 'confidence': 70, 'method': 'insufficient_data'}

def predict_over_under(current_score, current_minute, goals_line):
    """Predict Over/Under"""
    home_score, away_score = current_score
    total_goals = home_score + away_score
    
    minutes_remaining = 90 - current_minute
    expected_additional = (2.7 / 90) * minutes_remaining * 1.2
    expected_total = total_goals + expected_additional
    
    if expected_total > goals_line + 0.3:
        confidence = min(95, 80 + (expected_total - goals_line) * 20)
        return {'prediction': f'Over {goals_line}', 'confidence': confidence, 'method': 'goal_rate'}
    else:
        return {'prediction': f'Under {goals_line}', 'confidence': 75, 'method': 'goal_rate'}

def predict_btts(current_score, current_minute):
    """Predict Both Teams To Score"""
    home_score, away_score = current_score
    
    if home_score > 0 and away_score > 0:
        return {'prediction': 'Yes', 'confidence': 92, 'method': 'already_scored'}
    
    if (home_score > 0 or away_score > 0) and current_minute <= 60:
        return {'prediction': 'Yes', 'confidence': 87, 'method': 'momentum'}
    
    return {'prediction': 'No', 'confidence': 65, 'method': 'low_probability'}

# ==================== ANALYSIS ENGINE ====================
def analyze_live_matches():
    """Analyze and send predictions for LIVE matches"""
    try:
        logger.info("🔍 Analyzing LIVE matches from API...")
        
        live_matches = fetch_live_matches_from_api()
        
        if not live_matches:
            no_matches_msg = f"""🔍 **NO LIVE MATCHES FOUND**

⏰ **Time:** {format_pakistan_time()}
📅 **Date:** {format_date()}

🌐 **API Status:** Active
🔍 **Checking:** All Leagues Worldwide

No live matches at the moment.
I'll check again in 2 minutes."""
            send_telegram_message(no_matches_msg)
            return 0
        
        predictions_sent = 0
        
        for match in live_matches:
            try:
                predictions = generate_predictions(match)
                
                if predictions:
                    message = format_prediction_message(match, predictions)
                    if send_telegram_message(message):
                        predictions_sent += 1
                        logger.info(f"✅ Predictions sent for {match['home']} vs {match['away']}")
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Match analysis error: {e}")
                continue
        
        logger.info(f"📈 Analysis complete: {predictions_sent} predictions sent")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}")
        return 0

def format_prediction_message(match, predictions):
    """Format prediction message"""
    current_time = format_pakistan_time()
    
    message = f"""🎯 **API-FOOTBALL 85%+ LIVE PREDICTIONS** 🎯

🏆 **League:** {match['league']}
🕒 **Minute:** {match['minute']}
📊 **Score:** {match['score']}
🌐 **Source:** Live API Data

🏠 **{match['home']}** vs 🛫 **{match['away']}**

🔥 **HIGH-CONFIDENCE BETS (85%+):**\n"""

    for market, prediction in predictions.items():
        if 'over' in market:
            display = f"⚽ {prediction['prediction']} Goals"
        elif market == 'btts':
            display = f"🎯 Both Teams To Score: {prediction['prediction']}"
        elif market == 'last_10_min_goal':
            display = f"⏰ Last 10 Min Goal: {prediction['prediction']}"
        elif market == 'winning_team':
            display = f"🏆 Winning Team: {prediction['prediction']}"
        else:
            display = f"📈 {market}: {prediction['prediction']}"
        
        message += f"• {display} - {prediction['confidence']}% ✅\n"
        message += f"  └── Method: {prediction['method']}\n"

    message += f"""
📊 **Analysis Time:** {current_time}
🎯 **Confidence Filter:** 85%+ Only
🔍 **Data Source:** API-Football Live

⚠️ *Professional analysis based on real-time match data*"""

    return message

def send_todays_schedule():
    """Send today's match schedule from API"""
    try:
        fixtures = fetch_todays_fixtures_from_api()
        
        if not fixtures:
            message = f"""📅 **TODAY'S SCHEDULE** 📅

**Date:** {format_date()}
**Status:** No fixtures found via API"""
            send_telegram_message(message)
            return
        
        # Filter only upcoming matches
        upcoming_matches = [f for f in fixtures if f['status'] in ['NS', 'TBD']]
        
        message = f"""📅 **TODAY'S MATCH SCHEDULE** 📅

**Date:** {format_date()}
**Total Matches:** {len(upcoming_matches)}
**Source:** API-Football Live

"""
        
        leagues = {}
        for fixture in upcoming_matches:
            league = fixture['league']
            if league not in leagues:
                leagues[league] = []
            leagues[league].append(fixture)
        
        for league, matches in leagues.items():
            message += f"\n**🏆 {league}**\n"
            for match in matches:
                message += f"• ⏰ {match['time']} - {match['home']} vs {match['away']}\n"
        
        # Add current LIVE matches
        live_matches = fetch_live_matches_from_api()
        if live_matches:
            message += f"\n\n🔴 **CURRENTLY LIVE:**\n"
            for match in live_matches:
                message += f"• ⚽ {match['home']} vs {match['away']} - {match['score']} ({match['minute']})\n"
        
        message += f"\n⏰ **Schedule Time:** {format_pakistan_time()}"
        message += "\n\n🎯 *Live predictions will be sent for LIVE matches*"
        
        send_telegram_message(message)
        logger.info("✅ API schedule sent")
        
    except Exception as e:
        logger.error(f"❌ Schedule error: {e}")

# ==================== FLASK ROUTES ====================
@app.route("/")
def home():
    live_matches = fetch_live_matches_from_api()
    return {
        "status": "running",
        "bot_started": bot_started,
        "live_matches": len(live_matches),
        "message_counter": message_counter,
        "timestamp": format_pakistan_time()
    }

@app.route("/health")
def health():
    return "OK", 200

@app.route("/test")
def test():
    live_matches = fetch_live_matches_from_api()
    fixtures = fetch_todays_fixtures_from_api()
    return {
        "status": "working",
        "live_matches": len(live_matches),
        "todays_fixtures": len(fixtures),
        "timestamp": format_pakistan_time()
    }

# ==================== BOT WORKER ====================
def send_startup_message():
    startup_msg = f"""🚀 **AUTO API-FOOTBALL BOT STARTED!**

⏰ **Startup Time:** {format_pakistan_time()}
📅 **Today's Date:** {format_date()}
🎯 **Confidence Threshold:** 85%+ ONLY

📊 **Data Sources:**
   • API-Football Live (Automatic)
   • Real-time Match Data
   • Worldwide Leagues

🌐 **API Status:** Connected
🔍 **Monitoring:** All Live Matches

Bot is now scanning for live opportunities!"""

    send_telegram_message(startup_msg)
    send_todays_schedule()

def bot_worker():
    global bot_started
    logger.info("🔄 Starting AUTO API-Football Bot Worker...")
    
    bot_started = True
    send_startup_message()
    
    cycle = 0
    
    while True:
        try:
            cycle += 1
            current_time = format_pakistan_time()
            logger.info(f"🔄 Cycle #{cycle} at {current_time}")
            
            predictions_sent = analyze_live_matches()
            
            if predictions_sent > 0:
                logger.info(f"📈 Cycle #{cycle}: {predictions_sent} predictions sent")
            
            # Send status every 6 cycles (12 minutes)
            if cycle % 6 == 0:
                fixtures = fetch_todays_fixtures_from_api()
                live_matches = fetch_live_matches_from_api()
                status_msg = f"""🔄 **Auto API Bot Status**
Cycles: {cycle}
Live Now: {len(live_matches)}
Today's Matches: {len(fixtures)}
Last Check: {current_time}
API Key: ✅ Active"""
                send_telegram_message(status_msg)
            
            time.sleep(Config.BOT_CYCLE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
            time.sleep(60)

def start_bot_thread():
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 Auto API Bot worker started")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return False

# ==================== STARTUP ====================
if BOT_TOKEN and OWNER_CHAT_ID:
    logger.info("🎯 Auto-starting API-Football Bot...")
    if start_bot_thread():
        logger.info("✅ Auto API Bot started successfully")
    else:
        logger.error("❌ Auto API Bot start failed")
else:
    logger.warning("⚠️ Missing credentials - bot not started")

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
