# Dissertation codebook v5 revision 15

This codebook defines the study population, scope inputs, substance fields and research-content variables. Inclusion is computed at the research-aim level and then aggregated to the dissertation or thesis. Scientific coding uses the title and abstract only. Every scope field is assessed in one scope pass, followed by content coding for the fixed qualifying targets.

# Part A — Procedure

## A1. Role

Use one scope coding pass per assessable record to identify all research units and assess their six S1–S4 fields plus record-level focus (S5). The same pass assesses substance-related and endogenous-system research. The runner checks the raw response schema and enums, applies the deterministic dependencies in A4a, validates the completed fields and sentence references, and derives inclusion and ordered targets under Part C. An applicable field coded `cannot_determine` is a completed assessment.

Content coding returns C1–C9 for the fixed in-scope targets. All scope fields S1–S5, unit identities, sentence references, inclusion and target membership are immutable inputs to content; they are not returned or revised by that request. Deterministic validation, normalization and derivation use the one scope response and do not constitute another coding pass. Operational retries repair delivery or validation of that same stage. Do not alter factual codes to obtain an inclusion outcome.

## A2. Evidence rule

- Code only from the title and abstract of that record.
- Do not use outside knowledge of the author, institution, degree, department, journal or discipline.
- Do not infer a design, data type, provenance or purpose that the abstract does not state. Absence of evidence is `cannot_determine`, not a best guess.
- A short abstract is still an abstract: no word-count threshold. Attempt each applicable variable; retain supported codes and use `cannot_determine` only for unsupported cells. Missing, whitespace-only or recognized placeholder abstracts follow A5 even when a title exists.
- **Aims rule.** Where a variable refers to the aims, use the stated aims, objectives, research questions or hypotheses. Where none are stated explicitly, use the abstract's description of what the dissertation does. Background and motivation sentences are not aims.
- **Scope reads every aim in the same pass.** One in-scope unit is enough. Assess the endogenous-system role alongside all other S1 roles and assess applicable S4 fields from the same evidence. A coded endogenous-system role independently establishes inclusion. Other units must connect their study-defined substance topic and in-scope purpose within the same unit; unrelated aims cannot supply separate halves of that test.
- **Identify the research target before assigning scope roles or purposes.** From the stated question or description of what the work does, identify what is compared, predicted, explained, changed, developed or evaluated. A substance-related sample, service setting, disease history, medication, dose measure or item in a broad endpoint list does not by itself make that substance the research target. A substantive substance role and qualifying S2 purpose require a connected substance-related question, co-primary analysis target, or result that answers a distinct substance-related aim. Endogenous-system research independently qualifies through its S1 role and does not require that substance-related connection. This does not require substance use/SUD to be the dissertation's primary focus: one supported qualifying aim is enough. If the abstract leaves the link unresolved, retain `cannot_determine` rather than inferring a qualifying or excluding purpose.

## A2a. Scope units and completeness

Start with one scope unit for the described research, with ID `a1`. Split into `a2`, `a3`, etc. only when distinct described parts would derive different unit-level eligibility under Part C: qualifying versus out of scope, qualifying versus undetermined, or out of scope versus undetermined. Do not split merely because the abstract lists multiple questions, chapters, methods, samples, endpoints, substances or studies. Parts that all qualify, or all fail in the same way, ordinarily remain one unit. Keep jointly studied drug combinations together when the same eligibility applies. Background sentences are not research parts.

**Preserve derivation and substance labels.** Do not combine parts if their field sets would falsely create a qualifying topic–purpose link across otherwise nonqualifying parts, or if a combined `substance_all` would violate S4 co-occurrence or erase a specific qualifying substance/domain label. Retain the minimum separate units needed for valid fields and correct derived outcomes, even when those parts all qualify. This is a structural safeguard, not permission to split merely for finer thematic description. The focal qualifying work in a combined unit is all qualifying research described by its supporting sentences; C1 still compares it with any separately represented nonqualifying research. C2–C9 describe that combined qualifying work, using `multiple_no_dominant` only where the variable permits it and the text supports no dominant contribution.

If aims are not explicitly numbered, use the abstract's description of what the work does. If even that is insufficient, retain one uncertain unit rather than an empty array. Represent nonqualifying and undetermined research separately when needed to preserve their status, so absence of a qualifying unit has an evidential basis. The runner first numbers title/abstract sentences with stable source IDs. Each unit returns nonempty `source_sentence_ids` locating its research and supporting methods/results; IDs may overlap for shared methods. These are structural routing metadata, not rationale, quotations or rewritten aim text. The runner validates referenced IDs and stores the sentence-index version. Unlocatable units or routing that loses essential methods require repair before content calls.

## A3. Content target — supplied by the runner

The runner supplies `target_aim_ids` containing every unit derived in scope from the single validated scope response, in the order those units appear in `scope_units`, with their stable sentence references. The content request codes those targets; it never executes Part C, selects study-defined units, fills S4 or edits the scope response.

Provide the original title and abstract as context, mark target spans/IDs, and designate only qualifying scope-unit objects as targets. Full context preserves shared methods and permits C1's assessment of the relative prominence of qualifying and nonqualifying work; it avoids an unvalidated extract changing the evidence base. Excluded/uncertain work is context only and cannot determine C2–C9. Other-unit outcomes may be supplied for C1's consistency check, not for eligibility reconsideration.

- No qualifying units → no production content request. Undetermined records await scope review (A6).
- A qualifying unit plus unresolved units → code only the qualifying target, retaining unresolved-unit flags. Any reviewed change in target membership invalidates and reruns content.
- Several qualifying aims: choose a dominant contribution only when supported; otherwise use `multiple_no_dominant` where allowed, combine multi-select forms within their limits, or use `cannot_determine` for unrepresentable ties.
- Dependent fields for tied objectives/types: all applicable → attempt field; all inapplicable → `not_applicable`; mixed/uncertain applicability → `cannot_determine`.
- Pain-treatment research solely for an unrelated indication plus an alcohol-withdrawal aim → C2–C9 from withdrawal research; C1 compares its stated contribution with the nonqualifying work. Pain research explicitly about drug/alcohol use, exposure, withdrawal or related harm may itself qualify and belongs in the target.
- Credential and field remain whole-dissertation metadata.

## A4. Status and confidence

**`coding_status`**

| Status | When |
|---|---|
| `coded` | The construct applies and the evidence supports a value |
| `cannot_determine` | Applicability or value cannot be established from the abstract, including an uncertain parent field |
| `not_applicable` | The construct does not apply to this record; allowed only where the variable says so |

**`confidence`** (coded values only): `high` (the abstract states what is needed; another competent coder would agree) · `medium` (reasonably supported, partial or near a boundary) · `low` (thin evidence, or a different reader could plausibly land elsewhere). Apply the named edge rules where they fit, but do not output a separate path label. A low-confidence value still requires support from the title/abstract; if no allowed value is supported, use `cannot_determine` and leave value and confidence null.

**Applicability precedence:** missing abstract (A5) → content gate (A6, content only) → variable-specific conditions → evidence sufficiency. An uncertain parent propagates `cannot_determine` to its dependent fields; it never establishes `not_applicable`. A known applicable parent does not force a coded child when evidence is insufficient. A defensible coded value requires evidence; low confidence cannot substitute for a missing category or evidence. A clear multiple/no-dominant rule may have high confidence.

For multi-select fields, include each value only when the unit's stated aim or description independently supports that value. One sentence may support several values, but do not add a plausible companion role or purpose solely because it often accompanies a selected one. Keep codebook vocabularies distinct: `explain_causes` is a C5 research-objective value, not an S2 stated-purpose value. For an etiologic aim with substance use as the outcome, assess S2 `use_or_misuse` and C5 `explain_causes` separately.

**Output only `value`, `coding_status` and `confidence` for each coded field.** Retain explicit `cannot_determine`; do not output rationale or quoted evidence.


## A4a. Rule-filled fields shared by model and human coding

Coders decide the parent fields and all genuinely applicable values. The same versioned processor fills the following consequences **after** receiving either model JSON or linked human CSV. The model's strict schema still contains every field; return a `not_applicable`/null placeholder for a field whose final value is supplied here. In the human CSV, leave rule-filled cells blank; the processor fills them after import. Keep the raw submission, final fields and per-field rule log. A rule-filled conflict is a diagnostic about a possible mistaken parent or omitted scope unit, not evidence that the parent was correct.

