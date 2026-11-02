"""Revision-13 rule filling for model JSON and parsed human CSV submissions."""

from __future__ import annotations

import copy


SUBSTANTIVE = {
    "object_of_study", "use_as_outcome", "use_as_exposure", "treatment_target",
    "therapeutic_agent", "substance_related_systems_responses",
}
GENERAL = {"general_SUD_unspecified", "general_drug_unspecified", "substance_unidentified"}
C6_APPLICABLE = {"intervene", "organize_deliver_services"}
C7_APPLICABLE = {"explain_causes", "consequences_of_use", "characterize_substance_action"}


def bundle(status: str, value=None, confidence=None) -> dict:
    return {"value": value, "coding_status": status, "confidence": confidence}


def fill(parent: dict, name: str, final: dict, rule: str, log: list[dict], flags: list[str],
         *, flag_conflict: bool = True) -> None:
    previous = parent[name]
    if previous == final:
        return
    if flag_conflict and previous.get("coding_status") == "coded" and previous.get("value") not in (None, final["value"]):
        flags.append(f"{name}: raw coded value conflicts with {rule}")
    log.append({"field": name, "rule": rule, "raw": copy.deepcopy(previous), "final": copy.deepcopy(final)})
    parent[name] = final


def clean_noncode(parent: dict, name: str, log: list[dict]) -> None:
    item = parent[name]
    if item.get("coding_status") not in {"cannot_determine", "not_applicable"}:
        return
    value = item.get("value")
    confidence = item.get("confidence")
    if value is None and confidence is None:
        return
    if value is None or value == item["coding_status"]:
        final = bundle(item["coding_status"])
        log.append({"field": name, "rule": "noncoded_empty_or_status_sentinel", "raw": copy.deepcopy(item), "final": final})
        parent[name] = final
    # A real value plus a noncoded status is ambiguous and remains invalid.


def normalize_scope(payload: dict, arm: str) -> tuple[dict, list[dict], list[str]]:
    result = copy.deepcopy(payload)
    log: list[dict] = []
    flags: list[str] = []
    for index, unit in enumerate(result["scope_units"]):
        unit_log: list[dict] = []
        roles = unit["substance_roles"]
        if roles["coding_status"] == "coded" and isinstance(roles["value"], list):
            role_set = set(roles["value"])
            if not role_set & SUBSTANTIVE:
                for name in ("stated_purposes", "unrelated_therapeutic_indication_tested"):
                    fill(unit, name, bundle("not_applicable"), "S1_no_substantive_role", unit_log, flags)
                if arm == "scope_compact_s2":
                    for name in ("effects_of_use_or_exposure", "core_definition_purpose"):
                        fill(unit, name, bundle("not_applicable"), "S1_no_substantive_role", unit_log, flags)
                if "behavioral_addiction" in role_set:
                    fill(unit, "substance_all", bundle("coded", ["behavioral_addiction"], roles["confidence"]),
                         "S1_behavioral_only", unit_log, flags)
                    fill(unit, "substance_primary", bundle("coded", "behavioral_addiction", roles["confidence"]),
                         "S1_behavioral_only", unit_log, flags)
                    fill(unit, "substance_assignment_basis", bundle("not_applicable"),
                         "S1_behavioral_only", unit_log, flags)
                else:
                    for name in ("substance_all", "substance_primary", "substance_assignment_basis"):
                        fill(unit, name, bundle("not_applicable"), "S1_no_substantive_role", unit_log, flags)
        elif roles["coding_status"] == "cannot_determine":
            for name in ("stated_purposes", "unrelated_therapeutic_indication_tested",
                         "substance_all", "substance_primary", "substance_assignment_basis"):
                fill(unit, name, bundle("cannot_determine"), "S1_uncertain", unit_log, flags)
            if arm == "scope_compact_s2":
                for name in ("effects_of_use_or_exposure", "core_definition_purpose"):
                    fill(unit, name, bundle("cannot_determine"), "S1_uncertain", unit_log, flags)
        labels = unit["substance_all"]
        if labels["coding_status"] == "coded" and isinstance(labels["value"], list):
            label_set = set(labels["value"])
            if len(label_set) == 1:
                fill(unit, "substance_primary", bundle("coded", next(iter(label_set)), labels["confidence"]),
                     "S4_sole_label_primary", unit_log, flags)
            if label_set & GENERAL:
                fill(unit, "substance_assignment_basis", bundle("coded", "general_substance_construct", labels["confidence"]),
                     "S4_general_label_basis", unit_log, flags)
        for name, item in unit.items():
            if isinstance(item, dict) and "coding_status" in item:
                clean_noncode(unit, name, unit_log)
        for item in unit_log:
            item["unit_index"] = index
        log.extend(unit_log)
    clean_noncode(result, "add_su_focus", log)
    return result, log, flags


def normalize_content(payload: dict, scope_units: list[dict], derive_unit) -> tuple[dict, list[dict], list[str]]:
    result = copy.deepcopy(payload)
    log: list[dict] = []
    flags: list[str] = []
    outcomes = [derive_unit(unit, "scope_full") for unit in scope_units]
    if outcomes and all(outcome == "in_scope" for outcome in outcomes):
        previous = result["mixed_purpose"]
        if previous.get("coding_status") == "coded" and previous.get("value") != "only_qualifying_described":
            flags.append("C1_scope_unit_completeness_review")
        fill(result, "mixed_purpose", bundle("coded", "only_qualifying_described", "high"),
             "C1_all_units_qualify", log, flags, flag_conflict=False)
    dtype = result["dissertation_type"]
    if dtype["coding_status"] == "coded" and dtype["value"] in {"evidence_synthesis", "conceptual_theoretical"}:
        fill(result, "study_design", bundle("not_applicable"), "C2_nonempirical_type", log, flags)
    elif dtype["coding_status"] == "cannot_determine":
        fill(result, "study_design", bundle("cannot_determine"), "C2_uncertain", log, flags)
    objective = result["research_objective"]
    if objective["coding_status"] == "cannot_determine":
        for name in ("intervention_continuum", "explanatory_domain"):
            fill(result, name, bundle("cannot_determine"), "C5_uncertain", log, flags)
    elif objective["coding_status"] == "coded" and objective["value"] != "multiple_no_dominant":
        if objective["value"] not in C6_APPLICABLE:
            fill(result, "intervention_continuum", bundle("not_applicable"), "C5_outside_C6", log, flags)
        if objective["value"] not in C7_APPLICABLE:
            fill(result, "explanatory_domain", bundle("not_applicable"), "C5_outside_C7", log, flags)
    origin = result["data_source_origin"]
    if origin["coding_status"] == "coded" and origin["value"] == "no_empirical_data":
        fill(result, "data_type", bundle("not_applicable"), "C9_no_empirical_data", log, flags)
    for name, item in result.items():
        if isinstance(item, dict) and "coding_status" in item:
            clean_noncode(result, name, log)
    return result, log, flags
