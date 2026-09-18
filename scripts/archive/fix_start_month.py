import re

with open("sanket/portfolio.py", "r") as f:
    content = f.read()

old_code = """        # Deduplicate strictly by reporting_month to extract latest observation per entity
        df_sorted = df_full.sort_values("reporting_month")
        latest_all = df_sorted.groupby("project_id").last().reset_index()"""

new_code = """        # Deduplicate strictly by reporting_month to extract latest observation per entity
        df_sorted = df_full.sort_values("reporting_month")
        latest_all = df_sorted.groupby("project_id").last().reset_index()
        
        # Calculate start_month
        first_all = df_sorted.groupby("project_id").first().reset_index()
        start_months = dict(zip(first_all["project_id"], first_all["reporting_month"]))
        latest_all["start_month"] = latest_all["project_id"].map(start_months)
"""
if old_code in content:
    with open("sanket/portfolio.py", "w") as f:
        f.write(content.replace(old_code, new_code))
    print("Patched portfolio.py")
else:
    print("Could not find old_code")
