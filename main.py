import asyncio
import logging
import aiosqlite
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Bot tokeni (Xavfsizlik uchun bu yerga tokeningizni yozing yoki Environment Variable ishlating)
TOKEN = "8253888597:AAHgdufA4zg1DKmnt_C3mQ19RP9updrLRAQ"

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Bot va Dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Ma'lumotlar bazasini sozlash
DB_PATH = "dating_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                age INTEGER,
                gender TEXT,
                photo_id TEXT,
                bio TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                from_user_id INTEGER,
                to_user_id INTEGER,
                is_like INTEGER,
                PRIMARY KEY (from_user_id, to_user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                user1_id INTEGER,
                user2_id INTEGER,
                PRIMARY KEY (user1_id, user2_id)
            )
        """)
        await db.commit()

# FSM holatlari
class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    photo = State()
    bio = State()

class Chatting(StatesGroup):
    active_chat = State()

# Asosiy menyu klaviaturasi
def main_menu():
    kb = [
        [KeyboardButton(text="🔍 Tanishuvni boshlash")],
        [KeyboardButton(text="👤 Mening profilim"), KeyboardButton(text="💬 Chatlar")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,)) as cursor:
            user = await cursor.fetchone()
            
    if user:
        await message.answer(f"Xush kelibsiz, {user[2]}! Tanishuvni boshlaymizmi?", reply_markup=main_menu())
    else:
        await message.answer("Xush kelibsiz! Tanishuv botidan foydalanish uchun avval ro'yxatdan o'ting.\nIsmingizni kiriting:")
        await state.set_state(Registration.name)

# Ro'yxatdan o'tish jarayoni
@dp.message(Registration.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Yoshingizni kiriting:")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or not (16 <= int(message.text) <= 99):
        await message.answer("Iltimos, yoshingizni raqamda kiriting (16-99 oralig'ida):")
        return
    await state.update_data(age=int(message.text))
    
    kb = [
        [KeyboardButton(text="Erkak"), KeyboardButton(text="Ayol")]
    ]
    markup = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Jinsingizni tanlang:", reply_markup=markup)
    await state.set_state(Registration.gender)

@dp.message(Registration.gender, F.text.in_(["Erkak", "Ayol"]))
async def process_gender(message: types.Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await message.answer("O'zingiz haqingizda qisqacha ma'lumot yozing (bio):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Registration.bio)

@dp.message(Registration.bio)
async def process_bio(message: types.Message, state: FSMContext):
    await state.update_data(bio=message.text)
    await message.answer("Profilingiz uchun rasm yuboring:")
    await state.set_state(Registration.photo)

@dp.message(Registration.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, full_name, age, gender, photo_id, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message.from_user.id, message.from_user.username, data['name'], data['age'], data['gender'], photo_id, data['bio']))
        await db.commit()
    
    await state.clear()
    await message.answer("Tabriklaymiz! Ro'yxatdan muvaffaqiyatli o'tdingiz.", reply_markup=main_menu())

# Profilni ko'rish
@dp.message(F.text == "👤 Mening profilim")
async def my_profile(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,)) as cursor:
            user = await cursor.fetchone()
    
    if user:
        caption = f"👤 {user[2]}, {user[3]}\n👫 Jinsi: {user[4]}\n📝 Bio: {user[6]}"
        await message.answer_photo(user[5], caption=caption)
    else:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start bosing.")

# Tanishuv (Qidiruv)
@dp.message(F.text == "🔍 Tanishuvni boshlash")
async def start_discovery(message: types.Message):
    await show_next_profile(message)

async def show_next_profile(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT * FROM users 
            WHERE user_id != ? 
            AND user_id NOT IN (SELECT to_user_id FROM likes WHERE from_user_id = ?)
            ORDER BY RANDOM() LIMIT 1
        """, (message.from_user.id, message.from_user.id)) as cursor:
            target = await cursor.fetchone()
    
    if target:
        caption = f"👤 {target[2]}, {target[3]}\n📝 Bio: {target[6]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="❤️ Like", callback_data=f"like_{target[0]}"),
                InlineKeyboardButton(text="👎 Dislike", callback_data=f"dislike_{target[0]}")
            ]
        ])
        await message.answer_photo(target[5], caption=caption, reply_markup=kb)
    else:
        await message.answer("Hozircha yangi profillar yo'q. Keyinroq urinib ko'ring.")

@dp.callback_query(F.data.startswith("like_") | F.data.startswith("dislike_"))
async def handle_vote(callback: types.CallbackQuery):
    action, target_id = callback.data.split("_")
    target_id = int(target_id)
    is_like = 1 if action == "like" else 0
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO likes (from_user_id, to_user_id, is_like) VALUES (?, ?, ?)",
                         (callback.from_user.id, target_id, is_like))
        await db.commit()
        
        if is_like:
            async with db.execute("SELECT * FROM likes WHERE from_user_id = ? AND to_user_id = ? AND is_like = 1",
                                 (target_id, callback.from_user.id)) as cursor:
                match = await cursor.fetchone()
                if match:
                    await db.execute("INSERT OR IGNORE INTO matches (user1_id, user2_id) VALUES (?, ?)",
                                     (min(callback.from_user.id, target_id), max(callback.from_user.id, target_id)))
                    await db.commit()
                    await callback.message.answer("🎉 Bu match! Siz bir-biringizga yoqdingiz. 'Chatlar' bo'limida gaplashishingiz mumkin.")
                    try:
                        await bot.send_message(target_id, "🎉 Sizda yangi match bor! 'Chatlar' bo'limini tekshiring.")
                    except:
                        pass
    
    await callback.message.delete()
    await show_next_profile(callback.message)

# Chatlar ro'yxati
@dp.message(F.text == "💬 Chatlar")
async def list_chats(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT u.user_id, u.full_name FROM users u
            JOIN matches m ON (m.user1_id = u.user_id OR m.user2_id = u.user_id)
            WHERE (m.user1_id = ? OR m.user2_id = ?) AND u.user_id != ?
        """, (message.from_user.id, message.from_user.id, message.from_user.id)) as cursor:
            matches = await cursor.fetchall()
    
    if matches:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=m[1], callback_data=f"chat_{m[0]}")] for m in matches
        ])
        await message.answer("Sizning matchlaringiz:", reply_markup=kb)
    else:
        await message.answer("Sizda hali matchlar yo'q. Ko'proq like bosing!")

@dp.callback_query(F.data.startswith("chat_"))
async def open_chat(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[1])
    await state.update_data(active_chat=target_id)
    await state.set_state(Chatting.active_chat)
    
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Chatni yopish")]], resize_keyboard=True)
    await callback.message.answer(f"Chat ochildi. Xabar yuboring. Chatni yopish uchun tugmani bosing.", reply_markup=kb)

@dp.message(Chatting.active_chat, F.text == "❌ Chatni yopish")
async def close_chat(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Chat yopildi.", reply_markup=main_menu())

@dp.message(Chatting.active_chat)
async def forward_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get('active_chat')
    
    if target_id:
        try:
            await bot.send_message(target_id, f"📩 Yangi xabar:\n\n{message.text}")
            await message.answer("✅ Yuborildi")
        except Exception:
            await message.answer("❌ Xabar yuborishda xatolik yuz berdi. Foydalanuvchi botni bloklagan bo'lishi mumkin.")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
