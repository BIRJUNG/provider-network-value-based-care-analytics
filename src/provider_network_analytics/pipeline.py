from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import PipelineConfig, find_project_root
from .custom_data import load_custom_provider_utilization
from .data_generation import generate_dataset
from .documentation import write_model_card, write_project_docs
from .marts import build_marts
from .quality import run_quality_checks
from .reporting import render_dashboard, write_executive_summary
from .scoring import score_network
from .warehouse import ensure_output_dirs, export_csv_tables, write_sqlite_database


def run_pipeline(config: PipelineConfig) -> dict[str, object]:
    ensure_output_dirs(config.project_root)
    if config.custom_provider_utilization_csv:
        generated = load_custom_provider_utilization(config.custom_provider_utilization_csv, performance_year=config.performance_year)
    else:
        generated = generate_dataset(
            seed=config.seed,
            provider_count=config.provider_count,
            facility_count=config.facility_count,
            aco_count=config.aco_count,
            market_count=config.market_count,
            performance_year=config.performance_year,
        )
    base_tables = generated.as_tables()
    marts = build_marts(base_tables)
    score_outputs = score_network(base_tables, marts, config.data_processed_dir)
    all_tables = {**base_tables, **marts, **score_outputs.score_tables}
    write_sqlite_database(all_tables, config.sqlite_path)
    export_csv_tables(all_tables, config.data_processed_dir)
    quality_report = run_quality_checks(base_tables, marts, score_outputs.metrics)
    quality_report.to_csv(config.reports_dir / "data_quality_report.csv", index=False)
    write_project_docs(config.docs_dir)
    write_model_card(score_outputs, config.model_card_path)
    render_dashboard(base_tables, marts, score_outputs, quality_report, config.dashboard_path)
    write_executive_summary(base_tables, marts, score_outputs, quality_report, config.summary_path)
    failures = int((quality_report["status"] == "FAIL").sum())
    return {
        "sqlite_path": config.sqlite_path,
        "dashboard_path": config.dashboard_path,
        "summary_path": config.summary_path,
        "quality_failures": failures,
        "table_count": len(all_tables),
        "provider_count": len(base_tables["dim_provider"]),
        "facility_count": len(base_tables["dim_facility"]),
        "aco_count": len(base_tables["dim_aco"]),
        "market_count": len(base_tables["dim_geography"]),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Provider Network Value-Based Care Analytics project.")
    parser.add_argument("--project-root", type=Path, default=find_project_root(), help="Repository/project root.")
    parser.add_argument("--providers", type=int, default=640)
    parser.add_argument("--facilities", type=int, default=120)
    parser.add_argument("--acos", type=int, default=64)
    parser.add_argument("--markets", type=int, default=34)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--performance-year", type=int, default=2025)
    parser.add_argument("--custom-provider-utilization", type=Path, default=None)
    parser.add_argument("--allow-quality-failures", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = PipelineConfig(
        project_root=args.project_root.resolve(),
        seed=args.seed,
        provider_count=args.providers,
        facility_count=args.facilities,
        aco_count=args.acos,
        market_count=args.markets,
        performance_year=args.performance_year,
        custom_provider_utilization_csv=args.custom_provider_utilization.resolve() if args.custom_provider_utilization else None,
    )
    result = run_pipeline(config)
    print("Provider Network Value-Based Care Analytics build complete")
    print(f"Providers: {result['provider_count']:,}")
    print(f"Facilities: {result['facility_count']:,}")
    print(f"ACOs: {result['aco_count']:,}")
    print(f"Markets: {result['market_count']:,}")
    print(f"Tables exported: {result['table_count']}")
    print(f"SQLite warehouse: {result['sqlite_path']}")
    print(f"Dashboard: {result['dashboard_path']}")
    print(f"Executive summary: {result['summary_path']}")
    print(f"Quality failures: {result['quality_failures']}")
    if result["quality_failures"] and not args.allow_quality_failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

