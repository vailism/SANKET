import pandas as pd
from sanket.inference import load_inference_engine, predict_point_in_time

engine = load_inference_engine()
df = pd.read_parquet("DATA/portfolio_active.parquet")
row = df[df["project_id"] == "180100210"]

try:
    pred = predict_point_in_time(row, engine)
    print("Success!")
    print(pred)
except Exception as e:
    import traceback
    traceback.print_exc()
