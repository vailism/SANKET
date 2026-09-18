import pandas as pd
df = pd.read_parquet("DATA/model_dataset.parquet")
matches = df[df["project_name"].str.contains("ATCHUTAPURAM", na=False)]
print(matches[["project_id", "project_name", "sector", "ministry", "state"]].drop_duplicates())
