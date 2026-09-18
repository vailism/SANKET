import os
import json
import pandas as pd
from typing import Dict, Any

from sanket.api import get_app_context, get_lazy_engine
from sanket.replay import get_project_replay
from sanket.inference import predict_point_in_time

def test_api_semantics():
    ctx = get_app_context()
    engine = get_lazy_engine(ctx)
    df = ctx.get("genuine_df")
    
    # Select 5 genuine projects
    sample_pids = ["180100210", "150100260", "150100360", "150200050", "150100650"]
    
    print("=== API SEMANTICS COMPARISON ===")
    
    for pid in sample_pids:
        print(f"\nProject: {pid}")
        # OLD BEHAVIOR (via get_project_replay)
        try:
            old_rep = get_project_replay(pid, dataset_path=ctx["dataset_path"], engine=engine)
            old_latest = old_rep["timeline"][-1]
        except Exception as e:
            print(f"  Old Failed: {e}")
            continue
            
        # NEW BEHAVIOR (via 1-row inference)
        row = df[df["project_id"] == pid]
        if row.empty:
            print("  New Failed: Not in genuine_df")
            continue
        
        rec = row.iloc[0]
        new_pred = predict_point_in_time(row, engine)
        
        print(f"  Field: OLD | NEW")
        print(f"  start_month: {old_rep['start_month']} | (Currently hardcoded Unknown in api.py)")
        print(f"  end_month: {old_rep['end_month']} | {rec.get('reporting_month')}")
        print(f"  total_observations: {old_rep['total_observations']} | {rec.get('observation_number')}")
        print(f"  raw_prob: {old_latest['raw_prob']} | {new_pred['raw_prob']}")
        print(f"  pred_prob: {old_latest['pred_prob']} | {new_pred['pred_prob']}")
        print(f"  risk_tier: {old_latest['risk_tier']} | {new_pred['risk_tier']}")
        print(f"  C_base: {old_latest['C_base']} | {rec.get('C_base')}")
        print(f"  expenditure: {old_latest['expenditure']} | {rec.get('expenditure')}")
        print(f"  financial_progress: {old_latest['financial_progress']} | {rec.get('financial_progress')}")
        print(f"  trajectory_risk_score: {old_latest['trajectory_risk_score']} | {rec.get('trajectory_risk_score')}")

if __name__ == "__main__":
    test_api_semantics()
