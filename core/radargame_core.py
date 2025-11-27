from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, ReactionTypeEmoji, CopyTextButton
from telegram.ext import ContextTypes, ConversationHandler
import requests
import random
import string
import os
import json

from core.config_loader import DBH, CFG, DNS_LIST
from core.texts import TEXTS
from core.utils import check_user

# RadarGame Functions
async def get_token(username, password):
    try:
        res = requests.post(f"{CFG["RADARGAME_API_BASE"]}/auth/login", json={"username": username, "password": password})
        data = res.json()
        if not data["isSuccess"]: return None
        return data["result"]["accessToken"]
    except:
        return None

async def get_servers(token):
    try:
        res = requests.get(f"{CFG["RADARGAME_API_BASE"]}/user/servers", headers={"Authorization": f"Bearer {token}"})
        data = res.json()
        return data["result"] if data["isSuccess"] else []
    except:
        return []

async def get_config(token, server_id):
    try:
        res = requests.get(f"{CFG["RADARGAME_API_BASE"]}/user/account/getAccount",
                           headers={"Authorization": f"Bearer {token}"},
                           params={"serverId": server_id})
        data = res.json()
        return data["result"] if data["isSuccess"] else None
    except:
        return None

async def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def build_config_file(data):
    rand = await generate_random_string()
    primary_dns = data.get("primary_dns", "8.8.8.8")
    secondary_dns = data.get("secondary_dns", "1.1.1.1")
    dns_value = ",".join([primary_dns, secondary_dns])

    content = (
        # f"# Radar WireGuard Config\n"
        # f"# Developer Telegram: @nimazerobit\n\n"
        f"[Interface]\n"
        f"PrivateKey = {data['privateKey']}\n"
        f"Address = {data['addresses']}\n"
        f"DNS = {dns_value}\n"
        f"MTU = {data['mtu']}\n\n"
        f"[Peer]\n"
        f"PublicKey = {data['endpointPublicKey']}\n"
        f"PresharedKey = {data['presharedKey']}\n"
        f"Endpoint = {data['endpoint']}\n"
        f"AllowedIPs = {data['allowedIPs']}\n"
        f"PersistentKeepalive = {data['persistentKeepalive']}\n"
    )
    file_path = f"configs/radar-{rand}.conf"
    os.makedirs("configs", exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)
    return file_path

# RadarGame account manager
async def change_radar_account(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1, edit: bool = False):
    if not await check_user(update, context):
        return

    user_id = update.effective_user.id
    radargame_account = DBH.get_user_radargame_accounts(user_id)

    if not radargame_account:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(TEXTS["radargame"]["new_account_button"], callback_data="new_account")],
            [InlineKeyboardButton(TEXTS["backtomain"], callback_data="backtomain")]
        ])
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(TEXTS["radargame"]["no_account_found"], reply_markup=markup)
        else:
            await update.effective_chat.send_message(TEXTS["radargame"]["no_account_found"], reply_markup=markup)
        return

    PAGE_SIZE = 5
    total = len(radargame_account)
    max_page = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, max_page))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    accounts = radargame_account[start:end]

    message = f"<b>👤 اکانت های شما (صفحه {page}/{max_page}):</b>\n\n"
    keyboard = []
    for account in accounts:
        keyboard.append([
            InlineKeyboardButton(f"{'🟢' if account["is_active"] else '👤'} {account["username"]}", callback_data=f"set_active:{account["username"]}:{page}")
        ])
        keyboard.append([
            InlineKeyboardButton("🗑️ حذف", callback_data=f"remove_account:{account["username"]}")
        ])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"change_account:{page-1}"))
    if page < max_page:
        nav_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"change_account:{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(TEXTS["radargame"]["new_account_button"], callback_data="new_account")])
    keyboard.append([InlineKeyboardButton(TEXTS["backtomain"], callback_data="backtomain")])

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
    else:
        await update.effective_chat.send_message(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)

    return

USERNAME, PASSWORD = range(2)
async def new_radar_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(TEXTS["radargame"]["cancel_note"])
    await update.effective_message.reply_text(TEXTS["radargame"]["ask_username"])
    return USERNAME

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["username"] = update.message.text
    await update.effective_chat.send_message(TEXTS["radargame"]["ask_password"])
    return PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    username = context.user_data["username"]
    password = update.message.text
    
    # remove password message after received
    try:
        await update.message.delete()
    except:
        pass
    
    login_state_message = await update.effective_chat.send_message("⏳")

    markup = InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["backtomain"], callback_data="backtomain")]])
    
    if DBH.radargame_username_exists(user_id, username):
        await login_state_message.edit_text(TEXTS["radargame"]["duplicate_account_error"].format(username=username), reply_markup=markup)
        return ConversationHandler.END

    token = await get_token(username, password)
    if not token:
        await login_state_message.edit_text(TEXTS["radargame"]["login_fail"], reply_markup=markup)
        return ConversationHandler.END

    DBH.add_radargame_account(user_id, username, password, token)
    context.user_data["token"] = token
    await login_state_message.edit_text(TEXTS["radargame"]["login_success"], reply_markup=markup)
    return ConversationHandler.END

