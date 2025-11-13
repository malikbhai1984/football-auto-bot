import os
import requests
import telebot
import time
import schedule
from datetime import datetime, timedelta
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

print("🔑 Bot configuration loaded successfully")

# Initialize bot
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    print("✅ Bot initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize bot: {e}")
    exit(1)

print("🚀 Starting Football Bot...")

# API Configuration
API_URL = "https://apiv3.apifootball.com"
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"

# Track API usage
api_hits = 0

# Define the 7 specific leagues + World Cup Qualifiers we want
TARGET_LEAGUES = {
    "152": "🏴 Premier League",
    "302": "🇪🇸 La Liga", 
    "207": "🇮🇹 Serie A",
    "168": "🇩🇪 Bundesliga",
    "176": "🇫🇷 Ligue 1",
    "262": "⭐ Champions League",
    "263": "🌍 Europa League",
    "5": "🌎 World Cup Qualifiers",
}

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
        print(f"❌ API call failed: {e}")
        return []

def get_todays_matches():
    """Get today's matches from specific leagues only"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get matches for all leagues first
    url = f"{API_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
    all_matches = safe_api_call(url)
    
    # Filter only our target leagues
    filtered_matches = []
    for match in all_matches:
        league_id = str(match.get('league_id', ''))
        if league_id in TARGET_LEAGUES:
            filtered_matches.append(match)
    
    print(f"📊 Found {len(filtered_matches)} matches in target leagues")
    return filtered_matches

def get_upcoming_matches():
    """Get upcoming matches for predictions (next 24 hours)"""
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    url = f"{API_URL}/?action=get_events&from={today}&to={tomorrow}&APIkey={API_KEY}"
    all_matches = safe_api_call(url)
    
    # Filter only our target leagues and upcoming matches
    upcoming_matches = []
    for match in all_matches:
        league_id = str(match.get('league_id', ''))
        status = match.get('match_status', '')
        
        # Only include matches from target leagues that haven't started
        if league_id in TARGET_LEAGUES and status == '':
            upcoming_matches.append(match)
    
    print(f"🔮 Found {len(upcoming_matches)} upcoming matches for predictions")
    return upcoming_matches

def get_live_matches():
    """Get live matches for today's date"""
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{API_URL}/?action=get_events&from={today}&to={today}&APIkey={API_KEY}"
    all_matches = safe_api_call(url)
    live_matches = [m for m in all_matches if m.get('match_live') == "1" and str(m.get('league_id', '')) in TARGET_LEAGUES]
    print(f"🔴 Found {len(live_matches)} live matches")
    return live_matches

def format_time(time_str):
    """Format time to 12-hour format"""
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

def get_league_name(league_id):
    """Get league name from ID"""
    return TARGET_LEAGUES.get(str(league_id), "⚽ Football Match")

def predict_match_result(home_team, away_team, home_goals, away_goals):
    """Simple prediction algorithm based on team stats"""
    try:
        home_attack = int(home_goals) if home_goals else 1
        away_attack = int(away_goals) if away_goals else 1
        
        total_attack = home_attack + away_attack
        if total_attack == 0:
            return "1-1 Draw"
            
        home_win_prob = (home_attack / total_attack) * 100
        away_win_prob = (away_attack / total_attack) * 100
        draw_prob = 100 - abs(home_win_prob - away_win_prob)
        
        if home_win_prob > 60:
            return f"2-1 Win for {home_team}"
        elif away_win_prob > 60:
            return f"1-2 Win for {away_team}"
        elif draw_prob > 40:
            return "1-1 Draw"
        else:
            return f"2-1 Win for {home_team}"
        
    except Exception as e:
        return f"2-1 Win for {home_team}"

