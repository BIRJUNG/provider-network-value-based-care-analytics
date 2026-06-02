from __future__ import annotations

from pathlib import Path


def write_project_docs(docs_dir: Path) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    docs = {
        "data_sources.md": DATA_SOURCES,
        "architecture.md": ARCHITECTURE,
        "kpi_dictionary.md": KPI_DICTIONARY,
        "data_dictionary.md": DATA_DICTIONARY,
        "dashboard_spec.md": DASHBOARD_SPEC,
        "custom_data_guide.md": CUSTOM_DATA_GUIDE,
    }
    for name, content in docs.items():
        (docs_dir / name).write_text(content.strip() + "\n", encoding="utf-8")


DATA_SOURCES = """
# Data Sources

The default build uses synthetic CMS-style provider network, ACO, hospital quality, and market data.

Reference sources used for domain design:

- CMS NPPES NPI Files
- CMS Physician and Other Practitioners by Provider and Service
- CMS Hospital Quality / Care Compare
- CMS Hospital Readmissions Reduction Program
- CMS Medicare Geographic Variation PUF
- Medicare Shared Savings Program ACO public data

Custom provider utilization data can be loaded with `--custom-provider-utilization`.
"""

ARCHITECTURE = """
# Architecture

1. Synthetic or custom source data
2. Provider, facility, geography, service, and ACO dimensions
3. Provider utilization, hospital quality, ACO performance, and market facts
4. SQLite warehouse
5. Provider, hospital, ACO, market, and contracting marts
6. Scoring tables
7. Quality report
8. Static dashboard
"""

KPI_DICTIONARY = """
# KPI Dictionary

| KPI | Definition |
|---|---|
| Payment per beneficiary | Medicare payment amount divided by beneficiary count |
| Services per beneficiary | Service count divided by beneficiary count |
| Peer cost percentile | Provider cost rank within specialty and state |
| Peer utilization percentile | Provider utilization rank within specialty and state |
| Quality composite score | Weighted hospital quality score |
| ACO savings rate | Gross savings/losses divided by benchmark expenditure |
| Network value score | Weighted score across volume, quality, cost efficiency, market need, and stability |
| Market opportunity score | Weighted cost, utilization, quality gap, and provider density gap |
"""

DATA_DICTIONARY = """
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
"""

DASHBOARD_SPEC = """
# Dashboard Specification

Dashboard views:

- executive overview
- provider peer benchmarking
- hospital quality
- ACO performance
- market opportunity
- contracting opportunity
- provider outlier queue
- governance
"""

CUSTOM_DATA_GUIDE = """
# Custom Data Guide

Run:

```powershell
python scripts\\run_provider_network_pipeline.py --custom-provider-utilization data\\raw\\custom_provider_utilization_template.csv
```

Recommended columns:

```text
provider_id,provider_name,specialty_group,provider_type,state_code,market,beneficiary_count,service_count,medicare_payment_amount,allowed_amount,quality_score,readmission_rate
```
"""


def write_model_card(score_outputs, output_path: Path) -> None:
    lines = ["# Scoring Model Cards", ""]
    for name, metrics in score_outputs.metrics.items():
        lines.append(f"## {name.replace('_', ' ').title()}")
        for key, value in metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.append("")
    lines.append("Scores are portfolio demonstration scores. They should not be used for real contracting, credentialing, or network decisions without validation and governance.")
    output_path.write_text("\n".join(lines), encoding="utf-8")

