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
import logging

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

print(f"🎯 Starting Today's Football Matches Bot...")

# ✅ API CONFIGURATION
API_FOOTBALL_URL = "https://apiv3.apifootball.com"

# -------------------------
# MATCH MANAGER FOR TODAY'S MATCHES
# -------------------------
class TodayMatchesManager:
    def __init__(self):
        self.live_matches = []
        self.upcoming_matches = []
        self.today_matches = []
        self.last_update = None
        
    def update_matches(self, matches):
        """Update all matches and categorize them"""
        current_time = datetime.now()
        self.last_update = current_time
        
        self.live_matches = []
        self.upcoming_matches = []
        self.today_matches = matches
        
        for match in matches:
            match_status = match.get("match_status", "")
            match_time = match.get("match_time", "")
            match_date = match.get("match_date", "")
            
            # Categorize matches
            if match_status == "Live" or match_status.isdigit():
                self.live_matches.append(match)
            elif match_status in ["Upcoming", "Pre-match"] or self.is_future_match(match_date, match_time):
                self.upcoming_matches.append(match)
        
        print(f"✅ Matches updated: {len(self.live_matches)} live, {len(self.upcoming_matches)} upcoming, {len(self.today_matches)} total")
    
    def is_future_match(self, match_date, match_time):
        """Check if match is in future"""
        try:
            if not match_date or not match_time:
                return False
            
            # Parse match datetime
            match_datetime_str = f"{match_date} {match_time}"
            match_datetime = datetime.strptime(match_datetime_str, "%Y-%m-%d %H:%M:%S")
            
            return match_datetime > datetime.now()
        except:
            return False
    
    def get_today_matches_by_league(self):
        """Get today's matches grouped by league"""
        leagues = {}
        
        for match in self.today_matches:
            league_id = match.get("league_id", "unknown")
            league_name = match.get("league_name", f"League {league_id}")
            
            if league_name not in leagues:
                leagues[league_name] = []
            leagues[league_name].append(match)
        
        return leagues
    
    def get_upcoming_matches_schedule(self):
        """Get schedule of upcoming matches"""
        schedule = {}
        
        for match in self.upcoming_matches:
            match_time = match.get("match_time", "00:00")
            hour = match_time.split(':')[0] if match_time else "00"
            
            if hour not in schedule:
                schedule[hour] = []
            schedule[hour].append(match)
        
        return schedule

# Initialize Match Manager
match_manager = TodayMatchesManager()

