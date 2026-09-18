import pandas as pd
df = pd.read_parquet("DATA/portfolio_genuine.parquet")
rec = df[df["project_id"] == "N16000342"].iloc[0]

print("sector:", str(rec["sector_display"]) if pd.notna(rec.get("sector_display")) else (str(rec["sector_clean"]) if pd.notna(rec.get("sector_clean")) else "OTHER"))
print("ministry:", str(rec["ministry"]) if pd.notna(rec.get("ministry")) else "—")
print("state:", str(rec["state"]) if pd.notna(rec.get("state")) else "—")
