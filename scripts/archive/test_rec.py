import pandas as pd
df = pd.read_parquet("DATA/portfolio_genuine.parquet")
rec = df[df["project_id"] == "N16000342"].iloc[0]
print("ministry from rec:", rec.get("ministry"))
print("pd.notna:", pd.notna(rec.get("ministry")))
print("sector from rec:", rec.get("sector_display"))
print("pd.notna sector:", pd.notna(rec.get("sector_display")))
print("sector_clean:", rec.get("sector_clean"))
print("pd.notna clean:", pd.notna(rec.get("sector_clean")))
