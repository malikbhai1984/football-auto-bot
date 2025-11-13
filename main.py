import os
import requests
import telebot
import time
from datetime import datetime, timedelta
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
print("🎯 Starting Today's Football Matches Bot...")

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
        
    def record_hit(self):
        self.total_hits += 1
        self.daily_hits += 1
        self.last_hit_time = datetime.now()
        print(f"🔥 API HIT #{self.total_hits} | Today: {self.daily_hits}/100")
        
    def can_make_request(self):
        if self.daily_hits >= 100:
            return False, "Daily limit reached"
        return True, "OK"
    
    def get_hit_stats(self):
        remaining_daily = max(0, 100 - self.daily_hits)
        stats = f"""
📊 **API Usage Statistics**

• Total Hits: {self.total_hits}
• Today's Hits: {self.daily_hits}/100
• Remaining Today: {remaining_daily}
• Last Update: {self.last_hit_time.strftime('%H:%M:%S') if self.last_hit_time else 'Never'}
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
# API Functions
# -------------------------
def fetch_todays_matches():
    """Fetch today's matches from API-Football"""
    
    hit_counter.record_hit()
    
    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        print(f"🚫 API Call Blocked: {reason}")
        return []
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"{API_FOOTBALL_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
        
        print(f"📡 Fetching today's matches...")
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data) if isinstance(data, list) else 0} matches")
            
            if isinstance(data, list):
                # Process matches
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                    
                    # Ensure required fields
                    match.setdefault("match_hometeam_score", "0")
                    match.setdefault("match_awayteam_score", "0")
                    match.setdefault("match_status", "Upcoming")
                    match.setdefault("match_time", "00:00")
                    match.setdefault("match_date", today)
                
                return data
        return []
            
    except Exception as e:
        print(f"❌ API error: {e}")
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
                    if match_time and ':' in match_time:
                        time_parts = match_time.split(':')
                        if len(time_parts) >= 2:
                            hour = int(time_parts[0])
                            minute = time_parts[1]
                            am_pm = "AM" if hour < 12 else "PM"
                            hour = hour if hour <= 12 else hour - 12
                            if hour == 0: hour = 12
                            display_time = f"{hour}:{minute} {am_pm}"
                        else:
                            display_time = match_time
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
            print(f"⚠️ Skipping match: {e}")
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
            "juventus", "napoli", "roma", "atalanta", "lazio", "sevilla"
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
        """Handle today's matches with focus on upcoming"""
        raw_matches = fetch_todays_matches()
        matches = process_match_data(raw_matches)
        
        if not matches:
            return "❌ آج کے لیے کوئی میچ نہیں ہیں۔\n\nNo matches found for today."
        
        # Split into live and upcoming
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if m['is_upcoming']]
        
        response = "📅 **آج کے فٹ بال میچز - Today's Football Matches**\n\n"
        response += f"⏰ Last Updated: {datetime.now().strftime('%I:%M %p')}\n\n"
        
        if live_matches:
            response += "🔴 **لائیو میچز - LIVE MATCHES**\n"
            for match in live_matches[:6]:
                response += f"{match['status']} {match['home_team']} {match['score']} {match['away_team']}\n"
                response += f"   🏆 {match['league']}\n\n"
        
        if upcoming_matches:
            response += "🕒 **آنے والے میچز - UPCOMING MATCHES**\n\n"
            
            # Group by time for better organization
            time_slots = {}
            for match in upcoming_matches:
                time_key = match['time']
                if time_key not in time_slots:
                    time_slots[time_key] = []
                time_slots[time_key].append(match)
            
            # Show matches in chronological order
            for time_slot in sorted(time_slots.keys()):
                response += f"🕐 **{time_slot}**\n"
                for match in time_slots[time_slot]:
                    response += f"• {match['home_team']} vs {match['away_team']}\n"
                    response += f"  🏆 {match['league']}\n"
                response += "\n"
        else:
            response += "🕒 آج کے لیے کوئی آنے والا میچ نہیں ہے۔\nNo upcoming matches for today.\n\n"
        
        response += f"📊 **خلاصہ:** {len(live_matches)} لائیو, {len(upcoming_matches)} آنے والے\n"
        response += f"**Summary:** {len(live_matches)} live, {len(upcoming_matches)} upcoming\n"
        response += f"🔥 API hits today: {hit_counter.daily_hits}/100"
        
        return response

    def handle_live_matches(self):
        """Handle live matches only"""
        raw_matches = fetch_live_matches()
        if not raw_matches:
            raw_matches = fetch_todays_matches()
        
        matches = [m for m in process_match_data(raw_matches) if m['is_live']]
        
        if not matches:
            return "🔴 فی الحال کوئی لائیو میچ نہیں چل رہا۔\n\nNo live matches at the moment."
        
        response = "🔴 **لائیو میچز - LIVE MATCHES**\n\n"
        
        for match in matches[:8]:
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
                    response = f"🔍 **{team.title()} کے آج کے میچز**\n\n"
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
                                if time and ':' in time:
                                    time_parts = time.split(':')
                                    hour = int(time_parts[0])
                                    minute = time_parts[1]
                                    am_pm = "AM" if hour < 12 else "PM"
                                    hour = hour if hour <= 12 else hour - 12
                                    if hour == 0: hour = 12
                                    formatted_time = f"{hour}:{minute} {am_pm}"
                                else:
                                    formatted_time = time
                            except:
                                formatted_time = time
                            status_text = f"🕒 {formatted_time}"
                        
                        response += f"**{home_team} vs {away_team}**\n"
                        response += f"📊 {score} | {status_text}\n"
                        response += f"🏆 {league}\n\n"
                    
                    return response
                else:
                    return f"❌ آج {team.title()} کا کوئی میچ نہیں ہے۔\n\nNo matches today for {team.title()}."
        
        return "🔍 براہ کرم ٹیم کا صحیح نام درج کریں۔\n\nPlease specify a team name."

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
🎯 **میچ پیشن گوئی - Match Prediction**

