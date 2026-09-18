import pandas as pd
df = pd.read_parquet("DATA/portfolio_genuine.parquet")
val = df[df["project_id"] == "N16000342"]["ministry"].iloc[0]
print("Type:", type(val))
print("Value:", val)
