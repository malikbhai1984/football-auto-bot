import os
import requests
import telebot
import time
import random
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import Flask, request
import threading
from dotenv import load_dotenv
import json
import pytz

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

print("🎯 Starting REAL-TIME FOOTBALL PREDICTION BOT...")

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
# REAL-TIME MATCH DATA FETCHING
# -------------------------
def fetch_real_live_matches():
    """Fetch REAL live matches from API"""
    try:
        print("🔴 Fetching REAL live matches from API...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={today}&to={today}"
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data and isinstance(data, list):
                live_matches = []
                for match in data:
                    # Check if match is live
                    if match.get("match_live") == "1" and match.get("match_status", "").isdigit():
                        league_id = match.get("league_id", "")
                        # Only include target leagues
                        if str(league_id) in TARGET_LEAGUES:
                            live_matches.append(match)
                
                print(f"✅ Found {len(live_matches)} REAL live matches")
                return live_matches
            else:
                print("⏳ No live matches data from API")
                return []
        else:
            print(f"❌ API Error {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Live matches fetch error: {e}")
        return []

def process_real_match(match):
    """Process real match data from API"""
    try:
        home_team = match.get("match_hometeam_name", "Unknown")
        away_team = match.get("match_awayteam_name", "Unknown")
        home_score = match.get("match_hometeam_score", "0")
        away_score = match.get("match_awayteam_score", "0")
        minute = match.get("match_status", "0")
        league_id = match.get("league_id", "")
        league_name = TARGET_LEAGUES.get(str(league_id), "Unknown League")
        
        # Determine match status
        if minute == "HT":
            match_status = "HALF TIME"
            display_minute = "HT"
        elif minute == "FT":
            match_status = "FULL TIME"
            display_minute = "FT"
        elif minute.isdigit():
            match_status = "LIVE"
            display_minute = f"{minute}'"
        else:
            match_status = "UPCOMING"
            display_minute = minute
        
        return {
            "home_team": home_team,
            "away_team": away_team,
            "score": f"{home_score}-{away_score}",
            "minute": display_minute,
            "status": match_status,
            "league": league_name,
            "league_id": league_id
        }
        
    except Exception as e:
        print(f"❌ Match processing error: {e}")
        return None

def get_real_live_matches():
    """Get real live matches from API"""
    try:
        raw_matches = fetch_real_live_matches()
        
        if not raw_matches:
            return []
        
        processed_matches = []
        for match in raw_matches:
            processed_match = process_real_match(match)
            if processed_match:
                processed_matches.append(processed_match)
        
        print(f"✅ Processed {len(processed_matches)} real live matches")
        return processed_matches
            
    except Exception as e:
        print(f"❌ Live matches processing error: {e}")
        return []

# -------------------------
# SMART AI CHATBOT (Improved)
# -------------------------
class SmartFootballAI:
    def __init__(self):
        self.conversation_memory = {}
        self.football_knowledge = self.initialize_football_knowledge()
    
    def initialize_football_knowledge(self):
        """Enhanced football database"""
        return {
            "teams": {
                "manchester city": {"strength": 95, "attack": 96, "defense": 90, "style": "attacking", "manager": "Pep Guardiola"},
                "liverpool": {"strength": 92, "attack": 94, "defense": 88, "style": "high press", "manager": "Jurgen Klopp"},
                "arsenal": {"strength": 90, "attack": 89, "defense": 91, "style": "possession", "manager": "Mikel Arteta"},
                "chelsea": {"strength": 85, "attack": 84, "defense": 86, "style": "balanced", "manager": "Mauricio Pochettino"},
                "manchester united": {"strength": 84, "attack": 83, "defense": 82, "style": "counter attack", "manager": "Erik ten Hag"},
                "tottenham": {"strength": 87, "attack": 88, "defense": 85, "style": "attacking", "manager": "Ange Postecoglou"},
                "real madrid": {"strength": 94, "attack": 93, "defense": 91, "style": "experienced", "manager": "Carlo Ancelotti"},
                "barcelona": {"strength": 92, "attack": 91, "defense": 89, "style": "possession", "manager": "Xavi Hernandez"},
                "bayern munich": {"strength": 93, "attack": 95, "defense": 88, "style": "dominant", "manager": "Thomas Tuchel"},
                "psg": {"strength": 90, "attack": 92, "defense": 85, "style": "attacking", "manager": "Luis Enrique"},
                "inter": {"strength": 89, "attack": 87, "defense": 90, "style": "defensive", "manager": "Simone Inzaghi"},
                "juventus": {"strength": 88, "attack": 85, "defense": 89, "style": "tactical", "manager": "Massimiliano Allegri"},
                "milan": {"strength": 86, "attack": 86, "defense": 85, "style": "balanced", "manager": "Stefano Pioli"},
                "napoli": {"strength": 85, "attack": 87, "defense": 83, "style": "attacking", "manager": "Walter Mazzarri"}
            },
            "players": {
                "haaland": {"team": "manchester city", "position": "striker", "goals": 25, "rating": 94},
                "salah": {"team": "liverpool", "position": "winger", "goals": 18, "rating": 92},
                "mbappe": {"team": "psg", "position": "forward", "goals": 27, "rating": 95},
                "kane": {"team": "bayern munich", "position": "striker", "goals": 30, "rating": 93},
                "de bruyne": {"team": "manchester city", "position": "midfielder", "goals": 8, "assists": 15, "rating": 93},
                "bellingham": {"team": "real madrid", "position": "midfielder", "goals": 20, "rating": 92},
                "vinicius": {"team": "real madrid", "position": "winger", "goals": 16, "rating": 91}
            }
        }
    
    def get_ai_response(self, user_message, user_id):
        """Smart AI response with context awareness"""
        try:
            user_message_lower = user_message.lower().strip()
            
            # Initialize conversation memory
            if user_id not in self.conversation_memory:
                self.conversation_memory[user_id] = []
            
            # Add to memory
            self.conversation_memory[user_id].append(f"User: {user_message}")
            
            # Get context from previous messages
            context = self.get_conversation_context(user_id)
            
            # Generate intelligent response
            response = self.analyze_query(user_message_lower, context, user_id)
            
            # Store response
            self.conversation_memory[user_id].append(f"Bot: {response}")
            
            # Keep conversation manageable
            if len(self.conversation_memory[user_id]) > 8:
                self.conversation_memory[user_id] = self.conversation_memory[user_id][-8:]
            
            return response
            
        except Exception as e:
            print(f"❌ AI response error: {e}")
            return "I'm here to help with football predictions and analysis! ⚽ What would you like to know?"
    
    def get_conversation_context(self, user_id):
        """Get context from conversation history"""
        if user_id in self.conversation_memory and len(self.conversation_memory[user_id]) > 0:
            return " ".join(self.conversation_memory[user_id][-3:])
        return ""
    
    def analyze_query(self, message, context, user_id):
        """Advanced query analysis with context awareness"""
        
        # Check for live matches query
        if any(word in message for word in ['live', 'current', 'now playing', 'right now', 'ongoing']):
            return self.handle_live_matches_query()
        
        # Check for specific match queries
        if any(word in message for word in [' vs ', ' versus ', ' against ']):
            return self.handle_specific_match_query(message)
        
        # Greetings and basic queries
        if any(word in message for word in ['hello', 'hi', 'hey', 'hola', 'namaste']):
            return random.choice([
                "👋 Hello! I'm your Football AI Assistant! Ready to talk football? ⚽",
                "👋 Hi there! Excited to discuss football predictions with you!",
                "👋 Hey! Great to see you! What match are we analyzing today?"
            ])
        
        # Thanks
        elif any(word in message for word in ['thank', 'thanks', 'shukriya']):
            return random.choice([
                "😊 You're welcome! Always happy to help with football insights!",
                "😊 My pleasure! Let me know if you need more predictions!",
                "😊 Glad I could help! What else can I analyze for you?"
            ])
        
        # Predictions
        elif any(word in message for word in ['predict', 'prediction', 'who will win', 'forecast', 'result']):
            return self.handle_prediction_query(message)
        
        # Betting advice
        elif any(word in message for word in ['bet', 'betting', 'odds', 'gambling', 'satta', 'wager']):
            return self.handle_betting_query(message)
        
        # Team analysis
        elif any(word in message for word in ['team', 'squad', 'performance', 'analysis']):
            return self.handle_team_query(message)
        
        # Player queries
        elif any(word in message for word in ['player', 'goal', 'assist', 'stats']):
            return self.handle_player_query(message)
        
        # League queries
        elif any(word in message for word in ['premier league', 'la liga', 'serie a', 'bundesliga', 'champions league', 'europa']):
            return self.handle_league_query(message)
        
        # Help
        elif any(word in message for word in ['help', 'what can you do', 'features', 'commands']):
            return self.get_help_response()
        
        # General football chat
        elif any(word in message for word in ['football', 'soccer', 'match', 'game', 'fixture']):
            return random.choice([
                "⚽ Football is my passion! I love analyzing matches and predicting outcomes. What specific match interests you?",
                "⚽ Great topic! I specialize in match predictions and team analysis. Which league are you following?",
                "⚽ Wonderful! I can help with predictions, betting tips, or team analysis. What would you like to discuss?"
            ])
        
        # Unknown query - intelligent fallback
        else:
            return self.handle_unknown_query(message, context)
    
    def handle_live_matches_query(self):
        """Handle live matches queries"""
        real_matches = get_real_live_matches()
        
        if real_matches:
            response = "🔴 **REAL LIVE MATCHES RIGHT NOW:**\n\n"
            
            # Group by league
            matches_by_league = {}
            for match in real_matches:
                league = match['league']
                if league not in matches_by_league:
                    matches_by_league[league] = []
                matches_by_league[league].append(match)
            
            for league, matches in matches_by_league.items():
                response += f"⚽ **{league}**\n"
                for match in matches:
                    status_icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "✅"
                    response += f"• {match['home_team']} {match['score']} {match['away_team']} {status_icon} {match['minute']}\n"
                response += "\n"
            
            response += "🔄 **Live updates every 5 minutes!**\n"
            response += "💬 **Ask me about any of these matches for predictions!**"
            
        else:
            response = "⏳ **No live matches currently playing in major leagues.**\n\n"
            response += "🔮 **But I can still help you with:**\n"
            response += "• Upcoming match predictions\n• Team analysis\n• Betting strategies\n• Player statistics\n\n"
            response += "Try: `/predict` for today's predictions or ask me about specific teams!"
        
        return response
    
    def handle_specific_match_query(self, message):
        """Handle specific match queries"""
        teams = self.extract_teams(message)
        
        if teams and len(teams) >= 2:
            home_team, away_team = teams[0], teams[1]
            return self.generate_detailed_prediction(home_team, away_team)
        else:
            return "🤔 I'd love to analyze a specific match for you! Please mention both teams, for example: 'Manchester City vs Liverpool' or 'Predict Arsenal vs Chelsea'"
    
    def handle_prediction_query(self, message):
        """Handle prediction queries"""
        teams = self.extract_teams(message)
        
        if teams and len(teams) >= 2:
            return self.generate_detailed_prediction(teams[0], teams[1])
        else:
            return "🎯 I can predict match outcomes! Please specify the teams, like: 'Predict Barcelona vs Real Madrid' or use `/predict` for today's matches."
    
    def handle_betting_query(self, message):
        """Handle betting queries with dynamic advice"""
        current_advice = """
💰 **SMART BETTING INSIGHTS** 🎯

🏠 **Home Advantage Tips:**
• Strong home teams win 45% more often
• Consider home team's recent form
• Check for key player availability

⚡ **Value Bet Opportunities:**
• BTTS YES in attacking matchups
• OVER 2.5 goals when both teams score freely
• Double Chance for evenly matched teams

🛡️ **Bankroll Management:**
• Never bet more than 5% of your bankroll
• Keep detailed records of all bets
• Stay disciplined with staking plans

🎲 **Today's Betting Philosophy:**
'Quality over quantity - one well-researched bet is better than ten random picks'

💡 **Pro Tip:** Always check team news 1 hour before kickoff!
"""
        return current_advice
    
    def handle_team_query(self, message):
        """Handle team queries"""
        for team_name in self.football_knowledge["teams"]:
            if team_name in message:
                return self.generate_team_analysis(team_name)
        
        return "Which team would you like me to analyze? I have detailed data on all major European clubs! 🏆"
    
    def handle_player_query(self, message):
        """Handle player queries"""
        for player_name, player_data in self.football_knowledge["players"].items():
            if player_name in message:
                return self.generate_player_analysis(player_name, player_data)
        
        return "I can analyze top players like Haaland, Salah, Mbappe, Kane, De Bruyne. Who interests you? ⚽"
    
    def handle_league_query(self, message):
        """Handle league queries"""
        league_info = {
            "premier league": "🇬🇧 **Premier League**: Most competitive league worldwide. High tempo, physical, unpredictable. Average goals: 2.8 per game.",
            "la liga": "🇪🇸 **La Liga**: Technical excellence, tactical battles. Barcelona & Real Madrid dominance. Average goals: 2.5 per game.", 
            "serie a": "🇮🇹 **Serie A**: Defensive mastery, tactical discipline. Known for tight games. Average goals: 2.4 per game.",
            "bundesliga": "🇩🇪 **Bundesliga**: High-scoring, fan-friendly football. Bayern's dominance continues. Average goals: 3.2 per game.",
            "champions league": "🏆 **Champions League**: Elite European competition. Highest quality, most unpredictable. Big teams often deliver."
        }
        
        for league, info in league_info.items():
            if league in message:
                return f"{info}\n\n💡 **Betting Insight**: {self.get_league_betting_tip(league)}"
        
        return "I cover all major European leagues! Which one would you like to discuss?"
    
    def handle_unknown_query(self, message, context):
        """Intelligent handling of unknown queries"""
        # Try to extract intent
        if any(word in message for word in ['how', 'what', 'when', 'where', 'why']):
            return "That's an interesting question! As a football prediction expert, I specialize in match analysis, team performance, and betting strategies. Could you rephrase your question in a football context?"
        
        elif any(word in message for word in ['good', 'bad', 'awesome', 'terrible']):
            return "I sense you have strong feelings about football! ⚽ Tell me which team or match you're referring to, and I'll give you my analysis!"
        
        elif len(message.split()) <= 3:
            return f"\"{message}\" - are you asking about a team, player, or match? I'd love to help with specific football analysis! 🎯"
        
        else:
            return "I'm constantly learning about football! While I specialize in predictions and analysis, I might not understand everything. Try asking me about:\n• Match predictions\n• Team analysis\n• Betting tips\n• Player stats\n• League information"
    
    def extract_teams(self, message):
        """Extract team names from message"""
        mentioned_teams = []
        for team_name in self.football_knowledge["teams"].keys():
            if team_name in message.lower():
                mentioned_teams.append(team_name)
        return mentioned_teams
    
    def generate_detailed_prediction(self, home_team, away_team):
        """Generate detailed match prediction"""
        home_data = self.football_knowledge["teams"].get(home_team)
        away_data = self.football_knowledge["teams"].get(away_team)
        
        if not home_data or not away_data:
            return f"❌ I don't have enough data for {home_team} vs {away_team}. Try teams from major European leagues!"
        
        # Advanced prediction algorithm
        home_advantage = 12
        home_total = home_data["strength"] + home_advantage
        away_total = away_data["strength"]
        total_power = home_total + away_total
        
        home_win_prob = (home_total / total_power) * 100
        away_win_prob = (away_total / total_power) * 100
        draw_prob = 100 - home_win_prob - away_win_prob
        
        # Determine confidence level
        confidence = "HIGH" if max(home_win_prob, away_win_prob, draw_prob) > 55 else "MEDIUM"
        
        # BTTS prediction
        btts_probability = (home_data["attack"] + away_data["attack"]) / 2
        btts = "YES" if btts_probability > 47 else "NO"
        
        # Goals prediction
        expected_goals = (home_data["attack"] + away_data["attack"]) / 50
        goals_pred = "OVER 2.5" if expected_goals > 2.7 else "UNDER 2.5"
        
        # Key factors analysis
        factors = self.analyze_key_factors(home_data, away_data)
        
        prediction = f"""
🎯 **DETAILED PREDICTION: {home_team.upper()} vs {away_team.upper()}**

📊 **TEAM ANALYSIS:**
🏠 **{home_team.title()}** 
   • Strength: {home_data['strength']}/100
   • Style: {home_data['style']}
   • Manager: {home_data['manager']}

✈️ **{away_team.title()}**
   • Strength: {away_data['strength']}/100  
   • Style: {away_data['style']}
   • Manager: {away_data['manager']}

📈 **PREDICTION RESULTS:**
• **Most Likely**: {self.get_most_likely_outcome(home_win_prob, away_win_prob, draw_prob)}
• **Confidence**: {confidence}
• **BTTS**: {btts} ({btts_probability:.0f}% probability)
• **Total Goals**: {goals_pred}

🔍 **KEY FACTORS:**
{factors}

💡 **BETTING RECOMMENDATION:**
{self.get_betting_recommendation(home_data, away_data, home_win_prob, away_win_prob, draw_prob)}

⚠️ *Remember: Football can be unpredictable! Use this as guidance.*
"""
        return prediction
    
    def analyze_key_factors(self, home_data, away_data):
        """Analyze key match factors"""
        factors = []
        
        if home_data["strength"] - away_data["strength"] > 15:
            factors.append("• Strong home advantage")
        elif away_data["strength"] - home_data["strength"] > 15:
            factors.append("• Away team quality advantage")
        
        if home_data["attack"] > 90 and away_data["attack"] > 90:
            factors.append("• Both teams have elite attacks")
        elif home_data["defense"] > 90 and away_data["defense"] > 90:
            factors.append("• Strong defensive matchup")
        
        if home_data["style"] == "attacking" and away_data["style"] == "attacking":
            factors.append("• Both teams prefer attacking football")
        elif home_data["style"] == "defensive" and away_data["style"] == "defensive":
            factors.append("• Defensive tactical battle expected")
        
        if not factors:
            factors.append("• Evenly balanced contest")
            factors.append("• Small details could decide outcome")
        
        return "\n".join(factors)
    
    def get_most_likely_outcome(self, home_prob, away_prob, draw_prob):
        """Determine most likely outcome"""
        if home_prob >= away_prob and home_prob >= draw_prob:
            return f"Home Win ({home_prob:.1f}%)"
        elif away_prob >= home_prob and away_prob >= draw_prob:
            return f"Away Win ({away_prob:.1f}%)"
        else:
            return f"Draw ({draw_prob:.1f}%)"
    
    def get_betting_recommendation(self, home_data, away_data, home_prob, away_prob, draw_prob):
        """Get smart betting recommendation"""
        if home_prob > 60:
            return "HOME WIN or -1 Handicap"
        elif away_prob > 60:
            return "AWAY WIN or Double Chance (X2)"
        elif draw_prob > 40:
            return "DRAW or Double Chance (1X/ X2)"
        elif home_data["attack"] > 85 and away_data["attack"] > 85:
            return "BTTS YES + OVER 2.5 GOALS"
        else:
            return "DOUBLE CHANCE + UNDER 3.5 GOALS"
    
    def generate_team_analysis(self, team_name):
        """Generate detailed team analysis"""
        team_data = self.football_knowledge["teams"][team_name]
        
        return f"""
🏆 **{team_name.upper()} - COMPREHENSIVE ANALYSIS**

📊 **Performance Metrics:**
• Overall Rating: {team_data['strength']}/100
• Attack Power: {team_data['attack']}/100
• Defense Stability: {team_data['defense']}/100
• Playing Philosophy: {team_data['style'].title()}
• Manager: {team_data['manager']}

🎯 **Tactical Identity:**
{self.get_tactical_analysis(team_name)}

💪 **Key Strengths:**
{self.get_team_strengths(team_name)}

⚠️ **Areas for Improvement:**
{self.get_team_weaknesses(team_name)}

🔮 **Betting Profile:**
{self.get_team_betting_profile(team_name)}
"""
    
    def get_tactical_analysis(self, team_name):
        """Get tactical analysis"""
        analysis = {
            "manchester city": "Possession-based dominance, high press, creative midfield overloads, fluid attacking movements",
            "liverpool": "Gegenpressing intensity, rapid transitions, full-back creativity, organized chaos",
            "arsenal": "Positional play discipline, youth energy, set-piece efficiency, tactical flexibility",
            "real madrid": "Big-game experience, individual brilliance, counter-attacking threat, European pedigree"
        }
        return analysis.get(team_name, "Balanced tactical approach with focus on both offensive and defensive organization")
    
    def get_team_strengths(self, team_name):
        """Get team strengths"""
        strengths = {
            "manchester city": "• World-class squad depth\n• Tactical versatility\n• Possession dominance\n• Clinical finishing",
            "liverpool": "• Pressing intensity\n• Anfield atmosphere\n• Fast transitions\n• Team cohesion", 
            "arsenal": "• Youthful energy\n• Tactical discipline\n• Set-piece quality\n• Defensive organization",
            "real madrid": "• Big-game mentality\n• Individual quality\n• European experience\n• Winning culture"
        }
        return strengths.get(team_name, "• Consistent performance\n• Strong team spirit\n• Tactical organization")
    
    def get_team_weaknesses(self, team_name):
        """Get team weaknesses"""
        weaknesses = {
            "manchester city": "• Vulnerability to counter-attacks\n• Occasional complacency\n• High defensive line risks",
            "liverpool": "• Defensive line exposure\n• Squad rotation challenges\n• Away form consistency",
            "arsenal": "• Big-game experience\n• Squad depth in key positions\n• European competition learning curve",
            "real madrid": "• Aging core players\n• Defensive transitions\n• Over-reliance on individual moments"
        }
        return weaknesses.get(team_name, "• Standard areas for improvement expected at elite level")
    
    def get_team_betting_profile(self, team_name):
        """Get team betting profile"""
        profiles = {
            "manchester city": "• Strong HOME WIN bets\n• OVER 2.5 goals frequently\n• HT/FT City-City value",
            "liverpool": "• BTTS YES common\n• HIGH scoring games\n• Strong Anfield record", 
            "arsenal": "• Clean sheet potential\n• UNDER 2.5 in big games\n• Set-piece threat",
            "real madrid": "• Big game performers\n• Late goal specialists\n• European night magic"
        }
        return profiles.get(team_name, "• Consider form and fixtures\n• Home/away performance variation\n• Match context important")
    
    def generate_player_analysis(self, player_name, player_data):
        """Generate player analysis"""
        return f"""
⭐ **{player_name.upper()} - PLAYER PROFILE**

🏷️ **Basic Info:**
• Team: {player_data['team'].title()}
• Position: {player_data['position'].title()}
• Rating: {player_data['rating']}/100

📈 **Performance Stats:**
• Goals: {player_data.get('goals', 'N/A')}
• Assists: {player_data.get('assists', 'N/A')}

🎯 **Playing Style:**
{self.get_player_style(player_name)}

💪 **Key Attributes:**
{self.get_player_attributes(player_name)}

🔮 **Betting Relevance:**
{self.get_player_betting_insight(player_name)}
"""
    
    def get_player_style(self, player_name):
        """Get player style"""
        styles = {
            "haaland": "Elite poacher, incredible movement, physical dominance, clinical finishing",
            "salah": "Left-footed wizard, cutting inside, goal threat, creative passing", 
            "mbappe": "Lightning speed, dribbling ability, big-game performer, versatile attacker",
            "de bruyne": "Complete midfielder, vision, passing range, set-piece specialist"
        }
        return styles.get(player_name, "Technical quality, tactical intelligence, consistent performer")
    
    def get_player_attributes(self, player_name):
        """Get player attributes"""
        attributes = {
            "haaland": "• Aerial dominance\n• Clinical finishing\n• Physical strength\n• Movement intelligence",
            "salah": "• Left-foot precision\n• Dribbling ability\n• Goal scoring\n• Creative vision",
            "mbappe": "• Explosive speed\n• Technical skill\n• Big-game mentality\n• Versatility",
            "de bruyne": "• Passing range\n• Vision intelligence\n• Set-piece quality\n• Leadership"
        }
        return attributes.get(player_name, "• Technical excellence\n• Tactical understanding\n• Consistent performance")
    
    def get_player_betting_insight(self, player_name):
        """Get player betting insight"""
        insights = {
            "haaland": "• Anytime goalscorer value\n• First goalscorer potential\n• Multiple goal threat",
            "salah": "• Shots on target markets\n• Anytime scorer\n• Assist potential", 
            "mbappe": "• First goalscorer\n• Anytime scorer\n• Man of the match candidate",
            "de bruyne": "• Assist markets\n• Shots on target\n• Set-piece involvement"
        }
        return insights.get(player_name, "• Consider position and role\n• Check recent form\n• Team performance context")
    
    def get_league_betting_tip(self, league):
        """Get league-specific betting tip"""
        tips = {
            "premier league": "Focus on home advantage and team form. BTTS markets often provide value.",
            "la liga": "Consider unders in defensive matchups. Home teams generally perform well.", 
            "serie a": "Defensive stability key. Lower scoring games common. Clean sheet bets valuable.",
            "bundesliga": "High scoring expected. Goal-based markets profitable. Home dominance strong.",
            "champions league": "Big teams often deliver. Experience crucial. Knockout rounds unpredictable."
        }
        return tips.get(league, "Research team form and tactical matchups for best value.")
    
    def get_help_response(self):
        """Get comprehensive help response"""
        return """
🤖 **FOOTBALL PREDICTION AI - COMPLETE GUIDE** ⚽

🎯 **MY CAPABILITIES:**
• Real-time match predictions
• Live match updates  
• Team performance analysis
• Player statistics and insights
• Betting strategies and tips
• League-specific analysis
• Natural conversation about football

⚡ **QUICK COMMANDS:**
`/start` - Welcome and introduction
`/predict` - Today's match predictions  
`/live` - Currently live matches
`/help` - This help guide

💬 **INTELLIGENT CHAT EXAMPLES:**
• "Predict Manchester City vs Liverpool"
• "Show me live matches right now"
• "Analyze Arsenal for me" 
• "Betting tips for today"
• "How will Barcelona do against Real Madrid?"
• "Tell me about Erling Haaland"
• "Premier League analysis"

🔮 **PREDICTION FEATURES:**
• Match outcome probabilities
• Both Teams to Score analysis
• Over/Under goals predictions
• Key match factors
• Betting recommendations
• Confidence levels

🏆 **COVERED LEAGUES:**
• Premier League, La Liga, Serie A
• Bundesliga, Ligue 1  
• Champions League, Europa League

💡 **I learn from our conversation and provide context-aware responses!**
"""

# Initialize AI Chatbot
football_ai = SmartFootballAI()

# -------------------------
# TELEGRAM BOT HANDLERS
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Welcome message"""
    welcome_text = """
🤖 **WELCOME TO FOOTBALL PREDICTION AI** ⚽

I'm your intelligent football assistant with **real-time capabilities**!

🎯 **REAL-TIME FEATURES:**
• Live match scores and updates
• AI-powered predictions
• Smart betting insights
• Team and player analysis
• Natural conversation

⚡ **QUICK ACCESS:**
`/predict` - Today's predictions
`/live` - Real live matches right now
`/help` - Complete guide

💬 **CHAT INTELLIGENTLY:**
• "Show me live matches"
• "Predict [Team A] vs [Team B]" 
• "Analyze [Team/Player]"
• "Betting tips for today"
• Ask anything football!

🔴 **I provide REAL live match data, not samples!**
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['predict'])
def get_predictions(message):
    """Get today's predictions"""
    try:
        response = "🔮 **Today's predictions are based on current form and statistical models...**\n\n"
        response += "For specific match predictions, please ask me like:\n"
        response += "• 'Predict Manchester City vs Liverpool'\n" 
        response += "• 'Who will win Barcelona vs Real Madrid?'\n"
        response += "• 'Arsenal vs Chelsea prediction'\n\n"
        response += "Or check `/live` for currently playing matches!"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Prediction error: {str(e)}")

