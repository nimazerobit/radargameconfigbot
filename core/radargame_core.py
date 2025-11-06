import requests
import random
import string
import os

from core.config_loader import CFG

async def get_token(username, password):
    try:
        res = requests.post(f"{CFG["َRADARGAME_API_BASE"]}/auth/login", json={"username": username, "password": password})
        data = res.json()
        if not data["isSuccess"]: return None
        return data["result"]["accessToken"]
    except:
        return None

async def get_servers(token):
    try:
        res = requests.get(f"{CFG["َRADARGAME_API_BASE"]}/user/servers", headers={"Authorization": f"Bearer {token}"})
        data = res.json()
        return data["result"] if data["isSuccess"] else []
    except:
        return []

async def get_config(token, server_id):
    try:
        res = requests.get(f"{CFG["َRADARGAME_API_BASE"]}/user/account/getAccount",
                           headers={"Authorization": f"Bearer {token}"},
                           params={"serverId": server_id})
        data = res.json()
        return data["result"] if data["isSuccess"] else None
    except:
        return None

async def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def build_config_file(data):
    rand = generate_random_string()
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
