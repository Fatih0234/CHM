"""Cross-milestone critical-path smoke gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTEST_BIN = ROOT / ".venv" / "bin" / "pytest"

SMOKE_SUITES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("schema-hard-gate", ("tests/integration/test_schema_constraints.py",)),
    ("api-contract-smoke", ("tests/contract/test_clients_pipelines_runs_api.py",)),
    ("summary-smoke", ("tests/integration/test_runs_latest_and_filters.py", "-k", "summary")),
    ("ingestion-idempotency-smoke", ("tests/integration/test_ingestion_idempotency.py",)),
    (
        "ingestion-progression-smoke",
        ("tests/integration/test_ingestion_progression_and_pagination.py",),
    ),
    ("alert-rules-contract-gate", ("tests/contract/test_alert_rules_api.py",)),
    ("alert-rules-scope-gate", ("tests/integration/test_alert_rules_scope.py",)),
)


def test_critical_path_gate_executes_required_smoke_suites() -> None:
    assert PYTEST_BIN.exists(), f"Missing pytest binary at {PYTEST_BIN}"

    failures: list[str] = []
    for suite_name, suite_args in SMOKE_SUITES:
        completed = subprocess.run(
            [str(PYTEST_BIN), *suite_args, "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if completed.returncode != 0:
            failure_output = "\n".join(
                line
                for line in (completed.stdout + "\n" + completed.stderr).splitlines()
                if line.strip()
            )
            failures.append(
                f"[{suite_name}] command failed with exit={completed.returncode}\n{failure_output}",
            )

    assert not failures, "\n\n".join(failures)

