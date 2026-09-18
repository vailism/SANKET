import psutil
import os
import gc
from fastapi.testclient import TestClient
from sanket.api import app

process = psutil.Process(os.getpid())
def get_mem():
    gc.collect()
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

pid = "180100210" # Known genuine project
client.get(f"/api/projects/{pid}")
print(f"After /api/projects/{pid}: {get_mem():.2f} MB")

# Mock the Gemini client so it doesn't fail if key is missing/bad
import os
os.environ["GEMINI_API_KEY"] = "MOCK"
try:
    client.post("/api/ai/project-brief", json={"project_id": pid})
except Exception:
    pass
print(f"After /api/ai/project-brief (no fallback): {get_mem():.2f} MB")

client.get(f"/api/projects/{pid}/replay")
print(f"After /api/projects/{pid}/replay (loads ML): {get_mem():.2f} MB")

try:
    client.post("/api/ai/project-brief", json={"project_id": "020100040"})
except Exception:
    pass
print(f"After second /api/ai/project-brief: {get_mem():.2f} MB")

