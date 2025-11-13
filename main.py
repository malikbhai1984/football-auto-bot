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

# Validate credentials
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN is missing!")
    exit(1)

if not OWNER_CHAT_ID:
    print("❌ ERROR: OWNER_CHAT_ID is missing!")
    exit(1)

# Initialize bot with better error handling
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ Bot initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize bot: {e}")
    exit(1)

print("🚀 Starting Football Matches Bot...")

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
        
        print(f"📊 API HIT #{self.total_hits} | Today: {self.daily_hits}/100")
        
    def can_make_request(self):
        if self.daily_hits >= 100:
            return False, "Daily limit reached"
        return True, "OK"
    
    def get_hit_stats(self):
        remaining_daily = max(0, 100 - self.daily_hits)
        
        stats = f"""
📊 **API Usage Statistics**

• **Total Hits:** {self.total_hits}
• **Today's Hits:** {self.daily_hits}/100
• **Remaining Today:** {remaining_daily}
• **Last Update:** {self.last_hit_time.strftime('%H:%M:%S') if self.last_hit_time else 'Never'}

{'🟢 Safe to continue' if self.daily_hits < 80 else '🟡 Slow down' if self.daily_hits < 95 else '🔴 STOP API CALLS'}
"""
        return stats

hit_counter = GlobalHitCounter()

# -------------------------
# League Configuration
# -------------------------
LEAGUE_CONFIG = {
    "152": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "302": "🇪🇸 La Liga", 
    "207": "🇮🇹 Serie A",
    "168": "🇩🇪 Bundesliga",
    "176": "🇫🇷 Ligue 1",
    "262": "⭐ Champions League",
    "263": "🌍 Europa League",
    "5": "🌎 World Cup Qualifiers",
}

def get_league_name(league_id):
    return LEAGUE_CONFIG.get(str(league_id), f"⚽ League {league_id}")

