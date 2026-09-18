import pandas as pd
df = pd.read_parquet("DATA/model_dataset.parquet")
m = df[df["project_id"] == "N16000342"].sort_values("reporting_month")
print(m[["reporting_month", "V_fin_1m", "V_fin_3m", "A_fin", "EWMA_V_fin"]].tail(5))
