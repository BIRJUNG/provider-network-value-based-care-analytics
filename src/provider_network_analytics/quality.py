from __future__ import annotations

import pandas as pd


def run_quality_checks(
    base_tables: dict[str, pd.DataFrame],
    marts: dict[str, pd.DataFrame],
    score_metrics: dict[str, dict[str, object]],
) -> pd.DataFrame:
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, value: object, threshold: str) -> None:
        checks.append({"check_name": name, "status": "PASS" if passed else "FAIL", "value": value, "threshold": threshold})

    provider = base_tables["dim_provider"]
    util = base_tables["fact_provider_service_utilization"]
    facility = base_tables["dim_facility"]
    aco = base_tables["dim_aco"]
    geo = base_tables["dim_geography"]

    add("provider_rows_positive", len(provider) > 0, len(provider), "> 0")
    add("provider_id_unique", provider["provider_id"].is_unique, int(provider["provider_id"].nunique()), "unique")
    add("provider_geo_integrity", provider["geo_key"].isin(geo["geo_key"]).all(), int(provider["geo_key"].isna().sum()), "all providers map to geography")
    add("utilization_rows_positive", len(util) > 0, len(util), "> 0")
    add("payment_non_negative", (util["medicare_payment_amount"] >= 0).all(), float(util["medicare_payment_amount"].min()), ">= 0")
    add("beneficiary_count_positive", (util["beneficiary_count"] > 0).all(), int((util["beneficiary_count"] <= 0).sum()), "no zero/negative beneficiaries")
    add("service_count_positive", (util["service_count"] > 0).all(), int((util["service_count"] <= 0).sum()), "no zero/negative services")
    add("facility_rows_positive", len(facility) > 0, len(facility), "> 0")
    add("aco_rows_positive", len(aco) > 0, len(aco), "> 0")
    for name, frame in marts.items():
        add(f"{name}_not_empty", not frame.empty, len(frame), "> 0 rows")
    add("provider_anomaly_score_ready", score_metrics.get("provider_anomaly_model", {}).get("rows", 0) > 0, score_metrics.get("provider_anomaly_model", {}).get("rows", 0), "> 0 rows")
    add("contracting_score_ready", score_metrics.get("contracting_opportunity_score", {}).get("rows", 0) > 0, score_metrics.get("contracting_opportunity_score", {}).get("rows", 0), "> 0 rows")
    return pd.DataFrame(checks)

