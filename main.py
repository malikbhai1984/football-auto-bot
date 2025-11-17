import os
import requests
import telebot
import time
import random
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request
import threading
from dotenv import load_dotenv

# =======================================================
# 1. Environment and Configuration
# =======================================================
load_dotenv()

# --- Load API Keys and Settings ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_KEY = os.environ.get("API_KEY") 
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 
PORT = int(os.environ.get('PORT', 5000))

# --- Validation and Initialization ---
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN missing!")
try:
    # Ensure OWNER_CHAT_ID is an integer
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except (ValueError, TypeError):
    logging.warning("❌ OWNER_CHAT_ID is missing or not an integer. Alerts will not be sent.")
    OWNER_CHAT_ID = None

# FIX: Simple logging setup to avoid the Gunicorn crash (AttributeError)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FootballBot') 

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- CONFIGURATION ---
API_FOOTBALL_URL = "https://apiv3.apifootball.com"
MAX_DAILY_HITS = 100 # Adjusted for typical free tier limit
SLEEP_TIME_SECONDS = 420 # 7 minutes interval for API calls
CONFIDENCE_THRESHOLD = 85.0 # Minimum confidence for expert bet alert

# Global State
hit_counter = {'daily_hits': 0, 'last_reset': datetime.now().date()}
match_cache = {}
last_fetch_time = "N/A"

# =======================================================
# 2. Match Analysis Dummy Class (FIXED LOCATION)
# =======================================================
class MatchAnalysis:
    """A placeholder class required for the EnhancedFootballAI to initialize without error."""
    def generate_simple_score_based_prediction(self, match_data):
        """Generates simple prediction based on current score and time"""
        minute = match_data.get("match_status", "0")
        if minute == "FT": return "🏁 Match is over."
        # This function is used by the prediction logic for insights
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        if home_score > away_score:
            return "✅ Home team has the lead."
        elif away_score > home_score:
            return "✅ Away team has the lead."
        else:
            return "🤝 Draw is highly likely."

# =======================================================
# 3. Enhanced Prediction Core (V2 Logic Integrated)
# =======================================================

class EnhancedFootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking", "goal_avg": 2.5},
            "liverpool": {"strength": 92, "style": "high press", "goal_avg": 2.2},
            "arsenal": {"strength": 90, "style": "possession", "goal_avg": 2.1},
            "real madrid": {"strength": 94, "style": "experienced", "goal_avg": 2.3},
            "unknown": {"strength": 75, "style": "standard", "goal_avg": 1.5}
        }
        # FIX: MatchAnalysis is now defined above, so this initialization works
        self.match_analyzer = MatchAnalysis() 

    def get_team_strength_and_avg(self, team_name):
        """Retrieve team strength and goal average"""
        team_key = team_name.lower()
        for key, data in self.team_data.items():
            if key in team_key or team_key in key:
                return data["strength"], data["goal_avg"]
        
        fallback = self.team_data.get("unknown")
        return fallback["strength"], fallback["goal_avg"]
        
    def generate_combined_prediction(self, match_data, team1, team2, send_alert=False):
        """Generates a prediction combining pre-match strength and live score analysis and checks for 85% confidence"""
        strength1, avg1 = self.get_team_strength_and_avg(team1)
        strength2, avg2 = self.get_team_strength_and_avg(team2)
        
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")
        
        if minute == "FT":
            return "🏁 Match is over. Final Score-based Prediction not applicable.", None
        
        # Calculate progress
        progress = 0
        if minute == "HT": progress = 50
        elif minute.isdigit(): progress = min(90, int(minute))
        progress_percent = progress / 90
        
        # --- Prediction Logic (1X2 & O/U) ---
        total_strength = strength1 + strength2
        prob1_base = (strength1 / total_strength) * 100
        prob2_base = (strength2 / total_strength) * 100
        strength_diff_factor = abs(strength1 - strength2) / total_strength
        draw_prob_base = 25 - (strength_diff_factor * 15) 
        
        remaining_prob = 100 - draw_prob_base
        prob1 = (prob1_base / (prob1_base + prob2_base)) * remaining_prob
        prob2 = (prob2_base / (prob1_base + prob2_base)) * remaining_prob
        
        score_diff = home_score - away_score
        
        # Live Adjustment (Simple): If a team is leading 1-0 late (progress_percent > 0.7), their win probability increases
        if abs(score_diff) == 1 and progress_percent > 0.7:
             if score_diff > 0: prob1 += 10; prob2 -= 5 
             else: prob2 += 10; prob1 -= 5
        
        draw_prob = max(0, 100 - prob1 - prob2)
        prob1 = max(0, prob1)
        prob2 = max(0, prob2)
        
        # Normalize to 100%
        final_total = prob1 + prob2 + draw_prob
        prob1 = (prob1 / final_total) * 100
        prob2 = (prob2 / final_total) * 100
        draw_prob = (draw_prob / final_total) * 100

        # Final Winner Determination
        max_prob_1x2 = max(prob1, prob2, draw_prob)
        if max_prob_1x2 == prob1: 
            winner = team1
            market_1x2 = f"{team1} to WIN"
        elif max_prob_1x2 == prob2: 
            winner = team2
            market_1x2 = f"{team2} to WIN"
        else: 
            winner = "DRAW"
            market_1x2 = "DRAW"
            
        # Over/Under Goals Prediction (Simplified)
        over_25_prob = 60 if (avg1 + avg2) > 2.5 else 40
        under_25_prob = 100 - over_25_prob
        
        # Alert Generation Check
        alert_to_send = None
        if send_alert:
            if max_prob_1x2 >= CONFIDENCE_THRESHOLD:
                alert_to_send = {"market": "Match Winner (1X2)", "prediction": market_1x2, "confidence": max_prob_1x2}
            elif max(over_25_prob, under_25_prob) >= CONFIDENCE_THRESHOLD:
                market_ou = "Over 2.5 Goals" if over_25_prob > under_25_prob else "Under 2.5 Goals"
                alert_to_send = {"market": market_ou, "prediction": market_ou, "confidence": max(over_25_prob, under_25_prob)}

        # Format the result for the user response
        result = f"""
**Pre-match & Live Score Model:**
• {team1} WIN: {prob1:.1f}%
• {team2} WIN: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%

🏆 **Current Verdict ({minute}' / {home_score}-{away_score}):**
• **Match Winner:** **{winner.upper()}** ({max_prob_1x2:.1f}%)
• **Goals:** **{'Over 2.5 Goals' if over_25_prob > under_25_prob else 'Under 2.5 Goals'}** ({max(over_25_prob, under_25_prob):.1f}%)

💡 **Insight:**
{self.match_analyzer.generate_simple_score_based_prediction(match_data)}
"""
        return result, alert_to_send

    def get_response(self, message):
        """Processes user message and delegates to the correct function"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'scores']):
            return self.handle_live_matches()
        
        elif any(word in message_lower for word in ['today', 'schedule', 'matches', 'list']):
            return self.handle_todays_matches()
        
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api usage']):
            return self.get_hit_stats_text()
        
        elif any(word in message_lower for word in ['analysis', 'analyze', 'detail', 'report']):
            # For text queries, check if teams are provided
            teams = [key for key in self.team_data if key in message_lower]
            if teams:
                 return self.handle_detailed_analysis("analysis " + " ".join(teams))
            return self.handle_detailed_analysis("analysis") # No team specified

        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'start']):
            return "👋 Hello! I'm **ENHANCED Football Analysis AI**! ⚽\n\n🔍 **Detailed Match Analysis**\n🔄 **Webhook Mode Active**\n\nTry: 'live matches', 'analysis man city', '/today', or '/stats'"
        
        else:
            return "🤔 Sorry, I didn't understand that. Try: `/live`, `/today`, or `/analysis Man City`."
            
    # --- Integration of V2 Handlers (Simplified) ---
    def handle_live_matches(self):
        matches = fetch_api_football_matches(match_live_only=True)
        
        if not matches:
            return "⏳ No live matches found right now."
        
        response = "🔵 **LIVE FOOTBALL MATCHES** ⚽\n\n"
        leagues = {}
        
        for match in matches:
            league = match['league_name']
            if league not in leagues: leagues[league] = []
            leagues[league].append(match)
        
        for league, league_matches in leagues.items():
            response += f"**{league}**\n"
            for match in league_matches:
                status = match.get('match_status')
                icon = "⏱️" if status.isdigit() else "🔄" if status == 'HT' else "🏁"
                response += f"🔵 {match['match_hometeam_name']} {match['match_hometeam_score']}-{match['match_awayteam_score']} {match['match_awayteam_name']} {icon} {status}'\n"
            response += "\n"
        
        response += self.get_hit_stats_text()
        return response

    def handle_todays_matches(self):
        """Handle request for today's scheduled matches (Integrated from V2)"""
        matches = fetch_api_football_matches(match_live_only=False) 
        
        if not matches:
            return "📅 **Today's Schedule**\n\n❌ No matches scheduled for today."
        
        live_matches = [m for m in matches if m.get('match_live') == '1' or m.get('match_status') in ['HT', 'FT', 'AET', 'PEN']]
        upcoming_matches = [m for m in matches if m.get('match_live') != '1' and m.get('match_status') not in ['HT', 'FT', 'AET', 'PEN']]
        
        response = f"📅 **TODAY'S FOOTBALL SCHEDULE ({datetime.now().strftime('%Y-%m-%d')})** ⚽\n\n"
        
        if live_matches:
            response += "--- **🔴 LIVE / FT MATCHES** ---\n"
            for match in live_matches[:5]:
                status = match.get('match_status')
                icon = "⏱️" if status.isdigit() else "🔄" if status == 'HT' else "🏁"
                response += f"{match['league_name']}\n🔵 {match['match_hometeam_name']} {match['match_hometeam_score']}-{match['match_awayteam_score']} {match['match_awayteam_name']} {icon} {status}'\n"
            response += "\n"
            
        if upcoming_matches:
            response += "--- **🕒 UPCOMING MATCHES** ---\n"
            for match in upcoming_matches:
                response += f"📅 {match['league_name']}\n{match['match_hometeam_name']} vs {match['match_awayteam_name']} 🕒 {match['match_time']}\n"
            response += "\n"
            
        return response
        
    def handle_detailed_analysis(self, query):
        """Handle detailed match analysis requests (Integrated V2 logic)"""
        
        teams_found = [key for key in self.team_data if key in query.lower()]
        
        match_data = None
        if teams_found:
            # Simple find by team name in live cache
            for match in match_cache.values():
                home = match.get('match_hometeam_name', '').lower()
                away = match.get('match_awayteam_name', '').lower()
                
                if teams_found[0] in home or teams_found[0] in away:
                    match_data = match
                    break

        if match_data and (match_data.get('match_live') == '1' or match_data.get('match_status') == 'HT'):
            return self.generate_live_match_report(match_data)
        else:
            if teams_found:
                return f"❌ {teams_found[0].title()} is not currently playing live. Use `/live` to see current matches."
            return "❌ Live match not found for analysis. Use `/live` to see current matches."

    def generate_live_match_report(self, match_data):
        """Generates detailed report using Prediction logic and basic info"""
        
        home_team = match_data.get("match_hometeam_name", "Home")
        away_team = match_data.get("match_awayteam_name", "Away")
        
        predictions, _ = self.generate_combined_prediction(match_data, home_team, away_team, send_alert=False)
        
        report = f"""
🔍 **DETAILED MATCH ANALYSIS**

🏆 **{match_data.get('league_name', 'Unknown League')}**

⚽ **{home_team}** {match_data.get('match_hometeam_score', '0')} - {match_data.get('match_awayteam_score', '0')} **{away_team}**

⏱️ **{match_data.get('match_status', 'N/A')}'**

---

🎯 **ENHANCED PREDICTIONS:**
{predictions}

"""
        return report

    def get_hit_stats_text(self):
        """Get API hit status as formatted text"""
        now = datetime.now()
        remaining_daily = max(0, MAX_DAILY_HITS - hit_counter['daily_hits'])
        
        status = f"""
🔥 **API USAGE STATISTICS**

📈 **Current Usage:**
• Today's Hits: {hit_counter['daily_hits']}/{MAX_DAILY_HITS}
• Last Fetch: {last_fetch_time}

🎯 **Remaining Capacity:**
• Daily Remaining: {remaining_daily} calls

💡 **Recommendation:** {'🟢 Safe to continue' if hit_counter['daily_hits'] < MAX_DAILY_HITS else '🔴 LIMIT REACHED'}
"""
        return status


