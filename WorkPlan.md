# PEAD-Bench Implementation Work Plan

Version: 1.0-plan
Plan date: 2026-07-30
Repository: `MAVS-RESEARCH/Predictive-Equivalence-and-Authorization-Divergence-MAVS`
Base commit: `9e6c1a7113f416c83aec4110c399273a2ded8b9b`
Normative specification: `PEAD_Benchmark_Implementation_Specification_v1.0.docx`
Scientific context: `MAVS-Diagnostic Sciences.pdf`

## 1. Purpose and non-negotiable contract

This plan converts the PEAD-Bench implementation specification into an executable, falsifiable, and audit-complete program. PEAD-Bench will construct decision worlds in which prediction-facing support is fixed while authorization-relevant evidence varies. It will test two separate hypotheses:

1. **H1 - information necessity:** whether prediction-facing state alone is sufficient to determine `Accept`, `Reject`, or `Escalate`.
2. **H2 - architecture value:** whether, after raw governance information is held equal, structured MAVS-GC governance provides a pre-registered advantage over strong flat or generic Raw-G methods.

H1 may pass while H2 fails. A MAVS win cannot rescue a failed or invalid H1 test. A scientifically negative result is retained and reported when integrity passes. An integrity failure invalidates the affected run.

The implementation will preserve the MAVS paper's central distinction:

> Prediction estimates support. Governance determines whether the available evidence authorizes action.

It will also preserve the Diagnostic Sciences requirements that each diagnostic has a declared scope, intended response, permitted influence path, and tests for in-scope value, out-of-scope influence, redundancy, instability, and composition.

### 1.1 Hard release gates

No headline claim is eligible unless all applicable gates pass:

- `PEI == 1.000000` for released exact pairs.
- `ADI == 1.000000` for released authorization-divergent exact pairs.
- Dual authorization-label agreement equals `1.000000`.
- Trace completeness equals `1.000000`.
- Access compliance equals `1.000000`.
- Deterministic artifact reproduction equals `1.000000`; explicitly registered tolerance rules apply only to nondeterministic model outputs.
- Holdout contamination, result-retention, budget-parity, abstention-degeneracy, and claim-eligibility audits pass.
- No generator, truth engine, or benchmark label code imports MAVS implementation code.
- Every claim-bearing number links to immutable decision traces, configuration hashes, code identity, and passing audits.

### 1.2 Scientific outcome is not a release gate

- If H1 fails with intact integrity, release a valid negative result.
- If H1 passes and H2 fails, conclude only that governance information matters on the registered PEAD class; do not claim MAVS architectural superiority.
- If a method achieves low unsafe acceptance through near-total rejection or escalation, report the coverage collapse; do not call it a safety success.
- Zero observed unsafe acceptance is finite-sample evidence, not certification.
- Self-Learning MAVS is excluded from the primary PEAD study. An adaptive-perception companion study may later use the reducibly ambiguous bank, but cannot rescue Paper 1.

## 2. Work discipline

### 2.1 `WorkPlan.md`

This file freezes phase scope, deliverables, implementation method, tests, commands, acceptance gates, model-training rules, claim boundaries, and phase dependencies. Any change after the study freeze creates a new study version.

### 2.2 `Path.md`

`Path.md` is the append-only execution ledger. Every meaningful implementation action must record:

- timestamp, phase, and change ID;
- files added, changed, removed, or generated;
- implementation details and commands;
- tests, benchmark runs, and exact artifact locations;
- pass/fail/invalid status with evidence;
- deviations from this plan and their scientific effect;
- failures, quarantines, corrections, and invalidated run IDs;
- result-cleaning operations and their exact scope;
- next permitted action.

A phase is not complete because code exists. It is complete only when its tests, stress runs, audits, retained evidence, and `Path.md` entries exist. A later defect reopens the affected phase and every dependent artifact.

### 2.3 Result hygiene

Generated results are never source code and are never silently reused.

- All new runs use immutable content-derived run IDs.
- A run directory is never overwritten. A rerun receives a new run ID and a parent/invalidation pointer.
- `scripts/clear_results.py` may remove only generated paths declared in a manifest and only after resolving and proving that every target is under `results/`.
- The cleanup command supports `--dry-run`, requires an explicit scope or run ID, rejects repository-root or unresolved targets, and writes a cleanup receipt to `Path.md` or a referenced artifact.
- Before the first PEAD run, pre-existing result artifacts must be inventoried and cleared. At plan creation, the remote repository contained only `LICENSE`; therefore the initial cleanup is a verified no-op.
- Development smoke artifacts are stored under named run IDs and are not carried into calibration, freeze, blind evaluation, or release.

### 2.4 Mandatory GitHub publication after every phase

Every phase must be committed and pushed to the GitHub repository automatically after its local completion gates pass. A phase is not complete, and work may not advance to the next phase, until its remote publication is verified.

The phase-close sequence is:

1. Finish the phase's implementation, tests, stress runs, audits, and evidence artifacts.
2. Update `Path.md` with the exact files, commands, test outcomes, run IDs, deviations, and phase-gate verdict.
3. Inspect `git status` and the complete intended diff; do not stage unrelated files.
4. Run `git diff --check` and all phase-required validation commands.
5. Commit the phase with a scoped message such as `phase-N: <completed scope>`.
6. Push the current study branch to `origin`.
7. Verify the remote branch resolves to the new commit.
8. Record the branch, commit SHA, push result, and remote verification in the next append-only publication entry in `Path.md`.

If commit, authentication, network, remote protection, or push verification fails, the phase status is `Publish blocked`, not `Complete`. Preserve the local commit and failure evidence, report the blocker, and do not begin the next phase until the push succeeds. No force-push, history rewrite, or branch deletion is allowed without explicit user authorization.

