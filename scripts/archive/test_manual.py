from fastapi.testclient import TestClient
from sanket.api import app, get_app_context
from sanket.inference import load_inference_engine, predict_point_in_time

client = TestClient(app)
pid = "180100210"

resp = client.get(f"/api/projects/{pid}")
api_data = resp.json()

ctx = get_app_context()
df = ctx.get("genuine_df")
row = df[df["project_id"] == pid]
rec = row.iloc[0]

engine = load_inference_engine()
pred = predict_point_in_time(row, engine)

print("API raw_prob:", api_data["latest_prediction"]["raw_prob"])
print("Static row raw_prob:", pred["raw_prob"])