# Initialize Enhanced AI
football_ai = EnhancedFootballAI()

# =======================================================
# 4. HTTP API Manager
# =======================================================

def get_league_name(league_id):
    """Get league name from ID (Simplified)"""
    if league_id == "152": return "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League"
    if league_id == "302": return "🇪🇸 La Liga"
    if league_id == "207": return "🇮🇹 Serie A"
    return f"League {league_id}"

def fetch_api_football_matches(match_live_only=True):
    """Fetch matches from API-Football HTTP API"""
    global hit_counter, last_fetch_time, match_cache
    
    # Check limit
    if hit_counter['daily_hits'] >= MAX_DAILY_HITS and hit_counter['last_reset'] == datetime.now().date():
        logger.warning("🛑 API Limit Reached for today. Serving from cache.")
        return list(match_cache.values())
        
    try:
        # Record hit only if successful, but check limit first.
        
        if match_live_only:
            url = f"{API_FOOTBALL_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
        else:
            today_date = datetime.now().strftime('%Y-%m-%d')
            url = f"{API_FOOTBALL_URL}/?action=get_events&from={today_date}&to={today_date}&APIkey={API_KEY}"
            
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
        
        data = response.json()
        
        if isinstance(data, list):
            # Only count hit if API call was successful
            hit_counter['daily_hits'] += 1
            logger.info(f"✅ API-Football: Found {len(data)} matches. Hit: {hit_counter['daily_hits']}")
            last_fetch_time = datetime.now().strftime('%H:%M:%S UTC')
            
            # Update Cache
            new_cache = {}
            for match in data:
                league_id = match.get("league_id", "")
                match["league_name"] = get_league_name(league_id)
                match_id = match.get("match_id", "")
                new_cache[match_id] = match
            
            match_cache = new_cache
            return data
        else:
            return list(match_cache.values())
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ API-Football Fetch Error: {e}. Serving from cache.")
        return list(match_cache.values())

