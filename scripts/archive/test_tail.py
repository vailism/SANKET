import pandas as pd
import numpy as np

df = pd.DataFrame({
    "project_id": ["A", "A", "A"],
    "reporting_month": ["2024-01", "2024-02", "2024-03"],
    "val": [10, 20, np.nan]
})

print("With .last():")
print(df.groupby("project_id").last())

print("\nWith .tail(1):")
print(df.groupby("project_id").tail(1))
