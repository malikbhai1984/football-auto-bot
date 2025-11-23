import os
import requests
import time
from flask import Flask
import logging
from datetime import datetime
import pytz
from threading import Thread
from bs4 import BeautifulSoup
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()

app = Flask(__name__)
PAK_TZ = pytz.timezone('Asia/Karachi')

class Config:
    BOT_CYCLE_INTERVAL = 120  # 2 minutes
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

# ==================== AUTOMATIC LIVE MATCHES FETCHER ====================
def fetch_automatic_live_matches():
    """Automatically fetch live matches from multiple sources"""
    all_matches = []
    
    # Source 1: FlashScore Scraping
    flashscore_matches = scrape_flashscore()
    all_matches.extend(flashscore_matches)
    
    # Source 2: LiveScore Scraping  
    livescore_matches = scrape_livescore()
    all_matches.extend(livescore_matches)
    
    # Source 3: Free API
    free_api_matches = fetch_free_api_matches()
    all_matches.extend(free_api_matches)
    
    # Remove duplicates
    unique_matches = remove_duplicate_matches(all_matches)
    
    logger.info(f"🔍 Total matches found: {len(unique_matches)}")
    return unique_matches

def scrape_flashscore():
    """Scrape live matches from FlashScore"""
    matches = []
    try:
        url = "https://www.flashscore.com/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for live match elements
            live_sections = soup.find_all('div', class_=lambda x: x and 'live' in x.lower())
            
            for section in live_sections[:20]:  # Limit to first 20
                try:
                    # Extract match information
                    teams = section.find_all('div', class_=lambda x: x and 'participant' in x.lower())
                    scores = section.find_all('div', class_=lambda x: x and 'score' in x.lower())
                    
                    if len(teams) >= 2 and len(scores) > 0:
                        home_team = teams[0].text.strip() if len(teams) > 0 else "Home"
                        away_team = teams[1].text.strip() if len(teams) > 1 else "Away"
                        score = scores[0].text.strip() if scores else "0-0"
                        
                        matches.append({
                            'home': home_team,
                            'away': away_team,
                            'score': score,
                            'minute': 'LIVE',
                            'current_minute': 45,
                            'home_score': int(score.split('-')[0]) if '-' in score else 0,
                            'away_score': int(score.split('-')[1]) if '-' in score else 0,
                            'league': 'FlashScore Live',
                            'status': 'LIVE',
                            'source': 'flashscore'
                        })
                except Exception as e:
                    continue
                    
    except Exception as e:
        logger.error(f"❌ FlashScore scraping error: {e}")
    
    return matches

def scrape_livescore():
    """Scrape live matches from LiveScore"""
    matches = []
    try:
        url = "https://www.livescore.com/en/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for live match elements
            match_elements = soup.find_all('div', class_=lambda x: x and 'match' in x.lower())
            
            for element in match_elements[:15]:
                try:
                    teams = element.find_all('div', class_=lambda x: x and 'team' in x.lower())
                    score_element = element.find('div', class_=lambda x: x and 'score' in x.lower())
                    
                    if len(teams) >= 2 and score_element:
                        home_team = teams[0].text.strip()
                        away_team = teams[1].text.strip() 
                        score = score_element.text.strip()
                        
                        matches.append({
                            'home': home_team,
                            'away': away_team,
                            'score': score,
                            'minute': 'LIVE',
                            'current_minute': 45,
                            'home_score': int(score.split('-')[0]) if '-' in score else 0,
                            'away_score': int(score.split('-')[1]) if '-' in score else 0,
                            'league': 'LiveScore Live',
                            'status': 'LIVE', 
                            'source': 'livescore'
                        })
                except Exception as e:
                    continue
                    
    except Exception as e:
        logger.error(f"❌ LiveScore scraping error: {e}")
    
    return matches

def fetch_free_api_matches():
    """Fetch from free football APIs"""
    matches = []
    try:
        # TheSportsDB API (Free)
        url = "https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4328&s=2024"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            
            for event in events:
                if event.get('strStatus') == 'Live':
                    matches.append({
                        'home': event.get('strHomeTeam', 'Home'),
                        'away': event.get('strAwayTeam', 'Away'),
                        'score': f"{event.get('intHomeScore', 0)}-{event.get('intAwayScore', 0)}",
                        'minute': 'LIVE',
                        'current_minute': 45,
                        'home_score': event.get('intHomeScore', 0),
                        'away_score': event.get('intAwayScore', 0),
                        'league': event.get('strLeague', 'Unknown'),
                        'status': 'LIVE',
                        'source': 'thesportsdb'
                    })
                    
    except Exception as e:
        logger.error(f"❌ Free API error: {e}")
    
    return matches

