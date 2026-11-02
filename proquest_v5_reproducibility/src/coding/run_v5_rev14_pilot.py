"""Checkpointed revision 14 development runner; live calls require explicit --run-live.

The input CSV must exist inside the authorized Workbench and contain GOID, title,
abstract; it may contain other GOIDs, which are never sent. Checkpoints contain
codes and usage only, never source text. The local
fixture mode exists solely to dry-run routing/validation without network access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from build_v5_calibration_packages import numbered_evidence
from normalize_v5_rev13 import normalize_content, normalize_scope
from validate_v5_rev14_pilot import ARTIFACTS, check_content, check_content_hard_rules, check_scope, derive_unit, schema_errors

RUNNER_VERSION = "rev14_scope_clarification_v1"


class QuotaPause(Exception):
    def __init__(self, reason: str):
        super().__init__(f"Proxy returned HTTP 429 ({reason}); run paused")
        self.reason = reason


class FatalConfigurationError(Exception):
    pass


class RecordFailure(Exception):
    def __init__(self, category: str, usage: dict | None = None, response_meta: dict | None = None):
        super().__init__(category)
        self.category = category
        self.usage = usage or {}
        self.response_meta = response_meta or {}


class TransientResponseError(ValueError):
    """Incomplete paid response with safe usage and response identifiers."""

    def __init__(self, message: str, usage: dict | None = None,
                 response_meta: dict | None = None):
        super().__init__(message)
        self.usage = usage if isinstance(usage, dict) else {}
        self.response_meta = response_meta if isinstance(response_meta, dict) else {}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_inputs(path: Path, pilot_goids: Path) -> list[dict[str, str]]:
    expected = [row["GOID"] for row in load_csv(pilot_goids)]
    if len(expected) != 40 or len(set(expected)) != 40:
        raise ValueError("Pilot manifest must contain 40 distinct GOIDs")
    records = load_csv(path)
    by_goid = {row["GOID"]: row for row in records}
    if len(by_goid) != len(records) or not set(expected) <= set(by_goid):
        raise ValueError("Input CSV has duplicates or lacks a pilot GOID")
    if any(not by_goid[goid]["abstract"].strip() for goid in expected):
        raise ValueError("Blank abstract in pilot input")
    return [by_goid[goid] for goid in expected]


def sentence_ids(record: dict[str, str]) -> tuple[list[str], str]:
    evidence = numbered_evidence(record["title"], record["abstract"])
    ids = [line.split("]", 1)[0][1:] for line in evidence.splitlines()]
    return ids, evidence


def load_checkpoint(path: Path, run_identity: dict) -> tuple[dict, dict, dict]:
    completed = {}
    invalid = {}
    failed = {}
    if not path.exists():
        return completed, invalid, failed
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item["run_identity"] != run_identity:
                raise ValueError("Checkpoint identity differs from frozen pilot configuration")
            if item["event"] == "validated":
                key = item["stage"], item["GOID"]
                if key in completed:
                    raise ValueError(f"Duplicate completed stage/GOID: {key}")
                completed[key] = item
                invalid.pop(key, None)
            elif item["event"] == "invalid":
                invalid[item["stage"], item["GOID"]] = item
            elif item["event"] == "failed":
                failed[item["stage"], item["GOID"]] = item
    return completed, invalid, failed


def append_checkpoint(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def estimate_request_tokens(prompt: str, schema: dict, user_data: dict, max_tokens: int) -> int:
    """Conservative reservation; actual service usage replaces it after a response."""
    input_bytes = len(prompt.encode("utf-8"))
    input_bytes += len(json.dumps(schema, ensure_ascii=False).encode("utf-8"))
    input_bytes += len(json.dumps(user_data, ensure_ascii=False).encode("utf-8"))
    return math.ceil(input_bytes / 3) + max_tokens


def recent_token_usage(path: Path, now: datetime, window_seconds: int = 65) -> list[tuple[datetime, int]]:
    if not path.exists():
        return []
    recent = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            usage = row.get("usage") or {}
            tokens = usage.get("total_tokens")
            if tokens is None:
                tokens = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
            if not isinstance(tokens, (int, float)) or tokens <= 0:
                continue
            at = datetime.fromisoformat(row["timestamp_utc"])
            if 0 <= (now - at).total_seconds() < window_seconds:
                recent.append((at, math.ceil(tokens)))
    return recent


def pace_before_request(checkpoint: Path, *, prompt: str, schema: dict, user_data: dict,
                        max_tokens: int, tokens_per_minute: int) -> None:
    reservation = estimate_request_tokens(prompt, schema, user_data, max_tokens)
    if reservation > tokens_per_minute:
        raise FatalConfigurationError(
            f"Estimated single request {reservation} tokens exceeds pacing target {tokens_per_minute}; raise target only after checking proxy limits")
    while True:
        now = datetime.now(timezone.utc)
        recent = recent_token_usage(checkpoint, now)
        used = sum(tokens for _, tokens in recent)
        if used + reservation <= tokens_per_minute:
            return
        wait_seconds = max(1.0, 65 - (now - min(at for at, _ in recent)).total_seconds() + 1)
        print(f"Pacing: {used} recent tokens; reserving {reservation}; waiting {math.ceil(wait_seconds)} seconds", flush=True)
        time.sleep(min(wait_seconds, 60))


def invoke_live(*, base_url: str, key: str, model: str, prompt: str, schema: dict,
                user_data: dict, max_tokens: int, seed: int | None,
                policy_400_handler=None) -> tuple[dict, dict, dict]:
    request_body = {
        "model": model, "temperature": 0, "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": prompt},
                     {"role": "user", "content": json.dumps(user_data, ensure_ascii=False)}],
        "response_format": {"type": "json_schema", "json_schema": schema},
    }
    if seed is not None:
        request_body["seed"] = seed
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 400 and policy_400_handler is not None:
            record_category = policy_400_handler(exc)
            if record_category:
                raise RecordFailure(record_category) from exc
        # Do not log request data, token, or source text. The service's error
        # body may echo them, so only report status and a bounded category.
        if exc.code == 429:
            reason = "unspecified_limit"
            try:
                raw = json.loads(exc.read(4096))
                error = raw.get("error", {})
                message = str(error.get("message") or "").lower()
                if "token/minute" in message or "tokens per minute" in message:
                    reason = "token_per_minute"
                elif "cost/day" in message or "spend/day" in message or "daily" in message:
                    reason = "daily_spend"
            except (ValueError, TypeError, AttributeError):
                pass
            raise QuotaPause(reason) from exc
        category = ""
        try:
            raw = json.loads(exc.read(4096))
            error = raw.get("error", {})
            category = str(error.get("code") or error.get("innererror", {}).get("code") or error.get("type") or "")[:80].lower()
        except (ValueError, TypeError, AttributeError):
            pass
        if category in {"content_filter", "content_filter_error", "content_policy_violation", "content_filtered"}:
            raise RecordFailure("content_filtered") from exc
        if exc.code in {400, 401, 403, 404, 405, 413, 415, 422}:
            raise FatalConfigurationError(f"Proxy rejected request with HTTP {exc.code}; category={category or 'unavailable'}") from exc
        raise RuntimeError(f"Proxy returned HTTP {exc.code}") from exc
    choice = body["choices"][0]
    meta = {"response_id": str(body.get("id") or ""),
            "response_model": body.get("model"),
            "system_fingerprint": body.get("system_fingerprint")}
    usage = body.get("usage") or {}
    if choice.get("finish_reason") == "content_filter" or choice.get("message", {}).get("refusal"):
        raise RecordFailure("content_filtered", usage, meta)
    if choice.get("finish_reason") != "stop":
        raise TransientResponseError("Model response did not finish cleanly", usage, meta)
    try:
        response_text = choice["message"]["content"]
        return json.loads(response_text), usage, meta
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise TransientResponseError("Model response was not valid JSON", usage, meta) from exc


def invoke_fixture(folder: Path, stage: str, goid: str, attempt: int) -> tuple[dict, dict, dict]:
    path = folder / f"{stage}_{goid}_attempt{attempt}.json"
    if not path.exists():
        path = folder / f"{stage}_{goid}.json"
    return json.loads(path.read_text(encoding="utf-8")), {}, {"response_id": f"fixture:{stage}:{goid}", "response_model": "synthetic_fixture", "system_fingerprint": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--pilot-goids", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-live", action="store_true")
    mode.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--base-url", help="Workbench proxy base URL; live mode only")
    parser.add_argument("--key-file", type=Path, help="Workbench-provided key file; live mode only")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--seed", type=int, help="Optional; set only after Workbench compatibility check")
    parser.add_argument("--pace-tpm", type=int, default=30000,
                        help="Conservative per-minute token target; default 30000")
    args = parser.parse_args()
    if args.run_live and (not args.base_url or not args.key_file):
        parser.error("Live mode requires Workbench proxy base URL and key file")
    if args.max_attempts < 1:
        parser.error("max-attempts must be positive")
    if args.pace_tpm < 1:
        parser.error("pace-tpm must be positive")
    artifacts_manifest = json.loads((ARTIFACTS / "manifest.json").read_text(encoding="utf-8"))
    pilot_manifest = json.loads((args.pilot_goids.parent / "manifest.json").read_text(encoding="utf-8"))
    if pilot_manifest["codebook_sha256"] != artifacts_manifest["codebook_sha256"]:
        raise ValueError("Pilot and prompt codebook hashes differ")
    for filename, expected in artifacts_manifest["file_sha256"].items():
        if digest(ARTIFACTS / filename) != expected:
            raise ValueError(f"Frozen artifact changed: {filename}")
    if digest(args.pilot_goids) != pilot_manifest["pilot_goids_sha256"]:
        raise ValueError("Pilot GOID file changed")
    records = load_inputs(args.input_csv, args.pilot_goids)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_identity = {"codebook_sha256": artifacts_manifest["codebook_sha256"],
                    "pilot_goids_sha256": pilot_manifest["pilot_goids_sha256"],
                    "model": args.model, "mode": "live" if args.run_live else "offline_fixture",
                    "input_sha256": digest(args.input_csv),
                    "artifact_hashes": artifacts_manifest["file_sha256"],
                    "normalizer_sha256": digest(Path(__file__).with_name("normalize_v5_rev13.py")),
                    "validator_sha256": digest(Path(__file__).with_name("validate_v5_rev14_pilot.py")),
                    "seed": args.seed,
                    "request_protocol_version": RUNNER_VERSION}
    checkpoint = args.output_dir / "pilot_checkpoints.jsonl"
    done, invalid, failed = load_checkpoint(checkpoint, run_identity)
    key = args.key_file.read_text(encoding="utf-8").strip() if args.run_live else ""
    stages = (("scope_full", "scope_prompt.md", "scope_full_schema.json"),
              ("content", "content_prompt.md", "content_schema.json"))
    for stage, prompt_name, schema_name in stages:
        prompt = (ARTIFACTS / prompt_name).read_text(encoding="utf-8")
        schema = json.loads((ARTIFACTS / schema_name).read_text(encoding="utf-8"))
        for record in records:
            goid = record["GOID"]
            if (stage, goid) in done or (stage, goid) in failed:
                continue
            ids, evidence = sentence_ids(record)
            source = {"record_id": goid, "numbered_evidence": evidence}
            if stage == "content":
                full = done.get(("scope_full", goid))
                if full is None:
                    if ("scope_full", goid) in failed:
                        continue
                    raise ValueError("Content phase reached without frozen full scope")
                if full["record_status"] != "in_scope":
                    continue
                target_ids = full["target_aim_ids"]
                source["target_aim_ids"] = target_ids
                source["frozen_scope_units"] = full["codes"]["scope_units"]
            prior_invalid = invalid.get((stage, goid))
            for attempt in range(1, args.max_attempts + 1):
                try:
                    request_source = source
                    if prior_invalid is not None:
                        request_source = {
                            **source,
                            "previous_response": prior_invalid["codes"],
                            "validation_errors": prior_invalid["validation_errors"][:12],
                            "correction_instruction": (
                                "Revise the complete previous response using the same numbered evidence, "
                                "codebook and schema. Resolve each listed validation error from the "
                                "evidence; do not guess or merely change status to pass validation."
                            ),
                        }
                    if args.run_live:
                        token_cap = 5000 if stage == "content" else 7000
                        pace_before_request(checkpoint, prompt=prompt, schema=schema,
                                            user_data=request_source, max_tokens=token_cap,
                                            tokens_per_minute=args.pace_tpm)
                        payload, usage, response_meta = invoke_live(
                            base_url=args.base_url, key=key, model=args.model, prompt=prompt,
                            schema=schema, user_data=request_source, max_tokens=token_cap,
                            seed=args.seed)
                    else:
                        payload, usage, response_meta = invoke_fixture(args.fixture_dir, stage, goid, attempt)
                    raw_payload = payload
                    errors = schema_errors(raw_payload, schema["schema"])
                    rule_log, rule_flags = [], []
                    if not errors and stage == "content":
                        payload, rule_log, rule_flags = normalize_content(raw_payload, full["codes"]["scope_units"], derive_unit)
                        errors = check_content(payload, record_id=goid, target_aim_ids=target_ids)
                        errors.extend(check_content_hard_rules(payload, scope_units=full["codes"]["scope_units"]))
                        status, targets = "completed", target_ids
                    elif not errors:
                        payload, rule_log, rule_flags = normalize_scope(raw_payload, stage)
                        errors, status, targets = check_scope(payload, arm=stage, record_id=goid,
                                                               sentence_ids=set(ids))
                    else:
                        status, targets = "invalid", []
                    if errors:
                        item = {"event": "invalid", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "runner_version": RUNNER_VERSION,
                                "run_identity": run_identity, "stage": stage, "GOID": goid,
                                "codes": payload, "raw_codes": raw_payload,
                                "rule_fills": rule_log, "rule_conflicts": rule_flags,
                                "validation_errors": errors[:20],
                                "usage": usage, **response_meta, "attempt": attempt}
                        append_checkpoint(checkpoint, item)
                        prior_invalid = item
                        invalid[(stage, goid)] = item
                        if attempt == args.max_attempts:
                            raise ValueError("Response failed schema or coding validation: " + "; ".join(errors[:5]))
                        continue
                    item = {"event": "validated", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "runner_version": RUNNER_VERSION,
                            "run_identity": run_identity, "stage": stage, "GOID": goid,
                            "record_status": status, "target_aim_ids": targets,
                            "codes": payload, "raw_codes": raw_payload,
                            "rule_fills": rule_log, "rule_conflicts": rule_flags,
                            "usage": usage, **response_meta, "attempt": attempt,
                            "content_hard_rule_diagnostics": [],
                            "repair_of_response_id": prior_invalid["response_id"] if prior_invalid else None}
                    append_checkpoint(checkpoint, item)
                    done[(stage, goid)] = item
                    invalid.pop((stage, goid), None)
                    break
                except QuotaPause as exc:
                    append_checkpoint(checkpoint, {"event": "paused_quota", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                                   "runner_version": RUNNER_VERSION,
                                                   "run_identity": run_identity, "stage": stage, "GOID": goid,
                                                   "quota_reason": exc.reason, "pace_tpm": args.pace_tpm})
                    print(str(exc), file=sys.stderr)
                    return 75
                except FatalConfigurationError:
                    raise
                except RecordFailure as exc:
                    item = {"event": "failed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "runner_version": RUNNER_VERSION, "run_identity": run_identity,
                            "stage": stage, "GOID": goid, "failure_category": exc.category,
                            "usage": exc.usage, **exc.response_meta, "attempt": attempt}
                    append_checkpoint(checkpoint, item)
                    failed[(stage, goid)] = item
                    break
                except (ValueError, RuntimeError, urllib.error.URLError, KeyError) as exc:
                    if attempt == args.max_attempts:
                        item = {"event": "failed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "runner_version": RUNNER_VERSION, "run_identity": run_identity,
                                "stage": stage, "GOID": goid, "failure_category": "response_or_transient_error",
                                "error_type": type(exc).__name__, "attempt": attempt}
                        append_checkpoint(checkpoint, item)
                        failed[(stage, goid)] = item
                        break
                    time.sleep(min(2 ** attempt, 8))
    excluded = [record["GOID"] for record in records if ("scope_full", record["GOID"]) in done and
                done[("scope_full", record["GOID"])]["record_status"] in {"out_of_scope", "undetermined"}]
    blind = args.output_dir / "blind_review_goids.csv"
    if blind.exists():
        existing = [row["GOID"] for row in load_csv(blind)]
        if existing != excluded:
            raise ValueError("Existing blind review list differs from frozen scope results")
    else:
        with blind.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["GOID"])
            writer.writeheader()
            writer.writerows({"GOID": goid} for goid in excluded)
    summary = {"status": ("development_retest_incomplete_failures" if failed else "development_retest_complete_comparison_pending") if args.run_live else "offline_fixture_dry_run_only",
               "codebook_sha256": artifacts_manifest["codebook_sha256"],
               "n": len(records),
               "validated_by_stage": {s: sum(stage == s for stage, _ in done) for s, _, _ in stages},
               "failed_by_stage": {s: sum(stage == s for stage, _ in failed) for s, _, _ in stages},
               "full_scope_status_counts": {s: sum(row["record_status"] == s for (stage, _), row in done.items() if stage == "scope_full")
                                                          for s in ("in_scope", "out_of_scope", "undetermined")},
               "content_hard_rule_warning_records": sum(bool(row.get("content_hard_rule_diagnostics"))
                                                        for (stage, _), row in done.items() if stage == "content"),
               "rule_fills_by_stage": {s: sum(len(row.get("rule_fills", [])) for (stage, _), row in done.items() if stage == s)
                                       for s, _, _ in stages},
               "rule_conflict_records_by_stage": {s: sum(bool(row.get("rule_conflicts")) for (stage, _), row in done.items() if stage == s)
                                                  for s, _, _ in stages},
               "blind_review_n": len(excluded), "checkpoint": checkpoint.name,
               "blind_review_goids": blind.name}
    (args.output_dir / "pilot_run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if args.run_live and failed else 0


if __name__ == "__main__":
    sys.exit(main())

