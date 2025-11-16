import os
import time
import threading
import json
import random
import requests
import logging # Correct logging import
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Third-party libraries
from telebot import TeleBot 
from telebot.types import Message
from flask import Flask, request

# =======================================================
# 1. Environment and Configuration
# =======================================================
load_dotenv()

# --- Load API Keys and Settings ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
BACKUP_API_KEY = os.getenv('BACKUP_API_KEY', None)
OWNER_CHAT_ID = os.getenv('OWNER_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# --- CONFIGURATION (Targeted Leagues and Stability) ---
# Add your top 10 League IDs here, separated by commas (Example IDs are placeholders)
TARGET_LEAGUE_IDS = os.getenv('TARGET_LEAGUE_IDS', "39,140,78,135,61,2,3,10") 

MAX_DAILY_HITS = 1000 # Actual API-Football Limit
SLEEP_TIME_SECONDS = 420 # 7 minutes interval for API calls
CONFIDENCE_THRESHOLD = 85.0 # Minimum confidence for expert bet alert
GITHUB_DATA_URL = os.getenv('GITHUB_DATA_URL', '') # Raw link to your Historical CSV/JSON data
ODDS_API_KEY = os.getenv('ODDS_API_KEY', None) # The Odds API Key (for future use)

# --- Initialization ---
app = Flask(__name__)
bot = TeleBot(BOT_TOKEN)

# FIX: Define logger correctly, which caused the Gunicorn crash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('FootballBot') 

# Global State
hit_counter = {'daily_hits': 0, 'last_reset': datetime.now().date()}
match_cache = {}
expert_predictions = {}
last_fetch_time = "N/A"

# =======================================================
# 2. Enhanced Prediction Core (V10 AI/ML Logic)
# =======================================================

class EnhancedFootballAI:
    def __init__(self):
        # Static Mocked Data (Fallback if GitHub fails)
        self.team_data = {
            'Liverpool': {'strength': 93, 'avg_goals': 2.3, 'def_rating': 90},
            'Man City': {'strength': 95, 'avg_goals': 2.5, 'def_rating': 95},
            # Add other key teams you track
        }
        self.historical_data = self._load_historical_data() 
        logger.info(f"AI Core Loaded. Historical Data status: {bool(self.historical_data)}")

    def _load_historical_data(self):
        """Fetches historical data from GitHub. (Assumes simple JSON/Dictionary structure)."""
        if not GITHUB_DATA_URL:
            logger.warning("❌ GITHUB_DATA_URL not configured.")
            return {}
        
        try:
            response = requests.get(GITHUB_DATA_URL, timeout=10)
            response.raise_for_status()
            logger.info("✅ Historical data loaded successfully from GitHub.")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch data from GitHub. Error: {e}")
            return {}

    def _get_h2h_factor(self, team1: str, team2: str) -> float:
        """Placeholder for H2H factor logic using loaded historical data."""
        # --- AI/ML LEVEL LOGIC: You will implement your parsing here ---
        if self.historical_data:
            # Example: If historical data favors team1, return 1.05.
            return random.uniform(0.98, 1.05) 
        return 1.0

    def _calculate_1x2_probability(self, team1, team2, minute, score_live):
        # V10 LOGIC: Use Static Strength + H2H Factor + Live Score Factor
        s1 = self.team_data.get(team1, {'strength': 75})['strength'] * self._get_h2h_factor(team1, team2)
        s2 = self.team_data.get(team2, {'strength': 75})['strength']
        
        # Simple Math (Replace with your detailed V7 math if available)
        total_s = s1 + s2
        prob_w1 = (s1 / total_s) * 100
        prob_w2 = (s2 / total_s) * 100
        prob_d = 100 - prob_w1 - prob_w2 
        
        # Live Score Adjustment: If a team leads late, their win prob goes up
        if minute > 60 and score_live['home'] > score_live['away']:
             prob_w1 += 10 # Example adjustment
        
        return prob_w1, prob_d, prob_w2

    def _calculate_btts_probability(self, team1_name, team2_name, minute, score_live):
        # V10 LOGIC: Based on Goal Averages + Live Minute Factor
        avg1 = self.team_data.get(team1_name, {'avg_goals': 1.5})['avg_goals']
        avg2 = self.team_data.get(team2_name, {'avg_goals': 1.5})['avg_goals']
        
        prob_yes = (avg1 + avg2) / 3.5 * 100 # Simple estimation
        
        # Live Adjustment: If both teams scored in the first half, confidence increases
        if score_live['home'] >= 1 and score_live['away'] >= 1:
            return 95.0
        
        return min(prob_yes, 99.0)

    def _calculate_over_under_probability_all(self, team1, team2, minute, score_live):
        """Calculates and returns the most confident O/U bet."""
        # V10 LOGIC: Check O/U 2.5
        avg_total = self.team_data.get(team1, {'avg_goals': 1.5})['avg_goals'] + self.team_data.get(team2, {'avg_goals': 1.5})['avg_goals']
        
        # If avg_total is high and score is low, predict OVER
        if avg_total >= 4.0 and score_live['home'] + score_live['away'] <= 2 and minute < 70:
            return {'market': 'O/U 2.5', 'type': 'OVER', 'confidence': 90.0}
        
        # If low scoring teams and score is 0-0 late, predict UNDER
        if avg_total < 3.0 and score_live['home'] + score_live['away'] == 0 and minute > 70:
            return {'market': 'O/U 2.5', 'type': 'UNDER', 'confidence': 86.0}

        return None

    def _check_last_10_min_goal(self, minute, score_live):
        """High confidence for Late Goal if score is tight and minute > 80."""
        # V10 LOGIC: Check for Late Goal
        current_total = score_live['home'] + score_live['away']
        if minute >= 80 and abs(score_live['home'] - score_live['away']) <= 1 and current_total >= 1:
            return {'market': 'Late Goal (80+)', 'type': 'YES', 'confidence': 90.0}
        return None

    def analyze_and_select_expert_bet(self, fixture: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Checks all markets and selects the highest confidence bet (>= 85%)."""
        
        match_info = fixture['fixture']
        teams = fixture['teams']
        
        team1 = teams['home']['name']
        team2 = teams['away']['name']
        minute = match_info['status']['elapsed']
        score_live = fixture['goals']

        # 1. Calculate All Markets
        prob_w1, prob_d, prob_w2 = self._calculate_1x2_probability(team1, team2, minute, score_live)
        prob_btts_yes = self._calculate_btts_probability(team1, team2, minute, score_live)
        best_ou = self._calculate_over_under_probability_all(team1, team2, minute, score_live)
        late_goal = self._check_last_10_min_goal(minute, score_live)

        # 2. Select Best Bet (>= CONFIDENCE_THRESHOLD)
        best_bet = None
        max_conf = CONFIDENCE_THRESHOLD 

        # Check 1X2
        if prob_w1 >= max_conf:
            max_conf = prob_w1
            best_bet = {'market': 'Match Winner', 'type': f'{team1} Win', 'confidence': prob_w1}
        # You can add checks for Draw and Away Win here similarly.

        # Check BTTS
        if prob_btts_yes >= max_conf:
            max_conf = prob_btts_yes
            best_bet = {'market': 'BTTS', 'type': 'YES', 'confidence': prob_btts_yes}

        # Check O/U
        if best_ou and best_ou['confidence'] >= max_conf:
            max_conf = best_ou['confidence']
            best_bet = best_ou

        # Check Late Goal
        if late_goal and late_goal['confidence'] >= max_conf:
            max_conf = late_goal['confidence']
            best_bet = late_goal

        return best_bet

AI_MODEL = EnhancedFootballAI()

# =======================================================
# 3. HTTP API Manager (Targeted Fetch and Backup)
# =======================================================

class HTTPAPIManager:
    def __init__(self, primary_key, backup_key):
        self.primary_key = primary_key
        self.backup_key = backup_key
        self.key_status = {primary_key: 'active', backup_key: 'active' if backup_key else 'inactive'}
        
    def fetch_api_football_matches(self, match_live_only: bool = True) -> List[Dict[str, Any]]:
        """Fetches targeted matches using primary key, switches to backup on failure/limit."""
        global hit_counter, last_fetch_time
        
        if hit_counter['daily_hits'] >= MAX_DAILY_HITS:
            logger.warning("🛑 API Limit Reached for today. Serving from cache.")
            return list(match_cache.values())

        url = "https://v3.football.api-sports.io/fixtures"
        today = datetime.now().strftime('%Y-%m-%d')
        
        # V10 Targeted Fetch
        params = {
            'date': today,
            'status': 'TBD-PST' if not match_live_only else 'LIVE-HT-ET-BT',
            'league': TARGET_LEAGUE_IDS # Only fetch required leagues!
        }
        
        keys_to_try = [self.primary_key]
        if self.backup_key: keys_to_try.append(self.backup_key)
        
        for key in keys_to_try:
            if self.key_status.get(key) == 'inactive': continue
            
            headers = {'x-apisports-key': key}
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status() 

                if response.status_code == 429:
                    logger.warning(f"⚠️ Key {key[:4]}... hit Rate Limit (429).")
                    self.key_status[key] = 'inactive'
                    continue 
                    
                hit_counter['daily_hits'] += 1
                last_fetch_time = datetime.now().strftime('%H:%M:%S UTC')
                data = response.json().get('response', [])
                
                # Update Cache
                for fix in data:
                    fixture_id = fix['fixture']['id']
                    match_cache[fixture_id] = fix
                return data
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Key {key[:4]}... failed with Error: {e}")
                if '401' in str(e) or '403' in str(e): 
                    self.key_status[key] = 'inactive'
                continue 
        
        logger.error("🚫 All API keys failed or hit limit. Serving from cache.")
        return list(match_cache.values())

API_MANAGER = HTTPAPIManager(API_KEY, BACKUP_API_KEY)


def fetch_live_odds(match_id):
    """Placeholder function for The Odds API call."""
    if not ODDS_API_KEY:
        return None
    
    # You will implement the actual API call here when you get the key.
    return {"odds_ou_2.5": 1.95, "odds_1x2_home": 2.50}


# =======================================================
# 4. Telegram Handlers and Auto-Updater
# =======================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 **Welcome to the Football Prediction Bot V10!**\n\n"
        "I provide high-confidence bets using Live Scores, Historical Data, and Multi-Market analysis.\n\n"
        "Commands:\n"
        "/live - Show current live matches (if any).\n"
        "/expert_bet - Get the most confirmed bet (85%+ Confidence).\n"
        "/stats - Check API usage and status."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['stats', 'hits'])
def send_stats(message):
    stats_text = (
        f"🔥 **API Usage Statistics**\n"
        f"🌐 Status: {'✅ LIVE' if hit_counter['daily_hits'] < MAX_DAILY_HITS else '🛑 LIMIT REACHED'}\n"
        f"📊 Calls Used: {hit_counter['daily_hits']}/{MAX_DAILY_HITS}\n"
        f"🕒 Last Fetch: {last_fetch_time}\n"
        f"🔄 Next Reset: {hit_counter['last_reset']}\n"
    )
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['expert_bet'])
def send_expert_bet(message):
    fixtures = API_MANAGER.fetch_api_football_matches(match_live_only=True)
    
    if not fixtures:
        bot.send_message(message.chat.id, "⏳ No live fixtures or cache available right now.")
        return

    best_overall_bet = None
    max_conf = CONFIDENCE_THRESHOLD 

    for fixture in fixtures:
        best_bet = AI_MODEL.analyze_and_select_expert_bet(fixture)
        
        if best_bet and best_bet['confidence'] >= max_conf:
            max_conf = best_bet['confidence']
            best_overall_bet = best_bet
            best_overall_bet['teams'] = f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']}"
            best_overall_bet['minute'] = fixture['fixture']['status']['elapsed']

    if best_overall_bet:
        bet_message = (
            f"👑 **EXPERT BET CONFIRMED (V10 AI)**\n"
            f"--- ⚽ {best_overall_bet['teams']} ---\n"
            f"⏱️ Minute: {best_overall_bet['minute']}'\n"
            f"📈 **Prediction:** {best_overall_bet['market']} - {best_overall_bet['type']}\n"
            f"🔥 **Confidence:** {best_overall_bet['confidence']:.2f}%\n"
            f"\n_This prediction exceeds {CONFIDENCE_THRESHOLD}% confidence._"
        )
        bot.send_message(message.chat.id, bet_message, parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, f"❌ NO {CONFIDENCE_THRESHOLD}% BET FOUND right now. Try again later.")

# --- Auto Updater Thread ---
def auto_updater_thread():
    logger.info("🚀 Auto-Updater thread started.")
    while True:
        try:
            today = datetime.now().date()
            if hit_counter['last_reset'] != today:
                hit_counter['daily_hits'] = 0
                hit_counter['last_reset'] = today
                logger.info("✅ Daily API Hit Counter Reset.")
                
            fixtures = API_MANAGER.fetch_api_football_matches(match_live_only=True)
            logger.info(f"✅ Fetched {len(fixtures)} targeted live fixtures. Hits: {hit_counter['daily_hits']}/{MAX_DAILY_HITS}")
            
        except Exception as e:
            logger.error(f"❌ Auto-Updater Error: {e}")
            
        time.sleep(SLEEP_TIME_SECONDS) # Sleeps for 7 minutes

# =======================================================
# 5. Flask Webhook Setup
# =======================================================

@app.before_request
def before_request():
    """Sets or verifies the webhook URL before handling any request."""
    if WEBHOOK_URL and bot.get_webhook_info().url != WEBHOOK_URL:
        try:
            bot.remove_webhook()
            if bot.set_webhook(url=WEBHOOK_URL):
                logger.info("✅ Webhook successfully set to: %s", WEBHOOK_URL)
            else:
                logger.error("❌ Webhook setup failed.")
        except Exception as e:
            logger.error(f"❌ Webhook setup exception: {e}")
    return

@app.route('/', methods=['GET'])
def index():
    return 'Bot is running...', 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = TeleBot.to_dict(json.loads(json_string))
        bot.process_new_updates([TeleBot.Update.de_json(update)])
        return 'OK', 200
    else:
        return 'Invalid request type', 403

if __name__ == '__main__':
    # Start the background thread
    threading.Thread(target=auto_updater_thread, daemon=True).start()

    # Start the Flask app
    logger.info("INFO:main:Starting gunicorn...")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
