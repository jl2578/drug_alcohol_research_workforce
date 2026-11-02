"""Fresh eight-fit/six-target institutional-count reproduction from candidate data.

The institution intercept is profiled exactly. Funding and log mapped indexed
output are estimated covariates; output is not an offset. Year nuisances remain
estimated. The reduced panel and one stored common-sample flag supply the adopted samples; this program does not
independently reconstruct source linkage, degree classification or separation.

The primary profile-HC3/working-Poisson Satterthwaite calculations are extracted
and adapted from the study's poisson_inference_validation.py (ProfileModel,
JointProfile, fit_profile, grouped, linearized_methods) and
institution_count_cluster_revision.py (targets_for, wald). Source attribution
and byte hashes are METHOD_SOURCES below. No original script is imported and
no saved coefficient, fitted mean, canonical point or reference result is read.

Dependencies: Python 3.11+ for the pinned NumPy/SciPy stack (tested 3.13.15).
No pandas, network or private inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from io import StringIO
import json
import math
import os
from pathlib import Path
import platform
import re

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np
import scipy
from scipy.linalg import block_diag
from scipy.stats import t

METHOD_SOURCES = {
    "poisson_inference_validation.py": "4114221751aec4278ad2c1c198f5f4ce4ce337fbeb77a8029a8bb679912e95db",
    "institution_count_cluster_revision.py": "13664845868b7e7299c91397b7cc5ef1bce8f9186fe10403223f0948d8f10b56",
}
SCALE = math.log(5) - math.log(2)
OWNERS = ("full", "exclude_ever_for_profit")
DEGREES = ("Research doctorate", "Masters")
PANEL_COLUMNS = ['institution_id', 'completion_year', 'degree_group', 'S_current', 'D_mapped_exact', 'F_window_project_years', 'ever_for_profit', 'retained_full_common']
REGISTRY_COLUMNS = ["fit_id", "ownership", "sample_type", "degree_group", "retained_flag",
                    "expected_cells", "expected_clusters"]
FLAGS = {(owner, sample): "retained_" + ("full" if owner == "full" else "noFP") + "_" + sample
         for owner in OWNERS for sample in ("main", "common")}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path, expected):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == expected, "Unexpected schema: " + path.name)
        data = list(reader)
    require(all(None not in row and all(v is not None for v in row.values()) for row in data),
            "Malformed CSV row: " + path.name)
    return data


def write_csv(path, rows):
    require(bool(rows), "Cannot write empty results")
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(output.getvalue(), encoding="utf-8", newline="")


def factorize(values):
    names, codes = np.unique(np.asarray(values), return_inverse=True)
    return codes, names


class ProfileModel:
    """Exact Poisson institution-intercept profile with estimated year nuisances."""
    def __init__(self, rows):
        self.rows = rows
        self.unit, self.units = factorize([r["institution_id"] for r in rows])
        self.year, self.years = factorize([int(r["completion_year"]) for r in rows])
        self.y = np.asarray([int(r["S_current"]) for r in rows], dtype=float)
        self.D = np.column_stack([
            [math.log1p(int(r["F_window_project_years"]) / int(r["window_years"])) for r in rows],
            [math.log(int(r["D_mapped_exact"])) for r in rows],
            np.eye(len(self.years))[self.year, 1:]])
        self.n, self.p = self.D.shape
        self.groups = len(self.units)
        self.labels = np.asarray([r["institution_id"] for r in rows])

    def evaluate(self, beta):
        totals = np.bincount(self.unit, weights=self.y, minlength=self.groups)
        eta = self.D @ beta
        mx = np.full(self.groups, -np.inf)
        np.maximum.at(mx, self.unit, eta)
        exp_eta = np.exp(eta - mx[self.unit])
        exp_sums = np.bincount(self.unit, weights=exp_eta, minlength=self.groups)
        mu = totals[self.unit] * exp_eta / exp_sums[self.unit]
        means = np.column_stack([np.bincount(self.unit, weights=mu * self.D[:, j],
                                            minlength=self.groups) for j in range(self.p)])
        means = np.divide(means, totals[:, None], out=np.zeros_like(means), where=totals[:, None] > 0)
        centered = self.D - means[self.unit]
        residual = self.y - mu
        return dict(beta_profile=beta.copy(), mu=mu, Z=centered,
                    H=centered.T @ (mu[:, None] * centered), score=centered.T @ residual,
                    residual=residual, ll=float(self.y @ eta - totals @ (mx + np.log(exp_sums))))

    def fit(self, max_iter=80):
        beta = np.zeros(self.p)
        converged = False
        for iteration in range(1, max_iter + 1):
            fit = self.evaluate(beta)
            score_norm = float(np.max(np.abs(fit["score"]), initial=0) / (1 + np.sum(self.y)))
            if score_norm < 1e-10:
                converged = True
                break
            step = np.linalg.solve(fit["H"], fit["score"])
            accepted = False
            for halving in range(35):
                candidate = beta + step * 2. ** (-halving)
                trial = self.evaluate(candidate)
                if np.isfinite(trial["ll"]) and trial["ll"] >= fit["ll"] - 1e-10 * (1 + abs(fit["ll"])):
                    beta = candidate
                    accepted = True
                    break
            require(accepted, "Profile Newton line search failed")
        fit = self.evaluate(beta)
        rank = int(np.linalg.matrix_rank(fit["H"], tol=max(np.linalg.norm(fit["H"], 2), 1) * 1e-10))
        require(converged and rank == self.p, "Profile fit failed convergence or full-rank check")
        fit.update(converged=True, iterations=iteration, normalized_score=score_norm, rank=rank)
        require(np.all(np.isfinite(fit["mu"])) and np.all(fit["mu"] > 0), "Invalid fitted mean")
        fitted_totals = np.bincount(self.unit, weights=fit["mu"], minlength=self.groups)
        observed_totals = np.bincount(self.unit, weights=self.y, minlength=self.groups)
        require(np.max(np.abs(fitted_totals - observed_totals)) < 1e-8, "Profile unit totals do not conserve")
        return fit


class JointProfile:
    """Separate degree nuisances with common institution labels and paired scores."""
    def __init__(self, models, fits):
        self.models = models
        self.n = sum(m.n for m in models)
        self.p = sum(m.p for m in models)
        self.labels = np.concatenate([m.labels for m in models])
        self.rows = sum((m.rows for m in models), [])
        self.fit = dict(beta_profile=np.concatenate([f["beta_profile"] for f in fits]),
                        mu=np.concatenate([f["mu"] for f in fits]),
                        Z=block_diag(*[f["Z"] for f in fits]), H=block_diag(*[f["H"] for f in fits]),
                        score=np.concatenate([f["score"] for f in fits]),
                        residual=np.concatenate([f["residual"] for f in fits]))


def linearized_primary(fit, labels, contrast):
    """Profile-HC3 variance and nuisance-adjusted working-Poisson reference df.

    Cluster influence uses (H-H_g)^-1 rather than H^-1. K retains the complete
    estimated nuisance projection. No CR2 or exact finite-sample claim is made.
    """
    codes, names = factorize(labels)
    groups = len(names)
    hessian = fit["H"]
    p = hessian.shape[0]
    inverse = np.linalg.inv(hessian)
    score_rows = fit["Z"] * fit["residual"][:, None]
    scores = np.column_stack([np.bincount(codes, weights=score_rows[:, j], minlength=groups)
                              for j in range(p)])
    group_hessian = np.zeros((groups, p, p))
    for j in range(p):
        weighted = fit["mu"] * fit["Z"][:, j]
        for k in range(j + 1):
            group_hessian[:, j, k] = np.bincount(codes, weights=weighted * fit["Z"][:, k], minlength=groups)
            group_hessian[:, k, j] = group_hessian[:, j, k]
    adjusted = np.linalg.solve(hessian[None, :, :] - group_hessian,
                               np.broadcast_to(contrast, (groups, p))[..., None])[..., 0]
    influence = np.einsum("ij,ij->i", scores, adjusted)
    variance = (groups - 1) / groups * float(influence @ influence)
    ah = np.einsum("ij,ijk->ik", adjusted, group_hessian)
    diagonal = np.einsum("ij,ij->i", ah, adjusted)
    q = ah.T @ ah
    trace_k = diagonal.sum() - np.trace(inverse @ q)
    trace_k2 = (diagonal @ diagonal - 2 * np.sum(diagonal * np.einsum("ij,jk,ik->i", ah, inverse, ah))
                + np.trace(inverse @ q @ inverse @ q))
    reference_df = float(trace_k ** 2 / trace_k2)
    info = np.einsum("i,gij,j->g", inverse @ contrast, group_hessian, inverse @ contrast)
    share = info / info.sum()
    require(groups > 1 and variance > 0 and reference_df > 0 and trace_k > 0 and trace_k2 > 0,
            "Invalid variance or working-reference degrees of freedom")
    return dict(cluster_count=groups, se_log=math.sqrt(variance), df=reference_df,
                working_K_trace=float(trace_k), working_K_squared_trace=float(trace_k2),
                information_effective_institutions=float(1 / (share @ share)),
                maximum_target_information_share=float(share.max()), influence=influence)


def wald(point, se, df):
    pvalue = float(2 * t.sf(abs(point / se), df))
    critical = float(t.ppf(.975, df))
    family_critical = float(t.ppf(1 - .05 / 6, df))
    return dict(se_log=se, df=df, pvalue=pvalue, bonferroni_family3_pvalue=min(1., 3 * pvalue),
                pointwise95_lower=math.exp(point - critical * se), pointwise95_upper=math.exp(point + critical * se),
                familywise95_lower=math.exp(point - family_critical * se),
                familywise95_upper=math.exp(point + family_critical * se))


def load_data(bundle):
    panel_path = bundle / "data/institutional_count_analysis_panel.csv"
    registry_path = bundle / "metadata/fit_registry.csv"
    panel = read_csv(panel_path, PANEL_COLUMNS)
    registry = read_csv(registry_path, REGISTRY_COLUMNS)
    require(len(panel) == 7798, "Expected the 7,798-row union of adopted native retained fits")
    require(len(registry) == 8, "Expected exactly eight retained fit definitions")
    require(len({r["fit_id"] for r in registry}) == 8, "Duplicate fit identifier")
    keys = [(r["institution_id"], r["completion_year"], r["degree_group"]) for r in panel]
    require(len(set(keys)) == len(panel), "Duplicate panel observation key")
    for row in panel:
        require(re.fullmatch(r"INST[0-9]{6}", row["institution_id"]) is not None, "Malformed institutional key")
        require(row["degree_group"] in DEGREES, "Unexpected degree group")
        for field in ("completion_year", "S_current", "D_mapped_exact", "F_window_project_years"):
            require(re.fullmatch(r"0|[1-9][0-9]*", row[field]) is not None, "Noninteger or negative " + field)
        require(2010 <= int(row["completion_year"]) <= 2023, "Unexpected completion year")
        require(0 <= int(row["S_current"]) <= int(row["D_mapped_exact"]) and int(row["D_mapped_exact"]) > 0, "Invalid S/D count")
        require(row["ever_for_profit"] in ("0", "1"), "Invalid historical ownership flag")
        require(row["retained_full_common"] in ("0", "1"), "Invalid full common-sample flag")
        # Version-specific exact relations proven for this retained-native union.
        # No denominator-status value is invented; that field is not a model input.
        row["window_years"] = "5" if row["degree_group"] == DEGREES[0] else "2"
        row["exposure_ready"] = row["include_primary"] = row["retained_full_main"] = "1"
        row["exclusion_reasons"] = ""
        row["retained_noFP_main"] = str(1 - int(row["ever_for_profit"]))
        row["retained_noFP_common"] = str(int(row["retained_full_common"]) * (1 - int(row["ever_for_profit"])))
    configs = {}
    for item in registry:
        owner, sample, degree = item["ownership"], item["sample_type"], item["degree_group"]
        require(owner in OWNERS and sample in ("main", "common") and degree in DEGREES, "Unexpected retained fit definition")
        require(item["retained_flag"] == FLAGS[owner, sample], "Incorrect retained flag in fit registry")
        key = owner, sample, degree
        require(key not in configs, "Duplicate retained model definition")
        selected = [r for r in panel if r["degree_group"] == degree and r[item["retained_flag"]] == "1"]
        selected.sort(key=lambda r: (r["institution_id"], int(r["completion_year"])))
        require(len(selected) == int(item["expected_cells"]), "Retained sample cell count differs from registry")
        require(len({r["institution_id"] for r in selected}) == int(item["expected_clusters"]), "Retained cluster count differs from registry")
        configs[key] = item, selected
    require(set(configs) == {(o, s, d) for o in OWNERS for s in ("main", "common") for d in DEGREES}, "Incomplete retained fit registry")
    for owner in OWNERS:
        left = configs[owner, "common", DEGREES[0]][1]
        right = configs[owner, "common", DEGREES[1]][1]
        require([(r["institution_id"], r["completion_year"]) for r in left] == [(r["institution_id"], r["completion_year"]) for r in right], "Direct degree samples have different keys")
    return panel_path, registry_path, configs


def reproduce(bundle, output_dir):
    require(not output_dir.resolve().is_relative_to(bundle.resolve()), "Fresh outputs must remain outside the candidate bundle")
    panel_path, registry_path, configs = load_data(bundle)
    output_dir.mkdir(parents=True, exist_ok=True)
    fitted, diagnostics, coefficients = {}, [], []
    for key, (item, selected) in configs.items():
        model = ProfileModel(selected)
        fit = model.fit()
        fitted[key] = model, fit
        diagnostics.append(dict(fit_id=item["fit_id"], ownership=key[0], sample_type=key[1], degree_group=key[2],
            retained_cells=model.n, institution_clusters=model.groups, completion_year_levels=len(model.years),
            profile_design_rank=fit["rank"], estimated_profile_parameters=model.p, iterations=fit["iterations"],
            normalized_score=fit["normalized_score"], funding_beta=float(fit["beta_profile"][0]),
            log_output_beta=float(fit["beta_profile"][1]), S_retained=sum(int(r["S_current"]) for r in selected),
            D_retained=sum(int(r["D_mapped_exact"]) for r in selected),
            zero_S_cells=sum(int(r["S_current"]) == 0 for r in selected),
            sample_selection="supplied_adopted_retained_flag", model_fitted_fresh=True))
        terms = ["funding_log1p", "log_mapped_indexed_output"] + ["year_" + str(y) for y in model.years[1:]]
        coefficients.extend(dict(fit_id=item["fit_id"], term=term, coefficient=float(value))
                            for term, value in zip(terms, fit["beta_profile"]))
    results, inference_diagnostics, paired_diagnostics = [], [], []
    for owner in OWNERS:
        targets = []
        for degree in DEGREES:
            model, fit = fitted[owner, "main", degree]
            contrast = np.zeros(model.p)
            contrast[0] = SCALE
            targets.append(("RD" if degree == DEGREES[0] else "M", degree, model, fit, contrast))
        rd, frd = fitted[owner, "common", DEGREES[0]]
        ma, fma = fitted[owner, "common", DEGREES[1]]
        require([(r["institution_id"], r["completion_year"]) for r in rd.rows]
                == [(r["institution_id"], r["completion_year"]) for r in ma.rows], "Direct degree samples have different keys")
        joint = JointProfile([rd, ma], [frd, fma])
        contrast = np.zeros(joint.p)
        contrast[0], contrast[rd.p] = -SCALE, SCALE
        targets.append(("MminusRD", "Masters minus research doctorate", joint, joint.fit, contrast))
        for short, degree, model, fit, contrast in targets:
            point = float(contrast @ fit["beta_profile"])
            inference = linearized_primary(fit, model.labels, contrast)
            numbers = wald(point, inference["se_log"], inference["df"])
            result_id = "RQ3.T3." + ("FULL" if owner == "full" else "NOFP") + "." + short
            results.append(dict(result_id=result_id, ownership=owner, degree_target=degree,
                population="iterated_common_retained_unit_year_support" if short == "MminusRD" else "full_eligible_degree_specific",
                estimand="ratio_of_funding_rate_ratios" if short == "MminusRD" else "funding_rate_ratio",
                funding_contrast="1 to 4 annualized funded application IDs per fiscal year",
                log_rate_ratio=point, rate_ratio=math.exp(point), percent_change=100 * math.expm1(point), **numbers,
                cluster_count=inference["cluster_count"], cluster_field="institution_id",
                inference_method="profile_HC3_working_Poisson_Satterthwaite", family_size=3,
                significance_family3_05=numbers["bonferroni_family3_pvalue"] < .05,
                point_source="fresh_candidate_refit", primary_inference="approximate_conditional_institution_cluster",
                paired_degree_covariance=short == "MminusRD"))
            inference_diagnostics.append(dict(result_id=result_id,
                **{k: v for k, v in inference.items() if k != "influence"}, profile_nuisance_parameters=model.p))
            if short == "MminusRD":
                left = np.zeros(joint.p)
                right = np.zeros(joint.p)
                left[0], right[rd.p] = -SCALE, SCALE
                il = linearized_primary(fit, joint.labels, left)
                ir = linearized_primary(fit, joint.labels, right)
                covariance = (inference["cluster_count"] - 1) / inference["cluster_count"] * float(il["influence"] @ ir["influence"])
                variance = il["se_log"] ** 2 + ir["se_log"] ** 2 + 2 * covariance
                require(abs(variance - inference["se_log"] ** 2) < 1e-12, "Paired cluster covariance does not reconstruct variance")
                paired_diagnostics.append(dict(result_id=result_id, common_cells_per_degree=rd.n,
                    common_institutions=inference["cluster_count"], doctorate_common_funding_beta=float(frd["beta_profile"][0]),
                    masters_common_funding_beta=float(fma["beta_profile"][0]),
                    signed_doctorate_component_variance=il["se_log"] ** 2,
                    masters_component_variance=ir["se_log"] ** 2, signed_cross_degree_covariance=covariance,
                    paired_target_variance=variance, paired_target_variance_without_covariance=variance - 2 * covariance,
                    separate_degree_nuisances=True, common_keys_equal=True))
    write_csv(output_dir / "fresh_primary_results.csv", results)
    write_csv(output_dir / "fresh_fit_diagnostics.csv", diagnostics)
    write_csv(output_dir / "fresh_fit_coefficients.csv", coefficients)
    write_csv(output_dir / "fresh_inference_diagnostics.csv", inference_diagnostics)
    write_csv(output_dir / "fresh_paired_covariance_diagnostics.csv", paired_diagnostics)
    receipt = dict(status="passed", scope="eight_adopted_retained_fits_six_primary_institutional_count_targets",
        fresh_fit_count=len(fitted), primary_target_count=len(results), model_points_fitted_from_candidate=True,
        canonical_points_or_saved_fit_vectors_read=False, sample_selection_reestimated=False,
        private_inputs_or_original_code_imported=False, bootstrap_or_exact_deletion_companions_reproduced=False,
        output_adjustment="estimated_logD_coefficient_not_offset", common_degree_covariance=True,
        contrast_log_scale=SCALE, family_size_per_ownership=3, method_sources=METHOD_SOURCES,
        runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        input_sha256={"data/institutional_count_analysis_panel.csv": digest(panel_path),
                      "metadata/fit_registry.csv": digest(registry_path)},
        code_sha256=digest(Path(__file__)),
        outputs={p.name: digest(p) for p in sorted(output_dir.glob("fresh_*.csv"))})
    (output_dir / "fresh_reproduction_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True, help="Destination for newly calculated results and diagnostics")
    args = parser.parse_args()
    receipt = reproduce(args.bundle.resolve(), args.output_dir.resolve())
    print(json.dumps({k: receipt[k] for k in ("status", "fresh_fit_count", "primary_target_count", "runtime")}, indent=2))


if __name__ == "__main__":
    main()
