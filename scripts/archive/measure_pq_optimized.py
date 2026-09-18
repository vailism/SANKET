import gc, os, psutil
import pandas as pd

process = psutil.Process(os.getpid())
def get_mem():
    gc.collect()
    return process.memory_info().rss / 1024 / 1024

print(f"Base: {get_mem():.2f} MB")

df = pd.read_parquet("DATA/model_dataset_optimized.parquet", filters=[("project_id", "==", "180100210")])

print(f"After filtered read: {get_mem():.2f} MB")
print(f"Rows read: {len(df)}")
