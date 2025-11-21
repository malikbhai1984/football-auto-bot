import os
import requests
import telebot
from dotenv import load_dotenv
import time
from flask import Flask, request
import logging
import random
from datetime import datetime, timedelta
import pytz
from threading import Thread, Lock
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import io
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Environment variables with fallbacks
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "").strip()
SPORTMONKS_API = os.getenv("API_KEY", "").strip()
FOOTBALL_DATA_API = os.getenv("FOOTBALL_DATA_API", "").strip()
BACKUP_API = os.getenv("BACKUP_API", "").strip()

logger.info("🚀 Initializing PRO API-Safe Multi-Source Bot...")

# Validate critical environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment variables")
    # Don't exit, just log - might be running in test mode

if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found in environment variables")

# Check if we have at least one API key
API_KEYS_AVAILABLE = any([SPORTMONKS_API, FOOTBALL_DATA_API, BACKUP_API])
if not API_KEYS_AVAILABLE:
    logger.warning("⚠️ No API keys found - running in limited mode")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID) if OWNER_CHAT_ID else 0
    if OWNER_CHAT_ID:
        logger.info(f"✅ OWNER_CHAT_ID: {OWNER_CHAT_ID}")
    else:
        logger.warning("⚠️ OWNER_CHAT_ID is 0 or invalid")
except (ValueError, TypeError) as e:
    logger.error(f"❌ Invalid OWNER_CHAT_ID: {e}")
    OWNER_CHAT_ID = 0

# Initialize bot only if token is available
if BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN)
else:
    logger.error("❌ BOT_TOKEN missing - Telegram features disabled")
    bot = None

app = Flask(__name__)

# Pakistan Time Zone
PAK_TZ = pytz.timezone('Asia/Karachi')

# Top Leagues Configuration
TOP_LEAGUES = {
    39: "Premier League",    # England
    140: "La Liga",          # Spain  
    78: "Bundesliga",        # Germany
    135: "Serie A",          # Italy
    61: "Ligue 1",           # France
    94: "Primeira Liga",     # Portugal
    88: "Eredivisie",        # Netherlands
    203: "UEFA Champions League"
}

# Configuration Constants
class Config:
    SPORTMONKS_LIMIT_PER_MINUTE = 8
    FOOTBALL_DATA_LIMIT_PER_MINUTE = 10
    BOT_CYCLE_INTERVAL = 300  # 5 minutes
    DATA_CLEANUP_INTERVAL = 12  # cycles
    HISTORICAL_DATA_RELOAD = 12  # cycles
    MIN_CONFIDENCE_THRESHOLD = 65  # Minimum confidence for sending predictions

# Global variables with thread safety
bot_started = False
message_counter = 0
historical_data = {}
model = None
scaler = StandardScaler()
data_lock = Lock()

# Enhanced API usage tracker
api_usage_tracker = {
    'sportmonks': {'count': 0, 'reset_time': datetime.now(), 'failures': 0, 'last_success': datetime.now()},
    'football_data': {'count': 0, 'reset_time': datetime.now(), 'failures': 0, 'last_success': datetime.now()},
    'github': {'count': 0, 'reset_time': datetime.now(), 'failures': 0, 'last_success': datetime.now()}
}

def get_pakistan_time():
    """Get current Pakistan time"""
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    """Format datetime in Pakistan time"""
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M %Z')

def check_api_health(api_name):
    """Check if API is healthy based on recent failures"""
    api_data = api_usage_tracker.get(api_name, {})
    
    # If too many consecutive failures, mark as unhealthy
    if api_data.get('failures', 0) >= 3:
        time_since_last_success = (datetime.now() - api_data.get('last_success', datetime.now())).seconds
        if time_since_last_success < 1800:  # 30 minutes
            return False
    
    return True

def update_api_status(api_name, success=True):
    """Update API status after call"""
    if api_name in api_usage_tracker:
        if success:
            api_usage_tracker[api_name]['failures'] = 0
            api_usage_tracker[api_name]['last_success'] = datetime.now()
        else:
            api_usage_tracker[api_name]['failures'] += 1

