# main.py
import os
import asyncio
import asyncpg
from datetime import datetime, time as datetime_time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import logging

# === Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Токен и URL базы из переменных окружения ===
BOT_TOKEN = os.getenv("8452366284:AAG9YOhS8mdibwfZ0lV8T-15FK0qAK7yqYg")
DATABASE_URL = os.getenv("postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:5432/${{PGDATABASE}}")

if not BOT_TOKEN:
    raise ValueError("❌ Переменная окружения BOT_TOKEN не установлена!")
if not DATABASE_URL:
    raise ValueError("❌ Переменная окружения DATABASE_URL не установлена!")

# === Инициализация базы данных ===
async def init_db():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                current_marathon TEXT,
                marathon_day INTEGER DEFAULT 1,
                last_task_date TEXT,
                reminder_time TEXT
            )
        ''')
        await conn.close()
        logger.info("✅ База данных инициализирована в PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе: {e}")

# === Команда /start ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    if not row:
        await conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
    await conn.close()

    keyboard = [
        [InlineKeyboardButton("🏃‍♂️ Выбрать марафон", callback_data="choose_marathon")],
        [InlineKeyboardButton("📈 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("⏰ Установить напоминание", callback_data="set_reminder")]
    ]
    await update.message.reply_text(
        "👋 Привет! Я помогу тебе прокачать привычки. Выбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === Выбор марафона ===
async def choose_marathon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🧘 Медитация", callback_data="marathon_meditation")],
        [InlineKeyboardButton("🏃 Бег", callback_data="marathon_running")],
        [InlineKeyboardButton("📚 Чтение", callback_data="marathon_reading")]
    ]
    await query.edit_message_text("Выбери марафон:", reply_markup=InlineKeyboardMarkup(keyboard))

# === Сохранение выбранного марафона ===
async def select_marathon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    marathon = query.data.replace("marathon_", "").replace("_", " ").title()

    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
        UPDATE users SET current_marathon = $1, marathon_day = 1, last_task_date = NULL 
        WHERE user_id = $2
    ''', marathon, user_id)
    await conn.close()

    await query.edit_message_text(
        f"🎉 Отлично! Ты начал марафон: **{marathon}**\nДень 1/30 — вперёд к цели!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Получить задание", callback_data="get_task")
        ]])
    )

# === Получение задания ===
async def get_daily_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT current_marathon, marathon_day FROM users WHERE user_id = $1", user_id)
    await conn.close()

    if not row or not row['current_marathon']:
        await query.edit_message_text("Сначала выбери марафон!")
        return

    task = f"Выполни 10 минут {row['current_marathon'].lower()} сегодня!"
    await query.edit_message_text(
        f"🎯 *Задание на день {row['marathon_day']}*:\n{task}\nУдачи!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Выполнено", callback_data="task_completed")
        ]])
    )

# === Подтверждение выполнения ===
async def task_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT marathon_day, current_marathon FROM users WHERE user_id = $1", user_id)
    if row and row['current_marathon']:
        new_day = row['marathon_day'] + 1
        today = datetime.now().strftime('%Y-%m-%d')
        await conn.execute('''
            UPDATE users SET marathon_day = $1, last_task_date = $2 WHERE user_id = $3
        ''', new_day, today, user_id)
        await query.edit_message_text(
            f"🎉 Отлично! Ты на дне {new_day}/30. Так держать!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Следующее задание", callback_data="get_task")
            ]])
        )
    await conn.close()

# === Прогресс пользователя ===
async def my_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    conn = await asyncpg.connect(DATABASE_URL)
    row = await conn.fetchrow("SELECT current_marathon, marathon_day FROM users WHERE user_id = $1", user_id)
    await conn.close()

    if not row or not row['current_marathon']:
        text = "Ты ещё не начал ни один марафон."
    else:
        text = f"🎯 Ты проходишь марафон: *{row['current_marathon']}*\n📅 День: {row['marathon_day']}/30"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
        ]])
    )

# === Помощь ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📚 *Помощь:*\n\n"
        "• /start — начать\n"
        "• Выбери марафон и получай задания каждый день\n"
        "• Нажми ✅ Выполнено после выполнения задания\n"
        "• Установи напоминание, чтобы не забыть\n"
        "• Прогресс сохраняется автоматически",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
        ]])
    )

# === Назад в меню ===
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start_command(update, context)

# === Установить напоминание ===
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⏰ 8:00", callback_data="remind_8:00")],
        [InlineKeyboardButton("⏰ 9:00", callback_data="remind_9:00")],
        [InlineKeyboardButton("⏰ 20:00", callback_data="remind_20:00")],
        [InlineKeyboardButton("🕒 Другое время", callback_data="remind_custom")],
        [InlineKeyboardButton("🔕 Отключить", callback_data="remind_off")]
    ]
    await query.edit_message_text("Выбери время напоминания:", reply_markup=InlineKeyboardMarkup(keyboard))

