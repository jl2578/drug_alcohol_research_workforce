"""Integrated revision-15 scope processing for one complete scope response.

The operative definitions are in dissertation_codebook_v5_rev15_reproduction.md.
This processor uses the complete assessed scope response. Callers validate the
raw schema before normalization and validate
the normalized fields/references before certifying outcomes or routing content.
"""
from __future__ import annotations

import copy
import hashlib
import json

from normalize_v5_rev13 import SUBSTANTIVE, GENERAL, bundle, clean_noncode, fill

S4 = ("substance_all", "substance_primary", "substance_assignment_basis")
NEGATIVE_PURPOSES = {"none_stated", "outside_study_scope"}


def scope_codes_sha(codes: dict) -> str:
    """Pin the complete assessed scope object, including record-level S5."""
    return hashlib.sha256(json.dumps(codes, sort_keys=True, separators=(",", ":")).encode('utf-8')).hexdigest()


def has_endogenous_role(unit: dict) -> bool:
    roles = unit["substance_roles"]
    return roles["coding_status"] == "coded" and "endogenous_system_only" in (roles["value"] or [])


def derive_unit(unit: dict, arm: str = "scope_full") -> str:
    """Part C.1, on structurally validated fields from the one scope stage."""
    if arm != "scope_full":
        raise ValueError("single_pass_requires_full_scope")
    roles = unit["substance_roles"]
    substances = unit["substance_all"]
    purposes = unit["stated_purposes"]
    # Raw schema allows null sentinels; a coded null/empty parent remains an
    # invalid field, never an empty coded set or a normalization exception.
    for parent in (roles, substances, purposes):
        if parent["coding_status"] == "coded" and (not isinstance(parent["value"], list) or not parent["value"]):
            return "invalid"
    if has_endogenous_role(unit):
        return "in_scope"
    labels = set(substances["value"] or []) if substances["coding_status"] == "coded" else set()
    if labels == {"behavioral_addiction"}:
        return "out_of_scope"
    if roles["coding_status"] != "coded":
        return "undetermined"
    if not set(roles["value"]) & SUBSTANTIVE:
        return "out_of_scope"
    if substances["coding_status"] != "coded":
        return "undetermined"
    if labels <= {"caffeine", "behavioral_addiction"}:
        return "out_of_scope"
    if purposes["coding_status"] == "cannot_determine":
        return "undetermined"
    if purposes["coding_status"] != "coded":
        return "invalid"
    values = set(purposes["value"])
    if values - NEGATIVE_PURPOSES:
        return "in_scope"
    if values == {"outside_study_scope"}:
        return "out_of_scope"
    indication = unit["unrelated_therapeutic_indication_tested"]
    return "out_of_scope" if indication["coding_status"] == "coded" and indication["value"] == "yes" else "undetermined"


def target_aim_ids(units: list[dict]) -> list[str]:
    """Select qualifying units from the assessed response in source order."""
    ids = [unit["aim_id"] for unit in units]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_aim_ids")
    return [unit["aim_id"] for unit in units if derive_unit(unit) == "in_scope"]


def normalize_scope(payload: dict, arm: str = "scope_full") -> tuple[dict, list[dict], list[str]]:
    """Apply A4a to this response, retaining the raw object and every fill log."""
    if arm != "scope_full":
        raise ValueError("single_pass_requires_full_scope")
    result = copy.deepcopy(payload)
    logs, flags = [], []
    for index, unit in enumerate(result["scope_units"]):
        local = []
        roles = unit["substance_roles"]
        if roles["coding_status"] == "coded" and isinstance(roles["value"], list):
            role_set = set(roles["value"])
            substantive = bool(role_set & SUBSTANTIVE)
            endogenous = "endogenous_system_only" in role_set
            if not substantive:
                for name in ("stated_purposes", "unrelated_therapeutic_indication_tested"):
                    fill(unit, name, bundle("not_applicable"), "S1_no_substantive_role", local, flags)
            if endogenous and unit["substance_all"]["coding_status"] == "not_applicable":
                fill(unit, "substance_all", bundle("cannot_determine"), "endogenous_S4_applicable", local, flags)
            if not substantive and not endogenous:
                if "behavioral_addiction" in role_set:
                    for name, value in (("substance_all", ["behavioral_addiction"]),
                                        ("substance_primary", "behavioral_addiction")):
                        fill(unit, name, bundle("coded", value, roles["confidence"]), "S1_behavioral_only", local, flags)
                    fill(unit, "substance_assignment_basis", bundle("not_applicable"), "S1_behavioral_only", local, flags)
                else:
                    for name in S4:
                        fill(unit, name, bundle("not_applicable"), "S1_no_substantive_role", local, flags)
        elif roles["coding_status"] == "cannot_determine":
            for name in ("stated_purposes", "unrelated_therapeutic_indication_tested", *S4):
                fill(unit, name, bundle("cannot_determine"), "S1_uncertain", local, flags)

        labels = unit["substance_all"]
        if labels["coding_status"] == "cannot_determine":
            for name in S4[1:]:
                fill(unit, name, bundle("cannot_determine"), "S4_uncertain", local, flags)
        elif labels["coding_status"] == "coded" and isinstance(labels["value"], list):
            values = labels["value"]
            if len(values) == 1:
                fill(unit, "substance_primary", bundle("coded", values[0], labels["confidence"]), "S4_sole_label_primary", local, flags)
            if set(values) & GENERAL:
                fill(unit, "substance_assignment_basis", bundle("coded", "general_substance_construct", labels["confidence"]), "S4_general_label_basis", local, flags)
            elif values == ["behavioral_addiction"]:
                fill(unit, "substance_assignment_basis", bundle("not_applicable"), "S4_behavioral_basis_inapplicable", local, flags)
        for name in ("substance_roles", "stated_purposes", "unrelated_therapeutic_indication_tested", *S4):
            clean_noncode(unit, name, local)
        for item in local:
            item["unit_index"] = index
        logs.extend(local)
    clean_noncode(result, "add_su_focus", logs)
    return result, logs, flags
