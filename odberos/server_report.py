import requests
import shutil
import socket
import psutil
import sys

# Reuse your existing Kuma Bot credentials
HC_UUID = "3d1e1a1e-29bd-4ee6-8508-9a46d53bedd0"
TOKEN = "8308981650:AAE9ruZxe9lZuMZFM24eEng1UuxwFKem4w4"
CHAT_ID = ["-1003891440639"]
HOSTNAME = socket.gethostname()

# 1. Stats
cpu = psutil.cpu_percent(interval=1)
ram = psutil.virtual_memory().percent
disk = round((shutil.disk_usage("/").used / shutil.disk_usage("/").total) * 100, 1)

# 2. Logic: Should we notify?
is_unhealthy = (cpu > 90 or ram > 90 or disk > 90)
is_9am_report = "--report" in sys.argv 

# 3. SILENT Heartbeat (Always runs)
try:
    url = f"https://hc-ping.com/{HC_UUID}"
    if is_unhealthy: url += "/fail"
    requests.post(url, data=f"CPU:{cpu}% RAM:{ram}% Disk:{disk}%", timeout=5)
except: pass

# 4. TELEGRAM Notification (Only on health change OR at 9:00 AM)
if is_unhealthy or is_9am_report:
    title = "DAILY HEALTH REPORT" if is_9am_report else "⚠️ SYSTEM HEALTH ALERT"
    status_emoji = "✅ Healthy" if not is_unhealthy else "❌ Unhealthy"
    
    msg = (f"{title}: {HOSTNAME}\n\n"
           f" CPU: {cpu}%\n"
           f"RAM: {ram}%\n"
           f"Disk: {disk}%\n"
           f"Status: {status_emoji}")
           
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass
