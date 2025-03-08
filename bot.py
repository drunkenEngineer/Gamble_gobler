import discord
from discord.ext import commands
import os
from datetime import datetime, timedelta
import asyncio
from games.blackjack import Blackjack, BlackjackView
from games.roulette import Roulette
import random
from dotenv import load_dotenv

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

# Add this dictionary to store work cooldowns
work_cooldowns = {}

# Add these dictionaries after your existing ones
bank_balances = {}  # For money in the bank
cash_balances = {}  # For withdrawn money (can be robbed)
robbery_stats = {}  # For tracking robbery statistics
crime_cooldowns = {}  # For tracking crime and 97ab cooldowns
lottery_tickets = {}  # For storing lottery tickets
lottery_jackpot = 100000  # Starting jackpot
last_lottery_draw = None  # To track when the last draw was
LOTTERY_TICKET_PRICE = 100  # Price per ticket
rps_games = {}  # For storing active RPS games

load_dotenv()

# Add this helper function at the top of the file, after the dictionaries
def initialize_user_balances(user_id: str):
    if user_id not in cash_balances:
        cash_balances[user_id] = STARTING_BALANCE
        bank_balances[user_id] = 0
        user_balances[user_id] = 0
    return cash_balances[user_id], bank_balances[user_id]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    bot.loop.create_task(lottery_draw_loop())

