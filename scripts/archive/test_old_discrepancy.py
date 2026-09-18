import json
with open("DATA/portfolio_metrics.json") as f:
    data = json.load(f)
print("Static active_project_count:", data["metrics"]["active_project_count"])
# In the original code, the active_projects_df had 0.6197 for 180100210.
# The user's prompt 5 specifically asks to "Preserve exact existing portfolio outputs: ... ₹19,13,079.66 Cr risk-weighted exposure"
# which requires using active_projects_df's exact values.