# -------------------------
# GLOBAL HIT COUNTER
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
🔥 **GLOBAL HIT COUNTER STATUS**

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
# COMPREHENSIVE LEAGUE CONFIGURATION
# -------------------------
LEAGUE_CONFIG = {
    # Major European Leagues
    "152": {"name": "Premier League", "priority": 1, "type": "domestic", "emoji": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "302": {"name": "La Liga", "priority": 1, "type": "domestic", "emoji": "🇪🇸"},
    "207": {"name": "Serie A", "priority": 1, "type": "domestic", "emoji": "🇮🇹"},
    "168": {"name": "Bundesliga", "priority": 1, "type": "domestic", "emoji": "🇩🇪"},
    "176": {"name": "Ligue 1", "priority": 1, "type": "domestic", "emoji": "🇫🇷"},
    "262": {"name": "UEFA Champions League", "priority": 1, "type": "european", "emoji": "⭐"},
    "263": {"name": "UEFA Europa League", "priority": 2, "type": "european", "emoji": "🌍"},
    "264": {"name": "UEFA Conference League", "priority": 2, "type": "european", "emoji": "🔵"},
    
    # World Cup Qualifiers
    "5": {"name": "World Cup Qualifiers (UEFA)", "priority": 1, "type": "worldcup", "emoji": "🌎"},
    "6": {"name": "World Cup Qualifiers (AFC)", "priority": 2, "type": "worldcup", "emoji": "🌏"},
    "7": {"name": "World Cup Qualifiers (CONMEBOL)", "priority": 1, "type": "worldcup", "emoji": "🇧🇷"},
    "8": {"name": "World Cup Qualifiers (CONCACAF)", "priority": 2, "type": "worldcup", "emoji": "🇺🇸"},
    "9": {"name": "World Cup Qualifiers (CAF)", "priority": 2, "type": "worldcup", "emoji": "🇿🇦"},
    
    # Other Important Leagues
    "175": {"name": "Saudi Pro League", "priority": 2, "type": "domestic", "emoji": "🇸🇦"},
    "344": {"name": "Major League Soccer", "priority": 2, "type": "domestic", "emoji": "🇺🇸"},
    "127": {"name": "UEFA Euro Qualifiers", "priority": 1, "type": "european", "emoji": "🇪🇺"},
}

def get_league_name(league_id):
    """Get league name from ID"""
    league_info = LEAGUE_CONFIG.get(str(league_id))
    if league_info:
        return f"{league_info['emoji']} {league_info['name']}"
    return f"⚽ League {league_id}"

# -------------------------
# API-FOOTBALL HTTP CLIENT (ENHANCED FOR TODAY'S MATCHES)
# -------------------------
def fetch_todays_matches():
    """Fetch today's matches from API-Football"""
    
    # Record the hit
    hit_info = hit_counter.record_hit()
    
    # Check if we can make the request
    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        print(f"🚫 API-Football Call Blocked: {reason}")
        return []
    
    try:
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Fetch matches for today
        url = f"{API_FOOTBALL_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
        
        print(f"📡 Fetching today's matches from API-Football...")
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
                print(f"✅ Today's Matches: Found {len(data)} matches")
                
                # Add league names and process match data
                processed_matches = []
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                    match["source"] = "api_football"
                    
                    # Ensure all required fields
                    match.setdefault("match_hometeam_score", "0")
                    match.setdefault("match_awayteam_score", "0")
                    match.setdefault("match_status", "Upcoming")
                    match.setdefault("match_time", "00:00")
                    match.setdefault("match_date", today)
                    
                    processed_matches.append(match)
                
                return processed_matches
            else:
                print(f"❌ API-Football: Invalid response format")
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

def fetch_live_matches_only():
    """Fetch only live matches"""
    try:
        url = f"{API_FOOTBALL_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
        
        hit_counter.record_hit()
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                return data
        return []
    except:
        return []

# -------------------------
# MATCH PROCESSOR (ENHANCED)
# -------------------------
def process_match_data(matches):
    """Process raw match data for display"""
    if not matches:
        return []
    
    processed_matches = []
    for match in matches:
        try:
            home_team = match.get("match_hometeam_name", "Unknown Team")
            away_team = match.get("match_awayteam_name", "Unknown Team")
            home_score = match.get("match_hometeam_score", "0")
            away_score = match.get("match_awayteam_score", "0")
            minute = match.get("match_status", "0")
            league_name = match.get("league_name", "Unknown League")
            match_time = match.get("match_time", "00:00")
            match_date = match.get("match_date", "")
            
            # Determine match status and emoji
            if minute == "HT":
                match_status = "HALF TIME"
                display_minute = "HT"
                status_emoji = "🔄"
            elif minute == "FT":
                match_status = "FULL TIME"
                display_minute = "FT"
                status_emoji = "🏁"
            elif minute.isdigit():
                match_status = "LIVE"
                display_minute = f"{minute}'"
                status_emoji = "⏱️"
            else:
                match_status = "UPCOMING"
                display_minute = match_time
                status_emoji = "🕒"
            
            # Format match time nicely
            try:
                if match_time and len(match_time) >= 5:
                    time_obj = datetime.strptime(match_time, "%H:%M:%S")
                    formatted_time = time_obj.strftime("%I:%M %p")
                else:
                    formatted_time = match_time
            except:
                formatted_time = match_time
            
            processed_matches.append({
                "home_team": home_team,
                "away_team": away_team,
                "score": f"{home_score}-{away_score}",
                "minute": display_minute,
                "status": match_status,
                "league": league_name,
                "match_time": formatted_time,
                "match_date": match_date,
                "is_live": match_status == "LIVE",
                "is_upcoming": match_status == "UPCOMING",
                "status_emoji": status_emoji,
                "raw_data": match
            })
            
        except Exception as e:
            print(f"⚠️ Match processing warning: {e}")
            continue
    
    return processed_matches

# -------------------------
# ENHANCED FOOTBALL AI FOR TODAY'S MATCHES
# -------------------------
class TodayFootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking"},
            "liverpool": {"strength": 92, "style": "high press"},
            "arsenal": {"strength": 90, "style": "possession"},
            "real madrid": {"strength": 94, "style": "experienced"},
            "barcelona": {"strength": 92, "style": "possession"},
            "bayern munich": {"strength": 93, "style": "dominant"},
            "psg": {"strength": 91, "style": "attacking"},
            "manchester united": {"strength": 88, "style": "transition"},
            "chelsea": {"strength": 87, "style": "possession"},
            "tottenham": {"strength": 86, "style": "attacking"},
            "ac milan": {"strength": 89, "style": "technical"},
            "inter": {"strength": 89, "style": "counter attack"},
            "juventus": {"strength": 88, "style": "defensive"},
            "atletico madrid": {"strength": 89, "style": "defensive"},
            "borussia dortmund": {"strength": 88, "style": "attacking"},
        }
    
    def get_response(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'matches', 'scores']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['today', 'aaj', 'aj', 'upcoming', 'schedule']):
            return self.handle_todays_matches()
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api']):
            return hit_counter.get_hit_stats()
        
        elif any(word in message_lower for word in ['predict', 'prediction']):
            return self.handle_prediction(message_lower)
        
        elif any(word in message_lower for word in ['team', 'search']):
            return self.handle_team_search(message_lower)
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "👋 Hello! I'm Today's Football Matches AI! ⚽\n\n📅 **Today's matches with schedule**\n🔴 **Live scores updates**\n🎯 **Match predictions**\n\nTry: 'today matches', 'live scores', or 'upcoming matches'"
        
        else:
            return self.handle_general_query(message_lower)

    def handle_todays_matches(self):
        """Handle today's matches with schedule"""
        raw_matches = fetch_todays_matches()
        match_manager.update_matches(raw_matches)
        matches = process_match_data(raw_matches)
        
        if not matches:
            return "❌ آج کے لیے کوئی میچ نہیں ہیں۔\n\nNo matches found for today."
        
        response = f"📅 **آج کے فٹ بال میچز - Today's Football Matches**\n\n"
        response += f"⏰ Last Updated: {datetime.now().strftime('%I:%M %p')}\n\n"
        
        # Group by league
        leagues = match_manager.get_today_matches_by_league()
        
        # Separate live and upcoming matches
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if m['is_upcoming']]
        
        if live_matches:
            response += "🔴 **LIVE MATCHES - براہ راست میچز**\n"
            for match in live_matches[:8]:  # Show max 8 live matches
                response += f"{match['status_emoji']} {match['home_team']} {match['score']} {match['away_team']} - {match['minute']}\n"
            response += "\n"
        
        if upcoming_matches:
            response += "🕒 **UPCOMING MATCHES - آنے والے میچز**\n"
            
            # Group by time
            schedule = {}
            for match in upcoming_matches:
                time_key = match['match_time']
                if time_key not in schedule:
                    schedule[time_key] = []
                schedule[time_key].append(match)
            
            # Show matches in time order
            for time_slot in sorted(schedule.keys()):
                response += f"\n🕐 **{time_slot}**\n"
                for match in schedule[time_slot]:
                    response += f"• {match['home_team']} vs {match['away_team']} - {match['league']}\n"
        
        response += f"\n📊 **Summary:** {len(live_matches)} Live, {len(upcoming_matches)} Upcoming, {len(matches)} Total"
        response += f"\n🔥 API Hits Today: {hit_counter.daily_hits}/100"
        
        return response

    def handle_live_matches(self):
        """Handle live matches only"""
        raw_matches = fetch_live_matches_only()
        matches = process_match_data(raw_matches)
        
        if not matches:
            # Try to get from today's matches
            raw_matches = fetch_todays_matches()
            matches = [m for m in process_match_data(raw_matches) if m['is_live']]
            
            if not matches:
                return "🔴 فی الحال کوئی لائیو میچ نہیں چل رہا۔\n\nNo live matches at the moment."
        
        response = "🔴 **LIVE FOOTBALL MATCHES - براہ راست فٹ بال میچز**\n\n"
        
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
                response += f"{match['status_emoji']} {match['home_team']} {match['score']} {match['away_team']} - {match['minute']}\n"
            response += "\n"
        
        response += f"🔥 API Hits Today: {hit_counter.daily_hits}/100"
        
        return response

    def handle_team_search(self, message):
        """Handle team-specific searches"""
        for team in self.team_data:
            if team in message.lower():
                # Search in today's matches
                raw_matches = fetch_todays_matches()
                team_matches = []
                
                for match in raw_matches:
                    home_team = match.get("match_hometeam_name", "").lower()
                    away_team = match.get("match_awayteam_name", "").lower()
                    
                    if team in home_team or team in away_team:
                        team_matches.append(match)
                
                if team_matches:
                    response = f"🔍 **{team.title()} کے آج کے میچز**\n\n"
                    for match in team_matches:
                        home_team = match.get("match_hometeam_name", "Unknown")
                        away_team = match.get("match_awayteam_name", "Unknown")
                        score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                        status = match.get("match_status", "Upcoming")
                        time = match.get("match_time", "00:00")
                        league = match.get("league_name", "Unknown League")
                        
                        if status == "Live" or status.isdigit():
                            status_text = f"LIVE - {status}'"
                            emoji = "🔴"
                        else:
                            status_text = f"At {time}"
                            emoji = "🕒"
                        
                        response += f"{emoji} **{home_team} vs {away_team}**\n"
                        response += f"   📊 {score} | {status_text}\n"
                        response += f"   🏆 {league}\n\n"
                    
                    return response
                else:
                    return f"❌ آج {team.title()} کا کوئی میچ نہیں ہے۔\n\nNo matches found for {team.title()} today."
        
        return "🔍 براہ کرم ٹیم کا صحیح نام درج کریں۔\n\nPlease enter a valid team name."

    def handle_prediction(self, message):
        teams = []
        for team in self.team_data:
            if team in message.lower():
                teams.append(team)
        
        if len(teams) >= 2:
            home_team, away_team = teams[0], teams[1]
            return self.generate_prediction(home_team, away_team)
        else:
            prediction_help = """
🎯 **میچ پیشن گوئی - Match Prediction**

مثال کے طور پر لکھیں:
• "پریڈکٹ مانچسٹر سٹی بمقابلہ لیورپول"
• "پیشن گوئی برازیل بمقابلہ ارجنٹینا"
• "predict man city vs liverpool"

میں ٹیموں کی طاقت کا تجزیہ کر کے آپ کو احتمالات بتاؤں گا! 📊
"""
            return prediction_help

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
🎯 **پیشن گوئی: {team1.upper()} بمقابلہ {team2.upper()}**

