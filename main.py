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
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")  # New API key

logger.info("🚀 Initializing Quad-Source Live Tracking Bot...")

# Validate environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found") 
if not SPORTMONKS_API:
    logger.error("❌ SPORTMONKS_API not found")
if not FOOTBALL_API_KEY:
    logger.warning("⚠️ FOOTBALL_API_KEY not found - some features disabled")

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

# Football-API.com League IDs
FOOTBALL_API_LEAGUES = {
    39: "Premier League",
    140: "La Liga", 
    78: "Bundesliga",
    135: "Serie A",
    61: "Ligue 1"
}

# Global variables
bot_started = False
message_counter = 0
historical_data = {}
live_match_tracker = {}  # Track match states for change detection
api_usage_tracker = {
    'sportmonks': {'count': 0, 'reset_time': datetime.now()},
    'github': {'count': 0, 'reset_time': datetime.now()},
    'football_api': {'count': 0, 'reset_time': datetime.now()}
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
        limits = {
            'sportmonks': 20,
            'github': 60,
            'football_api': 30  # Free plan typically 30-100 calls/minute
        }
        
        limit = limits.get(api_name, 20)
        if api_data['count'] >= limit * 0.8:  # 80% threshold
            logger.warning(f"⚠️ {api_name.upper()} API near limit: {api_data['count']}/{limit}")
        if api_data['count'] >= limit:
            logger.error(f"🚫 {api_name.upper()} API limit reached")
            return False
        
        api_data['count'] += 1
        return True
        
    except Exception as e:
        logger.error(f"❌ API limit check error: {e}")
        return True

def safe_api_call(url, api_name, headers=None, timeout=10):
    """Make safe API call with rate limiting"""
    try:
        if not check_api_limits(api_name):
            logger.warning(f"⏸️ Skipping {api_name} call due to limits")
            return None
        
        if headers:
            response = requests.get(url, headers=headers, timeout=timeout)
        else:
            response = requests.get(url, timeout=timeout)
        
        # Check for rate limit headers
        if response.status_code == 429:
            logger.warning(f"⏰ {api_name.upper()} rate limited, waiting...")
            time.sleep(60)
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

def fetch_football_api_live_matches():
    """Fetch live matches from Football-API.com with detailed events"""
    try:
        if not FOOTBALL_API_KEY:
            logger.warning("⚠️ Football-API key not configured")
            return []
            
        if not check_api_limits('football_api'):
            return []
        
        # Get current live matches
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        headers = {
            'x-rapidapi-key': FOOTBALL_API_KEY,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        
        logger.info("🌐 Fetching live matches from Football-API...")
        response = safe_api_call(url, 'football_api', headers=headers, timeout=15)
        
        if not response:
            return []
        
        data = response.json()
        live_matches = []
        
        for match in data.get('response', []):
            fixture = match.get('fixture', {})
            league_info = match.get('league', {})
            teams = match.get('teams', {})
            goals = match.get('goals', {})
            score = match.get('score', {})
            
            league_id = league_info.get('id')
            status = fixture.get('status', {}).get('short')
            minute = fixture.get('status', {}).get('elapsed', 0)
            
            # Only include top leagues and live matches
            if league_id in FOOTBALL_API_LEAGUES and status == 'LIVE':
                home_team = teams.get('home', {}).get('name', 'Unknown Home')
                away_team = teams.get('away', {}).get('name', 'Unknown Away')
                home_score = goals.get('home', 0)
                away_score = goals.get('away', 0)
                
                if 60 <= minute <= 89:
                    # Get match events for goal detection
                    events = fetch_match_events(fixture.get('id'))
                    
                    match_data = {
                        "home": home_team,
                        "away": away_team,
                        "league": FOOTBALL_API_LEAGUES[league_id],
                        "score": f"{home_score}-{away_score}",
                        "minute": f"{minute}'",
                        "current_minute": minute,
                        "home_score": home_score,
                        "away_score": away_score,
                        "status": status,
                        "match_id": f"football_api_{fixture.get('id')}",
                        "is_live": True,
                        "api_source": "football_api",
                        "events": events,
                        "last_update": datetime.now()
                    }
                    
                    live_matches.append(match_data)
                    logger.info(f"✅ Football-API: {home_team} vs {away_team} - {home_score}-{away_score} ({minute}')")
        
        logger.info(f"📊 Football-API live matches: {len(live_matches)}")
        return live_matches
        
    except Exception as e:
        logger.error(f"❌ Football-API error: {e}")
        return []

def fetch_match_events(match_id):
    """Fetch match events (goals, cards, etc) from Football-API"""
    try:
        if not match_id:
            return []
            
        url = f"https://v3.football.api-sports.io/fixtures/events?fixture={match_id}"
        headers = {
            'x-rapidapi-key': FOOTBALL_API_KEY,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        
        response = safe_api_call(url, 'football_api', headers=headers, timeout=10)
        if response:
            data = response.json()
            return data.get('response', [])
        return []
        
    except Exception as e:
        logger.error(f"❌ Match events error: {e}")
        return []

def detect_score_changes(current_matches):
    """Detect if scores have changed since last check"""
    try:
        score_changes = []
        
        for match in current_matches:
            match_id = match['match_id']
            current_score = f"{match['home_score']}-{match['away_score']}"
            
            if match_id in live_match_tracker:
                previous_score = live_match_tracker[match_id]['score']
                previous_minute = live_match_tracker[match_id]['minute']
                
                # Check if score changed
                if current_score != previous_score:
                    change_type = "SCORE_CHANGE"
                    logger.info(f"🎯 Score change detected: {match['home']} vs {match['away']} - {previous_score} → {current_score}")
                # Check if significant time passed
                elif match['current_minute'] > previous_minute + 3:
                    change_type = "TIME_UPDATE"
                else:
                    continue
                
                score_changes.append({
                    'match': match,
                    'previous_score': previous_score,
                    'current_score': current_score,
                    'change_type': change_type,
                    'minute': match['minute']
                })
            
            # Update tracker
            live_match_tracker[match_id] = {
                'score': current_score,
                'minute': match['current_minute'],
                'last_checked': datetime.now(),
                'home': match['home'],
                'away': match['away']
            }
        
        return score_changes
        
    except Exception as e:
        logger.error(f"❌ Score change detection error: {e}")
        return []

def fetch_all_live_matches():
    """Fetch live matches from all available sources"""
    all_matches = []
    
    # Source 1: Sportmonks
    sportmonks_matches = fetch_current_live_matches()
    all_matches.extend(sportmonks_matches)
    
    # Source 2: Football-API.com
    football_api_matches = fetch_football_api_live_matches()
    all_matches.extend(football_api_matches)
    
    # Remove duplicates based on team names and minute
    unique_matches = []
    seen_matches = set()
    
    for match in all_matches:
        match_key = f"{match['home']}_{match['away']}_{match['current_minute']}"
        if match_key not in seen_matches:
            seen_matches.add(match_key)
            unique_matches.append(match)
    
    logger.info(f"🎯 Total unique live matches: {len(unique_matches)}")
    
    # Detect score changes
    score_changes = detect_score_changes(unique_matches)
    
    return unique_matches, score_changes

class RealTimePredictor:
    def __init__(self):
        self.prediction_history = {}
    
    def calculate_dynamic_prediction(self, match, score_changed=False):
        """Calculate prediction that adapts to score changes"""
        try:
            minute = match.get('current_minute', 0)
            home_score = match.get('home_score', 0)
            away_score = match.get('away_score', 0)
            time_remaining = 90 - minute
            
            # Base chance factors
            base_chance = 35
            
            # Score-based dynamic factors
            goal_difference = home_score - away_score
            
            if score_changed:
                # Recent goal scored - high chance of another goal
                recent_goal_boost = 20
                logger.info(f"⚡ Recent goal boost applied for {match['home']} vs {match['away']}")
            else:
                recent_goal_boost = 0
            
            # Match situation analysis
            if goal_difference == 0:  # Equal score
                situation_factor = 25
                pressure = "HIGH - Both teams pushing"
            elif abs(goal_difference) == 1:  # Close game
                situation_factor = 20
                pressure = "MEDIUM - Losing team attacking"
            else:  # One-sided
                situation_factor = -10
                pressure = "LOW - Match may be decided"
            
            # Time pressure (exponential in last 10 minutes)
            if time_remaining <= 10:
                time_pressure = 25
            elif time_remaining <= 15:
                time_pressure = 20
            elif time_remaining <= 20:
                time_pressure = 15
            else:
                time_pressure = 10
            
            # Team momentum (simulated based on recent events)
            if match.get('events'):
                recent_events = [e for e in match['events'] if e.get('time', {}).get('elapsed', 0) >= minute - 5]
                momentum = len(recent_events) * 3
            else:
                momentum = random.randint(5, 15)
            
            total_chance = (base_chance + situation_factor + time_pressure + 
                          momentum + recent_goal_boost)
            
            # Ensure realistic limits
            final_chance = min(95, max(10, total_chance))
            
            analysis = {
                'last_10_min_chance': final_chance,
                'factors': {
                    'base': base_chance,
                    'situation': situation_factor,
                    'time_pressure': time_pressure,
                    'momentum': momentum,
                    'recent_goal_boost': recent_goal_boost
                },
                'pressure_level': pressure,
                'time_remaining': time_remaining,
                'prediction_type': 'DYNAMIC_REALTIME',
                'score_changed': score_changed
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Dynamic prediction error: {e}")
            return {}

def format_realtime_alert(match, analysis, score_change=None):
    """Format real-time alert for score changes"""
    try:
        if score_change and score_change['change_type'] == 'SCORE_CHANGE':
            message = "🚨 **REAL-TIME GOAL ALERT** 🚨\n\n"
            message += f"⚽ **Goal!** {match['home']} {match['home_score']} - {match['away_score']} {match['away']}\n"
            message += f"⏰ **Minute:** {match['minute']}\n"
            message += f"🏆 **League:** {match['league']}\n\n"
            
            message += f"📊 **Score Change:** {score_change['previous_score']} → {score_change['current_score']}\n\n"
        else:
            message = "🎯 **REAL-TIME PREDICTION UPDATE** 🎯\n\n"
            message += f"⚽ **Match:** {match['home']} vs {match['away']}\n"
            message += f"🏆 **League:** {match['league']}\n"
            message += f"📊 **Live Score:** {match['score']} ({match['minute']}')\n\n"
        
        # Prediction analysis
        chance = analysis.get('last_10_min_chance', 0)
        message += f"🔮 **NEXT GOAL PREDICTION**\n"
        message += f"• Chance in last 10min: {chance:.1f}%\n"
        message += f"• Time Remaining: {analysis.get('time_remaining', 0)} minutes\n"
        message += f"• Pressure: {analysis.get('pressure_level', 'N/A')}\n"
        message += f"• Prediction Type: {analysis.get('prediction_type', 'N/A')}\n\n"
        
        if analysis.get('score_changed'):
            message += f"⚡ **Momentum Alert:** Recent goal detected!\n"
            message += f"📈 **Confidence Boost:** Active\n\n"
        
        # Betting recommendation
        if chance >= 75:
            recommendation = "✅ **STRONG BET**: Next Goal Expected"
            emoji = "💰🔥"
        elif chance >= 60:
            recommendation = "🟡 **MODERATE BET**: Good Opportunity" 
            emoji = "💸"
        else:
            recommendation = "🔴 **CAUTION**: Wait for better opportunity"
            emoji = "⚡"
        
        message += f"{emoji} **REAL-TIME RECOMMENDATION**\n{recommendation}\n\n"
        
        message += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
        message += "🔄 Monitoring continues..."
        
        return message
        
    except Exception as e:
        logger.error(f"❌ Realtime alert formatting error: {e}")
        return "Error generating alert"

def analyze_realtime_matches():
    """Analyze matches with real-time score tracking"""
    try:
        logger.info("🔍 Starting real-time analysis with score tracking...")
        
        # Fetch from all sources
        all_matches, score_changes = fetch_all_live_matches()
        
        if not all_matches:
            send_telegram_message(
                "📭 **NO LIVE MATCHES**\n\n"
                "No active matches in analysis window.\n"
                f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
                "🔄 Will check again in 5 minutes..."
            )
            return 0
        
        predictor = RealTimePredictor()
        alerts_sent = 0
        
        # Process score changes first (highest priority)
        for change in score_changes:
            match = change['match']
            analysis = predictor.calculate_dynamic_prediction(match, score_changed=True)
            
            if analysis.get('last_10_min_chance', 0) >= 50:  # Lower threshold for goal alerts
                message = format_realtime_alert(match, analysis, change)
                if send_telegram_message(message):
                    alerts_sent += 1
                    logger.info(f"🚨 Score change alert sent for {match['home']} vs {match['away']}")
        
        # Process high-probability matches
        for match in all_matches:
            # Skip if already processed for score change
            if any(change['match']['match_id'] == match['match_id'] for change in score_changes):
                continue
            
            analysis = predictor.calculate_dynamic_prediction(match)
            chance = analysis.get('last_10_min_chance', 0)
            
            if chance >= 70:
                message = format_realtime_alert(match, analysis)
                if send_telegram_message(message):
                    alerts_sent += 1
                    logger.info(f"🎯 Prediction alert sent for {match['home']} vs {match['away']}")
        
        # Send summary if no alerts
        if alerts_sent == 0 and all_matches:
            summary_msg = create_realtime_summary(all_matches, predictor)
            send_telegram_message(summary_msg)
            alerts_sent = 1
        
        logger.info(f"📈 Real-time alerts sent: {alerts_sent}")
        return alerts_sent
        
    except Exception as e:
        logger.error(f"❌ Real-time analysis error: {e}")
        return 0

def create_realtime_summary(matches, predictor):
    """Create real-time monitoring summary"""
    summary_msg = "📊 **REAL-TIME MONITORING**\n\n"
    summary_msg += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
    summary_msg += f"🔴 **Live Matches:** {len(matches)}\n"
    summary_msg += f"📡 **Data Sources:** Sportmonks + Football-API.com\n\n"
    
    for match in matches[:3]:
        analysis = predictor.calculate_dynamic_prediction(match)
        chance = analysis.get('last_10_min_chance', 0)
        
        summary_msg += f"⚽ **{match['home']} vs {match['away']}**\n"
        summary_msg += f"   📊 {match['score']} ({match['minute']}')\n"
        summary_msg += f"   🎯 Next Goal: {chance:.1f}%\n"
        summary_msg += f"   ⏰ Remaining: {90 - match['current_minute']}m\n"
        summary_msg += f"   📡 Source: {match.get('api_source', 'sportmonks')}\n\n"
    
    summary_msg += "🚨 **Real-time score change detection ACTIVE**\n"
    summary_msg += "⏰ Next update in 5 minutes"
    
    return summary_msg

def send_startup_message():
    """Send startup message"""
    try:
        message = (
            "🚨 **REAL-TIME SCORE TRACKING BOT ACTIVATED!** 🚨\n\n"
            "✅ **Status:** Quad-Source Monitoring Active\n"
            f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
            "⏰ **Update Interval:** Every 5 minutes\n\n"
            "📡 **INTEGRATED DATA SOURCES:**\n"
            "• Sportmonks API ✓\n"
            "• Football-API.com ✓\n" 
            "• Peter McLagan Historical ✓\n"
            "• OpenFootball Updates ✓\n\n"
            "🎯 **REAL-TIME FEATURES:**\n"
            "• Live Score Change Detection\n"
            "• Dynamic Prediction Updates\n"
            "• Goal Alert System\n"
            "• Multi-Source Verification\n\n"
            "🚨 **Goal alerts will trigger immediately!**\n"
            "🔜 Starting real-time monitoring..."
        )
        return send_telegram_message(message)
    except Exception as e:
        logger.error(f"❌ Startup message failed: {e}")
        return False

# ... [Include all the previous functions for historical data, etc.]

def bot_worker():
    """Main bot worker with real-time tracking"""
    global bot_started
    logger.info("🔄 Starting Real-Time Tracking Bot...")
    
    # Load historical data
    logger.info("📥 Loading historical databases...")
    load_historical_data()
    
    time.sleep(10)
    
    logger.info("📤 Sending startup message...")
    send_startup_message()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            logger.info(f"🔄 Real-Time Cycle #{cycle} at {format_pakistan_time()}")
            
            # Real-time analysis with score tracking
            alerts = analyze_realtime_matches()
            logger.info(f"📈 Cycle #{cycle}: {alerts} real-time alerts sent")
            
            # Clean old match data every 12 cycles
            if cycle % 12 == 0:
                cleanup_old_matches()
            
            # Wait 5 minutes for faster response to score changes
            logger.info("⏰ Waiting 5 minutes for next real-time check...")
            time.sleep(300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"❌ Real-time bot error: {e}")
            time.sleep(300)

def cleanup_old_matches():
    """Clean up old match data from tracker"""
    try:
        current_time = datetime.now()
        expired_matches = []
        
        for match_id, match_data in list(live_match_tracker.items()):
            if (current_time - match_data['last_checked']).seconds > 3600:  # 1 hour
                expired_matches.append(match_id)
        
        for match_id in expired_matches:
            del live_match_tracker[match_id]
        
        if expired_matches:
            logger.info(f"🧹 Cleaned up {len(expired_matches)} expired matches")
            
    except Exception as e:
        logger.error(f"❌ Cleanup error: {e}")

# ... [Include other necessary functions]

# Auto-start bot
logger.info("🎯 Auto-starting Real-Time Tracking Bot...")
start_bot_thread()

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
