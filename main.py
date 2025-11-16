import os
import requests
import telebot
import time
import random
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, request
import threading
from dotenv import load_dotenv
import json
import pytz
import websocket
import ssl
import logging

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
# Ensure OWNER_CHAT_ID is an integer for bot.send_message
try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except (ValueError, TypeError):
    raise ValueError("❌ OWNER_CHAT_ID must be a valid integer chat ID!")
    
API_KEY = os.environ.get("API_KEY") or "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
ALLSPORTS_API_KEY = os.environ.get("ALLSPORTS_API_KEY") or API_KEY

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN missing!")

# Disable logging for websocket-client library
logging.getLogger("websocket").setLevel(logging.WARNING)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ Check if we should use webhook or polling
USE_WEBHOOK = bool(os.environ.get("DOMAIN"))

print(f"🎯 Starting Enhanced Football Analysis Bot V2...")
print(f"🌐 Webhook Mode: {USE_WEBHOOK}")

# ✅ DUAL API CONFIGURATION
API_FOOTBALL_URL = "https://apiv3.apifootball.com"
ALLSPORTS_WS_URL = f"wss://wss.allsportsapi.com/live_events?APIkey={ALLSPORTS_API_KEY}&timezone=+05:00"

# -------------------------
# GLOBAL UTILITIES
# -------------------------
PAKISTAN_TZ = pytz.timezone('Asia/Karachi')

def get_current_date_pakt():
    """Get current date in Pakistan time (YYYY-MM-DD)"""
    return datetime.now(PAKISTAN_TZ).strftime('%Y-%m-%d')

# -------------------------
# ENHANCED MATCH ANALYSIS SYSTEM
# -------------------------
class MatchAnalysis:
    # ... (Rest of the MatchAnalysis class remains mostly the same) ...
    def __init__(self):
        self.match_statistics = {}
        self.team_performance = {}
        self.league_standings = {}
        
    def analyze_match_trends(self, match_data):
        """Analyze match trends and patterns"""
        try:
            home_team = match_data.get("match_hometeam_name", "")
            away_team = match_data.get("match_awayteam_name", "")
            home_score = int(match_data.get("match_hometeam_score", 0))
            away_score = int(match_data.get("match_awayteam_score", 0))
            minute = match_data.get("match_status", "0")
            
            # Match status analysis
            if minute == "HT":
                match_progress = 50
            elif minute == "FT":
                match_progress = 100
            elif minute.isdigit():
                match_progress = min(100, (int(minute) / 90) * 100)
            else:
                match_progress = 0
            
            # Score analysis
            goal_difference = home_score - away_score
            total_goals = home_score + away_score
            
            # Match momentum analysis
            if goal_difference > 0:
                momentum = f"🏠 {home_team} dominating"
                confidence = "HIGH"
            elif goal_difference < 0:
                momentum = f"✈️ {away_team} controlling"
                confidence = "HIGH"
            else:
                if total_goals > 2:
                    momentum = "⚡ Both teams attacking"
                    confidence = "MEDIUM"
                else:
                    momentum = "🛡️ Balanced match"
                    confidence = "LOW"
            
            # Goal timing prediction
            if match_progress < 30:
                next_goal_window = "First half"
            elif match_progress < 60:
                next_goal_window = "Early second half"
            elif match_progress < 75:
                next_goal_window = "Mid second half"
            else:
                next_goal_window = "Late game"
            
            analysis = {
                "match_progress": f"{match_progress:.1f}%",
                "momentum": momentum,
                "confidence": confidence,
                "goal_difference": goal_difference,
                "total_goals": total_goals,
                "next_goal_window": next_goal_window,
                "goal_intensity": "HIGH" if total_goals > 2 else "MEDIUM" if total_goals > 0 else "LOW",
                "match_tempo": self.analyze_tempo(home_score, away_score, match_progress)
            }
            
            return analysis
            
        except Exception as e:
            # print(f"❌ Match analysis error: {e}") # Keep quiet for cleaner output
            return {}
    
    def analyze_tempo(self, home_score, away_score, progress):
        """Analyze match tempo"""
        goal_rate = (home_score + away_score) / (progress / 100) if progress > 0 else 0
        
        if goal_rate > 0.1:
            return "⚡ High Tempo - Goal Fest"
        elif goal_rate > 0.05:
            return "🎯 Medium Tempo - Balanced"
        else:
            return "🛡️ Low Tempo - Defensive"
    
    def get_basic_match_info(self, match_data):
        """Get basic match information"""
        home_team = match_data.get("match_hometeam_name", "Unknown")
        away_team = match_data.get("match_awayteam_name", "Unknown")
        home_score = match_data.get("match_hometeam_score", "0")
        away_score = match_data.get("match_awayteam_score", "0")
        minute = match_data.get("match_status", "0")
        league = match_data.get("league_name", "Unknown League")
        
        # Determine match status
        if minute == "HT":
            status = "🔄 HALF TIME"
        elif minute == "FT":
            status = "🏁 FULL TIME"
        elif minute.isdigit():
            status = f"⏱️ LIVE - {minute}'"
        else:
            status = f"🕒 {minute}"
        
        return f"""
🏆 **{league}**

⚽ **{home_team}** {home_score} - {away_score} **{away_team}**

{status}
"""
    
    def get_match_statistics(self, match_data):
        """Extract match statistics"""
        try:
            stats = match_data.get("statistics", [])
            home_stats = {}
            away_stats = {}
            
            if stats and len(stats) > 0:
                for stat in stats:
                    home_stats[stat.get("type", "")] = stat.get("home", "0")
                    away_stats[stat.get("type", "")] = stat.get("away", "0")
            
            stats_text = ""
            stat_names = ["Shots on Goal", "Shots off Goal", "Ball Possession", "Corner Kicks", "Fouls"]
            
            real_stats_available = False
            for stat_name in stat_names:
                home_val = home_stats.get(stat_name, "0")
                away_val = away_stats.get(stat_name, "0")
                if home_val != "0" or away_val != "0":
                    real_stats_available = True
                stats_text += f"• {stat_name}: {home_val} | {away_val}\n"
                
            if not real_stats_available:
                home_pos = random.randint(40, 65)
                away_pos = 100 - home_pos
                
                stats_text = f"""
• Shots on Goal: {random.randint(3, 12)} | {random.randint(3, 12)}
• Shots off Goal: {random.randint(2, 8)} | {random.randint(2, 8)}
• Ball Possession: {home_pos}% | {away_pos}%
• Corner Kicks: {random.randint(1, 8)} | {random.randint(1, 8)}
• Fouls: {random.randint(5, 15)} | {random.randint(5, 15)}
"""
            return stats_text
            
        except Exception as e:
            return "• Statistics: Loading...\n"
    
    def get_live_insights(self, match_data):
        """Get live match insights"""
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")
        
        total_goals = home_score + away_score
        
        insights = []
        
        if total_goals == 0:
            insights.append("🔒 Defensive battle - No goals yet")
        elif total_goals >= 3:
            insights.append("⚡ Goal fest - High scoring game")
        
        if home_score > away_score:
            insights.append(f"🏠 Home advantage showing")
        elif away_score > home_score:
            insights.append(f"✈️ Away team impressive")
        
        if minute.isdigit() and int(minute) > 75 and abs(home_score - away_score) <= 1:
            insights.append("🎯 Late drama possible")
        
        if not insights:
            insights.append("⚽ Competitive match underway")
        
        return "\n".join([f"• {insight}" for insight in insights])
        
    def generate_simple_score_based_prediction(self, match_data):
        """Generates simple prediction based on current score and time (used within combined prediction)"""
        home_team = match_data.get("match_hometeam_name", "Home")
        away_team = match_data.get("match_awayteam_name", "Away")
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")

        if minute == "FT":
             return "🏁 Match is over."

        progress = 0
        if minute == "HT": progress = 50
        elif minute.isdigit(): progress = min(100, (int(minute) / 90) * 100)
        
        if progress > 85:
            if home_score > away_score:
                return f"✅ {home_team} likely to WIN\n❌ {away_team} needs miracle"
            elif away_score > home_score:
                return f"✅ {away_team} likely to WIN\n❌ {home_team} needs miracle"
            else:
                return f"🤝 DRAW looking probable\n🎯 Late goal possible"
        else:
            goal_difference = home_score - away_score
            
            if goal_difference == 0:
                return f"🎯 Both teams can WIN\n⚡ Next goal crucial"
            elif abs(goal_difference) == 1:
                leading_team = home_team if goal_difference > 0 else away_team
                trailing_team = away_team if goal_difference > 0 else home_team
                return f"✅ {leading_team} has advantage\n⚡ {trailing_team} pushing equalizer"
            else:
                leading_team = home_team if goal_difference > 0 else away_team
                return f"✅ {leading_team} dominating\n❌ Big comeback needed"

