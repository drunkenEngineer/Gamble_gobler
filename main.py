import discord
from discord.ext import commands
import os
from datetime import datetime, timedelta
import asyncio
from games.blackjack import Blackjack, BlackjackView
from games.roulette import Roulette
import random
from dotenv import load_dotenv
from keep_alive import keep_alive

# Load environment variables
load_dotenv()

# Bot configuration
COMMAND_PREFIX = '!'
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Dictionary to store user balances (you might want to use a database later)
user_balances = {}

# Default starting balance for new users
STARTING_BALANCE = 10000

# Add these dictionaries
work_cooldowns = {}
bank_balances = {}  # For money in the bank
cash_balances = {}  # For withdrawn money (can be robbed)
robbery_stats = {}  # For tracking robbery statistics
crime_cooldowns = {}  # For tracking crime and 97ab cooldowns
lottery_tickets = {}  # For storing lottery tickets
lottery_jackpot = 100000  # Starting jackpot
last_lottery_draw = None  # To track when the last draw was
LOTTERY_TICKET_PRICE = 100  # Price per ticket
rps_games = {}  # For storing active RPS games

# Rest of your bot code here...
# [Copy all the command functions and other code from your original bot.py]

# Keep the bot alive
keep_alive()

# Run the bot using the token from environment variable
bot.run(os.getenv('DISCORD_TOKEN')) 