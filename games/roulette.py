import discord
from discord.ext import commands
import random

class Roulette:
    def __init__(self, bot):
        self.bot = bot
        self.numbers = list(range(37))  # 0-36
        self.colors = {
            0: 'green',
            **{num: 'red' if num in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'black' 
               for num in range(1, 37)}
        }
        
    def spin(self):
        return random.choice(self.numbers)
    
    def check_bet(self, bet_type, bet_value, result):
        if bet_type == 'number':
            return bet_value == result, 35
        elif bet_type == 'color':
            return bet_value == self.colors[result], 2
        elif bet_type == 'even':
            return result != 0 and result % 2 == 0, 2
        elif bet_type == 'odd':
            return result != 0 and result % 2 == 1, 2
        elif bet_type == '1-18':
            return 1 <= result <= 18, 2
        elif bet_type == '19-36':
            return 19 <= result <= 36, 2
        
    def create_game_embed(self, result, bet_type, bet_value, won, multiplier, amount):
        color = discord.Color.green() if self.colors[result] == 'green' else \
                discord.Color.red() if self.colors[result] == 'red' else \
                discord.Color.dark_grey()
                
        embed = discord.Embed(title="Roulette Game", color=color)
        embed.add_field(name="Result", value=f"Number: {result} ({self.colors[result]})", inline=False)
        embed.add_field(name="Your Bet", value=f"Type: {bet_type}\nValue: {bet_value}\nAmount: ${amount}", inline=False)
        
        if won:
            winnings = amount * multiplier
            embed.add_field(name="Outcome", value=f"You won ${winnings}!", inline=False)
        else:
            embed.add_field(name="Outcome", value="You lost!", inline=False)
            
        return embed 