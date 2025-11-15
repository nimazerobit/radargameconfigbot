from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import Forbidden, BadRequest

import json
import random
import string
import time
import jdatetime
from datetime import timezone, timedelta

from core.config_loader import DBH, CFG

### --- Generate Hash --- ###
def gen_hash(n: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.choice(alphabet) for _ in range(n))

### --- Humanize time --- ###
def human_ago(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} ثانیه"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} دقیقه"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ساعت"
    days = hours // 24
    if days < 30:
        return f"{days} روز"
    months = days // 30
    if months < 12:
        return f"{months} ماه"
    years = months // 12
    return f"{years} سال"

### --- Return current timestamp --- ###
def now_ts() -> int:
    return int(time.time())

### --- Return current time string --- ###
def fmt_ts(ts: int) -> str:
    # local naive format
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

# persian digit map
PERSIAN_DIGIT_MAP = {
    "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴",
    "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹"
}

### --- Return persian digit --- ###
def to_persian_digits(text: str) -> str:
    return "".join(PERSIAN_DIGIT_MAP.get(ch, ch) for ch in str(text))

### --- Return current shamsi datetime --- ###
def get_tehran_shamsi_datetime() -> str:
    now_tehran = jdatetime.datetime.now(timezone(timedelta(hours=3, minutes=30)))
    date_str = now_tehran.strftime("%Y/%m/%d %H:%M")
    return to_persian_digits(date_str)

### --- Check is user admin or not --- ###
def is_admin(user_id: int) -> bool:
    # Check ban status
    row = DBH.get_user(user_id)
    if row and row["banned"]:
        return False

    # Check role
    return user_id in set(CFG.get("ADMINS", []) + CFG.get("OWNERS", []))

### --- Check is user owner or not --- ###
def is_owner(user_id: int) -> bool:
    # Check ban status
    row = DBH.get_user(user_id)
    if row and row["banned"]:
        return False

    # Check role
    return user_id in set(CFG.get("OWNERS", []))

### --- create or update user --- ###
async def ensure_user(update: Update, update_last_active: bool = True) -> int:
    user = update.effective_user

    if user is None:
        return 2  # error

    full_name = (user.full_name or "").strip()
    username = user.username
    db_user = DBH.get_user(user.id)
    if not db_user:
        # first-time: new user_hash
        user_hash = gen_hash(12)
        is_new = True
    else:
        user_hash = db_user["user_hash"]
        is_new = False

    now = now_ts() if update_last_active else (db_user["last_active"] if db_user else now_ts())
    try:
        DBH.upsert_user(user.id, username, full_name, user_hash, now)
    except Exception:
        return 2  # error

    return 1 if is_new else 0

### --- Check is user banned or not --- ###
async def banned_guard(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    row = DBH.get_user(user.id)
    if row and row["banned"]:
        if update.callback_query:
            await update.callback_query.answer("⛔️ دسترسی شما مسدود است")
        else:
            await update.effective_chat.send_message(f"⛔️ دسترسی شما مسدود است", parse_mode="HTML")
        return False
    return True

### --- Check is user joined channel/group or not --- ###
reported_missing_chats = set()

async def is_user_joined(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Forbidden:
        # Bot cannot access member info (maybe not an admin in channel/group)
        return False
    
async def check_required_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    not_joined_user = []

    for item in CFG["REQUIRED_CHATS"]:
        title = item["title"]
        chat = item["username"]

        try:
            bot_member = await context.bot.get_chat_member(chat, context.bot.id)
            if bot_member.status in ["left", "kicked"]:
                if chat not in reported_missing_chats:
                    for admin_id in CFG["OWNERS"]:
                        await context.bot.send_message(
                            admin_id,
                            f"⚠️ ربات در چت {chat} ({title}) عضو نیست!"
                        )
                    reported_missing_chats.add(chat)
                return True
        except BadRequest:
            if chat not in reported_missing_chats:
                for admin_id in CFG["OWNERS"]:
                    await context.bot.send_message(
                        admin_id,
                        f"❌ دسترسی به چت {chat} ({title}) وجود ندارد یا پیدا نشد."
                    )
                reported_missing_chats.add(chat)
            return True

        if not await is_user_joined(context.bot, chat, user_id):
            not_joined_user.append((title, chat))

    if not_joined_user:
        buttons = [
            [InlineKeyboardButton(title, url=f"https://t.me/{chat.lstrip('@')}")]
            for title, chat in not_joined_user
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        await update.effective_message.reply_text(
            "🚫 برای استفاده از بات باید در کانال و گروه‌های زیر عضو شوید:",
            reply_markup=reply_markup
        )
        return False

    return True

async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE, check_force_join: bool=True, check_ban: bool=True, check_user_db: bool=True):
    if check_user_db:
        await ensure_user(update)
    if check_ban:
        if not await banned_guard(update):
            return False
    if check_force_join:
        if not await check_required_chats(update, context):
            return False
    return True

### --- Check is user has active chat with bot --- ###
async def has_active_private_chat(bot, user_id: int) -> bool:
    try:
        await bot.send_chat_action(chat_id=user_id, action="typing")  
        return True
    except Forbidden:
        return False
    except Exception as e:
        return False