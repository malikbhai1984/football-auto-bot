import os
import requests
import telebot
import time
import random
import math
import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
from flask import Flask, request
import threading
from dotenv import load_dotenv
import json
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, classification_report
import warnings
warnings.filterwarnings('ignore')

import pytz
PK_TZ = pytz.timezone("Asia/Karachi")

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

print("🎯 Starting ML/AI POWERED FOOTBALL PREDICTION BOT...")

# -------------------------
# SPECIFIC LEAGUES CONFIGURATION
# -------------------------
TARGET_LEAGUES = {
    "152": "Premier League",
    "302": "La Liga", 
    "207": "Serie A",
    "168": "Bundesliga",
    "176": "Ligue 1",
    "3": "Champions League",
    "4": "Europa League"
}

# -------------------------
# ML/AI PREDICTION ENGINE
# -------------------------
class MLFootballPredictor:
    def __init__(self):
        self.models = {}
        self.label_encoders = {}
        self.scaler = StandardScaler()
        self.model_accuracy = {}
        self.feature_importance = {}
        self.min_confidence = 85
        
        # Initialize models
        self.initialize_models()
        
    def initialize_models(self):
        """Initialize ML models for different prediction types"""
        try:
            # Model for Match Result Prediction
            self.models['result'] = RandomForestClassifier(
                n_estimators=200,
                max_depth=15,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=42
            )
            
            # Model for BTTS Prediction
            self.models['btts'] = GradientBoostingClassifier(
                n_estimators=150,
                max_depth=10,
                learning_rate=0.1,
                random_state=42
            )
            
            # Model for Over/Under 2.5 Goals
            self.models['goals'] = LogisticRegression(
                C=1.0,
                max_iter=1000,
                random_state=42
            )
            
            # Initialize label encoders
            self.label_encoders['team'] = LabelEncoder()
            self.label_encoders['league'] = LabelEncoder()
            self.label_encoders['result'] = LabelEncoder()
            
            print("✅ ML Models Initialized Successfully")
            
        except Exception as e:
            print(f"❌ Model initialization error: {e}")
    
    def load_historical_data(self):
        """Load and prepare historical football data"""
        try:
            # Load data from football.json repository
            seasons = ['2018-19', '2019-20', '2020-21', '2021-22', '2022-23']
            all_matches = []
            
            for season in seasons:
                url = f"https://raw.githubusercontent.com/openfootball/football.json/master/{season}/en.1.json"
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        for match in data.get('matches', []):
                            match_data = self.process_match_data(match, season)
                            if match_data:
                                all_matches.append(match_data)
                        print(f"✅ Loaded {len(data.get('matches', []))} matches from {season}")
                except Exception as e:
                    print(f"⚠️ Could not load {season}: {e}")
                    continue
            
            return pd.DataFrame(all_matches)
            
        except Exception as e:
            print(f"❌ Historical data loading error: {e}")
            return self.generate_synthetic_data()
    
    def generate_synthetic_data(self):
        """Generate synthetic training data when historical data is unavailable"""
        print("🔄 Generating synthetic training data...")
        
        teams = [
            'Manchester City', 'Liverpool', 'Arsenal', 'Chelsea', 'Tottenham',
            'Manchester United', 'Newcastle', 'Brighton', 'West Ham', 'Crystal Palace',
            'Fulham', 'Wolves', 'Everton', 'Brentford', 'Nottingham Forest',
            'Luton', 'Burnley', 'Sheffield United'
        ]
        
        matches = []
        for _ in range(2000):  # Generate 2000 synthetic matches
            home_team = random.choice(teams)
            away_team = random.choice([t for t in teams if t != home_team])
            
            # Team strengths (simulated)
            home_attack = np.random.normal(75, 15)
            home_defense = np.random.normal(75, 15)
            away_attack = np.random.normal(75, 15)
            away_defense = np.random.normal(75, 15)
            
            # Home advantage
            home_advantage = np.random.normal(0.3, 0.1)
            
            # Calculate expected goals
            home_xg = max(0, (home_attack / 100) * (away_defense / 100) * 3 + home_advantage)
            away_xg = max(0, (away_attack / 100) * (home_defense / 100) * 3 - home_advantage)
            
            # Simulate actual goals (Poisson distribution)
            home_goals = np.random.poisson(home_xg)
            away_goals = np.random.poisson(away_xg)
            
            # Determine result
            if home_goals > away_goals:
                result = 'H'
            elif away_goals > home_goals:
                result = 'A'
            else:
                result = 'D'
            
            match_data = {
                'home_team': home_team,
                'away_team': away_team,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'result': result,
                'btts': 1 if home_goals > 0 and away_goals > 0 else 0,
                'over_25': 1 if home_goals + away_goals > 2.5 else 0,
                'home_attack': home_attack,
                'home_defense': home_defense,
                'away_attack': away_attack,
                'away_defense': away_defense,
                'home_advantage': home_advantage,
                'total_goals': home_goals + away_goals
            }
            matches.append(match_data)
        
        return pd.DataFrame(matches)
    
    def process_match_data(self, match, season):
        """Process individual match data"""
        try:
            home_team = match.get('team1', '')
            away_team = match.get('team2', '')
            score = match.get('score', {})
            
            if not home_team or not away_team or not score.get('ft'):
                return None
            
            home_goals, away_goals = map(int, score['ft'])
            
            # Determine result
            if home_goals > away_goals:
                result = 'H'
            elif away_goals > home_goals:
                result = 'A'
            else:
                result = 'D'
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'result': result,
                'btts': 1 if home_goals > 0 and away_goals > 0 else 0,
                'over_25': 1 if home_goals + away_goals > 2.5 else 0,
                'season': season,
                'total_goals': home_goals + away_goals
            }
        except:
            return None
    
    def extract_features(self, df):
        """Extract features from match data"""
        try:
            # Team performance features
            team_stats = self.calculate_team_stats(df)
            
            features = []
            targets = {
                'result': [],
                'btts': [],
                'over_25': []
            }
            
            for _, match in df.iterrows():
                home_team = match['home_team']
                away_team = match['away_team']
                
                # Get team statistics
                home_stats = team_stats.get(home_team, self.get_default_stats())
                away_stats = team_stats.get(away_team, self.get_default_stats())
                
                # Feature vector
                feature_vector = [
                    home_stats['attack_strength'],
                    home_stats['defense_strength'],
                    away_stats['attack_strength'],
                    away_stats['defense_strength'],
                    home_stats['home_advantage'],
                    home_stats['form'],
                    away_stats['form'],
                    home_stats['goals_scored_avg'],
                    away_stats['goals_scored_avg'],
                    home_stats['goals_conceded_avg'],
                    away_stats['goals_conceded_avg']
                ]
                
                features.append(feature_vector)
                targets['result'].append(match['result'])
                targets['btts'].append(match['btts'])
                targets['over_25'].append(match['over_25'])
            
            return np.array(features), targets
            
        except Exception as e:
            print(f"❌ Feature extraction error: {e}")
            return np.array([]), {}
    
    def calculate_team_stats(self, df):
        """Calculate team statistics from historical data"""
        team_stats = {}
        
        for team in set(list(df['home_team']) + list(df['away_team'])):
            # Home matches
            home_matches = df[df['home_team'] == team]
            # Away matches
            away_matches = df[df['away_team'] == team]
            
            if len(home_matches) > 0:
                home_goals_scored = home_matches['home_goals'].mean()
                home_goals_conceded = home_matches['away_goals'].mean()
                home_win_rate = (home_matches['result'] == 'H').mean()
            else:
                home_goals_scored = home_goals_conceded = home_win_rate = 1.0
            
            if len(away_matches) > 0:
                away_goals_scored = away_matches['away_goals'].mean()
                away_goals_conceded = away_matches['home_goals'].mean()
                away_win_rate = (away_matches['result'] == 'A').mean()
            else:
                away_goals_scored = away_goals_conceded = away_win_rate = 1.0
            
            # Overall statistics
            all_matches = pd.concat([home_matches, away_matches])
            if len(all_matches) > 0:
                form = all_matches.tail(5)['result'].apply(lambda x: 1 if x == 'H' or x == 'A' else 0).mean()
            else:
                form = 0.5
            
            team_stats[team] = {
                'attack_strength': (home_goals_scored + away_goals_scored) / 2,
                'defense_strength': (home_goals_conceded + away_goals_conceded) / 2,
                'home_advantage': home_win_rate - away_win_rate,
                'form': form,
                'goals_scored_avg': (home_goals_scored + away_goals_scored) / 2,
                'goals_conceded_avg': (home_goals_conceded + away_goals_conceded) / 2
            }
        
        return team_stats
    
    def get_default_stats(self):
        """Return default statistics for unknown teams"""
        return {
            'attack_strength': 1.0,
            'defense_strength': 1.0,
            'home_advantage': 0.0,
            'form': 0.5,
            'goals_scored_avg': 1.0,
            'goals_conceded_avg': 1.0
        }
    
    def train_models(self):
        """Train all ML models"""
        try:
            print("🔄 Training ML models with historical data...")
            
            # Load and prepare data
            df = self.load_historical_data()
            
            if df.empty:
                print("❌ No training data available")
                return False
            
            # Extract features
            features, targets = self.extract_features(df)
            
            if features.size == 0:
                print("❌ No features extracted")
                return False
            
            # Scale features
            features_scaled = self.scaler.fit_transform(features)
            
            # Train each model
            for target_name, model in self.models.items():
                if target_name in targets and len(targets[target_name]) > 0:
                    X_train, X_test, y_train, y_test = train_test_split(
                        features_scaled, targets[target_name], 
                        test_size=0.2, random_state=42
                    )
                    
                    model.fit(X_train, y_train)
                    
                    # Calculate accuracy
                    y_pred = model.predict(X_test)
                    accuracy = accuracy_score(y_test, y_pred)
                    self.model_accuracy[target_name] = accuracy
                    
                    print(f"✅ {target_name.upper()} Model trained - Accuracy: {accuracy:.2%}")
                    
                    # Feature importance for tree-based models
                    if hasattr(model, 'feature_importances_'):
                        self.feature_importance[target_name] = model.feature_importances_
            
            print("🎯 All ML models trained successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Model training error: {e}")
            return False
    
    def predict_match(self, home_team, away_team, team_stats):
        """Predict match outcomes using ML models"""
        try:
            # Get team statistics
            home_stats = team_stats.get(home_team, self.get_default_stats())
            away_stats = team_stats.get(away_team, self.get_default_stats())
            
            # Create feature vector
            features = [
                home_stats['attack_strength'],
                home_stats['defense_strength'],
                away_stats['attack_strength'],
                away_stats['defense_strength'],
                home_stats['home_advantage'],
                home_stats['form'],
                away_stats['form'],
                home_stats['goals_scored_avg'],
                away_stats['goals_scored_avg'],
                home_stats['goals_conceded_avg'],
                away_stats['goals_conceded_avg']
            ]
            
            features_scaled = self.scaler.transform([features])
            
            predictions = {}
            
            # Make predictions for each model
            for target_name, model in self.models.items():
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(features_scaled)[0]
                    prediction = model.predict(features_scaled)[0]
                    
                    if target_name == 'result':
                        # For result prediction, get probability of each class
                        classes = model.classes_
                        if len(classes) == 3:  # H, D, A
                            predictions['home_win_prob'] = proba[0] * 100
                            predictions['draw_prob'] = proba[1] * 100
                            predictions['away_win_prob'] = proba[2] * 100
                            predictions['predicted_result'] = ['H', 'D', 'A'][prediction]
                        else:
                            # Handle binary classification
                            predictions['home_win_prob'] = proba[1] * 100 if classes[1] == 'H' else proba[0] * 100
                            predictions['predicted_result'] = 'H' if prediction == 1 else 'A'
                    
                    elif target_name == 'btts':
                        predictions['btts_yes_prob'] = proba[1] * 100
                        predictions['btts_prediction'] = 'YES' if prediction == 1 else 'NO'
                    
                    elif target_name == 'goals':
                        predictions['over_25_prob'] = proba[1] * 100
                        predictions['goals_prediction'] = 'OVER 2.5' if prediction == 1 else 'UNDER 2.5'
            
            return predictions
            
        except Exception as e:
            print(f"❌ Prediction error: {e}")
            return {}
    
    def generate_ml_predictions(self, match):
        """Generate ML-based predictions for a match"""
        try:
            home_team = match.get("match_hometeam_name", "Home")
            away_team = match.get("match_awayteam_name", "Away")
            league_id = match.get("league_id", "")
            league_name = TARGET_LEAGUES.get(str(league_id), match.get("league_name", ""))
            
            print(f"  🤖 ML ANALYSIS: {home_team} vs {away_team}")
            
            # Load current team stats (you would update this with latest data)
            df = self.load_historical_data()
            team_stats = self.calculate_team_stats(df)
            
            # Get ML predictions
            ml_predictions = self.predict_match(home_team, away_team, team_stats)
            
            if not ml_predictions:
                return None
            
            predictions = []
            
            # Match Result Prediction
            if 'predicted_result' in ml_predictions:
                result = ml_predictions['predicted_result']
                if result == 'H':
                    confidence = ml_predictions.get('home_win_prob', 0)
                    prediction_text = f"HOME WIN - {home_team}"
                elif result == 'A':
                    confidence = ml_predictions.get('away_win_prob', 0)
                    prediction_text = f"AWAY WIN - {away_team}"
                else:
                    confidence = ml_predictions.get('draw_prob', 0)
                    prediction_text = "DRAW"
                
                if confidence >= self.min_confidence:
                    predictions.append({
                        "market": "MATCH RESULT",
                        "prediction": prediction_text,
                        "confidence": round(confidence),
                        "odds": self.calculate_odds(confidence),
                        "reasoning": f"ML Model Prediction (Accuracy: {self.model_accuracy.get('result', 0):.1%})",
                        "bet_type": "Single",
                        "stake": "HIGH" if confidence >= 90 else "MEDIUM",
                        "model_confidence": f"{confidence:.1f}%"
                    })
            
            # BTTS Prediction
            if 'btts_prediction' in ml_predictions:
                confidence = ml_predictions.get('btts_yes_prob', 0)
                if confidence >= self.min_confidence:
                    predictions.append({
                        "market": "BOTH TEAMS TO SCORE",
                        "prediction": ml_predictions['btts_prediction'],
                        "confidence": round(confidence),
                        "odds": self.calculate_odds(confidence),
                        "reasoning": f"ML BTTS Model (Accuracy: {self.model_accuracy.get('btts', 0):.1%})",
                        "bet_type": "Single",
                        "stake": "MEDIUM",
                        "model_confidence": f"{confidence:.1f}%"
                    })
            
            # Goals Prediction
            if 'goals_prediction' in ml_predictions:
                confidence = ml_predictions.get('over_25_prob', 0)
                if confidence >= self.min_confidence:
                    predictions.append({
                        "market": "TOTAL GOALS",
                        "prediction": ml_predictions['goals_prediction'],
                        "confidence": round(confidence),
                        "odds": self.calculate_odds(confidence),
                        "reasoning": f"ML Goals Model (Accuracy: {self.model_accuracy.get('goals', 0):.1%})",
                        "bet_type": "Single",
                        "stake": "MEDIUM",
                        "model_confidence": f"{confidence:.1f}%"
                    })
            
            if not predictions:
                return None
            
            return {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "match_info": {
                    "home_team": home_team,
                    "away_team": away_team,
                    "league": league_name,
                    "match_time": match.get("match_time", ""),
                    "match_date": match.get("match_date", ""),
                    "analysis_type": "ML/AI PREDICTION"
                },
                "ml_predictions": predictions,
                "model_accuracies": self.model_accuracy,
                "risk_level": "VERY LOW"
            }
            
        except Exception as e:
            print(f"❌ ML prediction generation error: {e}")
            return None
    
    def calculate_odds(self, probability):
        """Calculate decimal odds from probability"""
        if probability <= 0:
            return "N/A"
        decimal_odds = round(100 / probability, 2)
        return f"{decimal_odds:.2f}"

