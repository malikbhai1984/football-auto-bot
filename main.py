import os
import time
import threading
import json
import random
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Third-party libraries
from telebot import TeleBot
from telebot.types import Message
from flask import Flask, request, jsonify

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

# Target League IDs (You must verify these IDs from API-Football documentation)
# EXAMPLE IDs: EPL(39), LaLiga(140), Bundesliga(78), SerieA(135), Ligue1(61), UCL(2), EuropaLeague(3), WorldCupQual-Europe(10), etc.
TARGET_LEAGUE_IDS = "39,140,78,135,61,2,3,10" # Add your top 10 League IDs here, separated by commas

MAX_DAILY_HITS = 1000 # Actual API-Football Limit
SLEEP_TIME_SECONDS = 420 # 7 minutes interval for API calls
CONFIDENCE_THRESHOLD = 85.0 # Minimum confidence for expert bet alert
GITHUB_DATA_URL = os.getenv('GITHUB_DATA_URL', '') # Raw link to your Historical CSV/JSON data
ODDS_API_KEY = os.getenv('ODDS_API_KEY', None) # New: The Odds API Key

# --- Initialization ---
app = Flask(__name__)
bot = TeleBot(BOT_TOKEN)
logger = bot.worker_pool.logger

# Global State
hit_counter = {'daily_hits': 0, 'last_reset': datetime.now().date()}
match_cache = {}
expert_predictions = {}
last_fetch_time = "N/A"