# New config
async def new_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return

    user_id = update.callback_query.from_user.id
    account = DBH.get_active_radargame_account(user_id)

    if account:
        context.user_data["username"] = account["username"]
        context.user_data["token"] = await get_token(account["username"], account["password"])
        if context.user_data["token"]:
            login_success_message = await update.effective_chat.send_message(TEXTS["radargame"]["login_success"])
            await context.bot.setMessageReaction(user_id, login_success_message.id, reaction=ReactionTypeEmoji('⚡'))
            await update.effective_chat.send_message(TEXTS["radargame"]["active_account_info"].format(user_id=user_id, email=account["username"]), reply_to_message_id=login_success_message.id, parse_mode="HTML")
            return await show_servers(update, context)
    else:
        await update.effective_chat.send_message(TEXTS["radargame"]["add_account_warning"], reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(TEXTS["main_menu"]["buttons"]["change_account"], callback_data="change_account")]]), parse_mode="HTML")
        return

async def show_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    servers = await get_servers(context.user_data["token"])
    if not servers:
        await update.effective_chat.send_message(TEXTS["radargame"]["no_server"])
        return ConversationHandler.END

    # Sort servers by loadPercentage (ascending)
    servers.sort(key=lambda server: server.get("loadPercentage", 100))

    keyboard = [
        [InlineKeyboardButton(TEXTS["radargame"]["server_button_format"].format(location=server['location'], load=server['loadPercentage']), callback_data=f"server_{str(server['id'])}")]
        for server in servers
    ]
    await update.effective_chat.send_message(TEXTS["radargame"]["choose_server"], reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

### --- RadarGame Callbacks --- ###
async def radargame_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user(update, context):
        return

    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id

    if data.startswith("dns_"):
        try:
            dns_idx = int(data.split("dns_")[1])
            
            if dns_idx >= len(DNS_LIST):
                raise ValueError("Invalid DNS selection")
                
            selected_dns = DNS_LIST[dns_idx]
            
            
        except Exception as e:
            print(f"Error processing DNS selection: {e}")
            await query.edit_message_text(TEXTS["radargame"]["cant_process_dns_selection"])
            return

        creds = DBH.get_active_radargame_account(query.from_user.id)
        if not creds:
            await query.edit_message_text(TEXTS["errors"]["unexpected_error"])
            return

        server_id = context.user_data.get("server_id")
        username = context.user_data.get("username")
        token = context.user_data.get("token")
        config = await get_config(token, server_id)
        if not config:
            await query.edit_message_text(TEXTS["errors"]["unexpected_error"])
            return

        config["primary_dns"] = selected_dns['primary']
        config["secondary_dns"] = selected_dns['secondary']
        file_path = await build_config_file(config)
        await query.edit_message_text(TEXTS["radargame"]["config_saved"])

        # Send config as text message
        with open(file_path, "r", encoding="utf-8") as f:
            config_text = f.read()
        await query.message.reply_text(f"<pre>{config_text}</pre>", parse_mode="HTML")

        # Send config as file
        await query.message.reply_document(InputFile(open(file_path, "rb")))

        # Warning text
        await query.message.reply_text(TEXTS["radargame"]["warning_text_1"], parse_mode="HTML")

        # Notify owner
        for owner_id in CFG["OWNERS"]:
            try:
                await context.bot.send_message(text=TEXTS["radargame"]["new_config_notify_owner"].format(user_id=query.from_user.id, fullname=query.from_user.full_name, username=query.from_user.username, radar_email=username),
                                               chat_id=owner_id, parse_mode="HTML")
            except Exception as e:
                print(f"Failed to notify owner: {e}")
        return

    elif data.startswith("server_"):
        server_id = str(data.split("server_")[1])
        context.user_data["server_id"] = server_id
        
        try:
            keyboard = [
                [InlineKeyboardButton(
                    dns["name"], 
                    callback_data=f"dns_{idx}"
                )]
                for idx, dns in enumerate(DNS_LIST)
            ]
            await query.edit_message_text(TEXTS["radargame"]["dns_selection"], reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            print(f"Error loading DNS config: {e}")
            await query.edit_message_text(TEXTS["radargame"]["cant_load_dns_list"])
        return
    
    elif data.startswith("set_active"):
        parts = data.split(":")
        if len(parts) < 2:
            await query.answer(TEXTS["radargame"]["change_account"]["error"], show_alert=True)
            return
        account_username = str(parts[1])
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        status = DBH.set_active_radargame(user_id, account_username)
        if status:
            await query.answer(TEXTS["radargame"]["change_account"]["success"], show_alert=True)
        else:
            await query.answer(TEXTS["radargame"]["change_account"]["error"], show_alert=True)
        await change_radar_account(update, context, page=page, edit=True)
        return

    elif data.startswith("change_account"):
        parts = data.split(":")
        page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        await change_radar_account(update, context, page=page, edit=True)
        return

    elif data.startswith("remove_account:"):
        parts = data.split(":")
        if len(parts) < 2:
            await query.answer(TEXTS["radargame"]["remove_account"]["error"], show_alert=True)
            return
        account_username = str(parts[1])
        removed = DBH.delete_radargame_account(user_id, account_username)
        if removed:
            await query.answer(TEXTS["radargame"]["remove_account"]["success"], show_alert=True)
        else:
            await query.answer(TEXTS["radargame"]["remove_account"]["error"], show_alert=True)
        await change_radar_account(update, context, page=1, edit=True)
        return