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

logger.info("🚀 Initializing ULTRA PRO 85%+ Confidence Multi-Market Bot...")

# Validate critical environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment variables")

if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found in environment variables")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID) if OWNER_CHAT_ID else 0
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

# Expanded Leagues Configuration
TOP_LEAGUES = {
    39: "Premier League",    # England
    140: "La Liga",          # Spain  
    78: "Bundesliga",        # Germany
    135: "Serie A",          # Italy
    61: "Ligue 1",           # France
    94: "Primeira Liga",     # Portugal
    88: "Eredivisie",        # Netherlands
    203: "UEFA Champions League",
    2: "Champions League",
    5: "Europa League", 
    45: "FA Cup",
    48: "EFL Cup",
    528: "World Cup"
}

# Configuration for 85%+ Confidence & All Markets
class Config:
    BOT_CYCLE_INTERVAL = 60  # 1 minute - faster checking
    MIN_CONFIDENCE_THRESHOLD = 85  # Increased to 85%
    DATA_CLEANUP_INTERVAL = 6  # cycles
    HISTORICAL_DATA_RELOAD = 6  # cycles
    
    # ALL Over/Under markets including 2.5
    MARKETS_TO_ANALYZE = [
        'winning_team', 'draw', 'btts', 
        'over_0.5', 'over_1.5', 'over_2.5', 'over_3.5', 'over_4.5', 'over_5.5',
        'last_10_min_goal'
    ]

# Global variables
bot_started = False
message_counter = 0
historical_data = {}
model = None
scaler = StandardScaler()
data_lock = Lock()

# API usage tracker
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
    
    if api_data.get('failures', 0) >= 3:
        time_since_last_success = (datetime.now() - api_data.get('last_success', datetime.now())).seconds
        if time_since_last_success < 1800:
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
    """API rate limiting"""
    try:
        current_time = datetime.now()
        api_data = api_usage_tracker[api_name]
        
        if (current_time - api_data['reset_time']).seconds >= 60:
            api_data['count'] = 0
            api_data['reset_time'] = current_time
        
        if api_name == 'sportmonks':
            if api_data['count'] >= 8:
                return False
        elif api_name == 'football_data':
            if api_data['count'] >= 8:
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
        "message_counter": message_counter
    }
    return json.dumps(status), 200, {'Content-Type': 'application/json'}

@app.route("/health")
def health_check():
    return "OK", 200

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
                time.sleep(2 ** attempt)
            else:
                logger.error(f"🚫 All {max_retries} attempts failed")
    return False

# Fetch matches from 1st minute
def fetch_sportmonks_matches():
    """Fetch live matches from Sportmonks - FROM 1ST MINUTE"""
    try:
        if not SPORTMONKS_API:
            return []
            
        if not check_api_limits('sportmonks'):
            return []
            
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("🌐 Fetching ALL live matches from Sportmonks...")
        
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
                
                # Include from 1st minute
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
                        
                        # Include ALL minutes from 1-90
                        if 1 <= current_minute <= 90:
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

def fetch_football_data_matches():
    """Fetch live matches from Football-Data.org - FROM 1ST MINUTE"""
    try:
        if not FOOTBALL_DATA_API:
            return []
            
        if not check_api_limits('football_data'):
            return []
            
        logger.info("🌐 Fetching ALL live matches from Football-Data.org...")
        
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
                
                # Include from 1st minute
                if status == "LIVE" and minute:
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
                continue
        
        logger.info(f"📊 Football-Data matches found: {len(current_matches)}")
        return current_matches
        
    except Exception as e:
        logger.error(f"❌ Football-Data API error: {e}")
        return []

