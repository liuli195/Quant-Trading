from __future__ import annotations

import itertools
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ConfigError(ValueError):
    """Raised when a scenario config is missing required fields."""


@dataclass(frozen=True)
class RunSpec:
    """A single run within a scenario — one parameter combination."""
    label: str
    params_diff: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioConfig:
    strategy_file: Path
    strategy: str
    scenario_id: str
    start_date: str
    end_date: str
    capital: int | float
    frequency: str = "1d"
    py_version: str = "Python3"
    batch_id: str | None = None
    strategy_name: str | None = None
    edit_url: str | None = None
    estimated_minutes: float = 0.0
    run_id: str | None = None
    result_source: str = "auto"
    allow_partial: bool = False
    params_base: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def expand_runs(self) -> list[RunSpec]:
        """Return the list of runs for this scenario.

        If the scenario config contains a 'sweep' block, expand it into
        individual RunSpec entries.  Otherwise return a single default run.
        """
        sweep = self.raw.get("sweep")
        if not sweep:
            label = "default"
            params_diff = _dictify(self.raw.get("params_diff"))
            if not params_diff and self.params_base:
                label = "baseline"
            return [RunSpec(label=label, params_diff=params_diff)]
        return _expand_sweep(sweep)

    def for_run(self, run_spec: RunSpec, run_id: str | None = None) -> "ScenarioConfig":
        """Derive a single-run config for one sweep combination."""
        return ScenarioConfig(
            strategy_file=self.strategy_file,
            strategy=self.strategy,
            scenario_id=self.scenario_id,
            start_date=self.start_date,
            end_date=self.end_date,
            capital=self.capital,
            frequency=self.frequency,
            py_version=self.py_version,
            batch_id=self.batch_id,
            strategy_name=self.strategy_name,
            edit_url=self.edit_url,
            estimated_minutes=self.estimated_minutes,
            run_id=run_id or self.run_id,
            result_source=self.result_source,
            allow_partial=self.allow_partial,
            params_base={**self.params_base, **run_spec.params_diff},
            raw={**self.raw, "_run_label": run_spec.label, "_run_params_diff": run_spec.params_diff},
        )

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
        estimated_raw = (
            data["estimated_minutes"]
            if data.get("estimated_minutes") not in (None, "")
            else data.get("estimated_compute_minutes", 0)
        )

        return cls(
            strategy_file=strategy_file,
            strategy=strategy,
            scenario_id=str(data["scenario_id"]),
            start_date=start_date,
            end_date=end_date,
            capital=_parse_capital(data["capital"]),
            frequency=_normalize_frequency(str(data.get("frequency") or "1d")),
            py_version=str(data.get("py_version") or data.get("pyVersion") or "Python3"),
            batch_id=_none_or_str(data.get("batch_id")),
            strategy_name=_none_or_str(data.get("strategy_name")) or strategy_file.stem,
            edit_url=_none_or_str(data.get("edit_url")),
            estimated_minutes=_parse_optional_float("estimated_minutes", estimated_raw),
            run_id=_none_or_str(data.get("run_id")),
            result_source=_normalize_result_source(str(data.get("result_source") or "auto")),
            allow_partial=_parse_bool(data.get("allow_partial"), default=False),
            params_base=_dictify(data.get("params_base")),
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


def _expand_sweep(sweep: dict[str, Any]) -> list[RunSpec]:
    """Expand a sweep definition into individual RunSpec entries."""
    strategy = sweep.get("strategy", "grid")
    if strategy == "grid":
        dimensions = sweep["dimensions"]
        if not isinstance(dimensions, dict) or not dimensions:
            raise ConfigError("sweep.strategy=grid requires non-empty dimensions dict")
        keys = list(dimensions.keys())
        values = [dimensions[k] for k in keys]
        result = []
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            label = "_".join(f"{k}={v}" for k, v in params.items())
            result.append(RunSpec(label=label, params_diff=params))
        return result
    if strategy == "list":
        combinations = sweep.get("combinations")
        if not isinstance(combinations, list) or not combinations:
            raise ConfigError("sweep.strategy=list requires non-empty combinations list")
        return [
            RunSpec(label=c["label"], params_diff=dict(c.get("params", {})))
            for c in combinations
        ]
    raise ConfigError(f"Unknown sweep strategy: {strategy}")


def _dictify(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _validate_date(name: str, value: str) -> str:
    if not DATE_RE.match(value):
        raise ConfigError(f"{name} must use YYYY-MM-DD format")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError(f"{name} is not a valid date: {value}") from exc
    return value


def _normalize_frequency(raw: str) -> str:
    """Normalize frequency to the canonical English form expected by JoinQuant.

    Accepts both Chinese display text and English aliases.  Unknown values
    raise ConfigError so the mistake is caught at the boundary rather than
    silently failing inside the browser automation.
    """
    v = raw.strip().lower()
    # Daily
    if v in ("每天", "daily", "1d", "d", "day"):
        return "1d"
    # Minute
    if v in ("每分钟", "minute", "1m", "m", "min"):
        return "1m"
    # Tick
    if v in ("tick",):
        return "tick"
    # Sub-minute bars
    if v in ("5m", "5min"):
        return "5m"
    if v in ("15m", "15min"):
        return "15m"
    if v in ("30m", "30min"):
        return "30m"
    if v in ("60m", "60min", "1h", "h", "hourly"):
        return "60m"
    raise ConfigError(
        f"Unsupported frequency: {raw!r}. "
        "Use '1d' (daily), '1m' (minute), 'tick', '5m', '15m', '30m', or '60m'."
    )


def _normalize_result_source(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"auto", "research", "detail"}:
        return value
    raise ConfigError("result_source must be one of: auto, research, detail")


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


def _parse_optional_float(name: str, value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be numeric")
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be numeric") from exc


def _parse_bool(value: Any, *, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(f"boolean value expected, got {value!r}")


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
