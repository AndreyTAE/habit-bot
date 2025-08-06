# main.py
# Telegram-бот для марафонов привычек
# Запускается на Railway.app с PostgreSQL
# Использует asyncpg, python-telegram-bot v20.3

import os
import asyncio
import logging
import re
import asyncpg  # ✅ Добавьте эту строку!
from datetime import datetime, time as datetime_time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes


# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # Автоматически от PostgreSQL в Railway

if not BOT_TOKEN:
    raise EnvironmentError("❌ Переменная окружения BOT_TOKEN не установлена")

if not DATABASE_URL:
    raise EnvironmentError("❌ Переменная окружения DATABASE_URL не установлена")

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Задания для марафонов ===
MARATHON_TASKS = {
    "📚 Чтение": [
        "Прочитай 5 страниц любой книги",
        "Прочитай 10 страниц и запиши одну мысль",
        "Выбери новую книгу для чтения",
        "Прочитай 15 страниц за один подход",
        "Поделись интересной цитатой с друзьями",
        "Прочитай в новом месте (парк, кафе)",
        "Прочитай перед сном вместо телефона",
        "Найди автора, которого раньше не читал",
        "Прочитай 20 страниц утром",
        "Обсуди прочитанное с кем-то",
        "Прочитай биографию интересного человека",
        "Сделай заметки во время чтения",
        "Прочитай 30 минут в тишине",
        "Найди книгу по новой теме",
        "Прочитай вслух 10 минут",
        "Прочитай статью на научную тему",
        "Перечитай любимую главу из книги",
        "Прочитай книгу на иностранном языке",
        "Посети библиотеку или книжный магазин",
        "Прочитай интервью с любимым автором",
        "Прочитай 25 страниц без перерыва",
        "Найди рекомендации новых книг",
        "Прочитай рецензию на интересную книгу",
        "Прочитай поэзию 15 минут",
        "Обменяйся книгами с другом",
        "Прочитай о жизни великого ученого",
        "Прочитай 30 страниц в один день",
        "Напиши отзыв о прочитанной книге",
        "Составь список книг на следующий месяц",
        "Прочитай и поделись лучшей мыслью дня"
    ],
    "💪 Фитнес": [
        "Сделай 10 приседаний",
        "Пройди 5000 шагов",
        "Сделай зарядку 10 минут",
        "20 отжиманий (можно с колен)",
        "Растяжка 15 минут",
        "Планка 1 минута",
        "Пробежка или быстрая ходьба 20 минут",
        "50 приседаний за день",
        "Тренировка пресса 10 минут",
        "Подъем по лестнице 10 этажей",
        "Танцы под любимую музыку 15 минут",
        "30 отжиманий за день",
        "Йога или растяжка 20 минут",
        "Прогулка на свежем воздухе 30 минут",
        "100 прыжков на скакалке",
        "Силовая тренировка 15 минут",
        "Плавание или водные процедуры",
        "Велосипедная прогулка 30 минут",
        "Интервальная тренировка 20 минут",
        "Медитативная ходьба 25 минут",
        "Тренировка с собственным весом",
        "Активные игры или спорт 30 минут",
        "Пилатес 20 минут",
        "Подъемы на носки 100 раз",
        "Функциональная тренировка",
        "Кардио-тренировка 25 минут",
        "Упражнения на гибкость",
        "Активный отдых на природе",
        "Полноценная тренировка 45 минут",
        "Планируй активность на следующий месяц"
    ]
}

# === Инициализация базы данных ===
async def init_db():
    try:
        conn = await asyncpg.connect(DATABASE_URL)

        # Таблица пользователей
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                registration_date TEXT,
                current_marathon TEXT,
                marathon_day INTEGER DEFAULT 1,
                last_task_date TEXT,
                reminder_time TEXT
            )
        ''')

        # Таблица марафонов
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS marathons (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE,
                description TEXT,
                is_premium INTEGER DEFAULT 0,
                price INTEGER DEFAULT 0
            )
        ''')

        # Добавляем марафоны, если их нет
        count = await conn.fetchval("SELECT COUNT(*) FROM marathons")
        if count == 0:
            marathons = [
                ("📚 Чтение", "30 дней формирования привычки к чтению", 0, 0),
                ("💪 Фитнес", "30 дней физической активности", 0, 0),
                ("🧘 Медитация", "30 дней осознанности", 1, 150),
                ("💰 Финансы", "30 дней финансовой грамотности", 1, 200)
            ]
            for name, desc, is_premium, price in marathons:
                await conn.execute('''
                    INSERT INTO marathons (name, description, is_premium, price)
                    VALUES ($1, $2, $3, $4)
                ''', name, desc, is_premium, price)

        await conn.close()
        logger.info("✅ База данных инициализирована в PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации базы данных: {e}")

