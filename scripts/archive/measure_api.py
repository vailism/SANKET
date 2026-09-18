import psutil
import os
from fastapi.testclient import TestClient
from sanket.api import app

process = psutil.Process(os.getpid())
def get_mem():
    return process.memory_info().rss / 1024 / 1024

print(f"Startup: {get_mem():.2f} MB")
client = TestClient(app)
print(f"After TestClient: {get_mem():.2f} MB")

client.get("/health")
print(f"After /health: {get_mem():.2f} MB")

client.get("/api/dashboard/summary")
print(f"After /api/dashboard/summary: {get_mem():.2f} MB")

client.get("/api/projects")
print(f"After /api/projects: {get_mem():.2f} MB")

# find a project id
from sanket.portfolio import _load_active_portfolio
df = _load_active_portfolio()
pid = df["project_id"].iloc[0]

client.get(f"/api/projects/{pid}")
print(f"After /api/projects/{pid}: {get_mem():.2f} MB")

client.get(f"/api/projects/{pid}/replay")
print(f"After /api/projects/{pid}/replay: {get_mem():.2f} MB")

print(f"Final: {get_mem():.2f} MB")
