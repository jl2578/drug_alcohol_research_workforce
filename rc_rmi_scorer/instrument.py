"""Resolve the declared components into the effective inputs the combination lookup reads.

The instrument publishes one set of reviewer records under two specifications. This module turns
those immutable records into effective inputs, applying the declared operations in the order plan
5.1 states and recording every step, so any difference between the two specifications traces to a
declared cause rather than to an edit.

Plan 5.1 declares five operations. Two are common to both specifications and resolve first: the
mathematics erratum for one occupation, and the four withdrawn teaching overrides. Three differ
between specifications and resolve after, in the order the plan's table lists them: the industry
dissent rule, establishment heterogeneity, and the nursing faculty research base. Only the
nursing base differs between specifications at the occupation level; no family-wide harmonization
is applied.

Nothing here reads a specification name to decide what to do. Which reviewer value a
specification selects, which specifications an operation applies to, and what value an override
assigns are all read from `specifications.json`, so changing a declared judgment is a
configuration change rather than a code change. An undeclared selection rule is an error, never
something to infer.

The clinical axis is handled here too, from the corroboration gate onward: positive establishment
context may raise a clinical score only where the occupation's own evidence carries affirmative
care, and an occupation recorded as having no identified care function is held to a ceiling that
fails the build rather than being silently capped. No occupation is named in this module. The
one occupation whose base and directness were settled by a release-blocking rereview carries
that decision, and its provenance, in its reviewed record; the code applies the same rule to it
as to every other row.
"""
import copy
import csv
import itertools
import json
import os


class SpecificationError(Exception):
    """The specification declaration is missing or contradicts itself."""


# How a specification may choose between two unequal ordinal reviewer values. The declaration
# names one of these per specification; adding a rule is a scientific decision, so an unknown
# name fails rather than falling back.
SELECTORS = {
    'min_by_ordinal_rank': lambda values, rank: min(values, key=lambda v: rank[v]),
    'max_by_ordinal_rank': lambda values, rank: max(values, key=lambda v: rank[v]),
}


