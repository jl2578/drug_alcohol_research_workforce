"""Build two independent, private round-one human calibration CSV packages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path


SOURCE_REVISION = "10"
SOURCE_SHA256 = "2B239675D7F7F35FA6534618CC667424F6871F878830975EAC28D48E46565008"
SENTENCE_INDEX_VERSION = "v5_calibration_sentence_index_v1"
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“‘(])")
SCOPE = (
    "substance_roles", "stated_purposes", "unrelated_therapeutic_indication_tested",
    "substance_all", "substance_primary", "substance_assignment_basis",
)
CONTENT = (
    "mixed_purpose", "dissertation_type", "study_design", "level_of_analysis",
    "research_objective", "intervention_continuum", "explanatory_domain",
    "data_type", "data_source_origin",
)
SUFFIXES = ("value", "coding_status", "decision_path", "confidence")
RECORD_COLUMNS = (
    "GOID", "title", "abstract", "abstract_input_status", "numbered_evidence",
    "coder_id", "codebook_revision", "codebook_sha256", "sentence_index_version",
    *(f"add_su_focus_{suffix}" for suffix in SUFFIXES),
    *(f"{field}_{suffix}" for field in CONTENT for suffix in SUFFIXES),
    "target_aim_ids", "calibration_note",
)
AIM_COLUMNS = (
    "GOID", "aim_id", "source_sentence_ids",
    *(f"{field}_{suffix}" for field in SCOPE for suffix in SUFFIXES),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def numbered_evidence(title: str, abstract: str) -> str:
    # IDs are structural references; original source fields remain unchanged.
    parts = [title.strip(), *(part.strip() for part in SENTENCE_BREAK.split(abstract.strip()))]
    return "\n".join(f"[s{index}] {part}" for index, part in enumerate(parts, 1) if part)


def write_csv(path: Path, columns: tuple[str, ...], records: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--random-sample", type=Path, required=True)
    parser.add_argument("--purposive", type=Path, required=True)
    parser.add_argument("--codebook", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error(f"Refusing to overwrite existing package: {args.output_dir}")
    ledger_rows = read_csv(args.ledger)
    by_goid = {row["GOID"]: row for row in ledger_rows}
    if len(by_goid) != len(ledger_rows):
        raise ValueError("Duplicate GOID in evidence ledger")
    random_rows = read_csv(args.random_sample)
    purposive_rows = read_csv(args.purposive)
    all_sample = random_rows + purposive_rows
    if len({row["GOID"] for row in all_sample}) != len(all_sample):
        raise ValueError("Random, held-out and purposive memberships overlap")
    random_goids = [row["GOID"] for row in random_rows if row["sample_role"] == "development_round1_random"]
    boundary_goids = [row["GOID"] for row in purposive_rows if row["sample_role"] == "development_round1_purposive_candidate"]
    if len(random_goids) != 40 or len(boundary_goids) != 33:
        raise ValueError(f"Expected 40 random + 33 purposive cases, got {len(random_goids)} + {len(boundary_goids)}")
    selected = random_goids + boundary_goids
    if any(goid not in by_goid or by_goid[goid]["abstract_input_status"] != "present" for goid in selected):
        raise ValueError("Selected GOID has no assessable local title/abstract")
    # A fixed order conceals which records were drawn randomly or purposively.
    selected.sort(key=lambda goid: (hashlib.sha256(f"p3_10a_round1_order:{goid}".encode()).digest(), goid))
    codebook_text = args.codebook.read_text(encoding="utf-8")
    if SOURCE_SHA256 not in codebook_text or "revision 10" not in codebook_text:
        raise ValueError("Unexpected calibration codebook provenance")
    args.output_dir.mkdir(parents=True)
    for coder in ("coder_a", "coder_b"):
        target = args.output_dir / coder
        target.mkdir()
        record_rows = []
        aim_rows = []
        for goid in selected:
            evidence = by_goid[goid]
            record_rows.append({
                "GOID": goid,
                "title": evidence["title"],
                "abstract": evidence["abstract"],
                "abstract_input_status": evidence["abstract_input_status"],
                "numbered_evidence": numbered_evidence(evidence["title"], evidence["abstract"]),
                "coder_id": coder,
                "codebook_revision": SOURCE_REVISION,
                "codebook_sha256": SOURCE_SHA256,
                "sentence_index_version": SENTENCE_INDEX_VERSION,
            })
            aim_rows.append({"GOID": goid, "aim_id": "a1"})
        write_csv(target / "records.csv", RECORD_COLUMNS, record_rows)
        write_csv(target / "aims.csv", AIM_COLUMNS, aim_rows)
        shutil.copyfile(args.codebook, target / "codebook.md")
    manifest = {
        "round": 1,
        "status": "ready_for_independent_human_coding",
        "random_n": len(random_goids),
        "purposive_n": len(boundary_goids),
        "total_n": len(selected),
        "sample_goids_sha256": hashlib.sha256("\n".join(sorted(selected)).encode()).hexdigest(),
        "selection_categories": dict(Counter(row["selection_category"] for row in purposive_rows if row["GOID"] in boundary_goids)),
        "sentence_index_version": SENTENCE_INDEX_VERSION,
        "sentence_index_rule": "s1 is the title; abstract starts at s2. Split abstract after .!? when followed by whitespace and an uppercase letter, digit, quote or opening parenthesis. Preserve original title/abstract fields.",
        "codebook_revision": SOURCE_REVISION,
        "codebook_source_sha256": SOURCE_SHA256,
        "input_sha256": {name: sha256(path) for name, path in {
            "ledger": args.ledger, "random_sample": args.random_sample,
            "purposive": args.purposive, "codebook": args.codebook,
        }.items()},
    }
    manifest["package_sha256"] = {
        coder: {name: sha256(args.output_dir / coder / name) for name in ("records.csv", "aims.csv", "codebook.md")}
        for coder in ("coder_a", "coder_b")
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("round", "random_n", "purposive_n", "total_n", "sample_goids_sha256")}, indent=2))


if __name__ == "__main__":
    main()
