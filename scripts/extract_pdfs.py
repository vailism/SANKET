#!/usr/bin/env python3
"""
scripts/extract_pdfs.py

Robust, scalable PDF ingestion and extraction pipeline for VIGIL.
Processes MoSPI OCMS / PAIMANA Flash Reports and Quarterly Reports.
Extracts longitudinal project observation records with zero hallucination.

Usage:
  python scripts/extract_pdfs.py --input "DATA(RAW) " --output DATA
"""

import os
import sys
import re
import argparse
import csv
import time
import concurrent.futures
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple
import pymupdf
import pandas as pd

# Import normalizers
from normalize import (
    clean_text, extract_project_code, normalize_project_id,
    normalize_month, normalize_progress, normalize_money, extract_multi_field,
    clean_sector_name
)

def detect_reporting_month(doc: pymupdf.Document, filename: str) -> Optional[str]:
    """Detect reporting month in strict YYYY-MM format across 2000-2029."""
    full_text = ""
    for p in range(min(8, len(doc))):
        full_text += doc[p].get_text() + "\n"

    # 1. Indian Quarter Month ranges in filename
    # e.g. Apr-June-2015 -> Q1 (2015-06)
    m_q_range = re.search(r'(?:Apr(?:il)?[-_ ]*Jun(?:e)?)[-_ ]*((?:19|20)\d{2})', filename, re.IGNORECASE)
    if m_q_range:
        return f"{m_q_range.group(1)}-06"
        
    m_q_range2 = re.search(r'(?:Jul(?:y)?[-_ ]*Sep(?:t|tember)?)[-_ ]*((?:19|20)\d{2})', filename, re.IGNORECASE)
    if m_q_range2:
        return f"{m_q_range2.group(1)}-09"
        
    m_q_range3 = re.search(r'(?:Oct(?:ober)?[-_ ]*Dec(?:ember)?)[-_ ]*((?:19|20)\d{2})', filename, re.IGNORECASE)
    if m_q_range3:
        return f"{m_q_range3.group(1)}-12"
        
    m_q_range4 = re.search(r'(?:Jan(?:uary)?[-_ ]*Mar(?:ch)?)[-_ ]*((?:19|20)\d{2})', filename, re.IGNORECASE)
    if m_q_range4:
        return f"{m_q_range4.group(1)}-03"

    # 2. Fiscal Quarter patterns in filename (e.g. QPSR 4th QTR 2023-2024, QPSIR_3qtr_21-22)
    m_q4 = re.search(r'Q(?:PSR|PISR)?[-_ ]?4th?[_-]?QTR[_-]?((?:19|20)\d{2}|\d{2})[-_](\d{2,4})', filename, re.IGNORECASE)
    if m_q4:
        y_str = m_q4.group(1)
        start_year = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
        return f"{start_year + 1}-03"
        
    m_q_file = re.search(r'(1st|2nd|3rd|4th|\d)[-_ ]*Q(?:TR|PSR|PISR)[-_ ]*((?:19|20)\d{2}|\d{2})[-_](\d{2,4})', filename, re.IGNORECASE)
    if m_q_file:
        q_num = m_q_file.group(1).lower()
        y_str = m_q_file.group(2)
        start_year = int(y_str) if len(y_str) == 4 else 2000 + int(y_str)
        if "1" in q_num:
            return f"{start_year}-06"
        elif "2" in q_num:
            return f"{start_year}-09"
        elif "3" in q_num:
            return f"{start_year}-12"
        elif "4" in q_num:
            return f"{start_year + 1}-03"

    # 3. Fiscal quarter mentioned in text
    m_q_text = re.search(r'(1st|2nd|3rd|4th)\s*Quarter\s*\(([^)]+)\)[,\s]+((?:19|20)\d{2})[-_](\d{2,4})', full_text, re.IGNORECASE)
    if m_q_text:
        q_num = m_q_text.group(1).lower()
        start_year = int(m_q_text.group(3))
        if "1st" in q_num:
            return f"{start_year}-06"
        elif "2nd" in q_num:
            return f"{start_year}-09"
        elif "3rd" in q_num:
            return f"{start_year}-12"
        elif "4th" in q_num:
            return f"{start_year + 1}-03"

    # 4. Month + Year anywhere in filename (e.g. FR_july_Report_2019.pdf, FLR_APR_2009.pdf, FR_AUG_2001.pdf)
    m_fn_my = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[^0-9]*((?:19|20)\d{2})', filename, re.IGNORECASE)
    if m_fn_my:
        norm = normalize_month(f"{m_fn_my.group(1)} {m_fn_my.group(2)}")
        if norm:
            return norm

    # 5. Flash Report date in text (e.g. Flash Report for the month of April 2012)
    m_fr = re.search(r'(?:Flash\s+Report.*?|Central\s+Sector.*?Projects.*?)?(January|February|March|April|May|June|July|August|September|October|November|December)[\s,]+((?:19|20)\d{2})', full_text, re.IGNORECASE)
    if m_fr:
        norm = normalize_month(f"{m_fr.group(1)} {m_fr.group(2)}")
        if norm:
            return norm
            
    # 6. Check filename for just Month name (e.g. January.pdf, December.pdf)
    m_fn = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)', filename, re.IGNORECASE)
    if m_fn:
        m_name = m_fn.group(1)
        m_y = re.search(r'(?:19|20)\d{2}', full_text)
        year = m_y.group(0) if m_y else "2024"
        norm = normalize_month(f"{m_name} {year}")
        if norm:
            return norm

    return None

