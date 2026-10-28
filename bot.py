$ AYASI $:
import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
import docx

# ==========================================
# 1. SOZLAMALAR (TOKENINGIZNI SHU YERGA YOZING)
# ==========================================
BOT_TOKEN = "9150360254:AAF27zMWU81-Z3uX9yxsLIwY7mN7zpvphws"      # @BotFather'dan olingan token
ADMIN_ID = 123456789                                # O'zingizning Telegram ID raqamingiz
FREE_LIMIT = 5                                      # Bepul urinishlar soni
VIP_PRICE = "25 000 so'm / oyiga"                   # Oylik VIP obuna narxi
CARD_NUMBER = "9860 0803 8904 1296(Vaxobova Komilaxon)"  # To'lov qabul qiladigan kartangiz
ADMIN_USERNAME = "@komilaxonacademy"                 # Telegram username'ingiz (@ siz)

# ==========================================
# 2. BAZA (SQLite)
# ==========================================
DB_FILE = "converter_bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            used_count INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            joined_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_or_create_user(user_id, username, full_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, used_count, is_vip FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO users (user_id, username, full_name, used_count, is_vip, joined_at) VALUES (?, ?, ?, 0, 0, ?)",
            (user_id, username, full_name, now)
        )
        conn.commit()
        conn.close()
        return {"user_id": user_id, "used_count": 0, "is_vip": 0}
    conn.close()
    return {"user_id": row[0], "used_count": row[1], "is_vip": row[2]}

def increment_user_usage(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET used_count = used_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def set_vip_status(user_id, is_vip=1):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET is_vip = ? WHERE user_id = ?", (is_vip, user_id))
    conn.commit()
    conn.close()

# ==========================================
# 3. 2026-YIL ALIFBO O'GIRISH QOIDALARI
# ==========================================
AP = r"['ʻ‘`´ʼ’\u02bb\u02bc\u2018\u2019]"

def convert_to_new_latin(text: str) -> str:
    if not text:
        return text

    # O' / Oʻ -> Ö
    text = re.sub(rf"O{AP}", "Ö", text)
    text = re.sub(rf"o{AP}", "ö", text)

    # G' / Gʻ -> Ğ
    text = re.sub(rf"G{AP}", "Ğ", text)
    text = re.sub(rf"g{AP}", "ğ", text)

    # Sh -> Ş
    text = re.sub(r"SH", "Ş", text)
    text = re.sub(r"Sh", "Ş", text)
    text = re.sub(r"sH", "ş", text)
    text = re.sub(r"sh", "ş", text)

    # Ch -> Ç
    text = re.sub(r"CH", "Ç", text)
    text = re.sub(r"Ch", "Ç", text)
    text = re.sub(r"cH", "ç", text)
    text = re.sub(r"ch", "ç", text)

    return text

def process_docx_file(input_file: str, output_file: str):
    doc = docx.Document(input_file)

    for p in doc.paragraphs:
        for r in p.runs:
            r.text = convert_to_new_latin(r.text)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.text = convert_to_new_latin(r.text)

    doc.save(output_file)

# ==========================================
# 4. TUGMALAR
# ==========================================
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Matn yuborish"), KeyboardButton(text="📂 Hujjat (.docx) yuklash")],
        [KeyboardButton(text="⭐ VIP Obuna / Tariflar"), KeyboardButton(text="📊 Mening hisobim")],
        [KeyboardButton(text="ℹ️ 2026 Alifbo haqida"), KeyboardButton(text="📞 Bog'lanish / Yordam")]
    ],
    resize_keyboard=True
)

def vip_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Adminga to'lov chekini yuborish", url=f"https://t.me/{ADMIN_USERNAME}")],
    ])

