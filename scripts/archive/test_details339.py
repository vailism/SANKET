import requests
import json

r = requests.get("http://localhost:8000/api/projects/N16000339")
if r.status_code == 200:
    data = r.json()
    print(json.dumps(data, indent=2))
