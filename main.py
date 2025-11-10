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

print("🎯 Starting LIVE PREDICTION UPDATER Bot...")

# -------------------------
# PREDICTION HISTORY TRACKER
# -------------------------
class PredictionTracker:
    def __init__(self):
        self.prediction_history = {}
        self.last_prediction_time = {}
        
    def should_send_new_prediction(self, match_id, current_time):
        """Check if we should send NEW prediction for this match"""
        last_time = self.last_prediction_time.get(match_id, 0)
        return current_time - last_time >= 300  # 5 minutes
    
    def store_prediction(self, match_id, prediction_data):
        """Store current prediction for comparison"""
        self.prediction_history[match_id] = {
            'prediction': prediction_data,
            'timestamp': time.time(),
            'home_score': prediction_data.get('current_home_score', 0),
            'away_score': prediction_data.get('current_away_score', 0),
            'minute': prediction_data.get('current_minute', 0)
        }
        
    def get_previous_prediction(self, match_id):
        """Get previous prediction for this match"""
        return self.prediction_history.get(match_id)
    
    def has_match_situation_changed(self, match_id, current_home_score, current_away_score, current_minute):
        """Check if match situation has changed significantly"""
        previous = self.get_previous_prediction(match_id)
        if not previous:
            return True
            
        # Check for significant changes
        if (previous['home_score'] != current_home_score or 
            previous['away_score'] != current_away_score or
            previous['minute'] != current_minute):
            return True
            
        return False

# Initialize tracker
prediction_tracker = PredictionTracker()

# -------------------------
# LIVE MATCHES FETCHING
# -------------------------
def fetch_live_matches_apifootball():
    """Fetch live matches from API-FOOTBALL.COM"""
    try:
        print("🔄 Fetching live matches from API-FOOTBALL.COM...")
        
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # API-FOOTBALL.COM endpoint
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data and isinstance(data, list):
                # Filter live matches
                live_matches = [match for match in data if match.get("match_live") == "1"]
                
                print(f"✅ Found {len(live_matches)} live matches from API-FOOTBALL")
                return live_matches
            else:
                print("⏳ No data in API response")
                return []
        else:
            print(f"❌ API Error {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ API-FOOTBALL fetch error: {e}")
        return []

def process_apifootball_match(match):
    """Process API-FOOTBALL match data into standardized format"""
    try:
        # Extract match data safely
        match_id = match.get("match_id", "unknown")
        home_team = match.get("match_hometeam_name", "Home Team")
        away_team = match.get("match_awayteam_name", "Away Team")
        home_score = match.get("match_hometeam_score", "0")
        away_score = match.get("match_awayteam_score", "0")
        league = match.get("league_name", "Unknown League")
        country = match.get("country_name", "")
        match_time = match.get("match_time", "")
        match_status = match.get("match_status", "")
        
        # Convert match status to our format
        if match_status.isdigit():  # Like "29", "70", etc.
            status = "LIVE"
            time_display = f"{match_status}'"
            current_minute = int(match_status)
        elif match_status == "Half Time":
            status = "HT"
            time_display = "HT"
            current_minute = 45
        elif match_status == "":
            status = "NS"
            time_display = "NS"
            current_minute = 0
        else:
            status = match_status
            time_display = match_status
            current_minute = 0
        
        # Determine if match is live
        is_live = match.get("match_live") == "1"
        
        processed_match = {
            "match_id": match_id,
            "match_hometeam_name": home_team,
            "match_awayteam_name": away_team,
            "match_hometeam_score": home_score if home_score != "" else "0",
            "match_awayteam_score": away_score if away_score != "" else "0",
            "league_name": league,
            "league_country": country,
            "match_time": time_display,
            "match_live": "1" if is_live else "0",
            "match_status": status,
            "match_date": match.get("match_date", ""),
            "current_minute": current_minute,
            "teams": {
                "home": {
                    "id": match.get("match_hometeam_id", ""),
                    "name": home_team
                },
                "away": {
                    "id": match.get("match_awayteam_id", ""),
                    "name": away_team
                }
            },
            "statistics": match.get("statistics", []),
            "goalscorer": match.get("goalscorer", []),
            "cards": match.get("cards", [])
        }
        
        return processed_match
        
    except Exception as e:
        print(f"⚠️ Error processing match {match.get('match_id')}: {e}")
        return None

