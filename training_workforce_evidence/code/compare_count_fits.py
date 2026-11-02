"""Compare fresh outputs to a separate canonical six-target reference snapshot.

Run only after reproduce_count_models.py. The reference is never an estimator
input. Its point strings were retained by the adopted inference revision.
"""
import argparse
import csv
import json
import math
from pathlib import Path

TOLERANCES = {
    "log_rate_ratio": 1e-7, "rate_ratio": 2e-7, "percent_change": 2e-5,
    "se_log": 1e-8, "df": 1e-5, "pvalue": 2e-7,
    "bonferroni_family3_pvalue": 6e-7,
    "pointwise95_lower": 2e-7, "pointwise95_upper": 2e-7,
    "familywise95_lower": 2e-7, "familywise95_upper": 2e-7,
}
EXACT = ("ownership", "degree_target", "cluster_count", "significance_family3_05")


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    keyed = {row["result_id"]: row for row in rows}
    if len(keyed) != 6 or len(rows) != 6:
        raise ValueError("Expected exactly six distinct institutional count targets")
    return keyed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    bundle, output = args.bundle.resolve(), args.output_dir.resolve()
    if output.is_relative_to(bundle):
        raise ValueError("Use an output directory outside the candidate")
    reference = read(bundle / "expected/primary_results_reference.csv")
    fresh = read(output / "fresh_primary_results.csv")
    if set(reference) != set(fresh):
        raise ValueError("Fresh target identifiers differ from reference")
    comparisons, maxima, exact_match = [], {}, True
    for result_id in sorted(reference):
        old, new = reference[result_id], fresh[result_id]
        for field in EXACT:
            same = old[field] == new[field]
            exact_match = exact_match and same
            comparisons.append(dict(result_id=result_id, field=field, canonical=old[field],
                                    fresh=new[field], absolute_difference="", absolute_tolerance="", passed=same))
        for field, tolerance in TOLERANCES.items():
            a, b = float(old[field]), float(new[field])
            difference = abs(a - b)
            passed = math.isfinite(a) and math.isfinite(b) and difference <= tolerance
            maxima[field] = max(maxima.get(field, 0), difference)
            comparisons.append(dict(result_id=result_id, field=field, canonical=old[field],
                                    fresh=new[field], absolute_difference=difference,
                                    absolute_tolerance=tolerance, passed=passed))
    passed = all(item["passed"] for item in comparisons)
    receipt = dict(status="passed" if passed else "failed", primary_targets=6,
                   numeric_fields_per_target=len(TOLERANCES), exact_fields_matched=exact_match,
                   maximum_absolute_differences=maxima, absolute_tolerances=TOLERANCES,
                   reference_role="canonical adopted results; read only after fresh estimation",
                   point_difference_explanation="adopted inference retained earlier canonical point strings; replay refits points",
                   scope="primary retained-sample points and institution-cluster inference only")
    output.mkdir(parents=True, exist_ok=True)
    with (output / "reference_comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(comparisons)
    (output / "reference_comparison.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="")
    print(json.dumps(receipt, indent=2))
    if not passed:
        raise ValueError("Fresh results differ from canonical reference beyond stated tolerances")


if __name__ == "__main__":
    main()
