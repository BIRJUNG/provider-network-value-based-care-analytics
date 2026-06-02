from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


@dataclass(slots=True)
class ScoreOutputs:
    metrics: dict[str, dict[str, float | int | str]]
    score_tables: dict[str, pd.DataFrame]


def score_network(tables: dict[str, pd.DataFrame], marts: dict[str, pd.DataFrame], output_dir: Path) -> ScoreOutputs:
    output_dir.mkdir(parents=True, exist_ok=True)
    provider_scores, provider_metrics = _provider_anomaly_scores(marts["mart_provider_peer_benchmark"])
    contracting_scores, contracting_metrics = _contracting_scores(marts["mart_contracting_opportunity"])
    aco_segments, aco_metrics = _aco_segments(marts["mart_aco_performance"])
    metrics = {
        "provider_anomaly_model": provider_metrics,
        "contracting_opportunity_score": contracting_metrics,
        "aco_performance_segmentation": aco_metrics,
    }
    score_tables = {
        "score_provider_anomaly": provider_scores,
        "score_contracting_opportunity": contracting_scores,
        "score_aco_segments": aco_segments,
    }
    for name, frame in score_tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)
    with (output_dir / "score_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
    return ScoreOutputs(metrics=metrics, score_tables=score_tables)


def _provider_anomaly_scores(provider: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    features = provider[
        [
            "payment_per_beneficiary",
            "services_per_beneficiary",
            "peer_cost_percentile",
            "peer_utilization_percentile",
            "quality_score",
            "readmission_rate",
            "service_concentration_index",
        ]
    ].apply(pd.to_numeric, errors="coerce").fillna(0)
    if len(provider) < 8:
        score = provider["provider_outlier_score"].rank(pct=True).to_numpy()
        status = "fallback_rank_score"
    else:
        model = IsolationForest(n_estimators=160, contamination=0.13, random_state=42)
        raw = -model.fit(features).score_samples(features)
        score = (raw - raw.min()) / max(raw.max() - raw.min(), 1e-9)
        status = "trained_isolation_forest"
    output = provider[
        [
            "provider_key",
            "provider_id",
            "provider_name",
            "specialty_group",
            "state_code",
            "market",
            "payment_per_beneficiary",
            "services_per_beneficiary",
        ]
    ].copy()
    output["provider_anomaly_score"] = score
    output["anomaly_tier"] = pd.cut(score, bins=[0, 0.45, 0.70, 0.88, 1.01], labels=["Normal", "Monitor", "Watchlist", "Audit candidate"], include_lowest=True).astype(str)
    return output.sort_values("provider_anomaly_score", ascending=False), {
        "status": status,
        "rows": int(len(output)),
        "audit_candidate_count": int((output["provider_anomaly_score"] >= 0.88).sum()),
    }


def _contracting_scores(contracting: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    output = contracting[
        [
            "provider_key",
            "provider_id",
            "provider_name",
            "specialty_group",
            "state_code",
            "market",
            "network_value_score",
            "opportunity_tier",
            "recommended_contract_action",
        ]
    ].copy()
    return output.sort_values("network_value_score", ascending=False), {
        "status": "deterministic_weighted_score",
        "rows": int(len(output)),
        "preferred_vbc_candidates": int((output["opportunity_tier"].astype(str) == "Preferred value-based contract candidate").sum()),
    }


def _aco_segments(aco: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    output = aco[["aco_key", "aco_id", "aco_name", "state_code", "market", "assigned_beneficiaries", "savings_rate", "quality_score", "quality_cost_quadrant", "aco_performance_tier"]].copy()
    return output.sort_values(["savings_rate", "quality_score"], ascending=False), {
        "status": "business_rule_segmentation",
        "rows": int(len(output)),
        "preferred_vbc_partners": int((output["aco_performance_tier"] == "Preferred VBC partner").sum()),
    }

