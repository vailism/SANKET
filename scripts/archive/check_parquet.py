import pandas as pd
df = pd.read_parquet("DATA/model_dataset.parquet", columns=["project_id", "reporting_month", "raw_prob", "pred_prob", "risk_tier", "alert"])
print(df.head())