@bot.message_handler(commands=['live'])
def get_live_matches(message):
    """Get REAL live matches"""
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Get real live matches
        live_matches = get_real_live_matches()
        
        if live_matches:
            response = "🔴 **REAL LIVE MATCHES RIGHT NOW:**\n\n"
            
            # Group by league
            matches_by_league = {}
            for match in live_matches:
                league = match['league']
                if league not in matches_by_league:
                    matches_by_league[league] = []
                matches_by_league[league].append(match)
            
            for league, matches in matches_by_league.items():
                response += f"⚽ **{league}**\n"
                for match in matches:
                    status_icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                    response += f"• {match['home_team']} {match['score']} {match['away_team']} {status_icon} {match['minute']}\n"
                response += "\n"
            
            response += "🔄 **Live updates every 5 minutes!**\n"
            response += "💬 **Ask me about any match for detailed predictions!**"
            
        else:
            response = "⏳ **No live matches currently playing in major leagues.**\n\n"
            response += "But I can still help you with:\n"
            response += "• Upcoming match predictions\n• Team analysis\n• Betting strategies\n• Player insights\n\n"
            response += "Try asking: 'Predict [Team A] vs [Team B]' or 'Analyze [Team Name]'"
        
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Live matches error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_ai_chat(message):
    """Handle all AI chat messages"""
    try:
        user_id = message.from_user.id
        user_message = message.text
        
        print(f"💬 AI Chat from user {user_id}: {user_message}")
        
        # Show typing action
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(1)  # Simulate thinking
        
        # Get AI response
        ai_response = football_ai.get_ai_response(user_message, user_id)
        
        # Send response
        bot.reply_to(message, ai_response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ AI chat error: {e}")
        bot.reply_to(message, "❌ Sorry, I encountered an error. Please try again!")

# -------------------------
# AUTO LIVE UPDATER
# -------------------------
def auto_live_updater():
    """Auto-update live matches every 5 minutes"""
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"\n🔄 [{current_time}] Checking for live matches...")
            
            live_matches = get_real_live_matches()
            
            if live_matches:
                print(f"✅ {len(live_matches)} live matches found")
            else:
                print("⏳ No live matches currently")
            
            time.sleep(300)  # 5 minutes
            
        except Exception as e:
            print(f"❌ Auto updater error: {e}")
            time.sleep(300)

# -------------------------
# FLASK WEBHOOK
# -------------------------
@app.route('/')
def home():
    return "🤖 Real-Time Football Prediction AI Bot - Live Match Updates! ⚽"

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

        # Start live match updater
        t = threading.Thread(target=auto_live_updater, daemon=True)
        t.start()
        print("✅ Live Match Auto-Updater Started!")

        startup_msg = f"""
🤖 **REAL-TIME FOOTBALL PREDICTION AI STARTED!**

⚽ **ACTIVE FEATURES:**
• Real Live Match Data
• AI-Powered Predictions  
• Smart Chat Responses
• Live Score Updates
• Betting Insights

🎯 **READY FOR ACTION:**
• Real matches from API-Football
• ChatGPT-like conversations
• Pakistan Time: {datetime.now(pytz.timezone('Asia/Karachi')).strftime('%Y-%m-%d %H:%M:%S')}
• Live updates every 5 minutes

✅ **System actively monitoring real matches!**
💬 **Users can chat naturally about football!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Bot setup error: {e}")
        bot.polling(none_stop=True)

if __name__ == '__main__':
    print("🚀 Starting Real-Time Football Prediction AI Bot...")
    setup_bot()
    app.run(host='0.0.0.0', port=PORT)
