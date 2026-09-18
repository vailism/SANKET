import pandas as pd
import pyarrow.parquet as pq

# 1. Read raw dataset to get start_month
print("Reading model_dataset.parquet...")
pf = pq.ParquetFile("DATA/model_dataset.parquet")
# Read only project_id and reporting_month
raw_df = pf.read(["project_id", "reporting_month"]).to_pandas()

print("Calculating start_month...")
first_df = raw_df.sort_values("reporting_month").groupby("project_id").first().reset_index()
start_months = dict(zip(first_df["project_id"], first_df["reporting_month"]))

# 2. Add to precomputed artifacts
for fname in ["DATA/portfolio_genuine.parquet", "DATA/portfolio_active.parquet", "DATA/portfolio_historical.parquet"]:
    print(f"Updating {fname}...")
    df = pd.read_parquet(fname)
    df["start_month"] = df["project_id"].map(start_months)
    df.to_parquet(fname, index=False)
print("Done.")