# =======================================================
# 5. Telegram Handlers and Auto-Updater
# =======================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 **ENHANCED FOOTBALL ANALYSIS BOT (WEBHOOK)** ⚽

🚀 **REAL-TIME ALERTS & TODAY'S SCHEDULE ADDED!**

⚡ **Commands:**
/live - Live matches
/today - Today's full schedule 📅
/analysis - Detailed analysis (e.g. /analysis Man City)
/stats - API hit statistics

⚠️ **Webhook Mode is active.**
"""
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['live', 'today', 'stats'])
def handle_direct_commands(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        command = message.text.lower()
        
        if command.startswith('/live'):
            response = football_ai.handle_live_matches()
        elif command.startswith('/today'):
            response = football_ai.handle_todays_matches()
        elif command.startswith('/stats'):
            response = football_ai.get_hit_stats_text()
        else:
            response = "Command not recognized."
            
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['analysis'])
def send_detailed_analysis(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        command_text = message.text.split(' ', 1)
        query = command_text[1] if len(command_text) > 1 else ""
        
        response = football_ai.handle_detailed_analysis(query)
            
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    """Fallback handler for text messages (e.g., 'live', 'hello')"""
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.get_response(message.text)
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"❌ Text message handler error: {e}")
        bot.reply_to(message, "❌ Sorry, error occurred. Please try again!")

# --- Auto Updater Thread ---
def auto_updater_thread():
    """Fetches matches and checks for high-confidence alerts"""
    logger.info("🚀 Auto-Updater thread started.")
    while True:
        try:
            today = datetime.now().date()
            if hit_counter['last_reset'] != today:
                hit_counter['daily_hits'] = 0
                hit_counter['last_reset'] = today
                logger.info("✅ Daily API Hit Counter Reset.")
                
            # 1. Fetch live matches (updates cache and uses 1 API hit)
            raw_matches = fetch_api_football_matches(match_live_only=True)
            
            # 2. Check for high-confidence alerts (85%+)
            if raw_matches and OWNER_CHAT_ID:
                for match in raw_matches:
                    home_team = match.get("match_hometeam_name", "Home")
                    away_team = match.get("match_awayteam_name", "Away")
                    minute = match.get("match_status", "0")
                    
                    # Only analyze live matches that are not FT or TBD
                    if minute.isdigit() and int(minute) < 90:
                        _, alert_result = football_ai.generate_combined_prediction(match, home_team, away_team, send_alert=True)
                        
                        if alert_result:
                            alert_message = f"""
