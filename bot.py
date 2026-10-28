import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import docx
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ============================================================
# SOZLAMALAR
# Render -> Service -> Environment bo'limida quyidagilarni kiriting:
# BOT_TOKEN, ADMIN_ID
# Tokenni kod ichiga yozmang.
# ============================================================
BOT_TOKEN = os.getenv("9150360254:AAF27zMWU81-Z3uX9yxsLIwY7mN7zpvphws", "").strip()
ADMIN_ID = int(os.getenv("komilaxon", "0"))
FREE_LIMIT = 5
VIP_PRICE = "25 000 so'm / oyiga"
CARD_NUMBER = "9860 0803 8904 1296 (Ism Familiya)"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "komilxonacademy").strip().lstrip("@")

DB_FILE = os.getenv("DB_FILE", "converter_bot.db")
DOWNLOAD_DIR = Path("downloads")
CONVERTED_DIR = Path("converted")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================
# MA'LUMOTLAR BAZASI
# ============================================================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                used_count INTEGER NOT NULL DEFAULT 0,
                is_vip INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT
            )
            """
        )


def get_or_create_user(user_id: int, username: str | None, full_name: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

        if row is None:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """
                INSERT INTO users
                (user_id, username, full_name, used_count, is_vip, joined_at)
                VALUES (?, ?, ?, 0, 0, ?)
                """,
                (user_id, username, full_name, now),
            )
            return {"user_id": user_id, "used_count": 0, "is_vip": 0}

        # Username yoki ism o'zgargan bo'lsa, bazani yangilash
        conn.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
            (username, full_name, user_id),
        )
        return {
            "user_id": row["user_id"],
            "used_count": row["used_count"],
            "is_vip": row["is_vip"],
        }


def increment_user_usage(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "UPDATE users SET used_count = used_count + 1 WHERE user_id = ?",
            (user_id,),
        )


def set_vip_status(user_id: int, is_vip: int = 1):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET is_vip = ? WHERE user_id = ?",
                (is_vip, user_id),
            )
            return True
        return False


# ============================================================
# MATNNI YANGI ALIFBO BELGILARIGA O'GIRISH
# Bu qoidalar foydalanuvchi bergan loyihadagi qoidalarga asoslangan.
# ============================================================
AP = r"['ʻ‘`´ʼ’\u02bb\u02bc\u2018\u2019]"


def convert_to_new_latin(text: str) -> str:
    if not text:
        return text

    # Avval uzun birikmalarni o'giramiz; katta-kichik harf saqlanadi.
    text = re.sub(rf"O{AP}", "Ö", text)
    text = re.sub(rf"o{AP}", "ö", text)
    text = re.sub(rf"G{AP}", "Ğ", text)
    text = re.sub(rf"g{AP}", "ğ", text)

    text = re.sub(r"SH", "Ş", text)
    text = re.sub(r"Sh", "Ş", text)
    text = re.sub(r"sH", "ş", text)
    text = re.sub(r"sh", "ş", text)

    text = re.sub(r"CH", "Ç", text)
    text = re.sub(r"Ch", "Ç", text)
    text = re.sub(r"cH", "ç", text)
    text = re.sub(r"ch", "ç", text)
    return text


def process_docx_file(input_file: str, output_file: str):
    document = docx.Document(input_file)

    def convert_paragraphs(paragraphs):
        for paragraph in paragraphs:
            for run in paragraph.runs:
                run.text = convert_to_new_latin(run.text)

    def convert_table(table):
        for row in table.rows:
            for cell in row.cells:
                convert_paragraphs(cell.paragraphs)
                for nested_table in cell.tables:
                    convert_table(nested_table)

    convert_paragraphs(document.paragraphs)
    for table in document.tables:
        convert_table(table)

    # Word hujjatining sarlavha va pastki kolontitrlari
    for section in document.sections:
        for part in (section.header, section.footer):
            convert_paragraphs(part.paragraphs)
            for table in part.tables:
                convert_table(table)

    document.save(output_file)


# ============================================================
# TELEGRAM TUGMALARI
# ============================================================
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📝 Matn yuborish"),
            KeyboardButton(text="📂 Hujjat (.docx) yuklash"),
        ],
        [
            KeyboardButton(text="⭐ VIP Obuna / Tariflar"),
            KeyboardButton(text="📊 Mening hisobim"),
        ],
        [
            KeyboardButton(text="ℹ️ 2026 Alifbo haqida"),
            KeyboardButton(text="📞 Bog'lanish / Yordam"),
        ],
    ],
    resize_keyboard=True,
)


def vip_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👨‍💻 Adminga to'lov chekini yuborish",
                    url=f"https://t.me/{ADMIN_USERNAME}",
                )
            ]
        ]
    )


# ============================================================
# BOT VA HANDLERLAR
# ============================================================
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Render Environment bo'limiga BOT_TOKEN kiriting."
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def get_user(message: types.Message):
    return get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )


def has_free_uses(user):
    return bool(user["is_vip"]) or user["used_count"] < FREE_LIMIT


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    user = get_user(message)
    remaining = (
        "Cheksiz"
        if user["is_vip"]
        else str(max(0, FREE_LIMIT - user["used_count"]))
    )

    welcome_text = (
        f"Assalomu alaykum, <b>{message.from_user.full_name}</b>!\n\n"
        "🏛 <b>O'zbek-Lotin alifbosi konvertor botiga xush kelibsiz!</b>\n\n"
        "Bot sozlamalarida belgilangan almashtirishlar:\n"
        "• <b>O' / Oʻ</b> ➔ <b>Ö ö</b>\n"
        "• <b>G' / Gʻ</b> ➔ <b>Ğ ğ</b>\n"
        "• <b>Sh sh</b> ➔ <b>Ş ş</b>\n"
        "• <b>Ch ch</b> ➔ <b>Ç ç</b>\n\n"
        f"🎁 Sizda <b>{remaining}</b> ta bepul o'girish imkoniyati bor.\n\n"
        "Matn yuboring yoki Word (.docx) / matn (.txt) faylini jo'nating."
    )
    await message.answer(
        welcome_text, parse_mode="HTML", reply_markup=main_keyboard
    )


@dp.message(F.text == "📊 Mening hisobim")
async def profile_handler(message: types.Message):
    user = get_user(message)
    status = (
        "🌟 VIP foydalanuvchi (cheksiz)"
        if user["is_vip"]
        else "Standart (bepul)"
    )
    remaining = (
        "Cheksiz"
        if user["is_vip"]
        else str(max(0, FREE_LIMIT - user["used_count"]))
    )
    text = (
        "👤 <b>Sizning profilingiz:</b>\n\n"
        f"• Telegram ID: <code>{user['user_id']}</code>\n"
        f"• Holat: <b>{status}</b>\n"
        f"• Ishlatilgan urinishlar: <b>{user['used_count']} ta</b>\n"
        f"• Qolgan bepul o'girishlar: <b>{remaining} ta</b>"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=None if user["is_vip"] else vip_inline_keyboard(),
    )


@dp.message(F.text == "⭐ VIP Obuna / Tariflar")
async def tariffs_handler(message: types.Message):
    text = (
        "⭐ <b>VIP obuna afzalliklari:</b>\n\n"
        "✅ Matn va Word (.docx) hujjatlarini cheksiz o'girish\n"
        f"💰 <b>Narxi:</b> {VIP_PRICE}\n"
        f"💳 <b>Karta raqami:</b> <code>{CARD_NUMBER}</code>\n\n"
        "To'lovdan keyin chekni adminga yuboring. "
        "Admin to'lovni tekshirib, /vip TELEGRAM_ID buyrug'i bilan "
        "VIP holatini yoqishi mumkin."
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=vip_inline_keyboard(),
        disable_web_page_preview=True,
    )


@dp.message(F.text == "ℹ️ 2026 Alifbo haqida")
async def info_handler(message: types.Message):
    await message.answer(
        "📜 <b>Konvertor qoidalari:</b>\n\n"
        "1. <b>O' / Oʻ ➔ Ö ö</b>\n"
        "2. <b>G' / Gʻ ➔ Ğ ğ</b>\n"
        "3. <b>Sh sh ➔ Ş ş</b>\n"
        "4. <b>Ch ch ➔ Ç ç</b>\n\n"
        "Eslatma: bu bot ichidagi almashtirish qoidalari. "
        "Ularning rasmiy imlo yoki qonuniy standart ekanini alohida tekshiring.",
        parse_mode="HTML",
    )


@dp.message(F.text == "📞 Bog'lanish / Yordam")
async def contact_handler(message: types.Message):
    await message.answer(
        f"Savol yoki VIP obuna bo'yicha admin: @{ADMIN_USERNAME}\n"
        "Botdagi muammo haqida xabar yuborishingiz mumkin."
    )


@dp.message(F.text == "📝 Matn yuborish")
async def send_text_hint(message: types.Message):
    await message.answer(
        "O'girmoqchi bo'lgan matningizni shu yerga yozing yoki nusxalab yuboring!"
    )


@dp.message(F.text == "📂 Hujjat (.docx) yuklash")
async def send_file_hint(message: types.Message):
    await message.answer(
        "📎 tugmasi orqali .docx Word yoki .txt faylini yuboring."
    )


@dp.message(Command("vip"))
async def add_vip_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID or ADMIN_ID == 0:
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Foydalanish: /vip TELEGRAM_ID")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Telegram ID faqat raqamlardan iborat bo'lishi kerak.")
        return

    if not set_vip_status(target_id, 1):
        await message.answer(
            "Bu foydalanuvchi bazada topilmadi. Avval botga /start yuborishi kerak."
        )
        return

    await message.answer(
        f"✅ <code>{target_id}</code> foydalanuvchiga VIP yoqildi!",
        parse_mode="HTML",
    )
    try:
        await bot.send_message(
            target_id,
            "🎉 Tabriklaymiz! Hisobingizga VIP obuna yoqildi.",
        )
    except Exception:
        logger.exception("VIP xabari foydalanuvchiga yuborilmadi.")


@dp.message(F.document)
async def document_handler(message: types.Message):
    user = get_user(message)
    if not has_free_uses(user):
        await message.answer(
            "⚠️ <b>Bepul limitingiz tugadi!</b>\n\n"
            "Davom etish uchun VIP obunani ko'ring.",
            parse_mode="HTML",
            reply_markup=vip_inline_keyboard(),
        )
        return

    document = message.document
    filename = document.file_name or "file"
    suffix = Path(filename).suffix.lower()

    if suffix not in (".docx", ".txt"):
        await message.answer(
            "Iltimos, faqat .docx Word yoki .txt fayl yuboring."
        )
        return

    wait_msg = await message.answer(
        "⏳ Fayl qayta ishlanmoqda, iltimos kuting..."
    )
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    CONVERTED_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    input_path = DOWNLOAD_DIR / f"{message.from_user.id}_{safe_name}"
    output_name = f"yangi_{Path(safe_name).stem}{suffix}"
    output_path = CONVERTED_DIR / f"{message.from_user.id}_{output_name}"

    try:
        file_info = await bot.get_file(document.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)

        if suffix == ".docx":
            process_docx_file(str(input_path), str(output_path))
        else:
            content = input_path.read_text(encoding="utf-8", errors="replace")
            output_path.write_text(
                convert_to_new_latin(content), encoding="utf-8"
            )

        increment_user_usage(message.from_user.id)
        await message.answer_document(
            document=FSInputFile(str(output_path), filename=output_name),
            caption="✅ Faylingiz qayta ishlashdan o'tdi.",
        )
        await wait_msg.delete()

    except Exception:
        logger.exception("Faylni qayta ishlashda xatolik")
        await wait_msg.edit_text(
            "❌ Faylni qayta ishlashda xatolik yuz berdi. "
            "Boshqa fayl bilan urinib ko'ring."
        )
    finally:
        for path in (input_path, output_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Vaqtinchalik faylni o'chirib bo'lmadi: %s", path)


@dp.message(F.text)
async def text_handler(message: types.Message):
    user = get_user(message)
    if not has_free_uses(user):
        await message.answer(
            "⚠️ <b>Bepul limitingiz tugadi!</b>\n\n"
            "Davom etish uchun VIP obunani ko'ring.",
            parse_mode="HTML",
            reply_markup=vip_inline_keyboard(),
        )
        return

    converted_text = convert_to_new_latin(message.text or "")
    increment_user_usage(message.from_user.id)

    # Telegram xabar uzunligi chegarasidan oshib ketmasligi uchun bo'lib yuborish
    for start in range(0, len(converted_text), 4000):
        await message.answer(converted_text[start : start + 4000])


async def main():
    init_db()
    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
