"""Build one private production input in TDM Studio from a frozen GOID assignment.

Only GOIDs and evidence hashes arrive in the upload bundle. Licensed title and
abstract text is read from XML and written only inside the Workbench. The input
is not created if any assigned record is missing, duplicated, blank or differs
substantively from the frozen reference hashes.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from extract_v5_rev13_pilot_from_xml import (
    PREFIX, CHECK_FIELDS, FIELDS, evidence_hash, plain_text, read_csv, sha256,
    loose_text, write_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-dir", type=Path, required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--reference-hashes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.xml_dir.is_dir():
        parser.error("XML directory is missing")
    if args.output.exists():
        parser.error("Refusing to overwrite an existing private production input")
    selected = json.loads(args.assignment.read_text(encoding="utf-8"))
    if not isinstance(selected, list) or not selected or len(selected) != len(set(selected)):
        parser.error("Assignment must be a nonempty JSON array of unique GOIDs")
    selected_set = set(selected)
    hashes = {row["GOID"]: row for row in read_csv(args.reference_hashes)}
    if not selected_set <= set(hashes):
        parser.error("Reference hashes lack assigned GOIDs")
    found: dict[str, tuple[str, str]] = {}
    duplicates: set[str] = set()
    paths = sorted(args.xml_dir.rglob("*.xml"))
    if not paths:
        parser.error("No XML files found")
    print(f"Scanning {len(paths)} XML files for {len(selected)} assigned GOIDs", flush=True)
    parse_errors = 0
    for index, path in enumerate(paths, 1):
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            parse_errors += 1
            continue
        goid = (root.findtext("./GOID") or "").strip()
        if goid not in selected_set:
            continue
        if goid in found:
            duplicates.add(goid)
            continue
        title = plain_text(root.find("./Obj/TitleAtt/Title"))
        abstract = PREFIX.sub("", plain_text(root.find("./Obj/Abstract")), count=1)
        found[goid] = title, abstract
        if index % 5000 == 0:
            print(f"Scanned {index}/{len(paths)} files; found {len(found)}/{len(selected)}", flush=True)
    check_rows: list[dict[str, str]] = []
    input_rows: list[dict[str, str]] = []
    for goid in selected:
        expected = hashes[goid]
        title, abstract = found.get(goid, ("", ""))
        if goid not in found:
            status = "missing_xml"
        elif goid in duplicates:
            status = "duplicate_xml"
        elif not title or not abstract:
            status = "missing_text"
        elif evidence_hash(title, abstract, loose=False) == expected["reference_exact_sha256"]:
            status = "exact"
        elif evidence_hash(title, abstract, loose=True) == expected["reference_loose_sha256"]:
            status = "formatting_only"
        else:
            status = "different"
        title_match = bool(title) and sha256(loose_text(title)) == expected["reference_title_loose_sha256"]
        abstract_match = bool(abstract) and sha256(loose_text(abstract)) == expected["reference_abstract_loose_sha256"]
        check_rows.append({"GOID": goid, "xml_found": str(goid in found).lower(),
                           "match_status": status, "title_loose_match": str(title_match).lower(),
                           "abstract_loose_match": str(abstract_match).lower()})
        if status in {"exact", "formatting_only"}:
            input_rows.append({"GOID": goid, "title": title, "abstract": abstract,
                               "abstract_input_status": "present", "evidence_source": "workbench_full_corpus_v4_xml"})
    check_path = args.output.with_name("production_xml_evidence_check.csv")
    write_csv(check_path, CHECK_FIELDS, check_rows)
    bad = [row for row in check_rows if row["match_status"] not in {"exact", "formatting_only"}]
    if bad:
        raise ValueError(f"{len(bad)} assigned XML records need resolution; GOID-only check: {check_path}")
    write_csv(args.output, FIELDS, input_rows)
    exact = sum(row["match_status"] == "exact" for row in check_rows)
    print(json.dumps({"assigned": len(selected), "exact": exact,
                      "formatting_only": len(selected) - exact,
                      "unselected_xml_parse_errors": parse_errors,
                      "private_input": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
