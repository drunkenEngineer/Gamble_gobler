from flask import Flask
from threading import Thread
import signal
import sys

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def signal_handler(sig, frame):
    print('\nShutting down web server...')
    sys.exit(0)

def keep_alive():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    t = Thread(target=run)
    t.daemon = True  # Set thread as daemon so it dies when main program exits
    t.start() 