📊 **امکانات:**
• {team1.title()}: {prob1:.1f}%
• {team2.title()}: {prob2:.1f}%  
• ڈرا: {draw_prob:.1f}%

🏆 **سب سے زیادہ ممکنہ نتیجہ: {winner}**

⚽ **توقع: دونوں ٹیمیں حملہ آور کھیل کھیلیں گی!**

⚠️ *فٹ بال غیر متوقع ہے - میچ کا لطف اٹھائیں!*
"""

    def handle_general_query(self, message):
        """Handle general queries"""
        if any(word in message for word in ['شکریہ', 'thanks', 'thank you']):
            return "👍 آپ کا شکریہ! مزید معلومات کے لیے پوچھتے رہیں۔\n\nYou're welcome! Ask for more information."
        
        elif any(word in message for word in ['help', 'مدد']):
            return self.get_help_message()
        
        else:
            return self.get_help_message()

    def get_help_message(self):
        """Get help message in Urdu/English"""
        return """
🤖 **آج کے فٹ بال میچز بوٹ - Today's Football Matches Bot**

📅 **آج کے میچز دیکھیں:**
• "آج کے میچز" - Today's matches
• "لائیو میچز" - Live matches  
• "آنے والے میچز" - Upcoming matches

🔍 **ٹیم سرچ:**
• "مانچسٹر سٹی میچ" - Manchester City matches
• "لیورپول سرچ" - Liverpool search

