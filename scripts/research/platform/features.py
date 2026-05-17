"""Persistent feature-cache helpers for local-first research."""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def stable_hash(payload: object) -> str:
    """Hash JSON-compatible content deterministically."""

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class FeatureBundle:
    """Loaded or freshly-built feature payload."""

    payload: dict[str, Any]
    cache_key: str
    cache_hit: bool
    build_seconds: float
    cache_dir: Path


class FeatureStore:
    """Persist derived features under `.local/research-cache/`."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or ".local/research-cache")

    def cache_key(
        self,
        *,
        dataset_fingerprint: str,
        feature_spec: dict[str, Any],
        code_version: str,
    ) -> str:
        return stable_hash(
            {
                "dataset_fingerprint": dataset_fingerprint,
                "feature_spec": feature_spec,
                "code_version": code_version,
            }
        )

    def load_or_build(
        self,
        key: str,
        builder: Callable[[], dict[str, Any]],
    ) -> FeatureBundle:
        cache_dir = self.root / key
        payload_path = cache_dir / "features.pkl"
        metadata_path = cache_dir / "metadata.json"
        if payload_path.is_file():
            with payload_path.open("rb") as file:
                payload = pickle.load(file)
            return FeatureBundle(
                payload=payload,
                cache_key=key,
                cache_hit=True,
                build_seconds=0.0,
                cache_dir=cache_dir,
            )

        started = time.perf_counter()
        payload = builder()
        build_seconds = time.perf_counter() - started
        cache_dir.mkdir(parents=True, exist_ok=True)
        with payload_path.open("wb") as file:
            pickle.dump(payload, file, protocol=pickle.HIGHEST_PROTOCOL)
        metadata_path.write_text(
            json.dumps(
                {
                    "cache_key": key,
                    "build_seconds": build_seconds,
                    "created_at_epoch": time.time(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return FeatureBundle(
            payload=payload,
            cache_key=key,
            cache_hit=False,
            build_seconds=build_seconds,
            cache_dir=cache_dir,
        )