# -------------------------
# API Functions with Better Error Handling
# -------------------------
def safe_api_call(url, description):
    """Make safe API call with comprehensive error handling"""
    try:
        hit_counter.record_hit()
        
        can_make, reason = hit_counter.can_make_request()
        if not can_make:
            print(f"🚫 API Call Blocked: {reason}")
            return None
        
        print(f"🌐 Fetching {description}...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ HTTP Error {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print("⏰ Request timeout")
        return None
    except requests.exceptions.ConnectionError:
        print("🔌 Connection error")
        return None
    except Exception as e:
        print(f"❌ API error: {e}")
        return None

def fetch_todays_matches():
    """Fetch today's matches from API-Football"""
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{API_FOOTBALL_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
    
    data = safe_api_call(url, "today's matches")
    
    if isinstance(data, list):
        print(f"✅ Found {len(data)} matches today")
        
        # Process matches
        for match in data:
            league_id = match.get("league_id", "")
            match["league_name"] = get_league_name(league_id)
            
            # Ensure required fields
            match.setdefault("match_hometeam_score", "0")
            match.setdefault("match_awayteam_score", "0") 
            match.setdefault("match_status", "Upcoming")
            match.setdefault("match_time", "00:00")
            
        return data
    else:
        print("❌ No matches data received")
        return []

def fetch_live_matches():
    """Fetch live matches only"""
    url = f"{API_FOOTBALL_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
    
    data = safe_api_call(url, "live matches")
    
    if isinstance(data, list):
        print(f"🔴 Found {len(data)} live matches")
        for match in data:
            league_id = match.get("league_id", "")
            match["league_name"] = get_league_name(league_id)
        return data
    else:
        return []

# -------------------------
# Match Processing
# -------------------------
def process_match_data(matches):
    """Process raw match data for display"""
    if not matches:
        return []
    
    processed = []
    for match in matches:
        try:
            home_team = match.get("match_hometeam_name", "TBD")
            away_team = match.get("match_awayteam_name", "TBD")
            home_score = match.get("match_hometeam_score", "0")
            away_score = match.get("match_awayteam_score", "0")
            minute = match.get("match_status", "")
            league_name = match.get("league_name", "Unknown")
            match_time = match.get("match_time", "00:00")
            
            # Determine status
            if minute == "HT":
                status = "🔄 HT"
                display_time = "HT"
            elif minute == "FT":
                status = "🏁 FT" 
                display_time = "FT"
            elif minute.isdigit():
                status = "🔴 LIVE"
                display_time = f"{minute}'"
            else:
                status = "🕒 UPCOMING"
                # Format time
                try:
                    if match_time and len(match_time) >= 5:
                        time_obj = datetime.strptime(match_time, "%H:%M:%S")
                        display_time = time_obj.strftime("%I:%M %p")
                    else:
                        display_time = match_time
                except:
                    display_time = match_time
            
            processed.append({
                "home_team": home_team,
                "away_team": away_team, 
                "score": f"{home_score}-{away_score}",
                "time": display_time,
                "status": status,
                "league": league_name,
                "is_live": minute.isdigit() or minute in ["HT", "1H", "2H"],
                "is_upcoming": not (minute.isdigit() or minute in ["HT", "FT", "1H", "2H"])
            })
            
        except Exception as e:
            print(f"⚠️ Skipping match due to error: {e}")
            continue
    
    return processed

# -------------------------
# Football AI
# -------------------------
class FootballAI:
    def __init__(self):
        self.popular_teams = [
            "manchester city", "liverpool", "arsenal", "chelsea", "tottenham",
            "manchester united", "real madrid", "barcelona", "atletico madrid",
            "bayern munich", "borussia dortmund", "psg", "ac milan", "inter milan",
            "juventus", "napoli", "roma"
        ]
    
    def get_response(self, message):
        message_lower = message.lower().strip()
        
        if any(word in message_lower for word in ['live', 'current', 'score']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['today', 'aaj', 'aj', 'upcoming']):
            return self.handle_todays_matches()
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api']):
            return hit_counter.get_hit_stats()
        
        elif any(word in message_lower for word in ['predict', 'prediction']):
            return self.handle_prediction(message_lower)
        
        elif any(word in message_lower for word in ['team', 'search']):
            return self.handle_team_search(message_lower)
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'start']):
            return self.get_welcome_message()
        
        else:
            return self.get_help_message()

    def handle_todays_matches(self):
        """Handle today's matches"""
        raw_matches = fetch_todays_matches()
        matches = process_match_data(raw_matches)
        
        if not matches:
            return "❌ No matches found for today. Try again later."
        
        # Split into live and upcoming
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if m['is_upcoming']]
        
        response = "📅 **Today's Football Matches**\n\n"
        response += f"⏰ Last Updated: {datetime.now().strftime('%I:%M %p')}\n\n"
        
        if live_matches:
            response += "🔴 **LIVE MATCHES**\n"
            for match in live_matches[:6]:  # Limit to 6 live matches
                response += f"{match['status']} {match['home_team']} {match['score']} {match['away_team']}\n"
                response += f"   🏆 {match['league']} | ⏱️ {match['time']}\n\n"
        
        if upcoming_matches:
            response += "🕒 **UPCOMING MATCHES**\n"
            
            # Group by league
            leagues = {}
            for match in upcoming_matches:
                league = match['league']
                if league not in leagues:
                    leagues[league] = []
                leagues[league].append(match)
            
            # Show max 3 leagues to avoid long messages
            for league_name, league_matches in list(leagues.items())[:3]:
                response += f"\n**{league_name}**\n"
                for match in league_matches[:4]:  # Max 4 matches per league
                    response += f"• {match['home_team']} vs {match['away_team']} - {match['time']}\n"
        
        response += f"\n📊 **Summary:** {len(live_matches)} live, {len(upcoming_matches)} upcoming"
        response += f"\n🔥 API hits today: {hit_counter.daily_hits}/100"
        
        return response

    def handle_live_matches(self):
        """Handle live matches only"""
        raw_matches = fetch_live_matches()
        if not raw_matches:
            # Fallback to today's matches and filter live ones
            raw_matches = fetch_todays_matches()
        
        matches = [m for m in process_match_data(raw_matches) if m['is_live']]
        
        if not matches:
            return "🔴 No live matches at the moment. Check /today for upcoming matches."
        
        response = "🔴 **LIVE MATCHES**\n\n"
        
        for match in matches[:8]:  # Limit to 8 matches
            response += f"{match['status']} **{match['home_team']} {match['score']} {match['away_team']}**\n"
            response += f"🏆 {match['league']} | ⏱️ {match['time']}\n\n"
        
        response += f"📊 {len(matches)} matches live | API hits: {hit_counter.daily_hits}/100"
        
        return response

    def handle_team_search(self, message):
        """Handle team-specific searches"""
        for team in self.popular_teams:
            if team in message.lower():
                raw_matches = fetch_todays_matches()
                team_matches = []
                
                for match in raw_matches:
                    home_team = match.get("match_hometeam_name", "").lower()
                    away_team = match.get("match_awayteam_name", "").lower()
                    
                    if team in home_team or team in away_team:
                        team_matches.append(match)
                
                if team_matches:
                    response = f"🔍 **Matches for {team.title()}**\n\n"
                    for match in team_matches:
                        home_team = match.get("match_hometeam_name", "TBD")
                        away_team = match.get("match_awayteam_name", "TBD")
                        score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                        status = match.get("match_status", "Upcoming")
                        time = match.get("match_time", "00:00")
                        league = match.get("league_name", "Unknown")
                        
                        if status == "Live" or status.isdigit():
                            status_text = f"🔴 LIVE - {status}'"
                        else:
                            # Format time
                            try:
                                time_obj = datetime.strptime(time, "%H:%M:%S")
                                formatted_time = time_obj.strftime("%I:%M %p")
                            except:
                                formatted_time = time
                            status_text = f"🕒 {formatted_time}"
                        
                        response += f"**{home_team} vs {away_team}**\n"
                        response += f"📊 {score} | {status_text}\n"
                        response += f"🏆 {league}\n\n"
                    
                    return response
                else:
                    return f"❌ No matches today for {team.title()}."
        
        return "🔍 Please specify a team name. Examples: 'manchester city', 'real madrid', 'barcelona'"

    def handle_prediction(self, message):
        teams = []
        for team in self.popular_teams:
            if team in message.lower():
                teams.append(team)
        
        if len(teams) >= 2:
            team1, team2 = teams[0], teams[1]
            return self.generate_prediction(team1, team2)
        else:
            return """
🎯 **Match Prediction**

Ask me like:
• "predict manchester city vs liverpool"
• "barcelona vs real madrid prediction"

I'll analyze the match and give you probabilities!
"""

    def generate_prediction(self, team1, team2):
        # Simple prediction based on team popularity
        team_strengths = {
            "manchester city": 95, "liverpool": 92, "arsenal": 90,
            "real madrid": 94, "barcelona": 92, "bayern munich": 93,
            "psg": 91, "manchester united": 88, "chelsea": 87
        }
        
        strength1 = team_strengths.get(team1.lower(), 80)
        strength2 = team_strengths.get(team2.lower(), 80)
        
        total = strength1 + strength2
        prob1 = (strength1 / total) * 100
        prob2 = (strength2 / total) * 100
        draw_prob = 30  # Base draw probability
        
        # Adjust probabilities
        prob1_adj = prob1 * 0.7
        prob2_adj = prob2 * 0.7
        draw_prob_adj = draw_prob
        
        # Normalize
        total_adj = prob1_adj + prob2_adj + draw_prob_adj
        prob1_final = (prob1_adj / total_adj) * 100
        prob2_final = (prob2_adj / total_adj) * 100
        draw_final = (draw_prob_adj / total_adj) * 100
        
        if prob1_final > prob2_final:
            winner = team1.title()
        else:
            winner = team2.title()
        
        return f"""
🎯 **PREDICTION: {team1.upper()} vs {team2.upper()}**

📊 **Probabilities:**
• {team1.title()}: {prob1_final:.1f}%
• {team2.title()}: {prob2_final:.1f}%
• Draw: {draw_final:.1f}%

🏆 **Most Likely Winner:** {winner}

⚽ **Expected:** Competitive match with goals!

⚠️ *Football is unpredictable - enjoy the game!*
"""

    def get_welcome_message(self):
        return """
🤖 **Football Matches Bot** ⚽

I can show you:
• 📅 Today's matches
• 🔴 Live scores  
• 🕒 Upcoming games
• 🎯 Match predictions
• 🔍 Team searches

**Try these commands:**
/today - Today's all matches
/live - Live matches only
/upcoming - Upcoming matches
/predict - Match predictions
/search - Team search
/hits - API usage stats

**Or just type:**
"today matches"
"live scores"
"manchester city"
"predict real madrid vs barcelona"
"""

    def get_help_message(self):
        return self.get_welcome_message()

