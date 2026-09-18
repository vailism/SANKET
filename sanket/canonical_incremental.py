import os
import json
import pandas as pd
from typing import List, Dict, Any, Set, Tuple
from sanket.incremental_manager import StagingContext

def to_float(val):
    try:
        if pd.notna(val) and str(val).strip() not in ["", "None", "nan"]:
            return float(val)
    except (ValueError, TypeError):
        pass
    return None

def apply_canonical_rules(group: List[Dict[str, Any]], pid: str, month: str) -> Dict[str, Any]:
    """Apply exact canonical deduplication rules to a group of raw records for (pid, month)."""
    dup_count = len(group)
    src_pdfs = sorted(list(set(str(g.get("source_pdf", "")) for g in group if g.get("source_pdf"))))
    src_pages = sorted(list(set(int(g["source_page"]) for g in group if g.get("source_page") and str(g["source_page"]).isdigit())))
    
    clean_names = [str(g["project_name"]).strip() for g in group if g.get("project_name") and len(str(g["project_name"]).strip()) >= 3]
    proj_name = max(clean_names, key=len) if clean_names else (str(group[0].get("project_name", "")))
    
    sector = next((g["sector"] for g in group if g.get("sector")), "")
    ministry = next((g["ministry"] for g in group if g.get("ministry")), "")
    state = next((g["state"] for g in group if g.get("state")), "")
    district = next((g["district"] for g in group if g.get("district")), "")
    project_size = next((g["project_size"] for g in group if g.get("project_size")), "")

    phys_vals = [f for f in (to_float(g.get("physical_progress")) for g in group) if f is not None]
    fin_vals = [f for f in (to_float(g.get("financial_progress")) for g in group) if f is not None]
    exp_vals = [f for f in (to_float(g.get("expenditure")) for g in group) if f is not None]
    cost_vals = [f for f in (to_float(g.get("approved_cost")) for g in group) if f is not None]
    rcost_vals = [f for f in (to_float(g.get("revised_cost")) for g in group) if f is not None]

    warnings = []
    if len(phys_vals) > 1 and (max(phys_vals) - min(phys_vals)) > 5.0:
        warnings.append(f"PHYS_PROG_VARIANCE({min(phys_vals):.1f}%-{max(phys_vals):.1f}%)")
    if len(fin_vals) > 1 and (max(fin_vals) - min(fin_vals)) > 5.0:
        warnings.append(f"FIN_PROG_VARIANCE({min(fin_vals):.1f}%-{max(fin_vals):.1f}%)")
    if dup_count > 1:
        warnings.insert(0, f"MERGED_{dup_count}_RAW_ROWS")

    orig_dates = [g["original_completion_date"] for g in group if g.get("original_completion_date")]
    rev_dates = [g["revised_completion_date"] for g in group if g.get("revised_completion_date")]
    milestones = [g["milestone_information"] for g in group if g.get("milestone_information")]
    devs = [g["schedule_deviation"] for g in group if g.get("schedule_deviation")]

    return {
        "project_id": pid,
        "project_name": proj_name,
        "sector": sector,
        "ministry": ministry,
        "state": state,
        "district": district,
        "project_size": project_size,
        "reporting_month": month,
        "physical_progress": max(phys_vals) if phys_vals else None,
        "financial_progress": max(fin_vals) if fin_vals else None,
        "expenditure": max(exp_vals) if exp_vals else None,
        "approved_cost": max(cost_vals) if cost_vals else None,
        "revised_cost": max(rcost_vals) if rcost_vals else None,
        "original_completion_date": orig_dates[0] if orig_dates else None,
        "revised_completion_date": rev_dates[0] if rev_dates else None,
        "milestone_information": max(milestones, key=len) if milestones else "",
        "schedule_deviation": devs[0] if devs else "",
        "duplicate_raw_record_count": dup_count,
        "source_pdf_count": len(src_pdfs),
        "source_pages": "; ".join([f"p.{p}" for p in src_pages]),
        "extraction_warning": "; ".join(warnings),
        "source_pdf": "; ".join(src_pdfs),
        "source_page": src_pages[0] if src_pages else 0
    }

def update_canonical_dataset(staging: StagingContext, affected_pairs: List[Tuple[str, str]], new_raw_records: List[Dict[str, Any]]):
    """Incrementally update project_monthly.csv by re-aggregating only the affected pairs."""
    raw_path = "DATA/raw_extractions.csv"
    monthly_path = "DATA/project_monthly.csv"
    
    print(f"Loading {raw_path} to fetch existing raw records for {len(affected_pairs)} affected pairs...")
    
    affected_set = set(tuple(p) for p in affected_pairs)
    affected_raw_list = []
    
    manifest_update = staging.load_json("ingestion_manifest.json")
    changed_pdfs = set(r.get("source_pdf") for r in new_raw_records if r.get("source_pdf")) if manifest_update else set()
    
    out_raw = staging.get_path("raw_extractions.csv")
    first = True
    
    if os.path.exists(raw_path):
        for chunk in pd.read_csv(raw_path, dtype=str, chunksize=10000):
            if changed_pdfs:
                chunk = chunk[~chunk["source_pdf"].isin(changed_pdfs)]
            
            if not chunk.empty:
                idx = chunk.set_index(["project_id", "reporting_month"]).index
                affected_raw_list.append(chunk[idx.isin(affected_set)])
                chunk.to_csv(out_raw, mode='w' if first else 'a', header=first, index=False)
                first = False

    df_new = pd.DataFrame(new_raw_records)
    if not df_new.empty:
        df_new.to_csv(out_raw, mode='w' if first else 'a', header=first, index=False)
        first = False
        idx_new = df_new.set_index(["project_id", "reporting_month"]).index
        affected_raw_list.append(df_new[idx_new.isin(affected_set)])
        
    if not os.path.exists(out_raw) and first:
        # Create empty if nothing was written
        pd.DataFrame(columns=["project_id", "reporting_month"]).to_csv(out_raw, index=False)
        
    df_raw_affected = pd.concat(affected_raw_list, ignore_index=True) if affected_raw_list else pd.DataFrame()
    
    # Apply canonical rules
    updated_canonical = []
    if not df_raw_affected.empty:
        groups = df_raw_affected.groupby(["project_id", "reporting_month"])
        for (pid, month), group_df in groups:
            # Check exclusions
            group_records = group_df.to_dict("records")
            clean_row = apply_canonical_rules(group_records, str(pid), str(month))
            updated_canonical.append(clean_row)
        
    # Write to staging canonical update
    staging.write_json("canonical_updates.json", updated_canonical)
    
    # Load existing project_monthly, update rows, write to staging
    out_monthly = staging.get_path("project_monthly.csv")
    first = True
    
    if os.path.exists(monthly_path):
        for chunk in pd.read_csv(monthly_path, dtype=str, chunksize=10000):
            chunk = chunk[~chunk.set_index(["project_id", "reporting_month"]).index.isin(affected_set)]
            if not chunk.empty:
                chunk.to_csv(out_monthly, mode='w' if first else 'a', header=first, index=False)
                first = False

    df_updated = pd.DataFrame(updated_canonical)
    if not df_updated.empty:
        df_updated.to_csv(out_monthly, mode='w' if first else 'a', header=first, index=False)
        first = False
        
    if not os.path.exists(out_monthly) and first:
        pd.DataFrame(columns=["project_id", "reporting_month"]).to_csv(out_monthly, index=False)
        
    print(f"Updated {len(updated_canonical)} canonical rows in staging.")