# ==========================================
# 5. BOT HANDLERLARI
# ==========================================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    remaining = "Cheksiz" if user["is_vip"] else max(0, FREE_LIMIT - user['used_count'])
    
    welcome_text = (
        f"Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        "🏛 <b>Yangi O'zbek-Lotin Alifbosi (2026) Konvertor Botiga xush kelibsiz!</b>\n\n"
        "2026-yil 21-oktabrda imzolangan qonun bo'yicha 4 ta yangi harf:\n"
        "• <b>O' / Oʻ</b> ➔ <b>Ö ö</b>\n"
        "• <b>G' / Gʻ</b> ➔ <b>Ğ ğ</b>\n"
        "• <b>Sh sh</b> ➔ <b>Ş ş</b>\n"
        "• <b>Ch ch</b> ➔ <b>Ç ç</b>\n\n"
        f"🎁 Sizda <b>{remaining} ta</b> bepul o'girish imkoniyati bor.\n\n"
        "Foydalanish uchun matn yoki <b>.docx</b> Word faylingizni yuboring!"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=main_keyboard)

@dp.message(F.text == "📊 Mening hisobim")
async def profile_handler(message: types.Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    status = "🌟 VIP Foydalanuvchi (Cheksiz)" if user["is_vip"] else "Standart (Bepul)"
    remaining = "Cheksiz" if user["is_vip"] else max(0, FREE_LIMIT - user["used_count"])

    text = (
        f"👤 <b>Sizning profilingiz:</b>\n\n"
        f"• Telegram ID: <code>{user['user_id']}</code>\n"
        f"• Holat: <b>{status}</b>\n"
        f"• Ishlatilgan urinishlar: <b>{user['used_count']} ta</b>\n"
        f"• Qolgan bepul o'girishlar: <b>{remaining} ta</b>\n"
    )
    kb = None if user["is_vip"] else vip_inline_keyboard()
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.message(F.text == "⭐ VIP Obuna / Tariflar")
async def tariffs_handler(message: types.Message):
    text = (
        "⭐ <b>VIP Obuna afzalliklari:</b>\n\n"
        "✅ Cheksiz matn va Word (.docx) hujjatlarini o'girish\n"
        "✅ Katta kitoblar, diplom va kurs ishlarini tezkor o'girish\n"
        "✅ Hech qanday cheklovsiz va yuqori tezlikda ishlash\n\n"
        f"💰 <b>Narxi:</b> {VIP_PRICE}\n"
        f"💳 <b>Karta raqami:</b> <code>{CARD_NUMBER}</code>\n\n"
        f"<i>To'lov qilgach, chekni <a href='https://t.me/{ADMIN_USERNAME}'>@{ADMIN_USERNAME}</a> ga yuboring, VIP holat darhol yoqiladi!</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=vip_inline_keyboard(), disable_web_page_preview=True)

@dp.message(F.text == "ℹ️ 2026 Alifbo haqida")
async def info_handler(message: types.Message):
    text = (
        "📜 <b>2026-yil 21-oktabr qonuni haqida:</b>\n\n"
        "1. <b>O' / Oʻ ➔ Ö ö</b>\n"
        "2. <b>G' / Gʻ ➔ Ğ ğ</b>\n"
        "3. <b>Sh sh ➔ Ş ş</b>\n"
        "4. <b>Ch ch ➔ Ç ç</b>\n"
        "5. <b>ng</b> harflar birikmasi mustaqil harf emas deb belgilandi.\n"
        "6. <b>Tutuq belgisi (')</b> o'z kuchida qoldi."
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📞 Bog'lanish / Yordam")
async def contact_handler(message: types.Message):
    await message.answer(
        f"Savol, taklif yoki VIP obunani faollashtirish bo'yicha:\n"
        f"👨‍💻 Admin: @{ADMIN_USERNAME}\n"
        "🤖 Bot 24/7 rejimda avtomatik ishlaydi.",
        parse_mode="HTML"
    )

@dp.message(F.text == "📝 Matn yuborish")
async def send_text_hint(message: types.Message):
    await message.answer("O'girmoqchi bo'lgan matningizni shu yerga yozing yoki nusxalab yuboring!")

@dp.message(F.text == "📂 Hujjat (.docx) yuklash")
async def send_file_hint(message: types.Message):
    await message.answer("<b>.docx</b> Word hujjatingizni burchakdagi 📎 (skrepka) orqali fayl shaklida yuboring!")

# Admin komandasi: /vip <user_id>
@dp.message(Command("vip"))
async def add_vip_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) >= 2:
        try:
            target_id = int(parts[1])
            set_vip_status(target_id, 1)
            await message.answer(f"✅ Foydalanuvchi <code>{target_id}</code> ga VIP maqomi berildi!", parse_mode="HTML")
            try:
                await bot.send_message(target_id, "🎉 <b>Tabriklaymiz! Hisobingizga VIP obuna yoqildi. Endi cheksiz foydalanishingiz mumkin!</b>", parse_mode="HTML")
            except Exception:
                pass
        except ValueError:
            await message.answer("Masalan: /vip 123456789")

# Word (.docx) va matn hujjatlarini qabul qilish
@dp.message(F.document)
async def document_handler(message: types.Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

    if not user["is_vip"] and user["used_count"] >= FREE_LIMIT:
        await message.answer(
            "⚠️ <b>Bepul limitingiz tugadi!</b>\n\n"
            "Cheksiz Word hujjatlarini o'girish uchun VIP obunani faollashtiring.",
            parse_mode="HTML",
            reply_markup=vip_inline_keyboard()
        )
        return

    doc = message.document
    if not (doc.file_name.endswith('.docx') or doc.file_name.endswith('.txt')):
        await message.answer("⚠️ Iltimos, faqat <b>.docx</b> (Word) yoki <b>.txt</b> fayllarni yuboring!", parse_mode="HTML")
        return

    wait_msg = await message.answer("⏳ Hujjatingiz yuklab olinmoqda va yangi alifboga o'girilmoqda, kuting...")

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("converted", exist_ok=True)

    input_path = f"downloads/{message.from_user.id}_{doc.file_name}"
    output_filename = f"yangi_{doc.file_name}"
    output_path = f"converted/{message.from_user.id}_{output_filename}"

    file_info = await bot.get_file(doc.file_id)
    await bot.download_file(file_info.file_path, input_path)

    try:
        if doc.file_name.endswith('.docx'):
            process_docx_file(input_path, output_path)
        else:
            with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            converted = convert_to_new_latin(content)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(converted)

        increment_user_usage(message.from_user.id)

        return_file = FSInputFile(output_path, filename=output_filename)
        await message.answer_document(
            document=return_file,
            caption="✅ <b>Hujjatingiz yangi o'zbek alifbosiga (Ö, Ğ, Ş, Ç) muvaffaqiyatli o'tkazildi!</b>",
            parse_mode="HTML"
        )
        await wait_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await wait_msg.edit_text("❌ Hujjatni qayta ishlashda xatolik yuz berdi.")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# Oddiy matnlarni qabul qilish
@dp.message(F.text)
async def text_handler(message: types.Message):
    user = get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)

if not user["is_vip"] and user["used_count"] >= FREE_LIMIT:
        await message.answer(
            "⚠️ <b>Bepul limitingiz tugadi!</b>\n\n"
            "Cheksiz o'girish uchun VIP obunani faollashtiring.",
            parse_mode="HTML",
            reply_markup=vip_inline_keyboard()
        )
        return

    converted_text = convert_to_new_latin(message.text)
    increment_user_usage(message.from_user.id)

    if len(converted_text) > 4000:
        for i in range(0, len(converted_text), 4000):
            await message.answer(converted_text[i:i+4000])
    else:
        await message.answer(converted_text)

# Botni ishga tushirish
async def main():
    init_db()
    print("Bot muvaffaqiyatli ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