def fetch_current_live_matches():
    """Fetch live matches from multiple APIs with fallback"""
    all_matches = []
    
    if SPORTMONKS_API and check_api_health('sportmonks'):
        sportmonks_matches = fetch_sportmonks_matches()
        if sportmonks_matches:
            all_matches.extend(sportmonks_matches)
    
    if not all_matches and FOOTBALL_DATA_API and check_api_health('football_data'):
        football_data_matches = fetch_football_data_matches()
        if football_data_matches:
            all_matches.extend(football_data_matches)
    
    # Remove duplicates
    unique_matches = []
    seen_matches = set()
    
    for match in all_matches:
        match_key = f"{match['home']}_{match['away']}_{match['league']}"
        if match_key not in seen_matches:
            seen_matches.add(match_key)
            unique_matches.append(match)
    
    logger.info(f"📊 Total unique live matches: {len(unique_matches)}")
    return unique_matches

# Enhanced prediction for ALL markets including Over 2.5
def predict_all_markets(match_data, historical_matches):
    """Predict ALL markets with 85%+ confidence focus"""
    predictions = {}
    
    try:
        home_team = match_data['home']
        away_team = match_data['away']
        current_score = match_data.get('home_score', 0), match_data.get('away_score', 0)
        current_minute = match_data.get('current_minute', 0)
        
        home_stats = get_enhanced_team_stats(home_team, historical_matches)
        away_stats = get_enhanced_team_stats(away_team, historical_matches)
        
        # 1. Winning Team & Draw Predictions
        winning_team_pred = predict_winning_team(home_stats, away_stats, current_score, current_minute)
        if winning_team_pred['confidence'] >= 85:
            predictions['winning_team'] = winning_team_pred
        
        draw_pred = predict_draw(home_stats, away_stats, current_score, current_minute)
        if draw_pred['confidence'] >= 85:
            predictions['draw'] = draw_pred
        
        # 2. BTTS Prediction
        btts_pred = predict_btts(home_stats, away_stats, current_score, current_minute)
        if btts_pred['confidence'] >= 85:
            predictions['btts'] = btts_pred
        
        # 3. ALL Over/Under Markets INCLUDING 2.5
        for goals in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            over_pred = predict_over_under(home_stats, away_stats, current_score, current_minute, goals, 'over')
            if over_pred['confidence'] >= 85:
                predictions[f'over_{goals}'] = over_pred
        
        # 4. Last 10 Minutes Goal Chance
        last_10_pred = predict_last_10_min_goal(home_stats, away_stats, current_score, current_minute)
        if last_10_pred['confidence'] >= 85:
            predictions['last_10_min_goal'] = last_10_pred
            
    except Exception as e:
        logger.error(f"❌ Multi-market prediction error: {e}")
    
    return predictions

# Specific market prediction functions
def predict_winning_team(home_stats, away_stats, current_score, current_minute):
    """Predict winning team with high confidence"""
    home_advantage = 1.15
    
    home_strength = (home_stats['win_rate'] * home_advantage + 
                    home_stats['form_strength'] * 0.3)
    away_strength = (away_stats['win_rate'] + 
                    away_stats['form_strength'] * 0.3)
    
    # Consider current score
    home_goals, away_goals = current_score
    score_impact = (home_goals - away_goals) * 0.1
    
    home_final = home_strength + score_impact
    away_final = away_strength - score_impact
    
    if home_final > away_final + 0.25:
        confidence = min(95, 70 + (home_final - away_final) * 80)
        return {'prediction': 'Home Win', 'confidence': confidence}
    elif away_final > home_final + 0.25:
        confidence = min(95, 70 + (away_final - home_final) * 80)
        return {'prediction': 'Away Win', 'confidence': confidence}
    else:
        return {'prediction': 'None', 'confidence': 40}