1. **S1 dependency.** When coded S1 has none of the six substantive substance roles, set S2 and S3 to `not_applicable` with null value/confidence. Endogenous-system research alone does not make S2 or S3 applicable. S4 applies when S1 has a substantive substance role or `endogenous_system_only`; retain supported labels and use `cannot_determine` when no class is supported. Do not erase S4 because an endogenous unit lacks a substantive substance role. If neither is present, focal behavioral-addiction-only S4 is coded `[behavioral_addiction]`, with that sole primary label and `not_applicable` assignment basis. Otherwise S4 is `not_applicable`. When S1 is uncertain, dependent fields are `cannot_determine`. A substantive substance role leaves S2, S3 and `substance_all` to judgment.
2. **S4 label consequences.** If coded `substance_all` has exactly one label, set `substance_primary` to it and carry the label-set confidence. With two or more labels, the coder judges dominance. Any of `general_SUD_unspecified`, `general_drug_unspecified` or `substance_unidentified` in coded `substance_all` sets `substance_assignment_basis` to `general_substance_construct`, with the label-set confidence. A sole behavioral-addiction label has `substance_assignment_basis: not_applicable`. Otherwise the coder judges named-focal versus target-system basis. When `substance_all` is `cannot_determine`, primary and assignment basis are also `cannot_determine`, with null value/confidence. For applicable endogenous S4, a raw `not_applicable` label-set placeholder is normalized to `cannot_determine`; no label is invented. Co-occurrence restrictions still apply to `substance_all` itself. These consequences are completed during scope processing.
3. **Status/null hygiene.** A noncoded field must have null value and confidence. The processor may null a repeated status sentinel or a stray confidence when value is already null. A noncoded status carrying a real category remains a conflict requiring correction **unless** another explicit A4a parent rule determines that whole child field; in that case preserve the raw category in the rule log.
4. **Content applicability.** All known scope units qualifying, with none unresolved, sets C1 `only_qualifying_described`; a conflicting raw C1 creates a scope-unit-completeness review flag. Known C2 `evidence_synthesis` or `conceptual_theoretical` sets C3 `not_applicable`; uncertain C2 sets C3 `cannot_determine`. A `practice_product` needs a separate judgment about whether it was evaluated; C2 alone does not settle C3. Known single C5 objectives outside C6's applicable set set C6 `not_applicable`; known single C5 objectives outside C7's applicable set set C7 `not_applicable`. If C5 is `cannot_determine`, both dependent fields are `cannot_determine`. A `multiple_no_dominant` C5 requires assessment of the tied objectives under A3; it is not automatically inapplicable. Applicable C3, C6 and C7 values remain coder judgments.
5. **Data pairing.** C9 `no_empirical_data` sets C8 `not_applicable`. A raw C8 `not_applicable` with a different coded C9 remains a conflict rather than silently changing C9. Evidence synthesis analyzes documents and is not `no_empirical_data`.

Rule filling never changes S1, a multi-label `substance_all`, a C2/C5 parent, source sentence IDs or the scope-unit split. Validate the completed response and retain unresolved conflicts. Every required field must be present before deriving scope; a malformed response is an operational/validation failure, not an admitted or uncertain scientific record. Report rule-use and conflict counts by stage; do not present structural success as an accuracy estimate. Human reference judgments remain independent of model scope outcomes.

## A5. Output contract

**Scope request:** `record_id`, nonempty `scope_units`, and `add_su_focus`. Each unit contains `aim_id`, `source_sentence_ids` and all six coded fields: `substance_roles`, `stated_purposes`, `unrelated_therapeutic_indication_tested`, `substance_all`, `substance_primary`, `substance_assignment_basis`. This one response includes the S4 assessment of every endogenous-system unit, including supported uncertainty. Missing a required field is invalid; returning valid `cannot_determine` is complete. Aim IDs are unique and sentence IDs must resolve to the supplied evidence. No duplicate record-wide scope fields.

**Content request:** `record_id`, echoed `target_aim_ids`, and C1–C9 only. The runner verifies exact target-ID equality, including order, and rejects added scope or substance fields. All S1–S5 codes, aim/sentence IDs and inclusion are immutable scope inputs, not repeated output. Each coded field has `value`, `coding_status`, `confidence`; coded values are non-null, and non-coded cells have null value and confidence. Coded multi-selects are nonempty arrays without duplicates.

**Merged ledger:** runner-attached `record_status`, scope outcomes, target IDs, `content_run_status` and validated responses. Record separate hashes, model/settings, routing version, dependencies and checkpoints for both stages. Pending/failed calls retain null content and operational status `pending`/`failed`; successful content has status `completed`. Do not disguise operational failure as scientific `cannot_determine`.

**Missing-abstract exception:** no model call; retain GOID with `record_status: not_assessed`, `scope_status: not_assessed`, `scope_reason: abstract_absent`, `scope_units: null`, all ten record-level coded fields null, and `content_run_status: skipped_missing_abstract`. Title alone does not permit coding.

**Missingness normalization:** collapse whitespace, trim, case-fold and strip terminal full stops for exact comparison with a versioned placeholder allowlist initially containing “abstract not available”, “no abstract available”, “no abstract provided” and “abstract unavailable”. Empty normalized text is missing too. Never match substrings; real abstracts mentioning unavailable abstracts are not missing. Flag unknown boilerplate for input review. Preserve original text privately and record `abstract_input_status` as `present`, `blank` or `placeholder`, plus normalization/allowlist versions. Check blank and placeholder abstracts in the input roster and preserve their statuses in the input ledger.

No rationale, quoted evidence, rewritten aim text or model-derived eligibility is output. Sentence IDs do not authorize abstract export.

## A6. Runner-controlled content routing

After validated scope coding and deterministic Part C:
- In scope → request C1–C9 for exactly the qualifying units.
- Out of scope → no content call; C1–C9 are `not_applicable` with null value/confidence; `content_run_status: skipped_out_of_scope`.
- Undetermined → defer production content until review; fields remain null with `content_run_status: deferred_scope_review`, not `not_applicable` or field-level `cannot_determine`.
- Not assessed → A5 exception.

Runner-level states override content consistency rules when content has not completed. Scope inference must not depend on anticipated content workload. Once scope is validated, valid unknown S4 remains unknown throughout content. An authorized correction to scope is versioned. Changed qualifying-unit membership requires content invalidation and recoding; preserve prior versions and request dependencies.

Human reference coding is independent of model inclusion. Both authors code the reference records independently before adjudication and use the same consensus in-scope aims for reference content coding. Model-excluded records can remain in the human reference. Human and model coding use the same scientific definitions.

**Stage-specific texts.** The scope request contains the evidence and unit rules, all S1–S5 definitions and dependencies, endogenous-system inclusion, and scope hard rules from this codebook. Content instructions contain the evidence and fixed-target rules, C1–C9 and content hard rules; scope units are frozen context only. Each schema contains only its stated output fields.

---

# Part B — Specification

## B0. Population definition and source basis

This is a **study-defined drug-, alcohol- and endogenous-system research population informed by NIDA/NIAAA missions**, within the retrieved dissertation universe. It is not an enumeration of either institute's full funding remit, funded portfolio or exclusive jurisdiction.

**Study inclusion:** include at least one connected aim about study-defined drug/alcohol use, addiction, exposure, relevant substance pharmacology, related harms, or explicitly substance-related prevention, treatment, services, policy, social responses, education/workforce or methods. Also include any aim coded `endogenous_system_only`, even without a focal exogenous drug or an explicit substance-use, addiction or substance-related harm aim. This independent route takes precedence when other roles co-occur. Basic, clinical, epidemiological, translational and implementation research can qualify through that connected aim. Diagnosed SUD, drug administration and an addiction-focused primary outcome are not prerequisites. NIDA’s stewardship of a research workforce does not by itself bring every education or workforce dissertation into this study population; the dissertation’s own research question must explicitly concern substance-related research, prevention, care or harms.

Caffeine-only research, behavioral-addiction-only research, industrial/instrumental uses without an in-scope aim, and therapeutic applications solely for unrelated conditions are study exclusions unless the same unit independently meets the endogenous-system inclusion rule. A familiar receptor or any named medication is not sufficient evidence of a study-defined topic. No actual funding, institution or department information enters coding.

## Scope layer

S1–S4 apply separately to each A2a unit. S5 applies to the record. Assess these fields together for every unit in the one scope pass. Endogenous-system research qualifies through its coded S1 role. Other inclusion routes require the same unit to establish the study-defined substance topic and qualifying purpose. Preserve uncertainty when the evidence does not establish a role or a class; do not use an endogenous default to fill an uncertain S1.

### S1. `substance_roles` — multi-select

