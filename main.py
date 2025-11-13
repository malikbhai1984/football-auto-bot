import os
import requests
import telebot
import time
from datetime import datetime, timedelta
import threading
from dotenv import load_dotenv

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
print("🎯 Starting Complete Football Matches Bot...")

# API Configuration
API_FOOTBALL_URL = "https://apiv3.apifootball.com"

# -------------------------
# Global Hit Counter
# -------------------------
class GlobalHitCounter:
    def __init__(self):
        self.total_hits = 0
        self.daily_hits = 0
        self.hourly_hits = 0
        self.last_hit_time = None
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
        
        print(f"🔥 API HIT #{self.total_hits} at {current_time.strftime('%H:%M:%S')}")
        print(f"📊 Today: {self.daily_hits}/100 | This Hour: {self.hourly_hits}")
        
    def get_hit_stats(self):
        """Get comprehensive hit statistics"""
        now = datetime.now()
        
        # Calculate hits per minute
        hits_per_minute = self.hourly_hits / 60
        
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
    
    # European Competitions
    "149": {"name": "Champions League", "priority": 1, "type": "european", "emoji": "⭐"},
    "150": {"name": "Europa League", "priority": 2, "type": "european", "emoji": "🌍"},
    "151": {"name": "Conference League", "priority": 3, "type": "european", "emoji": "🔵"},
    
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
    "128": {"name": "International Friendlies", "priority": 3, "type": "international", "emoji": "🤝"},
}

def get_league_name(league_id):
    """Get league name from ID"""
    league_info = LEAGUE_CONFIG.get(str(league_id))
    if league_info:
        return f"{league_info['emoji']} {league_info['name']}"
    return f"⚽ League {league_id}"

# -------------------------
# API-FOOTBALL HTTP CLIENT
# -------------------------
def fetch_api_football_matches(match_type="today"):
    """Fetch matches from API-Football HTTP API"""
    
    # Record the hit
    hit_counter.record_hit()
    
    # Check if we can make the request
    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        print(f"🚫 API-Football Call Blocked: {reason}")
        return []
    
    try:
        if match_type == "today":
            # Fetch today's matches
            today = datetime.now().strftime("%Y-%m-%d")
            url = f"{API_FOOTBALL_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
        elif match_type == "live":
            # Fetch live matches
            url = f"{API_FOOTBALL_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
        else:
            url = f"{API_FOOTBALL_URL}/?action=get_events&APIkey={API_KEY}"
        
        print(f"📡 Fetching from API-Football...")
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
                print(f"✅ API-Football: Found {len(data)} matches")
                
                # Add league names to matches
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
                    match.setdefault("match_date", datetime.now().strftime("%Y-%m-%d"))
                    
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
                "raw_data": match  # Keep original data for analysis
            })
            
        except Exception as e:
            print(f"⚠️ Match processing warning: {e}")
            continue
    
    return processed_matches

