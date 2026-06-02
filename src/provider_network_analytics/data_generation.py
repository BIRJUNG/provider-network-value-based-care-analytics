from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class GeneratedDataset:
    dim_provider: pd.DataFrame
    dim_facility: pd.DataFrame
    dim_geography: pd.DataFrame
    dim_service: pd.DataFrame
    dim_aco: pd.DataFrame
    fact_provider_service_utilization: pd.DataFrame
    fact_provider_year: pd.DataFrame
    fact_hospital_quality: pd.DataFrame
    fact_aco_performance: pd.DataFrame
    fact_geo_variation: pd.DataFrame

    def as_tables(self) -> dict[str, pd.DataFrame]:
        return {
            "dim_provider": self.dim_provider,
            "dim_facility": self.dim_facility,
            "dim_geography": self.dim_geography,
            "dim_service": self.dim_service,
            "dim_aco": self.dim_aco,
            "fact_provider_service_utilization": self.fact_provider_service_utilization,
            "fact_provider_year": self.fact_provider_year,
            "fact_hospital_quality": self.fact_hospital_quality,
            "fact_aco_performance": self.fact_aco_performance,
            "fact_geo_variation": self.fact_geo_variation,
        }


STATES = ["CA", "TX", "FL", "NY", "PA", "OH", "GA", "NC", "MI", "AZ", "IL", "WA"]
REGIONS = ["West", "South", "Northeast", "Midwest"]
SPECIALTIES = ["Primary care", "Cardiology", "Orthopedics", "Emergency medicine", "Radiology", "Oncology", "Behavioral health", "Surgery", "Facility", "DME/supplier"]
SERVICES = [
    ("99213", "Office visit", "Evaluation management"),
    ("99214", "Complex office visit", "Evaluation management"),
    ("93000", "EKG", "Cardiology"),
    ("27447", "Joint replacement", "Orthopedics"),
    ("71046", "Chest imaging", "Imaging"),
    ("70553", "MRI brain", "Imaging"),
    ("77301", "Radiation therapy", "Oncology"),
    ("90834", "Psychotherapy", "Behavioral health"),
    ("A0428", "Ambulance transport", "DME/supplier"),
    ("99285", "Emergency visit", "Emergency medicine"),
]


def generate_dataset(
    seed: int = 42,
    provider_count: int = 640,
    facility_count: int = 120,
    aco_count: int = 64,
    market_count: int = 34,
    performance_year: int = 2025,
) -> GeneratedDataset:
    rng = np.random.default_rng(seed)
    dim_geography = _geographies(rng, market_count)
    dim_provider = _providers(rng, provider_count, dim_geography)
    dim_facility = _facilities(rng, facility_count, dim_geography)
    dim_service = _services()
    dim_aco = _acos(rng, aco_count, dim_geography, performance_year)
    utilization = _provider_service_utilization(rng, dim_provider, dim_service, dim_geography, performance_year)
    provider_year = _provider_year(utilization, dim_provider)
    hospital_quality = _hospital_quality(rng, dim_facility, dim_geography, performance_year)
    aco_performance = _aco_performance(rng, dim_aco, dim_geography, performance_year)
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


def _geographies(rng: np.random.Generator, market_count: int) -> pd.DataFrame:
    state = rng.choice(STATES, market_count)
    market = [f"{s} Market {i + 1:02d}" for i, s in enumerate(state)]
    per_capita = np.clip(rng.normal(12600, 2200, market_count), 7600, 20500)
    risk = np.clip(rng.normal(1.0, 0.14, market_count), 0.72, 1.42)
    density = np.clip(rng.normal(2.4, 0.75, market_count), 0.55, 5.4)
    sdoh = np.clip(rng.beta(2.4, 3.0, market_count), 0.05, 0.95)
    return pd.DataFrame(
        {
            "geo_key": np.arange(1, market_count + 1),
            "state_code": state,
            "market": market,
            "region": rng.choice(REGIONS, market_count),
            "per_capita_cost_benchmark": per_capita.round(2),
            "risk_score": risk.round(3),
            "provider_density": density.round(3),
            "sdoh_risk_index": sdoh.round(3),
        }
    )


def _providers(rng: np.random.Generator, provider_count: int, geos: pd.DataFrame) -> pd.DataFrame:
    specialty = rng.choice(SPECIALTIES, provider_count, p=[0.24, 0.09, 0.08, 0.08, 0.11, 0.05, 0.07, 0.09, 0.13, 0.06])
    geo_key = rng.choice(geos["geo_key"], provider_count)
    geo = geos.set_index("geo_key").loc[geo_key]
    names = [f"{spec} Network Partner {i + 1:04d}" for i, spec in enumerate(specialty)]
    quality = np.clip(rng.normal(78, 12, provider_count) + (specialty == "Primary care") * 5 - (specialty == "DME/supplier") * 4, 35, 99)
    readmission = np.clip(rng.normal(0.105, 0.035, provider_count) + (specialty == "Facility") * 0.04, 0.02, 0.28)
    return pd.DataFrame(
        {
            "provider_key": np.arange(1, provider_count + 1),
            "provider_id": [f"NPI{1000000000 + i}" for i in range(provider_count)],
            "provider_name": names,
            "specialty_group": specialty,
            "provider_type": np.where(specialty == "Facility", "Hospital", "Professional"),
            "entity_type": np.where(specialty == "Facility", "Organization", "Individual"),
            "geo_key": geo_key,
            "state_code": geo["state_code"].to_numpy(),
            "market": geo["market"].to_numpy(),
            "network_tier": rng.choice(["Preferred", "Standard", "Watchlist"], provider_count, p=[0.36, 0.52, 0.12]),
            "quality_score": quality.round(2),
            "readmission_rate": readmission.round(4),
        }
    )