def predict_draw(home_stats, away_stats, current_score, current_minute):
    """Predict draw with high confidence"""
    home_goals, away_goals = current_score
    
    # If current score is draw and late game
    if home_goals == away_goals and current_minute >= 75:
        return {'prediction': 'Draw', 'confidence': 85}
    
    # Both teams have high draw rates
    avg_draw_rate = (home_stats['draw_rate'] + away_stats['draw_rate']) / 2
    if avg_draw_rate > 0.35 and current_minute >= 60:
        confidence = min(90, 60 + avg_draw_rate * 80)
        return {'prediction': 'Draw', 'confidence': confidence}
    
    return {'prediction': 'No Draw', 'confidence': 30}

def predict_btts(home_stats, away_stats, current_score, current_minute):
    """Predict Both Teams To Score"""
    home_goals, away_goals = current_score
    
    # If already both scored
    if home_goals > 0 and away_goals > 0:
        return {'prediction': 'Yes', 'confidence': 90}
    
    # High scoring teams
    home_attack = home_stats['avg_goals_for']
    away_attack = away_stats['avg_goals_for']
    home_defense = home_stats['avg_goals_against'] 
    away_defense = away_stats['avg_goals_against']
    
    btts_probability = (home_attack * away_defense + away_attack * home_defense) / 2
    
    if btts_probability > 1.2 and current_minute <= 75:
        confidence = min(88, 60 + btts_probability * 20)
        return {'prediction': 'Yes', 'confidence': confidence}
    
    return {'prediction': 'No', 'confidence': 40}

def predict_over_under(home_stats, away_stats, current_score, current_minute, line, market_type):
    """Predict Over/Under markets INCLUDING 2.5"""
    home_goals, away_goals = current_score
    total_goals = home_goals + away_goals
    
    # Calculate expected additional goals
    minutes_remaining = 90 - current_minute
    home_goal_rate = home_stats['avg_goals_for'] / 90
    away_goal_rate = away_stats['avg_goals_for'] / 90
    
    expected_additional = (home_goal_rate + away_goal_rate) * minutes_remaining
    expected_total = total_goals + expected_additional
    
    if market_type == 'over':
        if expected_total > line + 0.5:
            confidence = min(95, 70 + (expected_total - line) * 40)
            return {'prediction': f'Over {line}', 'confidence': confidence}
    
    return {'prediction': f'Under {line}', 'confidence': 40}

def predict_last_10_min_goal(home_stats, away_stats, current_score, current_minute):
    """Predict goal in last 10 minutes"""
    if current_minute >= 80:
        return {'prediction': 'High Chance', 'confidence': 45}
    
    home_goal_rate = home_stats['avg_goals_for'] / 90
    away_goal_rate = away_stats['avg_goals_for'] / 90
    
    goal_probability = (home_goal_rate + away_goal_rate) * 10
    
    if goal_probability > 0.8:
        confidence = min(90, 60 + goal_probability * 40)
        return {'prediction': 'High Chance', 'confidence': confidence}
    
    return {'prediction': 'Low Chance', 'confidence': 35}

def get_enhanced_team_stats(team_name, historical_matches):
    """Enhanced team statistics"""
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
    
    for match in team_matches[-10:]:
        is_home = match['home_team'] == team_name
        
        if is_home:
            goals_for += match.get('home_goals', 0)
            goals_against += match.get('away_goals', 0)
            
            if match.get('result') == 'H':
                wins += 1
                recent_form.append(1)
            elif match.get('result') == 'D':
                draws += 1
                recent_form.append(0.5)
            else:
                losses += 1
                recent_form.append(0)
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

# Historical data functions
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

def find_relevant_historical_data(match):
    """Find relevant historical data for a match"""
    if not historical_data or 'matches' not in historical_data:
        return []
    
    home_team = match['home']
    away_team = match['away']
    league = match['league']
    
    relevant_matches = []
    
    for historical_match in historical_data['matches']:
        teams_match = (
            (historical_match['home_team'] == home_team and historical_match['away_team'] == away_team) or
            (historical_match['home_team'] == away_team and historical_match['away_team'] == home_team)
        )
        
        league_similar = (
            league.lower() in historical_match['league'].lower() or
            historical_match['league'].lower() in league.lower()
        )
        
        if teams_match or league_similar:
            relevant_matches.append(historical_match)
    
    return relevant_matches

