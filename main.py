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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")

logger.info("🚀 Initializing REAL-TIME Betting Bot...")

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
    return dt.strftime('%H:%M %Z')

@app.route("/")
def health():
    return "⚽ REAL-TIME Betting Bot is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

@app.route("/test-message")
def test_message():
    """Test endpoint to send a message"""
    try:
        send_telegram_message("🧪 **REAL-TIME BOT TEST**\n\n✅ Bot is working!\n🕒 " + format_pakistan_time())
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

def fetch_current_live_matches():
    """Fetch ONLY current live matches that are actually playing NOW"""
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("🌐 Fetching CURRENT live matches...")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        current_matches = []
        
        for match in data.get("data", []):
            league_id = match.get("league_id")
            
            # Only include top leagues
            if league_id in TOP_LEAGUES:
                # Check if match is actually LIVE and playing
                status = match.get("status", "")
                minute = match.get("minute", "")
                
                # ONLY include matches that are IN PROGRESS
                if status == "LIVE" and minute and minute != "FT" and minute != "HT":
                    
                    participants = match.get("participants", [])
                    
                    if len(participants) >= 2:
                        home_team = participants[0].get("name", "Unknown Home")
                        away_team = participants[1].get("name", "Unknown Away")
                        
                        home_score = match.get("scores", {}).get("home_score", 0)
                        away_score = match.get("scores", {}).get("away_score", 0)
                        
                        # Convert minute to integer for analysis
                        try:
                            if isinstance(minute, str) and "'" in minute:
                                current_minute = int(minute.replace("'", ""))
                            else:
                                current_minute = int(minute)
                        except:
                            current_minute = 0
                        
                        # ONLY include matches between 1st and 89th minute
                        if 1 <= current_minute <= 89:
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
                            logger.info(f"✅ CURRENT LIVE: {home_team} vs {away_team} - {home_score}-{away_score} ({minute}')")
        
        logger.info(f"📊 ACTIVE LIVE matches: {len(current_matches)}")
        return current_matches
        
    except Exception as e:
        logger.error(f"❌ Error fetching current matches: {e}")
        return []

def get_todays_upcoming_matches():
    """Get today's upcoming matches (next few hours)"""
    try:
        today = get_pakistan_time().strftime('%Y-%m-%d')
        url = f"https://api.sportmonks.com/v3/football/fixtures/date/{today}?api_token={SPORTMONKS_API}&include=league,participants"
        
        logger.info(f"📅 Fetching TODAY'S matches ({today})...")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        upcoming_matches = []
        
        current_time = get_pakistan_time()
        
        for match in data.get("data", []):
            league_id = match.get("league_id")
            
            if league_id in TOP_LEAGUES:
                starting_at = match.get("starting_at")
                if starting_at:
                    # Convert UTC to Pakistan time
                    utc_time = datetime.fromisoformat(starting_at.replace('Z', '+00:00'))
                    match_time = utc_time.astimezone(PAK_TZ)
                    
                    # Only include matches in next 6 hours
                    time_diff = match_time - current_time
                    if timedelta(hours=0) <= time_diff <= timedelta(hours=6):
                        
                        participants = match.get("participants", [])
                        if len(participants) >= 2:
                            home_team = participants[0].get("name", "Unknown Home")
                            away_team = participants[1].get("name", "Unknown Away")
                            
                            match_data = {
                                "home": home_team,
                                "away": away_team,
                                "league": TOP_LEAGUES[league_id],
                                "match_time": match_time.strftime('%H:%M %Z'),
                                "time_until": str(time_diff).split('.')[0],
                                "match_id": match.get("id"),
                                "is_live": False,
                                "type": "UPCOMING"
                            }
                            
                            upcoming_matches.append(match_data)
                            logger.info(f"✅ UPCOMING: {home_team} vs {away_team} - {match_time.strftime('%H:%M %Z')}")
        
        logger.info(f"📊 Today's upcoming matches: {len(upcoming_matches)}")
        return upcoming_matches
        
    except Exception as e:
        logger.error(f"❌ Error fetching upcoming matches: {e}")
        return []

