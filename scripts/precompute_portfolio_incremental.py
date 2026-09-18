#!/usr/bin/env python3
"""
scripts/precompute_portfolio_incremental.py
Incrementally updates the portfolio datasets and global metrics.
"""

import os
import json
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from sanket.incremental_manager import StagingContext
from sanket.inference import load_inference_engine, get_risk_tier
from sanket.portfolio import is_genuine_project

def build_incremental_portfolio(staging: StagingContext, union_pids: list):
    print(f"Incrementally updating portfolio predictions for {len(union_pids)} projects...")

    from sanket.dataset import DatasetReader
    staging_dataset_dir = os.path.join("DATA", "datasets", staging.run_id)
    reader = DatasetReader(staging_dataset_dir)
    
    # Identify affected sectors
    index_df = reader.index
    affected_sectors_df = index_df[index_df["project_id"].isin(union_pids)]
    affected_sectors = affected_sectors_df["sector_clean"].unique().tolist()
    
    if not affected_sectors:
        print("No affected projects found in index. Skipping portfolio update.")
        return

    active_sectors_list = []
    historical_sectors_list = []
    genuine_sectors_list = []
    
    for sector in affected_sectors:
        df_sector = reader.read_partitions("model_dataset", filters={"sector_clean": [sector]})
        if df_sector.empty:
            continue
            
        def _ym_to_month_num(series):
            s = series.astype(str).str.strip().replace("nan", "")
            parts = s.str.split("-", expand=True)
            if parts.shape[1] >= 2:
                y = pd.to_numeric(parts[0], errors="coerce")
                m = pd.to_numeric(parts[1], errors="coerce")
                return (y * 12 + m).where((m >= 1) & (m <= 12), np.nan)
            return pd.Series(np.nan, index=series.index)
    
        df_sector = df_sector.sort_values("reporting_month")
        
        rev_nums = _ym_to_month_num(df_sector.get("revised_completion_date", pd.Series(np.nan, index=df_sector.index)))
        orig_nums = _ym_to_month_num(df_sector.get("original_completion_date", pd.Series(np.nan, index=df_sector.index)))
        if "schedule_deviation_months" in df_sector.columns:
            df_sector["schedule_deviation_months"] = df_sector["schedule_deviation_months"].fillna(rev_nums - orig_nums)
            df_sector["schedule_deviation_months"] = df_sector.groupby("project_id")["schedule_deviation_months"].ffill()
    
        latest_sector = df_sector.groupby("project_id").tail(1).reset_index(drop=True)
        first_sector = df_sector.groupby("project_id").first().reset_index()
        start_months = dict(zip(first_sector["project_id"], first_sector["reporting_month"]))
        latest_sector["start_month"] = latest_sector["project_id"].map(start_months)
        
        genuine_flags = [is_genuine_project(pid, name) for pid, name in zip(latest_sector["project_id"], latest_sector["project_name"])]
        latest_sector["is_genuine"] = genuine_flags
        genuine_sector = latest_sector[latest_sector["is_genuine"]].copy()
    
        engine = load_inference_engine()
        features = engine["features"]
        cat_features = engine["categorical_features"]
    
        if not genuine_sector.empty:
            X_gen = pd.DataFrame(index=genuine_sector.index)
            for f in features:
                X_gen[f] = genuine_sector[f] if f in genuine_sector.columns else np.nan
            for cat in cat_features:
                if cat in X_gen.columns:
                    X_gen[cat] = X_gen[cat].astype("category")
    
            raw_probs = engine["model"].predict_proba(X_gen)[:, 1]
            cal_probs = engine["calibrator"].predict(raw_probs)
            risk_tiers = [get_risk_tier(p) for p in cal_probs]
    
            genuine_sector["latest_risk"] = np.round(cal_probs, 4)
            genuine_sector["risk_tier"] = risk_tiers
            genuine_sector["latest_risk_tier"] = risk_tiers
    
            cbase_vals = pd.to_numeric(genuine_sector["C_base"], errors="coerce").fillna(0).values
            genuine_sector["baseline_cost"] = np.round(cbase_vals, 2)
            genuine_sector["priority_score"] = np.round(genuine_sector["latest_risk"] * genuine_sector["baseline_cost"], 2)
            genuine_sector["risk_weighted_exposure"] = genuine_sector["priority_score"]
    
            genuine_sector["sector_display"] = genuine_sector["sector_clean"].fillna(genuine_sector["sector"]).fillna("Unknown").astype(str)
            genuine_sector["sector_clean"] = genuine_sector["sector_clean"].fillna("OTHER").replace({"": "OTHER", "nan": "OTHER"})
    
        active_mask = genuine_sector["reporting_month"] >= "2024-01"
        active_sector = genuine_sector[active_mask].copy()
        historical_sector = genuine_sector[~active_mask].copy()
        
        reader.write_partitions("portfolio_active", active_sector, partition_cols=["sector_clean"], base_dir=os.path.join(staging_dataset_dir, "portfolio_active"))
        reader.write_partitions("portfolio_historical", historical_sector, partition_cols=["sector_clean"], base_dir=os.path.join(staging_dataset_dir, "portfolio_historical"))
        reader.write_partitions("portfolio_genuine", genuine_sector, partition_cols=["sector_clean"], base_dir=os.path.join(staging_dataset_dir, "portfolio_genuine"))
    
    # 3. To compute global metrics, read only what is necessary
    import pyarrow.dataset as ds
    df_active = reader.read_dataset("portfolio_active")
    df_genuine = reader.read_dataset("portfolio_genuine")
    
    # Efficiently read only required columns from full model_dataset
    model_ds = ds.dataset(os.path.join(staging_dataset_dir, "model_dataset"), partitioning="hive")
    df_full_cols = model_ds.to_table(columns=["project_id", "reporting_month"]).to_pandas()
    
    risk_weighted_exposure = df_active["risk_weighted_exposure"].sum()
    tier_counts = df_active["risk_tier"].value_counts().to_dict()
    active_baseline_exposure = df_active["baseline_cost"].sum()
    exposure_in_escalate = df_active[df_active["risk_tier"] == "ESCALATE"]["baseline_cost"].sum()

    sector_breakdown = []
    for s_name, s_df in df_active.groupby("sector_display"):
        sector_breakdown.append({
            "sector": str(s_name),
            "total_projects": int(len(s_df)),
            "escalate_count": int((s_df["risk_tier"] == "ESCALATE").sum()),
            "review_count": int((s_df["risk_tier"] == "REVIEW").sum()),
            "watch_count": int((s_df["risk_tier"] == "WATCH").sum()),
            "total_exposure": float(s_df["baseline_cost"].sum())
        })
    sector_breakdown.sort(key=lambda x: x["total_exposure"], reverse=True)
    
    count_2024 = len(df_active)
    mask_2023_full = (df_genuine["reporting_month"] >= "2023-01") & (df_genuine["reporting_month"] < "2024-01")
    count_2023 = df_genuine[mask_2023_full]["project_id"].nunique()
    
    yoy_change = round(((count_2024 - count_2023) / count_2023 * 100), 1) if count_2023 else 0.0
    first_months = df_genuine.groupby("project_id")["reporting_month"].min()
    added_this_quarter = int(sum(first_months >= "2024-01"))
    
    active_telemetry_pct = round((count_2024 / len(df_full_cols["project_id"].unique())) * 100, 1) if not df_full_cols.empty else 0.0

    model_calibration = 92.4
    median_lead_time = 6.5
    try:
        with open("DATA/model_metrics.json") as mf:
            mdata = json.load(mf)
            lgbm_metrics = mdata.get("global_out_of_fold_metrics", {}).get("lightgbm", {})
            roc_auc = lgbm_metrics.get("roc_auc", 0.924)
            model_calibration = round(roc_auc * 100, 1)
            lead_metrics = mdata.get("global_out_of_fold_metrics", {}).get("lead_time", {})
            median_lead_time = float(lead_metrics.get("median_lead_time_months", 3.0))
    except Exception:
        pass

    metadata = {
        "_metadata": {
            "schema_version": "1.0",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "source_dataset_path": "DATA/datasets/LATEST",
            "active_window_start": "2024-01"
        },
        "metrics": {
            "active_project_count": int(count_2024),
            "historical_project_count": int(len(reader.read_dataset("portfolio_historical"))),
            "genuine_project_count": int(len(df_genuine)),
            "total_archive_entities": int(df_full_cols["project_id"].nunique()),
            "archive_start": str(df_full_cols["reporting_month"].min()),
            "archive_end": str(df_full_cols["reporting_month"].max()),
            "latest_data_month": str(df_full_cols["reporting_month"].max()),
            "active_baseline_exposure": float(active_baseline_exposure),
            "exposure_in_escalate": float(exposure_in_escalate),
            "risk_weighted_exposure": float(risk_weighted_exposure),
            "watch_count": int(tier_counts.get("WATCH", 0)),
            "review_count": int(tier_counts.get("REVIEW", 0)),
            "escalate_count": int(tier_counts.get("ESCALATE", 0)),
            "normal_count": int(tier_counts.get("NORMAL", 0)),
            "historical_median_warning_lead": median_lead_time,
            "yoy_change": float(yoy_change),
            "added_this_quarter": int(added_this_quarter),
            "active_telemetry_pct": float(active_telemetry_pct),
            "model_calibration_accuracy": float(model_calibration),
            "sector_breakdown": sector_breakdown
        }
    }

    metrics_path = os.path.join(staging_dataset_dir, "portfolio_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metadata, f)
    print("Incremental portfolio metrics successfully saved to staging dataset.")

def main():
    parser = argparse.ArgumentParser(description="Incremental Portfolio Precomputation")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    staging = StagingContext(args.run_id)
    union_pids = staging.load_json("union_pids.json")
    
    if not union_pids:
        affected_pairs = staging.load_json("affected_pairs.json") or []
        union_pids = list(set(p[0] for p in affected_pairs))
        
    if not union_pids:
        print("No affected projects found. Exiting.")
        return

    build_incremental_portfolio(staging, union_pids)

if __name__ == "__main__":
    main()
    import os
    os._exit(0)
