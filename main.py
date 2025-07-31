import logging
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# Замените на ваш токен от BotFather
BOT_TOKEN = "8452366284:AAG9YOhS8mdibwfZ0lV8T-15FK0qAK7yqYg"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('habit_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            registration_date TEXT,
            current_marathon TEXT,
            marathon_day INTEGER DEFAULT 0,
            last_task_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marathons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            is_premium INTEGER DEFAULT 0,
            price INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM marathons')
    count = cursor.fetchone()[0]
    if count == 0:
        marathons = [
            ("📚 Чтение", "30 дней формирования привычки к чтению", 0, 0),
            ("💪 Фитнес", "30 дней физической активности", 0, 0),
            ("🧘 Медитация", "30 дней осознанности", 1, 150),
            ("💰 Финансы", "30 дней финансовой грамотности", 1, 200)
        ]
        cursor.executemany('''
            INSERT INTO marathons (name, description, is_premium, price) 
            VALUES (?, ?, ?, ?)
        ''', marathons)
    conn.commit()
    conn.close()

# Задания для марафонов
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
        "Прочитай в тишине 30 минут",
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

async def start_command(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name

    conn = sqlite3.connect('habit_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, registration_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

    keyboard = [
        [InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")],
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

async def choose_marathon(update: Update, context):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect('habit_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, description, is_premium, price FROM marathons')
    marathons = cursor.fetchall()
    conn.close()

    keyboard = []
    text = "🎯 Выбери марафон:\n"
    for name, desc, is_premium, price in marathons:
        text += f"{name} - {desc}\n"
        text += f"💎 ПРЕМИУМ - {price}₽\n" if is_premium else "🆓 БЕСПЛАТНО\n"
        btn_text = f"{name} (ПРЕМИУМ)" if is_premium else name
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"marathon_{name}")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def select_marathon(update: Update, context):
    query = update.callback_query
    await query.answer()
    marathon_name = query.data.replace("marathon_", "")
    user_id = update.effective_user.id

    conn = sqlite3.connect('habit_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_premium, price FROM marathons WHERE name = ?', (marathon_name,))
    result = cursor.fetchone()

    if result and result[0]:
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_{marathon_name}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="choose_marathon")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"💎 {marathon_name}\n"
            f"Стоимость: {result[1]}₽\n"
            "• 30 персонализированных заданий\n"
            "• Подробные инструкции\n"
            "• Мотивационный контент\n"
            "• Сертификат о прохождении\n"
            "Оплатить марафон?",
            reply_markup=reply_markup
        )
    else:
        cursor.execute('''
            UPDATE users SET current_marathon = ?, marathon_day = 1, last_task_date = ?
            WHERE user_id = ?
        ''', (marathon_name, datetime.now().strftime('%Y-%m-%d'), user_id))
        conn.commit()
        conn.close()

        keyboard = [
            [InlineKeyboardButton("✅ Получить первое задание", callback_data="get_task")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🎉 Отлично! Ты записан на марафон:\n{marathon_name}\n"
            "Марафон начинается прямо сейчас!\n"
            "Готов к первому заданию?",
            reply_markup=reply_markup
        )

async def get_daily_task(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    conn = sqlite3.connect('habit_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT current_marathon, marathon_day, last_task_date 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result or not result[0]:
        await query.edit_message_text(
            "❌ Ты не участвуешь ни в одном марафоне!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")
            ]])
        )
        return

    marathon_name, day, last_date = result
    today = datetime.now().strftime('%Y-%m-%d')

    if last_date == today:
        current_task = MARATHON_TASKS[marathon_name][day - 1] if marathon_name in MARATHON_TASKS else "Задание дня"
        keyboard = [
            [InlineKeyboardButton("✅ Задание выполнено", callback_data="task_completed")],
            [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📋 Твое задание на сегодня (День {day}):\n"
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

    current_task = MARATHON_TASKS[marathon_name][day - 1] if marathon_name in MARATHON_TASKS else "Задание дня"
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
        "Выполни и отметь завершение! 💪",
        reply_markup=reply_markup
    )

async def task_completed(update: Update, context):
    query = update.callback_query
    await query.answer("Отлично! Задание выполнено! 🎉")
    user_id = update.effective_user.id
    today = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect('habit_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET marathon_day = marathon_day + 1, last_task_date = ?
        WHERE user_id = ?
    ''', (today, user_id))
    cursor.execute('SELECT marathon_day FROM users WHERE user_id = ?', (user_id,))
    new_day = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    if new_day > 30:
        await query.edit_message_text(
            "🏆 ПОЗДРАВЛЯЮ! ТЫ ЗАВЕРШИЛ МАРАФОН! 🏆\n"
            "Ты молодец! Ты сформировал новую привычку! 💪",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 Новый марафон", callback_data="choose_marathon")]
            ])
        )
    else:
        await query.edit_message_text(
            f"🎉 Отлично! День {new_day-1} завершен!\n"
            f"Прогресс: {new_day-1}/30 дней\n"
            "Так держать! Увидимся завтра! 🚀",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")]
            ])
        )

async def my_progress(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    conn = sqlite3.connect('habit_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT current_marathon, marathon_day, registration_date 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        await query.edit_message_text("❌ Данные не найдены")
        return

    current_marathon, day, reg_date = result
    if not current_marathon:
        text = f"📊 Твоя статистика:\n📅 Дата регистрации: {reg_date}\n🎯 Активных марафонов: 0"
        keyboard = [[InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")]]
    else:
        progress_percent = min(day * 100 // 30, 100)
        progress_bar = "█" * (progress_percent // 10) + "░" * (10 - progress_percent // 10)
        text = (f"📊 Твоя статистика:\n"
                f"🎯 Текущий марафон: {current_marathon}\n"
                f"📅 День: {day}/30\n"
                f"📈 Прогресс: {progress_percent}% [{progress_bar}]\n"
                f"📅 Дата регистрации: {reg_date}\n")
        if day > 30:
            text += "🏆 Марафон завершён! 🎉"
            keyboard = [[InlineKeyboardButton("🎯 Новый марафон", callback_data="choose_marathon")]]
        else:
            keyboard = [
                [InlineKeyboardButton("🎯 Получить задание", callback_data="get_task")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]
            ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def help_command(update: Update, context):
    query = update.callback_query
    await query.answer()
    text = ("ℹ️ Как работает бот:\n"
            "1️⃣ Выбери марафон\n"
            "2️⃣ Каждый день получай задание\n"
            "3️⃣ Выполняй и отмечай ✅\n"
            "4️⃣ Через 30 дней — новая привычка!\n\n"
            "🆓 Бесплатные:\n• 📚 Чтение\n• 💪 Фитнес\n\n"
            "💎 Премиум:\n• 🧘 Медитация (150₽)\n• 💰 Финансы (200₽)")
    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def back_to_start(update: Update, context):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🎯 Выбрать марафон", callback_data="choose_marathon")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="my_progress")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🏠 Главное меню", reply_markup=reply_markup)

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(choose_marathon, pattern="choose_marathon"))
    app.add_handler(CallbackQueryHandler(select_marathon, pattern="marathon_"))
    app.add_handler(CallbackQueryHandler(get_daily_task, pattern="get_task"))
    app.add_handler(CallbackQueryHandler(task_completed, pattern="task_completed"))
    app.add_handler(CallbackQueryHandler(my_progress, pattern="my_progress"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="help"))
    app.add_handler(CallbackQueryHandler(back_to_start, pattern="back_to_start"))

    print("Бот запущен! Нажмите Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()