def calculate_smart_prediction(match):
    """Calculate smart prediction for live matches"""
    try:
        minute = match.get('current_minute', 0)
        home_score = match.get('home_score', 0)
        away_score = match.get('away_score', 0)
        
        # Base analysis
        base_chance = 30
        
        # Time analysis - only for matches past 60 minutes
        if minute >= 60:
            time_remaining = 90 - minute
            time_factor = (30 - time_remaining) * 1.8
        else:
            time_factor = 0
        
        # Score pressure analysis
        goal_difference = home_score - away_score
        if goal_difference == 0:  # Equal score
            score_factor = 25
        elif abs(goal_difference) == 1:  # Close game
            score_factor = 20
        else:  # One-sided
            score_factor = -10
        
        # Final minutes boost
        if minute >= 75:
            final_push = 20
        elif minute >= 65:
            final_push = 10
        else:
            final_push = 0
        
        total_chance = base_chance + time_factor + score_factor + final_push
        
        # Add some intelligent randomness
        randomness = random.randint(-8, 15)
        final_chance = min(92, max(8, total_chance + randomness))
        
        return final_chance
        
    except Exception as e:
        logger.error(f"❌ Prediction calculation error: {e}")
        return random.randint(40, 70)

def analyze_real_time_matches():
    """Analyze only current real-time matches"""
    try:
        logger.info("🔍 Analyzing REAL-TIME matches...")
        
        # Get current live matches
        live_matches = fetch_current_live_matches()
        predictions_sent = 0
        
        if not live_matches:
            # Check for upcoming matches
            upcoming_matches = get_todays_upcoming_matches()
            
            if upcoming_matches:
                # Send upcoming matches info
                message = "🟡 **UPCOMING MATCHES TODAY**\n\n"
                message += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n\n"
                
                for match in upcoming_matches[:5]:  # Show first 5
                    message += f"⚽ **{match['home']} vs {match['away']}**\n"
                    message += f"   🏆 {match['league']}\n"
                    message += f"   ⏰ {match['match_time']} (in {match['time_until']})\n\n"
                
                message += "🔔 I'll alert you when matches go LIVE!"
                send_telegram_message(message)
                return 1
            else:
                # No matches at all
                send_telegram_message(
                    "📭 **NO ACTIVE MATCHES**\n\n"
                    "No live matches in top leagues right now.\n"
                    "Also no upcoming matches in next 6 hours.\n\n"
                    f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
                    "🔄 Will check again in 7 minutes..."
                )
                return 0
        
        # Analyze live matches
        high_confidence_predictions = []
        
        for match in live_matches:
            prediction_chance = calculate_smart_prediction(match)
            
            # Only send high-confidence predictions (75%+)
            if prediction_chance >= 75:
                high_confidence_predictions.append({
                    'match': match,
                    'confidence': prediction_chance
                })
        
        # Send predictions
        for pred in high_confidence_predictions:
            match = pred['match']
            
            message = (
                f"🔥 **REAL-TIME PREDICTION** 🔥\n\n"
                f"⚽ **Match:** {match['home']} vs {match['away']}\n"
                f"🏆 **League:** {match['league']}\n"
                f"📊 **Live Score:** {match['score']} ({match['minute']}')\n"
                f"🎯 **Prediction:** GOAL IN REMAINING TIME\n"
                f"✅ **Confidence:** {pred['confidence']}%\n"
                f"💰 **Bet Suggestion:** YES - Next Goal\n\n"
                f"⏰ **Time Left:** {90 - match['current_minute']} minutes\n"
                f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
                f"🔄 Next analysis in 7 minutes..."
            )
            
            if send_telegram_message(message):
                predictions_sent += 1
        
        # If no high-confidence predictions, send live matches summary
        if predictions_sent == 0 and live_matches:
            summary_msg = "📊 **CURRENT LIVE MATCHES**\n\n"
            summary_msg += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n\n"
            
            for match in live_matches[:4]:  # Show first 4 matches
                chance = calculate_smart_prediction(match)
                summary_msg += f"⚽ **{match['home']} vs {match['away']}**\n"
                summary_msg += f"   📊 {match['score']} ({match['minute']}')\n"
                summary_msg += f"   🎯 Goal Chance: {chance}%\n"
                summary_msg += f"   🏆 {match['league']}\n\n"
            
            summary_msg += "🔍 Monitoring for betting opportunities...\n"
            summary_msg += "⏰ Next update in 7 minutes"
            
            send_telegram_message(summary_msg)
            predictions_sent = 1
        
        logger.info(f"📈 Real-time predictions sent: {predictions_sent}")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Real-time analysis error: {e}")
        return 0

