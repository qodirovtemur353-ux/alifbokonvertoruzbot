import asyncio
import html
import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from aiohttp import web
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

# SOZLAMALAR
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
ADMIN_USERNAME = os.environ.get(
    "ADMIN_USERNAME", "komilxonacademy"
).strip().lstrip("@")
FREE_LIMIT = int(os.environ.get("FREE_LIMIT", "5"))
VIP_PRICE = os.environ.get("VIP_PRICE", "25 000 so'm / oyiga")
CARD_NUMBER = os.environ.get(
    "CARD_NUMBER", "KARTA_RAQAMINI_SHU_YERGA_KIRITING"
)

DB_FILE = os.environ.get("DB_FILE", "converter_bot.db")
DOWNLOAD_DIR = Path("downloads")
CONVERTED_DIR = Path("converted")
MAX_TEXT_LENGTH = 4000

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Render Environment bo'limida "
        "BOT_TOKEN o'zgaruvchisini kiriting."
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# MA'LUMOTLAR BAZASI
def db_connect():
    return sqlite3.connect(DB_FILE, timeout=30)


def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                used_count INTEGER NOT NULL DEFAULT 0,
                is_vip INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT
            )
        """)
        conn.commit()


def get_or_create_user(user_id, username, full_name):
    with db_connect() as conn:
        row = conn.execute(
            "SELECT user_id, used_count, is_vip "
            "FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if row is None:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """INSERT INTO users
                (user_id, username, full_name, used_count,
                 is_vip, joined_at)
                VALUES (?, ?, ?, 0, 0, ?)""",
                (user_id, username, full_name or "", now),
            )
            conn.commit()
            return {
                "user_id": user_id,
                "used_count": 0,
                "is_vip": 0,
            }

        conn.execute(
            "UPDATE users SET username = ?, full_name = ? "
            "WHERE user_id = ?",
            (username, full_name or "", user_id),
        )
        conn.commit()

        return {
            "user_id": row[0],
            "used_count": row[1],
            "is_vip": row[2],
        }


def increment_user_usage(user_id):
    with db_connect() as conn:
        conn.execute(
            "UPDATE users SET used_count = used_count + 1 "
            "WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()


def set_vip_status(user_id, is_vip=1):
    with db_connect() as conn:
        conn.execute(
            "UPDATE users SET is_vip = ? WHERE user_id = ?",
            (is_vip, user_id),
        )
        conn.commit()


# MATNNI O'GIRISH
AP = r"['ʻ‘`´ʼ’\u02bb\u02bc\u2018\u2019]"


def convert_to_new_latin(text: str) -> str:
    if not text:
        return text

    text = re.sub(rf"o{AP}", "ö", text)
    text = re.sub(rf"O{AP}", "Ö", text)
    text = re.sub(rf"g{AP}", "ğ", text)
    text = re.sub(rf"G{AP}", "Ğ", text)

    text = re.sub(r"SH", "Ş", text)
    text = re.sub(r"Sh", "Ş", text)
    text = re.sub(r"sH", "ş", text)
    text = re.sub(r"sh", "ş", text)

    text = re.sub(r"CH", "Ç", text)
    text = re.sub(r"Ch", "Ç", text)
    text = re.sub(r"cH", "ç", text)
    text = re.sub(r"ch", "ç", text)

    return text


def process_docx_file(input_file, output_file):
    document = docx.Document(input_file)

    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.text = convert_to_new_latin(run.text)

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.text = convert_to_new_latin(run.text)

    for section in document.sections:
        for part in (section.header, section.footer):
            for paragraph in part.paragraphs:
                for run in paragraph.runs:
                    run.text = convert_to_new_latin(run.text)

    document.save(output_file)


# TUGMALAR
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
            KeyboardButton(text="ℹ️ Alifbo haqida"),
            KeyboardButton(text="📞 Bog'lanish / Yordam"),
        ],
    ],
    resize_keyboard=True,
)


def vip_inline_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="👨‍💻 Adminga yozish",
                url=f"https://t.me/{ADMIN_USERNAME}",
            )
        ]]
    )


def remaining_uses(user):
    if user["is_vip"]:
        return "Cheksiz"
    return max(0, FREE_LIMIT - user["used_count"])
