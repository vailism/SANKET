#!/usr/bin/env python3
"""
sanket/features_incremental.py
Incrementally updates the model dataset.
"""

import os
import argparse
import pandas as pd
from typing import List, Tuple
from sanket.incremental_manager import StagingContext
from sanket.features import assemble_model_dataset

def build_incremental_features(staging: StagingContext, affected_pairs: List[Tuple[str, str]]):
    affected_pids = set(p[0] for p in affected_pairs)
    
    from sanket.dataset import DatasetReader
    staging_dataset_dir = os.path.join("DATA", "datasets", staging.run_id)
    reader = DatasetReader(staging_dataset_dir)
    
    # 1. Identify affected sectors from index
    index_df = reader.index
    affected_sectors_df = index_df[index_df["project_id"].isin(affected_pids)]
    affected_sectors = affected_sectors_df["sector_clean"].unique().tolist()
    
    if not affected_sectors:
        print("No sectors affected. Exiting.")
        return
        
    print(f"Incrementally updating model dataset for {len(affected_sectors)} affected sectors: {affected_sectors}")
    
    for sector in affected_sectors:
        df_traj_affected = reader.read_partitions("project_trajectories", filters={"sector_clean": [sector]})
        df_targets_affected = reader.read_partitions("project_targets", filters={"sector_clean": [sector]})
        
        if df_traj_affected.empty or df_targets_affected.empty:
            continue
            
        merged_affected = pd.merge(
            df_traj_affected,
            df_targets_affected,
            on=["project_id", "reporting_month"],
            how="inner"
        )
        
        merged_affected["feature_cutoff_month"] = merged_affected["reporting_month"]
        
        def _add_months_vectorized(series, months):
            s = series.astype(str).str.strip().replace("nan", "")
            parts = s.str.split("-", expand=True)
            if parts.shape[1] >= 2:
                y = pd.to_numeric(parts[0], errors="coerce")
                m = pd.to_numeric(parts[1], errors="coerce")
                total_m = y * 12 + (m - 1) + months
                new_y = total_m // 12
                new_m = total_m % 12 + 1
                return new_y.map(lambda x: f"{int(x):04d}" if pd.notna(x) else "") + "-" + new_m.map(lambda x: f"{int(x):02d}" if pd.notna(x) else "")
            return pd.Series("", index=series.index)
    
        merged_affected["target_horizon_month_6m"] = _add_months_vectorized(merged_affected["reporting_month"], 6).replace("-", "")
        merged_affected["target_horizon_month_12m"] = _add_months_vectorized(merged_affected["reporting_month"], 12).replace("-", "")
    
        # Clean up columns and merge back partition columns
        if "sector_clean_x" in merged_affected.columns:
            merged_affected["sector_clean"] = merged_affected["sector_clean_x"]
            merged_affected.drop(columns=[c for c in merged_affected.columns if c.startswith("sector_clean_")], inplace=True)
        if "reporting_year_x" in merged_affected.columns:
            merged_affected["reporting_year"] = merged_affected["reporting_year_x"]
            merged_affected.drop(columns=[c for c in merged_affected.columns if c.startswith("reporting_year_")], inplace=True)
            
        if "reporting_year" not in merged_affected.columns:
            merged_affected["reporting_year"] = merged_affected["reporting_month"].astype(str).str[:4]
        
        merged_affected = merged_affected.sort_values(by=["project_id", "reporting_month"], ascending=[True, True]).reset_index(drop=True)
        
        # 4. Write ONLY these recomputed sector partitions back to staging
        reader.write_partitions(
            name="model_dataset",
            df=merged_affected,
            partition_cols=["sector_clean", "reporting_year"],
            base_dir=os.path.join(staging_dataset_dir, "model_dataset")
        )
    print(f"Updated model dataset partitions for {len(affected_sectors)} sectors.")

def main():
    parser = argparse.ArgumentParser(description="Incremental Features Builder")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    staging = StagingContext(args.run_id)
    affected_pairs = staging.load_json("affected_pairs.json") or []
    
    if not affected_pairs:
        print("No affected pairs found. Exiting.")
        return

    build_incremental_features(staging, affected_pairs)

if __name__ == "__main__":
    main()
    import os
    os._exit(0)
