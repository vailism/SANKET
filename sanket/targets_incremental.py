#!/usr/bin/env python3
"""
sanket/targets_incremental.py
Incrementally updates right-censored targets for affected projects.
"""

import os
import argparse
import pandas as pd
from typing import List, Tuple
from sanket.incremental_manager import StagingContext
from sanket.targets import compute_targets

def build_incremental_targets(staging: StagingContext, affected_pairs: List[Tuple[str, str]]):
    affected_pids = set(p[0] for p in affected_pairs)
    
    print(f"Incrementally updating targets for {len(affected_pids)} directly affected projects...")
    
    from sanket.dataset import DatasetReader
    staging_dataset_dir = os.path.join("DATA", "datasets", staging.run_id)
    reader = DatasetReader(staging_dataset_dir)
    
    # Identify affected sectors and years for the DIRECTLY affected pids
    index_df = reader.index
    affected_sectors_df = index_df[index_df["project_id"].isin(affected_pids)]
    
    if affected_sectors_df.empty:
        print("No affected projects found in index. Exiting.")
        return
        
    # Find unique partitions affected
    affected_partitions = affected_sectors_df[["sector_clean", "reporting_year"]].drop_duplicates().to_dict('records')
    
    for part in affected_partitions:
        s_clean, r_year = part["sector_clean"], part["reporting_year"]
        filter_part = {"sector_clean": [s_clean], "reporting_year": [r_year]}
        
        # 1. Read the newly updated timelines FOR ONLY THIS AFFECTED PARTITION
        df_timelines_part = reader.read_partitions("project_timelines", filters=filter_part)
        
        # Slice timelines for JUST the directly affected_pids
        df_affected = df_timelines_part[df_timelines_part["project_id"].isin(affected_pids)].copy()
        
        if df_affected.empty:
            continue
            
        # Compute targets for affected projects
        df_affected_targets = compute_targets(df_affected)
        
        # Join partition columns if missing
        if "reporting_year" not in df_affected_targets.columns:
            df_affected_targets["reporting_year"] = df_affected_targets["reporting_month"].astype(str).str[:4]
        if "sector_clean" not in df_affected_targets.columns:
            latest_sectors = index_df.sort_values("reporting_year", ascending=False).drop_duplicates("project_id")
            df_affected_targets = df_affected_targets.merge(latest_sectors[["project_id", "sector_clean"]], on="project_id", how="left")
            df_affected_targets["sector_clean"] = df_affected_targets["sector_clean"].fillna("OTHER").replace({"": "OTHER", "nan": "OTHER"})
        
        # 2. Write ONLY the affected partition back to staging
        df_existing_part = reader.read_partitions("project_targets", filters=filter_part)
        df_affected_part = df_affected_targets[(df_affected_targets["sector_clean"] == s_clean) & (df_affected_targets["reporting_year"] == r_year)]
        df_affected_part = df_affected_part[df_affected_part["project_id"].isin(affected_pids)]
        
        if not df_existing_part.empty:
            df_existing_part = df_existing_part[~df_existing_part["project_id"].isin(affected_pids)]
            df_targets_part = pd.concat([df_existing_part, df_affected_part], ignore_index=True)
        else:
            df_targets_part = df_affected_part
            
        df_targets_part = df_targets_part.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)
        
        reader.write_partitions(
            name="project_targets",
            df=df_targets_part,
            partition_cols=["sector_clean", "reporting_year"],
            base_dir=os.path.join(staging_dataset_dir, "project_targets")
        )
    print(f"Incrementally updated targets for {len(affected_partitions)} partitions.")

def main():
    parser = argparse.ArgumentParser(description="Incremental Target Builder")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    staging = StagingContext(args.run_id)
    affected_pairs = staging.load_json("affected_pairs.json") or []
    
    if not affected_pairs:
        print("No affected pairs found. Exiting.")
        return

    build_incremental_targets(staging, affected_pairs)

if __name__ == "__main__":
    main()
    import os
    os._exit(0)
