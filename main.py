import os
import requests
import telebot
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")

# Validate credentials
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN is missing!")
    print("Please set BOT_TOKEN in your .env file")
    exit(1)

if not OWNER_CHAT_ID:
    print("❌ ERROR: OWNER_CHAT_ID is missing!")
    print("Please set OWNER_CHAT_ID in your .env file")
    exit(1)

# Initialize bot
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ Bot initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize bot: {e}")
    exit(1)

print("🚀 Starting Football Matches Bot...")

# API Configuration
API_URL = "https://apiv3.apifootball.com"
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

# Track API usage
api_hits = 0

def safe_api_call(url):
    """Safe API call with error handling"""
    global api_hits
    try:
        api_hits += 1
        print(f"🌐 API Call #{api_hits}")
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []
        else:
            print(f"❌ HTTP Error {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ API Error: {e}")
        return []

def get_todays_matches():
    """Get today's matches"""
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{API_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
    return safe_api_call(url)

def get_live_matches():
    """Get live matches"""
    url = f"{API_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
    return safe_api_call(url)

def format_time(time_str):
    """Format time string to 12-hour format"""
    if not time_str or ':' not in time_str:
        return time_str
    
    try:
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = parts[1]
        period = "AM" if hour < 12 else "PM"
        hour = hour if hour <= 12 else hour - 12
        if hour == 0: 
            hour = 12
        return f"{hour}:{minute} {period}"
    except:
        return time_str

def format_matches(matches, match_type="today"):
    """Format matches for display"""
    if not matches:
        if match_type == "live":
            return "🔴 No live matches at the moment"
        elif match_type == "upcoming":
            return "🕒 No upcoming matches found"
        else:
            return "❌ No matches found for today"
    
    output = []
    match_count = 0
    
    for match in matches:
        try:
            home_team = match.get('match_hometeam_name', 'Unknown').strip()
            away_team = match.get('match_awayteam_name', 'Unknown').strip()
            home_score = match.get('match_hometeam_score', '0')
            away_score = match.get('match_awayteam_score', '0')
            status = str(match.get('match_status', ''))
            time_str = match.get('match_time', '')
            league_id = match.get('league_id', '')
            
            # Skip if teams are unknown
            if home_team == 'Unknown' and away_team == 'Unknown':
                continue
            
            # Get league name
            league_name = get_league_name(league_id)
            
            # Determine match status and format
            if status == 'HT':
                display = f"🔄 **{home_team} {home_score}-{away_score} {away_team}**\n   ⏱️ Half Time | {league_name}"
            elif status == 'FT':
                display = f"🏁 **{home_team} {home_score}-{away_score} {away_team}**\n   ⏱️ Full Time | {league_name}"
            elif status.isdigit():
                display = f"🔴 **{home_team} {home_score}-{away_score} {away_team}**\n   ⏱️ {status}' | {league_name}"
            else:
                # Upcoming match
                formatted_time = format_time(time_str)
                display = f"🕒 **{home_team} vs {away_team}**\n   ⏰ {formatted_time} | {league_name}"
            
            output.append(display)
            match_count += 1
            
            # Limit to 15 matches to avoid long messages
            if match_count >= 15:
                break
                
        except Exception as e:
            print(f"⚠️ Error formatting match: {e}")
            continue
    
    if not output:
        return "❌ No valid matches to display"
    
    return "\n\n".join(output)

def get_league_name(league_id):
    """Get league name from ID"""
    leagues = {
        "152": "🏴 Premier League",
        "302": "🇪🇸 La Liga", 
        "207": "🇮🇹 Serie A",
        "168": "🇩🇪 Bundesliga", 
        "176": "🇫🇷 Ligue 1",
        "262": "⭐ Champions League",
        "263": "🌍 Europa League",
        "5": "🌎 World Cup Qualifiers",
    }
    return leagues.get(str(league_id), "⚽ Football Match")

# Bot message handlers
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome = """
🤖 **Football Matches Bot** ⚽

I can show you today's football matches with live scores!

**Commands:**
/today - Today's all matches
/live - Live matches only  
/upcoming - Upcoming matches
/stats - Bot statistics

**Just type:**
"today matches"
"live scores" 
"upcoming games"

Let's get started! 🎯
"""
    try:
        bot.reply_to(message, welcome, parse_mode='Markdown')
    except Exception as e:
        print(f"Error sending welcome: {e}")

@bot.message_handler(commands=['today'])
def send_today(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        matches = get_todays_matches()
        
        response = "📅 **Today's Football Matches**\n\n"
        response += f"⏰ Last Updated: {datetime.now().strftime('%I:%M %p')}\n\n"
        
        formatted_matches = format_matches(matches, "today")
        response += formatted_matches
        
        response += f"\n\n📊 **API calls today:** {api_hits}"
        response += f"\n⚽ **Total matches:** {len(matches) if matches else 0}"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = "❌ Error fetching today's matches. Please try again later."
        bot.reply_to(message, error_msg)
        print(f"Today matches error: {e}")

@bot.message_handler(commands=['live'])
def send_live(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        matches = get_live_matches()
        
        # If no live matches, try to find live matches from today's data
        if not matches:
            today_matches = get_todays_matches()
            if today_matches:
                matches = [m for m in today_matches if str(m.get('match_status', '')).isdigit() or m.get('match_status') in ['HT', '1H', '2H']]
        
        response = "🔴 **Live Football Matches**\n\n"
        
        formatted_matches = format_matches(matches, "live")
        response += formatted_matches
        
        response += f"\n\n📊 **API calls today:** {api_hits}"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = "❌ Error fetching live matches. Please try again later."
        bot.reply_to(message, error_msg)
        print(f"Live matches error: {e}")

@bot.message_handler(commands=['upcoming'])
def send_upcoming(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        matches = get_todays_matches()
        
        # Filter upcoming matches (not live and not finished)
        upcoming_matches = []
        if matches:
            for match in matches:
                status = str(match.get('match_status', ''))
                if not status.isdigit() and status not in ['HT', 'FT', '1H', '2H']:
                    upcoming_matches.append(match)
        
        response = "🕒 **Upcoming Matches Today**\n\n"
        
        formatted_matches = format_matches(upcoming_matches, "upcoming")
        response += formatted_matches
        
        response += f"\n\n📊 **API calls today:** {api_hits}"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        error_msg = "❌ Error fetching upcoming matches. Please try again later."
        bot.reply_to(message, error_msg)
        print(f"Upcoming matches error: {e}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    try:
        stats = f"""
📊 **Bot Statistics**

• **API Calls Today:** {api_hits}
• **Current Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
• **Bot Status:** ✅ Running
• **Region:** us-west1

Everything is working perfectly! 🚀
"""
        bot.reply_to(message, stats, parse_mode='Markdown')
    except Exception as e:
        print(f"Stats error: {e}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        text = message.text.lower()
        
        if any(word in text for word in ['today', 'matches', 'aaj', 'aj']):
            send_today(message)
        elif any(word in text for word in ['live', 'score']):
            send_live(message)
        elif any(word in text for word in ['upcoming', 'coming']):
            send_upcoming(message)
        elif any(word in text for word in ['stat', 'hit']):
            send_stats(message)
        elif any(word in text for word in ['hello', 'hi', 'hey']):
            bot.reply_to(message, "👋 Hello! I'm Football Bot! Use /today to see matches!")
        else:
            send_welcome(message)
            
    except Exception as e:
        error_msg = "❌ Error processing your message. Please try again."
        bot.reply_to(message, error_msg)
        print(f"Message handler error: {e}")

def start_bot():
    """Start the bot with comprehensive error handling"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"🚀 Starting bot (attempt {attempt + 1}/{max_retries})...")
            
            # Test bot connection
            bot_info = bot.get_me()
            print(f"✅ Bot authorized: @{bot_info.username}")
            
            # Test API connection
            print("🔍 Testing API connection...")
            test_matches = get_todays_matches()
            print(f"✅ API test: {len(test_matches)} matches found")
            
            # Send startup message
            startup_msg = f"""
🤖 **Football Bot Started Successfully!**

• **Bot:** @{bot_info.username}
• **Matches Loaded:** {len(test_matches)}
• **API Calls:** {api_hits}
• **Time:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
• **Region:** us-west1 ✅

Bot is ready to serve football updates! ⚽
"""
            bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
            
            print("🔄 Starting polling...")
            bot.polling(none_stop=True, timeout=60)
            break
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 10
                print(f"🔄 Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("❌ Max retries reached. Please check your configuration.")
                break

if __name__ == '__main__':
    start_bot()
