import os
import psutil
import time

process = psutil.Process(os.getpid())
def get_mem():
    return process.memory_info().rss / 1024 / 1024

print(f"Base memory: {get_mem():.2f} MB")

import pandas as pd
print(f"After pandas: {get_mem():.2f} MB")

from sanket import storage
print(f"After sanket.storage: {get_mem():.2f} MB")

from sanket import portfolio
print(f"After sanket.portfolio: {get_mem():.2f} MB")

from sanket import inference
print(f"After sanket.inference: {get_mem():.2f} MB")

from sanket import replay
print(f"After sanket.replay: {get_mem():.2f} MB")

from sanket import api
print(f"After sanket.api: {get_mem():.2f} MB")
