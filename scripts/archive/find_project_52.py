import requests

r = requests.get("https://vigil-kou0.onrender.com/api/projects?limit=500")
data = r.json()

for p in data.get("projects", []):
    # score logic from app.js
    risk_tier = p.get("latest_risk_tier")
    latest_risk = p.get("latest_risk", 0) or 0
    score = 0 if risk_tier == 'NORMAL' else round(latest_risk * 100)
    
    if score == 52:
        print(f"FOUND PROJECT 52: {p.get('project_id')} ({p.get('project_name')}), latest_risk_tier={risk_tier}, latest_risk={latest_risk}")