# === Обработка выбора времени ===
async def save_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # 🔐 Защита: проверяем, доступен ли job_queue
    if context.job_queue is None:
        await query.edit_message_text(
            "❌ Ошибка: система напоминаний временно недоступна. Перезапустите бота."
        )
        return

    user_id = update.effective_user.id
    data = query.data
    job_name = f"reminder_{user_id}"

    # Удаляем старое напоминание
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

    if data == "remind_off":
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE users SET reminder_time = NULL WHERE user_id = $1", user_id)
        await conn.close()
        await query.edit_message_text(
            "🔕 Напоминания отключены.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
            ]])
        )
        return

    time_str = data.replace("remind_", "")
    try:
        hours, minutes = map(int, time_str.split(":"))
        # Устанавливаем новое напоминание
        context.job_queue.run_daily(
            send_daily_reminder,
            time=datetime_time(hour=hours, minute=minutes),
            data={"user_id": user_id},
            name=job_name
        )
        # Сохраняем в базу
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE users SET reminder_time = $1 WHERE user_id = $2", time_str, user_id)
        await conn.close()
        await query.edit_message_text(
            f"✅ Напоминание установлено на **{time_str}** каждый день! ⏰",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
            ]]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка при установке напоминания: {e}")
        await query.edit_message_text("❌ Не удалось установить напоминание.")

# === Ввод своего времени ===
async def request_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите время в формате ЧЧ:ММ (например, 7:30)")

# === Обработка ввода времени ===
async def handle_custom_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    try:
        hours, minutes = map(int, text.split(":"))
        if 0 <= hours < 24 and 0 <= minutes < 60:
            job_name = f"reminder_{user_id}"
            if context.job_queue:
                for job in context.job_queue.get_jobs_by_name(job_name):
                    job.schedule_removal()
                context.job_queue.run_daily(
                    send_daily_reminder,
                    time=datetime_time(hour=hours, minute=minutes),
                    data={"user_id": user_id},
                    name=job_name
                )
                conn = await asyncpg.connect(DATABASE_URL)
                await conn.execute("UPDATE users SET reminder_time = $1 WHERE user_id = $2", text, user_id)
                await conn.close()
                await update.message.reply_text(
                    f"✅ Напоминание установлено на {text}!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
                    ]])
                )
            else:
                await update.message.reply_text("❌ Ошибка: напоминания недоступны.")
        else:
            await update.message.reply_text("❌ Неверное время. Введите от 00:00 до 23:59.")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте ЧЧ:ММ.")

# === Ежедневное напоминание ===
async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.data["user_id"]

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow('''
            SELECT current_marathon, marathon_day, last_task_date 
            FROM users WHERE user_id = $1
        ''', user_id)
        await conn.close()

        if not row or not row['current_marathon']:
            return

        today = datetime.now().strftime('%Y-%m-%d')
        if row['last_task_date'] == today:
            return  # Уже выполнил

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"⏰ *Напоминание!*\n"
                f"Не забудь сегодняшнее задание:\n"
                f"🎯 **{row['current_marathon']}**\n"
                f"📅 День {row['marathon_day']}/30\n"
                f"Нажми, чтобы посмотреть!"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Получить задание", callback_data="get_task")
            ]]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Ошибка отправки напоминания {user_id}: {e}")

# === Главная функция запуска бота ===
async def run_bot():
    await init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # 🔄 Восстанавливаем напоминания из базы
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch("SELECT user_id, reminder_time FROM users WHERE reminder_time IS NOT NULL")
        await conn.close()

        for user_id, time_str in rows:
            if not time_str:
                continue
            try:
                hours, minutes = map(int, time_str.split(":"))
                job_name = f"reminder_{user_id}"
                if app.job_queue:
                    for job in app.job_queue.get_jobs_by_name(job_name):
                        job.schedule_removal()
                    app.job_queue.run_daily(
                        send_daily_reminder,
                        time=datetime_time(hour=hours, minute=minutes),
                        data={"user_id": user_id},
                        name=job_name
                    )
                    logger.info(f"✅ Напоминание восстановлено для {user_id} на {time_str}")
            except Exception as e:
                logger.warning(f"❌ Не удалось восстановить напоминание для {user_id}: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка при восстановлении напоминаний: {e}")

    # 📌 Обработчики
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

    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            poll_interval=2.0,
            drop_pending_updates=False,
            allowed_updates=Update.ALL_TYPES
        )
        await asyncio.Event().wait()  # Ждём вечно
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")
    finally:
        await app.updater.stop()
        await app.stop()

# === Запуск бота (для Railway) ===
def main():
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(run_bot())
            logger.info("✅ Задача добавлена в уже запущенный event loop")
    except RuntimeError:
        # Нет активного loop — создаём
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())

if __name__ == '__main__':
    main()
