import pandas as pd
from sanket.inference import load_inference_engine
engine = load_inference_engine()
features = engine["features"]
df = pd.read_parquet("DATA/portfolio_active.parquet")
missing = [f for f in features if f not in df.columns]
print(f"Missing features in active_projects_df: {missing}")
