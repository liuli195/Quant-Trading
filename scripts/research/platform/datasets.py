"""Repository-level immutable dataset snapshots."""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.research.research_core.pointers import (
    read_data_center_pointer as _read_data_center_pointer,
    read_json_object as _read_json_object,
    read_logical_bytes as _read_logical_bytes,
    read_text_file as _read_text_file,
)
from scripts.research.research_core.prices import PriceFrames, load_price_bundle


class DatasetError(RuntimeError):
    """Raised when a dataset snapshot cannot be loaded or created."""


DATASET_SCHEMA_VERSION = 1
DATASET_LIFECYCLES = {"active", "superseded", "archived"}
BACKTEST_RUN_RAW_FILES = (
    Path("api_export.json"),
    Path("detail_api_export.json"),
    Path("summary_metrics.json"),
    Path("tabs_raw/audit_log.jsonl"),
    Path("tabs_raw/daily_returns.md"),
    Path("tabs_raw/positioninfo.md"),
    Path("tabs_raw/transactioninfo.md"),
    Path("tabs_raw/balances.md"),
    Path("tabs_raw/period_risks.md"),
    Path("tabs_raw/logs.md"),
)
BACKTEST_RUN_LARGE_FILES = BACKTEST_RUN_RAW_FILES
BACKTEST_RUN_FILE_KEYS = {
    Path("api_export.json"): "api_export_source",
    Path("detail_api_export.json"): "detail_api_export_source",
    Path("summary_metrics.json"): "summary_metrics",
    Path("tabs_raw/audit_log.jsonl"): "audit_log_source",
    Path("tabs_raw/daily_returns.md"): "daily_returns_source",
    Path("tabs_raw/positioninfo.md"): "positioninfo_source",
    Path("tabs_raw/transactioninfo.md"): "transactioninfo_source",
    Path("tabs_raw/balances.md"): "balances_source",
    Path("tabs_raw/period_risks.md"): "period_risks_source",
    Path("tabs_raw/logs.md"): "logs_source",
}
CATALOG_REQUIRED_FIELDS = {
    "dataset_id",
    "snapshot_id",
    "fingerprint",
    "row_count",
    "date_range",
    "source_kind",
    "owner",
    "lifecycle",
}


@dataclass(frozen=True)
class DatasetSnapshot:
    """One immutable dataset snapshot."""

    root: Path
    metadata: dict[str, Any]

    @property
    def dataset_id(self) -> str:
        return str(self.metadata["dataset_id"])

    @property
    def snapshot_id(self) -> str:
        return str(self.metadata["snapshot_id"])

    @property
    def fingerprint(self) -> str:
        return str(self.metadata["fingerprint"])

    @property
    def raw_path(self) -> Path:
        return self.root / self.metadata["files"]["raw"]

    @property
    def parquet_path(self) -> Path:
        return self.root / self.metadata["files"]["canonical"]


@dataclass(frozen=True)
class BacktestRunMigrationResult:
    """One backtest run migration outcome."""

    strategy: str
    run_id: str
    dataset_id: str
    snapshot_id: str
    snapshot_root: Path
    imported: bool
    compacted_files: tuple[str, ...]


class DatasetRegistry:
    """Small facade around ``research_datasets/catalog.json``."""

    def __init__(self, datasets_root: str | Path = "research_datasets") -> None:
        self.root = _datasets_root(datasets_root)

    @property
    def catalog_path(self) -> Path:
        return self.root / "catalog.json"

    def refresh(self) -> list[dict[str, Any]]:
        _update_catalog(self.root)
        return self.list()

    def list(self) -> list[dict[str, Any]]:
        if not self.catalog_path.is_file():
            return []
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def find(self, dataset_id: str, snapshot_id: str) -> DatasetSnapshot:
        return load_snapshot(dataset_id, snapshot_id, datasets_root=self.root)

    def validate(self) -> list[str]:
        errors: list[str] = []
        catalog = self.list()
        for index, row in enumerate(catalog):
            missing = sorted(CATALOG_REQUIRED_FIELDS - set(row))
            if missing:
                errors.append(f"catalog row {index} missing field(s): {', '.join(missing)}")
        indexed = {
            (row.get("dataset_id"), row.get("snapshot_id"))
            for row in catalog
            if row.get("dataset_id") and row.get("snapshot_id")
        }
        actual = {
            (path.parent.parent.name, path.parent.name)
            for path in self.root.glob("*/*/dataset.json")
        }
        for dataset_id, snapshot_id in sorted(actual - indexed):
            errors.append(f"catalog missing: {dataset_id}/{snapshot_id}")
        for dataset_id, snapshot_id in sorted(indexed - actual):
            errors.append(f"catalog stale: {dataset_id}/{snapshot_id}")
        for row in catalog:
            if not row.get("dataset_id") or not row.get("snapshot_id"):
                continue
            metadata_path = self.root / row["dataset_id"] / row["snapshot_id"] / "dataset.json"
            if not metadata_path.is_file():
                errors.append(f"missing dataset.json: {metadata_path}")
                continue
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            errors.extend(
                f"{row['dataset_id']}/{row['snapshot_id']}: {message}"
                for message in validate_dataset_metadata(metadata)
            )
            if metadata.get("fingerprint") != row.get("fingerprint"):
                errors.append(f"catalog fingerprint mismatch: {row['dataset_id']}/{row['snapshot_id']}")
            if metadata.get("source", {}).get("kind", "") != row.get("source_kind"):
                errors.append(f"catalog source_kind mismatch: {row['dataset_id']}/{row['snapshot_id']}")
            if metadata.get("owner") != row.get("owner"):
                errors.append(f"catalog owner mismatch: {row['dataset_id']}/{row['snapshot_id']}")
            files = metadata.get("files", {})
            if isinstance(files, dict):
                for label, rel_path in files.items():
                    if label.endswith("_source") or _is_ignored_raw_payload(str(rel_path)):
                        continue
                    if not (metadata_path.parent / rel_path).exists():
                        errors.append(f"missing declared dataset file {label}: {row['dataset_id']}/{row['snapshot_id']}/{rel_path}")
            raw_integrity = metadata.get("raw_file_integrity", {})
            if isinstance(raw_integrity, dict):
                errors.extend(_validate_raw_file_integrity(metadata_path.parent, raw_integrity))
        return errors


