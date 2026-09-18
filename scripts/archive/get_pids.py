import pandas as pd
df = pd.read_parquet("DATA/portfolio_genuine.parquet")
print(df["project_id"].head(5).tolist())
