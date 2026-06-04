-- Named SQL analytics used by the Python pipeline after the SQLite warehouse is built.
-- Each query must begin with "-- name:" so src/provider_network_analytics/sql_analytics.py can execute it.

-- name: provider_value_leaders
SELECT
    provider_id,
    provider_name,
    specialty_group,
    state_code,
    market,
    ROUND(network_value_score, 4) AS network_value_score,
    opportunity_tier,
    recommended_contract_action
FROM mart_contracting_opportunity
ORDER BY network_value_score DESC
LIMIT 25;

-- name: provider_audit_candidates
SELECT
    provider_id,
    provider_name,
    specialty_group,
    state_code,
    market,
    ROUND(payment_per_beneficiary, 2) AS payment_per_beneficiary,
    ROUND(services_per_beneficiary, 2) AS services_per_beneficiary,
    ROUND(provider_anomaly_score, 4) AS provider_anomaly_score,
    anomaly_tier
FROM score_provider_anomaly
WHERE anomaly_tier IN ('Audit candidate', 'Watchlist')
ORDER BY provider_anomaly_score DESC
LIMIT 30;

-- name: market_network_gaps
SELECT
    market,
    state_code,
    region,
    beneficiaries,
    ROUND(per_capita_cost, 2) AS per_capita_cost,
    ROUND(provider_density, 3) AS provider_density,
    ROUND(avg_hospital_quality, 3) AS avg_hospital_quality,
    ROUND(market_opportunity_score, 4) AS market_opportunity_score,
    recommended_market_action
FROM mart_market_opportunity
ORDER BY market_opportunity_score DESC
LIMIT 20;

-- name: aco_savings_quality_segments
SELECT
    aco_id,
    aco_name,
    state_code,
    market,
    assigned_beneficiaries,
    ROUND(savings_rate, 4) AS savings_rate,
    ROUND(quality_score, 2) AS quality_score,
    ROUND(earned_shared_savings, 2) AS earned_shared_savings,
    quality_cost_quadrant,
    aco_performance_tier
FROM mart_aco_performance
ORDER BY earned_shared_savings DESC, quality_score DESC
LIMIT 25;
