"""Schemas for governance audit results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditFinding:
    """One governance finding."""

    rule_id: str
    severity: str
    message: str


@dataclass(frozen=True)
class AuditReport:
    """Complete governance audit report."""

    ok: bool
    findings: tuple[AuditFinding, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "findings": [finding.__dict__ for finding in self.findings],
        }
