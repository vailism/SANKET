import gc, os, psutil
process = psutil.Process(os.getpid())
def get_mem():
    gc.collect()
    return process.memory_info().rss / 1024 / 1024

print(f"Base: {get_mem():.2f} MB")
from sanket.inference import load_inference_engine
print(f"After import: {get_mem():.2f} MB")
engine = load_inference_engine()
print(f"After engine: {get_mem():.2f} MB")
import pandas as pd
p_df = pd.read_parquet("DATA/model_dataset.parquet", filters=[("project_id", "==", "180100210")])
print(f"After read_parquet: {get_mem():.2f} MB")
from sanket.replay import replay_project_from_dataframe
replay_project_from_dataframe(p_df, engine=engine)
print(f"After replay: {get_mem():.2f} MB")