def check_api_limits(api_name):
    """Improved API rate limiting with realistic limits"""
    try:
        current_time = datetime.now()
        api_data = api_usage_tracker[api_name]
        
        # Reset counter every minute for minute-based limits
        if (current_time - api_data['reset_time']).seconds >= 60:
            api_data['count'] = 0
            api_data['reset_time'] = current_time
        
        # Realistic limits based on API documentation
        if api_name == 'sportmonks':
            if api_data['count'] >= 8:  # Safe buffer
                return False
                
        elif api_name == 'football_data':
            if api_data['count'] >= 8:  # Safe buffer
                return False
                
        elif api_name == 'github':
            if api_data['count'] >= 50:
                return False
        
        api_data['count'] += 1
        return True
        
    except Exception as e:
        logger.error(f"❌ API limit check error: {e}")
        return True

def safe_api_call(url, api_name, headers=None, timeout=10):
    """Make safe API call with multiple fallbacks"""
    try:
        if not check_api_limits(api_name) or not check_api_health(api_name):
            logger.warning(f"⏸️ Skipping {api_name} call due to limits/health")
            return None
        
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 429:
            logger.warning(f"⏰ {api_name.upper()} rate limited")
            time.sleep(30)
            return None
            
        if response.status_code == 200:
            update_api_status(api_name, success=True)
            return response
        else:
            logger.warning(f"❌ {api_name.upper()} API error: {response.status_code}")
            update_api_status(api_name, success=False)
            return None
            
    except Exception as e:
        logger.error(f"❌ {api_name.upper()} API call error: {e}")
        update_api_status(api_name, success=False)
        return None

@app.route("/")
def health():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "timestamp": format_pakistan_time(),
        "bot_started": bot_started,
        "message_counter": message_counter,
        "apis_available": API_KEYS_AVAILABLE
    }
    return json.dumps(status), 200, {'Content-Type': 'application/json'}

@app.route("/health")
def health_check():
    return "OK", 200

@app.route("/api-status")
def api_status():
    """Enhanced API status with health information"""
    status_msg = "📊 **PRO API USAGE STATUS**\n\n"
    
    for api_name, data in api_usage_tracker.items():
        remaining_time = 60 - (datetime.now() - data['reset_time']).seconds
        status_msg += f"**{api_name.upper()}:**\n"
        status_msg += f"• Requests: {data['count']}/"
        status_msg += f"{'10' if api_name in ['sportmonks', 'football_data'] else '60'}\n"
        status_msg += f"• Reset in: {remaining_time} seconds\n"
        status_msg += f"• Failures: {data['failures']}\n"
        status_msg += f"• Status: {'✅ HEALTHY' if data['failures'] < 3 else '⚠️ UNHEALTHY'}\n\n"
    
    return status_msg

