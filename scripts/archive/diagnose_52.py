import requests

base = "https://vigil-kou0.onrender.com"
r = requests.get(f"{base}/api/projects?limit=500")
data = r.json()

pids = []
for p in data.get("projects", []):
    risk_tier = p.get("latest_risk_tier")
    latest_risk = p.get("latest_risk", 0) or 0
    score = 0 if risk_tier == 'NORMAL' else round(latest_risk * 100)
    if score == 52:
        pids.append(p.get("project_id"))

for pid in pids:
    print(f"\n--- Checking {pid} ---")
    for sub in ["", "/replay"]:
        url = f"{base}/api/projects/{pid}{sub}"
        r = requests.get(url)
        print(f"{url} -> {r.status_code}")
        if r.status_code != 200:
            print(r.text)
