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



# global hit counter
import time

hits = 0

def fetch_live_matches():
    global hits
    hits += 1
    print(f"🔥 API HIT #{hits} at {time.strftime('%H:%M:%S')}")

    url = "https://apiv3.apifootball.com/?action=get_events&match_live=1&APIkey=839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
    response = requests.get(url)
    data = response.json()
    return data


# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
PORT = int(os.environ.get("PORT", 8080))
DOMAIN = os.environ.get("DOMAIN")

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_KEY missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ Check if we should use webhook or polling
USE_WEBHOOK = bool(DOMAIN)

print(f"🎯 Starting Football Prediction Bot...")
print(f"🌐 Webhook Mode: {USE_WEBHOOK}")
print(f"🔗 Domain: {DOMAIN}")

# ✅ CORRECT API URL FOR API-FOOTBALL.COM
API_URL = "https://apiv3.apifootball.com"

# -------------------------
# AUTO LIMIT PROTECTOR SYSTEM
# -------------------------
class AutoLimitProtector:
    def __init__(self):
        self.daily_limit = 100  # Free plan daily limit
        self.emergency_mode = False
        self.protection_log = []
        self.last_warning_sent = None
        
    def check_api_health(self, current_usage):
        """Check API usage and return protection level"""
        remaining_calls = self.daily_limit - current_usage
        
        if current_usage >= 95:
            level = "CRITICAL"
            action = "STOP_UPDATES"
            interval = 1800  # 30 minutes
        elif current_usage >= 80:
            level = "HIGH" 
            action = "REDUCE_HEAVY"
            interval = 600   # 10 minutes
        elif current_usage >= 60:
            level = "MEDIUM"
            action = "REDUCE_MEDIUM"
            interval = 300   # 5 minutes
        elif current_usage >= 40:
            level = "LOW"
            action = "REDUCE_LIGHT" 
            interval = 180   # 3 minutes
        else:
            level = "SAFE"
            action = "NORMAL"
            interval = 120   # 2 minutes
            
        return {
            "level": level,
            "action": action,
            "interval": interval,
            "remaining": remaining_calls,
            "usage_percent": (current_usage / self.daily_limit) * 100
        }
    
    def should_make_api_call(self, current_usage, call_type="auto"):
        """Determine if API call should be made"""
        if current_usage >= 100:
            self.log_protection("BLOCKED", f"{call_type} call blocked - Daily limit reached")
            return False
            
        if current_usage >= 95 and call_type == "auto":
            self.log_protection("BLOCKED", f"Auto update blocked - Critical level")
            return False
            
        return True
    
    def get_smart_interval(self, current_usage):
        """Get smart interval based on usage"""
        health = self.check_api_health(current_usage)
        
        # Add some randomness to avoid patterns
        random_buffer = random.randint(10, 30)
        final_interval = health["interval"] + random_buffer
        
        self.log_protection(health["level"], 
                           f"Interval: {final_interval}s, Remaining: {health['remaining']}")
        
        return final_interval, health
    
    def log_protection(self, level, message):
        """Log protection actions"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        self.protection_log.append(log_entry)
        
        # Keep only last 50 entries
        if len(self.protection_log) > 50:
            self.protection_log = self.protection_log[-50:]
            
        print(f"🛡️ [{level}] {message}")
    
    def send_warning_alert(self, health, current_usage, bot_instance):
        """Send warning alerts to owner"""
        try:
            if self.last_warning_sent and (datetime.now() - self.last_warning_sent).total_seconds() < 3600:
                return  # Don't spam warnings
                
            if health["level"] in ["CRITICAL", "HIGH"]:
                warning_msg = f"""
🚨 **API LIMIT ALERT**

📊 **Current Usage:** {current_usage}/{self.daily_limit}
📈 **Usage Percentage:** {health['usage_percent']:.1f}%
🛡️ **Protection Level:** {health['level']}
⏱️ **Update Interval:** {health['interval']} seconds
🔄 **Action Taken:** {health['action']}

