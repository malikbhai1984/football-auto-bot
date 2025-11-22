import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask
import logging
from datetime import datetime
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
load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
SPORTMONKS_API = os.getenv("SPORTMONKS_API", "").strip()

logger.info("🚀 Starting Live Scores Bot...")

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
    384: "Serie B", 462: "Coupe de France", 539: "UEFA Europa Conference League"
}

# Configuration
class Config:
    BOT_CYCLE_INTERVAL = 120  # 2 minutes
    API_TIMEOUT = 15

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

def fetch_all_live_matches():
    """Fetch all live matches from SportMonks"""
    try:
        logger.info("🌐 Fetching live matches from SportMonks...")
        
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        response = requests.get(url, timeout=Config.API_TIMEOUT)
        
        if response.status_code != 200:
            logger.error(f"❌ API Error: {response.status_code}")
            return []
        
        data = response.json()
        all_matches = data.get("data", [])
        logger.info(f"📊 Total matches from API: {len(all_matches)}")
        
        return all_matches
        
    except Exception as e:
        logger.error(f"❌ API fetch error: {e}")
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

def get_live_matches_with_scores():
    """Get all live matches with scores"""
    try:
        all_matches = fetch_all_live_matches()
        live_matches = []
        
        logger.info(f"🔍 Checking {len(all_matches)} matches for live games...")
        
        for match in all_matches:
            try:
                league_id = match.get("league_id")
                status = match.get("status", "")
                minute = match.get("minute", "")
                participants = match.get("participants", [])
                
                # Check if match is LIVE
                if status == "LIVE" and minute and minute not in ["FT", "HT", "PEN", "BT", "Canceled"]:
                    if len(participants) >= 2:
                        home_team = participants[0].get("name", "Unknown Home")
                        away_team = participants[1].get("name", "Unknown Away")
                        home_score = match.get("scores", {}).get("home_score", 0)
                        away_score = match.get("scores", {}).get("away_score", 0)
                        current_minute = parse_minute(minute)
                        
                        league_name = TOP_LEAGUES.get(league_id, f"League {league_id}")
                        
                        match_data = {
                            "home": home_team, "away": away_team, "league": league_name,
                            "score": f"{home_score}-{away_score}", "minute": minute,
                            "current_minute": current_minute, "home_score": home_score,
                            "away_score": away_score, "status": status, 
                            "match_id": match.get("id"), "is_live": True
                        }
                        
                        live_matches.append(match_data)
                        logger.info(f"✅ Live: {home_team} {home_score}-{away_score} {away_team} - {minute}")
                        
            except Exception as e:
                logger.error(f"❌ Error processing match: {e}")
                continue
        
        logger.info(f"🎯 Total live matches found: {len(live_matches)}")
        return live_matches
        
    except Exception as e:
        logger.error(f"❌ Live matches error: {e}")
        return []

def format_live_scores_message(live_matches):
    """Format live scores message for Telegram"""
    current_time = format_pakistan_time()
    
    if not live_matches:
        return f"""⚽ **LIVE MATCHES UPDATE** ⚽

🕒 **Last Check:** {current_time}

😴 **No live matches currently playing.**

⏰ Next check in 2 minutes..."""
    
    # Sort matches by minute (highest first)
    live_matches.sort(key=lambda x: x['current_minute'], reverse=True)
    
    message = f"""⚽ **LIVE MATCHES UPDATE** ⚽

🕒 **Last Check:** {current_time}
📊 **Total Live Matches:** {len(live_matches)}

"""
    
    for i, match in enumerate(live_matches, 1):
        # Add emoji based on match status
        if match['current_minute'] >= 80:
            time_emoji = "🔥"
        elif match['current_minute'] >= 60:
            time_emoji = "⚡" 
        else:
            time_emoji = "🕒"
        
        message += f"""**Match {i}:**
🏆 **League:** {match['league']}
{time_emoji} **Minute:** {match['minute']}
📊 **Score:** **{match['score']}**
🏠 **{match['home']}** vs 🛫 **{match['away']}**

"""
    
    message += "⏰ Next update in 2 minutes..."
    
    return message

def send_live_scores_update():
    """Send live scores update to Telegram"""
    try:
        logger.info("📊 Sending live scores update...")
        
        live_matches = get_live_matches_with_scores()
        message = format_live_scores_message(live_matches)
        
        if send_telegram_message(message):
            logger.info(f"✅ Live scores update sent - {len(live_matches)} matches")
            return True
        else:
            logger.error("❌ Failed to send live scores update")
            return False
            
    except Exception as e:
        logger.error(f"❌ Live scores update error: {e}")
        return False

@app.route("/")
def home():
    return f"""
    <html>
        <head><title>Live Scores Bot</title></head>
        <body>
            <h1>⚽ Live Scores Bot</h1>
            <p><strong>Status:</strong> 🟢 Running</p>
            <p><strong>Last Check:</strong> {format_pakistan_time()}</p>
            <p><strong>Messages Sent:</strong> {message_counter}</p>
            <p><a href="/health">Health Check</a> | <a href="/live-scores">Live Scores</a></p>
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

@app.route("/live-scores")
def live_scores():
    try:
        live_matches = get_live_matches_with_scores()
        result = {
            "timestamp": format_pakistan_time(),
            "live_matches": len(live_matches),
            "matches": live_matches
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def send_startup_message():
    startup_msg = f"""🚀 **Live Scores Bot Started!**

⏰ **Startup Time:** {format_pakistan_time()}
📊 **API Status:** ✅ Connected
🔄 **Update Interval:** {Config.BOT_CYCLE_INTERVAL} seconds

🤖 **Features:**
   • Real-time live scores
   • All major leagues
   • Automatic updates every 2 minutes
   • No predictions - just live scores

Bot is now actively monitoring live matches!"""
    send_telegram_message(startup_msg)

def bot_worker():
    global bot_started
    logger.info("🔄 Starting Live Scores Bot Worker...")
    bot_started = True
    
    time.sleep(2)
    send_startup_message()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            current_time = format_pakistan_time()
            logger.info(f"🔄 Cycle #{cycle} at {current_time}")
            
            # Send live scores update
            send_live_scores_update()
            
            logger.info(f"⏰ Waiting {Config.BOT_CYCLE_INTERVAL} seconds...")
            time.sleep(Config.BOT_CYCLE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Bot worker error: {e}")
            time.sleep(Config.BOT_CYCLE_INTERVAL)

def start_bot():
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 Live Scores Bot started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return False

# Auto-start bot
logger.info("🎯 Auto-starting Live Scores Bot...")
if start_bot():
    logger.info("✅ Bot auto-started successfully")
else:
    logger.error("❌ Bot auto-start failed")

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
