import json
from pathlib import Path
from core.db import DB

# Paths
CONFIG_PATH = Path("config/config.json")
TEXTS_PATH = Path("config/texts.json")
DNS_LIST_PATH = Path("config/custom_dns.json")

# Initial
CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
TEXTS = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
DNS_LIST = json.loads(DNS_LIST_PATH.read_text(encoding="utf-8")).get('dns_list', [])
DBH = DB(CFG["DB_PATH"])

def reload_config():
    global CFG, DBH
    new_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    CFG.clear()
    CFG.update(new_cfg)
    DBH = DB(CFG["DB_PATH"])
    return CFG

def reload_dns_list():
    global DNS_LIST
    new_dns_list = json.loads(DNS_LIST_PATH.read_text(encoding="utf-8")).get('dns_list', [])
    DNS_LIST.clear()
    DNS_LIST.extend(new_dns_list)
    return DNS_LIST

def reload_texts():
    global TEXTS
    new_texts = json.loads(TEXTS_PATH.read_text(encoding="utf-8"))
    TEXTS.clear()
    TEXTS.update(new_texts)
    return TEXTS