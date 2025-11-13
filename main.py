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
    raise ValueError("BOT_TOKEN or OWNER_CHAT_ID missing!")

bot = telebot.TeleBot(BOT_TOKEN)

print("Starting Today's Football Matches Bot...")

# API Configuration
API_FOOTBALL_URL = "https://apiv3.apifootball.com"

# -------------------------
# Global Hit Counter
# -------------------------
class GlobalHitCounter:
    def __init__(self):
        self.total_hits = 0
        self.daily_hits = 0
        self.last_hit_time = None
        self.last_reset = datetime.now()
        
    def record_hit(self):
        current_time = datetime.now()
        
        # Reset daily counter if new day
        if current_time.date() > self.last_reset.date():
            self.daily_hits = 0
            self.last_reset = current_time
        
        self.total_hits += 1
        self.daily_hits += 1
        self.last_hit_time = current_time
        
        print(f"API HIT #{self.total_hits} at {current_time.strftime('%H:%M:%S')}")
        print(f"Today: {self.daily_hits}/100")
        
    def can_make_request(self):
        if self.daily_hits >= 100:
            return False, "Daily limit reached"
        return True, "OK"
    
    def get_hit_stats(self):
        remaining_daily = max(0, 100 - self.daily_hits)
        
        stats = f"""
API HIT COUNTER STATUS

Current Usage:
• Total Hits: {self.total_hits}
• Today's Hits: {self.daily_hits}/100
• Remaining: {remaining_daily} calls

Last Hit: {self.last_hit_time.strftime('%H:%M:%S') if self.last_hit_time else 'Never'}
"""
        return stats

hit_counter = GlobalHitCounter()

# -------------------------
# League Configuration
# -------------------------
LEAGUE_CONFIG = {
    "152": {"name": "Premier League", "emoji": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "302": {"name": "La Liga", "emoji": "🇪🇸"},
    "207": {"name": "Serie A", "emoji": "🇮🇹"},
    "168": {"name": "Bundesliga", "emoji": "🇩🇪"},
    "176": {"name": "Ligue 1", "emoji": "🇫🇷"},
    "262": {"name": "Champions League", "emoji": "⭐"},
    "263": {"name": "Europa League", "emoji": "🌍"},
}

def get_league_name(league_id):
    league_info = LEAGUE_CONFIG.get(str(league_id))
    if league_info:
        return f"{league_info['emoji']} {league_info['name']}"
    return f"League {league_id}"

# -------------------------
# API Functions
# -------------------------
def fetch_todays_matches():
    """Fetch today's matches from API-Football"""
    
    hit_counter.record_hit()
    
    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        print(f"API Call Blocked: {reason}")
        return []
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"{API_FOOTBALL_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
        
        print(f"Fetching today's matches...")
        print(f"URL: {url.replace(API_KEY, 'API_KEY_HIDDEN')}")
        
        response = requests.get(url, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Type: {type(data)}")
            
            if isinstance(data, list):
                print(f"Found {len(data)} matches")
                
                processed_matches = []
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                    
                    # Ensure all required fields
                    match.setdefault("match_hometeam_score", "0")
                    match.setdefault("match_awayteam_score", "0")
                    match.setdefault("match_status", "Upcoming")
                    match.setdefault("match_time", "00:00")
                    match.setdefault("match_date", today)
                    
                    processed_matches.append(match)
                
                return processed_matches
            else:
                print("Invalid response format")
                return []
        else:
            print(f"HTTP Error {response.status_code}")
            return []
            
    except Exception as e:
        print(f"API fetch error: {str(e)}")
        return []

def fetch_live_matches():
    """Fetch live matches only"""
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
# Match Processor
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
            
            # Determine match status
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
            
            # Format match time
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
                "is_live": match_status == "LIVE",
                "is_upcoming": match_status == "UPCOMING",
                "status_emoji": status_emoji,
            })
            
        except Exception as e:
            print(f"Match processing warning: {e}")
            continue
    
    return processed_matches