# -------------------------
# ENHANCED FOOTBALL AI
# -------------------------
class FootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking"},
            "liverpool": {"strength": 92, "style": "high press"},
            "arsenal": {"strength": 90, "style": "possession"},
            "chelsea": {"strength": 87, "style": "transition"},
            "tottenham": {"strength": 86, "style": "attacking"},
            "manchester united": {"strength": 88, "style": "counter attack"},
            "newcastle": {"strength": 85, "style": "physical"},
            "brighton": {"strength": 84, "style": "possession"},
            "west ham": {"strength": 83, "style": "counter attack"},
            "crystal palace": {"strength": 82, "style": "defensive"},
            
            "real madrid": {"strength": 94, "style": "experienced"},
            "barcelona": {"strength": 92, "style": "possession"},
            "atletico madrid": {"strength": 89, "style": "defensive"},
            "sevilla": {"strength": 85, "style": "technical"},
            "valencia": {"strength": 83, "style": "attacking"},
            
            "bayern munich": {"strength": 93, "style": "dominant"},
            "borussia dortmund": {"strength": 88, "style": "attacking"},
            "rb leipzig": {"strength": 86, "style": "pressing"},
            "bayer leverkusen": {"strength": 87, "style": "attacking"},
            
            "psg": {"strength": 91, "style": "attacking"},
            "monaco": {"strength": 84, "style": "offensive"},
            "marseille": {"strength": 83, "style": "aggressive"},
            
            "ac milan": {"strength": 89, "style": "technical"},
            "inter": {"strength": 89, "style": "counter attack"},
            "juventus": {"strength": 88, "style": "defensive"},
            "napoli": {"strength": 87, "style": "attacking"},
            "roma": {"strength": 86, "style": "tactical"},
            "lazio": {"strength": 85, "style": "counter attack"},
            "atalanta": {"strength": 84, "style": "attacking"},
            
            "benfica": {"strength": 86, "style": "attacking"},
            "porto": {"strength": 85, "style": "dominant"},
            "sporting": {"strength": 84, "style": "possession"},
            
            "ajax": {"strength": 84, "style": "youthful"},
            "feyenoord": {"strength": 83, "style": "attacking"},
            "psv": {"strength": 83, "style": "offensive"},
            
            "celtic": {"strength": 82, "style": "dominant"},
            "rangers": {"strength": 82, "style": "physical"},
            
            "brazil": {"strength": 96, "style": "samba"},
            "argentina": {"strength": 94, "style": "technical"},
            "france": {"strength": 95, "style": "balanced"},
            "germany": {"strength": 92, "style": "efficient"},
            "england": {"strength": 93, "style": "attacking"},
            "spain": {"strength": 92, "style": "possession"},
            "portugal": {"strength": 91, "style": "technical"},
            "netherlands": {"strength": 90, "style": "total football"},
            "italy": {"strength": 91, "style": "defensive"},
            "croatia": {"strength": 88, "style": "technical"},
        }
    
    def get_response(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'matches', 'scores']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['today', 'aaj', 'aj', 'upcoming']):
            return self.handle_todays_matches()
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api']):
            return hit_counter.get_hit_stats()
        
        elif any(word in message_lower for word in ['predict', 'prediction']):
            return self.handle_prediction(message_lower)
        
        elif any(word in message_lower for word in ['team', 'search']):
            return self.handle_team_search(message_lower)
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "👋 Hello! I'm Complete Football Matches AI! ⚽\n\n📅 **Today's matches with schedule**\n🔴 **Live scores updates**\n🎯 **Match predictions**\n🔍 **Team search**\n\nTry: 'today matches', 'live scores', or 'predict man city vs liverpool'"
        
        else:
            return self.handle_team_specific_query(message_lower)

    def handle_todays_matches(self):
        """Handle today's matches with schedule"""
        raw_matches = fetch_api_football_matches("today")
        matches = process_match_data(raw_matches)
        
        if not matches:
            return "❌ آج کے لیے کوئی میچ نہیں ہیں۔\n\nNo matches found for today."
        
        response = f"📅 **آج کے فٹ بال میچز - Today's Football Matches**\n\n"
        response += f"⏰ Last Updated: {datetime.now().strftime('%I:%M %p')}\n\n"
        
        # Separate live and upcoming matches
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if m['is_upcoming']]
        
        if live_matches:
            response += "🔴 **لائیو میچز - LIVE MATCHES**\n"
            for match in live_matches[:8]:  # Show max 8 live matches
                response += f"{match['status_emoji']} {match['home_team']} {match['score']} {match['away_team']} - {match['minute']}\n"
                response += f"   🏆 {match['league']}\n\n"
        
        if upcoming_matches:
            response += "🕒 **آنے والے میچز - UPCOMING MATCHES**\n"
            
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
                    response += f"• {match['home_team']} vs {match['away_team']}\n"
                    response += f"  🏆 {match['league']}\n"
        
        response += f"\n📊 **خلاصہ:** {len(live_matches)} لائیو, {len(upcoming_matches)} آنے والے\n"
        response += f"**Summary:** {len(live_matches)} live, {len(upcoming_matches)} upcoming\n"
        response += f"🔥 API Hits Today: {hit_counter.daily_hits}/100"
        
        return response

    def handle_live_matches(self):
        """Handle live matches only"""
        raw_matches = fetch_api_football_matches("live")
        if not raw_matches:
            # Fallback to today's matches and filter live ones
            raw_matches = fetch_api_football_matches("today")
        
        matches = [m for m in process_match_data(raw_matches) if m['is_live']]
        
        if not matches:
            return "🔴 فی الحال کوئی لائیو میچ نہیں چل رہا۔\n\nNo live matches at the moment."
        
        response = "🔴 **لائیو فٹ بال میچز - LIVE FOOTBALL MATCHES**\n\n"
        
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
                raw_matches = fetch_api_football_matches("today")
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

    def handle_team_specific_query(self, message):
        """Handle team-specific queries"""
        for team in self.team_data:
            if team in message.lower():
                # Search in today's matches
                raw_matches = fetch_api_football_matches("today")
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
        
        # Default response for unrecognized queries
        return "🤖 **COMPLETE FOOTBALL MATCHES AI** ⚽\n\n📅 **Today's matches with schedule**\n🔴 **Live scores updates**\n🎯 **Match predictions**\n🔍 **Team search**\n\nTry: 'today matches', 'live scores', 'manchester city', or 'predict real madrid vs barcelona'"

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