🔥 **85%+ CONFIDENCE LIVE ALERT!** 🔥
📢 **MATCH:** {home_team} vs {away_team}
🏆 **LEAGUE:** {match.get('league_name', 'Unknown')}
⏱️ **MINUTE:** {minute}' | **SCORE:** {match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}

🎯 **PREDICTION:** **{alert_result['prediction'].upper()}**
📊 **CONFIDENCE:** {alert_result['confidence']:.1f}%

⚠️ *Betting is risky. Use your own discretion.*
"""
                            logger.info(f"✅ ALERT SENT: {alert_result['prediction']} @ {alert_result['confidence']:.1f}%")
                            bot.send_message(OWNER_CHAT_ID, alert_message, parse_mode='Markdown')

            
        except Exception as e:
            logger.error(f"❌ Auto-Updater Error: {e}")
            
        time.sleep(SLEEP_TIME_SECONDS) # Sleeps for 7 minutes

# =======================================================
# 6. Flask Webhook Setup
# =======================================================

@app.before_request
def before_request():
    """Sets the webhook URL before handling any request (Ensures Webhook is always set)"""
    if WEBHOOK_URL and bot.get_webhook_info().url != WEBHOOK_URL:
        try:
            bot.remove_webhook()
            # Set webhook to the full URL including the token
            full_webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
            if bot.set_webhook(url=full_webhook_url):
                logger.info("✅ Webhook successfully set to: %s", full_webhook_url)
            else:
                logger.error("❌ Webhook setup failed.")
        except Exception as e:
            logger.error(f"❌ Webhook setup exception: {e}")
    return

@app.route('/', methods=['GET'])
def index():
    """Simple health check"""
    return 'Bot Webhook is running...', 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Telegram Webhook handler"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Invalid request type', 403

# =======================================================
# 7. Startup
# =======================================================
if __name__ == '__main__':
    # Start the background thread for API calls and Alerts
    threading.Thread(target=auto_updater_thread, daemon=True).start()

    # Start the Flask app using Gunicorn (implied by Railway/Procfile)
    logger.info("INFO:main:Starting Flask/Gunicorn server...")
    app.run(host='0.0.0.0', port=PORT)