**Study meaning of substance:** alcohol and the drug classes in S4 (including tobacco/nicotine and caffeine for explicit downstream exclusion); named novel psychoactive substances such as kratom; investigational compounds acting at those classes' target systems; and substance use/addiction in general. Related harms, care and systems research can qualify through its target even when its intervention is not itself such a drug. Behavioral addictions are coded explicitly for exclusion/co-occurrence. This does not mean any chemical or medicine: ordinary antibiotic research with no study-defined substance-related target is outside this definition. Receptor identity establishes candidacy, not relevance.

**What it is.** The roles these study-defined substances/topics play **in the unit's aim**. Never `not_applicable`; `cannot_determine` only when the abstract gives too little to tell what the study is about.

| Value | Definition |
|---|---|
| `object_of_study` | A substance or compound itself is what is studied: its action, pharmacology, chemistry, properties, markets, regulation or availability |
| `use_as_outcome` | Substance use, misuse, addiction, SUD or an addiction phenomenon is what is predicted, explained or changed |
| `use_as_exposure` | Substance use or exposure (including prenatal exposure and intoxication) predicts or causes the outcomes studied |
| `treatment_target` | Prevention, diagnosis, treatment, recovery or harm reduction targets substance use/SUD or explicitly substance-related harms/conditions, including overdose and alcohol-related organ damage |
| `substance_related_systems_responses` | Services, policy, social responses (including stigma), or education/workforce/research infrastructure studied as an object explicitly serving substance-related research, prevention, care or harm reduction |
| `therapeutic_agent` | A substance is studied as a treatment for a condition (for example psilocybin for depression, ketamine as an anesthetic, cannabinoids for pain) |
| `context_only` | Substances appear only as background, motivation, a covariate, one correlate among many, a sample descriptor or a setting |
| `instrument_only` | A substance is used as a tool rather than a subject: a solvent, a reagent, an insecticide, a biofuel, an assay control |
| `endogenous_system_only` | Endogenous-system biology with neither a focal exogenous drug nor an explicit substance-use, addiction or substance-related harm aim |
| `behavioral_addiction` | A behavioral addiction (gambling, gaming, internet, sex) is focal |
| `none` | No study-defined substance/topic or behavioral addiction appears in this unit, including generic antibiotic research without such a target. **Exclusive** |

**Clear case.** Read the aims and ask what the substance is doing in them. One or more substantive roles (`object_of_study`, `use_as_outcome`, `use_as_exposure`, `treatment_target`, `therapeutic_agent`, `substance_related_systems_responses`) → list them. Otherwise record the non-substantive role.

**Edge rules**
- **E1. Aims decide.** A substance that appears only in the title or the background, with aims about something else → `context_only`, `confidence: low`.
- **E2. One correlate among many.** A substance that is one of several risk correlates, not named as a focus in the aims → `context_only`. Named as a co-primary outcome or exposure → the substantive role.
- **E2a. Outcome batteries and composite measures.** A substance-use item included in a broad outcome battery or composite is `context_only` when no stated question singles it out as a co-primary outcome or distinct analysis target. A stated substance-use hypothesis, co-primary outcome or separately described result that answers a distinct substance-use aim supports `use_as_outcome`. A result sentence that merely lists substance use among the endpoints of another question does not establish a distinct aim. When the abstract leaves its research role unresolved, use `cannot_determine` rather than presuming either role.
- **E3. General SUD.** Substance use or addiction in general, with no specific substance → still a substantive role; the substance labels carry `general_SUD_unspecified`.
- **E4. The research question decides.** Generic endocannabinoid signaling → `endogenous_system_only`. Endogenous signaling explicitly investigated to explain ethanol self-administration, withdrawal or relapse → `use_as_outcome`, even without drug administration. A tool compound does not erase the substantive role of the addiction question.
- **E5. Novel and investigational compounds** acting at a receptor, transporter or enzyme system characteristic of a DSM substance class → `object_of_study`; labels by target system (S4, `target_system_mapping`). This establishes centrality only; purpose is settled within the same unit by S2 and S3. A shared target is not evidence of abuse potential, relevant use or a qualifying purpose.
- **E6. Tobacco, nicotine, caffeine, kratom, novel psychoactive substances** → substantive roles as for any substance. Caffeine-only units are excluded later by C.1, not by S1.
- **E7. Behavioral addiction with a substance component** → code both `behavioral_addiction` and the substance's role.
- **E8. Instrument versus object.** Nicotine studied as a plant defense chemical or insecticide toxin, with no human use, dependence or addiction-relevant target → `instrument_only`. Ethanol as an industrial product → `instrument_only`.

### S2. `stated_purposes` — multi-select, conditional

Purposes supported by the unit's stated aim or description of the work. Applicable when S1 has one of the six substantive substance roles; S1 uncertain → `cannot_determine`; established absence of those roles → `not_applicable`, including endogenous-system research without a co-occurring substantive substance role.

| Value | Definition |
|---|---|
| `sud_treatment` | Prevention, diagnosis, treatment, recovery or harm reduction for substance use or SUD |
| `use_or_misuse` | Substance-use patterns, causes, correlates or trajectories |
| `abuse_liability_dependence_withdrawal` | Abuse liability, reinforcement, dependence, tolerance, withdrawal, craving or relapse |
| `effects_of_use_or_exposure` | Health, cognitive, behavioral, developmental or social effects of substance use/exposure; not therapeutic benefit for an unrelated condition |
| `mechanism_of_action` | Action, chemistry, pharmacology, pharmacokinetics or metabolism of a study-defined drug; basic research need not name a treatment application |
| `substance_exposure` | Characterizing exposure, including prenatal, environmental, secondhand exposure and intoxication |
| `substance_related_harm_care` | Preventing, diagnosing or treating explicitly substance-related harms/conditions, including overdose, alcohol-related organ injury or substance-related infectious harm |
| `services_implementation` | Organization, access, delivery, financing or implementation of substance-related care/services |
| `policy_social_responses` | Substance-related regulation, markets, policy, stigma, meanings, attitudes or other social responses |
| `education_workforce` | Education, curricula, workforce preparation or research/training infrastructure explicitly for substance-related research, prevention, care or harm reduction, studied as the unit’s research object; training status or program affiliation alone is insufficient |
| `measurement_methods` | Developing or validating measures, assays, models or methods explicitly for a substance-related research/care target |
| `none_stated` | No qualifying purpose established, but relevance is unstated/unresolved or only an unrelated therapeutic aim is established (S3); exclusive |
| `outside_study_scope` | The aim is clearly unrelated to the study-defined drug/alcohol research target, beyond the separately coded unrelated-therapeutic case; exclusive. Never infer this from a missing application |

**Rules**
1. Read only the unit's aim, not background application lists. A qualifying purpose in one unit cannot supply purpose to another.
1a. A purpose must be stated or supported by the abstract's description of the work, not inferred from a role label alone. `use_as_outcome` does not automatically add every use, misuse, treatment and policy purpose. If the stated question is why substance use occurs, S2 uses `use_or_misuse`; C5 separately uses `explain_causes` if that is the main qualifying research objective.
2. Basic action/metabolism/toxicity research on a study-defined drug may qualify without a clinical application. Novel ligand affinity/selectivity/SAR with no stated relevant application remains `none_stated` and undetermined; receptor identity alone does not establish relevance.
3. Routine mechanism or pharmacokinetic measurements serving solely an unrelated therapeutic-efficacy aim do not independently establish `mechanism_of_action`. A separately stated drug-action or abuse-liability question is coded as its own unit.
4. Treating alcohol-related liver injury is `substance_related_harm_care`, even without treating AUD. Comorbidity or recruitment alone is insufficient: generic diabetes care among people with SUD needs an explicit substance-related care question.
5. Policy, stigma, services and education need not measure changes in consumption to qualify, but their research subject must explicitly concern the substance-related target. A general service delivered in a SUD treatment setting, or used by people with SUD, does not qualify on setting or sample alone; the service or social-response question must itself be substance-related. NIDA-supported training is an agency activity, not a presumption that any dissertation about a workforce or training program qualifies.
6. Clear unrelated therapeutic aim → `none_stated` and S3 yes. Inadequate evidence to establish the unit's purpose → `cannot_determine`, not `none_stated`.
7. Ordinary antibiotic research without a study-defined substance/topic is S1 `none`, so S2–S4 are `not_applicable`. Reserve `outside_study_scope` for clearly excluded purposes when S1 does establish a study-defined substantive topic; uncertain novel-ligand relevance remains `none_stated`. A biological mechanism alone is insufficient.
8. Caffeine units with a substantive role may receive descriptive purpose codes but are excluded in C.1 unless the same unit independently qualifies through its coded endogenous-system role. Behavioral-addiction-only units have S2/S3 not_applicable and populated S4; without the endogenous role they exit at C.1 step 2.
9. **Prescribing and medical use of controlled substances.** This covers opioid, benzodiazepine, stimulant or other controlled-substance prescribing and dispensing. It qualifies when the unit's research is framed around misuse, diversion, dependence, overdose, or policies addressing those harms, such as prescription drug monitoring programs, prescribing limits aimed at misuse, or co-prescribing risk. Code `use_or_misuse`, `substance_related_harm_care` or `policy_social_responses` as appropriate.

   Analgesic effectiveness, symptom control, or prescribing quality for the treated condition does not qualify merely because the medicine is an opioid or other controlled substance. A prescribed opioid dose or reduction in administered opioid consumption, measured as part of pain care, is not by itself a misuse or harm-care question. With no qualifying purpose, code S2 `none_stated` and S3 `yes` when a therapeutic indication is tested or its outcomes are reported. If the prescribing or regulatory framing is unclear about whether misuse-related harms are addressed, use `cannot_determine`.

