import requests
import json

r = requests.get("http://localhost:8000/api/projects/N16000305")
if r.status_code == 200:
    data = r.json()
    print("Project Details Keys:")
    print(list(data.keys()))
    print(data)
