#!/usr/bin/env python3
"""
scripts/extract_pdfs_incremental.py
Wrapper around extract_pdfs to implement True Incremental Extraction based on content hashes.
"""

import os
import sys
import argparse
import time
import concurrent.futures
from typing import List, Dict, Any

from sanket.incremental_manager import get_file_hash, load_manifest, save_manifest, StagingContext
from scripts.extract_pdfs import worker_process_pdf

def main():
    parser = argparse.ArgumentParser(description="Incremental PDF Extraction Wrapper")
    parser.add_argument("--input", "-i", default="DATA(RAW) ", help="Path to raw PDF folder")
    parser.add_argument("--output", "-o", default="DATA", help="Path to output folder")
    parser.add_argument("--run-id", required=True, help="Incremental run identifier")
    args = parser.parse_args()

    input_dir = args.input
    staging = StagingContext(args.run_id)
    manifest = load_manifest()

    pdf_files = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")])
    
    changed_files = []
    current_hashes = {}

    print("=" * 90)
    print("VIGIL INCREMENTAL PIPELINE: CONTENT ADDRESSING")
    print("=" * 90)
    print(f"Scanning {len(pdf_files)} PDFs in {input_dir}...")
    
    existing_hashes = set(record.get("hash") for record in manifest.values() if record.get("hash"))
    
    for f in pdf_files:
        filepath = os.path.join(input_dir, f)
        file_hash = get_file_hash(filepath)
        current_hashes[f] = file_hash
        
        manifest_record = manifest.get(f)
        if not manifest_record or manifest_record.get("hash") != file_hash:
            # Check if this exact content already exists under a different filename
            if file_hash in existing_hashes:
                print(f"Skipping {f}: Identical content already exists in manifest.")
                # Add to manifest so we don't check it again next time
                manifest[f] = {
                    "filename": f,
                    "hash": file_hash,
                    "status": "DUPLICATE",
                    "timestamp": time.time(),
                    "projects_detected": 0
                }
                continue
                
            changed_files.append(f)

    if not changed_files:
        print("No new or changed documents detected. System is idempotent.")
        # Touch a NO_CHANGES marker
        with open(staging.get_path("NO_CHANGES"), "w") as f:
            f.write("")
        return

    print(f"Detected {len(changed_files)} new or changed PDFs.")
    
    # Process only changed files
    file_tasks = [(idx, f, os.path.join(input_dir, f)) for idx, f in enumerate(changed_files, 1)]
    max_workers = min(7, os.cpu_count() or 4)
    
    all_monthly_records: List[Dict[str, Any]] = []
    completed = 0
    
    print("-" * 90)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(worker_process_pdf, t): t[1] for t in file_tasks}
        for future in concurrent.futures.as_completed(future_to_file):
            completed += 1
            try:
                idx, f, records, quality, errors, duration = future.result()
                all_monthly_records.extend(records)
                print(f"[{completed:03d}/{len(changed_files):03d}] {f[:32]:<32} | {quality['extraction_status']:<22} | {quality['projects_detected']:<5} records | {duration:.1f}s", flush=True)
                
                # Update manifest entry
                manifest[f] = {
                    "filename": f,
                    "hash": current_hashes[f],
                    "status": quality["extraction_status"],
                    "timestamp": time.time(),
                    "projects_detected": quality["projects_detected"]
                }
            except Exception as exc:
                fname = future_to_file[future]
                print(f"[{completed:03d}/{len(changed_files):03d}] {fname[:32]:<32} | ERROR: {exc}", flush=True)
                manifest[f] = {
                    "filename": f,
                    "hash": current_hashes[f],
                    "status": "ERROR",
                    "timestamp": time.time(),
                    "projects_detected": 0
                }
                
    print("-" * 90)
    
    # Identify affected (project_id, reporting_month) pairs
    affected_pairs = set()
    for r in all_monthly_records:
        pid = str(r.get("project_id", "") or "").strip()
        month = str(r.get("reporting_month", "") or "").strip()
        if pid and pid != "UNKNOWN" and month and month != "UNKNOWN":
            affected_pairs.add((pid, month))
            
    # Write affected records to staging
    staging.write_affected_records(all_monthly_records)
    
    # Write manifest update to staging (to be committed later atomically)
    staging.write_json("ingestion_manifest.json", manifest)
    
    # Also save the affected pairs specifically for easy loading
    staging.write_json("affected_pairs.json", list(affected_pairs))
    
    # Run Canonical Deduplication Incrementally
    from sanket.canonical_incremental import update_canonical_dataset
    update_canonical_dataset(staging, list(affected_pairs), all_monthly_records)
    
    print(f"Incremental Extraction Complete: {len(all_monthly_records)} raw records extracted.")
    print(f"Identified {len(affected_pairs)} affected (project, month) canonical pairs.")

if __name__ == "__main__":
    main()
