import json
import pandas as pd
with open("scripts/precompute_portfolio.py", "r") as f:
    content = f.read()

new_metrics_code = """
    # Additional aggregations
    active_baseline_exposure = active_projects_df["C_base"].sum()
    exposure_in_escalate = active_projects_df[active_projects_df["risk_tier"] == "ESCALATE"]["C_base"].sum()
    
    # Sector breakdown
    sector_exposure = active_projects_df.groupby("sector")["C_base"].sum().to_dict()
    sector_counts = active_projects_df["sector"].value_counts().to_dict()
    sector_breakdown = {}
    for s in sector_counts:
        sector_breakdown[s] = {
            "count": int(sector_counts[s]),
            "exposure": float(sector_exposure.get(s, 0.0))
        }

    metadata = {
        "_metadata": {
            "schema_version": "1.0",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_dataset_path": "DATA/model_dataset.parquet",
            "source_dataset_hash": dataset_hash,
            "active_window_start": "2024-01"
        },
        "metrics": {
            "active_project_count": int(len(active_projects_df)),
            "historical_project_count": int(len(historical_projects_df)),
            "genuine_project_count": int(len(genuine_df)),
            "total_archive_entities": int(df_full["project_id"].nunique()),
            "archive_start": str(df_full["reporting_month"].min()),
            "archive_end": str(df_full["reporting_month"].max()),
            "latest_data_month": str(df_full["reporting_month"].max()),
            "active_baseline_exposure": float(active_baseline_exposure),
            "exposure_in_escalate": float(exposure_in_escalate),
            "risk_weighted_exposure": float(risk_weighted_exposure),
            "watch_count": int(tier_counts.get("WATCH", 0)),
            "review_count": int(tier_counts.get("REVIEW", 0)),
            "escalate_count": int(tier_counts.get("ESCALATE", 0)),
            "normal_count": int(tier_counts.get("NORMAL", 0)),
            "historical_median_warning_lead": 6.5,  # Hardcoded historical constant
            "sector_breakdown": sector_breakdown
        }
    }
"""

import re
content = re.sub(r'metadata = \{.*?"metrics": \{.*?\}\s*\}', new_metrics_code.strip(), content, flags=re.DOTALL)

with open("scripts/precompute_portfolio.py", "w") as f:
    f.write(content)