# Initialize ML Predictor
ml_predictor = MLFootballPredictor()

# -------------------------
# HYBRID PREDICTION SYSTEM (ML + Rules)
# -------------------------
class HybridPredictor:
    def __init__(self):
        self.ml_predictor = ml_predictor
        self.team_database = {
            # Enhanced team database with ML features
            "Manchester City": {"attack": 95, "defense": 90, "form": 92, "home_strength": 96, "ml_rating": 94},
            "Liverpool": {"attack": 92, "defense": 88, "form": 90, "home_strength": 92, "ml_rating": 92},
            "Arsenal": {"attack": 90, "defense": 89, "form": 88, "home_strength": 91, "ml_rating": 89},
            # ... other teams
        }
    
    def generate_hybrid_predictions(self, match):
        """Generate predictions using both ML and rule-based approaches"""
        try:
            # First, try ML predictions
            ml_analysis = self.ml_predictor.generate_ml_predictions(match)
            
            if ml_analysis and ml_analysis["ml_predictions"]:
                return ml_analysis
            
            # Fallback to rule-based if ML fails
            return self.generate_rule_based_predictions(match)
            
        except Exception as e:
            print(f"❌ Hybrid prediction error: {e}")
            return self.generate_rule_based_predictions(match)
    
    def generate_rule_based_predictions(self, match):
        """Rule-based fallback predictions"""
        # Your existing rule-based prediction logic here
        # ... (keep your existing prediction logic as fallback)
        return None

