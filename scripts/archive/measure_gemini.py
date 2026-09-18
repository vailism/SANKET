import gc, os, psutil
process = psutil.Process(os.getpid())
def get_mem():
    gc.collect()
    return process.memory_info().rss / 1024 / 1024

print(f"Base: {get_mem():.2f} MB")
import google.generativeai as genai
print(f"After import: {get_mem():.2f} MB")
model = genai.GenerativeModel("gemini-1.5-flash")
print(f"After init: {get_mem():.2f} MB")
