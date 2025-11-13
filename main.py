@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 Hello! Welcome to Football Bot ⚽

"
        "I can help you track live football matches, upcoming games, and provide predictions.

"
        "Use these commands to get started:
"
        "/live - Show live matches now
"
        "/upcoming - See upcoming matches
"
        "/predict - Get match predictions
"
        "/stats - View bot statistics

"
        "Enjoy! If you need help, just type /help again."
    )
    bot.reply_to(message, welcome_text)
