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

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY") or "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

if not all([BOT_TOKEN, OWNER_CHAT_ID]):
    raise ValueError("❌ BOT_TOKEN or OWNER_CHAT_ID missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ Check if we should use webhook or polling
USE_WEBHOOK = bool(os.environ.get("DOMAIN"))

print(f"🎯 Starting Football Prediction Bot...")
print(f"🌐 Webhook Mode: {USE_WEBHOOK}")

# ✅ CORRECT API URL FOR API-FOOTBALL.COM
API_URL = "https://apiv3.apifootball.com"

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
        
        stats = f"""
🔥 **GLOBAL HIT COUNTER STATS**

📈 **Current Usage:**
• Total Hits: {self.total_hits}
• Today's Hits: {self.daily_hits}/100
• This Hour: {self.hourly_hits}
• Hits/Minute: {hits_per_minute:.1f}

🎯 **Remaining Capacity:**
• Daily Remaining: {remaining_daily} calls
• Time Until Reset: {hours_until_reset}h {minutes_until_reset}m
• Usage Percentage: {(self.daily_hits/100)*100:.1f}%

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
# OPTIMIZED API CACHING SYSTEM
# -------------------------
class OptimizedAPICache:
    def __init__(self):
        self.cache_file = "api_cache.json"
        self.cache_duration = 300  # 5 minutes cache
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
                    "sample_matches": {"data": self.get_sample_matches(), "timestamp": datetime.now().isoformat()}
                }
                self.save_cache()
        except Exception as e:
            print(f"❌ Cache load error: {e}")
            self.cache = {
                "live_matches": {"data": [], "timestamp": None},
                "sample_matches": {"data": self.get_sample_matches(), "timestamp": datetime.now().isoformat()}
            }
    
    def get_sample_matches(self):
        """Get sample matches for demo when API is down"""
        return [
            {
                "match_hometeam_name": "Manchester City",
                "match_awayteam_name": "Liverpool", 
                "match_hometeam_score": "1",
                "match_awayteam_score": "1",
                "match_status": "45",
                "league_id": "152",
                "match_live": "1",
                "league_name": "Premier League"
            },
            {
                "match_hometeam_name": "Real Madrid",
                "match_awayteam_name": "Barcelona",
                "match_hometeam_score": "2", 
                "match_awayteam_score": "0",
                "match_status": "65",
                "league_id": "302",
                "match_live": "1",
                "league_name": "La Liga"
            },
            {
                "match_hometeam_name": "Bayern Munich",
                "match_awayteam_name": "Borussia Dortmund",
                "match_hometeam_score": "1",
                "match_awayteam_score": "1", 
                "match_status": "HT",
                "league_id": "168",
                "match_live": "1",
                "league_name": "Bundesliga"
            }
        ]
    
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
                    "total_requests": 0,
                    "cache_hits": 0,
                    "successful_api_calls": 0,
                    "failed_api_calls": 0,
                    "last_success": None
                }
                self.save_stats()
        except Exception as e:
            print(f"❌ Stats load error: {e}")
            self.stats = {
                "total_requests": 0,
                "cache_hits": 0,
                "successful_api_calls": 0,
                "failed_api_calls": 0,
                "last_success": None
            }
    
    def save_stats(self):
        """Save statistics to file"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"❌ Stats save error: {e}")
    
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
        self.stats["total_requests"] += 1
        
        if self.is_cache_valid(cache_key):
            self.stats["cache_hits"] += 1
            self.save_stats()
            print(f"✅ Cache HIT for {cache_key}")
            return self.cache[cache_key]["data"]
        else:
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
    
    def record_api_result(self, success=True):
        """Record API call result"""
        if success:
            self.stats["successful_api_calls"] += 1
            self.stats["last_success"] = datetime.now().isoformat()
        else:
            self.stats["failed_api_calls"] += 1
        self.save_stats()
    
    def get_cache_stats(self):
        """Get cache statistics"""
        total_requests = self.stats["total_requests"]
        cache_hit_rate = (self.stats["cache_hits"] / total_requests * 100) if total_requests > 0 else 0
        
        total_api_calls = self.stats["successful_api_calls"] + self.stats["failed_api_calls"]
        success_rate = (self.stats["successful_api_calls"] / total_api_calls * 100) if total_api_calls > 0 else 0
        
        return f"""
💾 **CACHE PERFORMANCE STATS**

📊 **Requests:**
• Total Requests: {self.stats['total_requests']}
• Cache Hits: {self.stats['cache_hits']}
• Cache Hit Rate: {cache_hit_rate:.1f}%

🔗 **API Calls:**
• Successful: {self.stats['successful_api_calls']}
• Failed: {self.stats['failed_api_calls']}
• Success Rate: {success_rate:.1f}%

⏱️ **Cache Duration:** {self.cache_duration} seconds
{'• Last Success: ' + datetime.fromisoformat(self.stats['last_success']).strftime('%H:%M:%S') if self.stats['last_success'] else '• No successful calls yet'}
"""

# Initialize Cache
api_cache = OptimizedAPICache()

# -------------------------
# OPTIMIZED LIVE MATCHES FETCHER
# -------------------------
def fetch_live_matches():
    """🔥 OPTIMIZED API CALL with hit counter and live matches filter"""
    
    # Record the hit
    hit_info = hit_counter.record_hit()
    
    # Check if we can make the request
    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        print(f"🚫 API Call Blocked: {reason}")
        return api_cache.cache.get("sample_matches", {}).get("data", [])
    
    try:
        # Use the optimized URL with match_live=1 parameter
        url = f"https://apiv3.apifootball.com/?action=get_events&match_live=1&APIkey={API_KEY}"
        
        print(f"📡 Fetching LIVE matches from API...")
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
                print(f"✅ Found {len(data)} live matches")
                api_cache.record_api_result(success=True)
                
                # Add league names to matches
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                
                return data
            else:
                print(f"❌ Invalid response format: {data}")
                api_cache.record_api_result(success=False)
                return api_cache.cache.get("sample_matches", {}).get("data", [])
        else:
            print(f"❌ HTTP Error {response.status_code}")
            api_cache.record_api_result(success=False)
            return api_cache.cache.get("sample_matches", {}).get("data", [])
            
    except requests.exceptions.Timeout:
        print("❌ API request timeout")
        api_cache.record_api_result(success=False)
        return api_cache.cache.get("sample_matches", {}).get("data", [])
    except requests.exceptions.ConnectionError:
        print("❌ API connection error")
        api_cache.record_api_result(success=False)
        return api_cache.cache.get("sample_matches", {}).get("data", [])
    except Exception as e:
        print(f"❌ API fetch error: {str(e)}")
        api_cache.record_api_result(success=False)
        return api_cache.cache.get("sample_matches", {}).get("data", [])

def get_league_name(league_id):
    """Get league name from ID"""
    league_map = {
        "152": "Premier League",
        "302": "La Liga", 
        "207": "Serie A",
        "168": "Bundesliga",
        "176": "Ligue 1",
        "149": "Champions League",
        "150": "Europa League"
    }
    return league_map.get(str(league_id), f"League {league_id}")

# -------------------------
# SMART MATCH PROCESSOR
# -------------------------
def get_optimized_live_matches():
    """Get live matches with smart caching and hit protection"""
    
    # First try cache
    cached_data = api_cache.get_cached_data("live_matches")
    if cached_data is not None:
        return cached_data
    
    # If cache miss, fetch from API
    print("🔄 Cache expired, fetching fresh data...")
    live_matches = fetch_live_matches()
    
    # Update cache with new data
    api_cache.update_cache("live_matches", live_matches)
    
    return live_matches

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
            
            processed_matches.append({
                "home_team": home_team,
                "away_team": away_team,
                "score": f"{home_score}-{away_score}",
                "minute": display_minute,
                "status": match_status,
                "league": league_name,
                "is_live": match_status == "LIVE"
            })
            
        except Exception as e:
            print(f"⚠️ Match processing warning: {e}")
            continue
    
    return processed_matches

# -------------------------
# SIMPLIFIED FOOTBALL AI
# -------------------------
class FootballAI:
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
            "psg": {"strength": 90, "style": "attacking"}
        }
    
    def get_response(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'matches', 'scores']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api']):
            return hit_counter.get_hit_stats() + "\n" + api_cache.get_cache_stats()
        
        elif any(word in message_lower for word in ['predict', 'prediction']):
            return self.handle_prediction(message_lower)
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "👋 Hello! I'm Football AI with Live Match Updates! ⚽\n\nTry: 'live matches' or 'hit stats'"
        
        else:
            return "🤖 I can show you:\n• Live matches & scores\n• API hit statistics\n• Match predictions\n\nTry: 'live matches' or 'hit counter'"

    def handle_live_matches(self):
        raw_matches = get_optimized_live_matches()
        matches = process_match_data(raw_matches)
        
        if not matches:
            return "⏳ No live matches found right now.\n\nTry again in a few minutes! 🔄"
        
        response = "🔴 **LIVE FOOTBALL MATCHES** ⚽\n\n"
        
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
                response += f"• {match['home_team']} {match['score']} {match['away_team']} {icon} {match['minute']}\n"
            response += "\n"
        
        response += f"🔥 API Hits Today: {hit_counter.daily_hits}/100\n"
        response += f"💾 Using: {'LIVE DATA' if raw_matches and raw_matches[0].get('match_hometeam_name') != 'Manchester City' else 'SAMPLE DATA'}"
        
        return response

    def handle_prediction(self, message):
        teams = []
        for team in self.team_data:
            if team in message:
                teams.append(team)
        
        if len(teams) >= 2:
            return self.generate_prediction(teams[0], teams[1])
        else:
            return "Please specify two teams for prediction. Example: 'Predict Manchester City vs Liverpool'"

    def generate_prediction(self, team1, team2):
        team1_data = self.team_data.get(team1, {"strength": 80})
        team2_data = self.team_data.get(team2, {"strength": 80})
        
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