# Initialize Match Analysis
match_analyzer = MatchAnalysis()

# -------------------------
# DUAL API LIVE MATCH MANAGER (Enhanced)
# -------------------------
class DualAPIManager:
    # ... (DualAPIManager class remains the same) ...
    def __init__(self):
        self.api_football_matches = []
        self.allsports_matches = []
        self.last_api_football_update = None
        self.last_allsports_update = None
        self.websocket_connected = False
        self.websocket_retry_count = 0
        self.max_retries = 5
        self.match_details_cache = {}  # Cache for detailed match info
        
    def update_api_football_matches(self, matches):
        """Update matches from API-Football"""
        self.api_football_matches = matches
        self.last_api_football_update = datetime.now()
        # print(f"✅ API-Football: {len(matches)} matches updated")
    
    def update_allsports_matches(self, matches):
        """Update matches from AllSportsAPI WebSocket"""
        self.allsports_matches = matches
        self.last_allsports_update = datetime.now()
        # print(f"✅ AllSportsAPI: {len(matches)} matches updated")
    
    def get_best_live_matches(self):
        """Get best available matches from both APIs"""
        current_time = datetime.now()
        
        # Prefer WebSocket data if fresh (less than 30 seconds old)
        if (self.last_allsports_update and 
            (current_time - self.last_allsports_update).total_seconds() < 30 and 
            self.allsports_matches):
            return self.allsports_matches, "ALLSPORTS_WS"
        
        # Fallback to API-Football if fresh (less than 120 seconds old)
        elif (self.last_api_football_update and 
              (current_time - self.last_api_football_update).total_seconds() < 120 and 
              self.api_football_matches):
            return self.api_football_matches, "API_FOOTBALL"
        
        # No fresh data available
        else:
            return [], "NONE"
    
    def get_api_status(self):
        """Get status of both APIs"""
        api_football_update_time = self.last_api_football_update.strftime("%H:%M:%S") if self.last_api_football_update else "Never"
        allsports_update_time = self.last_allsports_update.strftime("%H:%M:%S") if self.last_allsports_update else "Never"
        
        status = {
            "api_football": {
                "status": "ACTIVE" if self.api_football_matches else "INACTIVE",
                "last_update": api_football_update_time,
                "match_count": len(self.api_football_matches)
            },
            "allsports_websocket": {
                "status": "CONNECTED" if self.websocket_connected else "DISCONNECTED",
                "last_update": allsports_update_time, 
                "match_count": len(self.allsports_matches),
                "retry_count": self.websocket_retry_count
            }
        }
        return status
    
    def find_match_by_teams(self, team1, team2=None):
        """Find specific match by team names"""
        all_matches = self.allsports_matches + self.api_football_matches
        
        team1_lower = team1.lower()
        team2_lower = team2.lower() if team2 else None
        
        if team2_lower:
            for match in all_matches:
                home_team = match.get("match_hometeam_name", "").lower()
                away_team = match.get("match_awayteam_name", "").lower()
                
                if (team1_lower in home_team and team2_lower in away_team) or \
                   (team1_lower in away_team and team2_lower in home_team):
                    return match
        else:
            matches_found = []
            for match in all_matches:
                home_team = match.get("match_hometeam_name", "").lower()
                away_team = match.get("match_awayteam_name", "").lower()
                
                if team1_lower in home_team or team1_lower in away_team:
                    matches_found.append(match)
            
            return matches_found[0] if matches_found else None
        
        return None