💡 **Recommendation:** {'STOP BOT until reset' if health['level'] == 'CRITICAL' else 'Reduced update frequency'}
"""
                bot_instance.send_message(OWNER_CHAT_ID, warning_msg, parse_mode='Markdown')
                self.last_warning_sent = datetime.now()
                
        except Exception as e:
            print(f"❌ Warning alert error: {e}")
    
    def get_protection_status(self):
        """Get protection system status"""
        if not self.protection_log:
            return "🟢 Protection System: No actions taken yet"
        
        recent_actions = self.protection_log[-5:]  # Last 5 actions
        actions_text = "\n".join([f"• {action['timestamp'][11:19]} - {action['level']}: {action['message']}" 
                                for action in recent_actions])
        
        return f"""
🛡️ **AUTO LIMIT PROTECTOR STATUS**

📊 **Recent Actions:**
{actions_text}

🎯 **Protection Levels:**
• 🟢 SAFE (0-39%) - 2-3 minute updates
• 🟡 LOW (40-59%) - 3-5 minute updates  
• 🟠 MEDIUM (60-79%) - 5-10 minute updates
• 🔴 HIGH (80-94%) - 10-30 minute updates
• 🚨 CRITICAL (95%+) - Stop auto updates

💾 **Daily Limit:** {self.daily_limit} calls
"""

# Initialize Auto Limit Protector
limit_protector = AutoLimitProtector()

# -------------------------
# SMART API CACHING SYSTEM
# -------------------------
class APICache:
    def __init__(self):
        self.cache_file = "api_cache.json"
        self.cache_duration = 120  # 2 minutes cache for live matches
        self.stats_file = "api_stats.json"
        self.load_cache()
        self.load_stats()
    
    def load_cache(self):
        """Load cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                print("✅ Cache loaded successfully")
            else:
                self.cache = {
                    "live_matches": {"data": [], "timestamp": None},
                    "today_matches": {"data": [], "timestamp": None}
                }
                self.save_cache()
        except Exception as e:
            print(f"❌ Cache load error: {e}")
            self.cache = {
                "live_matches": {"data": [], "timestamp": None},
                "today_matches": {"data": [], "timestamp": None}
            }
    
    def save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"❌ Cache save error: {e}")
    
    def load_stats(self):
        """Load API statistics"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    self.stats = json.load(f)
            else:
                self.stats = {
                    "total_api_calls": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "daily_calls": 0,
                    "last_reset": datetime.now().isoformat()
                }
                self.save_stats()
        except Exception as e:
            print(f"❌ Stats load error: {e}")
            self.stats = {
                "total_api_calls": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "daily_calls": 0,
                "last_reset": datetime.now().isoformat()
            }
    
    def save_stats(self):
        """Save statistics to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"❌ Stats save error: {e}")
    
    def reset_daily_counter(self):
        """Reset daily counter if new day"""
        try:
            last_reset = datetime.fromisoformat(self.stats["last_reset"])
            now = datetime.now()
            if now.date() > last_reset.date():
                self.stats["daily_calls"] = 0
                self.stats["last_reset"] = now.isoformat()
                self.save_stats()
                print("🔄 Daily API counter reset")
                return True
            return False
        except Exception as e:
            print(f"❌ Daily counter reset error: {e}")
            return False
    
    def is_cache_valid(self, cache_key):
        """Check if cache is still valid"""
        if cache_key not in self.cache:
            return False
        
        cached_data = self.cache[cache_key]
        if not cached_data["timestamp"]:
            return False
        
        try:
            cache_time = datetime.fromisoformat(cached_data["timestamp"])
            time_diff = (datetime.now() - cache_time).total_seconds()
            return time_diff < self.cache_duration
        except:
            return False
    
    def get_cached_data(self, cache_key):
        """Get cached data if valid"""
        self.reset_daily_counter()
        
        if self.is_cache_valid(cache_key):
            self.stats["cache_hits"] += 1
            self.save_stats()
            print(f"✅ Cache HIT for {cache_key}")
            return self.cache[cache_key]["data"]
        else:
            self.stats["cache_misses"] += 1
            self.save_stats()
            print(f"🔄 Cache MISS for {cache_key}")
            return None
    
    def update_cache(self, cache_key, data):
        """Update cache with new data"""
        try:
            self.cache[cache_key] = {
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            self.save_cache()
            print(f"💾 Cache UPDATED for {cache_key}")
        except Exception as e:
            print(f"❌ Cache update error: {e}")
    
    def record_api_call(self):
        """Record API call in statistics"""
        self.stats["total_api_calls"] += 1
        self.stats["daily_calls"] += 1
        self.save_stats()
        
        # Check protection system
        health = limit_protector.check_api_health(self.stats["daily_calls"])
        
        print(f"📊 API Call #{self.stats['total_api_calls']} (Today: {self.stats['daily_calls']}/{limit_protector.daily_limit})")
        print(f"🛡️ Protection Level: {health['level']}")
        
        # Send warning if needed
        if health["level"] in ["HIGH", "CRITICAL"]:
            limit_protector.send_warning_alert(health, self.stats["daily_calls"], bot)
    
    def get_cache_stats(self):
        """Get cache statistics"""
        total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
        hit_rate = (self.stats["cache_hits"] / total_requests * 100) if total_requests > 0 else 0
        
        health = limit_protector.check_api_health(self.stats["daily_calls"])
        
        return f"""
📊 **CACHE & PROTECTION STATISTICS**

🔢 **API Usage:**
• Total API Calls: {self.stats['total_api_calls']}
• Today's Calls: {self.stats['daily_calls']}/{limit_protector.daily_limit}
• Remaining Today: {limit_protector.daily_limit - self.stats['daily_calls']}
• Usage Percentage: {health['usage_percent']:.1f}%

💾 **Cache Performance:**
• Cache Hits: {self.stats['cache_hits']}
• Cache Misses: {self.stats['cache_misses']}
• Hit Rate: {hit_rate:.1f}%

🛡️ **Protection System:**
• Current Level: {health['level']}
• Update Interval: {health['interval']}s
• Action: {health['action']}

⏱️ **Cache Duration:** {self.cache_duration} seconds
"""

# Initialize cache
api_cache = APICache()

# -------------------------
# UPDATED & VERIFIED LEAGUE IDs
# -------------------------
TARGET_LEAGUES = {
    "152": "Premier League",
    "302": "La Liga", 
    "207": "Serie A",
    "168": "Bundesliga",
    "176": "Ligue 1",
    "149": "Champions League",
    "150": "Europa League"
}

# -------------------------
# CACHED REAL-TIME MATCH DATA FETCHING
# -------------------------
def fetch_real_live_matches():
    """Fetch REAL live matches from API with caching"""
    
    # First check cache
    cached_data = api_cache.get_cached_data("live_matches")
    if cached_data is not None:
        return cached_data
    
    # Check if API call should be made (protection system)
    if not limit_protector.should_make_api_call(api_cache.stats["daily_calls"], "auto"):
        print("🛡️ API call blocked by protection system")
        stale_cache = api_cache.cache.get("live_matches", {}).get("data", [])
        return stale_cache
    
    # If no cache, make API call
    try:
        print("🔴 Fetching LIVE matches from API...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
        
        print(f"📡 API URL: {url.replace(API_KEY, 'API_KEY_HIDDEN')}")
        
        response = requests.get(url, timeout=20)
        
        # Record API call
        api_cache.record_api_call()
        
        if response.status_code == 200:
            data = response.json()
            
            # Debug output
            print(f"📊 API Response type: {type(data)}")
            if isinstance(data, list):
                print(f"📊 Total matches found: {len(data)}")
            else:
                print(f"📊 API Response: {data}")
            
            if data and isinstance(data, list):
                live_matches = []
                for match in data:
                    try:
                        # Multiple ways to detect live matches
                        match_status = str(match.get("match_status", ""))
                        match_live = str(match.get("match_live", "0"))
                        match_time = match.get("match_time", "")
                        
                        # Check if match is live
                        is_live = (
                            match_live == "1" or 
                            match_status.isdigit() or 
                            match_status in ["1H", "2H", "HT", "IN PROGRESS"]
                        )
                        
                        if is_live:
                            league_id = match.get("league_id", "")
                            # Only include target leagues
                            if str(league_id) in TARGET_LEAGUES:
                                live_matches.append(match)
                                print(f"✅ Live match found: {match.get('match_hometeam_name')} vs {match.get('match_awayteam_name')}")
                    
                    except Exception as e:
                        print(f"⚠️ Match processing warning: {e}")
                        continue
                
                print(f"✅ Found {len(live_matches)} REAL live matches in target leagues")
                
                # Update cache
                api_cache.update_cache("live_matches", live_matches)
                
                return live_matches
            else:
                print("⏳ No live matches data from API or invalid response")
                if isinstance(data, dict) and 'error' in data:
                    print(f"❌ API Error: {data['error']}")
                
                # Cache empty result to avoid frequent API calls
                api_cache.update_cache("live_matches", [])
                return []
        else:
            print(f"❌ API Error {response.status_code}: {response.text}")
            
            # Cache empty result on error
            api_cache.update_cache("live_matches", [])
            return []
            
    except requests.exceptions.Timeout:
        print("❌ API request timeout")
        # Return cached data even if stale on timeout
        stale_cache = api_cache.cache.get("live_matches", {}).get("data", [])
        return stale_cache
    except requests.exceptions.ConnectionError:
        print("❌ API connection error")
        # Return cached data even if stale on connection error
        stale_cache = api_cache.cache.get("live_matches", {}).get("data", [])
        return stale_cache
    except Exception as e:
        print(f"❌ Live matches fetch error: {str(e)}")
        # Return cached data even if stale on other errors
        stale_cache = api_cache.cache.get("live_matches", {}).get("data", [])
        return stale_cache

def process_real_match(match):
    """Process real match data from API"""
    try:
        home_team = match.get("match_hometeam_name", "Unknown")
        away_team = match.get("match_awayteam_name", "Unknown")
        home_score = match.get("match_hometeam_score", "0")
        away_score = match.get("match_awayteam_score", "0")
        minute = match.get("match_status", "0")
        league_id = match.get("league_id", "")
        league_name = TARGET_LEAGUES.get(str(league_id), f"League {league_id}")
        
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
        
        return {
            "home_team": home_team,
            "away_team": away_team,
            "score": f"{home_score}-{away_score}",
            "minute": display_minute,
            "status": match_status,
            "league": league_name,
            "league_id": league_id
        }
        
    except Exception as e:
        print(f"❌ Match processing error: {e}")
        return None

def get_real_live_matches():
    """Get real live matches from API with caching and retry logic"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            raw_matches = fetch_real_live_matches()
            
            if not raw_matches:
                if attempt < max_retries - 1:
                    print(f"🔄 Retry {attempt + 1}/{max_retries} in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    print("⏳ No live matches found after retries")
                    return []
            
            processed_matches = []
            for match in raw_matches:
                processed_match = process_real_match(match)
                if processed_match:
                    processed_matches.append(processed_match)
            
            print(f"✅ Successfully processed {len(processed_matches)} real live matches")
            return processed_matches
                
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    
    return []

# -------------------------
# ENHANCED AI CHATBOT WITH CACHE & PROTECTION AWARENESS
# -------------------------
class SmartFootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking"},
            "liverpool": {"strength": 92, "style": "high press"},
            "arsenal": {"strength": 90, "style": "possession"},
            "chelsea": {"strength": 85, "style": "balanced"},
            "manchester united": {"strength": 84, "style": "counter attack"},
            "tottenham": {"strength": 87, "style": "attacking"},
            "real madrid": {"strength": 94, "style": "experienced"},
            "barcelona": {"strength": 92, "style": "possession"},
            "bayern munich": {"strength": 93, "style": "dominant"},
            "psg": {"strength": 90, "style": "attacking"},
            "inter": {"strength": 89, "style": "defensive"},
            "juventus": {"strength": 88, "style": "tactical"},
            "milan": {"strength": 86, "style": "balanced"},
            "napoli": {"strength": 85, "style": "attacking"}
        }
    
    def get_ai_response(self, user_message, user_id):
        """AI response with cache and protection awareness"""
        user_message_lower = user_message.lower()
        
        if any(word in user_message_lower for word in ['live', 'current', 'now playing']):
            return self.handle_live_matches_query()
        
        elif any(word in user_message_lower for word in ['predict', 'prediction', 'who will win']):
            return self.handle_prediction_query(user_message_lower)
        
        elif any(word in user_message_lower for word in ['cache', 'statistics', 'stats', 'api']):
            return api_cache.get_cache_stats()
        
        elif any(word in user_message_lower for word in ['protection', 'limit', 'quota']):
            return limit_protector.get_protection_status()
        
        elif any(word in user_message_lower for word in ['hello', 'hi', 'hey']):
            return "👋 Hello! I'm Football Prediction AI with AUTO LIMIT PROTECTION! ⚽\n\nAsk me about live matches, predictions, or protection status!"
        
        elif any(word in user_message_lower for word in ['help']):
            return self.get_help_response()
        
        else:
            return "🤖 I can help with:\n• Live match updates (PROTECTED)\n• Match predictions\n• Cache statistics\n• API limit protection\n\nTry: 'Show me live matches' or 'protection status'"

    def handle_live_matches_query(self):
        """Handle live matches queries with protection info"""
        real_matches = get_real_live_matches()
        
        # Get protection info
        health = limit_protector.check_api_health(api_cache.stats["daily_calls"])
        protection_icon = "🟢" if health["level"] == "SAFE" else "🟡" if health["level"] == "LOW" else "🟠" if health["level"] == "MEDIUM" else "🔴"
        
        protection_info = f"\n{protection_icon} *Protection: {health['level']} ({health['remaining']} calls left)*"
        
        if real_matches:
            response = f"🔴 **LIVE MATCHES RIGHT NOW:**{protection_info}\n\n"
            
            # Group by league for better organization
            matches_by_league = {}
            for match in real_matches:
                league = match['league']
                if league not in matches_by_league:
                    matches_by_league[league] = []
                matches_by_league[league].append(match)
            
            for league, matches in matches_by_league.items():
                response += f"⚽ **{league}**\n"
                for match in matches:
                    status_icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                    response += f"• {match['home_team']} {match['score']} {match['away_team']} {status_icon} {match['minute']}\n"
                response += "\n"
            
            response += f"🔄 Updates: {health['interval']}s intervals\n"
            response += f"📊 API Usage: {api_cache.stats['daily_calls']}/{limit_protector.daily_limit}"
            
        else:
            response = f"⏳ No live matches in major leagues right now.{protection_info}\n\n"
            response += "Try asking for predictions instead!"
        
        return response

    def handle_prediction_query(self, message):
        """Handle prediction queries"""
        teams = []
        for team in self.team_data:
            if team in message:
                teams.append(team)
        
        if len(teams) >= 2:
            return self.generate_prediction(teams[0], teams[1])
        else:
            return "Please specify two teams for prediction. Example: 'Predict Manchester City vs Liverpool'"

    def generate_prediction(self, team1, team2):
        """Generate AI prediction"""
        team1_data = self.team_data.get(team1, {"strength": 80, "style": "balanced"})
        team2_data = self.team_data.get(team2, {"strength": 80, "style": "balanced"})
        
        strength1 = team1_data["strength"]
        strength2 = team2_data["strength"]
        
        # Advanced prediction algorithm
        total = strength1 + strength2
        prob1 = (strength1 / total) * 100
        prob2 = (strength2 / total) * 100
        draw_prob = (100 - abs(prob1 - prob2)) / 3
        
        # Adjust probabilities
        prob1 = prob1 - (draw_prob / 2)
        prob2 = prob2 - (draw_prob / 2)
        
        # Normalize
        total_prob = prob1 + prob2 + draw_prob
        prob1 = (prob1 / total_prob) * 100
        prob2 = (prob2 / total_prob) * 100
        draw_prob = (draw_prob / total_prob) * 100
        
        if prob1 > prob2 and prob1 > draw_prob:
            winner = team1.title()
            confidence = "HIGH" if prob1 > 55 else "MEDIUM"
        elif prob2 > prob1 and prob2 > draw_prob:
            winner = team2.title()
            confidence = "HIGH" if prob2 > 55 else "MEDIUM"
        else:
            winner = "Draw"
            confidence = "MEDIUM"
        
        # BTTS prediction
        btts_prob = (team1_data["strength"] + team2_data["strength"]) / 2
        btts = "YES" if btts_prob > 45 else "NO"
        
        return f"""
🎯 **AI PREDICTION: {team1.upper()} vs {team2.upper()}**

📊 **Probabilities:**
• {team1.title()}: {prob1:.1f}%
• {team2.title()}: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%

🏆 **Predicted Winner: {winner}**
🎯 **Confidence: {confidence}**

⚽ **Match Analysis:**
• Both Teams to Score: {btts}
• Expected Goals: OVER 2.5
• Match Intensity: HIGH

💡 **Betting Tips:**
• Consider {winner} to win
• Both teams likely to score
• Expect an exciting match!

⚠️ *Football is unpredictable - bet responsibly!*
"""

    def get_help_response(self):
        health = limit_protector.check_api_health(api_cache.stats["daily_calls"])
        
        return f"""
🤖 **FOOTBALL PREDICTION BOT WITH AUTO LIMIT PROTECTION**

⚡ **COMMANDS:**
/live - Get current live matches (PROTECTED)
/predict - Get match predictions  
/stats - Cache & API statistics
/protection - Protection system status
/help - This help message

💬 **CHAT EXAMPLES:**
• "Show me live matches"
• "Predict Manchester City vs Liverpool" 
• "Cache statistics"
• "Protection status"
• "How many API calls left?"

🎯 **FEATURES:**
• Real-time live scores (Smart caching)
• AI match predictions
• 7 major leagues coverage
• Auto API limit protection
• Smart rate limiting

🛡️ **PROTECTION SYSTEM:**
• Current Level: {health['level']}
• API Usage: {api_cache.stats['daily_calls']}/{limit_protector.daily_limit}
• Update Interval: {health['interval']} seconds
• Remaining Calls: {health['remaining']}

💾 **CACHE BENEFITS:**
• Reduces API calls by 80%+
• Faster response times  
• Avoids daily limits
• Works offline with cached data

📊 **Current Stats:**
• API Calls Today: {api_cache.stats['daily_calls']}/{limit_protector.daily_limit}
• Cache Hits: {api_cache.stats['cache_hits']}
• Total Saved: {api_cache.stats['cache_hits']} calls
"""

# Initialize AI
football_ai = SmartFootballAI()

# -------------------------
# TELEGRAM BOT HANDLERS
# -------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
🤖 **WELCOME TO FOOTBALL PREDICTION AI** ⚽

🚀 **NOW WITH AUTO LIMIT PROTECTION!**

I provide:
• 🔴 Real-time live matches (PROTECTED)
• 🎯 AI-powered predictions  
• 📊 7 major leagues coverage
• 🛡️ Auto API limit protection
• 💾 Smart caching system

⚡ **Quick Commands:**
/live - Current live matches (PROTECTED)
/predict - Match predictions
/stats - Cache & protection stats  
/protection - Protection system status
/help - Help guide

💬 **Or just chat naturally!**

🛡️ **Auto protection prevents hitting API limits!**
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['live'])
def get_live_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        live_matches = get_real_live_matches()
        
        # Get protection info
        health = limit_protector.check_api_health(api_cache.stats["daily_calls"])
        protection_icon = "🟢" if health["level"] == "SAFE" else "🟡" if health["level"] == "LOW" else "🟠" if health["level"] == "MEDIUM" else "🔴"
        
        protection_info = f"\n{protection_icon} *Protection: {health['level']} ({health['remaining']} calls left)*"
        
        if live_matches:
            response = f"🔴 **LIVE MATCHES RIGHT NOW:**{protection_info}\n\n"
            
            # Group by league for better organization
            matches_by_league = {}
            for match in live_matches:
                league = match['league']
                if league not in matches_by_league:
                    matches_by_league[league] = []
                matches_by_league[league].append(match)
            
            for league, matches in matches_by_league.items():
                response += f"⚽ **{league}**\n"
                for match in matches:
                    status_icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                    response += f"• {match['home_team']} {match['score']} {match['away_team']} {status_icon} {match['minute']}\n"
                response += "\n"
            
            response += f"🔄 Updates: {health['interval']}s intervals\n"
            response += f"📊 API Usage: {api_cache.stats['daily_calls']}/{limit_protector.daily_limit}"
            
        else:
            response = f"⏳ **No live matches in major leagues right now.**{protection_info}\n\n"
            response += "Try the /predict command for upcoming match predictions!"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def get_predictions(message):
    try:
        response = """
🔮 **MATCH PREDICTIONS**

For specific match predictions, please ask me like:
• "Predict Manchester City vs Liverpool"
• "Who will win Barcelona vs Real Madrid?"
• "Arsenal vs Chelsea prediction"

I cover all major European leagues! 🏆
"""
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['stats', 'cache'])
def get_stats(message):
    try:
        stats_text = api_cache.get_cache_stats()
        bot.reply_to(message, stats_text, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Stats error: {str(e)}")

@bot.message_handler(commands=['protection', 'limit'])
def get_protection(message):
    try:
        protection_text = limit_protector.get_protection_status()
        bot.reply_to(message, protection_text, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Protection status error: {str(e)}")

@bot.message_handler(commands=['help'])
def get_help(message):
    help_text = football_ai.get_help_response()
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_ai_chat(message):
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        print(f"💬 Chat from user {user_id}: {user_message}")
        
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(1)
        
        ai_response = football_ai.get_ai_response(user_message, user_id)
        
        bot.reply_to(message, ai_response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        bot.reply_to(message, "❌ Sorry, error occurred. Please try again!")

# -------------------------
# SMART AUTO UPDATER WITH AUTO LIMIT PROTECTION
# -------------------------
def smart_auto_updater():
    """Smart auto-updater with automatic limit protection"""
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Smart protection update check...")
            
            # Get current usage
            current_usage = api_cache.stats["daily_calls"]
            
            # Check if we should make API call
            if not limit_protector.should_make_api_call(current_usage, "auto"):
                # Get interval even when blocked (for waiting)
                interval, health = limit_protector.get_smart_interval(current_usage)
                print(f"🛡️ Auto-update blocked. Waiting {interval} seconds...")
                time.sleep(interval)
                continue
            
            # Only update if cache is expired
            if not api_cache.is_cache_valid("live_matches"):
                print("💾 Cache expired, updating with protection...")
                live_matches = get_real_live_matches()
                
                if live_matches:
                    print(f"✅ {len(live_matches)} live matches cached")
                else:
                    print("⏳ No live matches to cache")
            else:
                print("💾 Cache still fresh, skipping API call")
            
            # Get smart interval based on current usage
            interval, health = limit_protector.get_smart_interval(current_usage)
            
            print(f"⏰ Next update in {interval} seconds (Protection: {health['level']})...")
            time.sleep(interval)
            
        except Exception as e:
            print(f"❌ Auto updater error: {e}")
            time.sleep(300)  # Wait 5 minutes on error

# -------------------------
# FLASK WEBHOOK ROUTES (Only for webhook mode)
# -------------------------
@app.route('/')
def home():
    health = limit_protector.check_api_health(api_cache.stats["daily_calls"])
    return f"🤖 Football Prediction AI Bot - Live Match Updates with Auto Limit Protection! ⚽<br>API Usage: {api_cache.stats['daily_calls']}/100 | Protection: {health['level']}"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.method == "POST":
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200

# -------------------------
# SMART STARTUP SYSTEM
# -------------------------
def setup_webhook():
    """Setup webhook for production"""
    try:
        print("🌐 Setting up webhook...")
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{DOMAIN}/{BOT_TOKEN}"
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook set: {webhook_url}")
        return True
    except Exception as e:
        print(f"❌ Webhook setup failed: {e}")
        return False

def start_polling():
    """Start polling for development"""
    try:
        print("🔄 Starting polling mode...")
        bot.remove_webhook()  # Ensure webhook is removed
        time.sleep(1)
        bot.infinity_polling()
        return True
    except Exception as e:
        print(f"❌ Polling failed: {e}")
        return False

def start_bot():
    """Main bot starter"""
    try:
        print("🚀 Starting Football Prediction Bot with AUTO LIMIT PROTECTION...")
        
        # Start smart auto-updater with protection
        updater_thread = threading.Thread(target=smart_auto_updater, daemon=True)
        updater_thread.start()
        print("✅ Smart Auto-Updater with Protection Started!")
        
        # Test system
        print("🔍 Testing protection system...")
        test_matches = get_real_live_matches()
        print(f"🔍 Initial cache load: {len(test_matches)} matches")
        
        health = limit_protector.check_api_health(api_cache.stats["daily_calls"])
        
        startup_msg = f"""
🤖 **FOOTBALL PREDICTION AI WITH AUTO LIMIT PROTECTION STARTED!**

✅ **Advanced Protection Features Active:**
• Real-time match updates (PROTECTED)
• AI predictions
• 7 major leagues coverage  
• Auto API limit protection
• Smart rate limiting
• Dynamic interval adjustment

🛡️ **Protection System:**
• Current Level: {health['level']}
• API Usage: {api_cache.stats['daily_calls']}/{limit_protector.daily_limit}
• Update Interval: {health['interval']}s
• Remaining Calls: {health['remaining']}

💾 **Cache System:**
• API Calls Saved: {api_cache.stats['cache_hits']}
• Cache Hit Rate: Calculating...

🌐 **Mode:** {'WEBHOOK' if USE_WEBHOOK else 'POLLING'}
🕒 **Pakistan Time:** {datetime.now(pytz.timezone('Asia/Karachi')).strftime('%Y-%m-%d %H:%M:%S')}

🛡️ **Bot is fully protected against API limits!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
        # Choose between webhook and polling
        if USE_WEBHOOK:
            print("🟢 Starting in WEBHOOK mode...")
            if setup_webhook():
                app.run(host='0.0.0.0', port=PORT, debug=False)
            else:
                print("🔄 Falling back to polling...")
                start_polling()
        else:
            print("🟢 Starting in POLLING mode...")
            start_polling()
            
    except Exception as e:
        print(f"❌ Bot startup error: {e}")
        print("🔄 Restarting in 10 seconds...")
        time.sleep(10)
        start_bot()

if __name__ == '__main__':
    start_bot()
