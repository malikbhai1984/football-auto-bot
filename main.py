import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask, request
import logging
import random
from datetime import datetime
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")
RAILWAY_PUBLIC_URL = os.getenv("RAILWAY_STATIC_URL", "https://your-app.railway.app")

logger.info("🚀 Initializing Real Match Betting Bot...")

# Validate environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found") 
if not SPORTMONKS_API:
    logger.error("❌ API_KEY not found")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
    logger.info(f"✅ OWNER_CHAT_ID: {OWNER_CHAT_ID}")
except (ValueError, TypeError) as e:
    logger.error(f"❌ Invalid OWNER_CHAT_ID: {e}")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

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

@app.route("/")
def health():
    return "⚽ Real Match Betting Bot is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

@app.route("/test-message")
def test_message():
    """Test endpoint to send a message"""
    try:
        send_telegram_message("🧪 **TEST MESSAGE**\n\n✅ Bot is working!\n🕒 " + datetime.now().strftime('%H:%M:%S'))
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

def fetch_real_live_matches():
    """Fetch real live matches from Sportmonks API"""
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("🌐 Fetching real live matches from Sportmonks...")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        live_matches = []
        
        for match in data.get("data", []):
            league_id = match.get("league_id")
            
            # Only include top leagues
            if league_id in TOP_LEAGUES:
                participants = match.get("participants", [])
                
                if len(participants) >= 2:
                    home_team = participants[0].get("name", "Unknown Home")
                    away_team = participants[1].get("name", "Unknown Away")
                    
                    # Get current match details
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
                        "match_id": match.get("id")
                    }
                    
                    live_matches.append(match_data)
                    logger.info(f"✅ Found match: {home_team} vs {away_team} - {home_score}-{away_score} ({minute}')")
        
        logger.info(f"📊 Total real matches found: {len(live_matches)}")
        return live_matches
        
    except Exception as e:
        logger.error(f"❌ Error fetching real matches: {e}")
        return []

def calculate_goal_prediction(match):
    """Calculate goal prediction based on match situation"""
    try:
        minute = match.get("minute", 0)
        home_score = match.get("home_score", 0)
        away_score = match.get("away_score", 0)
        
        # Convert minute to integer if it's string
        if isinstance(minute, str) and "'" in minute:
            minute = int(minute.replace("'", ""))
        else:
            minute = int(minute)
        
        # Base factors
        base_chance = 40
        time_factor = 0
        score_factor = 0
        pressure_factor = 0
        
        # Time-based factors (last 30 minutes)
        if minute >= 60:
            time_remaining = 90 - minute
            time_factor = (30 - time_remaining) * 2  # More pressure in last minutes
        
        # Score-based factors
        goal_difference = home_score - away_score
        
        if goal_difference == 0:  # Equal score - both teams attacking
            score_factor = 25
        elif abs(goal_difference) == 1:  # Close match - losing team attacks
            score_factor = 20
        elif abs(goal_difference) >= 2:  # One-sided
            score_factor = -10
        
        # Pressure factor (last 15 minutes)
        if minute >= 75:
            pressure_factor = 20
        
        # Calculate total chance
        total_chance = base_chance + time_factor + score_factor + pressure_factor
        
        # Add some randomness for realism
        randomness = random.randint(-5, 10)
        final_chance = min(95, max(10, total_chance + randomness))
        
        return final_chance
        
    except Exception as e:
        logger.error(f"❌ Error calculating prediction: {e}")
        return random.randint(60, 85)