# Initialize AI
football_ai = FootballAI()

# -------------------------
# Telegram Bot Handlers with Better Error Handling
# -------------------------
def safe_reply(message, text):
    """Safely send reply with error handling"""
    try:
        # Split long messages (Telegram limit: 4096 characters)
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                bot.reply_to(message, part)
                time.sleep(0.5)  # Avoid rate limiting
        else:
            bot.reply_to(message, text, parse_mode='Markdown')
        return True
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
        try:
            bot.reply_to(message, "❌ Error sending message. Please try again.")
        except:
            print("❌ Critical: Cannot send any messages")
        return False

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.get_welcome_message()
        safe_reply(message, response)
    except Exception as e:
        print(f"❌ Welcome handler error: {e}")

@bot.message_handler(commands=['today'])
def send_todays_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()
        safe_reply(message, response)
    except Exception as e:
        print(f"❌ Today matches error: {e}")
        safe_reply(message, "❌ Error fetching today's matches. Please try again.")

@bot.message_handler(commands=['live'])
def send_live_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_live_matches()
        safe_reply(message, response)
    except Exception as e:
        print(f"❌ Live matches error: {e}")
        safe_reply(message, "❌ Error fetching live matches. Please try again.")

@bot.message_handler(commands=['upcoming'])
def send_upcoming_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()  # Shows both live and upcoming
        safe_reply(message, response)
    except Exception as e:
        print(f"❌ Upcoming matches error: {e}")
        safe_reply(message, "❌ Error fetching upcoming matches.")

