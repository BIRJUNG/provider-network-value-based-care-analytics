from __future__ import annotations

import sqlite3

from provider_network_analytics.config import PipelineConfig
from provider_network_analytics.data_generation import generate_dataset
from provider_network_analytics.marts import build_marts
from provider_network_analytics.pipeline import run_pipeline
from provider_network_analytics.quality import run_quality_checks
from provider_network_analytics.scoring import score_network


def test_generated_dataset_builds_marts_and_scores(tmp_path):
    generated = generate_dataset(seed=5, provider_count=120, facility_count=30, aco_count=16, market_count=10)
    tables = generated.as_tables()
    marts = build_marts(tables)
    scores = score_network(tables, marts, tmp_path)
    quality = run_quality_checks(tables, marts, scores.metrics)

    assert len(tables["dim_provider"]) == 120
    assert not tables["fact_provider_service_utilization"].empty
    assert not marts["mart_provider_peer_benchmark"].empty
    assert not marts["mart_contracting_opportunity"].empty
    assert not scores.score_tables["score_provider_anomaly"].empty
    assert (quality["status"] == "FAIL").sum() == 0


def test_end_to_end_pipeline_writes_outputs(tmp_path):
    config = PipelineConfig(project_root=tmp_path, seed=9, provider_count=140, facility_count=32, aco_count=18, market_count=11)
    result = run_pipeline(config)

    assert result["quality_failures"] == 0
    assert config.sqlite_path.exists()
    assert config.dashboard_path.exists()
    assert config.summary_path.exists()
    assert (config.data_processed_dir / "mart_provider_peer_benchmark.csv").exists()
    assert (config.data_processed_dir / "score_provider_anomaly.csv").exists()

    conn = sqlite3.connect(config.sqlite_path)
    try:
        provider_count = conn.execute("SELECT COUNT(*) FROM dim_provider").fetchone()[0]
        benchmark_count = conn.execute("SELECT COUNT(*) FROM mart_provider_peer_benchmark").fetchone()[0]
    finally:
        conn.close()

    assert provider_count == 140
    assert benchmark_count > 0


def test_pipeline_accepts_custom_provider_utilization_csv(tmp_path):
    custom = tmp_path / "custom_provider.csv"
    custom.write_text(
        "\n".join(
            [
                "provider_id,provider_name,specialty_group,provider_type,state_code,market,beneficiary_count,service_count,medicare_payment_amount,allowed_amount,quality_score,readmission_rate,aco_name,aco_quality_score,aco_savings_rate",
                "P1,Metro PCP,Primary care,Professional,TX,Dallas,700,3500,620000,780000,92,0.06,Northstar ACO,94,0.03",
                "P2,Metro Hospital,Facility,Hospital,TX,Dallas,2200,7800,6100000,7100000,70,0.18,Northstar ACO,94,0.03",
                "P3,Valley Ortho,Orthopedics,Professional,FL,Tampa,420,1500,1180000,1400000,78,0.09,Suncoast ACO,86,0.01",
                "P4,Precision Imaging,Radiology,Professional,CA,Los Angeles,800,4300,940000,1100000,88,0.05,Pacific ACO,90,0.02",
            ]
        ),
        encoding="utf-8",
    )
    config = PipelineConfig(project_root=tmp_path, custom_provider_utilization_csv=custom)
    result = run_pipeline(config)

    assert result["quality_failures"] == 0
    assert result["provider_count"] == 4
    assert result["aco_count"] == 3
    assert config.dashboard_path.exists()