# Initialize AI
football_ai = FootballAI()

# -------------------------
# TELEGRAM BOT HANDLERS
# -------------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
🤖 **FOOTBALL LIVE BOT** ⚽

🔥 **Now with GLOBAL HIT COUNTER!**

I provide:
• 🔴 Real-time live matches
• 📊 API hit statistics  
• 🎯 Match predictions
• 💾 Smart caching

⚡ **Commands:**
/live - Live matches
/hits - Hit counter stats
/predict - Match predictions
/help - Help guide

💬 **Or chat naturally:**
"show me live matches"
"hit statistics"
"predict man city vs liverpool"

🚀 **Optimized for API limits!**
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

@bot.message_handler(commands=['hits', 'stats'])
def send_hit_stats(message):
    try:
        stats = hit_counter.get_hit_stats() + "\n" + api_cache.get_cache_stats()
        bot.reply_to(message, stats, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def send_predict_help(message):
    help_text = """
🔮 **MATCH PREDICTIONS**

Ask me like:
• "Predict Manchester City vs Liverpool"
• "Who will win Barcelona vs Real Madrid?"
• "Arsenal vs Chelsea prediction"

I'll analyze team strengths and give you probabilities! 📊
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
🤖 **FOOTBALL LIVE BOT HELP**

⚡ **QUICK COMMANDS:**
/live - Get current live matches
/hits - API hit counter statistics  
/predict - Match predictions
/help - This help message

💬 **CHAT EXAMPLES:**
• "Show me live matches"
• "Hit counter stats"
• "Predict Man City vs Liverpool"
• "How many API calls today?"

🎯 **FEATURES:**
• Real-time live scores
• Global hit counter
• Smart API caching
• Match predictions
• 5-minute cache updates

🔥 **HIT COUNTER:**
• Tracks all API calls
• Shows daily usage (100 limit)
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
# AUTO UPDATER WITH HIT PROTECTION
# -------------------------
def auto_updater():
    """Auto-update matches with hit protection"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Auto-update check...")
            
            # Check if we can make API call
            can_make, reason = hit_counter.can_make_request()
            
            if not can_make:
                print(f"⏸️ Auto-update skipped: {reason}")
                wait_time = 300  # Wait 5 minutes
            else:
                # Only update if cache is expired
                if not api_cache.is_cache_valid("live_matches"):
                    print("💾 Updating cache...")
                    get_optimized_live_matches()
                else:
                    print("💾 Cache still fresh")
                
                # Smart wait time based on usage
                if hit_counter.daily_hits >= 80:
                    wait_time = 600  # 10 minutes if high usage
                elif hit_counter.daily_hits >= 50:
                    wait_time = 300  # 5 minutes if medium usage
                else:
                    wait_time = 180  # 3 minutes if low usage
            
            print(f"⏰ Next update in {wait_time} seconds...")
            time.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Auto-updater error: {e}")
            time.sleep(300)

# -------------------------
# STARTUP FUNCTION
# -------------------------
def start_bot():
    """Start the bot"""
    try:
        print("🚀 Starting Football Live Bot with Global Hit Counter...")
        
        # Start auto-updater
        updater_thread = threading.Thread(target=auto_updater, daemon=True)
        updater_thread.start()
        print("✅ Auto-updater started!")
        
        # Test API
        print("🔍 Testing API connection...")
        test_matches = get_optimized_live_matches()
        print(f"🔍 Initial load: {len(test_matches)} matches")
        
        # Send startup message
        startup_msg = f"""
🤖 **FOOTBALL LIVE BOT STARTED!**

✅ **Features Active:**
• Global Hit Counter
• Live Match Updates
• Smart Caching
• API Limit Protection

🔥 **Hit Counter Ready**
📊 Today's Hits: {hit_counter.daily_hits}/100
💾 Cache System: Active

🕒 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🌐 **Mode:** {'WEBHOOK' if USE_WEBHOOK else 'POLLING'}

🚀 **Bot is live and tracking API hits!**
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
