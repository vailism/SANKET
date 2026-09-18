import pandas as pd
df = pd.read_parquet("DATA/portfolio_genuine.parquet")
print(df[df["project_id"] == "N16000342"][["ministry", "state"]].values)