# Initialize AI
football_ai = FootballAI()

# -------------------------
# TELEGRAM BOT HANDLERS
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 **COMPLETE FOOTBALL MATCHES BOT** ⚽

📅 **Today's all football matches**
🔴 **Live scores with real-time updates**
🎯 **Match predictions & analysis**
🔍 **Team search functionality**
📊 **API usage statistics**

⚡ **Commands:**
/today - Today's matches (Live + Upcoming)
/live - Live matches only
/upcoming - Upcoming matches
/predict - Match predictions
/search - Team search
/hits - API hit statistics
/help - This help message

💬 **Natural Chat:**
"today matches"
"live scores" 
"manchester city"
"predict barcelona vs real madrid"
"api stats"

🚀 **Get started with /today to see today's matches!**
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['today'])
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
        # Use today's matches but focus on upcoming
        raw_matches = fetch_api_football_matches("today")
        matches = [m for m in process_match_data(raw_matches) if m['is_upcoming']]
        
        if not matches:
            response = "🕒 No upcoming matches found for today."
        else:
            response = "🕒 **UPCOMING MATCHES TODAY**\n\n"
            
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
                    response += f"• {match['home_team']} vs {match['away_team']} - {match['match_time']}\n"
                response += "\n"
            
            response += f"📊 Total upcoming matches: {len(matches)}"
        
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['search'])
def send_search_help(message):
    help_text = """
🔍 **TEAM SEARCH**

Search for matches by team name:

**Examples:**
• "manchester city"
• "real madrid match"
• "barcelona"
• "bayern munich"
• "liverpool"

I'll show you today's matches for that team! 🔎
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
🎯 **MATCH PREDICTIONS**

Get match predictions by specifying two teams:

**Examples:**
• "predict manchester city vs liverpool"
• "barcelona vs real madrid prediction"
• "who will win brazil vs argentina"

I'll analyze team strengths and give you probabilities! 📊
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
# AUTO UPDATER
# -------------------------
def auto_updater():
    """Auto-update matches periodically"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Auto-update check...")
            
            # Check if we can make API call
            can_make, reason = hit_counter.can_make_request()
            
            if can_make:
                matches = fetch_api_football_matches("today")
                print(f"✅ Auto-update: {len(matches)} matches cached")
            else:
                print(f"⏸️ Auto-update skipped: {reason}")
            
            # Smart wait time based on API usage
            if hit_counter.daily_hits >= 80:
                wait_time = 600  # 10 minutes if high usage
            elif hit_counter.daily_hits >= 50:
                wait_time = 300  # 5 minutes if medium usage
            else:
                wait_time = 120  # 2 minutes if low usage
            
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
        print("🚀 Starting Complete Football Matches Bot...")
        
        # Start auto-updater in background
        updater_thread = threading.Thread(target=auto_updater, daemon=True)
        updater_thread.start()
        print("✅ Auto-Updater started!")
        
        # Initial API test
        print("🔍 Testing API connections...")
        test_matches = fetch_api_football_matches("today")
        print(f"✅ Initial load: {len(test_matches)} matches")
        
        # Send startup message
        startup_msg = f"""
🤖 **COMPLETE FOOTBALL BOT STARTED!**

✅ **System Active:**
• Bot: Ready
• Matches Loaded: {len(test_matches)}
• API System: Active
• Auto-Updater: Running

📊 **Initial Status:**
• Live Matches: {len([m for m in process_match_data(test_matches) if m['is_live']])}
• Upcoming Matches: {len([m for m in process_match_data(test_matches) if m['is_upcoming']])}
• API Hits: {hit_counter.daily_hits}/100

🕒 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🚀 **Ready to serve football updates!**
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
