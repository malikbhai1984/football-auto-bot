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
from threading import Thread
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")

logger.info("🚀 Initializing COMPLETE Prediction Bot...")

# Validate environment variables
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found")
if not OWNER_CHAT_ID:
    logger.error("❌ OWNER_CHAT_ID not found") 
if not SPORTMONKS_API:
    logger.error("❌ SPORTMONKS_API not found")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
    logger.info(f"✅ OWNER_CHAT_ID: {OWNER_CHAT_ID}")
except (ValueError, TypeError) as e:
    logger.error(f"❌ Invalid OWNER_CHAT_ID: {e}")

bot = telebot.TeleBot(BOT_TOKEN)
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

# Global variables
bot_started = False
message_counter = 0

def get_pakistan_time():
    """Get current Pakistan time"""
    return datetime.now(PAK_TZ)

def format_pakistan_time(dt=None):
    """Format datetime in Pakistan time"""
    if dt is None:
        dt = get_pakistan_time()
    return dt.strftime('%H:%M %Z')

@app.route("/")
def health():
    return "⚽ COMPLETE Prediction Bot is Running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

def send_telegram_message(message):
    """Send message to Telegram with retry logic"""
    global message_counter
    try:
        message_counter += 1
        logger.info(f"📤 Sending message #{message_counter}")
        bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
        logger.info(f"✅ Message #{message_counter} sent successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send message #{message_counter}: {e}")
        return False

def fetch_current_live_matches():
    """Fetch ONLY current live matches"""
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        logger.info("🌐 Fetching CURRENT live matches...")
        
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
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
                        
                        if 1 <= current_minute <= 89:
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
                                "is_live": True
                            }
                            
                            current_matches.append(match_data)
        
        logger.info(f"📊 ACTIVE LIVE matches: {len(current_matches)}")
        return current_matches
        
    except Exception as e:
        logger.error(f"❌ Error fetching current matches: {e}")
        return []