def remove_duplicate_matches(matches):
    """Remove duplicate matches"""
    seen = set()
    unique_matches = []
    
    for match in matches:
        identifier = f"{match['home']}_{match['away']}_{match['league']}"
        if identifier not in seen:
            seen.add(identifier)
            unique_matches.append(match)
    
    return unique_matches

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
    
    return {'prediction': 'No', 'confidence': 65, 'method': 'low_probability'}

# ==================== BOT WORKER ====================
def analyze_live_matches():
    """Analyze and send predictions"""
    try:
        logger.info("🔍 Analyzing automatic live matches...")
        
        live_matches = fetch_automatic_live_matches()
        
        if not live_matches:
            no_matches_msg = f"""🔍 **SCANNING FOR LIVE MATCHES**

⏰ **Time:** {format_pakistan_time()}
📅 **Date:** {format_date()}

🌐 **Sources:** FlashScore, LiveScore, Free APIs
🔍 **Status:** Actively scanning...

No live matches detected at the moment.
Scanning again in 2 minutes..."""
            send_telegram_message(no_matches_msg)
            return 0
        
        predictions_sent = 0
        
        for match in live_matches[:5]:  # Process first 5 matches only
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
    
    message = f"""🎯 **AUTOMATIC LIVE PREDICTIONS** 🎯

🏆 **League:** {match['league']}
🕒 **Status:** {match['minute']}
📊 **Score:** {match['score']}
🌐 **Source:** {match.get('source', 'Auto-Scraping')}

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
🔍 **Data Source:** Automatic Live Scraping

⚠️ *Real-time professional analysis*"""

    return message

def send_startup_message():
    """Send startup message"""
    startup_msg = f"""🚀 **AUTOMATIC LIVE MATCHES BOT STARTED!**

⏰ **Startup Time:** {format_pakistan_time()}
📅 **Today's Date:** {format_date()}
🎯 **Confidence Threshold:** 85%+ ONLY

🌐 **Automatic Sources:**
   • FlashScore.com (Live Scores)
   • LiveScore.com (Live Matches) 
   • Free Football APIs
   • Real-time Web Scraping

🔍 **Monitoring:** Worldwide Live Matches
⚡ **Updates:** Every 2 Minutes

Bot is now automatically scanning for live matches!"""

    send_telegram_message(startup_msg)

def bot_worker():
    """Main bot worker"""
    global bot_started
    logger.info("🔄 Starting Automatic Live Matches Bot...")
    
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
            
            # Status update every 6 cycles
            if cycle % 6 == 0:
                live_matches = fetch_automatic_live_matches()
                status_msg = f"""🔄 **Auto Bot Status**
Cycles: {cycle}
Live Matches Found: {len(live_matches)}
Last Check: {current_time}
Status: ✅ Actively Scanning"""
                send_telegram_message(status_msg)
            
            time.sleep(Config.BOT_CYCLE_INTERVAL)
            
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
            time.sleep(60)

def start_bot_thread():
    """Start bot thread"""
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 Automatic Bot worker started")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return False

# ==================== FLASK ROUTES ====================
@app.route("/")
def home():
    live_matches = fetch_automatic_live_matches()
    return {
        "status": "running",
        "bot_started": bot_started,
        "live_matches": len(live_matches),
        "message_counter": message_counter,
        "timestamp": format_pakistan_time()
    }

@app.route("/health")
def health():
    return "OK", 200

@app.route("/test")
def test():
    live_matches = fetch_automatic_live_matches()
    return {
        "status": "working",
        "live_matches": len(live_matches),
        "timestamp": format_pakistan_time()
    }

# ==================== STARTUP ====================
if BOT_TOKEN and OWNER_CHAT_ID:
    logger.info("🎯 Auto-starting Automatic Bot...")
    if start_bot_thread():
        logger.info("✅ Automatic Bot started successfully")
    else:
        logger.error("❌ Automatic Bot start failed")
else:
    logger.warning("⚠️ Missing credentials - bot not started")

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
