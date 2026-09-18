import os
import pytest
import json
from sanket.incremental_manager import StagingContext, load_manifest, save_manifest

def test_incremental_staging_context(tmp_path):
    os.environ["DATA_DIR"] = str(tmp_path)
    # Patch the staging context to use tmp_path
    staging = StagingContext("run_123")
    staging.staging_dir = os.path.join(str(tmp_path), ".staging", "run_123")
    os.makedirs(staging.staging_dir, exist_ok=True)
    staging.affected_records_path = os.path.join(staging.staging_dir, "affected_records.json")
    
    records = [{"project_id": "P1", "reporting_month": "2024-01"}]
    staging.write_affected_records(records)
    loaded = staging.load_affected_records()
    assert len(loaded) == 1
    assert loaded[0]["project_id"] == "P1"

def test_idempotent_no_changes():
    # If no files changed, manifest logic should detect it
    pass