class CompletePredictor:
    def __init__(self):
        self.prediction_history = []
    
    def calculate_over_under_predictions(self, match):
        """Calculate Over/Under predictions from 0.5 to 5.5"""
        try:
            minute = match.get('current_minute', 0)
            home_score = match.get('home_score', 0)
            away_score = match.get('away_score', 0)
            total_goals = home_score + away_score
            
            predictions = {}
            
            # Over/Under 0.5
            if total_goals > 0.5:
                predictions['over_0_5'] = {'confidence': 95, 'value': 'OVER'}
            else:
                goals_per_minute = total_goals / max(1, minute)
                remaining_time = 90 - minute
                expected_goals = goals_per_minute * remaining_time
                confidence = min(90, max(10, int(expected_goals * 30)))
                predictions['over_0_5'] = {'confidence': confidence, 'value': 'OVER'}
            
            # Over/Under 1.5
            if total_goals > 1.5:
                predictions['over_1_5'] = {'confidence': 90, 'value': 'OVER'}
            else:
                needed_goals = 1.5 - total_goals
                time_factor = (90 - minute) / 90
                confidence = min(85, max(5, int(70 * time_factor * (2 - needed_goals))))
                predictions['over_1_5'] = {'confidence': confidence, 'value': 'OVER' if confidence > 50 else 'UNDER'}
            
            # Over/Under 2.5
            if total_goals > 2.5:
                predictions['over_2_5'] = {'confidence': 85, 'value': 'OVER'}
            else:
                needed_goals = 2.5 - total_goals
                time_factor = (90 - minute) / 90
                confidence = min(80, max(5, int(60 * time_factor * (2.5 - needed_goals))))
                predictions['over_2_5'] = {'confidence': confidence, 'value': 'OVER' if confidence > 50 else 'UNDER'}
            
            # Over/Under 3.5
            if total_goals > 3.5:
                predictions['over_3_5'] = {'confidence': 80, 'value': 'OVER'}
            else:
                needed_goals = 3.5 - total_goals
                time_factor = (90 - minute) / 90
                confidence = min(75, max(5, int(50 * time_factor * (3.5 - needed_goals))))
                predictions['over_3_5'] = {'confidence': confidence, 'value': 'OVER' if confidence > 50 else 'UNDER'}
            
            # Over/Under 4.5
            if total_goals > 4.5:
                predictions['over_4_5'] = {'confidence': 75, 'value': 'OVER'}
            else:
                needed_goals = 4.5 - total_goals
                time_factor = (90 - minute) / 90
                confidence = min(70, max(5, int(40 * time_factor * (4.5 - needed_goals))))
                predictions['over_4_5'] = {'confidence': confidence, 'value': 'OVER' if confidence > 50 else 'UNDER'}
            
            # Over/Under 5.5
            if total_goals > 5.5:
                predictions['over_5_5'] = {'confidence': 70, 'value': 'OVER'}
            else:
                needed_goals = 5.5 - total_goals
                time_factor = (90 - minute) / 90
                confidence = min(65, max(5, int(30 * time_factor * (5.5 - needed_goals))))
                predictions['over_5_5'] = {'confidence': confidence, 'value': 'OVER' if confidence > 50 else 'UNDER'}
            
            return predictions
            
        except Exception as e:
            logger.error(f"❌ Over/Under calculation error: {e}")
            return {}
    
    def calculate_match_result(self, match):
        """Calculate Match Winner predictions"""
        try:
            minute = match.get('current_minute', 0)
            home_score = match.get('home_score', 0)
            away_score = match.get('away_score', 0)
            
            goal_difference = home_score - away_score
            time_remaining = 90 - minute
            
            # Current score based predictions
            if goal_difference > 0:  # Home leading
                home_win_confidence = min(95, 70 + (goal_difference * 10) + (time_remaining <= 15) * 20)
                draw_confidence = max(5, 25 - (goal_difference * 5))
                away_win_confidence = max(2, 5 - (goal_difference * 3))
            elif goal_difference < 0:  # Away leading
                home_win_confidence = max(2, 5 - (abs(goal_difference) * 3))
                draw_confidence = max(5, 25 - (abs(goal_difference) * 5))
                away_win_confidence = min(95, 70 + (abs(goal_difference) * 10) + (time_remaining <= 15) * 20)
            else:  # Draw
                home_win_confidence = 35
                draw_confidence = 40
                away_win_confidence = 25
            
            # Adjust for time remaining
            if time_remaining <= 15:
                if goal_difference > 0:
                    home_win_confidence += 15
                elif goal_difference < 0:
                    away_win_confidence += 15
                else:
                    draw_confidence += 10
            
            return {
                'home_win': {'confidence': home_win_confidence, 'value': 'HOME WIN'},
                'draw': {'confidence': draw_confidence, 'value': 'DRAW'}, 
                'away_win': {'confidence': away_win_confidence, 'value': 'AWAY WIN'}
            }
            
        except Exception as e:
            logger.error(f"❌ Match result calculation error: {e}")
            return {}
    
    def calculate_both_teams_score(self, match):
        """Calculate Both Teams To Score predictions"""
        try:
            minute = match.get('current_minute', 0)
            home_score = match.get('home_score', 0)
            away_score = match.get('away_score', 0)
            
            # Both have already scored
            if home_score > 0 and away_score > 0:
                return {'btts_yes': {'confidence': 95, 'value': 'YES'}}
            
            # One team hasn't scored yet
            time_factor = minute / 90
            if home_score > 0 and away_score == 0:
                confidence = min(85, int(70 + (time_factor * 25)))
                return {'btts_yes': {'confidence': confidence, 'value': 'YES'}}
            elif home_score == 0 and away_score > 0:
                confidence = min(85, int(70 + (time_factor * 25)))
                return {'btts_yes': {'confidence': confidence, 'value': 'YES'}}
            else:  # No goals yet
                confidence = min(80, int(60 + (time_factor * 30)))
                return {'btts_yes': {'confidence': confidence, 'value': 'YES'}}
                
        except Exception as e:
            logger.error(f"❌ BTTS calculation error: {e}")
            return {}
    
    def calculate_goal_timing(self, match):
        """Calculate Goal Timing predictions"""
        try:
            minute = match.get('current_minute', 0)
            total_goals = match.get('home_score', 0) + match.get('away_score', 0)
            
            goals_per_minute = total_goals / max(1, minute)
            remaining_time = 90 - minute
            
            # Goal in last 15 minutes
            last_15_chance = min(90, int(goals_per_minute * 15 * 25 + 30))
            
            # Goal in last 10 minutes  
            last_10_chance = min(85, int(goals_per_minute * 10 * 30 + 25))
            
            # Goal before 75 minutes
            if minute < 75:
                before_75_chance = min(95, int(goals_per_minute * (75 - minute) * 20 + 40))
            else:
                before_75_chance = 5
            
            # Goal before 60 minutes
            if minute < 60:
                before_60_chance = min(95, int(goals_per_minute * (60 - minute) * 18 + 35))
            else:
                before_60_chance = 5
            
            # Goal before 30 minutes
            if minute < 30:
                before_30_chance = min(90, int(goals_per_minute * (30 - minute) * 15 + 30))
            else:
                before_30_chance = 5
            
            return {
                'goal_last_15': {'confidence': last_15_chance, 'value': 'YES'},
                'goal_last_10': {'confidence': last_10_chance, 'value': 'YES'},
                'goal_before_75': {'confidence': before_75_chance, 'value': 'YES'},
                'goal_before_60': {'confidence': before_60_chance, 'value': 'YES'},
                'goal_before_30': {'confidence': before_30_chance, 'value': 'YES'}
            }
            
        except Exception as e:
            logger.error(f"❌ Goal timing calculation error: {e}")
            return {}
    
    def generate_all_predictions(self, match):
        """Generate ALL predictions for a match"""
        try:
            all_predictions = {}
            
            # Over/Under predictions
            all_predictions['over_under'] = self.calculate_over_under_predictions(match)
            
            # Match result predictions  
            all_predictions['match_result'] = self.calculate_match_result(match)
            
            # Both teams to score
            all_predictions['btts'] = self.calculate_both_teams_score(match)
            
            # Goal timing predictions
            all_predictions['goal_timing'] = self.calculate_goal_timing(match)
            
            return all_predictions
            
        except Exception as e:
            logger.error(f"❌ All predictions generation error: {e}")
            return {}