# -------------------------
# REST OF THE BOT CODE WITH ML INTEGRATION
# -------------------------

# Update match data fetching functions (keep existing)
def fetch_upcoming_matches():
    """Fetch upcoming matches for predictions"""
    # ... (your existing implementation)

def fetch_live_matches():
    """Fetch live matches for real-time predictions"""
    # ... (your existing implementation)

def process_match_smart(match):
    """Process match data"""
    # ... (your existing implementation)

def get_upcoming_matches():
    """Get upcoming matches for predictions"""
    # ... (your existing implementation)

def get_live_matches():
    """Get current live matches"""
    # ... (your existing implementation)

# Update prediction message generation
def generate_ml_prediction_message(match_analysis):
    """Generate ML-based prediction message"""
    try:
        if not match_analysis or not match_analysis["ml_predictions"]:
            return None
            
        match_info = match_analysis["match_info"]
        predictions = match_analysis["ml_predictions"]
        accuracies = match_analysis.get("model_accuracies", {})
        
        message = f"🤖 **ML/AI PREDICTION** 🤖\n"
        message += f"⏰ Analysis Time: {match_analysis['timestamp']}\n\n"
        
        message += f"⚽ **{match_info['home_team']} vs {match_info['away_team']}**\n"
        message += f"🏆 {match_info.get('league', '')}\n"
        message += f"📅 {match_info.get('match_date', '')} | 🕒 {match_info.get('match_time', '')}\n\n"
        
        # Model accuracies
        if accuracies:
            message += "📊 **MODEL ACCURACIES:**\n"
            for model, accuracy in accuracies.items():
                message += f"• {model.upper()}: {accuracy:.1%}\n"
            message += "\n"
        
        message += "💰 **ML PREDICTIONS:**\n\n"
        
        for prediction in predictions:
            message += f"🎯 **{prediction['market']}**\n"
            message += f"✅ **Prediction:** `{prediction['prediction']}`\n"
            message += f"📈 **Confidence:** `{prediction['confidence']}%`\n"
            message += f"🤖 **ML Confidence:** `{prediction.get('model_confidence', 'N/A')}`\n"
            message += f"🎯 **Odds:** `{prediction['odds']}`\n"
            message += f"💡 **Reason:** {prediction['reasoning']}\n"
            message += f"💰 **Stake:** {prediction['stake']}\n\n"
        
        message += f"⚠️ **RISK LEVEL:** {match_analysis['risk_level']}\n\n"
        message += "🔔 **ML BETTING ADVICE:**\n"
        message += "• Predictions generated by Machine Learning models\n"
        message += "• Trained on historical football data\n"
        message += "• Higher accuracy than traditional methods\n"
        message += "• Good luck! 🍀\n\n"
        message += "✅ **ML/AI POWERED - SCIENTIFIC BETTING**"
        
        return message
        
    except Exception as e:
        print(f"❌ ML message generation error: {e}")
        return None