def generate_predictions():
    """Generate predictions for upcoming matches"""
    print("🎯 Generating predictions...")
    
    upcoming_matches = get_upcoming_matches()
    predictions = []
    
    for match in upcoming_matches[:10]:
        try:
            home_team = match.get('match_hometeam_name', 'Unknown').strip()
            away_team = match.get('match_awayteam_name', 'Unknown').strip()
            time_str = match.get('match_time', '')
            league_id = match.get('league_id', '')
            
            if home_team == 'Unknown' or away_team == 'Unknown':
                continue
            
            league_name = get_league_name(league_id)
            
            home_goals = match.get('match_hometeam_score', '0')
            away_goals = match.get('match_awayteam_score', '0')
            
            prediction = predict_match_result(home_team, away_team, home_goals, away_goals)
            formatted_time = format_time(time_str)
            
            prediction_text = f"**{home_team} vs {away_team}**
"
            prediction_text += f"🕒 {formatted_time} | {league_name}
"
            prediction_text += f"🔮 **Prediction:** {prediction}
"
            prediction_text += "─" * 30
            
            predictions.append(prediction_text)
            
        except Exception as e:
            print(f"⚠️ Error predicting match: {e}")
            continue
    
    if not predictions:
        return "No upcoming matches found for predictions."
    
    header = "🔮 **FOOTBALL MATCH PREDICTIONS** 🔮

"
    header += f"⏰ Generated: {datetime.now().strftime('%I:%M %p')}

"
    
    return header + "

".join(predictions)

def generate_live_predictions():
    """Generate predictions for live matches"""
    live_matches = get_live_matches()
    if not live_matches:
        return "No live matches currently for predictions."
    
    predictions = []
    for match in live_matches:
        home_team = match.get('match_hometeam_name', 'Unknown')
        away_team = match.get('match_awayteam_name', 'Unknown')
        home_goals = match.get('match_hometeam_score', '0')
        away_goals = match.get('match_awayteam_score', '0')

        prediction = predict_match_result(home_team, away_team, home_goals, away_goals)
        league_name = get_league_name(match.get('league_id', ''))
        time_str = format_time(match.get('match_time', ''))

        pred_text = f"**{home_team} vs {away_team}**
🕒 {time_str} | {league_name}
🔮 **Prediction:** {prediction}
{'─'*30}"
        predictions.append(pred_text)

    header = "🔴 **LIVE MATCH PREDICTIONS** 🔴

"
    header += f"⏰ Updated: {datetime.now().strftime('%I:%M %p')}

"
    return header + "

".join(predictions)

def send_auto_predictions():
    """Automatically send predictions to owner"""
    try:
        print("🤖 Auto-sending upcoming predictions...")
        predictions = generate_predictions()
        bot.send_message(OWNER_CHAT_ID, predictions, parse_mode='Markdown')
        print("✅ Upcoming predictions sent successfully")

        print("🤖 Auto-sending live predictions...")
        live_preds = generate_live_predictions()
        bot.send_message(OWNER_CHAT_ID, live_preds, parse_mode='Markdown')
        print("✅ Live predictions sent successfully")
    except Exception as e:
        print(f"❌ Failed to send auto-predictions: {e}")

def setup_scheduler():
    """Setup automatic scheduling for predictions"""
    schedule.every(7).minutes.do(send_auto_predictions)
    schedule.every(1).hours.do(lambda: bot.send_message(
        OWNER_CHAT_ID, 
        f"🤖 Bot is running! API calls: {api_hits}", 
        parse_mode='Markdown'
    ))

    print("⏰ Scheduler setup: Predictions every 7 minutes")

def run_scheduler():
    """Run the scheduler continuously"""
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
            time.sleep(60)

def format_matches(matches, match_type="all"):
    if not matches:
        return "No matches found today."
    
    output = []
    count = 0
    
    for match in matches:
        try:
            home_team = match.get('match_hometeam_name', 'Unknown').strip()
            away_team = match.get('match_awayteam_name', 'Unknown').strip()
            home_score = match.get('match_hometeam_score', '0')
            away_score = match.get('match_awayteam_score', '0')
            status = str(match.get('match_status', ''))
            time_str = match.get('match_time', '')
            league_id = match.get('league_id', '')

            if home_team == 'Unknown' and away_team == 'Unknown':
                continue
            
            league_name = get_league_name(league_id)
            
            if match_type == "live" and not (status.isdigit() or status in ['HT', '1H', '2H']):
                continue
            elif match_type == "upcoming" and (status.isdigit() or status in ['HT', 'FT', '1H', '2H']):
                continue

            if status == 'HT':
                display = f"🔄 **{home_team} {home_score}-{away_score} {away_team}**
