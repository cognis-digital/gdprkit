"""GDPRKIT core engine - real compliance logic, stdlib only."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

# GDPR Art. 12(3): respond to a DSAR without undue delay and within one month.
# Operationalised as 30 calendar days, extendable by 2 further months (60 days)
# for complex/numerous requests.
DSAR_LEGAL_DAYS = 30
DSAR_EXTENSION_DAYS = 60

# Lawful bases under GDPR Art. 6(1).
LAWFUL_BASES = {
    "consent",
    "contract",
    "legal_obligation",
    "vital_interests",
    "public_task",
    "legitimate_interests",
}

# Special-category data under Art. 9 requires an Art. 9(2) condition, not just Art. 6.
SPECIAL_CATEGORIES = {
    "racial",
    "ethnic",
    "political",
    "religious",
    "philosophical",
    "trade_union",
    "genetic",
    "biometric",
    "health",
    "sex_life",
    "sexual_orientation",
}

# Valid DSAR request types under GDPR Ch. III.
DSAR_TYPES = {
    "access",        # Art. 15
    "rectification", # Art. 16
    "erasure",       # Art. 17
    "restriction",   # Art. 18
    "portability",   # Art. 20
    "objection",     # Art. 21
}

# Cookie categories. Only "strictly_necessary" is exempt from prior consent
# under the ePrivacy Directive Art. 5(3).
CONSENT_REQUIRED_CATEGORIES = {"functional", "analytics", "marketing", "social", "advertising"}
EXEMPT_CATEGORIES = {"strictly_necessary", "essential"}


def _parse_date(value: str) -> _dt.date:
    """Parse an ISO date (YYYY-MM-DD). Raises ValueError on bad input."""
    return _dt.date.fromisoformat(value)


# --------------------------------------------------------------------------- #
# DSAR tracking
# --------------------------------------------------------------------------- #
@dataclass
class DSARRequest:
    """A single data-subject request with deadline computation."""
    id: str
    subject: str
    type: str
    received: str                 # ISO date
    extended: bool = False
    fulfilled: str | None = None  # ISO date or None

    def __post_init__(self) -> None:
        if self.type not in DSAR_TYPES:
            raise ValueError(
                f"unknown DSAR type {self.type!r}; expected one of {sorted(DSAR_TYPES)}"
            )
        # Validate dates eagerly so bad data fails fast.
        _parse_date(self.received)
        if self.fulfilled is not None:
            _parse_date(self.fulfilled)

    @property
    def allowed_days(self) -> int:
        return DSAR_EXTENSION_DAYS if self.extended else DSAR_LEGAL_DAYS

    def due_date(self) -> _dt.date:
        return _parse_date(self.received) + _dt.timedelta(days=self.allowed_days)

    def evaluate(self, today: _dt.date | None = None) -> dict[str, Any]:
        today = today or _dt.date.today()
        due = self.due_date()
        if self.fulfilled is not None:
            fulfilled = _parse_date(self.fulfilled)
            late = fulfilled > due
            status = "closed_late" if late else "closed_ontime"
            days_remaining = (due - fulfilled).days
        else:
            days_remaining = (due - today).days
            if days_remaining < 0:
                status = "overdue"
            elif days_remaining <= 7:
                status = "due_soon"
            else:
                status = "open"
        return {
            "id": self.id,
            "subject": self.subject,
            "type": self.type,
            "received": self.received,
            "due": due.isoformat(),
            "extended": self.extended,
            "fulfilled": self.fulfilled,
            "days_remaining": days_remaining,
            "status": status,
        }


class DSARTracker:
    """Holds a set of DSARs and produces a compliance summary."""

    def __init__(self, requests: list[DSARRequest]):
        self.requests = requests

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> "DSARTracker":
        reqs = [
            DSARRequest(
                id=str(r["id"]),
                subject=str(r.get("subject", "")),
                type=str(r["type"]),
                received=str(r["received"]),
                extended=bool(r.get("extended", False)),
                fulfilled=(str(r["fulfilled"]) if r.get("fulfilled") else None),
            )
            for r in records
        ]
        return cls(reqs)

    def report(self, today: _dt.date | None = None) -> dict[str, Any]:
        rows = [r.evaluate(today) for r in self.requests]
        overdue = [r for r in rows if r["status"] == "overdue"]
        late = [r for r in rows if r["status"] == "closed_late"]
        due_soon = [r for r in rows if r["status"] == "due_soon"]
        return {
            "total": len(rows),
            "overdue": len(overdue),
            "due_soon": len(due_soon),
            "closed_late": len(late),
            "compliant": len(overdue) == 0 and len(late) == 0,
            "requests": rows,
        }


# --------------------------------------------------------------------------- #
# RoPA validation (GDPR Art. 30)
# --------------------------------------------------------------------------- #
@dataclass
class ROPAEntry:
    name: str
    purpose: str = ""
    lawful_basis: str = ""
    categories: list[str] = field(default_factory=list)
    retention: str = ""
    recipients: list[str] = field(default_factory=list)
    international_transfer: bool = False
    transfer_safeguard: str = ""


def validate_ropa(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate processing-activity records against Art. 30 requirements."""
    results: list[dict[str, Any]] = []
    for raw in records:
        entry = ROPAEntry(
            name=str(raw.get("name", "")),
            purpose=str(raw.get("purpose", "")),
            lawful_basis=str(raw.get("lawful_basis", "")),
            categories=list(raw.get("categories", [])),
            retention=str(raw.get("retention", "")),
            recipients=list(raw.get("recipients", [])),
            international_transfer=bool(raw.get("international_transfer", False)),
            transfer_safeguard=str(raw.get("transfer_safeguard", "")),
        )
        issues: list[str] = []
        if not entry.name:
            issues.append("missing activity name")
        if not entry.purpose:
            issues.append("missing purpose of processing (Art. 30(1)(b))")
        if not entry.lawful_basis:
            issues.append("missing lawful basis (Art. 6(1))")
        elif entry.lawful_basis not in LAWFUL_BASES:
            issues.append(
                f"invalid lawful basis {entry.lawful_basis!r}; expected one of {sorted(LAWFUL_BASES)}"
            )
        if not entry.categories:
            issues.append("missing categories of data subjects/data (Art. 30(1)(c))")
        if not entry.retention:
            issues.append("missing retention/erasure period (Art. 30(1)(f))")
        # Special-category data on consent/contract alone is a flag.
        special = sorted(set(entry.categories) & SPECIAL_CATEGORIES)
        if special:
            issues.append(
                "special-category data " + ",".join(special) + " requires an Art. 9(2) condition"
            )
        # International transfers need a safeguard (Art. 44-49).
        if entry.international_transfer and not entry.transfer_safeguard:
            issues.append("international transfer without safeguard (Art. 44-49)")
        results.append(
            {
                "name": entry.name or "<unnamed>",
                "valid": not issues,
                "issues": issues,
            }
        )
    invalid = [r for r in results if not r["valid"]]
    return {
        "total": len(results),
        "invalid": len(invalid),
        "compliant": len(invalid) == 0,
        "activities": results,
    }


