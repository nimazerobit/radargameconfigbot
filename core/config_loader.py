import json
from pathlib import Path
from core.db import DB

# ——— Global state ———
CFG = json.loads(Path("config/config.json").read_text(encoding="utf-8"))
DBH = DB(CFG["DB_PATH"])
DNS_LIST = json.loads(Path('config/custom_dns.json').read_text(encoding='utf-8')).get('dns_list', [])


def reload_config():
    global CFG, DNS_LIST
    new_cfg = json.loads(Path("config/config.json").read_text(encoding="utf-8"))
    CFG = new_cfg
    new_dns_list = json.loads(Path('config/custom_dns.json').read_text(encoding='utf-8')).get('dns_list', [])
    DNS_LIST = new_dns_list
    return CFG, DNS_LIST