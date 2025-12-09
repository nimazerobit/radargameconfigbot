from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler

from core.config_loader import CFG, TEXTS
from core.radargame_core import radargame_callbacks, new_radar_account, get_username, get_password, USERNAME, PASSWORD
from core.utils import check_user
from core.admin_system import show_all_users, broadcast, adminpanel, admin_userinfo, admin_callbacks
from core.main_menu_handler import show_main_menu, main_menu_callbacks

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return
    await update.message.reply_text(TEXTS["help_text"], parse_mode="HTML")
    return

async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return
    message_id = update.effective_message.message_id
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(r"¯\_(ツ)_/¯", callback_data="emptycallback")]])
    await update.effective_chat.send_animation("CAACAgQAAxkBAAEYyVZpDKbhBLct5GxqAgLGhtlAtFw-XgAC5RoAAl5MgVAKPOJUbDxWLjYE", reply_to_message_id=message_id)
    await update.effective_chat.send_message(text=TEXTS["dev"].format(version=CFG["VERSION"]), reply_to_message_id=message_id, reply_markup=markup, parse_mode="HTML")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ دستور لغو شد", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ——— Global Callbacks ———
async def global_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    # user_id = update.effective_user.id

    if not await check_user(update, context, check_user_db=False):
        return

    # Empty Callback
    if data == "emptycallback":
        await query.answer(r"¯\_(ツ)_/¯")
        return

# === Main Init ===
def main():
    token = CFG["BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler(["start", "menu"], show_main_menu))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("dev", developer))
    app.add_handler(CommandHandler("users", show_all_users))
    app.add_handler(CommandHandler("user", admin_userinfo))
    app.add_handler(CommandHandler("adminpanel", adminpanel))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Callbacks
    app.add_handler(CallbackQueryHandler(radargame_callbacks, pattern=r"^(server_|dns_|change_account|remove_account|set_active)"))
    app.add_handler(CallbackQueryHandler(global_callbacks, pattern=r"^(emptycallback)$"))
    app.add_handler(CallbackQueryHandler(main_menu_callbacks, pattern=r"^(backtomain|new_config|profile|help)"))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern=r"^(admin_|show_users:|toggle_user_notify|status_panel|reload_|adminpanel)"))

    # Conversations
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(new_radar_account, pattern="^new_account$")],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    print("Bot started")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
