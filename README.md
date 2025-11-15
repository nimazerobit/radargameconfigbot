# RadarGame Config Telegram Bot
Telegram bot for recieve RadarGame Wireguard config built in Python

## 🚀 Features
-   Handle multiple RadarGame account for each bot user
-   Admin panel for managing bot log notifications and managing users.
-   Able to choose custom DNS server before generating config file.
-   Force join and ban system for users.

## 📥 Installation & Setup
1.  Clone project:
    ```bash
    git clone https://github.com/nimazerobit/radargameconfigbot.git
    cd radargameconfigbot
    ```
2.  Install requirements:
    ```bash
    pip install -r requirements.txt
    ```
3.  Modify config files:
    -   Edit `custom_dns.json` inside `config/` if you want to.
    -   RENAME `config-example.json` to `config.json`
4.  Run the bot:
    ```bash
    python main.py
    ```

## 👍 Contributing
Open issues for improvements.