def load_specifications(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def read_rows(path):
    with open(path, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def specification_ids(spec):
    return [s['id'] for s in spec['specifications']]


def _selector(name):
    try:
        return SELECTORS[name]
    except KeyError:
        raise SpecificationError(
            'unknown selection rule %r. The declaration may choose among %s; a new rule is a '
            'scientific decision and must be added deliberately, not inferred.'
            % (name, ', '.join(sorted(SELECTORS))))


def _components(spec):
    by_id = {}
    for component in spec['components']:
        if component['id'] in by_id:
            raise SpecificationError('component %r declared twice' % (component['id'],))
        by_id[component['id']] = component
    return by_id


def _override_value(override, specification, component_id):
    """The value an override assigns under one specification, read from the declaration."""
    key = '%s_value' % specification
    if key in override:
        return override[key]
    if 'assigned_value' in override:
        return override['assigned_value']
    raise SpecificationError(
        'component %r declares no value for specification %r. Expected %r or a common '
        'assigned_value.' % (component_id, specification, key))


class Step(dict):
    """One ordered resolution step, retained so a resolved value stays traceable."""

    def __init__(self, specification, unit_type, unit_code, axis, order, operation,
                 value_in, value_out, rule):
        super().__init__(
            specification=specification, unit_type=unit_type, unit_code=unit_code, axis=axis,
            step_order=order, operation_id=operation, value_in=value_in, value_out=value_out,
            changed='yes' if value_in != value_out else 'no', rule=rule)


def derive_industry_dissent(industry_rows, component):
    """The disputed industry research contexts, derived from the reviewer record itself.

    The set is derived, never enumerated: a record qualifies when both reviewers supplied ordinal
    values and those values differ. A comparison involving an information status such as RU is not
    a dissent in degree and is excluded. Each qualifying record carries the value every declared
    specification selects, so the caller never infers a selection from a specification's name.
    """
    d = component['derivation']
    ordinal = set(d['ordinal_values'])
    rank = d['ordinal_rank']
    excluded = set(d['excluded_values'])
    a_field, b_field = d['compare_fields']
    selection = d['selection']

    out = {}
    for row in industry_rows:
        a, b = row[a_field], row[b_field]
        if a in excluded or b in excluded:
            continue
        if a not in ordinal or b not in ordinal or a == b:
            continue
        values = (a, b)
        out[row[d['key_field']]] = {
            'reviewer_values': values,
            'by_specification': {name: _selector(rule)(values, rank)
                                 for name, rule in selection.items()},
            'selection_rules': dict(selection),
        }
    return out


def resolve_industry(industry_rows, spec, specification):
    """Effective industry research context under one specification, with its ordered steps."""
    components = _components(spec)
    dissent_component = components['industry_dissent_rule']
    dissent = derive_industry_dissent(industry_rows, dissent_component)

    heterogeneity = components['establishment_heterogeneity']
    het_applies = specification in heterogeneity['applies_to']
    het_codes = {c['naics_code_canonical'] for c in heterogeneity['override']['codes']}
    het_value = _override_value(heterogeneity['override'], specification,
                                'establishment_heterogeneity')

    resolved, steps = [], []
    for row in industry_rows:
        code = row['naics_code_canonical']
        recorded = row['research_final']
        effective = recorded
        path = []
        order = 0

        if specification in dissent_component['applies_to'] and code in dissent:
            entry = dissent[code]
            chosen = entry['by_specification'][specification]
            order += 1
            steps.append(Step(specification, 'industry', code, 'research_context', order,
                              'industry_dissent_rule', effective, chosen,
                              'select the reviewer value by %s'
                              % entry['selection_rules'][specification]))
            effective = chosen
            path.append('industry_dissent_rule')

        if het_applies and code in het_codes:
            order += 1
            steps.append(Step(specification, 'industry', code, 'research_context', order,
                              'establishment_heterogeneity', effective, het_value,
                              'assign %s for a heterogeneous category' % het_value))
            effective = het_value
            path.append('establishment_heterogeneity')

        resolved.append({
            'specification': specification,
            'naics_code_canonical': code,
            'official_naics_title': row['official_naics_title'],
            'research_context_recorded': recorded,
            'research_context_effective': effective,
            'clinical_context_recorded': row['clinical_final'],
            'component_path': ';'.join(path),
            'component_count': str(len(path)),
        })
    return resolved, steps


def occupation_operations(spec, specification):
    """The occupation-base operations to apply, in plan 5.1 order.

    The two common operations come first and behave identically under both specifications; the
    nursing base follows and is the only occupation base that differs between them. Returned as an
    ordered list so a resolution path records each operation separately rather than collapsing
    them into one family-wide override.
    """
    common = spec['common_to_both_specifications']
    operations = []
    for key in ('mathematics_faculty_erratum', 'withdrawn_teaching_overrides'):
        block = common[key]
        if specification not in block['applies_to']:
            raise SpecificationError(
                '%r is declared common to both specifications but does not apply to %r'
                % (key, specification))
        operations.append((
            key,
            {c['soc_code_canonical'] for c in block['codes']},
            _override_value(block, specification, key),
            'apply %s, common to both specifications' % key,
        ))

    nursing = _components(spec)['nursing_faculty_research_base']
    if specification in nursing['applies_to']:
        operations.append((
            'nursing_faculty_research_base',
            {c['soc_code_canonical'] for c in nursing['override']['codes']},
            _override_value(nursing['override'], specification,
                            'nursing_faculty_research_base'),
            'apply the nursing faculty research base declared for this specification',
        ))
    return operations


def resolve_occupation(occupation_rows, spec, specification):
    """Effective occupation research base under one specification, with its ordered steps."""
    operations = occupation_operations(spec, specification)

    resolved, steps = [], []
    for row in occupation_rows:
        code = row['soc_code_canonical']
        recorded = row['research_final']
        effective = recorded
        path = []
        order = 0

        for operation_id, codes, value, rule in operations:
            if code not in codes:
                continue
            order += 1
            steps.append(Step(specification, 'occupation', code, 'research_base', order,
                              operation_id, effective, value, rule))
            effective = value
            path.append(operation_id)

        resolved.append({
            'specification': specification,
            'soc_code_canonical': code,
            'official_soc_title': row['official_soc_title'],
            'research_base_recorded': recorded,
            'research_base_effective': effective,
            'clinical_base_recorded': row['clinical_final'],
            'directness_recorded': row['directness_final'],
            'component_path': ';'.join(path),
            'component_count': str(len(path)),
        })
    return resolved, steps


def declared_operations(spec):
    """Every operation id the declaration permits in a resolution path.

    A path may cite a differing component or a common operation and nothing else. Used by the
    contract checks so an undeclared id fails rather than passing unnoticed.
    """
    return ({c['id'] for c in spec['components']}
            | {k for k in spec['common_to_both_specifications'] if k != 'note'})


def check_declaration(spec):
    """Confirm the declaration matches what plan 5.1 states, before anything is resolved.

    Returns the counts it verified so a caller can record them. Raises on the first
    contradiction: a declaration that disagrees with the plan is a scientific problem, not
    something to resolve around.
    """
    expected = spec['expected_counts']
    found = {}

    ids = specification_ids(spec)
    if len(ids) != expected['specifications']:
        raise SpecificationError('declares %d specifications, expected %d'
                                 % (len(ids), expected['specifications']))
    found['specifications'] = len(ids)

    components = _components(spec)
    if len(components) != expected['specification_dependent_components']:
        raise SpecificationError('declares %d differing components, expected %d'
                                 % (len(components), expected['specification_dependent_components']))
    found['specification_dependent_components'] = len(components)

    orders = sorted(c['order'] for c in spec['components'])
    if orders != list(range(1, len(orders) + 1)):
        raise SpecificationError('component orders are %r, expected a 1..n sequence' % (orders,))

    for component_id, count_key in (
            ('establishment_heterogeneity', 'establishment_heterogeneity_codes'),
            ('nursing_faculty_research_base', 'nursing_faculty_research_base_codes')):
        codes = components[component_id]['override']['codes']
        if len(codes) != expected[count_key]:
            raise SpecificationError('%s declares %d codes, expected %d'
                                     % (component_id, len(codes), expected[count_key]))
        found[count_key] = len(codes)

    for key, count_key in (('mathematics_faculty_erratum', 'mathematics_erratum_codes'),
                           ('withdrawn_teaching_overrides', 'withdrawn_teaching_override_codes')):
        codes = spec['common_to_both_specifications'][key]['codes']
        if len(codes) != expected[count_key]:
            raise SpecificationError('%s declares %d codes, expected %d'
                                     % (key, len(codes), expected[count_key]))
        found[count_key] = len(codes)

    for name, rule in components['industry_dissent_rule']['derivation']['selection'].items():
        if name not in ids:
            raise SpecificationError('selection names undeclared specification %r' % (name,))
        _selector(rule)
    if set(components['industry_dissent_rule']['derivation']['selection']) != set(ids):
        raise SpecificationError('every declared specification needs a selection rule')

    return found


def differing_occupation_bases(occupation_rows, spec):
    """Occupation codes whose effective research base differs between the specifications.

    Plan 5.1 states that only the nursing faculty base differs. This recomputes that from the
    declaration rather than asserting it, so a declaration that quietly makes another base differ
    is visible instead of silent.
    """
    ids = specification_ids(spec)
    by_spec = {s: {r['soc_code_canonical']: r['research_base_effective']
                   for r in resolve_occupation(occupation_rows, spec, s)[0]} for s in ids}
    first = by_spec[ids[0]]
    return sorted(code for code in first
                  if len({by_spec[s][code] for s in ids}) > 1)


# ----------------------------------------------------------------------------- clinical axis

class ClinicalRecordError(Exception):
    """A reviewed clinical record violates a declared constraint."""


class RuleTableError(Exception):
    """The pinned rule table is missing, malformed, or does not cover a required key."""


# Plan 5.2. Directness values carrying affirmative care evidence may keep a declared positive
# context; the rest cannot corroborate one.
CORROBORATING_DIRECTNESS = frozenset({
    'direct_care',
    'indirect_patient_specific',
    'mixed_direct_indirect',
})
NON_CORROBORATING_DIRECTNESS = frozenset({
    'no_clinical_care_function_identified',
    'unknown',
})
DIRECTNESS_VALUES = CORROBORATING_DIRECTNESS | NON_CORROBORATING_DIRECTNESS

# Only a declared positive context can be transformed by the gate; C0, C1 and CU pass through.
GATEABLE_CONTEXTS = frozenset({'C2', 'C3'})
GATE_FALLBACK = 'C1'

# The directness value that also constrains the occupation base and the final pair score.
NO_CARE = 'no_clinical_care_function_identified'
NO_CARE_MAX_BASE = 1
NO_CARE_MAX_FINAL = 1

UNCLASSIFIABLE = 'U'
LIKELY_THRESHOLD = 3
CURRENT_MATRIX_VERSION = 'combination_matrix_v3.0'

JOINT_BOTH = 'both'
JOINT_RESEARCH_ONLY = 'research_likely_only'
JOINT_CLINICAL_ONLY = 'clinical_likely_only'
JOINT_NEITHER = 'neither'
JOINT_UNCLASSIFIABLE = 'unclassifiable'


def apply_corroboration_gate(declared_context, directness):
    """Return (effective_context, gate_applied) for one pair.

    Only a declared C2 or C3 can be transformed, and only where the occupation's directness
    carries no affirmative care evidence. Every other combination passes through unchanged, so
    the gate can lower a context but never raise one.
    """
    if directness not in DIRECTNESS_VALUES:
        raise ClinicalRecordError('unrecognised clinical directness %r' % (directness,))
    if declared_context in GATEABLE_CONTEXTS and directness in NON_CORROBORATING_DIRECTNESS:
        return GATE_FALLBACK, 'yes'
    return declared_context, 'no'


def gate_transition_table():
    """Every directness by context combination and what the gate does with it.

    Returned rather than written out, so the audit table and the tests read the same source the
    resolver does.
    """
    rows = []
    for directness in sorted(DIRECTNESS_VALUES):
        for context in ('C0', 'C1', 'C2', 'C3', 'CU'):
            effective, applied = apply_corroboration_gate(context, directness)
            rows.append({
                'clinical_directness': directness,
                'clinical_context_code_declared': context,
                'clinical_context_code_effective': effective,
                'clinical_corroboration_gate_applied': applied,
                'may_raise': 'yes' if directness in CORROBORATING_DIRECTNESS else 'no',
            })
    return rows


def assert_no_care_base_ceiling(occupation_rows):
    """An occupation with no identified care function must carry clinical base 0 or 1.

    A violation fails the build. It is a contradiction inside a reviewed record, not something to
    cap silently: capping would turn a recording error into a finding of absence. U is exempt,
    because an undecidable base is not a claim about level.
    """
    violations = []
    for row in occupation_rows:
        if row['directness_final'] != NO_CARE:
            continue
        base = row['clinical_final']
        if base == UNCLASSIFIABLE:
            continue
        if not base.isdigit() or int(base) > NO_CARE_MAX_BASE:
            violations.append('%s has clinical base %r with directness %s'
                              % (row['soc_code_canonical'], base, NO_CARE))
    if violations:
        raise ClinicalRecordError('; '.join(violations))
    return True


def assert_no_care_final_ceiling(pair_rows):
    """No pair whose occupation has no identified care function may score above 1 clinically."""
    violations = []
    for row in pair_rows:
        if row.get('clinical_directness') != NO_CARE:
            continue
        final = str(row.get('clinical_final_score', ''))
        if final == UNCLASSIFIABLE:
            continue
        if not final.isdigit() or int(final) > NO_CARE_MAX_FINAL:
            violations.append('%s x %s has clinical final %r with directness %s'
                              % (row.get('soc_code_canonical'), row.get('naics_code_canonical'),
                                 final, NO_CARE))
    if violations:
        raise ClinicalRecordError('; '.join(violations))
    return True


# --------------------------------------------------------------------------- pinned lookup

def load_rule_table(path, expected_version=None):
    """Load and validate a rule table. Returns a lookup keyed by (axis, base, context).

    The version is checked against `expected_version`, which defaults to the current matrix. A
    historical table is a sensitivity input: loading one requires naming its version at the call
    site, so a sensitivity says in its own code which matrix it is contrasting against and the
    engine can never pick up an old table by accident.
    """
    rows = read_rows(path)
    if not rows:
        raise RuleTableError('%s is empty' % path)
    versions = {row['matrix_version'] for row in rows}
    if len(versions) != 1:
        raise RuleTableError('the table mixes rule versions: %s' % sorted(versions))
    version = next(iter(versions))
    wanted = expected_version or CURRENT_MATRIX_VERSION
    if version != wanted:
        raise RuleTableError(
            'this call requires %s, not %s. A historical matrix is a sensitivity input and is '
            'never loaded as the current engine.' % (wanted, version))
    table = {}
    for row in rows:
        key = (row['axis'], row['soc_input_score'], row['naics_context_code'])
        if key in table:
            raise RuleTableError('duplicate rule for %r' % (key,))
        table[key] = row
    return table


def score(table, axis, base, context):
    """Look up one axis score. No inference, no arithmetic, no fallback."""
    try:
        rule = table[(axis, base, context)]
    except KeyError:
        raise RuleTableError(
            'no rule for axis %r, base %r, context %r. The pinned table is the only source of a '
            'score; a missing key is a table error, not something to derive.'
            % (axis, base, context))
    return rule['output_score'], rule['rule_id']


def is_likely(final_score):
    """A likely role is a final score at or above the declared threshold. U is not a low score."""
    if final_score == UNCLASSIFIABLE:
        return False
    return int(final_score) >= LIKELY_THRESHOLD


def joint_class(research_final, clinical_final):
    if research_final == UNCLASSIFIABLE or clinical_final == UNCLASSIFIABLE:
        return JOINT_UNCLASSIFIABLE
    research, clinical = is_likely(research_final), is_likely(clinical_final)
    if research and clinical:
        return JOINT_BOTH
    if research:
        return JOINT_RESEARCH_ONLY
    if clinical:
        return JOINT_CLINICAL_ONLY
    return JOINT_NEITHER


def resolve_pair(table, occupation, industry, specification, instrument_version):
    """Score one occupation-industry pair and retain the complete path behind each axis.

    Plan 5.1's order, from resolved inputs: the clinical gate, then the pinned lookup. The
    resolved rows this consumes have already had the common erratum and the differing components
    applied, so the component path they carry is prefixed onto the pair's path here.
    """
    research_context = industry['research_context_effective']
    research_final, research_rule = score(table, 'research',
                                          occupation['research_base_effective'], research_context)

    directness = occupation['directness_recorded']
    declared = industry['clinical_context_recorded']
    effective, gate_applied = apply_corroboration_gate(declared, directness)
    clinical_final, clinical_rule = score(table, 'clinical',
                                          occupation['clinical_base_recorded'], effective)

    clinical_path = ['clinical_corroboration_gate'] if gate_applied == 'yes' else []
    research_path = [p for p in (occupation['component_path'], industry['component_path']) if p]

    return {
        'instrument_version': instrument_version,
        'combination_rule_version': CURRENT_MATRIX_VERSION,
        'specification': specification,
        'pair_id': '%s|%s' % (occupation['soc_code_canonical'],
                              industry['naics_code_canonical']),
        'soc_code_canonical': occupation['soc_code_canonical'],
        'official_soc_title': occupation['official_soc_title'],
        'naics_code_canonical': industry['naics_code_canonical'],
        'official_naics_title': industry['official_naics_title'],
        'research_base_recorded': occupation['research_base_recorded'],
        'research_base_effective': occupation['research_base_effective'],
        'research_context_recorded': industry['research_context_recorded'],
        'research_context_effective': research_context,
        'research_final_score': research_final,
        'research_rule_id': research_rule,
        'research_component_path': ';'.join(research_path),
        'clinical_directness': directness,
        'clinical_base_recorded': occupation['clinical_base_recorded'],
        'clinical_context_recorded': declared,
        'clinical_context_code_declared': declared,
        'clinical_context_code_effective': effective,
        'clinical_corroboration_gate_applied': gate_applied,
        'clinical_final_score': clinical_final,
        'clinical_rule_id': clinical_rule,
        'clinical_component_path': ';'.join(clinical_path),
        'research_likely': 'yes' if is_likely(research_final) else 'no',
        'clinical_likely': 'yes' if is_likely(clinical_final) else 'no',
        'joint_class': joint_class(research_final, clinical_final),
    }


# ===========================================================================
# Whole-domain generation
#
# Plan 7.2 puts the full instruments, the diff, the census and the counterfactuals in this
# module, behind one entry point. Everything below writes to the external work directory and
# never to the release tree; plan 7.3 owns that boundary and `code/sources.py` enforces it.
# ===========================================================================

PAIRS_PER_SPECIFICATION = 20604
SPECIFICATION_IDS = ('conservative', 'inclusive')

# The pair fields the specification diff compares. The full row also carries the specification
# name and its resolution path, which differ by construction; comparing whole rows would mark
# every pair changed and say nothing.
COMPARED_FIELDS = ('research_final_score', 'clinical_final_score')

# What each generated instrument column means, for the dictionary that ships beside the two
# instrument files. Every column is declared here; a column without an entry fails the build
# rather than shipping as an unlabelled field.
FIELD_DEFINITIONS = {
    'instrument_version': ('identifier', 'Instrument version these rows were generated under.'),
    'combination_rule_version': ('identifier', 'Pinned combination matrix version supplying every score.'),
    'specification': ('enumeration', 'Scoring specification: conservative or inclusive. The two differ only in the three declared components.'),
    'pair_id': ('identifier', 'Occupation-industry key, "<SOC>|<NAICS>". Unique within a specification.'),
    'soc_code_canonical': ('identifier', 'Canonical O*NET-SOC occupation code.'),
    'official_soc_title': ('string', 'Official occupation title as published.'),
    'naics_code_canonical': ('identifier', 'Canonical NAICS industry code.'),
    'official_naics_title': ('string', 'Official industry title as published.'),
    'research_base_recorded': ('ordinal 0-4 or U', 'Reviewed occupation research base, exactly as recorded. Never overwritten.'),
    'research_base_effective': ('ordinal 0-4 or U', 'Occupation research base after the declared operations; equals the recorded value where none applied.'),
    'research_context_recorded': ('ordinal R0-R3 or RU', 'Reviewed industry research context, exactly as recorded.'),
    'research_context_effective': ('ordinal R0-R3 or RU', 'Industry research context after the declared components resolved.'),
    'research_final_score': ('ordinal 0-4 or U', 'Research role score from the pinned matrix. U is unclassifiable, not a low score.'),
    'research_rule_id': ('identifier', 'Matrix rule that produced the research score.'),
    'research_component_path': ('semicolon list', 'Ordered declared operations behind the effective research inputs; empty where none applied.'),
    'clinical_directness': ('enumeration', 'Reviewed directness of the occupation to clinical care, including the no-care and unknown states.'),
    'clinical_base_recorded': ('ordinal 0-4 or U', 'Reviewed occupation clinical base, exactly as recorded.'),
    'clinical_context_recorded': ('ordinal C0-C3 or CU', 'Reviewed industry clinical context, exactly as recorded.'),
    'clinical_context_code_declared': ('ordinal C0-C3 or CU', 'Clinical context as declared by the industry record, before the corroboration gate.'),
    'clinical_context_code_effective': ('ordinal C0-C3 or CU', 'Clinical context the matrix actually read, after the corroboration gate.'),
    'clinical_corroboration_gate_applied': ('flag yes/no', 'Whether the gate lowered a declared C2 or C3 for want of affirmative occupation care evidence.'),
    'clinical_final_score': ('ordinal 0-4 or U', 'Clinical role score from the pinned matrix. Common to both specifications.'),
    'clinical_rule_id': ('identifier', 'Matrix rule that produced the clinical score.'),
    'clinical_component_path': ('semicolon list', 'Ordered operations behind the effective clinical inputs; empty where none applied.'),
    'research_likely': ('flag yes/no', 'Research score at or above the likely threshold of 3.'),
    'clinical_likely': ('flag yes/no', 'Clinical score at or above the likely threshold of 3.'),
    'joint_class': ('enumeration', 'both, research_likely_only, clinical_likely_only, neither, or unclassifiable.'),
}


class GenerationError(RuntimeError):
    """Whole-domain generation produced something the plan's structure does not allow."""


def field_dictionary(sample_row):
    """Dictionary rows for the generated instrument columns, declared rather than inferred."""
    undeclared = [name for name in sample_row if name not in FIELD_DEFINITIONS]
    if undeclared:
        raise GenerationError(
            'generated columns carry no dictionary entry: %s. A shipped column is described in '
            'FIELD_DEFINITIONS or it does not ship.' % ', '.join(undeclared))
    return [{'field': name,
             'type': FIELD_DEFINITIONS[name][0],
             'description': FIELD_DEFINITIONS[name][1]}
            for name in sample_row]


def write_rows(path, rows):
    """Write one CSV, taking the field order from the first row."""
    directory = os.path.dirname(str(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(str(path), 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def score_domain(occupations, industries, spec, specification, table):
    """Score every occupation-industry pair under one specification, with its resolution steps."""
    resolved_occupations, occupation_steps = resolve_occupation(occupations, spec, specification)
    resolved_industries, industry_steps = resolve_industry(industries, spec, specification)
    rows = [resolve_pair(table, occupation, industry, specification, spec['instrument_version'])
            for occupation in resolved_occupations for industry in resolved_industries]
    if len(rows) != PAIRS_PER_SPECIFICATION:
        raise GenerationError(
            'expected %d pairs under %r, generated %d. The domain is 303 occupations by 68 '
            'industries; a different count is a domain error, not something to trim.'
            % (PAIRS_PER_SPECIFICATION, specification, len(rows)))
    if len({row['pair_id'] for row in rows}) != PAIRS_PER_SPECIFICATION:
        raise GenerationError('pair keys are not unique under %r' % specification)
    assert_no_care_final_ceiling(rows)
    return rows, occupation_steps, industry_steps


