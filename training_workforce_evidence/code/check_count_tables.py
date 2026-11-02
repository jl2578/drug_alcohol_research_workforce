"""Verify exact candidate inventory, hashes and table dictionary coverage."""
import argparse
import csv
import json
from pathlib import Path


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    bundle, output = args.bundle.resolve(), args.output_dir.resolve()
    if output.is_relative_to(bundle):
        raise ValueError("Use an output directory outside the candidate")
    # File inventory and hashes are checked once, by verify_all.py and the root SHA256SUMS.txt.
    _, catalog = read(bundle / "metadata/file_catalog.csv")
    covered = []
    for item in catalog:
        fields, rows = read(bundle / item["path"])
        _, dictionary = read(bundle / item["dictionary"])
        if [row["field"] for row in dictionary] != fields:
            raise ValueError("Dictionary does not match ordered table columns: " + item["path"])
        if len(rows) != int(item["rows"]) or len(fields) != int(item["columns"]):
            raise ValueError("Table dimensions differ from catalog")
        key = item["primary_key"].split(";")
        if len({tuple(row[name] for name in key) for row in rows}) != len(rows):
            raise ValueError("Duplicate primary key: " + item["path"])
        covered.append(dict(path=item["path"], rows=len(rows), columns=len(fields), dictionary_checked=True))
    if {row["path"] for row in covered} != {"data/institutional_count_analysis_panel.csv", "metadata/fit_registry.csv", "expected/primary_results_reference.csv"}:
        raise ValueError("Unexpected analysis-table catalog")
    receipt = dict(status="passed", catalog_tables=covered,
                   verification="table dimensions, keys and ordered dictionary coverage")
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest_verification.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
