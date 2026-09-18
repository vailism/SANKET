with open("tests/test_api.py", "r") as f:
    content = f.read()

import re

# Replace test 9 and 10 with the rigorous parity tests
old_test_pattern = r'def test_9_api_predictions_match_inference_engine.*?def test_10_api_replay_matches_get_project_replay.*?(?=def |\Z)'
new_test = """def test_9_api_predictions_match_canonical_replay(client):
    \"\"\"9. Test API project details prediction matches independent chronological replay calculation.\"\"\"
    # Explicitly test the discrepant project (180100210) and a few others
    pids = ["180100210", "150100650", "220100133", "180100262", "150101111"]
    
    engine = load_inference_engine()
    
    for pid in pids:
        resp = client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        api_data = resp.json()
        
        # Canonical replay path
        rep = get_project_replay(pid, engine=engine)
        latest_rec = rep["timeline"][-1]
        
        # They must match canonical chronological replay exactly
        assert api_data["latest_prediction"]["raw_prob"] == pytest.approx(latest_rec["raw_prob"], abs=1e-5)
        assert api_data["latest_prediction"]["pred_prob"] == pytest.approx(latest_rec["pred_prob"], abs=1e-5)
        assert api_data["latest_prediction"]["risk_tier"] == latest_rec["risk_tier"]
        assert api_data["latest_prediction"]["alert"] == latest_rec["alert"]

def test_10_static_artifact_matches_canonical_replay(client):
    \"\"\"10. Validate static artifact directly against canonical replay inference path.\"\"\"
    from sanket.api import get_app_context
    ctx = get_app_context()
    df = ctx.get("genuine_df")
    
    pids = ["180100210", "150100650", "220100133"]
    engine = load_inference_engine()
    
    for pid in pids:
        row = df[df["project_id"] == pid].iloc[0]
        
        from sanket.inference import predict_point_in_time
        pred = predict_point_in_time(row, engine)
        
        rep = get_project_replay(pid, engine=engine)
        latest_rec = rep["timeline"][-1]
        
        assert pred["raw_prob"] == pytest.approx(latest_rec["raw_prob"], abs=1e-5)
        assert pred["pred_prob"] == pytest.approx(latest_rec["pred_prob"], abs=1e-5)
        assert pred["risk_tier"] == latest_rec["risk_tier"]
"""

content = re.sub(old_test_pattern, new_test, content, flags=re.DOTALL)

with open("tests/test_api.py", "w") as f:
    f.write(content)
