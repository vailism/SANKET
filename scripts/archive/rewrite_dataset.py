import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import hashlib

OLD_FILE = "DATA/model_dataset.parquet"
NEW_FILE = "DATA/model_dataset_new.parquet"

print("1. Loading old dataset...")
df_old = pd.read_parquet(OLD_FILE)
old_rows = len(df_old)
old_cols = df_old.columns.tolist()

def get_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

old_hash = get_hash(OLD_FILE)
print(f"Old hash: {old_hash}")
print(f"Old rows: {old_rows}")

print("2. Sorting...")
df_new = df_old.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)

print("3. Writing new dataset with row_group_size=5000...")
table = pa.Table.from_pandas(df_new, preserve_index=False)
pq.write_table(table, NEW_FILE, row_group_size=5000)

print("4. Validating equivalence...")
df_reload = pd.read_parquet(NEW_FILE)

# Validate identical rows
assert len(df_reload) == old_rows, f"Row count mismatch: {len(df_reload)} vs {old_rows}"
# Validate identical columns
assert df_reload.columns.tolist() == old_cols, "Column mismatch"

# Validate exact values mapping
df_old_sorted = df_old.sort_values(by=["project_id", "reporting_month"]).reset_index(drop=True)

# Using equals to check exact match including NaNs
pd.testing.assert_frame_equal(df_old_sorted, df_reload, check_like=True)
print("Data equivalence perfectly validated. All rows, columns, types, and NaNs match.")

import os
os.rename(OLD_FILE, "DATA/model_dataset.parquet.bak")
os.rename(NEW_FILE, OLD_FILE)

new_hash = get_hash(OLD_FILE)
print(f"New hash: {new_hash}")
print("Rewrite complete and verified.")