def validate_dataset_metadata(metadata: dict[str, Any]) -> list[str]:
    """Validate one immutable ``dataset.json`` control-plane record."""

    errors: list[str] = []
    if not isinstance(metadata, dict):
        return ["dataset metadata must be an object"]
    if metadata.get("schema_version") != DATASET_SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    for field in ("dataset_id", "snapshot_id", "fingerprint", "created_at", "owner", "lifecycle"):
        if not isinstance(metadata.get(field), str) or not str(metadata.get(field)).strip():
            errors.append(f"{field} is required")
    if metadata.get("lifecycle") not in DATASET_LIFECYCLES:
        errors.append(f"lifecycle must be one of {sorted(DATASET_LIFECYCLES)}")
    if not str(metadata.get("fingerprint", "")).startswith("sha256:"):
        errors.append("fingerprint must use sha256:<hex>")
    if not isinstance(metadata.get("source"), dict) or not str(metadata.get("source", {}).get("kind", "")).strip():
        errors.append("source.kind is required")
    if not isinstance(metadata.get("row_count"), int) or metadata.get("row_count", -1) < 0:
        errors.append("row_count must be a non-negative integer")
    date_range = metadata.get("date_range")
    if (
        not isinstance(date_range, list)
        or len(date_range) != 2
        or any(not isinstance(item, str) for item in date_range)
    ):
        errors.append("date_range must be a two-item string list")
    files = metadata.get("files")
    if not isinstance(files, dict):
        errors.append("files must be an object")
    else:
        for field in ("raw", "canonical"):
            if not isinstance(files.get(field), str) or not files[field].strip():
                errors.append(f"files.{field} is required")
    return errors


class DataViewLoader:
    """Load common views from one dataset snapshot."""

    def __init__(self, snapshot: DatasetSnapshot) -> None:
        self.snapshot = snapshot

    def path(self, key: str) -> Path:
        files = self.snapshot.metadata.get("files", {})
        if key not in files:
            raise DatasetError(f"view not declared in dataset metadata: {key}")
        return self.snapshot.root / files[key]

    def summary_metrics(self) -> dict[str, Any]:
        files = self.snapshot.metadata.get("files", {})
        if "summary_metrics" not in files:
            return dict(self.snapshot.metadata.get("summary_metrics", {}))
        path = self.path("summary_metrics")
        return _read_json_object(path) if path.is_file() else dict(self.snapshot.metadata.get("summary_metrics", {}))

    def raw_text(self, key: str) -> str:
        """Read a declared raw source file, including gzip files."""

        return _read_text_file(self.path(key))

    def daily_returns(self) -> pd.DataFrame:
        path = self.path("daily_returns")
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        return _parse_daily_returns_md(path)

    def audit_events(self) -> list[dict[str, Any]]:
        files = self.snapshot.metadata.get("files", {})
        key = "audit_log" if "audit_log" in files else "audit_log_source"
        path = self.path(key) if key in files else Path()
        if not path.is_file():
            events_path = self.path("audit_events")
            if events_path.suffix.lower() == ".parquet" and events_path.is_file():
                frame = pd.read_parquet(events_path)
                if "payload_json" in frame:
                    return [json.loads(value) for value in frame["payload_json"].dropna().tolist()]
            return []
        return _read_jsonl(path)


class BacktestRunImporter:
    """Import complete JoinQuant backtest run directories into immutable snapshots."""

    def __init__(self, datasets_root: str | Path = "research_datasets") -> None:
        self.datasets_root = _datasets_root(datasets_root)

    def import_run(self, source: str | Path, *, dataset_id: str, snapshot_id: str | None = None) -> DatasetSnapshot:
        return import_backtest_run(
            source,
            dataset_id=dataset_id,
            snapshot_id=snapshot_id,
            datasets_root=self.datasets_root,
        )


