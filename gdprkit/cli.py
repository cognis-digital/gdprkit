"""GDPRKIT command-line interface."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from typing import Any

from . import TOOL_NAME, TOOL_VERSION
from .core import DSARTracker, validate_ropa, audit_cookies


def _load_records(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        # allow {"records": [...]} wrapper
        for key in ("records", "requests", "activities", "cookies", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
        raise ValueError("input object must contain a list under a known key")
    if not isinstance(data, list):
        raise ValueError("input must be a JSON list or wrapper object")
    return data


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print("(no rows)")
        return
    widths = {c: len(c) for c in columns}
    str_rows = []
    for r in rows:
        sr = {}
        for c in columns:
            v = r.get(c, "")
            if isinstance(v, list):
                v = "; ".join(str(x) for x in v)
            sr[c] = str(v)
            widths[c] = max(widths[c], len(sr[c]))
        str_rows.append(sr)
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("  ".join("-" * widths[c] for c in columns))
    for sr in str_rows:
        print("  ".join(sr[c].ljust(widths[c]) for c in columns))


def _emit(payload: dict[str, Any], rows: list[dict[str, Any]], columns: list[str], fmt: str) -> None:
    if fmt == "json":
        _print_json(payload)
    else:
        _print_table(rows, columns)
        summary = {k: v for k, v in payload.items() if not isinstance(v, list)}
        print("")
        print("summary: " + "  ".join(f"{k}={v}" for k, v in summary.items()))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=TOOL_NAME, description="GDPR/CCPA DSAR, RoPA, and cookie-consent toolkit")
    p.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument("--format", choices=("table", "json"), default="table")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("dsar", help="track data-subject access requests and deadlines")
    d.add_argument("input", help="JSON file of DSAR records")
    d.add_argument("--today", help="override today's date (YYYY-MM-DD) for deadline calc")

    r = sub.add_parser("ropa", help="validate Record of Processing Activities (Art. 30)")
    r.add_argument("input", help="JSON file of processing-activity records")

    c = sub.add_parser("cookies", help="audit cookie-consent compliance (ePrivacy Art. 5(3))")
    c.add_argument("input", help="JSON file of cookie records")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    fmt = args.format

    try:
        records = _load_records(args.input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: could not load input: {exc}", file=sys.stderr)
        return 2

    try:
        if args.command == "dsar":
            today = _dt.date.fromisoformat(args.today) if args.today else None
            payload = DSARTracker.from_records(records).report(today)
            cols = ["id", "subject", "type", "received", "due", "days_remaining", "status"]
            _emit(payload, payload["requests"], cols, fmt)
            return 0 if payload["compliant"] else 1
        elif args.command == "ropa":
            payload = validate_ropa(records)
            cols = ["name", "valid", "issues"]
            _emit(payload, payload["activities"], cols, fmt)
            return 0 if payload["compliant"] else 1
        elif args.command == "cookies":
            payload = audit_cookies(records)
            cols = ["name", "category", "needs_consent", "valid", "issues"]
            _emit(payload, payload["cookies"], cols, fmt)
            return 0 if payload["compliant"] else 1
    except (ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