# -------------------------
# Football AI
# -------------------------
class FootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95},
            "liverpool": {"strength": 92},
            "arsenal": {"strength": 90},
            "real madrid": {"strength": 94},
            "barcelona": {"strength": 92},
            "bayern munich": {"strength": 93},
            "psg": {"strength": 91},
            "manchester united": {"strength": 88},
            "chelsea": {"strength": 87},
        }
    
    def get_response(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'matches', 'scores']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['today', 'aaj', 'aj', 'upcoming']):
            return self.handle_todays_matches()
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats']):
            return hit_counter.get_hit_stats()
        
        elif any(word in message_lower for word in ['predict']):
            return self.handle_prediction(message_lower)
        
        elif any(word in message_lower for word in ['team', 'search']):
            return self.handle_team_search(message_lower)
        
        else:
            return self.get_help_message()

    def handle_todays_matches(self):
        """Handle today's matches"""
        raw_matches = fetch_todays_matches()
        matches = process_match_data(raw_matches)
        
        if not matches:
            return "No matches found for today."
        
        response = f"📅 Today's Football Matches\n\n"
        response += f"⏰ Last Updated: {datetime.now().strftime('%I:%M %p')}\n\n"
        
        # Separate live and upcoming matches
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if m['is_upcoming']]
        
        if live_matches:
            response += "🔴 LIVE MATCHES\n"
            for match in live_matches[:8]:
                response += f"{match['status_emoji']} {match['home_team']} {match['score']} {match['away_team']} - {match['minute']}\n"
            response += "\n"
        
        if upcoming_matches:
            response += "🕒 UPCOMING MATCHES\n"
            
            # Group by league
            leagues = {}
            for match in upcoming_matches:
                league = match['league']
                if league not in leagues:
                    leagues[league] = []
                leagues[league].append(match)
            
            for league, league_matches in leagues.items():
                response += f"\n{league}\n"
                for match in league_matches:
                    response += f"• {match['home_team']} vs {match['away_team']} - {match['match_time']}\n"
        
        response += f"\n📊 Summary: {len(live_matches)} Live, {len(upcoming_matches)} Upcoming"
        response += f"\n🔥 API Hits Today: {hit_counter.daily_hits}/100"
        
        return response

    def handle_live_matches(self):
        """Handle live matches only"""
        raw_matches = fetch_live_matches()
        if not raw_matches:
            raw_matches = fetch_todays_matches()
        
        matches = [m for m in process_match_data(raw_matches) if m['is_live']]
        
        if not matches:
            return "No live matches at the moment."
        
        response = "🔴 LIVE FOOTBALL MATCHES\n\n"
        
        for match in matches:
            response += f"{match['status_emoji']} {match['home_team']} {match['score']} {match['away_team']} - {match['minute']}\n"
            response += f"   {match['league']}\n\n"
        
        response += f"🔥 API Hits Today: {hit_counter.daily_hits}/100"
        
        return response

    def handle_team_search(self, message):
        """Handle team-specific searches"""
        for team in self.team_data:
            if team in message.lower():
                raw_matches = fetch_todays_matches()
                team_matches = []
                
                for match in raw_matches:
                    home_team = match.get("match_hometeam_name", "").lower()
                    away_team = match.get("match_awayteam_name", "").lower()
                    
                    if team in home_team or team in away_team:
                        team_matches.append(match)
                
                if team_matches:
                    response = f"🔍 Matches for {team.title()}\n\n"
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
                        
                        response += f"{emoji} {home_team} vs {away_team}\n"
                        response += f"   Score: {score} | {status_text}\n"
                        response += f"   League: {league}\n\n"
                    
                    return response
                else:
                    return f"No matches found for {team.title()} today."
        
        return "Please enter a valid team name."

    def handle_prediction(self, message):
        teams = []
        for team in self.team_data:
            if team in message.lower():
                teams.append(team)
        
        if len(teams) >= 2:
            home_team, away_team = teams[0], teams[1]
            return self.generate_prediction(home_team, away_team)
        else:
            return "Please specify two teams. Example: 'predict man city vs liverpool'"

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
🎯 PREDICTION: {team1.upper()} vs {team2.upper()}