### S3. `unrelated_therapeutic_indication_tested` — single-select, conditional

Replaces `non_sud_indication_tested`; it is not an alias. Whether the unit tests a substance/compound/intervention for a condition **unrelated to substance use, SUD or substance-related harms**. Applicability follows S2.

| Value | Definition |
|---|---|
| `yes` | An unrelated indication is tested in a model, assay or endpoint, or outcomes for that indication are reported |
| `no` | The described work does not test an unrelated indication; background lists do not establish testing |

Insufficient evidence → `cannot_determine`. Psilocybin for depression alone or a novel nicotinic modulator tested only in pain models → yes. Treatment of alcohol-associated liver injury → no. A qualifying purpose established within the same connected unit takes precedence over yes; independent relationships must first be split under A2a.

### S4. Substance labels — `substance_all`, `substance_primary`, `substance_assignment_basis`

**Vocabulary and rules.** Apply per scope unit:
- **Applicable** when `substance_roles` contains a substantive substance role, `endogenous_system_only` or `behavioral_addiction`. Code a supported label; use `cannot_determine` when no label is supported.
- **`not_applicable`** when S1 establishes none of those roles; uncertain S1 → `cannot_determine`.
- Endogenous-system labels require explicit support from the title and abstract for a substance class or target-system mapping. Assess them during the same scope pass as the unit's S1 role. Do not infer a class from funding, anatomy alone or generic endogenous biology, and do not substitute `general_SUD_unspecified` without a stated general substance-use construct. Unresolved labels do not reverse endogenous-system inclusion.
- **Behavioral addiction with no substance:** `substance_all` = `[behavioral_addiction]`.

| Label | Covers |
|---|---|
| `alcohol` | AUD, heavy and binge drinking; alcohol's health effects, metabolism, intoxication, fetal alcohol exposure |
| `cannabis` | Marijuana, THC, hashish, cannabidiol, CUD; CB1/CB2-targeted compounds |
| `opioids` | Heroin, fentanyl, oxycodone, morphine, prescription opioids, OUD; mu/kappa/delta-targeted compounds |
| `sedative_hypnotic_anxiolytic` | Benzodiazepines, barbiturates, Z-drugs |
| `stimulant` | Methamphetamine, amphetamine, cocaine, prescription stimulants used nonmedically; dopamine-transporter-targeted compounds |
| `tobacco_nicotine` | Cigarettes, smokeless tobacco, vaping, e-cigarettes, nicotine dependence, cessation; nicotinic-receptor-targeted compounds |
| `hallucinogen_phencyclidine` | LSD, psilocybin, MDMA as hallucinogen, PCP, ketamine |
| `inhalant` | Solvents, glue, nitrites, aerosol propellants |
| `caffeine` | Only where central |
| `behavioral_addiction` | Behavioral addiction focal |
| `other_named_non_alcohol_drug` | A named substance outside the classes above, not alcohol |
| `substance_unidentified` | A specific substance is central but unnamed |
| `general_SUD_unspecified` | Substance use or addiction in general, alcohol not excluded. **Fully exclusive** |
| `general_drug_unspecified` | Non-alcohol drug use in general, alcohol clearly excluded. **Exclusive except with `alcohol`** |

`substance_primary`: one of the labels above or `none_dominant`.

`substance_assignment_basis`:
- `named_focal_substance`: every label traces to a substance named in the text;
- `general_substance_construct`: **mechanical**, whenever any general construct label is present;
- `target_system_mapping`: at least one label needed receptor, transporter or enzyme identity.

For a behavioral-addiction-only unit, `substance_all` and `substance_primary` are `behavioral_addiction`; assignment basis is structurally `not_applicable`, because no substance is assigned.

**Target attribution and safeguards**
- Label the substance-related research target, not an incidental treatment/tool drug: naltrexone for AUD or a nonpsychoactive treatment for alcohol-related liver injury → `alcohol`; OUD provider-stigma research → `opioids`.
- General substance-specific workforce/services → the appropriate general construct. Generic health-workforce research does not qualify through a background substance mention.
- An established focal drug class can support basic pharmacology. `other_named_non_alcohol_drug` does not make all named medicines study-defined: there must be stated psychoactive/nonmedical use, abuse potential, or an explicit study-defined substance-related research target. If relevance of a novel target-mapped compound is unstated, preserve uncertainty.
- One label → primary equals it; any named primary must be in the list; `none_dominant` requires at least two labels. The list and primary share status unless dominance alone cannot be determined.
- General SUD is exclusive; general drug is exclusive except with alcohol. Named non-alcohol classes plus residual “other drugs” retain only named classes. Alcohol plus unspecified drugs uses `[alcohol, general_drug_unspecified]`.
- Any general construct, including `substance_unidentified`, forces `general_substance_construct`. Otherwise use `target_system_mapping` only if target identity is needed to assign a label; otherwise `named_focal_substance`.
- Record-level analysis labels are derived only from qualifying units (C.2). Nonqualifying therapeutic aims cannot add a drug domain to an otherwise alcohol-only qualifying record.

**Co-occurrence.**
- `general_SUD_unspecified` is fully exclusive; `general_drug_unspecified` combines with `alcohol` only; all other labels combine freely.
- "Drug and alcohol treatment court" → `[alcohol, general_drug_unspecified]`.
- "Alcohol and other substance use," "drug and alcohol treatment," and equivalent contrasts → `[alcohol, general_drug_unspecified]` when both sides are focal and no non-alcohol class is named. Do not collapse that explicit contrast to `general_SUD_unspecified` merely because the abstract later uses "SUD" as an umbrella term.

**`substance_primary` invariants.**
1. One label ⇒ `substance_primary` equals it.
2. A named `substance_primary` appears in `substance_all`.
3. `none_dominant` requires at least two labels.
4. The two fields share `coding_status`, except that `substance_primary` alone may be `cannot_determine` when dominance cannot be established.

**Assignment basis.**
- **Mechanical rule; check it first.** If `substance_all` contains `general_SUD_unspecified`, `general_drug_unspecified` or `substance_unidentified`, the basis is `general_substance_construct`, however many other labels are explicitly named. It is a property of the label set, not a judgment about the abstract.
- **Necessity test.** Would every `substance_all` label still be assigned if receptor, transporter and enzyme names were removed? If yes, do not use `target_system_mapping`. Receptor language in work explicitly centered on named opioids remains `named_focal_substance`. Use `target_system_mapping` only when target identity is necessary to supply at least one label.
- `named_focal_substance` requires that every label trace to a substance named in the text.