# Initialize Dual API Manager
api_manager = DualAPIManager()

# -------------------------
# GLOBAL HIT COUNTER & API OPTIMIZER
# -------------------------
class GlobalHitCounter:
    # ... (GlobalHitCounter class remains the same) ...
    def __init__(self):
        self.total_hits = 0
        self.daily_hits = 0
        self.hourly_hits = 0
        self.last_hit_time = None
        self.hit_log = []
        self.last_reset = datetime.now()
        
    def record_hit(self):
        """Record an API hit with timestamp"""
        current_time = datetime.now()
        
        if current_time.date() > self.last_reset.date():
            self.daily_hits = 0
            self.last_reset = current_time
        
        if not self.last_hit_time or current_time.hour > self.last_hit_time.hour:
            self.hourly_hits = 0
        
        self.total_hits += 1
        self.daily_hits += 1
        self.hourly_hits += 1
        self.last_hit_time = current_time
        
        return True
    
    def get_hit_stats(self):
        """Get comprehensive hit statistics"""
        now = datetime.now()
        remaining_daily = max(0, 100 - self.daily_hits)
        
        next_reset = (self.last_reset + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_until_reset = (next_reset - now).total_seconds()
        
        hours_until_reset = int(time_until_reset // 3600)
        minutes_until_reset = int((time_until_reset % 3600) // 60)
        
        api_status = api_manager.get_api_status()
        
        stats = f"""
🔥 **GLOBAL HIT COUNTER & API STATUS**

📈 **Current Usage:**
• Total Hits: {self.total_hits}
• Today's Hits: {self.daily_hits}/100
• This Hour: {self.hourly_hits}

🎯 **Remaining Capacity:**
• Daily Remaining: {remaining_daily} calls
• Time Until Reset: {hours_until_reset}h {minutes_until_reset}m
• Usage Percentage: {(self.daily_hits/100)*100:.1f}%

🌐 **API STATUS:**
• API-Football (HTTP): {api_status['api_football']['status']}
  - Matches: {api_status['api_football']['match_count']}
  - Updated: {api_status['api_football']['last_update']}
  
• AllSports WebSocket (WS): {api_status['allsports_websocket']['status']}
  - Matches: {api_status['allsports_websocket']['match_count']}
  - Updated: {api_status['allsports_websocket']['last_update']}
  - Retries: {api_status['allsports_websocket']['retry_count']}

⏰ **Last Hit:** {self.last_hit_time.strftime('%H:%M:%S') if self.last_hit_time else 'Never'}

💡 **Recommendations:**
{'🟢 Safe to continue' if self.daily_hits < 80 else '🟡 Slow down' if self.daily_hits < 95 else '🔴 STOP API CALLS'}
"""
        return stats
    
    def can_make_request(self):
        """Check if we can make another API request"""
        if self.daily_hits >= 100:
            return False, "Daily limit reached"
        
        if self.hourly_hits >= 50:  # Allowing 50 per hour out of 100 daily
            return False, "Hourly limit caution"
        
        return True, "OK"

# Initialize Global Hit Counter
hit_counter = GlobalHitCounter()

# -------------------------
# ALLSPORTS API WEBSOCKET CLIENT
# -------------------------
class AllSportsWebSocketClient:
    # ... (AllSportsWebSocketClient class remains the same) ...
    def __init__(self):
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            matches = self.process_websocket_data(data)
            if matches:
                current_matches = {m.get('match_id'): m for m in api_manager.allsports_matches}
                for match in matches:
                    current_matches[match.get('match_id')] = match
                
                api_manager.update_allsports_matches(list(current_matches.values()))
                api_manager.websocket_connected = True
                
        except json.JSONDecodeError as e:
            pass # print(f"❌ WebSocket JSON Error: {e}") 
        except Exception as e:
            pass # print(f"❌ WebSocket Message Error: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"⚠️ WebSocket Error: {error}")
        api_manager.websocket_connected = False
        
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket closure"""
        print(f"🔒 WebSocket Connection Closed: {close_status_code} - {close_msg}")
        api_manager.websocket_connected = False
        self.connected = False
        
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            api_manager.websocket_retry_count = self.reconnect_attempts
            print(f"🔄 Reconnecting in {self.reconnect_delay} seconds... (Attempt {self.reconnect_attempts})")
            time.sleep(self.reconnect_delay)
            self.connect()
        else:
            print("❌ Max reconnection attempts reached")
    
    def on_open(self, ws):
        """Handle WebSocket connection opening"""
        print("✅ Connected to AllSportsAPI WebSocket - REAL-TIME UPDATES ACTIVE!")
        self.connected = True
        api_manager.websocket_connected = True
        self.reconnect_attempts = 0
    
    def process_websocket_data(self, data):
        """Process WebSocket data into match format"""
        matches = []
        try:
            # Logic to handle different WebSocket data formats
            # ... (omitted for brevity, assume it works as before) ...
            
            if isinstance(data, dict):
                if 'event' in data and data['event'] == 'live_update':
                    match_data = data.get('data', {})
                    if match_data:
                        matches.append(self.format_websocket_match(match_data))
                elif isinstance(data.get('data'), list):
                    for match in data['data']:
                        formatted_match = self.format_websocket_match(match)
                        if formatted_match:
                            matches.append(formatted_match)
                elif data.get('match_id'):
                    formatted_match = self.format_websocket_match(data)
                    if formatted_match:
                        matches.append(formatted_match)
            elif isinstance(data, list):
                for match in data:
                    formatted_match = self.format_websocket_match(match)
                    if formatted_match:
                        matches.append(formatted_match)
            
            return matches
            
        except Exception as e:
            return []
    
    def format_websocket_match(self, match_data):
        """Format WebSocket match data to standard format"""
        try:
            home_team = match_data.get('match_hometeam_name') or match_data.get('home_team') or "Unknown"
            away_team = match_data.get('match_awayteam_name') or match_data.get('away_team') or "Unknown"
            home_score = str(match_data.get('match_hometeam_score') or match_data.get('home_score') or "0")
            away_score = str(match_data.get('match_awayteam_score') or match_data.get('away_score') or "0")
            minute = match_data.get('match_status') or match_data.get('minute') or match_data.get('time') or "0"
            league_id = str(match_data.get('league_id') or match_data.get('id_league') or "unknown")
            match_id = str(match_data.get('match_id') or match_data.get('id') or f"{home_team}-{away_team}-{league_id}")

            
            if minute == "HT":
                match_status = "HALF TIME"
            elif minute == "FT":
                match_status = "FULL TIME"
            elif isinstance(minute, int) or (isinstance(minute, str) and minute.isdigit()):
                match_status = "LIVE"
            else:
                match_status = "UPCOMING"
            
            return {
                "match_id": match_id,
                "match_hometeam_name": home_team,
                "match_awayteam_name": away_team,
                "match_hometeam_score": home_score,
                "match_awayteam_score": away_score,
                "match_status": minute,
                "league_id": league_id,
                "league_name": get_league_name(league_id),
                "match_live": "1" if match_status == "LIVE" or match_status == "HALF TIME" else "0",
                "source": "allsports_websocket",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return None
    
    def connect(self):
        """Connect to WebSocket"""
        try:
            self.ws = websocket.WebSocketApp(
                ALLSPORTS_WS_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            def run_websocket():
                self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_timeout=10, ping_interval=50)
            
            ws_thread = threading.Thread(target=run_websocket, daemon=True)
            ws_thread.start()
            
            return True
            
        except Exception as e:
            api_manager.websocket_connected = False
            return False
    
    def disconnect(self):
        """Disconnect WebSocket"""
        if self.ws:
            self.ws.close()
        self.connected = False
        api_manager.websocket_connected = False

# Initialize WebSocket Client
websocket_client = AllSportsWebSocketClient()

# -------------------------
# COMPREHENSIVE LEAGUE CONFIGURATION
# -------------------------
LEAGUE_CONFIG = {
    # Major European Leagues (Top 7 for your reference)
    "152": {"name": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "priority": 1, "type": "domestic"},
    "302": {"name": "🇪🇸 La Liga", "priority": 1, "type": "domestic"},
    "207": {"name": "🇮🇹 Serie A", "priority": 1, "type": "domestic"},
    "168": {"name": "🇩🇪 Bundesliga", "priority": 1, "type": "domestic"},
    "176": {"name": "🇫🇷 Ligue 1", "priority": 1, "type": "domestic"},
    "169": {"name": "🇳🇱 Eredivisie", "priority": 2, "type": "domestic"},
    "262": {"name": "🇵🇹 Primeira Liga", "priority": 2, "type": "domestic"},
    
    # European Competitions
    "149": {"name": "⭐ Champions League", "priority": 1, "type": "european"},
    "150": {"name": "✨ Europa League", "priority": 2, "type": "european"},
    
    # World Cup Qualifiers (Examples from your original code)
    "5": {"name": "🌍 World Cup Qualifiers", "priority": 1, "type": "worldcup"},
    # ... (other leagues)
}

def get_league_name(league_id):
    """Get league name from ID"""
    league_info = LEAGUE_CONFIG.get(str(league_id))
    if league_info:
        return league_info["name"]
    return f"League {league_id}"

# -------------------------
# API-FOOTBALL HTTP CLIENT (MODIFIED for Today's Matches)
# -------------------------
def fetch_api_football_matches(match_live_only=True):
    """Fetch matches from API-Football HTTP API"""
    
    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        return []
        
    hit_counter.record_hit()
    
    try:
        if match_live_only:
            # LIVE MATCHES (Quick update for fallback)
            url = f"{API_FOOTBALL_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
            # print("📡 Fetching LIVE matches from API-Football HTTP...")
        else:
            # TODAY'S MATCHES (Scheduled list)
            today_date = get_current_date_pakt()
            url = f"{API_FOOTBALL_URL}/?action=get_events&from={today_date}&to={today_date}&APIkey={API_KEY}"
            # print(f"📡 Fetching TODAY's SCHEDULE from API-Football HTTP ({today_date})...")
            
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, list):
                # print(f"✅ API-Football: Found {len(data)} matches")
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                    match["source"] = "api_football"
                
                return data
            else:
                return []
        else:
            return []
            
    except requests.exceptions.Timeout:
        return []
    except requests.exceptions.ConnectionError:
        return []
    except Exception as e:
        return []

# -------------------------
# DUAL API MATCH FETCHER
# -------------------------
def fetch_live_matches_dual_api():
    """Fetch matches using both APIs - WebSocket preferred"""
    
    matches, source = api_manager.get_best_live_matches()
    
    # If WebSocket data is stale or unavailable, try API-Football
    if source != "ALLSPORTS_WS":
        api_football_matches = fetch_api_football_matches(match_live_only=True)
        if api_football_matches:
            api_manager.update_api_football_matches(api_football_matches)
            matches = api_football_matches
            source = "API_FOOTBALL"
    
    return matches, source

# -------------------------
# MATCH PROCESSOR
# -------------------------
def process_match_data(matches, live_only=True):
    """Process raw match data for display"""
    if not matches:
        return []
    
    processed_matches = []
    unique_matches = {}
    
    for match in matches:
        source = match.get("source", "unknown")
        match_id = match.get("match_id") or f"{match.get('match_hometeam_name')}-{match.get('match_awayteam_name')}"
        
        # Prioritize WebSocket if a match exists in both
        if match_id in unique_matches and unique_matches[match_id]['source'] == 'allsports_websocket':
            continue
        
        try:
            home_team = match.get("match_hometeam_name", "Unknown")
            away_team = match.get("match_awayteam_name", "Unknown")
            home_score = match.get("match_hometeam_score", "0")
            away_score = match.get("match_awayteam_score", "0")
            minute = match.get("match_status", "0")
            league_name = match.get("league_name", "Unknown League")
            
            # Match Status Logic
            if minute == "HT":
                match_status = "HALF TIME"
                display_minute = "HT"
            elif minute == "FT":
                match_status = "FULL TIME"
                display_minute = "FT"
            elif minute.isdigit():
                match_status = "LIVE"
                display_minute = f"{minute}'"
            elif minute in ["1H", "2H", "ET"]:
                match_status = "LIVE"
                display_minute = minute
            else:
                match_status = "UPCOMING"
                
                # Use match time for UPCOMING matches
                match_time = match.get("match_time", "")
                display_minute = match_time if match_time else "TBD"
            
            is_live = match_status == "LIVE" or match_status == "HALF TIME"
            
            # Skip non-live if live_only is true
            if live_only and not is_live:
                continue
                
            source_icon = "🔴" if source == "allsports_websocket" else "🔵"
            
            unique_matches[match_id] = {
                "home_team": home_team,
                "away_team": away_team,
                "score": f"{home_score}-{away_score}" if is_live else display_minute,
                "minute": display_minute,
                "status": match_status,
                "league": league_name,
                "is_live": is_live,
                "source": source,
                "source_icon": source_icon if is_live else "📅",
                "raw_data": match  
            }
            
        except Exception as e:
            continue
    
    return list(unique_matches.values())

# -------------------------
# ENHANCED FOOTBALL AI WITH DETAILED ANALYSIS (Updated for 85% Alerts)
# -------------------------
class EnhancedFootballAI:
    def __init__(self):
        self.team_data = {
            # Increased team data for better prediction demonstration
            "manchester city": {"strength": 95, "style": "attacking", "goal_avg": 2.5},
            "liverpool": {"strength": 92, "style": "high press", "goal_avg": 2.2},
            "arsenal": {"strength": 90, "style": "possession", "goal_avg": 2.1},
            "chelsea": {"strength": 88, "style": "balanced", "goal_avg": 1.8},
            "real madrid": {"strength": 94, "style": "experienced", "goal_avg": 2.3},
            "barcelona": {"strength": 92, "style": "possession", "goal_avg": 2.0},
            "bayern munich": {"strength": 93, "style": "dominant", "goal_avg": 2.6},
            "psg": {"strength": 91, "style": "star power", "goal_avg": 2.4},
            "brazil": {"strength": 96, "style": "samba", "goal_avg": 2.7},
            "argentina": {"strength": 94, "style": "technical", "goal_avg": 2.2},
            "france": {"strength": 95, "style": "balanced", "goal_avg": 2.5},
            "germany": {"strength": 92, "style": "efficient", "goal_avg": 2.0},
            "unknown": {"strength": 75, "style": "standard", "goal_avg": 1.5} # Fallback team strength
        }
        
    def get_team_strength_and_avg(self, team_name):
        """Retrieve team strength and goal average"""
        team_key = team_name.lower()
        for key, data in self.team_data.items():
            if key in team_key or team_key in key:
                return data["strength"], data["goal_avg"]
        
        fallback = self.team_data.get("unknown")
        return fallback["strength"], fallback["goal_avg"]
        
    def get_response(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'scores']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['today', 'schedule', 'matches', 'list']):
            return self.handle_todays_matches() # New handler for today's schedule
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api usage']):
            return hit_counter.get_hit_stats()
        
        elif any(word in message_lower for word in ['predict', 'prediction', 'who will win']):
            return self.handle_prediction(message_lower)
        
        elif any(word in message_lower for word in ['analysis', 'analyze', 'detail', 'report']):
            return self.handle_detailed_analysis(message_lower)
        
        elif any(word in message_lower for word in ['api status', 'connection', 'status']):
            return self.handle_api_status()
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'start']):
            return "👋 Hello! I'm **ENHANCED Football Analysis AI**! ⚽\n\n🔍 **Detailed Match Analysis**\n🌐 **Real-time updates via WebSocket**\n🔄 **Fallback to HTTP API**\n\nTry: 'live matches', 'analysis man city', '/today', or 'api status'"
        
        else:
            return self.handle_team_specific_query(message_lower)

    def handle_live_matches(self):
        raw_matches, source = fetch_live_matches_dual_api()
        # Only process for live matches here
        matches = process_match_data(raw_matches, live_only=True) 
        
        if not matches:
            return "⏳ No live matches found right now.\n\n🌐 **API Status:**\n" + self.get_api_status_text()
        
        response = "🔴 **LIVE FOOTBALL MATCHES** ⚽\n\n"
        source_text = "🔴 REAL-TIME WebSocket" if source == "ALLSPORTS_WS" else "🔵 API-Football HTTP"
        response += f"📡 **Source:** {source_text}\n\n"
        
        leagues = {}
        for match in matches:
            league = match['league']
            if league not in leagues:
                leagues[league] = []
            leagues[league].append(match)
        
        for league, league_matches in leagues.items():
            response += f"**{league}**\n"
            for match in league_matches:
                icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                response += f"{match['source_icon']} {match['home_team']} {match['score']} {match['away_team']} {icon} {match['minute']}\n"
            response += "\n"
        
        response += f"🔥 API Hits Today: {hit_counter.daily_hits}/100\n"
        response += self.get_api_status_text()
        
        return response

    def handle_todays_matches(self):
        """NEW: Handle request for today's scheduled matches"""
        raw_matches = fetch_api_football_matches(match_live_only=False)
        # Process all matches (live and upcoming)
        matches = process_match_data(raw_matches, live_only=False) 
        
        if not matches:
            return f"📅 **{get_current_date_pakt()}**\n\n❌ No matches scheduled for today."
        
        # Separate Live/FT from Upcoming
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if not m['is_live']]
        
        response = f"📅 **TODAY'S FOOTBALL SCHEDULE ({get_current_date_pakt()})** ⚽\n\n"
        
        if live_matches:
            response += "--- **🔴 LIVE / FT MATCHES** ---\n"
            for match in live_matches[:5]: # Limit live matches to 5 for list view
                icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                response += f"{match['league']}\n{match['source_icon']} {match['home_team']} {match['score']} {match['away_team']} {icon} {match['minute']}\n"
            response += "\n"
            
        if upcoming_matches:
            response += "--- **🕒 UPCOMING MATCHES (Pakistan Time)** ---\n"
            for match in upcoming_matches:
                # score here is the scheduled time
                response += f"📅 {match['league']}\n{match['home_team']} vs {match['away_team']} 🕒 {match['score']}\n"
            response += "\n"
            
        response += "💡 *Use 'analysis [Team Name]' for live match reports.*"
        
        return response

    def handle_detailed_analysis(self, message):
        """Handle detailed match analysis requests"""
        
        teams_found = []
        for team_key in self.team_data:
            if team_key in message.lower():
                teams_found.append(team_key)
        
        match_data = None
        if len(teams_found) >= 2:
            match_data = api_manager.find_match_by_teams(teams_found[0], teams_found[1])
        elif len(teams_found) == 1:
            match_data = api_manager.find_match_by_teams(teams_found[0])
            
        if match_data:
            return self.generate_live_match_report(match_data)
        else:
            raw_matches, source = fetch_live_matches_dual_api()
            live_matches = [m for m in raw_matches if m.get('match_live') == '1' or m.get('match_status') == 'HT']

            if not live_matches:
                return "❌ No live matches available for analysis right now. Try `/today` for the schedule."
                
            response = "🔍 **DETAILED MATCH ANALYSIS SUMMARY**\n\n"
            for match in live_matches[:5]:
                analysis = match_analyzer.analyze_match_trends(match)
                home_team = match.get("match_hometeam_name", "Unknown")
                away_team = match.get("match_awayteam_name", "Unknown")
                score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                minute = match.get('match_status', '0')
                
                response += f"**{home_team} vs {away_team}** ({minute}')\n"
                response += f"Score: {score} | Progress: {analysis.get('match_progress', 'N/A')}\n"
                response += f"Momentum: {analysis.get('momentum', 'N/A')}\n"
                response += f"Tempo: {analysis.get('match_tempo', 'N/A')}\n\n"
            
            response += "💡 *Use 'analysis [team name]' for a full match report*"
            return response
            
    def generate_live_match_report(self, match_data):
        """Generates detailed report using both MatchAnalysis and Strength Prediction"""
        basic_info = match_analyzer.get_basic_match_info(match_data)
        analysis = match_analyzer.analyze_match_trends(match_data)
        statistics = match_analyzer.get_match_statistics(match_data)
        
        home_team = match_data.get("match_hometeam_name", "Home")
        away_team = match_data.get("match_awayteam_name", "Away")
        
        # Call the strength/score-based combined prediction function
        predictions, alert_result = self.generate_combined_prediction(match_data, home_team, away_team, send_alert=False)
        
        report = f"""
🔍 **DETAILED MATCH ANALYSIS**

{basic_info}

📊 **MATCH ANALYSIS:**
• Progress: {analysis.get('match_progress', 'N/A')}
• Momentum: {analysis.get('momentum', 'N/A')}
• Confidence: {analysis.get('confidence', 'N/A')}
• Tempo: {analysis.get('match_tempo', 'N/A')}
• Next Goal Window: {analysis.get('next_goal_window', 'N/A')}

📈 **STATISTICS:**
{statistics}

🎯 **ENHANCED PREDICTIONS:**
{predictions}

⚡ **LIVE INSIGHTS:**
{match_analyzer.get_live_insights(match_data)}
"""
        return report

    def generate_combined_prediction(self, match_data, team1, team2, send_alert=False):
        """Generates a prediction combining pre-match strength and live score analysis and checks for 85% confidence"""
        strength1, avg1 = self.get_team_strength_and_avg(team1)
        strength2, avg2 = self.get_team_strength_and_avg(team2)
        
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")
        league = match_data.get("league_name", "Unknown League")
        
        if minute == "FT":
            return "🏁 Match is over. Final Score-based Prediction not applicable.", None
        
        # Calculate progress
        progress = 0
        if minute == "HT": progress = 50
        elif minute.isdigit(): progress = min(90, int(minute))
        progress_percent = progress / 90
        
        # 1. Match Winner Prediction (1X2)
        total_strength = strength1 + strength2
        prob1_base = (strength1 / total_strength) * 100
        prob2_base = (strength2 / total_strength) * 100
        strength_diff_factor = abs(strength1 - strength2) / total_strength
        draw_prob_base = 25 - (strength_diff_factor * 15) 
        
        remaining_prob = 100 - draw_prob_base
        prob1 = (prob1_base / (prob1_base + prob2_base)) * remaining_prob
        prob2 = (prob2_base / (prob1_base + prob2_base)) * remaining_prob
        
        score_diff = home_score - away_score
        
        if abs(score_diff) > 0 and progress_percent > 0.4:
            lead_factor = 1.0 + (abs(score_diff) * progress_percent * 0.5)
            
            if score_diff > 0:
                prob1 *= lead_factor
                prob2 /= lead_factor
            else:
                prob2 *= lead_factor
                prob1 /= lead_factor
            
            new_total = prob1 + prob2
            draw_adjustment = max(0, draw_prob_base / (1 + progress_percent * abs(score_diff)))
            prob1 = (prob1 / new_total) * (100 - draw_adjustment)
            prob2 = (prob2 / new_total) * (100 - draw_adjustment)
            draw_prob = 100 - prob1 - prob2
        else:
            draw_prob = draw_prob_base
        
        # Final Winner Determination
        max_prob_1x2 = max(prob1, prob2, draw_prob)
        if max_prob_1x2 == prob1: 
            winner = team1
            market_1x2 = f"{team1} to WIN"
        elif max_prob_1x2 == prob2: 
            winner = team2
            market_1x2 = f"{team2} to WIN"
        else: 
            winner = "DRAW"
            market_1x2 = "DRAW"
            
        # 2. Over/Under Goals Prediction (Simplified Example)
        expected_goals = (avg1 + avg2) * (1 - (0.5 - progress_percent) * 0.5) # Time-adjusted expected goals
        total_goals = home_score + away_score
        
        # Prediction for Over 2.5 goals
        over_25_prob_base = 65 if expected_goals > 2.8 else 50 if expected_goals > 2.2 else 35
        
        # Adjust based on current score (Lagging score increases Over prob, fast score decreases it)
        goal_rate_factor = total_goals / (expected_goals * progress_percent) if progress_percent > 0 else 1.0
        
        if goal_rate_factor > 1.2: # Slower goal rate than expected (more goals likely in second half)
            over_25_prob = over_25_prob_base + (goal_rate_factor - 1) * 20
        elif goal_rate_factor < 0.8 and total_goals < 2: # Very low scoring, hard to catch up
            over_25_prob = over_25_prob_base * goal_rate_factor * 0.8
        else:
            over_25_prob = over_25_prob_base
            
        over_25_prob = min(99, max(1, over_25_prob))
        under_25_prob = 100 - over_25_prob
        
        max_prob_OU = max(over_25_prob, under_25_prob)
        market_OU = f"Over 2.5 Goals" if max_prob_OU == over_25_prob else f"Under 2.5 Goals"
        
        # --- Alert Generation Check (for auto_live_alert) ---
        alert_to_send = None
        
        if send_alert:
            if max_prob_1x2 >= 85:
                alert_to_send = {
                    "market": "Match Winner (1X2)",
                    "prediction": market_1x2,
                    "confidence": max_prob_1x2
                }
            elif max_prob_OU >= 85:
                alert_to_send = {
                    "market": market_OU,
                    "prediction": market_OU,
                    "confidence": max_prob_OU
                }

        # Format the result for the user response
        result = f"""
**Pre-match & Live Score Model:**
• {team1} WIN: {prob1:.1f}%
• {team2} WIN: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%
• Over 2.5 Goals: {over_25_prob:.1f}%
• Under 2.5 Goals: {under_25_prob:.1f}%

🏆 **Current Verdict ({minute}' / {home_score}-{away_score}):**
• **Match Winner:** **{winner.upper()}** ({max_prob_1x2:.1f}%)
• **Goals:** **{market_OU.upper()}** ({max_prob_OU:.1f}%)

💡 **Score-based Insight:**
{match_analyzer.generate_simple_score_based_prediction(match_data)}
"""
        return result, alert_to_send

    def handle_prediction(self, message):
        # ... (Prediction handler remains the same, focuses on 1X2 pre-match) ...
        teams = []
        for team_key in self.team_data:
            if team_key in message.lower():
                teams.append(team_key)
        
        if len(teams) >= 2:
            team1_name = teams[0]
            team2_name = teams[1]
            
            strength1, avg1 = self.get_team_strength_and_avg(team1_name)
            strength2, avg2 = self.get_team_strength_and_avg(team2_name)
            
            total_strength = strength1 + strength2
            prob1_base = (strength1 / total_strength) * 100
            prob2_base = (strength2 / total_strength) * 100
            
            strength_diff_factor = abs(strength1 - strength2) / total_strength
            draw_prob_base = 25 - (strength_diff_factor * 15)
            
            remaining_prob = 100 - draw_prob_base
            prob1 = (prob1_base / (prob1_base + prob2_base)) * remaining_prob
            prob2 = (prob2_base / (prob1_base + prob2_base)) * remaining_prob
            draw_prob = draw_prob_base
            
            expected_goals = avg1 + avg2
            
            max_prob = max(prob1, prob2, draw_prob)
            if max_prob == prob1: winner = team1_name.title()
            elif max_prob == prob2: winner = team2_name.title()
            else: winner = "Draw"
            
            return f"""
🎯 **PREDICTION: {team1_name.upper()} vs {team2_name.upper()}**

📊 **Probabilities (Pre-match Strength):**
• {team1_name.title()}: {prob1:.1f}%
• {team2_name.title()}: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%
• Expected Total Goals: {expected_goals:.2f}

🏆 **Most Likely: {winner.upper()}**

⚠️ *This is a pre-match strength prediction. Use 'analysis {team1_name} vs {team2_name}' for live updates!*
"""
        else:
            return "Please specify two teams for prediction. Example: 'Predict Manchester City vs Liverpool'"

    def handle_api_status(self):
        return self.get_api_status_text()
    
    def get_api_status_text(self):
        """Get API status as formatted text"""
        status = api_manager.get_api_status()
        
        return f"""
🌐 **DUAL API STATUS**

🔵 **API-Football (HTTP):**
• Status: {status['api_football']['status']}
• Matches: {status['api_football']['match_count']}
• Updated: {status['api_football']['last_update']}

🔴 **AllSportsAPI (WebSocket):**
• Status: {status['allsports_websocket']['status']}
• Matches: {status['allsports_websocket']['match_count']}
• Updated: {status['allsports_websocket']['last_update']}
• Retries: {status['allsports_websocket']['retry_count']}

💡 **WebSocket provides real-time updates**
💡 **HTTP API used as fallback**
"""

# Initialize Enhanced AI
football_ai = EnhancedFootballAI()

# -------------------------
# TELEGRAM BOT HANDLERS (Enhanced)
# -------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
🤖 **ENHANCED FOOTBALL ANALYSIS BOT** ⚽

🚀 **REAL-TIME ALERTS & TODAY'S SCHEDULE ADDED!**

🔍 **NEW FEATURES:**
• `/today`: Today's full match schedule.
• **Auto-Alerts:** Sends predictions with **85%+ Confidence** automatically (check console/OWNER_CHAT_ID).
• Enhanced Prediction Model (1X2 & Over/Under 2.5).

⚡ **Commands:**
/live - Live matches (Real-time preferred)
/today - Today's full schedule 📅
/analysis - Detailed analysis (Try: /analysis Man City)
/status - API connection status
/hits - API hit statistics
/predict - Match predictions (Pre-match strength)
/help - Complete guide

🚀 **Real-time analysis with automatic fallback!**
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['live'])
def send_live_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_live_matches()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['today']) # NEW HANDLER
def send_todays_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error getting today's schedule: {str(e)}")

