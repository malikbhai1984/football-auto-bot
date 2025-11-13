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
API_URL = "https://apiv3.apifootball.com"
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

# Track API usage
api_hits = 0

def safe_api_call(url):
    """Safe API call with error handling"""
    global api_hits
    try:
        api_hits += 1
        print(f"🌐 API Call #{api_hits}: {url.split('?')[0]}")
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []
        else:
            print(f"❌ HTTP {response.status_code}")
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

def format_matches(matches):
    """Format matches for display"""
    if not matches:
        return "❌ No matches found"
    
    output = []
    
    for match in matches[:15]:  # Limit to 15 matches
        try:
            home_team = match.get('match_hometeam_name', 'Unknown')
            away_team = match.get('match_awayteam_name', 'Unknown')
            home_score = match.get('match_hometeam_score', '0')
            away_score = match.get('match_awayteam_score', '0')
            status = match.get('match_status', '')
            time_str = match.get('match_time', '')
            
            # Determine status
            if status == 'HT':
                display = f"🔄 {home_team} {home_score}-{away_score} {away_team} (HT)"
            elif status == 'FT':
                display = f"🏁 {home_team} {home_score}-{away_score} {away_team} (FT)"
            elif status.isdigit():
                display = f"🔴 {home_team} {home_score}-{away_score} {away_team} ({status}')"
            else:
                # Format time
                try:
                    if time_str and ':' in time_str:
                        parts = time_str.split(':')
                        hour = int(parts[0])
                        minute = parts[1]
                        period = "AM" if hour < 12 else "PM"
                        hour = hour if hour <= 12 else hour - 12
                        if hour == 0: hour = 12
                        time_str = f"{hour}:{minute} {period}"
                except:
                    pass
                display = f"🕒 {home_team} vs {away_team} ({time_str})"
            
            output.append(display)
            
        except Exception as e:
            print(f"⚠️ Error formatting match: {e}")
            continue
    
    return "\n".join(output) if output else "❌ No valid matches to display"

# Bot message handlers
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome = """
🤖 **Football Matches Bot** ⚽

I can show you today's football matches and live scores!

**Commands:**
/today - Today's matches
/live - Live matches  
/upcoming - Upcoming matches
/stats - Bot statistics

**Examples:**
"today matches"
"live scores"
"upcoming games"

Let's get started! 🎯
"""
    bot.reply_to(message, welcome, parse_mode='Markdown')

@bot.message_handler(commands=['today'])
def send_today(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        matches = get_todays_matches()
        
        response = f"📅 **Today's Football Matches**\n\n"
        response += f"⏰ Last Updated: {datetime.now().strftime('%I:%M %p')}\n\n"
        
        formatted_matches = format_matches(matches)
        response += formatted_matches
        
        response += f"\n\n📊 API calls today: {api_hits}"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error fetching matches: {str(e)}")

@bot.message_handler(commands=['live'])
def send_live(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        matches = get_live_matches()
        
        if not matches:
            # Try to get live matches from today's matches
            matches = get_todays_matches()
            live_matches = [m for m in matches if m.get('match_status', '').isdigit() or m.get('match_status') in ['HT', '1H', '2H']]
            matches = live_matches
        
        response = f"🔴 **Live Football Matches**\n\n"
        
        formatted_matches = format_matches(matches)
        response += formatted_matches
        
        if "No matches" in formatted_matches:
            response = "🔴 No live matches at the moment. Check /today for upcoming matches."
        
        response += f"\n\n📊 API calls today: {api_hits}"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error fetching live matches: {str(e)}")

@bot.message_handler(commands=['upcoming'])
def send_upcoming(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        matches = get_todays_matches()
        
        # Filter upcoming matches (not live and not finished)
        upcoming_matches = []
        for match in matches:
            status = match.get('match_status', '')
            if not status.isdigit() and status not in ['HT', 'FT', '1H', '2H']:
                upcoming_matches.append(match)
        
        response = f"🕒 **Upcoming Matches Today**\n\n"
        
        formatted_matches = format_matches(upcoming_matches)
        response += formatted_matches
        
        if "No matches" in formatted_matches:
            response = "🕒 No upcoming matches found for today."
        
        response += f"\n\n📊 API calls today: {api_hits}"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error fetching upcoming matches: {str(e)}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    stats = f"""
📊 **Bot Statistics**

• API Calls Today: {api_hits}
• Current Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
• Bot Status: ✅ Running

Everything is working fine! 🚀
"""
    bot.reply_to(message, stats, parse_mode='Markdown')

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
        else:
            send_welcome(message)
            
    except Exception as e:
        bot.reply_to(message, "❌ Error processing your message. Please try again.")

def start_bot():
    """Start the bot with comprehensive error handling"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"🚀 Starting bot (attempt {retry_count + 1}/{max_retries})...")
            
            # Test bot connection
            bot_info = bot.get_me()
            print(f"✅ Bot authorized: @{bot_info.username}")
            
            # Test API connection
            test_matches = get_todays_matches()
            print(f"✅ API test: {len(test_matches)} matches found")
            
            # Send startup message
            startup_msg = f"""
🤖 **Football Bot Started Successfully!**

• Bot: @{bot_info.username}
• Matches Loaded: {len(test_matches)}
• API Calls: {api_hits}
• Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
• Region: us-west1 ✅

Bot is ready to serve! 🚀
"""
            bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
            
            print("🔄 Starting polling...")
            bot.polling(none_stop=True, timeout=60)
            break
            
        except Exception as e:
            retry_count += 1
            print(f"❌ Attempt {retry_count} failed: {e}")
            
            if retry_count < max_retries:
                wait_time = 10 * retry_count
                print(f"🔄 Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("❌ Max retries reached. Shutting down.")
                break

if __name__ == '__main__':
    start_bot()