# Enhanced analysis for ALL markets including Over 2.5
def analyze_all_markets():
    """Analyze ALL markets with 85%+ confidence focus"""
    try:
        logger.info("🔍 Starting ULTRA 85%+ Multi-Market Analysis...")
        
        live_matches = fetch_current_live_matches()
        
        if not live_matches:
            logger.info("😴 No live matches found for analysis")
            return 0
        
        predictions_sent = 0
        
        for match in live_matches:
            try:
                historical_for_match = find_relevant_historical_data(match)
                
                if len(historical_for_match) >= 3:
                    # Get predictions for ALL markets INCLUDING Over 2.5
                    market_predictions = predict_all_markets(match, historical_for_match)
                    
                    # Send message only if we have 85%+ predictions
                    if market_predictions:
                        message = format_multi_market_message(match, market_predictions, len(historical_for_match))
                        
                        if send_telegram_message(message):
                            predictions_sent += 1
                            logger.info(f"✅ 85%+ predictions sent for {match['home']} vs {match['away']} - {len(market_predictions)} markets")
                        time.sleep(1)
                    else:
                        logger.info(f"📊 No 85%+ predictions for {match['home']} vs {match['away']}")
                        
            except Exception as e:
                logger.error(f"❌ Error analyzing match {match.get('home', 'Unknown')}: {e}")
                continue
        
        logger.info(f"📈 ULTRA Analysis complete: {predictions_sent} matches with 85%+ predictions")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ ULTRA Multi-market analysis error: {e}")
        return 0

# Format message for ALL markets including Over 2.5
def format_multi_market_message(match, market_predictions, historical_count):
    """Format message showing ALL 85%+ confidence predictions"""
    current_time = format_pakistan_time()
    
    message = f"""🎯 **ULTRA 85%+ CONFIDENCE PREDICTIONS** 🎯

🏆 **League:** {match['league']}
🕒 **Minute:** {match['minute']}
📊 **Score:** {match['score']}

🏠 **{match['home']}** vs 🛫 **{match['away']}**

🔥 **HIGH-CONFIDENCE BETS (85%+):**\n"""

    # Add each market prediction
    for market, prediction in market_predictions.items():
        if 'over' in market:
            market_display = f"⚽ {prediction['prediction']} Goals"
        elif market == 'btts':
            market_display = f"🎯 Both Teams To Score: {prediction['prediction']}"
        elif market == 'last_10_min_goal':
            market_display = f"⏰ Last 10 Min Goal: {prediction['prediction']}"
        elif market == 'winning_team':
            market_display = f"🏆 Winning Team: {prediction['prediction']}"
        elif market == 'draw':
            market_display = f"🤝 Match Draw: {prediction['prediction']}"
        else:
            market_display = f"📈 {market}: {prediction['prediction']}"
        
        message += f"• {market_display} - {prediction['confidence']}% ✅\n"

    message += f"""
📈 **Analysis:** {historical_count} historical matches
🕐 **Time:** {current_time}
🎯 **Strategy:** Ultra High Confidence (85%+ Only)

⚠️ *Professional betting analysis - gamble responsibly*"""

    return message

def cleanup_old_data():
    """Clean up old data to prevent memory issues"""
    global historical_data, message_counter
    
    try:
        current_time = get_pakistan_time()
        cutoff_time = current_time - timedelta(hours=24)
        
        if historical_data and 'matches' in historical_data:
            original_count = len(historical_data['matches'])
            historical_data['matches'] = [
                m for m in historical_data['matches'] 
                if m.get('timestamp', current_time) > cutoff_time
            ]
            new_count = len(historical_data['matches'])
            
            if new_count < original_count:
                logger.info(f"🧹 Cleaned {original_count - new_count} old historical records")
        
        if message_counter > 10000:
            message_counter = 0
            logger.info("🔄 Message counter reset")
            
        logger.info("✅ Data cleanup completed")
        
    except Exception as e:
        logger.error(f"❌ Data cleanup error: {e}")