def _facilities(rng: np.random.Generator, facility_count: int, geos: pd.DataFrame) -> pd.DataFrame:
    geo_key = rng.choice(geos["geo_key"], facility_count)
    geo = geos.set_index("geo_key").loc[geo_key]
    return pd.DataFrame(
        {
            "facility_key": np.arange(1, facility_count + 1),
            "ccn": [f"CCN{300000 + i}" for i in range(facility_count)],
            "facility_name": [f"Regional Medical Center {i + 1:03d}" for i in range(facility_count)],
            "facility_type": rng.choice(["Acute care hospital", "Critical access", "Specialty hospital"], facility_count, p=[0.72, 0.18, 0.10]),
            "ownership_type": rng.choice(["Non-profit", "For-profit", "Government"], facility_count, p=[0.55, 0.30, 0.15]),
            "geo_key": geo_key,
            "state_code": geo["state_code"].to_numpy(),
            "market": geo["market"].to_numpy(),
            "beds": rng.integers(35, 640, facility_count),
            "emergency_services_flag": rng.choice([0, 1], facility_count, p=[0.12, 0.88]),
        }
    )


def _services() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "service_key": np.arange(1, len(SERVICES) + 1),
            "hcpcs_code": [s[0] for s in SERVICES],
            "hcpcs_description": [s[1] for s in SERVICES],
            "service_category": [s[2] for s in SERVICES],
        }
    )


def _acos(rng: np.random.Generator, aco_count: int, geos: pd.DataFrame, performance_year: int) -> pd.DataFrame:
    geo_key = rng.choice(geos["geo_key"], aco_count)
    geo = geos.set_index("geo_key").loc[geo_key]
    assigned = rng.integers(4_800, 68_000, aco_count)
    return pd.DataFrame(
        {
            "aco_key": np.arange(1, aco_count + 1),
            "aco_id": [f"ACO{5000 + i}" for i in range(aco_count)],
            "aco_name": [f"Value Care Collaborative {i + 1:03d}" for i in range(aco_count)],
            "performance_year": performance_year,
            "geo_key": geo_key,
            "state_code": geo["state_code"].to_numpy(),
            "market": geo["market"].to_numpy(),
            "assigned_beneficiaries": assigned,
            "risk_model": rng.choice(["One-sided", "Enhanced", "Basic Track"], aco_count, p=[0.40, 0.32, 0.28]),
        }
    )


def _provider_service_utilization(
    rng: np.random.Generator,
    providers: pd.DataFrame,
    services: pd.DataFrame,
    geos: pd.DataFrame,
    performance_year: int,
) -> pd.DataFrame:
    rows = []
    service_weights = np.array([0.24, 0.18, 0.08, 0.06, 0.12, 0.08, 0.05, 0.08, 0.04, 0.07])
    base_pay = np.array([92, 138, 54, 11200, 86, 420, 980, 118, 340, 620])
    for provider in providers.itertuples(index=False):
        service_n = int(rng.integers(2, 7))
        chosen = rng.choice(services["service_key"].to_numpy(), service_n, replace=False, p=service_weights)
        for service_key in chosen:
            beneficiaries = int(np.clip(rng.lognormal(5.2, 0.65), 28, 4200))
            service_count = int(beneficiaries * rng.uniform(1.2, 6.6))
            service_idx = int(service_key) - 1
            specialty_multiplier = 1 + (provider.specialty_group in ["Cardiology", "Oncology", "Orthopedics", "Facility"]) * rng.uniform(0.35, 1.45)
            payment_per_service = base_pay[service_idx] * specialty_multiplier * rng.uniform(0.75, 1.35)
            payment = service_count * payment_per_service
            allowed = payment * rng.uniform(1.08, 1.32)
            rows.append(
                {
                    "provider_key": provider.provider_key,
                    "service_key": int(service_key),
                    "geo_key": provider.geo_key,
                    "performance_year": performance_year,
                    "beneficiary_count": beneficiaries,
                    "service_count": service_count,
                    "submitted_charge_amount": round(allowed * rng.uniform(1.25, 1.95), 2),
                    "allowed_amount": round(allowed, 2),
                    "medicare_payment_amount": round(payment, 2),
                    "payment_per_service": round(payment / max(service_count, 1), 2),
                    "payment_per_beneficiary": round(payment / max(beneficiaries, 1), 2),
                }
            )
    return pd.DataFrame(rows)


