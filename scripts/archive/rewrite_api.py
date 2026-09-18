import re

with open("sanket/api.py", "r") as f:
    content = f.read()

# 1. Rewrite get_project_details
old_details = """def get_project_details(project_id: str) -> Dict[str, Any]:
    \"\"\"
    Retrieve project metadata, latest point-in-time prediction,
    latest trajectory metrics, current risk tier, and top explanations.
    \"\"\"
    ctx = get_app_context()
    try:
        rep = get_project_replay(project_id, dataset_path=ctx["dataset_path"], engine=get_lazy_engine(ctx))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    if not rep["timeline"]:
        raise HTTPException(status_code=404, detail=f"No timeline observations for project '{project_id}'.")

    latest_rec = rep["timeline"][-1]

    response = {
        "project_id": rep["project_id"],
        "project_name": rep["project_name"],
        "sector": rep["sector"],
        "ministry": rep["ministry"],
        "state": rep["state"],
        "approved_cost": rep["approved_cost"],
        "total_observations": rep["total_observations"],
        "start_month": rep["start_month"],
        "end_month": rep["end_month"],
        "latest_observation": latest_rec["reporting_month"],
        "latest_prediction": {
            "raw_prob": latest_rec["raw_prob"],
            "pred_prob": latest_rec["pred_prob"],
            "risk_tier": latest_rec["risk_tier"],
            "alert": latest_rec["alert"]
        },
        "current_trajectory_metrics": {
            "C_base": latest_rec["C_base"],
            "expenditure": latest_rec["expenditure"],
            "financial_progress": latest_rec["financial_progress"],
            "schedule_deviation_months": latest_rec["schedule_deviation_months"],
            "V_fin_1m": latest_rec["V_fin_1m"],
            "V_fin_3m": latest_rec["V_fin_3m"],
            "A_fin": latest_rec["A_fin"],
            "EWMA_V_fin": latest_rec["EWMA_V_fin"],
            "Z_peer_V_fin": latest_rec["Z_peer_V_fin"],
            "trajectory_risk_score": latest_rec["trajectory_risk_score"]
        },
        "current_risk_tier": latest_rec["risk_tier"],
        "top_explanations": latest_rec["top_explanations"]
    }
    return sanitize_for_json(response)"""

new_details = """def get_project_details(project_id: str) -> Dict[str, Any]:
    \"\"\"
    Retrieve project metadata, latest point-in-time prediction,
    latest trajectory metrics, current risk tier, and top explanations.
    Optimized to use precomputed portfolio state where possible to avoid massive parquet reads.
    \"\"\"
    ctx = get_app_context()
    df = ctx.get("genuine_df")
    
    if df is None or project_id not in df["project_id"].values:
        # True fallback if completely unknown
        try:
            rep = get_project_replay(project_id, dataset_path=ctx["dataset_path"], engine=get_lazy_engine(ctx))
            if not rep["timeline"]:
                raise HTTPException(status_code=404, detail=f"No timeline observations for project '{project_id}'.")
            latest_rec = rep["timeline"][-1]
            return sanitize_for_json({
                "project_id": rep["project_id"],
                "project_name": rep["project_name"],
                "sector": rep["sector"],
                "ministry": rep["ministry"],
                "state": rep["state"],
                "approved_cost": rep["approved_cost"],
                "total_observations": rep["total_observations"],
                "start_month": rep["start_month"],
                "end_month": rep["end_month"],
                "latest_observation": latest_rec["reporting_month"],
                "latest_prediction": {
                    "raw_prob": latest_rec["raw_prob"],
                    "pred_prob": latest_rec["pred_prob"],
                    "risk_tier": latest_rec["risk_tier"],
                    "alert": latest_rec["alert"]
                },
                "current_trajectory_metrics": {
                    "C_base": latest_rec["C_base"],
                    "expenditure": latest_rec["expenditure"],
                    "financial_progress": latest_rec["financial_progress"],
                    "schedule_deviation_months": latest_rec["schedule_deviation_months"],
                    "V_fin_1m": latest_rec.get("V_fin_1m"),
                    "V_fin_3m": latest_rec.get("V_fin_3m"),
                    "A_fin": latest_rec.get("A_fin"),
                    "EWMA_V_fin": latest_rec.get("EWMA_V_fin"),
                    "Z_peer_V_fin": latest_rec.get("Z_peer_V_fin"),
                    "trajectory_risk_score": latest_rec.get("trajectory_risk_score")
                },
                "current_risk_tier": latest_rec["risk_tier"],
                "top_explanations": latest_rec.get("top_explanations", [])
            })
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
            
    # Extract from memory (zero parquet overhead!)
    row = df[df["project_id"] == str(project_id)]
    rec = row.iloc[0]
    
    from sanket.inference import predict_point_in_time
    engine = get_lazy_engine(ctx)
    pred = predict_point_in_time(row, engine)
    
    return sanitize_for_json({
        "project_id": str(rec["project_id"]),
        "project_name": str(rec.get("project_name", rec["project_id"])),
        "sector": str(rec.get("sector_display", rec.get("sector_clean", "OTHER"))),
        "ministry": str(rec.get("ministry", "—")),
        "state": str(rec.get("state", "—")),
        "approved_cost": float(rec.get("approved_cost", 0.0)),
        "total_observations": int(rec.get("observation_number", 1)),
        "start_month": "Unknown", # Static fallback
        "end_month": str(rec.get("reporting_month", "")),
        "latest_observation": str(rec.get("reporting_month", "")),
        "latest_prediction": {
            "raw_prob": pred["raw_prob"],
            "pred_prob": pred["pred_prob"],
            "risk_tier": pred["risk_tier"],
            "alert": pred["alert"]
        },
        "current_trajectory_metrics": {
            "C_base": float(rec.get("C_base", 0.0)),
            "expenditure": float(rec.get("expenditure", 0.0)),
            "financial_progress": float(rec.get("financial_progress", 0.0)),
            "schedule_deviation_months": float(rec.get("schedule_deviation_months", 0.0)),
            "V_fin_1m": float(rec.get("V_fin_1m", 0.0)),
            "V_fin_3m": float(rec.get("V_fin_3m", 0.0)),
            "A_fin": float(rec.get("A_fin", 0.0)),
            "EWMA_V_fin": float(rec.get("EWMA_V_fin", 0.0)),
            "Z_peer_V_fin": float(rec.get("Z_peer_V_fin", 0.0)),
            "trajectory_risk_score": float(rec.get("trajectory_risk_score", 0.0))
        },
        "current_risk_tier": pred["risk_tier"],
        "top_explanations": pred["top_explanations"]
    })"""

