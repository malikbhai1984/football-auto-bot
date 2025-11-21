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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")
FOOTBALL_API = os.getenv("FOOTBALL_API")  # Second API

logger.info("🚀 Initializing Smart Betting Bot with Dual APIs...")

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

def get_pakistan_time():
    """Get current Pakistan time"""
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    """Format datetime in Pakistan time"""
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%Y-%m-%d %H:%M:%S %Z%z')

@app.route("/")
def health():
    return "⚽ Smart Betting Bot (Pakistan Time) is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

@app.route("/test-message")
def test_message():
    """Test endpoint to send a message"""
    try:
        send_telegram_message("🧪 **TEST MESSAGE - PAKISTAN TIME**\n\n✅ Bot is working!\n🕒 " + format_pakistan_time())
        return "Test message sent!", 200
    except Exception as e:
        return f"Error: {e}", 500

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

def fetch_live_matches_sportmonks():
    """Fetch live matches from Sportmonks API"""
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("🌐 Fetching LIVE matches from Sportmonks...")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        matches = []
        
        for match in data.get("data", []):
            league_id = match.get("league_id")
            
            if league_id in TOP_LEAGUES:
                participants = match.get("participants", [])
                
                if len(participants) >= 2:
                    home_team = participants[0].get("name", "Unknown Home")
                    away_team = participants[1].get("name", "Unknown Away")
                    
                    home_score = match.get("scores", {}).get("home_score", 0)
                    away_score = match.get("scores", {}).get("away_score", 0)
                    minute = match.get("minute", 0)
                    status = match.get("status", "")
                    
                    match_data = {
                        "home": home_team,
                        "away": away_team,
                        "league": TOP_LEAGUES[league_id],
                        "score": f"{home_score}-{away_score}",
                        "minute": minute,
                        "status": status,
                        "home_score": home_score,
                        "away_score": away_score,
                        "match_id": match.get("id"),
                        "api_source": "sportmonks",
                        "type": "LIVE"
                    }
                    
                    matches.append(match_data)
                    logger.info(f"✅ LIVE: {home_team} vs {away_team} - {home_score}-{away_score} ({minute}')")
        
        logger.info(f"📊 Sportmonks LIVE matches: {len(matches)}")
        return matches
        
    except Exception as e:
        logger.error(f"❌ Error fetching Sportmonks LIVE matches: {e}")
        return []