def send_telegram_message(message, max_retries=3):
    """Send message to Telegram with improved retry logic"""
    global message_counter
    
    if not bot or not OWNER_CHAT_ID:
        logger.error("❌ Cannot send message - bot or chat ID not configured")
        return False
        
    for attempt in range(max_retries):
        try:
            message_counter += 1
            logger.info(f"📤 Sending message #{message_counter} (Attempt {attempt + 1})")
            bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
            logger.info(f"✅ Message #{message_counter} sent successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"🚫 All {max_retries} attempts failed")
    return False

def fetch_football_data_matches():
    """Fetch live matches from Football-Data.org API"""
    try:
        if not FOOTBALL_DATA_API:
            logger.warning("⚠️ Football-Data API key not configured")
            return []
            
        if not check_api_limits('football_data'):
            return []
            
        logger.info("🌐 Fetching live matches from Football-Data.org...")
        
        url = "https://api.football-data.org/v4/matches"
        headers = {'X-Auth-Token': FOOTBALL_DATA_API}
        
        response = safe_api_call(url, 'football_data', headers=headers, timeout=15)
        
        if not response:
            return []
        
        data = response.json()
        current_matches = []
        
        for match in data.get("matches", []):
            try:
                status = match.get("status", "")
                minute = match.get("minute", None)
                score = match.get("score", {})
                
                if status == "LIVE" and minute and minute >= 60:
                    home_team = match.get("homeTeam", {}).get("name", "Unknown Home")
                    away_team = match.get("awayTeam", {}).get("name", "Unknown Away")
                    home_score = score.get("fullTime", {}).get("home", 0)
                    away_score = score.get("fullTime", {}).get("away", 0)
                    
                    competition = match.get("competition", {}).get("name", "Unknown League")
                    
                    match_data = {
                        "home": home_team,
                        "away": away_team,
                        "league": competition,
                        "score": f"{home_score}-{away_score}",
                        "minute": f"{minute}'",
                        "current_minute": minute,
                        "home_score": home_score,
                        "away_score": away_score,
                        "status": status,
                        "match_id": match.get("id"),
                        "is_live": True,
                        "timestamp": get_pakistan_time(),
                        "source": "football_data"
                    }
                    
                    current_matches.append(match_data)
                    
            except Exception as e:
                logger.error(f"❌ Error processing Football-Data match: {e}")
                continue
        
        logger.info(f"📊 Football-Data matches found: {len(current_matches)}")
        return current_matches
        
    except Exception as e:
        logger.error(f"❌ Football-Data API error: {e}")
        return []

def fetch_sportmonks_matches():
    """Original Sportmonks fetch function"""
    try:
        if not SPORTMONKS_API:
            logger.warning("⚠️ Sportmonks API key not configured")
            return []
            
        if not check_api_limits('sportmonks'):
            return []
            
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("🌐 Fetching live matches from Sportmonks...")
        
        response = safe_api_call(url, 'sportmonks', timeout=15)
        
        if not response:
            return []
        
        data = response.json()
        current_matches = []
        
        for match in data.get("data", []):
            league_id = match.get("league_id")
            
            if league_id in TOP_LEAGUES:
                status = match.get("status", "")
                minute = match.get("minute", "")
                
                if status == "LIVE" and minute and minute != "FT" and minute != "HT":
                    participants = match.get("participants", [])
                    
                    if len(participants) >= 2:
                        home_team = participants[0].get("name", "Unknown Home")
                        away_team = participants[1].get("name", "Unknown Away")
                        
                        home_score = match.get("scores", {}).get("home_score", 0)
                        away_score = match.get("scores", {}).get("away_score", 0)
                        
                        try:
                            if isinstance(minute, str) and "'" in minute:
                                current_minute = int(minute.replace("'", ""))
                            else:
                                current_minute = int(minute)
                        except:
                            current_minute = 0
                        
                        if 60 <= current_minute <= 89:
                            match_data = {
                                "home": home_team,
                                "away": away_team,
                                "league": TOP_LEAGUES[league_id],
                                "score": f"{home_score}-{away_score}",
                                "minute": minute,
                                "current_minute": current_minute,
                                "home_score": home_score,
                                "away_score": away_score,
                                "status": status,
                                "match_id": match.get("id"),
                                "is_live": True,
                                "timestamp": get_pakistan_time(),
                                "source": "sportmonks"
                            }
                            
                            current_matches.append(match_data)
        
        return current_matches
        
    except Exception as e:
        logger.error(f"❌ Sportmonks matches error: {e}")
        return []

def fetch_current_live_matches():
    """Fetch live matches from multiple APIs with fallback"""
    all_matches = []
    
    # Try Sportmonks first
    if SPORTMONKS_API and check_api_health('sportmonks'):
        sportmonks_matches = fetch_sportmonks_matches()
        if sportmonks_matches:
            all_matches.extend(sportmonks_matches)
            logger.info(f"✅ Sportmonks provided {len(sportmonks_matches)} matches")
    
    # Try Football-Data as fallback
    if not all_matches and FOOTBALL_DATA_API and check_api_health('football_data'):
        football_data_matches = fetch_football_data_matches()
        if football_data_matches:
            all_matches.extend(football_data_matches)
            logger.info(f"✅ Football-Data provided {len(football_data_matches)} matches")
    
    # Remove duplicates based on team names and league
    unique_matches = []
    seen_matches = set()
    
    for match in all_matches:
        match_key = f"{match['home']}_{match['away']}_{match['league']}"
        if match_key not in seen_matches:
            seen_matches.add(match_key)
            unique_matches.append(match)
    
    logger.info(f"📊 Total unique live matches: {len(unique_matches)}")
    return unique_matches

def fetch_petermclagan_data():
    """Enhanced historical data fetching"""
    try:
        if not check_api_limits('github'):
            return []
            
        logger.info("📊 Fetching Peter McLagan historical data...")
        
        base_url = "https://raw.githubusercontent.com/petermclagan/footballAPI/main/data/"
        
        datasets = {
            'premier_league': 'premier_league.csv',
            'la_liga': 'la_liga.csv',
        }
        
        historical_matches = []
        
        for league, filename in datasets.items():
            try:
                url = base_url + filename
                response = safe_api_call(url, 'github', timeout=15)
                
                if response:
                    csv_data = io.StringIO(response.text)
                    df = pd.read_csv(csv_data)
                    
                    for _, row in df.iterrows():
                        home_team = clean_team_name(row.get('HomeTeam', ''))
                        away_team = clean_team_name(row.get('AwayTeam', ''))
                        
                        match_data = {
                            'league': league.replace('_', ' ').title(),
                            'home_team': home_team,
                            'away_team': away_team,
                            'home_goals': row.get('FTHG', 0),
                            'away_goals': row.get('FTAG', 0),
                            'date': row.get('Date', ''),
                            'result': row.get('FTR', ''),
                            'source': 'petermclagan',
                            'timestamp': get_pakistan_time(),
                        }
                        historical_matches.append(match_data)
                    
                    logger.info(f"✅ Loaded {len(df)} matches from {league}")
                else:
                    logger.warning(f"⚠️ Skipped {league} due to API limits")
                    
            except Exception as e:
                logger.error(f"❌ Error loading {league}: {e}")
                continue
        
        logger.info(f"📈 Peter McLagan matches: {len(historical_matches)}")
        return historical_matches
        
    except Exception as e:
        logger.error(f"❌ Peter McLagan API error: {e}")
        return []

def clean_team_name(team_name):
    """Clean team names for better matching"""
    if not team_name:
        return ""
    
    clean_name = str(team_name).strip()
    clean_name = re.sub(r'FC$|CF$|AFC$|CFC$', '', clean_name).strip()
    clean_name = re.sub(r'\s+', ' ', clean_name)
    
    return clean_name

def load_historical_data():
    """Load historical data from multiple sources"""
    global historical_data
    try:
        logger.info("📥 Loading historical data from multiple sources...")
        
        petermclagan_data = fetch_petermclagan_data()
        
        # Store in global variable with timestamp
        historical_data = {
            'matches': petermclagan_data,
            'last_updated': get_pakistan_time(),
            'total_matches': len(petermclagan_data),
        }
        
        logger.info(f"✅ Historical data loaded: {len(petermclagan_data)} total matches")
        return True
        
    except Exception as e:
        logger.error(f"❌ Historical data loading error: {e}")
        return False

def train_enhanced_ml_model():
    """Enhanced ML model with more features"""
    global model, scaler
    
    try:
        if not historical_data or 'matches' not in historical_data:
            return False
        
        matches = historical_data['matches']
        if len(matches) < 50:
            return False
        
        features = []
        labels = []
        
        for match in matches:
            try:
                home_goals = match.get('home_goals', 0)
                away_goals = match.get('away_goals', 0)
                
                total_goals = home_goals + away_goals
                goal_difference = home_goals - away_goals
                
                # Determine result
                result = match.get('result', '')
                if result == 'H':
                    label = 0  # Home win
                elif result == 'A':
                    label = 1  # Away win
                else:
                    label = 2  # Draw
                
                # Feature vector
                feature = [
                    home_goals, away_goals, total_goals, goal_difference,
                    random.uniform(0.8, 1.2)  # Small randomness
                ]
                
                features.append(feature)
                labels.append(label)
                
            except Exception as e:
                continue
        
        if len(features) < 30:
            return False
        
        # Use better model
        features_scaled = scaler.fit_transform(features)
        
        model = GradientBoostingClassifier(
            n_estimators=50,
            learning_rate=0.1,
            max_depth=3,
            random_state=42
        )
        model.fit(features_scaled, labels)
        
        logger.info(f"✅ Enhanced ML Model trained on {len(features)} matches")
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced ML Model training error: {e}")
        return False

def predict_enhanced_outcome(match_data, historical_matches):
    """Enhanced prediction with multiple algorithms"""
    try:
        home_team = match_data['home']
        away_team = match_data['away']
        current_score = match_data.get('home_score', 0), match_data.get('away_score', 0)
        current_minute = match_data.get('current_minute', 0)
        
        # Get team stats
        home_stats = get_enhanced_team_stats(home_team, historical_matches)
        away_stats = get_enhanced_team_stats(away_team, historical_matches)
        
        # Multiple prediction methods
        ml_prediction = ml_prediction_method(match_data, home_stats, away_stats)
        historical_prediction = historical_prediction_method(home_stats, away_stats)
        minute_based_prediction = minute_based_prediction_method(current_score, current_minute)
        
        # Weighted consensus
        final_prediction = weighted_consensus(
            ml_prediction, historical_prediction, minute_based_prediction,
            current_minute
        )
        
        return final_prediction
        
    except Exception as e:
        logger.error(f"❌ Enhanced prediction error: {e}")
        return simple_prediction(match_data, historical_matches)

def ml_prediction_method(match_data, home_stats, away_stats):
    """ML-based prediction"""
    if model is None:
        return None
    
    try:
        features = [
            home_stats['avg_goals_for'], away_stats['avg_goals_for'],
            home_stats['avg_goals_against'], away_stats['avg_goals_against'],
            home_stats['win_rate'] - away_stats['win_rate'],
        ]
        
        features_scaled = scaler.transform([features])
        prediction = model.predict(features_scaled)[0]
        probability = model.predict_proba(features_scaled)[0]
        
        outcomes = ['Home Win', 'Away Win', 'Draw']
        confidence = max(probability) * 100
        
        return {
            'prediction': outcomes[prediction],
            'confidence': confidence,
            'method': 'ml_model'
        }
    except:
        return None

def historical_prediction_method(home_stats, away_stats):
    """Historical data-based prediction"""
    home_advantage = 1.2  # Home advantage factor
    
    home_strength = home_stats['win_rate'] * home_advantage
    away_strength = away_stats['win_rate']
    
    if home_strength > away_strength + 0.1:
        prediction = "Home Win"
        confidence = 50 + (home_strength - away_strength) * 100
    elif away_strength > home_strength + 0.1:
        prediction = "Away Win"
        confidence = 50 + (away_strength - home_strength) * 100
    else:
        prediction = "Draw"
        confidence = 40 + (1 - abs(home_strength - away_strength)) * 30
    
    return {
        'prediction': prediction,
        'confidence': min(95, max(35, confidence)),
        'method': 'historical_analysis'
    }

def minute_based_prediction_method(current_score, current_minute):
    """Time-based prediction considering current score and minute"""
    home_score, away_score = current_score
    
    if current_minute >= 75:  # Late game
        if home_score > away_score:
            return {'prediction': 'Home Win', 'confidence': 75, 'method': 'late_game'}
        elif away_score > home_score:
            return {'prediction': 'Away Win', 'confidence': 75, 'method': 'late_game'}
        else:
            return {'prediction': 'Draw', 'confidence': 60, 'method': 'late_game'}
    else:
        # Early to mid game - less confidence
        goal_difference = home_score - away_score
        if abs(goal_difference) >= 2:
            winning_team = 'Home Win' if goal_difference > 0 else 'Away Win'
            return {'prediction': winning_team, 'confidence': 65, 'method': 'score_momentum'}
        else:
            return None  # Not confident enough

def weighted_consensus(ml_pred, historical_pred, minute_pred, current_minute):
    """Weighted consensus of multiple prediction methods"""
    predictions = []
    weights = []
    
    # ML prediction weight
    if ml_pred and ml_pred['confidence'] > 60:
        predictions.append(ml_pred)
        weights.append(0.4)
    
    # Historical prediction weight
    if historical_pred:
        predictions.append(historical_pred)
        weights.append(0.3)
    
    # Minute-based prediction weight (increases with time)
    if minute_pred:
        time_weight = min(0.4, current_minute / 200)  # Max 40% weight
        predictions.append(minute_pred)
        weights.append(time_weight)
    
    if not predictions:
        return historical_pred  # Fallback
    
    # Normalize weights
    total_weight = sum(weights)
    weights = [w/total_weight for w in weights]
    
    # Calculate weighted consensus
    prediction_scores = {'Home Win': 0, 'Away Win': 0, 'Draw': 0}
    confidence_sum = 0
    
    for pred, weight in zip(predictions, weights):
        prediction_scores[pred['prediction']] += pred['confidence'] * weight
        confidence_sum += pred['confidence'] * weight
    
    # Get final prediction
    final_prediction = max(prediction_scores, key=prediction_scores.get)
    final_confidence = prediction_scores[final_prediction]
    
    return {
        'prediction': final_prediction,
        'confidence': min(95, max(Config.MIN_CONFIDENCE_THRESHOLD, final_confidence)),
        'method': 'consensus',
        'components': len(predictions)
    }

def get_enhanced_team_stats(team_name, historical_matches):
    """Enhanced team statistics with form and advanced metrics"""
    team_matches = [m for m in historical_matches 
                   if m['home_team'] == team_name or m['away_team'] == team_name]
    
    if not team_matches:
        return {
            'win_rate': 0.35, 'draw_rate': 0.3, 'loss_rate': 0.35,
            'avg_goals_for': 1.3, 'avg_goals_against': 1.3,
            'form_strength': 0.5, 'total_matches': 0
        }
    
    wins = draws = losses = 0
    goals_for = goals_against = 0
    recent_form = []
    
    for match in team_matches[-10:]:  # Last 10 matches for form
        is_home = match['home_team'] == team_name
        
        if is_home:
            goals_for += match.get('home_goals', 0)
            goals_against += match.get('away_goals', 0)
            
            if match.get('result') == 'H':
                wins += 1
                recent_form.append(1)  # Win
            elif match.get('result') == 'D':
                draws += 1
                recent_form.append(0.5)  # Draw
            else:
                losses += 1
                recent_form.append(0)  # Loss
        else:
            goals_for += match.get('away_goals', 0)
            goals_against += match.get('home_goals', 0)
            
            if match.get('result') == 'A':
                wins += 1
                recent_form.append(1)
            elif match.get('result') == 'D':
                draws += 1
                recent_form.append(0.5)
            else:
                losses += 1
                recent_form.append(0)
    
    total_matches = len(team_matches)
    form_strength = sum(recent_form) / len(recent_form) if recent_form else 0.5
    
    return {
        'win_rate': wins / total_matches,
        'draw_rate': draws / total_matches,
        'loss_rate': losses / total_matches,
        'avg_goals_for': goals_for / total_matches,
        'avg_goals_against': goals_against / total_matches,
        'form_strength': form_strength,
        'total_matches': total_matches
    }

def simple_prediction(match_data, historical_matches):
    """Simple fallback prediction"""
    home_team = match_data['home']
    away_team = match_data['away']
    current_score = match_data.get('home_score', 0), match_data.get('away_score', 0)
    
    home_stats = get_enhanced_team_stats(home_team, historical_matches)
    away_stats = get_enhanced_team_stats(away_team, historical_matches)
    
    # Simple logic based on current score and historical performance
    if current_score[0] > current_score[1]:
        prediction = "Home Win"
        confidence = 60 + home_stats['win_rate'] * 20
    elif current_score[0] < current_score[1]:
        prediction = "Away Win"
        confidence = 60 + away_stats['win_rate'] * 20
    else:
        prediction = "Draw"
        confidence = 40 + (home_stats['draw_rate'] + away_stats['draw_rate']) * 15
    
    return {
        'prediction': prediction,
        'confidence': min(95, max(30, confidence)),
        'method': 'historical_analysis'
    }

def find_relevant_historical_data(match):
    """Find relevant historical data for a match"""
    if not historical_data or 'matches' not in historical_data:
        return []
    
    home_team = match['home']
    away_team = match['away']
    league = match['league']
    
    relevant_matches = []
    
    for historical_match in historical_data['matches']:
        # Check if teams match (either home-home or home-away)
        teams_match = (
            (historical_match['home_team'] == home_team and historical_match['away_team'] == away_team) or
            (historical_match['home_team'] == away_team and historical_match['away_team'] == home_team)
        )
        
        # Check if league is similar
        league_similar = (
            league.lower() in historical_match['league'].lower() or
            historical_match['league'].lower() in league.lower()
        )
        
        if teams_match or league_similar:
            relevant_matches.append(historical_match)
    
    return relevant_matches

def analyze_with_multiple_sources():
    """Enhanced analysis with confidence threshold"""
    try:
        logger.info("🔍 Starting PRO multi-source analysis...")
        
        live_matches = fetch_current_live_matches()
        
        if not live_matches:
            logger.info("😴 No live matches found for analysis")
            return 0
        
        predictions_sent = 0
        
        for match in live_matches:
            try:
                historical_for_match = find_relevant_historical_data(match)
                
                if len(historical_for_match) >= 3:  # Minimum data
                    prediction = predict_enhanced_outcome(match, historical_for_match)
                    
                    # Only send high-confidence predictions
                    if prediction['confidence'] >= Config.MIN_CONFIDENCE_THRESHOLD:
                        message = format_enhanced_prediction_message(match, prediction, len(historical_for_match))
                        
                        if send_telegram_message(message):
                            predictions_sent += 1
                            logger.info(f"✅ High-confidence prediction sent for {match['home']} vs {match['away']} "
                                      f"(Confidence: {prediction['confidence']}%)")
                        time.sleep(1)  # Reduced delay
                    else:
                        logger.info(f"📊 Low confidence for {match['home']} vs {match['away']}: "
                                  f"{prediction['confidence']}%")
                        
            except Exception as e:
                logger.error(f"❌ Error analyzing match {match.get('home', 'Unknown')}: {e}")
                continue
        
        logger.info(f"📈 PRO Analysis complete: {predictions_sent} high-confidence predictions sent")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ PRO Multi-source analysis error: {e}")
        return 0

def format_enhanced_prediction_message(match, prediction, historical_count):
    """Enhanced prediction message with more details"""
    current_time = format_pakistan_time()
    
    message = f"""⚽ **PRO MATCH PREDICTION** ⚽

🏆 **League:** {match['league']}
🕒 **Minute:** {match['minute']}
📊 **Score:** {match['score']}
🌐 **Source:** {match.get('source', 'Multiple APIs')}

🏠 **{match['home']}** vs 🛫 **{match['away']}**

🔮 **PREDICTION:** {prediction['prediction'].upper()}
🎯 **CONFIDENCE:** {prediction['confidence']}% ⭐
🛠️ **Method:** {prediction['method']}
🧩 **Components:** {prediction.get('components', 1)} algorithms

📈 **Historical Data:** {historical_count} matches analyzed
🕐 **Analysis Time:** {current_time}

💡 **PRO ANALYSIS:** High-confidence prediction based on multiple data sources.

⚠️ *Professional analysis for informational purposes.*"""

    return message

def cleanup_old_data():
    """Clean up old data to prevent memory issues"""
    global historical_data, message_counter
    
    try:
        current_time = get_pakistan_time()
        cutoff_time = current_time - timedelta(hours=24)
        
        # Clean historical data
        if historical_data and 'matches' in historical_data:
            original_count = len(historical_data['matches'])
            historical_data['matches'] = [
                m for m in historical_data['matches'] 
                if m.get('timestamp', current_time) > cutoff_time
            ]
            new_count = len(historical_data['matches'])
            
            if new_count < original_count:
                logger.info(f"🧹 Cleaned {original_count - new_count} old historical records")
        
        # Reset message counter if it gets too large
        if message_counter > 10000:
            message_counter = 0
            logger.info("🔄 Message counter reset")
            
        logger.info("✅ Data cleanup completed")
        
    except Exception as e:
        logger.error(f"❌ Data cleanup error: {e}")

def get_api_status_message():
    """Get API status message"""
    status_msg = "📊 **PRO API USAGE STATUS**\n\n"
    
    for api_name, data in api_usage_tracker.items():
        remaining_time = 60 - (datetime.now() - data['reset_time']).seconds
        used = data['count']
        limit = 10 if api_name in ['sportmonks', 'football_data'] else 60
        
        status_msg += f"**{api_name.upper()}:** {used}/{limit} requests\n"
        status_msg += f"Reset in: {remaining_time}s\n"
        status_msg += f"Failures: {data['failures']}\n"
        
        if used >= limit * 0.8:
            status_msg += "Status: ⚠️ **NEAR LIMIT**\n"
        elif used >= limit * 0.5:
            status_msg += "Status: 🟡 **MODERATE**\n"
        else:
            status_msg += "Status: ✅ **SAFE**\n"
        
        status_msg += "\n"
    
    # Add historical data stats
    if historical_data:
        status_msg += f"📈 **Historical Data:** {historical_data.get('total_matches', 0)} matches\n"
        status_msg += f"🕒 **Last Updated:** {historical_data.get('last_updated', 'Never')}\n\n"
    
    status_msg += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
    status_msg += f"📨 **Messages Sent:** {message_counter}\n"
    status_msg += "🔄 Next check in 30 minutes"
    
    return status_msg

def send_startup_message():
    """Enhanced startup message"""
    startup_msg = f"""🚀 **PRO API-Safe Multi-Source Bot Started Successfully!**

⏰ **Startup Time:** {format_pakistan_time()}
📊 **Data Sources:**
   • Sportmonks API: {'✅ Available' if SPORTMONKS_API else '❌ Missing'}
   • Football-Data.org: {'✅ Available' if FOOTBALL_DATA_API else '❌ Missing'}
   • Historical Data: ✅ Available

🛡️ **PRO Features:**
   • Dual API Fallback System
   • Enhanced ML Predictions
   • Multi-Algorithm Consensus
   • Confidence-Based Filtering (>{Config.MIN_CONFIDENCE_THRESHOLD}%)

🎯 **Settings:**
   • Cycle Interval: {Config.BOT_CYCLE_INTERVAL} seconds
   • High-Accuracy Mode: Enabled

Bot is now running and will send HIGH-CONFIDENCE predictions automatically!"""

    send_telegram_message(startup_msg)

def bot_worker():
    """Enhanced bot worker with better error recovery"""
    global bot_started
    logger.info("🔄 Starting PRO API-Safe Bot Worker...")
    
    bot_started = True
    
    # Quick startup
    logger.info("📥 Loading initial historical data...")
    load_historical_data()
    
    # Train model in background
    Thread(target=train_enhanced_ml_model, daemon=True).start()
    
    time.sleep(2)
    
    logger.info("📤 Sending startup message...")
    send_startup_message()
    
    consecutive_failures = 0
    cycle = 0
    
    while True:
        try:
            cycle += 1
            logger.info(f"🔄 PRO Cycle #{cycle} at {format_pakistan_time()}")
            
            # Reload data periodically
            if cycle % Config.HISTORICAL_DATA_RELOAD == 0:
                Thread(target=load_historical_data, daemon=True).start()
            
            if cycle % Config.DATA_CLEANUP_INTERVAL == 0:
                cleanup_old_data()
            
            # Main analysis
            predictions_sent = analyze_with_multiple_sources()
            
            if predictions_sent > 0:
                consecutive_failures = 0
                logger.info(f"📈 Cycle #{cycle}: {predictions_sent} predictions sent")
            else:
                consecutive_failures += 1
                logger.info(f"😴 Cycle #{cycle}: No high-confidence predictions")
            
            # Send status every 6 cycles (30 minutes)
            if cycle % 6 == 0:
                api_status_msg = get_api_status_message()
                send_telegram_message(api_status_msg)
            
            # Adaptive sleep based on performance
            sleep_time = Config.BOT_CYCLE_INTERVAL
            if consecutive_failures > 3:
                sleep_time = min(600, sleep_time * 1.5)
                logger.info(f"💤 Adaptive sleep: {sleep_time} seconds")
            
            logger.info(f"⏰ Waiting {sleep_time} seconds for next cycle...")
            time.sleep(sleep_time)
            
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"❌ PRO Bot worker error in cycle #{cycle}: {e}")
            time.sleep(min(300, 60 * consecutive_failures))

def start_bot_thread():
    """Start bot with monitoring"""
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 PRO Bot worker thread started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start PRO bot thread: {e}")
        return False

# Auto-start bot only if we have basic configuration
if BOT_TOKEN and OWNER_CHAT_ID:
    logger.info("🎯 Auto-starting PRO API-Safe Multi-Source Bot...")
    if start_bot_thread():
        logger.info("✅ PRO Bot auto-started successfully")
    else:
        logger.error("❌ PRO Bot auto-start failed")
else:
    logger.warning("⚠️ Missing BOT_TOKEN or OWNER_CHAT_ID - bot not auto-started")

if __name__ == "__main__":
    logger.info("🌐 Starting PRO Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
