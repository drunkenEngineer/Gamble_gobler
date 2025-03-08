import sqlite3
from datetime import datetime
import json

class Database:
    def __init__(self, db_file="casino.db"):
        self.db_file = db_file
        self.setup_database()

    def get_connection(self):
        return sqlite3.connect(self.db_file)

    def setup_database(self):
        """Create all necessary tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create users table for balances
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    cash_balance INTEGER DEFAULT 10000,
                    bank_balance INTEGER DEFAULT 0,
                    last_work TIMESTAMP,
                    last_crime TIMESTAMP
                )
            ''')
            
            # Create lottery table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lottery (
                    jackpot INTEGER DEFAULT 100000,
                    last_draw TIMESTAMP,
                    current_tickets TEXT DEFAULT '{}'
                )
            ''')
            
            # Create robbery stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS robbery_stats (
                    user_id TEXT PRIMARY KEY,
                    total_stolen INTEGER DEFAULT 0,
                    successful_robberies INTEGER DEFAULT 0,
                    failed_robberies INTEGER DEFAULT 0
                )
            ''')
            
            conn.commit()

    def get_user(self, user_id):
        """Get or create user record"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (str(user_id),))
            user = cursor.fetchone()
            
            if not user:
                cursor.execute(
                    'INSERT INTO users (user_id, cash_balance, bank_balance) VALUES (?, 10000, 0)',
                    (str(user_id),)
                )
                conn.commit()
                return {'user_id': str(user_id), 'cash_balance': 10000, 'bank_balance': 0}
            
            return {
                'user_id': user[0],
                'cash_balance': user[1],
                'bank_balance': user[2],
                'last_work': user[3],
                'last_crime': user[4]
            }

    def update_balance(self, user_id, cash_change=0, bank_change=0):
        """Update user's cash and bank balances"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if cash_change != 0:
                cursor.execute(
                    'UPDATE users SET cash_balance = cash_balance + ? WHERE user_id = ?',
                    (cash_change, str(user_id))
                )
            if bank_change != 0:
                cursor.execute(
                    'UPDATE users SET bank_balance = bank_balance + ? WHERE user_id = ?',
                    (bank_change, str(user_id))
                )
            conn.commit()

    def get_cooldown(self, user_id, cooldown_type):
        """Get last activity timestamp for work or crime"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            column = f'last_{cooldown_type}'
            cursor.execute(f'SELECT {column} FROM users WHERE user_id = ?', (str(user_id),))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None

    def set_cooldown(self, user_id, cooldown_type):
        """Set cooldown timestamp for work or crime"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            column = f'last_{cooldown_type}'
            cursor.execute(
                f'UPDATE users SET {column} = ? WHERE user_id = ?',
                (datetime.now().isoformat(), str(user_id))
            )
            conn.commit()

    def get_lottery_info(self):
        """Get current lottery status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM lottery LIMIT 1')
            result = cursor.fetchone()
            
            if not result:
                cursor.execute(
                    'INSERT INTO lottery (jackpot, current_tickets) VALUES (?, ?)',
                    (100000, '{}')
                )
                conn.commit()
                return {'jackpot': 100000, 'tickets': {}, 'last_draw': None}
            
            return {
                'jackpot': result[0],
                'last_draw': result[1],
                'tickets': json.loads(result[2])
            }

    def update_lottery(self, jackpot=None, tickets=None):
        """Update lottery information"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if jackpot is not None:
                cursor.execute('UPDATE lottery SET jackpot = ?', (jackpot,))
            if tickets is not None:
                cursor.execute('UPDATE lottery SET current_tickets = ?', (json.dumps(tickets),))
            conn.commit()

    def reset_lottery(self):
        """Reset lottery after draw"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE lottery 
                SET jackpot = 100000,
                    last_draw = ?,
                    current_tickets = '{}'
            ''', (datetime.now().isoformat(),))
            conn.commit()

    def get_robbery_stats(self, user_id):
        """Get user's robbery statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM robbery_stats WHERE user_id = ?', (str(user_id),))
            stats = cursor.fetchone()
            
            if not stats:
                return {'total_stolen': 0, 'successful_robberies': 0, 'failed_robberies': 0}
            
            return {
                'total_stolen': stats[1],
                'successful_robberies': stats[2],
                'failed_robberies': stats[3]
            }

    def update_robbery_stats(self, user_id, amount_stolen=0, success=True):
        """Update user's robbery statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO robbery_stats (user_id, total_stolen, successful_robberies, failed_robberies)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    total_stolen = total_stolen + ?,
                    successful_robberies = successful_robberies + ?,
                    failed_robberies = failed_robberies + ?
            ''', (
                str(user_id),
                amount_stolen if success else 0,
                1 if success else 0,
                0 if success else 1,
                amount_stolen if success else 0,
                1 if success else 0,
                0 if success else 1
            ))
            conn.commit()

    def get_leaderboard(self):
        """Get user rankings by total wealth"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, (cash_balance + bank_balance) as total_wealth
                FROM users
                ORDER BY total_wealth DESC
            ''')
            return cursor.fetchall()

    def add_tickets(self, user_id, new_tickets):
        """Add new tickets to user's lottery tickets"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT current_tickets FROM lottery')
            result = cursor.fetchone()
            
            if not result:
                cursor.execute(
                    'INSERT INTO lottery (current_tickets) VALUES (?)',
                    ('{}',)
                )
                conn.commit()
                tickets = {}
            else:
                tickets = json.loads(result[0])
            
            tickets[user_id] = tickets.get(user_id, []) + new_tickets
            cursor.execute('UPDATE lottery SET current_tickets = ?', (json.dumps(tickets),))
            conn.commit() 