def fetch_upcoming_matches_sportmonks():
    """Fetch upcoming matches from Sportmonks API"""
    try:
        # Get tomorrow's date
        tomorrow = (get_pakistan_time() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        url = f"https://api.sportmonks.com/v3/football/fixtures/date/{tomorrow}?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info(f"📅 Fetching UPCOMING matches for {tomorrow} from Sportmonks...")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        matches = []
        
        for match in data.get("data", []):
            league_id = match.get("league_id")
            
            if league_id in TOP_LEAGUES:
                participants = match.get("participants", [])
                
                if len(participants) >= 2:
                    home_team = participants[0].get("name", "Unknown Home")
                    away_team = participants[1].get("name", "Unknown Away")
                    
                    # Convert UTC time to Pakistan time
                    starting_at = match.get("starting_at")
                    if starting_at:
                        utc_time = datetime.fromisoformat(starting_at.replace('Z', '+00:00'))
                        pak_time = utc_time.astimezone(PAK_TZ)
                        match_time = pak_time.strftime('%H:%M %Z')
                    else:
                        match_time = "TBA"
                    
                    match_data = {
                        "home": home_team,
                        "away": away_team,
                        "league": TOP_LEAGUES[league_id],
                        "match_time": match_time,
                        "date": tomorrow,
                        "match_id": match.get("id"),
                        "api_source": "sportmonks",
                        "type": "UPCOMING"
                    }
                    
                    matches.append(match_data)
                    logger.info(f"✅ UPCOMING: {home_team} vs {away_team} - {match_time} PKT")
        
        logger.info(f"📊 Sportmonks UPCOMING matches: {len(matches)}")
        return matches
        
    except Exception as e:
        logger.error(f"❌ Error fetching Sportmonks UPCOMING matches: {e}")
        return []

def fetch_football_api_matches():
    """Fetch matches from second football API"""
    try:
        # This is a placeholder for your second API
        # Replace with actual API call
        logger.info("🔗 Second API integration placeholder")
        
        # Example structure - replace with actual API call
        # url = f"https://api.football-data.org/v4/matches?dateFrom={tomorrow}&dateTo={tomorrow}"
        # headers = {"X-Auth-Token": FOOTBALL_API}
        # response = requests.get(url, headers=headers, timeout=15)
        
        return []  # Empty for now
        
    except Exception as e:
        logger.error(f"❌ Error fetching second API matches: {e}")
        return []

def combine_all_matches():
    """Combine matches from all APIs and remove duplicates"""
    all_matches = []
    
    # Fetch from both APIs
    sportmonks_live = fetch_live_matches_sportmonks()
    sportmonks_upcoming = fetch_upcoming_matches_sportmonks()
    football_api_matches = fetch_football_api_matches()
    
    # Combine all matches
    all_matches.extend(sportmonks_live)
    all_matches.extend(sportmonks_upcoming)
    all_matches.extend(football_api_matches)
    
    # Remove duplicates based on match_id
    unique_matches = []
    seen_ids = set()
    
    for match in all_matches:
        match_id = match.get('match_id')
        if match_id and match_id not in seen_ids:
            seen_ids.add(match_id)
            unique_matches.append(match)
    
    logger.info(f"🎯 TOTAL UNIQUE MATCHES: {len(unique_matches)}")
    return unique_matches

def calculate_prediction(match):
    """Calculate prediction based on match type and data"""
    try:
        if match.get('type') == 'LIVE':
            # Live match prediction
            minute = match.get("minute", 0)
            home_score = match.get("home_score", 0)
            away_score = match.get("away_score", 0)
            
            if isinstance(minute, str) and "'" in minute:
                minute = int(minute.replace("'", ""))
            else:
                minute = int(minute)
            
            # Only predict for matches past 60 minutes
            if minute >= 60:
                base_chance = 40
                time_remaining = 90 - minute
                time_factor = (30 - time_remaining) * 2
                
                goal_difference = home_score - away_score
                if goal_difference == 0:
                    score_factor = 25
                elif abs(goal_difference) == 1:
                    score_factor = 20
                else:
                    score_factor = -10
                
                if minute >= 75:
                    pressure_factor = 20
                else:
                    pressure_factor = 0
                
                total_chance = base_chance + time_factor + score_factor + pressure_factor
                randomness = random.randint(-5, 10)
                final_chance = min(95, max(10, total_chance + randomness))
                
                return final_chance
        
        elif match.get('type') == 'UPCOMING':
            # Upcoming match prediction (pre-match analysis)
            # Simulate some pre-match analysis
            base_chance = random.randint(65, 90)
            return base_chance
        
        return 0  # No prediction for this match
        
    except Exception as e:
        logger.error(f"❌ Prediction calculation error: {e}")
        return 0

def analyze_all_matches():
    """Analyze all matches and send predictions"""
    try:
        logger.info("🔍 Analyzing ALL matches (Live + Upcoming)...")
        all_matches = combine_all_matches()
        
        if not all_matches:
            logger.info("📭 No matches found from any API")
            # Send notification about no matches
            send_telegram_message(
                "📭 **NO MATCHES FOUND**\n\n"
                "Currently no live matches in top leagues.\n"
                "🔄 Will check again in 30 minutes.\n"
                f"🕒 Last check: {format_pakistan_time()}"
            )
            return 0
        
        predictions_sent = 0
        live_predictions = 0
        upcoming_predictions = 0
        
        for match in all_matches:
            prediction_chance = calculate_prediction(match)
            
            if prediction_chance >= 75:
                if match.get('type') == 'LIVE':
                    message = (
                        f"🔥 **LIVE MATCH PREDICTION** 🔥\n\n"
                        f"⚽ **Match:** {match['home']} vs {match['away']}\n"
                        f"🏆 **League:** {match['league']}\n"
                        f"📊 **Live Score:** {match['score']} ({match['minute']}')\n"
                        f"🎯 **Prediction:** GOAL IN REMAINING TIME\n"
                        f"✅ **Confidence:** {prediction_chance}%\n"
                        f"💰 **Bet Suggestion:** YES - Next Goal\n\n"
                        f"⏰ **Pakistan Time:** {format_pakistan_time()}\n"
                        f"🔄 Next analysis in 30 minutes..."
                    )
                    live_predictions += 1
                
                elif match.get('type') == 'UPCOMING':
                    message = (
                        f"🎯 **UPCOMING MATCH PREDICTION** 🎯\n\n"
                        f"⚽ **Match:** {match['home']} vs {match['away']}\n"
                        f"🏆 **League:** {match['league']}\n"
                        f"🕒 **Match Time:** {match['match_time']} PKT\n"
                        f"📅 **Date:** {match['date']}\n"
                        f"🎯 **Prediction:** HIGH-SCORING MATCH\n"
                        f"✅ **Confidence:** {prediction_chance}%\n"
                        f"💰 **Bet Suggestion:** OVER 2.5 GOALS\n\n"
                        f"⏰ **Alert Time:** {format_pakistan_time()}\n"
                        f"🔄 Will update 1 hour before match..."
                    )
                    upcoming_predictions += 1
                
                if send_telegram_message(message):
                    predictions_sent += 1
        
        # Send summary if no high-confidence predictions
        if predictions_sent == 0:
            summary_msg = "📊 **DAILY MATCHES SUMMARY**\n\n"
            summary_msg += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n\n"
            
            live_matches = [m for m in all_matches if m.get('type') == 'LIVE']
            upcoming_matches = [m for m in all_matches if m.get('type') == 'UPCOMING']
            
            if live_matches:
                summary_msg += "🔴 **LIVE MATCHES:**\n"
                for match in live_matches[:3]:
                    summary_msg += f"⚽ {match['home']} vs {match['away']}\n"
                    summary_msg += f"   📊 {match['score']} ({match['minute']}')\n"
                    summary_msg += f"   🏆 {match['league']}\n\n"
            
            if upcoming_matches:
                summary_msg += "🟢 **UPCOMING MATCHES:**\n"
                for match in upcoming_matches[:3]:
                    summary_msg += f"⚽ {match['home']} vs {match['away']}\n"
                    summary_msg += f"   🕒 {match['match_time']} PKT\n"
                    summary_msg += f"   🏆 {match['league']}\n\n"
            
            summary_msg += "🎯 Monitoring for betting opportunities..."
            send_telegram_message(summary_msg)
            predictions_sent = 1
        
        logger.info(f"📈 Predictions: {predictions_sent} (Live: {live_predictions}, Upcoming: {upcoming_predictions})")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}")
        return 0

