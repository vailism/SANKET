import json
from fastapi.testclient import TestClient
from sanket.api import app

client = TestClient(app)

pids = ["180100210", "340600100", "340600110", "330400030", "330400040"]

for pid in pids:
    print(f"\n--- Project: {pid} ---")
    resp = client.get(f"/api/projects/{pid}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"start_month: {data['start_month']}")
        print(f"end_month: {data['end_month']}")
        print(f"total_observations: {data['total_observations']}")
        print(f"risk_tier: {data['current_risk_tier']}")
    else:
        print(f"Failed: {resp.status_code}")