def classify_document(filename: str, page_count: int) -> str:
    """Classify document into one of four operational families."""
    f_lower = filename.lower()
    if page_count <= 25 or "synopsis" in f_lower or "(synopsis)" in f_lower:
        return "SYNOPSIS"
    elif "part-ii" in f_lower or "part-2" in f_lower or "part_ii" in f_lower:
        if "april" in f_lower or "may" in f_lower:
            return "ANNEXURE_XVIII"
        elif "qpsr" in f_lower or "qpisr" in f_lower:
            return "CLASSIC_MASTER_TABLE"
        else:
            return "MODERN_TABLE_7"
    elif any(k in f_lower for k in ["apr-jun", "july-sep", "oct-dec", "jan-mar", "jan-march"]):
        return "CLASSIC_MASTER_TABLE"
    elif "qpsr" in f_lower or "qpisr" in f_lower or filename.startswith("QPSIR_1st_QTR_2022-23"):
        if "part2" in f_lower or "3rd_qtr" in f_lower or "4th_qtr" in f_lower:
            return "MODERN_TABLE_7"
        else:
            return "QPSR_CARDS"
    elif filename.startswith("FR_") or filename.startswith("MonthlyFR_") or filename.startswith("FLR_") or (filename.startswith("FR") and "march" not in f_lower):
        return "CLASSIC_MASTER_TABLE"
    else:
        return "MODERN_TABLE_7"

def clean_project_title(raw_cell: str) -> str:
    """Extract clean project name without trailing metadata, codes, or agency."""
    t = clean_text(raw_cell)
    # Strip pattern: - [CODE],AGENCY,STATE
    t = re.sub(r'-\s*\[.*?\](?:\s*,\s*[^,]+)?(?:\s*,\s*[^\n]+)?', '', t)
    # Strip pattern: - (CODE),AGENCY,STATE
    t = re.sub(r'-\s*\(.*?\)(?:\s*,\s*[^,]+)?(?:\s*,\s*[^\n]+)?', '', t)
    # Strip unclosed brackets or trailing bracket patterns
    t = re.sub(r'-\s*\[.*$', '', t)
    t = re.sub(r'-\s*\(.*$', '', t)
    # Strip brackets containing codes
    t = re.sub(r'\[[Nn]?\d{8,9}\].*$', '', t).strip()
    t = re.sub(r'\([Nn]?\d{8,9}\).*$', '', t).strip()
    # Strip trailing agency in parentheses e.g. (IOCL ) or (NHAI )
    t = re.sub(r'\([A-Za-z0-9\s\.\&\-]{2,20}\)\s*$', '', t).strip()
    # Strip trailing commas, hyphens, and dashes
    t = re.sub(r'[\s,\-]+$', '', t).strip()
    t = re.sub(r'^\s*-\s*', '', t).strip()
    return clean_text(t)

def is_excluded_non_project(project_id: str, project_name: str) -> bool:
    """
    Identifies non-project artifacts (table headings, section titles, column headers).
    Preserves all legitimate projects with official MoSPI codes (e.g. N26000101, N18000372, N24002214).
    """
    if not str(project_id).startswith("PRJ_"):
        return False
        
    name = (project_name or "").strip()
    
    if re.search(r"(?i)\b(?:table\s*[:-]?\s*\d+|table\s*[–-]\s*\d+|annexure(?:\s*[-–]\s*[a-z0-9]+)?)\b", name):
        return True
    if re.search(r"(?i)\b(?:details?\s+of\s+central\s+sector|details?\s+of\s+ongoing|list\s+of\s+projects?|projects?\s+showing|ahead\s+of\s+schedule|delayed|on\s+schedule|without\s+schedule|project\s+status\s+with\s+respect|summary\s+of\s+projects|flash\s+report|status\s+report|costing\s+rs|statement\s+showing|sector\s+wise|state\s+wise|ministry\s+wise|central\s+sector\s+projects?)\b", name):
        return True
    if re.search(r"(?i)\b(?:sl\.?\s*no|si\.?\s*no|s\.?no|date\s+of\s+commissioning|date\s+of\s+approval|original\s*/\s*revised|anticipated\s+cost|cumulative\s+expenditure|cost\s+overrun|time\s+overrun|expenditure\s+is\s+more|project\s+doa\s+doc|sn\s+project|doa\s+doc)\b", name):
        return True
    if re.match(r"(?i)^(?:railways?|coal|power|petroleum|steel|atomic\s+energy|road\s+transport(?:\s+and\s+highways)?|civil\s+aviation|telecom(?:munications?)?|mines|fertilizers?|shipping|ports|dpiit|doner|home\s+affairs|commerce|finance|social\s+justice|water\s+resources|health|heavy\s+industries|department\s+of\s+[a-z\s]+|ministry\s+of\s+[a-z\s]+|urban\s+development)$", name):
        return True
    if re.match(r"(?i)^(?:total|grand\s+total|all\s+projects|sub[- ]?total|various|miscellaneous|ongoing\s+projects?|completed\s+projects?|others?|nil|none|na|n\.a\.?)$", name):
        return True
    if re.match(r"^([0-9\W_]{1,4}|[A-Za-z]{1,3})$", name):
        return True
        
    return False

def extract_from_modern_table(page: pymupdf.Page, page_num: int, filename: str, reporting_month: str, current_context: Dict[str, str]) -> List[Dict[str, Any]]:
    """Extract rows from modern Table 6 / 7 (e.g. December 2024, July 2024)."""
    records = []
    tabs = page.find_tables()
    tables_list = tabs.tables if tabs.tables else page.find_tables(strategy="text").tables
    for tab in tables_list:
        rows = tab.extract()
        if not rows:
            continue
            
        for r in rows:
            if not r or len(r) < 5:
                continue
                
            row_str = " ".join([str(c or "") for c in r])
            if "Project Name" in row_str or "Sl No" in row_str or "Cumulative" in row_str:
                continue
                
            col0 = clean_text(r[0] if len(r) > 0 else "")
            col1 = clean_text(r[1] if len(r) > 1 else "")
            s0 = clean_sector_name(col0)
            if s0:
                current_context["sector"] = s0
            s1 = clean_sector_name(col1)
            if s1:
                current_context["sector"] = s1
                
            sl_col = -1
            for idx, c in enumerate(r[:4]):
                if c and re.match(r'^\d+$', str(c).strip()):
                    sl_col = idx
                    break
                    
            if sl_col == -1 or sl_col + 1 >= len(r):
                continue
                
            proj_cell = str(r[sl_col + 1] or "").strip()
            if not proj_cell or proj_cell in ["1", "2", "3", "4", "5", "6", "7", "(1)", "(2)", "(3)"]:
                continue
                
            is_paimana = False
            code = None
            if re.match(r'^\d{6,8}$', proj_cell) and len(r) > sl_col + 2:
                is_paimana = True
                code = proj_cell
                proj_cell = str(r[sl_col + 2] or "").strip()
                
            proj_name = clean_project_title(proj_cell)
            if len(proj_name) < 3 or re.match(r'^\d+$', proj_name):
                continue
                
            if is_paimana:
                doc_cell = ""
                c_orig = str(r[sl_col + 3] or "").strip() if len(r) > sl_col + 3 else ""
                c_rev = str(r[sl_col + 4] or "").strip() if len(r) > sl_col + 4 else ""
                cost_cell = c_orig + "\n" + c_rev
                exp_cell = str(r[sl_col + 5] or "").strip() if len(r) > sl_col + 5 else ""
                prog_cell = str(r[sl_col + 6] or "").strip() if len(r) > sl_col + 6 else ""
            else:
                _ = str(r[sl_col + 2] or "") if len(r) > sl_col + 2 else ""
                doc_cell = str(r[sl_col + 3] or "") if len(r) > sl_col + 3 else ""
                cost_cell = str(r[sl_col + 4] or "") if len(r) > sl_col + 4 else ""
                exp_cell = str(r[sl_col + 5] or "") if len(r) > sl_col + 5 else ""
                prog_cell = str(r[sl_col + 6] or "") if len(r) > sl_col + 6 else ""
            
            if not is_paimana:
                code = extract_project_code(proj_cell)
            
            agency_matches = re.findall(r'\(([A-Za-z0-9\s\.\&\-]+)\)', proj_cell)
            agency_list = [a.strip() for a in agency_matches if not extract_project_code(a)]
            agency = agency_list[0] if agency_list else current_context.get("sector", "")
            
            doc_orig, doc_rev, doc_antic = extract_multi_field(doc_cell)
            cost_orig, cost_rev, cost_antic = extract_multi_field(cost_cell)
            
            norm_doc_orig = normalize_month(doc_orig)
            norm_doc_rev = normalize_month(doc_rev) or normalize_month(doc_antic)
            
            norm_cost_orig = normalize_money(cost_orig)
            norm_cost_rev = normalize_money(cost_rev) or normalize_money(cost_antic)
            norm_exp = normalize_money(exp_cell)
            norm_prog = normalize_progress(prog_cell)
            
            fin_prog = round((norm_exp / norm_cost_orig * 100), 2) if (norm_exp and norm_cost_orig and norm_cost_orig > 0) else None
            
            if is_paimana and code:
                proj_id = code  # Use PAIMANA 6-digit code directly
            else:
                proj_id = normalize_project_id(code, proj_name, current_context.get("sector", ""), agency, current_context.get("state", ""))
            if not proj_id or len(proj_name) < 3 or re.match(r'^\d+$', proj_name):
                continue
            
            records.append({
                "project_id": proj_id,
                "project_name": proj_name,
                "sector": clean_sector_name(current_context.get("sector", "")) or "",
                "ministry": agency,
                "state": current_context.get("state", ""),
                "district": "",
                "project_size": "",
                "reporting_month": reporting_month,
                "physical_progress": norm_prog,
                "financial_progress": fin_prog,
                "expenditure": norm_exp,
                "approved_cost": norm_cost_orig,
                "revised_cost": norm_cost_rev,
                "original_completion_date": norm_doc_orig,
                "revised_completion_date": norm_doc_rev,
                "milestone_information": "",
                "schedule_deviation": "",
                "source_pdf": filename,
                "source_page": page_num,
                "raw_text": clean_text(f"{proj_cell} | {doc_cell} | {cost_cell} | {exp_cell} | {prog_cell}")
            })
    return records

