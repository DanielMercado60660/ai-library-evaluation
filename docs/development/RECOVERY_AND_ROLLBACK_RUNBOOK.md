# Recovery and Rollback Runbook

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-10-07
- Scope: Backup, restore, and verification procedures for benchmark run artifacts
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Related Workstream: evaluation-harness, infrastructure-services

## Purpose

Ensures benchmark run artifacts and index state can be backed up, destroyed, restored, and verified — proving recoverability before local alpha promotion.

## Artifact Structure

```
artifacts/
├── runs/
│   ├── index.json                  # Run index (atomic JSON with fcntl locking)
│   └── {run_id}/                   # Per-run artifact directory
│       ├── benchmark-report.json   # Benchmark report for this run
│       ├── trace.jsonl             # Trace events
│       └── ...                     # Additional run artifacts
├── benchmark-report.json           # Latest flat-file report (backward compat)
├── perf-smoke-report.json          # Performance smoke report
└── release-gates/                  # Release gate reports
```

## Backup Procedure

### Manual
```bash
# Back up a specific run
cp -r artifacts/runs/{run_id} /path/to/backup/{run_id}
# Back up the index entry
python -c "
import json; idx = json.load(open('artifacts/runs/index.json'))
entry = [r for r in idx.get('runs', []) if r['run_id'] == '{run_id}']
json.dump(entry[0] if entry else {}, open('/path/to/backup/index-entry.json', 'w'), indent=2)
"
```

### Automated
```bash
uv run python scripts/recovery_drill.py backup --run-id {run_id} --backup-dir /path/to/backup
```

## Restore Procedure

### Manual
```bash
# Restore run artifacts
cp -r /path/to/backup/{run_id} artifacts/runs/{run_id}
# Merge index entry back
# (manually add entry from index-entry.json into artifacts/runs/index.json)
```

### Automated
```bash
uv run python scripts/recovery_drill.py restore --backup-dir /path/to/backup --target-dir artifacts/runs
```

## Verify Procedure

Compares SHA256 checksums of all files in the original and restored directories.

```bash
uv run python scripts/recovery_drill.py verify --original artifacts/runs/{run_id} --restored /path/to/restored/{run_id}
```

## Full Drill Cycle

The drill subcommand executes the complete backup → destroy → restore → verify cycle:

```bash
uv run python scripts/recovery_drill.py drill --run-id {run_id} --backup-dir /tmp/drill-backup --output artifacts/recovery-drill-report.json
```

Steps:
1. **Backup** — copies run directory and index entry to backup location
2. **Destroy** — removes the original run directory (simulates data loss)
3. **Restore** — restores from backup to original location
4. **Verify** — SHA256 checksum comparison confirms byte-identical restoration

## Recovery Drill Report

The drill produces a JSON report at `artifacts/recovery-drill-report.json`:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-02-09T00:00:00Z",
  "drill_steps": ["backup", "destroy", "restore", "verify"],
  "errors": [],
  "status": "pass"
}
```

## When to Run

- Before each version promotion gate
- After any changes to artifact storage or index persistence logic
- As part of the v2.0 RC release gate (`scripts/release_gate_v2_0_rc.py`)
