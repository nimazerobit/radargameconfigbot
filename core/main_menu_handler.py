from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from core.texts import TEXTS
from core.config_loader import DBH, CFG
from core.radargame_core import change_radar_account, new_config
from core.utils import *

### --- Main Menu --- ###
def main_menu_keyboard():
    button_text = TEXTS["main_menu"]["buttons"]
    rows = [
        [InlineKeyboardButton(button_text["new_config"], callback_data="new_config")],
        [InlineKeyboardButton(button_text["change_account"], callback_data="change_account")],
        [InlineKeyboardButton(button_text["profile"], callback_data="profile")],
        [InlineKeyboardButton(button_text["help"], callback_data="help")]
    ]
    return InlineKeyboardMarkup(rows)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    if not await check_user(update, context):
        return
    main_menu_text = TEXTS["main_menu"]["title"].format(version=CFG["VERSION"])
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(f'{main_menu_text}', reply_markup=main_menu_keyboard(), parse_mode="HTML")
    else:
        await update.effective_chat.send_message(f'{main_menu_text}', reply_markup=main_menu_keyboard(), parse_mode="HTML")

### --- Main Menu Callbacks --- ###
async def main_menu_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return

    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id

    if data == "backtomain":
        await show_main_menu(update, context, edit=True)
        return

    elif data == "new_config":
        await new_config(update, context)
        return

    elif data == "profile":
        user_data = DBH.stats_for_user(user_id)
        now = now_ts()
        txt = TEXTS["profile"].format(
            full_name=user_data["full_name"] or "-",
            username=user_data["username"] or "-",
            user_id=user_id,
            user_hash=user_data["user_hash"],
            config_count=user_data["usage_count"],
            radargame_count=user_data["radargame_count"] or "0",
            created_at=fmt_ts(user_data["created_at"]),
            created_ago=human_ago(now - user_data["created_at"]),
            last_active=fmt_ts(user_data["last_active"]),
            last_ago=human_ago(now - user_data["last_active"]),
        )
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["backtomain"], callback_data="backtomain")]]), parse_mode="HTML")
        return
    
    elif data == "help":
        await query.edit_message_text(TEXTS["help_text"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["backtomain"], callback_data="backtomain")]]), parse_mode="HTML")
        return