def extract_from_classic_table(page: pymupdf.Page, page_num: int, filename: str, reporting_month: str, current_context: Dict[str, str]) -> List[Dict[str, Any]]:
    """Extract rows from Classic Flash Report Master Table or Annexures."""
    records = []
    tabs = page.find_tables()
    tables_list = tabs.tables if tabs.tables else page.find_tables(strategy="text").tables
    for tab in tables_list:
        rows = tab.extract()
        if not rows:
            continue
            
        for r in rows:
            if not r or len(r) < 5:
                continue
            row_str = " ".join([str(c or "") for c in r])
            if "Detail of ongoing" in row_str or "SI.No" in row_str or "Sl.No" in row_str or "Details of Ongoing" in row_str:
                continue
                
            sl_cell = str(r[0] or "").strip()
            if not re.match(r'^\d+$', sl_cell):
                text_clean = clean_text(row_str)
                # Check for continuation of previous project row (e.g. split across pages)
                proj_cell = str(r[1] or "").strip() if len(r) > 1 else ""
                if records and proj_cell and not any(k in proj_cell.lower() for k in ["total", "sl.no", "page", "table", "annexure", "unit", "crore"]):
                    new_code = extract_project_code(proj_cell)
                    m_meta = re.search(r'-\s*(?:\[.*?\]|\(.*?\))\s*,\s*([^,]+)(?:,\s*([^\n]+))?', proj_cell)
                    if m_meta:
                        records[-1]["ministry"] = records[-1]["ministry"] or m_meta.group(1).strip()
                        records[-1]["state"] = records[-1]["state"] or (m_meta.group(2).strip() if m_meta.group(2) else "")
                    elif re.search(r'\[([Nn]\d{8}|\d{9})\],([^,]+)(?:,(.*))?', proj_cell):
                        m_tail = re.search(r'\[([Nn]\d{8}|\d{9})\],([^,]+)(?:,(.*))?', proj_cell)
                        records[-1]["ministry"] = records[-1]["ministry"] or m_tail.group(2).strip()
                        records[-1]["state"] = records[-1]["state"] or (m_tail.group(3).strip() if m_tail.group(3) else "")
                    cleaned_extra = clean_project_title(proj_cell)
                    if cleaned_extra:
                        records[-1]["project_name"] = clean_text(records[-1]["project_name"] + " " + cleaned_extra)
                    if new_code and records[-1]["project_id"].startswith("PRJ_"):
                        records[-1]["project_id"] = new_code
                elif (text_clean and len(text_clean) < 50 
                      and not re.search(r'[\d\[\]\(\)\{\},:;/\\]', text_clean)
                      and not any(k in text_clean.lower() for k in ["total", "sl.no", "page", "table", "annexure", "unit", "crore", "detail"])):
                    current_context["sector"] = text_clean
                continue
                
            proj_cell = str(r[1] or "").strip()
            if not proj_cell or proj_cell in ["1", "2", "3", "4", "5", "6", "7", "(1)", "(2)", "(3)"]:
                continue
                
            proj_name = clean_project_title(proj_cell)
            if len(proj_name) < 3 or re.match(r'^\d+$', proj_name):
                continue
                
            _ = str(r[2] or "") if len(r) > 2 else ""
            doc_cell = str(r[3] or "") if len(r) > 3 else ""
            cost_cell = str(r[4] or "") if len(r) > 4 else ""
            exp_cell = str(r[5] or "") if len(r) > 5 else ""
            milestone_cell = str(r[6] or "") if len(r) > 6 else ""
            
            code = extract_project_code(proj_cell)
            
            agency = ""
            state = ""
            m_meta = re.search(r'-\s*(?:\[.*?\]|\(.*?\))\s*,\s*([^,]+)(?:,\s*([^\n]+))?', proj_cell)
            if m_meta:
                agency = m_meta.group(1).strip()
                state = m_meta.group(2).strip() if m_meta.group(2) else ""
            else:
                m_code_tail = re.search(r'\[([Nn]\d{8}|\d{9})\],([^,]+)(?:,(.*))?', proj_cell)
                if m_code_tail:
                    agency = m_code_tail.group(2).strip()
                    state = m_code_tail.group(3).strip() if m_code_tail.group(3) else ""
                    
            doc_orig, doc_rev, doc_antic = extract_multi_field(doc_cell)
            cost_orig, cost_rev, cost_antic = extract_multi_field(cost_cell)
            exp_orig, _, time_overrun = extract_multi_field(exp_cell)
            
            norm_doc_orig = normalize_month(doc_orig)
            norm_doc_rev = normalize_month(doc_rev) or normalize_month(doc_antic)
            
            norm_cost_orig = normalize_money(cost_orig)
            norm_cost_rev = normalize_money(cost_rev) or normalize_money(cost_antic)
            norm_exp = normalize_money(exp_orig)
            
            fin_prog = round((norm_exp / norm_cost_orig * 100), 2) if (norm_exp and norm_cost_orig and norm_cost_orig > 0) else None
            
            delay_clean = ""
            if time_overrun:
                delay_m = re.search(r'\d+', time_overrun)
                if delay_m:
                    delay_clean = delay_m.group(0)
                    
            proj_id = normalize_project_id(code, proj_name, current_context.get("sector", ""), agency, state)
            if not proj_id or len(proj_name) < 3 or re.match(r'^\d+$', proj_name):
                continue
            
            records.append({
                "project_id": proj_id,
                "project_name": proj_name,
                "sector": clean_sector_name(current_context.get("sector", "")) or "",
                "ministry": agency,
                "state": state,
                "district": "",
                "project_size": "",
                "reporting_month": reporting_month,
                "physical_progress": None,
                "financial_progress": fin_prog,
                "expenditure": norm_exp,
                "approved_cost": norm_cost_orig,
                "revised_cost": norm_cost_rev,
                "original_completion_date": norm_doc_orig,
                "revised_completion_date": norm_doc_rev,
                "milestone_information": clean_text(milestone_cell),
                "schedule_deviation": delay_clean,
                "source_pdf": filename,
                "source_page": page_num,
                "raw_text": clean_text(f"{proj_cell} | {doc_cell} | {cost_cell} | {exp_cell} | {milestone_cell}")
            })
    return records

