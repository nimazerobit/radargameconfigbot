from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from core.config_loader import DBH, CFG, reload_config
from core.texts import TEXTS
from core.utils import *

# Admin panel settings:
ADMIN_PANEL = {
    "notify_new_user": True,
    "notify_new_config": True
}

### ---------------------------- Admin Panel ---------------------------- ###
def admin_panel_keyboard():
    rows = [
        [
            InlineKeyboardButton(
                "👤 غیر فعال کردن اعلان ثبت‌نام" if ADMIN_PANEL["notify_new_user"] else "👤 فعال کردن اعلان ثبت‌نام",
                callback_data="toggle_user_notify"
            )
        ],
        [
            InlineKeyboardButton(
                "🔕 غیر فعال کردن اعلان کانفیگ جدید" if ADMIN_PANEL["notify_new_config"] else "🔔 فعال کردن اعلان کانفیگ جدید",
                callback_data="toggle_config_notify"
            )
        ],
        [
            InlineKeyboardButton("📊 وضعیت ربات", callback_data="status_panel")
        ]
    ]
    return InlineKeyboardMarkup(rows)

def admin_panel_text():
    panel_text = (
        "<b>⚙️ پنل مدیریت</b>\n"
        f"<b>اعلان کاربر جدید:</b> {'فعال ✅' if ADMIN_PANEL['notify_new_user'] else 'غیرفعال ❌'}\n"
        f"<b>اعلان کانفیگ جدید:</b> {'فعال ✅' if ADMIN_PANEL['notify_new_config'] else 'غیرفعال ❌'}"
    )
    return panel_text

async def adminpanel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    if not is_admin(update.effective_user.id):
        return
    await update.effective_chat.send_message(admin_panel_text(), reply_markup=admin_panel_keyboard(), parse_mode="HTML")

### --- Broadcast Command --- ###
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)

    # Check is owner
    if not is_owner(update.effective_user.id):
        return
    
    # If not a reply, show usage help
    if not update.message or not update.message.reply_to_message:
        await update.effective_chat.send_message(
            "برای ارسال پیام همگانی، این دستور را روی پیام مورد نظر ریپلای کنید.\n"
            "یا یک شناسه (آیدی عددی، یوزرنیم، یا هش کاربر) بدهید.",
            parse_mode="HTML"
        )
        return
    
    # Check if broadcasting to all or single user
    target = None
    if context.args:
        key = context.args[0]
        user = DBH.find_user_by_any(key)
        if not user:
            await update.effective_chat.send_message(TEXTS["errors"]["user_notfound"], parse_mode="HTML")
            return
        target = user["user_id"]

    # Get all target chat IDs
    chat_ids = []
    if target:
        chat_ids = [target]
    else:
        with DBH._connect() as con:
            cur = con.cursor()
            # Add all active user IDs
            user_ids = [row[0] for row in cur.execute(
                "SELECT user_id FROM users WHERE banned=0"
            ).fetchall()]
        
        # Merge lists and remove duplicates
        chat_ids = list(set(user_ids))
    
    # Forward message
    message = update.message.reply_to_message
    success = 0
    failed = 0
    for chat_id in chat_ids:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id
            )
            success += 1
        except Exception:
            failed += 1
    
    await update.effective_chat.send_message(
        f"✅ <b>ارسال شد</b>\n\n🟢 موفق : {success}\n🔴 ناموفق : {failed}",
        parse_mode="HTML"
    )

### --- Admin view list of all users Command --- ###
async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in CFG["OWNERS"]:
        return

    users = DBH.get_all_users()
    if not users:
        await update.message.reply_text("هیچ کاربری یافت نشد ❌")
        return
    
    users = sorted(users, key=lambda u: u["created_at"] or 0)

    message = f"📊 تعداد کل کاربران: {len(users)}\n\n"
    message += "\n".join([f"🔹<code>{user["user_id"]}</code> - {user["full_name"] or "بدون نام"}" for user in users])
    await update.message.reply_text(message[:4096], parse_mode="HTML")  # Telegram max message size

