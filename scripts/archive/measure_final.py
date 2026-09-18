import requests
import time
import psutil
import json

def get_server_rss():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(proc.info['cmdline'] or [])
            if "uvicorn sanket.api:app" in cmd:
                return proc.memory_info().rss / (1024 * 1024)
        except:
            pass
    return 0

base_url = "http://127.0.0.1:8000"

print(f"Initial server memory: {get_server_rss():.1f} MB")

endpoints = [
    "/api/dashboard/summary",
    "/api/dashboard/interventions",
    "/api/projects/N16000115",
    "/api/projects/N16000115/replay",
    "/api/projects/N18000110",
    "/api/projects/N18000110/replay",
    "/api/projects/N24000134",
    "/api/projects/N24000134/replay"
]

max_rss = get_server_rss()

for ep in endpoints:
    print(f"Requesting {ep}...")
    try:
        r = requests.get(base_url + ep)
        rss = get_server_rss()
        max_rss = max(max_rss, rss)
        print(f" -> {r.status_code}, RSS: {rss:.1f} MB")
    except Exception as e:
        print(f" -> Error: {e}")
    time.sleep(0.5)

print(f"Peak memory observed: {max_rss:.1f} MB (Must be < 512 MB)")
