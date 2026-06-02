# Data Dictionary

| Table | Grain | Purpose |
|---|---|---|
| `dim_provider` | One row per provider | Provider identity, specialty, geography, quality proxy |
| `dim_facility` | One row per facility | Hospital/facility identity |
| `dim_geography` | One row per market | Market, cost, risk, density, SDOH context |
| `dim_aco` | One row per ACO-year | ACO participation context |
| `fact_provider_service_utilization` | Provider-service-year | Payment and utilization |
| `fact_provider_year` | Provider-year | Peer benchmarking features |
| `fact_hospital_quality` | Facility-year | Quality scores |
| `fact_aco_performance` | ACO-year | Savings and quality performance |
| `fact_geo_variation` | Market-year | Cost and utilization variation |
