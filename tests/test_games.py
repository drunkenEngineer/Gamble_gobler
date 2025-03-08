import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from games.blackjack import Blackjack, Card
from games.roulette import Roulette

def test_blackjack():
    print("\n=== Testing Blackjack ===")
    
    # Create a mock bot object (since we don't need actual Discord functionality)
    class MockBot:
        pass
    
    bot = MockBot()
    game = Blackjack(bot)
    
    # Test deck creation
    deck = game.create_deck()
    print(f"Deck size: {len(deck)}")  # Should be 52
    
    # Test hand calculation
    test_hands = [
        ([Card('Hearts', 'A'), Card('Spades', 'K')], 21),  # Blackjack
        ([Card('Hearts', '2'), Card('Spades', '3')], 5),   # Simple sum
        ([Card('Hearts', 'A'), Card('Spades', 'A')], 12),  # Multiple aces
        ([Card('Hearts', 'K'), Card('Spades', 'Q'), Card('Diamonds', 'J')], 30)  # Bust
    ]
    
    for hand, expected in test_hands:
        value = game.calculate_hand(hand)
        print(f"\nHand: {[str(card) for card in hand]}")
        print(f"Calculated value: {value}")
        print(f"Expected value: {expected}")
        print(f"Test {'passed' if value == expected else 'failed'}")

def test_roulette():
    print("\n=== Testing Roulette ===")
    
    class MockBot:
        pass
    
    bot = MockBot()
    game = Roulette(bot)
    
    # Test different bet types
    test_bets = [
        ('number', '0', 0),
        ('color', 'red', 1),
        ('even', 'even', 2),
        ('odd', 'odd', 3),
        ('1-18', '1-18', 10),
        ('19-36', '19-36', 20)
    ]
    
    for bet_type, bet_value, result in test_bets:
        won, multiplier = game.check_bet(bet_type, bet_value, result)
        print(f"\nBet type: {bet_type}")
        print(f"Bet value: {bet_value}")
        print(f"Result: {result}")
        print(f"Won: {won}")
        print(f"Multiplier: {multiplier}")
    
    # Test random spins
    print("\nTesting random spins:")
    for _ in range(5):
        result = game.spin()
        print(f"Spin result: {result} ({game.colors[result]})")

if __name__ == "__main__":
    test_blackjack()
    test_roulette() 