**Edge rules**
- **E1.** See co-occurrence above.
- **E2. Measured but not focal.** Aims about alcohol with cannabis as a covariate → `[alcohol]`.
- **E2a. Co-medications and guideline conditions.** A substance mentioned only as a contraindicated co-prescription, comparator, covariate, assay control or background risk is not focal. An opioid-prescribing-guideline study does not add `sedative_hypnotic_anxiolytic` solely because a guideline says to avoid concurrent benzodiazepines. Add the class only when its use or outcomes are independently part of the unit's aim.
- **E3. Behavioral addiction does not count toward polysubstance.**
- **E4. MDMA and ketamine.** By framing; ketamine → `hallucinogen_phencyclidine` always.
- **E5. Prescription stimulants.** Nonmedical use → `stimulant`.
- **E6. Alcohol's health effects still code `alcohol`.**
- **E7.** A coded `substance_all` requires at least one label. Endogenous-system research remains in scope when its substance labels cannot be determined.
- **E8. Missing versus empty.** Non-coded is `null`, never `[]`.
- **E9. Medications: code the target, not the drug class.** Naltrexone for AUD → `[alcohol]`; for OUD → `[opioids]`.
- **E10. `general_drug_unspecified` versus `general_SUD_unspecified`.** The former only where alcohol is clearly excluded; if ambiguous, the latter.
- **E11. `substance_unidentified` versus `other_named_non_alcohol_drug`.** Named and not alcohol → the latter; central but unnamed → the former.
- **E12. Novel compounds** code to the class of their target system, with `target_system_mapping`.
- **E13. Explicit class plus receptor language.** A class explicitly named as focal → `named_focal_substance` even when its receptors are analyzed, unless target identity supplies an additional label.
- **E14. Named classes plus a residual "other drugs" phrase.** Code only the named classes.
  - "Alcohol, cannabis and other drug use" → `[alcohol, cannabis]`.
  - "Opioid and other drug overdose" → `[opioids]`.
  - "Drug and alcohol treatment court" → `[alcohol, general_drug_unspecified]`, because no specific non-alcohol class is named.

### S5. `add_su_focus` — ordinal 1–3

How central substance use, misuse, addiction or SUD is, across the described dissertation. It stratifies the in-scope population (A/B/C) and gates nothing; a missing focus gives stratum U and never removes eligibility. Never `not_applicable` for assessed records.

| Value | Definition |
|---|---|
| **1 — Core** | Primary questions, aims or hypotheses explicitly about substance use, misuse, addiction or SUD |
| **2 — Shared focus** | One of several central constructs |
| **3 — Peripheral or absent** | Mentioned only as background; or a substance is central but no use, misuse, addiction or SUD construct appears |

**Clear case.** Write the one-sentence description. Is substance use or addiction in it? As the main idea → 1. Sharing equal weight → 2. No → 3.

**Revision 11 clarification for the focused check.** First ask whether a use, misuse, addiction or SUD construct is actually a stated research focus; a substance drug, receptor, exposure or harm can be central while this construct is absent, yielding 3. If that construct is focal, assign 1 when it is the principal question and 2 only when a distinct non-use topic is presented as coequal. A broad list of outcomes or covariates does not alone establish coequal focus. Do not infer focus from a substance mention in the title or from the number of coded scope roles.

**Edge rules**
- **E1. 1 versus 2.** How would this be listed on a CV or biosketch?
- **E2.** Substance use as the outcome of a non-addiction exposure → 1.
- **E3.** Many co-primary outcomes → 2.
- **E4. Comorbidity.** 2 where both disorders are focal; 1 where the other is a covariate.
- **E5. Substance central, no use-or-disorder construct → 3.** Pharmacology, receptor binding, alcohol-related organ damage, prenatal exposure, intoxication.
- **E6. Medications for SUD.** A buprenorphine retention trial → 1. Phase 1 pharmacokinetics of a formulation → 3.
- **E7. Title mentions, abstract doesn't.** Follow the aims: 3, `confidence: low`.
- **E8. SUD-specific services and social endpoints remain core.** Treatment delivery, provider behavior, stigma, policy, recovery, harm reduction or training **specifically for substance use or SUD** → 1. The service or social endpoint is not automatically a second focus.
- **E9. Shared focus requires a distinct coequal topic.** A non-SUD disorder, therapeutic indication, exposure or social problem must share the aims with substance use or addiction → 2. Integrated SUD–PTSD treatment → 2; EMS care specifically for opioid addiction → 1.
- **E10.** Substance, therapeutic and legal framings can share focus. A kratom study giving coequal attention to pain relief, addiction concerns, user experience and a proposed ban → 2.

## Content layer (production set)

Production content follows only the runner-selected qualifying target in A3; skipped/deferred records follow A6.

### C1. `mixed_purpose` — single-select

**What it is.** The prominence of runner-selected qualifying research relative to nonqualifying research described in the title or abstract. This is a record-level characterization of the dissertation, not an inclusion rule or a reassessment of unit eligibility. C2–C9 still describe only the qualifying target.

| Value | Definition |
|---|---|
| `only_qualifying_described` | All research described in the title and abstract is in qualifying units; this makes no claim about unmentioned chapters or aims |
| `qualifying_primary` | Both qualifying and nonqualifying research are described, and the qualifying research is presented as the dissertation's main contribution |
| `coequal` | Both are described as coequal contributions; neither is presented as primary |
| `nonqualifying_primary` | Both are described, and the nonqualifying research is presented as the dissertation's main contribution |
| `mixed_prominence_unclear` | Both are described, but the evidence does not establish their relative prominence |

**Applicability:** requested only for in-scope records; other states follow A6.

**Evidence and edge rules.** Use stated overall objectives, chapter descriptions, and the abstract's account of its contributions. Do not infer prominence from chapter count alone, relative word count in the abstract, disciplinary assumptions, or a broad title. A chapter count can inform the judgment when the abstract explains what the chapters contribute. An abstract describing only qualifying research yields `only_qualifying_described`, not an assertion that every unseen part qualifies. A dissertation with several qualifying drug/alcohol-context pain chapters and a qualifying withdrawal chapter has no nonqualifying work on that evidence. A dissertation dominated by unrelated-indication pain-treatment chapters with a separate qualifying withdrawal aim may be `nonqualifying_primary` if the abstract establishes that balance; otherwise use `mixed_prominence_unclear`.

**Consistency check:** with all described units in scope and none unresolved, C1 must be `only_qualifying_described`. Any of the four mixed values requires at least one known nonqualifying unit; a minor but distinct nonqualifying research aim can yield `qualifying_primary`. Do not count background, routine methods, or an unrelated condition mentioned only as context as separate nonqualifying research. If a unit is unresolved and could change whether any nonqualifying work exists, use field-level `cannot_determine`; if a known mix exists but its balance is not established, use `mixed_prominence_unclear`. Flag contradictions or omitted units for correction. C1 never changes target IDs or eligibility.

**Use.** Report the distribution of in-scope research prominence. C1 alone does not establish the content of research outside the fixed targets.

### C2. `dissertation_type` — single-select

**What it is.** What kind of scholarly contribution the qualifying research makes, judged by its purpose or deliverable, not its format. A three-paper dissertation is classified by what its qualifying research delivers.

| Value | Definition |
|---|---|
| `empirical_research` | Collects or analyzes data to produce generalizable knowledge, in one study or several |
| `program_evaluation_qi` | Evaluates or improves a specific program, service or practice in a named or local setting, framed for that setting's decisions |
| `evidence_synthesis` | Systematic, scoping or structured literature review, or meta-analysis, as the main contribution |
| `conceptual_theoretical` | Argument, theory-building, historical, legal or philosophical analysis without new empirical analysis |
| `practice_product` | A clinical manual, curriculum, training, protocol or toolkit is the deliverable, with or without a pilot |
| `methods_development` | A measure, assay, analytic method or model is developed or validated, and its performance is the deliverable |
| `multiple_no_dominant` | Different qualifying contributions carry the aims equally |

**Clear case.** What does the qualifying research hand over at the end: knowledge, a judgment about one program, a literature summary, an argument, a usable product, or a validated tool?

**Edge rules**
- **E1.** A local program evaluated to inform that program → `program_evaluation_qi`; the same design framed around a generalizable hypothesis → `empirical_research`.
- **E2.** Product as stated deliverable → `practice_product`; evaluating an existing product → E1.
- **E3.** Validation primary → `methods_development`; validation as a preliminary step within a substantive study → the substantive type.
- **E4. Multi-paper format does not decide type.** Papers with different contributions: code the contribution carrying the main qualifying aim. If none dominates, `multiple_no_dominant`.
- **E5.** Secondary data analysis is `empirical_research`; type does not depend on data origin.
- **E6.** Novel-compound synthesis and characterization → `empirical_research`; developing an assay or detection method whose performance is primary → `methods_development`.

### C3. `study_design` — single-select

**What it is.** A pragmatic classification of how the main qualifying empirical question is answered. It combines assignment, timing and approach, and resolves overlaps by the precedence order below. It does not separate those dimensions fully. `not_applicable` when `dissertation_type` is `evidence_synthesis` or `conceptual_theoretical`, or is a `practice_product` with no evaluation.