def _provider_year(utilization: pd.DataFrame, providers: pd.DataFrame) -> pd.DataFrame:
    fact = (
        utilization.groupby(["provider_key", "performance_year"], as_index=False)
        .agg(
            beneficiary_count=("beneficiary_count", "sum"),
            service_count=("service_count", "sum"),
            total_payment=("medicare_payment_amount", "sum"),
            total_allowed=("allowed_amount", "sum"),
            total_submitted=("submitted_charge_amount", "sum"),
            service_mix_count=("service_key", "nunique"),
        )
        .merge(providers[["provider_key", "specialty_group", "state_code", "geo_key", "quality_score", "readmission_rate"]], on="provider_key", how="left")
    )
    fact["payment_per_beneficiary"] = fact["total_payment"] / fact["beneficiary_count"].clip(lower=1)
    fact["services_per_beneficiary"] = fact["service_count"] / fact["beneficiary_count"].clip(lower=1)
    fact["payment_per_service"] = fact["total_payment"] / fact["service_count"].clip(lower=1)
    fact["service_concentration_index"] = 1 / fact["service_mix_count"].clip(lower=1)
    return fact


def _hospital_quality(rng: np.random.Generator, facilities: pd.DataFrame, geos: pd.DataFrame, performance_year: int) -> pd.DataFrame:
    n = len(facilities)
    star = np.clip(rng.normal(3.4, 0.9, n), 1, 5)
    readmission = np.clip(rng.normal(3.2, 0.85, n), 1, 5)
    mortality = np.clip(rng.normal(3.4, 0.7, n), 1, 5)
    experience = np.clip(rng.normal(3.5, 0.8, n), 1, 5)
    safety = np.clip(rng.normal(3.3, 0.75, n), 1, 5)
    composite = 0.30 * star + 0.25 * readmission + 0.20 * mortality + 0.15 * experience + 0.10 * safety
    return facilities[["facility_key", "geo_key", "state_code", "market"]].assign(
        performance_year=performance_year,
        overall_star_rating=star.round(2),
        readmission_score=readmission.round(2),
        mortality_score=mortality.round(2),
        patient_experience_score=experience.round(2),
        safety_score=safety.round(2),
        quality_composite_score=composite.round(3),
    )


def _aco_performance(rng: np.random.Generator, acos: pd.DataFrame, geos: pd.DataFrame, performance_year: int) -> pd.DataFrame:
    benchmark = acos["assigned_beneficiaries"].to_numpy() * rng.normal(12_200, 1_400, len(acos))
    savings_rate = np.clip(rng.normal(0.012, 0.045, len(acos)), -0.12, 0.14)
    actual = benchmark * (1 - savings_rate)
    gross = benchmark - actual
    earned = np.where(gross > 0, gross * rng.uniform(0.34, 0.58, len(acos)), 0)
    quality = np.clip(rng.normal(86, 9, len(acos)) + (savings_rate > 0) * 3, 48, 99)
    return acos[["aco_key", "geo_key", "performance_year", "assigned_beneficiaries"]].assign(
        benchmark_expenditure=benchmark.round(2),
        actual_expenditure=actual.round(2),
        gross_savings_losses=gross.round(2),
        earned_shared_savings=earned.round(2),
        quality_score=quality.round(2),
        savings_rate=savings_rate.round(4),
    )


def _geo_variation(
    rng: np.random.Generator,
    geos: pd.DataFrame,
    utilization: pd.DataFrame,
    hospital_quality: pd.DataFrame,
    performance_year: int,
) -> pd.DataFrame:
    util = utilization.groupby("geo_key", as_index=False).agg(total_payment=("medicare_payment_amount", "sum"), beneficiaries=("beneficiary_count", "sum"), services=("service_count", "sum"))
    quality = hospital_quality.groupby("geo_key", as_index=False).agg(avg_quality=("quality_composite_score", "mean"))
    fact = geos.merge(util, on="geo_key", how="left").merge(quality, on="geo_key", how="left").fillna(0)
    fact["performance_year"] = performance_year
    fact["per_capita_cost"] = fact["total_payment"] / fact["beneficiaries"].clip(lower=1)
    fact["admissions_per_1000"] = np.clip(rng.normal(190, 42, len(fact)) * fact["risk_score"], 70, 360)
    fact["ed_visits_per_1000"] = np.clip(rng.normal(430, 92, len(fact)) * (0.8 + fact["sdoh_risk_index"]), 120, 920)
    fact["readmissions_per_1000"] = np.clip(rng.normal(42, 11, len(fact)) * fact["risk_score"], 15, 94)
    fact["standardized_payment"] = fact["per_capita_cost"] / fact["risk_score"].clip(lower=0.1)
    return fact[
        [
            "geo_key",
            "performance_year",
            "beneficiaries",
            "per_capita_cost",
            "risk_score",
            "provider_density",
            "sdoh_risk_index",
            "avg_quality",
            "admissions_per_1000",
            "ed_visits_per_1000",
            "readmissions_per_1000",
            "standardized_payment",
        ]
    ].round(3)