def extract_from_qpsr_page(page: pymupdf.Page, page_num: int, filename: str, reporting_month: str) -> List[Dict[str, Any]]:
    """Extract projects from QPSR cards/tables (e.g. QPSR_1st_QTR_2023-24.pdf)."""
    records = []
    text = page.get_text()
    if "Date of" not in text or "Original" not in text:
        return records
        
    tabs = page.find_tables()
    if not tabs.tables:
        return records
        
    blocks = page.get_text("blocks")
    
    for t_idx, tab in enumerate(tabs.tables):
        t_rows = tab.extract()
        if len(t_rows) < 2:
            continue
            
        data_row = t_rows[1]
        if len(data_row) < 7:
            continue
            
        _ = str(data_row[0] or "")
        cost_cell = str(data_row[1] or "")
        _ = str(data_row[2] or "")
        doc_cell = str(data_row[3] or "")
        exp_cell = str(data_row[4] or "")
        time_overrun = str(data_row[5] or "")
        prog_cell = str(data_row[6] or "")
        
        tab_bbox = tab.bbox
        
        above_text = ""
        for b in blocks:
            if b[3] <= tab_bbox[1] and (t_idx == 0 or b[1] >= tabs.tables[t_idx-1].bbox[3] - 10):
                above_text += " " + b[4].replace("\n", " ")
                
        below_text = ""
        for b in blocks:
            if b[1] >= tab_bbox[3] and (t_idx == len(tabs.tables)-1 or b[3] <= tabs.tables[t_idx+1].bbox[1] + 10):
                below_text += " " + b[4].replace("\n", " ")
                
        code = extract_project_code(above_text)
        
        m_loc = re.search(r'Location:\s*([A-Za-z\s]+?)(?:Capacity|\d{9}|[Nn]\d{8}|Date|$)', above_text, re.IGNORECASE)
        state = clean_text(m_loc.group(1)) if m_loc else ""
        
        m_name = re.search(r'^\s*([A-Z0-9\s,\.\(\)\-\/\&]{5,100}?)(?:Location:|\d{9}|[Nn]\d{8})', above_text.strip())
        proj_name = clean_project_title(m_name.group(1)) if m_name else clean_project_title(above_text[:60])
        
        if len(proj_name) < 3 or re.match(r'^\d+$', proj_name):
            continue
            
        cost_orig, cost_rev, cost_antic = extract_multi_field(cost_cell)
        doc_orig, doc_rev, doc_antic = extract_multi_field(doc_cell)
        exp_lines = [l.strip() for l in exp_cell.splitlines() if l.strip()]
        exp_val_str = exp_lines[-1] if exp_lines else exp_cell
        
        norm_cost_orig = normalize_money(cost_orig)
        norm_cost_rev = normalize_money(cost_rev) or normalize_money(cost_antic)
        norm_doc_orig = normalize_month(doc_orig)
        norm_doc_rev = normalize_month(doc_rev) or normalize_month(doc_antic)
        norm_exp = normalize_money(exp_val_str)
        norm_prog = normalize_progress(prog_cell)
        
        fin_prog = round((norm_exp / norm_cost_orig * 100), 2) if (norm_exp and norm_cost_orig and norm_cost_orig > 0) else None
        
        delay_clean = ""
        if time_overrun:
            m_del = re.search(r'\d+', time_overrun)
            if m_del:
                delay_clean = m_del.group(0)
                
        proj_id = normalize_project_id(code, proj_name, "", "", state)
        if not proj_id or len(proj_name) < 3 or re.match(r'^\d+$', proj_name):
            continue
        
        records.append({
            "project_id": proj_id,
            "project_name": proj_name,
            "sector": "",
            "ministry": "",
            "state": state,
            "district": "",
            "project_size": "",
            "reporting_month": reporting_month,
            "physical_progress": norm_prog,
            "financial_progress": fin_prog,
            "expenditure": norm_exp,
            "approved_cost": norm_cost_orig,
            "revised_cost": norm_cost_rev,
            "original_completion_date": norm_doc_orig,
            "revised_completion_date": norm_doc_rev,
            "milestone_information": clean_text(below_text)[:150],
            "schedule_deviation": delay_clean,
            "source_pdf": filename,
            "source_page": page_num,
            "raw_text": clean_text(f"{above_text} | {cost_cell} | {doc_cell} | {exp_cell} | {prog_cell}")
        })
    return records

def process_pdf(filepath: str, filename: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """Process a single PDF document through targeted table extraction."""
    records = []
    errors = []
    quality = {
        "source_pdf": filename,
        "pages": 0,
        "text_extracted": False,
        "tables_detected": 0,
        "projects_detected": 0,
        "reporting_month_detected": "UNKNOWN",
        "ocr_used": False,
        "extraction_status": "PENDING",
        "confidence": 0.0
    }
    
    try:
        doc = pymupdf.open(filepath)
        page_count = len(doc)
        quality["pages"] = page_count
        
        rep_month = detect_reporting_month(doc, filename)
        if rep_month:
            quality["reporting_month_detected"] = rep_month
        else:
            rep_month = "UNKNOWN"
            
        category = classify_document(filename, page_count)
        
        if category == "SYNOPSIS":
            quality["text_extracted"] = True
            quality["extraction_status"] = "SYNOPSIS_NO_PROJECT_TABLES"
            quality["confidence"] = 1.0
            doc.close()
            return records, quality, errors
            
        current_context = {"sector": "", "state": ""}
        total_tables = 0
        in_classic_master_table = False
        
        for p_num in range(page_count):
            try:
                page = doc[p_num]
                p_text = page.get_text()
                if not p_text.strip():
                    continue
                quality["text_extracted"] = True
                
                page_records = []
                
                if category == "MODERN_TABLE_7":
                    if re.search(r'(?i)\bTable\s*[:-–]?\s*[67]\b|Project\s*List\s*:\s*Ongoing|Major\s+On-going\s+Projects\s+Monitored\s+under\s+PAIMANA', p_text):
                        page_records = extract_from_modern_table(page, p_num + 1, filename, rep_month, current_context)
                        
                elif category == "ANNEXURE_XVIII":
                    if p_num >= 440 and any(k in p_text for k in ["Annexure - XVII", "Annexure  XVII", "Annexure - XVIII", "Annexure  XVIII", "Details of North East", "Details of Ongoing"]):
                        in_classic_master_table = True
                    if in_classic_master_table:
                        page_records = extract_from_classic_table(page, p_num + 1, filename, rep_month, current_context)
                        
                elif category == "CLASSIC_MASTER_TABLE":
                    if not in_classic_master_table:
                        if any(k in p_text for k in [
                            "Detail of ongoing Projects", "Details of Ongoing Projects", "List of Projects Ahead", 
                            "List of Projects On Schedule", "List of Projects Delayed", "List of Projects Without Schedule",
                            "Sector-Wise analysis of projects", "Sector-wise analysis of projects", "Sector-Wise Analysis of Projects",
                            "Sector - Wise analysis of projects", "All Ongoing Projects", "Ongoing Projects", "LIST OF PROJECTS",
                            "Appendix-1", "Appendix-I", "Appendix-VII", "List of Projects in which Expenditure",
                            "List of projects without Date of Commissioning"
                        ]):
                            in_classic_master_table = True
                        elif ("qpsr" in filename.lower() or "qpisr" in filename.lower()) and p_num >= 7 and "Commissioning" in p_text:
                            in_classic_master_table = True
                        elif p_num >= 30 and ("Commissioning" in p_text or "Cumulative" in p_text) and ("Cost" in p_text or "Expenditure" in p_text):
                            in_classic_master_table = True
                    if in_classic_master_table:
                        page_records = extract_from_classic_table(page, p_num + 1, filename, rep_month, current_context)
                        
                elif category == "QPSR_CARDS":
                    if "Date of" in p_text and "Original" in p_text and ("Physical" in p_text or "Exp" in p_text or "Cost" in p_text):
                        page_records = extract_from_qpsr_page(page, p_num + 1, filename, rep_month)
                        
                if page_records:
                    records.extend(page_records)
                    total_tables += 1
                    
            except Exception as pe:
                errors.append({
                    "source_pdf": filename,
                    "page": p_num + 1,
                    "error_type": "PAGE_EXTRACTION_ERROR",
                    "error_message": str(pe)
                })
                
        doc.close()
        quality["tables_detected"] = total_tables
        quality["projects_detected"] = len(records)
        
        if len(records) > 0:
            quality["extraction_status"] = "SUCCESS"
            valid_id_count = sum(1 for r in records if r["project_id"] and not r["project_id"].startswith("UNKNOWN"))
            valid_month_count = sum(1 for r in records if r["reporting_month"] != "UNKNOWN")
            conf = (valid_id_count / len(records)) * 0.5 + (valid_month_count / len(records)) * 0.5
            quality["confidence"] = round(conf, 2)
        else:
            quality["extraction_status"] = "NO_PROJECTS_FOUND"
            quality["confidence"] = 0.0
            
    except Exception as e:
        quality["extraction_status"] = "FILE_READ_ERROR"
        quality["confidence"] = 0.0
        errors.append({
            "source_pdf": filename,
            "page": 0,
            "error_type": "FILE_LEVEL_EXCEPTION",
            "error_message": str(e)
        })
        
    return records, quality, errors

def worker_process_pdf(args_tuple: Tuple[int, str, str]) -> Tuple[int, str, List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]], float]:
    idx, filename, filepath = args_tuple
    t_f0 = time.time()
    records, quality, errors = process_pdf(filepath, filename)
    duration = time.time() - t_f0
    return idx, filename, records, quality, errors, duration