def fetch_all_live_matches():
    """Fetch and process all LIVE matches"""
    try:
        print("🎯 Fetching LIVE matches for NEW predictions...")
        
        raw_matches = fetch_live_matches_apifootball()
        
        if not raw_matches:
            print("⏳ No live matches found")
            return []
        
        # Process all matches
        processed_matches = []
        for match in raw_matches:
            processed_match = process_apifootball_match(match)
            if processed_match and processed_match['match_live'] == '1':
                processed_matches.append(processed_match)
        
        print(f"✅ Processed {len(processed_matches)} LIVE matches for predictions")
        return processed_matches
            
    except Exception as e:
        print(f"❌ Live match fetching error: {e}")
        return []

# -------------------------
# ADVANCED PREDICTION ENGINE
# -------------------------
class LivePredictionEngine:
    def __init__(self):
        self.confidence_threshold = 75
        
    def generate_new_predictions(self, match):
        """Generate NEW predictions based on current match situation"""
        try:
            home_team = match.get("match_hometeam_name", "Home")
            away_team = match.get("match_awayteam_name", "Away")
            home_score = int(match.get("match_hometeam_score", 0))
            away_score = int(match.get("match_awayteam_score", 0))
            minute = match.get("current_minute", 0)
            status = match.get("match_status", "")
            statistics = match.get("statistics", [])
            
            print(f"  🎯 Generating NEW predictions for: {home_team} vs {away_team}")
            
            # Extract current match stats
            current_stats = self.extract_current_stats(statistics, home_score, away_score, minute)
            
            # Generate fresh predictions
            predictions = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "match_info": {
                    "home_team": home_team,
                    "away_team": away_team,
                    "current_score": f"{home_score}-{away_score}",
                    "current_minute": minute,
                    "match_status": status
                },
                "market_predictions": self.generate_market_predictions(home_score, away_score, minute, current_stats),
                "confidence_analysis": self.analyze_confidence(home_score, away_score, minute, current_stats),
                "risk_assessment": self.assess_risk(home_score, away_score, minute),
                "expected_events": self.predict_future_events(home_score, away_score, minute, current_stats)
            }
            
            return predictions
            
        except Exception as e:
            print(f"❌ Prediction generation error: {e}")
            return self.get_default_predictions(match)

    def extract_current_stats(self, statistics, home_score, away_score, minute):
        """Extract current match statistics"""
        stats = {
            "home_possession": 50,
            "away_possession": 50,
            "home_attacks": 0,
            "away_attacks": 0,
            "home_dangerous_attacks": 0,
            "away_dangerous_attacks": 0,
            "home_shots_on_target": 0,
            "away_shots_on_target": 0,
            "home_corners": 0,
            "away_corners": 0,
            "home_fouls": 0,
            "away_fouls": 0,
            "home_yellow_cards": 0,
            "away_yellow_cards": 0
        }
        
        try:
            for stat in statistics:
                stat_type = stat.get("type", "")
                home_val = stat.get("home", "0")
                away_val = stat.get("away", "0")
                
                if stat_type == "Ball Possession":
                    stats["home_possession"] = int(home_val.replace('%', '')) if home_val and '%' in home_val else 50
                    stats["away_possession"] = int(away_val.replace('%', '')) if away_val and '%' in away_val else 50
                elif stat_type == "Attacks":
                    stats["home_attacks"] = int(home_val) if home_val else 0
                    stats["away_attacks"] = int(away_val) if away_val else 0
                elif stat_type == "Dangerous Attacks":
                    stats["home_dangerous_attacks"] = int(home_val) if home_val else 0
                    stats["away_dangerous_attacks"] = int(away_val) if away_val else 0
                elif stat_type == "On Target":
                    stats["home_shots_on_target"] = int(home_val) if home_val else 0
                    stats["away_shots_on_target"] = int(away_val) if away_val else 0
                elif stat_type == "Corners":
                    stats["home_corners"] = int(home_val) if home_val else 0
                    stats["away_corners"] = int(away_val) if away_val else 0
                elif stat_type == "Fouls":
                    stats["home_fouls"] = int(home_val) if home_val else 0
                    stats["away_fouls"] = int(away_val) if away_val else 0
                    
        except Exception as e:
            print(f"⚠️ Stats extraction error: {e}")
            
        return stats

    def generate_market_predictions(self, home_score, away_score, minute, stats):
        """Generate NEW predictions for all markets"""
        goal_diff = home_score - away_score
        total_goals = home_score + away_score
        time_remaining = 90 - minute
        
        # Calculate match momentum
        momentum = self.calculate_momentum(home_score, away_score, minute, stats)
        
        # 1. MATCH RESULT PREDICTION
        result_prediction = self.predict_match_result(home_score, away_score, minute, stats, momentum)
        
        # 2. OVER/UNDER PREDICTIONS
        over_under = self.predict_over_under(total_goals, minute, stats, momentum)
        
        # 3. BTTS PREDICTION
        btts_prediction = self.predict_btts(home_score, away_score, minute, stats)
        
        # 4. NEXT GOAL PREDICTION
        next_goal = self.predict_next_goal(home_score, away_score, minute, stats, momentum)
        
        # 5. CORRECT SCORE PREDICTION
        correct_score = self.predict_correct_score(home_score, away_score, minute, stats)
        
        # 6. GOAL TIMING PREDICTION
        goal_timing = self.predict_goal_timing(minute, stats, momentum)
        
        return {
            "match_result": result_prediction,
            "over_under": over_under,
            "both_teams_score": btts_prediction,
            "next_goal": next_goal,
            "correct_score": correct_score,
            "goal_timing": goal_timing
        }

    def calculate_momentum(self, home_score, away_score, minute, stats):
        """Calculate current match momentum"""
        goal_diff = home_score - away_score
        time_factor = minute / 90.0
        
        # Base momentum from score
        if goal_diff > 0:
            base_momentum = 70 + (goal_diff * 10)
        elif goal_diff < 0:
            base_momentum = 30 - (abs(goal_diff) * 10)
        else:
            base_momentum = 50
            
        # Adjust with statistics
        possession_factor = (stats["home_possession"] - 50) * 0.5
        attack_factor = (stats["home_dangerous_attacks"] - stats["away_dangerous_attacks"]) * 0.1
        shots_factor = (stats["home_shots_on_target"] - stats["away_shots_on_target"]) * 2
        
        total_momentum = base_momentum + possession_factor + attack_factor + shots_factor
        return max(10, min(90, total_momentum))

    def predict_match_result(self, home_score, away_score, minute, stats, momentum):
        """Predict match result based on current situation"""
        goal_diff = home_score - away_score
        time_factor = minute / 90.0
        
        if goal_diff > 0:
            # Home leading
            home_win = 60 + (goal_diff * 8) + (time_factor * 10) + (momentum - 50) * 0.3
            draw = 25 - (goal_diff * 3)
            away_win = 15 - (goal_diff * 5)
        elif goal_diff < 0:
            # Away leading
            away_win = 60 + (abs(goal_diff) * 8) + (time_factor * 10) + ((100 - momentum) - 50) * 0.3
            draw = 25 - (abs(goal_diff) * 3)
            home_win = 15 - (abs(goal_diff) * 5)
        else:
            # Draw
            home_win = 40 + (momentum - 50) * 0.4
            away_win = 35 + ((100 - momentum) - 50) * 0.4
            draw = 25
            
        # Normalize to 100%
        total = home_win + away_win + draw
        home_win = (home_win / total) * 100
        away_win = (away_win / total) * 100
        draw = (draw / total) * 100
        
        confidence = self.calculate_prediction_confidence(goal_diff, minute, stats)
        
        return {
            "market": "Match Result",
            "predictions": [
                {"outcome": "Home Win", "probability": round(home_win, 1), "trend": "📈" if home_win > 50 else "📉"},
                {"outcome": "Draw", "probability": round(draw, 1), "trend": "➡️" if abs(draw-33) < 10 else "📉"},
                {"outcome": "Away Win", "probability": round(away_win, 1), "trend": "📈" if away_win > 40 else "📉"}
            ],
            "recommended": "Home Win" if home_win > away_win and home_win > draw else "Away Win" if away_win > draw else "Draw",
            "confidence": confidence,
            "reasoning": self.get_result_reasoning(home_score, away_score, minute, goal_diff)
        }

    def predict_over_under(self, total_goals, minute, stats, momentum):
        """Predict Over/Under markets"""
        goals_per_minute = total_goals / max(minute, 1)
        time_remaining = 90 - minute
        
        # Calculate expected additional goals
        if minute > 0:
            expected_additional = goals_per_minute * time_remaining * 1.2
        else:
            expected_additional = 2.5
            
        total_expected = total_goals + expected_additional
        
        # Generate predictions for different lines
        lines = [0.5, 1.5, 2.5, 3.5]
        predictions = []
        
        for line in lines:
            if total_expected > line:
                probability = min(95, 50 + (total_expected - line) * 25)
                recommendation = "Over"
            else:
                probability = min(95, 50 + (line - total_expected) * 25)
                recommendation = "Under"
                
            confidence = min(90, int(probability * 0.8))
            predictions.append({
                "line": line,
                "recommendation": recommendation,
                "probability": round(probability, 1),
                "confidence": confidence
            })
        
        return {
            "market": "Over/Under Goals",
            "predictions": predictions,
            "expected_total_goals": round(total_expected, 1),
            "top_pick": f"{predictions[0]['recommendation']} {predictions[0]['line']}",
            "confidence": predictions[0]['confidence']
        }

    def predict_btts(self, home_score, away_score, minute, stats):
        """Predict Both Teams to Score"""
        if home_score > 0 and away_score > 0:
            # Both already scored
            btts_yes = 90
            reasoning = "Both teams have already scored"
        elif home_score > 0 or away_score > 0:
            # One team scored
            if minute >= 75:
                btts_yes = 30
                reasoning = "Late in match, low chance for other team to score"
            else:
                btts_yes = 65
                reasoning = "One team scored, other team likely to respond"
        else:
            # No goals yet
            if minute >= 60:
                btts_yes = 25
                reasoning = "Late in match with no goals"
            else:
                btts_yes = 55
                reasoning = "Early match, both teams likely to score"
                
        btts_no = 100 - btts_yes
        confidence = min(85, 70 + (minute / 90.0) * 15)
        
        return {
            "market": "Both Teams to Score",
            "predictions": [
                {"outcome": "Yes", "probability": btts_yes, "confidence": confidence},
                {"outcome": "No", "probability": btts_no, "confidence": confidence}
            ],
            "recommended": "Yes" if btts_yes > btts_no else "No",
            "confidence": confidence,
            "reasoning": reasoning
        }

    def predict_next_goal(self, home_score, away_score, minute, stats, momentum):
        """Predict next goal scorer"""
        goal_diff = home_score - away_score
        
        # Base probabilities from momentum
        home_next = momentum * 0.8
        away_next = (100 - momentum) * 0.8
        no_goal = 100 - home_next - away_next
        
        # Adjust based on match situation
        if goal_diff > 0:
            # Home leading - away might push for equalizer
            away_next += 10
        elif goal_diff < 0:
            # Away leading - home might push for equalizer
            home_next += 10
            
        # Normalize
        total = home_next + away_next + no_goal
        home_next = (home_next / total) * 100
        away_next = (away_next / total) * 100
        no_goal = (no_goal / total) * 100
        
        confidence = min(80, 60 + (minute / 90.0) * 20)
        
        return {
            "market": "Next Goal",
            "predictions": [
                {"outcome": "Home Team", "probability": round(home_next, 1), "confidence": confidence},
                {"outcome": "Away Team", "probability": round(away_next, 1), "confidence": confidence},
                {"outcome": "No Goal", "probability": round(no_goal, 1), "confidence": confidence-10}
            ],
            "recommended": "Home Team" if home_next > away_next and home_next > no_goal else "Away Team" if away_next > no_goal else "No Goal",
            "confidence": confidence
        }

    def predict_correct_score(self, home_score, away_score, minute, stats):
        """Predict likely final score"""
        goal_diff = home_score - away_score
        total_goals = home_score + away_score
        
        # Generate likely scorelines based on current state
        if goal_diff > 0:
            if goal_diff >= 2:
                # Home comfortable lead
                scores = [
                    f"{home_score+1}-{away_score}", 
                    f"{home_score}-{away_score}", 
                    f"{home_score+1}-{away_score+1}",
                    f"{home_score+2}-{away_score}"
                ]
            else:
                # Home narrow lead
                scores = [
                    f"{home_score+1}-{away_score}", 
                    f"{home_score}-{away_score}", 
                    f"{home_score}-{away_score+1}",
                    f"{home_score+1}-{away_score+1}"
                ]
        elif goal_diff < 0:
            if abs(goal_diff) >= 2:
                # Away comfortable lead
                scores = [
                    f"{home_score}-{away_score+1}", 
                    f"{home_score}-{away_score}", 
                    f"{home_score+1}-{away_score+1}",
                    f"{home_score}-{away_score+2}"
                ]
            else:
                # Away narrow lead
                scores = [
                    f"{home_score}-{away_score+1}", 
                    f"{home_score}-{away_score}", 
                    f"{home_score+1}-{away_score}",
                    f"{home_score+1}-{away_score+1}"
                ]
        else:
            # Draw
            scores = [
                f"{home_score+1}-{away_score}", 
                f"{home_score}-{away_score+1}", 
                f"{home_score+1}-{away_score+1}",
                f"{home_score}-{away_score}"
            ]
        
        confidence = min(75, 50 + (minute / 90.0) * 25)
        
        predictions = []
        for i, score in enumerate(scores[:4]):  # Top 4 predictions
            prob = max(10, 40 - (i * 10))
            predictions.append({
                "score": score,
                "probability": prob,
                "confidence": confidence - (i * 5)
            })
        
        return {
            "market": "Correct Score",
            "predictions": predictions,
            "recommended": predictions[0]['score'],
            "confidence": predictions[0]['confidence']
        }

    def predict_goal_timing(self, minute, stats, momentum):
        """Predict when next goals might come"""
        current_minute = minute
        time_remaining = 90 - current_minute
        
        # Generate likely goal minutes
        if current_minute < 45:
            # First half
            minutes = [
                current_minute + 5, 
                current_minute + 15, 
                current_minute + 25,
                45,  # Just before halftime
                min(90, current_minute + 35)
            ]
        else:
            # Second half
            minutes = [
                current_minute + 5,
                current_minute + 10,
                current_minute + 15,
                min(90, current_minute + 20),
                min(90, current_minute + 25)
            ]
        
        # Remove duplicates and sort
        minutes = sorted(list(set(minutes)))
        confidence = min(80, 60 + (stats["home_dangerous_attacks"] + stats["away_dangerous_attacks"]) / 10)
        
        predictions = []
        for i, minute in enumerate(minutes[:5]):  # Top 5 minutes
            prob = max(15, 35 - (i * 5))
            predictions.append({
                "minute": minute,
                "probability": prob,
                "confidence": confidence - (i * 5)
            })
        
        return {
            "market": "Goal Timing",
            "predictions": predictions,
            "recommended": f"{predictions[0]['minute']}'",
            "confidence": predictions[0]['confidence']
        }

    def calculate_prediction_confidence(self, goal_diff, minute, stats):
        """Calculate confidence for predictions"""
        confidence_factors = []
        
        # Goal difference factor
        if abs(goal_diff) >= 3:
            confidence_factors.append(90)
        elif abs(goal_diff) == 2:
            confidence_factors.append(80)
        elif abs(goal_diff) == 1:
            confidence_factors.append(70)
        else:
            confidence_factors.append(60)
            
        # Time factor
        if minute >= 75:
            confidence_factors.append(85)
        elif minute >= 60:
            confidence_factors.append(75)
        elif minute >= 30:
            confidence_factors.append(65)
        else:
            confidence_factors.append(55)
            
        return min(95, sum(confidence_factors) // len(confidence_factors))

    def analyze_confidence(self, home_score, away_score, minute, stats):
        """Analyze overall prediction confidence"""
        goal_diff = home_score - away_score
        
        factors = {
            "match_progress": f"{minute} minutes played",
            "score_stability": "High" if abs(goal_diff) >= 2 else "Medium" if abs(goal_diff) == 1 else "Low",
            "momentum_indicator": "Clear" if abs(goal_diff) >= 2 else "Balanced",
            "data_quality": "Good" if stats["home_dangerous_attacks"] + stats["away_dangerous_attacks"] > 20 else "Average"
        }
        
        overall_confidence = self.calculate_prediction_confidence(goal_diff, minute, stats)
        
        return {
            "overall_confidence": overall_confidence,
            "factors": factors,
            "risk_level": "Low" if overall_confidence >= 80 else "Medium" if overall_confidence >= 65 else "High"
        }

    def assess_risk(self, home_score, away_score, minute):
        """Assess risk level for predictions"""
        goal_diff = abs(home_score - away_score)
        
        if goal_diff >= 3:
            return "🟢 LOW RISK - Clear match direction"
        elif goal_diff == 2:
            return "🟡 MEDIUM RISK - Comfortable lead"
        elif goal_diff == 1:
            return "🟠 MODERATE RISK - Close match"
        else:
            return "🔴 HIGH RISK - Unpredictable"

    def predict_future_events(self, home_score, away_score, minute, stats):
        """Predict future match events"""
        predictions = []
        
        # Goal predictions
        if minute < 80:
            predictions.append(f"Expect 1-2 more goals before full time")
        
        # Card predictions
        total_fouls = stats["home_fouls"] + stats["away_fouls"]
        if total_fouls > 15:
            predictions.append(f"High foul count - possible yellow cards")
            
        # Momentum predictions
        goal_diff = home_score - away_score
        if goal_diff == 0 and minute > 60:
            predictions.append(f"Late equalizer possible")
        elif abs(goal_diff) == 1 and minute > 75:
            predictions.append(f"Late goal expected from trailing team")
            
        return predictions

    def get_result_reasoning(self, home_score, away_score, minute, goal_diff):
        """Get reasoning for match result prediction"""
        if goal_diff > 0:
            if minute >= 75:
                return f"Home team leading {goal_diff}-0 with {90-minute} minutes left - high probability to maintain lead"
            else:
                return f"Home team leading but {90-minute} minutes remaining - match still open"
        elif goal_diff < 0:
            if minute >= 75:
                return f"Away team leading {abs(goal_diff)}-0 with {90-minute} minutes left - high probability to maintain lead"
            else:
                return f"Away team leading but {90-minute} minutes remaining - match still open"
        else:
            return f"Match evenly poised at {home_score}-{away_score} - next goal crucial"

    def get_default_predictions(self, match):
        """Return default predictions if analysis fails"""
        return {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "match_info": {
                "home_team": match.get("match_hometeam_name", "Home"),
                "away_team": match.get("match_awayteam_name", "Away"),
                "current_score": "0-0",
                "current_minute": 0,
                "match_status": "Unknown"
            },
            "market_predictions": {},
            "confidence_analysis": {"overall_confidence": 0, "risk_level": "High"},
            "risk_assessment": "🔴 HIGH RISK - Analysis failed",
            "expected_events": ["System temporarily unavailable"]
        }

# Initialize prediction engine
prediction_engine = LivePredictionEngine()

# -------------------------
# NEW PREDICTION MESSAGE GENERATOR
# -------------------------
def generate_new_prediction_message(match, previous_prediction=None):
    """Generate NEW prediction message with fresh analysis"""
    try:
        home = match.get("match_hometeam_name", "Home Team")
        away = match.get("match_awayteam_name", "Away Team")
        home_score = match.get("match_hometeam_score", "0")
        away_score = match.get("match_awayteam_score", "0")
        league = match.get("league_name", "Unknown League")
        country = match.get("league_country", "")
        match_time = match.get("match_time", "NS")
        status = match.get("match_status", "NS")
        
        # Generate NEW predictions
        new_predictions = prediction_engine.generate_new_predictions(match)
        
        # Generate message
        message = f"🔄 **NEW PREDICTION UPDATE**\n"
        message += f"⏰ {new_predictions['timestamp']}\n\n"
        
        message += f"⚽ **{home} vs {away}**\n"
        if country:
            message += f"🏆 {country} - {league}\n"
        else:
            message += f"🏆 {league}\n"
            
        message += f"⏱️ {match_time} | 🔴 {status}\n"
        message += f"📊 **Current Score: {home_score}-{away_score}**\n\n"
        
        # Show changes from previous prediction if available
        if previous_prediction:
            message += f"📈 **SINCE LAST UPDATE:**\n"
            old_score = previous_prediction.get('home_score', 0) + "-" + previous_prediction.get('away_score', 0)
            if f"{home_score}-{away_score}" != old_score:
                message += f"• Score changed: {old_score} → {home_score}-{away_score}\n"
            if match_time != previous_prediction.get('minute', 'NS'):
                message += f"• Time progressed: {previous_prediction.get('minute', 'NS')} → {match_time}\n"
            message += "\n"
        
        message += "🎯 **FRESH PREDICTIONS**\n\n"
        
        # Add each market prediction
        markets = new_predictions['market_predictions']
        for market_name, market_data in markets.items():
            if market_data.get('confidence', 0) >= prediction_engine.confidence_threshold:
                message += f"**{market_data['market']}**\n"
                message += f"✅ Recommended: `{market_data['recommended']}`\n"
                message += f"🎯 Confidence: `{market_data['confidence']}%`\n"
                
                # Show top predictions
                for pred in market_data.get('predictions', [])[:2]:
                    if pred.get('probability', 0) > 20:
                        message += f"• `{pred['outcome']}`: {pred['probability']}%"
                        if pred.get('trend'):
                            message += f" {pred['trend']}"
                        message += "\n"
                
                if market_data.get('reasoning'):
                    message += f"💡 {market_data['reasoning']}\n"
                    
                message += "\n"
        
        # Add confidence analysis
        confidence_data = new_predictions['confidence_analysis']
        message += f"📊 **CONFIDENCE ANALYSIS**\n"
        message += f"• Overall Confidence: `{confidence_data['overall_confidence']}%`\n"
        message += f"• Risk Level: {confidence_data['risk_level']}\n"
        
        for factor, value in confidence_data.get('factors', {}).items():
            message += f"• {factor.replace('_', ' ').title()}: `{value}`\n"
        
        message += f"\n⚠️ **{new_predictions['risk_assessment']}**\n"
        
        # Add expected events
        events = new_predictions.get('expected_events', [])
        if events:
            message += f"\n🔮 **EXPECTED EVENTS:**\n"
            for event in events[:3]:
                message += f"• {event}\n"
        
        message += f"\n⏰ **Next prediction update in 5 minutes...**\n"
        message += "🎯 *Based on current match situation*"

        return message
        
    except Exception as e:
        print(f"❌ Prediction message generation error: {e}")
        return f"❌ Error generating NEW predictions for {match.get('match_hometeam_name')} vs {match.get('match_awayteam_name')}"

# -------------------------
# AUTO PREDICTION UPDATER - EVERY 5 MINUTES
# -------------------------
def prediction_updater():
    """Auto-update system that sends NEW predictions every 5 minutes"""
    while True:
        try:
            current_time = time.time()
            print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] Generating NEW predictions...")
            
            matches = fetch_all_live_matches()
            
            if matches:
                print(f"📊 Generating NEW predictions for {len(matches)} LIVE matches...")
                
                predictions_sent = 0
                
                for i, match in enumerate(matches, 1):
                    try:
                        match_id = match.get('match_id', f"match_{i}")
                        home = match.get('match_hometeam_name', 'Unknown')
                        away = match.get('match_awayteam_name', 'Unknown')
                        home_score = int(match.get("match_hometeam_score", 0))
                        away_score = int(match.get("match_awayteam_score", 0))
                        minute = match.get('current_minute', 0)
                        
                        print(f"  {i}/{len(matches)}: {home} vs {away} | {home_score}-{away_score} | {minute}'")
                        
                        # Check if we should send NEW prediction for this match
                        if prediction_tracker.should_send_new_prediction(match_id, current_time):
                            # Get previous prediction for comparison
                            previous_prediction = prediction_tracker.get_previous_prediction(match_id)
                            
                            # Generate NEW prediction message
                            prediction_msg = generate_new_prediction_message(match, previous_prediction)
                            
                            if prediction_msg:
                                try:
                                    bot.send_message(OWNER_CHAT_ID, prediction_msg, parse_mode='Markdown')
                                    predictions_sent += 1
                                    
                                    # Store this prediction
                                    prediction_data = {
                                        'current_home_score': home_score,
                                        'current_away_score': away_score,
                                        'current_minute': minute,
                                        'timestamp': current_time
                                    }
                                    prediction_tracker.store_prediction(match_id, prediction_data)
                                    prediction_tracker.last_prediction_time[match_id] = current_time
                                    
                                    print(f"    ✅ NEW PREDICTION SENT: {home} vs {away}")
                                    time.sleep(3)  # Rate limiting
                                except Exception as e:
                                    print(f"    ❌ Send failed: {e}")
                        else:
                            print(f"    ⏳ Prediction update not due yet")
                            
                    except Exception as e:
                        print(f"    ❌ Match {i} prediction error: {e}")
                        continue
                
                # Send summary
                if predictions_sent > 0:
                    summary_msg = f"""
📊 **PREDICTION UPDATE SUMMARY**

⏰ Time: {datetime.now().strftime('%H:%M:%S')}
🔍 Matches Analyzed: {len(matches)}
🎯 New Predictions Sent: {predictions_sent}

✅ Fresh predictions delivered!
⏳ Next prediction cycle in 5 minutes...
"""
                    try:
                        bot.send_message(OWNER_CHAT_ID, summary_msg, parse_mode='Markdown')
                        print(f"📊 Summary sent: {predictions_sent} NEW predictions delivered")
                    except Exception as e:
                        print(f"❌ Summary send failed: {e}")
                else:
                    print("📊 No new predictions sent this cycle")
                    
            else:
                print("⏳ No live matches available for predictions")
                # Send status update
                status_msg = "🔍 **PREDICTION SYSTEM**\n\nNo live matches currently available for predictions.\n\nNext check in 5 minutes..."
                try:
                    bot.send_message(OWNER_CHAT_ID, status_msg, parse_mode='Markdown')
                except Exception as e:
                    print(f"❌ Status message failed: {e}")
                
        except Exception as e:
            print(f"❌ Prediction updater system error: {e}")
        
        print("💤 Waiting 5 minutes for next prediction cycle...")
        time.sleep(300)  # 5 minutes

