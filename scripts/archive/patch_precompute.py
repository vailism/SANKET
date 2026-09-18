import re

with open("scripts/precompute_portfolio.py", "r") as f:
    content = f.read()

new_code = """
    # Sector breakdown
    sector_breakdown = []
    for s_name, s_df in active_projects_df.groupby("sector_display"):
        sector_breakdown.append({
            "sector": str(s_name),
            "total_projects": int(len(s_df)),
            "escalate_count": int((s_df["risk_tier"] == "ESCALATE").sum()),
            "review_count": int((s_df["risk_tier"] == "REVIEW").sum()),
            "watch_count": int((s_df["risk_tier"] == "WATCH").sum()),
            "total_exposure": float(s_df["baseline_cost"].sum())
        })
    sector_breakdown.sort(key=lambda x: x["total_exposure"], reverse=True)
"""

pattern = r'    # Sector breakdown.*?    sector_breakdown.sort\(key=lambda x: x\["total_exposure"\], reverse=True\)'
content = re.sub(pattern, new_code.strip(), content, flags=re.DOTALL)

with open("scripts/precompute_portfolio.py", "w") as f:
    f.write(content)
