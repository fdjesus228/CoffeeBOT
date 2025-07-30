from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import sqlite3
import datetime
import re
from collections import Counter

# === Настройки ===
import os
TOKEN = os.getenv("BOT_TOKEN")

# === Подключение к базе ===
conn = sqlite3.connect("flavor_journal.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS recipes (
    user_id INTEGER,
    name TEXT,
    method TEXT,
    bean TEXT,
    dose TEXT,
    taste TEXT,
    score TEXT,
    notes TEXT,
    date TEXT
)
""")
conn.commit()

# === Временное хранилище ===
user_states = {}

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["➕ Добавить рецепт", "📖 Список рецептов"],
        ["🔍 Поиск по вкусу", "📊 Профиль"],
        ["🛠 Настроить вкус", "❓ Помощь"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Привет! Это твой 'Журнал вкуса'. Выбери действие:", reply_markup=reply_markup)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states[update.effective_user.id] = {}
    await update.message.reply_text("Введи название рецепта:")

async def handle_add_recipe_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user_data = user_states[user_id]

    if "name" not in user_data:
        user_data["name"] = text
        await update.message.reply_text("Метод (эспрессо / фильтр / альтернативный):")
    elif "method" not in user_data:
        user_data["method"] = text
        await update.message.reply_text("Зерно (регион, обжарка, обжарщик):")
    elif "bean" not in user_data:
        user_data["bean"] = text
        await update.message.reply_text("Дозировка (грамм / вода / температура / время):")
    elif "dose" not in user_data:
        user_data["dose"] = text
        await update.message.reply_text("Вкус (через запятую):")
    elif "taste" not in user_data:
        user_data["taste"] = text
        await update.message.reply_text("Оценка (по 10-бальной шкале):")
    elif "score" not in user_data:
        user_data["score"] = text
        await update.message.reply_text("Заметки:")
    elif "notes" not in user_data:
        user_data["notes"] = text

        cursor.execute("INSERT INTO recipes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
            user_id,
            user_data["name"],
            user_data["method"],
            user_data["bean"],
            user_data["dose"],
            user_data["taste"],
            user_data["score"],
            user_data["notes"],
            datetime.date.today().isoformat()
        ))
        conn.commit()

        del user_states[user_id]
        await update.message.reply_text("✅ Рецепт сохранён! Напиши /list чтобы его увидеть.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()

    if text == "➕ добавить рецепт":
        await add(update, context)
    elif text == "📖 список рецептов":
        await list_recipes(update, context)
    elif text == "🔍 поиск по вкусу":
        await update.message.reply_text("Напиши: /filter шоколад (или другой вкус)")
    elif text == "📊 профиль":
        await profile(update, context)
    elif text == "🛠 настроить вкус":
        await update.message.reply_text("Напиши: /tune очень кисло (или опиши вкус)")
    elif text == "❓ помощь":
        await help_command(update, context)
    elif user_id in user_states:
        await handle_add_recipe_flow(update, context)
    else:
        await update.message.reply_text("Не понял 🤔 Нажми кнопку или используй /help")

async def list_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Эспрессо", callback_data='method_эспрессо'),
            InlineKeyboardButton("V60", callback_data='method_v60'),
        ],
        [
            InlineKeyboardButton("Турка", callback_data='method_турка'),
            InlineKeyboardButton("Все", callback_data='method_all')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери метод приготовления:", reply_markup=reply_markup)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT taste, bean, method FROM recipes WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("У тебя пока нет сохранённых рецептов 😔 Используй /add, чтобы добавить.")
        return

    taste_words = ["кисл", "горч", "слад", "ягод", "шокол", "цитрус", "фрукт", "цветоч", "орех", "тело"]
    taste_counter = Counter()
    origin_counter = Counter()
    method_counter = Counter()

    for taste, bean, method in rows:
        text = f"{taste.lower()} {bean.lower()} {method.lower()}"

        for word in taste_words:
            if re.search(word, text):
                taste_counter[word] += 1

        if "эфиоп" in text:
            origin_counter["Эфиопия"] += 1
        if "колумб" in text:
            origin_counter["Колумбия"] += 1
        if "бразил" in text:
            origin_counter["Бразилия"] += 1

        if "v60" in text or "воронк" in text:
            method_counter["V60"] += 1
        if "эспрессо" in text:
            method_counter["Эспрессо"] += 1
        if "турка" in text:
            method_counter["Турка"] += 1

    def format_counter(counter):
        return "\n".join(f"– {k.capitalize()} — {v}×" for k, v in counter.most_common()) if counter else "– Нет данных"

    message = (
        f"📊 Твой вкусовой профиль:\n\n"
        f"☕ Всего рецептов: {len(rows)}\n\n"
        f"✅ Часто встречающиеся вкусы:\n{format_counter(taste_counter)}\n\n"
        f"🌍 Страны происхождения:\n{format_counter(origin_counter)}\n\n"
        f"🛠 Методы приготовления:\n{format_counter(method_counter)}"
    )

    await update.message.reply_text(message)

async def filter_recipes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Напиши вкус, по которому фильтровать. Например: /filter шоколад")
        return

    keyword = " ".join(context.args).lower()
    cursor.execute("SELECT name, method, taste, score FROM recipes WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()

    filtered = [r for r in rows if keyword in r[2].lower()]

    if not filtered:
        await update.message.reply_text(f"Ничего не найдено по вкусу: {keyword}")
        return

    msg = f"🔍 Рецепты с вкусом '{keyword}':\n\n"
    for r in filtered:
        msg += f"• {r[0]} ({r[1]}) — вкус: {r[2]} — {r[3]}/10\n"

    await update.message.reply_text(msg)

async def method_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    method = query.data.replace("method_", "")

    if method == "all":
        cursor.execute("SELECT name, method, taste, score, date, dose, notes FROM recipes WHERE user_id = ?", (user_id,))
    else:
        cursor.execute(
            "SELECT name, method, taste, score, date, dose, notes FROM recipes WHERE user_id = ? AND LOWER(method) LIKE ?",
            (user_id, f"%{method}%")
        )

    rows = cursor.fetchall()

    if not rows:
        await query.edit_message_text("Нет рецептов для выбранного метода 😔")
        return

    msg = "📖 *Твои рецепты:*\n\n"
    for r in rows:
        name, method, taste, score, date, dose, notes = r

        msg += f"📌 *{name}*  _({method}, {date})_\n"
        msg += f"🥄 *Вкус:* {taste}\n"
        msg += f"⭐ *Оценка:* {score}/10\n"
        msg += f"📐 *Дозировка:* {dose}\n"

        # Анализ проливов для V60
        if "v60" in method.lower():
            water_match = re.search(r"(\d{2,4})\s*мл", dose.lower())
            pours_match = re.search(r"(\d+)\s*пролив", dose.lower())

            if water_match and pours_match:
                total_water = int(water_match.group(1))
                pours = int(pours_match.group(1))
                if pours > 0:
                    per_pour = round(total_water / pours)
                    msg += f"💧 *Проливов:* {pours} × ~{per_pour}мл\n"

        msg += f"📝 *Заметки:* {notes if notes else '–'}\n\n"

    await query.edit_message_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 Доступные команды:\n"
        "/start — приветствие\n"
        "/add — добавить новый рецепт\n"
        "/list — посмотреть список рецептов\n"
        "/tune [вкус] — советы по настройке вкуса (например: /tune очень кисло)\n"
        "/help — показать это сообщение"
    )
    await update.message.reply_text(help_text)

async def tune(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Напиши, что именно не так со вкусом. Например: /tune очень кисло")
        return

    feedback = " ".join(context.args).lower()

    if "кисло" in feedback:
        response = (
            "☕️ Вкус слишком кислый:\n"
            "- Уменьши размер помола (сделай его тоньше)\n"
            "- Увеличь время экстракции на 2–3 секунды\n"
            "- Убедись, что температура воды не ниже 92°C"
        )
    elif "горько" in feedback:
        response = (
            "☕️ Вкус слишком горький:\n"
            "- Увеличь помол (сделай крупнее)\n"
            "- Уменьши температуру воды до 91–92°C\n"
            "- Попробуй уменьшить время пролива"
        )
    elif "водянист" in feedback or "пусто" in feedback:
        response = (
            "☕️ Вкус водянистый:\n"
            "- Увеличь дозу кофе\n"
            "- Проверь равномерность трамбовки\n"
            "- Сократи время пролива на 2–3 секунды"
        )
    else:
        response = "Пока не знаю, как расшифровать такой вкус 😔 Попробуй описать его иначе!"

    await update.message.reply_text(response)

# === Запуск ===

if not TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден в переменных окружения!")

app = ApplicationBuilder().token(TOKEN).build()

# Обработчики команд
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("list", list_recipes))
app.add_handler(CommandHandler("tune", tune))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(CommandHandler("filter", filter_recipes))

# Обработчики кнопок и обычных сообщений
app.add_handler(CallbackQueryHandler(method_filter_callback, pattern="^method_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("✅ Бот 'Журнал вкуса' запущен. Ожидаю команды от пользователей...")

try:
    app.run_polling()
except Exception as e:
    print("❌ Ошибка при запуске бота:", e)