| Value | Definition |
|---|---|
| `mixed_methods` | Explicit integration of qualitative and quantitative components |
| `qualitative` | Interviews, focus groups, ethnography, qualitative document or media analysis, whether at one time point or several |
| `single_case` | Single-subject or case-study designs |
| `computational_modeling` | Simulation, in silico, pharmacometric or systems models whose output is the main result |
| `synthesis_characterization` | Chemical synthesis, structural or analytical characterization of compounds or materials, with no experimental comparison |
| `experimental_randomized` | Conditions assigned at random by the investigator: RCTs, randomized laboratory or vignette experiments |
| `experimental_nonrandomized` | Investigator manipulates exposure or treatment with a comparison, randomization not stated: most animal, in vitro and dose–response work |
| `quasi_experimental` | Treatment not assigned by the investigator, analyzed with a comparison built for causal inference: natural experiments, difference-in-differences, interrupted time series, regression discontinuity, synthetic control |
| `single_group_pre_post` | One group measured before and after an intervention, no comparison |
| `longitudinal_observational` | Repeated measures on the same units, no manipulation |
| `cross_sectional_observational` | One time point, associational or descriptive |
| `multiple_no_dominant` | Two or more designs, none carrying the main qualifying aim |

**Precedence.** First identify the main qualifying study under A3; if equally important studies have different designs, use `multiple_no_dominant` before this within-study precedence. For a single study, apply the first that fits, in table order: `mixed_methods` → `qualitative` → `single_case` → `computational_modeling` → `synthesis_characterization` → assignment (`experimental_randomized` → `experimental_nonrandomized` → `quasi_experimental` → `single_group_pre_post`) → timing (`longitudinal_observational` → `cross_sectional_observational`). A randomized trial with an integrated qualitative component is `mixed_methods`; its assignment is not recorded.

**Edge rules**
- **E1.** Randomization must be stated.
- **E2.** Secondary analysis of a completed trial for a non-randomized question → the observational design matching its structure.
- **E3.** Repeated within-person measures as the analytic focus → `longitudinal_observational`; one wave of a longitudinal dataset → `cross_sectional_observational`.
- **E4.** Qualitative plus quantitative without integration, both substantial → `multiple_no_dominant`.
- **E5.** Survey and vignette experiments with random assignment → `experimental_randomized`.
- **E6.** Design not stated → `cannot_determine`.

### C4. `level_of_analysis` — single-select

**What it is.** The unit about which the main qualifying conclusions are drawn. `not_applicable` for `conceptual_theoretical` work with no unit.

| Value | Definition |
|---|---|
| `molecular_cellular` | Molecules, receptors, compounds, cells, tissue, or biospecimens studied as material |
| `organism_nonhuman` | Whole living non-human organisms |
| `individual_human` | Individual people, including their brains, physiology and behavior |
| `dyad_family_group` | Couples, parent–child dyads, families, peer or therapy groups as units |
| `organization_program` | Clinics, treatment programs, schools, agencies, workplaces, provider organizations |
| `community_jurisdiction_population` | Neighborhoods, counties, states, countries, or population aggregates |
| `texts_media_discourse` | Documents, media, policies or online content as units |
| `multiple_no_dominant` | Two or more levels carry the conclusions equally |

**Edge rules**
- **E1.** In multilevel analyses, the level of the primary outcome decides.
- **E2.** Human biospecimens: about the people → `individual_human`; about the material or mechanism → `molecular_cellular`.
- **E3.** Individual data aggregated to rates or area-level measures → `community_jurisdiction_population`.
- **E4.** Providers surveyed as individuals → `individual_human`; organizations as units → `organization_program`.
- **E5.** Evidence syntheses → the level of the synthesized studies' conclusions.
- **E6.** Post-mortem human tissue: donors as a population → `individual_human`; tissue as substrate → `molecular_cellular`.

### C5. `research_objective` — single-select

**What it is.** The kind of question the main qualifying aim asks.

| Value | Definition |
|---|---|
| `describe_distribution` | How much, where, in whom, over time: prevalence, incidence, trends, disparities |
| `explain_causes` | Why use, misuse or addiction occurs: risk and protective factors, etiology, processes producing addiction phenomena. Substance use is the **outcome** |
| `consequences_of_use` | What substance use or exposure does: physiological, organ, developmental, cognitive, psychiatric, behavioral, social, academic, occupational or justice outcomes. Substance use is the **exposure** |
| `characterize_substance_action` | How a substance or compound acts: binding, selectivity, potency, pharmacokinetics, structure–activity, characterized toward understanding or development |
| `intervene` | Developing or testing an intervention to prevent, detect, treat, or support recovery from substance use/SUD or explicitly substance-related harms and conditions |
| `organize_deliver_services` | How care or programs are organized, delivered, staffed, financed, accessed, adopted or scaled, including organizational policy |
| `law_policy_economics` | Laws, regulation, enforcement, markets, prices or economic conditions as causes or objects |
| `meanings_attitudes` | Stigma, discourse, identity, norms, or public and professional attitudes as the principal object or outcome |
| `education_workforce` | Training, curricula, competencies or professional preparation as the object |
| `measurement` | Developing or evaluating a measure, assay, method, platform or paradigm where its performance is primary |
| `other_stated_objective` | The objective is clear but no listed category fits; review each use |
| `multiple_no_dominant` | Different qualifying objectives carry the aims equally |

**Endogenous-system objectives.** Apply the stated meanings of C5 to the admitted research. Endogenous mechanisms alone do not imply `characterize_substance_action` or a substance-use outcome. When the objective is stated but none of the listed categories fits, use `other_stated_objective`; insufficient evidence remains `cannot_determine`.

**Edge rules**
- **E1. Direction test.** Is substance use the exposure or the outcome? Outcome → `explain_causes`; exposure → `consequences_of_use`. Mechanistic language does not override direction. Bidirectional models: use the explicitly dominant direction; neither primary → `multiple_no_dominant`.
- **E2. Endpoint test.** In mechanistic studies of a substance, read the endpoint:
  - an addiction phenomenon (tolerance, withdrawal, sensitization, craving, relapse, reinstatement, self-administration, reinforcement, abuse liability, dependence, escalation) → `explain_causes`;
  - a non-addiction consequence → `consequences_of_use`;
  - the compound itself → `characterize_substance_action`.
- **E3.** How much and in whom → `describe_distribution`; why → `explain_causes`.
- **E4.** Build or validate a measure → `measurement`; apply one in a service context → `intervene` (screening).
- **E5.** Organization or delivery system as the unit → `organize_deliver_services`; patient outcomes of an intervention → `intervene`.
- **E6.** Law, regulation, enforcement or economic condition → `law_policy_economics`; internal organizational procedure → `organize_deliver_services`.
- **E7. Meanings boundary.**
  - Stigma or attitudes as the measured outcome → `meanings_attitudes`.
  - Stigma predicting service access → `organize_deliver_services`.
  - Stigma or norms predicting use → `explain_causes`.
- **E8.** Prenatal exposure and intoxication → `consequences_of_use`.
- **E9.** Assay, receptor-platform or analytical-method development whose performance is the deliverable → `measurement`; an established platform used to characterize compounds → `characterize_substance_action`.
- **E10.** Qualitative recovery processes framed around achieving or sustaining recovery → `intervene` with continuum `recovery_harm_reduction` if an intervention or support is studied; otherwise `explain_causes`.
- **E11. Therapeutic boundaries.** Prevention/treatment of substance-related harm or disease → `intervene`, including alcohol-related organ injury. Unrelated therapeutic-efficacy aims receive no content unless independently in scope through the endogenous-system rule. Independent substance-action research → `characterize_substance_action`; adverse substance effects → `consequences_of_use`. Do not recast unrelated therapeutic benefit as a qualifying substance mechanism.

### C6. `intervention_continuum` — single-select, conditional

**What it is.** Which part of the prevention-to-recovery continuum the intervention or service addresses. Applicable when `research_objective` is `intervene` or `organize_deliver_services`; other known single objectives → `not_applicable`; uncertain objective → `cannot_determine`; tied objectives follow A3. Apply the continuum to substance-related care, including prevention, detection and treatment of related harms.

| Value | Definition |
|---|---|
| `prevention` | People without the condition: preventing initiation or escalation |
| `screening_early_intervention` | Identifying existing use or risk in a service context, including brief intervention |
| `treatment` | Active treatment of substance use/SUD or substance-related disease/harm: detoxification, initiation, retention, completion, pharmacotherapy, psychosocial treatment, acute overdose care or organ-disease treatment |
| `recovery_harm_reduction` | Sustaining remission, post-treatment relapse prevention, peer recovery support, or reducing harm without requiring abstinence |
| `multiple_no_dominant` | Two or more, none dominant |

**Edge rules:**
- completion or retention and post-treatment relapse co-primary → the endpoint emphasized in the stated objective;
- if neither dominates → `multiple_no_dominant`.

### C7. `explanatory_domain` — single-select, conditional

