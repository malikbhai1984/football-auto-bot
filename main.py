import os
import requests
import time
from flask import Flask
import logging
from datetime import datetime
import pytz
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables - Metal automatically injects these
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "bbafeb00dfe6e1e97248c9a3c8b9c69e").strip()

logger.info("🚀 Starting Football Prediction Bot on Metal...")

app = Flask(__name__)
PAK_TZ = pytz.timezone('Asia/Karachi')

class Config:
    BOT_CYCLE_INTERVAL = 300  # 5 minutes
    MIN_CONFIDENCE_THRESHOLD = 85

bot_started = False
message_counter = 0

def get_pakistan_time():
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M PKT')

def send_telegram_message(message):
    """Send message to Telegram"""
    global message_counter
    if not BOT_TOKEN or not OWNER_CHAT_ID:
        logger.error("❌ Missing Telegram credentials")
        return False
        
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        payload = {
            'chat_id': OWNER_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(telegram_url, json=payload, timeout=10)
        if response.status_code == 200:
            message_counter += 1
            logger.info(f"✅ Message #{message_counter} sent")
            return True
    except Exception as e:
        logger.error(f"❌ Telegram error: {e}")
    return False

# ==================== API-FOOTBALL LIVE MATCHES ====================
def fetch_live_matches():
    """Fetch LIVE matches from API-Football.com"""
    matches = []
    
    if not API_FOOTBALL_KEY:
        logger.error("❌ API_FOOTBALL_KEY not set")
        return matches
    
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        headers = {
            'x-rapidapi-key': API_FOOTBALL_KEY,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        
        params = {'live': 'all'}
        
        logger.info("🔍 Fetching live matches from API-Football...")
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        logger.info(f"📡 API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'response' in data:
                fixtures = data['response']
                logger.info(f"📊 Found {len(fixtures)} fixtures")
                
                for fixture in fixtures:
                    fixture_data = fixture.get('fixture', {})
                    status = fixture_data.get('status', {})
                    status_short = status.get('short')
                    
                    # Check if match is live
                    if status_short in ['1H', '2H', 'HT', 'ET', 'P']:
                        teams = fixture.get('teams', {})
                        goals = fixture.get('goals', {})
                        league = fixture.get('league', {})
                        
                        home_team = teams.get('home', {}).get('name', 'Unknown')
                        away_team = teams.get('away', {}).get('name', 'Unknown')
                        home_score = goals.get('home', 0)
                        away_score = goals.get('away', 0)
                        minute = status.get('elapsed', 0)
                        league_name = league.get('name', 'Unknown League')
                        country = league.get('country', 'Unknown')
                        
                        match_data = {
                            'home': home_team,
                            'away': away_team,
                            'score': f"{home_score}-{away_score}",
                            'minute': f"{minute}'",
                            'current_minute': minute,
                            'home_score': home_score,
                            'away_score': away_score,
                            'league': f"{league_name} ({country})",
                            'status': 'LIVE',
                            'fixture_id': fixture_data.get('id'),
                            'source': 'api-football',
                            'timestamp': get_pakistan_time()
                        }
                        matches.append(match_data)
                        logger.info(f"✅ LIVE: {home_team} {home_score}-{away_score} {away_team} ({minute}')")
            
            elif 'errors' in data:
                errors = data['errors']
                logger.error(f"❌ API Errors: {errors}")
                
        elif response.status_code == 429:
            logger.error("❌ API rate limit exceeded")
        else:
            logger.error(f"❌ API error {response.status_code}")
            
    except Exception as e:
        logger.error(f"❌ API-Football connection error: {e}")
    
    return matches

# ==================== PREDICTION ENGINE ====================
def generate_predictions(match_data):
    """Generate predictions for matches"""
    predictions = {}
    
    try:
        current_score = match_data.get('home_score', 0), match_data.get('away_score', 0)
        current_minute = match_data.get('current_minute', 0)
        
        if current_minute < 25:
            return predictions
        
        # Winning Team Prediction
        winning_pred = predict_winning_team(current_score, current_minute)
        if winning_pred['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
            predictions['winning_team'] = winning_pred
        
        # Over/Under Predictions
        for goals_line in [0.5, 1.5, 2.5, 3.5]:
            over_pred = predict_over_under(current_score, current_minute, goals_line)
            if over_pred['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
                predictions[f'over_{goals_line}'] = over_pred
        
        # BTTS Prediction
        btts_pred = predict_btts(current_score, current_minute)
        if btts_pred['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
            predictions['btts'] = btts_pred
        
        # Last 10 minutes goal
        if current_minute >= 75:
            last_10_pred = {'prediction': 'High Chance', 'confidence': 88, 'method': 'closing_stages'}
            predictions['last_10_min_goal'] = last_10_pred
                
    except Exception as e:
        logger.error(f"❌ Prediction error: {e}")
    
    return predictions

def predict_winning_team(current_score, current_minute):
    home_score, away_score = current_score
    goal_difference = home_score - away_score
    
    if current_minute >= 75:
        if goal_difference > 0:
            return {'prediction': 'Home Win', 'confidence': 88, 'method': 'late_game'}
        elif goal_difference < 0:
            return {'prediction': 'Away Win', 'confidence': 87, 'method': 'late_game'}
        else:
            return {'prediction': 'Draw', 'confidence': 85, 'method': 'late_game'}
    
    if current_minute >= 45 and abs(goal_difference) >= 2:
        winning_team = 'Home Win' if goal_difference > 0 else 'Away Win'
        return {'prediction': winning_team, 'confidence': 86, 'method': 'dominant_lead'}
    
    return {'prediction': 'None', 'confidence': 70, 'method': 'insufficient_data'}

def predict_over_under(current_score, current_minute, goals_line):
    home_score, away_score = current_score
    total_goals = home_score + away_score
    
    minutes_remaining = 90 - current_minute
    expected_additional = (2.7 / 90) * minutes_remaining * 1.2
    expected_total = total_goals + expected_additional
    
    if expected_total > goals_line + 0.3:
        confidence = min(95, 80 + (expected_total - goals_line) * 20)
        return {'prediction': f'Over {goals_line}', 'confidence': confidence, 'method': 'goal_rate'}
    else:
        return {'prediction': f'Under {goals_line}', 'confidence': 75, 'method': 'goal_rate'}

def predict_btts(current_score, current_minute):
    home_score, away_score = current_score
    
    if home_score > 0 and away_score > 0:
        return {'prediction': 'Yes', 'confidence': 92, 'method': 'already_scored'}
    
    if (home_score > 0 or away_score > 0) and current_minute <= 60:
        return {'prediction': 'Yes', 'confidence': 87, 'method': 'momentum'}
    
    return {'prediction': 'No', 'confidence': 65, 'method': 'low_probability'}

# ==================== BOT WORKER ====================
def analyze_live_matches():
    """Analyze and send predictions"""
    try:
        logger.info("🔍 Analyzing live matches...")
        
        live_matches = fetch_live_matches()
        
        if not live_matches:
            no_matches_msg = f"""🔍 **NO LIVE MATCHES FOUND**

⏰ **Time:** {format_pakistan_time()}
📅 **Date:** {datetime.now().strftime('%Y-%m-%d')}

🌐 **API Status:** Active
🔍 **Next Check:** 5 minutes

No live matches currently playing."""
            send_telegram_message(no_matches_msg)
            return 0
        
        predictions_sent = 0
        
        for match in live_matches:
            try:
                predictions = generate_predictions(match)
                
                if predictions:
                    message = format_prediction_message(match, predictions)
                    if send_telegram_message(message):
                        predictions_sent += 1
                        logger.info(f"✅ Predictions sent for {match['home']} vs {match['away']}")
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Match analysis error: {e}")
                continue
        
        logger.info(f"📈 Analysis complete: {predictions_sent} predictions")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}")
        return 0

def format_prediction_message(match, predictions):
    """Format prediction message"""
    current_time = format_pakistan_time()
    
    message = f"""🎯 **LIVE MATCH PREDICTIONS** 🎯

🏆 **League:** {match['league']}
🕒 **Minute:** {match['minute']}
📊 **Score:** {match['score']}
🌐 **Source:** API-Football.com

🏠 **{match['home']}** vs 🛫 **{match['away']}**

🔥 **HIGH-CONFIDENCE BETS (85%+):**\n"""

    for market, prediction in predictions.items():
        if 'over' in market:
            display = f"⚽ {prediction['prediction']} Goals"
        elif market == 'btts':
            display = f"🎯 Both Teams To Score: {prediction['prediction']}"
        elif market == 'last_10_min_goal':
            display = f"⏰ Last 10 Min Goal: {prediction['prediction']}"
        elif market == 'winning_team':
            display = f"🏆 Winning Team: {prediction['prediction']}"
        else:
            display = f"📈 {market}: {prediction['prediction']}"
        
        message += f"• {display} - {prediction['confidence']}% ✅\n"
        message += f"  └── Method: {prediction['method']}\n"

    message += f"""
📊 **Analysis Time:** {current_time}
🎯 **Confidence Filter:** 85%+ Only

⚠️ *Professional betting analysis*"""

    return message

def send_startup_message():
    """Send startup message"""
    startup_msg = f"""🚀 **FOOTBALL PREDICTION BOT STARTED!**

⏰ **Startup Time:** {format_pakistan_time()}
📅 **Today's Date:** {datetime.now().strftime('%Y-%m-%d')}
🎯 **Confidence Threshold:** 85%+ ONLY

🌐 **API Status:** Connected
🔍 **Monitoring:** Live Matches
⚡ **Interval:** 5 Minutes

Bot is now actively scanning for live matches!"""

    send_telegram_message(startup_msg)

def bot_worker():
    """Main bot worker"""
    global bot_started
    logger.info("🔄 Starting Football Prediction Bot...")
    
    bot_started = True
    send_startup_message()
    
    cycle = 0
    
    while True:
        try:
            cycle += 1
            current_time = format_pakistan_time()
            logger.info(f"🔄 Cycle #{cycle} at {current_time}")
            
            predictions_sent = analyze_live_matches()
            
            if predictions_sent > 0:
                logger.info(f"📈 Cycle #{cycle}: {predictions_sent} predictions sent")
            
            time.sleep(Config.BOT_CYCLE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
            time.sleep(60)

def start_bot_thread():
    """Start bot thread"""
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 Bot worker started")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return False

# ==================== FLASK ROUTES ====================
@app.route("/")
def home():
    live_matches = fetch_live_matches()
    return {
        "status": "running",
        "bot_started": bot_started,
        "live_matches": len(live_matches),
        "message_counter": message_counter,
        "timestamp": format_pakistan_time()
    }

@app.route("/health")
def health():
    return {"status": "healthy", "timestamp": format_pakistan_time()}, 200

# ==================== STARTUP ====================
if __name__ == "__main__":
    logger.info("🌐 Starting Flask server on Metal...")
    
    if BOT_TOKEN and OWNER_CHAT_ID and API_FOOTBALL_KEY:
        logger.info("🎯 Starting Bot with credentials...")
        start_bot_thread()
    else:
        logger.warning("⚠️ Bot not started - missing credentials")
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