⏱️ Half Time | {league_name}"
            elif status == 'FT':
                display = f"🏁 **{home_team} {home_score}-{away_score} {away_team}**
⏱️ Full Time | {league_name}"
            elif status.isdigit():
                display = f"🔴 **{home_team} {home_score}-{away_score} {away_team}**
⏱️ {status}' | {league_name}"
            else:
                formatted_time = format_time(time_str)
                display = f"🕒 **{home_team} vs {away_team}**
⏰ {formatted_time} | {league_name}"

            output.append(display)
            count += 1
            
            if count >= 15:
                break
                
        except Exception as e:
            print(f"⚠️ Error formatting match: {e}")
            continue
    
    if not output:
        return "No matches found for the selected type."
    
    return "

".join(output)

# Telegram Commands
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome = """
🤖 **Football Matches Bot** ⚽

Commands:
/today - Today's all matches
/live - Live matches only  
/upcoming - Upcoming matches
/predict - Match predictions
/stats - Bot statistics

Type keywords like:
"today", "live", "upcoming", "predict"
"""
    bot.reply_to(message, welcome, parse_mode='Markdown')

@bot.message_handler(commands=['today'])
def send_today(message):
    matches = get_todays_matches()
    response = "📅 **Today's Football Matches**

"
    response += f"⏰ Updated: {datetime.now().strftime('%I:%M %p')}

"
    response += format_matches(matches, "all")
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['predict'])
def send_predictions(message):
    predictions = generate_predictions()
    bot.reply_to(message, predictions, parse_mode='Markdown')

@bot.message_handler(commands=['live'])
def send_live(message):
    matches = get_todays_matches()
    response = "🔴 **Live Football Matches**

"
    response += format_matches(matches, "live")
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['upcoming'])
def send_upcoming(message):
    matches = get_todays_matches()
    response = "🕒 **Upcoming Matches Today**

"
    response += format_matches(matches, "upcoming")
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def send_stats(message):
    stats = f"""
📊 **Bot Statistics**

• API Calls Today: {api_hits}
• Target Leagues: {len(TARGET_LEAGUES)}
• Auto Predictions: Every 7 minutes
• Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
• Bot Status: ✅ Running
"""
    bot.reply_to(message, stats, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text.lower()
    if any(word in text for word in ['today', 'matches', 'aaj', 'aj']):
        send_today(message)
    elif any(word in text for word in ['live', 'score']):
        send_live(message)
    elif any(word in text for word in ['upcoming', 'coming']):
        send_upcoming(message)
    elif any(word in text for word in ['predict', 'prediction']):
        send_predictions(message)
    elif any(word in text for word in ['stat', 'hit']):
        send_stats(message)
    elif any(word in text for word in ['hello', 'hi']):
        bot.reply_to(message, "👋 Hello! Use /today to see football matches!")
    else:
        send_welcome(message)

def start_bot():
    print("="*50)
    print("🚀 FOOTBALL BOT STARTUP")
    print("="*50)

    print("🔐 Testing bot connection...")
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot connected: @{bot_info.username}")
    except Exception as e:
        print(f"❌ Bot connection failed: {e}")
        return

    print("🔍 Testing football API availability...")
    matches = get_todays_matches()
    print(f"✅ Matches loaded for today: {len(matches)}")

    setup_scheduler()
    
    try:
        bot.send_message(OWNER_CHAT_ID, "🤖 Football Bot Started Successfully!")
        print("✅ Startup message sent")
    except Exception as e:
        print(f"⚠️ Failed to send startup message: {e}")

    import threading
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("⏰ Scheduler running in background")

    print("📱 Starting bot polling...")
    try:
        bot.polling(none_stop=True, timeout=60, skip_pending=True)
    except Exception as e:
        print(f"❌ Polling error: {e}")

if __name__ == '__main__':
    start_bot()