def main():
    parser = argparse.ArgumentParser(description="Extract infrastructure project data from PDFs for VIGIL")
    parser.add_argument("--input", "-i", default="DATA(RAW) ", help="Path to raw PDF folder")
    parser.add_argument("--output", "-o", default="DATA", help="Path to output folder")
    parser.add_argument("--from-raw", action="store_true", help="Re-aggregate canonical dataset directly from DATA/raw_extractions.csv")
    parser.add_argument("--incremental", action="store_true", help="Only process new PDFs that are not already in raw_extractions.csv")
    args = parser.parse_args()

    input_dir = args.input
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    raw_csv_path = os.path.join(output_dir, "raw_extractions.csv")
    pipeline_start = time.time()
    raw_extractions = []
    all_quality_records: List[Dict[str, Any]] = []
    all_error_records: List[Dict[str, Any]] = []

    if args.from_raw and os.path.exists(raw_csv_path):
        print("=" * 90)
        print(f"VIGIL PIPELINE: RE-AGGREGATING CANONICAL DATASET FROM RAW EXTRACTIONS")
        print(f"Raw Input       : {raw_csv_path}")
        print(f"Output Directory: {os.path.abspath(output_dir)}")
        print("=" * 90)
        df_raw_in = pd.read_csv(raw_csv_path, dtype=object)
        for r in df_raw_in.to_dict("records"):
            # Clean nan values
            cleaned_r = {k: (None if pd.isna(v) else v) for k, v in r.items()}
            raw_extractions.append(cleaned_r)
        print(f"Loaded {len(raw_extractions):,} raw records from {raw_csv_path}")
    else:
        pdf_files = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")])
        
        if args.incremental and os.path.exists(raw_csv_path):
            print(f"Incremental mode: loading existing records from {raw_csv_path}...")
            df_existing = pd.read_csv(raw_csv_path, dtype=object)
            for r in df_existing.to_dict("records"):
                cleaned_r = {k: (None if pd.isna(v) else v) for k, v in r.items()}
                raw_extractions.append(cleaned_r)
            existing_pdfs = set(r.get("source_pdf") for r in raw_extractions if r.get("source_pdf"))
            pdf_files = [f for f in pdf_files if f not in existing_pdfs]
            print(f"Found {len(existing_pdfs)} already processed PDFs. {len(pdf_files)} new PDFs to process.")
            
            if not pdf_files:
                print("No new PDFs to process. Proceeding to canonical aggregation...")
        
        print("=" * 90)
        print(f"VIGIL PIPELINE: EXTRACTING INFRASTRUCTURE PROJECT PDFS")
        print(f"Input Directory : {os.path.abspath(input_dir)}")
        print(f"Output Directory: {os.path.abspath(output_dir)}")
        print(f"Total PDFs found: {len(pdf_files)}")
        print("=" * 90)

        all_monthly_records: List[Dict[str, Any]] = []
        file_tasks = [(idx, f, os.path.join(input_dir, f)) for idx, f in enumerate(pdf_files, 1)]
        max_workers = min(7, os.cpu_count() or 4)
        print(f"Parallel extraction active: utilizing {max_workers} worker processes", flush=True)

        completed = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(worker_process_pdf, t): t[1] for t in file_tasks}
            for future in concurrent.futures.as_completed(future_to_file):
                completed += 1
                try:
                    idx, f, records, quality, errors, duration = future.result()
                    all_monthly_records.extend(records)
                    all_quality_records.append(quality)
                    all_error_records.extend(errors)
                    print(f"[{completed:03d}/{len(pdf_files):03d}] {f[:32]:<32} | {quality['extraction_status']:<22} | {quality['projects_detected']:<5} records | {duration:.1f}s | conf: {quality['confidence']}", flush=True)
                except Exception as exc:
                    fname = future_to_file[future]
                    print(f"[{completed:03d}/{len(pdf_files):03d}] {fname[:32]:<32} | ERROR: {exc}", flush=True)

        print("-" * 90)
        print("Post-processing: Writing raw extractions and aggregating canonical dataset...")

        # 1. Append and assign sequential raw_record_id to every raw record
        for r in all_monthly_records:
            raw_rec = dict(r)
            raw_extractions.append(raw_rec)
            
        for r_idx, r in enumerate(raw_extractions, 1):
            r["raw_record_id"] = r_idx

        # Write raw_extractions.csv
        raw_fields = [
            "raw_record_id", "project_id", "project_name", "sector", "ministry", "state",
            "district", "project_size", "reporting_month", "physical_progress",
            "financial_progress", "expenditure", "approved_cost", "revised_cost",
            "original_completion_date", "revised_completion_date", "milestone_information",
            "schedule_deviation", "source_pdf", "source_page", "raw_text"
        ]
        with open(raw_csv_path, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=raw_fields, extrasaction='ignore')
            writer.writeheader()
            for r in raw_extractions:
                writer.writerow(r)
        print(f"Wrote {len(raw_extractions):,} raw records -> {raw_csv_path}")

    # Load approved identity-audit exclusions if file exists
    explicit_excludes = set()
    review_path = os.path.join(output_dir, "project_identity_review.csv")
    if os.path.exists(review_path):
        try:
            df_rev = pd.read_csv(review_path)
            explicit_excludes = set(df_rev[df_rev["recommended_action"] == "EXCLUDE"]["project_id"].dropna())
        except Exception:
            pass

    # 2. Canonical Aggregation by (project_id, reporting_month)
    groups = defaultdict(list)
    for r in raw_extractions:
        pid = str(r.get("project_id", "") or "").strip()
        month = str(r.get("reporting_month", "") or "").strip()
        if not pid or pid == "UNKNOWN" or not month or month == "UNKNOWN":
            continue
        groups[(pid, month)].append(r)

    canonical_records = []
    
    for (pid, month), group in groups.items():
        dup_count = len(group)
        src_pdfs = sorted(list(set(str(g["source_pdf"]) for g in group if g.get("source_pdf"))))
        src_pages = sorted(list(set(int(g["source_page"]) for g in group if g.get("source_page") and str(g["source_page"]).isdigit())))
        
        # Cleanest project name: prefer longest non-empty string
        clean_names = [str(g["project_name"]).strip() for g in group if g.get("project_name") and len(str(g["project_name"]).strip()) >= 3]
        proj_name = max(clean_names, key=len) if clean_names else (str(group[0]["project_name"] or ""))
        
        # Apply approved identity-audit exclusions (preserves raw_extractions.csv)
        if pid in explicit_excludes or is_excluded_non_project(pid, proj_name):
            continue
        
        sector = next((g["sector"] for g in group if g.get("sector")), "")
        ministry = next((g["ministry"] for g in group if g.get("ministry")), "")
        state = next((g["state"] for g in group if g.get("state")), "")
        district = next((g["district"] for g in group if g.get("district")), "")
        project_size = next((g["project_size"] for g in group if g.get("project_size")), "")

        def to_float(val):
            try:
                if val is not None and str(val).strip() not in ["", "None", "nan"]:
                    return float(val)
            except (ValueError, TypeError):
                pass
            return None

        # Progress and numerical fields
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

        # Dates & text
        orig_dates = [g["original_completion_date"] for g in group if g.get("original_completion_date")]
        rev_dates = [g["revised_completion_date"] for g in group if g.get("revised_completion_date")]
        milestones = [g["milestone_information"] for g in group if g.get("milestone_information")]
        devs = [g["schedule_deviation"] for g in group if g.get("schedule_deviation")]

        canonical_records.append({
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
        })

    # Sort canonical records chronologically per project
    canonical_records.sort(key=lambda x: (x["project_id"], x["reporting_month"]))

    # STRICT ASSERTION: Grain must be uniquely (project_id, reporting_month)
    df_canonical = pd.DataFrame(canonical_records)
    assert not df_canonical.duplicated(["project_id", "reporting_month"]).any(), "DUPLICATE (project_id, reporting_month) FOUND IN CANONICAL DATASET!"

    # Write project_monthly.csv
    monthly_csv_path = os.path.join(output_dir, "project_monthly.csv")
    monthly_fields = [
        "project_id", "project_name", "sector", "ministry", "state", "district",
        "project_size", "reporting_month", "physical_progress", "financial_progress",
        "expenditure", "approved_cost", "revised_cost", "original_completion_date",
        "revised_completion_date", "milestone_information", "schedule_deviation",
        "duplicate_raw_record_count", "source_pdf_count", "source_pages",
        "extraction_warning", "source_pdf", "source_page"
    ]
    with open(monthly_csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=monthly_fields, extrasaction='ignore')
        writer.writeheader()
        for r in canonical_records:
            writer.writerow(r)
    print(f"Wrote {len(canonical_records):,} canonical project-month observations -> {monthly_csv_path}")

    # Build Project Master (unique project_id)
    project_master: Dict[str, Dict[str, Any]] = {}
    for r in canonical_records:
        pid = r["project_id"]
        if pid not in project_master:
            project_master[pid] = {
                "project_id": pid,
                "project_name": r["project_name"],
                "sector": r["sector"],
                "ministry": r["ministry"],
                "state": r["state"],
                "district": r["district"],
                "project_size": r["project_size"],
                "original_completion_date": r["original_completion_date"],
                "revised_completion_date": r["revised_completion_date"],
                "first_seen_month": r["reporting_month"],
                "last_seen_month": r["reporting_month"]
            }
        else:
            m = project_master[pid]
            for attr in ["project_name", "sector", "ministry", "state", "original_completion_date", "revised_completion_date"]:
                if not m[attr] and r[attr]:
                    m[attr] = r[attr]
            if r["reporting_month"] < m["first_seen_month"]:
                m["first_seen_month"] = r["reporting_month"]
            if r["reporting_month"] > m["last_seen_month"]:
                m["last_seen_month"] = r["reporting_month"]

    # Write projects.csv
    projects_csv_path = os.path.join(output_dir, "projects.csv")
    projects_fields = [
        "project_id", "project_name", "sector", "ministry", "state", "district",
        "project_size", "original_completion_date", "revised_completion_date",
        "first_seen_month", "last_seen_month"
    ]
    with open(projects_csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=projects_fields)
        writer.writeheader()
        for p in project_master.values():
            writer.writerow(p)
    print(f"Wrote {len(project_master):,} unique projects -> {projects_csv_path}")

    # Recalculate project_coverage.csv from project_monthly.csv ONLY
    coverage_rows = []
    for pid, pdf in df_canonical.groupby("project_id"):
        obs_cnt = pdf["reporting_month"].nunique()
        total_raw = int(pdf["duplicate_raw_record_count"].sum())
        ratio = round(total_raw / obs_cnt, 2)
        pname = max([n for n in pdf["project_name"] if n], key=len, default="")
        sec = next((s for s in pdf["sector"] if s), "")
        minis = next((m for m in pdf["ministry"] if m), "")
        st = next((s for s in pdf["state"] if s), "")
        f_obs = pdf["reporting_month"].min()
        l_obs = pdf["reporting_month"].max()
        
        coverage_rows.append({
            "project_id": pid,
            "project_name": pname,
            "sector": sec,
            "ministry": minis,
            "state": st,
            "first_observation": f_obs,
            "last_observation": l_obs,
            "observation_count": obs_cnt,
            "total_raw_records": total_raw,
            "raw_to_canonical_ratio": ratio
        })

    df_coverage = pd.DataFrame(coverage_rows)
    # STRICT ASSERTION: observation_count == number of unique reporting_month values
    assert (df_coverage["observation_count"] == df_canonical.groupby("project_id")["reporting_month"].nunique().loc[df_coverage["project_id"]].values).all()

    # Sort coverage descending by observation_count, then by raw_to_canonical_ratio
    df_coverage.sort_values(by=["observation_count", "raw_to_canonical_ratio"], ascending=[False, False], inplace=True)
    coverage_csv_path = os.path.join(output_dir, "project_coverage.csv")
    df_coverage.to_csv(coverage_csv_path, index=False, encoding="utf-8")
    print(f"Wrote longitudinal coverage for {len(df_coverage):,} projects -> {coverage_csv_path}")

    # Write extraction_quality.csv
    quality_csv_path = os.path.join(output_dir, "extraction_quality.csv")
    quality_fields = [
        "source_pdf", "pages", "text_extracted", "tables_detected",
        "projects_detected", "reporting_month_detected", "ocr_used",
        "extraction_status", "confidence"
    ]
    with open(quality_csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=quality_fields)
        writer.writeheader()
        for q in all_quality_records:
            writer.writerow(q)

    # Write extraction_errors.csv
    errors_csv_path = os.path.join(output_dir, "extraction_errors.csv")
    errors_fields = ["source_pdf", "page", "error_type", "error_message"]
    with open(errors_csv_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=errors_fields)
        writer.writeheader()
        for err in all_error_records:
            writer.writerow(err)

    # Print summary metrics requested
    total_raw = len(raw_extractions)
    canonical_obs = len(canonical_records)
    dups_removed = total_raw - canonical_obs
    unique_projects = len(df_coverage)

    print("=" * 90)
    print("VIGIL CANONICAL DATASET INTEGRITY REPORT")
    print("=" * 90)
    print(f"Total raw extracted records: {total_raw:,}")
    print(f"Canonical project-month observations: {canonical_obs:,}")
    print(f"Duplicates removed/merged: {dups_removed:,}")
    print(f"Unique projects: {unique_projects:,}")
    print("=" * 90)

    print("\nTOP 20 PROJECTS WITH HIGHEST RAW-TO-CANONICAL DUPLICATION RATIO:")
    top_dup = df_coverage.sort_values(by="raw_to_canonical_ratio", ascending=False).head(20)
    print(f"{'Project ID':<16} | {'Obs':<4} | {'Raw':<5} | {'Ratio':<5} | {'Project Name'}")
    print("-" * 80)
    for _, row in top_dup.iterrows():
        print(f"{row['project_id']:<16} | {row['observation_count']:<4} | {row['total_raw_records']:<5} | {row['raw_to_canonical_ratio']:<5.1f} | {str(row['project_name'])[:45]}")

    print("\nPROJECT OBSERVATION DENSITY BREAKDOWN:")
    cnt_1 = (df_coverage['observation_count'] == 1).sum()
    cnt_2 = (df_coverage['observation_count'] == 2).sum()
    cnt_3_5 = ((df_coverage['observation_count'] >= 3) & (df_coverage['observation_count'] <= 5)).sum()
    cnt_6_12 = ((df_coverage['observation_count'] >= 6) & (df_coverage['observation_count'] <= 12)).sum()
    cnt_12_plus = (df_coverage['observation_count'] > 12).sum()

    print(f"Projects with 1 observation       : {cnt_1:,} ({cnt_1/unique_projects*100:.1f}%)")
    print(f"Projects with 2 observations      : {cnt_2:,} ({cnt_2/unique_projects*100:.1f}%)")
    print(f"Projects with 3–5 observations    : {cnt_3_5:,} ({cnt_3_5/unique_projects*100:.1f}%)")
    print(f"Projects with 6–12 observations   : {cnt_6_12:,} ({cnt_6_12/unique_projects*100:.1f}%)")
    print(f"Projects with 12+ observations    : {cnt_12_plus:,} ({cnt_12_plus/unique_projects*100:.1f}%)")

    print("\nCANONICAL INTEGRITY ASSERTION:")
    print("assert not project_monthly.duplicated(['project_id', 'reporting_month']).any() -> PASSED ✓")
    print(f"Extraction Pipeline completed in {time.time() - pipeline_start:.1f} seconds total!")
    print("=" * 90)

if __name__ == "__main__":
    main()