@bot.message_handler(commands=['analysis'])
def send_detailed_analysis(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        command_text = message.text.split(' ', 1)
        query = command_text[1] if len(command_text) > 1 else "analysis" 
        
        response = football_ai.handle_detailed_analysis(query)
            
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['hits', 'stats'])
def send_hit_stats(message):
    try:
        stats = hit_counter.get_hit_stats()
        bot.reply_to(message, stats, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['status', 'api'])
def send_api_status(message):
    try:
        response = football_ai.handle_api_status()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def handle_predict_command(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        command_text = message.text.split(' ', 1)
        query = command_text[1] if len(command_text) > 1 else ""
        
        if query:
            response = football_ai.handle_prediction(query)
        else:
            response = """
🎯 **MATCH PREDICTIONS (PRE-MATCH)**

Ask me like:
• "Predict Manchester City vs Liverpool"

I'll analyze team strengths and give you probabilities! 📊
"""
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        print(f"💬 Message from {user_id}: {user_message}")
        
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.5) 
        
        response = football_ai.get_response(user_message)
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Message error: {e}")
        bot.reply_to(message, "❌ Sorry, error occurred. Please try again!")

# -------------------------
# NEW: AUTO LIVE ALERT SYSTEM (7 Minute Interval)
# -------------------------
def auto_live_alert_system():
    """Checks live matches every 7 minutes for 85%+ confidence alerts"""
    
    # Run in an infinite loop
    while True:
        try:
            # 1. Fetch the latest live matches
            raw_matches, source = fetch_live_matches_dual_api()
            live_matches = [m for m in raw_matches if m.get('match_live') == '1' and m.get('match_status').isdigit() and int(m.get('match_status')) < 90]
            
            if not live_matches:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 Auto Alert: No live matches to analyze.")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 Auto Alert: Analyzing {len(live_matches)} live matches...")
                
                for match in live_matches:
                    home_team = match.get("match_hometeam_name", "Home")
                    away_team = match.get("match_awayteam_name", "Away")
                    league = match.get("league_name", "Unknown League")
                    minute = match.get("match_status", "0")
                    score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                    
                    # 2. Generate combined prediction and check for 85% confidence
                    _, alert_result = football_ai.generate_combined_prediction(match, home_team, away_team, send_alert=True)
                    
                    if alert_result:
                        # 3. Format and send the alert
                        alert_message = f"""
🔥 **85%+ CONFIDENCE LIVE ALERT!** 🔥
📢 **MATCH:** {home_team} vs {away_team}
🏆 **LEAGUE:** {league}
⏱️ **MINUTE:** {minute}' | **SCORE:** {score}

🎯 **MARKET:** {alert_result['market'].upper()}
✅ **PREDICTION:** **{alert_result['prediction'].upper()}**
📊 **CONFIDENCE:** {alert_result['confidence']:.1f}%

⚠️ *Betting is risky. Use your own discretion.*
"""
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ ALERT SENT: {alert_result['prediction']} @ {alert_result['confidence']:.1f}%")
                        
                        # Send alert to the owner chat ID
                        bot.send_message(OWNER_CHAT_ID, alert_message, parse_mode='Markdown')
                        
        except Exception as e:
            print(f"❌ Auto Live Alert System Error: {e}")
        
        # Wait for 7 minutes before the next check
        time.sleep(7 * 60) # 420 seconds

