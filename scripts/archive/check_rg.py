import pyarrow.parquet as pq
pf = pq.ParquetFile("DATA/model_dataset.parquet")
print(f"Num row groups: {pf.num_row_groups}")
print(f"Rows per group: {pf.metadata.row_group(0).num_rows}")
