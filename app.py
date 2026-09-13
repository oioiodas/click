import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
#   КОНФИГУРАЦИЯ
# ============================================================
BOT_TOKEN = "8987999012:AAH90oHXkNtImrD82QRFxLB4e5gIYMKj_Jk"  # Токен от @BotFather
WEBAPP_URL = "https://click-production.up.railway.app"  # HTTPS URL
DB_PATH = "clicks.db"

# ============================================================
#   ИНИЦИАЛИЗАЦИЯ FLASK
# ============================================================
app = Flask(__name__)


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
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_agent TEXT,
        ip TEXT,
        referrer TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pageviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_agent TEXT,
        ip TEXT
    )''')
    conn.commit()
    conn.close()


init_db()


# ============================================================
#   API ДЛЯ СЧЁТЧИКА НА САЙТЕ
# ============================================================
@app.route('/api/track/click', methods=['POST'])
def track_click():
    """Принимает данные о клике с сайта."""
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO clicks (page, element, user_agent, ip, referrer)
                 VALUES (?, ?, ?, ?, ?)''',
              (data.get('page'), data.get('element'),
               request.headers.get('User-Agent'),
               request.remote_addr, data.get('referrer')))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 200


@app.route('/api/track/pageview', methods=['POST'])
def track_pageview():
    """Принимает данные о просмотре страницы."""
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO pageviews (page, user_agent, ip)
                 VALUES (?, ?, ?)''',
              (data.get('page'),
               request.headers.get('User-Agent'),
               request.remote_addr))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 200


# ============================================================
#   API ДЛЯ MINI APP (СТАТИСТИКА)
# ============================================================
@app.route('/api/stats/summary')
def stats_summary():
    """Общая статистика за последние 7 дней."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

    # Всего кликов
    c.execute("SELECT COUNT(*) FROM clicks WHERE timestamp > ?", (seven_days_ago,))
    total_clicks = c.fetchone()[0]

    # Всего просмотров
    c.execute("SELECT COUNT(*) FROM pageviews WHERE timestamp > ?", (seven_days_ago,))
    total_views = c.fetchone()[0]

    # Уникальные IP
    c.execute("SELECT COUNT(DISTINCT ip) FROM pageviews WHERE timestamp > ?", (seven_days_ago,))
    unique_users = c.fetchone()[0]

    # Топ страниц
    c.execute('''SELECT page, COUNT(*) as cnt FROM pageviews 
                 WHERE timestamp > ? GROUP BY page ORDER BY cnt DESC LIMIT 5''',
              (seven_days_ago,))
    top_pages = [{"page": row[0], "count": row[1]} for row in c.fetchall()]

    # Топ кликов
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
    """Статистика по дням за последние 7 дней."""
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


# ============================================================
#   MINI APP (HTML)
# ============================================================
@app.route('/')
def index():
    return render_template('index.html')


# ============================================================
#   TELEGRAM BOT
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — показывает кнопку для открытия Mini App."""
    keyboard = [
        [InlineKeyboardButton(
            "📊 Открыть статистику",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Привет! Я бот для мониторинга кликов и статистики сайта.\n\n"
        "Нажми кнопку ниже, чтобы открыть панель управления:",
        reply_markup=reply_markup
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — краткая статистика в чате."""
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


def main():
    """Запуск бота и Flask."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))

    # Запуск Flask в отдельном потоке (или используйте gunicorn для продакшена)
    import threading
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False))
    flask_thread.start()

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()