#!/usr/bin/env python3
"""
sanket/timeline_incremental.py
Incrementally updates project timelines.
"""

import os
import argparse
import pandas as pd
from typing import List, Tuple
from sanket.incremental_manager import StagingContext
from sanket.timeline import ym_to_month_index

def build_incremental_timelines(staging: StagingContext, affected_pairs: List[Tuple[str, str]]):
    """Recompute timelines only for projects that had observations added/changed/removed."""
    affected_pids = set(p[0] for p in affected_pairs)
    print(f"Incrementally updating timelines for {len(affected_pids)} affected projects...")

    # Load the updated canonical rows for these projects from the staging project_monthly.csv
    # To be memory efficient and strictly incremental in compute, we only process the affected pids.
    df_affected_chunks = []
    for chunk in pd.read_csv(staging.get_path("project_monthly.csv"), dtype=str, chunksize=10000):
        df_affected_chunks.append(chunk[chunk["project_id"].isin(affected_pids)])
    df_affected = pd.concat(df_affected_chunks, ignore_index=True) if df_affected_chunks else pd.DataFrame()
    
    # 2. Strict sorting by project_id and reporting_month
    df_affected["month_idx"] = ym_to_month_index(df_affected["reporting_month"])
    df_affected = df_affected.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)

    # 3. Vectorized temporal metadata computation for ONLY affected projects
    grouped = df_affected.groupby("project_id", sort=False)
    import numpy as np

    df_affected["observation_number"] = grouped.cumcount() + 1
    df_affected["prev_month_idx"] = grouped["month_idx"].shift(1)
    df_affected["months_since_previous_observation"] = df_affected["month_idx"] - df_affected["prev_month_idx"]

    df_affected["reporting_gap_flag"] = np.where(
        df_affected["months_since_previous_observation"].fillna(1) > 1, 1, 0
    ).astype(np.int32)

    first_month_idx = grouped["month_idx"].transform("first")
    df_affected["project_age_months"] = (df_affected["month_idx"] - first_month_idx).astype(np.int32)
    df_affected.drop(columns=["month_idx", "prev_month_idx"], inplace=True)

    df_affected["observation_number"] = df_affected["observation_number"].astype(np.int32)
    df_affected["months_since_previous_observation"] = df_affected["months_since_previous_observation"].astype(np.float64)

    numeric_cols = [
        "physical_progress", "financial_progress", "expenditure",
        "approved_cost", "revised_cost", "schedule_deviation"
    ]
    for col in numeric_cols:
        if col in df_affected.columns:
            df_affected[col] = pd.to_numeric(df_affected[col], errors="coerce")

    # Now we write only the affected sectors back to the partitioned dataset
    # We must ensure we have sector_clean and reporting_year columns to partition by!
    # df_affected may not have sector_clean if it wasn't in project_monthly.csv
    # Actually, projects.csv has sector. Let's merge sector_clean from project_index
    from sanket.dataset import DatasetReader
    reader = DatasetReader("DATA/datasets/LATEST") # Read from current index
    
    # Fast join for missing partition keys
    if "sector_clean" not in df_affected.columns:
        index_df = reader.index
        # Get latest sector mapping for each project
        latest_sectors = index_df.sort_values("reporting_year", ascending=False).drop_duplicates("project_id")
        df_affected = df_affected.merge(latest_sectors[["project_id", "sector_clean"]], on="project_id", how="left")
        df_affected["sector_clean"] = df_affected["sector_clean"].fillna("OTHER").replace({"": "OTHER", "nan": "OTHER"})
        
    df_affected["reporting_year"] = df_affected["reporting_month"].astype(str).str[:4]

    # Find unique partitions affected
    affected_partitions = df_affected[["sector_clean", "reporting_year"]].drop_duplicates().to_dict('records')
    
    # We must read the existing data for these affected partitions, drop the affected PIDs, merge, and overwrite the partitions.
    if len(affected_partitions) > 0:
        staging_dataset_dir = os.path.join("DATA", "datasets", staging.run_id)
        
        for part in affected_partitions:
            s_clean, r_year = part["sector_clean"], part["reporting_year"]
            
            filter_dict = {"sector_clean": [s_clean], "reporting_year": [r_year]}
            df_existing_part = reader.read_partitions("project_timelines", filters=filter_dict)
            
            df_affected_part = df_affected[(df_affected["sector_clean"] == s_clean) & (df_affected["reporting_year"] == r_year)]
            
            if not df_existing_part.empty:
                df_existing_part = df_existing_part[~df_existing_part["project_id"].isin(affected_pids)]
                df_timeline_part = pd.concat([df_existing_part, df_affected_part], ignore_index=True)
            else:
                df_timeline_part = df_affected_part
                
            df_timeline_part = df_timeline_part.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)
            
            reader.write_partitions(
                name="project_timelines", 
                df=df_timeline_part, 
                partition_cols=["sector_clean", "reporting_year"],
                base_dir=os.path.join(staging_dataset_dir, "project_timelines")
            )
        print(f"Incrementally updated {len(affected_partitions)} partitions.")


def main():
    parser = argparse.ArgumentParser(description="Incremental Timeline Builder")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    staging = StagingContext(args.run_id)
    affected_pairs = staging.load_json("affected_pairs.json") or []
    
    if not affected_pairs:
        print("No affected pairs found. Exiting.")
        return

    build_incremental_timelines(staging, affected_pairs)

if __name__ == "__main__":
    main()
    import os
    os._exit(0)
