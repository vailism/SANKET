import requests
import json

r = requests.get("http://localhost:8000/api/projects/N16000342")
if r.status_code == 200:
    data = r.json()
    print("Project Name:", data["project_name"])
    print("EWMA:", data.get("current_trajectory_metrics", {}).get("EWMA_V_fin"))
    print("V(3m):", data.get("current_trajectory_metrics", {}).get("V_fin_3m"))
