"""Prepare the 40-record pilot input inside TDM Studio from existing XML.

This script writes title/abstract text only inside the Workbench. It compares
each record with the frozen local evidence using hashes, without receiving any
local source text. A missing or substantively different record stops the run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import unicodedata
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET


FIELDS = ("GOID", "title", "abstract", "abstract_input_status", "evidence_source")
CHECK_FIELDS = ("GOID", "xml_found", "match_status", "title_loose_match", "abstract_loose_match")
PREFIX = re.compile(r"^\s*ENG\s+English\s+English\s*", re.IGNORECASE)


class TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def plain_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    parser = TextOnly()
    parser.feed(unescape("".join(node.itertext())))
    parser.close()
    return " ".join(parser.parts)


def norm_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def loose_text(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKC", norm_text(value)).casefold() if char.isalnum())


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def evidence_hash(title: str, abstract: str, *, loose: bool) -> str:
    clean = loose_text if loose else norm_text
    return sha256(clean(title) + "\0" + clean(abstract))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml-dir", type=Path, required=True)
    parser.add_argument("--pilot-goids", type=Path, required=True)
    parser.add_argument("--reference-hashes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.xml_dir.is_dir():
        raise ValueError(f"XML directory not found: {args.xml_dir}")
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite frozen pilot input: {args.output}")
    selected = [row["GOID"] for row in read_csv(args.pilot_goids)]
    if len(selected) != 40 or len(set(selected)) != 40:
        raise ValueError("Expected 40 distinct pilot GOIDs")
    hash_rows = read_csv(args.reference_hashes)
    hashes = {row["GOID"]: row for row in hash_rows}
    if len(hashes) != 40 or len(hash_rows) != 40 or set(hashes) != set(selected):
        raise ValueError("Reference hashes do not match the 40 pilot GOIDs")
    found: dict[str, tuple[str, str]] = {}
    duplicates: set[str] = set()
    paths = sorted(args.xml_dir.rglob("*.xml"))
    if not paths:
        raise ValueError(f"No XML files under {args.xml_dir}")
    print(f"Scanning {len(paths)} Workbench XML files for 40 pilot GOIDs", flush=True)
    parse_errors = 0
    for index, path in enumerate(paths, 1):
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            parse_errors += 1
            continue
        goid = (root.findtext("./GOID") or "").strip()
        if goid not in hashes:
            continue
        if goid in found:
            duplicates.add(goid)
            continue
        title = plain_text(root.find("./Obj/TitleAtt/Title"))
        abstract = PREFIX.sub("", plain_text(root.find("./Obj/Abstract")), count=1)
        found[goid] = title, abstract
        if index % 5000 == 0:
            print(f"Scanned {index}/{len(paths)} files; found {len(found)}/40", flush=True)
    check_rows: list[dict[str, str]] = []
    input_rows: list[dict[str, str]] = []
    for goid in selected:
        expected = hashes[goid]
        if goid not in found:
            status, title, abstract = "missing_xml", "", ""
        else:
            title, abstract = found[goid]
            if goid in duplicates:
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
                               "abstract_input_status": "present",
                               "evidence_source": "workbench_full_corpus_v4_xml"})
    check_path = args.output.with_name("pilot_xml_evidence_check.csv")
    write_csv(check_path, CHECK_FIELDS, check_rows)
    bad = [row for row in check_rows if row["match_status"] not in {"exact", "formatting_only"}]
    if bad:
        raise ValueError(f"Pilot XML evidence differs for {len(bad)} GOIDs; inspect GOID-only {check_path} before model calls")
    if parse_errors:
        print(f"XML parse errors outside selected GOIDs: {parse_errors}", flush=True)
    write_csv(args.output, FIELDS, input_rows)
    exact = sum(row["match_status"] == "exact" for row in check_rows)
    print(f"Prepared 40 Workbench records: {exact} exact, {40-exact} formatting-only matches; input stays in Workbench", flush=True)


if __name__ == "__main__":
    main()

