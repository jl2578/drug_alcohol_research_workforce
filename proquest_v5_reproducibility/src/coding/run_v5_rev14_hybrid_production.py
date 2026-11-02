"""Run one revision-14 hybrid production partition with durable code-only output.

One process owns one assignment and output folder. Workbench XML extraction
must have created the private input CSV first. Quota or transient pauses exit 75 and a
later invocation with identical identity resumes. Final export is withheld
until every assigned GOID has valid scope and every inclusion has content.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import socket
import sys
import time
import urllib.error
from urllib.parse import urlparse
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from normalize_v5_rev13 import normalize_content
from reviewer_scope_single_pass import normalize_scope, scope_codes_sha
from run_v5_rev14_pilot import (
    FatalConfigurationError, QuotaPause, RecordFailure, digest,
    estimate_request_tokens, invoke_fixture, invoke_live as invoke_4o, sentence_ids,
)
from run_v5_rev14_scope_compare import (
    FatalConfigurationError as ScopeFatalConfigurationError,
    QuotaPause as ScopeQuotaPause,
    RecordFailure as ScopeRecordFailure,
    invoke_live as invoke_5,
)
from validate_v5_rev14_pilot import (
    ARTIFACTS, check_content, check_content_hard_rules, check_scope,
    derive_unit, schema_errors,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "config/coding/reviewer_single_pass_v15_freeze.json"
RUNNER_VERSION = "v5_rev15_single_scope_public_rerun_v1"
STAGES = (("scope_full", "scope_prompt.md", "scope_full_schema.json", 12000),
          ("content", "content_prompt.md", "content_schema.json", 8000))
STAGE_MODELS = {"scope_full": "gpt_5_2025_08_07", "content": "gpt_4o_2024_08_06"}
CHECKPOINT = "production_checkpoints.jsonl"
PROGRESS = "production_progress.json"
PACKAGE = "production_export_package.zip"

_HTTP400_PROXY_HOST = "agai-proxy.prod.int.tdmstudio.proquest.com"
_HTTP400_POLICY_CODES = {"content_filter", "content_filtered", "content_filter_error",
                         "content_policy_violation", "responsibleaipolicyviolation"}
_HTTP400_KNOWN_CODES = _HTTP400_POLICY_CODES | {"invalid_request_error", "context_length_exceeded",
                                               "insufficient_quota", "rate_limit_exceeded"}
_HTTP400_KNOWN_PARAMS = {"prompt", "messages", "model", "response_format", "json_schema",
                         "max_completion_tokens", "reasoning_effort"}
_HTTP400_TOP_KEYS = {"error", "errors", "detail", "message", "code", "type", "status",
                     "request_id", "innererror", "inner_error"}


def _http400_nested_json(value):
    if not isinstance(value, str) or not value.strip().startswith(("{", "[")):
        return None
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return None


def _http400_details(payload):
    codes, params, messages = set(), set(), []
    envelope = {"error", "errors", "detail", "details", "innererror", "inner_error"}
    message_fields = {"message", "description", "reason", "error_description", "msg"}

    def visit(value, depth=0):
        if depth > 8:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                key = str(key).lower()
                if key in {"code", "error_code", "errorcode", "type"} and isinstance(child, str):
                    candidate = child.lower()
                    if candidate in _HTTP400_KNOWN_CODES:
                        codes.add(candidate)
                elif key == "param" and isinstance(child, str):
                    candidate = child.lower()
                    if candidate in _HTTP400_KNOWN_PARAMS:
                        params.add(candidate)
                elif key in message_fields and isinstance(child, str):
                    messages.append(child.lower())
                    nested = _http400_nested_json(child)
                    if nested is not None:
                        visit(nested, depth + 1)
                elif key in envelope:
                    if isinstance(child, str):
                        messages.append(child.lower())
                        nested = _http400_nested_json(child)
                        if nested is not None:
                            visit(nested, depth + 1)
                    else:
                        visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value[:20]:
                visit(child, depth + 1)

    visit(payload)
    policy_phrase = any(
        (("content management policy" in message or "content policy" in message
          or "content filter" in message)
         and ("filtered" in message or "blocked" in message or "rejected" in message
              or "violation" in message))
        for message in messages
    )
    return codes, params, policy_phrase


def _http400_checkpoint_pass(checkpoint, stage, goid):
    if not checkpoint.is_file():
        return ""
    state, retry_seen = "first_pass", False
    try:
        with checkpoint.open(encoding="utf-8") as handle:
            for line in handle:
                event = json.loads(line)
                if event.get("stage") != stage or event.get("GOID") != goid:
                    continue
                kind = event.get("event")
                if kind in {"validated", "failed"}:
                    state = ""
                elif kind == "retry_authorized" and state == "" and not retry_seen:
                    state, retry_seen = "authorized_retry", True
                elif kind == "retry_authorized":
                    return ""
        return state
    except (OSError, ValueError, TypeError):
        return ""


def _http400_isolated_allowed(checkpoint, stage):
    try:
        consecutive = 0
        with checkpoint.open(encoding="utf-8") as handle:
            for line in handle:
                event = json.loads(line)
                if event.get("stage") != stage:
                    continue
                if event.get("event") == "validated":
                    consecutive = 0
                elif (event.get("event") == "failed" and event.get("failure_category")
                      in {"proxy_http400_deferred", "record_context_length"}):
                    consecutive += 1
        return consecutive == 0
    except (OSError, ValueError, TypeError):
        return False


def _classify_http400_response(exc, *, stage, goid, base_url, checkpoint, assigned):
    """Return a record-failure category or leave the original error fatal.

    Only the original ProQuest HTTPS proxy and an assigned, checkpoint-eligible
    record may be deferred. Raw error bodies and evidence are never logged.
    """
    try:
        body = exc.read(65536)
        exc.fp = io.BytesIO(body)
        exc.file = exc.fp
        exc.read = exc.fp.read
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            payload = None
        codes, params, policy_phrase = _http400_details(payload)
        parsed = urlparse(base_url)
        request_ok = (parsed.scheme == "https" and parsed.hostname == _HTTP400_PROXY_HOST
                      and stage in {"scope_full", "content"} and goid in assigned)
        checkpoint_pass = _http400_checkpoint_pass(checkpoint, stage, goid) if request_ok else ""
        configuration = bool(params or codes & {"invalid_request_error", "insufficient_quota",
                                               "rate_limit_exceeded"})
        conflicting = bool(codes & {"context_length_exceeded", "insufficient_quota",
                                    "rate_limit_exceeded"})
        confirmed_policy = (not configuration and not conflicting
                            and (bool(codes & _HTTP400_POLICY_CODES) or policy_phrase))
        category = None
        if checkpoint_pass and confirmed_policy:
            category = "content_filtered"
        elif (checkpoint_pass and not configuration and isinstance(payload, dict)
              and bool(set(payload) & _HTTP400_TOP_KEYS)
              and _http400_isolated_allowed(checkpoint, stage)):
            category = ("record_context_length" if "context_length_exceeded" in codes
                        else "proxy_http400_deferred")
        audit = {"adapter_version": "http400_policy_v3_integrated", "status": 400,
                 "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                 "body_sha256": hashlib.sha256(body).hexdigest(),
                 "body_bytes_read": len(body), "body_is_json": payload is not None,
                 "known_codes": sorted(codes), "known_params": sorted(params),
                 "policy_phrase_confirmed": policy_phrase,
                 "frozen_proxy_request": request_ok, "stage": stage if request_ok else None,
                 "checkpoint_pass": checkpoint_pass, "record_failure_category": category,
                 "action": checkpoint_pass if category == "content_filtered"
                           else "isolated_record_deferred" if category
                           else "leave_original_error"}
        print("HTTP400_POLICY_AUDIT " + json.dumps(audit, sort_keys=True),
              file=sys.stderr, flush=True)
        return category
    except Exception as diagnostic_error:
        print("HTTP400_POLICY_AUDIT unavailable: " + type(diagnostic_error).__name__,
              file=sys.stderr, flush=True)
        return None

# A stage/GOID that pauses this many times in a row without any other event is
# treated as a record failure (e.g. a truncated response), so one record cannot
# stall the worker; the single retry pass still applies to it.
TRANSIENT_PAUSES_BEFORE_FAILURE = 3
SETTLED_STATUSES = {"complete", "scope_complete_held", "scope_complete_with_failures_held",
                    "content_complete_with_failures_held"}


class RollingPacer:
    """Conservative all-token 65-second window, rebuilt once from checkpoint."""

    def __init__(self, checkpoint: Path, target: int):
        self.target = target
        self.recent: deque[tuple[datetime, int]] = deque()
        if checkpoint.exists():
            now = datetime.now(timezone.utc)
            for line in checkpoint.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                usage = item.get("usage") or {}
                tokens = usage.get("total_tokens")
                if tokens is None:
                    tokens = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
                at = datetime.fromisoformat(item["timestamp_utc"])
                if isinstance(tokens, (int, float)) and tokens > 0 and 0 <= (now - at).total_seconds() < 65:
                    self.recent.append((at, math.ceil(tokens)))

    def charge(self, usage: dict) -> None:
        tokens = usage.get("total_tokens")
        if tokens is None:
            tokens = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
        if isinstance(tokens, (int, float)) and tokens > 0:
            self.recent.append((datetime.now(timezone.utc), math.ceil(tokens)))

    def before(self, *, prompt: str, schema: dict, user_data: dict, max_tokens: int) -> None:
        reservation = estimate_request_tokens(prompt, schema, user_data, max_tokens)
        if reservation > self.target:
            raise FatalConfigurationError(
                f"Estimated single request {reservation} tokens exceeds pacing target {self.target}")
        while True:
            now = datetime.now(timezone.utc)
            while self.recent and (now - self.recent[0][0]).total_seconds() >= 65:
                self.recent.popleft()
            used = sum(tokens for _, tokens in self.recent)
            if used + reservation <= self.target:
                return
            wait = max(1.0, 66 - (now - self.recent[0][0]).total_seconds())
            print(f"Pacing: {used} recent tokens; reserving {reservation}; waiting {math.ceil(wait)} seconds", flush=True)
            time.sleep(min(wait, 60))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def append_event(path: Path, event: dict) -> None:
    # Raw invalid model JSON remains in the private Workbench checkpoint;
    # only validated, enum-constrained codes enter the export package.
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    if '"numbered_evidence"' in data or '"abstract"' in data or '"title"' in data:
        raise ValueError("Source text field cannot be checkpointed")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(data + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def scope_units_sha(scope: dict) -> str:
    value = scope["codes"]["scope_units"]
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def check_response_model(stage: str, model: str | None, *, live: bool) -> None:
    if not live:
        return
    expected = {"scope_full": {"gpt-5-2025-08-07", "gpt_5_2025_08_07"},
                "content": {"gpt-4o-2024-08-06", "gpt_4o_2024_08_06"}}[stage]
    if model not in expected:
        raise FatalConfigurationError(f"Unexpected {stage} response model: {model!r}")


def load_checkpoint(path: Path, identity: dict, assigned: set[str]) -> tuple[dict, dict, dict]:
    done: dict[tuple[str, str], dict] = {}
    invalid: dict[tuple[str, str], dict] = {}
    failed: dict[tuple[str, str], dict] = {}
    retried: set[tuple[str, str]] = set()
    if not path.exists():
        return done, invalid, failed
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupt checkpoint line {number}; preserve it for audit") from exc
        if item.get("run_identity") != identity:
            raise ValueError("Checkpoint identity differs from the frozen production run")
        stage, goid, event = item.get("stage"), item.get("GOID"), item.get("event")
        if stage not in {"scope_full", "content"} or goid not in assigned:
            raise ValueError(f"Checkpoint line {number} is outside the assignment")
        key = stage, goid
        if event == "validated":
            if key in done or key in failed:
                raise ValueError(f"Duplicate or post-failure validated response: {key}")
            done[key] = item
            invalid.pop(key, None)
        elif event == "invalid":
            if key in done or key in failed:
                raise ValueError(f"Invalid response follows terminal response: {key}")
            if key in invalid and item["attempt"] <= invalid[key]["attempt"]:
                raise ValueError(f"Invalid attempt numbering regressed: {key}")
            invalid[key] = item
        elif event == "failed":
            if key in done or key in failed:
                raise ValueError(f"Duplicate terminal response: {key}")
            failed[key] = item
            invalid.pop(key, None)
        elif event == "retry_authorized":
            if key not in failed or key in retried:
                raise ValueError(f"Failure retry is missing or repeated: {key}")
            failed.pop(key)
            invalid.pop(key, None)
            retried.add(key)
        elif event not in {"paused_quota", "paused_transient"}:
            raise ValueError(f"Unknown checkpoint event on line {number}")
        if event == "validated":
            check_response_model(stage, item.get("response_model"), live=identity["mode"] == "live")
    for (stage, goid), item in done.items():
        if stage == "content":
            scope = done.get(("scope_full", goid))
            if scope is None or scope["record_status"] != "in_scope":
                raise ValueError(f"Content lacks frozen in-scope decision: {goid}")
            if item["target_aim_ids"] != scope["target_aim_ids"]:
                raise ValueError(f"Content target IDs differ from scope: {goid}")
            if item.get("frozen_scope_units_sha256") != scope_units_sha(scope):
                raise ValueError(f"Content scope units differ from scope: {goid}")
            if item.get("frozen_scope_sha256") != scope_codes_sha(scope["codes"]):
                raise ValueError(f"Content complete scope differs from scope: {goid}")
    return done, invalid, failed


def checkpoint_history(path: Path) -> tuple[set[tuple[str, str]], dict[tuple[str, str], int]]:
    """Return retried stage/GOID pairs and each pair's current run of transient pauses."""
    retried: set[tuple[str, str]] = set()
    streaks: dict[tuple[str, str], int] = {}
    if not path.exists():
        return retried, streaks
    for line in path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        key, event = (item["stage"], item["GOID"]), item["event"]
        if event == "paused_transient":
            streaks[key] = streaks.get(key, 0) + 1
        elif event != "paused_quota":
            streaks.pop(key, None)
        if event == "retry_authorized":
            retried.add(key)
    return retried, streaks