## 3. Target repository and engineering layout

The implementation will create the following responsibility-separated structure. Equivalent refinements are allowed only if the trust boundaries remain unchanged and the deviation is logged.

```text
.
|-- README.md
|-- LICENSE
|-- CITATION.cff
|-- WorkPlan.md
|-- Path.md
|-- CLAIMS.md
|-- CLAIM_ELIGIBILITY.md
|-- REPRODUCE.md
|-- pyproject.toml
|-- requirements.lock
|-- configs/
|   |-- study/pead_main_v1.yaml
|   |-- access/{p_only,raw_g,oracle_g}.yaml
|   |-- tracks/{exact,near,reversal,scope,evidence}.yaml
|   |-- domains/*.yaml
|   |-- mechanisms/*.yaml
|   |-- methods/*.yaml
|   |-- holdouts/*.yaml
|   `-- metrics/*.yaml
|-- src/pead/
|   |-- core/
|   |-- world/
|   |-- labels/
|   |-- projections/
|   |-- tracks/
|   |-- domains/
|   |-- baselines/
|   |-- mavs/
|   |-- metrics/
|   |-- audits/
|   `-- reports/
|-- scripts/
|-- tests/
|   |-- unit/
|   |-- property/
|   |-- metamorphic/
|   |-- integration/
|   |-- blind_contract/
|   `-- stress/
|-- banks/
|   |-- development/
|   |-- calibration/
|   |-- public_validation/
|   `-- sealed/
|-- manifests/
`-- results/
    |-- raw/<run_id>/
    |-- processed/<run_id>/
    |-- audits/<run_id>/
    |-- reports/<run_id>/
    `-- manifests/<run_id>/
```

## 4. Data, truth, and access contracts

The foundational immutable records are:

- `WorldState`: complete latent causal world.
- `PredictiveState`: declared prediction-facing state `p(x)`.
- `GovernanceState`: raw, visible governance evidence that excludes latent truth and MAVS diagnostics.
- `OracleState`: latent governance variables used only for upper-bound and generator sanity checks.
- `AuthorizationLabel`: `Accept`, `Reject`, or `Escalate`, with reason class and rule lineage.
- `CaseRecord`, `PairRecord`, and `SequenceRecord`: content-addressed evaluation units and lineage.
- `ScopeContract`: `(failure family, context, response, allowed influence)`.
- `MethodDecision`: decision, named scores, operating point, trace, resource use, and projection hash.
- `AuditRecord`: gate, severity, evidence pointers, invalidation scope, and status.

The runner must never give a `WorldState` to a method. The only legal route is:

```text
WorldState -> frozen AccessProfile -> sealed projection -> method decision commit
           -> hidden label reveal -> evaluator -> immutable trace -> audits
```

Every method receives one of three access profiles:

- **P-only:** `PredictiveState` only; tests prediction sufficiency.
- **Raw-G:** the same `PredictiveState` plus the same registered raw `GovernanceState`; tests architecture under equal information.
- **Oracle-G:** Raw-G plus latent governance truth; sanity/upper bound only and never a headline baseline.

## 5. Training, evaluation, and anti-overfitting doctrine

### 5.1 What is trained

Trainable P-only methods:

- regularized logistic regression;
- gradient-boosted trees;
- MLP;
- canonical-record sequence model;
- reject-option and conformal variants where their calibration contains learned parameters.

Trainable Raw-G methods:

- regularized logistic regression and decision tree;
- gradient-boosted trees;
- MLP;
- sequence encoder;
- provenance/dependency GNN;
- Bayesian network or factor-graph parameterization where applicable;
- learned judge/verifier benchmark adapter;
- learned scalar-risk compression;
- mixture/stacked ensemble.

Non-trained or fixed methods:

- confidence, uncertainty, disagreement, and deterministic self-consistency gates;
- declarative policy engine and validator stack;
- reference authorization evaluators;
- primary frozen MAVS-GC and MAVS-GC + DS-CF;
- fixed MAVS scalarization and fixed component ablations;
- Oracle rule evaluator.

If a fixed MAVS threshold or coefficient is calibrated during development, that process is treated as tuning and is frozen before the blind bank is unlocked. The primary DS-CF condition remains an explicit governance transformation, not a predictor retraining exercise.

### 5.2 Training benchmark versus claim-bearing benchmarks

The claim-bearing tests must be **structurally different from the training benchmark**, not merely different rows or random seeds.

| Partition | Permitted content | Scientific role | Isolation requirement |
|---|---|---|---|
| Development/training | Open mechanisms, open policy forms, open graph families, domains D1-D6, development templates and seeds | Train models, debug code, fit representations | May be regenerated; never claim-bearing |
| Calibration | Disjoint worlds from known mechanisms and templates; no holdout logical forms | Select thresholds and operating points | No architecture changes after final calibration |
| Public validation | New seeds, nuisance families, and mechanism compositions from known development families | Sanity, power, public figures | Cannot determine final claim |
| Structural holdout | Unseen mechanism families/compositions, policy logical forms, provenance topologies/depths, diagnostic interactions, and intervention types | Causal generalization | Authored and sealed before model tuning ends |
| Domain holdout | Two complete surface domains, provisionally D7 clinical-triage proxy and D8 content/policy-safety proxy | Cross-domain latent-grammar transfer | No templates, feature statistics, examples, labels, or adapter outputs exposed during training |
| Final blind bank | Cross-product of structural holdouts and the two unseen domains, with hidden seeds and held-out nuisance families | Claim-bearing evaluation | Unlocked only after signed freeze; single scientific run |

The holdout registry will be frozen before final tuning. If D7/D8 prove invalid during independent domain review, replacement domains must be selected before freeze and the change logged; they cannot be swapped based on method performance.

### 5.3 Brutal independent evaluation

Every trained model must be evaluated on all applicable test families below, none of which may contribute training examples, early-stopping feedback, feature-selection feedback, threshold selection, or hyperparameter selection:

1. **Unseen causal mechanisms:** at least two withheld families or novel three-fact compositions.
2. **Unseen policy grammar:** new logical forms, nesting, temporal clauses, and contradiction patterns rather than changed numeric thresholds.
3. **Unseen provenance graphs:** unseen topology classes, depth ranges, dependency sharing, and compromised-source patterns.
4. **Unseen interventions:** delayed compromise discovery, permission expiry/restore, policy version reversal, rollback loss, and evidence restoration.
5. **Unseen domains:** two complete surface adapters absent from training and calibration.
6. **Unseen scope compositions:** pairwise and higher-order diagnostic interactions withheld from development.
7. **Near-equivalence ladder:** frozen epsilon grid with both divergent and same-label controls.
8. **Reversal sequences:** stale-authorization, detection-latency, and recovery tests.
9. **Evidence sufficiency:** resolvable, reducibly ambiguous, and irreducibly ambiguous banks.
10. **Adversarial nuisance tests:** label-swapped templates, identifier/style/order changes, prior shift, label permutation, canaries, and held-out nuisance generators.
11. **Coverage-collapse tests:** full risk-coverage frontiers and forced operating points that expose reject-all/escalate-all behavior.
12. **Worst-world tests:** catastrophic acceptance, worst mechanism/domain, and worst-decile loss.
13. **Metamorphic tests:** irrelevant interventions preserve labels; causal interventions flip them; scope-inappropriate diagnostics cannot acquire forbidden authority.
14. **Reproduction tests:** clean checkout, fresh environment, regenerated deterministic banks, rerun traces, and conclusion-preserving model tolerances.

### 5.4 Anti-overfitting and contamination controls

- Holdout mechanisms, logical forms, graph families, domain adapters, templates, and seed ranges are hashed before final tuning.
- Final case IDs contain no label, domain, mechanism, split, or policy-name information.
- Final text templates never appear verbatim in development or calibration.
- High-capacity leakage adversaries predict authorization, intervention, domain, mechanism, and split from P-only fields. Frozen permutation-derived chance bands govern release.
- Exact and approximate duplicate audits cover lexical, tabular, vector, structural, and graph similarity.
- No final-bank label prevalence is available for threshold setting.
- Early stopping uses development data only. Operating points use calibration data only.
- Hyperparameter spaces, trial counts, compute ceilings, and tie-breakers are pre-registered.
- The same training/calibration case IDs are used within each access profile.
- Raw-G methods receive semantically equivalent canonical tabular, sequence, and graph renderings from the same raw object; every lossy transformation is declared.
- All final-bank access is logged. Manual inspection quarantines affected cases unless pre-authorized for infrastructure audit.
- Scientific underperformance never permits retuning. Infrastructure repair requires invalidation, a documented diff, and complete affected-suite rerun.
- Sensitivity panels and Pareto neighborhoods prevent a conclusion from depending on one favorable threshold.
- Per-domain, per-mechanism, and tail results are reported before macro averages.

### 5.5 Complete registered mechanism inventory

Every mechanism in the specification is implemented, configured, unit-tested, instantiated across valid domains, and represented in the audit/report strata. Simple cases are theorem sanity checks and may not dominate claim-bearing banks.

| ID | Mechanism | Required implementation behavior |
|---|---|---|
| M01 | Authority mismatch | Hold prediction fixed while permission/delegation changes; produce valid `Accept <-> Reject` twins and revoke/restore sequences |
| M02 | Policy conflict | Compose active policy constraints independently of predictive support; test new logical forms and policy versions |
| M03 | Provenance dependence | Distinguish independent sources from shared/compromised sources using graph structure, not only counts |
| M04 | Evidence masking | Mask benign or harmful witnesses; route unresolved visible states to evidence-derived `Escalate` |
| M05 | Reversibility shift | Hold the candidate fixed while rollback availability or irreversibility changes authorization |
| M06 | Consequence escalation | Vary registered impact class/budget without leaking it into P-only fields |
| M07 | Temporal validity | Expire/restore permission, policy, exception, or evidence with stale-authorization and recovery tests |
| M08 | Shared premise corruption | Model correlated specialist support caused by one wrong latent premise and preserve DS-CF scope semantics |
| M09 | Counterfactual fragility | Evaluate registered alternate views and prevent unregistered view access |
| M10 | Constraint interaction | Require multi-fact composition, including at least one claim-bearing three-or-more-fact rule |
| M11 | Scope boundary | Present surface patterns outside a diagnostic's authorized context; ground truth must remain unchanged |
| M12 | Ambiguity class | Prove multiple terminal labels remain compatible with visible evidence and no permitted resolution action remains |

### 5.6 Complete MAVS ablation inventory

All ablations use the same Raw-G projection unless the ablation explicitly tests removal of governance information. Every ablation logs its changed component and preserves all unrelated code/configuration.

| ID | Condition | Registered causal question |
|---|---|---|
| A00 | Prediction-only MAVS | Are gains caused by governance information? |
| A01 | No provenance diagnostics | Does source/dependency evidence causally matter? |
| A02 | No policy diagnostics | Can authorization work without policy conflict/validity? |
| A03 | No authority diagnostics | Does permission/delegation remain necessary? |
| A04 | No evidence-availability diagnostics | Does hidden missingness force terminal errors? |
| A05 | No counterfactual fragility | Which alternate-view failures are missed? |
| A06 | No contextual weights | Does context-dependent specialist influence matter? |
| A07 | No mitigation | Does safe-consistency recall protection prevent FRR/escalation? |
| A08 | No hard veto | Are certified harmful cases accepted by threshold logic? |
| A09 | No escalation | What binary error is created by ambiguity? |
| A10 | No scope contracts | Does unbounded diagnostic authority cause scope leakage? |
| A11 | One fixed scalar | Can hand-designed scalar aggregation replace structure? |
| A12 | One learned scalar | Can high-capacity scalarization replace structure under equal information? |
| A13 | Flat Raw-G classifier | Does generic terminal function approximation suffice? |
| A14 | Original MAVS-GC | Does DS-CF repair the registered correlated-scope failure? |
| A15 | Full MAVS-GC + DS-CF | Reference fixed structured-governance condition |

### 5.7 Outcome tiers and claim boundaries

| Outcome | Objective condition | Maximum permitted interpretation |
|---|---|---|
| Integrity-valid negative | All integrity gates pass; H1 fails | Registered PEAD formulation did not establish prediction insufficiency |
| Paradigm support | Exact/near P-only frontier matches the registered lower bound and Raw-G escapes on blind families | Prediction-facing state is insufficient on the registered PEAD class |
| Generalized paradigm support | Paradigm effect persists across structural and domain holdouts | Effect covers the broad registered class, not one grammar |
| Architectural support | MAVS improves a pre-registered protected/scope/transfer frontier over the best equal-information flat Raw-G method | Structured MAVS governance adds value in the registered conditions |
| Strongest result | Generalized H1, architectural support, scalar-compression failure, and audit-perfect reproduction | Paradigm-level impact potential; not universal validity, deployment readiness, or zero risk |

Forbidden conclusions include universal prediction insufficiency, universal MAVS optimality, deployment certification, zero-risk claims, treating escalation as safety, or claiming official external benchmark execution when only an adaptation/projection was used.

### 5.8 Risk controls and mandatory stop conditions

| Risk ID | Risk | Preventive implementation | Stop or claim action |
|---|---|---|---|
| R1 | Trivial permission-bit benchmark | Composition, graph, time, scope, ambiguity, anti-triviality review | Fail the affected domain/release bank |
| R2 | Predictive leakage | Firewall, nuisance balance, canaries, multi-family adversaries | Quarantine and regenerate the bank |
| R3 | MAVS-coupled truth | Independent generators/evaluators and dependency audit | Invalidate the study version |
| R4 | Weak Raw-G baselines | GBDT, neural, graph, rule, validator, judge, scalar, ensemble | Prohibit architecture claim |
| R5 | Escalation/rejection collapse | Joint UAR/FRR/escalation/coverage and Pareto frontiers | Prohibit safety-success claim |
| R6 | No transfer | Structural plus two-domain holdouts | Limit claim to seen families |
| R7 | Label ambiguity bug | Dual engines and compatible-world proof | Block release |
| R8 | Post-freeze tuning | Signed freeze and access logs | Invalidate blind result |
| R9 | Compute inequity | Budget classes, matched IDs/trials, resource audit | Downgrade/prohibit fairness claim |
| R10 | Overloaded scope | Prioritize integrity and causal diversity; stage optional high-cost methods transparently | Cut non-primary extras before core gates |
| R11 | MAVS loses equal-information test | Retain and analyze the result | No MAVS architecture claim |
| R12 | Reproduction mismatch | Locks, manifests, tolerance policy, clean rebuild | Block reproducibility and affected release claims |

Execution stops immediately for any non-identical released exact twin, any released dual-label disagreement, forbidden method access, final-bank contamination, post-freeze tuning, missing headline trace lineage, claim-changing clean-reproduction failure, or evidence that truth generation depends on MAVS code.

## 6. Phase plan

### Phase 0 - Research charter, claim ledger, and execution controls

**Scope**

Freeze hypotheses H1/H2, claims C1-C6, nulls, non-claims, access profiles, outcome tiers, stop conditions, study versioning, paper boundary, negative-result policy, and the causal-rejection closure map. Establish `WorkPlan.md`/`Path.md` discipline and record the empty-repository/result baseline.

**Files**

- `WorkPlan.md`, `Path.md`, `CLAIMS.md`
- `configs/study/pead_main_v1.yaml`
- `configs/holdouts/holdout_registry_v1.yaml`
- `configs/metrics/protected_objective_v1.yaml`
- `README.md`, `CITATION.cff`, `pyproject.toml`

**Code and implementation method**

- Add typed configuration schemas and a schema-validation command.
- Encode every claim's required metrics, splits, audits, and forbidden wording.
- Encode the lexicographic operating-point objective: unsafe-acceptance constraint, then FRR, unnecessary escalation, resource cost, and frozen low-complexity tie-break.
- Add source-document hashes and base commit to the study manifest.

**Verification and completion gates**

- Every specification concern maps to at least one implementation control, executable audit, gate, and retained artifact.
- Schema validation passes.
- H1 and H2 are independently reportable.
- Negative scientific outcomes are explicitly publishable.
- Phase 0 evidence is recorded in `Path.md`.

### Phase 1 - Core immutable infrastructure and safe result hygiene

**Scope**

Implement typed records, canonical serialization, IDs, hashing, seed lineage, configuration loading, registries, immutable run layout, trace writing, and safe cleanup.

**Files**

- `src/pead/core/{types,ids,hashing,seeds,config,registry,runner,traces,paths}.py`
- `scripts/clear_results.py`, `scripts/validate_config.py`
- `tests/unit/test_{types,ids,hashing,seeds,config,paths,traces}.py`
- `tests/property/test_canonicalization.py`

**Code and implementation method**

- Use frozen dataclasses/Pydantic-compatible schemas with explicit schema versions.
- Canonicalize UTF-8 objects with sorted keys, frozen float quantization, sorted graph/set fields, and normalized candidate actions.
- Hash individual fields and complete records.
- Write append-only JSONL and Parquet-compatible traces with atomic finalization.
- Generate content-derived world, pair, sequence, run, and artifact IDs.
- Implement deletion guards using resolved absolute paths and manifest membership.

**Verification and completion gates**

- Duplicate deterministic runs produce byte-identical canonical records and IDs.
- Serialization order changes do not change canonical hashes.
- ID collision/property stress tests pass.
- Malformed or incomplete traces are rejected.
- Cleanup dry-run and adversarial path tests prove repository-root and out-of-results deletion impossible.

### Phase 2 - Independent authorization truth system

**Scope**

Implement the declarative policy DSL, parser, total deterministic evaluator, a separately coded procedural reference evaluator, compatible-world ambiguity logic, rule fixtures, and label agreement auditing.

**Files**

- `src/pead/labels/{dsl,parser,evaluator_dsl,evaluator_reference,ambiguity,reasons}.py`
- `configs/mechanisms/*.yaml`, `configs/policies/*.yaml`
- `scripts/audit_labels.py`
- `tests/unit/test_policy_dsl.py`
- `tests/property/test_label_*.py`
- `tests/metamorphic/test_authorization_invariants.py`

**Code and implementation method**

- DSL supports typed predicates, logical composition, temporal validity, graph conditions, consequence thresholds, evidence availability, and explicit ambiguity rules.
- Reference evaluator must not parse or import the DSL evaluator and receives only serialized latent facts.
- Both evaluators return label, reason class, satisfied/violated constraints, ambiguity basis, and rule lineage.
- Enumerate or safely sample compatible latent worlds to derive `Escalate`, never infer it from author preference.

**Verification and completion gates**

- `100%` dual-engine agreement on every released fixture/case.
- Oracle rule evaluator obtains `100%` on valid deterministic fixtures.
- Positive, negative, boundary, contradictory, and temporal fixtures exist for every rule family.
- Permission revocation/prohibition monotonicity and irrelevant-intervention invariance pass.
- Any disagreement quarantines the case and blocks dependent release.

### Phase 3 - Causal world registry, exact twins, and near twins

**Scope**

Implement the latent factorization, mechanism registry M01-M12, primary and reference generation paths, exact-twin construction, near-twin perturbations, nuisance controls, and leakage audits.

**Files**

- `src/pead/world/{schema,generator_primary,generator_reference,mechanisms,interventions,nuisance}.py`
- `src/pead/tracks/{exact,near}.py`
- `src/pead/audits/{equivalence,authorization,leakage}.py`
- `scripts/generate_bank.py`, `scripts/audit_equivalence.py`, `scripts/audit_leakage.py`
- `tests/property/test_twin_invariance.py`
- `tests/metamorphic/test_nuisance_invariance.py`

**Code and implementation method**

- Sample complete worlds before any method-specific transformation.
- Change exactly registered authorization parents outside `PredictiveState` while freezing predictive parents.
- Accept exact pairs only after field-level and byte-level equivalence, dual-label agreement, authorization divergence, and leakage checks.
- Implement the frozen epsilon grid `{0, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 5e-2, 1e-1}` after normalized-distance calibration.
- Generate balanced nuisance, label-swapped, irrelevant-intervention, and same-label controls.
- Keep the reference path free of shared authorization functions.

**Verification and completion gates**

- Development exact bank has `PEI == 1` and `ADI == 1`.
- Same-label controls preserve labels.
- Near pairs respect frozen distance metrics and do not reveal governance interventions.
- Linear, GBDT, sequence, graph, and nearest-neighbor leakage adversaries remain within frozen chance bands or the affected bank is repaired and regenerated.

### Phase 4 - Reversals, scope banks, and evidence-sufficiency boundaries

**Scope**

Implement governance-reversal sequences, Diagnostic Sciences scope contracts, positive/negative/boundary/out-of-scope/composition/nuisance banks, and the three evidence-sufficiency classes.

**Files**

- `src/pead/tracks/{reversal,scope,evidence_sufficiency}.py`
- `src/pead/core/scope_contract.py`
- `configs/tracks/{reversal,scope,evidence}.yaml`
- `tests/property/test_scope_safe_diagnostics.py`
- `tests/metamorphic/test_reversal_fidelity.py`
- `tests/unit/test_ambiguity_proof.py`

**Code and implementation method**

- Encode permission, policy, provenance, rollback, expiry, and evidence-restoration reversals with known change times.
- Generate scope-positive, matched-negative, boundary, adversarial out-of-scope, composition, and nuisance cases for every registered diagnostic.
- Compute ambiguity from compatible worlds and permitted resolution channels.
- Preserve the Paper 1/Paper 2 boundary: fixed methods represent unresolved evidence; adaptive acquisition is out of scope.

**Verification and completion gates**

- Reversal times and recovery states reproduce deterministically.
- Out-of-scope fixtures do not alter truth and cannot acquire unregistered terminal influence.
- Ambiguity proofs reproduce every `Escalate` label.
- Removing all permitted resolution channels converts reducible ambiguity to irreducible ambiguity, not arbitrary rejection.

### Phase 5 - Eight domain adapters and independent validity review

**Scope**

Implement tool execution, cyber response, multi-agent operations, retrieval/provenance, software deployment, financial approval proxy, clinical triage proxy, and content/policy safety adapters.

**Files**

- `src/pead/domains/{base,tool,cyber,multi_agent,retrieval,software,finance,clinical,content}.py`
- `configs/domains/*.yaml`
- `tests/integration/test_domain_contracts.py`
- `results/audits/<review_id>/domain_validity/*.json`

**Code and implementation method**

- All adapters implement the same task, candidate, mechanism, projection, and validation protocol.
- Each domain instantiates at least six mechanism families, including composition and ambiguity.
- At least two domains use graph-dependent authorization; two use temporal reversal; two use policy-grammar composition.
- Authorization may not be exposed as one obvious Raw-G Boolean.
- Apply domain-specific label-swapping and surface anti-shortcut transformations.

**Verification and completion gates**

- Cross-domain schema parity passes.
- Every domain meets anti-triviality minima.
- An evaluator who did not author an adapter reviews substantive meaning, projection defensibility, shortcuts, and bounded proxy claims.
- Two valid domains are sealed as complete domain holdouts before final tuning.

### Phase 6 - Projection layer, feature firewall, and equal-information renderings

**Scope**

Implement P-only, Raw-G, and Oracle-G projections; sealed inputs; static/runtime access enforcement; hidden canaries; and canonical tabular, sequence, and graph renderings.

**Files**

- `src/pead/projections/{predictive,raw_governance,oracle,firewall,tabular,sequence,graph}.py`
- `configs/access/{p_only,raw_g,oracle_g}.yaml`
- `src/pead/audits/access.py`
- `scripts/audit_access.py`, `scripts/audit_representation_parity.py`
- `tests/integration/test_access_profiles.py`
- `tests/blind_contract/test_hidden_truth_isolation.py`

**Code and implementation method**

- The projection package is the only package allowed to transform `WorldState` into method input.
- Return immutable objects with no back-reference to hidden state.
- Log field masks, transformations, truncation, missing-value behavior, and projection hashes for every decision.
- Static dependency scanning forbids method imports from hidden world, label, evaluator, and audit modules.
- Runtime proxy logging records forbidden access attempts and inserts randomized hidden canaries.
- A field-by-method matrix proves semantic Raw-G parity across representations.

**Verification and completion gates**

- No forbidden import, attribute access, label access, or canary correlation.
- Every representation can be traced back to the same Raw-G facts.
- A representation-oracle test proves the canonical renderings retain truth-relevant visible information.
- Any lossy transformation is declared and scientifically justified.

### Phase 7 - Baseline suite and common training harness

**Scope**

Implement all P-only and Raw-G baselines, a shared adapter interface, resource accounting, deterministic data loading, training, calibration, checkpointing, and pre-registered search.

**Files**

- `src/pead/baselines/{base,p_only,tabular,neural,sequence,graph,bayesian,policy,validator,judge,scalar,ensemble}.py`
- `src/pead/core/{training,calibration,budgets}.py`
- `configs/methods/{p_only_*,raw_g_*}.yaml`
- `scripts/train_suite.py`, `scripts/run_suite.py`, `scripts/audit_budget.py`
- `tests/integration/test_method_suite.py`

**Code and implementation method**

- Every method emits the same three-outcome `MethodDecision` schema.
- Freeze search spaces, trials, training IDs, early-stopping rules, calibration IDs, compute limits, and tie-breakers.
- Use matched training/calibration IDs inside each access profile.
- Record seeds, package versions, hardware, wall time, memory, calls/tokens, checkpoint hashes, and complete hyperparameter history.
- Fit calibration and terminal operating points only on the calibration split using the registered lexicographic objective.
- Threshold sweeps are reported but cannot replace the pre-registered headline operating point.

**Verification and completion gates**

- All 9 P-only and 12 Raw-G method families run through the same runner.
- GBDT, graph, scalar-risk, validator/policy, and ensemble comparators are not omitted.
- Training is reproducible within registered deterministic/tolerance rules.
- Budget parity and equal-information audits pass.
- No development or public-validation metric can change holdout definitions.

### Phase 8 - Frozen MAVS-GC, DS-CF, and architectural ablations

**Scope**

Integrate original MAVS-GC, MAVS-GC + DS-CF, prediction-only MAVS, fixed and learned scalarized variants, and ablations A00-A15.

**Files**

- `src/pead/mavs/{adapter,governed_consensus,ds_cf,profiles,scalarization,ablations,traces}.py`
- `configs/methods/mavs_*.yaml`
- `tests/unit/test_ds_cf_invariants.py`
- `tests/integration/test_mavs_adapter.py`
- `tests/property/test_mavs_scope_and_veto.py`

**Code and implementation method**

- Keep specialist answer evidence separate from diagnostic condition evidence through authorization.
- Trace supports, diagnostic vector, severity, contextual weights, mitigation, threshold, veto, ambiguity, consensus, and terminal decision.
- DS-CF separately represents correlation presence, harmful correlation, safe consistency, missing evidence, policy conflict, overconfidence, and counterfactual fragility.
- Raw correlation alone cannot hard-veto; safe consistency cannot override a certified hard veto; mitigation remains bounded.
- All ablations retain identical Raw-G access. Learned scalarization uses the same training/calibration data and budget policy as comparable Raw-G learners.
- No MAVS module is importable from generators or label engines.

**Verification and completion gates**

- Original and DS-CF profiles are frozen and versioned.
- Exhaustive/discretized rule-fidelity tests find zero registered veto violations.
- Scope, ambiguity, mitigation, monotonicity, and trace-completeness tests pass.
- The central scalar-compression test is executable on structural and domain holdouts.

### Phase 9 - Metrics, statistics, audits, failure cards, and report builders

**Scope**

Implement integrity, paradigm, protected-decision, Diagnostic Sciences, sequential, causal, statistical, and claim-eligibility metrics, plus the complete audit suite and report traceability.

**Files**

- `src/pead/metrics/{paradigm,protected,causal,scope,sequential,statistics}.py`
- `src/pead/audits/{equivalence,authorization,leakage,access,holdouts,budget,traces,abstention,manifest,reproduction,claims,failure_retention,non_triviality}.py`
- `src/pead/reports/{tables,figures,failure_cards,claim_ledger}.py`
- `scripts/{audit_all,build_report}.py`
- `tests/unit/test_metrics_*.py`
- `tests/integration/test_master_audit.py`

**Code and implementation method**

- Compute LBG, GIG, GAG, AFA, UAR, FRR, escalation, terminal coverage, forced-certainty error, unnecessary escalation, catastrophic acceptance, worst-world, worst-decile, scope influence, redundancy, instability, and composition.
- Use paired world/pair/sequence analysis; cluster bootstrap by evaluation unit and by mechanism/domain for generalization.
- Use exact binomial intervals for zero counts.
- Report per-domain/per-mechanism effects before macro averages.
- Apply multiple-comparison correction to secondary ablation families.
- Generate immutable failure cards for every protected error, scope anomaly, label conflict, access violation, invalidation, and reproduction mismatch.

**Verification and completion gates**

- Metric unit tests include edge cases, empty denominators, zero counts, and known analytic fixtures.
- Master audit returns nonzero for every release-blocking fixture.
- Report builder cannot suppress failed methods/cases or emit an ineligible claim.
- Every table/figure cell resolves to processed data, raw traces, config, and audit IDs.

### Phase 10 - Development banks, training, calibration, and public validation

**Scope**

Generate the canonical-scale open banks, train every trainable method, run fixed methods, select operating points, perform public validation, power/effect-size checks, and create a freeze candidate.

**Files and artifacts**

- `banks/development/`, `banks/calibration/`, `banks/public_validation/`
- `results/raw/<dev_run_id>/`
- `results/processed/<dev_run_id>/`
- `results/audits/<dev_run_id>/`
- `results/reports/<dev_run_id>/`
- `manifests/freeze_candidate_v1.json`

**Code and implementation method**

- Target canonical volumes: 16,000 exact pairs, 8,000 near pairs, 4,000 reversal sequences, 22,400 scope cases, 12,000 evidence-sufficiency cases, and at least 20% negative controls, subject to logged resource staging.
- Infrastructure defects may be fixed; each fix invalidates and regenerates affected artifacts.
- Scientific underperformance is retained.
- Select thresholds on calibration only.
- Freeze report templates, statistical procedures, minimum effect sizes, and primary architecture-specific advantage before the blind run.

**Verification and completion gates**

- No sealed/final-bank access occurs.
- All public-validation integrity gates pass.
- Leakage, duplicate, budget, parity, non-triviality, and abstention audits pass.
- Power/effect-size report justifies claim-bearing sample sizes.
- Freeze candidate includes every claim-relevant file hash.

### Phase 11 - Sealed structural/domain banks and signed study freeze

**Scope**

Finalize structurally different holdouts, generate or package two unseen domains, seal blind content, sign manifests, and prove contamination isolation.

**Files and artifacts**

- `banks/sealed/structural/`
- `banks/sealed/domains/`
- `banks/sealed/final_blind/`
- `configs/holdouts/final_holdouts_v1.yaml`
- `manifests/freeze_manifest.json`
- `manifests/blind_bank_manifest.json`
- `results/audits/<freeze_id>/holdout_audit.json`

**Code and implementation method**

- Build unseen mechanism compositions, logical policy forms, graph topologies, intervention types, nuisance families, and scope interactions with code paths/configs unavailable to training.
- Cross these structures with two complete unseen surface domains.
- Hide labels, mechanism IDs, domain IDs, and seed lineage from method processes.
- Sign hashes for code, configs, environment, generators, truth engines, projections, metrics, methods, hyperparameters, templates, and banks.
- Lock method code and operating points.

**Verification and completion gates**

- Nearest-neighbor/structural/graph duplicate audit finds no prohibited overlap.
- Training, calibration, and final template/grammar/topology registries are disjoint by construction and by hash.
- Blind-contract tests prove the final bank cannot be read before unlock.
- Freeze manifest is complete and signed.
- Any post-freeze claim-relevant change creates a new study version.

### Phase 12 - One-pass blind evaluation and brutal generalization audit

**Scope**

Unlock the sealed bank, execute all valid methods once, audit before aggregate inspection, classify incidents, and retain all scientific outcomes.

**Files and artifacts**

- `results/raw/<blind_run_id>/`
- `results/processed/<blind_run_id>/`
- `results/audits/<blind_run_id>/`
- `results/reports/<blind_run_id>/`
- `results/manifests/<blind_run_id>/`
- `Path.md` incident and adjudication entries

**Code and implementation method**

- Verify signed freeze and bank seals before execution.
- Commit every decision before hidden-label reveal.
- Execute matched methods on exact, near, reversal, scope, evidence, structural, and domain holdouts.
- Run leakage, access, trace, budget, holdout, abstention, failure-retention, non-triviality, and manifest audits before aggregate author inspection where practical.
- Classify events as infrastructure, contamination, or scientific. Only infrastructure defects permit a documented invalidation and complete affected-suite rerun.

**Verification and completion gates**

- No post-freeze parameter, feature, threshold, or representation changes.
- Every release-blocking audit passes.
- P-only lower-bound/error-coverage results, Raw-G escape, MAVS-vs-Raw-G, scalar compression, scope leakage, reversal fidelity, ambiguity, domain transfer, and worst-world results are all reported.
- Every failure and negative outcome is retained.
- Invalidated run IDs remain referenced and cannot be mistaken for valid release runs.

### Phase 13 - Evidence package, clean reproduction, and bounded release

**Scope**

Build the public evidence package, regenerate all tables/figures, run clean-checkout reproduction, generate claim eligibility, and perform the final causal-rejection and completeness audits.

**Files and artifacts**

- `CLAIM_ELIGIBILITY.md`, `REPRODUCE.md`
- `results/reports/<release_run_id>/`
- `results/audits/<release_run_id>/master_audit.json`
- `manifests/final_release.json`
- public case banks/traces according to the release policy
- failure cards, invalidation ledger, and artifact-to-claim map

**Code and implementation method**

- Rebuild deterministic banks and processed results from a clean checkout and locked environment.
- Distinguish exact hashes from frozen model-output tolerance checks.
- Generate claim language automatically from passed outcome tiers.
- Package code, configs, environment lock, manifests, banks, traces, processed results, audits, failures, claim ledger, and regeneration commands.

**Verification and completion gates**

- Every headline result resolves to raw traces and passed audits.
- Clean reproduction matches signed expectations and preserves all conclusions.
- All failed methods, errors, quarantines, and negative results remain visible.
- Causal-rejection closure and final delivery checklist pass.
- `Path.md` records the final run identity, reproduction identity, deviations, and release verdict.

## 7. Phase dependency and reopening rules

```text
0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12 -> 13
         \---------------- truth ----------------/     \-- freeze --/ \-- release --/
```

- Phase 2 truth defects reopen Phases 2-13.
- Phase 3/4 bank defects reopen the affected generator phase and Phases 10-13.
- Phase 5 domain defects reopen the affected adapter, holdout selection, and Phases 10-13.
- Phase 6 access defects invalidate affected method results and reopen Phases 6-13.
- Phase 7/8 method defects after freeze require a new study version unless they are proven interface-only infrastructure defects and the complete affected blind suite is invalidated and rerun.
- Phase 9 metric/audit defects reopen every claim that depends on them.
- Any Phase 11 contamination or post-freeze tuning invalidates the generalization claim and blind run.
- A Phase 13 reproduction mismatch blocks the release claim even if scientific results are favorable.

## 8. Canonical commands

Commands will be finalized against the implemented CLI, but the required interfaces are:

```bash
python scripts/clear_results.py --scope pead --dry-run
python scripts/clear_results.py --scope pead --confirm
python scripts/validate_config.py --study configs/study/pead_main_v1.yaml
python -m pytest tests/unit tests/property tests/metamorphic -q
python -m pytest tests/integration tests/blind_contract -q
python -m compileall -q src scripts tests
python scripts/generate_bank.py --study configs/study/pead_main_v1.yaml --split development
python scripts/train_suite.py --study configs/study/pead_main_v1.yaml
python scripts/run_suite.py --study configs/study/pead_main_v1.yaml --split public_validation
python scripts/freeze_study.py --study configs/study/pead_main_v1.yaml
python scripts/run_blind_suite.py --freeze-manifest manifests/freeze_manifest.json
python scripts/audit_all.py --study configs/study/pead_main_v1.yaml --run-id <RUN_ID> --strict
python scripts/build_report.py --run-id <RUN_ID>
python scripts/reproduce_all.py --manifest manifests/final_release.json
```

## 9. Specification coverage matrix

This matrix prevents omissions. A phase may not be closed until the corresponding specification obligations have executable evidence.

| Specification area | Implementing phases |
|---|---|
| Document control, executive contract, claim decomposition, nulls, non-claims | 0, 13 |
| Formal hypothesis, exact equivalence, lower bound, deferral frontier, near equivalence | 0, 3, 9, 12 |
| Causal rejection closure model | 0, 9, 13 |
| Architecture and trust boundaries | 1, 2, 3, 6, 9 |
| Repository layout and WorkPlan/Path discipline | 0, 1, all phases |
| Core records, visibility, canonicalization, traces | 1, 6 |
| Mechanisms M01-M12, twin generation, nuisance controls, independent paths | 3 |
| DSL, reference evaluator, ambiguity truth, label agreement | 2 |
| Tracks I-V | 3, 4, 9, 12 |
| Eight domain adapters and anti-triviality review | 5, 11, 12 |
| P-only/Raw-G/Oracle-G ladder, firewall, resource parity | 6, 7, 9 |
| P-only, Raw-G, MAVS, Oracle method suites | 7, 8 |
| Training, tuning, calibration, holdouts, freeze, contamination, adjudication | 7, 10, 11, 12 |
| Integrity, paradigm, protected, Diagnostic Sciences, sequential, statistical metrics | 9 |
| MAVS ablations A00-A15 and scalar reduction | 8, 12 |
| Canonical experiment scale and compute budgets | 7, 10 |
| Automated audits, adversaries, parity and non-triviality | 3, 6, 7, 9, 10-13 |
| Reproducibility and evidence package | 1, 9, 13 |
| Outcome/claim ledger and Paper 1/Paper 2 boundary | 0, 4, 9, 13 |
| Risk register and stop conditions | 0, 9, 12, 13 |
| Final completeness and revision record | 13 |
| Appendix A data dictionaries | 1, 4, 6 |
| Appendix B blind/lower-bound/claim algorithms | 9, 11, 12 |
| Appendix C complete test inventory | 1-13 |
| Appendix D artifact manifest and final checklist | 10-13 |

## 10. Definition of done

The project is complete only when:

1. All phases are closed in `Path.md` with commands and evidence.
2. No mandatory specification item is marked prose-only.
3. All integrity gates pass on the release run.
4. Claim-bearing benchmarks are structurally and domain-wise different from training and calibration.
5. Every trained model has been evaluated on the complete applicable independent holdout battery.
6. H1 and H2 are reported separately and honestly, including negative outcomes.
7. Every number, failure, deviation, invalidation, and artifact is traceable.
8. A clean checkout reproduces deterministic artifacts and conclusion-preserving model results.
9. Only the new, manifest-identified PEAD release results are present in the release package.