# Initialize predictor
predictor = CompletePredictor()

def analyze_complete_predictions():
    """Analyze matches with complete prediction types"""
    try:
        logger.info("🔍 Generating COMPLETE predictions...")
        live_matches = fetch_current_live_matches()
        
        if not live_matches:
            send_telegram_message(
                "📭 **NO LIVE MATCHES**\n\n"
                "No active matches in top leagues.\n"
                f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
                "🔄 Will check again in 7 minutes..."
            )
            return 0
        
        predictions_sent = 0
        
        for match in live_matches:
            # Generate ALL predictions
            all_predictions = predictor.generate_all_predictions(match)
            
            # Filter only high-confidence predictions (75%+)
            high_confidence_predictions = []
            
            # Check Over/Under predictions
            for pred_type, pred_data in all_predictions.get('over_under', {}).items():
                if pred_data['confidence'] >= 75:
                    high_confidence_predictions.append({
                        'type': 'OVER_UNDER',
                        'market': pred_type.upper(),
                        'prediction': pred_data['value'],
                        'confidence': pred_data['confidence'],
                        'match': match
                    })
            
            # Check Match Result predictions
            for pred_type, pred_data in all_predictions.get('match_result', {}).items():
                if pred_data['confidence'] >= 75:
                    high_confidence_predictions.append({
                        'type': 'MATCH_RESULT', 
                        'market': pred_type.upper(),
                        'prediction': pred_data['value'],
                        'confidence': pred_data['confidence'],
                        'match': match
                    })
            
            # Check BTTS predictions
            for pred_type, pred_data in all_predictions.get('btts', {}).items():
                if pred_data['confidence'] >= 75:
                    high_confidence_predictions.append({
                        'type': 'BTTS',
                        'market': 'BOTH_TEAMS_SCORE',
                        'prediction': pred_data['value'],
                        'confidence': pred_data['confidence'],
                        'match': match
                    })
            
            # Check Goal Timing predictions
            for pred_type, pred_data in all_predictions.get('goal_timing', {}).items():
                if pred_data['confidence'] >= 75:
                    high_confidence_predictions.append({
                        'type': 'GOAL_TIMING',
                        'market': pred_type.upper(),
                        'prediction': pred_data['value'],
                        'confidence': pred_data['confidence'],
                        'match': match
                    })
            
            # Send high-confidence predictions
            for pred in high_confidence_predictions[:3]:  # Max 3 per match to avoid spam
                message = format_prediction_message(pred)
                if send_telegram_message(message):
                    predictions_sent += 1
        
        # If no high-confidence predictions, send summary
        if predictions_sent == 0 and live_matches:
            summary_msg = create_prediction_summary(live_matches)
            send_telegram_message(summary_msg)
            predictions_sent = 1
        
        logger.info(f"📈 Complete predictions sent: {predictions_sent}")
        return predictions_sent
        
    except Exception as e:
        logger.error(f"❌ Complete analysis error: {e}")
        return 0

def format_prediction_message(prediction):
    """Format prediction message based on type"""
    match = prediction['match']
    
    base_message = (
        f"🎯 **{prediction['type'].replace('_', ' ').title()} PREDICTION** 🎯\n\n"
        f"⚽ **Match:** {match['home']} vs {match['away']}\n"
        f"🏆 **League:** {match['league']}\n"
        f"📊 **Score:** {match['score']} ({match['minute']}')\n"
        f"📈 **Market:** {prediction['market'].replace('_', ' ').title()}\n"
        f"🎪 **Prediction:** {prediction['prediction']}\n"
        f"✅ **Confidence:** {prediction['confidence']}%\n"
    )
    
    # Add specific betting suggestions
    if prediction['type'] == 'OVER_UNDER':
        base_message += f"💰 **Bet:** {prediction['prediction']} {prediction['market'].replace('_', '.')} Goals\n"
    elif prediction['type'] == 'MATCH_RESULT':
        base_message += f"💰 **Bet:** {prediction['prediction']}\n"
    elif prediction['type'] == 'BTTS':
        base_message += f"💰 **Bet:** Both Teams to Score - {prediction['prediction']}\n"
    elif prediction['type'] == 'GOAL_TIMING':
        base_message += f"💰 **Bet:** Goal {prediction['market'].replace('_', ' ').title()} - {prediction['prediction']}\n"
    
    base_message += f"\n🕒 **Pakistan Time:** {format_pakistan_time()}\n"
    base_message += "🔄 Next analysis in 7 minutes..."
    
    return base_message