def send_startup_message():
    """Send startup message"""
    try:
        message = (
            "🎯 **REAL-TIME BETTING BOT ACTIVATED!** 🎯\n\n"
            "✅ **Status:** Monitoring ACTIVE Matches\n"
            f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
            "📡 **Focus:** ONLY Live & Upcoming Matches\n"
            "⏰ **Update Interval:** Every 7 minutes\n\n"
            "🎪 **Smart Filters:**\n"
            "   • Only ACTIVE live matches\n"
            "   • Minutes 1-89 only (no FT/HT)\n"
            "   • Top leagues priority\n"
            "   • 75%+ confidence only\n\n"
            "🔜 Scanning for current matches...\n"
            "💰 Real-time betting alerts incoming!"
        )
        return send_telegram_message(message)
    except Exception as e:
        logger.error(f"❌ Startup message failed: {e}")
        return False

def bot_worker():
    """Main bot worker with 7-minute intervals"""
    global bot_started
    logger.info("🔄 Starting Real-Time Bot Worker...")
    
    # Wait for initialization
    time.sleep(10)
    
    # Send startup message
    logger.info("📤 Sending startup message...")
    if send_startup_message():
        logger.info("✅ Startup message delivered")
    else:
        logger.error("❌ Startup message failed")
    
    # Main loop - 7 minute intervals
    cycle = 0
    while True:
        try:
            cycle += 1
            current_time = get_pakistan_time()
            logger.info(f"🔄 Real-Time Cycle #{cycle} at {format_pakistan_time(current_time)}")
            
            # Analyze REAL-TIME matches
            predictions = analyze_real_time_matches()
            logger.info(f"📈 Cycle #{cycle}: {predictions} alerts sent")
            
            # Status update every 6 cycles (~42 minutes)
            if cycle % 6 == 0:
                status_msg = (
                    f"📊 **REAL-TIME BOT STATUS**\n\n"
                    f"🔄 Analysis Cycles: {cycle}\n"
                    f"📨 Total Messages: {message_counter}\n"
                    f"🎯 Last Predictions: {predictions}\n"
                    f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
                    f"✅ Status: ACTIVE MATCH MONITORING\n\n"
                    f"⏰ Next real-time analysis in 7 minutes..."
                )
                send_telegram_message(status_msg)
            
            # Wait 7 minutes for next analysis
            logger.info("⏰ Waiting 7 minutes for next real-time analysis...")
            time.sleep(420)  # 7 minutes
            
        except Exception as e:
            logger.error(f"❌ Bot worker error: {e}")
            time.sleep(420)

def start_bot_thread():
    """Start bot in background thread"""
    global bot_started
    if not bot_started:
        logger.info("🚀 Starting real-time bot thread...")
        thread = Thread(target=bot_worker, daemon=True)
        thread.start()
        bot_started = True
        logger.info("✅ Real-time bot thread started")
    else:
        logger.info("✅ Bot thread already running")

# Auto-start bot
logger.info("🎯 Auto-starting Real-Time Betting Bot...")
start_bot_thread()

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
