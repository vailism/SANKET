from fastapi.testclient import TestClient
from sanket.api import app
client = TestClient(app)
resp = client.get("/api/projects?search=020100040")
data = resp.json()
print("Search results for 020100040:", [p["project_id"] for p in data["projects"]])
