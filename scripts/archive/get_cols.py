import pandas as pd
df = pd.read_parquet("DATA/portfolio_genuine.parquet")
print(df.columns.tolist()[:10], len(df.columns))
