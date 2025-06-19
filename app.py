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
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

@app.route('/')
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