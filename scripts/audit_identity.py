#!/usr/bin/env python3
"""
scripts/audit_identity.py

Quality audit script for project identities in VIGIL.
Inspects project_monthly.csv and identifies records where project_name appears to be:
- table headings
- section headings
- report titles
- column headers
- generic phrases (e.g. "DETAILS OF...", "LIST OF PROJECTS...", "PROJECTS SHOWING...")
- schedule status phrases ("AHEAD OF SCHEDULE", "DELAYED", "ON SCHEDULE", "WITHOUT SCHEDULE")
- generic ministry/sector names
- other obvious non-project entities

Creates:
  DATA/project_identity_review.csv

Fields:
  project_id
  project_name
  observation_count
  reason_flagged
  recommended_action (KEEP, REVIEW, EXCLUDE)
"""

import os
import re
import pandas as pd

def run_audit(input_csv="DATA/project_monthly.csv", output_csv="DATA/project_identity_review.csv"):
    if not os.path.exists(input_csv):
        print(f"Error: {input_csv} not found.")
        return

    df = pd.read_csv(input_csv, dtype=str)
    total_unique_projects = df["project_id"].nunique()

    # Define rule patterns
    rules = [
        ("TABLE_HEADING", r"(?i)\b(?:table\s*[:-]?\s*\d+|table\s*[–-]\s*\d+|annexure(?:\s*[-–]\s*[a-z0-9]+)?)\b"),
        ("REPORT_TITLE_OR_SECTION", r"(?i)\b(?:details?\s+of\s+central\s+sector|details?\s+of\s+ongoing|list\s+of\s+projects?|projects?\s+showing|ahead\s+of\s+schedule|delayed|on\s+schedule|without\s+schedule|project\s+status\s+with\s+respect|summary\s+of\s+projects|flash\s+report|status\s+report|costing\s+rs|statement\s+showing|sector\s+wise|state\s+wise|ministry\s+wise|central\s+sector\s+projects?|part\s*[-–]?\s*(?:i{1,3}|iv|v|1|2))\b"),
        ("COLUMN_HEADER_ARTIFACT", r"(?i)\b(?:sl\.?\s*no|si\.?\s*no|s\.?no|date\s+of\s+commissioning|date\s+of\s+approval|original\s*/\s*revised|anticipated\s+cost|cumulative\s+expenditure|cost\s+overrun|time\s+overrun|expenditure\s+is\s+more|project\s+doa\s+doc|sn\s+project|expenditure\s+cost|original/revised)\b"),
        ("GENERIC_MINISTRY_OR_SECTOR", r"(?i)^(?:railways?|coal|power|petroleum|steel|atomic\s+energy|road\s+transport\s+and\s+highways|civil\s+aviation|telecom(?:munications?)?|mines|fertilizers?|shipping|ports|dpiit|doner|home\s+affairs|commerce|finance|social\s+justice|water\s+resources|health|heavy\s+industries|department\s+of\s+[a-z\s]+|ministry\s+of\s+[a-z\s]+)$"),
        ("GENERIC_NON_PROJECT", r"(?i)^(?:total|grand\s+total|all\s+projects|sub[- ]?total|various|miscellaneous|ongoing\s+projects?|completed\s+projects?|others?|nil|none|na|n\.a\.?)$"),
        ("FRAGMENT_OR_SHORT_CODE", r"^([0-9\W_]{1,4}|[A-Za-z]{1,3})$")
    ]

    flagged_records = []

    for pid, group in df.groupby("project_id"):
        obs_cnt = group["reporting_month"].nunique()
        names = [str(n).strip() for n in group["project_name"].dropna().unique() if str(n).strip()]
        if not names:
            names = [""]

        # Check primary name (longest or most common)
        primary_name = max(names, key=len) if names else ""
        
        matched_reason = None
        matched_rule = None

        for name_str in names:
            for r_name, r_regex in rules:
                m = re.search(r_regex, name_str)
                if m:
                    matched_rule = r_name
                    matched_reason = f"{r_name}: matched '{m.group(0)}'"
                    break
            if matched_reason:
                break

        if matched_reason:
            has_official_code = not str(pid).startswith("PRJ_")
            
            # Obvious table/section headers or column artifacts
            is_definitely_header = bool(re.match(r"(?i)^(?:table|annexure|details?\s+of|list\s+of|projects?\s+showing|summary|sector|state|ministry|railways|coal|power|petroleum|steel|atomic\s+energy|civil\s+aviation|mines|dpiit|doner|commerce|finance|road\s+transport|home\s+affairs|urban\s+development|water\s+resources|health|department\s+of|telecommunications?)\b", primary_name)) or bool(re.search(r"(?i)\b(?:sn\s+project|doa\s+doc)\b", primary_name))

            if has_official_code:
                # Real project code exists
                if re.match(r"(?i)^(?:construction|widening|4-lan|four\s+lan|six\s+lan|transmission|ts\s+for|rehabilitation|augmentation|development|laying|setting|bg\s+line|gauge|doubling)\b", primary_name):
                    action = "KEEP"
                else:
                    action = "REVIEW"
            elif is_definitely_header or matched_rule in ["TABLE_HEADING", "REPORT_TITLE_OR_SECTION", "GENERIC_MINISTRY_OR_SECTOR", "GENERIC_NON_PROJECT", "FRAGMENT_OR_SHORT_CODE"]:
                action = "EXCLUDE"
            else:
                action = "REVIEW"

            flagged_records.append({
                "project_id": pid,
                "project_name": primary_name,
                "observation_count": obs_cnt,
                "reason_flagged": matched_reason,
                "recommended_action": action
            })

    df_flagged = pd.DataFrame(flagged_records)
    
    # Sort by observation count descending, then recommended_action
    if not df_flagged.empty:
        df_flagged.sort_values(by=["observation_count", "project_id"], ascending=[False, True], inplace=True)
    
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_flagged.to_csv(output_csv, index=False, encoding="utf-8")

    total_flagged = len(df_flagged)
    cnt_exclude = (df_flagged["recommended_action"] == "EXCLUDE").sum() if not df_flagged.empty else 0
    cnt_review = (df_flagged["recommended_action"] == "REVIEW").sum() if not df_flagged.empty else 0
    cnt_keep = (df_flagged["recommended_action"] == "KEEP").sum() if not df_flagged.empty else 0

    print("=" * 80)
    print("VIGIL PROJECT IDENTITY QUALITY AUDIT")
    print("=" * 80)
    print(f"Total unique projects in dataset    : {total_unique_projects:,}")
    print(f"Total projects flagged              : {total_flagged:,} ({total_flagged/total_unique_projects*100:.2f}%)")
    print(f"Projects recommended for EXCLUSION  : {cnt_exclude:,}")
    print(f"Projects recommended for REVIEW     : {cnt_review:,}")
    print(f"Projects recommended to KEEP        : {cnt_keep:,}")
    print(f"Wrote audit review artifact         -> {output_csv}")
    print("=" * 80)

    print("\nTOP 50 SUSPICIOUS PROJECT IDENTITIES:")
    print(f"{'Project ID':<18} | {'Obs':<3} | {'Action':<7} | {'Reason Flagged':<32} | {'Project Name'}")
    print("-" * 110)
    for _, row in df_flagged.head(50).iterrows():
        p_name = str(row['project_name'])[:45]
        print(f"{row['project_id']:<18} | {row['observation_count']:<3} | {row['recommended_action']:<7} | {row['reason_flagged'][:32]:<32} | {p_name}")
    print("=" * 110)

if __name__ == "__main__":
    run_audit()
