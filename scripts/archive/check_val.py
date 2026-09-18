import pandas as pd
df = pd.read_parquet("DATA/model_dataset.parquet", filters=[("project_id", "==", "180100210")])
print(df[["reporting_month", "schedule_deviation_months", "schedule_deviation_change"]].tail())