# -------------------------
# TELEGRAM COMMANDS
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_help(message):
    help_text = """
🤖 **LIVE PREDICTION UPDATER BOT**

🔄 **NEW PREDICTIONS EVERY 5 MINUTES!**
• Fresh predictions based on current match situation
• Real-time probability updates  
• Multiple betting markets covered
• Match insights and trend analysis

📊 **Prediction Markets:**
• Match Result (1X2)
• Over/Under Goals
• Both Teams to Score  
• Next Goal Scorer
• Correct Score
• Goal Timing

⚡ **Commands:**
• `/predict` - Get current predictions
• `/matches` - List live matches
• `/status` - System status

🎯 **System generates NEW predictions every 5 minutes!**
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['predict'])
def send_current_predictions(message):
    """Send current predictions for live matches"""
    try:
        matches = fetch_all_live_matches()
        if matches:
            prediction_msg = f"🎯 **CURRENT LIVE PREDICTIONS**\n\n"
            prediction_msg += f"Live Matches: {len(matches)}\n\n"
            
            for i, match in enumerate(matches[:3], 1):  # Show predictions for first 3 matches
                home = match.get('match_hometeam_name', 'Unknown')
                away = match.get('match_awayteam_name', 'Unknown')
                score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                
                # Generate quick prediction
                predictions = prediction_engine.generate_new_predictions(match)
                market_data = predictions['market_predictions'].get('match_result', {})
                recommended = market_data.get('recommended', 'Analyzing...')
                confidence = market_data.get('confidence', 0)
                
                prediction_msg += f"{i}. **{home}** {score} **{away}**\n"
                prediction_msg += f"   🎯 Prediction: `{recommended}` (Conf: `{confidence}%`)\n\n"
            
            prediction_msg += "🔄 Auto-predictions running every 5 minutes..."
            bot.reply_to(message, prediction_msg, parse_mode='Markdown')
        else:
            bot.reply_to(message, "⏳ No live matches currently. System is monitoring...")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['matches'])
def list_matches(message):
    """List current live matches"""
    try:
        matches = fetch_all_live_matches()
        
        matches_msg = f"🔴 **CURRENT LIVE MATCHES**\n\n"
        matches_msg += f"Total Live Matches: {len(matches)}\n\n"
        
        for i, match in enumerate(matches, 1):
            home = match.get('match_hometeam_name', 'Unknown')
            away = match.get('match_awayteam_name', 'Unknown')
            score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
            league = match.get('league_name', 'Unknown')
            time_display = match.get('match_time', 'NS')
            
            matches_msg += f"{i}. **{home}** {score} **{away}**\n"
            matches_msg += f"   🏆 {league} | ⏱️ {time_display}\n\n"
        
        matches_msg += "Use `/predict` to get current predictions!"
        bot.reply_to(message, matches_msg, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['status'])
def send_status(message):
    try:
        matches = fetch_all_live_matches()
        
        status_msg = f"""