content = content.replace(old_details, new_details)

# 2. Rewrite fallback in AI brief
old_ai_fallback = """    except Exception:
        # Fallback to historical archive
        try:
            rep = get_project_replay(project_id, dataset_path=ctx["dataset_path"], engine=get_lazy_engine(ctx))
            status_info = {}
            warnings = []
            audit_events = []
            if not rep["timeline"]:
                raise ValueError("No timeline")
            latest_rec = rep["timeline"][-1]
            
            context = {
                "project_id": project_id,
                "name": rep["project_name"],
                "sector": rep["sector"],
                "state": rep["state"],
                "ministry": rep["ministry"],
                "approved_cost_cr": rep["approved_cost"],
                "latest_observation_month": latest_rec.get("reporting_month"),
                "total_observations": rep["total_observations"],
                "operational_status": "HISTORICAL",
                "trajectory": {
                    "C_base": safe_val(latest_rec.get("C_base")),
                    "expenditure": safe_val(latest_rec.get("expenditure")),
                    "financial_progress": safe_val(latest_rec.get("financial_progress")),
                    "schedule_deviation_months": safe_val(latest_rec.get("schedule_deviation_months"))
                },
                "model_risk": {
                    "calibrated_probability": safe_val(latest_rec.get("pred_prob")),
                    "risk_tier": safe_val(latest_rec.get("risk_tier")),
                    "top_drivers": latest_rec.get("top_explanations", [])
                },
                "warnings": warnings,
                "audit_events": audit_events
            }
        except Exception:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found in monitoring DB or archive.")"""

new_ai_fallback = """    except Exception:
        # Fallback to historical/genuine dataframe (no heavy parquet reading!)
        df = ctx.get("genuine_df")
        if df is None or project_id not in df["project_id"].values:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found in monitoring DB or archive.")
            
        row = df[df["project_id"] == str(project_id)]
        rec = row.iloc[0]
        
        from sanket.inference import predict_point_in_time
        engine = get_lazy_engine(ctx)
        pred = predict_point_in_time(row, engine)
        
        status_info = {}
        warnings = []
        audit_events = []
        
        context = {
            "project_id": str(project_id),
            "name": str(rec.get("project_name", project_id)),
            "sector": str(rec.get("sector_display", rec.get("sector", "OTHER"))),
            "state": str(rec.get("state", "—")),
            "ministry": str(rec.get("ministry", "—")),
            "approved_cost_cr": float(rec.get("approved_cost", 0.0)),
            "latest_observation_month": str(rec.get("reporting_month", "")),
            "total_observations": int(rec.get("observation_number", 1)),
            "operational_status": "HISTORICAL",
            "trajectory": {
                "C_base": safe_val(rec.get("C_base")),
                "expenditure": safe_val(rec.get("expenditure")),
                "financial_progress": safe_val(rec.get("financial_progress")),
                "schedule_deviation_months": safe_val(rec.get("schedule_deviation_months"))
            },
            "model_risk": {
                "calibrated_probability": safe_val(pred.get("pred_prob")),
                "risk_tier": safe_val(pred.get("risk_tier")),
                "top_drivers": pred.get("top_explanations", [])
            },
            "warnings": warnings,
            "audit_events": audit_events
        }"""

content = content.replace(old_ai_fallback, new_ai_fallback)

with open("sanket/api.py", "w") as f:
    f.write(content)