def send_startup_message():
    """Enhanced startup message"""
    startup_msg = f"""🚀 **ULTRA 85%+ MULTI-MARKET BOT STARTED!**

⏰ **Startup Time:** {format_pakistan_time()}
🎯 **Confidence Threshold:** 85%+ ONLY
📈 **ALL Markets Analyzed:**
   • Winning Team + Draw
   • BTTS (Both Teams To Score) 
   • Over/Under 0.5, 1.5, 2.5, 3.5, 4.5, 5.5 Goals
   • Last 10 Minutes Goal Chance

⚡ **Features:**
   • 1st Minute Start
   • ALL Markets Analysis
   • Ultra High Confidence Filter
   • 1-Minute Cycle Interval

Bot is now scanning ALL markets for 85%+ confidence opportunities!"""

    send_telegram_message(startup_msg)

def bot_worker():
    """Enhanced bot worker for ultra mode"""
    global bot_started
    logger.info("🔄 Starting ULTRA 85%+ Multi-Market Bot Worker...")
    
    bot_started = True
    
    # Quick startup
    logger.info("📥 Loading initial historical data...")
    load_historical_data()
    
    time.sleep(2)
    
    logger.info("📤 Sending startup message...")
    send_startup_message()
    
    consecutive_failures = 0
    cycle = 0
    
    while True:
        try:
            cycle += 1
            logger.info(f"🔄 ULTRA Cycle #{cycle} at {format_pakistan_time()}")
            
            # Reload data periodically
            if cycle % Config.HISTORICAL_DATA_RELOAD == 0:
                Thread(target=load_historical_data, daemon=True).start()
            
            if cycle % Config.DATA_CLEANUP_INTERVAL == 0:
                cleanup_old_data()
            
            # Main analysis - ALL markets INCLUDING Over 2.5
            predictions_sent = analyze_all_markets()
            
            if predictions_sent > 0:
                consecutive_failures = 0
                logger.info(f"📈 Cycle #{cycle}: {predictions_sent} matches with 85%+ predictions")
            else:
                consecutive_failures += 1
                logger.info(f"😴 Cycle #{cycle}: No 85%+ predictions found")
            
            # Status update every 10 cycles
            if cycle % 10 == 0:
                status_msg = f"🔄 **ULTRA Bot Status**\nCycles: {cycle}\nMessages: {message_counter}\nLast Check: {format_pakistan_time()}"
                send_telegram_message(status_msg)
            
            logger.info(f"⏰ Waiting {Config.BOT_CYCLE_INTERVAL} seconds for next cycle...")
            time.sleep(Config.BOT_CYCLE_INTERVAL)
            
        except Exception as e:
            consecutive_failures += 1
            logger.error(f"❌ ULTRA Bot worker error in cycle #{cycle}: {e}")
            time.sleep(min(300, 60 * consecutive_failures))

def start_bot_thread():
    """Start bot with monitoring"""
    try:
        bot_thread = Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🤖 ULTRA Bot worker thread started successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start ULTRA bot thread: {e}")
        return False

# Auto-start bot
if BOT_TOKEN and OWNER_CHAT_ID:
    logger.info("🎯 Auto-starting ULTRA 85%+ Multi-Market Bot...")
    if start_bot_thread():
        logger.info("✅ ULTRA Bot auto-started successfully")
    else:
        logger.error("❌ ULTRA Bot auto-start failed")
else:
    logger.warning("⚠️ Missing BOT_TOKEN or OWNER_CHAT_ID - bot not auto-started")

if __name__ == "__main__":
    logger.info("🌐 Starting ULTRA Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