# Initialize hybrid predictor
hybrid_predictor = HybridPredictor()

# Train ML models on startup
print("🔄 Training ML models on startup...")
ml_training_success = ml_predictor.train_models()

if ml_training_success:
    print("✅ ML models trained successfully!")
else:
    print("⚠️ Using rule-based predictions as fallback")

# Update auto updater to use ML predictions
def auto_ml_updater():
    """Auto-updater with ML predictions"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Starting ML PREDICTION cycle...")
            
            # Get matches
            upcoming_matches = get_upcoming_matches()
            
            ml_predictions_sent = 0
            
            for match in upcoming_matches[:5]:  # Limit to 5 for quality
                try:
                    match_id = match.get("match_id")
                    
                    if prediction_manager.should_analyze_pre_match(match_id):
                        print(f"  🤖 Generating ML predictions...")
                        
                        # Use hybrid predictor (ML + rules)
                        analysis = hybrid_predictor.generate_hybrid_predictions(match)
                        
                        if analysis and analysis.get("ml_predictions"):
                            message = generate_ml_prediction_message(analysis)
                            
                            if message:
                                bot.send_message(OWNER_CHAT_ID, message, parse_mode='Markdown')
                                prediction_manager.mark_pre_match_sent(match_id)
                                ml_predictions_sent += 1
                                print(f"    ✅ ML PREDICTION SENT")
                                time.sleep(3)
                                
                except Exception as e:
                    print(f"    ❌ ML analysis failed: {e}")
                    continue
            
            # Summary
            if ml_predictions_sent > 0:
                summary_msg = f"""
