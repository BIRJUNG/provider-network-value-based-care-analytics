from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def find_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class PipelineConfig:
    project_root: Path
    seed: int = 42
    provider_count: int = 640
    facility_count: int = 120
    aco_count: int = 64
    market_count: int = 34
    performance_year: int = 2025
    custom_provider_utilization_csv: Path | None = None

    @property
    def data_processed_dir(self) -> Path:
        return self.project_root / "data" / "processed"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / "reports"

    @property
    def dashboard_dir(self) -> Path:
        return self.reports_dir / "dashboard"

    @property
    def docs_dir(self) -> Path:
        return self.project_root / "docs"

    @property
    def sqlite_path(self) -> Path:
        return self.data_processed_dir / "provider_network_vbc.db"

    @property
    def dashboard_path(self) -> Path:
        return self.dashboard_dir / "provider_network_vbc_dashboard.html"

    @property
    def summary_path(self) -> Path:
        return self.reports_dir / "executive_summary.md"

    @property
    def model_card_path(self) -> Path:
        return self.docs_dir / "model_cards.md"

