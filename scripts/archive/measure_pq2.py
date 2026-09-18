import gc, os, psutil
import pyarrow as pa
import pyarrow.parquet as pq
process = psutil.Process(os.getpid())
def get_mem():
    gc.collect()
    pa.default_memory_pool().release_unused()
    import ctypes
    libc = ctypes.CDLL("libc.dylib" if os.uname().sysname == "Darwin" else "libc.so.6")
    try:
        # malloc_trim
        libc.malloc_trim(0)
    except:
        pass
    return process.memory_info().rss / 1024 / 1024

print(f"Base: {get_mem():.2f} MB")
table = pq.read_table("DATA/model_dataset.parquet", filters=[("project_id", "==", "180100210")])
print(f"After read_table: {get_mem():.2f} MB")
df = table.to_pandas()
print(f"After to_pandas: {get_mem():.2f} MB")
del table
del df
print(f"After del: {get_mem():.2f} MB")
