#!/usr/bin/env python3
"""
run_incremental_pipeline.py

The atomic orchestrator for True Incremental Ingestion using Partitioned Datasets.
Runs all incremental stages sequentially. If successful, atomically publishes
the new dataset version via a `LATEST` symlink switch.
"""

import os
import sys
import time
import subprocess
import shutil
import json
from datetime import datetime

DATA_DIR = "DATA"
DATASETS_DIR = os.path.join(DATA_DIR, "datasets")
LATEST_LINK = os.path.join(DATASETS_DIR, "LATEST")

def run_step(name: str, cmd: list):
    print(f"\n{'='*80}")
    print(f"--- {name} ---")
    print(f"{'='*80}")
    t0 = time.time()
    
    # Enable PYTHONPATH to point to the project root
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(".")
    
    result = subprocess.run(cmd, env=env)
    
    if result.returncode != 0:
        print(f"\n[ERROR] Pipeline step '{name}' failed with code {result.returncode}.")
        sys.exit(result.returncode)
        
    dur = time.time() - t0
    print(f"[SUCCESS] {name} completed in {dur:.2f}s.\n")

def create_staging_version() -> str:
    """
    Creates a new version directory by hardlinking all unchanged partitions
    from the LATEST version. This ensures zero-copy clones for unchanged data.
    """
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    version_name = f"v{run_id}"
    version_dir = os.path.join(DATASETS_DIR, version_name)
    
    if os.path.exists(LATEST_LINK):
        real_latest = os.path.realpath(LATEST_LINK)
        print(f"Cloning {real_latest} to {version_dir} using hardlinks...")
        shutil.copytree(real_latest, version_dir, copy_function=os.link)
    else:
        print(f"No LATEST version found. Creating empty version dir {version_dir}...")
        os.makedirs(version_dir)
        
    return version_name, version_dir

def atomic_commit(version_name: str, version_dir: str):
    """Atomically commit the new version by switching the LATEST symlink."""
    print("--- ATOMIC PUBLICATION ---")
    
    # Write manifest.json
    manifest_path = os.path.join(version_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump({"version": version_name, "timestamp": datetime.utcnow().isoformat()}, f)
        
    # Copy ingestion_manifest.json from staging to DATA/ atomically if it exists
    staging_manifest = os.path.join("DATA", ".staging", version_name, "ingestion_manifest.json")
    if os.path.exists(staging_manifest):
        tmp_manifest = "DATA/ingestion_manifest.json.tmp"
        shutil.copy2(staging_manifest, tmp_manifest)
        os.rename(tmp_manifest, "DATA/ingestion_manifest.json")
        
    # Atomically link LATEST
    tmp_link = os.path.join(DATASETS_DIR, "LATEST_tmp")
    if os.path.islink(tmp_link):
        os.unlink(tmp_link)
    os.symlink(version_name, tmp_link)
    os.rename(tmp_link, LATEST_LINK)
    print(f"Published LATEST -> {version_name}")

def main():
    version_name, staging_dir = create_staging_version()
    print(f"VIGIL TRUE INCREMENTAL PIPELINE STARTED [VERSION: {version_name}]")
    
    # 1. Extraction (Find affected PDFs)
    # Note: extraction still places JSON state in a staging folder so downstream tasks know what to compute.
    extract_state_dir = os.path.join("DATA", ".staging", version_name)
    run_step(
        "1. Incremental PDF Extraction",
        [sys.executable, "scripts/extract_pdfs_incremental.py", "--run-id", version_name]
    )
    
    if os.path.exists(os.path.join(extract_state_dir, "NO_CHANGES")):
        print("Idempotent run detected. No PDFs changed. Removing unused version.")
        shutil.rmtree(staging_dir)
        sys.exit(0)
        
    # 2. Timeline
    run_step(
        "2. Incremental Timelines",
        [sys.executable, "sanket/timeline_incremental.py", "--run-id", version_name]
    )
    
    # 3. Trajectory
    run_step(
        "3. Incremental Trajectories",
        [sys.executable, "sanket/trajectory_incremental.py", "--run-id", version_name]
    )
    
    # 4. Targets
    run_step(
        "4. Incremental Targets",
        [sys.executable, "sanket/targets_incremental.py", "--run-id", version_name]
    )
    
    # 5. Features
    run_step(
        "5. Incremental Features",
        [sys.executable, "sanket/features_incremental.py", "--run-id", version_name]
    )
    
    # 6. Portfolio
    run_step(
        "6. Incremental Portfolio",
        [sys.executable, "scripts/precompute_portfolio_incremental.py", "--run-id", version_name]
    )
    
    # 7. Commit
    atomic_commit(version_name, staging_dir)
    
    print("--- ALL INCREMENTAL DATA PIPELINES COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    main()
