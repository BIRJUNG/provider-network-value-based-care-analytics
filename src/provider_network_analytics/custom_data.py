from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .data_generation import GeneratedDataset, _geo_variation, _provider_year, _services


ALIASES = {
    "provider_id": ["provider_id", "npi", "billing_provider_id"],
    "provider_name": ["provider_name", "provider", "organization_name"],
    "specialty_group": ["specialty_group", "specialty", "taxonomy_group"],
    "provider_type": ["provider_type", "entity_type", "facility_type"],
    "state_code": ["state_code", "state"],
    "market": ["market", "city", "county", "region"],
    "beneficiary_count": ["beneficiary_count", "beneficiaries", "bene_count", "assigned_beneficiaries"],
    "service_count": ["service_count", "services", "visits", "utilization_count"],
    "medicare_payment_amount": ["medicare_payment_amount", "payment_amount", "paid_amount", "total_payment"],
    "allowed_amount": ["allowed_amount", "allowed", "contracted_amount"],
    "quality_score": ["quality_score", "quality", "star_score"],
    "readmission_rate": ["readmission_rate", "readmit_rate"],
    "aco_name": ["aco_name", "aco", "organization"],
    "aco_quality_score": ["aco_quality_score", "aco_quality", "mssp_quality_score"],
    "aco_savings_rate": ["aco_savings_rate", "savings_rate", "shared_savings_rate"],
}


def load_custom_provider_utilization(path: Path, performance_year: int = 2025) -> GeneratedDataset:
    raw = pd.read_csv(path)
    data = _canonicalize(raw)
    if data.empty:
        raise ValueError("Custom provider utilization CSV has no rows.")
    data = _fill_defaults(data)
    dim_geography = _geographies(data)
    dim_provider = _providers(data, dim_geography)
    dim_service = _services()
    utilization = _utilization(data, dim_provider, dim_service, dim_geography, performance_year)
    provider_year = _provider_year(utilization, dim_provider)
    dim_facility = _facilities(data, dim_geography)
    hospital_quality = _hospital_quality(dim_facility, data, performance_year)
    dim_aco = _acos(data, dim_geography, performance_year)
    aco_performance = _aco_performance(dim_aco, data, performance_year)
    rng = np.random.default_rng(2025)
    geo_variation = _geo_variation(rng, dim_geography, utilization, hospital_quality, performance_year)
    return GeneratedDataset(
        dim_provider=dim_provider,
        dim_facility=dim_facility,
        dim_geography=dim_geography,
        dim_service=dim_service,
        dim_aco=dim_aco,
        fact_provider_service_utilization=utilization,
        fact_provider_year=provider_year,
        fact_hospital_quality=hospital_quality,
        fact_aco_performance=aco_performance,
        fact_geo_variation=geo_variation,
    )


def _canonicalize(raw: pd.DataFrame) -> pd.DataFrame:
    normalized = {str(col).strip().lower().replace(" ", "_"): col for col in raw.columns}
    out = pd.DataFrame(index=raw.index)
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                out[canonical] = raw[normalized[alias]]
                break
    return out


