# main.py
import os
import asyncio
import asyncpg
from datetime import datetime, time as datetime_time
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import logging

# === Настройка логирования ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")  # По умолчанию Москва
if not BOT_TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не установлена.")
if not DATABASE_URL:
    raise RuntimeError("❌ Переменная окружения DATABASE_URL не установлена.")

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
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        raise

# === Команда /start ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not row:
            await conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Ошибка при работе с БД: {e}")
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
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute('''
            UPDATE users SET current_marathon = $1, marathon_day = 1, last_task_date = NULL 
            WHERE user_id = $2
        ''', marathon, user_id)
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении марафона: {e}")
    await query.edit_message_text(
        f"🎉 Отлично! Ты начал марафон: {marathon}\n"
        f"День 1/30 — вперёд к цели!",
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
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT current_marathon, marathon_day FROM users WHERE user_id = $1", user_id)
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Ошибка при получении данных: {e}")
        await query.edit_message_text("⚠️ Не удалось получить данные. Попробуйте позже.")
        return
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
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT marathon_day FROM users WHERE user_id = $1", user_id)
        if row:
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
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении прогресса: {e}")
        await query.edit_message_text("⚠️ Не удалось обновить прогресс.")

# === Прогресс пользователя ===
async def my_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT current_marathon, marathon_day FROM users WHERE user_id = $1", user_id)
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Ошибка при получении прогресса: {e}")
        await query.edit_message_text("⚠️ Ошибка загрузки прогресса.")
        return
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

# === Настройка напоминаний ===
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⏰ 8:00", callback_data="remind_8:00")],
        [InlineKeyboardButton("⏰ 9:00", callback_data="remind_9:00")],
        [InlineKeyboardButton("⏰ 10:00", callback_data="remind_10:00")],
        [InlineKeyboardButton("🕒 Свое время", callback_data="remind_custom")],
        [InlineKeyboardButton("🔕 Отключить", callback_data="remind_off")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")]
    ]
    await query.edit_message_text("Выбери время напоминания:", reply_markup=InlineKeyboardMarkup(keyboard))

# === Ввод своего времени ===
async def request_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите время в формате ЧЧ:ММ (например, 18:30)")

# === Обработка своего времени ===
async def handle_custom_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    time_str = update.message.text.strip()
    try:
        hours, minutes = map(int, time_str.split(":"))
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используй ЧЧ:ММ (например, 18:30)")
        return
    
    # Проверяем, что job_queue доступен
    if context.job_queue is None:
        await update.message.reply_text("❌ Ошибка: система напоминаний временно недоступна.")
        return
    
    job_name = f"reminder_{user_id}"
    # Удаляем старое напоминание
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
    
    # Устанавливаем новое напоминание с учетом часового пояса
    context.job_queue.run_daily(
        send_daily_reminder,
        time=datetime_time(hour=hours, minute=minutes),
        data={"user_id": user_id},
        name=job_name
    )
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE users SET reminder_time = $1 WHERE user_id = $2", time_str, user_id)
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения времени напоминания: {e}")
    
    await update.message.reply_text(
        f"✅ Напоминание установлено на **{time_str}**! ⏰",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
        ]]),
        parse_mode="Markdown"
    )

# === Сохранение напоминания ===
async def save_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    # Проверяем, что job_queue доступен
    if context.job_queue is None:
        await query.edit_message_text("❌ Ошибка: система напоминаний временно недоступна.")
        return
    
    job_name = f"reminder_{user_id}"
    # Удаляем старое напоминание
    for job in context.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
    
    if data == "remind_off":
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            await conn.execute("UPDATE users SET reminder_time = NULL WHERE user_id = $1", user_id)
            await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка отключения напоминания: {e}")
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
        context.job_queue.run_daily(
            send_daily_reminder,
            time=datetime_time(hour=hours, minute=minutes),
            data={"user_id": user_id},
            name=job_name
        )
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("UPDATE users SET reminder_time = $1 WHERE user_id = $2", time_str, user_id)
        await conn.close()
        await query.edit_message_text(
            f"✅ Напоминание установлено на **{time_str}**! ⏰",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
            ]]),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при установке напоминания: {e}")
        await query.edit_message_text("❌ Не удалось установить напоминание.")

# === Ежедневное напоминание ===
async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.data["user_id"]
    logger.info(f"⏰ Запуск напоминания для пользователя {user_id}")  # <-- Добавлено
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow('''
            SELECT current_marathon, marathon_day, last_task_date FROM users WHERE user_id = $1
        ''', user_id)
        await conn.close()
        if not row or not row['current_marathon']:
            logger.info(f"❌ Нет данных о марафоне для {user_id}")
            return
        today = datetime.now().strftime('%Y-%m-%d')
        if row['last_task_date'] == today:
            logger.info(f"✅ Пользователь {user_id} уже выполнил задание сегодня")
            return  # Уже выполнил
        logger.info(f"✅ Отправка напоминания пользователю {user_id}")
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
        logger.warning(f"❌ Ошибка отправки напоминания {user_id}: {e}")

# === Назад в меню ===
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🏃‍♂️ Выбрать марафон", callback_data="choose_marathon")],
        [InlineKeyboardButton("📈 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("⏰ Установить напоминание", callback_data="set_reminder")]
    ]
    await query.edit_message_text("Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

# === Помощь ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "ℹ️ Помощь:\n"
        "• /start — начать\n"
        "• Нажми на кнопки, чтобы выбрать марафон и получать задания\n"
        "• Установи напоминание, чтобы не забывать\n"
        "• Отмечай выполнение заданий\n"
        "• Прогресс сохраняется в базе данных",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
        ]])
    )

# === Запуск бота ===
async def run_bot():
    await init_db()
    # Создаём Application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # === 🔥 СНАЧАЛА initialize() и start() ===
    await app.initialize()
    await app.start()
    
    # === Восстановление напоминаний из базы ===
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
                app.job_queue.run_daily(
                    send_daily_reminder,
                    time=datetime_time(hour=hours, minute=minutes),
                    data={"user_id": user_id},
                    name=job_name
                )
                logger.info(f"✅ Напоминание восстановлено для {user_id} на {time_str}")
            except Exception as e:
                logger.warning(f"❌ Не удалось восстановить напоминание: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка при восстановлении напоминаний: {e}")
    
    # === Обработчики ===
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
    app.add_handler(CallbackQueryHandler(save_reminder, pattern="^remind_off$"))
    app.add_handler(CallbackQueryHandler(save_reminder, pattern="^remind_\\d{1,2}:\\d{2}$"))
    app.add_handler(MessageHandler(filters.Regex(r"^\d{1,2}:\d{2}$"), handle_custom_time_input))
    
    logger.info("🚀 Бот запущен и начинает polling...")
    # Запуск polling
    await app.updater.start_polling(
        poll_interval=2.0,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )
    await asyncio.Event().wait()  # Бесконечно ждём

# === Точка входа ===
if __name__ == '__main__':
    asyncio.run(run_bot())