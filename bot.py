import asyncio
import sqlite3
import random
from datetime import datetime, date, timedelta
from pytz import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "8938274310:AAFfpqAIX-Kdf6FnqOv-PyvGCtuSITI_lDI"
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone=timezone("Europe/Moscow"))

def init_db():
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        nickname TEXT,
        xp INTEGER DEFAULT 0,
        coins INTEGER DEFAULT 50,
        brush_streak INTEGER DEFAULT 0,
        last_brush DATE,
        nails_streak INTEGER DEFAULT 0,
        last_nails DATE,
        water_count INTEGER DEFAULT 0,
        thyroxine_streak INTEGER DEFAULT 0,
        last_thyroxine DATE,
        total_tasks_done INTEGER DEFAULT 0,
        double_xp_day DATE,
        consecutive_days INTEGER DEFAULT 0,
        last_any_task_date DATE
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS daily_tasks (
        user_id INTEGER,
        task_id INTEGER,
        date DATE,
        completed BOOLEAN DEFAULT 0,
        PRIMARY KEY (user_id, task_id, date)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS achievements (
        user_id INTEGER,
        ach_name TEXT,
        unlocked_date DATE,
        PRIMARY KEY (user_id, ach_name)
    )''')
    conn.commit()
    conn.close()

init_db()

TASKS = {
    1: {"name": "💧 Выпить 1.5 л воды", "xp": 15, "coins": 5},
    2: {"name": "🚶 Пройти 6000 шагов", "xp": 20, "coins": 10},
    3: {"name": "✋ Не грызть ногти", "xp": 25, "coins": 10},
    4: {"name": "🦷 Почистить зубы вечером", "xp": 10, "coins": 5},
    5: {"name": "💊 Принять тироксин", "xp": 15, "coins": 5}
}

LEVELS = [
    (0, "Ленивец"), (100, "Новичок"), (300, "Худеющий"), (600, "Зубная фея"),
    (1000, "Мастер ногтей"), (1500, "Здоровяк"), (2500, "Легенда"),
    (4000, "Абсолют"), (6000, "Бессмертный"), (9000, "ЗОЖ-бог")
]

def get_rank(xp):
    for i in range(len(LEVELS)-1, -1, -1):
        if xp >= LEVELS[i][0]:
            return LEVELS[i][1]
    return "Ленивец"

def get_today_str():
    return datetime.now(timezone("Europe/Moscow")).date().isoformat()

def add_coins(user_id, amount):
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def complete_task(user_id, task_id):
    today = get_today_str()
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO daily_tasks (user_id, task_id, date, completed) VALUES (?,?,?,0)", (user_id, task_id, today))
    cur.execute("SELECT completed FROM daily_tasks WHERE user_id=? AND task_id=? AND date=?", (user_id, task_id, today))
    row = cur.fetchone()
    if row and row[0] == 0:
        cur.execute("UPDATE daily_tasks SET completed=1 WHERE user_id=? AND task_id=? AND date=?", (user_id, task_id, today))
        xp_reward = TASKS[task_id]["xp"]
        coin_reward = TASKS[task_id]["coins"]
        cur.execute("SELECT double_xp_day FROM users WHERE user_id=?", (user_id,))
        double_day = cur.fetchone()[0]
        if double_day == today:
            xp_reward *= 2
        conn.close()
        conn = sqlite3.connect("game_bot.db")
        cur = conn.cursor()
        cur.execute("UPDATE users SET xp = xp + ? WHERE user_id=?", (xp_reward, user_id))
        cur.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (coin_reward, user_id))
        if task_id == 1:
            cur.execute("UPDATE users SET water_count = water_count + 1 WHERE user_id=?", (user_id,))
        elif task_id == 4:
            cur.execute("UPDATE users SET brush_streak = brush_streak + 1, last_brush=? WHERE user_id=?", (today, user_id))
        elif task_id == 3:
            cur.execute("UPDATE users SET nails_streak = nails_streak + 1, last_nails=? WHERE user_id=?", (today, user_id))
        elif task_id == 5:
            cur.execute("UPDATE users SET thyroxine_streak = thyroxine_streak + 1, last_thyroxine=? WHERE user_id=?", (today, user_id))
        cur.execute("UPDATE users SET total_tasks_done = total_tasks_done + 1 WHERE user_id=?", (user_id,))
        cur.execute("SELECT last_any_task_date FROM users WHERE user_id=?", (user_id,))
        last_date_str = cur.fetchone()[0]
        if last_date_str == (datetime.now(timezone("Europe/Moscow")).date() - timedelta(days=1)).isoformat():
            cur.execute("UPDATE users SET consecutive_days = consecutive_days + 1, last_any_task_date=? WHERE user_id=?", (today, user_id))
        elif last_date_str != today:
            cur.execute("UPDATE users SET consecutive_days = 1, last_any_task_date=? WHERE user_id=?", (today, user_id))
        conn.commit()
        conn.close()
        return True, xp_reward, coin_reward, ""
    conn.close()
    return False, 0, 0, ""

def main_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Задания", callback_data="tasks"),
         InlineKeyboardButton(text="✅ Выполнил", callback_data="complete_menu")],
        [InlineKeyboardButton(text="🍽 Записать еду", callback_data="food"),
         InlineKeyboardButton(text="🏆 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🛍 Магазин", callback_data="shop"),
         InlineKeyboardButton(text="🏅 Достижения", callback_data="achievements")],
        [InlineKeyboardButton(text="💪 Подбодрить", callback_data="cheer"),
         InlineKeyboardButton(text="📊 Топ", callback_data="top")],
        [InlineKeyboardButton(text="💊 Тироксин", callback_data="thyroxine"),
         InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])
    return kb

def tasks_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1. 💧 Вода", callback_data="complete_1"),
         InlineKeyboardButton(text="2. 🚶 Шаги", callback_data="complete_2")],
        [InlineKeyboardButton(text="3. ✋ Ногти", callback_data="complete_3"),
         InlineKeyboardButton(text="4. 🦷 Зубы", callback_data="complete_4")],
        [InlineKeyboardButton(text="5. 💊 Тироксин", callback_data="complete_5")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back_main")]
    ])
    return kb

def shop_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 Пропуск задания (30🪙)", callback_data="buy_skip")],
        [InlineKeyboardButton(text="⚡ Удвоитель опыта (50🪙)", callback_data="buy_double")],
        [InlineKeyboardButton(text="✨ Сменить ник (40🪙)", callback_data="buy_rename")],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back_main")]
    ])
    return kb

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, nickname) VALUES (?,?)", (user_id, message.from_user.first_name))
    conn.commit()
    conn.close()
    await message.answer(
        f"🔥 Привет, {message.from_user.first_name}! Это игровой ЗОЖ-бот.\nТвои параметры: 176 см / 110 кг, гипотиреоз.\n\nКаждый день в 8:00 МСК я присылаю 5 заданий.\nВыполняй, получай опыт и монеты, повышай ранг!\n\nВажно: бот не заменяет врача.",
        reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "tasks")
async def show_tasks(callback: CallbackQuery):
    user_id = callback.from_user.id
    today = get_today_str()
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    text = "📋 *Задания на сегодня:*\n\n"
    for tid, info in TASKS.items():
        cur.execute("SELECT completed FROM daily_tasks WHERE user_id=? AND task_id=? AND date=?", (user_id, tid, today))
        row = cur.fetchone()
        status = "✅" if row and row[0] else "⬜"
        text += f"{status} {info['name']}  +{info['xp']}XP / +{info['coins']}🪙\n"
    conn.close()
    await callback.message.edit_text(text, reply_markup=tasks_keyboard(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("complete_"))
async def complete_task_cb(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    success, xp, coins, _ = complete_task(user_id, task_id)
    if success:
        await callback.answer(f"✅ +{xp} XP, +{coins} монет!", show_alert=True)
        await show_tasks(callback)
    else:
        await callback.answer("Уже выполнено сегодня!", show_alert=True)

@dp.callback_query(lambda c: c.data == "complete_menu")
async def complete_menu(callback: CallbackQuery):
    await show_tasks(callback)

@dp.callback_query(lambda c: c.data == "profile")
async def profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT xp, coins, brush_streak, nails_streak, water_count, thyroxine_streak, total_tasks_done, consecutive_days, nickname FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    if res:
        xp, coins, brush_str, nails_str, water_cnt, thyro_str, total_done, consec_days, nick = res
        rank = get_rank(xp)
        text = f"👤 *{nick}*\n🏅 *Ранг:* {rank}\n⚡ *Опыт:* {xp}\n🪙 *Монеты:* {coins}\n🦷 *Чистка зубов:* {brush_str} дн.\n✋ *Без грызения:* {nails_str} дн.\n💧 *Водные дни:* {water_cnt}\n💊 *Тироксин:* {thyro_str} дн.\n📊 *Всего заданий:* {total_done}\n🔥 *Серия дней:* {consec_days}"
    else:
        text = "Ошибка профиля"
    conn.close()
    await callback.message.edit_text(text, reply_markup=main_keyboard(), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "achievements")
async def list_achievements(callback: CallbackQuery):
    text = "🏅 Достижения будут позже"
    await callback.message.edit_text(text, reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "shop")
async def shop_menu(callback: CallbackQuery):
    await callback.message.edit_text("🛍 Магазин временно не работает", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cheer")
async def cheer(callback: CallbackQuery):
    phrases = ["Ты молодец!", "Так держать!", "Всё получится!"]
    await callback.answer(random.choice(phrases), show_alert=True)

@dp.callback_query(lambda c: c.data == "top")
async def top_players(callback: CallbackQuery):
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT nickname, xp FROM users ORDER BY xp DESC LIMIT 10")
    top = cur.fetchall()
    text = "🏆 Топ игроков:\n"
    for i, (name, xp) in enumerate(top, 1):
        text += f"{i}. {name} – {xp} XP\n"
    conn.close()
    await callback.message.edit_text(text, reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "thyroxine")
async def thyroxine_info(callback: CallbackQuery):
    await callback.message.answer("💊 Принимай L-тироксин утром натощак, за 30 минут до еды.", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "help")
async def help_cmd(callback: CallbackQuery):
    await callback.message.answer("❓ Нажимай кнопки, выполняй задания, получай награды!", reply_markup=main_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "food")
async def food_log(callback: CallbackQuery):
    await callback.message.answer("🍽 Запись еды: просто напиши что съел. Бот даст +2 монеты.", reply_markup=main_keyboard())
    await callback.answer()

async def send_daily_tasks():
    conn = sqlite3.connect("game_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()
    for (user_id,) in users:
        try:
            text = "🌞 Доброе утро! Твои задания на сегодня:\n\n"
            for tid, info in TASKS.items():
                text += f"⬜ {info['name']} +{info['xp']}XP / +{info['coins']}🪙\n"
            await bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=main_keyboard())
        except:
            pass

scheduler.add_job(send_daily_tasks, "cron", hour=8, minute=0, timezone=timezone("Europe/Moscow"))
scheduler.start()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())