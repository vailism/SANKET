import requests
import json

r = requests.get("http://localhost:8000/api/projects/N16000305")
if r.status_code == 200:
    data = r.json()
    print("Project Details (metrics portion):")
    print(f"total_observations: {data['total_observations']}")
    print(f"V_fin_1m: {data['trajectory_metrics']['V_fin_1m']}")
    print(f"V_fin_3m: {data['trajectory_metrics']['V_fin_3m']}")
    print(f"A_fin: {data['trajectory_metrics']['A_fin']}")
    print(f"EWMA: {data['trajectory_metrics']['EWMA_V_fin']}")
    
    print("\nExplanations:")
    for ex in data['top_explanations']:
        print(ex)
else:
    print(f"Failed: {r.status_code}")
