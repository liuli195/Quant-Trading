from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ConfigError(ValueError):
    """Raised when a scenario config is missing required fields."""


@dataclass(frozen=True)
class ScenarioConfig:
    strategy_file: Path
    strategy: str
    scenario_id: str
    start_date: str
    end_date: str
    capital: int | float
    frequency: str = "每天"
    py_version: str = "Python3"
    batch_id: str | None = None
    strategy_name: str | None = None
    edit_url: str | None = None
    estimated_minutes: float = 0.0
    run_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, data: dict[str, Any], base_dir: Path | None = None) -> "ScenarioConfig":
        missing = [
            key
            for key in ["strategy_file", "scenario_id", "start_date", "end_date", "capital"]
            if data.get(key) in (None, "")
        ]
        if missing:
            raise ConfigError(f"Missing required scenario fields: {', '.join(missing)}")

        base = base_dir or Path.cwd()
        strategy_file = Path(str(data["strategy_file"]))
        if not strategy_file.is_absolute():
            strategy_file = (base / strategy_file).resolve()

        start_date = _validate_date("start_date", str(data["start_date"]))
        end_date = _validate_date("end_date", str(data["end_date"]))
        if date.fromisoformat(start_date) > date.fromisoformat(end_date):
            raise ConfigError("start_date must be earlier than or equal to end_date")

        strategy = str(data.get("strategy") or _infer_strategy_name(strategy_file))
        if not strategy:
            raise ConfigError("strategy is required when it cannot be inferred from strategy_file")

        return cls(
            strategy_file=strategy_file,
            strategy=strategy,
            scenario_id=str(data["scenario_id"]),
            start_date=start_date,
            end_date=end_date,
            capital=_parse_capital(data["capital"]),
            frequency=str(data.get("frequency") or "每天"),
            py_version=str(data.get("py_version") or data.get("pyVersion") or "Python3"),
            batch_id=_none_or_str(data.get("batch_id")),
            strategy_name=_none_or_str(data.get("strategy_name")) or strategy_file.stem,
            edit_url=_none_or_str(data.get("edit_url")),
            estimated_minutes=float(data.get("estimated_minutes") or data.get("estimated_compute_minutes") or 0),
            run_id=_none_or_str(data.get("run_id")),
            raw=dict(data),
        )


def load_scenario_config(path: str | Path) -> ScenarioConfig:
    config_path = Path(path).resolve()
    data = load_config_mapping(config_path)
    return ScenarioConfig.from_mapping(data, base_dir=config_path.parent)


def load_config_mapping(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    suffix = config_path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ConfigError("YAML configs require PyYAML. Install requirements.txt first.") from exc
        data = yaml.safe_load(text)
    else:
        raise ConfigError(f"Unsupported config extension: {config_path.suffix}")

    if not isinstance(data, dict):
        raise ConfigError("Scenario config must contain a JSON/YAML object")
    return data


def _validate_date(name: str, value: str) -> str:
    if not DATE_RE.match(value):
        raise ConfigError(f"{name} must use YYYY-MM-DD format")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"{name} is not a valid date: {value}") from exc
    return value


def _parse_capital(value: Any) -> int | float:
    if isinstance(value, bool):
        raise ConfigError("capital must be numeric")
    if isinstance(value, (int, float)):
        return value
    try:
        parsed = float(str(value).replace(",", ""))
    except ValueError as exc:
        raise ConfigError("capital must be numeric") from exc
    return int(parsed) if parsed.is_integer() else parsed


def _infer_strategy_name(strategy_file: Path) -> str:
    parts = strategy_file.parts
    for index, part in enumerate(parts):
        if part == "strategies" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _none_or_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
