import pandas as pd
df = pd.read_parquet("DATA/portfolio_active.parquet")
print(df.columns.tolist())
