import os
import sqlite3
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
#   КОНФИГУРАЦИЯ
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8987999012:AAH90oHXkNtImrD82QRFxLB4e5gIYMKj_Jk")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://click-ivmd.onrender.com")
DB_PATH = os.getenv("DB_PATH", "/tmp/clicks.db")

# ============================================================
#   FLASK
# ============================================================
app = Flask(__name__)
CORS(app)

# ============================================================
#   БАЗА ДАННЫХ
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page TEXT,
        element TEXT,
        text TEXT,
        x INTEGER,
        y INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_agent TEXT,
        ip TEXT,
        referrer TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pageviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page TEXT,
        title TEXT,
        referrer TEXT,
        screen TEXT,
        language TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_agent TEXT,
        ip TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ============================================================
#   API ДЛЯ СЧЁТЧИКА
# ============================================================
@app.route('/api/track/click', methods=['POST'])
def track_click():
    data = request.get_json(silent=True) or {}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO clicks (page, element, text, x, y, user_agent, ip, referrer)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (data.get('page'), data.get('element'), data.get('text'),
               data.get('x'), data.get('y'),
               request.headers.get('User-Agent'),
               request.remote_addr, data.get('referrer')))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 200

@app.route('/api/track/pageview', methods=['POST'])
def track_pageview():
    data = request.get_json(silent=True) or {}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO pageviews (page, title, referrer, screen, language, user_agent, ip)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (data.get('page'), data.get('title'), data.get('referrer'),
               data.get('screen'), data.get('language'),
               request.headers.get('User-Agent'), request.remote_addr))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 200

# ============================================================
#   API ДЛЯ MINI APP
# ============================================================
@app.route('/api/stats/summary')
def stats_summary():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

    c.execute("SELECT COUNT(*) FROM clicks WHERE timestamp > ?", (seven_days_ago,))
    total_clicks = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM pageviews WHERE timestamp > ?", (seven_days_ago,))
    total_views = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT ip) FROM pageviews WHERE timestamp > ?", (seven_days_ago,))
    unique_users = c.fetchone()[0]

    c.execute('''SELECT page, COUNT(*) as cnt FROM pageviews
                 WHERE timestamp > ? GROUP BY page ORDER BY cnt DESC LIMIT 5''',
              (seven_days_ago,))
    top_pages = [{"page": row[0], "count": row[1]} for row in c.fetchall()]

    c.execute('''SELECT element, COUNT(*) as cnt FROM clicks
                 WHERE timestamp > ? GROUP BY element ORDER BY cnt DESC LIMIT 5''',
              (seven_days_ago,))
    top_clicks = [{"element": row[0], "count": row[1]} for row in c.fetchall()]

    conn.close()
    return jsonify({
        "total_clicks": total_clicks,
        "total_views": total_views,
        "unique_users": unique_users,
        "top_pages": top_pages,
        "top_clicks": top_clicks
    })

@app.route('/api/stats/daily')
def stats_daily():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

    c.execute('''SELECT DATE(timestamp) as day, COUNT(*) as cnt
                 FROM pageviews WHERE timestamp > ?
                 GROUP BY DATE(timestamp) ORDER BY day''',
              (seven_days_ago,))
    daily = [{"date": row[0], "count": row[1]} for row in c.fetchall()]

    c.execute('''SELECT DATE(timestamp) as day, COUNT(*) as cnt
                 FROM clicks WHERE timestamp > ?
                 GROUP BY DATE(timestamp) ORDER BY day''',
              (seven_days_ago,))
    daily_clicks = [{"date": row[0], "count": row[1]} for row in c.fetchall()]

    conn.close()
    return jsonify({
        "daily_views": daily,
        "daily_clicks": daily_clicks
    })

@app.route('/api/stats/recent')
def stats_recent():
    """Последние 20 событий — для ленты активности."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT page, element, text, timestamp FROM clicks
                 ORDER BY timestamp DESC LIMIT 20''')
    recent = [{"page": r[0], "element": r[1], "text": r[2], "timestamp": r[3]}
              for r in c.fetchall()]
    conn.close()
    return jsonify({"recent": recent})

# ============================================================
#   MINI APP
# ============================================================
@app.route('/')
def index():
    return send_file('index.html')

@app.route('/health')
def health():
    return "ok", 200

# ============================================================
#   TELEGRAM BOT
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(
        "📊 Открыть статистику",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )]]
    await update.message.reply_text(
        "👋 Привет! Я бот для мониторинга кликов и статистики сайта.\n\n"
        "Нажми кнопку ниже, чтобы открыть панель управления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

    c.execute("SELECT COUNT(*) FROM clicks WHERE timestamp > ?", (seven_days_ago,))
    clicks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM pageviews WHERE timestamp > ?", (seven_days_ago,))
    views = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT ip) FROM pageviews WHERE timestamp > ?", (seven_days_ago,))
    users = c.fetchone()[0]
    conn.close()

    await update.message.reply_text(
        f"📊 *Статистика за 7 дней:*\n\n"
        f"👆 Кликов: `{clicks}`\n"
        f"👁 Просмотров: `{views}`\n"
        f"👤 Уникальных: `{users}`",
        parse_mode="Markdown"
    )

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))

    loop.run_until_complete(application.run_polling())

_bot_thread = threading.Thread(target=run_bot, daemon=True)
_bot_thread.start()

# ============================================================
#   ЛОКАЛЬНЫЙ ЗАПУСК
# ============================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