**What it is.** The domain of the explanation or effect studied. Applicable when `research_objective` is `explain_causes`, `consequences_of_use` or `characterize_substance_action`; other known single objectives → `not_applicable`; uncertain objective → `cannot_determine`; tied objectives follow A3.

| Value | Definition |
|---|---|
| `biological_neural` | Molecular, genetic, neural, physiological or pharmacological processes |
| `psychological_behavioral` | Cognition, emotion, personality, learning, decision-making, behavior |
| `social_environmental` | Family, peers, community, culture, policy environment, economic or physical environment |
| `multiple_no_dominant` | Two or more domains carry the aims equally |

**Edge rules**
- **E1.** The domain of the explanatory variables for `explain_causes`, and of the outcome for `consequences_of_use`.
- **E2.** `characterize_substance_action` is normally `biological_neural`; human behavioral pharmacology measuring subjective or behavioral effects → `psychological_behavioral`.
- **E3.** Neuroimaging of cognitive processes: neural measures as the explanation → `biological_neural`; task performance only → `psychological_behavioral`.

### C8. `data_type` — multi-select

**What it is.** The **form** of the data the main qualifying analysis actually uses. Up to three, most central first. Include a second or third form only when the abstract says it was analyzed for qualifying research; a record, document or instrument mentioned as context, setting or intervention material does not by itself establish a data form. If more than three are equally central and no defensible subset exists, use `cannot_determine` and retain a capacity flag. Who generated the data, and whether it was collected for surveillance, is not recorded here. Provenance is `data_source_origin`. `not_applicable` when no data/evidence are analyzed, including conceptual work or a practice product without analyzed data; otherwise apply A3/A4.

| Value | Definition |
|---|---|
| `survey_questionnaire` | Self-report instruments, questionnaires, rating scales, vignette responses, whether author-administered or from an existing survey |
| `interview_observation` | Interviews, focus groups, field notes, observation, open-ended text from participants |
| `behavioral_task` | Laboratory tasks, cognitive or neuropsychological tests, observed or recorded behavior, self-administration |
| `biological_physiological` | Biospecimens, biomarkers, physiology, toxicology, clinical measurements |
| `neuroimaging_electrophysiology` | MRI, PET, EEG, electrophysiology, other brain measures |
| `genetic_genomic` | Genotypes, sequencing, gene expression, epigenetics |
| `chemical_analytical` | Compound synthesis, binding and functional assays, analytical or forensic chemistry |
| `health_records` | Electronic health records, claims, prescription or treatment records, registries, vital statistics, poison-center reports |
| `administrative_records` | Justice, education, social service or program operations records |
| `documents_media_online` | Policies, laws, media, social media, websites, published literature |
| `geospatial_market_environmental` | Geographic, outlet-density, price, market or environmental data |
| `simulated_model_data` | Data generated by simulation or models |

**Edge rules**
- **E1.** A national survey analyzed secondarily → `survey_questionnaire`, with `data_source_origin: secondary_existing`.
- **E2.** Records are classified by the domain that generated them: health care → `health_records`; justice, education or social services → `administrative_records`.
- **E3.** Evidence syntheses → `documents_media_online`.
- **E4.** Animal behavior paired with neural recording → both, most central first.

### C9. `data_source_origin` — single-select

**Applicability follows A6.** Provenance only: who generated the data analyzed for the qualifying target. The form of the data is `data_type`.

`primary_generated` · `secondary_existing` · `mixed_primary_secondary` · `no_empirical_data`

**Edge rules**
- **E1.** Aggregate jurisdictional data → `secondary_existing`.
- **E2.** Animal and laboratory work → `primary_generated` where the author generated the data. Synthesized compounds tested in the author's assays → `primary_generated`.
- **E3.** New measures within someone else's cohort → `mixed_primary_secondary`.
- **E4.** Administrative and health records → `secondary_existing`.
- **E5.** Author-run trial → `primary_generated`; secondary analysis of a completed trial → `secondary_existing`; not stated → `cannot_determine`.
- **E6. Qualitative provenance.** Author-conducted interviews, focus groups or observations → `primary_generated`. Reanalysis of existing transcripts or qualitative archives → `secondary_existing`. An abstract that says only "qualitative study", without identifying collection or source → `cannot_determine`; do not infer primary generation from the method label.
- **E7.** Reviews and document analysis → `secondary_existing`.
- **E8. Cannot tell** → `cannot_determine`. Do not default.
- **E9. Archived specimens.** Existing specimens plus newly generated measurements → `mixed_primary_secondary`.
- **E10.** Conceptual work and practice products with no analyzed data → `no_empirical_data` (paired with `data_type: not_applicable`).

## Cross-variable consistency

**Hard rules for both requests (errors)**
- Apply A5's missing-abstract exception first; do not validate its null fields as assessed-record cells.
- Coded cells have an allowed value and confidence; non-coded cells have null value and confidence.

**Scope hard rules (errors; scope request and scope validation)**
- Each assessed record has at least one uniquely identified scope unit; each unit contains `aim_id`, validated `source_sentence_ids` and the six coded fields.
- Validate the raw schema/enums before rule filling; validate the normalized cells and unit references before deriving outcomes. The endogenous inclusion rule does not bypass structural validation. Duplicate aim IDs, unknown sentence IDs or absent required fields are invalid, not evidence of inclusion.
- Per unit: `none` is exclusive in S1; `none_stated` and `outside_study_scope` are each exclusive in S2.
- Apply the parent-uncertainty and applicability rules of S2–S4.
- Apply S4's label invariants: co-occurrence, `substance_primary` invariants, the mechanical assignment-basis rule, and E14.
- Never combine scope facts across units to establish eligibility.
- `add_su_focus` is coded or `cannot_determine` for every assessed record; never `not_applicable`.

**Content hard rules (errors; content request and content validation)**
- Apply A6 first. Skipped and deferred records suspend content implications; only out-of-scope records receive structural `not_applicable` cells. Check `content_run_status` before validating field-level content.
- Echoed `target_aim_ids` exactly equal the runner-supplied targets.
- Content contains no scope fields, substance-unit additions or altered aim/sentence references. Preserve every scope field and its dependency identity before and after content processing; a successful content response cannot revise the scope ledger.
- Otherwise use variable-specific applicability and A3's tied-parent rules. An applicable field can still be `cannot_determine`.
- C1 follows its consistency check against the known unit outcomes.
- C3 may be `not_applicable` under its own condition; an uncertain type and mixed applicability follow A4 and A3.
- C6 and C7 follow their explicit objective conditions, including uncertain and tied objectives.
- For completed content, `data_source_origin: no_empirical_data` requires `data_type: not_applicable`, and vice versa. Conceptual work and practice products with no analyzed data use this pair. Evidence synthesis uses `documents_media_online` and `secondary_existing`; absence of newly collected data is not absence of analyzed evidence.

**Scope review flags (retain initial derivation; resolve before population certification)**
- Every unit containing `other_named_non_alcohol_drug`, especially sole-label units, requires review of S4's study-defined-topic safeguard against the original abstract. Log accepted/revised/unresolved disposition; the catch-all is not automatic domain evidence.
- Uncertain `substance_primary` does not block eligibility when `substance_all` is supported. Uncertain assignment basis likewise raises review, not a replacement scope gate.
- Invalid sentence IDs, omitted described aims, conflicting unit boundaries or missing shared methods require routing repair before affected content calls.

**Flags (review, do not block)**
- `study_design: qualitative` without `interview_observation` or `documents_media_online` in `data_type`.
- `research_objective: characterize_substance_action` with `level_of_analysis` of organization or community.
- `substance_assignment_basis: target_system_mapping` with `stated_purposes` containing only `none_stated`.
- `substance_roles` containing `therapeutic_agent` with `stated_purposes` containing `effects_of_use_or_exposure` (check that therapeutic benefit was not coded as an in-scope effect).
- `mixed_purpose` in {`coequal`, `nonqualifying_primary`, `mixed_prominence_unclear`} (check the content target and stated contribution).

---

# Part C — Derived fields (computed, never coded)

## C.1 Unit-level eligibility (computed, never coded)

Substantive roles are:
`object_of_study`, `use_as_outcome`, `use_as_exposure`, `treatment_target`, `therapeutic_agent`, `substance_related_systems_responses`.

Compute each unit independently from the one scope response, after the raw schema check, A4a normalization and completed-field/reference validation. Invalid structure requires correction before scientific derivation; an endogenous role does not convert invalid input into an admitted record. Status checks precede operations on a field's value; never interpret null as an empty coded set. Only `coding_status: coded` establishes an S1 role: the string `endogenous_system_only` in an uncertain or malformed field does not qualify. A qualifying purpose is any S2 value other than `none_stated` or `outside_study_scope`.