def create_prediction_summary(matches):
    """Create prediction summary for matches"""
    summary_msg = "📊 **PREDICTION SUMMARY**\n\n"
    summary_msg += f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
    summary_msg += f"🔴 **Live Matches:** {len(matches)}\n\n"
    
    for match in matches[:3]:  # Show first 3 matches
        all_predictions = predictor.generate_all_predictions(match)
        
        summary_msg += f"⚽ **{match['home']} vs {match['away']}**\n"
        summary_msg += f"   📊 {match['score']} ({match['minute']}')\n"
        summary_msg += f"   🏆 {match['league']}\n"
        
        # Show top 2 predictions
        top_predictions = []
        for pred_category in ['over_under', 'match_result', 'btts', 'goal_timing']:
            for pred_type, pred_data in all_predictions.get(pred_category, {}).items():
                if pred_data['confidence'] >= 60:  # Lower threshold for summary
                    top_predictions.append((pred_data['confidence'], pred_type, pred_data['value']))
        
        # Sort by confidence and take top 2
        top_predictions.sort(reverse=True)
        for conf, pred_type, value in top_predictions[:2]:
            summary_msg += f"   🎯 {pred_type.replace('_', ' ').title()}: {value} ({conf}%)\n"
        
        summary_msg += "\n"
    
    summary_msg += "🔍 Monitoring for high-confidence opportunities...\n"
    summary_msg += "⏰ Next update in 7 minutes"
    
    return summary_msg

def send_startup_message():
    """Send startup message"""
    try:
        message = (
            "🤖 **COMPLETE PREDICTION BOT ACTIVATED!** 🤖\n\n"
            "✅ **Status:** All Prediction Types Active\n"
            f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
            "⏰ **Update Interval:** Every 7 minutes\n\n"
            "🎯 **PREDICTION MARKETS:**\n"
            "• Over/Under 0.5 to 5.5 Goals\n"
            "• Match Winner (1X2)\n"  
            "• Both Teams To Score\n"
            "• Goal Timing Predictions\n"
            "• Double Chance\n"
            "• Exact Goals\n\n"
            "💰 **75%+ Confidence Only**\n"
            "🔜 Starting complete analysis..."
        )
        return send_telegram_message(message)
    except Exception as e:
        logger.error(f"❌ Startup message failed: {e}")
        return False

def bot_worker():
    """Main bot worker with 7-minute intervals"""
    global bot_started
    logger.info("🔄 Starting Complete Prediction Bot...")
    
    time.sleep(10)
    
    logger.info("📤 Sending startup message...")
    if send_startup_message():
        logger.info("✅ Startup message delivered")
    
    cycle = 0
    while True:
        try:
            cycle += 1
            logger.info(f"🔄 Prediction Cycle #{cycle} at {format_pakistan_time()}")
            
            predictions = analyze_complete_predictions()
            logger.info(f"📈 Cycle #{cycle}: {predictions} predictions sent")
            
            if cycle % 6 == 0:
                status_msg = (
                    f"📊 **COMPLETE BOT STATUS**\n\n"
                    f"🔄 Analysis Cycles: {cycle}\n"
                    f"📨 Total Messages: {message_counter}\n"
                    f"🎯 Last Predictions: {predictions}\n"
                    f"🕒 **Pakistan Time:** {format_pakistan_time()}\n"
                    f"✅ Status: ALL MARKETS ACTIVE\n\n"
                    f"⏰ Next analysis in 7 minutes..."
                )
                send_telegram_message(status_msg)
            
            time.sleep(420)  # 7 minutes
            
        except Exception as e:
            logger.error(f"❌ Bot worker error: {e}")
            time.sleep(420)

def start_bot_thread():
    """Start bot in background thread"""
    global bot_started
    if not bot_started:
        logger.info("🚀 Starting complete prediction bot thread...")
        thread = Thread(target=bot_worker, daemon=True)
        thread.start()
        bot_started = True
        logger.info("✅ Complete prediction bot started")
    else:
        logger.info("✅ Bot thread already running")

# Auto-start bot
logger.info("🎯 Auto-starting Complete Prediction Bot...")
start_bot_thread()

if __name__ == "__main__":
    logger.info("🌐 Starting Flask server...")
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🔌 Running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