def _datasets_root(root: str | Path = "research_datasets") -> Path:
    return Path(root)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_joinquant_price_payload(payload: dict[str, Any]) -> pd.DataFrame:
    """Normalize the repository's JoinQuant price JSON into long-form rows."""

    rows: list[dict[str, Any]] = []
    for symbol, records in payload.get("prices", {}).items():
        for record in records:
            rows.append(
                {
                    "date": pd.Timestamp(record["date"]).normalize(),
                    "symbol": symbol,
                    "open": record.get("open"),
                    "close": record.get("close"),
                    "high": record.get("high"),
                    "low": record.get("low"),
                    "money": record.get("money"),
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["date", "symbol"]).reset_index(drop=True)


def _profile(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "row_count": int(len(frame)),
        "date_range": [
            "" if frame.empty else str(frame["date"].min().date()),
            "" if frame.empty else str(frame["date"].max().date()),
        ],
        "symbols": [] if frame.empty else sorted(frame["symbol"].dropna().unique().tolist()),
        "null_summary": {column: int(frame[column].isna().sum()) for column in frame.columns},
    }


def _render_schema(frame: pd.DataFrame) -> str:
    rows = ["| 字段 | dtype |", "| --- | --- |"]
    rows.extend(f"| {column} | {dtype} |" for column, dtype in frame.dtypes.items())
    return "\n".join(["# 数据字段", "", *rows, ""])


def _render_profile(profile: dict[str, Any]) -> str:
    rows = [
        "# 数据概览",
        "",
        f"- **行数**: `{profile['row_count']}`",
        f"- **日期范围**: `{profile['date_range'][0]} ~ {profile['date_range'][1]}`",
        f"- **标的数**: `{len(profile['symbols'])}`",
        "",
        "| 字段 | 缺失值 |",
        "| --- | ---: |",
    ]
    rows.extend(f"| {field} | {count} |" for field, count in profile["null_summary"].items())
    rows.append("")
    return "\n".join(rows)


def _render_readme(metadata: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {metadata['dataset_id']}",
            "",
            f"- **snapshot**: `{metadata['snapshot_id']}`",
            f"- **fingerprint**: `{metadata['fingerprint']}`",
            f"- **来源**: `{metadata['source']['kind']}`",
            f"- **行数**: `{metadata['row_count']}`",
            f"- **日期范围**: `{metadata['date_range'][0]} ~ {metadata['date_range'][1]}`",
            "",
            "优先阅读 `views/profile.md`、`views/schema.md` 与 `views/sample.csv`；",
            "程序读取请使用 `data/data.parquet`。",
            "",
        ]
    )