def read_inputs(path: Path, assigned: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"GOID", "title", "abstract"} <= set(reader.fieldnames or []):
            raise ValueError("Private input lacks required fields")
        rows = list(reader)
    by_id = {row["GOID"]: row for row in rows}
    if len(rows) != len(by_id) or set(by_id) != set(assigned):
        raise ValueError("Private input GOIDs differ from selected worker assignment")
    if any(not by_id[g]["title"].strip() or not by_id[g]["abstract"].strip() for g in assigned):
        raise ValueError("Private input contains blank title or abstract")
    return [by_id[g] for g in assigned]


def verify_setup(args: argparse.Namespace) -> tuple[list[dict[str, str]], dict]:
    freeze = load_json(FREEZE)
    if freeze["status"] != "frozen_reviewer_single_pass_v15":
        raise ValueError("Hybrid production freeze is absent")
    if freeze["stage_models"] != STAGE_MODELS:
        raise ValueError("Production stage models differ from frozen profiles")
    for name, expected in freeze["files_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Frozen file changed: {name}")
    manifest = load_json(args.plan_manifest)
    if manifest["purpose"] != "public_reproduction_rerun" or manifest["stage_models"] != STAGE_MODELS:
        raise ValueError("Production plan identity or stage models disagree")
    if manifest["codebook_sha256"] != freeze["files_sha256"]["config/coding/dissertation_codebook_v5_rev15_reproduction.md"]:
        raise ValueError("Production plan and codebook disagree")
    if not 1 <= args.worker_id <= args.worker_count or args.worker_count != manifest["worker_count"]:
        raise ValueError("Worker selection differs from this rerun plan")
    expected_name = f"{args.worker_count}_workbenches_worker_{args.worker_id}_goids.json"
    if args.assignment.name != expected_name:
        raise ValueError("Assignment filename does not match worker selection")
    file_info = manifest["files"][expected_name]
    if digest(args.assignment) != file_info["sha256"]:
        raise ValueError("Assignment file differs from partition manifest")
    assigned = load_json(args.assignment)
    if (not isinstance(assigned, list) or len(assigned) != file_info["count"]
            or len(assigned) != len(set(assigned)) or any(not str(g).isdigit() for g in assigned)):
        raise ValueError("Invalid assignment GOID list")
    if manifest["assessable_count"] < len(assigned):
        raise ValueError("Production assignment count disagrees with plan")
    artifacts = load_json(ARTIFACTS / "manifest.json")
    if artifacts["codebook_sha256"] != manifest["codebook_sha256"]:
        raise ValueError("Stage artifacts and production plan disagree")
    for name, expected in artifacts["file_sha256"].items():
        if digest(ARTIFACTS / name) != expected:
            raise ValueError(f"Stage artifact changed: {name}")
    records = read_inputs(args.input_csv, assigned)
    from extract_v5_rev13_pilot_from_xml import evidence_hash
    with args.reference_hashes.open(encoding="utf-8-sig", newline="") as handle:
        hash_rows = list(csv.DictReader(handle))
    hash_by_id = {row["GOID"]: row for row in hash_rows}
    if len(hash_rows) != len(hash_by_id) or set(hash_by_id) != set(assigned):
        raise ValueError("Reference hash rows differ from worker assignment")
    hash_name = f"hybrid_worker_{args.worker_id}_reference_hashes.csv"
    if digest(args.reference_hashes) != manifest["files"][hash_name]["sha256"]:
        raise ValueError("Reference hash file differs from frozen plan")
    for record in records:
        expected = hash_by_id[record["GOID"]]
        if not (evidence_hash(record["title"], record["abstract"], loose=False) == expected["reference_exact_sha256"]
                or evidence_hash(record["title"], record["abstract"], loose=True) == expected["reference_loose_sha256"]):
            raise ValueError(f"Private input evidence differs for assigned GOID {record['GOID']}")
    identity = {
        "runner_version": RUNNER_VERSION,
        "codebook_sha256": manifest["codebook_sha256"],
        "stage_models": STAGE_MODELS,
        "stage_profiles": freeze["stage_profiles"],
        "mode": "live" if args.run_live else "preflight" if args.preflight_only else "offline_fixture",
        "worker_count": args.worker_count,
        "worker_id": args.worker_id,
        "assignment_sha256": digest(args.assignment),
        "plan_manifest_sha256": digest(args.plan_manifest),
        "input_sha256": digest(args.input_csv),
        "freeze_sha256": digest(FREEZE),
        "runner_sha256": digest(Path(__file__)),
        "scope_invoker_sha256": digest(ROOT / "src/coding/run_v5_rev14_scope_compare.py"),
        "content_invoker_sha256": digest(ROOT / "src/coding/run_v5_rev14_pilot.py"),
        "scope_prompt_sha256": digest(ARTIFACTS / "scope_prompt.md"),
        "content_prompt_sha256": digest(ARTIFACTS / "content_prompt.md"),
        "scope_schema_sha256": digest(ARTIFACTS / "scope_full_schema.json"),
        "content_schema_sha256": digest(ARTIFACTS / "content_schema.json"),
        "normalizer_sha256": digest(ROOT / "src/coding/normalize_v5_rev13.py"),
        "scope_processor_sha256": digest(ROOT / "src/coding/reviewer_scope_single_pass.py"),
        "validator_sha256": digest(ROOT / "src/coding/validate_v5_rev14_pilot.py"),
        "seed": None,
        "reference_hashes_sha256": digest(args.reference_hashes),
        "max_attempts": args.max_attempts,
        "max_tokens_by_stage": {stage: cap for stage, _, _, cap in STAGES},
    }
    return records, identity


