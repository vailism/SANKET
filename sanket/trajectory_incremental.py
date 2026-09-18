#!/usr/bin/env python3
"""
sanket/trajectory_incremental.py
Incrementally updates trajectory features and component risk scores.
"""

import os
import argparse
import pandas as pd
import numpy as np
from typing import List, Tuple
from sanket.incremental_manager import StagingContext
from sanket.trajectory import compute_trajectories, load_config

def build_incremental_trajectories(staging: StagingContext, affected_pairs: List[Tuple[str, str]]):
    affected_pids = set(p[0] for p in affected_pairs)
    
    print(f"Incrementally updating trajectories for {len(affected_pids)} directly affected projects...")
    
    from sanket.dataset import DatasetReader
    
    # We read from the staging version, which already has the updated timelines from step 2
    staging_dataset_dir = os.path.join("DATA", "datasets", staging.run_id)
    reader = DatasetReader(staging_dataset_dir)
    
    # 1. Identify affected sectors
    index_df = reader.index
    affected_sectors_df = index_df[index_df["project_id"].isin(affected_pids)]
    affected_sectors = affected_sectors_df["sector_clean"].unique().tolist()
    
    if not affected_sectors:
        print("No sectors affected (or projects missing from index). Exiting.")
        return
        
    print(f"Affected sectors requiring trajectory recomputation: {affected_sectors}")
    
    # 2. Read FULL timelines for the affected sectors.
    # This guarantees that peer statistics are computed correctly across the entire sector,
    # and chronological EWMA propagates correctly for all projects in the sector.
    df_sector_timelines = reader.read_partitions("project_timelines", filters={"sector_clean": affected_sectors})
    
    # 3. Compute global peer stats FOR THESE SECTORS
    # We can just compute peer stats natively inside compute_trajectories if we pass the whole sector dataframe.
    staging_dataset_dir = os.path.join("DATA", "datasets", staging.run_id)
    union_pids = []
    
    for sector in affected_sectors:
        # Read only ONE sector's timeline
        df_sector_timeline = reader.read_partitions("project_timelines", filters={"sector_clean": [sector]})
        
        if df_sector_timeline.empty:
            continue
            
        # Compute trajectory for this sector
        df_sector_traj = compute_trajectories(df_sector_timeline, config=load_config(), peer_stats=None)
        
        # Merge partition columns if needed
        if "reporting_year" not in df_sector_traj.columns:
            df_sector_traj["reporting_year"] = df_sector_traj["reporting_month"].astype(str).str[:4]
        if "sector_clean" not in df_sector_traj.columns:
            latest_sectors = index_df.sort_values("reporting_year", ascending=False).drop_duplicates("project_id")
            df_sector_traj = df_sector_traj.merge(latest_sectors[["project_id", "sector_clean"]], on="project_id", how="left")
            df_sector_traj["sector_clean"] = df_sector_traj["sector_clean"].fillna("OTHER").replace({"": "OTHER", "nan": "OTHER"})
            
        df_affected = df_sector_traj
        affected_partitions = df_affected[df_affected["project_id"].isin(affected_pids)][["sector_clean", "reporting_year"]].drop_duplicates().to_dict("records")
    
        if len(affected_partitions) > 0:
            for part in affected_partitions:
                s_clean, r_year = part["sector_clean"], part["reporting_year"]
                
                filter_dict = {"sector_clean": [s_clean], "reporting_year": [r_year]}
                df_existing_part = reader.read_partitions("project_trajectories", filters=filter_dict)
                
                df_affected_part = df_affected[(df_affected["sector_clean"] == s_clean) & (df_affected["reporting_year"] == r_year)]
                df_affected_part = df_affected_part[df_affected_part["project_id"].isin(affected_pids)]
                
                if not df_existing_part.empty:
                    df_existing_part = df_existing_part[~df_existing_part["project_id"].isin(affected_pids)]
                    df_traj_part = pd.concat([df_existing_part, df_affected_part], ignore_index=True)
                else:
                    df_traj_part = df_affected_part
                    
                df_traj_part = df_traj_part.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)
                
                reader.write_partitions(
                    name="project_trajectories", 
                    df=df_traj_part, 
                    partition_cols=["sector_clean", "reporting_year"],
                    base_dir=os.path.join(staging_dataset_dir, "project_trajectories")
                )
        
        union_pids.extend(df_sector_traj["project_id"].unique().tolist())
    
    print(f"Updated trajectories for affected sectors.")
    staging.write_json("union_pids.json", union_pids)


def main():
    parser = argparse.ArgumentParser(description="Incremental Trajectory Builder")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    staging = StagingContext(args.run_id)
    affected_pairs = staging.load_json("affected_pairs.json") or []
    
    if not affected_pairs:
        print("No affected pairs found. Exiting.")
        return

    build_incremental_trajectories(staging, affected_pairs)

if __name__ == "__main__":
    main()
    import os
    os._exit(0)