def import_joinquant_price_json(
    source: str | Path,
    *,
    dataset_id: str,
    datasets_root: str | Path = "research_datasets",
    snapshot_id: str | None = None,
) -> DatasetSnapshot:
    """Create one immutable price-dataset snapshot from a JoinQuant JSON export."""

    source_path = Path(source)
    raw_bytes = _read_logical_bytes(source_path)
    payload = json.loads(raw_bytes.decode("utf-8"))
    frame = normalize_joinquant_price_payload(payload)
    if frame.empty:
        raise DatasetError("normalized dataset is empty")

    fingerprint = f"sha256:{sha256_bytes(raw_bytes)}"
    generated_snapshot = snapshot_id or (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ") + "_" + fingerprint.split(":", 1)[1][:12]
    )
    root = _datasets_root(datasets_root) / dataset_id / generated_snapshot
    if root.exists():
        raise DatasetError(f"dataset snapshot already exists: {root}")
    for directory in (root / "raw", root / "data", root / "views"):
        directory.mkdir(parents=True, exist_ok=True)

    (root / "raw" / "source.json.gz").write_bytes(gzip.compress(raw_bytes, compresslevel=9))
    try:
        frame.to_parquet(root / "data" / "data.parquet", index=False, compression="zstd")
    except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency.
        raise DatasetError("Parquet support requires pyarrow; install requirements.txt first") from exc

    profile = _profile(frame)
    metadata = {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "snapshot_id": generated_snapshot,
        "fingerprint": fingerprint,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner": "research-platform",
        "created_by": "research-platform",
        "lifecycle": "active",
        "source": {"kind": "joinquant_price_json", "path": source_path.as_posix()},
        "storage": {"canonical": "parquet", "compression": "zstd", "raw": "json.gz"},
        "primary_keys": ["date", "symbol"],
        "columns": list(frame.columns),
        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
        **profile,
        "files": {
            "raw": "raw/source.json.gz",
            "canonical": "data/data.parquet",
            "sample": "views/sample.csv",
            "profile_json": "views/profile.json",
        },
    }
    (root / "dataset.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "README.md").write_text(_render_readme(metadata), encoding="utf-8")
    (root / "views" / "schema.md").write_text(_render_schema(frame), encoding="utf-8")
    (root / "views" / "profile.md").write_text(_render_profile(profile), encoding="utf-8")
    (root / "views" / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    frame.head(20).to_csv(root / "views" / "sample.csv", index=False)
    _update_catalog(_datasets_root(datasets_root))
    return DatasetSnapshot(root=root, metadata=metadata)


def import_backtest_run(
    source: str | Path,
    *,
    dataset_id: str,
    datasets_root: str | Path = "research_datasets",
    snapshot_id: str | None = None,
    allow_partial: bool = False,
) -> DatasetSnapshot:
    """Create one immutable dataset snapshot from a ``backtest_runs/<run_id>`` directory."""

    source_path = Path(source)
    if not source_path.is_dir():
        raise DatasetError(f"backtest run directory not found: {source_path}")
    missing_required = _missing_backtest_run_source_files(source_path)
    if missing_required and not allow_partial:
        raise DatasetError(f"backtest run missing required file(s): {', '.join(missing_required)}")

    fingerprint = f"sha256:{_sha256_tree(source_path)}"
    generated_snapshot = snapshot_id or (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        + "_"
        + fingerprint.split(":", 1)[1][:12]
    )
    root = _datasets_root(datasets_root) / dataset_id / generated_snapshot
    if root.exists():
        raise DatasetError(f"dataset snapshot already exists: {root}")
    for directory in (root / "raw", root / "data", root / "views"):
        directory.mkdir(parents=True, exist_ok=True)

    summary_path = source_path / "summary_metrics.json"
    metadata_path = source_path / "metadata.json"
    audit_path = source_path / "tabs_raw" / "audit_log.jsonl"
    daily_returns_path = source_path / "tabs_raw" / "daily_returns.md"
    (root / "raw" / "source.json.gz").write_bytes(
        gzip.compress(json.dumps(_source_manifest(source_path), ensure_ascii=False, indent=2).encode("utf-8"), compresslevel=9)
    )
    raw_file_integrity: dict[str, dict[str, Any]] = {}
    for relative_path in BACKTEST_RUN_RAW_FILES:
        source_file = source_path / relative_path
        if source_file.is_file():
            raw_file_integrity[relative_path.as_posix()] = _write_gzip_file(
                source_file,
                root / "raw" / _gzip_name(relative_path),
            )

    daily_returns = _parse_daily_returns_md(daily_returns_path)
    if daily_returns.empty and not allow_partial:
        raise DatasetError(f"daily_returns.md did not contain parseable rows: {daily_returns_path}")
    if daily_returns.empty:
        daily_returns = pd.DataFrame(columns=["date", "cumulative_return"])
    daily_returns.to_parquet(root / "data" / "data.parquet", index=False, compression="zstd")

    audit_events = _read_jsonl(audit_path) if audit_path.is_file() else []
    audit_frame = pd.DataFrame(
        [
            {
                "seq": event.get("seq"),
                "event": event.get("event", "unknown"),
                "current_dt": event.get("current_dt", ""),
                "payload_json": json.dumps(event, ensure_ascii=False, sort_keys=True),
            }
            for event in audit_events
        ]
    )
    if audit_frame.empty:
        audit_frame = pd.DataFrame(columns=["seq", "event", "current_dt", "payload_json"])
    audit_frame.to_parquet(root / "data" / "audit_events.parquet", index=False, compression="zstd")

    audit_line_count = int(len(audit_events))
    audit_profile = _audit_profile(audit_events)

    summary_metrics = _read_json_object(summary_path) if summary_path.is_file() else {}
    source_metadata = _read_json_object(metadata_path) if metadata_path.is_file() else {}
    date_range = _date_range_from_daily_returns(daily_returns)
    row_count = int(len(daily_returns)) if not daily_returns.empty else audit_line_count
    files = {
        "raw": "raw/source.json.gz",
        "profile_json": "views/profile.json",
        "audit_events": "data/audit_events.parquet",
        "daily_returns": "data/data.parquet",
        "canonical": "data/data.parquet",
        "sample": "views/sample.csv",
    }
    for relative_path, key in BACKTEST_RUN_FILE_KEYS.items():
        integrity = raw_file_integrity.get(relative_path.as_posix())
        if integrity:
            files[key] = str(integrity["dataset_file"])

    metadata = {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "snapshot_id": generated_snapshot,
        "fingerprint": fingerprint,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner": "research-platform",
        "created_by": "research-platform",
        "lifecycle": "active",
        "source": {"kind": "joinquant_backtest_run", "path": source_path.as_posix()},
        "storage": {"canonical": "parquet", "compression": "zstd", "raw": "json.gz/jsonl.gz"},
        "row_count": row_count,
        "date_range": date_range,
        "run_id": source_path.name,
        "partial": bool(missing_required),
        "missing_required_files": missing_required,
        "summary_metrics": summary_metrics,
        "source_metadata": source_metadata,
        "audit_line_count": audit_line_count,
        "audit_date_range": audit_profile["date_range"],
        "audit_event_counts": audit_profile["event_counts"],
        "etf_pool": audit_profile["etf_pool"],
        "report_files": sorted(path.name for path in (source_path / "report").glob("*.md")) if (source_path / "report").is_dir() else [],
        "files": files,
        "raw_file_integrity": raw_file_integrity,
    }
    profile = {
        "row_count": row_count,
        "date_range": date_range,
        "audit_line_count": audit_line_count,
        "audit_date_range": audit_profile["date_range"],
        "audit_event_counts": audit_profile["event_counts"],
        "etf_pool": audit_profile["etf_pool"],
        "summary_metric_keys": sorted(summary_metrics),
        "report_files": metadata["report_files"],
    }
    (root / "dataset.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "README.md").write_text(_render_backtest_readme(metadata), encoding="utf-8")
    (root / "views" / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "views" / "profile.md").write_text(_render_backtest_profile(profile), encoding="utf-8")
    (root / "views" / "schema.md").write_text(_render_backtest_schema(), encoding="utf-8")
    daily_returns.head(20).to_csv(root / "views" / "sample.csv", index=False)
    _update_catalog(_datasets_root(datasets_root))
    return DatasetSnapshot(root=root, metadata=metadata)


def migrate_backtest_runs_to_datasets(
    *,
    strategies_root: str | Path = "strategies",
    datasets_root: str | Path = "research_datasets",
    strategy: str | None = None,
    compact_source: bool = False,
    dry_run: bool = False,
) -> list[BacktestRunMigrationResult]:
    """Import repository backtest runs into the data center."""

    datasets_base = _datasets_root(datasets_root)
    results: list[BacktestRunMigrationResult] = []
    for strategy_name, run_dir in _iter_backtest_run_dirs(strategies_root, strategy=strategy):
        dataset_id = f"{_safe_component(strategy_name)}_backtest_runs"
        snapshot_id = _safe_component(run_dir.name)
        snapshot_root = datasets_base / dataset_id / snapshot_id
        imported = False
        compacted_files: tuple[str, ...] = ()
        if snapshot_root.exists() and not (snapshot_root / "dataset.json").is_file():
            shutil.rmtree(snapshot_root)
        if not dry_run and not snapshot_root.exists():
            snapshot = import_backtest_run(
                run_dir,
                dataset_id=dataset_id,
                snapshot_id=snapshot_id,
                datasets_root=datasets_base,
                allow_partial=True,
            )
            snapshot_root = snapshot.root
            imported = True
        if compact_source and not dry_run and snapshot_root.exists():
            compacted_files = _compact_backtest_run_source(
                run_dir,
                dataset_id=dataset_id,
                snapshot_id=snapshot_id,
                snapshot_root=snapshot_root,
            )
        results.append(
            BacktestRunMigrationResult(
                strategy=strategy_name,
                run_id=run_dir.name,
                dataset_id=dataset_id,
                snapshot_id=snapshot_id,
                snapshot_root=snapshot_root,
                imported=imported,
                compacted_files=compacted_files,
            )
        )
    if not dry_run:
        _update_catalog(datasets_base)
    return results


def compact_backtest_run_source(
    run_dir: str | Path,
    *,
    dataset_id: str,
    snapshot_id: str,
    snapshot_root: str | Path,
) -> tuple[str, ...]:
    """Replace large source files in one run with data-center pointers."""

    return _compact_backtest_run_source(
        Path(run_dir),
        dataset_id=dataset_id,
        snapshot_id=snapshot_id,
        snapshot_root=Path(snapshot_root),
    )


def _iter_backtest_run_dirs(strategies_root: str | Path, *, strategy: str | None = None) -> list[tuple[str, Path]]:
    root = Path(strategies_root)
    if not root.is_dir():
        return []
    strategy_dirs = [root / strategy] if strategy else sorted(path for path in root.iterdir() if path.is_dir())
    runs: list[tuple[str, Path]] = []
    for strategy_dir in strategy_dirs:
        runs_root = strategy_dir / "backtest_runs"
        if not runs_root.is_dir():
            continue
        for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            runs.append((strategy_dir.name, run_dir))
    return runs


def _compact_backtest_run_source(
    run_dir: Path,
    *,
    dataset_id: str,
    snapshot_id: str,
    snapshot_root: Path,
) -> tuple[str, ...]:
    compacted: list[str] = []
    raw_integrity = _load_snapshot_raw_integrity(snapshot_root)
    files = _load_snapshot_files(snapshot_root)
    for relative_path in BACKTEST_RUN_RAW_FILES:
        source_file = run_dir / relative_path
        if not source_file.is_file():
            continue
        dataset_file = f"raw/{_gzip_name(relative_path)}"
        target = snapshot_root / dataset_file
        pointer = _read_data_center_pointer(source_file)
        if pointer is not None:
            if target.is_file():
                compressed_sha256 = sha256_bytes(target.read_bytes())
                if pointer.get("compressed_sha256") != compressed_sha256:
                    pointer["compressed_sha256"] = compressed_sha256
                    source_file.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                raw_integrity[relative_path.as_posix()] = {
                    "dataset_file": str(pointer.get("dataset_file", dataset_file)),
                    "original_sha256": str(pointer.get("original_sha256", "")),
                    "compressed_sha256": compressed_sha256,
                    "original_bytes": int(pointer.get("original_bytes", 0)),
                }
                key = BACKTEST_RUN_FILE_KEYS.get(relative_path)
                if key:
                    files[key] = str(pointer.get("dataset_file", dataset_file))
            continue
        integrity = _write_gzip_file(source_file, target)
        raw_integrity[relative_path.as_posix()] = integrity
        key = BACKTEST_RUN_FILE_KEYS.get(relative_path)
        if key:
            files[key] = dataset_file
        payload = {
            "kind": "data_center_pointer",
            "dataset_id": dataset_id,
            "snapshot_id": snapshot_id,
            "dataset_snapshot": snapshot_root.as_posix(),
            "dataset_file": dataset_file,
            "original_path": relative_path.as_posix(),
            "original_sha256": integrity["original_sha256"],
            "compressed_sha256": integrity["compressed_sha256"],
            "original_bytes": source_file.stat().st_size,
        }
        source_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        compacted.append(relative_path.as_posix())
    if raw_integrity or files:
        _compact_snapshot_derived_files(snapshot_root, files=files, raw_integrity=raw_integrity)
    return tuple(compacted)


def _update_catalog(root: Path) -> None:
    rows: list[dict[str, Any]] = []
    if root.exists():
        for metadata_path in root.glob("*/*/dataset.json"):
            rows.append(json.loads(metadata_path.read_text(encoding="utf-8")))
    root.mkdir(parents=True, exist_ok=True)
    catalog = [
        {
            "dataset_id": row["dataset_id"],
            "snapshot_id": row["snapshot_id"],
            "fingerprint": row["fingerprint"],
            "row_count": row["row_count"],
            "date_range": row["date_range"],
            "source_kind": row.get("source", {}).get("kind", ""),
            "owner": row.get("owner", "research-platform"),
            "lifecycle": row.get("lifecycle", "active"),
        }
        for row in sorted(rows, key=lambda item: (item["dataset_id"], item["snapshot_id"]))
    ]
    (root / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# 研究数据目录",
        "",
        "| dataset_id | snapshot_id | source_kind | owner | lifecycle | row_count | date_range |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    lines.extend(
        f"| {item['dataset_id']} | {item['snapshot_id']} | {item.get('source_kind', '')} | "
        f"{item.get('owner', '')} | {item.get('lifecycle', '')} | {item['row_count']} | "
        f"{item['date_range'][0]} ~ {item['date_range'][1]} |"
        for item in catalog
    )
    lines.append("")
    (root / "catalog.md").write_text("\n".join(lines), encoding="utf-8")


def load_snapshot(
    dataset_id: str,
    snapshot_id: str,
    *,
    datasets_root: str | Path = "research_datasets",
) -> DatasetSnapshot:
    root = _datasets_root(datasets_root) / dataset_id / snapshot_id
    metadata_path = root / "dataset.json"
    if not metadata_path.is_file():
        raise DatasetError(f"dataset snapshot not found: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    errors = validate_dataset_metadata(metadata)
    if errors:
        raise DatasetError(f"invalid dataset metadata {metadata_path}: {'; '.join(errors)}")
    return DatasetSnapshot(root=root, metadata=metadata)


def load_price_frames(snapshot: DatasetSnapshot, codes: tuple[str, ...] | None = None) -> PriceFrames:
    """Load price frames from Parquet, falling back to preserved raw JSON."""

    if snapshot.parquet_path.is_file():
        try:
            frame = pd.read_parquet(snapshot.parquet_path)
            frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
            selected_codes = tuple(codes or sorted(frame["symbol"].unique()))
            calendar = pd.DatetimeIndex(sorted(frame["date"].unique()))

            def pivot(field: str) -> pd.DataFrame:
                return (
                    frame.pivot(index="date", columns="symbol", values=field)
                    .reindex(index=calendar, columns=list(selected_codes))
                    .sort_index()
                )

            return PriceFrames(
                open=pivot("open"),
                close=pivot("close"),
                high=pivot("high"),
                low=pivot("low"),
                money=pivot("money"),
                calendar=calendar,
            )
        except ImportError:
            pass
    return load_price_bundle(snapshot.raw_path, codes=codes)


def _sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_read_logical_bytes(path))
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_backtest_run_source(source_path: Path) -> None:
    missing = _missing_backtest_run_source_files(source_path)
    if missing:
        raise DatasetError(f"backtest run missing required file(s): {', '.join(missing)}")


def _missing_backtest_run_source_files(source_path: Path) -> list[str]:
    required = [
        source_path / "summary_metrics.json",
        source_path / "tabs_raw" / "daily_returns.md",
        source_path / "tabs_raw" / "audit_log.jsonl",
    ]
    missing = [path.relative_to(source_path).as_posix() for path in required if not path.is_file()]
    if _first_existing(source_path / "detail_api_export.json", source_path / "api_export.json") is None:
        missing.append("detail_api_export.json or api_export.json")
    if missing:
        return missing
    return []


def _write_gzip_file(source: Path, target: Path) -> dict[str, Any]:
    raw_bytes = _read_logical_bytes(source)
    compressed = gzip.compress(raw_bytes, compresslevel=9)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(compressed)
    return {
        "dataset_file": f"raw/{target.name}",
        "original_sha256": sha256_bytes(raw_bytes),
        "compressed_sha256": sha256_bytes(compressed),
        "original_bytes": len(raw_bytes),
    }


def _gzip_name(relative_path: Path) -> str:
    return f"{relative_path.name}.gz"


def _is_data_center_pointer(path: Path) -> bool:
    return _read_data_center_pointer(path) is not None


def _load_snapshot_files(snapshot_root: Path) -> dict[str, str]:
    metadata_path = snapshot_root / "dataset.json"
    if not metadata_path.is_file():
        return {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    files = metadata.get("files", {})
    return dict(files) if isinstance(files, dict) else {}


def _load_snapshot_raw_integrity(snapshot_root: Path) -> dict[str, dict[str, Any]]:
    metadata_path = snapshot_root / "dataset.json"
    if not metadata_path.is_file():
        return {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw_integrity = metadata.get("raw_file_integrity", {})
    return dict(raw_integrity) if isinstance(raw_integrity, dict) else {}


def _compact_snapshot_derived_files(
    snapshot_root: Path,
    *,
    files: dict[str, str],
    raw_integrity: dict[str, dict[str, Any]],
) -> None:
    metadata_path = snapshot_root / "dataset.json"
    if not metadata_path.is_file():
        return
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    files = dict(metadata.get("files", {}), **files)
    files["daily_returns"] = "data/data.parquet"
    files["canonical"] = "data/data.parquet"
    files.pop("daily_returns_sample", None)
    metadata["files"] = files
    metadata["raw_file_integrity"] = raw_integrity
    metadata.setdefault("storage", {})["raw"] = "json.gz/jsonl.gz/md.gz"
    for path in (
        snapshot_root / "raw" / "summary_metrics.json",
        snapshot_root / "raw" / "daily_returns.md",
        snapshot_root / "data" / "daily_returns.parquet",
        snapshot_root / "views" / "daily_returns.csv",
    ):
        if path.is_file():
            path.unlink()
    (snapshot_root / "dataset.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (snapshot_root / "README.md").write_text(_render_backtest_readme(metadata), encoding="utf-8")
    schema_path = snapshot_root / "views" / "schema.md"
    if schema_path.parent.is_dir():
        schema_path.write_text(_render_backtest_schema(), encoding="utf-8")


def _validate_raw_file_integrity(snapshot_root: Path, raw_integrity: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for original_path, raw_info in raw_integrity.items():
        if not isinstance(raw_info, dict):
            errors.append(f"raw_file_integrity entry must be object: {original_path}")
            continue
        dataset_file = str(raw_info.get("dataset_file", ""))
        if not dataset_file:
            errors.append(f"raw_file_integrity missing dataset_file: {original_path}")
            continue
        target = snapshot_root / dataset_file
        if not target.is_file():
            errors.append(f"missing raw_file_integrity dataset_file: {original_path}")
            continue
        compressed = target.read_bytes()
        if raw_info.get("compressed_sha256") and raw_info["compressed_sha256"] != sha256_bytes(compressed):
            errors.append(f"compressed sha256 mismatch: {original_path}")
        if target.suffix.lower() == ".gz" and raw_info.get("original_sha256"):
            try:
                original = gzip.decompress(compressed)
            except OSError:
                errors.append(f"compressed raw file is not valid gzip: {original_path}")
                continue
            if raw_info["original_sha256"] != sha256_bytes(original):
                errors.append(f"original sha256 mismatch: {original_path}")
    return errors


def _is_ignored_raw_payload(rel_path: str) -> bool:
    return rel_path.startswith("raw/") and rel_path.endswith(".gz") and Path(rel_path).name != "source.json.gz"


def _safe_component(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(value)).strip("-")
    return safe or "unnamed"


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def _source_manifest(source_path: Path) -> dict[str, Any]:
    return {
        "source": source_path.as_posix(),
        "files": [
            _source_manifest_file(source_path, path)
            for path in sorted(item for item in source_path.rglob("*") if item.is_file())
        ],
    }


def _source_manifest_file(source_path: Path, path: Path) -> dict[str, Any]:
    raw_bytes = _read_logical_bytes(path)
    return {
        "path": path.relative_to(source_path).as_posix(),
        "sha256": sha256_bytes(raw_bytes),
        "bytes": len(raw_bytes),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in _read_text_file(path).splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _audit_profile(events: list[dict[str, Any]]) -> dict[str, Any]:
    dates: list[str] = []
    event_counts: dict[str, int] = {}
    etf_pool: list[str] = []
    for event in events:
        event_type = str(event.get("event", "unknown"))
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        current_dt = str(event.get("current_dt", ""))
        if current_dt:
            dates.append(current_dt[:10])
        if event_type == "run_start" and not etf_pool:
            raw_pool = event.get("params", {}).get("etf_pool", [])
            if isinstance(raw_pool, list):
                etf_pool = [str(item) for item in raw_pool]
    return {
        "date_range": [min(dates), max(dates)] if dates else ["", ""],
        "event_counts": dict(sorted(event_counts.items())),
        "etf_pool": etf_pool,
    }


def _parse_daily_returns_md(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return pd.DataFrame()
    for line in _read_text_file(path).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2 or cells[0].lower() == "date":
            continue
        try:
            rows.append({"date": cells[0], "cumulative_return": float(cells[1])})
        except ValueError:
            continue
    return pd.DataFrame(rows)


def _date_range_from_daily_returns(frame: pd.DataFrame) -> list[str]:
    if frame.empty or "date" not in frame:
        return ["", ""]
    return [str(frame["date"].iloc[0]), str(frame["date"].iloc[-1])]


def _render_backtest_readme(metadata: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {metadata['dataset_id']}",
            "",
            f"- **snapshot**: `{metadata['snapshot_id']}`",
            f"- **run_id**: `{metadata['run_id']}`",
            f"- **fingerprint**: `{metadata['fingerprint']}`",
            f"- **日期范围**: `{metadata['date_range'][0]} ~ {metadata['date_range'][1]}`",
            f"- **审计日志行数**: `{metadata['audit_line_count']}`",
            "",
            "原始文件压缩保存在 `raw/*.gz`；常用轻量索引见 `views/`；程序读取优先使用 `data/data.parquet`。",
            "",
        ]
    )

def _render_backtest_profile(profile: dict[str, Any]) -> str:
    lines = [
        "# 回测 run 概览",
        "",
        f"- **行数**: `{profile['row_count']}`",
        f"- **日期范围**: `{profile['date_range'][0]} ~ {profile['date_range'][1]}`",
        f"- **审计日志行数**: `{profile['audit_line_count']}`",
        f"- **审计日期范围**: `{profile['audit_date_range'][0]} ~ {profile['audit_date_range'][1]}`",
        f"- **ETF 池**: `{', '.join(profile['etf_pool'])}`",
        "",
        "## 审计事件分布",
        "",
        "| 事件类型 | 数量 |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {event} | {count} |" for event, count in profile["audit_event_counts"].items())
    lines.extend([
        "",
        "## 报告文件",
        "",
        "| 报告文件 |",
        "| --- |",
    ])
    lines.extend(f"| {name} |" for name in profile["report_files"])
    lines.append("")
    return "\n".join(lines)


def _render_backtest_schema() -> str:
    return "\n".join(
        [
            "# 回测 run 快照字段",
            "",
            "| 视图 | 说明 |",
            "| --- | --- |",
            "| `raw/source.json.gz` | 原始 run 文件清单与哈希 |",
            "| `raw/*.gz` | 压缩保存的原始回测文件 |",
            "| `data/data.parquet` | 累计收益序列主存储 |",
            "| `data/audit_events.parquet` | 审计事件主存储 |",
            "| `views/sample.csv` | 收益序列小样本 |",
            "| `views/profile.json` | 行数、日期范围、审计日志和报告文件摘要 |",
            "",
        ]
    )


def import_audit_log_jsonl(
    source: str | Path,
    *,
    dataset_id: str,
    datasets_root: str | Path = "research_datasets",
    snapshot_id: str | None = None,
) -> DatasetSnapshot:
    """Create an immutable dataset snapshot from a JoinQuant audit_log.jsonl."""

    source_path = Path(source)
    raw_bytes = _read_logical_bytes(source_path)
    fingerprint = f"sha256:{sha256_bytes(raw_bytes)}"

    lines = [line for line in raw_bytes.decode("utf-8").splitlines() if line.strip()]
    total_lines = len(lines)
    event_counts: dict[str, int] = {}
    dates: list[str] = []
    params_snapshot: dict[str, Any] = {}

    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = str(ev.get("event", "unknown"))
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        if ev.get("event") == "run_start" and not params_snapshot:
            params_snapshot = {
                "etf_pool": ev.get("params", {}).get("etf_pool", []),
                "benchmark": ev.get("params", {}).get("benchmark"),
                "current_dt": ev.get("current_dt"),
            }
        dt = ev.get("current_dt", "")
        if dt:
            dates.append(dt[:10])

    generated_snapshot = snapshot_id or (
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        + "_"
        + fingerprint.split(":", 1)[1][:12]
    )
    root = _datasets_root(datasets_root) / dataset_id / generated_snapshot
    if root.exists():
        raise DatasetError(f"dataset snapshot already exists: {root}")
    for directory in (root / "raw", root / "data", root / "views"):
        directory.mkdir(parents=True, exist_ok=True)

    (root / "raw" / "audit_log.jsonl.gz").write_bytes(gzip.compress(raw_bytes, compresslevel=9))

    # 归一化为 Parquet 主存储（从 rebalance_signals 事件中提取标量 + 数组展平）
    parquet_row_count = 0
    etf_pool = params_snapshot.get("etf_pool", [])
    n_etf = len(etf_pool)
    if n_etf > 0:
        signal_rows = []
        for line in lines:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") != "rebalance_signals":
                continue
            row = {"date": pd.Timestamp(ev.get("current_dt", "")).date()}
            array_fields = [
                "trend_gates", "rp_weights", "momentum_scores", "momentum_tilts",
                "rsrs_tilts", "tilted_weights", "crowd_penalties", "raw_weights",
                "final_weights_before_constraints", "final_weights",
            ]
            for field in array_fields:
                arr = ev.get(field, [])
                for i in range(n_etf):
                    row[f"{field}_{i}"] = float(arr[i]) if i < len(arr) else 0.0
            row["portfolio_vol_scale"] = float(ev.get("portfolio_vol_scale", 1.0))
            row["n_active"] = int(sum(1 for g in ev.get("trend_gates", []) if g > 0))
            signal_rows.append(row)
        if signal_rows:
            frame = pd.DataFrame(signal_rows)
            frame.to_parquet(root / "data" / "data.parquet", index=False, compression="zstd")
            parquet_row_count = int(len(frame))

    date_range = [min(dates), max(dates)] if dates else ["", ""]
    metadata = {
        "schema_version": 1,
        "dataset_id": dataset_id,
        "snapshot_id": generated_snapshot,
        "fingerprint": fingerprint,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner": "research-platform",
        "created_by": "research-platform",
        "lifecycle": "active",
        "source": {"kind": "joinquant_audit_log_jsonl", "path": source_path.as_posix()},
        "storage": {"canonical": "parquet", "compression": "zstd", "raw": "jsonl.gz"},
        "row_count": parquet_row_count or total_lines,
        "columns": [] if parquet_row_count == 0 else list(frame.columns),
        "etf_pool": etf_pool,
        "date_range": date_range,
        "total_events": total_lines,
        "event_counts": event_counts,
        "params_snapshot": params_snapshot,
        "files": {
            "raw": "raw/audit_log.jsonl.gz",
            "canonical": "data/data.parquet",
            "profile_json": "views/profile.json",
        },
    }
    (root / "dataset.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "README.md").write_text(
        "\n".join([
            f"# {dataset_id}",
            "",
            f"- **snapshot**: `{generated_snapshot}`",
            f"- **fingerprint**: `{fingerprint}`",
            "- **来源**: joinquant_audit_log_jsonl",
            f"- **事件总数**: `{total_lines}`",
            f"- **ETF 池**: {params_snapshot.get('etf_pool', [])}",
        ] + (["", f"- **日期范围**: `{date_range[0]} ~ {date_range[1]}`"] if date_range[0] else []) + [""]),
        encoding="utf-8",
    )

    # views/profile.md
    profile = [f"# 审计日志概览\n\n- **事件总数**: `{total_lines}`"]
    if date_range[0]:
        profile.append(f"- **日期范围**: `{date_range[0]} ~ {date_range[1]}`")
    profile.append("\n## 事件类型分布\n\n| 事件类型 | 数量 |\n| --- | ---: |")
    for et, cnt in sorted(event_counts.items(), key=lambda x: x[1], reverse=True):
        profile.append(f"| {et} | {cnt} |")
    (root / "views" / "profile.md").write_text("\n".join(profile), encoding="utf-8")

    # views/schema.md
    (root / "views" / "schema.md").write_text(
        "\n".join([
            "# 审计日志字段",
            "",
            "每行一个 JSON 事件，字段随 `event` 类型变化。",
            "",
            "## 公共字段",
            "| 字段 | 类型 | 说明 |",
            "| --- | --- | --- |",
            "| `seq` | int | 事件序号 |",
            "| `event` | str | run_start / rebalance_signals / rebalance_order / run_end |",
            "| `audit_token` | str | 审计令牌 |",
            "| `current_dt` | str | 当前时间 |",
            "| `previous_date` | str | 上一交易日 |",
            "",
            "## rebalance_signals 特有字段",
            "| 字段 | 类型 |",
            "| --- | --- |",
            "| `trend_gates` | list[float] |",
            "| `rp_weights` | list[float] |",
            "| `tilted_weights` | list[float] |",
            "| `crowd_penalties` | list[float] |",
            "| `raw_weights` | list[float] |",
            "| `portfolio_vol_scale` | float |",
            "| `final_weights_before_constraints` | list[float] |",
            "| `final_weights` | list[float] |",
            "",
        ]),
        encoding="utf-8",
    )

    (root / "views" / "profile.json").write_text(
        json.dumps({
            "total_events": total_lines,
            "date_range": date_range,
            "event_counts": event_counts,
            "params_snapshot": params_snapshot,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _update_catalog(_datasets_root(datasets_root))
    return DatasetSnapshot(root=root, metadata=metadata)

