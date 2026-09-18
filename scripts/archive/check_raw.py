import pandas as pd
df = pd.read_parquet("DATA/model_dataset.parquet")
print(df[df["project_id"] == "180100210"][["reporting_month", "schedule_deviation_months", "schedule_deviation_change"]].tail())