### --- Admin view user information Command --- ###
async def admin_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    await ensure_user(update)
    # Check is admin or owner
    if not is_admin(update.effective_user.id):
        return
    
    is_edit = update.callback_query is not None
    query = update.callback_query
    row = None

    # Check arguments
    if (not context.args) and is_edit == False:
        await update.effective_chat.send_message(f'<b>{TEXTS["errors"]["invalid_command"]}</b>', parse_mode="HTML")
        return

    # Get user id
    target_user_id = None
    if context.args:
        key = context.args[0]
        row = DBH.find_user_by_any(key)
        if row:
            target_user_id = row["user_id"]
        else:
            await update.effective_chat.send_message(TEXTS["errors"]["user_notfound"], parse_mode="HTML")
            return
    elif is_edit:
        if user_id:
            target_user_id = user_id
            row = DBH.get_user(target_user_id)
            if not row:
                await update.effective_chat.send_message(TEXTS["errors"]["user_notfound"], parse_mode="HTML")
                return
        else:
            await update.effective_chat.send_message(TEXTS["errors"]["user_notfound"], parse_mode="HTML")
            return

    # Get user stats
    text = await generate_userinfo_text(target_user_id)
    banned = row["banned"]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ رفع بن" if banned else "🚫 بن",
            callback_data=f"admin_banuser:{row['user_id']}"
        )]
    ])

    if is_edit:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.effective_chat.send_message(text, reply_markup=keyboard, parse_mode="HTML")

# Generate userinfo text from user_id
async def generate_userinfo_text(user_id: int) -> str:
    # Get user stats from DB
    user_stats = DBH.stats_for_user(user_id)
    now = now_ts()
    text = TEXTS["admin"]["user_info"].format(
        user_id=user_id,
        username=user_stats["username"] or "بدون یوزرنیم",
        full_name=user_stats["full_name"] or "بدون نام",
        user_hash=user_stats["user_hash"] or "بدون هش",
        created_at=fmt_ts(user_stats["created_at"]) if user_stats["created_at"] else "-",
        created_ago=human_ago(max(0, now - (user_stats["created_at"] or now))),
        last_active=fmt_ts(user_stats["last_active"]) if user_stats["last_active"] else "-",
        last_ago=human_ago(max(0, now - (user_stats["last_active"] or now))),
        radargame_count=user_stats["radargame_count"] or "بدون اکانت رادارگیم",
        config_count=user_stats["usage_count"] or "-",
        status="🚫 بن شده" if user_stats["banned"] else "✅ عادی"
    )
    return text

### --- Admin Callbacks --- ###
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)
    
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await query.answer("دسترسی فقط برای ادمین های فعال ❌", show_alert=True)
        return
    
    elif data.startswith("admin_banuser:"):
        target_user_id = int(data.split(":")[1])
        user = DBH.get_user(target_user_id)

        # Check ban yourself
        if user_id == target_user_id:
            await query.answer("میخوای خودتو بن کنی 😔", show_alert=True)
            return

        # Check is user available
        if not user:
            await query.answer(TEXTS["errors"]["user_notfound"], show_alert=True)
            return
        
        DBH.set_ban(target_user_id, not user["banned"])
        await query.answer("✅ وضعیت بن کاربر توسط ادمین تغییر کرد", show_alert=True)
        await admin_userinfo(update, context, target_user_id)
        return

    elif data == "toggle_user_notify":
        ADMIN_PANEL["notify_new_user"] = not ADMIN_PANEL["notify_new_user"]
        await query.answer("✅ تنظیمات ذخیره شد")

    elif data == "toggle_config_notify":
        ADMIN_PANEL["notify_new_config"] = not ADMIN_PANEL["notify_new_config"]
        await query.answer("✅ تنظیمات ذخیره شد")

    elif data == "status_panel":
        with DBH._connect() as conn:
            cursor = conn.cursor()
            total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            total_radargame = cursor.execute("SELECT COUNT(*) FROM radargame").fetchone()[0]
            banned_users = cursor.execute("SELECT COUNT(*) FROM users WHERE banned=1").fetchone()[0]
            import datetime
            today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_ts = int(today.timestamp())
            today_active = cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (today_ts,)).fetchone()[0]

        status_text = (
            f"<b>📊 آمار ربات</b>\n"
            f"• کل کاربران: <b>{total_users}</b>\n"
            f"• تعداد اکانت های رادارگیم: <b>{total_radargame}</b>\n"
            f"• کاربران بن شده: <b>{banned_users}</b>\n"
            f"• کاربران فعال امروز: <b>{today_active}</b>\n"
        )

        await query.edit_message_text(
            status_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(TEXTS["admin"]["backtomenu"], callback_data="adminpanel")]
            ]),
            parse_mode="HTML"
        )
        return
    
    elif data == "adminpanel":
        await query.edit_message_text(admin_panel_text(), reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        return

    await query.edit_message_text(admin_panel_text(), reply_markup=admin_panel_keyboard(), parse_mode="HTML")
    return