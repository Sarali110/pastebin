import string

class IDEncoder:
    def __init__(self):
        self.alphabet = string.ascii_letters + string.digits  # a-zA-Z0-9
        self.base = len(self.alphabet)

    def encode(self, num):
        s = []
        while num > 0:
            s.append(self.alphabet[num % self.base])
            num //= self.base
        return ''.join(reversed(s)) or '0'

    def decode(self, short_id):
        num = 0
        for char in short_id:
            num = num * self.base + self.alphabet.index(char)
        return num
    
from flask import Flask, request, redirect, jsonify, render_template
import sqlite3
import time
import redis

app = Flask(__name__)
encoder = IDEncoder()

# Set up the database
conn = sqlite3.connect('urls.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS urls
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              short_id TEXT UNIQUE,
              long_url TEXT,
              created_at INTEGER,
              click_count INTEGER DEFAULT 0)''')
conn.commit()

# Set up Redis
r = redis.from_url("https://console.upstash.com/redis/129165a4-46f6-4530-b2de-fe5fa5618d61?teamid=0")

def home():
    return render_template('index.html')

@app.route('/shorten', methods=['POST'])
def shorten():
    long_url = request.json['url']
    created_at = int(time.time())

    # Insert a new row
    c.execute("INSERT INTO urls (long_url, created_at) VALUES (?, ?)", (long_url, created_at))
    new_id = c.lastrowid
    short_id = encoder.encode(new_id)
    c.execute("UPDATE urls SET short_id = ? WHERE id = ?", (short_id, new_id))
    conn.commit()

    # Cache the new mapping
    r.set(short_id, long_url)

    return jsonify({'short_url': f"http://short.ly/{short_id}"})

@app.route('/<short_id>')
def redirect_url(short_id):
    long_url = r.get(short_id)
    if not long_url:
        c.execute("SELECT long_url FROM urls WHERE short_id = ?", (short_id,))
        row = c.fetchone()
        if row:
            long_url = row[0]
            r.set(short_id, long_url)  # Update cache
        else:
            return "Not Found", 404

    c.execute("UPDATE urls SET click_count = click_count + 1 WHERE short_id = ?", (short_id,))
    conn.commit()
    return redirect(long_url)