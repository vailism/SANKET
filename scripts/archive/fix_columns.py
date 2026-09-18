with open("scripts/precompute_portfolio.py", "r") as f:
    content = f.read()

import re

new_code = """
    active_projects_df["latest_risk"] = np.round(cal_probs, 4)
    active_projects_df["risk_tier"] = risk_tiers
    active_projects_df["latest_risk_tier"] = risk_tiers

    cbase_vals = pd.to_numeric(active_projects_df["C_base"], errors="coerce").fillna(0).values
    active_projects_df["baseline_cost"] = np.round(cbase_vals, 2)
    active_projects_df["priority_score"] = np.round(
        active_projects_df["latest_risk"] * active_projects_df["baseline_cost"], 2
    )
    active_projects_df["risk_weighted_exposure"] = active_projects_df["priority_score"]
    
    active_projects_df["sector_display"] = (
        active_projects_df["sector_clean"]
        .fillna(active_projects_df["sector"])
        .fillna("Unknown")
        .astype(str)
    )

    risk_weighted_exposure = active_projects_df["risk_weighted_exposure"].sum()

    tier_counts = active_projects_df["risk_tier"].value_counts().to_dict()

    # Additional aggregations
    active_baseline_exposure = active_projects_df["baseline_cost"].sum()
    exposure_in_escalate = active_projects_df[active_projects_df["risk_tier"] == "ESCALATE"]["baseline_cost"].sum()
    
    # Sector breakdown
    sector_exposure = active_projects_df.groupby("sector")["baseline_cost"].sum().to_dict()
"""

pattern = r'    active_projects_df\["latest_risk"\].*?sector_exposure = active_projects_df.groupby\("sector"\)\["C_base"\].sum\(\).to_dict\(\)'
content = re.sub(pattern, new_code.strip(), content, flags=re.DOTALL)

with open("scripts/precompute_portfolio.py", "w") as f:
    f.write(content)
