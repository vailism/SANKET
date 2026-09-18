import pandas as pd
df = pd.read_parquet("DATA/model_dataset.parquet")
match = df[df["project_id"] == "N16000305"].sort_values("reporting_month")
print(match[["reporting_month", "V_exp_3m", "expenditure_to_baseline", "V_fin_1m", "V_fin_3m", "A_fin", "EWMA_V_fin", "schedule_deviation_months"]].tail(5))
