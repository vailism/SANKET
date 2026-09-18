import json
import pandas as pd

def test_static_portfolio_metrics_exact_match():
    with open("DATA/portfolio_metrics.json", "r") as f:
        data = json.load(f)

    metrics = data["metrics"]

    # 5. Preserve exact existing portfolio outputs:
    # 2,390 active genuine projects (353-PDF Baseline Snapshot)
    assert metrics["active_project_count"] == 2390
    # 4,656 genuine projects
    assert metrics["genuine_project_count"] == 4656
    # 2,266 historical genuine projects
    assert metrics["historical_project_count"] == 2266

    # ₹54,66,819.25 Cr active baseline exposure
    assert abs(metrics["active_baseline_exposure"] - 5466819.25) < 0.1
    # ₹24,29,427.17 Cr risk-weighted exposure
    assert abs(metrics["risk_weighted_exposure"] - 2429427.17) < 0.1

    # risk tiers (353-PDF baseline)
    assert metrics["normal_count"] == 504
    assert metrics["watch_count"] == 386
    assert metrics["review_count"] == 135
    assert metrics["escalate_count"] == 1365

def test_static_portfolio_parquet_counts():
    active_df = pd.read_parquet("DATA/portfolio_active.parquet")
    assert len(active_df) == 2390

    historical_df = pd.read_parquet("DATA/portfolio_historical.parquet")
    assert len(historical_df) == 2266

    genuine_df = pd.read_parquet("DATA/portfolio_genuine.parquet")
    assert len(genuine_df) == 4656