🤖 **LIVE PREDICTION SYSTEM STATUS**

✅ Online & Predicting
🕐 Last Update: {datetime.now().strftime('%H:%M:%S')}
⏰ Prediction Interval: 5 minutes
🔴 Live Matches: {len(matches)}

**Features:**
• Fresh Predictions: ✅
• Real-time Analysis: ✅  
• Multiple Markets: ✅
• Auto-updates: ✅

**Next Prediction Cycle:** 5 minutes
"""
        bot.reply_to(message, status_msg, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Status error: {str(e)}")

# -------------------------
# FLASK WEBHOOK
# -------------------------
@app.route('/')
def home():
    return "🤖 Live Prediction Updater Bot - New Predictions Every 5 Minutes"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.Types.Update.de_json(request.get_json())
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

        # Start prediction updater
        t = threading.Thread(target=prediction_updater, daemon=True)
        t.start()
        print("✅ Live prediction updater started!")

        startup_msg = f"""
🤖 **LIVE PREDICTION UPDATER STARTED!**

🔄 **NEW PREDICTIONS EVERY 5 MINUTES**
• Fresh analysis based on current match situation
• Real-time probability updates
• Multiple betting markets
• Confidence scoring

🎯 **Now generating NEW predictions every 5 minutes!**
⏰ **First predictions in 1 minute...**

⚡ **Ready to deliver fresh predictions!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Bot setup error: {e}")
        bot.polling(none_stop=True)

if __name__ == '__main__':
    print("🚀 Starting Live Prediction Updater Bot...")
    setup_bot()
    app.run(host='0.0.0.0', port=PORT)