# === Основные команды ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name
    now = datetime.now().strftime('%Y-%m-%d')

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        INSERT INTO users (user_id, username, first_name, registration_date)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO UPDATE SET
        username = $2, first_name = $3
    ''', user_id, username, first_name, now)
    await conn.close()

    keyboard = [
        [InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton("⏰ Напоминание", callback_data="set_reminder")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎯 Привет, {first_name}!\n"
        "Добро пожаловать в Марафон Полезных Привычек! 💪\n"
        "Я помогу тебе сформировать новые привычки за 30 дней.\n"
        "Каждый день ты будешь получать небольшое задание,\n"
        "которое приведёт к большим изменениям!\n\n"
        "Что хочешь сделать?",
        reply_markup=reply_markup
    )

# === Напоминания ===
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("⏰ 8:00", callback_data="remind_8:00"),
         InlineKeyboardButton("⏰ 9:00", callback_data="remind_9:00")],
        [InlineKeyboardButton("⏰ 12:00", callback_data="remind_12:00"),
         InlineKeyboardButton("⏰ 18:00", callback_data="remind_18:00")],
        [InlineKeyboardButton("⏰ 20:00", callback_data="remind_20:00"),
         InlineKeyboardButton("⏰ 21:00", callback_data="remind_21:00")],
        [InlineKeyboardButton("⏰ Ввести своё время", callback_data="remind_custom")],
        [InlineKeyboardButton("🚫 Отключить", callback_data="remind_off")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "⏰ *Выбери время для напоминаний*\n"
        "Я буду присылать напоминание каждый день в это время.\n"
        "Можешь выбрать из списка или ввести своё время.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def request_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⌨️ Введи время в формате **ЧЧ:ММ**\n\n"
        "Например:\n"
        "• `9:00`\n"
        "• `18:30`\n"
        "• `21:45`\n\n"
        "Я запомню и буду напоминать каждый день!",
        parse_mode="Markdown"
    )
    context.user_data['state'] = 'waiting_for_custom_time'

async def save_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data

    conn = await asyncpg.connect(DATABASE_URL)

    # Удаляем старое напоминание
    job_name = f"reminder_{user_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    if data == "remind_off":
        await conn.execute('UPDATE users SET reminder_time = NULL WHERE user_id = $1', user_id)
        await conn.close()
        await query.answer("🔕 Напоминания отключены")
        await query.edit_message_text(
            "Напоминания отключены.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
            ]])
        )
        return

    time_str = data.replace("remind_", "")
    hours, minutes = map(int, time_str.split(":"))

    # Устанавливаем новое
    context.job_queue.run_daily(
        send_daily_reminder,
        time=datetime_time(hour=hours, minute=minutes),
        data={"user_id": user_id},
        name=job_name
    )

    await conn.execute('UPDATE users SET reminder_time = $1 WHERE user_id = $2', time_str, user_id)
    await conn.close()

    await query.answer(f"✅ Установлено на {time_str}")
    await query.edit_message_text(
        f"✅ Напоминание установлено на **{time_str}** каждый день! ⏰",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
        ]]),
        parse_mode="Markdown"
    )

async def handle_custom_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('state') != 'waiting_for_custom_time':
        return
    context.user_data['state'] = None

    user_id = update.effective_user.id
    text = update.message.text.strip()
    match = re.match(r"^([0-2]?[0-9]):([0-5][0-9])$", text)

    if not match:
        await update.message.reply_text(
            "❌ Неверный формат. Используй **ЧЧ:ММ**, например: `9:00`",
            parse_mode="Markdown"
        )
        return

    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23:
        await update.message.reply_text("❌ Часы — от 0 до 23.")
        return

    time_str = f"{hours:02d}:{minutes:02d}"
    job_name = f"reminder_{user_id}"

    # Удаляем старое
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    # Устанавливаем новое
    context.job_queue.run_daily(
        send_daily_reminder,
        time=datetime_time(hour=hours, minute=minutes),
        data={"user_id": user_id},
        name=job_name
    )

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('UPDATE users SET reminder_time = $1 WHERE user_id = $2', time_str, user_id)
    await conn.close()

    await update.message.reply_text(
        f"✅ Напоминание установлено на **{time_str}** каждый день! ⏰",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
        ]]),
        parse_mode="Markdown"
    )

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.data["user_id"]

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow('''
        SELECT current_marathon, marathon_day, last_task_date
        FROM users WHERE user_id = $1
    ''', user_id)
    await conn.close()

    if not row or not row['current_marathon']:
        return

    marathon_name, day, last_date = row['current_marathon'], row['marathon_day'], row['last_task_date']
    today = datetime.now().strftime('%Y-%m-%d')

    if last_date == today:
        return

    try:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Получить задание", callback_data="get_task")
        ]])
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ *Напоминание!*\n"
                 f"Не забудь сегодняшнее задание:\n"
                 f"🎯 **{marathon_name}**\n"
                 f"📅 День {day}/30\n"
                 f"Нажми, чтобы посмотреть!",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Ошибка отправки напоминания {user_id}: {e}")

# === Марафоны и задания ===
async def choose_marathon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = await asyncpg.connect(DATABASE_URL)
    marathons = await conn.fetch("SELECT name, description, is_premium FROM marathons")
    await conn.close()

    keyboard = []
    text = "🎯 *Выбери марафон:*\n"
    for row in marathons:
        text += f"**{row['name']}** — {row['description']}\n"
        text += "💎 ПРЕМИУМ\n" if row['is_premium'] else "🆓 БЕСПЛАТНО\n"
        btn_text = f"{row['name']} (ПРЕМИУМ)" if row['is_premium'] else row['name']
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"marathon_{row['name']}")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def select_marathon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    marathon_name = query.data.replace("marathon_", "", 1)
    user_id = update.effective_user.id

    conn = await asyncpg.connect(DATABASE_URL)
    is_premium = await conn.fetchval("SELECT is_premium FROM marathons WHERE name = $1", marathon_name)

    if is_premium:
        await query.edit_message_text(
            f"🔒 Марафон *{marathon_name}* доступен по подписке.\n"
            "Скоро добавим оплату!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data="choose_marathon")
            ]]),
            parse_mode="Markdown"
        )
    else:
        await conn.execute('''
            UPDATE users SET current_marathon = $1, marathon_day = 1, last_task_date = $2
            WHERE user_id = $3
        ''', marathon_name, datetime.now().strftime('%Y-%m-%d'), user_id)
        await conn.close()

        keyboard = [
            [InlineKeyboardButton("✅ Начать марафон", callback_data="get_task")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎉 Отлично! Ты записан на марафон:\n"
            f"**{marathon_name}**\n"
            "Марафон начинается прямо сейчас!\n"
            "Готов к первому заданию? 💪",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def get_daily_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow('''
        SELECT current_marathon, marathon_day, last_task_date
        FROM users WHERE user_id = $1
    ''', user_id)
    await conn.close()

    if not row or not row['current_marathon']:
        await query.edit_message_text(
            "❌ Ты не участвуешь ни в одном марафоне!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")
            ]])
        )
        return

    marathon_name, day, last_date = row['current_marathon'], row['marathon_day'], row['last_task_date']
    today = datetime.now().strftime('%Y-%m-%d')

    if last_date == today:
        current_task = MARATHON_TASKS.get(marathon_name, ["Задание недоступно"])[day - 1]
        keyboard = [
            [InlineKeyboardButton("✅ Задание выполнено", callback_data="task_completed")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📋 Задание на сегодня (День {day}):\n"
            f"🎯 {current_task}\n"
            "Ты уже получил задание. Выполни и отметь!",
            reply_markup=reply_markup
        )
        return

    if day > 30:
        await query.edit_message_text(
            "🎉 Поздравляю! Ты завершил марафон! 💪",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 Новый марафон", callback_data="choose_marathon")
            ]])
        )
        return

    current_task = MARATHON_TASKS.get(marathon_name, ["Задание недоступно"])[day - 1]
    keyboard = [
        [InlineKeyboardButton("✅ Задание выполнено", callback_data="task_completed")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"📋 Задание на День {day}:\n"
        f"🎯 {current_task}\n"
        f"Марафон: {marathon_name}\n"
        f"Прогресс: {day}/30 дней\n"
        "Выполни и отметь! 💪",
        reply_markup=reply_markup
    )

async def task_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Отлично! Задание выполнено! 🎉")
    user_id = update.effective_user.id
    today = datetime.now().strftime('%Y-%m-%d')

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        UPDATE users SET marathon_day = marathon_day + 1, last_task_date = $1
        WHERE user_id = $2
    ''', today, user_id)
    new_day = await conn.fetchval("SELECT marathon_day FROM users WHERE user_id = $1", user_id)
    await conn.close()

    if new_day > 30:
        await query.edit_message_text(
            "🏆 *ПОЗДРАВЛЯЮ! ТЫ ЗАВЕРШИЛ МАРАФОН!*\n"
            "Ты молодец! Ты сформировал новую полезную привычку! 💪",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 Новый марафон", callback_data="choose_marathon")
            ]]),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            f"🎉 *Отлично! День {new_day-1} завершён!*\n"
            f"📈 Прогресс: **{new_day-1}/30 дней**\n"
            "Так держать! Увидимся завтра! 🚀",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")
            ]]),
            parse_mode="Markdown"
        )

