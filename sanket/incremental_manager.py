import os
import json
import hashlib
from typing import Dict, List, Any, Optional

MANIFEST_PATH = "DATA/ingestion_manifest.json"

def get_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_manifest() -> Dict[str, Any]:
    """Load the ingestion manifest."""
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}

def save_manifest(manifest: Dict[str, Any]):
    """Save the ingestion manifest."""
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

class StagingContext:
    """Manages the staging directory for an incremental run."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.staging_dir = os.path.join("DATA", ".staging", self.run_id)
        os.makedirs(self.staging_dir, exist_ok=True)
        self.affected_records_path = os.path.join(self.staging_dir, "affected_records.json")
    
    def get_path(self, filename: str) -> str:
        """Get the path to a file within the staging directory."""
        return os.path.join(self.staging_dir, filename)

    def write_affected_records(self, records: List[Dict[str, Any]]):
        """Write the raw extracted records that changed."""
        with open(self.affected_records_path, "w") as f:
            json.dump(records, f)

    def load_affected_records(self) -> List[Dict[str, Any]]:
        """Load the raw extracted records that changed."""
        if not os.path.exists(self.affected_records_path):
            return []
        with open(self.affected_records_path, "r") as f:
            return json.load(f)

    def write_json(self, filename: str, data: Any):
        """Write generic JSON to staging."""
        with open(self.get_path(filename), "w") as f:
            json.dump(data, f)
            
    def load_json(self, filename: str) -> Any:
        """Load generic JSON from staging."""
        path = self.get_path(filename)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)
