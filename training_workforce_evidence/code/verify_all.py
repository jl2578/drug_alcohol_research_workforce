"""Check every supplied number that can be checked, with one command.

    python code/verify_all.py --output <new folder outside this package>

The command restores each original table from the stacked data files, confirms it
matches its recorded SHA-256, then runs the arithmetic checks and the institutional
count fits. Run it with ordinary Python, not python -O. The count fits need the two
packages in code/requirements.txt; use --skip-fits if they are not installed.

Other uses:
    python code/verify_all.py export DEP2_T1_outcome_coverage --output table.csv
    python code/verify_all.py export-tables --output <new folder>
    python code/verify_all.py restore --output <new folder>
"""
import argparse
import csv
import hashlib
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
CODE = PACKAGE / "code"
DATA = PACKAGE / "data"
csv.field_size_limit(10**9)

# Expected results of each route. A change in any value fails the run.
EXPECTED = {
    "measurement": {"csv_rows_inspected": 2284, "proportions_recomputed": 1761, "wilson_intervals_recomputed": 549, "content_kappa_fields": 8},
    "rq2_points": {"supported_count_rows": 2528, "group_points": 3376, "pairwise_points": 5280},
    "funding_rebuild": {"funding_window_rows": 26628, "exposure_replay_byte_equal": True},
    "count_tables": {"status": "passed"},
    "count_fits": {"fresh_fit_count": 8, "primary_target_count": 6},
    "count_reference": {"status": "passed"},
    "rq3_aggregates": {"numerical_checks_total": 19353, "saved_summary_inference_rows_replayed": 98},
    "employment": {"csv_rows": 5751, "arithmetic_checks": 14024, "figure_cells": 156},
    "added_tables": {"checks": 624},
}


def index():
    with (DATA / "TABLE_INDEX.csv").open(encoding="utf-8", newline="") as stream:
        entries = list(csv.DictReader(stream))
    with (CODE / "table_restore.csv").open(encoding="utf-8", newline="") as stream:
        extra = {row["table"]: row for row in csv.DictReader(stream)}
    return [{**entry, **extra[entry["table"]]} for entry in entries]


def stacked_rows(path):
    """Yield (table, row number, cells) from a stacked file."""
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        next(reader)
        for line in reader:
            yield line[0], int(line[1]), line[2:]


def load_stacks(entries):
    tables = {}
    for name in sorted({e["file"] for e in entries if e["storage"] == "stacked"}):
        for table, _, cells in stacked_rows(PACKAGE / name):
            tables.setdefault(table, []).append(cells)
    return tables


def table_bytes(entry, rows):
    width = int(entry["columns"])
    text = io.StringIO(newline="")
    eol = "\r\n" if entry["line_ending"] == "CRLF" else "\n"
    csv.writer(text, lineterminator=eol).writerows(row[:width] for row in rows)
    return (b"\xef\xbb\xbf" if entry["bom"] == "yes" else b"") + text.getvalue().encode("utf-8")


