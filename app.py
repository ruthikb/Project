from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

DATABASE = 'database.db'

# Initialize the database
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                activity TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        conn.commit()

# Helper function to log activity
def log_activity(user_id, activity):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO activity_log (user_id, activity) VALUES (?, ?)", (user_id, activity))
        conn.commit()

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                flash("Registration successful! Please log in.")
                return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    if username == "admin" and password == "admin":
        session['is_admin'] = 1
        return redirect(url_for('admin'))
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[3]
            log_activity(user[0], "Logged in")
            with open('session.txt', 'w') as file:
                file.write(str(user[0]))
            return redirect(url_for('admin' if user[3] else 'profile'))
        flash("Invalid username or password.")
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    log_activity(session['user_id'], "Viewed profile")
    return render_template('profile.html', username=session['username'])

@app.route('/attend')
def attend():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    log_activity(session['user_id'], "Class Attended")
    return render_template('profile.html', username=session['username'])

@app.route('/admin')
def admin():
    if 'is_admin' in session and session['is_admin']:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users")
            users = cursor.fetchall()
        return render_template('admin.html', users=users)
    return redirect(url_for('home'))

@app.route('/activity_log')
def activity_log():
    if 'is_admin' in session and session['is_admin']:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, u.username, a.activity, a.timestamp
                FROM activity_log a
                JOIN users u ON a.user_id = u.id
                ORDER BY a.timestamp DESC
            ''')
            logs = cursor.fetchall()
        return render_template('activity_log.html', logs=logs)
    return redirect(url_for('home'))

# Duration calculation
def durc(start, end):
    if not start or not end:
        return "N/A"
    start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
    return end_dt - start_dt

# Fetch timestamps helper function
def fetch_timestamps(cursor, user_id, activity):
    try:
        cursor.execute("""
            SELECT MIN(timestamp), MAX(timestamp)
            FROM activity_log 
            WHERE user_id = ? AND activity = ?
        """, (user_id, activity))
        return cursor.fetchone()
    except Exception as e:
        print(f"Error fetching timestamps: {e}")
        return None, None

@app.route('/sessionview/<id>')
def seesionview(id):
    if 'is_admin' in session and session['is_admin']:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            # Fetch timestamps for each activity
            activity1, activity2 = fetch_timestamps(cursor, id, 'Active')
            distracted1, distracted2 = fetch_timestamps(cursor, id, 'distracted')
            looking_away1, looking_away2 = fetch_timestamps(cursor, id, 'looking_away')
            asleep1, asleep2 = fetch_timestamps(cursor, id, 'asleep')

            # Calculate durations
            at = durc(activity1, activity2) if activity1 and activity2 else "N/A"
            dt = durc(distracted1, distracted2) if distracted1 and distracted2 else "N/A"
            lat = durc(looking_away1, looking_away2) if looking_away1 and looking_away2 else "N/A"
            ast = durc(asleep1, asleep2) if asleep1 and asleep2 else "N/A"

        return render_template('sessionview.html', at=at, lat=lat, dt=dt, ast=ast)
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], "Logged out")
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
