-- Representative mart SQL for the Provider Network VBC platform.
-- The Python pipeline builds equivalent pandas marts and exports them to SQLite/CSV.

WITH provider_benchmark AS (
    SELECT
        p.provider_name,
        p.specialty_group,
        p.state_code,
        f.beneficiary_count,
        f.total_payment,
        f.payment_per_beneficiary,
        f.services_per_beneficiary,
        p.quality_score,
        p.readmission_rate
    FROM fact_provider_year f
    JOIN dim_provider p
        ON f.provider_key = p.provider_key
),
ranked AS (
    SELECT
        *,
        PERCENT_RANK() OVER (
            PARTITION BY specialty_group, state_code
            ORDER BY payment_per_beneficiary
        ) AS peer_cost_percentile,
        PERCENT_RANK() OVER (
            PARTITION BY specialty_group, state_code
            ORDER BY services_per_beneficiary
        ) AS peer_utilization_percentile
    FROM provider_benchmark
)
SELECT *
FROM ranked
ORDER BY peer_cost_percentile DESC;

