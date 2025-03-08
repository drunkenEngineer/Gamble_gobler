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
from database import Database
import signal
import sys

# Load environment variables
load_dotenv()

# Bot configuration
COMMAND_PREFIX = '!'
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Initialize database
db = Database()

# Constants
LOTTERY_TICKET_PRICE = 100  # Price per ticket

def signal_handler(sig, frame):
    print('\nShutting down bot gracefully...')
    asyncio.run(bot.close())
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    bot.loop.create_task(lottery_draw_loop())

@bot.command(name='balance')
async def balance(ctx):
    user_id = str(ctx.author.id)
    
    # Get user data from database
    user_data = db.get_user(user_id)
    cash_balance = user_data['cash_balance']
    bank_balance = user_data['bank_balance']
    total = cash_balance + bank_balance

    embed = discord.Embed(
        title="💰 Your Balances",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash", value=f"${cash_balance:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${bank_balance:,}", inline=True)
    embed.add_field(name="💳 Total", value=f"${total:,}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='blackjack', aliases=['bj'])
async def blackjack(ctx, bet: str = None):
    user_id = str(ctx.author.id)
    
    # Get user data from database
    user_data = db.get_user(user_id)
    
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
        bet = user_data['cash_balance']
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
    
    if bet > user_data['cash_balance']:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You need ${bet:,} in cash, but you only have ${user_data['cash_balance']:,}!\nWithdraw from your bank first!",
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
    
    # Create view with buttons
    view = BlackjackView(game, player_hand, dealer_hand, bet, user_id, db)
    
    # Show initial hands
    embed = game.create_game_embed(
        player_hand, 
        dealer_hand, 
        bet=bet,
        balance=user_data['cash_balance']
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
    
    # Get user data from database
    user_data = db.get_user(user_id)
    
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
        bet = user_data['cash_balance']
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
        
    if bet > user_data['cash_balance']:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You need ${bet:,} in cash, but you only have ${user_data['cash_balance']:,}!\nWithdraw from your bank first!",
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
    
    # Update cash balance through database
    if won:
        db.update_balance(user_id, cash_change=bet * multiplier)
        embed = discord.Embed(
            title="🎰 You Won!",
            description=f"Ball landed on {result}!\nYou won ${bet * multiplier:,}!",
            color=discord.Color.green()
        )
    else:
        db.update_balance(user_id, cash_change=-bet)
        embed = discord.Embed(
            title="😢 You Lost!",
            description=f"Ball landed on {result}!\nYou lost ${bet:,}!",
            color=discord.Color.red()
        )
    
    # Get updated user data
    updated_data = db.get_user(user_id)
    
    embed.add_field(
        name="💰 New Cash Balance",
        value=f"${updated_data['cash_balance']:,}",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='dice')
async def dice(ctx, bet: str = None, number: str = None):
    user_id = str(ctx.author.id)
    
    # Get user data from database
    user_data = db.get_user(user_id)
    
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
        bet = user_data['cash_balance']
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

    if bet > user_data['cash_balance']:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You need ${bet:,} in cash, but you only have ${user_data['cash_balance']:,}!",
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
        db.update_balance(user_id, cash_change=winnings - bet)  # Subtract original bet since we're adding total winnings
        
        embed = discord.Embed(
            title="🎲 You Won!",
            description=f"The dice rolled a {roll}!\nYou won ${winnings:,}!",
            color=discord.Color.green()
        )
    else:
        db.update_balance(user_id, cash_change=-bet)
        
        embed = discord.Embed(
            title="🎲 You Lost!",
            description=f"The dice rolled a {roll}!\nYou lost ${bet:,}!",
            color=discord.Color.red()
        )
    
    # Get updated user data
    updated_data = db.get_user(user_id)
    
    embed.add_field(
        name="💰 New Balance",
        value=f"${updated_data['cash_balance']:,}",
        inline=False
    )
    
    await message.edit(embed=embed)

@bot.command(name='leaderboard', aliases=['lb'])
async def leaderboard(ctx):
    # Get leaderboard data from database
    leaderboard_data = db.get_leaderboard()
    
    # Calculate total pages (10 users per page)
    users_per_page = 10
    total_pages = max(1, (len(leaderboard_data) + users_per_page - 1) // users_per_page)

    class LeaderboardView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.current_page = 1

        async def get_page_embed(self):
            start_idx = (self.current_page - 1) * users_per_page
            end_idx = start_idx + users_per_page
            current_page_users = leaderboard_data[start_idx:end_idx]

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
    
    # Get user data from database
    user_data = db.get_user(user_id)
    
    # Get leaderboard data to calculate rank
    leaderboard_data = db.get_leaderboard()
    rank = next(i for i, (uid, _) in enumerate(leaderboard_data, 1) if uid == user_id)

    embed = discord.Embed(
        title=f"💰 {ctx.author.name}'s Money",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash", value=f"${user_data['cash_balance']:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${user_data['bank_balance']:,}", inline=True)
    embed.add_field(name="💳 Total", value=f"${user_data['cash_balance'] + user_data['bank_balance']:,}", inline=False)
    embed.add_field(name="📊 Rank", value=f"#{rank}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='work')
async def work(ctx):
    user_id = str(ctx.author.id)
    current_time = datetime.now()
    
    # Get user data from database
    user_data = db.get_user(user_id)
    
    # Check cooldown
    last_work = user_data.get('last_work')
    if last_work:
        last_work = datetime.fromisoformat(last_work)
        time_diff = current_time - last_work
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
    
    # Update user's balance and set cooldown
    db.update_balance(user_id, cash_change=earnings)
    db.set_cooldown(user_id, 'work')
    
    # Get updated user data
    updated_data = db.get_user(user_id)
    
    # Create list of work messages
    work_messages = [
        f"You worked as a casino dealer and earned ${earnings:,}! 🎰",
        f"You helped count cards (legally) and earned ${earnings:,}! 🃏",
        f"You maintained slot machines and earned ${earnings:,}! 🎮",
        f"You served drinks at the casino and earned ${earnings:,}! 🍷",
        f"You worked as a security guard and earned ${earnings:,}! 👮",
        f"You cleaned the casino floor and earned ${earnings:,}! 🧹",
        f"You worked as a valet parker and earned ${earnings:,}! 🚗",
        f"You entertained guests as a performer and earned ${earnings:,}! 🎭",
        f"You worked as a cashier and earned ${earnings:,}! 💰",
        f"You gave casino tours and earned ${earnings:,}! 🎪"
    ]
    
    # Create and send embed
    embed = discord.Embed(
        title="💼 Work Complete!",
        description=random.choice(work_messages),
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="💳 New Balance",
        value=f"${updated_data['cash_balance']:,}",
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
    
    # Get user data from database
    user_data = db.get_user(user_id)
    
    # Check cooldown
    last_crime = user_data.get('last_work')
    if last_crime:
        last_crime = datetime.fromisoformat(last_crime)
        time_diff = current_time - last_crime
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
    
    # 20% success rate
    if random.random() <= 0.20:  # Success
        earnings = random.randint(30000, 50000)
        db.update_balance(user_id, cash_change=earnings)
        db.update_robbery_stats(user_id, amount_stolen=earnings, success=True)
        
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
        db.update_balance(user_id, cash_change=-fine)
        db.update_robbery_stats(user_id, amount_stolen=0, success=False)
        
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
    db.set_cooldown(user_id, 'work')
    
    # Get updated user data
    updated_data = db.get_user(user_id)
    
    embed.add_field(
        name="💰 New Balance",
        value=f"${updated_data['cash_balance']:,}",
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
    
    # Get user data from database
    user_data = db.get_user(user_id)
    
    # Check cooldown
    last_crime = user_data.get('last_work')
    if last_crime:
        last_crime = datetime.fromisoformat(last_crime)
        time_diff = current_time - last_crime
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
        db.update_balance(user_id, cash_change=earnings)
        
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
        db.update_balance(user_id, cash_change=earnings)
        
        embed = discord.Embed(
            title="rgadti b alf",
            description=f"You got ${earnings}! 💰",
            color=discord.Color.green()
        )
    
    # Set cooldown
    db.set_cooldown(user_id, 'work')
    
    # Get updated user data
    updated_data = db.get_user(user_id)
    
    embed.add_field(
        name="💰 New Balance",
        value=f"${updated_data['cash_balance']:,}",
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
    current_time = datetime.now()
    
    # Get user data from database
    user_data = db.get_user(user_id)
    last_work = user_data.get('last_work')
    
    if not last_work:
        embed = discord.Embed(
            title="✅ Work Available!",
            description="You can work right now! Use !work to earn money.",
            color=discord.Color.green()
        )
    else:
        last_work = datetime.fromisoformat(last_work)
        time_diff = current_time - last_work
        
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
    
    # Get user data from database
    user_data = db.get_user(user_id)

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
    if user_data['cash_balance'] <= 0:
        embed = discord.Embed(
            title="❌ No Cash to Deposit",
            description=f"You have no cash to deposit!\nYour bank balance: ${user_data['bank_balance']:,}\n\nUse `!withdraw <amount>` or `!with <amount>` to withdraw money from your bank.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Handle 'all' case
    if amount.lower() == 'all':
        amount = user_data['cash_balance']
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

    if amount > user_data['cash_balance']:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You only have ${user_data['cash_balance']:,} in cash!\nYour bank balance: ${user_data['bank_balance']:,}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Process deposit through database
    db.update_balance(user_id, cash_change=-amount, bank_change=amount)
    
    # Get updated data
    updated_data = db.get_user(user_id)

    embed = discord.Embed(
        title="💰 Deposit Successful",
        description=f"Deposited ${amount:,} into your bank account!",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash Balance", value=f"${updated_data['cash_balance']:,}", inline=True)
    embed.add_field(name="🏦 Bank Balance", value=f"${updated_data['bank_balance']:,}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='withdraw', aliases=['with'])
async def withdraw(ctx, amount: str = None):
    user_id = str(ctx.author.id)
    
    # Get user data from database
    user_data = db.get_user(user_id)

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
        amount = user_data['bank_balance']
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

    if amount > user_data['bank_balance']:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You only have ${user_data['bank_balance']:,} in your bank account!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Process withdrawal through database
    db.update_balance(user_id, cash_change=amount, bank_change=-amount)
    
    # Get updated data
    updated_data = db.get_user(user_id)

    embed = discord.Embed(
        title="💸 Withdrawal Successful",
        description=f"Withdrew ${amount:,} from your bank account!",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Cash Balance", value=f"${updated_data['cash_balance']:,}", inline=True)
    embed.add_field(name="🏦 Bank Balance", value=f"${updated_data['bank_balance']:,}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='chfara')
async def chfara(ctx, page: int = 1):
    user_id = str(ctx.author.id)
    
    # Get user's robbery stats
    user_stats = db.get_robbery_stats(user_id)
    
    # Get all robbery stats for leaderboard in one query
    all_stats = db.get_all_robbery_stats()
    
    # Filter out users with no stolen amount and sort
    sorted_robbers = [(uid, stats) for uid, stats in all_stats if stats['total_stolen'] > 0]
    sorted_robbers.sort(key=lambda x: x[1]['total_stolen'], reverse=True)
    
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
    
    # Get data for both users
    robber_data = db.get_user(robber_id)
    target_data = db.get_user(target_id)
    
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
    if target_data['cash_balance'] <= 0:
        db.update_robbery_stats(robber_id, amount_stolen=0, success=False)
        embed = discord.Embed(
            title="😅 Failed Robbery",
            description=f"{target.mention} has no cash to steal!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # 20% chance of getting caught
    if random.random() < 0.2:
        # Calculate fine (30% of total balance)
        total_balance = robber_data['cash_balance'] + robber_data['bank_balance']
        fine = int(total_balance * 0.3)
        
        # Update database
        db.update_balance(robber_id, cash_change=-fine)
        db.update_robbery_stats(robber_id, amount_stolen=0, success=False)
        
        # Get updated robber data
        updated_robber = db.get_user(robber_id)

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
            value=f"${updated_robber['cash_balance']:,}",
            inline=False
        )
        await ctx.send(embed=embed)
        return

    # Successful robbery (80% chance)
    percentage = random.uniform(0.6, 1.0)
    stolen_amount = int(target_data['cash_balance'] * percentage)
    
    # Update balances in database
    db.update_balance(target_id, cash_change=-stolen_amount)
    db.update_balance(robber_id, cash_change=stolen_amount)
    db.update_robbery_stats(robber_id, amount_stolen=stolen_amount, success=True)
    
    # Get updated robber data and stats
    updated_robber = db.get_user(robber_id)
    robbery_stats = db.get_robbery_stats(robber_id)

    embed = discord.Embed(
        title="🦹‍♂️ Successful Robbery!",
        description=f"You stole ${stolen_amount:,} from {target.mention}!",
        color=discord.Color.green()
    )
    embed.add_field(
        name="💰 Your New Cash Balance",
        value=f"${updated_robber['cash_balance']:,}",
        inline=False
    )
    embed.add_field(
        name="📊 Total Amount Stolen",
        value=f"${robbery_stats['total_stolen']:,}",
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
    
    # Get data for both users
    payer_data = db.get_user(payer_id)
    receiver_data = db.get_user(receiver_id)

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
        amount = payer_data['cash_balance']
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

    if amount > payer_data['cash_balance']:
        embed = discord.Embed(
            title="❌ Insufficient Cash",
            description=f"You only have ${payer_data['cash_balance']:,} in cash!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Process payment through database
    db.update_balance(payer_id, cash_change=-amount)
    db.update_balance(receiver_id, cash_change=amount)
    
    # Get updated data
    updated_payer = db.get_user(payer_id)
    updated_receiver = db.get_user(receiver_id)

    embed = discord.Embed(
        title="💸 Payment Successful",
        description=f"You paid ${amount:,} to {target.mention}!",
        color=discord.Color.green()
    )
    embed.add_field(name="💵 Your New Cash Balance", value=f"${updated_payer['cash_balance']:,}", inline=True)
    embed.add_field(name="💰 Their New Cash Balance", value=f"${updated_receiver['cash_balance']:,}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='lottery', aliases=['lot'])
async def lottery(ctx, action: str = None, amount: str = None):
    user_id = str(ctx.author.id)
    current_time = datetime.now()
    
    # Get user and lottery data from database
    user_data = db.get_user(user_id)
    lottery_data = db.get_lottery_info()
    
    if action is None:
        # Show lottery status
        last_draw = lottery_data.get('last_draw')
        if not last_draw:
            next_draw = "First draw pending"
        else:
            last_draw = datetime.fromisoformat(last_draw)
            time_until_draw = timedelta(days=1) - (current_time - last_draw)
            hours = int(time_until_draw.total_seconds() / 3600)
            minutes = int((time_until_draw.total_seconds() % 3600) / 60)
            next_draw = f"In {hours} hours and {minutes} minutes"
        
        # Get user's tickets
        tickets = lottery_data['tickets'].get(user_id, [])
        
        embed = discord.Embed(
            title="🎟️ Lottery Status",
            description="Try your luck in the daily lottery!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🏆 Current Jackpot",
            value=f"${lottery_data['jackpot']:,}",
            inline=False
        )
        embed.add_field(
            name="🎫 Your Tickets",
            value=f"You have {len(tickets)} tickets",
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
            if num_tickets <= 0:
                raise ValueError
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be a positive number!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        total_cost = num_tickets * LOTTERY_TICKET_PRICE
        
        if total_cost > user_data['cash_balance']:
            embed = discord.Embed(
                title="❌ Insufficient Cash",
                description=f"You need ${total_cost:,} to buy {num_tickets} tickets!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        try:
            # Generate tickets
            new_tickets = [random.randint(1, 99) for _ in range(num_tickets)]
            
            # Update database atomically
            db.update_balance(user_id, cash_change=-total_cost)
            db.add_tickets(user_id, new_tickets)
            
            # Update jackpot (50% of ticket cost goes to jackpot)
            current_jackpot = lottery_data['jackpot']
            db.update_lottery(jackpot=current_jackpot + total_cost // 2)
            
            # Get updated data
            updated_data = db.get_user(user_id)
            
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
                value=f"${updated_data['cash_balance']:,}",
                inline=False
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error buying lottery tickets: {e}")
            # Try to refund the user if something went wrong
            try:
                db.update_balance(user_id, cash_change=total_cost)
            except:
                pass
            embed = discord.Embed(
                title="❌ Error",
                description="There was an error buying tickets. Please try again.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
    elif action.lower() == 'numbers':
        tickets = lottery_data['tickets'].get(user_id, [])
        if not tickets:
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
        chunks = [tickets[i:i + 10] for i in range(0, len(tickets), 10)]

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
        
        # Get lottery data
        lottery_data = db.get_lottery_info()
        last_draw = lottery_data.get('last_draw')
        
        # Initialize last_draw if it's None
        if not last_draw:
            db.reset_lottery()
            await asyncio.sleep(3600)
            continue
            
        last_draw = datetime.fromisoformat(last_draw)
        
        # Check if 24 hours have passed since last draw
        if current_time - last_draw >= timedelta(days=1):
            # Perform lottery draw
            winning_number = random.randint(1, 99)
            winners = []
            
            # Check all tickets
            for user_id, tickets in lottery_data['tickets'].items():
                if winning_number in tickets:
                    winners.append(user_id)
            
            # Calculate prize
            if winners:
                prize_per_winner = lottery_data['jackpot'] // len(winners)
                # Pay winners
                for winner_id in winners:
                    db.update_balance(winner_id, cash_change=prize_per_winner)
                    
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
            db.reset_lottery()
            
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
        self.accepted = False
    
    @discord.ui.button(label="Accept ✅", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can accept!", ephemeral=True)
            return
            
        # Check if opponent has enough money
        opponent_data = db.get_user(str(self.opponent.id))
        if opponent_data['cash_balance'] < self.bet:
            await interaction.response.send_message(
                f"You need ${self.bet:,} in cash to accept this challenge, but you only have ${opponent_data['cash_balance']:,}!",
                ephemeral=True
            )
            return
            
        self.accepted = True
        
        # Clear all buttons first
        self.clear_items()
        
        # Add game buttons using the callback decorators
        self.add_item(self.rock_button_callback)
        self.add_item(self.paper_button_callback)
        self.add_item(self.scissors_button_callback)
        
        embed = discord.Embed(
            title="🎮 Rock Paper Scissors Game",
            description=f"Game accepted! Make your choices!\nBet amount: ${self.bet:,}",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Decline ❌", style=discord.ButtonStyle.red)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can decline!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="❌ Challenge Declined",
            description=f"{self.opponent.mention} declined the challenge!",
            color=discord.Color.red()
        )
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.accepted:
            return True
        if interaction.user.id not in [self.challenger.id, self.opponent.id]:
            await interaction.response.send_message("You're not part of this game!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Rock 🪨", style=discord.ButtonStyle.gray)
    async def rock_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "rock")
    
    @discord.ui.button(label="Paper 📄", style=discord.ButtonStyle.gray)
    async def paper_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "paper")
    
    @discord.ui.button(label="Scissors ✂️", style=discord.ButtonStyle.gray)
    async def scissors_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "scissors")
    
    async def make_choice(self, interaction: discord.Interaction, choice):
        if not self.accepted:
            await interaction.response.send_message("Wait for the challenge to be accepted!", ephemeral=True)
            return
            
        user_id = str(interaction.user.id)
        
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
        
        # Handle bet
        challenger_id = str(self.challenger.id)
        opponent_id = str(self.opponent.id)
        
        if winner:
            winner_id = str(winner.id)
            loser_id = opponent_id if winner_id == challenger_id else challenger_id
            
            # Transfer money through database
            db.update_balance(winner_id, cash_change=self.bet)
            db.update_balance(loser_id, cash_change=-self.bet)
            
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
        if not self.accepted:
            embed = discord.Embed(
                title="⏰ Challenge Expired",
                description=f"{self.opponent.mention} didn't respond in time!",
                color=discord.Color.red()
            )
        elif not (self.challenger_choice and self.opponent_choice):
            embed = discord.Embed(
                title="⏰ Game Timed Out",
                description="One or both players didn't make a choice in time!",
                color=discord.Color.red()
            )
            # Return bets
            challenger_id = str(self.challenger.id)
            opponent_id = str(self.opponent.id)
            # Return bets through database
            db.update_balance(challenger_id, cash_change=self.bet)
            db.update_balance(opponent_id, cash_change=self.bet)
            embed.add_field(
                name="💰 Bets Returned",
                value="All bets have been returned to players.",
                inline=False
            )
        
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(embed=embed, view=self)
        except:
            pass
        self.stop()

@bot.command(name='rps')
async def rps(ctx, opponent: discord.Member = None, bet: str = None):
    challenger_id = str(ctx.author.id)
    
    if opponent is None or bet is None:
        embed = discord.Embed(
            title="🎮 Rock Paper Scissors Help",
            description="Challenge someone to a game of Rock Paper Scissors!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Usage",
            value="!rps @player <bet_amount>\n!rps @player all",
            inline=False
        )
        embed.add_field(
            name="Example",
            value="!rps @JohnDoe 1000\n!rps @JohnDoe all",
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
    challenger_data = db.get_user(challenger_id)
    if bet.lower() == 'all':
        bet_amount = challenger_data['cash_balance']
    else:
        try:
            bet_amount = int(bet)
            if bet_amount <= 0:
                raise ValueError
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet amount must be a positive number or 'all'!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
    # Check if challenger has enough money
    if challenger_data['cash_balance'] < bet_amount:
        embed = discord.Embed(
            title="❌ Insufficient Funds",
            description=f"You need ${bet_amount:,} in cash, but you only have ${challenger_data['cash_balance']:,}!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Create game view (only with accept/decline buttons initially)
    view = RPSView(ctx.author, opponent, bet_amount)
    
    embed = discord.Embed(
        title="🎮 Rock Paper Scissors Challenge",
        description=f"{ctx.author.mention} has challenged {opponent.mention} to a game!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="💰 Bet Amount",
        value=f"${bet_amount:,}",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Instructions",
        value=f"{opponent.mention}, use the buttons below to accept or decline the challenge!",
        inline=False
    )
    
    message = await ctx.send(embed=embed, view=view)
    view.message = message

# Keep the bot alive
keep_alive()

# Run the bot using the token from environment variable
bot.run(os.getenv('DISCORD_TOKEN')) 