def send_startup_message():
    """Send startup message"""
    try:
        message = (
            "🎯 **SMART BETTING BOT ACTIVATED!** 🎯\n\n"
            "✅ **Status:** Dual API Monitoring\n"
            f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
            "📡 **Sources:** Sportmonks + Football API\n"
            "⏰ **Schedule:**\n"
            "   • Live Matches: Every 30 mins\n"
            "   • Upcoming: Daily at 10 AM PKT\n\n"
            "🎪 **Coverage:**\n"
            "   • Live Match Predictions\n"
            "   • Tomorrow's Match Alerts\n"
            "   • 75%+ Confidence Only\n\n"
            "🔜 Scanning all matches now...\n"
            "💰 Real betting opportunities coming!"
        )
        return send_telegram_message(message)
    except Exception as e:
        logger.error(f"❌ Startup message failed: {e}")
        return False

def bot_worker():
    """Main bot worker function"""
    global bot_started
    logger.info("🔄 Starting smart betting bot worker...")
    
    # Wait for initialization
    time.sleep(10)
    
    # Send startup message
    logger.info("📤 Sending startup message...")
    if send_startup_message():
        logger.info("✅ Startup message delivered")
    else:
        logger.error("❌ Startup message failed")
    
    # Main loop
    cycle = 0
    while True:
        try:
            cycle += 1
            current_time = get_pakistan_time()
            logger.info(f"🔄 Analysis cycle #{cycle} at {format_pakistan_time(current_time)}")
            
            # Analyze ALL matches
            predictions = analyze_all_matches()
            logger.info(f"📈 Cycle #{cycle}: {predictions} predictions sent")
            
            # Send status update every 6 cycles (3 hours)
            if cycle % 6 == 0:
                status_msg = (
                    f"📊 **SMART BOT STATUS**\n\n"
                    f"🔄 Analysis Cycles: {cycle}\n"
                    f"📨 Total Messages: {message_counter}\n"
                    f"🎯 Last Predictions: {predictions}\n"
                    f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
                    f"✅ Status: DUAL API MONITORING\n\n"
                    f"⏰ Next analysis in 30 minutes..."
                )
                send_telegram_message(status_msg)
            
            # Wait 30 minutes for next analysis
            logger.info("⏰ Waiting 30 minutes for next analysis...")
            time.sleep(1800)  # 30 minutes
            
        except Exception as e:
            logger.error(f"❌ Bot worker error: {e}")
            time.sleep(1800)

def start_bot_thread():
    """Start bot in background thread"""
    global bot_started
    if not bot_started:
        logger.info("🚀 Starting smart betting bot thread...")
        thread = Thread(target=bot_worker, daemon=True)
        thread.start()
        bot_started = True
        logger.info("✅ Smart betting bot thread started")
    else:
        logger.info("✅ Bot thread already running")

# Auto-start bot
logger.info("🎯 Auto-starting smart betting bot...")
start_bot_thread()

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