Probabilities:
• {team1.title()}: {prob1:.1f}%
• {team2.title()}: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%

Most Likely: {winner}

Expected: Competitive match!
"""

    def get_help_message(self):
        return """
🤖 Today's Football Matches Bot

Commands:
/today - Today's matches
/live - Live matches
/upcoming - Upcoming matches
/predict - Match predictions
/search - Team search
/hits - API hit counter

Examples:
"today matches"
"live scores" 
"manchester united"
"predict man city vs liverpool"
"""

# Initialize AI
football_ai = FootballAI()

# -------------------------
# Telegram Bot Handlers
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 Today's Football Matches Bot ⚽

See all of today's football matches with live scores and schedules!

Commands:
/today - Today's all matches
/live - Live matches only  
/upcoming - Upcoming matches
/predict - Match predictions
/search - Team search
/hits - API hit counter

Just type "today matches" to get started!
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['today'])
def send_todays_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

@bot.message_handler(commands=['live'])
def send_live_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_live_matches()
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

@bot.message_handler(commands=['upcoming'])
def send_upcoming_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()
        bot.reply_to(message, response)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

@bot.message_handler(commands=['search'])
def send_search_help(message):
    help_text = """
🔍 Team Search

Examples:
"manchester city"
"liverpool match" 
"real madrid"
"barcelona"

I'll show you today's matches for that team!
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['hits'])
def send_hit_stats(message):
    try:
        stats = hit_counter.get_hit_stats()
        bot.reply_to(message, stats)
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def send_predict_help(message):
    help_text = """
🎯 Match Prediction

Examples:
"predict man city vs liverpool"
"prediction brazil argentina"

I'll analyze team strengths and give you probabilities!
"""
    bot.reply_to(message, help_text)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        user_message = message.text
        print(f"Message: {user_message}")
        
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.get_response(user_message)
        bot.reply_to(message, response)
        
    except Exception as e:
        print(f"Message error: {e}")
        bot.reply_to(message, "Sorry, error occurred. Please try again!")

# -------------------------
# Auto Updater
# -------------------------
def auto_updater():
    """Auto-update matches periodically"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"Auto-update check at {current_time}")
            
            can_make, reason = hit_counter.can_make_request()
            if can_make:
                raw_matches = fetch_todays_matches()
                print(f"Auto-update: {len(raw_matches)} matches")
            else:
                print(f"Auto-update skipped: {reason}")
            
            time.sleep(600)  # 10 minutes
            
        except Exception as e:
            print(f"Auto-updater error: {e}")
            time.sleep(300)

# -------------------------
# Startup Function
# -------------------------
def start_bot():
    """Start the bot"""
    try:
        print("Starting Football Bot...")
        
        # Start auto-updater
        updater_thread = threading.Thread(target=auto_updater, daemon=True)
        updater_thread.start()
        print("Auto-Updater started!")
        
        # Initial load
        raw_matches = fetch_todays_matches()
        print(f"Initial load: {len(raw_matches)} matches")
        
        # Send startup message
        startup_msg = f"""
🤖 Football Bot Started!

• Today's matches loaded: {len(raw_matches)}
• API Hits Today: {hit_counter.daily_hits}/100
• Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}

Ready to show today's matches!
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg)
        
        # Start bot polling
        print("Starting in polling mode...")
        bot.infinity_polling()
            
    except Exception as e:
        print(f"Startup error: {e}")
        time.sleep(10)
        start_bot()

if __name__ == '__main__':
    start_bot()
