import string
from flask import Flask, request, redirect, jsonify, render_template
import sqlite3
import time
import redis
import traceback

# --- Short ID Encoder ---
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

# --- App Setup ---
app = Flask(__name__)
encoder = IDEncoder()

# --- SQLite Setup ---
conn = sqlite3.connect('paste.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS urls
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              short_id TEXT UNIQUE,
              content TEXT,
              created_at INTEGER,
              click_count INTEGER DEFAULT 0)''')
conn.commit()

# --- Redis Setup ---
r = redis.from_url(
    "rediss://default:AX-CAAIjcDExMjk5ODFlODVmMGE0YjdmYWJhYWIyMmE5MTk4M2FiMXAxMA@known-anemone-32642.upstash.io:6379",
    decode_responses=True
)

# --- Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/paste', methods=['POST'])
def paste():
    try:
        data = request.get_json(force=True)
        if not data or 'content' not in data:
            return jsonify({'error': 'Missing "content" in request'}), 400

        content = data['content']
        created_at = int(time.time())

        c.execute("INSERT INTO urls (content, created_at) VALUES (?, ?)", (content, created_at))
        new_id = c.lastrowid
        short_id = encoder.encode(new_id)
        c.execute("UPDATE urls SET short_id = ? WHERE id = ?", (short_id, new_id))
        conn.commit()

        r.set(short_id, content)

        host_url = request.host_url.rstrip('/')  # Ensure no trailing slash
        return jsonify({'short_url': f"{host_url}/{short_id}"})

    except Exception as e:
        print("---- ERROR ----")
        print(f"Exception occurred: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/<short_id>')
def show_content(short_id):
    content = r.get(short_id)
    if not content:
        c.execute("SELECT content FROM urls WHERE short_id = ?", (short_id,))
        row = c.fetchone()
        if row:
            content = row[0]
            r.set(short_id, content)
        else:
            return "Not Found", 404

    c.execute("UPDATE urls SET click_count = click_count + 1 WHERE short_id = ?", (short_id,))
    conn.commit()

    # ✅ Render the paste content directly in the page
    return f"""
        <html>
        <head><title>Paste</title></head>
        <body>
            <h1>Paste Content</h1>
            <pre>{content}</pre>
        </body>
        </html>
    """

