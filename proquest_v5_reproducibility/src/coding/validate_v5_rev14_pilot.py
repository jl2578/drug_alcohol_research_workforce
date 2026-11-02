"""Validate revision 14 model responses and linked human CSV coder files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from reviewer_scope_single_pass import normalize_scope


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "config/coding/reviewer_single_pass_v15"
SUBSTANTIVE = {
    "object_of_study", "use_as_outcome", "use_as_exposure", "treatment_target",
    "therapeutic_agent", "substance_related_systems_responses",
}
NEGATIVE_PURPOSES = {"none_stated", "outside_study_scope"}
GENERAL_LABELS = {"general_SUD_unspecified", "general_drug_unspecified", "substance_unidentified"}
SCOPE_FIELDS = (
    "substance_roles", "stated_purposes", "unrelated_therapeutic_indication_tested",
    "substance_all", "substance_primary", "substance_assignment_basis",
)
CONTENT_FIELDS = (
    "mixed_purpose", "dissertation_type", "study_design", "level_of_analysis",
    "research_objective", "intervention_continuum", "explanatory_domain",
    "data_type", "data_source_origin",
)


def schema_errors(value: Any, spec: dict, path: str = "$",) -> list[str]:
    if "anyOf" in spec:
        if any(not schema_errors(value, choice, path) for choice in spec["anyOf"]):
            return []
        return [f"{path}: no allowed schema branch matches"]
    if "enum" in spec and value not in spec["enum"]:
        return [f"{path}: value outside enum"]
    kind = spec.get("type")
    if kind == "null" and value is not None:
        return [f"{path}: expected null"]
    if kind == "string" and not isinstance(value, str):
        return [f"{path}: expected string"]
    if kind == "array" and not isinstance(value, list):
        return [f"{path}: expected array"]
    if kind == "object" and not isinstance(value, dict):
        return [f"{path}: expected object"]
    if kind == "array" and isinstance(value, list):
        errors = []
        if len(value) < spec.get("minItems", 0) or len(value) > spec.get("maxItems", float("inf")):
            errors.append(f"{path}: invalid array length")
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, spec["items"], f"{path}[{index}]"))
        return errors
    if kind == "object" and isinstance(value, dict):
        errors = []
        props = spec.get("properties", {})
        for key in spec.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: missing")
        if spec.get("additionalProperties") is False:
            for key in value.keys() - props.keys():
                errors.append(f"{path}.{key}: unexpected field")
        for key in value.keys() & props.keys():
            errors.extend(schema_errors(value[key], props[key], f"{path}.{key}"))
        return errors
    return []


def load_schema(name: str) -> dict:
    return json.loads((ARTIFACTS / f"{name}_schema.json").read_text(encoding="utf-8"))["schema"]


def check_field(item: dict, path: str) -> list[str]:
    status, value, confidence = (item.get(key) for key in ("coding_status", "value", "confidence"))
    if status == "coded":
        if value is None or value == []:
            return [f"{path}: coded requires nonempty value"]
        if confidence not in {"high", "medium", "low"}:
            return [f"{path}: coded requires confidence"]
    elif status in {"cannot_determine", "not_applicable"}:
        if value is not None or confidence is not None:
            return [f"{path}: noncoded value and confidence must be null"]
    else:
        return [f"{path}: invalid coding_status"]
    if isinstance(value, list) and len(value) != len(set(value)):
        return [f"{path}: duplicate array item"]
    return []


def check_scope(payload: dict, *, arm: str, record_id: str, sentence_ids: set[str]) -> tuple[list[str], str, list[str]]:
    if arm != "scope_full":
        raise ValueError("Unknown scope arm")
    errors = schema_errors(payload, load_schema(arm))
    if errors:
        return errors, "invalid", []
    if payload["record_id"] != record_id:
        errors.append("$.record_id: GOID mismatch")
    units = payload["scope_units"]
    if not units:
        errors.append("$.scope_units: empty")
    aim_ids = [unit["aim_id"] for unit in units]
    if aim_ids != [f"a{i}" for i in range(1, len(units) + 1)]:
        errors.append("$.scope_units: aim IDs must be a1..aN in order")
    errors.extend(check_field(payload["add_su_focus"], "$.add_su_focus"))
    if payload["add_su_focus"]["coding_status"] == "not_applicable":
        errors.append("$.add_su_focus: not_applicable forbidden")
    outcomes = []
    targets = []
    for index, unit in enumerate(units):
        path = f"$.scope_units[{index}]"
        refs = unit["source_sentence_ids"]
        if not refs or len(refs) != len(set(refs)) or not set(refs) <= sentence_ids:
            errors.append(f"{path}.source_sentence_ids: empty, duplicate or unknown ID")
        for name in (*SCOPE_FIELDS, *(("effects_of_use_or_exposure", "core_definition_purpose") if arm == "scope_compact_s2" else ())):
            errors.extend(check_field(unit[name], f"{path}.{name}"))
        roles = unit["substance_roles"]
        purposes = unit["stated_purposes"]
        substances = unit["substance_all"]
        primary = unit["substance_primary"]
        basis = unit["substance_assignment_basis"]
        role_set = set(roles["value"] or []) if roles["coding_status"] == "coded" else set()
        purpose_set = set(purposes["value"] or []) if purposes["coding_status"] == "coded" and arm == "scope_full" else set()
        substance_set = set(substances["value"] or []) if substances["coding_status"] == "coded" else set()
        if "none" in role_set and len(role_set) > 1:
            errors.append(f"{path}.substance_roles: none must be exclusive")
        if purpose_set & NEGATIVE_PURPOSES and len(purpose_set) > 1:
            errors.append(f"{path}.stated_purposes: negative purpose must be exclusive")
        if "general_SUD_unspecified" in substance_set and len(substance_set) > 1:
            errors.append(f"{path}.substance_all: general SUD must be exclusive")
        if "general_drug_unspecified" in substance_set and not substance_set <= {"general_drug_unspecified", "alcohol"}:
            errors.append(f"{path}.substance_all: general drug may combine only with alcohol")
        if primary["coding_status"] == "coded" and substances["coding_status"] == "coded":
            pval = primary["value"]
            if len(substance_set) == 1 and pval != next(iter(substance_set)):
                errors.append(f"{path}.substance_primary: must equal sole label")
            if pval == "none_dominant" and len(substance_set) < 2:
                errors.append(f"{path}.substance_primary: none_dominant needs two labels")
            if pval != "none_dominant" and pval not in substance_set:
                errors.append(f"{path}.substance_primary: not in substance_all")
        if substances["coding_status"] == "coded" and basis["coding_status"] == "coded":
            if substance_set & GENERAL_LABELS and basis["value"] != "general_substance_construct":
                errors.append(f"{path}.substance_assignment_basis: general construct required")
            if not substance_set & GENERAL_LABELS and basis["value"] == "general_substance_construct":
                errors.append(f"{path}.substance_assignment_basis: general construct unsupported")
        if roles["coding_status"] == "not_applicable":
            errors.append(f"{path}.substance_roles: not_applicable forbidden")
        if substances["coding_status"] == "coded":
            if primary["coding_status"] == "not_applicable":
                errors.append(f"{path}.substance_primary: applicable for coded labels")
            if basis["coding_status"] == "not_applicable" and substance_set != {"behavioral_addiction"}:
                errors.append(f"{path}.substance_assignment_basis: applicable unless sole behavioral label")
        elif substances["coding_status"] in {"cannot_determine", "not_applicable"}:
            if any(child["coding_status"] != substances["coding_status"] for child in (primary, basis)):
                errors.append(f"{path}: S4 child statuses must follow the label-set status")
        if roles["coding_status"] == "cannot_determine" and any(
            unit[name]["coding_status"] != "cannot_determine" for name in SCOPE_FIELDS[1:]
        ):
            errors.append(f"{path}: uncertain S1 requires uncertain dependent scope fields")
        substantive = bool(role_set & SUBSTANTIVE)
        if roles["coding_status"] == "coded" and not substantive:
            if purposes["coding_status"] != "not_applicable" or unit["unrelated_therapeutic_indication_tested"]["coding_status"] != "not_applicable":
                errors.append(f"{path}: S2/S3 must be not_applicable without substantive role")
            if not role_set & {"behavioral_addiction", "endogenous_system_only"} and substances["coding_status"] != "not_applicable":
                errors.append(f"{path}: S4 must be not_applicable without substantive role")
        if substantive and (purposes["coding_status"] == "not_applicable" or unit["unrelated_therapeutic_indication_tested"]["coding_status"] == "not_applicable"):
            errors.append(f"{path}: S2/S3 cannot be not_applicable with substantive role")
        if (substantive or "endogenous_system_only" in role_set) and substances["coding_status"] == "not_applicable":
            errors.append(f"{path}.substance_all: not_applicable is invalid with substantive S1")
        if arm == "scope_compact_s2":
            for name in ("effects_of_use_or_exposure", "core_definition_purpose"):
                if purposes["coding_status"] == "coded" and purposes["value"] == "qualifying_purpose" and unit[name]["coding_status"] == "not_applicable":
                    errors.append(f"{path}.{name}: required for qualifying purpose")
                if purposes["coding_status"] == "cannot_determine" and unit[name]["coding_status"] == "not_applicable":
                    errors.append(f"{path}.{name}: unresolved purpose cannot establish inapplicability")
        outcome = "invalid" if errors else derive_unit(unit, arm)
        outcomes.append(outcome)
        if outcome == "in_scope":
            targets.append(unit["aim_id"])
    if errors:
        return errors, "invalid", []
    status = "in_scope" if "in_scope" in outcomes else "undetermined" if "undetermined" in outcomes else "out_of_scope"
    return [], status, targets


def derive_unit(unit: dict, arm: str) -> str:
    from reviewer_scope_single_pass import derive_unit as integrated_scope
    return integrated_scope(unit, arm)


def check_content(payload: dict, *, record_id: str, target_aim_ids: list[str]) -> list[str]:
    errors = schema_errors(payload, load_schema("content"))
    if errors:
        return errors
    if payload["record_id"] != record_id:
        errors.append("$.record_id: GOID mismatch")
    if payload["target_aim_ids"] != target_aim_ids:
        errors.append("$.target_aim_ids: must exactly echo frozen qualifying targets")
    for name in CONTENT_FIELDS:
        errors.extend(check_field(payload[name], f"$.{name}"))
    return errors


def check_content_hard_rules(payload: dict, *, scope_units: list[dict]) -> list[str]:
    """Pilot diagnostics: retain structurally valid content and count rule conflicts."""
    findings = []
    field = lambda name: payload[name]
    status = lambda name: field(name)["coding_status"]
    value = lambda name: field(name)["value"] if status(name) == "coded" else None
    outcomes = [derive_unit(unit, "scope_full") for unit in scope_units]
    if outcomes and all(outcome == "in_scope" for outcome in outcomes):
        if status("mixed_purpose") != "coded" or value("mixed_purpose") != "only_qualifying_described":
            findings.append("C1: all known units qualify, so only_qualifying_described is required")
    elif "out_of_scope" in outcomes and status("mixed_purpose") == "coded" and value("mixed_purpose") == "only_qualifying_described":
        findings.append("C1: a known nonqualifying unit conflicts with only_qualifying_described")
    dtype = value("dissertation_type")
    if dtype in {"evidence_synthesis", "conceptual_theoretical"} and status("study_design") != "not_applicable":
        findings.append("C3: study_design must be not_applicable for evidence synthesis or conceptual work")
    objective = value("research_objective")
    for name, applicable in (
        ("intervention_continuum", {"intervene", "organize_deliver_services"}),
        ("explanatory_domain", {"explain_causes", "consequences_of_use", "characterize_substance_action"}),
    ):
        if status("research_objective") == "cannot_determine" and status(name) != "cannot_determine":
            findings.append(f"{name}: uncertain objective requires cannot_determine")
        elif objective and objective != "multiple_no_dominant":
            if objective in applicable and status(name) == "not_applicable":
                findings.append(f"{name}: applicable objective cannot yield not_applicable")
            if objective not in applicable and status(name) != "not_applicable":
                findings.append(f"{name}: known inapplicable objective requires not_applicable")
    no_data = value("data_source_origin") == "no_empirical_data"
    not_applicable = status("data_type") == "not_applicable"
    if no_data != not_applicable:
        findings.append("C8/C9: no_empirical_data and data_type not_applicable must be paired")
    return findings


def csv_field(row: dict[str, str], name: str, multiselect: bool) -> dict:
    status = row[f"{name}_coding_status"].strip()
    raw = row[f"{name}_value"].strip()
    confidence = row[f"{name}_confidence"].strip() or None
    if not status:
        return {"coding_status": "", "value": raw or None, "confidence": confidence}
    if not raw:
        value = None
    elif multiselect:
        value = json.loads(raw) if raw.startswith("[") else [part.strip() for part in raw.split(";") if part.strip()]
    elif name == "add_su_focus" and raw.isdigit():
        value = int(raw)
    else:
        value = raw
    return {"coding_status": status, "value": value, "confidence": confidence}


def check_coder_files(records_path: Path, aims_path: Path) -> dict:
    with records_path.open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    with aims_path.open(encoding="utf-8-sig", newline="") as handle:
        aims = list(csv.DictReader(handle))
    by_aim: dict[str, list[dict]] = {}
    for row in aims:
        by_aim.setdefault(row["GOID"], []).append(row)
    findings = {}
    for row in records:
        goid = row["GOID"]
        units = []
        for aim in by_aim.get(goid, []):
            unit = {"aim_id": aim["aim_id"],
                    "source_sentence_ids": re.findall(r"\bs\d+\b", aim["source_sentence_ids"])}
            unit.update({name: csv_field(aim, name, name in {"substance_roles", "stated_purposes", "substance_all"}) for name in SCOPE_FIELDS})
            units.append(unit)
        payload = {"record_id": goid, "scope_units": units,
                   "add_su_focus": csv_field(row, "add_su_focus", False)}
        sentence_ids = set(re.findall(r"\[(s\d+)\]", row["numbered_evidence"]))
        normalized, rule_log, flags = normalize_scope(payload, "scope_full")
        errors, status, targets = check_scope(normalized, arm="scope_full", record_id=goid, sentence_ids=sentence_ids)
        raw_targets = row.get("target_aim_ids", "").strip()
        if raw_targets:
            listed = json.loads(raw_targets) if raw_targets.startswith("[") else [part.strip() for part in raw_targets.split(";") if part.strip()]
        else:
            listed = []
        if status == "in_scope" and raw_targets and listed != targets:
            errors.append("target_aim_ids: differs from derived qualifying units")
        if status == "out_of_scope" and listed:
            errors.append("target_aim_ids: nonempty on out-of-scope record")
        findings[goid] = {"scope_status": status, "target_aim_ids": targets, "errors": errors,
                          "rule_fills": len(rule_log), "rule_conflicts": flags}
    return {"records": len(records),
            "rule_fills": sum(row["rule_fills"] for row in findings.values()),
            "rule_conflict_goids": {goid: row["rule_conflicts"] for goid, row in findings.items() if row["rule_conflicts"]},
            "invalid_goids": {goid: row["errors"] for goid, row in findings.items() if row["errors"]}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--content", type=Path)
    parser.add_argument("--arm", choices=["scope_full"], default="scope_full")
    parser.add_argument("--record-id")
    parser.add_argument("--sentence-ids", nargs="*")
    parser.add_argument("--target-aim-ids", nargs="*")
    parser.add_argument("--coder-records", type=Path)
    parser.add_argument("--coder-aims", type=Path)
    args = parser.parse_args()
    if args.coder_records and args.coder_aims:
        result = check_coder_files(args.coder_records, args.coder_aims)
    elif args.scope and args.record_id:
        result = check_scope(json.loads(args.scope.read_text(encoding="utf-8")), arm=args.arm,
                             record_id=args.record_id, sentence_ids=set(args.sentence_ids or []))
    elif args.content and args.record_id:
        result = check_content(json.loads(args.content.read_text(encoding="utf-8")), record_id=args.record_id,
                               target_aim_ids=args.target_aim_ids or [])
    else:
        parser.error("Provide coder CSV pair, or a scope/content response and record ID")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

