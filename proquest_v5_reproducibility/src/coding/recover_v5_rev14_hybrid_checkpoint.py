"""Safely recover a stopped hybrid Workbench after an instance interruption.

Only a trailing incomplete checkpoint event may be removed. Its raw bytes are
preserved privately for audit; no completed event is altered or exported here.
Never run this while a worker or supervisor process is alive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


def dead_owner(path: Path, pattern: str) -> bool:
    if not path.exists():
        return False
    match = re.fullmatch(pattern, path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"Unknown lock format: {path.name}; inspect manually")
    pid = int(match.group(1))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 87:
            return True
        raise ValueError(f"Cannot prove {path.name} owner is stopped") from exc
    raise ValueError(f"{path.name} owner PID is still active; do not recover")


def recover(output: Path, checkpoint_name: str) -> dict:
    output = output.resolve()
    if checkpoint_name not in {"production_checkpoints.jsonl", "smoke_checkpoints.jsonl"}:
        raise ValueError("Unknown hybrid checkpoint")
    locks = ((output / ".supervisor.lock", r"pid=(\d+);started_utc=[^\r\n]+\n"),
             (output / ".runner.lock", r"worker=\d+;pid=(\d+)\n"))
    stale = [path for path, pattern in locks if dead_owner(path, pattern)]
    checkpoint = output / checkpoint_name
    repair = "none"
    if checkpoint.exists():
        raw = checkpoint.read_bytes()
        complete, separator, tail = raw.rpartition(b"\n")
        completed_lines = complete.split(b"\n") if separator else []
        for number, line in enumerate(completed_lines, 1):
            try:
                json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Corrupt completed checkpoint line {number}; inspect manually") from exc
        if raw and not raw.endswith(b"\n"):
            try:
                json.loads(tail if separator else raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                damaged = tail if separator else raw
                suffix = hashlib.sha256(damaged).hexdigest()[:16]
                backup = output / f"recovery_truncated_tail_{suffix}_PRIVATE.bin"
                if backup.exists() and backup.read_bytes() != damaged:
                    raise ValueError("Recovery tail backup collision")
                with backup.open("wb") as handle:
                    handle.write(damaged)
                    handle.flush()
                    os.fsync(handle.fileno())
                repaired = complete + b"\n" if separator else b""
                temporary = checkpoint.with_name(checkpoint.name + ".recovery.tmp")
                with temporary.open("wb") as handle:
                    handle.write(repaired)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, checkpoint)
                repair = "truncated_tail_preserved_privately"
            else:
                with checkpoint.open("ab") as handle:
                    handle.write(b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                repair = "completed_final_line_terminated"
    for path in stale:
        path.unlink()
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "checkpoint": checkpoint_name, "repair": repair,
              "stale_locks_removed": [path.name for path in stale],
              "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest() if checkpoint.exists() else None}
    if repair != "none" or stale:
        with (output / "recovery_audit_PRIVATE.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    print(json.dumps(recover(args.output_dir, args.checkpoint), indent=2))


if __name__ == "__main__":
    main()
