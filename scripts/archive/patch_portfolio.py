import json
import os
import pandas as pd
import numpy as np

def patch():
    with open("sanket/portfolio.py", "r") as f:
        content = f.read()

    # We need to rewrite `SanitizedPortfolio._load_and_sanitize`
    # and `SanitizedPortfolio.__init__` maybe.
    
    # It currently says:
    #     def _load_and_sanitize(self):
    #         actual_dataset_path = get_artifact(self.dataset_path)
    
    # We will replace _load_and_sanitize entirely.
    
    import re
    # Find start and end of _load_and_sanitize
    match = re.search(r'    def _load_and_sanitize\(self\):.*?(?=    def get_summary_dict\(self\) -> Dict\[str, Any\]:)', content, re.DOTALL)
    if not match:
        print("Could not find _load_and_sanitize")
        return
        
    old_method = match.group(0)
    
    new_method = """    def _load_and_sanitize(self):
        metrics_path = get_artifact("DATA/portfolio_metrics.json")
        active_path = get_artifact("DATA/portfolio_active.parquet")
        hist_path = get_artifact("DATA/portfolio_historical.parquet")
        gen_path = get_artifact("DATA/portfolio_genuine.parquet")
        
        # Load precomputed static artifacts
        if not os.path.exists(metrics_path):
            raise FileNotFoundError(f"Portfolio metrics cache '{metrics_path}' missing. Please run scripts/precompute_portfolio.py")
            
        with open(metrics_path, "r") as f:
            data = json.load(f)
            
        # Validation: Internally consistent schema
        meta = data.get("_metadata", {})
        if "source_dataset_hash" not in meta or "schema_version" not in meta:
            raise ValueError("Invalid portfolio_metrics.json: missing required artifact metadata.")
            
        metrics = data.get("metrics", {})
        
        # Load dataframes
        self.active_projects_df = pd.read_parquet(active_path)
        self.historical_projects_df = pd.read_parquet(hist_path)
        self.genuine_projects_df = pd.read_parquet(gen_path)
        
        # Validation: Ensure row counts match JSON
        if len(self.active_projects_df) != metrics.get("active_project_count"):
            raise ValueError("Artifact corruption: active_projects_df row count does not match metrics.")
        
        # Restore scalar metrics
        for k, v in metrics.items():
            setattr(self, k, v)
            
        # Preserve backwards compatibility for tests/callers that expect `portfolio.engine`.
        # However, we do not load it eagerly. We use a property to load it lazily if accessed.
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from sanket.inference import load_inference_engine
            self._engine = load_inference_engine()
        return self._engine

"""
    new_content = content.replace(old_method, new_method)
    
    with open("sanket/portfolio.py", "w") as f:
        f.write(new_content)
    print("Patched sanket/portfolio.py")

if __name__ == "__main__":
    patch()