def restore(tree):
    """Rebuild the original tables and check inputs under tree; return how many were hash-checked."""
    entries = index()
    stacks = load_stacks(entries)
    checked = 0
    for entry in entries:
        if not entry["restored_path"]:
            continue
        target = tree / entry["restored_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        from table_access import content as table_content
        content = table_content(sys.modules[__name__], entry, {e["table"]: e for e in entries}, stacks)
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError("Restored table differs from its recorded hash: " + entry["table"])
        target.write_bytes(content)
        checked += 1
    for archive_name, prefix in (("code/check_inputs.zip", ""), ("data/nih_funding_rebuild.zip", "DEP3/institutional_nih/")):
        with zipfile.ZipFile(PACKAGE / archive_name) as archive:
            for member in archive.namelist():
                if member.endswith("/"):
                    continue
                target = tree / (prefix + member)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
    return checked


def long_path(path):
    """Restored paths are deep; on Windows this allows folders whose full path would pass 260 characters."""
    path = path.resolve()
    return Path("\\\\?\\" + str(path)) if sys.platform == "win32" else path


def run(name, command, results, parse_json=True):
    print(f"  {name} ...", flush=True)
    done = subprocess.run([sys.executable, "-B", *map(str, command)], capture_output=True, text=True, encoding="utf-8")
    if done.returncode:
        results[name] = {"status": "FAILED", "stderr": done.stderr[-2000:], "stdout": done.stdout[-500:]}
        return None
    if not parse_json:
        return done.stdout
    return json.loads(done.stdout)


def compare(name, got, results):
    wanted = EXPECTED[name]
    bad = {k: (got.get(k), v) for k, v in wanted.items() if got.get(k) != v}
    results[name] = {"status": "FAILED" if bad else "passed", **{k: got.get(k) for k in wanted}}
    if bad:
        results[name]["differences"] = {k: {"got": a, "expected": b} for k, (a, b) in bad.items()}


def added_tables():
    """Arithmetic for the tables added in recent versions, and printed tables that follow from the supplied data."""
    entries = index()
    stacks = load_stacks(entries)
    def rows(table):
        head, *body = stacks[table]
        width = next(e for e in entries if e["table"] == table)
        return [dict(zip(head[:int(width["columns"])], r)) for r in body]
    checks = []
    def near(label, a, b, tol=5e-4):
        checks.append(label)
        if abs(a - b) > tol:
            raise ValueError(f"{label}: {a} != {b}")
    screen = {r["measure"]: int(r["value"]) for r in rows("DEP1_later_doctorate_screen")}
    near("share of master's works with a candidate", 100 * screen["masters_works_with_candidate"] / screen["masters_works"], 10.7, .05)
    near("share of psychology master's works with a candidate", 100 * screen["psychology_works_with_candidate"] / screen["psychology_masters_works"], 27.2, .05)
    near("in-scope candidates do not exceed candidates", min(screen["works_with_in_scope_candidate"], screen["masters_works_with_candidate"]), screen["works_with_in_scope_candidate"], 0)
    near("usable names do not exceed works", min(screen["masters_works_with_usable_name"], screen["masters_works"]), screen["masters_works_with_usable_name"], 0)
    near("pairs cover works", max(screen["candidate_pairs"], screen["masters_works_with_candidate"]), screen["candidate_pairs"], 0)
    near("remaining works", screen["psychology_masters_works"] - screen["psychology_works_with_candidate"], screen["psychology_works_after_exclusion"], 0)
    near("remaining connected works", screen["psychology_connected_works"] - screen["excluded_connected_works"], screen["connected_works_after_exclusion"], 0)
    before = 100 * screen["psychology_connected_works"] / screen["psychology_masters_works"]
    after = 100 * screen["connected_works_after_exclusion"] / screen["psychology_works_after_exclusion"]
    near("connection share before exclusion", before, 39.8, .05)
    near("connection share after exclusion", after, 38.4, .05)
    near("decrease in connection share", before - after, 1.4, .05)
    reach = rows("DEP3_degree_field_funding_reach")
    psychology = next(r for r in reach if r["degree"] == "Masters" and r["field_code"] == "BF01")
    near("psychology works match the reach table", int(psychology["all_works_n"]), screen["psychology_masters_works"], 0)
    near("psychology connected works match the reach table", int(psychology["connected_works_n"]), screen["psychology_connected_works"], 0)
    near("master's works match the cohort", sum(int(r["all_works_n"]) for r in reach if r["degree"] == "Masters"), screen["masters_works"], 0)
    printed = {("Research doctorate", "preceding_in_joint_model"): 1.207, ("Research doctorate", "later_in_joint_model"): 1.134,
               ("Research doctorate", "preceding_only_same_cells"): 1.167, ("Masters", "preceding_in_joint_model"): 1.097,
               ("Masters", "later_in_joint_model"): 1.121, ("Masters", "preceding_only_same_cells"): 1.104}
    timing = rows("DEP3_joint_timing_check")
    for row in timing:
        key = (row["degree_group"], row["term"])
        near("printed rate ratio " + str(key), round(float(row["rate_ratio"]), 3), printed[key], 1e-9)
        if row["log_rate_ratio"]:
            near("log rate ratio " + str(key), math.exp(float(row["log_rate_ratio"])), float(row["rate_ratio"]), 1e-9)
        near("retained cells " + str(key), int(row["retained_cells"]), {"Research doctorate": 2575, "Masters": 2769}[row["degree_group"]], 0)
    # Tables S3.6 and S3.7 follow from the institution panel.
    with (DATA / "institution_panel.csv").open(encoding="utf-8-sig", newline="") as stream:
        panel = list(csv.DictReader(stream))
    samples = {("Full", "Research doctorate"): (4444, 350, 7949, 649632), ("Full", "Masters"): (3354, 283, 3455, 307177),
               ("Full common", "Research doctorate"): (2440, 196, 4983, 399094), ("Full common", "Masters"): (2440, 196, 2759, 262338),
               ("Excluded", "Research doctorate"): (4304, 337, 7374, 625090), ("Excluded", "Masters"): (3309, 279, 3386, 305789),
               ("Excluded common", "Research doctorate"): (2408, 193, 4905, 396803), ("Excluded common", "Masters"): (2408, 193, 2714, 261076)}
    for (name, degree), printed in samples.items():
        chosen = [r for r in panel if r["degree_group"] == degree
                  and ("common" not in name or r["retained_full_common"] == "1")
                  and ("Excluded" not in name or r["ever_for_profit"] == "0")]
        found = (len(chosen), len({r["institution_id"] for r in chosen}), sum(int(r["S_current"]) for r in chosen), sum(int(r["D_mapped_exact"]) for r in chosen))
        for label, a, b in zip(("cells", "institutions", "S", "D"), found, printed):
            near(f"Table S3.6 {name} {degree} {label}", a, b, 0)
    support = {"Research doctorate": ((101, 51), (33, 24), (149, 11)), "Masters": ((212, 80), (46, 26), (244, 19))}
    for degree, years in (("Research doctorate", 5), ("Masters", 2)):
        chosen = [(r["institution_id"], int(r["F_window_project_years"]) / years) for r in panel if r["degree_group"] == degree]
        ranges = {}
        for unit, value in chosen:
            ranges.setdefault(unit, []).append(value)
        bracket = [unit for unit, values in ranges.items() if min(values) <= 1 and max(values) >= 4]
        found = (([u for u, v in chosen if v == 1], {u for u, v in chosen if v == 1}), ([u for u, v in chosen if v == 4], {u for u, v in chosen if v == 4}),
                 ([u for u, v in chosen if u in bracket], bracket))
        for label, (cells, units), printed in zip(("exactly 1", "exactly 4", "brackets 1 to 4"), found, support[degree]):
            near(f"Table S3.7 {degree} {label} cells", len(cells), printed[0], 0)
            near(f"Table S3.7 {degree} {label} institutions", len(units), printed[1], 0)
    # Table S3.12 prints the works connected to both institutes: NIDA plus NIAAA minus either.
    observed = {(r["population"], r["institute"]): int(r["numerator"]) for r in rows("DEP3_observed_reach")
                if r["ownership"] == "full" and r["connection_definition"] == "combined_clear"}
    for population, printed in (("Research doctorate", 791), ("All credentials", 930)):
        near(f"Table S3.12 {population} both institutes", observed[population, "NIDA"] + observed[population, "NIAAA"] - observed[population, "NIDA/NIAAA"], printed, 0)
    with (DATA / "industry_focus.csv").open(encoding="utf-8", newline="") as stream:
        focus = list(csv.DictReader(stream))
    if len(focus) != 3 or {r["specification"] for r in focus} != {"inclusive", "conservative", "no_hospital_override"}:
        raise ValueError("Industry-focus specification set changed")
    for row in focus:
        if row["naics_groups"] != "5417;3254;3345;3391" or row["research_score_threshold"] != "3":
            raise ValueError("Industry-focus definition changed")
        tag = row["specification"]
        near(tag + " connected observed", int(row["connected_observations"]), 15, 0)
        near(tag + " connected likely", int(row["connected_likely_research"]), 15, 0)
        near(tag + " remaining observed", int(row["no_identified_connection_observations"]), 10, 0)
        near(tag + " remaining likely", int(row["no_identified_connection_likely_research"]), 7, 0)
        near(tag + " total", int(row["total_observations"]), int(row["connected_observations"]) + int(row["no_identified_connection_observations"]), 0)
        near(tag + " connected percent", float(row["connected_percent"]), 100*int(row["connected_likely_research"])/int(row["connected_observations"]), 1e-9)
        near(tag + " remaining percent", float(row["no_identified_connection_percent"]), 100*int(row["no_identified_connection_likely_research"])/int(row["no_identified_connection_observations"]), 1e-9)
        near(tag + " difference", float(row["difference_percentage_points"]), float(row["connected_percent"])-float(row["no_identified_connection_percent"]), 1e-9)
    # Table S4.15: research roles by destination and identified connection (destination_*.csv).
    def load(name):
        with (DATA / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    specs = ("inclusive", "conservative", "no_hospital_override")
    dest = load("destination_connection.csv")
    if {r["specification"] for r in dest} != set(specs) or {r["degree_group"] for r in dest} != {"Research doctorate"}:
        raise ValueError("Destination comparison set changed")
    counts = ("connected_observed_n", "connected_likely_n", "no_identified_connection_observed_n", "no_identified_connection_likely_n")
    for r in dest:
        tag = " ".join((r["specification"], r["dimension"], r["group"]))
        c_obs, c_lik, n_obs, n_lik = (int(r[c]) for c in counts)
        near(tag + " total", int(r["total_n"]), c_obs + n_obs, 0)
        if c_obs:
            near(tag + " connected percent", float(r["connected_pct"]), 100*c_lik/c_obs, 1e-9)
        if n_obs:
            near(tag + " remaining percent", float(r["no_identified_connection_pct"]), 100*n_lik/n_obs, 1e-9)
        if c_obs and n_obs:
            near(tag + " difference", float(r["difference_pp"]), float(r["connected_pct"]) - float(r["no_identified_connection_pct"]), 1e-9)
    by = {(r["specification"], r["dimension"], r["group"]): r for r in dest}
    college, outside = "Colleges universities and professional schools (611310)", "Outside 611310 with known industry"
    for spec in specs:
        whole = by[spec, "pooled", "All observed"]
        for dim in ("college_vs_outside", "figure_destination", "broad_sector", "retained_detailed_destination"):
            parts = [r for r in dest if r["specification"] == spec and r["dimension"] == dim]
            for c in counts:
                near(f"{spec} {dim} partition {c}", sum(int(r[c]) for r in parts), int(whole[c]), 0)
        groups = [r for r in dest if r["specification"] == spec and r["dimension"] == "figure_destination" and r["group"] not in (college, "Unknown industry")]
        for c in counts:
            near(f"{spec} outside destinations sum {c}", sum(int(r[c]) for r in groups), int(by[spec, "college_vs_outside", outside][c]), 0)
        pool = [by[spec, "figure_destination", g] for g in ("Scientific R&D services", "Pharmaceutical, device and instrument manufacturing")]
        row = next(r for r in focus if r["specification"] == spec)
        for c, f in zip(counts, ("connected_observations", "connected_likely_research", "no_identified_connection_observations", "no_identified_connection_likely_research")):
            near(f"{spec} R&D and manufacturing pool {c}", sum(int(r[c]) for r in pool), int(row[f]), 0)
    for g in load("destination_gap_contrast.csv"):
        spec = g["specification"]
        near(spec + " outside gap", float(g["outside_gap_pp"]), float(by[spec, "college_vs_outside", outside]["difference_pp"]), 1e-9)
        near(spec + " college gap", float(g["college_gap_pp"]), float(by[spec, "college_vs_outside", college]["difference_pp"]), 1e-9)
        near(spec + " gap contrast", float(g["outside_minus_college_gap_pp"]), float(g["outside_gap_pp"]) - float(g["college_gap_pp"]), 1e-9)
        for side, sign in (("low", -1), ("high", 1)):
            near(f"{spec} gap contrast {side}", float(g[f"normal_approx_95_{side}_pp"]), float(g["outside_minus_college_gap_pp"]) + sign*1.959963984540054*float(g["hc3_se_pp"]), 1e-6)
    for s in load("destination_standardization.csv"):
        spec = s["specification"]
        near(spec + " crude known-industry difference", float(s["crude_known_industry_difference_pp"]), float(by[spec, "pooled", "Known industry"]["difference_pp"]), 1e-9)
        near(spec + " standardized difference", float(s["standardized_difference_pp"]), float(s["connected_standardized_pct"]) - float(s["no_identified_connection_standardized_pct"]), 1e-9)
    return {"status": "passed", "checks": len(checks)}


def verify(args):
    if sys.flags.optimize or not __debug__:
        raise SystemExit("Run with ordinary Python, not python -O: some checks use assertions.")
    output = args.output.resolve()
    if output == PACKAGE or PACKAGE in output.parents:
        raise SystemExit("--output must be outside this package")
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix="tw_") as temp:
        tree = Path(temp)
        print("Restoring original tables and checking their hashes ...", flush=True)
        restored = restore(tree)
        results["table_restore"] = {"status": "passed", "tables_hash_checked": restored}
        print(f"  {restored} tables match\nRunning checks ...", flush=True)
        nih = tree / "DEP3/institutional_nih/nih"
        count = tree / "DEP3/institutional_nih/rq3"

        got = run("measurement", [CODE / "check_measurement.py", "--root", tree / "DEP1/measurement", "--output", output / "measurement.json"], results)
        if got: compare("measurement", got, results)
        got = run("rq2_points", [CODE / "rebuild_rq2_points.py", "--counts", tree / "DEP2/research_content/inputs/group_period_category_counts.csv", "--estimates", DATA / "rq2_estimates.csv"], results)
        if got: compare("rq2_points", got, results)
        got = run("funding_rebuild", [nih / "code/verify_candidate.py", "--bundle", nih, "--output-dir", output / "funding"], results)
        if got: compare("funding_rebuild", got["funding"], results)
        got = run("count_tables", [CODE / "check_count_tables.py", "--bundle", count, "--output-dir", output / "count"], results)
        if got: compare("count_tables", got, results)
        if args.skip_fits:
            results["count_fits"] = results["count_reference"] = {"status": "not run (--skip-fits)"}
        else:
            got = run("count_fits", [CODE / "fit_count_models.py", "--bundle", count, "--output-dir", output / "count"], results)
            if got: compare("count_fits", got, results)
            got = run("count_reference", [CODE / "compare_count_fits.py", "--bundle", count, "--output-dir", output / "count"], results)
            if got: compare("count_reference", got, results)
        got = run("rq3_aggregates", [CODE / "check_rq3_package.py", "--bundle", tree / "DEP3/other_rq3", "--output-dir", output / "rq3_aggregates"], results)
        if got: compare("rq3_aggregates", got, results)
        got = run("employment", [CODE / "check_employment.py", "--root", tree / "DEP4/rc_rmi"], results)
        if got: compare("employment", got, results)
    print("  added_tables ...", flush=True)
    compare("added_tables", added_tables(), results)
    failed = [k for k, v in results.items() if v["status"] == "FAILED"]
    results["overall"] = "FAILED" if failed else "passed"
    (output / "verification_receipt.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
    print()
    for key, value in results.items():
        if key != "overall":
            details = ", ".join(f"{a}={b}" for a, b in value.items() if a not in {"status", "stderr", "stdout", "differences"})
            print(f"{value['status']:<8} {key:<18} {details}")
    print("\nOverall:", results["overall"], "| receipt:", output / "verification_receipt.json")
    if failed:
        print("Details are in the receipt.")
        raise SystemExit(1)


def export(args):
    entries = index()
    entry = next((e for e in entries if e["table"] == args.table), None)
    if not entry:
        raise SystemExit("Unknown table; see data/TABLE_INDEX.csv")
    if args.output.exists():
        raise SystemExit("Output already exists")
    from table_access import content as table_content
    entries = index()
    content = table_content(sys.modules[__name__], entry, {e["table"]: e for e in entries}, load_stacks(entries))
    args.output.write_bytes(content)
    print(args.output, len(content), "bytes")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="verify", choices=("verify", "export", "export-tables", "restore"))
    parser.add_argument("table", nargs="?")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-fits", action="store_true", help="Skip the count fits, which need NumPy and SciPy")
    args = parser.parse_args()
    if args.command == "export":
        export(args)
    elif args.command == "export-tables":
        from table_access import export_tables
        export_tables(sys.modules[__name__], args.output)
    elif args.command == "restore":
        if args.output.exists() and any(args.output.iterdir()):
            raise SystemExit("--output must be a new or empty folder")
        args.output.mkdir(parents=True, exist_ok=True)
        print(restore(long_path(args.output)), "tables restored and hash-checked under", args.output)
    else:
        verify(args)


if __name__ == "__main__":
    main()
