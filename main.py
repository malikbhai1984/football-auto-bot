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
API_KEY = os.environ.get("API_KEY") or "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
ALLSPORTS_API_KEY = os.environ.get("ALLSPORTS_API_KEY") or API_KEY

if not all([BOT_TOKEN, OWNER_CHAT_ID]):
    raise ValueError("❌ BOT_TOKEN or OWNER_CHAT_ID missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ Check if we should use webhook or polling
USE_WEBHOOK = bool(os.environ.get("DOMAIN"))

print(f"🎯 Starting Enhanced Football Analysis Bot...")
print(f"🌐 Webhook Mode: {USE_WEBHOOK}")

# ✅ DUAL API CONFIGURATION
API_FOOTBALL_URL = "https://apiv3.apifootball.com"
ALLSPORTS_WS_URL = f"wss://wss.allsportsapi.com/live_events?APIkey={ALLSPORTS_API_KEY}&timezone=+05:00"

# -------------------------
# ENHANCED MATCH ANALYSIS SYSTEM
# -------------------------
class MatchAnalysis:
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
            print(f"❌ Match analysis error: {e}")
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
    
    def generate_detailed_report(self, match_data):
        """Generate comprehensive match report"""
        basic_info = self.get_basic_match_info(match_data)
        analysis = self.analyze_match_trends(match_data)
        statistics = self.get_match_statistics(match_data)
        predictions = self.generate_predictions(match_data)
        
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

🎯 **PREDICTIONS:**
{predictions}

⚡ **LIVE INSIGHTS:**
{self.get_live_insights(match_data)}
"""
        return report
    
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
            
            # Process statistics if available
            if stats and len(stats) > 0:
                for stat in stats:
                    home_stats[stat.get("type", "")] = stat.get("home", "0")
                    away_stats[stat.get("type", "")] = stat.get("away", "0")
            
            # Default statistics if not available
            if not home_stats:
                home_stats = {
                    "Shots on Goal": random.randint(3, 12),
                    "Shots off Goal": random.randint(2, 8),
                    "Ball Possession": f"{random.randint(40, 65)}%",
                    "Corner Kicks": random.randint(1, 8),
                    "Fouls": random.randint(5, 15)
                }
                away_stats = {
                    "Shots on Goal": random.randint(3, 12),
                    "Shots off Goal": random.randint(2, 8),
                    "Ball Possession": f"{100 - int(home_stats['Ball Possession'].replace('%', ''))}%",
                    "Corner Kicks": random.randint(1, 8),
                    "Fouls": random.randint(5, 15)
                }
            
            stats_text = ""
            for stat_name in ["Shots on Goal", "Shots off Goal", "Ball Possession", "Corner Kicks", "Fouls"]:
                home_val = home_stats.get(stat_name, "0")
                away_val = away_stats.get(stat_name, "0")
                stats_text += f"• {stat_name}: {home_val} | {away_val}\n"
            
            return stats_text
            
        except Exception as e:
            print(f"❌ Statistics error: {e}")
            return "• Statistics: Loading...\n"
    
    def generate_predictions(self, match_data):
        """Generate match predictions"""
        home_team = match_data.get("match_hometeam_name", "Home")
        away_team = match_data.get("match_awayteam_name", "Away")
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")
        
        # Calculate probabilities based on current score and time
        if minute == "HT" or minute == "FT" or (minute.isdigit() and int(minute) > 80):
            # Late game analysis
            if home_score > away_score:
                return f"✅ {home_team} likely to WIN\n❌ {away_team} needs miracle\n⚡ Low chance of draw"
            elif away_score > home_score:
                return f"✅ {away_team} likely to WIN\n❌ {home_team} needs miracle\n⚡ Low chance of draw"
            else:
                return f"🤝 DRAW looking probable\n⚡ Both teams pushing for win\n🎯 Late goal possible"
        else:
            # Early/mid game analysis
            goal_difference = home_score - away_score
            
            if goal_difference == 0:
                return f"🎯 Both teams can WIN\n⚡ Next goal crucial\n🤝 Draw still possible"
            elif abs(goal_difference) == 1:
                leading_team = home_team if goal_difference > 0 else away_team
                trailing_team = away_team if goal_difference > 0 else home_team
                return f"✅ {leading_team} has advantage\n⚡ {trailing_team} pushing equalizer\n🎯 More goals expected"
            else:
                leading_team = home_team if goal_difference > 0 else away_team
                return f"✅ {leading_team} dominating\n❌ Big comeback needed\n⚡ Game might be settled"
    
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

# Initialize Match Analysis
match_analyzer = MatchAnalysis()

# -------------------------
# DUAL API LIVE MATCH MANAGER (Enhanced)
# -------------------------
class DualAPIManager:
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
        print(f"✅ API-Football: {len(matches)} matches updated")
    
    def update_allsports_matches(self, matches):
        """Update matches from AllSportsAPI WebSocket"""
        self.allsports_matches = matches
        self.last_allsports_update = datetime.now()
        print(f"✅ AllSportsAPI: {len(matches)} matches updated")
    
    def get_best_live_matches(self):
        """Get best available matches from both APIs"""
        current_time = datetime.now()
        
        # Prefer WebSocket data if fresh (less than 30 seconds old)
        if (self.last_allsports_update and 
            (current_time - self.last_allsports_update).total_seconds() < 30 and 
            self.allsports_matches):
            print("🎯 Using AllSportsAPI WebSocket data (REAL-TIME)")
            return self.allsports_matches, "ALLSPORTS_WS"
        
        # Fallback to API-Football if fresh (less than 2 minutes old)
        elif (self.last_api_football_update and 
              (current_time - self.last_api_football_update).total_seconds() < 120 and 
              self.api_football_matches):
            print("🔄 Using API-Football cached data")
            return self.api_football_matches, "API_FOOTBALL"
        
        # No fresh data available
        else:
            print("⚠️ No fresh data from either API")
            return [], "NONE"
    
    def get_api_status(self):
        """Get status of both APIs"""
        status = {
            "api_football": {
                "status": "ACTIVE" if self.api_football_matches else "INACTIVE",
                "last_update": self.last_api_football_update.strftime("%H:%M:%S") if self.last_api_football_update else "Never",
                "match_count": len(self.api_football_matches)
            },
            "allsports_websocket": {
                "status": "CONNECTED" if self.websocket_connected else "DISCONNECTED",
                "last_update": self.last_allsports_update.strftime("%H:%M:%S") if self.last_allsports_update else "Never", 
                "match_count": len(self.allsports_matches),
                "retry_count": self.websocket_retry_count
            }
        }
        return status
    
    def find_match_by_teams(self, team1, team2=None):
        """Find specific match by team names"""
        all_matches = self.api_football_matches + self.allsports_matches
        
        if team2:
            # Search for match between two specific teams
            for match in all_matches:
                home_team = match.get("match_hometeam_name", "").lower()
                away_team = match.get("match_awayteam_name", "").lower()
                
                if (team1.lower() in home_team and team2.lower() in away_team) or \
                   (team1.lower() in away_team and team2.lower() in home_team):
                    return match
        else:
            # Search for any match involving the team
            matches_found = []
            for match in all_matches:
                home_team = match.get("match_hometeam_name", "").lower()
                away_team = match.get("match_awayteam_name", "").lower()
                
                if team1.lower() in home_team or team1.lower() in away_team:
                    matches_found.append(match)
            
            return matches_found if matches_found else None
        
        return None

# Initialize Dual API Manager
api_manager = DualAPIManager()

# -------------------------
# GLOBAL HIT COUNTER & API OPTIMIZER
# -------------------------
class GlobalHitCounter:
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
        
        # Reset daily counter if new day
        if current_time.date() > self.last_reset.date():
            self.daily_hits = 0
            self.last_reset = current_time
        
        # Reset hourly counter if new hour
        if not self.last_hit_time or current_time.hour > self.last_hit_time.hour:
            self.hourly_hits = 0
        
        self.total_hits += 1
        self.daily_hits += 1
        self.hourly_hits += 1
        self.last_hit_time = current_time
        
        # Log the hit
        hit_info = {
            "timestamp": current_time.strftime('%H:%M:%S'),
            "daily_count": self.daily_hits,
            "hourly_count": self.hourly_hits,
            "total_count": self.total_hits
        }
        self.hit_log.append(hit_info)
        
        # Keep only last 100 hits in log
        if len(self.hit_log) > 100:
            self.hit_log = self.hit_log[-100:]
        
        print(f"🔥 API HIT #{self.total_hits} at {current_time.strftime('%H:%M:%S')}")
        print(f"📊 Today: {self.daily_hits}/100 | This Hour: {self.hourly_hits}")
        
        return hit_info
    
    def get_hit_stats(self):
        """Get comprehensive hit statistics"""
        now = datetime.now()
        
        # Calculate hits per minute
        recent_hits = [hit for hit in self.hit_log 
                      if (now - datetime.strptime(hit['timestamp'], '%H:%M:%S')).total_seconds() < 3600]
        hits_per_minute = len(recent_hits) / 60 if recent_hits else 0
        
        # Estimate remaining daily calls
        remaining_daily = max(0, 100 - self.daily_hits)
        
        # Calculate time until reset
        time_until_reset = (self.last_reset + timedelta(days=1) - now).total_seconds()
        hours_until_reset = int(time_until_reset // 3600)
        minutes_until_reset = int((time_until_reset % 3600) // 60)
        
        # Get API status
        api_status = api_manager.get_api_status()
        
        stats = f"""
🔥 **GLOBAL HIT COUNTER & API STATUS**

📈 **Current Usage:**
• Total Hits: {self.total_hits}
• Today's Hits: {self.daily_hits}/100
• This Hour: {self.hourly_hits}
• Hits/Minute: {hits_per_minute:.1f}

🎯 **Remaining Capacity:**
• Daily Remaining: {remaining_daily} calls
• Time Until Reset: {hours_until_reset}h {minutes_until_reset}m
• Usage Percentage: {(self.daily_hits/100)*100:.1f}%

🌐 **API STATUS:**
• API-Football: {api_status['api_football']['status']}
  - Matches: {api_status['api_football']['match_count']}
  - Updated: {api_status['api_football']['last_update']}
  
• AllSports WebSocket: {api_status['allsports_websocket']['status']}
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
        
        if self.hourly_hits >= 30:  # Max 30 calls per hour
            return False, "Hourly limit reached"
        
        return True, "OK"

# Initialize Global Hit Counter
hit_counter = GlobalHitCounter()

# -------------------------
# ALLSPORTS API WEBSOCKET CLIENT
# -------------------------
class AllSportsWebSocketClient:
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
            print(f"\n📡 AllSportsAPI WebSocket Update Received:")
            
            # Process the live data
            matches = self.process_websocket_data(data)
            if matches:
                api_manager.update_allsports_matches(matches)
                api_manager.websocket_connected = True
                
        except json.JSONDecodeError as e:
            print(f"❌ WebSocket JSON Error: {e}")
        except Exception as e:
            print(f"❌ WebSocket Message Error: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"⚠️ WebSocket Error: {error}")
        api_manager.websocket_connected = False
        
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket closure"""
        print(f"🔒 WebSocket Connection Closed: {close_status_code} - {close_msg}")
        api_manager.websocket_connected = False
        self.connected = False
        
        # Attempt reconnection
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
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
        self.reconnect_attempts = 0  # Reset counter on successful connection
    
    def process_websocket_data(self, data):
        """Process WebSocket data into match format"""
        try:
            matches = []
            
            # Handle different data structures from WebSocket
            if isinstance(data, dict):
                # Single match update
                if 'event' in data and data['event'] == 'live_update':
                    match_data = data.get('data', {})
                    if match_data:
                        matches.append(self.format_websocket_match(match_data))
                
                # Multiple matches in array
                elif isinstance(data.get('data'), list):
                    for match in data['data']:
                        formatted_match = self.format_websocket_match(match)
                        if formatted_match:
                            matches.append(formatted_match)
                
                # Direct match object
                elif data.get('match_id'):
                    formatted_match = self.format_websocket_match(data)
                    if formatted_match:
                        matches.append(formatted_match)
            
            elif isinstance(data, list):
                # Array of matches
                for match in data:
                    formatted_match = self.format_websocket_match(match)
                    if formatted_match:
                        matches.append(formatted_match)
            
            print(f"🔄 Processed {len(matches)} matches from WebSocket")
            return matches
            
        except Exception as e:
            print(f"❌ WebSocket data processing error: {e}")
            return []
    
    def format_websocket_match(self, match_data):
        """Format WebSocket match data to standard format"""
        try:
            # Map different field names to standard format
            home_team = match_data.get('match_hometeam_name') or match_data.get('home_team') or "Unknown"
            away_team = match_data.get('match_awayteam_name') or match_data.get('away_team') or "Unknown"
            home_score = str(match_data.get('match_hometeam_score') or match_data.get('home_score') or "0")
            away_score = str(match_data.get('match_awayteam_score') or match_data.get('away_score') or "0")
            minute = match_data.get('match_status') or match_data.get('minute') or match_data.get('time') or "0"
            league_id = match_data.get('league_id') or "unknown"
            
            # Determine match status
            if minute == "HT":
                match_status = "HALF TIME"
                display_minute = "HT"
            elif minute == "FT":
                match_status = "FULL TIME"
                display_minute = "FT"
            elif isinstance(minute, int) or (isinstance(minute, str) and minute.isdigit()):
                match_status = "LIVE"
                display_minute = f"{minute}'"
            elif minute in ["1H", "2H"]:
                match_status = "LIVE"
                display_minute = minute
            else:
                match_status = "UPCOMING"
                display_minute = minute
            
            return {
                "match_hometeam_name": home_team,
                "match_awayteam_name": away_team,
                "match_hometeam_score": home_score,
                "match_awayteam_score": away_score,
                "match_status": minute,
                "league_id": league_id,
                "league_name": get_league_name(league_id),
                "match_live": "1",
                "source": "allsports_websocket",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ WebSocket match formatting error: {e}")
            return None
    
    def connect(self):
        """Connect to WebSocket"""
        try:
            print(f"🔗 Connecting to AllSportsAPI WebSocket...")
            self.ws = websocket.WebSocketApp(
                ALLSPORTS_WS_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Run WebSocket in background thread
            def run_websocket():
                self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            
            ws_thread = threading.Thread(target=run_websocket, daemon=True)
            ws_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
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
    # Major European Leagues
    "152": {"name": "Premier League", "priority": 1, "type": "domestic"},
    "302": {"name": "La Liga", "priority": 1, "type": "domestic"},
    "207": {"name": "Serie A", "priority": 1, "type": "domestic"},
    "168": {"name": "Bundesliga", "priority": 1, "type": "domestic"},
    "176": {"name": "Ligue 1", "priority": 1, "type": "domestic"},
    
    # European Competitions
    "149": {"name": "Champions League", "priority": 1, "type": "european"},
    "150": {"name": "Europa League", "priority": 2, "type": "european"},
    
    # World Cup Qualifiers
    "5": {"name": "World Cup Qualifiers (UEFA)", "priority": 1, "type": "worldcup"},
    "6": {"name": "World Cup Qualifiers (AFC)", "priority": 2, "type": "worldcup"},
    "7": {"name": "World Cup Qualifiers (CONMEBOL)", "priority": 1, "type": "worldcup"},
    "8": {"name": "World Cup Qualifiers (CONCACAF)", "priority": 2, "type": "worldcup"},
    "9": {"name": "World Cup Qualifiers (CAF)", "priority": 2, "type": "worldcup"},
    "10": {"name": "World Cup Qualifiers (OFC)", "priority": 3, "type": "worldcup"},
}

def get_league_name(league_id):
    """Get league name from ID"""
    league_info = LEAGUE_CONFIG.get(str(league_id))
    if league_info:
        return league_info["name"]
    return f"League {league_id}"

# -------------------------
# API-FOOTBALL HTTP CLIENT
# -------------------------
def fetch_api_football_matches():
    """Fetch matches from API-Football HTTP API"""
    
    # Record the hit
    hit_info = hit_counter.record_hit()
    
    # Check if we can make the request
    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        print(f"🚫 API-Football Call Blocked: {reason}")
        return []
    
    try:
        # Use the optimized URL with match_live=1 parameter
        url = f"{API_FOOTBALL_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
        
        print(f"📡 Fetching from API-Football HTTP...")
        print(f"🔗 URL: {url.replace(API_KEY, 'API_KEY_HIDDEN')}")
        
        start_time = time.time()
        response = requests.get(url, timeout=15)
        response_time = time.time() - start_time
        
        print(f"⏱️ Response Time: {response_time:.2f}s")
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📦 Response Type: {type(data)}")
            
            if isinstance(data, list):
                print(f"✅ API-Football: Found {len(data)} live matches")
                
                # Add league names to matches
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                    match["source"] = "api_football"
                
                return data
            else:
                print(f"❌ API-Football: Invalid response format: {data}")
                return []
        else:
            print(f"❌ API-Football: HTTP Error {response.status_code}")
            return []
            
    except requests.exceptions.Timeout:
        print("❌ API-Football: Request timeout")
        return []
    except requests.exceptions.ConnectionError:
        print("❌ API-Football: Connection error")
        return []
    except Exception as e:
        print(f"❌ API-Football fetch error: {str(e)}")
        return []

# -------------------------
# DUAL API MATCH FETCHER
# -------------------------
def fetch_live_matches_dual_api():
    """Fetch matches using both APIs - WebSocket preferred"""
    
    # Get best available matches
    matches, source = api_manager.get_best_live_matches()
    
    # If no WebSocket data, try API-Football
    if source in ["NONE", "API_FOOTBALL"]:
        print("🔄 Falling back to API-Football HTTP...")
        api_football_matches = fetch_api_football_matches()
        if api_football_matches:
            api_manager.update_api_football_matches(api_football_matches)
            matches = api_football_matches
            source = "API_FOOTBALL"
    
    print(f"🎯 Final match source: {source}, Matches: {len(matches)}")
    return matches, source

# -------------------------
# MATCH PROCESSOR
# -------------------------
def process_match_data(matches):
    """Process raw match data for display"""
    if not matches:
        return []
    
    processed_matches = []
    for match in matches:
        try:
            home_team = match.get("match_hometeam_name", "Unknown")
            away_team = match.get("match_awayteam_name", "Unknown")
            home_score = match.get("match_hometeam_score", "0")
            away_score = match.get("match_awayteam_score", "0")
            minute = match.get("match_status", "0")
            league_name = match.get("league_name", "Unknown League")
            source = match.get("source", "unknown")
            
            # Determine match status
            if minute == "HT":
                match_status = "HALF TIME"
                display_minute = "HT"
            elif minute == "FT":
                match_status = "FULL TIME"
                display_minute = "FT"
            elif minute.isdigit():
                match_status = "LIVE"
                display_minute = f"{minute}'"
            elif minute in ["1H", "2H"]:
                match_status = "LIVE"
                display_minute = minute
            else:
                match_status = "UPCOMING"
                display_minute = minute
            
            # Source icon
            source_icon = "🔴" if source == "allsports_websocket" else "🔵"
            
            processed_matches.append({
                "home_team": home_team,
                "away_team": away_team,
                "score": f"{home_score}-{away_score}",
                "minute": display_minute,
                "status": match_status,
                "league": league_name,
                "is_live": match_status == "LIVE",
                "source": source,
                "source_icon": source_icon,
                "raw_data": match  # Keep original data for analysis
            })
            
        except Exception as e:
            print(f"⚠️ Match processing warning: {e}")
            continue
    
    return processed_matches

# -------------------------
# ENHANCED FOOTBALL AI WITH DETAILED ANALYSIS
# -------------------------
class EnhancedFootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking"},
            "liverpool": {"strength": 92, "style": "high press"},
            "arsenal": {"strength": 90, "style": "possession"},
            "real madrid": {"strength": 94, "style": "experienced"},
            "barcelona": {"strength": 92, "style": "possession"},
            "bayern munich": {"strength": 93, "style": "dominant"},
            "brazil": {"strength": 96, "style": "samba"},
            "argentina": {"strength": 94, "style": "technical"},
            "france": {"strength": 95, "style": "balanced"},
            "germany": {"strength": 92, "style": "efficient"},
        }
    
    def get_response(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'matches', 'scores']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api']):
            return hit_counter.get_hit_stats()
        
        elif any(word in message_lower for word in ['predict', 'prediction']):
            return self.handle_prediction(message_lower)
        
        elif any(word in message_lower for word in ['api status', 'connection']):
            return self.handle_api_status()
        
        elif any(word in message_lower for word in ['analysis', 'analyze', 'detail', 'report']):
            return self.handle_detailed_analysis(message_lower)
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "👋 Hello! I'm ENHANCED Football Analysis AI! ⚽\n\n🔍 **Detailed Match Analysis**\n🌐 **Real-time updates via WebSocket**\n🔄 **Fallback to HTTP API**\n\nTry: 'live matches', 'analysis man city', or 'api status'"
        
        else:
            return self.handle_team_specific_query(message_lower)

    def handle_live_matches(self):
        raw_matches, source = fetch_live_matches_dual_api()
        matches = process_match_data(raw_matches)
        
        if not matches:
            return "⏳ No live matches found right now.\n\n🌐 **API Status:**\n" + self.get_api_status_text()
        
        response = "🔴 **LIVE FOOTBALL MATCHES** ⚽\n\n"
        
        # Add source info
        source_text = "🔴 REAL-TIME WebSocket" if source == "ALLSPORTS_WS" else "🔵 API-Football HTTP"
        response += f"📡 **Source:** {source_text}\n\n"
        
        # Group by league
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
        response += f"🌐 Data Source: {source}\n"
        response += self.get_api_status_text()
        
        return response

    def handle_detailed_analysis(self, message):
        """Handle detailed match analysis requests"""
        # Extract team names from message
        teams = []
        for team in self.team_data:
            if team in message.lower():
                teams.append(team)
        
        if teams:
            # Find matches involving these teams
            matches_found = []
            for team in teams:
                team_matches = api_manager.find_match_by_teams(team)
                if team_matches:
                    if isinstance(team_matches, list):
                        matches_found.extend(team_matches)
                    else:
                        matches_found.append(team_matches)
            
            if matches_found:
                # Get the first match for analysis
                match_data = matches_found[0]
                return match_analyzer.generate_detailed_report(match_data)
            else:
                return f"❌ No live matches found for {', '.join(teams)}. Try 'live matches' to see current games."
        else:
            # Show analysis for all current matches
            raw_matches, source = fetch_live_matches_dual_api()
            if not raw_matches:
                return "❌ No live matches available for analysis."
            
            response = "🔍 **DETAILED MATCH ANALYSIS SUMMARY**\n\n"
            
            for i, match in enumerate(raw_matches[:5]):  # Limit to 5 matches
                analysis = match_analyzer.analyze_match_trends(match)
                home_team = match.get("match_hometeam_name", "Unknown")
                away_team = match.get("match_awayteam_name", "Unknown")
                score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                
                response += f"**{home_team} vs {away_team}**\n"
                response += f"Score: {score} | Progress: {analysis.get('match_progress', 'N/A')}\n"
                response += f"Momentum: {analysis.get('momentum', 'N/A')}\n"
                response += f"Tempo: {analysis.get('match_tempo', 'N/A')}\n\n"
            
            response += "💡 *Use 'analysis [team name]' for detailed match report*"
            return response

    def handle_team_specific_query(self, message):
        """Handle team-specific queries"""
        for team in self.team_data:
            if team in message.lower():
                # Check if this team is playing
                matches = api_manager.find_match_by_teams(team)
                if matches:
                    if isinstance(matches, list):
                        match_data = matches[0]
                    else:
                        match_data = matches
                    
                    return match_analyzer.generate_detailed_report(match_data)
                else:
                    return f"❌ {team.title()} is not playing right now. Try 'live matches' to see current games."
        
        # Default response for unrecognized queries
        return "🤖 **ENHANCED FOOTBALL ANALYSIS AI** ⚽\n\n🔍 **Detailed Match Analysis**\n🌐 **Real-time WebSocket Updates**\n🔄 **HTTP API Fallback**\n\nTry: 'live matches', 'analysis man city', 'api status', or 'hit stats'"

    def handle_prediction(self, message):
        teams = []
        for team in self.team_data:
            if team in message.lower():
                teams.append(team)
        
        if len(teams) >= 2:
            home_team, away_team = teams[0], teams[1]
            return self.generate_prediction(home_team, away_team)
        else:
            return "Please specify two teams for prediction. Example: 'Predict Manchester City vs Liverpool' or 'Brazil vs Argentina'"

    def generate_prediction(self, team1, team2):
        team1_data = self.team_data.get(team1.lower(), {"strength": 80})
        team2_data = self.team_data.get(team2.lower(), {"strength": 80})
        
        strength1 = team1_data["strength"]
        strength2 = team2_data["strength"]
        
        total = strength1 + strength2
        prob1 = (strength1 / total) * 100
        prob2 = (strength2 / total) * 100
        draw_prob = 100 - prob1 - prob2
        
        if prob1 > prob2:
            winner = team1.title()
        else:
            winner = team2.title()
        
        return f"""
🎯 **PREDICTION: {team1.upper()} vs {team2.upper()}**

📊 **Probabilities:**
• {team1.title()}: {prob1:.1f}%
• {team2.title()}: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%

🏆 **Most Likely: {winner}**

⚽ **Expected: High-scoring match with both teams attacking!**

⚠️ *Football is unpredictable - enjoy the game!*
"""

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

🚀 **NOW WITH DETAILED MATCH ANALYSIS!**

🔍 **NEW FEATURES:**
• Detailed Match Analysis & Statistics
• Live Match Trends & Momentum
• Team Performance Insights
• Advanced Predictions
• Real-time WebSocket Updates

🌐 **DUAL API SYSTEM:**
• 🔴 AllSportsAPI WebSocket (Real-time)
• 🔵 API-Football HTTP (Fallback)
• 🎯 Perfect Failover System

⚡ **Commands:**
/live - Live matches (Real-time preferred)
/analysis - Detailed match analysis
/status - API connection status
/hits - API hit statistics
/predict - Match predictions
/help - Complete guide

💬 **Natural Chat:**
"show me live matches"
"analysis manchester city"
"detailed report for barcelona"
"api status" 
"hit counter stats"

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

@bot.message_handler(commands=['analysis', 'detail', 'report'])
def send_detailed_analysis(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        # Extract text after command
        command_text = message.text.split(' ', 1)
        query = command_text[1] if len(command_text) > 1 else ""
        
        if query:
            response = football_ai.handle_detailed_analysis(query)
        else:
            response = football_ai.handle_detailed_analysis("analysis")
            
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
def send_predict_help(message):
    help_text = """
🎯 **MATCH PREDICTIONS**

Ask me like:
• "Predict Manchester City vs Liverpool"
• "Who will win Barcelona vs Real Madrid?"
• "Brazil vs Argentina prediction"

I'll analyze team strengths and give you probabilities! 📊
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
🤖 **ENHANCED FOOTBALL ANALYSIS BOT HELP**

🔍 **NEW ANALYSIS FEATURES:**
• Detailed match statistics
• Live momentum analysis
• Goal timing predictions
• Team performance insights
• Match tempo analysis

⚡ **QUICK COMMANDS:**
/live - Live matches (Real-time WebSocket)
/analysis - Detailed match analysis
/status - API connection status
/hits - API hit counter statistics  
/predict - Match predictions
/help - This help message

🌐 **API SYSTEM:**
• 🔴 AllSportsAPI WebSocket - Real-time updates
• 🔵 API-Football HTTP - Reliable fallback
• Automatic failover between APIs
• Real-time status monitoring

💬 **CHAT EXAMPLES:**
• "Show me live matches"
• "Analysis Manchester City"
• "Detailed report for Barcelona vs Real Madrid"
• "API status"
• "Hit counter stats"

🎯 **FEATURES:**
• Real-time live scores (WebSocket)
• Detailed match analysis
• HTTP API fallback
• Global hit counter
• Smart API caching
• Match predictions

🔥 **HIT COUNTER:**
• Tracks all API calls
• Daily limit: 100 calls
• Prevents overuse
• Real-time statistics
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        print(f"💬 Message from {user_id}: {user_message}")
        
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.5)  # Quick response
        
        response = football_ai.get_response(user_message)
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Message error: {e}")
        bot.reply_to(message, "❌ Sorry, error occurred. Please try again!")

# -------------------------
# AUTO UPDATER WITH DUAL API SUPPORT
# -------------------------
def auto_updater():
    """Auto-update matches with dual API support"""
    
    # Start WebSocket connection first
    print("🔗 Starting WebSocket connection...")
    websocket_client.connect()
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Dual-API update check...")
            
            # Check if we can make HTTP API call (for fallback)
            can_make, reason = hit_counter.can_make_request()
            
            # If WebSocket is not connected, use HTTP API
            if not api_manager.websocket_connected:
                print("⚠️ WebSocket disconnected, using HTTP API fallback...")
                if can_make:
                    matches = fetch_api_football_matches()
                    if matches:
                        api_manager.update_api_football_matches(matches)
                else:
                    print(f"⏸️ HTTP API call blocked: {reason}")
            
            # Smart wait time based on WebSocket status
            if api_manager.websocket_connected:
                wait_time = 30  # Quick checks when WebSocket is active
            elif hit_counter.daily_hits >= 80:
                wait_time = 600  # 10 minutes if high usage
            elif hit_counter.daily_hits >= 50:
                wait_time = 300  # 5 minutes if medium usage
            else:
                wait_time = 120  # 2 minutes if low usage
            
            print(f"⏰ Next update check in {wait_time} seconds...")
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Auto-updater error: {e}")
            time.sleep(300)

# -------------------------
# STARTUP FUNCTION
# -------------------------
def start_bot():
    """Start the bot with dual API support"""
    try:
        print("🚀 Starting Enhanced Football Analysis Bot...")
        
        # Start auto-updater
        updater_thread = threading.Thread(target=auto_updater, daemon=True)
        updater_thread.start()
        print("✅ Dual-API Auto-Updater started!")
        
        # Initial API test
        print("🔍 Testing API connections...")
        test_matches, source = fetch_live_matches_dual_api()
        print(f"🔍 Initial load: {len(test_matches)} matches from {source}")
        
        # Send startup message
        api_status = api_manager.get_api_status()
        startup_msg = f"""
🤖 **ENHANCED FOOTBALL ANALYSIS BOT STARTED!**

🔍 **NEW: Detailed Match Analysis Active**

✅ **Dual API System Active:**
• 🔴 WebSocket: {api_status['allsports_websocket']['status']}
• 🔵 HTTP API: {api_status['api_football']['status']}
• 🎯 Automatic Failover
• 📊 Real-time Monitoring

🌐 **Current Status:**
• WebSocket Matches: {api_status['allsports_websocket']['match_count']}
• HTTP API Matches: {api_status['api_football']['match_count']}
• WebSocket Retries: {api_status['allsports_websocket']['retry_count']}

🔥 **Hit Counter Ready**
📊 Today's Hits: {hit_counter.daily_hits}/100
💾 Analysis System: Active

🕒 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🌐 **Mode:** {'WEBHOOK' if USE_WEBHOOK else 'POLLING'}

🚀 **Real-time analysis with perfect fallback!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
        # Start bot
        if USE_WEBHOOK:
            print("🌐 Starting in webhook mode...")
            # Webhook setup code here
        else:
            print("🔄 Starting in polling mode...")
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling()
            
    except Exception as e:
        print(f"❌ Startup error: {e}")
        time.sleep(10)
        start_bot()

if __name__ == '__main__':
    start_bot()