async def my_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow('''
        SELECT current_marathon, marathon_day, registration_date
        FROM users WHERE user_id = $1
    ''', user_id)
    await conn.close()

    if not row:
        await query.edit_message_text("❌ Данные не найдены")
        return

    current_marathon, day, reg_date = row['current_marathon'], row['marathon_day'], row['registration_date']

    if not current_marathon:
        text = f"📊 *Твоя статистика:*\n📅 Дата регистрации: {reg_date}\n🎯 Активных марафонов: 0"
        keyboard = [[InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")]]
    else:
        progress_percent = min(day * 100 // 30, 100)
        progress_bar = "█" * (progress_percent // 10) + "░" * (10 - progress_percent // 10)
        text = (f"📊 *Твоя статистика:*\n"
                f"🎯 **{current_marathon}**\n"
                f"📅 День: **{day}/30**\n"
                f"📈 Прогресс: **{progress_percent}%**\n"
                f"[{progress_bar}]\n"
                f"📅 Зарегистрирован: {reg_date}")
        if day > 30:
            text += "\n🏆 *Марафон завершён!* 🎉"
        keyboard = [[InlineKeyboardButton("🎯 Новый марафон", callback_data="choose_marathon")]] \
            if day > 30 else [
            [InlineKeyboardButton("📋 Получить задание", callback_data="get_task")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = ("ℹ️ *Как работает бот:*\n"
            "1️⃣ Выбери марафон\n"
            "2️⃣ Получай задание каждый день\n"
            "3️⃣ Выполняй и отмечай ✅\n"
            "4️⃣ Через 30 дней — новая привычка!\n\n"
            "🎁 *Бесплатные марафоны:*\n"
            "• 📚 Чтение\n"
            "• 💪 Фитнес\n\n"
            "💎 *Премиум марафоны скоро:*\n"
            "• 🧘 Медитация\n"
            "• 💰 Финансы\n\n"
            "💬 По вопросам — пиши в поддержку!")

    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton("⏰ Напоминание", callback_data="set_reminder")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🏠 Главное меню", reply_markup=reply_markup)

# === Запуск бота ===
async def main():
    await init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Восстанавливаем напоминания при запуске
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT user_id, reminder_time FROM users WHERE reminder_time IS NOT NULL")
    await conn.close()

    for user_id, time_str in rows:
        if not time_str:
            continue
        try:
            hours, minutes = map(int, time_str.split(":"))
            app.job_queue.run_daily(
                send_daily_reminder,
                time=datetime_time(hour=hours, minute=minutes),
                data={"user_id": user_id},
                name=f"reminder_{user_id}"
            )
        except Exception as e:
            logger.warning(f"Не удалось восстановить напоминание для {user_id}: {e}")

    # Обработчики
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(choose_marathon, pattern="^choose_marathon$"))
    app.add_handler(CallbackQueryHandler(select_marathon, pattern="^marathon_"))
    app.add_handler(CallbackQueryHandler(get_daily_task, pattern="^get_task$"))
    app.add_handler(CallbackQueryHandler(task_completed, pattern="^task_completed$"))
    app.add_handler(CallbackQueryHandler(my_progress, pattern="^my_progress$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_to_start, pattern="^back_to_start$"))
    app.add_handler(CallbackQueryHandler(set_reminder, pattern="^set_reminder$"))
    app.add_handler(CallbackQueryHandler(request_custom_time, pattern="^remind_custom$"))
    app.add_handler(CallbackQueryHandler(save_reminder, pattern="^remind_(?!custom|off)"))
    app.add_handler(CallbackQueryHandler(save_reminder, pattern="^remind_off$"))
    app.add_handler(MessageHandler(filters.Regex(r"^\d{1,2}:\d{2}$"), handle_custom_time_input))

    logger.info("🚀 Бот запущен и начинает polling...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())