@bot.command(name='balance')
async def balance(ctx):
    user_id = str(ctx.author.id)
    
    # Initialize balances if they don't exist
    if user_id not in cash_balances:
        cash_balances[user_id] = user_balances.get(user_id, STARTING_BALANCE)
        bank_balances[user_id] = 0
        user_balances[user_id] = 0

    embed = discord.Embed(
        title="💰 Your Balances",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash", value=f"${cash_balances[user_id]}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${bank_balances[user_id]}", inline=True)
    embed.add_field(name="💳 Total", value=f"${cash_balances[user_id] + bank_balances[user_id]}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='blackjack', aliases=['bj'])
async def blackjack(ctx, bet: str = None):
    user_id = str(ctx.author.id)
    
    # Initialize balances first
    cash_balance, _ = initialize_user_balances(user_id)
    
    if bet is None:
        embed = discord.Embed(
            title="ℹ️ Blackjack Help",
            description="To play blackjack, you need to specify a bet amount.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value="!blackjack <bet_amount>\nor\n!bj <bet_amount>\nor\n!blackjack all",
            inline=False
        )
        embed.add_field(
            name="Example",
            value="!blackjack 100\n!blackjack all",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # Handle 'all' case
    if bet.lower() == 'all':
        bet = cash_balance
    else:
        try:
            bet = int(bet)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet amount must be a number or 'all'!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    
    if bet > cash_balance:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You need ${bet} in cash, but you only have ${cash_balance}!\nWithdraw from your bank first!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    if bet <= 0:
        embed = discord.Embed(
            title="❌ Invalid Bet",
            description="Bet amount must be greater than 0!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    # Initialize game
    game = Blackjack(bot)
    player_hand = [game.deck.pop(), game.deck.pop()]
    dealer_hand = [game.deck.pop(), game.deck.pop()]
    
    # Create view with buttons and pass user_balances
    view = BlackjackView(game, player_hand, dealer_hand, bet, user_id, user_balances)
    
    # Show initial hands
    embed = game.create_game_embed(
        player_hand, 
        dealer_hand, 
        bet=bet,
        balance=user_balances[user_id]  # Show initial balance
    )
    game_message = await ctx.send(embed=embed, view=view)
    
    # Wait for the view to timeout or the game to end
    await view.wait()
    
    if not view.ended:
        for child in view.children:
            child.disabled = True
        timeout_embed = discord.Embed(
            title="⏰ Game Timed Out",
            description="No action taken for 30 seconds",
            color=discord.Color.light_grey()
        )
        await game_message.edit(embed=timeout_embed, view=view)

@bot.command(name='roulette', aliases=['rl'])
async def roulette(ctx, bet_value: str = None, amount: str = None):
    user_id = str(ctx.author.id)
    
    # Initialize balances
    cash_balance, _ = initialize_user_balances(user_id)
    
    # Show help if parameters are missing
    if None in (bet_value, amount):
        embed = discord.Embed(
            title="ℹ️ Roulette Help",
            description="Place your bets on the roulette table!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value="!roulette <number/color> <bet>\n!roulette <number/color> all",
            inline=False
        )
        embed.add_field(
            name="Examples",
            value="!roulette red 100\n!roulette 7 50\n!roulette black all",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # Handle 'all' case
    if amount.lower() == 'all':
        bet = cash_balance
    else:
        try:
            bet = int(amount)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet amount must be a number or 'all'!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
    if bet > cash_balance:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You need ${bet:,} in cash, but you only have ${cash_balance:,}!\nWithdraw from your bank first!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
        
    if bet <= 0:
        embed = discord.Embed(
            title="❌ Invalid Bet",
            description="Bet amount must be greater than 0!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Check if bet is on color or number
    if bet_value.lower() in ['red', 'black']:
        bet_type = 'color'
    elif bet_value.isdigit() and 0 <= int(bet_value) <= 36:
        bet_type = 'number'
    else:
        embed = discord.Embed(
            title="❌ Invalid Bet",
            description="Bet must be a color (red/black) or number (0-36)!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
        
    game = Roulette(bot)
    result = game.spin()
    won, multiplier = game.check_bet(bet_type, bet_value, result)
    
    # Update cash balance
    if won:
        cash_balances[user_id] += bet * multiplier
        embed = discord.Embed(
            title="🎰 You Won!",
            description=f"Ball landed on {result}!\nYou won ${bet * multiplier}!",
            color=discord.Color.green()
        )
    else:
        cash_balances[user_id] -= bet
        embed = discord.Embed(
            title="😢 You Lost!",
            description=f"Ball landed on {result}!\nYou lost ${bet}!",
            color=discord.Color.red()
        )
    
    embed.add_field(
        name="💰 New Cash Balance",
        value=f"${cash_balances[user_id]}",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='dice')
async def dice(ctx, bet: str = None, number: str = None):
    user_id = str(ctx.author.id)
    
    # Initialize balances
    cash_balance, _ = initialize_user_balances(user_id)
    
    # Show help if parameters are missing
    if None in (bet, number):
        embed = discord.Embed(
            title="🎲 Dice Help",
            description="Bet on a dice roll (1-6)!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value="!dice <bet_amount> <number>",
            inline=False
        )
        embed.add_field(
            name="Example",
            value="!dice 1000 6\n!dice all 3",
            inline=False
        )
        embed.add_field(
            name="Payout",
            value="Win: 5x your bet\nLose: Lose your bet",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # Handle 'all' case
    if bet.lower() == 'all':
        bet = cash_balance
    else:
        try:
            bet = int(bet)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet amount must be a number or 'all'!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

    # Validate bet amount
    if bet <= 0:
        embed = discord.Embed(
            title="❌ Invalid Bet",
            description="Bet amount must be greater than 0!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if bet > cash_balance:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You need ${bet:,} in cash, but you only have ${cash_balance:,}!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Validate number
    try:
        chosen_number = int(number)
        if not 1 <= chosen_number <= 6:
            raise ValueError
    except ValueError:
        embed = discord.Embed(
            title="❌ Invalid Number",
            description="Please choose a number between 1 and 6!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Roll the dice
    roll = random.randint(1, 6)
    
    # Create suspense message
    embed = discord.Embed(
        title="🎲 Rolling the Dice...",
        description="The dice is rolling...",
        color=discord.Color.gold()
    )
    message = await ctx.send(embed=embed)
    
    # Add suspense delay
    await asyncio.sleep(2)
    
    # Check result
    if roll == chosen_number:
        winnings = bet * 5
        cash_balances[user_id] += winnings - bet  # Subtract original bet since we're adding total winnings
        
        embed = discord.Embed(
            title="🎲 You Won!",
            description=f"The dice rolled a {roll}!\nYou won ${winnings:,}!",
            color=discord.Color.green()
        )
    else:
        cash_balances[user_id] -= bet
        
        embed = discord.Embed(
            title="🎲 You Lost!",
            description=f"The dice rolled a {roll}!\nYou lost ${bet:,}!",
            color=discord.Color.red()
        )
    
    embed.add_field(
        name="💰 New Balance",
        value=f"${cash_balances[user_id]:,}",
        inline=False
    )
    
    await message.edit(embed=embed)

@bot.command(name='leaderboard', aliases=['lb'])
async def leaderboard(ctx):
    # Calculate total wealth for each user (cash + bank)
    total_wealth = {}
    
    # Get all users who have interacted with the bot
    all_users = set(cash_balances.keys()) | set(bank_balances.keys())
    
    # Calculate wealth for each user
    for user_id in all_users:
        cash = cash_balances.get(user_id, 0)
        bank = bank_balances.get(user_id, 0)
        total_wealth[user_id] = cash + bank

    # Sort users by total wealth
    sorted_users = sorted(total_wealth.items(), key=lambda x: x[1], reverse=True)
    
    # Calculate total pages (10 users per page)
    users_per_page = 10
    total_pages = max(1, (len(sorted_users) + users_per_page - 1) // users_per_page)

    class LeaderboardView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.current_page = 1

        async def get_page_embed(self):
            start_idx = (self.current_page - 1) * users_per_page
            end_idx = start_idx + users_per_page
            current_page_users = sorted_users[start_idx:end_idx]

            embed = discord.Embed(
                title="💎 Richest Players",
                description=f"Page {self.current_page} of {total_pages}",
                color=discord.Color.gold()
            )

            for position, (user_id, wealth) in enumerate(current_page_users, start=start_idx + 1):
                try:
                    # Try to get member from guild first
                    member = ctx.guild.get_member(int(user_id))
                    if member is None:
                        # If not found in guild, try to fetch user
                        user = await bot.fetch_user(int(user_id))
                        username = user.name if user else "Unknown User"
                    else:
                        username = member.name
                    
                    if position == 1:
                        medal = "🥇"
                    elif position == 2:
                        medal = "🥈"
                    elif position == 3:
                        medal = "🥉"
                    else:
                        medal = "💰"
                    
                    embed.add_field(
                        name=f"{medal} #{position} - {username}",
                        value=f"${wealth:,}",
                        inline=False
                    )
                except Exception as e:
                    print(f"Error fetching user {user_id}: {e}")
                    continue

            return embed

        @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray, disabled=True)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You can't use these buttons!", ephemeral=True)
                return

            # Add delay
            await asyncio.sleep(0.5)

            self.current_page = max(1, self.current_page - 1)
            
            # Update button states
            self.previous_button.disabled = self.current_page == 1
            self.next_button.disabled = self.current_page == total_pages
            
            await interaction.response.edit_message(embed=await self.get_page_embed(), view=self)

        @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.gray)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You can't use these buttons!", ephemeral=True)
                return

            # Add delay
            await asyncio.sleep(0.5)

            self.current_page = min(total_pages, self.current_page + 1)
            
            # Update button states
            self.previous_button.disabled = self.current_page == 1
            self.next_button.disabled = self.current_page == total_pages
            
            await interaction.response.edit_message(embed=await self.get_page_embed(), view=self)

        async def on_timeout(self):
            # Disable all buttons when the view times out
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass

    # Create and send the initial view
    view = LeaderboardView()
    view.next_button.disabled = total_pages == 1
    message = await ctx.send(embed=await view.get_page_embed(), view=view)
    view.message = message

@bot.command(name='money', aliases=['bal'])
async def money(ctx):
    user_id = str(ctx.author.id)
    
    # Initialize balances if they don't exist
    cash_balance, bank_balance = initialize_user_balances(user_id)
    total = cash_balance + bank_balance

    # Get user's rank
    total_wealth = {}
    for uid in set(cash_balances.keys()) | set(bank_balances.keys()):
        total_wealth[uid] = cash_balances.get(uid, 0) + bank_balances.get(uid, 0)
    
    sorted_users = sorted(total_wealth.items(), key=lambda x: x[1], reverse=True)
    rank = next(i for i, (uid, _) in enumerate(sorted_users, 1) if uid == user_id)

    embed = discord.Embed(
        title=f"💰 {ctx.author.name}'s Money",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash", value=f"${cash_balance:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${bank_balance:,}", inline=True)
    embed.add_field(name="💳 Total", value=f"${total:,}", inline=False)
    embed.add_field(name="📊 Rank", value=f"#{rank}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='work')
async def work(ctx):
    user_id = str(ctx.author.id)
    current_time = datetime.now()
    
    # Initialize user balance if not exists
    if user_id not in user_balances:
        user_balances[user_id] = STARTING_BALANCE
    
    # Check cooldown
    if user_id in work_cooldowns:
        time_diff = current_time - work_cooldowns[user_id]
        if time_diff < timedelta(hours=1):
            remaining = timedelta(hours=1) - time_diff
            minutes = int(remaining.total_seconds() / 60)
            embed = discord.Embed(
                title="⏳ Work Cooldown",
                description=f"You need to wait {minutes} minutes before working again!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    
    # Generate random earnings
    earnings = random.randint(1000, 5000)
    user_balances[user_id] += earnings
    
    # Set cooldown
    work_cooldowns[user_id] = current_time
    
    # Create list of work messages
    work_messages = [
        f"You worked as a casino dealer and earned ${earnings}! 🎰",
        f"You helped count cards (legally) and earned ${earnings}! 🃏",
        f"You maintained slot machines and earned ${earnings}! 🎮",
        f"You served drinks at the casino and earned ${earnings}! 🍷",
        f"You worked as a security guard and earned ${earnings}! 👮",
        f"You cleaned the casino floor and earned ${earnings}! 🧹",
        f"You worked as a valet parker and earned ${earnings}! 🚗",
        f"You entertained guests as a performer and earned ${earnings}! 🎭",
        f"You worked as a cashier and earned ${earnings}! 💰",
        f"You gave casino tours and earned ${earnings}! 🎪"
    ]
    
    # Create and send embed
    embed = discord.Embed(
        title="💼 Work Complete!",
        description=random.choice(work_messages),
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="💳 New Balance",
        value=f"${user_balances[user_id]}",
        inline=False
    )
    
    embed.add_field(
        name="⏰ Next Work Available",
        value="In 1 hour",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='crime')
async def crime(ctx):
    user_id = str(ctx.author.id)
    current_time = datetime.now()
    
    # Initialize user balance if not exists
    cash_balance, _ = initialize_user_balances(user_id)
    
    # Check cooldown
    if user_id in crime_cooldowns:
        time_diff = current_time - crime_cooldowns[user_id]
        if time_diff < timedelta(hours=1):
            remaining = timedelta(hours=1) - time_diff
            minutes = int(remaining.total_seconds() / 60)
            embed = discord.Embed(
                title="⏳ Crime Cooldown",
                description=f"You need to wait {minutes} minutes before committing another crime!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    
    # 20% success rate
    if random.random() <= 0.20:  # Success
        earnings = random.randint(30000, 50000)
        cash_balances[user_id] += earnings
        
        # Create list of success messages
        success_messages = [
            f"You successfully robbed a high-security vault and got ${earnings:,}! 🏦",
            f"You pulled off a casino heist and earned ${earnings:,}! 🎰",
            f"You hacked into an offshore account and transferred ${earnings:,}! 💻",
            f"You successfully counterfeited money and made ${earnings:,}! 💵",
            f"You orchestrated a high-stakes jewelry theft and got ${earnings:,}! 💎",
            f"You ran an elaborate ponzi scheme and earned ${earnings:,}! 📈",
            f"You successfully smuggled contraband and earned ${earnings:,}! 📦",
            f"You pulled off an art gallery heist and got ${earnings:,}! 🎨"
        ]
        
        embed = discord.Embed(
            title="🦹‍♂️ Crime Successful!",
            description=random.choice(success_messages),
            color=discord.Color.green()
        )
        
    else:  # Failure
        fine = 10000
        cash_balances[user_id] -= fine
        
        # Create list of failure messages
        failure_messages = [
            "You got caught by security cameras! 📸",
            "A witness reported you to the police! 👮",
            "Your getaway driver abandoned you! 🚗",
            "Your inside man was an undercover cop! 🚔",
            "The silent alarm was triggered! 🚨",
            "Your fake ID didn't work! 🪪",
            "You left fingerprints everywhere! 👆",
            "Your hacking attempt was traced! 💻"
        ]
        
        embed = discord.Embed(
            title="🚔 Crime Failed!",
            description=f"{random.choice(failure_messages)}\nYou were fined ${fine:,}!",
            color=discord.Color.red()
        )
    
    # Set cooldown
    crime_cooldowns[user_id] = current_time
    
    embed.add_field(
        name="💰 New Balance",
        value=f"${cash_balances[user_id]:,}",
        inline=False
    )
    
    embed.add_field(
        name="⏰ Next Crime Available",
        value="In 1 hour",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='97ab')
async def adult_work(ctx):
    user_id = str(ctx.author.id)
    current_time = datetime.now()
    
    # Initialize user balance if not exists
    cash_balance, _ = initialize_user_balances(user_id)
    
    # Check cooldown
    if user_id in crime_cooldowns:
        time_diff = current_time - crime_cooldowns[user_id]
        if time_diff < timedelta(hours=1):
            remaining = timedelta(hours=1) - time_diff
            minutes = int(remaining.total_seconds() / 60)
            embed = discord.Embed(
                title="⏳ Cooldown",
                description=f"You need to wait {minutes} minutes before working again!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    
    # Random number for outcome
    chance = random.random()
    
    if chance <= 0.20:  # 20% chance for original easter egg
        earnings = random.randint(10, 100)
        cash_balances[user_id] += earnings
        
        embed = discord.Embed(
            title="97ba rkhisa ajomi",
            description=f"You found ${earnings:,}! 💸",
            color=discord.Color.green()
        )
    
    elif chance <= 0.60:  # 40% chance for first new outcome
        embed = discord.Embed(
            title="7wak o hrob a jomi",
            description="You got nothing! 🏃‍♂️",
            color=discord.Color.red()
        )
        
    else:  # 40% chance for second new outcome
        earnings = 50
        cash_balances[user_id] += earnings
        
        embed = discord.Embed(
            title="rgadti b alf",
            description=f"You got ${earnings}! 💰",
            color=discord.Color.green()
        )
    
    # Set cooldown
    crime_cooldowns[user_id] = current_time
    
    embed.add_field(
        name="💰 New Balance",
        value=f"${cash_balances[user_id]:,}",
        inline=False
    )
    
    embed.add_field(
        name="⏰ Next Work Available",
        value="In 1 hour",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='nextwork')
async def nextwork(ctx):
    user_id = str(ctx.author.id)
    
    if user_id not in work_cooldowns:
        embed = discord.Embed(
            title="✅ Work Available!",
            description="You can work right now! Use !work to earn money.",
            color=discord.Color.green()
        )
    else:
        current_time = datetime.now()
        time_diff = current_time - work_cooldowns[user_id]
        
        if time_diff >= timedelta(hours=1):
            embed = discord.Embed(
                title="✅ Work Available!",
                description="You can work right now! Use !work to earn money.",
                color=discord.Color.green()
            )
        else:
            remaining = timedelta(hours=1) - time_diff
            minutes = int(remaining.total_seconds() / 60)
            embed = discord.Embed(
                title="⏳ Work Cooldown",
                description=f"You need to wait {minutes} minutes before working again!",
                color=discord.Color.gold()
            )
    
    await ctx.send(embed=embed)

@bot.command(name='botm9wd', aliases=['commands', 'menu'])
async def botm9wd_help(ctx):
    embed = discord.Embed(
        title="🎰 Casino Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.blue()
    )
    
    # Banking Commands
    embed.add_field(
        name="🏦 Banking",
        value=(
            "**!deposit/!dep <amount>** - Deposit cash to your bank (safe from robbery)\n"
            "**!withdraw/!with <amount>** - Withdraw cash from your bank\n"
            "**!pay <@user> <amount>** - Pay another player from your cash\n"
            "**!money/!bal** - Check your balances and rank\n"
            "**!rob <@user>** - Rob someone's cash"
        ),
        inline=False
    )
    
    # Games Commands
    embed.add_field(
        name="🎮 Games",
        value=(
            "**!blackjack/!bj <bet>** - Play blackjack\n"
            "**!roulette/!rl <number/color> <bet>** - Play roulette\n"
            "**!dice <bet> <number>** - Bet on a dice roll (1-6)\n"
            "**!rps @player <bet>** - Challenge someone to Rock Paper Scissors\n"
            "**!lottery/!lot** - View lottery status\n"
            "**!lottery buy <amount>** - Buy lottery tickets\n"
            "**!lottery numbers** - View your tickets\n"
            "• Use 'all' to bet all your cash\n"
            "• Roulette: bet on numbers (0-36) or colors (red/black)\n"
            "• Dice: Win 5x your bet if you guess right\n"
            "• Lottery draws happen daily with growing jackpot"
        ),
        inline=False
    )
    
    # Economy Commands
    embed.add_field(
        name="💰 Economy",
        value=(
            "**!work** - Work to earn money (1-hour cooldown)\n"
            "**!nextwork** - Check when you can work again\n"
            "**!crime** - Commit a crime (high risk/reward, 1h cooldown)\n"
            "**!97ab** - Special work (1h cooldown)\n"
            "**!leaderboard/!lb** - View richest players"
        ),
        inline=False
    )
    
    # Additional Information
    embed.add_field(
        name="💡 Tips",
        value=(
            "• Starting balance: $10,000\n"
            "• Work earns $1,000-$5,000\n"
            "• Crime earns $30,000-$50,000\n"
            "• Failed robbery: 30% fine of total balance\n"
            "• Successful robbery: 60-100% of target's cash"
        ),
        inline=False
    )
    
    embed.set_footer(text="Use !botm9wd, !commands, or !menu to see this menu again")
    
    await ctx.send(embed=embed)

@bot.command(name='deposit', aliases=['dep'])
async def deposit(ctx, amount: str = None):
    user_id = str(ctx.author.id)
    
    # Initialize balances if they don't exist
    cash_balance, bank_balance = initialize_user_balances(user_id)

    if amount is None:
        embed = discord.Embed(
            title="ℹ️ Deposit Help",
            description="Deposit your cash into the bank for safekeeping.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Usage", value="!deposit <amount>\n!deposit all", inline=False)
        embed.add_field(name="Examples", value="!deposit 1000\n!deposit all", inline=False)
        await ctx.send(embed=embed)
        return

    # Check if user has any cash first
    if cash_balance <= 0:
        embed = discord.Embed(
            title="❌ No Cash to Deposit",
            description=f"You have no cash to deposit!\nYour bank balance: ${bank_balance:,}\n\nUse `!withdraw <amount>` or `!with <amount>` to withdraw money from your bank.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Handle 'all' case
    if amount.lower() == 'all':
        amount = cash_balance
    else:
        try:
            amount = int(amount)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be a number or 'all'!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

    if amount <= 0:
        embed = discord.Embed(
            title="❌ Invalid Amount",
            description="Amount must be greater than 0!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if amount > cash_balance:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You only have ${cash_balance:,} in cash!\nYour bank balance: ${bank_balance:,}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Process deposit
    cash_balances[user_id] -= amount
    bank_balances[user_id] += amount

    embed = discord.Embed(
        title="💰 Deposit Successful",
        description=f"Deposited ${amount:,} into your bank account!",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash Balance", value=f"${cash_balances[user_id]:,}", inline=True)
    embed.add_field(name="🏦 Bank Balance", value=f"${bank_balances[user_id]:,}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='withdraw', aliases=['with'])
async def withdraw(ctx, amount: str = None):
    user_id = str(ctx.author.id)
    
    # Initialize balances if they don't exist
    cash_balance, bank_balance = initialize_user_balances(user_id)

    if amount is None:
        embed = discord.Embed(
            title="ℹ️ Withdraw Help",
            description="Withdraw money from your bank account.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Usage", value="!withdraw <amount>\n!withdraw all", inline=False)
        embed.add_field(name="Examples", value="!withdraw 1000\n!withdraw all", inline=False)
        await ctx.send(embed=embed)
        return

    # Handle 'all' case
    if amount.lower() == 'all':
        amount = bank_balance
    else:
        try:
            amount = int(amount)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be a number or 'all'!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

    if amount <= 0:
        embed = discord.Embed(
            title="❌ Invalid Amount",
            description="Amount must be greater than 0!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if amount > bank_balance:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have ${bank_balance} in your bank account!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Process withdrawal
    bank_balances[user_id] -= amount
    cash_balances[user_id] += amount

    embed = discord.Embed(
        title="💸 Withdrawal Successful",
        description=f"Withdrew ${amount} from your bank account!",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash Balance", value=f"${cash_balances[user_id]}", inline=True)
    embed.add_field(name="🏦 Bank Balance", value=f"${bank_balances[user_id]}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='chfara')
async def chfara(ctx, page: int = 1):
    user_id = str(ctx.author.id)
    
    # Initialize stats if they don't exist
    if user_id not in robbery_stats:
        robbery_stats[user_id] = {
            'total_stolen': 0,
            'successful_robberies': 0,
            'failed_robberies': 0
        }
    
    # Sort users by total amount stolen
    sorted_robbers = sorted(robbery_stats.items(), key=lambda x: x[1]['total_stolen'], reverse=True)
    
    # Calculate total pages (10 users per page)
    users_per_page = 10
    total_pages = max(1, (len(sorted_robbers) + users_per_page - 1) // users_per_page)

    class RobberyStatsView(discord.ui.View):
        def __init__(self, user_id: str):
            super().__init__(timeout=60)
            self.current_page = page
            self.user_id = user_id

        async def get_page_embed(self):
            # Validate page number
            self.current_page = max(1, min(self.current_page, total_pages))
            
            # Get user's rank
            user_rank = next((i for i, (uid, _) in enumerate(sorted_robbers, 1) if uid == self.user_id), len(sorted_robbers))
            
            # Create embed
            embed = discord.Embed(
                title="🦹‍♂️ Master Thieves Leaderboard",
                description=f"Page {self.current_page} of {total_pages}",
                color=discord.Color.gold()
            )
            
            # Add user's personal stats first
            user_stats = robbery_stats[self.user_id]
            
            embed.add_field(
                name="📊 Your Robbery Stats",
                value=(
                    f"Rank: #{user_rank}\n"
                    f"Total Stolen: ${user_stats['total_stolen']:,}"
                ),
                inline=False
            )
            
            # Calculate start and end indices for current page
            start_idx = (self.current_page - 1) * users_per_page
            end_idx = start_idx + users_per_page
            current_page_users = sorted_robbers[start_idx:end_idx]
            
            # Add leaderboard
            embed.add_field(
                name="🏆 Top Robbers",
                value="Ranked by total amount stolen:",
                inline=False
            )
            
            for position, (user_id, stats) in enumerate(current_page_users, start=start_idx + 1):
                try:
                    # Try to get member from guild first
                    member = ctx.guild.get_member(int(user_id))
                    if member is None:
                        # If not found in guild, try to fetch user
                        user = await bot.fetch_user(int(user_id))
                        username = user.name if user else "Unknown User"
                    else:
                        username = member.name
                    
                    if position == 1:
                        medal = "🥇"
                    elif position == 2:
                        medal = "🥈"
                    elif position == 3:
                        medal = "🥉"
                    else:
                        medal = "💰"
                    
                    embed.add_field(
                        name=f"{medal} #{position} - {username}",
                        value=f"Total Stolen: ${stats['total_stolen']:,}",
                        inline=False
                    )
                except Exception as e:
                    print(f"Error fetching user {user_id}: {e}")
                    continue
            
            return embed

        @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray, disabled=True)
        async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You can't use these buttons!", ephemeral=True)
                return

            # Add delay
            await asyncio.sleep(0.5)

            self.current_page = max(1, self.current_page - 1)
            
            # Update button states
            self.previous_button.disabled = self.current_page == 1
            self.next_button.disabled = self.current_page == total_pages
            
            await interaction.response.edit_message(embed=await self.get_page_embed(), view=self)

        @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.gray)
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != ctx.author:
                await interaction.response.send_message("You can't use these buttons!", ephemeral=True)
                return

            # Add delay
            await asyncio.sleep(0.5)

            self.current_page = min(total_pages, self.current_page + 1)
            
            # Update button states
            self.previous_button.disabled = self.current_page == 1
            self.next_button.disabled = self.current_page == total_pages
            
            await interaction.response.edit_message(embed=await self.get_page_embed(), view=self)

        async def on_timeout(self):
            # Disable all buttons when the view times out
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass

    # Create and send the initial view
    view = RobberyStatsView(user_id)
    view.next_button.disabled = total_pages == 1
    message = await ctx.send(embed=await view.get_page_embed(), view=view)
    view.message = message

@bot.command(name='rob')
async def rob(ctx, target: discord.Member = None):
    if target is None:
        embed = discord.Embed(
            title="ℹ️ Rob Help",
            description="Rob another player's cash!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value="!rob @username",
            inline=False
        )
        embed.add_field(
            name="Example",
            value="!rob @JohnDoe",
            inline=False
        )
        embed.add_field(
            name="Stats",
            value="Use !chfara to view robbery statistics!",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    robber_id = str(ctx.author.id)
    target_id = str(target.id)
    
    # Initialize stats if they don't exist
    if robber_id not in robbery_stats:
        robbery_stats[robber_id] = {
            'total_stolen': 0,
            'successful_robberies': 0,
            'failed_robberies': 0
        }
    
    # Initialize balances for both robber and target
    robber_cash, robber_bank = initialize_user_balances(robber_id)
    target_cash, _ = initialize_user_balances(target_id)

    # Can't rob yourself
    if robber_id == target_id:
        embed = discord.Embed(
            title="🤦‍♂️ Bruh",
            description="You can't rob yourself!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Check if target has cash to steal
    if target_cash <= 0:
        robbery_stats[robber_id]['failed_robberies'] += 1
        embed = discord.Embed(
            title="😅 Failed Robbery",
            description=f"{target.mention} has no cash to steal!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # 20% chance of getting caught
    if random.random() < 0.2:
        robbery_stats[robber_id]['failed_robberies'] += 1
        # Calculate fine (30% of total balance)
        total_balance = robber_cash + robber_bank
        fine = int(total_balance * 0.3)
        
        # If robber has no cash, make balance negative
        if robber_cash < fine:
            cash_balances[robber_id] = -fine
        else:
            cash_balances[robber_id] -= fine

        embed = discord.Embed(
            title="🚔 Caught in the Act!",
            description=f"You were caught trying to rob {target.mention}!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="💰 Fine",
            value=f"You were fined ${fine:,}!",
            inline=False
        )
        embed.add_field(
            name="💵 New Cash Balance",
            value=f"${cash_balances[robber_id]:,}",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # Successful robbery (80% chance)
    robbery_stats[robber_id]['successful_robberies'] += 1
    percentage = random.uniform(0.6, 1.0)
    stolen_amount = int(target_cash * percentage)
    cash_balances[target_id] -= stolen_amount
    cash_balances[robber_id] += stolen_amount
    
    # Update robbery stats
    robbery_stats[robber_id]['total_stolen'] += stolen_amount

    embed = discord.Embed(
        title="🦹‍♂️ Successful Robbery!",
        description=f"You stole ${stolen_amount:,} from {target.mention}!",
        color=discord.Color.green()
    )
    embed.add_field(
        name="💰 Your New Cash Balance",
        value=f"${cash_balances[robber_id]:,}",
        inline=False
    )
    embed.add_field(
        name="📊 Total Amount Stolen",
        value=f"${robbery_stats[robber_id]['total_stolen']:,}",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='pay')
async def pay(ctx, target: discord.Member = None, amount: str = None):
    if target is None or amount is None:
        embed = discord.Embed(
            title="ℹ️ Pay Help",
            description="Pay another player from your cash balance!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value="!pay @username <amount>\n!pay @username all",
            inline=False
        )
        embed.add_field(
            name="Example",
            value="!pay @JohnDoe 1000\n!pay @JohnDoe all",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    payer_id = str(ctx.author.id)
    receiver_id = str(target.id)
    
    # Initialize balances for both users
    payer_cash, _ = initialize_user_balances(payer_id)
    receiver_cash, _ = initialize_user_balances(receiver_id)

    # Can't pay yourself
    if payer_id == receiver_id:
        embed = discord.Embed(
            title="🤦‍♂️ Bruh",
            description="You can't pay yourself!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Handle 'all' case
    if amount.lower() == 'all':
        amount = payer_cash
    else:
        try:
            amount = int(amount)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be a number or 'all'!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

    if amount <= 0:
        embed = discord.Embed(
            title="❌ Invalid Amount",
            description="Amount must be greater than 0!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if amount > payer_cash:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You only have ${payer_cash} in cash!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Process payment
    cash_balances[payer_id] -= amount
    cash_balances[receiver_id] += amount

    embed = discord.Embed(
        title="💸 Payment Successful",
        description=f"You paid ${amount} to {target.mention}!",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Your New Cash Balance", value=f"${cash_balances[payer_id]}", inline=True)
    embed.add_field(name="💰 Their New Cash Balance", value=f"${cash_balances[receiver_id]}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='lottery', aliases=['lot'])
async def lottery(ctx, action: str = None, amount: str = None):
    global lottery_jackpot, last_lottery_draw  # Move global declaration to top of function
    
    user_id = str(ctx.author.id)
    current_time = datetime.now()
    
    # Initialize user balance if not exists
    cash_balance, _ = initialize_user_balances(user_id)
    
    # Initialize lottery tickets for user if not exists
    if user_id not in lottery_tickets:
        lottery_tickets[user_id] = []
    
    if action is None:
        # Show lottery status
        if last_lottery_draw is None:
            next_draw = "First draw pending"
        else:
            time_until_draw = timedelta(days=1) - (current_time - last_lottery_draw)
            hours = int(time_until_draw.total_seconds() / 3600)
            minutes = int((time_until_draw.total_seconds() % 3600) / 60)
            next_draw = f"In {hours} hours and {minutes} minutes"
        
        embed = discord.Embed(
            title="🎟️ Lottery Status",
            description="Try your luck in the daily lottery!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🏆 Current Jackpot",
            value=f"${lottery_jackpot:,}",
            inline=False
        )
        embed.add_field(
            name="🎫 Your Tickets",
            value=f"You have {len(lottery_tickets[user_id])} tickets",
            inline=False
        )
        embed.add_field(
            name="⏰ Next Draw",
            value=next_draw,
            inline=False
        )
        embed.add_field(
            name="💰 Ticket Price",
            value=f"${LOTTERY_TICKET_PRICE} each",
            inline=False
        )
        embed.add_field(
            name="Commands",
            value="!lottery buy <amount>\n!lottery numbers",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    if action.lower() == 'buy':
        if amount is None:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Please specify how many tickets to buy!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        try:
            num_tickets = int(amount)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be a number!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        total_cost = num_tickets * LOTTERY_TICKET_PRICE
        
        if total_cost > cash_balance:
            embed = discord.Embed(
                title="❌ Insufficient Cash",
                description=f"You need ${total_cost:,} to buy {num_tickets} tickets!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Generate tickets
        new_tickets = [random.randint(1, 99) for _ in range(num_tickets)]
        lottery_tickets[user_id].extend(new_tickets)
        
        # Update balance and jackpot
        cash_balances[user_id] -= total_cost
        lottery_jackpot += total_cost // 2  # Half of ticket sales go to jackpot
        
        embed = discord.Embed(
            title="🎫 Tickets Purchased!",
            description=f"You bought {num_tickets} lottery tickets!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="🔢 Your New Numbers",
            value=", ".join(str(num) for num in new_tickets),
            inline=False
        )
        embed.add_field(
            name="💰 New Balance",
            value=f"${cash_balances[user_id]:,}",
            inline=False
        )
        await ctx.send(embed=embed)
        
    elif action.lower() == 'numbers':
        if not lottery_tickets[user_id]:
            embed = discord.Embed(
                title="❌ No Tickets",
                description="You don't have any lottery tickets!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🎫 Your Lottery Numbers",
            description="Here are all your active tickets:",
            color=discord.Color.blue()
        )
        
        # Split numbers into groups of 10 for readability
        chunks = [lottery_tickets[user_id][i:i + 10] for i in range(0, len(lottery_tickets[user_id]), 10)]
        for i, chunk in enumerate(chunks, 1):
            embed.add_field(
                name=f"Tickets {(i-1)*10 + 1}-{(i-1)*10 + len(chunk)}",
                value=", ".join(str(num) for num in chunk),
                inline=False
            )
        
        await ctx.send(embed=embed)

async def lottery_draw_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        current_time = datetime.now()
        global last_lottery_draw, lottery_jackpot
        
        # Initialize last_lottery_draw if it's None
        if last_lottery_draw is None:
            last_lottery_draw = current_time
            
        # Check if 24 hours have passed since last draw
        if current_time - last_lottery_draw >= timedelta(days=1):
            # Perform lottery draw
            winning_number = random.randint(1, 99)
            winners = []
            
            # Check all tickets
            for user_id, tickets in lottery_tickets.items():
                if winning_number in tickets:
                    winners.append(user_id)
            
            # Calculate prize
            if winners:
                prize_per_winner = lottery_jackpot // len(winners)
                # Pay winners
                for winner_id in winners:
                    cash_balances[winner_id] = cash_balances.get(winner_id, 0) + prize_per_winner
                    
                    try:
                        winner = await bot.fetch_user(int(winner_id))
                        embed = discord.Embed(
                            title="🎉 Lottery Winner!",
                            description=f"Congratulations! Your number {winning_number} won!",
                            color=discord.Color.gold()
                        )
                        embed.add_field(
                            name="💰 Prize",
                            value=f"${prize_per_winner:,}",
                            inline=False
                        )
                        await winner.send(embed=embed)
                    except:
                        pass  # In case DM fails
            
            # Reset lottery
            lottery_tickets.clear()
            lottery_jackpot = 100000  # Reset to starting jackpot
            last_lottery_draw = current_time
            
            # Announce results in all guilds
            for guild in bot.guilds:
                try:
                    embed = discord.Embed(
                        title="🎲 Daily Lottery Results",
                        description=f"The winning number was: {winning_number}",
                        color=discord.Color.blue()
                    )
                    
                    if winners:
                        winners_text = []
                        for winner_id in winners:
                            try:
                                winner = await bot.fetch_user(int(winner_id))
                                winners_text.append(winner.name)
                            except:
                                winners_text.append("Unknown User")
                        
                        embed.add_field(
                            name="🏆 Winners",
                            value="\n".join(winners_text),
                            inline=False
                        )
                        embed.add_field(
                            name="💰 Prize Per Winner",
                            value=f"${prize_per_winner:,}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="😢 No Winners",
                            value="Better luck next time!",
                            inline=False
                        )
                    
                    # Try to find a general channel to announce in
                    announcement_channel = None
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            announcement_channel = channel
                            break
                    
                    if announcement_channel:
                        await announcement_channel.send(embed=embed)
                except:
                    continue  # Skip if we can't announce in this guild
        
        # Wait for 1 hour before checking again
        await asyncio.sleep(3600)

class RPSView(discord.ui.View):
    def __init__(self, challenger, opponent, bet):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.challenger_choice = None
        self.opponent_choice = None
    
    @discord.ui.button(label="Rock 🪨", style=discord.ButtonStyle.gray)
    async def rock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "rock")
    
    @discord.ui.button(label="Paper 📄", style=discord.ButtonStyle.gray)
    async def paper_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "paper")
    
    @discord.ui.button(label="Scissors ✂️", style=discord.ButtonStyle.gray)
    async def scissors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "scissors")
    
    async def make_choice(self, interaction: discord.Interaction, choice):
        user_id = str(interaction.user.id)
        
        if user_id not in [str(self.challenger.id), str(self.opponent.id)]:
            await interaction.response.send_message("You're not part of this game!", ephemeral=True)
            return
        
        if user_id == str(self.challenger.id) and self.challenger_choice is None:
            self.challenger_choice = choice
            await interaction.response.send_message(f"You chose {choice}!", ephemeral=True)
        elif user_id == str(self.opponent.id) and self.opponent_choice is None:
            self.opponent_choice = choice
            await interaction.response.send_message(f"You chose {choice}!", ephemeral=True)
        else:
            await interaction.response.send_message("You've already made your choice!", ephemeral=True)
            return
        
        # If both players have made their choices, determine the winner
        if self.challenger_choice and self.opponent_choice:
            await self.end_game(interaction)
    
    async def end_game(self, interaction):
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        # Determine winner
        winner = None
        if self.challenger_choice == self.opponent_choice:
            result = "It's a tie!"
        else:
            winning_combinations = {
                "rock": "scissors",
                "paper": "rock",
                "scissors": "paper"
            }
            if winning_combinations[self.challenger_choice] == self.opponent_choice:
                winner = self.challenger
                result = f"{self.challenger.mention} wins!"
            else:
                winner = self.opponent
                result = f"{self.opponent.mention} wins!"
        
        # Create result embed
        embed = discord.Embed(
            title="🎮 Rock Paper Scissors Results",
            description=result,
            color=discord.Color.gold()
        )
        embed.add_field(
            name=f"{self.challenger.name}'s Choice",
            value=f"{self.challenger_choice.capitalize()} {self.get_emoji(self.challenger_choice)}",
            inline=True
        )
        embed.add_field(
            name=f"{self.opponent.name}'s Choice",
            value=f"{self.opponent_choice.capitalize()} {self.get_emoji(self.opponent_choice)}",
            inline=True
        )
        
        # Handle bet if there was one
        if self.bet > 0:
            challenger_id = str(self.challenger.id)
            opponent_id = str(self.opponent.id)
            
            if winner:
                winner_id = str(winner.id)
                loser_id = opponent_id if winner_id == challenger_id else challenger_id
                
                # Transfer money
                cash_balances[winner_id] += self.bet
                cash_balances[loser_id] -= self.bet
                
                embed.add_field(
                    name="💰 Bet Result",
                    value=f"{winner.name} won ${self.bet:,}!",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💰 Bet Result",
                    value="Tie game! No money exchanged.",
                    inline=False
                )
        
        await interaction.message.edit(embed=embed, view=self)
        self.stop()
    
    def get_emoji(self, choice):
        emojis = {
            "rock": "🪨",
            "paper": "📄",
            "scissors": "✂️"
        }
        return emojis.get(choice, "")
    
    async def on_timeout(self):
        if not (self.challenger_choice and self.opponent_choice):
            embed = discord.Embed(
                title="⏰ Game Timed Out",
                description="One or both players didn't make a choice in time!",
                color=discord.Color.red()
            )
            # Return bets if any
            if self.bet > 0:
                challenger_id = str(self.challenger.id)
                opponent_id = str(self.opponent.id)
                cash_balances[challenger_id] += self.bet
                cash_balances[opponent_id] += self.bet
                embed.add_field(
                    name="💰 Bets Returned",
                    value="All bets have been returned to players.",
                    inline=False
                )
            
            for child in self.children:
                child.disabled = True
            await self.message.edit(embed=embed, view=self)
        self.stop()

@bot.command(name='rps')
async def rps(ctx, opponent: discord.Member = None, bet: str = None):
    challenger_id = str(ctx.author.id)
    
    if opponent is None:
        embed = discord.Embed(
            title="🎮 Rock Paper Scissors Help",
            description="Challenge someone to a game of Rock Paper Scissors!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value="!rps @player <bet_amount>\n!rps @player",
            inline=False
        )
        embed.add_field(
            name="Example",
            value="!rps @JohnDoe 1000\n!rps @JohnDoe",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    if opponent.id == ctx.author.id:
        embed = discord.Embed(
            title="❌ Invalid Opponent",
            description="You can't play against yourself!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    # Handle bet
    bet_amount = 0
    if bet is not None:
        try:
            bet_amount = int(bet)
            if bet_amount <= 0:
                raise ValueError
            
            # Check if both players have enough money
            challenger_balance = cash_balances.get(challenger_id, 0)
            opponent_balance = cash_balances.get(str(opponent.id), 0)
            
            if challenger_balance < bet_amount or opponent_balance < bet_amount:
                embed = discord.Embed(
                    title="❌ Insufficient Funds",
                    description="Both players need enough cash for the bet!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            
            # Deduct bets
            cash_balances[challenger_id] -= bet_amount
            cash_balances[str(opponent.id)] -= bet_amount
            
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet amount must be a positive number!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
    
    # Create game
    view = RPSView(ctx.author, opponent, bet_amount)
    
    embed = discord.Embed(
        title="🎮 Rock Paper Scissors Challenge",
        description=f"{ctx.author.mention} has challenged {opponent.mention} to a game!",
        color=discord.Color.blue()
    )
    
    if bet_amount > 0:
        embed.add_field(
            name="💰 Bet Amount",
            value=f"${bet_amount:,}",
            inline=False
        )
    
    embed.add_field(
        name="How to Play",
        value="Both players click a button to make your choice!",
        inline=False
    )
    
    message = await ctx.send(embed=embed, view=view)
    view.message = message

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN')) 
