import pandas as pd
from sanket.inference import load_inference_engine
from sanket.replay import get_project_replay

engine = load_inference_engine()
pid = "180100210"

old_rep = get_project_replay(pid, dataset_path="DATA/model_dataset.parquet", engine=engine)
old_timeline = pd.read_parquet("DATA/model_dataset.parquet", filters=[("project_id", "==", pid)])
old_row = old_timeline.iloc[-1]

df = pd.read_parquet("DATA/portfolio_genuine.parquet")
new_row = df[df["project_id"] == pid].iloc[0]

features = engine["features"]

diffs = []
for f in features:
    old_val = old_row[f]
    new_val = new_row[f]
    
    # Handle NaN comparisons
    if pd.isna(old_val) and pd.isna(new_val):
        continue
    if old_val != new_val:
        diffs.append((f, old_val, new_val))

print(f"Differences in features for {pid}:")
for f, old, new in diffs:
    print(f"  {f}: OLD={old} | NEW={new}")
    
