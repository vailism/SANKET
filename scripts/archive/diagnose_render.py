import requests

base = "https://vigil-kou0.onrender.com"

endpoints = [
    "/health",
    "/api/dashboard/summary",
    "/api/projects?limit=5"
]

print("=== DIAGNOSING RENDER ===")
real_pid = None

for ep in endpoints:
    url = base + ep
    print(f"\n--- {ep} ---")
    r = requests.get(url)
    print(f"STATUS: {r.status_code}")
    
    try:
        data = r.json()
        print(f"RESPONSE JSON KEYS: {list(data.keys()) if isinstance(data, dict) else 'List of length ' + str(len(data))}")
        if ep == "/api/projects?limit=5":
            if "projects" in data and len(data["projects"]) > 0:
                real_pid = data["projects"][0]["project_id"]
                print(f"SELECTED REAL PROJECT ID: {real_pid}")
    except Exception as e:
        print(f"RESPONSE TEXT: {r.text[:500]}")

if real_pid:
    for sub in ["", "/replay"]:
        url = f"{base}/api/projects/{real_pid}{sub}"
        print(f"\n--- /api/projects/{real_pid}{sub} ---")
        r = requests.get(url)
        print(f"STATUS: {r.status_code}")
        try:
            print(f"RESPONSE TEXT: {r.text[:500]}")
        except:
            pass