def summary(assigned: list[str], done: dict, failed: dict, checkpoint: Path,
            identity: dict, *, paused: str | None, pause_type: str | None, pace_tpm: int,
            release_content: bool, retried: set[tuple[str, str]]) -> dict:
    scopes = {g: done.get(("scope_full", g)) for g in assigned}
    expected_content = {g for g, row in scopes.items() if row and row["record_status"] == "in_scope"}
    completed_content = {g for g in expected_content if ("content", g) in done}
    missing_scope = [g for g, row in scopes.items() if row is None and ("scope_full", g) not in failed]
    missing_content = sorted(expected_content - completed_content - {g for g in expected_content if ("content", g) in failed})
    scope_failures = [pair for pair in failed if pair[0] == "scope_full"]
    scope_complete = not missing_scope and not scope_failures
    # Failures that survived their one retry pass no longer hold back the
    # remaining records; they stay listed and still block a certified export.
    scope_settled = not missing_scope and all(pair in retried for pair in scope_failures)
    failures_retried = all(pair in retried for pair in failed)
    complete = release_content and not paused and scope_complete and not missing_content and not failed
    usage = {stage: {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "calls_with_usage": 0}
             for stage, _, _, _ in STAGES}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            stage = item["stage"]
            u = item.get("usage") or {}
            if stage not in usage or not u:
                continue
            usage[stage]["prompt_tokens"] += u.get("prompt_tokens") or 0
            usage[stage]["cached_tokens"] += (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
            usage[stage]["completion_tokens"] += u.get("completion_tokens") or 0
            usage[stage]["calls_with_usage"] += 1
    state = ("complete" if complete else f"paused_{pause_type}" if paused else
             "scope_complete_held" if scope_complete and not release_content else
             "scope_complete_with_failures_held" if scope_settled and not release_content else
             "content_complete_with_failures_held"
             if release_content and scope_settled and not missing_content and failed and failures_retried
             else "incomplete")
    return {"status": state,
            "run_identity": identity, "assigned_n": len(assigned),
            "scope_validated_n": sum(row is not None for row in scopes.values()),
            "scope_failed_n": len(scope_failures),
            "failed_after_retry_n": sum(pair in retried for pair in failed),
            "failed_awaiting_retry_n": sum(pair not in retried for pair in failed),
            "scope_status_counts": {s: sum(row is not None and row["record_status"] == s for row in scopes.values())
                                    for s in ("in_scope", "out_of_scope", "undetermined")},
            "content_required_n": len(expected_content),
            "content_validated_n": len(completed_content),
            "content_failed_n": sum(stage == "content" for stage, _ in failed),
            "scope_pending_n": len(missing_scope), "content_pending_n": len(missing_content),
            "failed_goids": sorted({g for _, g in failed}),
            "quota_reason": paused if pause_type == "quota" else None,
            "pause_reason": paused, "pause_type": pause_type,
            "pace_tpm_last_run": pace_tpm,
            "usage_by_stage": usage,
            "checkpoint": checkpoint.name,
            "final_export": PACKAGE if complete else None}


def write_progress(output: Path, value: dict) -> None:
    atomic_write(output / PROGRESS, (json.dumps(value, indent=2) + "\n").encode("utf-8"))


def write_failure_report(output: Path, failed: dict, progress: dict) -> None:
    """Code-only diagnostic; unresolved records never count as completed codes."""
    report = {
        "status": "unresolved_record_failures" if failed else "no_unresolved_record_failures",
        "run_identity": progress["run_identity"],
        "checkpoint_sha256": digest(output / CHECKPOINT),
        "failures": [
            {"stage": stage, "GOID": goid,
             "failure_category": item["failure_category"], "attempt": item.get("attempt")}
            for (stage, goid), item in sorted(failed.items())
        ],
    }
    body = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    atomic_write(output / "production_failure_list.json", body)
    package = output / "production_failure_report.zip"
    staging = package.with_name(package.name + ".tmp")
    with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo("production_failure_list.json", date_time=(2026, 9, 29, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, body)
    os.replace(staging, package)


def export_complete(output: Path, assigned: list[str], done: dict, progress: dict) -> None:
    if progress["status"] != "complete":
        raise ValueError("Cannot export incomplete production partition")
    lines = []
    for goid in assigned:
        scope = done[("scope_full", goid)]
        content = done.get(("content", goid))
        if (scope["record_status"] == "in_scope") != (content is not None):
            raise ValueError(f"Content routing mismatch for {goid}")
        row = {"GOID": goid, "record_status": scope["record_status"],
               "target_aim_ids": scope["target_aim_ids"],
               "scope_codes": scope["codes"],
               "content_codes": content["codes"] if content else None,
               "content_frozen_scope_units_sha256": content["frozen_scope_units_sha256"] if content else None,
               "content_frozen_scope_sha256": content["frozen_scope_sha256"] if content else None,
               "scope_response_id": scope.get("response_id"),
               "scope_response_model": scope.get("response_model"),
               "content_response_id": content.get("response_id") if content else None,
               "content_response_model": content.get("response_model") if content else None}
        lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    data = ("\n".join(lines) + "\n").encode("utf-8")
    if b'"numbered_evidence"' in data or b'"abstract"' in data or b'"title"' in data:
        raise ValueError("Source text field found in export")
    target = output / "production_codes.jsonl"
    if target.exists() and target.read_bytes() != data:
        raise ValueError("Existing final export differs from reproducible checkpoint export")
    atomic_write(target, data)
    manifest = {"status": "complete_code_only_export", "records": len(assigned),
                "stage_models": STAGE_MODELS,
                "codebook_sha256": progress["run_identity"]["codebook_sha256"],
                "worker_count": progress["run_identity"]["worker_count"],
                "worker_id": progress["run_identity"]["worker_id"],
                "assignment_sha256": progress["run_identity"]["assignment_sha256"],
                "checkpoint_sha256": digest(output / CHECKPOINT),
                "codes_sha256": hashlib.sha256(data).hexdigest(),
                "codes_file": target.name}
    atomic_write(output / "production_export_manifest.json",
                 (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    package = output / PACKAGE
    staging = package.with_name(package.name + ".tmp")
    with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("production_codes.jsonl", "production_export_manifest.json", PROGRESS):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (output / name).read_bytes())
    if package.exists() and package.read_bytes() != staging.read_bytes():
        staging.unlink()
        raise ValueError("Existing final export package differs from checkpoint export")
    os.replace(staging, package)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--reference-hashes", type=Path, required=True)
    parser.add_argument("--plan-manifest", type=Path, required=True)
    parser.add_argument("--worker-count", type=int, required=True)
    parser.add_argument("--worker-id", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--release-content", action="store_true",
                        help="Release this worker's content only after its scope is complete")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-live", action="store_true")
    mode.add_argument("--fixture-dir", type=Path)
    mode.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--base-url")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--pace-tpm", type=int, help="Per-Workbench target established after bounded throughput check")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--retry-failures-once", action="store_true",
                        help="Authorize one bounded retry pass for terminal record failures under the same identity")
    args = parser.parse_args()
    if args.max_attempts < 1:
        parser.error("max-attempts must be positive")
    if args.run_live and (not args.base_url or not args.key_file or not args.pace_tpm):
        parser.error("Live mode requires proxy URL, Workbench key file and measured pace-tpm")
    if args.pace_tpm is not None and args.pace_tpm <= 0:
        parser.error("pace-tpm must be positive")
    if args.fixture_dir and not args.fixture_dir.is_dir():
        parser.error("Fixture directory is missing")
    records, identity = verify_setup(args)
    assigned = [row["GOID"] for row in records]
    if args.preflight_only:
        print(json.dumps({"preflight": "passed_no_model_calls", "assigned_n": len(assigned),
                          "worker_count": args.worker_count, "worker_id": args.worker_id,
                          "codebook_sha256": identity["codebook_sha256"],
                          "assignment_sha256": identity["assignment_sha256"],
                          "input_sha256": identity["input_sha256"]}, indent=2))
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    lock = args.output_dir / ".runner.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError("Output folder has an active or stale runner lock; inspect before reuse") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"worker={args.worker_id};pid={os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())
        checkpoint = args.output_dir / CHECKPOINT
        done, invalid, failed = load_checkpoint(checkpoint, identity, set(assigned))
        retried, transient_streaks = checkpoint_history(checkpoint)
        scope_first_pass_done = all(("scope_full", g) in done or ("scope_full", g) in failed for g in assigned)
        content_targets = {g for g in assigned if done.get(("scope_full", g), {}).get("record_status") == "in_scope"}
        content_first_pass_done = all(("content", g) in done or ("content", g) in failed for g in content_targets)
        if args.retry_failures_once and failed and (content_first_pass_done if args.release_content else scope_first_pass_done):
            for pair in sorted(set(failed) - retried):
                append_event(checkpoint, {"event": "retry_authorized",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "runner_version": RUNNER_VERSION, "run_identity": identity,
                    "stage": pair[0], "GOID": pair[1]})
                failed.pop(pair)
                retried.add(pair)
                transient_streaks.pop(pair, None)

        def scope_settled() -> bool:
            # Content may run once every scope GOID is validated or has failed
            # again after its single retry pass.
            return (all(("scope_full", g) in done or ("scope_full", g) in failed for g in assigned)
                    and all(pair in retried for pair in failed if pair[0] == "scope_full"))

        if args.release_content and not scope_settled():
            raise ValueError("Content release requires every scope GOID validated, "
                             "or failed again after its one retry pass")
        if args.release_content:
            prior_progress = args.output_dir / PROGRESS
            if not prior_progress.is_file():
                raise ValueError("Content release requires a prior scope-complete progress record")
            recorded = load_json(prior_progress)
            if recorded["run_identity"] != identity or recorded["scope_pending_n"]:
                raise ValueError("Scope-complete progress identity or status differs")
        pacer = RollingPacer(checkpoint, args.pace_tpm) if args.run_live else None
        key = args.key_file.read_text(encoding="utf-8").strip() if args.run_live else ""
        pause_reason = None
        pause_type = None
        for stage, prompt_file, schema_file, token_cap in STAGES:
            if stage == "content":
                if not args.release_content or not scope_settled():
                    break
            prompt = (ARTIFACTS / prompt_file).read_text(encoding="utf-8")
            schema = load_json(ARTIFACTS / schema_file)
            for record in records:
                goid = record["GOID"]
                pair = stage, goid
                if pair in done or pair in failed:
                    continue
                full = done.get(("scope_full", goid))
                if stage == "content":
                    if full is None:
                        continue  # A failed or pending scope cannot be routed to content.
                    if full["record_status"] != "in_scope":
                        continue
                ids, evidence = sentence_ids(record)
                source = {"record_id": goid, "numbered_evidence": evidence}
                if stage == "content":
                    source["target_aim_ids"] = full["target_aim_ids"]
                    source["frozen_scope_units"] = full["codes"]["scope_units"]
                    source["frozen_add_su_focus"] = full["codes"]["add_su_focus"]
                    source["frozen_scope_sha256"] = scope_codes_sha(full["codes"])
                prior = invalid.get(pair)
                first_attempt = (prior["attempt"] + 1) if prior else 1
                if first_attempt > args.max_attempts:
                    # A stopped instance may have durably written the final
                    # invalid event but not yet its terminal marker.
                    failure = {"event": "failed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                               "runner_version": RUNNER_VERSION, "run_identity": identity,
                               "stage": stage, "GOID": goid,
                               "failure_category": "validation_exhausted", "attempt": prior["attempt"]}
                    append_event(checkpoint, failure)
                    failed[pair] = failure
                    invalid.pop(pair, None)
                    continue
                for attempt in range(first_attempt, args.max_attempts + 1):
                    request_source = source
                    if prior:
                        request_source = {**source, "previous_response": prior["codes"],
                                          "validation_errors": prior["validation_errors"][:12],
                                          "correction_instruction": (
                                              "Revise the complete previous response using the same numbered evidence, "
                                              "codebook and schema. Resolve each listed validation error from the evidence; "
                                              "do not guess or merely change status to pass validation.")}
                    started = datetime.now(timezone.utc).isoformat()
                    try:
                        if args.run_live:
                            pacer.before(prompt=prompt, schema=schema, user_data=request_source,
                                         max_tokens=token_cap)
                            invoke = invoke_5 if stage == "scope_full" else invoke_4o
                            payload, usage, meta = invoke(
                                base_url=args.base_url, key=key, model=STAGE_MODELS[stage],
                                prompt=prompt, schema=schema, user_data=request_source,
                                max_tokens=token_cap, seed=None,
                                policy_400_handler=lambda exc: _classify_http400_response(
                                    exc, stage=stage, goid=goid, base_url=args.base_url,
                                    checkpoint=checkpoint, assigned=assigned))
                        else:
                            payload, usage, meta = invoke_fixture(args.fixture_dir, stage, goid, attempt)
                            if payload.get("_fixture_quota"):
                                raise QuotaPause("fixture_only")
                        check_response_model(stage, meta.get("response_model"), live=args.run_live)
                        raw = payload
                        errors = schema_errors(raw, schema["schema"])
                        fills: list[dict] = []
                        conflicts: list[str] = []
                        if not errors and stage == "content":
                            payload, fills, conflicts = normalize_content(raw, full["codes"]["scope_units"], derive_unit)
                            errors = check_content(payload, record_id=goid, target_aim_ids=full["target_aim_ids"])
                            errors.extend(check_content_hard_rules(payload, scope_units=full["codes"]["scope_units"]))
                            status, targets = "completed", full["target_aim_ids"]
                        elif not errors:
                            payload, fills, conflicts = normalize_scope(raw, stage)
                            errors, status, targets = check_scope(payload, arm=stage, record_id=goid,
                                                                   sentence_ids=set(ids))
                        else:
                            status, targets = "invalid", []
                        common = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                  "request_started_utc": started, "runner_version": RUNNER_VERSION,
                                  "run_identity": identity, "stage": stage, "GOID": goid,
                                  "codes": payload, "raw_codes": raw,
                                  "rule_fills": fills, "rule_conflicts": conflicts,
                                  "usage": usage, **meta, "attempt": attempt}
                        if stage == "content":
                            common["frozen_scope_units_sha256"] = scope_units_sha(full)
                            common["frozen_scope_sha256"] = scope_codes_sha(full["codes"])
                        if errors:
                            item = {"event": "invalid", **common, "validation_errors": errors[:20]}
                            append_event(checkpoint, item)
                            if pacer:
                                pacer.charge(usage)
                            prior = item
                            invalid[pair] = item
                            if attempt == args.max_attempts:
                                failure = {"event": "failed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                           "runner_version": RUNNER_VERSION, "run_identity": identity,
                                           "stage": stage, "GOID": goid,
                                           "failure_category": "validation_exhausted", "attempt": attempt}
                                append_event(checkpoint, failure)
                                failed[pair] = failure
                                invalid.pop(pair, None)
                            continue
                        item = {"event": "validated", **common, "record_status": status,
                                "target_aim_ids": targets,
                                "content_hard_rule_diagnostics": [],
                                "repair_of_response_id": prior.get("response_id") if prior else None}
                        append_event(checkpoint, item)
                        if pacer:
                            pacer.charge(usage)
                        done[pair] = item
                        invalid.pop(pair, None)
                        break
                    except (QuotaPause, ScopeQuotaPause) as exc:
                        pause_reason = exc.reason
                        pause_type = "quota"
                        append_event(checkpoint, {"event": "paused_quota",
                                                  "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                                  "runner_version": RUNNER_VERSION, "run_identity": identity,
                                                  "stage": stage, "GOID": goid,
                                                  "quota_reason": exc.reason, "pace_tpm": args.pace_tpm})
                        break
                    except (FatalConfigurationError, ScopeFatalConfigurationError):
                        raise
                    except (RecordFailure, ScopeRecordFailure) as exc:
                        failure = {"event": "failed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                   "runner_version": RUNNER_VERSION, "run_identity": identity,
                                   "stage": stage, "GOID": goid, "failure_category": exc.category,
                                   "usage": exc.usage, **exc.response_meta, "attempt": attempt}
                        append_event(checkpoint, failure)
                        if pacer:
                            pacer.charge(exc.usage)
                        failed[pair] = failure
                        break
                    except (ValueError, RuntimeError, urllib.error.URLError, TimeoutError,
                            ConnectionError, socket.timeout, KeyError) as exc:
                        # Proxy/server/transport and malformed-response errors are not
                        # record-level coding failures. Resume the same GOID later,
                        # unless this GOID keeps failing the same way.
                        usage = getattr(exc, "usage", None) or {}
                        response_meta = getattr(exc, "response_meta", None) or {}
                        streak = transient_streaks.get(pair, 0) + 1
                        transient_streaks[pair] = streak
                        append_event(checkpoint, {"event": "paused_transient",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "runner_version": RUNNER_VERSION, "run_identity": identity,
                            "stage": stage, "GOID": goid,
                            "error_type": type(exc).__name__, "attempt": attempt,
                            "consecutive_transient_n": streak, "usage": usage,
                            **response_meta})
                        if pacer:
                            pacer.charge(usage)
                        if streak >= TRANSIENT_PAUSES_BEFORE_FAILURE:
                            failure = {"event": "failed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                       "runner_version": RUNNER_VERSION, "run_identity": identity,
                                       "stage": stage, "GOID": goid,
                                       "failure_category": "repeated_transient_error",
                                       "error_type": type(exc).__name__, "attempt": attempt}
                            append_event(checkpoint, failure)
                            failed[pair] = failure
                            invalid.pop(pair, None)
                            transient_streaks.pop(pair, None)
                            break
                        pause_reason = "transient_error"
                        pause_type = "transient"
                        break
                if pause_reason:
                    break
            if pause_reason:
                break
        progress = summary(assigned, done, failed, checkpoint, identity,
                           paused=pause_reason, pause_type=pause_type, pace_tpm=args.pace_tpm or 0,
                           release_content=args.release_content, retried=retried)
        write_progress(args.output_dir, progress)
        if checkpoint.exists():
            write_failure_report(args.output_dir, failed, progress)
        if progress["status"] == "complete":
            export_complete(args.output_dir, assigned, done, progress)
        print(json.dumps({key: value for key, value in progress.items() if key != "run_identity"}, indent=2))
        return 75 if pause_reason else 0 if progress["status"] in SETTLED_STATUSES else 1
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