@bot.message_handler(commands=['search'])
def send_search_help(message):
    help_text = """
🔍 **Team Search**

Examples:
• "manchester city"
• "real madrid match"
• "barcelona"
• "bayern munich"

I'll show you today's matches for that team!
"""
    safe_reply(message, help_text)

@bot.message_handler(commands=['hits'])
def send_hit_stats(message):
    try:
        stats = hit_counter.get_hit_stats()
        safe_reply(message, stats)
    except Exception as e:
        print(f"❌ Hits stats error: {e}")
        safe_reply(message, "❌ Error fetching stats.")

@bot.message_handler(commands=['predict'])
def send_predict_help(message):
    help_text = """
🎯 **Match Prediction**

Ask me like:
• "predict manchester city vs liverpool"
• "barcelona vs real madrid prediction"
• "who will win arsenal vs chelsea"

I'll analyze and give you match probabilities!
"""
    safe_reply(message, help_text)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        user_message = message.text
        print(f"💬 Received: {user_message}")
        
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.3)  # Small delay for better UX
        
        response = football_ai.get_response(user_message)
        safe_reply(message, response)
        
    except Exception as e:
        print(f"❌ Message handler error: {e}")
        safe_reply(message, "❌ Sorry, an error occurred. Please try again.")

# -------------------------
# Auto Updater
# -------------------------
def auto_updater():
    """Background match updater"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"🔄 Auto-update at {current_time}")
            
            # Only update if we have API calls remaining
            can_make, _ = hit_counter.can_make_request()
            if can_make:
                matches = fetch_todays_matches()
                print(f"✅ Auto-update: {len(matches)} matches cached")
            else:
                print("⏸️ Auto-update skipped: Daily limit reached")
            
            # Wait 15 minutes between updates
            time.sleep(900)
            
        except Exception as e:
            print(f"❌ Auto-updater error: {e}")
            time.sleep(300)  # Wait 5 minutes on error

# -------------------------
# Startup Function
# -------------------------
def start_bot():
    """Start the bot with comprehensive error handling"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print("🚀 Starting Football Matches Bot...")
            
            # Test bot token
            print("🔐 Testing bot token...")
            bot_info = bot.get_me()
            print(f"✅ Bot authorized: @{bot_info.username}")
            
            # Start auto-updater
            updater_thread = threading.Thread(target=auto_updater, daemon=True)
            updater_thread.start()
            print("✅ Auto-updater started")
            
            # Initial matches load
            print("📥 Loading initial matches...")
            matches = fetch_todays_matches()
            print(f"✅ Initial load: {len(matches)} matches")
            
            # Send startup message
            startup_msg = f"""
🤖 **Football Bot Started Successfully!**

✅ **System Status:**
• Bot: @{bot_info.username}
• Matches Loaded: {len(matches)}
• API Hits: {hit_counter.daily_hits}/100
• Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}

🚀 **Ready to serve football updates!**
"""
            safe_reply_to_owner(startup_msg)
            
            print("🔄 Starting polling...")
            bot.polling(none_stop=True, timeout=60)
            break
            
        except Exception as e:
            retry_count += 1
            print(f"❌ Startup attempt {retry_count} failed: {e}")
            
            if retry_count < max_retries:
                wait_time = 10 * retry_count
                print(f"🔄 Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("❌ Max retries reached. Shutting down.")
                break

def safe_reply_to_owner(text):
    """Safely send message to owner"""
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                bot.send_message(OWNER_CHAT_ID, part, parse_mode='Markdown')
        else:
            bot.send_message(OWNER_CHAT_ID, text, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ Failed to send to owner: {e}")

if __name__ == '__main__':
    start_bot()
