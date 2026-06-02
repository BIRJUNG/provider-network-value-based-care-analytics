from __future__ import annotations

import numpy as np
import pandas as pd


def build_marts(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    provider = _provider_peer_benchmark(tables)
    hospital = _hospital_quality_scorecard(tables)
    aco = _aco_performance(tables)
    market = _market_opportunity(tables, hospital)
    contracting = _contracting_opportunity(provider, market)
    outlier = _provider_outlier_queue(provider)
    return {
        "mart_provider_peer_benchmark": provider,
        "mart_hospital_quality_scorecard": hospital,
        "mart_aco_performance": aco,
        "mart_market_opportunity": market,
        "mart_contracting_opportunity": contracting,
        "mart_provider_outlier_queue": outlier,
    }


def _provider_peer_benchmark(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    fact = tables["fact_provider_year"]
    provider = tables["dim_provider"]
    geo = tables["dim_geography"][
        ["geo_key", "region", "per_capita_cost_benchmark", "risk_score", "provider_density", "sdoh_risk_index"]
    ]
    provider_attrs = provider.drop(columns=["specialty_group", "state_code", "geo_key", "quality_score", "readmission_rate"])
    mart = fact.merge(provider_attrs, on="provider_key", how="left").merge(geo, on="geo_key", how="left")
    mart["peer_cost_percentile"] = mart.groupby(["specialty_group", "state_code"])["payment_per_beneficiary"].rank(pct=True)
    mart["peer_utilization_percentile"] = mart.groupby(["specialty_group", "state_code"])["services_per_beneficiary"].rank(pct=True)
    mart["quality_percentile"] = mart["quality_score"].rank(pct=True)
    mart["readmission_percentile"] = mart["readmission_rate"].rank(pct=True)
    mart["provider_outlier_score"] = (
        0.36 * mart["peer_cost_percentile"]
        + 0.27 * mart["peer_utilization_percentile"]
        + 0.18 * mart["readmission_percentile"]
        + 0.19 * (1 - mart["quality_percentile"])
    )
    mart["performance_tier"] = pd.cut(mart["provider_outlier_score"], bins=[0, 0.45, 0.70, 0.88, 1.01], labels=["Efficient", "Standard", "Watchlist", "Intervention"], include_lowest=True)
    mart["recommended_action"] = np.select(
        [
            mart["provider_outlier_score"] >= 0.88,
            mart["peer_cost_percentile"] >= 0.90,
            mart["quality_score"] < 65,
            mart["readmission_rate"] > 0.16,
        ],
        ["Provider relations and contracting review", "Peer cost benchmark discussion", "Quality improvement plan", "Readmission reduction workflow"],
        default="Monitor provider trend",
    )
    return mart.sort_values("provider_outlier_score", ascending=False)


def _hospital_quality_scorecard(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    mart = tables["fact_hospital_quality"].merge(tables["dim_facility"], on=["facility_key", "geo_key", "state_code", "market"], how="left")
    mart["quality_tier"] = pd.cut(mart["quality_composite_score"], bins=[0, 2.3, 3.2, 4.1, 5.1], labels=["Network intervention", "Watchlist", "Standard", "Preferred"], include_lowest=True)
    mart["network_action"] = np.select(
        [mart["quality_composite_score"] < 2.3, mart["readmission_score"] < 2.5, mart["quality_composite_score"] >= 4.1],
        ["Review contract and quality improvement plan", "Readmission performance discussion", "Preferred steering candidate"],
        default="Monitor quality trend",
    )
    return mart.sort_values("quality_composite_score")


def _aco_performance(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    mart = tables["fact_aco_performance"].merge(tables["dim_aco"], on=["aco_key", "geo_key", "performance_year", "assigned_beneficiaries"], how="left")
    mart["quality_cost_quadrant"] = np.select(
        [
            (mart["gross_savings_losses"] > 0) & (mart["quality_score"] >= 90),
            (mart["gross_savings_losses"] > 0) & (mart["quality_score"] < 90),
            (mart["gross_savings_losses"] <= 0) & (mart["quality_score"] >= 90),
        ],
        ["High quality savings", "Savings with quality opportunity", "High quality cost opportunity"],
        default="Underperforming",
    )
    mart["aco_performance_tier"] = np.select(
        [
            (mart["earned_shared_savings"] > 0) & (mart["quality_score"] >= 90),
            mart["earned_shared_savings"] > 0,
            mart["quality_score"] >= 90,
        ],
        ["Preferred VBC partner", "Savings candidate", "Quality partner needing cost support"],
        default="Performance improvement required",
    )
    return mart.sort_values(["earned_shared_savings", "quality_score"], ascending=False)


def _market_opportunity(tables: dict[str, pd.DataFrame], hospital: pd.DataFrame) -> pd.DataFrame:
    geo = tables["dim_geography"]
    variation = tables["fact_geo_variation"]
    provider_count = tables["dim_provider"].groupby("geo_key", as_index=False).agg(providers=("provider_key", "nunique"))
    quality = hospital.groupby("geo_key", as_index=False).agg(avg_hospital_quality=("quality_composite_score", "mean"))
    mart = variation.merge(geo, on="geo_key", how="left", suffixes=("", "_dim")).merge(provider_count, on="geo_key", how="left").merge(quality, on="geo_key", how="left").fillna(0)
    mart["cost_index"] = mart["per_capita_cost"].rank(pct=True)
    mart["utilization_index"] = (mart["admissions_per_1000"].rank(pct=True) + mart["ed_visits_per_1000"].rank(pct=True)) / 2
    mart["quality_gap_index"] = 1 - mart["avg_hospital_quality"].rank(pct=True)
    mart["density_gap_index"] = 1 - mart["provider_density"].rank(pct=True)
    mart["market_opportunity_score"] = 0.34 * mart["cost_index"] + 0.24 * mart["utilization_index"] + 0.22 * mart["quality_gap_index"] + 0.20 * mart["density_gap_index"]
    mart["recommended_market_action"] = np.select(
        [
            mart["market_opportunity_score"] >= 0.78,
            mart["quality_gap_index"] >= 0.70,
            mart["density_gap_index"] >= 0.70,
        ],
        ["Network strategy review and VBC expansion", "Quality intervention focus", "Network adequacy and access review"],
        default="Monitor market trend",
    )
    return mart.sort_values("market_opportunity_score", ascending=False)


def _contracting_opportunity(provider: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    market_score = market[["geo_key", "market_opportunity_score"]]
    mart = provider.merge(market_score, on="geo_key", how="left")
    mart["volume_score"] = mart["beneficiary_count"].rank(pct=True)
    mart["cost_efficiency_score"] = 1 - mart["peer_cost_percentile"]
    mart["quality_score_norm"] = mart["quality_score"].rank(pct=True)
    mart["stability_score"] = 1 - mart["readmission_rate"].rank(pct=True)
    mart["network_value_score"] = (
        0.30 * mart["volume_score"]
        + 0.25 * mart["quality_score_norm"]
        + 0.20 * mart["cost_efficiency_score"]
        + 0.15 * mart["market_opportunity_score"].fillna(0)
        + 0.10 * mart["stability_score"]
    )
    mart["opportunity_tier"] = pd.cut(mart["network_value_score"], bins=[0, 0.45, 0.65, 0.80, 1.01], labels=["Monitor", "Strategic partner", "VBC candidate", "Preferred value-based contract candidate"], include_lowest=True)
    mart["recommended_contract_action"] = np.select(
        [
            mart["network_value_score"] >= 0.80,
            (mart["peer_cost_percentile"] >= 0.90) & (mart["quality_score"] >= 80),
            mart["quality_score"] < 65,
            mart["provider_outlier_score"] >= 0.88,
        ],
        ["Preferred value-based contract candidate", "Negotiate performance guarantee", "Quality improvement plan", "Provider education and utilization review"],
        default="Monitor only",
    )
    return mart.sort_values("network_value_score", ascending=False)


def _provider_outlier_queue(provider: pd.DataFrame) -> pd.DataFrame:
    queue = provider[provider["provider_outlier_score"] >= provider["provider_outlier_score"].quantile(0.82)].copy()
    fields = [
        "provider_id",
        "provider_name",
        "specialty_group",
        "state_code",
        "market",
        "payment_per_beneficiary",
        "services_per_beneficiary",
        "quality_score",
        "readmission_rate",
        "provider_outlier_score",
        "performance_tier",
        "recommended_action",
    ]
    return queue[fields].sort_values("provider_outlier_score", ascending=False)