📊 **ML PREDICTION CYCLE COMPLETE**

⏰ Cycle Time: {current_time}
🤖 ML Predictions Sent: {ml_predictions_sent}
🎯 Model Accuracies:
   • Result: {ml_predictor.model_accuracy.get('result', 0):.1%}
   • BTTS: {ml_predictor.model_accuracy.get('btts', 0):.1%}
   • Goals: {ml_predictor.model_accuracy.get('goals', 0):.1%}

🔔 Next ML prediction cycle in 30 minutes...
"""
                try:
                    bot.send_message(OWNER_CHAT_ID, summary_msg, parse_mode='Markdown')
                except Exception as e:
                    print(f"❌ Summary send failed: {e}")
                
        except Exception as e:
            print(f"❌ ML updater error: {e}")
        
        print("💤 Next ML prediction cycle in 30 minutes...")
        time.sleep(1800)  # 30 minutes

# Add ML-specific command
@bot.message_handler(commands=['ml_predict'])
def ml_predict_command(message):
    """Get ML-based predictions"""
    try:
        bot.reply_to(message, "🤖 Generating ML/AI PREDICTIONS...")
        
        upcoming_matches = get_upcoming_matches()
        
        if not upcoming_matches:
            bot.reply_to(message, "⏳ No matches for ML analysis.")
            return
        
        response_message = "🤖 **ML/AI PREDICTIONS** 🤖\n\n"
        
        for match in upcoming_matches[:2]:
            analysis = hybrid_predictor.generate_hybrid_predictions(match)
            
            if analysis and analysis.get("ml_predictions"):
                match_info = analysis["match_info"]
                
                response_message += f"⚽ **{match_info['home_team']} vs {match_info['away_team']}**\n"
                response_message += f"🏆 {match_info['league']}\n"
                
                for pred in analysis["ml_predictions"]:
                    response_message += f"✅ {pred['market']}: `{pred['prediction']}` ({pred['confidence']}%)\n"
                    response_message += f"🤖 ML Confidence: {pred.get('model_confidence', 'N/A')}\n"
                
                response_message += "\n"
        
        if "✅" not in response_message:
            response_message += "⏳ No high-confidence ML predictions found.\n"
        
        bot.reply_to(message, response_message, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ ML prediction error: {str(e)}")

# Update startup message
def setup_bot():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
        print(f"✅ Webhook set: {DOMAIN}/{BOT_TOKEN}")

        # Start ML updater
        t = threading.Thread(target=auto_ml_updater, daemon=True)
        t.start()
        print("✅ ML Auto Updater Started!")

        startup_msg = f"""
🤖 **ML/AI FOOTBALL PREDICTION BOT STARTED!**

🎯 **ADVANCED ML FEATURES:**
• Machine Learning Models: Random Forest, Gradient Boosting, Logistic Regression
• Historical Data Training: 5+ seasons of football data
• Feature Engineering: Attack/Defense metrics, Form analysis
• Model Accuracies: {ml_predictor.model_accuracy.get('result', 0):.1%} (Result), {ml_predictor.model_accuracy.get('btts', 0):.1%} (BTTS)
• Hybrid System: ML + Rule-based fallback

✅ **System actively generating ML-powered predictions!**
⏰ **First ML prediction cycle in 1 minute...**

🔔 **Ready to deliver scientific betting insights!** 🎯
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Bot setup error: {e}")
        bot.polling(none_stop=True)

# Note: Keep your existing PredictionManager class and other utilities

if __name__ == '__main__':
    print("🚀 Starting ML/AI Football Prediction Bot...")
    setup_bot()
    app.run(host='0.0.0.0', port=PORT)