def analyze_real_matches():
    """Analyze real matches and send predictions"""
    try:
        logger.info("🔍 Analyzing real matches...")
        real_matches = fetch_real_live_matches()
        predictions_sent = 0
        
        if not real_matches:
            logger.info("📭 No live matches found")
            return 0
        
        for match in real_matches:
            minute = match.get("minute", 0)
            
            # Only analyze matches that are in progress and past 60 minutes
            if minute >= 60:
                goal_chance = calculate_goal_prediction(match)
                
                if goal_chance >= 75:  # Lowered threshold for real matches
                    message = (
                        f"🔥 **REAL MATCH PREDICTION** 🔥\n\n"
                        f"⚽ **Match:** {match['home']} vs {match['away']}\n"
                        f"🏆 **League:** {match['league']}\n"
                        f"📊 **Live Score:** {match['score']} ({match['minute']}')\n"
                        f"🎯 **Prediction:** GOAL IN REMAINING TIME\n"
                        f"✅ **Confidence:** {goal_chance}%\n"
                        f"💰 **Bet Suggestion:** YES - Next Goal\n\n"
                        f"⏰ Match Time: {match['minute']} minutes played\n"
                        f"🔄 Next analysis in 5 minutes..."
                    )
                    
                    if send_telegram_message(message):
                        predictions_sent += 1
                        logger.info(f"✅ Real prediction sent: {match['home']} vs {match['away']}")
        
        # If no high-confidence predictions, send summary
        if predictions_sent == 0 and real_matches:
            summary_msg = "📊 **LIVE MATCHES SUMMARY**\n\n"
            for match in real_matches[:3]:  # Show first 3 matches
                summary_msg += f"⚽ {match['home']} vs {match['away']}\n"
                summary_msg += f"   📊 {match['score']} ({match['minute']}')\n"
                summary_msg += f"   🏆 {match['league']}\n\n"
            
            summary_msg += "🔄 Monitoring for betting opportunities..."
            send_telegram_message(summary_msg)
            predictions_sent = 1
        
        logger.info(f"📈 Real predictions sent: {predictions_sent}")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Real analysis error: {e}")
        return 0

def send_startup_message():
    """Send startup message"""
    try:
        message = (
            "🎯 **REAL MATCH BETTING BOT ACTIVATED!** 🎯\n\n"
            "✅ **Status:** Monitoring Real Matches\n"
            "🕒 **Startup Time:** " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n"
            "📡 **Source:** Sportmonks Live API\n"
            "⏰ **Update Interval:** Every 5 minutes\n"
            "🎪 **Features:**\n"
            "   • Real Live Match Data\n"
            "   • Goal Predictions (75%+ confidence)\n"
            "   • Top Leagues Only\n\n"
            "🔜 Scanning for live matches now...\n"
            "💰 Real betting opportunities coming up!"
        )
        return send_telegram_message(message)
    except Exception as e:
        logger.error(f"❌ Startup message failed: {e}")
        return False

def bot_worker():
    """Main bot worker function"""
    global bot_started
    logger.info("🔄 Starting real match bot worker...")
    
    # Wait for initialization
    time.sleep(10)
    
    # Send startup message
    logger.info("📤 Sending startup message...")
    if send_startup_message():
        logger.info("✅ Startup message delivered")
    else:
        logger.error("❌ Startup message failed")
    
    # Main loop - check every 5 minutes
    cycle = 0
    while True:
        try:
            cycle += 1
            logger.info(f"🔄 Analysis cycle #{cycle}")
            
            # Analyze REAL matches and send predictions
            predictions = analyze_real_matches()
            logger.info(f"📈 Cycle #{cycle}: {predictions} real predictions sent")
            
            # Send status update every 3 cycles
            if cycle % 3 == 0:
                status_msg = (
                    f"📊 **REAL BOT STATUS**\n\n"
                    f"🔄 Analysis Cycles: {cycle}\n"
                    f"📨 Total Messages: {message_counter}\n"
                    f"🎯 Last Predictions: {predictions}\n"
                    f"🕒 Last Update: {datetime.now().strftime('%H:%M:%S')}\n"
                    f"✅ Status: MONITORING REAL MATCHES\n\n"
                    f"⏰ Next real analysis in 5 minutes..."
                )
                send_telegram_message(status_msg)
            
            # Wait 5 minutes for next analysis
            logger.info("⏰ Waiting 5 minutes for next real match analysis...")
            time.sleep(300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"❌ Bot worker error: {e}")
            time.sleep(300)

def start_bot_thread():
    """Start bot in background thread"""
    global bot_started
    if not bot_started:
        logger.info("🚀 Starting real match bot thread...")
        thread = Thread(target=bot_worker, daemon=True)
        thread.start()
        bot_started = True
        logger.info("✅ Real match bot thread started")
    else:
        logger.info("✅ Bot thread already running")

# Auto-start bot
logger.info("🎯 Auto-starting real match bot...")
start_bot_thread()

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