Ordered rules, first match wins:
1. Coded S1 containing `endogenous_system_only` → `in_scope / endogenous_system_aim`, independently of S2, S3 and S4 and including co-occurring roles. S2 and S3 keep their ordinary applicability rules; S4 is applicable and may be `cannot_determine` without changing inclusion.
2. Coded `substance_all` containing only behavioral addiction → `out_of_scope / behavioral_addiction_only`.
3. Uncertain S1 → `undetermined / substance_role_undetermined`.
4. Coded S1 with no substantive substance role → `out_of_scope / no_substance_central`.
5. Uncertain `substance_all` → `undetermined / substance_undetermined`. Structural `substance_all: not_applicable` with a substantive substance role is invalid and requires correction.
6. `substance_all` contains no label except caffeine and/or behavioral addiction → `out_of_scope / excluded_topic_only` (use `caffeine_only` for caffeine alone). Neither contributes a substance domain.
7. S2 is coded with a qualifying purpose → `in_scope / qualifying_aim`, regardless of S3, because the purpose and study-defined substance topic are connected in this unit.
8. S2 is uncertain → `undetermined / purpose_undetermined`, even if S3 is yes.
9. S2 is `outside_study_scope` → `out_of_scope / outside_study_scope`.
10. S2 is `none_stated` and S3 yes → `out_of_scope / unrelated_therapeutic_only`.
11. S2 is `none_stated` and S3 no or uncertain → `undetermined / purpose_undetermined`. Lack of a stated application is not a definite exclusion.

S2 or S3 structurally inapplicable with a substantive substance role is invalid. An endogenous-system-only unit retains S2 and S3 as structurally inapplicable. An established purpose cannot be rescued or defeated by labels or indications from a different unit. 

## C.2 Record-level `scope_v2` and analysis domains

Apply the documented year, language, geography and document-type rules to the reader's XML and metadata exports. The resulting roster is specific to that search and is not required to match the study's record set or count. The missing-abstract exception applies where appropriate. Eligibility is determined by the rules below independently of search-term membership.

After structural validation:
1. Missing abstract → `not_assessed / abstract_absent`; do not evaluate units.
2. At least one in-scope unit → `in_scope / qualifying_aim`, even if another unit is undetermined or excluded. Retain all unit outcomes and flag unresolved units for review.
3. No in-scope unit, at least one undetermined unit → `undetermined`. Use the common unit reason if all undetermined units share it; otherwise `multiple_undetermined_reasons`.
4. All units out of scope → `out_of_scope`. Use the common reason if all units share it; otherwise `multiple_exclusion_reasons`.

For an assessed in-scope record, `target_aim_ids` is exactly the list of all units whose C.1 outcome is `in_scope`, preserving their order in `scope_units`. Each target ID appears once and must identify a validated unit. Substance-related and endogenous-system units enter this list in the same derivation. Retain excluded and unresolved units and their outcomes for accounting and C1 context. Preserve the complete scope response and dependency hash when routing content.

For in-scope records, derive stratum A/B/C/U from focus 1/2/3/uncertain. Focus never gates inclusion. Non-in-scope records have null stratum.

**Substance domains:** compute from in-scope units only. The internal codes are `nida`, `niaaa`, `both` and `nida_niaaa_unspecified`. **Displays and manuscript text use drug, alcohol, both and general/unspecified**, respectively. The codes do not establish funding, referral or exclusive institute jurisdiction.
- Alcohol without study-defined non-alcohol or unresolved topic labels → `niaaa`.
- Study-defined non-alcohol labels without alcohol or unresolved labels → `nida`.
- Explicit alcohol plus study-defined non-alcohol labels → `both`.
- `general_SUD_unspecified`, `substance_unidentified` or unresolved substance labels leaves domain unresolved unless explicit in-scope labels already establish both → `nida_niaaa_unspecified`. Endogenous-system research with no supported class contributes no guessed label.
- `general_drug_unspecified` establishes a non-alcohol drug topic. Caffeine and behavioral addiction never contribute a study-defined domain.
- `other_named_non_alcohol_drug` contributes only through an in-scope unit with supported S4 target attribution.
- For non-in-scope records, analysis domain is null. Unit-level labels remain available for exclusion and uncertainty accounting.

A derived `qualifying_substance_all` is the union of qualifying-unit labels after removing caffeine/behavioral-addiction labels. Keep this union as provenance of the aggregation; it may contain general and specific labels from different units and is exempt from within-unit exclusivity rules. No record-wide primary label or assignment-basis code is forced across conflicting units; report unit bases or a prespecified downstream summary.
`polysubstance_flag` is true when this union contains at least two specific labels from {alcohol, cannabis, opioids, sedative_hypnotic_anxiolytic, stimulant, tobacco_nicotine, hallucinogen_phencyclidine, inhalant, other_named_non_alcohol_drug}. General labels do not count. This describes dissertation coverage, not necessarily concurrent use. Non-in-scope records have null flag.


### Scope examples

| Case | Scope |
|---|---|
| Treatment of alcohol-related liver injury without an AUD endpoint | In scope: harm care; alcohol target |
| Provider stigma toward people with OUD | In scope: social responses; opioids |
| Substance-specific clinician curriculum evaluation | In scope: education/workforce |
| Endogenous signaling explicitly studied as a mechanism of alcohol withdrawal, no drug administered | In scope: addiction phenomenon |
| Generic endocannabinoid signaling without a substance-related aim | In: endogenous-system research; cannabis label only when supported by target-system mapping |
| Explicit endogenous-system biology with no supported S4 class | In: coded endogenous role; all unsupported S4 values remain `cannot_determine` from scope through content |
| An alcohol-use unit alongside an endogenous-system unit | In: the one scope response assesses both; both IDs become fixed content targets in unit order |
| Coded endogenous role co-occurring with another S1 role and uncertain S2/S4 | In through the endogenous rule after valid normalization; descriptive uncertainty is retained |
| S1 itself is `cannot_determine` and endogenous involvement is only plausible | No endogenous admission; derive the uncertainty outcome from the validated scope fields |
| Novel CB1 ligand affinity series, relevance/application unstated | Undetermined: purpose |
| Psilocybin efficacy for depression alone, routine mechanism measures | Out: unrelated therapeutic only |
| Analgesic efficacy plus a separate abuse-liability aim | In: abuse-liability unit qualifies |
| Caffeine-use aim plus separate ketamine-for-depression aim | Out: multiple exclusion reasons; no cross-unit rescue |
| Alcohol-use aim plus separate ketamine-for-depression aim | In; analysis domain alcohol only |
| Study-defined cocaine mechanism aim plus an uncertain second aim | In; unresolved unit retained for review |
| No qualifying aim, one uncertain aim, other aims excluded | Undetermined |
| Named ordinary antibiotic action, clearly unrelated to use/addiction/related harm | Out: no substance centrality; S1 none, S2–S4 not_applicable |
| Caffeine-only use research | Out: caffeine only |
| Gambling-only research | Out: behavioral addiction only |
| Short abstract with adequate alcohol-use aim but no design detail | In; design cannot determine |
| Title available, abstract absent | Not assessed; no model call |
| Entire abstract is “Abstract not available.” | Not assessed after exact normalized placeholder match |
| Supported substance_all, uncertain substance_primary dominance | Eligibility determined from substance_all; primary uncertainty alone does not block |
| Post-surgical opioid prescribing quality or analgesic effectiveness, no misuse, diversion or overdose framing | Out: unrelated therapeutic only (S2 rule 9) |
| Effect of a prescription drug monitoring program on opioid overdose or doctor shopping | In scope: policy/harm; opioids |

### Evidence completeness within the retrieved universe

Within the retrieved universe:
- Confirmed in-scope count = N(in_scope).
- Maximum under an all-unresolved-in-scope scenario = N(in_scope) + N(undetermined) + N(not_assessed).
- Width = N(undetermined) + N(not_assessed).

Count distinct GOIDs, not units; statuses partition the established roster. Report both scenario counts and their components at one review/derivation snapshot. This is an evidence-completeness range, not a confidence interval or guarantee against classification error. Repair failed scope calls before certified enumeration; operational failures are not silently assigned scientific statuses.

## C.3 Additional derived field

`tobacco_consequences` is true for an in-scope record with an in-scope unit containing `tobacco_nicotine` in `substance_all` and `effects_of_use_or_exposure` in `stated_purposes`. It describes the coded research target and purpose; it does not identify funding.