مثال کے طور پر لکھیں:
• "پریڈکٹ مانچسٹر سٹی بمقابلہ لیورپول"
• "پیشن گوئی برازیل بمقابلہ ارجنٹینا"
• "predict man city vs liverpool"

میں ٹیموں کی طاقت کا تجزیہ کر کے آپ کو احتمالات بتاؤں گا! 📊
"""

    def generate_prediction(self, team1, team2):
        # Simple prediction based on team popularity
        team_strengths = {
            "manchester city": 95, "liverpool": 92, "arsenal": 90,
            "real madrid": 94, "barcelona": 92, "bayern munich": 93,
            "psg": 91, "manchester united": 88, "chelsea": 87,
            "tottenham": 86, "ac milan": 89, "inter milan": 89,
            "juventus": 88, "napoli": 87, "roma": 86
        }
        
        strength1 = team_strengths.get(team1.lower(), 80)
        strength2 = team_strengths.get(team2.lower(), 80)
        
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

    def get_welcome_message(self):
        return """
🤖 **آج کے فٹ بال میچز بوٹ** ⚽

میں آپ کو دکھا سکتا ہوں:
• 📅 آج کے میچز
• 🔴 لائیو اسکورز  
• 🕒 آنے والے میچز
• 🎯 میچ پیشن گوئی
• 🔍 ٹیم سرچ

**کمانڈز:**
/today - آج کے تمام میچز
/live - لائیو میچز
/upcoming - آنے والے میچز
/predict - میچ پیشن گوئی
/search - ٹیم سرچ
/hits - API استعمال

**یا صرف لکھیں:**
"آج کے میچز"
"لائیو اسکورز"
"مانچسٹر سٹی"
"پریڈکٹ ریال میڈرڈ بمقابلہ بارسیلونا"
"""

    def get_help_message(self):
        return self.get_welcome_message()

# Initialize AI
football_ai = FootballAI()

# -------------------------
# Telegram Bot Handlers
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.get_welcome_message()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

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
        response = football_ai.handle_todays_matches()
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

@bot.message_handler(commands=['hits'])
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
        user_message = message.text
        print(f"💬 Received: {user_message}")
        
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.3)
        
        response = football_ai.get_response(user_message)
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Message error: {e}")
        bot.reply_to(message, "❌ معذرت، غلطی ہوئی۔ براہ کرم دوبارہ کوشش کریں!")

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
            time.sleep(300)

# -------------------------
# Startup Function
# -------------------------
def start_bot():
    """Start the bot"""
    try:
        print("🚀 Starting Football Matches Bot...")
        
        # Test bot token
        bot_info = bot.get_me()
        print(f"✅ Bot authorized: @{bot_info.username}")
        
        # Start auto-updater in background
        import threading
        updater_thread = threading.Thread(target=auto_updater, daemon=True)
        updater_thread.start()
        print("✅ Auto-updater started")
        
        # Initial matches load
        matches = fetch_todays_matches()
        print(f"✅ Initial load: {len(matches)} matches")
        
        # Send startup message
        startup_msg = f"""
🤖 **فٹ بال میچز بوٹ شروع ہو گیا!**

✅ **سسٹم ایکٹو:**
• Bot: @{bot_info.username}
• Matches Loaded: {len(matches)}
• API Hits: {hit_counter.daily_hits}/100
• Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}

🚀 **آج کے میچز دیکھنے کے لیے تیار!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
        print("🔄 Starting polling...")
        bot.polling(none_stop=True, timeout=60)
            
    except Exception as e:
        print(f"❌ Startup error: {e}")
        time.sleep(10)
        start_bot()

if __name__ == '__main__':
    start_bot()
