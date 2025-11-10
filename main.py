import os
import requests
import telebot
import time
import random
import math
from datetime import datetime, timedelta
from flask import Flask, request
import threading
from dotenv import load_dotenv
import json

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
PORT = int(os.environ.get("PORT", 8080))
DOMAIN = os.environ.get("DOMAIN")

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, API_KEY, or DOMAIN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ✅ CORRECT API URL FOR API-FOOTBALL.COM
API_URL = "https://apiv3.apifootball.com"

print("🎯 Starting REAL-TIME PREDICTION UPDATER...")

# -------------------------
# SMART MATCH PROCESSING
# -------------------------
def safe_int(value, default=0):
    """Safely convert to integer"""
    try:
        if value is None or value == '' or value == ' ':
            return default
        return int(value)
    except:
        return default

def fetch_live_matches_reliable():
    """Reliably fetch live matches"""
    try:
        print("🔄 Fetching current live matches...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
        
        response = requests.get(url, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            
            if data and isinstance(data, list):
                live_matches = [match for match in data if match.get("match_live") == "1"]
                print(f"✅ Found {len(live_matches)} live matches")
                return live_matches
            else:
                print("⏳ No live matches data")
                return []
        else:
            print(f"❌ API Error {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Fetch error: {e}")
        return []

def process_match_smart(match):
    """Smart match processing with fallbacks"""
    try:
        # Essential data extraction
        match_id = match.get("match_id", f"match_{random.randint(1000,9999)}")
        home_team = match.get("match_hometeam_name", "Home Team")
        away_team = match.get("match_awayteam_name", "Away Team")
        
        # Safe score conversion
        home_score = safe_int(match.get("match_hometeam_score"), 0)
        away_score = safe_int(match.get("match_awayteam_score"), 0)
        
        league = match.get("league_name", "Unknown League")
        country = match.get("country_name", "")
        match_status = match.get("match_status", "")
        
        # Smart time parsing
        if match_status.isdigit():
            current_minute = safe_int(match_status, 45)
            status = "LIVE"
            time_display = f"{current_minute}'"
        elif match_status == "Half Time":
            current_minute = 45
            status = "HT"
            time_display = "HT"
        elif match_status == "Finished":
            current_minute = 90
            status = "FT"
            time_display = "FT"
        else:
            current_minute = 0
            status = "NS"
            time_display = "NS"
        
        is_live = match.get("match_live") == "1"
        
        return {
            "match_id": match_id,
            "match_hometeam_name": home_team,
            "match_awayteam_name": away_team,
            "match_hometeam_score": str(home_score),
            "match_awayteam_score": str(away_score),
            "league_name": league,
            "league_country": country,
            "match_time": time_display,
            "match_live": "1" if is_live else "0",
            "match_status": status,
            "current_minute": current_minute,
            "statistics": match.get("statistics", []),
            "goalscorer": match.get("goalscorer", []),
            "cards": match.get("cards", []),
            "match_date": match.get("match_date", "")
        }
        
    except Exception as e:
        print(f"⚠️ Match processing error: {e}")
        return None

def get_current_matches():
    """Get current matches with reliable processing"""
    try:
        raw_matches = fetch_live_matches_reliable()
        
        if not raw_matches:
            print("⏳ No live matches available")
            return []
        
        processed_matches = []
        for match in raw_matches:
            processed_match = process_match_smart(match)
            if processed_match:
                processed_matches.append(processed_match)
        
        print(f"✅ Successfully processed {len(processed_matches)} matches")
        return processed_matches
            
    except Exception as e:
        print(f"❌ Match processing system error: {e}")
        return []

# -------------------------
# REAL-TIME PREDICTION ENGINE
# -------------------------
class RealTimePredictor:
    def __init__(self):
        self.min_confidence = 80  # 80%+ confidence for updates
        
    def generate_fresh_predictions(self, match):
        """Generate FRESH predictions based on CURRENT match situation"""
        try:
            home_team = match.get("match_hometeam_name", "Home")
            away_team = match.get("match_awayteam_name", "Away")
            home_score = safe_int(match.get("match_hometeam_score"), 0)
            away_score = safe_int(match.get("match_awayteam_score"), 0)
            minute = safe_int(match.get("current_minute"), 0)
            status = match.get("match_status", "")
            
            print(f"  🔄 FRESH ANALYSIS: {home_team} {home_score}-{away_score} {away_team} ({minute}')")
            
            # Generate fresh analysis based on current situation
            fresh_predictions = self.analyze_current_situation(home_score, away_score, minute, status)
            
            return {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "match_info": {
                    "home_team": home_team,
                    "away_team": away_team,
                    "current_score": f"{home_score}-{away_score}",
                    "current_minute": minute,
                    "match_status": status,
                    "league": match.get("league_name", "")
                },
                "fresh_predictions": fresh_predictions,
                "match_insights": self.generate_match_insights(home_score, away_score, minute)
            }
            
        except Exception as e:
            print(f"❌ Fresh prediction error: {e}")
            return None

    def analyze_current_situation(self, home_score, away_score, minute, status):
        """Analyze CURRENT match situation for FRESH predictions"""
        goal_diff = home_score - away_score
        total_goals = home_score + away_score
        time_remaining = 90 - minute
        
        predictions = []
        
        # 1. CURRENT MATCH RESULT PREDICTION
        result_pred = self.predict_current_result(home_score, away_score, minute)
        if result_pred:
            predictions.append(result_pred)
        
        # 2. CURRENT GOAL EXPECTATIONS
        goal_pred = self.predict_goal_expectations(total_goals, minute, goal_diff)
        if goal_pred:
            predictions.append(goal_pred)
        
        # 3. CURRENT BTTS SITUATION
        btts_pred = self.predict_current_btts(home_score, away_score, minute)
        if btts_pred:
            predictions.append(btts_pred)
        
        # 4. CURRENT NEXT GOAL SITUATION
        next_goal_pred = self.predict_current_next_goal(home_score, away_score, minute)
        if next_goal_pred:
            predictions.append(next_goal_pred)
        
        # 5. CURRENT MATCH TREND
        trend_pred = self.predict_match_trend(home_score, away_score, minute)
        if trend_pred:
            predictions.append(trend_pred)
            
        return predictions

    def predict_current_result(self, home_score, away_score, minute):
        """Predict result based on CURRENT situation"""
        goal_diff = home_score - away_score
        time_factor = minute / 90.0
        
        if goal_diff > 0:
            # Home leading
            if minute >= 80:
                confidence = 90 + (goal_diff * 3)
                prediction = "HOME WIN"
                reason = f"Home leading by {goal_diff} with only {90-minute} mins left"
            elif minute >= 60:
                confidence = 75 + (goal_diff * 5)
                prediction = "HOME WIN" 
                reason = f"Home leading by {goal_diff} with {90-minute} mins remaining"
            else:
                confidence = 60 + (goal_diff * 6)
                prediction = "HOME WIN"
                reason = f"Home leading but {90-minute} mins to play"
                
        elif goal_diff < 0:
            # Away leading
            if minute >= 80:
                confidence = 90 + (abs(goal_diff) * 3)
                prediction = "AWAY WIN"
                reason = f"Away leading by {abs(goal_diff)} with only {90-minute} mins left"
            elif minute >= 60:
                confidence = 75 + (abs(goal_diff) * 5)
                prediction = "AWAY WIN"
                reason = f"Away leading by {abs(goal_diff)} with {90-minute} mins remaining"
            else:
                confidence = 60 + (abs(goal_diff) * 6)
                prediction = "AWAY WIN"
                reason = f"Away leading but {90-minute} mins to play"
                
        else:
            # Draw
            if minute >= 80:
                confidence = 85
                prediction = "DRAW"
                reason = f"Score level with only {90-minute} mins remaining"
            elif minute >= 60:
                confidence = 65
                prediction = "DRAW"
                reason = f"Close match with {90-minute} mins to play"
            else:
                confidence = 50
                prediction = "DRAW"
                reason = f"Evenly poised with {90-minute} mins remaining"
        
        if confidence >= self.min_confidence:
            return {
                "market": "MATCH RESULT",
                "prediction": prediction,
                "confidence": min(95, confidence),
                "reason": reason,
                "current_situation": f"{home_score}-{away_score} at {minute}'"
            }
        return None

    def predict_goal_expectations(self, total_goals, minute, goal_diff):
        """Predict goal expectations based on CURRENT situation"""
        time_remaining = 90 - minute
        
        # Calculate expected additional goals
        if minute > 0:
            goals_per_minute = total_goals / minute
            expected_additional = goals_per_minute * time_remaining * 1.1
        else:
            expected_additional = 2.5
            
        total_expected = total_goals + expected_additional
        
        # Generate predictions
        if total_expected >= 3.5 and minute <= 70:
            confidence = 85 + (total_expected - 3.5) * 10
            return {
                "market": "GOAL EXPECTATION",
                "prediction": f"HIGH SCORING - Expected {total_expected:.1f} total goals",
                "confidence": min(95, confidence),
                "reason": f"Current {total_goals} goals + expected {expected_additional:.1f} more",
                "current_situation": f"{total_goals} goals by {minute}'"
            }
        elif total_expected <= 1.5 and minute >= 60:
            confidence = 88
            return {
                "market": "GOAL EXPECTATION", 
                "prediction": "LOW SCORING - Under 2.5 goals likely",
                "confidence": confidence,
                "reason": f"Only {total_goals} goals after {minute} minutes",
                "current_situation": f"{total_goals} goals by {minute}'"
            }
        elif total_goals >= 4:
            confidence = 95
            return {
                "market": "GOAL EXPECTATION",
                "prediction": "VERY HIGH SCORING - Over 3.5 goals",
                "confidence": confidence,
                "reason": f"Already {total_goals} goals scored",
                "current_situation": f"{total_goals} goals by {minute}'"
            }
            
        return None

    def predict_current_btts(self, home_score, away_score, minute):
        """Predict BTTS based on CURRENT situation"""
        if home_score > 0 and away_score > 0:
            confidence = 95
            return {
                "market": "BOTH TEAMS SCORED",
                "prediction": "YES - Both teams already scored",
                "confidence": confidence,
                "reason": "Both teams have found the net",
                "current_situation": f"Score: {home_score}-{away_score}"
            }
        elif home_score > 0 and minute <= 40:
            confidence = 80
            return {
                "market": "BOTH TEAMS SCORED",
                "prediction": "LIKELY YES - Away team should respond",
                "confidence": confidence,
                "reason": f"Home scored early, away team pushing for equalizer",
                "current_situation": f"Score: {home_score}-{away_score} at {minute}'"
            }
        elif away_score > 0 and minute <= 40:
            confidence = 80
            return {
                "market": "BOTH TEAMS SCORED",
                "prediction": "LIKELY YES - Home team should respond",
                "confidence": confidence,
                "reason": f"Away scored early, home team pushing for equalizer",
                "current_situation": f"Score: {home_score}-{away_score} at {minute}'"
            }
        elif home_score == 0 and away_score == 0 and minute >= 70:
            confidence = 85
            return {
                "market": "BOTH TEAMS SCORED",
                "prediction": "LIKELY NO - Late without goals",
                "confidence": confidence,
                "reason": f"No goals after {minute} minutes",
                "current_situation": f"Score: {home_score}-{away_score} at {minute}'"
            }
            
        return None

    def predict_current_next_goal(self, home_score, away_score, minute):
        """Predict next goal based on CURRENT situation"""
        goal_diff = home_score - away_score
        time_remaining = 90 - minute
        
        if minute >= 85:
            confidence = 90
            return {
                "market": "NEXT GOAL",
                "prediction": "NO MORE GOALS - Match ending",
                "confidence": confidence,
                "reason": f"Only {time_remaining} minutes remaining",
                "current_situation": f"{minute}' played"
            }
        elif goal_diff >= 2 and minute >= 60:
            confidence = 85
            return {
                "market": "NEXT GOAL",
                "prediction": "AWAY TEAM - Needs to respond",
                "confidence": confidence,
                "reason": f"Away team trailing by {goal_diff} goals",
                "current_situation": f"Score: {home_score}-{away_score}"
            }
        elif goal_diff <= -2 and minute >= 60:
            confidence = 85
            return {
                "market": "NEXT GOAL",
                "prediction": "HOME TEAM - Needs to respond", 
                "confidence": confidence,
                "reason": f"Home team trailing by {abs(goal_diff)} goals",
                "current_situation": f"Score: {home_score}-{away_score}"
            }
        elif goal_diff == 0 and minute >= 75:
            confidence = 80
            return {
                "market": "NEXT GOAL",
                "prediction": "EITHER TEAM - Late winner possible",
                "confidence": confidence,
                "reason": f"Score level with {time_remaining} mins left",
                "current_situation": f"Score: {home_score}-{away_score}"
            }
            
        return None

    def predict_match_trend(self, home_score, away_score, minute):
        """Predict match trend based on CURRENT situation"""
        goal_diff = home_score - away_score
        
        if goal_diff >= 2 and minute >= 70:
            return {
                "market": "MATCH TREND",
                "prediction": "HOME CONTROL - Comfortable lead",
                "confidence": 88,
                "reason": f"Home leading by {goal_diff} with {90-minute} mins left",
                "current_situation": f"Score: {home_score}-{away_score}"
            }
        elif goal_diff <= -2 and minute >= 70:
            return {
                "market": "MATCH TREND",
                "prediction": "AWAY CONTROL - Comfortable lead",
                "confidence": 88,
                "reason": f"Away leading by {abs(goal_diff)} with {90-minute} mins left", 
                "current_situation": f"Score: {home_score}-{away_score}"
            }
        elif abs(goal_diff) == 1 and minute >= 80:
            return {
                "market": "MATCH TREND",
                "prediction": "TENSE FINISH - One goal game",
                "confidence": 85,
                "reason": f"Close game with {90-minute} mins remaining",
                "current_situation": f"Score: {home_score}-{away_score}"
            }
        elif goal_diff == 0 and minute >= 60:
            return {
                "market": "MATCH TREND",
                "prediction": "BALANCED - Either team could win",
                "confidence": 82,
                "reason": f"Even match with {90-minute} mins to play",
                "current_situation": f"Score: {home_score}-{away_score}"
            }
            
        return None

    def generate_match_insights(self, home_score, away_score, minute):
        """Generate insights based on current match state"""
        insights = []
        goal_diff = home_score - away_score
        
        if minute >= 80 and abs(goal_diff) <= 1:
            insights.append(f"⏰ Last 10 minutes - crucial period")
        
        if goal_diff >= 2:
            insights.append(f"📈 Home team in control")
        elif goal_diff <= -2:
            insights.append(f"📈 Away team in control")
        else:
            insights.append(f"⚖️ Match evenly balanced")
            
        if minute <= 30 and home_score + away_score >= 2:
            insights.append(f"🎯 High-tempo start")
        elif minute >= 60 and home_score + away_score == 0:
            insights.append(f"🛡️ Defensive battle")
            
        return insights

# Initialize predictor
realtime_predictor = RealTimePredictor()

# -------------------------
# FRESH PREDICTION MESSAGES
# -------------------------
def generate_fresh_prediction_message(match_analysis):
    """Generate FRESH prediction message based on CURRENT analysis"""
    try:
        if not match_analysis or not match_analysis["fresh_predictions"]:
            return None
            
        match_info = match_analysis["match_info"]
        fresh_predictions = match_analysis["fresh_predictions"]
        
        message = f"🔄 **FRESH PREDICTION UPDATE**\n"
        message += f"⏰ Analysis Time: {match_analysis['timestamp']}\n\n"
        
        message += f"⚽ **{match_info['home_team']} vs {match_info['away_team']}**\n"
        message += f"🏆 {match_info.get('league', '')}\n"
        message += f"📊 Current: {match_info['current_score']} | ⏱️ {match_info['current_minute']}' | 🔴 {match_info['match_status']}\n\n"
        
        message += "🎯 **CURRENT SITUATION ANALYSIS**\n\n"
        
        for prediction in fresh_predictions:
            message += f"**{prediction['market']}**\n"
            message += f"✅ Prediction: `{prediction['prediction']}`\n"
            message += f"📈 Confidence: `{prediction['confidence']}%`\n"
            message += f"💡 Reason: {prediction['reason']}\n"
            message += f"📊 Situation: {prediction['current_situation']}\n\n"
        
        # Add match insights
        insights = match_analysis.get("match_insights", [])
        if insights:
            message += "🔍 **MATCH INSIGHTS:**\n"
            for insight in insights:
                message += f"• {insight}\n"
            message += "\n"
        
        message += "🔄 Next fresh analysis in 5 minutes...\n"
        message += "🎯 *Predictions based on current match situation*"
        
        return message
        
    except Exception as e:
        print(f"❌ Fresh message generation error: {e}")
        return None

# -------------------------
# PREDICTION HISTORY MANAGER
# -------------------------
class PredictionManager:
    def __init__(self):
        self.last_analysis_time = {}
        
    def should_analyze_match(self, match_id):
        """Check if we should analyze this match (5 minute interval)"""
        current_time = time.time()
        last_time = self.last_analysis_time.get(match_id, 0)
        
        # Analyze every 5 minutes
        if current_time - last_time >= 300:
            self.last_analysis_time[match_id] = current_time
            return True
        return False

prediction_manager = PredictionManager()

# -------------------------
# REAL-TIME AUTO UPDATER
# -------------------------
def realtime_auto_updater():
    """Auto-updater that provides FRESH analysis every 5 minutes"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Starting FRESH analysis cycle...")
            
            # Get current matches
            matches = get_current_matches()
            
            if not matches:
                print("⏳ No live matches for analysis")
                time.sleep(300)
                continue
            
            fresh_analyses = 0
            predictions_sent = 0
            
            for match in matches:
                try:
                    match_id = match.get("match_id")
                    home = match.get("match_hometeam_name")
                    away = match.get("match_awayteam_name")
                    score = f"{match.get('match_hometeam_score')}-{match.get('match_awayteam_score')}"
                    minute = match.get("current_minute")
                    
                    print(f"  🔄 Fresh analysis: {home} {score} {away} ({minute}')")
                    
                    # Check if we should analyze this match
                    if prediction_manager.should_analyze_match(match_id):
                        # Generate FRESH predictions based on current situation
                        fresh_analysis = realtime_predictor.generate_fresh_predictions(match)
                        
                        if fresh_analysis and fresh_analysis["fresh_predictions"]:
                            fresh_analyses += 1
                            
                            # Generate and send message
                            message = generate_fresh_prediction_message(fresh_analysis)
                            
                            if message:
                                try:
                                    bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
                                    predictions_sent += 1
                                    print(f"    ✅ FRESH ANALYSIS SENT: {home} vs {away}")
                                    time.sleep(2)  # Rate limiting
                                except Exception as e:
                                    print(f"    ❌ Send failed: {e}")
                    else:
                        print(f"    ⏳ Analysis not due yet")
                        
                except Exception as e:
                    print(f"    ❌ Match analysis failed: {e}")
                    continue
            
            # Send cycle summary
            summary_msg = f"""
📊 **FRESH ANALYSIS CYCLE COMPLETE**

⏰ Cycle Time: {current_time}
🔍 Matches Processed: {len(matches)}
🔄 Fresh Analyses: {fresh_analyses}
📤 Predictions Sent: {predictions_sent}

{'✅ Fresh predictions delivered!' if predictions_sent > 0 else '⏳ No high-confidence opportunities'}
🔄 Next analysis cycle in 5 minutes...
"""
            try:
                bot.send_message(OWNER_CHAT_ID, summary_msg, parse_mode='Markdown')
                print(f"📊 Cycle summary sent: {predictions_sent} fresh analyses")
            except Exception as e:
                print(f"❌ Summary send failed: {e}")
                
        except Exception as e:
            print(f"❌ Auto-updater system error: {e}")
        
        print("💤 Next analysis cycle in 5 minutes...")
        time.sleep(300)

# -------------------------
# TELEGRAM COMMANDS
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    help_text = """
🤖 **REAL-TIME PREDICTION UPDATER**

🔄 **FRESH ANALYSIS EVERY 5 MINUTES!**
• Completely new predictions based on current match situation
• Real-time score and time analysis
• Current match trend predictions
• Fresh insights every cycle

📊 **Analysis Includes:**
• Match Result predictions
• Goal expectations
• Both Teams to Score
• Next Goal scenarios
• Match trend analysis

⚡ **Commands:**
• `/analyze` - Manual fresh analysis
• `/matches` - Current live matches
• `/status` - System status

🎯 **Auto-analyzes every 5 minutes with fresh data!**
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['analyze'])
def manual_analysis(message):
    """Manual fresh analysis"""
    try:
        bot.reply_to(message, "🔍 Starting FRESH analysis of current matches...")
        
        matches = get_current_matches()
        
        if not matches:
            bot.reply_to(message, "⏳ No live matches currently available.")
            return
        
        analysis_count = 0
        response_message = "🔄 **FRESH ANALYSIS RESULTS**\n\n"
        
        for match in matches[:3]:  # Analyze first 3 matches
            fresh_analysis = realtime_predictor.generate_fresh_predictions(match)
            
            if fresh_analysis and fresh_analysis["fresh_predictions"]:
                analysis_count += 1
                match_info = fresh_analysis["match_info"]
                
                response_message += f"⚽ **{match_info['home_team']} vs {match_info['away_team']}**\n"
                response_message += f"📊 {match_info['current_score']} | ⏱️ {match_info['current_minute']}'\n"
                
                # Show top prediction
                top_pred = fresh_analysis["fresh_predictions"][0]
                response_message += f"🎯 {top_pred['market']}: `{top_pred['prediction']}` ({top_pred['confidence']}%)\n\n"
        
        if analysis_count == 0:
            response_message += "⏳ No fresh analysis opportunities found.\n"
        
        response_message += f"🔍 Analyzed {len(matches)} live matches"
        
        bot.reply_to(message, response_message, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Analysis error: {str(e)}")

@bot.message_handler(commands=['matches'])
def list_current_matches(message):
    """List current live matches"""
    try:
        matches = get_current_matches()
        
        if not matches:
            bot.reply_to(message, "⏳ No live matches currently.")
            return
        
        matches_msg = f"🔴 **CURRENT LIVE MATCHES**\n\n"
        matches_msg += f"Total: {len(matches)} matches\n\n"
        
        for i, match in enumerate(matches[:6], 1):
            home = match.get('match_hometeam_name', 'Unknown')
            away = match.get('match_awayteam_name', 'Unknown')
            score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
            league = match.get('league_name', 'Unknown')
            time_display = match.get('match_time', 'NS')
            
            matches_msg += f"{i}. **{home}** {score} **{away}**\n"
            matches_msg += f"   🏆 {league} | ⏱️ {time_display}\n\n"
        
        matches_msg += "Use `/analyze` for fresh predictions!"
        bot.reply_to(message, matches_msg, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['status'])
def send_status(message):
    try:
        matches = get_current_matches()
        
        status_msg = f"""
🤖 **REAL-TIME PREDICTION UPDATER**

✅ System Status: ACTIVE
🕐 Last Cycle: {datetime.now().strftime('%H:%M:%S')}
⏰ Analysis Interval: 5 minutes
🎯 Confidence Threshold: 80%+
🔴 Live Matches: {len(matches)}

**Features:**
• Fresh Analysis: ✅
• Real-time Updates: ✅
• Current Situation: ✅
• Auto Cycles: ✅

**Next Analysis Cycle:** 5 minutes
"""
        bot.reply_to(message, status_msg, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Status error: {str(e)}")

# -------------------------
# FLASK WEBHOOK
# -------------------------
@app.route('/')
def home():
    return "🤖 Real-Time Prediction Updater - Fresh Analysis Every 5 Minutes"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return 'ERROR', 400

def setup_bot():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
        print(f"✅ Webhook set: {DOMAIN}/{BOT_TOKEN}")

        # Start real-time auto updater
        t = threading.Thread(target=realtime_auto_updater, daemon=True)
        t.start()
        print("✅ Real-time auto updater started!")

        startup_msg = f"""
🤖 **REAL-TIME PREDICTION UPDATER STARTED!**

🔄 **FRESH ANALYSIS EVERY 5 MINUTES**
• Completely new predictions each cycle
• Based on current match situation
• Real-time score analysis
• Fresh insights and trends

✅ **System actively analyzing matches!**
⏰ **First analysis cycle in 1 minute...**

🎯 **Ready to deliver fresh predictions!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Bot setup error: {e}")
        bot.polling(none_stop=True)

if __name__ == '__main__':
    print("🚀 Starting Real-Time Prediction Updater...")
    setup_bot()
    app.run(host='0.0.0.0', port=PORT)