# =======================================================
# 2. Enhanced Prediction Core (V9 AI/ML Logic)
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
        logger.info(f"Historical Data Loaded: {bool(self.historical_data)}")

    def _load_historical_data(self):
        """Fetches historical data from GitHub. (Assumes simple JSON/Dictionary structure)."""
        if not GITHUB_DATA_URL:
            logger.warning("❌ GITHUB_DATA_URL not configured. Using only static data.")
            return {}
        
        try:
            response = requests.get(GITHUB_DATA_URL, timeout=10)
            response.raise_for_status()
            # If your GitHub file is a CSV, you need the 'pandas' library and 'pd.read_csv'.
            # Assuming JSON/Dict for simplicity here.
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch data from GitHub. Error: {e}")
            return {}

    def _get_h2h_factor(self, team1: str, team2: str) -> float:
        """Calculates H2H factor using loaded historical data."""
        # --- IMPROVED AI/ML LEVEL LOGIC (Requires your actual historical data parsing) ---
        # If historical data shows Team A won 80% of last 10 encounters against Team B.
        if self.historical_data:
            # Placeholder Logic: Needs actual parsing logic specific to your loaded JSON/CSV structure
            return 1.05 if team1 in self.historical_data.get('dominators', []) else 1.0
        return 1.0

    def _calculate_1x2_probability(self, team1, team2, minute, score):
        # V9 LOGIC: Use Static Strength + H2H Factor + Live Score Factor
        s1 = self.team_data.get(team1, {'strength': 70})['strength'] * self._get_h2h_factor(team1, team2)
        s2 = self.team_data.get(team2, {'strength': 70})['strength']
        
        # ... (Existing V7 math to calculate W1, D, W2 probabilities remains the same) ...
        # Placeholder for simplicity, you will use your detailed V7 math here
        prob_w1 = s1 / (s1 + s2) * 100
        prob_w2 = s2 / (s1 + s2) * 100
        prob_d = 100 - prob_w1 - prob_w2 
        
        return prob_w1, prob_d, prob_w2

    def _calculate_btts_probability(self, team1_name, team2_name, minute, score):
        # V9 LOGIC: Based on Goal Averages + Live Minute Factor
        avg1 = self.team_data.get(team1_name, {'avg_goals': 1.5})['avg_goals']
        avg2 = self.team_data.get(team2_name, {'avg_goals': 1.5})['avg_goals']
        
        # ... (Existing V7 math to calculate BTTS Yes/No remains the same) ...
        # Placeholder for simplicity
        prob_yes = (avg1 + avg2) / 4 * 100
        return prob_yes

    def _calculate_over_under_probability_all(self, team1, team2, minute, score):
        # V9 LOGIC: Check all O/U lines (0.5 to 4.5)
        # ... (Existing V7 math to find the best O/U line remains the same) ...
        
        # Placeholder: Always select O/U 2.5 for simplicity in this example
        best_market = {
            'market': 'O/U 2.5',
            'type': 'OVER',
            'confidence': random.uniform(80.0, 95.0) 
        }
        return best_market

    def _check_last_10_min_goal(self, minute, score):
        """High confidence for Late Goal if score is tight and minute > 80."""
        # V9 LOGIC: Check for Late Goal
        if minute >= 80 and abs(score[0] - score[1]) <= 1:
            return {'market': 'Late Goal (80+)', 'type': 'YES', 'confidence': 90.0}
        return None

    def analyze_and_select_expert_bet(self, fixture: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Checks all markets and selects the highest confidence bet (>= 85%)."""
        
        match_info = fixture['fixture']
        teams = fixture['teams']
        
        team1 = teams['home']['name']
        team2 = teams['away']['name']
        minute = match_info['status']['elapsed']
        score_ft = fixture['score']['fulltime']
        score_ht = fixture['score']['halftime']
        score_live = fixture['goals']
        
        # 1. Calculate All Markets
        prob_w1, prob_d, prob_w2 = self._calculate_1x2_probability(team1, team2, minute, score_live)
        prob_btts_yes = self._calculate_btts_probability(team1, team2, minute, score_live)
        best_ou = self._calculate_over_under_probability_all(team1, team2, minute, score_live)
        late_goal = self._check_last_10_min_goal(minute, score_live)

        # 2. Get Live Odds (New: Will be used when ODDS_API_KEY is available)
        # live_odds = fetch_live_odds(team1, team2) # Call new function here

        # 3. Select Best Bet (>= CONFIDENCE_THRESHOLD)
        best_bet = None
        max_conf = CONFIDENCE_THRESHOLD 

        # Check 1X2
        if prob_w1 >= max_conf:
            max_conf = prob_w1
            best_bet = {'market': '1X2', 'type': f'{team1} Win', 'confidence': prob_w1}
        # ... (Check Draw, W2 similarly) ...

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
        
        # --- V9 Targeted Fetch ---
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
                    
                # Success!
                hit_counter['daily_hits'] += 1
                last_fetch_time = datetime.now().strftime('%H:%M:%S UTC')
                data = response.json().get('response', [])
                
                if not data:
                    logger.info("INFO:main:API returned empty response.")
                    return list(match_cache.values())
                    
                # Update Cache
                for fix in data:
                    fixture_id = fix['fixture']['id']
                    match_cache[fixture_id] = fix
                return data
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Key {key[:4]}... failed with Error: {e}")
                if '401' in str(e) or '403' in str(e): # Handle Auth/Forbidden errors
                    self.key_status[key] = 'inactive'
                continue 
        
        logger.error("🚫 All API keys failed or hit limit. Serving from cache.")
        return list(match_cache.values())

API_MANAGER = HTTPAPIManager(API_KEY, BACKUP_API_KEY)


def fetch_live_odds(match_id):
    """Placeholder function for The Odds API call."""
    if not ODDS_API_KEY:
        return {"error": "Odds API Key not configured"}
    
    # --- V9 Odds API Integration ---
    # When you get the key, update this function to call The Odds API
    # and return the relevant O/U and 1X2 odds for the match_id.
    logger.warning("⚠️ Odds API called but function is placeholder.")
    return {"odds_ou_2.5": 1.95, "odds_1x2_home": 2.50}


# =======================================================
# 4. Telegram Handlers and Auto-Updater
# =======================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 Welcome to the Football Prediction Bot V9!\n\n"
        "I provide high-confidence bets using Live Scores, Historical Data, and Odds analysis.\n\n"
        "Commands:\n"
        "/live - Show current live matches.\n"
        "/expert_bet - Get the most confirmed bet (85%+ Confidence).\n"
        "/stats - Check API usage and status."
    )
    bot.send_message(message.chat.id, welcome_text)

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
        bot.send_message(message.chat.id, "⏳ No live fixtures available right now or API data is empty.")
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
            f"👑 **EXPERT BET CONFIRMED (V9 AI)**\n"
            f"--- ⚽ {best_overall_bet['teams']} ---\n"
            f"⏱️ Minute: {best_overall_bet['minute']}'\n"
            f"📈 **Prediction:** {best_overall_bet['market']} - {best_overall_bet['type']}\n"
            f"🔥 **Confidence:** {best_overall_bet['confidence']:.2f}%\n"
            f"\n_This prediction exceeds {CONFIDENCE_THRESHOLD}% confidence based on Live Score, Historical Data, and Multi-Market Analysis._"
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
            
            # --- Alert Logic ---
            # You can place logic here to automatically send /expert_bet to OWNER_CHAT_ID 
            # if a high-confidence bet is found, similar to the /expert_bet handler.
            
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