# --------------------------------------------------------------------------- #
# Cookie-consent audit (ePrivacy Art. 5(3) + GDPR consent)
# --------------------------------------------------------------------------- #
def audit_cookies(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit cookies for valid prior consent / categorization."""
    results: list[dict[str, Any]] = []
    for raw in records:
        name = str(raw.get("name", ""))
        category = str(raw.get("category", "")).lower()
        consent_before_set = bool(raw.get("consent_before_set", False))
        provider = str(raw.get("provider", ""))
        third_party = bool(raw.get("third_party", False))
        expiry_days = raw.get("expiry_days")
        issues: list[str] = []

        if not name:
            issues.append("missing cookie name")
        if not category:
            issues.append("missing category")
        elif category not in (CONSENT_REQUIRED_CATEGORIES | EXEMPT_CATEGORIES):
            issues.append(f"unknown category {category!r}")

        needs_consent = category in CONSENT_REQUIRED_CATEGORIES
        if needs_consent and not consent_before_set:
            issues.append("non-essential cookie set before consent (ePrivacy Art. 5(3))")
        if third_party and not provider:
            issues.append("third-party cookie without disclosed provider")
        # Flag implausibly long-lived consent cookies (>13 months guidance, CNIL).
        try:
            if expiry_days is not None and int(expiry_days) > 395:
                issues.append("expiry exceeds 13-month consent-lifetime guidance")
        except (TypeError, ValueError):
            issues.append("invalid expiry_days value")

        results.append(
            {
                "name": name or "<unnamed>",
                "category": category or "<none>",
                "needs_consent": needs_consent,
                "valid": not issues,
                "issues": issues,
            }
        )
    noncompliant = [r for r in results if not r["valid"]]
    return {
        "total": len(results),
        "noncompliant": len(noncompliant),
        "compliant": len(noncompliant) == 0,
        "cookies": results,
    }
