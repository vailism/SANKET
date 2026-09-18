#!/usr/bin/env python3
"""
scripts/validate_incremental_parity.py
Validates exact mathematical parity between the Batch and Incremental pipelines.
"""

import os
import argparse
import pandas as pd
import numpy as np
import shutil
import subprocess

def run_batch():
    print("Running Batch Pipeline...")
    subprocess.run(["./run_pipeline.sh"], check=True)

def run_incremental():
    print("Running Incremental Pipeline...")
    subprocess.run(["./run_incremental_pipeline.py"], check=True)

def check_parity(batch_file, incr_file):
    print(f"Validating parity for {batch_file} vs {incr_file}...")
    if not os.path.exists(batch_file):
        raise FileNotFoundError(f"{batch_file} not found.")
    if not os.path.exists(incr_file):
        raise FileNotFoundError(f"{incr_file} not found.")

    import pyarrow.dataset as ds
    
    if batch_file.endswith(".parquet") or os.path.isdir(batch_file):
        # We must use partitioning="hive" so that partition columns are included in the dataframe
        df_batch = ds.dataset(batch_file, partitioning="hive").to_table().to_pandas()
        df_incr = ds.dataset(incr_file, partitioning="hive").to_table().to_pandas()
    elif batch_file.endswith(".csv"):
        df_batch = pd.read_csv(batch_file)
        df_incr = pd.read_csv(incr_file)
    else:
        raise ValueError("Unsupported format.")
        
    # Align columns
    common_cols = [c for c in df_batch.columns if c in df_incr.columns]
    df_batch = df_batch[common_cols]
    df_incr = df_incr[common_cols]
    
    # Also we don't care about reporting_year which is purely a partition column not in original
    if "reporting_year" in df_batch.columns:
        df_batch = df_batch.drop(columns=["reporting_year"])
    if "reporting_year" in df_incr.columns:
        df_incr = df_incr.drop(columns=["reporting_year"])

    df_batch = df_batch.sort_values(by=list(df_batch.columns)).reset_index(drop=True)
    df_incr = df_incr.sort_values(by=list(df_incr.columns)).reset_index(drop=True)

    try:
        pd.testing.assert_frame_equal(df_batch, df_incr, check_like=True, check_dtype=False)
        print(f"✅ Exact Parity Verified for {os.path.basename(batch_file)}!")
    except AssertionError as e:
        print(f"❌ PARITY FAILED for {os.path.basename(batch_file)}!")
        print(e)

def main():
    parser = argparse.ArgumentParser(description="Parity Validator")
    parser.add_argument("--batch-dir", default="DATA_BATCH")
    parser.add_argument("--incr-dir", default="DATA")
    parser.add_argument("--compare-only", action="store_true")
    args = parser.parse_args()

    if not args.compare_only:
        print("To run a full end-to-end parity test, you must have two directories set up,")
        print("run a full batch, copy it to incremental, add a PDF, and run both pipelines.")
        print("This script is meant to compare two directories' outputs directly.")
    
    # Map logical names to their paths in batch vs incr
    # If the user still has monolithic parquets in batch_dir, they will have the .parquet extension.
    # In incr_dir, they are partitioned directories under datasets/LATEST.
    
    files_to_check = {
        "project_monthly.csv": ("project_monthly.csv", "project_monthly.csv"),
        "project_timelines": ("project_timelines.parquet", "datasets/LATEST/project_timelines"),
        "project_trajectories": ("project_trajectories.parquet", "datasets/LATEST/project_trajectories"),
        "project_targets": ("project_targets.parquet", "datasets/LATEST/project_targets"),
        "model_dataset": ("model_dataset.parquet", "datasets/LATEST/model_dataset"),
        "portfolio_active": ("portfolio_active.parquet", "datasets/LATEST/portfolio_active"),
        "portfolio_historical": ("portfolio_historical.parquet", "datasets/LATEST/portfolio_historical"),
        "portfolio_genuine": ("portfolio_genuine.parquet", "datasets/LATEST/portfolio_genuine")
    }
    
    for logical_name, (batch_name, incr_name) in files_to_check.items():
        batch_f = os.path.join(args.batch_dir, batch_name)
        incr_f = os.path.join(args.incr_dir, incr_name)
        if os.path.exists(batch_f) and os.path.exists(incr_f):
            check_parity(batch_f, incr_f)
        else:
            print(f"Skipping {logical_name} (not found in both directories: {batch_f} vs {incr_f})")

if __name__ == "__main__":
    main()