🎯 **پیشن گوئی:**
• "پریڈکٹ ٹیم1 بمقابلہ ٹیم2"
• "پیشن گوئی برازیل ارجنٹینا"

📊 **API معلومات:**
• "ہٹ کاؤنٹر" - Hit counter
• "API اسٹیٹس" - API status

⚽ **Enjoy football matches with real-time updates!**
"""

# Initialize AI
football_ai = TodayFootballAI()

# -------------------------
# TELEGRAM BOT HANDLERS
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 **آج کے فٹ بال میچز بوٹ - Today's Football Matches Bot** ⚽

📅 **آج کے تمام میچز دیکھیں**
🔴 **لائیو اسکورز اپڈیٹس**
🎯 **میچ پیشن گوئی**
🔍 **ٹیم کی سرچ**

🕌 **اردو اور انگریزی دونوں میں بات کریں**

⚡ **کمانڈز:**
/today - آج کے تمام میچز
/live - لائیو میچز
/upcoming - آنے والے میچز
/predict - میچ پیشن گوئی
/search - ٹیم سرچ
/hits - API ہٹ کاؤنٹر

💬 **قدرتی بات چیت:**
"آج کے میچز"
"لائیو اسکورز" 
"مانچسٹر یونائیٹڈ میچ"
"پیشن گوئی برازیل ارجنٹینا"

🚀 **آج کے میچز حاصل کریں!**
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['today', 'aaj', 'aj'])
def send_todays_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['live'])
def send_live_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_live_matches()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['upcoming'])
def send_upcoming_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()  # This shows both live and upcoming
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['search'])
def send_search_help(message):
    help_text = """
