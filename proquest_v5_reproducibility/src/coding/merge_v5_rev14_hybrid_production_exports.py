"""Verify and merge code-only Workbench exports against the frozen v5 roster."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path

from validate_v5_rev14_pilot import check_content, check_content_hard_rules, check_scope


ROOT = Path(__file__).resolve().parents[2]
ROSTER = ROOT / "private/reviewer_rerun/roster.csv"
PLAN_DIR = ROOT / "private/reviewer_rerun"
SOURCE_PLAN_DIR = PLAN_DIR / "source_partition"
FREEZE = ROOT / "config/coding/reviewer_single_pass_v15_freeze.json"
EXPECTED_MEMBERS = {"production_codes.jsonl", "production_export_manifest.json", "production_progress.json"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def report_failures(*, packages: list[Path], plan_dir: Path, output_dir: Path) -> dict:
    """Reconcile unresolved failures separately; never certify missing codes."""
    if output_dir.exists():
        raise FileExistsError(f"Preserve existing failure report: {output_dir}")
    plan_path = plan_dir / "hybrid_production_plan.json"
    plan = load_json(plan_path)
    seen = set()
    rows = []
    for package in packages:
        with zipfile.ZipFile(package) as archive:
            if archive.namelist() != ["production_failure_list.json"]:
                raise ValueError("Failure package has missing or extra members")
            report = json.loads(archive.read("production_failure_list.json"))
        identity = report["run_identity"]
        worker = identity["worker_id"]
        if worker in seen or worker not in range(1, plan["worker_count"] + 1):
            raise ValueError("Duplicate or invalid failure worker")
        seen.add(worker)
        assignment_name = f"{plan['worker_count']}_workbenches_worker_{worker}_goids.json"
        assignment_path = plan_dir / assignment_name
        assignment = load_json(assignment_path)
        if (identity["plan_manifest_sha256"] != sha(plan_path.read_bytes())
                or identity["worker_count"] != plan["worker_count"] or identity["mode"] != "live"
                or identity["assignment_sha256"] != plan["files"][assignment_name]["sha256"]
                or sha(assignment_path.read_bytes()) != plan["files"][assignment_name]["sha256"]
                or identity["stage_models"] != plan["stage_models"]):
            raise ValueError("Failure report identity disagrees with frozen plan")
        expected_status = "unresolved_record_failures" if report["failures"] else "no_unresolved_record_failures"
        if report["status"] != expected_status:
            raise ValueError("Failure report status and records disagree")
        assigned = set(assignment)
        for failure in report["failures"]:
            if failure["GOID"] not in assigned or failure["stage"] not in {"scope_full", "content"}:
                raise ValueError("Failure lies outside worker assignment")
            rows.append({"worker_id": worker, **failure})
    result = {"status": "diagnostic_not_certified", "workers_reported": sorted(seen),
              "unresolved_failure_n": len(rows), "unresolved_failures": rows,
              "plan_manifest_sha256": sha(plan_path.read_bytes())}
    output_dir.mkdir(parents=True)
    (output_dir / "hybrid_unresolved_failure_report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def merge(*, packages: list[Path], worker_count: int, plan_dir: Path, roster: Path,
          freeze_path: Path, output_dir: Path, production: bool = True) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"Preserve existing merged output: {output_dir}")
    if worker_count < 1 or len(packages) != worker_count:
        raise ValueError("Provide one package per selected Workbench")
    plan_path = plan_dir / "hybrid_production_plan.json"
    plan = load_json(plan_path)
    freeze = load_json(freeze_path)
    if plan["purpose"] != "public_reproduction_rerun" or worker_count != plan["worker_count"]:
        raise ValueError("Full production plan counts changed")
    codebook_hash = freeze["files_sha256"]["config/coding/dissertation_codebook_v5_rev15_reproduction.md"]
    if plan["codebook_sha256"] != codebook_hash:
        raise ValueError("Production plan differs from coding freeze")
    with roster.open(encoding="utf-8-sig", newline="") as handle:
        all_goids = [row["GOID"] for row in csv.DictReader(handle)]
    if len(all_goids) != plan["roster_count"] or len(set(all_goids)) != len(all_goids):
        raise ValueError("Roster differs from plan count or has duplicate GOIDs")
    source_plan_path = plan_dir / "source_partition/partition_options_manifest.json"
    if sha(source_plan_path.read_bytes()) != plan["source_partition_manifest_sha256"]:
        raise ValueError("Source roster partition plan changed")
    source_plan = load_json(source_plan_path)
    exception_path = plan_dir / "source_partition/unassessable_goids.json"
    if sha(exception_path.read_bytes()) != source_plan["files"][exception_path.name]["sha256"]:
        raise ValueError("Abstract exception file changed")
    exceptions = load_json(exception_path)
    exception_map = {row["GOID"]: row["abstract_input_status"] for row in exceptions}
    if len(exception_map) != len(exceptions) or any(s not in {"blank", "placeholder"} for s in exception_map.values()):
        raise ValueError("Invalid abstract exception list")
    if set(exception_map) - set(all_goids):
        raise ValueError("Abstract exception lies outside roster")
    if len(exception_map) != plan["roster_count"] - plan["assessable_count"]:
        raise ValueError("Exception count differs from this rerun plan")

    combined: dict[str, dict] = {}
    package_meta = []
    seen_workers = set()
    for package in packages:
        with zipfile.ZipFile(package) as archive:
            if set(archive.namelist()) != EXPECTED_MEMBERS:
                raise ValueError(f"Package has missing or extra members: {package.name}")
            codes_bytes = archive.read("production_codes.jsonl")
            export = json.loads(archive.read("production_export_manifest.json"))
            progress = json.loads(archive.read("production_progress.json"))
        count, worker = export["worker_count"], export["worker_id"]
        if count != worker_count or worker in seen_workers or not 1 <= worker <= worker_count:
            raise ValueError("Duplicate, wrong-count or out-of-range Workbench package")
        seen_workers.add(worker)
        name = f"{worker_count}_workbenches_worker_{worker}_goids.json"
        assignment_path = plan_dir / name
        assignment = load_json(assignment_path)
        assignment_hash = sha(assignment_path.read_bytes())
        if assignment_hash != plan["files"][name]["sha256"]:
            raise ValueError("Assignment changed after partition plan")
        if (export["status"] != "complete_code_only_export" or progress["status"] != "complete"
                or export["records"] != len(assignment) or export["codes_sha256"] != sha(codes_bytes)
                or export["assignment_sha256"] != assignment_hash
                or export["codebook_sha256"] != codebook_hash
                or export["stage_models"] != freeze["stage_models"]):
            raise ValueError("Export manifest, code bytes or coding freeze disagree")
        identity = progress["run_identity"]
        if production and identity["mode"] != "live":
            raise ValueError("Offline fixture result cannot be merged as production")
        if (identity["worker_count"] != count or identity["worker_id"] != worker
                or identity["assignment_sha256"] != assignment_hash
                or identity["plan_manifest_sha256"] != sha(plan_path.read_bytes())
                or identity["freeze_sha256"] != sha(freeze_path.read_bytes())
                or identity["codebook_sha256"] != codebook_hash
                or identity["stage_models"] != freeze["stage_models"]
                or identity["stage_profiles"] != freeze["stage_profiles"]
                or progress["assigned_n"] != len(assignment)
                or progress["scope_validated_n"] != len(assignment)
                or progress["content_validated_n"] != progress["content_required_n"]
                or progress["scope_failed_n"] or progress["content_failed_n"]):
            raise ValueError("Progress and Workbench identity disagree")
        if b'"numbered_evidence"' in codes_bytes or b'"title"' in codes_bytes or b'"abstract"' in codes_bytes:
            raise ValueError("Source field found in code-only export")
        rows = [json.loads(line) for line in codes_bytes.decode("utf-8").splitlines()]
        if [row["GOID"] for row in rows] != assignment:
            raise ValueError("Export rows differ from ordered worker assignment")
        for row in rows:
            goid = row["GOID"]
            if production and (row["scope_response_model"] not in {"gpt-5-2025-08-07", "gpt_5_2025_08_07"}
                               or (row["content_codes"] is not None
                                   and row["content_response_model"] not in {"gpt-4o-2024-08-06", "gpt_4o_2024_08_06"})):
                raise ValueError(f"Actual response model differs from frozen snapshot: {goid}")
            if goid in combined or goid in exception_map:
                raise ValueError(f"GOID overlaps between workers or exception list: {goid}")
            scope = row["scope_codes"]
            ids = {sid for unit in scope["scope_units"] for sid in unit["source_sentence_ids"]}
            errors, status, targets = check_scope(scope, arm="scope_full", record_id=goid, sentence_ids=ids)
            if errors or status != row["record_status"] or targets != row["target_aim_ids"]:
                raise ValueError(f"Scope code derivation differs in export: {goid}")
            content = row["content_codes"]
            if (content is not None) != (status == "in_scope"):
                raise ValueError(f"Content route differs from scope: {goid}")
            if content is not None:
                frozen_hash = hashlib.sha256(json.dumps(scope["scope_units"], sort_keys=True,
                    separators=(",", ":")).encode("utf-8")).hexdigest()
                if row.get("content_frozen_scope_units_sha256") != frozen_hash:
                    raise ValueError(f"Content used different GPT-5 scope units: {goid}")
                from reviewer_scope_single_pass import scope_codes_sha
                if row.get("content_frozen_scope_sha256") != scope_codes_sha(scope):
                    raise ValueError(f"Content used different complete scope: {goid}")
                errors = check_content(content, record_id=goid, target_aim_ids=targets)
                errors.extend(check_content_hard_rules(content, scope_units=scope["scope_units"]))
                if errors:
                    raise ValueError(f"Content code failed local validation: {goid}")
            combined[goid] = row
        package_meta.append({"worker_id": worker, "package_sha256": sha(package.read_bytes()),
                             "codes_sha256": export["codes_sha256"], "records": len(rows),
                             "scope_status_counts": progress["scope_status_counts"]})
    if seen_workers != set(range(1, worker_count + 1)):
        raise ValueError("One or more Workbench packages are missing")
    if set(combined) | set(exception_map) != set(all_goids):
        raise ValueError("Merged Workbench codes and exceptions do not cover the frozen roster")
    if len(combined) != plan["assessable_count"]:
        raise ValueError("Merged assessable count differs from plan")
    lines = []
    status_counts = {s: 0 for s in ("in_scope", "out_of_scope", "undetermined", "not_assessable")}
    for goid in all_goids:
        if goid in combined:
            row = combined[goid]
        else:
            row = {"GOID": goid, "record_status": "not_assessable",
                   "abstract_input_status": exception_map[goid], "target_aim_ids": [],
                   "scope_codes": None, "content_codes": None}
        status_counts[row["record_status"]] += 1
        lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    output_dir.mkdir(parents=True)
    output = output_dir / "v5_rev14_hybrid_merged_codes.jsonl"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = {"status": "synthetic_example_only" if not production else "new_rerun_reconciled_code_only", "roster_n": len(all_goids),
              "assessable_n": len(combined), "abstract_exception_n": len(exception_map),
              "scope_status_counts": status_counts, "worker_count": worker_count,
              "workers": sorted(package_meta, key=lambda row: row["worker_id"]),
              "merged_codes_sha256": sha(output.read_bytes()),
              "roster_sha256": sha(roster.read_bytes()),
              "plan_manifest_sha256": sha(plan_path.read_bytes()),
              "coding_freeze_sha256": sha(freeze_path.read_bytes())}
    (output_dir / "v5_rev14_hybrid_merge_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, action="append")
    parser.add_argument("--failure-package", type=Path, action="append",
                        help="Produce a separate diagnostic of unresolved records, not a certified code merge")
    parser.add_argument("--worker-count", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.failure_package and not args.package:
        result = report_failures(packages=args.failure_package, plan_dir=PLAN_DIR,
                                 output_dir=args.output_dir)
    elif args.package and not args.failure_package:
        result = merge(packages=args.package, worker_count=args.worker_count,
                       plan_dir=PLAN_DIR, roster=ROSTER, freeze_path=FREEZE,
                       output_dir=args.output_dir)
    else:
        parser.error("Provide final worker packages or separate failure packages")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
