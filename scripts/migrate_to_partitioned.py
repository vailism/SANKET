#!/usr/bin/env python3
"""
scripts/migrate_to_partitioned.py
Converts monolithic Parquet files to Hive-partitioned datasets.
Generates `project_index.parquet`.
"""

import os
import shutil
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from datetime import datetime

DATA_DIR = "DATA"
DATASETS_DIR = os.path.join(DATA_DIR, "datasets")
VERSION = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
VERSION_DIR = os.path.join(DATASETS_DIR, VERSION)
LATEST_LINK = os.path.join(DATASETS_DIR, "LATEST")

def setup_directories():
    os.makedirs(VERSION_DIR, exist_ok=True)
    print(f"Created version directory: {VERSION_DIR}")

def migrate_project_index():
    print("Generating project_index.parquet...")
    # Load model_dataset to extract all unique project_id, sector_clean, reporting_year combinations
    df = pd.read_parquet(os.path.join(DATA_DIR, "model_dataset.parquet"), columns=["project_id", "sector_clean", "reporting_month"])
    df["reporting_year"] = df["reporting_month"].str[:4]
    
    # Fill missing sectors just in case
    df["sector_clean"] = df["sector_clean"].fillna("OTHER")
    df["sector_clean"] = df["sector_clean"].replace({"": "OTHER", "nan": "OTHER"})
    
    index_df = df[["project_id", "sector_clean", "reporting_year"]].drop_duplicates().reset_index(drop=True)
    
    out_path = os.path.join(VERSION_DIR, "project_index.parquet")
    index_df.to_parquet(out_path, index=False, engine="pyarrow")
    print(f"Generated project_index.parquet with {len(index_df)} partition mappings.")
    return index_df

def migrate_temporal_dataset(name: str, index_df: pd.DataFrame):
    src_path = os.path.join(DATA_DIR, f"{name}.parquet")
    if not os.path.exists(src_path):
        print(f"Skipping {name}: file not found.")
        return
        
    print(f"Migrating {name}...")
    df = pd.read_parquet(src_path)
    
    # Ensure reporting_year exists
    if "reporting_month" in df.columns and "reporting_year" not in df.columns:
        df["reporting_year"] = df["reporting_month"].str[:4]
        
    # Ensure sector_clean exists
    if "sector_clean" not in df.columns:
        if name == "project_targets":
            # Target dataset doesn't have sector_clean, join it from index
            # But the index has year-level sector, and target has reporting_month
            # We can map by project_id and reporting_year
            unique_index = index_df.drop_duplicates(["project_id", "reporting_year"])
            df = df.merge(unique_index, on=["project_id", "reporting_year"], how="left")
            df["sector_clean"] = df["sector_clean"].fillna("OTHER")
        else:
            df["sector_clean"] = "OTHER"
            
    df["sector_clean"] = df["sector_clean"].fillna("OTHER").replace({"": "OTHER", "nan": "OTHER"})
    
    table = pa.Table.from_pandas(df)
    schema = pa.schema([
        ("sector_clean", pa.string()),
        ("reporting_year", pa.string())
    ])
    part = ds.partitioning(schema=schema, flavor="hive")
    
    out_dir = os.path.join(VERSION_DIR, name)
    os.makedirs(out_dir, exist_ok=True)
    
    ds.write_dataset(
        data=table,
        base_dir=out_dir,
        format="parquet",
        partitioning=part,
        existing_data_behavior="overwrite_or_ignore"
    )
    print(f"Migrated {name} to {out_dir}")

def migrate_portfolio_dataset(name: str, index_df: pd.DataFrame):
    src_path = os.path.join(DATA_DIR, f"{name}.parquet")
    if not os.path.exists(src_path):
        print(f"Skipping {name}: file not found.")
        return
        
    print(f"Migrating {name}...")
    df = pd.read_parquet(src_path)
    
    # Portfolio doesn't have reporting_year (it represents the latest state).
    # We partition portfolio ONLY by sector_clean.
    if "sector_clean" not in df.columns:
        if "sector_display" in df.columns:
            df["sector_clean"] = df["sector_display"]
        else:
            # Map from index (latest year's sector)
            latest_sectors = index_df.sort_values("reporting_year", ascending=False).drop_duplicates("project_id")
            df = df.merge(latest_sectors[["project_id", "sector_clean"]], on="project_id", how="left")
            
    df["sector_clean"] = df["sector_clean"].fillna("OTHER").replace({"": "OTHER", "nan": "OTHER"})
    
    table = pa.Table.from_pandas(df)
    schema = pa.schema([
        ("sector_clean", pa.string())
    ])
    part = ds.partitioning(schema=schema, flavor="hive")
    
    out_dir = os.path.join(VERSION_DIR, name)
    os.makedirs(out_dir, exist_ok=True)
    
    ds.write_dataset(
        data=table,
        base_dir=out_dir,
        format="parquet",
        partitioning=part,
        existing_data_behavior="overwrite_or_ignore"
    )
    print(f"Migrated {name} to {out_dir}")

def publish_latest():
    # Write manifest.json
    manifest_path = os.path.join(VERSION_DIR, "manifest.json")
    import json
    with open(manifest_path, "w") as f:
        json.dump({"version": VERSION, "timestamp": datetime.utcnow().isoformat()}, f)
        
    # Atomically link LATEST
    # We use a temporary link and rename for atomic behavior
    tmp_link = os.path.join(DATASETS_DIR, "LATEST_tmp")
    if os.path.islink(tmp_link):
        os.unlink(tmp_link)
    os.symlink(VERSION, tmp_link)
    os.rename(tmp_link, LATEST_LINK)
    print(f"Published LATEST -> {VERSION}")

def main():
    setup_directories()
    index_df = migrate_project_index()
    
    temporal_datasets = ["project_timelines", "project_trajectories", "project_targets", "model_dataset"]
    for d in temporal_datasets:
        migrate_temporal_dataset(d, index_df)
        
    portfolio_datasets = ["portfolio_genuine", "portfolio_active", "portfolio_historical"]
    for d in portfolio_datasets:
        migrate_portfolio_dataset(d, index_df)
        
    publish_latest()

if __name__ == "__main__":
    main()