def _fill_defaults(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    n = len(result)
    defaults = {
        "provider_id": [f"CUSTOM_NPI_{i + 1:05d}" for i in range(n)],
        "provider_name": "Custom Provider",
        "specialty_group": "Primary care",
        "provider_type": "Professional",
        "state_code": "US",
        "market": "Custom Market",
        "beneficiary_count": 250,
        "service_count": 1200,
        "medicare_payment_amount": 250000.0,
        "allowed_amount": 310000.0,
        "quality_score": 78.0,
        "readmission_rate": 0.10,
        "aco_name": "Custom ACO",
        "aco_quality_score": 86.0,
        "aco_savings_rate": 0.01,
    }
    for col, default in defaults.items():
        if col not in result.columns:
            result[col] = default
    numeric = ["beneficiary_count", "service_count", "medicare_payment_amount", "allowed_amount", "quality_score", "readmission_rate", "aco_quality_score", "aco_savings_rate"]
    for col in numeric:
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(defaults[col]).clip(lower=0)
    result["quality_score"] = result["quality_score"].clip(0, 100)
    result["aco_quality_score"] = result["aco_quality_score"].clip(0, 100)
    result["readmission_rate"] = result["readmission_rate"].clip(0, 1)
    return result


def _geographies(data: pd.DataFrame) -> pd.DataFrame:
    geo = data[["state_code", "market"]].drop_duplicates().reset_index(drop=True)
    geo["geo_key"] = np.arange(1, len(geo) + 1)
    geo["region"] = "Custom"
    geo["per_capita_cost_benchmark"] = 12000.0
    geo["risk_score"] = 1.0
    geo["provider_density"] = np.clip(data.groupby(["state_code", "market"])["provider_id"].transform("nunique").groupby([data["state_code"], data["market"]]).first().to_numpy() / 10, 0.5, 5)
    geo["sdoh_risk_index"] = 0.45
    return geo[["geo_key", "state_code", "market", "region", "per_capita_cost_benchmark", "risk_score", "provider_density", "sdoh_risk_index"]]


def _providers(data: pd.DataFrame, geos: pd.DataFrame) -> pd.DataFrame:
    grouped = data.groupby("provider_id", as_index=False).agg(
        provider_name=("provider_name", "first"),
        specialty_group=("specialty_group", "first"),
        provider_type=("provider_type", "first"),
        state_code=("state_code", "first"),
        market=("market", "first"),
        quality_score=("quality_score", "mean"),
        readmission_rate=("readmission_rate", "mean"),
    )
    geo_key = {(r.state_code, r.market): r.geo_key for r in geos.itertuples(index=False)}
    grouped["provider_key"] = np.arange(1, len(grouped) + 1)
    grouped["geo_key"] = [geo_key[(r.state_code, r.market)] for r in grouped.itertuples(index=False)]
    grouped["entity_type"] = np.where(grouped["provider_type"].astype(str).str.contains("hospital|facility", case=False), "Organization", "Individual")
    grouped["network_tier"] = "Standard"
    return grouped[
        ["provider_key", "provider_id", "provider_name", "specialty_group", "provider_type", "entity_type", "geo_key", "state_code", "market", "network_tier", "quality_score", "readmission_rate"]
    ]


def _utilization(data: pd.DataFrame, providers: pd.DataFrame, services: pd.DataFrame, geos: pd.DataFrame, performance_year: int) -> pd.DataFrame:
    provider_key = dict(zip(providers["provider_id"], providers["provider_key"]))
    geo_key = {(r.state_code, r.market): r.geo_key for r in geos.itertuples(index=False)}
    rows = []
    for row in data.itertuples(index=False):
        service_key = 1
        rows.append(
            {
                "provider_key": provider_key[row.provider_id],
                "service_key": service_key,
                "geo_key": geo_key[(row.state_code, row.market)],
                "performance_year": performance_year,
                "beneficiary_count": int(row.beneficiary_count),
                "service_count": int(row.service_count),
                "submitted_charge_amount": round(float(row.allowed_amount) * 1.55, 2),
                "allowed_amount": round(float(row.allowed_amount), 2),
                "medicare_payment_amount": round(float(row.medicare_payment_amount), 2),
                "payment_per_service": round(float(row.medicare_payment_amount) / max(float(row.service_count), 1), 2),
                "payment_per_beneficiary": round(float(row.medicare_payment_amount) / max(float(row.beneficiary_count), 1), 2),
            }
        )
    return pd.DataFrame(rows)


def _facilities(data: pd.DataFrame, geos: pd.DataFrame) -> pd.DataFrame:
    facilities = data[data["provider_type"].astype(str).str.contains("hospital|facility", case=False)].copy()
    if facilities.empty:
        facilities = data.head(min(3, len(data))).copy()
    geo_key = {(r.state_code, r.market): r.geo_key for r in geos.itertuples(index=False)}
    facilities = facilities.drop_duplicates("provider_id").reset_index(drop=True)
    return pd.DataFrame(
        {
            "facility_key": np.arange(1, len(facilities) + 1),
            "ccn": [f"CUSTOM_CCN_{i + 1:04d}" for i in range(len(facilities))],
            "facility_name": facilities["provider_name"].to_numpy(),
            "facility_type": "Custom facility",
            "ownership_type": "Unknown",
            "geo_key": [geo_key[(r.state_code, r.market)] for r in facilities.itertuples(index=False)],
            "state_code": facilities["state_code"].to_numpy(),
            "market": facilities["market"].to_numpy(),
            "beds": 120,
            "emergency_services_flag": 1,
        }
    )


def _hospital_quality(facilities: pd.DataFrame, data: pd.DataFrame, performance_year: int) -> pd.DataFrame:
    quality_lookup = data.groupby("provider_name")["quality_score"].mean().to_dict()
    score = facilities["facility_name"].map(quality_lookup).fillna(78) / 20
    readmit = 5 - data.groupby("provider_name")["readmission_rate"].mean().reindex(facilities["facility_name"]).fillna(0.10).to_numpy() * 10
    composite = 0.30 * score + 0.25 * readmit + 0.20 * score + 0.15 * score + 0.10 * score
    return facilities[["facility_key", "geo_key", "state_code", "market"]].assign(
        performance_year=performance_year,
        overall_star_rating=score.round(2),
        readmission_score=np.clip(readmit, 1, 5).round(2),
        mortality_score=score.round(2),
        patient_experience_score=score.round(2),
        safety_score=score.round(2),
        quality_composite_score=np.clip(composite, 1, 5).round(3),
    )


def _acos(data: pd.DataFrame, geos: pd.DataFrame, performance_year: int) -> pd.DataFrame:
    grouped = data.groupby("aco_name", as_index=False).agg(state_code=("state_code", "first"), market=("market", "first"), assigned_beneficiaries=("beneficiary_count", "sum"))
    geo_key = {(r.state_code, r.market): r.geo_key for r in geos.itertuples(index=False)}
    grouped["aco_key"] = np.arange(1, len(grouped) + 1)
    grouped["aco_id"] = [f"CUSTOM_ACO_{i + 1:04d}" for i in range(len(grouped))]
    grouped["performance_year"] = performance_year
    grouped["geo_key"] = [geo_key[(r.state_code, r.market)] for r in grouped.itertuples(index=False)]
    grouped["risk_model"] = "Custom"
    return grouped[["aco_key", "aco_id", "aco_name", "performance_year", "geo_key", "state_code", "market", "assigned_beneficiaries", "risk_model"]]


def _aco_performance(acos: pd.DataFrame, data: pd.DataFrame, performance_year: int) -> pd.DataFrame:
    aco_metrics = data.groupby("aco_name", as_index=False).agg(quality_score=("aco_quality_score", "mean"), savings_rate=("aco_savings_rate", "mean"))
    perf = acos.merge(aco_metrics, on="aco_name", how="left")
    benchmark = perf["assigned_beneficiaries"] * 12000
    actual = benchmark * (1 - perf["savings_rate"])
    gross = benchmark - actual
    earned = np.where(gross > 0, gross * 0.45, 0)
    return perf[["aco_key", "geo_key", "performance_year", "assigned_beneficiaries"]].assign(
        benchmark_expenditure=benchmark.round(2),
        actual_expenditure=actual.round(2),
        gross_savings_losses=gross.round(2),
        earned_shared_savings=earned.round(2),
        quality_score=perf["quality_score"].round(2),
        savings_rate=perf["savings_rate"].round(4),
    )