🔍 **ٹیم سرچ - Team Search**

مثال کے طور پر لکھیں:
• "مانچسٹر سٹی"
• "لیورپول میچ"
• "برازیل سرچ"
• "realmadrid"

میں آج کے اس ٹیم کے میچز دکھاؤں گا! 🔎
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['hits', 'stats'])
def send_hit_stats(message):
    try:
        stats = hit_counter.get_hit_stats()
        bot.reply_to(message, stats, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def send_predict_help(message):
    help_text = """
🎯 **میچ پیشن گوئی - Match Prediction**

مثال کے طور پر لکھیں:
• "پریڈکٹ مانچسٹر سٹی بمقابلہ لیورپول"
• "پیشن گوئی برازیل بمقابلہ ارجنٹینا"
• "predict man city vs liverpool"

میں ٹیموں کی طاقت کا تجزیہ کر کے آپ کو احتمالات بتاؤں گا! 📊
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
        bot.reply_to(message, "❌ معذرت، غلطی ہوئی۔ براہ کرم دوبارہ کوشش کریں!\n\nSorry, error occurred. Please try again!")

# -------------------------
# AUTO UPDATER
# -------------------------
def auto_updater():
    """Auto-update matches periodically"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Auto-update check...")
            
            # Fetch today's matches to keep cache updated
            can_make, reason = hit_counter.can_make_request()
            if can_make:
                raw_matches = fetch_todays_matches()
                match_manager.update_matches(raw_matches)
                print(f"✅ Auto-update: {len(raw_matches)} matches cached")
            else:
                print(f"⏸️ Auto-update skipped: {reason}")
            
            # Wait 10 minutes between updates
            time.sleep(600)
            
        except Exception as e:
            print(f"❌ Auto-updater error: {e}")
            time.sleep(300)

# -------------------------
# STARTUP FUNCTION
# -------------------------
def start_bot():
    """Start the bot"""
    try:
        print("🚀 Starting Today's Football Matches Bot...")
        
        # Start auto-updater
        updater_thread = threading.Thread(target=auto_updater, daemon=True)
        updater_thread.start()
        print("✅ Auto-Updater started!")
        
        # Initial matches load
        print("🔍 Loading today's matches...")
        raw_matches = fetch_todays_matches()
        match_manager.update_matches(raw_matches)
        print(f"✅ Initial load: {len(raw_matches)} matches")
        
        # Send startup message
        startup_msg = f"""
🤖 **آج کے فٹ بال میچز بوٹ شروع ہو گیا!**

✅ **سسٹم ایکٹو:**
• 📅 آج کے میچز: {len(match_manager.today_matches)}
• 🔴 لائیو میچز: {len(match_manager.live_matches)}
• 🕒 آنے والے میچز: {len(match_manager.upcoming_matches)}

🔥 **ہٹ کاؤنٹر:**
• آج کے ہٹس: {hit_counter.daily_hits}/100
• ٹوٹل ہٹس: {hit_counter.total_hits}

🕒 **وقت:** {datetime.now().strftime('%Y-%m-%d %I:%M %p')}

🚀 **آج کے میچز دیکھنے کے لیے تیار!**
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
        start_bot()

if __name__ == '__main__':
    start_bot()
