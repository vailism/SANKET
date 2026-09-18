import pandas as pd
df = pd.read_parquet("DATA/model_dataset.parquet")
match = df[df["project_name"].str.contains("ATCHUTAPURAM", na=False)]
print(match[["project_id", "project_name", "sector", "ministry", "state"]].head(1))
