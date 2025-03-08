import discord
from discord.ext import commands
import random
from discord.ui import Button, View

class Card:
    def __init__(self, suit, value):
        self.suit = suit
        self.value = value

    def __str__(self):
        return f"{self.value} of {self.suit}"

    @property
    def emoji(self):
        # Card emojis mapping
        suits_emoji = {
            'Hearts': '♥️',
            'Diamonds': '♦️',
            'Clubs': '♣️',
            'Spades': '♠️'
        }
        
        # Special formatting for face cards
        value_display = {
            'A': 'A',
            'K': 'K',
            'Q': 'Q',
            'J': 'J'
        }.get(self.value, self.value)
        
        return f"`{value_display}{suits_emoji[self.suit]}`"

class BlackjackView(View):
    def __init__(self, game, player_hand, dealer_hand, bet, user_id, db):
        super().__init__(timeout=30)
        self.game = game
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.bet = bet
        self.user_id = user_id
        self.ended = False
        self.db = db

    @discord.ui.button(label="Hit 👊", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        self.player_hand.append(self.game.deck.pop())
        player_value = self.game.calculate_hand(self.player_hand)

        if player_value > 21:
            self.ended = True
            for child in self.children:
                child.disabled = True
            
            # Update balance through database
            self.db.update_balance(self.user_id, cash_change=-self.bet)
            
            # Get updated user data
            updated_data = self.db.get_user(self.user_id)
            
            embed = self.game.create_game_embed(
                self.player_hand, 
                self.dealer_hand,
                hide_dealer=False,
                game_over=True,
                bet=self.bet,
                balance=updated_data['cash_balance']
            )
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # Get current balance for display
        current_data = self.db.get_user(self.user_id)
        embed = self.game.create_game_embed(
            self.player_hand, 
            self.dealer_hand, 
            bet=self.bet,
            balance=current_data['cash_balance']
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand ✋", style=discord.ButtonStyle.red)
    async def stand_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != int(self.user_id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        dealer_value = self.game.calculate_hand(self.dealer_hand)
        while dealer_value < 17:
            self.dealer_hand.append(self.game.deck.pop())
            dealer_value = self.game.calculate_hand(self.dealer_hand)

        player_value = self.game.calculate_hand(self.player_hand)
        
        # Update balance through database
        if dealer_value > 21 or player_value > dealer_value:
            self.db.update_balance(self.user_id, cash_change=self.bet)
        elif player_value < dealer_value:
            self.db.update_balance(self.user_id, cash_change=-self.bet)

        self.ended = True
        for child in self.children:
            child.disabled = True

        # Get updated user data
        updated_data = self.db.get_user(self.user_id)

        embed = self.game.create_game_embed(
            self.player_hand,
            self.dealer_hand,
            hide_dealer=False,
            game_over=True,
            bet=self.bet,
            balance=updated_data['cash_balance']
        )
        await interaction.response.edit_message(embed=embed, view=self)

class Blackjack:
    def __init__(self, bot):
        self.bot = bot
        self.suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        self.values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.deck = self.create_deck()
        random.shuffle(self.deck)
        
    def create_deck(self):
        return [Card(suit, value) for suit in self.suits for value in self.values]

    def calculate_hand(self, hand):
        value = 0
        aces = 0
        
        for card in hand:
            if card.value in ['J', 'Q', 'K']:
                value += 10
            elif card.value == 'A':
                aces += 1
            else:
                value += int(card.value)
                
        for _ in range(aces):
            if value + 11 <= 21:
                value += 11
            else:
                value += 1
                
        return value

    def create_game_embed(self, player_hand, dealer_hand, hide_dealer=True, game_over=False, bet=0, balance=None):
        embed = discord.Embed(
            title="🎰 Blackjack Table 🎰",
            color=discord.Color.gold()
        )

        # Dealer's section with improved formatting
        dealer_cards = [card.emoji for card in dealer_hand]
        dealer_value = self.calculate_hand(dealer_hand)
        
        if hide_dealer:
            dealer_cards[1] = "`🎴`"
            dealer_display = f"**Dealer's Hand**\n{'  '.join(dealer_cards)}"
        else:
            dealer_display = f"**Dealer's Hand ({dealer_value})**\n{'  '.join(dealer_cards)}"
        
        embed.add_field(name="🎩 Dealer", value=dealer_display, inline=False)

        # Decorative separator
        embed.add_field(name="", value="▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰", inline=False)

        # Player's section with improved formatting
        player_value = self.calculate_hand(player_hand)
        player_cards = [card.emoji for card in player_hand]
        player_display = f"**Your Hand ({player_value})**\n{'  '.join(player_cards)}"
        
        embed.add_field(name="👤 Player", value=player_display, inline=False)

        # Update the bet and balance information
        embed.add_field(name="💰 Current Bet", value=f"${bet}", inline=True)
        if balance is not None:
            embed.add_field(name="💳 Your Balance", value=f"${balance}", inline=True)

        if game_over:
            result = self._get_game_result(player_value, dealer_value)
            embed.add_field(name="📌 Result", value=result, inline=True)
            
            if "Win" in result:
                embed.color = discord.Color.green()
            elif "Lose" in result:
                embed.color = discord.Color.red()
            else:
                embed.color = discord.Color.greyple()
        else:
            status = self._get_game_status(player_value)
            embed.add_field(name="📊 Status", value=status, inline=True)

        return embed

    def _get_game_result(self, player_value, dealer_value):
        if player_value > 21:
            return "❌ z3mti!"
        elif dealer_value > 21:
            return "✨ dealer z3am!"
        elif player_value > dealer_value:
            return "🎉 rb7ti!"
        elif player_value < dealer_value:
            return "😔 Dealer 7wak a jomi!"
        else:
            return "🤝 ta3adol!"

    def _get_game_status(self, value):
        if value == 21:
            return "🎯 Blackjack!"
        elif value > 21:
            return "💥 Bust!"
        else:
            return "🎮 Your turn..." 