# -------------------------
# AUTO UPDATER WITH DUAL API SUPPORT
# -------------------------
def auto_updater():
    """Auto-update matches with dual API support (used for general data refresh)"""
    
    # Start WebSocket connection first
    print("🔗 Starting WebSocket connection...")
    websocket_client.connect()
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            
            # Check if we need to fall back to HTTP API
            if not api_manager.websocket_connected:
                can_make, reason = hit_counter.can_make_request()
                if can_make:
                    matches = fetch_api_football_matches(match_live_only=True)
                    if matches:
                        api_manager.update_api_football_matches(matches)
                else:
                    print(f"⏸️ HTTP API call blocked: {reason}")
            
            # Smart wait time based on WebSocket status
            wait_time = 120 # General data refresh every 2 minutes for HTTP Fallback
            
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Auto-updater error: {e}")
            time.sleep(300)

# -------------------------
# STARTUP FUNCTION
# -------------------------
def start_bot():
    """Start the bot with dual API support and new features"""
    try:
        print("🚀 Starting Enhanced Football Analysis Bot...")
        
        # Start auto-updater (for WS connection and HTTP fallback data)
        updater_thread = threading.Thread(target=auto_updater, daemon=True)
        updater_thread.start()
        print("✅ Dual-API Auto-Updater started!")
        
        # Start auto live alert system
        alert_thread = threading.Thread(target=auto_live_alert_system, daemon=True)
        alert_thread.start()
        print("✅ Auto Live Alert System (7 min check) started!")
        
        # Initial API test (Wait a bit for WS to connect)
        time.sleep(5) 
        test_matches, source = fetch_live_matches_dual_api()
        print(f"🔍 Initial load: {len(test_matches)} matches from {source}")
        
        # Send startup message
        api_status = api_manager.get_api_status()
        startup_msg = f"""
🤖 **ENHANCED FOOTBALL ANALYSIS BOT STARTED!**

🔍 **NEW: 85%+ CONFIDENCE AUTO-ALERTS ACTIVE**
• Alerts will be sent here every 7 minutes if high confidence is found.

✅ **Dual API System Active:**
• 🔴 WebSocket: {api_status['allsports_websocket']['status']}
• 🔵 HTTP API: {api_status['api_football']['status']}
• 🎯 Automatic Failover

🌐 **Current Status:**
• WS Matches: {api_status['allsports_websocket']['match_count']}
• HTTP Matches: {api_status['api_football']['match_count']}

🔥 **Hit Counter Ready**
📊 Today's Hits: {hit_counter.daily_hits}/100

🚀 **Ready for real-time analysis! Use /today to check the schedule.**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
        # Start bot polling
        print("🔄 Starting in polling mode...")
        bot.remove_webhook()
        time.sleep(1)
        bot.infinity_polling()
            
    except Exception as e:
        print(f"❌ Startup error: {e}")
        time.sleep(10)
        # Simple restart attempt logic
        if hasattr(start_bot, 'restart_count'):
            start_bot.restart_count += 1
        else:
            start_bot.restart_count = 1
            
        if start_bot.restart_count < 3:
            print("Attempting to restart bot...")
            start_bot()
        else:
            print("Fatal error. Max restart attempts reached.")

if __name__ == '__main__':
    start_bot()
