import requests
import json

r = requests.get("http://localhost:8000/api/projects/N16000342")
if r.status_code == 200:
    data = r.json()
    print("latest_prediction:", data["latest_prediction"])
