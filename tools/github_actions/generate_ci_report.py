from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_many(paths: list[Path]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            items.append(data)
    return items


def _sum_field(rows: list[dict[str, Any]], key: str) -> int:
    return sum(_to_int(row.get(key, 0)) for row in rows)


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (str(r.get("os", "")), str(r.get("python_version", ""))))


def _add_test_detail_table(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.append("")
    lines.append(title)
    lines.append("| OS | Python | Status | Total | Passed | Failed | Errors | Skipped |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|")
    if not rows:
        lines.append("| n/a | n/a | n/a | 0 | 0 | 0 | 0 | 0 |")
        return

    for row in _sort_rows(rows):
        lines.append(
            f"| {row.get('os', 'n/a')} | {row.get('python_version', 'n/a')} | {row.get('status', 'n/a')} "
            f"| {_to_int(row.get('tests', 0))} | {_to_int(row.get('passed', 0))} | {_to_int(row.get('failures', 0))} "
            f"| {_to_int(row.get('errors', 0))} | {_to_int(row.get('skipped', 0))} |"
        )


def _add_security_detail_table(lines: list[str], rows: list[dict[str, Any]]) -> None:
    lines.append("")
    lines.append("### Security details (per OS/Python)")
    lines.append("| OS | Python | Status | pip-audit status | pip-audit vulns | safety status | safety vulns |")
    lines.append("|---|---|---|---|---:|---|---:|")
    if not rows:
        lines.append("| n/a | n/a | n/a | n/a | 0 | n/a | 0 |")
        return

    for row in _sort_rows(rows):
        lines.append(
            f"| {row.get('os', 'n/a')} | {row.get('python_version', 'n/a')} | {row.get('status', 'n/a')} "
            f"| {row.get('pip_audit_status', 'n/a')} | {_to_int(row.get('pip_audit_vulnerabilities', 0))} "
            f"| {row.get('safety_status', 'n/a')} | {_to_int(row.get('safety_vulnerabilities', 0))} |"
        )


def main() -> int:
    artifacts_dir = Path("artifacts")
    unit = _load_many(sorted(artifacts_dir.glob("unit-summary-*/unit-summary.json")))
    e2e = _load_many(sorted(artifacts_dir.glob("e2e-summary-*/e2e-summary.json")))
    security = _load_many(sorted(artifacts_dir.glob("security-summary-*/security-summary.json")))

    unit_total = _sum_field(unit, "tests")
    unit_passed = _sum_field(unit, "passed")
    unit_failed = _sum_field(unit, "failures")
    unit_errors = _sum_field(unit, "errors")
    unit_skipped = _sum_field(unit, "skipped")

    e2e_total = _sum_field(e2e, "tests")
    e2e_passed = _sum_field(e2e, "passed")
    e2e_failed = _sum_field(e2e, "failures")
    e2e_errors = _sum_field(e2e, "errors")
    e2e_skipped = _sum_field(e2e, "skipped")

    pip_audit_vulns = sum(
        _to_int(row.get("pip_audit_vulnerabilities", 0))
        for row in security
        if _to_int(row.get("pip_audit_vulnerabilities", 0)) > 0
    )
    safety_vulns = sum(
        _to_int(row.get("safety_vulnerabilities", 0))
        for row in security
        if _to_int(row.get("safety_vulnerabilities", 0)) > 0
    )

    needs = {
        "Unit tests job": os.getenv("UNIT_TESTS_JOB_RESULT", "unknown"),
        "E2E tests job": os.getenv("E2E_TESTS_JOB_RESULT", "unknown"),
        "Lint job": os.getenv("LINT_JOB_RESULT", "unknown"),
        "Detect secrets job": os.getenv("DETECT_SECRETS_JOB_RESULT", "unknown"),
        "Security check job": os.getenv("SECURITY_CHECK_JOB_RESULT", "unknown"),
    }

    lines: list[str] = []
    lines.append("## CI Report")
    lines.append("")
    lines.append("### Job status")
    lines.append("| Check | Result |")
    lines.append("|---|---|")
    for name, status in needs.items():
        lines.append(f"| {name} | {status} |")

    lines.append("")
    lines.append("### Unit test counts (all matrix runs)")
    lines.append("| Total | Passed | Failed | Errors | Skipped |")
    lines.append("|---:|---:|---:|---:|---:|")
    lines.append(f"| {unit_total} | {unit_passed} | {unit_failed} | {unit_errors} | {unit_skipped} |")
    _add_test_detail_table(lines, "### Unit test details (per OS/Python)", unit)

    lines.append("")
    lines.append("### E2E test counts (all matrix runs)")
    lines.append("| Total | Passed | Failed | Errors | Skipped |")
    lines.append("|---:|---:|---:|---:|---:|")
    lines.append(f"| {e2e_total} | {e2e_passed} | {e2e_failed} | {e2e_errors} | {e2e_skipped} |")
    _add_test_detail_table(lines, "### E2E test details (per OS/Python)", e2e)

    lines.append("")
    lines.append("### Security findings")
    lines.append("| Scanner | Vulnerabilities |")
    lines.append("|---|---:|")
    lines.append(f"| pip-audit | {pip_audit_vulns} |")
    lines.append(f"| safety | {safety_vulns} |")
    _add_security_detail_table(lines, security)

    report = "\n".join(lines) + "\n"
    Path("ci-report.md").write_text(report, encoding="utf-8")

    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with Path(step_summary).open("a", encoding="utf-8") as summary_file:
            summary_file.write(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
